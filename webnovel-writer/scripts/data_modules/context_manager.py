#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContextManager - assemble context packs with weighted priorities.
"""
from __future__ import annotations

import json
import re
import sys
import logging
from pathlib import Path

from .runtime_compat import enable_windows_utf8_stdio
from typing import Any, Dict, List, Optional
from .agent_protocol import serialize_context_payload, write_protocol_json

try:
    from chapter_outline_loader import (
        is_missing_chapter_outline,
        load_chapter_outline,
        validate_chapter_contract,
    )
except ImportError:  # pragma: no cover
    from scripts.chapter_outline_loader import (
        is_missing_chapter_outline,
        load_chapter_outline,
        validate_chapter_contract,
    )

from .config import get_config
from .index_manager import IndexManager, WritingChecklistScoreMeta
from .context_ranker import ContextRanker
from .snapshot_manager import SnapshotManager, SnapshotVersionMismatch
from .context_weights import (
    DEFAULT_TEMPLATE as CONTEXT_DEFAULT_TEMPLATE,
    TEMPLATE_WEIGHTS as CONTEXT_TEMPLATE_WEIGHTS,
    TEMPLATE_WEIGHTS_DYNAMIC_DEFAULT as CONTEXT_TEMPLATE_WEIGHTS_DYNAMIC_DEFAULT,
)
from .genre_aliases import normalize_genre_token, to_profile_key
from .genre_profile_builder import (
    build_composite_genre_hints,
    extract_genre_section,
    extract_markdown_refs,
    parse_genre_tokens,
)
from .state_validator import memory_tier_rank, normalize_story_memory, normalize_foreshadowing_tier
from .writing_guidance_builder import (
    build_methodology_guidance_items,
    build_methodology_strategy_card,
    build_guidance_items,
    build_writing_checklist,
    is_checklist_item_completed,
)
from .technique_blueprint import (
    ensure_story_technique_blueprint,
    load_project_memory,
    build_chapter_technique_plan,
)


logger = logging.getLogger(__name__)


def _friendly_context_error(error: Exception) -> str:
    message = str(error)
    hints = ["请检查项目结构与依赖文件。"]

    if "缺少可用大纲" in message:
        hints = [
            "请在 `大纲/` 下补齐对应章节大纲后重试。",
            "可先执行 `webnovel.py extract-context --chapter N --format text` 做写前自检。",
        ]
    elif "缺少关键项" in message or "最小章节契约" in message:
        hints = [
            "请补齐最小章节契约：目标/冲突/动作/结果/代价/钩子。",
            "建议采用 `字段: 内容` 的结构化写法，避免解析失败。",
        ]
    elif "状态变化" in message:
        hints = [
            "请在章纲或任务书中补充可追踪变化（资源/关系/认知/位置/战力）。",
            "若当前为试写阶段，可临时降低 `context_min_state_changes_per_chapter`。",
        ]

    return f"{message} | 修复建议：{'；'.join(hints)}"


class ContextManager:
    DEFAULT_TEMPLATE = CONTEXT_DEFAULT_TEMPLATE
    TEMPLATE_WEIGHTS = CONTEXT_TEMPLATE_WEIGHTS
    TEMPLATE_WEIGHTS_DYNAMIC = CONTEXT_TEMPLATE_WEIGHTS_DYNAMIC_DEFAULT
    EXTRA_SECTIONS = {
        "story_skeleton",
        "story_recall",
        "chapter_intent",
        "chapter_technique_plan",
        "memory",
        "preferences",
        "alerts",
        "reader_signal",
        "genre_profile",
        "writing_guidance",
        "story_technique_blueprint",
    }
    SECTION_ORDER = [
        "core",
        "scene",
        "global",
        "reader_signal",
        "genre_profile",
        "story_technique_blueprint",
        "writing_guidance",
        "chapter_technique_plan",
        "chapter_intent",
        "story_skeleton",
        "story_recall",
        "memory",
        "preferences",
        "alerts",
    ]
    SUMMARY_SECTION_RE = re.compile(r"##\s*剧情摘要\s*\r?\n(.*?)(?=\r?\n##|\Z)", re.DOTALL)

    def __init__(self, config=None, snapshot_manager: Optional[SnapshotManager] = None):
        self.config = config or get_config()
        self.snapshot_manager = snapshot_manager or SnapshotManager(self.config)
        self.index_manager = IndexManager(self.config)
        self.context_ranker = ContextRanker(self.config)

    def _story_memory_path(self) -> Path:
        return getattr(self.config, "story_memory_file", self.config.webnovel_dir / "memory" / "story_memory.json")

    def _project_memory_path(self) -> Path:
        return self.config.project_memory_file

    def _story_technique_blueprint_path(self) -> Path:
        return self.config.story_technique_blueprint_file

    def _author_intent_path(self) -> Path:
        return self.config.author_intent_file

    def _current_focus_path(self) -> Path:
        return self.config.current_focus_file

    def _chapter_intent_path(self, chapter: int) -> Path:
        return self.config.chapter_intent_dir / f"chapter-{int(chapter):04d}.json"

    def _chapter_technique_plan_path(self, chapter: int) -> Path:
        return self.config.chapter_technique_plan_dir / f"chapter-{int(chapter):04d}.json"

    def _file_mtime_ns(self, path: Path) -> int:
        try:
            return int(path.stat().st_mtime_ns)
        except Exception:
            return 0

    def _load_story_memory_bundle(self) -> Dict[str, Any]:
        """加载故事记忆层，返回 content/meta 两部分。"""
        path = self._story_memory_path()
        if not path.exists():
            return {"content": {}, "meta": {"mtime_ns": 0}}

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"content": {}, "meta": {"mtime_ns": self._file_mtime_ns(path)}}

        if not isinstance(raw, dict):
            return {"content": {}, "meta": {"mtime_ns": self._file_mtime_ns(path)}}

        raw = normalize_story_memory(raw)

        meta = {
            "version": str(raw.get("version", "")),
            "last_consolidated_chapter": int(raw.get("last_consolidated_chapter") or 0),
            "last_consolidated_at": str(raw.get("last_consolidated_at", "")),
            "mtime_ns": self._file_mtime_ns(path),
        }
        return {"content": raw, "meta": meta}

    def _load_project_memory_bundle(self) -> Dict[str, Any]:
        path = self._project_memory_path()
        raw = load_project_memory(path)

        return {
            "content": raw,
            "meta": {"mtime_ns": self._file_mtime_ns(path)},
        }

    def _load_story_technique_blueprint_bundle(
        self,
        state: Optional[Dict[str, Any]] = None,
        project_memory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        path = self._story_technique_blueprint_path()
        payload = ensure_story_technique_blueprint(
            config=self.config,
            state=state or self._load_state(),
            project_memory=project_memory or load_project_memory(self._project_memory_path()),
        )
        return {
            "content": payload,
            "meta": {
                "mtime_ns": self._file_mtime_ns(path),
                "version": str(payload.get("version") or ""),
            },
        }

    def _load_control_object(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return dict(raw) if isinstance(raw, dict) else {}

    def _context_dependency_meta(
        self,
        story_memory_bundle: Optional[Dict[str, Any]] = None,
        project_memory_bundle: Optional[Dict[str, Any]] = None,
        story_technique_blueprint_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        story_memory_bundle = story_memory_bundle or self._load_story_memory_bundle()
        project_memory_bundle = project_memory_bundle or self._load_project_memory_bundle()
        story_technique_blueprint_bundle = story_technique_blueprint_bundle or self._load_story_technique_blueprint_bundle()

        story_meta = dict((story_memory_bundle or {}).get("meta") or {})
        project_meta = dict((project_memory_bundle or {}).get("meta") or {})
        technique_meta = dict((story_technique_blueprint_bundle or {}).get("meta") or {})
        return {
            "story_memory_version": story_meta.get("version", ""),
            "story_memory_last_consolidated_chapter": story_meta.get("last_consolidated_chapter", 0),
            "story_memory_last_consolidated_at": story_meta.get("last_consolidated_at", ""),
            "story_memory_mtime_ns": story_meta.get("mtime_ns", 0),
            "state_mtime_ns": self._file_mtime_ns(self.config.state_file),
            "project_memory_mtime_ns": project_meta.get("mtime_ns", 0),
            "story_technique_blueprint_mtime_ns": technique_meta.get("mtime_ns", 0),
            "story_technique_blueprint_version": technique_meta.get("version", ""),
        }

    def _is_snapshot_compatible(
        self,
        cached: Dict[str, Any],
        template: str,
        story_memory_meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """判断快照是否可用于当前模板。"""
        if not isinstance(cached, dict):
            return False

        meta = cached.get("meta")
        if not isinstance(meta, dict):
            # 兼容旧快照：未记录 template 时仅允许默认模板复用
            return template == self.DEFAULT_TEMPLATE and not story_memory_meta

        cached_template = meta.get("template")
        if not isinstance(cached_template, str):
            return template == self.DEFAULT_TEMPLATE and not story_memory_meta

        if cached_template != template:
            return False

        if story_memory_meta:
            cached_story_version = str(meta.get("story_memory_version", ""))
            cached_story_chapter = int(meta.get("story_memory_last_consolidated_chapter") or 0)
            cached_story_mtime = int(meta.get("story_memory_mtime_ns") or 0)
            cached_state_mtime = int(meta.get("state_mtime_ns") or 0)
            cached_project_mtime = int(meta.get("project_memory_mtime_ns") or 0)
            cached_blueprint_mtime = int(meta.get("story_technique_blueprint_mtime_ns") or 0)
            cached_blueprint_version = str(meta.get("story_technique_blueprint_version") or "")
            current_story_version = str(story_memory_meta.get("version", ""))
            current_story_chapter = int(story_memory_meta.get("last_consolidated_chapter") or 0)
            current_story_mtime = int(story_memory_meta.get("mtime_ns") or 0)
            current_state_mtime = self._file_mtime_ns(self.config.state_file)
            current_project_mtime = self._file_mtime_ns(self._project_memory_path())
            current_blueprint_bundle = self._load_story_technique_blueprint_bundle()
            current_blueprint_mtime = int((current_blueprint_bundle.get("meta") or {}).get("mtime_ns") or 0)
            current_blueprint_version = str((current_blueprint_bundle.get("meta") or {}).get("version") or "")
            if cached_story_version != current_story_version:
                return False
            if cached_story_chapter != current_story_chapter:
                return False
            if cached_story_mtime != current_story_mtime:
                return False
            if cached_state_mtime != current_state_mtime:
                return False
            if cached_project_mtime != current_project_mtime:
                return False
            if cached_blueprint_mtime != current_blueprint_mtime:
                return False
            if cached_blueprint_version != current_blueprint_version:
                return False

        return True

    def build_context(
        self,
        chapter: int,
        template: str | None = None,
        use_snapshot: bool = True,
        save_snapshot: bool = True,
        max_chars: Optional[int] = None,
    ) -> Dict[str, Any]:
        template = template or self.DEFAULT_TEMPLATE
        self._active_template = template
        if template not in self.TEMPLATE_WEIGHTS:
            template = self.DEFAULT_TEMPLATE
            self._active_template = template

        story_memory_bundle = self._load_story_memory_bundle()
        project_memory_bundle = self._load_project_memory_bundle()
        story_technique_blueprint_bundle = self._load_story_technique_blueprint_bundle(
            project_memory=project_memory_bundle.get("content") or {},
        )
        story_memory_meta = self._context_dependency_meta(
            story_memory_bundle=story_memory_bundle,
            project_memory_bundle=project_memory_bundle,
            story_technique_blueprint_bundle=story_technique_blueprint_bundle,
        )

        if use_snapshot:
            try:
                cached = self.snapshot_manager.load_snapshot(chapter)
                if cached and self._is_snapshot_compatible(cached, template, story_memory_meta):
                    cached_payload = cached.get("payload", cached)
                    if isinstance(cached_payload, dict):
                        meta = cached_payload.setdefault("meta", {})
                        if isinstance(meta, dict):
                            meta["snapshot_used"] = True
                    return cached_payload
            except SnapshotVersionMismatch:
                # Snapshot incompatible; rebuild below.
                pass

        pack = self._build_pack(
            chapter,
            story_memory_bundle=story_memory_bundle,
            project_memory_bundle=project_memory_bundle,
        )
        if getattr(self.config, "context_ranker_enabled", True):
            pack = self.context_ranker.rank_pack(pack, chapter)
        assembled = self.assemble_context(pack, template=template, max_chars=max_chars)

        if save_snapshot:
            meta = {"template": template}
            meta.update(story_memory_meta)
            self.snapshot_manager.save_snapshot(chapter, assembled, meta=meta)

        return assembled

    def assemble_context(
        self,
        pack: Dict[str, Any],
        template: str = DEFAULT_TEMPLATE,
        max_chars: Optional[int] = None,
    ) -> Dict[str, Any]:
        chapter = int((pack.get("meta") or {}).get("chapter") or 0)
        weights = self._resolve_template_weights(template=template, chapter=chapter)
        max_chars = max_chars or 8000
        extra_budget = int(self.config.context_extra_section_budget or 0)

        sections = {}
        for section_name in self.SECTION_ORDER:
            if section_name in pack:
                sections[section_name] = pack[section_name]

        assembled: Dict[str, Any] = {"meta": pack.get("meta", {}), "sections": {}}
        for name, content in sections.items():
            weight = weights.get(name, 0.0)
            if weight > 0:
                budget = int(max_chars * weight)
            elif name in self.EXTRA_SECTIONS and extra_budget > 0:
                budget = extra_budget
            else:
                budget = None
            text = self._compact_json_text(content, budget)
            assembled["sections"][name] = {"content": content, "text": text, "budget": budget}

        assembled["template"] = template
        assembled["weights"] = weights
        assembled.setdefault("meta", {})["snapshot_used"] = False
        if chapter > 0:
            assembled.setdefault("meta", {})["context_weight_stage"] = self._resolve_context_stage(chapter)
        return assembled

    def filter_invalid_items(self, items: List[Dict[str, Any]], source_type: str, id_key: str) -> List[Dict[str, Any]]:
        confirmed = self.index_manager.get_invalid_ids(source_type, status="confirmed")
        pending = self.index_manager.get_invalid_ids(source_type, status="pending")
        result = []
        for item in items:
            item_id = str(item.get(id_key, ""))
            if item_id in confirmed:
                continue
            if item_id in pending:
                item = dict(item)
                item["warning"] = "pending_invalid"
            result.append(item)
        return result

    def apply_confidence_filter(self, items: List[Dict[str, Any]], min_confidence: float) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for item in items:
            conf = item.get("confidence")
            if conf is None or conf >= min_confidence:
                filtered.append(item)
        return filtered

    def _build_pack(
        self,
        chapter: int,
        story_memory_bundle: Optional[Dict[str, Any]] = None,
        project_memory_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        state = self._load_state()
        story_memory_bundle = story_memory_bundle or self._load_story_memory_bundle()
        project_memory_bundle = project_memory_bundle or self._load_project_memory_bundle()
        project_memory = project_memory_bundle.get("content") or self._load_json_optional(self._project_memory_path())
        story_technique_blueprint_bundle = self._load_story_technique_blueprint_bundle(
            state=state,
            project_memory=project_memory,
        )
        story_technique_blueprint = dict(story_technique_blueprint_bundle.get("content") or {})
        story_memory_content = dict(story_memory_bundle.get("content") or {})
        story_memory_meta = dict(story_memory_bundle.get("meta") or {})
        chapter_outline = self._load_outline(chapter)
        story_recall = self._build_story_recall(chapter, chapter_outline, state, story_memory_content, story_memory_meta)
        author_intent = self._load_control_object(self._author_intent_path())
        current_focus = self._load_control_object(self._current_focus_path())
        core = {
            "chapter_outline": chapter_outline,
            "protagonist_snapshot": state.get("protagonist_state", {}),
            "recent_summaries": self._load_recent_summaries(
                chapter,
                window=self.config.context_recent_summaries_window,
            ),
            "recent_meta": self._load_recent_meta(
                state,
                chapter,
                window=self.config.context_recent_meta_window,
            ),
        }

        scene = {
            "location_context": state.get("protagonist_state", {}).get("location", {}),
            "appearing_characters": self._load_recent_appearances(
                limit=self.config.context_max_appearing_characters,
            ),
        }
        scene["appearing_characters"] = self.filter_invalid_items(
            scene["appearing_characters"], source_type="entity", id_key="entity_id"
        )

        global_ctx = {
            "worldview_skeleton": self._load_setting("世界观"),
            "power_system_skeleton": self._load_setting("力量体系"),
            "style_contract_ref": self._load_setting("风格契约"),
        }

        preferences = self._load_json_optional(self.config.webnovel_dir / "preferences.json")
        memory = {
            "project_memory": project_memory,
            "project_memory_meta": dict(project_memory_bundle.get("meta") or {}),
            "story_memory": story_memory_content,
            "story_memory_meta": story_memory_meta,
            "story_technique_blueprint": story_technique_blueprint,
            "story_technique_blueprint_meta": dict(story_technique_blueprint_bundle.get("meta") or {}),
            "author_intent": author_intent,
            "current_focus": current_focus,
        }
        story_skeleton = self._load_story_skeleton(chapter)
        alert_slice = max(0, int(self.config.context_alerts_slice))
        reader_signal = self._load_reader_signal(chapter)
        genre_profile = self._load_genre_profile(state)
        writing_guidance = self._build_writing_guidance(
            chapter,
            reader_signal,
            genre_profile,
            project_memory=project_memory,
            story_technique_blueprint=story_technique_blueprint,
        )
        current_focus = self._resolve_current_focus(
            chapter=chapter,
            chapter_outline=chapter_outline,
            story_recall=story_recall,
            state=state,
            author_intent=author_intent,
            current_focus=current_focus,
            writing_guidance=writing_guidance,
        )
        memory["current_focus"] = current_focus
        chapter_intent = self._build_chapter_intent(
            chapter=chapter,
            chapter_outline=chapter_outline,
            story_recall=story_recall,
            state=state,
            story_memory=story_memory_content,
            author_intent=author_intent,
            current_focus=current_focus,
            writing_guidance=writing_guidance,
        )
        self._validate_chapter_contract(chapter, chapter_intent)
        self._validate_state_change_minimum(chapter, story_recall)

        chapter_technique_plan = self._build_chapter_technique_plan(
            chapter=chapter,
            chapter_outline=chapter_outline,
            reader_signal=reader_signal,
            genre_profile=genre_profile,
            story_recall=story_recall,
            chapter_intent=chapter_intent,
            writing_guidance=writing_guidance,
            story_technique_blueprint=story_technique_blueprint,
            project_memory=project_memory,
        )

        return {
            "meta": {"chapter": chapter},
            "core": core,
            "scene": scene,
            "global": global_ctx,
            "reader_signal": reader_signal,
            "genre_profile": genre_profile,
            "story_technique_blueprint": story_technique_blueprint,
            "writing_guidance": writing_guidance,
            "chapter_technique_plan": chapter_technique_plan,
            "chapter_intent": chapter_intent,
            "story_skeleton": story_skeleton,
            "story_recall": story_recall,
            "preferences": preferences,
            "memory": memory,
            "alerts": {
                "disambiguation_warnings": (
                    state.get("disambiguation_warnings", [])[-alert_slice:] if alert_slice else []
                ),
                "disambiguation_pending": (
                    state.get("disambiguation_pending", [])[-alert_slice:] if alert_slice else []
                ),
            },
        }

    def _load_reader_signal(self, chapter: int) -> Dict[str, Any]:
        if not getattr(self.config, "context_reader_signal_enabled", True):
            return {}

        recent_limit = max(1, int(getattr(self.config, "context_reader_signal_recent_limit", 5)))
        pattern_window = max(1, int(getattr(self.config, "context_reader_signal_window_chapters", 20)))
        review_window = max(1, int(getattr(self.config, "context_reader_signal_review_window", 5)))
        include_debt = bool(getattr(self.config, "context_reader_signal_include_debt", False))

        recent_power = self.index_manager.get_recent_reading_power(limit=recent_limit)
        pattern_stats = self.index_manager.get_pattern_usage_stats(last_n_chapters=pattern_window)
        hook_stats = self.index_manager.get_hook_type_stats(last_n_chapters=pattern_window)
        review_trend = self.index_manager.get_review_trend_stats(last_n=review_window)

        low_score_ranges: List[Dict[str, Any]] = []
        for row in review_trend.get("recent_ranges", []):
            score = row.get("overall_score")
            if isinstance(score, (int, float)) and float(score) < 75:
                low_score_ranges.append(
                    {
                        "start_chapter": row.get("start_chapter"),
                        "end_chapter": row.get("end_chapter"),
                        "overall_score": score,
                    }
                )

        signal: Dict[str, Any] = {
            "recent_reading_power": recent_power,
            "pattern_usage": pattern_stats,
            "hook_type_usage": hook_stats,
            "review_trend": review_trend,
            "low_score_ranges": low_score_ranges,
            "next_chapter": chapter,
        }

        if include_debt:
            signal["debt_summary"] = self.index_manager.get_debt_summary()

        return signal

    def _load_genre_profile(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if not getattr(self.config, "context_genre_profile_enabled", True):
            return {}

        fallback = str(getattr(self.config, "context_genre_profile_fallback", "shuangwen") or "shuangwen")
        project = state.get("project") or {}
        project_info = state.get("project_info") or {}
        genre_raw = str(project.get("genre") or project_info.get("genre") or fallback)
        genres = self._parse_genre_tokens(genre_raw)
        if not genres:
            genres = [fallback]
        max_genres = max(1, int(getattr(self.config, "context_genre_profile_max_genres", 2)))
        genres = genres[:max_genres]

        primary_genre = genres[0]
        secondary_genres = genres[1:]
        composite = len(genres) > 1
        profile_path = self.config.project_root / ".claude" / "references" / "genre-profiles.md"
        taxonomy_path = self.config.project_root / ".claude" / "references" / "reading-power-taxonomy.md"

        profile_text = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""
        taxonomy_text = taxonomy_path.read_text(encoding="utf-8") if taxonomy_path.exists() else ""

        profile_excerpt = self._extract_genre_section(profile_text, primary_genre)
        taxonomy_excerpt = self._extract_genre_section(taxonomy_text, primary_genre)

        secondary_profiles: List[str] = []
        secondary_taxonomies: List[str] = []
        for extra in secondary_genres:
            secondary_profiles.append(self._extract_genre_section(profile_text, extra))
            secondary_taxonomies.append(self._extract_genre_section(taxonomy_text, extra))

        refs = self._extract_markdown_refs(
            "\n".join([profile_excerpt] + secondary_profiles),
            max_items=int(getattr(self.config, "context_genre_profile_max_refs", 8)),
        )

        composite_hints = self._build_composite_genre_hints(genres, refs)

        return {
            "genre": primary_genre,
            "genre_raw": genre_raw,
            "genres": genres,
            "composite": composite,
            "secondary_genres": secondary_genres,
            "profile_excerpt": profile_excerpt,
            "taxonomy_excerpt": taxonomy_excerpt,
            "secondary_profile_excerpts": secondary_profiles,
            "secondary_taxonomy_excerpts": secondary_taxonomies,
            "reference_hints": refs,
            "composite_hints": composite_hints,
        }

    def _build_writing_guidance(
        self,
        chapter: int,
        reader_signal: Dict[str, Any],
        genre_profile: Dict[str, Any],
        project_memory: Optional[Dict[str, Any]] = None,
        story_technique_blueprint: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not getattr(self.config, "context_writing_guidance_enabled", True):
            return {}

        limit = max(1, int(getattr(self.config, "context_writing_guidance_max_items", 6)))
        low_score_threshold = float(
            getattr(self.config, "context_writing_guidance_low_score_threshold", 75.0)
        )

        guidance_bundle = build_guidance_items(
            chapter=chapter,
            reader_signal=reader_signal,
            genre_profile=genre_profile,
            low_score_threshold=low_score_threshold,
            hook_diversify_enabled=bool(
                getattr(self.config, "context_writing_guidance_hook_diversify", True)
            ),
            project_memory=project_memory or {},
            story_technique_blueprint=story_technique_blueprint or {},
        )

        guidance = list(guidance_bundle.get("guidance") or [])
        methodology_strategy: Dict[str, Any] = {}

        if self._is_methodology_enabled_for_genre(genre_profile):
            methodology_strategy = build_methodology_strategy_card(
                chapter=chapter,
                reader_signal=reader_signal,
                genre_profile=genre_profile,
                label=str(getattr(self.config, "context_methodology_label", "digital-serial-v1")),
            )
            guidance.extend(build_methodology_guidance_items(methodology_strategy))

        checklist = self._build_writing_checklist(
            chapter=chapter,
            guidance_items=guidance,
            reader_signal=reader_signal,
            genre_profile=genre_profile,
            strategy_card=methodology_strategy,
            project_memory=project_memory or {},
            story_technique_blueprint=story_technique_blueprint or {},
        )

        checklist_score = self._compute_writing_checklist_score(
            chapter=chapter,
            checklist=checklist,
            reader_signal=reader_signal,
        )

        if getattr(self.config, "context_writing_score_persist_enabled", True):
            self._persist_writing_checklist_score(checklist_score)

        low_ranges = guidance_bundle.get("low_ranges") or []
        hook_usage = guidance_bundle.get("hook_usage") or {}
        pattern_usage = guidance_bundle.get("pattern_usage") or {}
        genre = str(guidance_bundle.get("genre") or genre_profile.get("genre") or "").strip()

        hook_types = list(hook_usage.keys())[:3] if isinstance(hook_usage, dict) else []
        top_patterns = (
            sorted(pattern_usage, key=pattern_usage.get, reverse=True)[:3]
            if isinstance(pattern_usage, dict)
            else []
        )

        return {
            "chapter": chapter,
            "guidance_items": guidance[:limit],
            "checklist": checklist,
            "checklist_score": checklist_score,
            "methodology": methodology_strategy,
            "blueprint_profile": str((story_technique_blueprint or {}).get("primary_profile") or ""),
            "signals_used": {
                "has_low_score_ranges": bool(low_ranges),
                "hook_types": hook_types,
                "top_patterns": top_patterns,
                "genre": genre,
                "methodology_enabled": bool(methodology_strategy.get("enabled")),
            },
        }

    def _build_chapter_technique_plan(
        self,
        *,
        chapter: int,
        chapter_outline: str,
        reader_signal: Dict[str, Any],
        genre_profile: Dict[str, Any],
        story_recall: Dict[str, Any],
        chapter_intent: Dict[str, Any],
        writing_guidance: Dict[str, Any],
        story_technique_blueprint: Dict[str, Any],
        project_memory: Dict[str, Any],
    ) -> Dict[str, Any]:
        plan = build_chapter_technique_plan(
            chapter=chapter,
            chapter_outline=chapter_outline,
            reader_signal=reader_signal,
            genre_profile=genre_profile,
            story_recall=story_recall,
            chapter_intent=chapter_intent,
            writing_guidance=writing_guidance,
            story_technique_blueprint=story_technique_blueprint,
            project_memory=project_memory,
        )
        try:
            self.config.ensure_dirs()
            self._chapter_technique_plan_path(chapter).write_text(
                json.dumps(plan, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("failed to persist chapter technique plan for chapter %s", chapter)
        return plan

    def _clean_outline_goal(self, chapter_outline: str) -> str:
        text = re.sub(r"\s+", " ", str(chapter_outline or "")).strip()
        text = re.sub(r"^#+\s*", "", text)
        return text[:120].strip()

    def _resolve_current_focus(
        self,
        chapter: int,
        chapter_outline: str,
        story_recall: Dict[str, Any],
        state: Dict[str, Any],
        author_intent: Dict[str, Any],
        current_focus: Dict[str, Any],
        writing_guidance: Dict[str, Any],
    ) -> Dict[str, Any]:
        if isinstance(current_focus, dict) and any(current_focus.get(key) for key in ("title", "goal", "must_resolve")):
            return current_focus
        if not bool(getattr(self.config, "context_current_focus_auto_generate", True)):
            return current_focus or {}

        must_resolve: List[str] = []
        for item in (story_recall.get("priority_foreshadowing") or [])[:2]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("name") or item.get("content") or item.get("event") or "").strip()
            if label:
                must_resolve.append(label)
        for item in (writing_guidance.get("guidance_items") or [])[:2]:
            text = str(item).strip()
            if text and text not in must_resolve:
                must_resolve.append(text)

        generated = {
            "title": "自动聚焦",
            "goal": self._clean_outline_goal(chapter_outline) or f"第 {chapter} 章优先推进当前主线",
            "must_resolve": must_resolve[:3],
            "hard_constraints": list(author_intent.get("hard_constraints") or [])[:3] if isinstance(author_intent, dict) else [],
            "generated": True,
        }
        protagonist_name = str(((state.get("protagonist_state") or {}).get("name")) or "").strip()
        if protagonist_name:
            generated["focus_character"] = protagonist_name
        return generated

    def _detect_emotional_continuity_risks(
        self,
        chapter: int,
        chapter_goal: str,
        protagonist_name: str,
        emotional_arcs: Dict[str, Any],
    ) -> List[str]:
        if not protagonist_name or not isinstance(emotional_arcs, dict):
            return []
        rows = emotional_arcs.get(protagonist_name) or []
        if not isinstance(rows, list) or not rows:
            return []
        latest = rows[-1] if isinstance(rows[-1], dict) else {}
        if not latest:
            return []
        latest_state = str(latest.get("emotional_state") or "").strip()
        latest_chapter = int(latest.get("chapter") or 0)
        stale_gap = max(0, chapter - latest_chapter)
        risks: List[str] = []
        if stale_gap >= int(getattr(self.config, "context_emotional_arc_stale_gap", 6) or 6):
            risks.append(f"{protagonist_name} 的情绪弧线已 {stale_gap} 章未更新")
        lowered = chapter_goal.lower()
        positive_cues = ("庆功", "甜", "轻松", "温馨", "和解", "表白", "胜利", "喜")
        negative_states = ("压抑", "愤怒", "悲伤", "恐惧", "痛苦", "绝望")
        if latest_state and latest_state in negative_states and any(cue in lowered for cue in positive_cues):
            risks.append(f"{protagonist_name} 当前情绪为“{latest_state}”，与本章目标语气可能冲突")
        return risks

    def _validate_chapter_contract(self, chapter: int, chapter_intent: Dict[str, Any]) -> None:
        if not bool(getattr(self.config, "context_require_chapter_contract", True)):
            return

        required_fields = {
            "chapter_goal": "目标",
            "must_resolve": "冲突",
            "story_risks": "动作/阻力",
            "focus_title": "钩子",
        }

        missing_labels: List[str] = []
        for field, label in required_fields.items():
            value = chapter_intent.get(field)
            if isinstance(value, str):
                if not value.strip():
                    missing_labels.append(label)
                continue
            if isinstance(value, list):
                if not any(str(item).strip() for item in value):
                    missing_labels.append(label)
                continue
            if not value:
                missing_labels.append(label)

        if missing_labels:
            joined = "、".join(missing_labels)
            raise ValueError(
                f"第{chapter}章未满足最小章节契约，缺少：{joined}。请先补充章节任务书后再写作。"
            )

    def _validate_state_change_minimum(self, chapter: int, story_recall: Dict[str, Any]) -> None:
        minimum = int(getattr(self.config, "context_min_state_changes_per_chapter", 1) or 0)
        if minimum <= 0:
            return

        change_focus = story_recall.get("structured_change_focus") or []
        if not isinstance(change_focus, list):
            change_focus = []

        if len(change_focus) < minimum:
            raise ValueError(
                f"第{chapter}章缺少可追踪状态变化（至少{minimum}项）。请在章纲或任务书中明确资源/关系/认知/位置/战力变化。"
            )

    def _build_chapter_intent(
        self,
        chapter: int,
        chapter_outline: str,
        story_recall: Dict[str, Any],
        state: Dict[str, Any],
        story_memory: Dict[str, Any],
        author_intent: Dict[str, Any],
        current_focus: Dict[str, Any],
        writing_guidance: Dict[str, Any],
    ) -> Dict[str, Any]:
        max_items = max(1, int(getattr(self.config, "context_chapter_intent_max_items", 3) or 3))
        chapter_goal = str(current_focus.get("chapter_goal") or current_focus.get("goal") or "").strip()
        if not chapter_goal:
            chapter_goal = self._clean_outline_goal(chapter_outline) or "围绕当前大纲推进本章核心冲突"

        must_resolve: List[str] = []
        for item in current_focus.get("must_resolve", []) or []:
            text = str(item).strip()
            if text:
                must_resolve.append(text)
        if not must_resolve:
            for item in (story_recall.get("priority_foreshadowing") or [])[:max_items]:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("name") or item.get("content") or item.get("event") or "").strip()
                if label:
                    must_resolve.append(label)

        priority_memory: List[Dict[str, Any]] = []
        for item in (story_recall.get("character_focus") or [])[:2]:
            if isinstance(item, dict):
                priority_memory.append(
                    {
                        "type": "character",
                        "label": str(item.get("name") or "未命名角色"),
                        "detail": str(item.get("current_state") or ""),
                    }
                )
        for item in (story_recall.get("recent_events") or [])[:1]:
            if isinstance(item, dict):
                priority_memory.append(
                    {
                        "type": "event",
                        "label": f"Ch.{item.get('ch') or item.get('chapter') or '?'}",
                        "detail": str(item.get("event") or item.get("content") or ""),
                    }
                )
        for item in (story_recall.get("structured_change_focus") or [])[:1]:
            if isinstance(item, dict):
                priority_memory.append(
                    {
                        "type": "change",
                        "label": f"{item.get('entity_id') or '—'}.{item.get('field') or '—'}",
                        "detail": f"{item.get('old_value')} -> {item.get('new_value')}",
                    }
                )

        story_risks: List[str] = []
        recall_policy = story_recall.get("recall_policy") or {}
        consolidation_gap = int(recall_policy.get("consolidation_gap") or 0)
        if consolidation_gap >= 3:
            story_risks.append(f"记忆整理滞后 {consolidation_gap} 章，易遗漏跨章细节")
        if len(story_recall.get("priority_foreshadowing") or []) >= max_items:
            story_risks.append("高优先级伏笔较多，本章若不回收会继续堆积")

        protagonist_name = str(((state.get("protagonist_state") or {}).get("name")) or "").strip()
        emotional_arcs = story_memory.get("emotional_arcs") or {}
        for risk in self._detect_emotional_continuity_risks(
            chapter=chapter,
            chapter_goal=chapter_goal,
            protagonist_name=protagonist_name,
            emotional_arcs=emotional_arcs if isinstance(emotional_arcs, dict) else {},
        ):
            if risk not in story_risks:
                story_risks.append(risk)

        for item in (writing_guidance.get("guidance_items") or [])[:2]:
            text = str(item).strip()
            if text and text not in story_risks:
                story_risks.append(text)

        hard_constraints: List[str] = []
        for source in (author_intent, current_focus):
            if not isinstance(source, dict):
                continue
            for item in source.get("hard_constraints", []) or []:
                text = str(item).strip()
                if text and text not in hard_constraints:
                    hard_constraints.append(text)

        intent = {
            "chapter": chapter,
            "focus_title": str(current_focus.get("title") or current_focus.get("focus") or "").strip(),
            "chapter_goal": chapter_goal,
            "must_resolve": must_resolve[:max_items],
            "priority_memory": priority_memory[: max_items + 1],
            "story_risks": story_risks[:max_items],
            "hard_constraints": hard_constraints[:max_items],
        }
        try:
            self.config.ensure_dirs()
            self._chapter_intent_path(chapter).write_text(
                json.dumps(intent, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("failed to persist chapter intent for chapter %s", chapter)
        return intent

    def _compute_writing_checklist_score(
        self,
        chapter: int,
        checklist: List[Dict[str, Any]],
        reader_signal: Dict[str, Any],
    ) -> Dict[str, Any]:
        total_items = len(checklist)
        required_items = 0
        completed_items = 0
        completed_required = 0
        total_weight = 0.0
        completed_weight = 0.0
        pending_labels: List[str] = []

        for item in checklist:
            if not isinstance(item, dict):
                continue
            required = bool(item.get("required"))
            weight = float(item.get("weight") or 1.0)
            total_weight += weight
            if required:
                required_items += 1

            completed = self._is_checklist_item_completed(item, reader_signal)
            if completed:
                completed_items += 1
                completed_weight += weight
                if required:
                    completed_required += 1
            else:
                pending_labels.append(str(item.get("label") or item.get("id") or "未命名项"))

        completion_rate = (completed_items / total_items) if total_items > 0 else 1.0
        weighted_rate = (completed_weight / total_weight) if total_weight > 0 else completion_rate
        required_rate = (completed_required / required_items) if required_items > 0 else 1.0

        score = 100.0 * (0.5 * weighted_rate + 0.3 * required_rate + 0.2 * completion_rate)

        if getattr(self.config, "context_writing_score_include_reader_trend", True):
            trend_window = max(1, int(getattr(self.config, "context_writing_score_trend_window", 10)))
            trend = self.index_manager.get_writing_checklist_score_trend(last_n=trend_window)
            baseline = float(trend.get("score_avg") or 0.0)
            if baseline > 0:
                score += max(-10.0, min(10.0, (score - baseline) * 0.1))

        score = round(max(0.0, min(100.0, score)), 2)

        return {
            "chapter": chapter,
            "score": score,
            "completion_rate": round(completion_rate, 4),
            "weighted_completion_rate": round(weighted_rate, 4),
            "required_completion_rate": round(required_rate, 4),
            "total_items": total_items,
            "required_items": required_items,
            "completed_items": completed_items,
            "completed_required": completed_required,
            "total_weight": round(total_weight, 2),
            "completed_weight": round(completed_weight, 2),
            "pending_items": pending_labels,
            "trend_window": int(getattr(self.config, "context_writing_score_trend_window", 10)),
        }

    def _is_checklist_item_completed(self, item: Dict[str, Any], reader_signal: Dict[str, Any]) -> bool:
        return is_checklist_item_completed(item, reader_signal)

    def _persist_writing_checklist_score(self, checklist_score: Dict[str, Any]) -> None:
        if not checklist_score:
            return
        try:
            self.index_manager.save_writing_checklist_score(
                WritingChecklistScoreMeta(
                    chapter=int(checklist_score.get("chapter") or 0),
                    template=str(getattr(self, "_active_template", self.DEFAULT_TEMPLATE) or self.DEFAULT_TEMPLATE),
                    total_items=int(checklist_score.get("total_items") or 0),
                    required_items=int(checklist_score.get("required_items") or 0),
                    completed_items=int(checklist_score.get("completed_items") or 0),
                    completed_required=int(checklist_score.get("completed_required") or 0),
                    total_weight=float(checklist_score.get("total_weight") or 0.0),
                    completed_weight=float(checklist_score.get("completed_weight") or 0.0),
                    completion_rate=float(checklist_score.get("completion_rate") or 0.0),
                    score=float(checklist_score.get("score") or 0.0),
                    score_breakdown={
                        "weighted_completion_rate": checklist_score.get("weighted_completion_rate"),
                        "required_completion_rate": checklist_score.get("required_completion_rate"),
                        "trend_window": checklist_score.get("trend_window"),
                    },
                    pending_items=list(checklist_score.get("pending_items") or []),
                    source="context_manager",
                )
            )
        except Exception as exc:
            logger.warning("failed to persist writing checklist score: %s", exc)

    def _resolve_context_stage(self, chapter: int) -> str:
        early = max(1, int(getattr(self.config, "context_dynamic_budget_early_chapter", 30)))
        late = max(early + 1, int(getattr(self.config, "context_dynamic_budget_late_chapter", 120)))
        if chapter <= early:
            return "early"
        if chapter >= late:
            return "late"
        return "mid"

    def _resolve_template_weights(self, template: str, chapter: int) -> Dict[str, float]:
        template_key = template if template in self.TEMPLATE_WEIGHTS else self.DEFAULT_TEMPLATE
        base = dict(self.TEMPLATE_WEIGHTS.get(template_key, self.TEMPLATE_WEIGHTS[self.DEFAULT_TEMPLATE]))
        if not getattr(self.config, "context_dynamic_budget_enabled", True):
            return base

        stage = self._resolve_context_stage(chapter)
        dynamic_weights = getattr(self.config, "context_template_weights_dynamic", None)
        if not isinstance(dynamic_weights, dict):
            dynamic_weights = self.TEMPLATE_WEIGHTS_DYNAMIC

        stage_weights = dynamic_weights.get(stage, {}) if isinstance(dynamic_weights.get(stage, {}), dict) else {}
        staged = stage_weights.get(template_key)
        if isinstance(staged, dict):
            return dict(staged)

        return base

    def _parse_genre_tokens(self, genre_raw: str) -> List[str]:
        support_composite = bool(getattr(self.config, "context_genre_profile_support_composite", True))
        separators_raw = getattr(self.config, "context_genre_profile_separators", ("+", "/", "|", ","))
        separators = tuple(str(token) for token in separators_raw if str(token))
        return parse_genre_tokens(
            genre_raw,
            support_composite=support_composite,
            separators=separators,
        )

    def _normalize_genre_token(self, token: str) -> str:
        return normalize_genre_token(token)

    def _build_composite_genre_hints(self, genres: List[str], refs: List[str]) -> List[str]:
        return build_composite_genre_hints(genres, refs)

    def _build_writing_checklist(
        self,
        chapter: int,
        guidance_items: List[str],
        reader_signal: Dict[str, Any],
        genre_profile: Dict[str, Any],
        strategy_card: Dict[str, Any] | None = None,
        project_memory: Optional[Dict[str, Any]] = None,
        story_technique_blueprint: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        _ = chapter
        if not getattr(self.config, "context_writing_checklist_enabled", True):
            return []

        min_items = max(1, int(getattr(self.config, "context_writing_checklist_min_items", 3)))
        max_items = max(min_items, int(getattr(self.config, "context_writing_checklist_max_items", 6)))
        default_weight = float(getattr(self.config, "context_writing_checklist_default_weight", 1.0))
        if default_weight <= 0:
            default_weight = 1.0

        return build_writing_checklist(
            guidance_items=guidance_items,
            reader_signal=reader_signal,
            genre_profile=genre_profile,
            strategy_card=strategy_card,
            min_items=min_items,
            max_items=max_items,
            default_weight=default_weight,
            project_memory=project_memory or {},
            story_technique_blueprint=story_technique_blueprint or {},
        )

    def _is_methodology_enabled_for_genre(self, genre_profile: Dict[str, Any]) -> bool:
        if not bool(getattr(self.config, "context_methodology_enabled", False)):
            return False

        whitelist_raw = getattr(self.config, "context_methodology_genre_whitelist", ("*",))
        if isinstance(whitelist_raw, str):
            whitelist_iter = [whitelist_raw]
        else:
            whitelist_iter = list(whitelist_raw or [])

        whitelist = {str(token).strip().lower() for token in whitelist_iter if str(token).strip()}
        if not whitelist:
            return True
        if "*" in whitelist or "all" in whitelist:
            return True

        genre = str((genre_profile or {}).get("genre") or "").strip()
        if not genre:
            return False

        profile_key = to_profile_key(genre)
        return profile_key in whitelist

    def _compact_json_text(self, content: Any, budget: Optional[int]) -> str:
        raw = json.dumps(content, ensure_ascii=False)
        if budget is None or len(raw) <= budget:
            return raw
        if not getattr(self.config, "context_compact_text_enabled", True):
            return raw[:budget]

        min_budget = max(1, int(getattr(self.config, "context_compact_min_budget", 120)))
        if budget <= min_budget:
            return raw[:budget]

        head_ratio = float(getattr(self.config, "context_compact_head_ratio", 0.65))
        head_budget = int(budget * max(0.2, min(0.9, head_ratio)))
        tail_budget = max(0, budget - head_budget - 10)
        compact = f"{raw[:head_budget]}…[TRUNCATED]{raw[-tail_budget:] if tail_budget else ''}"
        return compact[:budget]

    def _extract_genre_section(self, text: str, genre: str) -> str:
        return extract_genre_section(text, genre)

    def _extract_markdown_refs(self, text: str, max_items: int = 8) -> List[str]:
        return extract_markdown_refs(text, max_items=max_items)

    def _load_state(self) -> Dict[str, Any]:
        path = self.config.state_file
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_outline(self, chapter: int) -> str:
        outline = load_chapter_outline(self.config.project_root, chapter, max_chars=1500)
        if bool(getattr(self.config, "context_require_chapter_outline", True)) and is_missing_chapter_outline(outline):
            raise ValueError(
                f"第{chapter}章缺少可用大纲。请先在`大纲/`补齐章节大纲，再执行写作流程。"
            )

        if bool(getattr(self.config, "context_require_chapter_contract", True)):
            min_state_changes = max(0, int(getattr(self.config, "context_min_state_changes_per_chapter", 0)))
            missing = validate_chapter_contract(outline, min_state_changes=min_state_changes)
            if missing:
                missing_text = "、".join(missing)
                raise ValueError(
                    f"第{chapter}章大纲缺少关键项：{missing_text}。"
                    "请补齐‘目标/冲突/动作/结果/代价/钩子’，并至少包含可识别的状态变化。"
                )

        return outline

    def _load_recent_summaries(self, chapter: int, window: int = 3) -> List[Dict[str, Any]]:
        summaries = []
        for ch in range(max(1, chapter - window), chapter):
            summary = self._load_summary_text(ch)
            if summary:
                summaries.append(summary)
        return summaries

    def _load_recent_meta(self, state: Dict[str, Any], chapter: int, window: int = 3) -> List[Dict[str, Any]]:
        meta = state.get("chapter_meta", {}) or {}
        results = []
        for ch in range(max(1, chapter - window), chapter):
            for key in (f"{ch:04d}", str(ch)):
                if key in meta:
                    results.append({"chapter": ch, **meta.get(key, {})})
                    break
        return results

    def _load_recent_appearances(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        appearances = self.index_manager.get_recent_appearances(limit=limit)
        return appearances or []

    def _load_setting(self, keyword: str) -> str:
        settings_dir = self.config.settings_dir
        candidates = [
            settings_dir / f"{keyword}.md",
        ]
        for path in candidates:
            if path.exists():
                return path.read_text(encoding="utf-8")
        # fallback: any file containing keyword
        matches = list(settings_dir.glob(f"*{keyword}*.md"))
        if matches:
            return matches[0].read_text(encoding="utf-8")
        return f"[{keyword}设定未找到]"

    def _extract_summary_excerpt(self, text: str, max_chars: int) -> str:
        if not text:
            return ""
        match = self.SUMMARY_SECTION_RE.search(text)
        excerpt = match.group(1).strip() if match else text.strip()
        if max_chars > 0 and len(excerpt) > max_chars:
            return excerpt[:max_chars].rstrip()
        return excerpt

    def _load_summary_text(self, chapter: int, snippet_chars: Optional[int] = None) -> Optional[Dict[str, Any]]:
        summary_path = self.config.webnovel_dir / "summaries" / f"ch{chapter:04d}.md"
        if not summary_path.exists():
            return None
        text = summary_path.read_text(encoding="utf-8")
        if snippet_chars:
            summary_text = self._extract_summary_excerpt(text, snippet_chars)
        else:
            summary_text = text
        return {"chapter": chapter, "summary": summary_text}

    def _load_story_skeleton(self, chapter: int) -> List[Dict[str, Any]]:
        interval = max(1, int(self.config.context_story_skeleton_interval))
        max_samples = max(0, int(self.config.context_story_skeleton_max_samples))
        snippet_chars = int(self.config.context_story_skeleton_snippet_chars)

        if max_samples <= 0 or chapter <= interval:
            return []

        samples: List[Dict[str, Any]] = []
        cursor = chapter - interval
        while cursor >= 1 and len(samples) < max_samples:
            summary = self._load_summary_text(cursor, snippet_chars=snippet_chars)
            if summary and summary.get("summary"):
                samples.append(summary)
            cursor -= interval

        samples.reverse()
        return samples

    def _build_story_recall(
        self,
        chapter: int,
        chapter_outline: str,
        state: Dict[str, Any],
        story_memory: Dict[str, Any],
        story_memory_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """构建写前优先召回层，帮助模型先看到未回收内容。"""
        if not isinstance(story_memory, dict):
            story_memory = {}
        if not isinstance(story_memory_meta, dict):
            story_memory_meta = {}

        characters = story_memory.get("characters", {})
        if not isinstance(characters, dict):
            characters = {}

        plot_threads = story_memory.get("plot_threads", [])
        if not isinstance(plot_threads, list):
            plot_threads = []

        recent_events = story_memory.get("recent_events", [])
        if not isinstance(recent_events, list):
            recent_events = []
        temporal_window: Dict[str, Any] = {}
        emotional_arcs = story_memory.get("emotional_arcs", {})
        if not isinstance(emotional_arcs, dict):
            emotional_arcs = {}

        change_ledger = story_memory.get("structured_change_ledger", story_memory.get("numeric_ledger", []))
        if not isinstance(change_ledger, list):
            change_ledger = []

        archive = story_memory.get("archive", {})
        if not isinstance(archive, dict):
            archive = {}
        archived_threads = archive.get("plot_threads", [])
        if not isinstance(archived_threads, list):
            archived_threads = []
        archived_events = archive.get("recent_events", [])
        if not isinstance(archived_events, list):
            archived_events = []
        archived_changes = archive.get("structured_change_ledger", [])
        if not isinstance(archived_changes, list):
            archived_changes = []

        protagonist_name = ""
        protagonist_state = state.get("protagonist_state", {}) if isinstance(state, dict) else {}
        if isinstance(protagonist_state, dict):
            protagonist_name = str(protagonist_state.get("name") or "").strip()

        if bool(getattr(self.config, "context_temporal_recall_enabled", True)) and chapter > 1:
            protagonist_entity_id = ""
            if protagonist_name:
                protagonist = self.index_manager.get_protagonist()
                if isinstance(protagonist, dict):
                    protagonist_entity_id = str(protagonist.get("id") or "").strip()
            temporal_window = self.index_manager.get_temporal_window(
                current_chapter=chapter,
                lookback=int(getattr(self.config, "context_temporal_recall_lookback", 12) or 12),
                entity_id=protagonist_entity_id or None,
                chapter_limit=int(getattr(self.config, "context_temporal_recall_chapter_limit", 3) or 3),
                state_change_limit=int(getattr(self.config, "context_temporal_recall_change_limit", 5) or 5),
                relationship_limit=int(getattr(self.config, "context_temporal_recall_relationship_limit", 5) or 5),
                appearance_limit=int(getattr(self.config, "context_temporal_recall_appearance_limit", 5) or 5),
            )

        def _thread_sort_key(item: Dict[str, Any]) -> tuple:
            urgency = item.get("urgency")
            try:
                urgency_value = float(urgency) if urgency is not None else -1.0
            except (TypeError, ValueError):
                urgency_value = -1.0
            tier = normalize_foreshadowing_tier(item.get("tier"))
            tier_weight = {"核心": 3, "支线": 2, "装饰": 1}.get(tier, 0)
            chapter_value = 0
            for key in ("target_chapter", "planted_chapter", "chapter"):
                try:
                    chapter_value = int(item.get(key) or 0)
                except (TypeError, ValueError):
                    chapter_value = 0
                if chapter_value:
                    break
            return (-tier_weight, -urgency_value, chapter_value, str(item.get("name") or item.get("content") or ""))

        priority_foreshadowing: List[Dict[str, Any]] = []
        for item in plot_threads:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").strip().lower()
            if status not in {"pending", "active", "未回收"}:
                continue
            priority_foreshadowing.append(item)
        priority_foreshadowing.sort(key=_thread_sort_key)

        character_focus: List[Dict[str, Any]] = []
        if protagonist_name and protagonist_name in characters and isinstance(characters.get(protagonist_name), dict):
            protagonist_entry = dict(characters.get(protagonist_name) or {})
            character_focus.append(
                {
                    "name": protagonist_name,
                    "current_state": protagonist_entry.get("current_state", ""),
                    "last_update_chapter": protagonist_entry.get("last_update_chapter", 0),
                }
            )

        remaining_characters: List[tuple[str, Dict[str, Any]]] = []
        for name, info in characters.items():
            if name == protagonist_name or not isinstance(info, dict):
                continue
            remaining_characters.append((str(name), dict(info)))
        remaining_characters.sort(
            key=lambda item: (
                -int(item[1].get("last_update_chapter") or 0),
                str(item[0]),
            )
        )
        for name, info in remaining_characters[:4]:
            character_focus.append(
                {
                    "name": name,
                    "current_state": info.get("current_state", ""),
                    "last_update_chapter": info.get("last_update_chapter", 0),
                }
            )

        emotional_focus: List[Dict[str, Any]] = []
        seen_emotion_names: set[str] = set()
        for name in [protagonist_name] + [str(item.get("name") or "") for item in character_focus]:
            if not name or name in seen_emotion_names:
                continue
            rows = emotional_arcs.get(name) or []
            if not isinstance(rows, list) or not rows:
                continue
            latest_arc = rows[-1]
            if not isinstance(latest_arc, dict):
                continue
            seen_emotion_names.add(name)
            emotional_focus.append(
                {
                    "name": name,
                    "emotional_state": latest_arc.get("emotional_state", ""),
                    "emotional_trend": latest_arc.get("emotional_trend", "stable"),
                    "trigger_event": latest_arc.get("trigger_event", ""),
                    "chapter": latest_arc.get("chapter", 0),
                    "confidence": latest_arc.get("confidence", 1.0),
                }
            )

        structured_change_focus: List[Dict[str, Any]] = []
        change_rows = [item for item in change_ledger if isinstance(item, dict)]
        tier_buckets: Dict[str, List[Dict[str, Any]]] = {"consolidated": [], "episodic": [], "working": []}
        for item in change_rows:
            tier = str(item.get("memory_tier") or "working").strip().lower()
            if tier not in tier_buckets:
                tier = "working"
            tier_buckets[tier].append(item)

        for tier_name in ("consolidated", "episodic", "working"):
            bucket = tier_buckets.get(tier_name, [])
            bucket.sort(
                key=lambda item: (
                    memory_tier_rank(item.get("memory_tier")),
                    -float(item.get("memory_score") or 0.0),
                    -abs(float(item.get("delta") or 0.0)),
                    -int(item.get("ch") or 0),
                    str(item.get("entity_id") or ""),
                    str(item.get("field") or ""),
                )
            )
            tier_limit = {"consolidated": 2, "episodic": 2, "working": 1}.get(tier_name, 1)
            for item in bucket[:tier_limit]:
                score = float(item.get("memory_score") or 0.0)
                structured_change_focus.append(
                    {
                        "ch": item.get("ch", 0),
                        "entity_id": item.get("entity_id", ""),
                        "field": item.get("field", ""),
                        "change_kind": item.get("change_kind") or item.get("type") or "state_change",
                        "memory_score": score,
                        "memory_tier": item.get("memory_tier") or "working",
                        "old_value": item.get("old_value"),
                        "new_value": item.get("new_value"),
                        "old_numeric": item.get("old_numeric"),
                        "new_numeric": item.get("new_numeric"),
                        "delta": item.get("delta"),
                    }
                )

        archive_presence = bool(archived_threads or archived_events or archived_changes)
        memory_presence = bool(characters or plot_threads or recent_events or change_ledger or archive_presence)
        consolidation_gap = max(
            0,
            int(chapter or 0) - int(story_memory_meta.get("last_consolidated_chapter") or 0),
        )
        signal_count = len(priority_foreshadowing) + len(character_focus) + len(structured_change_focus) + len(recent_events) + len(emotional_focus)
        if temporal_window:
            signal_count += len(temporal_window.get("state_changes") or [])
        recall_reasons: List[str] = []
        if not memory_presence:
            recall_mode = "off"
            recall_reasons.append("story_memory_empty")
        elif priority_foreshadowing or signal_count >= 3 or consolidation_gap >= 3:
            recall_mode = "boost"
            if priority_foreshadowing:
                recall_reasons.append("unresolved_foreshadowing")
            if len(structured_change_focus) > 0:
                recall_reasons.append("recent_structured_changes")
            if archive_presence:
                recall_reasons.append("archived_memory_available")
            if consolidation_gap >= 3:
                recall_reasons.append("consolidation_gap")
        else:
            recall_mode = "normal"
            recall_reasons.append("story_memory_available")

        chapter_outline_text = str(chapter_outline or "")
        def _text_fragments(text: str, min_size: int = 2, max_size: int = 4, max_fragments: int = 120) -> set[str]:
            cleaned = re.sub(r"\s+", "", str(text or ""))
            fragments: set[str] = set()
            if not cleaned:
                return fragments
            upper = min(max_size, len(cleaned))
            for size in range(min_size, upper + 1):
                for index in range(0, len(cleaned) - size + 1):
                    fragment = cleaned[index : index + size].strip()
                    if fragment:
                        fragments.add(fragment)
                        if len(fragments) >= max_fragments:
                            return fragments
            return fragments

        outline_fragments = _text_fragments(chapter_outline_text)
        active_token_sources = [protagonist_name]
        active_token_sources.extend(
            str(row.get("name") or row.get("content") or row.get("event") or "")
            for row in priority_foreshadowing[:5]
            if isinstance(row, dict)
        )
        active_token_sources.extend(
            str(row.get("name") or row.get("current_state") or "")
            for row in character_focus[:5]
            if isinstance(row, dict)
        )
        active_token_sources.extend(
            str(row.get("event") or row.get("content") or "")
            for row in recent_events[-5:]
            if isinstance(row, dict)
        )
        active_token_sources.extend(
            f"{row.get('entity_id')}.{row.get('field')}"
            for row in structured_change_focus[:5]
            if isinstance(row, dict)
        )
        reference_fragments = set(outline_fragments)
        reference_fragments.update(
            fragment
            for source in active_token_sources
            for fragment in _text_fragments(str(source))
            if fragment
        )

        def _archive_score(text: str) -> int:
            if not text:
                return 0
            score = 0
            text_value = str(text)
            text_fragments = _text_fragments(text_value)
            overlap = reference_fragments.intersection(text_fragments)
            if overlap:
                score += min(4, len(overlap))
            if chapter_outline_text and text_value in chapter_outline_text:
                score += 2
            if protagonist_name and protagonist_name in text_value:
                score += 2
            return score

        def _archive_signature(item: Dict[str, Any]) -> str:
            return "|".join(
                [
                    str(item.get("content") or item.get("event") or item.get("name") or ""),
                    str(item.get("entity_id") or ""),
                    str(item.get("field") or ""),
                ]
            ).strip("|")

        active_signatures = {
            _archive_signature(item)
            for item in priority_foreshadowing + recent_events + structured_change_focus
            if isinstance(item, dict)
        }
        archive_recall: Dict[str, List[Dict[str, Any]]] = {
            "plot_threads": [],
            "recent_events": [],
            "structured_change_focus": [],
        }

        if memory_presence and (recall_mode == "boost" or consolidation_gap >= 3):
            for item in archived_threads:
                if not isinstance(item, dict):
                    continue
                signature = _archive_signature(item)
                if signature in active_signatures:
                    continue
                content = str(item.get("content") or item.get("event") or item.get("name") or "")
                score = _archive_score(content)
                if score < 2:
                    continue
                archive_recall["plot_threads"].append(
                    {
                        "content": content,
                        "status": str(item.get("status") or "已归档"),
                        "tier": str(item.get("tier") or "archive"),
                        "resolved_chapter": item.get("resolved_chapter"),
                        "last_update_chapter": item.get("updated_at_chapter") or item.get("chapter") or 0,
                        "memory_tier": "archive",
                        "archive_score": score,
                    }
                )

            for item in archived_events:
                if not isinstance(item, dict):
                    continue
                signature = _archive_signature(item)
                if signature in active_signatures:
                    continue
                text = str(item.get("event") or item.get("content") or "")
                score = _archive_score(text)
                if score < 2:
                    continue
                archive_recall["recent_events"].append(
                    {
                        "ch": item.get("ch") or item.get("chapter") or 0,
                        "event": text,
                        "memory_tier": "archive",
                        "archive_score": score,
                    }
                )

            for item in archived_changes:
                if not isinstance(item, dict):
                    continue
                signature = _archive_signature(item)
                if signature in active_signatures:
                    continue
                text = " ".join(
                    str(part or "")
                    for part in (
                        item.get("entity_id"),
                        item.get("field"),
                        item.get("old_value"),
                        item.get("new_value"),
                    )
                    if part
                )
                score = _archive_score(text)
                if score < 2:
                    continue
                archive_recall["structured_change_focus"].append(
                    {
                        "ch": item.get("ch", 0),
                        "entity_id": item.get("entity_id", ""),
                        "field": item.get("field", ""),
                        "change_kind": item.get("change_kind") or item.get("type") or "state_change",
                        "memory_score": float(item.get("memory_score") or 0.0),
                        "memory_tier": "archive",
                        "old_value": item.get("old_value"),
                        "new_value": item.get("new_value"),
                        "delta": item.get("delta"),
                        "archive_score": score,
                    }
                )

            archive_recall["plot_threads"] = archive_recall["plot_threads"][:2]
            archive_recall["recent_events"] = archive_recall["recent_events"][:2]
            archive_recall["structured_change_focus"] = archive_recall["structured_change_focus"][:2]

        return {
            "version": story_memory_meta.get("version", ""),
            "last_consolidated_chapter": story_memory_meta.get("last_consolidated_chapter", 0),
            "last_consolidated_at": story_memory_meta.get("last_consolidated_at", ""),
            "recall_policy": {
                "mode": recall_mode,
                "should_recall_story_memory": memory_presence,
                "reasons": recall_reasons,
                "signal_count": signal_count,
                "consolidation_gap": consolidation_gap,
                "tier_counts": {
                    "consolidated": len(tier_buckets["consolidated"]),
                    "episodic": len(tier_buckets["episodic"]),
                    "working": len(tier_buckets["working"]),
                },
            },
            "priority_foreshadowing": priority_foreshadowing[:5],
            "recent_events": recent_events[-5:],
            "character_focus": character_focus[:5],
            "emotional_focus": emotional_focus[:3],
            "structured_change_focus": structured_change_focus,
            "temporal_window": temporal_window,
            "archive_recall": archive_recall if any(archive_recall.values()) else {},
        }

    def _load_json_optional(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}


def main():
    import argparse
    from .cli_output import print_success, print_error

    parser = argparse.ArgumentParser(description="Context Manager CLI")
    parser.add_argument("--project-root", type=str, help="项目根目录")
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--template", type=str, default=ContextManager.DEFAULT_TEMPLATE)
    parser.add_argument("--no-snapshot", action="store_true")
    parser.add_argument("--max-chars", type=int, default=8000)
    parser.add_argument("--output-file", type=str, default=None, help="输出到指定文件路径（独立输出模式）")

    args = parser.parse_args()

    config = None
    if args.project_root:
        # 允许传入“工作区根目录”，统一解析到真正的 book project_root（必须包含 .webnovel/state.json）
        from project_locator import resolve_project_root
        from .config import DataModulesConfig

        resolved_root = resolve_project_root(args.project_root)
        config = DataModulesConfig.from_project_root(resolved_root)

    manager = ContextManager(config)
    try:
        payload = manager.build_context(
            chapter=args.chapter,
            template=args.template,
            use_snapshot=not args.no_snapshot,
            save_snapshot=True,
            max_chars=args.max_chars,
        )

        # 独立输出模式：写入文件
        if args.output_file:
            output_path = Path(args.output_file)
            protocol_payload = serialize_context_payload(
                payload,
                project_root=manager.config.project_root,
                chapter=args.chapter,
            )
            write_protocol_json(output_path, protocol_payload)
            print(f"Context written to {args.output_file}", file=sys.stderr)
        else:
            print_success(payload, message="context_built")

        try:
            manager.index_manager.log_tool_call("context_manager:build", True, chapter=args.chapter)
        except Exception as exc:
            logger.warning("failed to log successful tool call: %s", exc)
    except Exception as exc:
        friendly = _friendly_context_error(exc)
        print_error("CONTEXT_BUILD_FAILED", friendly, suggestion="请按修复建议补齐章纲/任务书后重试")
        try:
            manager.index_manager.log_tool_call(
                "context_manager:build", False, error_code="CONTEXT_BUILD_FAILED", error_message=friendly, chapter=args.chapter
            )
        except Exception as log_exc:
            logger.warning("failed to log failed tool call: %s", log_exc)


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        enable_windows_utf8_stdio()
    main()
