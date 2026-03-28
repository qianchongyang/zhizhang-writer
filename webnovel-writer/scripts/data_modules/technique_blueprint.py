#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Story technique blueprint + chapter technique plan helpers.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

from .genre_aliases import normalize_genre_token, to_profile_key


SUPPORTED_PRIORITY_GENRES = {
    "shuangwen",
    "xianxia",
    "romance",
    "mystery",
    "rules-mystery",
    "urban-power",
}

GENERALIZED_PROFILE_MAP = {
    "zhihu-short": "shuangwen",
    "substitute": "romance",
    "esports": "urban-power",
    "livestream": "urban-power",
    "cosmic-horror": "mystery",
    "history-travel": "urban-power",
    "game-lit": "shuangwen",
}

PROFILE_BLUEPRINTS: dict[str, dict[str, Any]] = {
    "shuangwen": {
        "platform_style": "高频付费连载",
        "hook_pool": ["渴望钩", "危机钩", "选择钩", "情绪钩"],
        "coolpoint_pool": ["装逼打脸", "扮猪吃虎", "越级反杀", "反派翻车"],
        "micropayoff_pool": ["能力兑现", "资源兑现", "认可兑现"],
        "non_routine_pool": ["规则内突破", "代价型胜利", "延迟反杀"],
        "anti_exposition_rules": ["设定通过冲突显露", "避免连续说明性对白", "战果必须有可见反馈"],
        "anti_template_rules": ["避免连续3章同构打脸", "避免空喊震惊无后果", "避免无代价碾压"],
        "info_density_baseline": "high",
        "default_scene_role_cycle": ["build_up", "confront", "release"],
    },
    "xianxia": {
        "platform_style": "升级驱动长篇连载",
        "hook_pool": ["危机钩", "渴望钩", "悬念钩", "选择钩"],
        "coolpoint_pool": ["越级反杀", "扮猪吃虎", "身份掉马", "反派翻车"],
        "micropayoff_pool": ["能力兑现", "资源兑现", "信息兑现"],
        "non_routine_pool": ["规则利用", "长线布局", "牺牲换胜利"],
        "anti_exposition_rules": ["境界说明后置", "设定通过试炼/代价展现", "突破后必须交代余波"],
        "anti_template_rules": ["避免纯数值播报", "避免一章多次重复顿悟", "避免反派纯工具人"],
        "info_density_baseline": "medium-high",
        "default_scene_role_cycle": ["build_up", "build_up", "confront", "release"],
    },
    "romance": {
        "platform_style": "关系位移驱动连载",
        "hook_pool": ["情绪钩", "选择钩", "渴望钩", "悬念钩"],
        "coolpoint_pool": ["甜蜜超预期", "身份掉马", "反派翻车", "误会反转"],
        "micropayoff_pool": ["关系兑现", "情绪兑现", "认可兑现"],
        "non_routine_pool": ["克制型心动", "代价型和解", "立场冲突下靠近"],
        "anti_exposition_rules": ["关系通过动作和反应显露", "避免角色直接解释爱意", "冲突优先于讲道理"],
        "anti_template_rules": ["避免连续误会拉扯不前进", "避免台词全是结论句", "避免角色反应失真"],
        "info_density_baseline": "medium",
        "default_scene_role_cycle": ["build_up", "confront", "release"],
    },
    "mystery": {
        "platform_style": "线索递进式连载",
        "hook_pool": ["悬念钩", "危机钩", "选择钩", "情绪钩"],
        "coolpoint_pool": ["身份掉马", "反派翻车", "信息反转", "规则破解"],
        "micropayoff_pool": ["信息兑现", "线索兑现", "关系兑现"],
        "non_routine_pool": ["伪答案回收", "规则反噬", "视角误导反转"],
        "anti_exposition_rules": ["规则先于解释", "线索通过现场细节显露", "避免一次性倒知识"],
        "anti_template_rules": ["避免假悬念", "避免机械降神", "避免谜底无前置支撑"],
        "info_density_baseline": "medium",
        "default_scene_role_cycle": ["build_up", "confront", "confront", "release"],
    },
    "rules-mystery": {
        "platform_style": "规则压迫式连载",
        "hook_pool": ["悬念钩", "危机钩", "选择钩"],
        "coolpoint_pool": ["规则破解", "身份掉马", "反派翻车", "代价换突破"],
        "micropayoff_pool": ["信息兑现", "生存兑现", "关系兑现"],
        "non_routine_pool": ["规则漏洞", "高代价破局", "次级规则揭露"],
        "anti_exposition_rules": ["规则先给后验", "代价先于胜利", "禁止说明书式灌输"],
        "anti_template_rules": ["避免规则自打脸", "避免低代价轻松通关", "避免解释压过恐怖感"],
        "info_density_baseline": "medium-high",
        "default_scene_role_cycle": ["build_up", "confront", "release"],
    },
    "urban-power": {
        "platform_style": "社会反馈链式连载",
        "hook_pool": ["危机钩", "渴望钩", "情绪钩", "选择钩"],
        "coolpoint_pool": ["打脸权威", "装逼打脸", "反派翻车", "身份掉马"],
        "micropayoff_pool": ["资源兑现", "认可兑现", "地位兑现"],
        "non_routine_pool": ["知识解题", "多线影响", "规则内突破"],
        "anti_exposition_rules": ["社会反馈前置", "解释通过结果倒逼", "避免行业设定硬塞对白"],
        "anti_template_rules": ["避免龙套齐声震惊", "避免每章都靠同一种打脸", "避免反派纯恶无动机"],
        "info_density_baseline": "high",
        "default_scene_role_cycle": ["build_up", "confront", "release"],
    },
}

GENERAL_FALLBACK_BLUEPRINT = {
    "platform_style": "通用长篇连载",
    "hook_pool": ["危机钩", "渴望钩", "悬念钩"],
    "coolpoint_pool": ["反派翻车", "身份掉马", "信息反转"],
    "micropayoff_pool": ["信息兑现", "关系兑现", "认可兑现"],
    "non_routine_pool": ["代价型胜利", "规则利用", "延迟兑现"],
    "anti_exposition_rules": ["设定通过情节显露", "避免说明性对白过长", "优先动作-结果闭环"],
    "anti_template_rules": ["避免连续重复同构钩子", "避免一章只有解释没有结果"],
    "info_density_baseline": "medium",
    "default_scene_role_cycle": ["build_up", "confront", "release"],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _split_genres(raw_genre: str) -> List[str]:
    raw = str(raw_genre or "").strip()
    if not raw:
        return []
    raw = re.sub(r"[＋/、|]", "+", raw)
    raw = raw.replace("与", "+")
    tokens = [normalize_genre_token(token.strip()) for token in raw.split("+") if token.strip()]
    return [token for token in tokens if token]


def _resolve_primary_profile(genres: List[str]) -> tuple[str, bool, str]:
    if not genres:
        return "shuangwen", False, ""
    original_profile = to_profile_key(genres[0])
    profile = original_profile
    generalized = False
    if profile not in SUPPORTED_PRIORITY_GENRES:
        generalized = True
        profile = GENERALIZED_PROFILE_MAP.get(profile, "shuangwen")
    return profile, generalized, original_profile


def normalize_project_memory(raw_project_memory: Any) -> Dict[str, Any]:
    if not isinstance(raw_project_memory, Mapping):
        raw_project_memory = {}

    normalized: Dict[str, Any] = {
        "patterns": [],
        "technique_patterns": [],
        "technique_execution_history": [],
        "technique_summary": {
            "effective": [],
            "fatigue": [],
            "last_updated": "",
        },
    }

    patterns = raw_project_memory.get("patterns")
    if isinstance(patterns, list):
        for item in patterns:
            if not isinstance(item, Mapping):
                continue
            normalized["patterns"].append(
                {
                    "pattern_type": str(item.get("pattern_type") or "hook"),
                    "description": str(item.get("description") or ""),
                    "source_chapter": int(item.get("source_chapter") or 0),
                    "learned_at": str(item.get("learned_at") or ""),
                }
            )

    technique_patterns = raw_project_memory.get("technique_patterns")
    if isinstance(technique_patterns, list):
        for item in technique_patterns:
            if not isinstance(item, Mapping):
                continue
            normalized["technique_patterns"].append(
                {
                    "technique_id": str(item.get("technique_id") or item.get("id") or ""),
                    "type": str(item.get("type") or item.get("pattern_type") or "technique"),
                    "description": str(item.get("description") or ""),
                    "genre_scope": str(item.get("genre_scope") or "general"),
                    "scene_role": str(item.get("scene_role") or ""),
                    "effectiveness": str(item.get("effectiveness") or "neutral"),
                    "source_chapter": int(item.get("source_chapter") or 0),
                    "last_used_chapter": int(item.get("last_used_chapter") or 0),
                    "use_count": int(item.get("use_count") or 0),
                    "tags": [str(tag) for tag in (item.get("tags") or []) if str(tag).strip()],
                    "learned_at": str(item.get("learned_at") or ""),
                }
            )

    execution_history = raw_project_memory.get("technique_execution_history")
    if isinstance(execution_history, list):
        for item in execution_history:
            if not isinstance(item, Mapping):
                continue
            normalized["technique_execution_history"].append(
                {
                    "chapter": int(item.get("chapter") or 0),
                    "genre": str(item.get("genre") or "general"),
                    "scene_role": str(item.get("scene_role") or ""),
                    "applied": [str(token) for token in (item.get("applied") or []) if str(token).strip()],
                    "failed": [str(token) for token in (item.get("failed") or []) if str(token).strip()],
                    "signals": dict(item.get("signals") or {}),
                    "overall_score": item.get("overall_score"),
                    "recorded_at": str(item.get("recorded_at") or ""),
                }
            )

    summary = raw_project_memory.get("technique_summary")
    if isinstance(summary, Mapping):
        normalized["technique_summary"] = {
            "effective": [str(token) for token in (summary.get("effective") or []) if str(token).strip()],
            "fatigue": [str(token) for token in (summary.get("fatigue") or []) if str(token).strip()],
            "last_updated": str(summary.get("last_updated") or ""),
        }

    return normalized


def load_project_memory(path: Path) -> Dict[str, Any]:
    payload = normalize_project_memory(_read_json(path))
    if not path.exists():
        _write_json(path, payload)
    return payload


def save_project_memory(path: Path, payload: Dict[str, Any]) -> None:
    _write_json(path, normalize_project_memory(payload))


def _infer_behavior_model(project: Mapping[str, Any], protagonist: Mapping[str, Any]) -> Dict[str, Any]:
    desire = str(project.get("protagonist_desire") or protagonist.get("desire") or "").strip()
    flaw = str(project.get("protagonist_flaw") or protagonist.get("flaw") or "").strip()
    archetype = str(project.get("protagonist_archetype") or protagonist.get("archetype") or "").strip()
    dialogue_style = "直白、目标导向"
    if any(token in archetype for token in ("腹黑", "权谋", "反派")):
        dialogue_style = "克制、试探、留后手"
    elif any(token in archetype for token in ("甜", "治愈", "社牛")):
        dialogue_style = "主动、情绪外显、带拉近感"

    return {
        "public_trait": archetype or "成长型主角",
        "hidden_trait": flaw or "遇压后会暴露真实脆弱点",
        "self_belief": desire or "必须拿到阶段性胜利",
        "pressure_trigger": "身份/资源/关系受到压制时立即反应",
        "stress_response": flaw or "先顶住压力，再寻找破局手段",
        "victory_response": "胜利后必须有可见余波、收获或关系位移",
        "shame_response": "遭遇羞辱/失败后形成下一步行动动机",
        "choice_bias": "优先保主线目标，再决定情绪回应",
        "dialogue_style": dialogue_style,
    }


def build_story_technique_blueprint(
    state: Mapping[str, Any],
    project_memory: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    project = dict(state.get("project_info") or state.get("project") or {})
    protagonist = dict(state.get("protagonist_state") or {})
    raw_genre = str(project.get("genre") or "")
    genres = _split_genres(raw_genre) or ["爽文/系统流"]
    primary_profile, generalized, original_profile = _resolve_primary_profile(genres)
    defaults = deepcopy(PROFILE_BLUEPRINTS.get(primary_profile, GENERAL_FALLBACK_BLUEPRINT))
    platform = str(project.get("platform") or "通用平台").strip() or "通用平台"
    target_reader = str(project.get("target_reader") or "网文主流付费读者").strip() or "网文主流付费读者"
    memory = normalize_project_memory(project_memory or {})
    summary = memory.get("technique_summary") or {}

    protagonist_name = str(protagonist.get("name") or project.get("protagonist_name") or "").strip()
    if not protagonist_name:
        protagonist_name = "主角"

    return {
        "version": "v1",
        "generated_at": _utc_now(),
        "project_title": str(project.get("title") or ""),
        "platform": platform,
        "target_reader": target_reader,
        "genres": genres,
        "primary_profile": primary_profile,
        "original_profile": original_profile or primary_profile,
        "generalized_strategy": generalized,
        "supported_priority_profile": primary_profile in SUPPORTED_PRIORITY_GENRES,
        "platform_strategy": {
            "style": defaults["platform_style"],
            "platform": platform,
            "reader_contract": f"{target_reader}偏好更快获得情绪回报与下一章理由",
        },
        "genre_strategy": {
            "profile": primary_profile,
            "hook_pool": defaults["hook_pool"],
            "coolpoint_pool": defaults["coolpoint_pool"],
            "micropayoff_pool": defaults["micropayoff_pool"],
            "non_routine_pool": defaults["non_routine_pool"],
            "info_density_baseline": defaults["info_density_baseline"],
            "scene_role_cycle": defaults["default_scene_role_cycle"],
        },
        "character_behavior_models": {
            protagonist_name: _infer_behavior_model(project, protagonist),
        },
        "exposition_rules": defaults["anti_exposition_rules"],
        "anti_template_constraints": defaults["anti_template_rules"],
        "banned_patterns": [
            "连续说明性对白灌输设定",
            "连续三章同构钩子或同构爽点",
            "没有余波的高光/打脸",
        ],
        "memory_bias": {
            "effective_techniques": list(summary.get("effective") or [])[:6],
            "fatigue_techniques": list(summary.get("fatigue") or [])[:6],
        },
    }


def ensure_story_technique_blueprint(
    *,
    config: Any,
    state: Mapping[str, Any] | None = None,
    project_memory: Mapping[str, Any] | None = None,
    force: bool = False,
) -> Dict[str, Any]:
    path = Path(config.story_technique_blueprint_file)
    if path.exists() and not force:
        payload = _read_json(path)
        if payload.get("version") and payload.get("genre_strategy"):
            return payload
    state = dict(state or _read_json(config.state_file))
    project_memory = project_memory or load_project_memory(config.project_memory_file)
    payload = build_story_technique_blueprint(state, project_memory=project_memory)
    _write_json(path, payload)
    return payload


def _infer_scene_role(chapter: int, outline: str, strategy: Mapping[str, Any]) -> str:
    text = str(outline or "")
    lowered = text.lower()
    if any(token in text for token in ("决战", "爆发", "打脸", "反杀", "揭露", "对决", "摊牌")):
        return "confront"
    if any(token in text for token in ("收尾", "余波", "庆功", "和解", "兑现", "回收", "收获")):
        return "release"
    if any(token in text for token in ("调查", "准备", "铺垫", "转场", "潜伏", "试探")):
        return "build_up"
    cycle = list(strategy.get("scene_role_cycle") or ["build_up", "confront", "release"])
    if not cycle:
        cycle = ["build_up", "confront", "release"]
    return cycle[(max(chapter, 1) - 1) % len(cycle)]


def _pick_with_fatigue(candidates: List[str], fatigue: List[str], dominant: str = "") -> List[str]:
    seen = set()
    ordered: List[str] = []
    fatigue_set = {str(item) for item in fatigue if str(item).strip()}
    for token in candidates:
        if token == dominant:
            continue
        if token in fatigue_set:
            continue
        if token not in seen:
            ordered.append(token)
            seen.add(token)
    for token in candidates:
        if token not in seen and token != dominant:
            ordered.append(token)
            seen.add(token)
    if dominant and dominant not in seen:
        ordered.append(dominant)
    return ordered


def build_chapter_technique_plan(
    *,
    chapter: int,
    chapter_outline: str,
    reader_signal: Mapping[str, Any],
    genre_profile: Mapping[str, Any],
    story_recall: Mapping[str, Any],
    chapter_intent: Mapping[str, Any],
    writing_guidance: Mapping[str, Any],
    story_technique_blueprint: Mapping[str, Any],
    project_memory: Mapping[str, Any],
) -> Dict[str, Any]:
    blueprint = dict(story_technique_blueprint or {})
    genre_strategy = dict(blueprint.get("genre_strategy") or {})
    scene_role = _infer_scene_role(chapter, chapter_outline, genre_strategy)

    hook_usage = dict(reader_signal.get("hook_type_usage") or {})
    dominant_hook = max(hook_usage.items(), key=lambda kv: kv[1])[0] if hook_usage else ""
    pattern_usage = dict(reader_signal.get("pattern_usage") or {})
    dominant_pattern = max(pattern_usage.items(), key=lambda kv: kv[1])[0] if pattern_usage else ""
    summary = normalize_project_memory(project_memory).get("technique_summary") or {}
    fatigue = list(summary.get("fatigue") or [])

    hook_candidates = _pick_with_fatigue(list(genre_strategy.get("hook_pool") or []), fatigue, dominant_hook)
    coolpoint_candidates = _pick_with_fatigue(list(genre_strategy.get("coolpoint_pool") or []), fatigue, dominant_pattern)
    micropayoffs = _pick_with_fatigue(list(genre_strategy.get("micropayoff_pool") or []), fatigue)[:2]

    opening_hook = hook_candidates[0] if hook_candidates else "危机钩"
    ending_hook = hook_candidates[1] if len(hook_candidates) > 1 else opening_hook
    if scene_role == "release" and "渴望钩" in hook_candidates:
        ending_hook = "渴望钩"
    elif scene_role == "confront" and "选择钩" in hook_candidates:
        ending_hook = "选择钩"

    climax_patterns = coolpoint_candidates[:2] if coolpoint_candidates else ["反派翻车"]
    unresolved = list(chapter_intent.get("must_resolve") or [])[:2]
    priority_foreshadowing = [
        str(item.get("name") or item.get("content") or "")
        for item in (story_recall.get("priority_foreshadowing") or [])[:2]
        if isinstance(item, Mapping)
    ]

    signals = {
        "dominant_hook": dominant_hook,
        "dominant_pattern": dominant_pattern,
        "low_score_ranges": len(reader_signal.get("low_score_ranges") or []),
        "effective_techniques": list(summary.get("effective") or [])[:3],
        "fatigue_techniques": fatigue[:3],
    }

    return {
        "version": "v1",
        "chapter": chapter,
        "scene_role": scene_role,
        "opening_hook": {
            "type": opening_hook,
            "goal": "开场即给目标/阻力/情绪触发，不先解释背景",
        },
        "mid_payoffs": micropayoffs or ["信息兑现"],
        "climax_patterns": climax_patterns,
        "ending_hook": {
            "type": ending_hook,
            "goal": "结尾保留下章理由，不在本章彻底封口",
        },
        "paragraph_rhythm": ["trigger", "reaction", "action", "result", "aftermath"],
        "anti_template_constraints": list(blueprint.get("anti_template_constraints") or [])[:3],
        "exposition_rules": list(blueprint.get("exposition_rules") or [])[:3],
        "must_resolve": [item for item in unresolved if item],
        "priority_foreshadowing": [item for item in priority_foreshadowing if item],
        "execution_focus": [
            "至少一段形成刺激器→反应→动作→结果闭环",
            "高光后必须有余波、反应或关系/资源变化",
            "避免把设定集中塞进一段对白",
        ],
        "signals": signals,
        "supporting_guidance": list(writing_guidance.get("guidance_items") or [])[:2],
    }


def summarize_technique_execution(
    *,
    chapter: int,
    genre: str,
    chapter_meta: Mapping[str, Any] | None = None,
    technique_execution: Mapping[str, Any] | None = None,
    overall_score: Any = None,
) -> Dict[str, Any]:
    chapter_meta = dict(chapter_meta or {})
    explicit = dict(technique_execution or {})

    applied: List[str] = []
    failed: List[str] = []
    signals: Dict[str, Any] = dict(explicit.get("signals") or {})

    for token in explicit.get("applied") or []:
        text = str(token).strip()
        if text and text not in applied:
            applied.append(text)
    for token in explicit.get("failed") or []:
        text = str(token).strip()
        if text and text not in failed:
            failed.append(text)

    hook = chapter_meta.get("hook")
    if hook:
        applied.append(f"hook:{hook}")
    for token in chapter_meta.get("coolpoint_patterns") or chapter_meta.get("patterns") or []:
        text = str(token).strip()
        if text:
            applied.append(f"coolpoint:{text}")

    return {
        "chapter": int(chapter),
        "genre": str(genre or "general"),
        "scene_role": str(explicit.get("scene_role") or chapter_meta.get("scene_role") or ""),
        "applied": applied,
        "failed": failed,
        "signals": signals,
        "overall_score": overall_score,
        "recorded_at": _utc_now(),
    }
