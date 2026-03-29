#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_chapter_context.py - extract chapter writing context

Features:
- chapter outline snippet
- previous chapter summaries (prefers .webnovel/summaries)
- compact state summary
- ContextManager contract sections (reader_signal / genre_profile / writing_guidance)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from chapter_outline_loader import (
    is_missing_chapter_outline,
    load_chapter_outline,
    validate_chapter_contract,
)

from runtime_compat import enable_windows_utf8_stdio

try:
    from chapter_paths import find_chapter_file
except ImportError:  # pragma: no cover
    from scripts.chapter_paths import find_chapter_file


def _ensure_scripts_path():
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


_RAG_TRIGGER_KEYWORDS = (
    "关系",
    "恩怨",
    "冲突",
    "敌对",
    "同盟",
    "师徒",
    "身份",
    "线索",
    "伏笔",
    "回收",
    "地点",
    "势力",
    "真相",
    "来历",
)


def find_project_root(start_path: Path | None = None) -> Path:
    """解析真实书项目根（包含 `.webnovel/state.json` 的目录）。"""
    from project_locator import resolve_project_root

    if start_path is None:
        return resolve_project_root()
    return resolve_project_root(str(start_path))


def extract_chapter_outline(project_root: Path, chapter_num: int) -> str:
    """Extract chapter outline segment from volume outline file."""
    return load_chapter_outline(project_root, chapter_num, max_chars=1500)


def _detect_outline_missing_reason(project_root: Path, chapter_num: int) -> tuple[str, str]:
    """
    检测大纲缺失的具体原因，用于提供更精确的错误提示。

    Returns:
        (reason, hint): reason 是缺失原因标识，hint 是修复提示
        reason 可能是:
        - "runtime_exists_but_node_missing": outline_runtime.json 存在但当前章节点缺失（动态窗口未生成成功）
        - "volume_exists_but_chapter_missing": 卷详细大纲存在但当前章条目缺失（计划窗口未覆盖）
        - "no_outline_file": 大纲文件完全不存在
    """
    from chapter_outline_loader import has_outline_runtime

    # 1. 检查运行时层
    if has_outline_runtime(project_root):
        try:
            from data_modules.outline_window_parser import load_chapter_outline_node
            node, source = load_chapter_outline_node(project_root, chapter_num)
            if node is not None:
                # 节点存在于运行时层，不应该走到这里
                return ("found", "")
            # 运行时层存在但当前章节节点缺失
            return (
                "runtime_exists_but_node_missing",
                "动态窗口未生成成功，当前章节点尚未创建。请确认写作流程已正确调用动态调纲模块。",
            )
        except ImportError:
            # outline_window_parser 不可用，降级检查
            pass

    # 2. 检查卷详细大纲
    from chapter_outline_loader import _find_volume_outline_file
    volume_file = _find_volume_outline_file(project_root, chapter_num)
    if volume_file is not None:
        # 卷详细大纲存在，尝试验证当前章是否真的不存在
        try:
            content = volume_file.read_text(encoding="utf-8")
            import re
            chapter_pattern = rf"###\s*第\s*{chapter_num}\s*章"
            if re.search(chapter_pattern, content):
                # 章节实际上存在于卷大纲中
                return ("found", "")
            # 卷大纲存在但当前章条目缺失
            return (
                "volume_exists_but_chapter_missing",
                "计划窗口未覆盖当前章节。请在卷详细大纲中补充第{chapter_num}章的章节条目，"
                "或使用动态调纲功能为当前章生成独立大纲。".format(chapter_num=chapter_num),
            )
        except Exception:
            pass

    # 3. 大纲文件完全不存在
    return (
        "no_outline_file",
        "大纲文件不存在。请在 `大纲/` 目录下创建卷详细大纲文件或独立章节大纲文件。",
    )


def ensure_chapter_outline_exists(
    project_root: Path,
    chapter_num: int,
    outline: str | None = None,
    require_contract: bool = True,
    min_state_changes: int = 0,
) -> str:
    """Hard gate: chapter outline must exist and be actionable."""
    resolved = outline if outline is not None else extract_chapter_outline(project_root, chapter_num)
    if is_missing_chapter_outline(resolved):
        # 检测缺失原因，提供更精确的错误提示
        reason, hint = _detect_outline_missing_reason(project_root, chapter_num)
        if reason == "runtime_exists_but_node_missing":
            raise ValueError(
                f"第{chapter_num}章缺少可用大纲（动态窗口未生成）。\n"
                f"{hint}\n"
                f"请确认已完成前一章写作并触发动态调纲。"
            )
        elif reason == "volume_exists_but_chapter_missing":
            raise ValueError(
                f"第{chapter_num}章缺少可用大纲（计划窗口未覆盖）。\n{hint}"
            )
        else:
            raise ValueError(
                f"第{chapter_num}章缺少可用大纲。\n{hint}"
                "请先在`大纲/`中补充对应章节大纲后再执行 /webnovel-write。"
            )
    if require_contract:
        missing = validate_chapter_contract(resolved, min_state_changes=min_state_changes)
        if missing:
            missing_text = "、".join(missing)
            raise ValueError(
                f"第{chapter_num}章大纲缺少关键项：{missing_text}。"
                "请补齐’目标/冲突/动作/结果/代价/钩子’，并至少包含可识别的状态变化。"
            )
    return resolved


def _friendly_context_error(error: Exception) -> str:
    message = str(error)
    hints = ["请先执行 preflight 或 where，确认 project_root 解析正确。"]

    if "动态窗口未生成" in message:
        hints = [
            "动态窗口未生成成功，请检查写作流程是否正确调用了动态调纲模块。",
            "可以手动执行 `/zhizhang-plan` 或 `/zhizhang-adjust` 来生成活动窗口。",
        ]
    elif "计划窗口未覆盖" in message:
        hints = [
            "当前章节未在卷详细大纲中，请使用 `/zhizhang-plan` 补充章节规划。",
            "或者使用 `/zhizhang-adjust` 为当前章生成独立章节大纲。",
        ]
    elif "缺少可用大纲" in message:
        hints = [
            "在 `大纲/` 下补齐目标章节（卷纲切片或独立章节纲均可）。",
            "可先运行 `webnovel.py extract-context --chapter N` 复检是否通过。",
        ]
    elif "缺少关键项" in message or "最小章节契约" in message:
        hints = [
            "在章纲中补齐：目标/冲突/动作/结果/代价/钩子。",
            "建议使用 `字段: 内容` 的结构化写法，便于自动解析。",
        ]
    elif "状态变化" in message:
        hints = [
            "在动作/结果/代价中补充可追踪变化，如：突破/失去/结盟/暴露/受伤/离开。",
            "若项目尚在早期试写，可临时下调 `context_min_state_changes_per_chapter`。",
        ]

    bullet = "\n".join(f"- {item}" for item in hints)
    return f"{message}\n修复建议：\n{bullet}"


def _load_summary_file(project_root: Path, chapter_num: int) -> str:
    """Load summary section from `.webnovel/summaries/chNNNN.md`."""
    summary_path = project_root / ".webnovel" / "summaries" / f"ch{chapter_num:04d}.md"
    if not summary_path.exists():
        return ""

    text = summary_path.read_text(encoding="utf-8")
    summary_match = re.search(r"##\s*剧情摘要\s*\r?\n(.+?)(?=\r?\n##|$)", text, re.DOTALL)
    if summary_match:
        return summary_match.group(1).strip()
    return ""


def extract_chapter_summary(project_root: Path, chapter_num: int) -> str:
    """Extract chapter summary, fallback to chapter body head."""
    summary = _load_summary_file(project_root, chapter_num)
    if summary:
        return summary

    chapter_file = find_chapter_file(project_root, chapter_num)
    if not chapter_file or not chapter_file.exists():
        return f"⚠️ 第{chapter_num}章文件不存在"

    content = chapter_file.read_text(encoding="utf-8")

    summary_match = re.search(r"##\s*本章摘要\s*\r?\n(.+?)(?=\r?\n##|$)", content, re.DOTALL)
    if summary_match:
        return summary_match.group(1).strip()

    stats_match = re.search(r"##\s*本章统计\s*\r?\n(.+?)(?=\r?\n##|$)", content, re.DOTALL)
    if stats_match:
        return f"[无摘要，仅统计]\n{stats_match.group(1).strip()}"

    lines = content.split("\n")
    text_lines = [line for line in lines if not line.startswith("#") and line.strip()]
    text = "\n".join(text_lines)[:500]
    return f"[自动截取前500字]\n{text}..."


def extract_state_summary(project_root: Path) -> str:
    """Extract key fields from `.webnovel/state.json`."""
    state_file = project_root / ".webnovel" / "state.json"
    if not state_file.exists():
        return "⚠️ state.json 不存在"

    state = json.loads(state_file.read_text(encoding="utf-8"))
    summary_parts: List[str] = []

    if "progress" in state:
        progress = state["progress"]
        summary_parts.append(
            f"**进度**: 第{progress.get('current_chapter', '?')}章 / {progress.get('total_words', '?')}字"
        )

    if "protagonist_state" in state:
        ps = state["protagonist_state"]
        power = ps.get("power", {})
        summary_parts.append(f"**主角实力**: {power.get('realm', '?')} {power.get('layer', '?')}层")
        summary_parts.append(f"**当前位置**: {ps.get('location', '?')}")
        golden_finger = ps.get("golden_finger", {})
        summary_parts.append(
            f"**金手指**: {golden_finger.get('name', '?')} Lv.{golden_finger.get('level', '?')}"
        )

    if "strand_tracker" in state:
        tracker = state["strand_tracker"]
        history = tracker.get("history", [])[-5:]
        if history:
            items: List[str] = []
            for row in history:
                if not isinstance(row, dict):
                    continue
                chapter = row.get("chapter", "?")
                strand = row.get("strand") or row.get("dominant") or "unknown"
                items.append(f"Ch{chapter}:{strand}")
            if items:
                summary_parts.append(f"**近5章Strand**: {', '.join(items)}")

    plot_threads = state.get("plot_threads", {}) if isinstance(state.get("plot_threads"), dict) else {}
    foreshadowing = plot_threads.get("foreshadowing", [])
    if isinstance(foreshadowing, list) and foreshadowing:
        active = [row for row in foreshadowing if row.get("status") in {"active", "未回收"}]
        urgent = [row for row in active if row.get("urgency", 0) > 50]
        if urgent:
            urgent_list = [
                f"{row.get('content', '?')[:30]}... (紧急度:{row.get('urgency')})"
                for row in urgent[:3]
            ]
            summary_parts.append(f"**紧急伏笔**: {'; '.join(urgent_list)}")

    return "\n".join(summary_parts)


def _normalize_outline_text(outline: str) -> str:
    text = str(outline or "")
    if not text or text.startswith("⚠️"):
        return ""
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_rag_query(outline: str, chapter_num: int, min_chars: int, max_chars: int) -> str:
    plain = _normalize_outline_text(outline)
    if not plain or len(plain) < min_chars:
        return ""

    if not any(keyword in plain for keyword in _RAG_TRIGGER_KEYWORDS):
        return ""

    if "关系" in plain or "师徒" in plain or "敌对" in plain or "同盟" in plain:
        topic = "人物关系与动机"
    elif "地点" in plain or "势力" in plain:
        topic = "地点势力与场景约束"
    elif "伏笔" in plain or "线索" in plain or "回收" in plain:
        topic = "伏笔与线索"
    else:
        topic = "剧情关键线索"

    clean_max = max(40, int(max_chars))
    return f"第{chapter_num}章 {topic}：{plain[:clean_max]}"


def _search_with_rag(
    project_root: Path,
    chapter_num: int,
    query: str,
    top_k: int,
) -> Dict[str, Any]:
    _ensure_scripts_path()
    from data_modules.config import DataModulesConfig
    from data_modules.rag_adapter import RAGAdapter

    config = DataModulesConfig.from_project_root(project_root)
    adapter = RAGAdapter(config)
    intent_payload = adapter.query_router.route_intent(query)
    center_entities = list(intent_payload.get("entities") or [])

    results = []
    mode = "auto"
    fallback_reason = ""
    has_embed_key = bool(str(getattr(config, "embed_api_key", "") or "").strip())
    if has_embed_key:
        try:
            results = asyncio.run(
                adapter.search(
                    query=query,
                    top_k=top_k,
                    strategy="auto",
                    chapter=chapter_num,
                    center_entities=center_entities,
                )
            )
        except Exception as exc:
            fallback_reason = f"auto_failed:{exc.__class__.__name__}"
            mode = "bm25_fallback"
            results = adapter.bm25_search(query=query, top_k=top_k, chapter=chapter_num)
    else:
        mode = "bm25_fallback"
        fallback_reason = "missing_embed_api_key"
        results = adapter.bm25_search(query=query, top_k=top_k, chapter=chapter_num)

    hits: List[Dict[str, Any]] = []
    for row in results:
        content = re.sub(r"\s+", " ", str(getattr(row, "content", "") or "")).strip()
        hits.append(
            {
                "chunk_id": str(getattr(row, "chunk_id", "") or ""),
                "chapter": int(getattr(row, "chapter", 0) or 0),
                "scene_index": int(getattr(row, "scene_index", 0) or 0),
                "score": round(float(getattr(row, "score", 0.0) or 0.0), 6),
                "source": str(getattr(row, "source", "") or mode),
                "source_file": str(getattr(row, "source_file", "") or ""),
                "content": content[:180],
            }
        )

    return {
        "invoked": True,
        "query": query,
        "mode": mode,
        "reason": fallback_reason or ("ok" if hits else "no_hit"),
        "intent": intent_payload.get("intent"),
        "needs_graph": bool(intent_payload.get("needs_graph")),
        "center_entities": center_entities,
        "hits": hits,
    }


def _load_rag_assist(project_root: Path, chapter_num: int, outline: str) -> Dict[str, Any]:
    _ensure_scripts_path()
    from data_modules.config import DataModulesConfig

    config = DataModulesConfig.from_project_root(project_root)
    enabled = bool(getattr(config, "context_rag_assist_enabled", True))
    top_k = max(1, int(getattr(config, "context_rag_assist_top_k", 4)))
    min_chars = max(20, int(getattr(config, "context_rag_assist_min_outline_chars", 40)))
    max_chars = max(40, int(getattr(config, "context_rag_assist_max_query_chars", 120)))
    base_payload = {"enabled": enabled, "invoked": False, "reason": "", "query": "", "hits": []}

    if not enabled:
        base_payload["reason"] = "disabled_by_config"
        return base_payload

    query = _build_rag_query(outline, chapter_num=chapter_num, min_chars=min_chars, max_chars=max_chars)
    if not query:
        base_payload["reason"] = "outline_not_actionable"
        return base_payload

    vector_db = config.vector_db
    if not vector_db.exists() or vector_db.stat().st_size <= 0:
        base_payload["reason"] = "vector_db_missing_or_empty"
        return base_payload

    try:
        rag_payload = _search_with_rag(project_root=project_root, chapter_num=chapter_num, query=query, top_k=top_k)
        rag_payload["enabled"] = True
        return rag_payload
    except Exception as exc:
        base_payload["reason"] = f"rag_error:{exc.__class__.__name__}"
        return base_payload


def _load_contract_context(project_root: Path, chapter_num: int) -> Dict[str, Any]:
    """Build context via ContextManager and return selected sections."""
    _ensure_scripts_path()
    from data_modules.config import DataModulesConfig
    from data_modules.context_manager import ContextManager

    config = DataModulesConfig.from_project_root(project_root)
    manager = ContextManager(config)
    payload = manager.build_context(
        chapter=chapter_num,
        template="plot",
        use_snapshot=True,
        save_snapshot=True,
        max_chars=8000,
    )

    sections = payload.get("sections", {})
    return {
        "context_contract_version": (payload.get("meta") or {}).get("context_contract_version"),
        "context_weight_stage": (payload.get("meta") or {}).get("context_weight_stage"),
        "memory": (sections.get("memory") or {}).get("content", {}),
        "story_recall": (sections.get("story_recall") or {}).get("content", {}),
        "chapter_intent": (sections.get("chapter_intent") or {}).get("content", {}),
        "chapter_technique_plan": (sections.get("chapter_technique_plan") or {}).get("content", {}),
        "reader_signal": (sections.get("reader_signal") or {}).get("content", {}),
        "genre_profile": (sections.get("genre_profile") or {}).get("content", {}),
        "story_technique_blueprint": (sections.get("story_technique_blueprint") or {}).get("content", {}),
        "writing_guidance": (sections.get("writing_guidance") or {}).get("content", {}),
    }


def build_chapter_context_payload(project_root: Path, chapter_num: int) -> Dict[str, Any]:
    """Assemble full chapter context payload for text/json output."""
    _ensure_scripts_path()
    from data_modules.config import DataModulesConfig

    config = DataModulesConfig.from_project_root(project_root)
    outline = ensure_chapter_outline_exists(
        project_root,
        chapter_num,
        require_contract=bool(getattr(config, "context_require_chapter_contract", True)),
        min_state_changes=max(0, int(getattr(config, "context_min_state_changes_per_chapter", 0))),
    )

    prev_summaries = []
    for prev_ch in range(max(1, chapter_num - 2), chapter_num):
        summary = extract_chapter_summary(project_root, prev_ch)
        prev_summaries.append(f"### 第{prev_ch}章摘要\n{summary}")

    state_summary = extract_state_summary(project_root)
    contract_context = _load_contract_context(project_root, chapter_num)
    rag_assist = _load_rag_assist(project_root, chapter_num, outline)
    memory_section = contract_context.get("memory", {}) if isinstance(contract_context, dict) else {}

    return {
        "chapter": chapter_num,
        "outline": outline,
        "previous_summaries": prev_summaries,
        "state_summary": state_summary,
        "context_contract_version": contract_context.get("context_contract_version"),
        "context_weight_stage": contract_context.get("context_weight_stage"),
        "memory": contract_context.get("memory", {}),
        "story_recall": contract_context.get("story_recall", {}),
        "chapter_intent": contract_context.get("chapter_intent", {}),
        "chapter_technique_plan": contract_context.get("chapter_technique_plan", {}),
        "reader_signal": contract_context.get("reader_signal", {}),
        "genre_profile": contract_context.get("genre_profile", {}),
        "story_technique_blueprint": contract_context.get("story_technique_blueprint", {}),
        "writing_guidance": contract_context.get("writing_guidance", {}),
        "story_memory": memory_section.get("story_memory", {}),
        "story_memory_meta": memory_section.get("story_memory_meta", {}),
        "rag_assist": rag_assist,
    }


def _render_text(payload: Dict[str, Any]) -> str:
    chapter_num = payload.get("chapter")
    lines: List[str] = []

    lines.append(f"# 第 {chapter_num} 章创作上下文")
    lines.append("")

    lines.append("## 本章大纲")
    lines.append("")
    lines.append(str(payload.get("outline", "")))
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 前文摘要")
    lines.append("")
    for item in payload.get("previous_summaries", []):
        lines.append(item)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 当前状态")
    lines.append("")
    lines.append(str(payload.get("state_summary", "")))
    lines.append("")

    chapter_intent = payload.get("chapter_intent") or {}
    if chapter_intent:
        lines.append("## 本章任务书")
        lines.append("")
        if chapter_intent.get("focus_title"):
            lines.append(f"- 当前焦点: {chapter_intent.get('focus_title')}")
        if chapter_intent.get("chapter_goal"):
            lines.append(f"- chapter_goal: {chapter_intent.get('chapter_goal')}")
        must_resolve = chapter_intent.get("must_resolve") or []
        if must_resolve:
            lines.append("- must_resolve:")
            for item in must_resolve:
                lines.append(f"  - {item}")
        story_risks = chapter_intent.get("story_risks") or []
        if story_risks:
            lines.append("- story_risks:")
            for item in story_risks:
                lines.append(f"  - {item}")
        hard_constraints = chapter_intent.get("hard_constraints") or []
        if hard_constraints:
            lines.append("- hard_constraints:")
            for item in hard_constraints:
                lines.append(f"  - {item}")
        priority_memory = chapter_intent.get("priority_memory") or []
        if priority_memory:
            lines.append("- priority_memory:")
            for item in priority_memory[:4]:
                if not isinstance(item, dict):
                    lines.append(f"  - {item}")
                    continue
                lines.append(f"  - [{item.get('type')}] {item.get('label')}: {item.get('detail')}")
        lines.append("")

    story_recall = payload.get("story_recall") or {}
    if story_recall:
        lines.append("## 高优先级召回")
        lines.append("")
        if story_recall.get("last_consolidated_chapter") is not None:
            lines.append(f"- last_consolidated_chapter: {story_recall.get('last_consolidated_chapter')}")
        recall_policy = story_recall.get("recall_policy") or {}
        if recall_policy:
            lines.append(
                f"- recall_policy: mode={recall_policy.get('mode')} "
                f"should_recall={recall_policy.get('should_recall_story_memory')} "
                f"signals={recall_policy.get('signal_count')} "
                f"gap={recall_policy.get('consolidation_gap')}"
            )
            reasons = recall_policy.get("reasons") or []
            if reasons:
                lines.append(f"  - reasons: {', '.join(str(reason) for reason in reasons)}")
        priority_foreshadowing = story_recall.get("priority_foreshadowing") or []
        if priority_foreshadowing:
            lines.append("- 未回收伏笔:")
            for row in priority_foreshadowing[:5]:
                if not isinstance(row, dict):
                    continue
                label = str(row.get("name") or row.get("content") or row.get("event") or "未命名伏笔")
                urgency = row.get("urgency")
                if urgency is not None:
                    lines.append(f"  - {label}（urgency={urgency}）")
                else:
                    lines.append(f"  - {label}")
        character_focus = story_recall.get("character_focus") or []
        if character_focus:
            lines.append("- 关键人物:")
            for row in character_focus[:5]:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "未命名角色")
                state_text = str(row.get("current_state") or "—")
                last_update = row.get("last_update_chapter") or "—"
                lines.append(f"  - {name}: {state_text}（Ch.{last_update}）")
        emotional_focus = story_recall.get("emotional_focus") or []
        if emotional_focus:
            lines.append("- 情绪弧线:")
            for row in emotional_focus[:3]:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"  - {row.get('name')}: {row.get('emotional_state') or '—'} / {row.get('emotional_trend') or 'stable'}"
                    f"（触发: {row.get('trigger_event') or '—'}，Ch.{row.get('chapter') or '—'}）"
                )
        change_focus = story_recall.get("structured_change_focus") or []
        if change_focus:
            lines.append("- 结构化变化账本:")
            for row in change_focus[:5]:
                if not isinstance(row, dict):
                    continue
                entity_id = str(row.get("entity_id") or "—")
                field = str(row.get("field") or "—")
                delta = row.get("delta")
                old_value = row.get("old_value")
                new_value = row.get("new_value")
                change_kind = str(row.get("change_kind") or "state_change")
                memory_score = row.get("memory_score")
                memory_tier = row.get("memory_tier")
                lines.append(f"  - [{change_kind}/{memory_tier}/score={memory_score}] {entity_id}.{field}: {old_value} -> {new_value}（Δ{delta}）")
        recent_events = story_recall.get("recent_events") or []
        if recent_events:
            lines.append("- 最近事件:")
            for row in recent_events[:5]:
                if not isinstance(row, dict):
                    continue
                ch = row.get("ch") or row.get("chapter") or "?"
                event = row.get("event") or row.get("content") or "—"
                lines.append(f"  - Ch.{ch}: {event}")
        temporal_window = story_recall.get("temporal_window") or {}
        if temporal_window:
            lines.append("- 时序窗口召回:")
            lines.append(
                f"  - 范围: Ch.{temporal_window.get('from_chapter') or '?'} ~ Ch.{temporal_window.get('to_chapter') or '?'}"
            )
            chapters = temporal_window.get("chapters") or []
            if chapters:
                lines.append("  - 章节切片:")
                for row in chapters[:3]:
                    if not isinstance(row, dict):
                        continue
                    lines.append(f"    - Ch.{row.get('chapter')}: {row.get('title') or '—'}")
            state_changes = temporal_window.get("state_changes") or []
            if state_changes:
                lines.append("  - 窗口状态变化:")
                for row in state_changes[:3]:
                    if not isinstance(row, dict):
                        continue
                    lines.append(
                        f"    - Ch.{row.get('chapter')}: {row.get('entity_id')}.{row.get('field')} {row.get('old_value')} -> {row.get('new_value')}"
                    )
            relationship_events = temporal_window.get("relationship_events") or []
            if relationship_events:
                lines.append("  - 窗口关系事件:")
                for row in relationship_events[:3]:
                    if not isinstance(row, dict):
                        continue
                    lines.append(
                        f"    - Ch.{row.get('chapter')}: {row.get('from_entity')} -> {row.get('to_entity')} / {row.get('type')}"
                    )
        archive_recall = story_recall.get("archive_recall") or {}
        if archive_recall:
            lines.append("- 归档召回:")
            archived_threads = archive_recall.get("plot_threads") or []
            if archived_threads:
                lines.append("  - 归档伏笔:")
                for row in archived_threads[:3]:
                    if not isinstance(row, dict):
                        continue
                    label = str(row.get("content") or row.get("event") or "未命名伏笔")
                    lines.append(f"    - {label}（tier={row.get('memory_tier')}, score={row.get('archive_score')}）")
            archived_events = archive_recall.get("recent_events") or []
            if archived_events:
                lines.append("  - 归档事件:")
                for row in archived_events[:3]:
                    if not isinstance(row, dict):
                        continue
                    ch = row.get("ch") or row.get("chapter") or "?"
                    event = row.get("event") or "—"
                    lines.append(f"    - Ch.{ch}: {event}")
            archived_changes = archive_recall.get("structured_change_focus") or []
            if archived_changes:
                lines.append("  - 归档变化:")
                for row in archived_changes[:3]:
                    if not isinstance(row, dict):
                        continue
                    entity_id = str(row.get("entity_id") or "—")
                    field = str(row.get("field") or "—")
                    lines.append(f"    - {entity_id}.{field}（tier={row.get('memory_tier')}, score={row.get('archive_score')}）")
        lines.append("")

    story_memory = payload.get("story_memory") or {}
    story_memory_meta = payload.get("story_memory_meta") or {}
    if story_memory_meta or story_memory:
        lines.append("## 故事记忆")
        lines.append("")
        if story_memory_meta:
            version = story_memory_meta.get("version") or "unknown"
            chapter = story_memory_meta.get("last_consolidated_chapter") or 0
            updated_at = story_memory_meta.get("last_consolidated_at") or ""
            lines.append(f"- version: {version}")
            lines.append(f"- last_consolidated_chapter: {chapter}")
            if updated_at:
                lines.append(f"- last_consolidated_at: {updated_at}")
        characters = story_memory.get("characters") or {}
        if characters:
            lines.append("- 角色摘要:")
            for name, info in list(characters.items())[:5]:
                if not isinstance(info, dict):
                    continue
                current_state = info.get("current_state") or "—"
                last_update = info.get("last_update_chapter") or "—"
                lines.append(f"  - {name}: {current_state}（Ch.{last_update}）")
        plot_threads = story_memory.get("plot_threads") or []
        if plot_threads:
            pending_threads = [row for row in plot_threads if isinstance(row, dict) and str(row.get("status") or "").lower() in {"pending", "active", "未回收"}]
            if pending_threads:
                lines.append("- 未回收伏笔:")
                for row in pending_threads[:5]:
                    content = str(row.get("name") or row.get("event") or row.get("content") or "未命名伏笔")
                    lines.append(f"  - {content}")
        recent_events = story_memory.get("recent_events") or []
        if recent_events:
            lines.append("- 近章重大事件:")
            for row in recent_events[:5]:
                if not isinstance(row, dict):
                    continue
                ch = row.get("ch") or row.get("chapter") or "?"
                event = row.get("event") or row.get("content") or "—"
                lines.append(f"  - Ch.{ch}: {event}")
        emotional_arcs = story_memory.get("emotional_arcs") or {}
        if emotional_arcs:
            lines.append("- 情感弧线:")
            for name, rows in list(emotional_arcs.items())[:3]:
                if not isinstance(rows, list) or not rows:
                    continue
                latest = rows[-1]
                if not isinstance(latest, dict):
                    continue
                lines.append(
                    f"  - {name}: {latest.get('emotional_state') or '—'} / {latest.get('emotional_trend') or 'stable'}"
                    f"（Ch.{latest.get('chapter') or '—'}）"
                )
        lines.append("")

    contract_version = payload.get("context_contract_version")
    if contract_version:
        lines.append(f"## Contract ({contract_version})")
        lines.append("")
        stage = payload.get("context_weight_stage")
        if stage:
            lines.append(f"- 上下文阶段权重: {stage}")
            lines.append("")

    chapter_technique_plan = payload.get("chapter_technique_plan") or {}
    if chapter_technique_plan:
        lines.append("## 章节技巧编排")
        lines.append("")
        lines.append(f"- 章型: {chapter_technique_plan.get('scene_role')}")
        opening_hook = chapter_technique_plan.get("opening_hook") or {}
        if opening_hook:
            if isinstance(opening_hook, dict):
                lines.append(f"- 开篇钩子: {opening_hook.get('type')} / {opening_hook.get('goal')}")
            else:
                lines.append(f"- 开篇钩子: {opening_hook}")
        mid_payoffs = chapter_technique_plan.get("mid_payoffs") or []
        if mid_payoffs:
            lines.append(f"- 章中微兑现: {', '.join(str(item) for item in mid_payoffs)}")
        climax_patterns = chapter_technique_plan.get("climax_patterns") or []
        if climax_patterns:
            lines.append(f"- 高潮模式: {', '.join(str(item) for item in climax_patterns)}")
        ending_hook = chapter_technique_plan.get("ending_hook") or {}
        if ending_hook:
            if isinstance(ending_hook, dict):
                lines.append(f"- 章末钩子: {ending_hook.get('type')} / {ending_hook.get('goal')}")
            else:
                lines.append(f"- 章末钩子: {ending_hook}")
        rhythm = chapter_technique_plan.get("paragraph_rhythm") or []
        if rhythm:
            lines.append(f"- 段落节拍: {' → '.join(str(item) for item in rhythm)}")
        anti_template = chapter_technique_plan.get("anti_template_constraints") or []
        if anti_template:
            lines.append("- 反模板约束:")
            for item in anti_template[:3]:
                lines.append(f"  - {item}")
        lines.append("")

    writing_guidance = payload.get("writing_guidance") or {}
    guidance_items = writing_guidance.get("guidance_items") or []
    checklist = writing_guidance.get("checklist") or []
    checklist_score = writing_guidance.get("checklist_score") or {}
    methodology = writing_guidance.get("methodology") or {}
    if guidance_items or checklist:
        lines.append("## 写作执行建议")
        lines.append("")
        for idx, item in enumerate(guidance_items, start=1):
            lines.append(f"{idx}. {item}")

        if checklist:
            total_weight = 0.0
            required_count = 0
            for row in checklist:
                if isinstance(row, dict):
                    try:
                        total_weight += float(row.get("weight") or 0)
                    except (TypeError, ValueError):
                        pass
                    if row.get("required"):
                        required_count += 1

            lines.append("")
            lines.append("### 执行检查清单（可评分）")
            lines.append("")
            lines.append(f"- 项目数: {len(checklist)}")
            lines.append(f"- 总权重: {total_weight:.2f}")
            lines.append(f"- 必做项: {required_count}")
            lines.append("")

            for idx, row in enumerate(checklist, start=1):
                if not isinstance(row, dict):
                    lines.append(f"{idx}. {row}")
                    continue
                label = str(row.get("label") or "").strip() or "未命名项"
                weight = row.get("weight")
                required_tag = "必做" if row.get("required") else "可选"
                verify_hint = str(row.get("verify_hint") or "").strip()
                lines.append(f"{idx}. [{required_tag}][w={weight}] {label}")
                if verify_hint:
                    lines.append(f"   - 验收: {verify_hint}")

        if checklist_score:
            lines.append("")
            lines.append("### 执行评分")
            lines.append("")
            lines.append(f"- 评分: {checklist_score.get('score')}")
            lines.append(f"- 完成率: {checklist_score.get('completion_rate')}")
            lines.append(f"- 必做完成率: {checklist_score.get('required_completion_rate')}")

        lines.append("")

    if isinstance(methodology, dict) and methodology.get("enabled"):
        lines.append("## 长篇方法论策略")
        lines.append("")
        lines.append(f"- 框架: {methodology.get('framework')}")
        methodology_scope = methodology.get("genre_profile_key") or methodology.get("pilot") or "general"
        lines.append(f"- 适用题材: {methodology_scope}")
        lines.append(f"- 章节阶段: {methodology.get('chapter_stage')}")
        observability = methodology.get("observability") or {}
        if observability:
            lines.append(
                "- 指标: "
                f"next_reason={observability.get('next_reason_clarity')}, "
                f"anchor={observability.get('anchor_effectiveness')}, "
                f"rhythm={observability.get('rhythm_naturalness')}"
            )
        signals = methodology.get("signals") or {}
        risk_flags = list(signals.get("risk_flags") or [])
        if risk_flags:
            lines.append(f"- 风险标记: {', '.join(str(flag) for flag in risk_flags)}")
        lines.append("")

    reader_signal = payload.get("reader_signal") or {}
    review_trend = reader_signal.get("review_trend") or {}
    if review_trend:
        overall_avg = review_trend.get("overall_avg")
        lines.append("## 追读信号")
        lines.append("")
        lines.append(f"- 最近审查均分: {overall_avg}")
        low_ranges = reader_signal.get("low_score_ranges") or []
        if low_ranges:
            lines.append(f"- 低分区间数: {len(low_ranges)}")
        lines.append("")

    genre_profile = payload.get("genre_profile") or {}
    if genre_profile.get("genre"):
        lines.append("## 题材锚定")
        lines.append("")
        lines.append(f"- 题材: {genre_profile.get('genre')}")
        genres = genre_profile.get("genres") or []
        if len(genres) > 1:
            lines.append(f"- 复合题材: {' + '.join(str(token) for token in genres)}")
            composite_hints = genre_profile.get("composite_hints") or []
            for row in composite_hints[:2]:
                lines.append(f"- {row}")
        refs = genre_profile.get("reference_hints") or []
        for row in refs[:3]:
            lines.append(f"- {row}")
            lines.append("")

    story_technique_blueprint = payload.get("story_technique_blueprint") or {}
    if story_technique_blueprint:
        lines.append("## 项目技巧蓝图")
        lines.append("")
        lines.append(f"- 主题材画像: {story_technique_blueprint.get('primary_profile')}")
        lines.append(f"- 降级策略: {story_technique_blueprint.get('generalized_strategy')}")
        genre_strategy = story_technique_blueprint.get("genre_strategy") or {}
        hook_pool = genre_strategy.get("hook_pool") or []
        if hook_pool:
            lines.append(f"- 钩子池: {', '.join(str(item) for item in hook_pool[:4])}")
        coolpoint_pool = genre_strategy.get("coolpoint_pool") or []
        if coolpoint_pool:
            lines.append(f"- 爽点池: {', '.join(str(item) for item in coolpoint_pool[:4])}")
        anti_template = story_technique_blueprint.get("anti_template_constraints") or []
        if anti_template:
            lines.append(f"- 反模板化: {'; '.join(str(item) for item in anti_template[:3])}")
        lines.append("")

    previous_meta_style = []
    for item in payload.get("story_recall", {}).get("recent_events", []):
        if isinstance(item, dict) and str(item.get("type") or "") == "style_fatigue":
            previous_meta_style.append(str(item.get("event") or "语言疲劳告警"))
    if previous_meta_style:
        lines.append("## 语言疲劳信号")
        lines.append("")
        for item in previous_meta_style[:3]:
            lines.append(f"- {item}")
        lines.append("")

    rag_assist = payload.get("rag_assist") or {}
    hits = rag_assist.get("hits") or []
    if rag_assist.get("invoked") and hits:
        lines.append("## RAG 检索线索")
        lines.append("")
        lines.append(f"- 模式: {rag_assist.get('mode')}")
        lines.append(f"- 意图: {rag_assist.get('intent')}")
        lines.append(f"- 查询: {rag_assist.get('query')}")
        lines.append("")
        for idx, row in enumerate(hits[:5], start=1):
            chapter = row.get("chapter", "?")
            scene_index = row.get("scene_index", "?")
            score = row.get("score", 0)
            source = row.get("source", "unknown")
            content = row.get("content", "")
            lines.append(f"{idx}. [Ch{chapter}-S{scene_index}][{source}][score={score}] {content}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="提取章节创作所需的精简上下文")
    parser.add_argument("--chapter", type=int, required=True, help="目标章节号")
    parser.add_argument("--project-root", type=str, help="项目根目录")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")

    args = parser.parse_args()

    try:
        project_root = (
            find_project_root(Path(args.project_root))
            if args.project_root
            else find_project_root()
        )
        payload = build_chapter_context_payload(project_root, args.chapter)

        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(_render_text(payload), end="")

    except Exception as exc:
        print(f"❌ 错误: {_friendly_context_error(exc)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if sys.platform == "win32":
        enable_windows_utf8_stdio()
    main()
