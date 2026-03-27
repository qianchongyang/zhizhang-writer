#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Runtime validators/normalizers for state.json sections.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional, Sequence


FORESHADOWING_STATUS_PENDING = "未回收"
FORESHADOWING_STATUS_RESOLVED = "已回收"

FORESHADOWING_TIER_CORE = "核心"
FORESHADOWING_TIER_SUB = "支线"
FORESHADOWING_TIER_DECOR = "装饰"

FORESHADOWING_PLANTED_KEYS = [
    "planted_chapter",
    "added_chapter",
    "source_chapter",
    "start_chapter",
    "chapter",
]

FORESHADOWING_TARGET_KEYS = [
    "target_chapter",
    "due_chapter",
    "deadline_chapter",
    "resolve_by_chapter",
    "target",
]

_PENDING_STATUS_TEXT = {"未回收", "待回收", "进行中", "未解决", "pending", "active"}
_RESOLVED_STATUS_TEXT = {"已回收", "已完成", "已解决", "完成", "resolved", "done", "complete"}

_TIER_CORE_TEXT = {"核心", "主线", "core", "main"}
_TIER_DECOR_TEXT = {"装饰", "次要", "decor", "decoration"}

_PATTERN_FIELDS = [
    "coolpoint_patterns",
    "coolpoint_pattern",
    "cool_point_patterns",
    "cool_point_pattern",
    "patterns",
    "pattern",
]

_PATTERN_SPLIT_RE = re.compile(r"[、,，/|+；;。]+")

_STORY_MEMORY_DEFAULT_VERSION = "1"
_STORY_MEMORY_CHARACTER_MILESTONE_LIMIT = 10
_STORY_MEMORY_RECENT_EVENT_LIMIT = 50
_STORY_MEMORY_CHAPTER_SNAPSHOT_LIMIT = 20
_STORY_MEMORY_CHANGE_LEDGER_LIMIT = 50
_STORY_MEMORY_ARCHIVE_STALE_CHAPTER_GAP = 3
_STORY_MEMORY_EMOTIONAL_ARC_LIMIT = 12

_CHANGE_KIND_RELATIONSHIP = "relationship_change"
_CHANGE_KIND_LOCATION = "location_change"
_CHANGE_KIND_TIMELINE = "timeline_change"
_CHANGE_KIND_GOAL = "goal_change"
_CHANGE_KIND_CLUE = "clue_change"
_CHANGE_KIND_QUANTITATIVE = "quantitative_change"
_CHANGE_KIND_ATTRIBUTE = "attribute_change"
_CHANGE_KIND_EVENT = "event_change"
_CHANGE_KIND_STATE = "state_change"

_MEMORY_TIER_ORDER = {
    "consolidated": 0,
    "episodic": 1,
    "working": 2,
}

_RELATIONSHIP_KEYWORDS = ("关系", "relation", "师徒", "盟", "敌", "仇", "友", "爱", "亲", "同伴", "同盟")
_LOCATION_KEYWORDS = ("地点", "位置", "location", "驻地", "住所", "居所", "城市", "村", "城", "房", "屋", "区域")
_TIMELINE_KEYWORDS = (
    "时间",
    "日期",
    "时刻",
    "小时",
    "分钟",
    "秒钟",
    "当天",
    "今日",
    "昨天",
    "明天",
    "前一天",
    "后一天",
    "翌日",
    "次日",
    "当夜",
    "凌晨",
    "上午",
    "下午",
    "傍晚",
    "黄昏",
    "夜里",
    "夜晚",
)
_GOAL_KEYWORDS = ("目标", "任务", "计划", "愿望", "使命", "目的", "追求", "mission", "goal", "quest")
_CLUE_KEYWORDS = ("线索", "伏笔", "秘密", "真相", "来历", "身份", "谜", "谜团", "暗示", "提示")
_QUANTITATIVE_KEYWORDS = ("数量", "余额", "库存", "持有", "拥有", "消耗", "增加", "减少", "剩余", "资源", "灵石", "金币", "积分")
_STATE_KEYWORDS = ("状态", "属性", "能力", "实力", "境界", "等级", "生命", "健康", "心情", "情绪", "战力", "力量", "体力")
_IMPORTANT_REASON_KEYWORDS = ("关键", "重大", "转折", "突破", "揭示", "回收", "升级", "死亡", "失去", "获得", "确认", "冲突", "改变", "暴露")


def to_positive_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None

    try:
        number = int(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        if isinstance(value, str):
            matched = re.search(r"\d+", value)
            if matched:
                number = int(matched.group(0))
                return number if number > 0 else None
    return None


def resolve_chapter_field(item: Mapping[str, Any], keys: Sequence[str]) -> Optional[int]:
    for key in keys:
        if key in item:
            chapter = to_positive_int(item.get(key))
            if chapter is not None:
                return chapter
    return None


def normalize_foreshadowing_status(
    raw_status: Any,
    default: str = FORESHADOWING_STATUS_PENDING,
) -> str:
    text = str(raw_status or "").strip()
    if not text:
        return default

    text_lower = text.lower()
    if (
        text in _RESOLVED_STATUS_TEXT
        or text_lower in _RESOLVED_STATUS_TEXT
        or FORESHADOWING_STATUS_RESOLVED in text
    ):
        return FORESHADOWING_STATUS_RESOLVED

    if text in _PENDING_STATUS_TEXT or text_lower in _PENDING_STATUS_TEXT:
        return FORESHADOWING_STATUS_PENDING

    return default


def is_resolved_foreshadowing_status(raw_status: Any) -> bool:
    return normalize_foreshadowing_status(raw_status) == FORESHADOWING_STATUS_RESOLVED


def normalize_foreshadowing_tier(
    raw_tier: Any,
    default: str = FORESHADOWING_TIER_SUB,
) -> str:
    text = str(raw_tier or "").strip()
    if not text:
        return default

    text_lower = text.lower()
    if text in _TIER_CORE_TEXT or text_lower in _TIER_CORE_TEXT:
        return FORESHADOWING_TIER_CORE
    if text in _TIER_DECOR_TEXT or text_lower in _TIER_DECOR_TEXT:
        return FORESHADOWING_TIER_DECOR
    return default


def split_patterns(raw_value: Any) -> List[str]:
    if raw_value is None:
        return []

    tokens: List[str] = []
    if isinstance(raw_value, list):
        for item in raw_value:
            text = str(item).strip()
            if text:
                tokens.append(text)
    elif isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return []
        split_values = [part.strip() for part in _PATTERN_SPLIT_RE.split(text)]
        tokens.extend([part for part in split_values if part])
    else:
        return []

    deduped: List[str] = []
    seen = set()
    for token in tokens:
        if token not in seen:
            seen.add(token)
            deduped.append(token)
    return deduped


def count_patterns(raw_value: Any) -> Optional[int]:
    patterns = split_patterns(raw_value)
    if not patterns:
        return None
    return len(patterns)


def normalize_foreshadowing_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)

    normalized["status"] = normalize_foreshadowing_status(item.get("status"))
    normalized["tier"] = normalize_foreshadowing_tier(item.get("tier"))

    content = str(item.get("content") or "").strip()
    if content:
        normalized["content"] = content

    planted_chapter = resolve_chapter_field(item, FORESHADOWING_PLANTED_KEYS)
    if planted_chapter is not None:
        normalized["planted_chapter"] = planted_chapter

    target_chapter = resolve_chapter_field(item, FORESHADOWING_TARGET_KEYS)
    if target_chapter is not None:
        normalized["target_chapter"] = target_chapter

    resolved_chapter = resolve_chapter_field(item, ["resolved_chapter", "resolved_at_chapter", "resolved"])
    if resolved_chapter is not None:
        normalized["resolved_chapter"] = resolved_chapter

    return normalized


def _stable_story_memory_id(prefix: str, chapter: int, content: str, extra: str = "") -> str:
    payload = f"{prefix}|{chapter}|{content}|{extra}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{chapter:04d}_{digest}"


def _normalize_story_memory_milestone(character_name: str, milestone: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(milestone)
    ch = to_positive_int(milestone.get("ch") or milestone.get("chapter")) or 0
    event = str(milestone.get("event") or milestone.get("content") or "").strip()
    normalized["ch"] = ch
    if event:
        normalized["event"] = event
    normalized.setdefault("source_of_truth", "story_memory")
    normalized["confidence"] = float(milestone.get("confidence") or 1.0)
    normalized["milestone_id"] = str(
        milestone.get("milestone_id")
        or milestone.get("story_memory_id")
        or _stable_story_memory_id("milestone", ch, event or character_name, character_name)
    )
    return normalized


def _normalize_story_memory_character(name: str, item: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)
    normalized["current_state"] = str(item.get("current_state") or item.get("summary") or "").strip()
    normalized["last_update_chapter"] = to_positive_int(item.get("last_update_chapter")) or 0

    milestones: List[Dict[str, Any]] = []
    if isinstance(item.get("milestones"), list):
        for milestone in item.get("milestones", []):
            if isinstance(milestone, Mapping):
                milestones.append(_normalize_story_memory_milestone(name, milestone))
    if len(milestones) > _STORY_MEMORY_CHARACTER_MILESTONE_LIMIT:
        milestones = milestones[-_STORY_MEMORY_CHARACTER_MILESTONE_LIMIT :]
    normalized["milestones"] = milestones
    return normalized


def _normalize_story_memory_thread(item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    normalized = dict(item)
    content = str(item.get("content") or item.get("name") or item.get("event") or "").strip()
    if content:
        normalized["content"] = content
    normalized["status"] = normalize_foreshadowing_status(item.get("status"))
    normalized["tier"] = normalize_foreshadowing_tier(item.get("tier"))
    planted_chapter = resolve_chapter_field(item, FORESHADOWING_PLANTED_KEYS)
    if planted_chapter is not None:
        normalized["planted_chapter"] = planted_chapter
    target_chapter = resolve_chapter_field(item, FORESHADOWING_TARGET_KEYS)
    if target_chapter is not None:
        normalized["target_chapter"] = target_chapter
    resolved_chapter = resolve_chapter_field(item, ["resolved_chapter", "resolved_at_chapter", "resolved"])
    if resolved_chapter is not None:
        normalized["resolved_chapter"] = resolved_chapter

    story_memory_id = str(
        item.get("story_memory_id")
        or item.get("foreshadowing_id")
        or _stable_story_memory_id(
            "foreshadowing",
            planted_chapter or target_chapter or index,
            content,
            str(normalized.get("tier") or ""),
        )
    )
    normalized["story_memory_id"] = story_memory_id
    normalized["foreshadowing_id"] = str(item.get("foreshadowing_id") or story_memory_id)
    normalized.setdefault("source_of_truth", "story_memory")
    normalized["confidence"] = float(item.get("confidence") or 1.0)
    return normalized


def _normalize_story_memory_event(item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    normalized = dict(item)
    ch = to_positive_int(item.get("ch") or item.get("chapter")) or 0
    event = str(item.get("event") or item.get("content") or "").strip()
    if event:
        normalized["event"] = event
    normalized["ch"] = ch
    normalized.setdefault("source_of_truth", "story_memory")
    normalized["confidence"] = float(item.get("confidence") or 1.0)
    story_memory_id = str(
        item.get("story_memory_id")
        or item.get("event_id")
        or _stable_story_memory_id("event", ch or index, event, str(item.get("type") or ""))
    )
    normalized["story_memory_id"] = story_memory_id
    normalized["event_id"] = str(item.get("event_id") or story_memory_id)
    return normalized


def _parse_numeric_value(raw_value: Any) -> Optional[float]:
    if raw_value is None or isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None


def infer_change_kind(change: Mapping[str, Any]) -> str:
    """基于字段名、原因和类型推断通用变化类型。"""
    text_parts = [
        str(change.get("entity_id") or ""),
        str(change.get("field") or ""),
        str(change.get("reason") or ""),
        str(change.get("note") or ""),
        str(change.get("type") or ""),
        str(change.get("change_kind") or ""),
    ]
    text = " ".join(part for part in text_parts if part).lower()

    def has_any(keywords: Sequence[str]) -> bool:
        return any(keyword.lower() in text for keyword in keywords)

    if has_any(_RELATIONSHIP_KEYWORDS):
        return _CHANGE_KIND_RELATIONSHIP
    if has_any(_LOCATION_KEYWORDS):
        return _CHANGE_KIND_LOCATION
    if has_any(_TIMELINE_KEYWORDS):
        return _CHANGE_KIND_TIMELINE
    if has_any(_GOAL_KEYWORDS):
        return _CHANGE_KIND_GOAL
    if has_any(_CLUE_KEYWORDS):
        return _CHANGE_KIND_CLUE
    if has_any(_QUANTITATIVE_KEYWORDS):
        return _CHANGE_KIND_QUANTITATIVE
    if has_any(_STATE_KEYWORDS):
        return _CHANGE_KIND_ATTRIBUTE

    old_value = change.get("old", change.get("old_value"))
    new_value = change.get("new", change.get("new_value"))
    if _parse_numeric_value(old_value) is not None or _parse_numeric_value(new_value) is not None:
        return _CHANGE_KIND_QUANTITATIVE

    return _CHANGE_KIND_STATE


def score_change_significance(change: Mapping[str, Any]) -> Dict[str, Any]:
    """为变化打重要性分，用于决定是否进入记忆层、进入哪一层。"""
    kind = infer_change_kind(change)
    score = 0.0
    reasons: List[str] = []

    kind_base = {
        _CHANGE_KIND_RELATIONSHIP: 85.0,
        _CHANGE_KIND_LOCATION: 80.0,
        _CHANGE_KIND_TIMELINE: 75.0,
        _CHANGE_KIND_GOAL: 88.0,
        _CHANGE_KIND_CLUE: 92.0,
        _CHANGE_KIND_QUANTITATIVE: 72.0,
        _CHANGE_KIND_ATTRIBUTE: 68.0,
        _CHANGE_KIND_EVENT: 60.0,
        _CHANGE_KIND_STATE: 50.0,
    }
    score = kind_base.get(kind, 50.0)
    reasons.append(f"kind={kind}")

    text = " ".join(
        part
        for part in [
            str(change.get("entity_id") or ""),
            str(change.get("field") or ""),
            str(change.get("reason") or ""),
            str(change.get("note") or ""),
            str(change.get("content") or ""),
        ]
        if part
    )
    if any(keyword in text for keyword in _IMPORTANT_REASON_KEYWORDS):
        score += 10.0
        reasons.append("important_keyword")

    if change.get("chapter_meta") or change.get("chapter_ending"):
        score += 8.0
        reasons.append("chapter_meta")

    old_numeric = _parse_numeric_value(change.get("old", change.get("old_value")))
    new_numeric = _parse_numeric_value(change.get("new", change.get("new_value")))
    if old_numeric is not None and new_numeric is not None:
        delta = abs(new_numeric - old_numeric)
        if delta > 0:
            score += min(8.0, delta * 0.1)
            reasons.append("numeric_delta")

    score = max(0.0, min(100.0, round(score, 2)))
    if score >= 80:
        tier = "consolidated"
    elif score >= 60:
        tier = "episodic"
    else:
        tier = "working"

    return {
        "change_kind": kind,
        "memory_score": score,
        "memory_tier": tier,
        "should_consolidate": score >= 60,
        "reasons": reasons,
    }


def memory_tier_rank(raw_tier: Any) -> int:
    tier = str(raw_tier or "working").strip().lower()
    return _MEMORY_TIER_ORDER.get(tier, _MEMORY_TIER_ORDER["working"])


def _normalize_story_memory_change_ledger(item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    normalized = dict(item)
    ch = to_positive_int(item.get("ch") or item.get("chapter")) or 0
    field = str(item.get("field") or "").strip()
    entity_id = str(item.get("entity_id") or "").strip()
    old_value = item.get("old_value", item.get("old"))
    new_value = item.get("new_value", item.get("new"))
    old_num = _parse_numeric_value(old_value)
    new_num = _parse_numeric_value(new_value)
    if old_num is not None:
        normalized["old_numeric"] = old_num
    if new_num is not None:
        normalized["new_numeric"] = new_num
    if old_num is not None and new_num is not None:
        normalized["delta"] = round(new_num - old_num, 6)
    change_kind = str(item.get("change_kind") or item.get("kind") or "state_change").strip() or "state_change"
    scoring = score_change_significance(item)
    normalized["ch"] = ch
    normalized["field"] = field
    normalized["entity_id"] = entity_id
    normalized["type"] = str(item.get("type") or change_kind)
    normalized["change_kind"] = change_kind
    normalized.setdefault("source_of_truth", "index.db")
    normalized["confidence"] = float(item.get("confidence") or 1.0)
    normalized["memory_score"] = scoring.get("memory_score", 0.0)
    normalized["memory_tier"] = scoring.get("memory_tier", "working")
    normalized["memory_reasons"] = list(scoring.get("reasons") or [])
    normalized["should_consolidate"] = bool(scoring.get("should_consolidate"))
    normalized["change_id"] = str(
        item.get("change_id")
        or item.get("numeric_change_id")
        or item.get("story_memory_id")
        or _stable_story_memory_id(
            "change",
            ch or index,
            f"{change_kind}:{entity_id}.{field}",
            json.dumps([old_value, new_value], ensure_ascii=False, sort_keys=True),
        )
    )
    return normalized


def _normalize_story_memory_foreshadowing_update(item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    normalized = dict(item)
    content = str(item.get("content") or item.get("name") or item.get("event") or "").strip()
    if content:
        normalized["content"] = content
    status = normalize_foreshadowing_status(item.get("status"))
    normalized["status"] = status
    normalized["tier"] = normalize_foreshadowing_tier(item.get("tier"))
    normalized["updated_at_chapter"] = to_positive_int(item.get("updated_at_chapter") or item.get("chapter")) or 0
    resolved_chapter = resolve_chapter_field(item, ["resolved_chapter", "resolved_at_chapter", "resolved"])
    if resolved_chapter is not None:
        normalized["resolved_chapter"] = resolved_chapter
    normalized["story_memory_id"] = str(
        item.get("story_memory_id")
        or item.get("foreshadowing_id")
        or _stable_story_memory_id(
            "foreshadowing_update",
            normalized["updated_at_chapter"] or index,
            content,
            status,
        )
    )
    normalized["foreshadowing_id"] = str(item.get("foreshadowing_id") or normalized["story_memory_id"])
    normalized.setdefault("source_of_truth", "story_memory")
    normalized["confidence"] = float(item.get("confidence") or 1.0)
    return normalized


def _normalize_story_memory_snapshot(item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    normalized = dict(item)
    chapter = to_positive_int(item.get("chapter")) or 0
    normalized["chapter"] = chapter
    story_memory_id = str(
        item.get("story_memory_id")
        or _stable_story_memory_id("snapshot", chapter or index, str(item.get("protagonist") or ""), str(item.get("saved_at") or ""))
    )
    normalized["story_memory_id"] = story_memory_id
    return normalized


def _normalize_emotional_arc_item(character_id: str, item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    normalized = dict(item)
    chapter = to_positive_int(item.get("chapter") or item.get("ch") or item.get("last_update_chapter")) or 0
    emotional_state = str(item.get("emotional_state") or item.get("state") or "").strip()
    emotional_trend = str(item.get("emotional_trend") or item.get("trend") or "stable").strip() or "stable"
    trigger_event = str(item.get("trigger_event") or item.get("event") or "").strip()
    normalized["character_id"] = character_id
    normalized["chapter"] = chapter
    normalized["emotional_state"] = emotional_state
    normalized["emotional_trend"] = emotional_trend
    normalized["trigger_event"] = trigger_event
    normalized.setdefault("source_of_truth", "story_memory")
    normalized["confidence"] = float(item.get("confidence") or 1.0)
    normalized["arc_id"] = str(
        item.get("arc_id")
        or item.get("story_memory_id")
        or _stable_story_memory_id("emotion", chapter or index, character_id, f"{emotional_state}|{emotional_trend}|{trigger_event}")
    )
    return normalized


def _normalize_story_memory_emotional_arcs(raw_arcs: Any) -> Dict[str, List[Dict[str, Any]]]:
    normalized: Dict[str, List[Dict[str, Any]]] = {}
    if not isinstance(raw_arcs, Mapping):
        return normalized

    for character_id, items in raw_arcs.items():
        if not isinstance(items, list):
            continue
        character_key = str(character_id or "").strip()
        if not character_key:
            continue
        rows: List[Dict[str, Any]] = []
        for index, item in enumerate(items):
            if isinstance(item, Mapping):
                rows.append(_normalize_emotional_arc_item(character_key, item, index))
        rows.sort(key=lambda row: (int(row.get("chapter") or 0), str(row.get("arc_id") or "")))
        if len(rows) > _STORY_MEMORY_EMOTIONAL_ARC_LIMIT:
            rows = rows[-_STORY_MEMORY_EMOTIONAL_ARC_LIMIT:]
        normalized[character_key] = rows
    return normalized


def _normalize_story_memory_archive(raw_archive: Any) -> Dict[str, List[Dict[str, Any]]]:
    archive = {
        "plot_threads": [],
        "recent_events": [],
        "structured_change_ledger": [],
        "chapter_snapshots": [],
        "emotional_arcs": [],
    }
    if not isinstance(raw_archive, Mapping):
        return archive

    for key in archive:
        items = raw_archive.get(key, [])
        if isinstance(items, list):
            for index, item in enumerate(items):
                if not isinstance(item, Mapping):
                    continue
                if key == "plot_threads":
                    archive[key].append(_normalize_story_memory_thread(item, index))
                elif key == "recent_events":
                    archive[key].append(_normalize_story_memory_event(item, index))
                elif key == "structured_change_ledger":
                    archive[key].append(_normalize_story_memory_change_ledger(item, index))
                elif key == "chapter_snapshots":
                    archive[key].append(_normalize_story_memory_snapshot(item, index))
                elif key == "emotional_arcs":
                    archive[key].append(_normalize_emotional_arc_item(str(item.get("character_id") or ""), item, index))
    return archive


def _archive_story_memory_items(
    normalized: Dict[str, Any],
    raw_archive: Any,
) -> Dict[str, List[Dict[str, Any]]]:
    archive = _normalize_story_memory_archive(raw_archive)
    last_consolidated = int(normalized.get("last_consolidated_chapter") or 0)

    def _append_archive(key: str, items: List[Dict[str, Any]]) -> None:
        if not items:
            return
        archive[key].extend(deepcopy(item) for item in items if isinstance(item, dict))

    active_threads = []
    for item in normalized.get("plot_threads", []):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        resolved_chapter = to_positive_int(item.get("resolved_chapter"))
        if (
            status in {"已回收", "resolved", "done", "complete"}
            and resolved_chapter is not None
            and last_consolidated > 0
            and resolved_chapter <= max(0, last_consolidated - _STORY_MEMORY_ARCHIVE_STALE_CHAPTER_GAP)
        ):
            archive["plot_threads"].append(deepcopy(item))
            continue
        active_threads.append(item)
    normalized["plot_threads"] = active_threads

    active_changes = []
    stale_changes = []
    for item in normalized.get("structured_change_ledger", []):
        if not isinstance(item, dict):
            continue
        score = float(item.get("memory_score") or 0.0)
        chapter = to_positive_int(item.get("ch")) or 0
        if (
            score < 60.0
            and last_consolidated > 0
            and chapter > 0
            and chapter <= max(0, last_consolidated - _STORY_MEMORY_ARCHIVE_STALE_CHAPTER_GAP)
        ):
            stale_changes.append(item)
            continue
        active_changes.append(item)
    if len(active_changes) > _STORY_MEMORY_CHANGE_LEDGER_LIMIT:
        overflow = active_changes[:-_STORY_MEMORY_CHANGE_LEDGER_LIMIT]
        stale_changes.extend(overflow)
        active_changes = active_changes[-_STORY_MEMORY_CHANGE_LEDGER_LIMIT :]
    normalized["structured_change_ledger"] = active_changes
    _append_archive("structured_change_ledger", stale_changes)

    active_events = list(normalized.get("recent_events", []))
    if len(active_events) > _STORY_MEMORY_RECENT_EVENT_LIMIT:
        overflow = active_events[:-_STORY_MEMORY_RECENT_EVENT_LIMIT]
        _append_archive("recent_events", overflow)
        active_events = active_events[-_STORY_MEMORY_RECENT_EVENT_LIMIT :]
    normalized["recent_events"] = active_events

    active_snapshots = list(normalized.get("chapter_snapshots", []))
    if len(active_snapshots) > _STORY_MEMORY_CHAPTER_SNAPSHOT_LIMIT:
        overflow = active_snapshots[:-_STORY_MEMORY_CHAPTER_SNAPSHOT_LIMIT]
        _append_archive("chapter_snapshots", overflow)
        active_snapshots = active_snapshots[-_STORY_MEMORY_CHAPTER_SNAPSHOT_LIMIT :]
    normalized["chapter_snapshots"] = active_snapshots

    active_arcs: Dict[str, List[Dict[str, Any]]] = {}
    for character_id, items in (normalized.get("emotional_arcs") or {}).items():
        if not isinstance(items, list):
            continue
        rows = list(items)
        if len(rows) > _STORY_MEMORY_EMOTIONAL_ARC_LIMIT:
            overflow = rows[:-_STORY_MEMORY_EMOTIONAL_ARC_LIMIT]
            _append_archive("emotional_arcs", overflow)
            rows = rows[-_STORY_MEMORY_EMOTIONAL_ARC_LIMIT:]
        active_arcs[str(character_id)] = rows
    normalized["emotional_arcs"] = active_arcs

    return archive


def normalize_story_memory(raw_story_memory: Any) -> Dict[str, Any]:
    if not isinstance(raw_story_memory, Mapping):
        raw_story_memory = {}

    normalized: Dict[str, Any] = {
        "version": str(raw_story_memory.get("version") or _STORY_MEMORY_DEFAULT_VERSION),
        "last_consolidated_chapter": to_positive_int(raw_story_memory.get("last_consolidated_chapter")) or 0,
        "last_consolidated_at": str(raw_story_memory.get("last_consolidated_at") or ""),
        "last_updated_at": str(raw_story_memory.get("last_updated_at") or ""),
        "characters": {},
        "plot_threads": [],
        "recent_events": [],
        "structured_change_ledger": [],
        "chapter_snapshots": [],
        "emotional_arcs": {},
        "archive": {
            "plot_threads": [],
            "recent_events": [],
            "structured_change_ledger": [],
            "chapter_snapshots": [],
            "emotional_arcs": [],
        },
        "meta": dict(raw_story_memory.get("meta") or {}),
    }

    characters = raw_story_memory.get("characters", {})
    if isinstance(characters, Mapping):
        for name, item in characters.items():
            if isinstance(item, Mapping):
                normalized["characters"][str(name)] = _normalize_story_memory_character(str(name), item)

    plot_threads = raw_story_memory.get("plot_threads", [])
    if isinstance(plot_threads, list):
        for index, item in enumerate(plot_threads):
            if isinstance(item, Mapping):
                normalized["plot_threads"].append(_normalize_story_memory_thread(item, index))

    recent_events = raw_story_memory.get("recent_events", [])
    if isinstance(recent_events, list):
        for index, item in enumerate(recent_events):
            if isinstance(item, Mapping):
                normalized["recent_events"].append(_normalize_story_memory_event(item, index))

    change_ledger = raw_story_memory.get("structured_change_ledger", raw_story_memory.get("numeric_ledger", []))
    if isinstance(change_ledger, list):
        for index, item in enumerate(change_ledger):
            if isinstance(item, Mapping):
                normalized["structured_change_ledger"].append(_normalize_story_memory_change_ledger(item, index))

    chapter_snapshots = raw_story_memory.get("chapter_snapshots", [])
    if isinstance(chapter_snapshots, list):
        for index, item in enumerate(chapter_snapshots):
            if isinstance(item, Mapping):
                normalized["chapter_snapshots"].append(_normalize_story_memory_snapshot(item, index))

    normalized["emotional_arcs"] = _normalize_story_memory_emotional_arcs(raw_story_memory.get("emotional_arcs"))

    archive = _archive_story_memory_items(normalized, raw_story_memory.get("archive"))
    normalized["archive"] = archive

    return normalized


def normalize_foreshadowing_list(raw_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for raw_item in raw_items:
        if isinstance(raw_item, Mapping):
            normalized.append(normalize_foreshadowing_item(raw_item))
    return normalized


def normalize_chapter_meta_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(entry)

    merged_patterns: List[str] = []
    seen = set()
    for field_name in _PATTERN_FIELDS:
        for pattern in split_patterns(entry.get(field_name)):
            if pattern not in seen:
                seen.add(pattern)
                merged_patterns.append(pattern)

    if merged_patterns:
        normalized["coolpoint_patterns"] = merged_patterns

    return normalized


def normalize_chapter_meta(raw_chapter_meta: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw_chapter_meta, Mapping):
        return {}

    normalized: Dict[str, Dict[str, Any]] = {}
    for chapter_key, chapter_entry in raw_chapter_meta.items():
        if isinstance(chapter_entry, Mapping):
            normalized[str(chapter_key)] = normalize_chapter_meta_entry(chapter_entry)
    return normalized


def get_chapter_meta_entry(state: Mapping[str, Any], chapter: int) -> Dict[str, Any]:
    chapter_meta = state.get("chapter_meta", {})
    if not isinstance(chapter_meta, Mapping):
        return {}

    for lookup_key in (f"{chapter:04d}", str(chapter)):
        value = chapter_meta.get(lookup_key)
        if isinstance(value, Mapping):
            return normalize_chapter_meta_entry(value)

    for raw_key, raw_value in chapter_meta.items():
        if to_positive_int(raw_key) == chapter and isinstance(raw_value, Mapping):
            return normalize_chapter_meta_entry(raw_value)

    return {}


def normalize_state_runtime_sections(state: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return {}

    plot_threads = state.get("plot_threads")
    if not isinstance(plot_threads, dict):
        plot_threads = {}
        state["plot_threads"] = plot_threads
    plot_threads["foreshadowing"] = normalize_foreshadowing_list(plot_threads.get("foreshadowing"))

    state["chapter_meta"] = normalize_chapter_meta(state.get("chapter_meta", {}))
    return state
