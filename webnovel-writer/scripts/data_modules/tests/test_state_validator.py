#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from data_modules.state_validator import (
    FORESHADOWING_STATUS_PENDING,
    FORESHADOWING_STATUS_RESOLVED,
    FORESHADOWING_TIER_CORE,
    FORESHADOWING_TIER_DECOR,
    FORESHADOWING_TIER_SUB,
    count_patterns,
    get_chapter_meta_entry,
    is_resolved_foreshadowing_status,
    normalize_chapter_meta,
    normalize_foreshadowing_item,
    normalize_foreshadowing_status,
    normalize_foreshadowing_tier,
    infer_change_kind,
    normalize_story_memory,
    memory_tier_rank,
    score_change_significance,
    normalize_state_runtime_sections,
    resolve_chapter_field,
    split_patterns,
    to_positive_int,
)


def test_to_positive_int_and_resolve_chapter_field():
    assert to_positive_int(12) == 12
    assert to_positive_int("ch-18") == 18
    assert to_positive_int(0) is None
    assert to_positive_int("no number") is None

    item = {"added_chapter": "第15章", "target": "200"}
    assert resolve_chapter_field(item, ["planted_chapter", "added_chapter"]) == 15
    assert resolve_chapter_field(item, ["target_chapter", "target"]) == 200


def test_status_and_tier_normalization():
    assert normalize_foreshadowing_status("pending") == FORESHADOWING_STATUS_PENDING
    assert normalize_foreshadowing_status("resolved") == FORESHADOWING_STATUS_RESOLVED
    assert normalize_foreshadowing_status("") == FORESHADOWING_STATUS_PENDING
    assert is_resolved_foreshadowing_status("已回收") is True
    assert is_resolved_foreshadowing_status("active") is False

    assert normalize_foreshadowing_tier("core") == FORESHADOWING_TIER_CORE
    assert normalize_foreshadowing_tier("decoration") == FORESHADOWING_TIER_DECOR
    assert normalize_foreshadowing_tier("unknown") == FORESHADOWING_TIER_SUB


def test_pattern_split_and_count():
    assert split_patterns(["A", " A ", "B", ""]) == ["A", "B"]
    assert split_patterns("A, B / C|A") == ["A", "B", "C"]
    assert count_patterns("A,B,C") == 3
    assert count_patterns(123) is None


def test_normalize_foreshadowing_item_and_chapter_meta_entry():
    item = {
        "content": "  遗迹钥匙  ",
        "status": "pending",
        "tier": "main",
        "added_chapter": "第30章",
        "target": "120",
    }
    normalized_item = normalize_foreshadowing_item(item)
    assert normalized_item["content"] == "遗迹钥匙"
    assert normalized_item["status"] == FORESHADOWING_STATUS_PENDING
    assert normalized_item["tier"] == FORESHADOWING_TIER_CORE
    assert normalized_item["planted_chapter"] == 30
    assert normalized_item["target_chapter"] == 120

    state = {
        "chapter_meta": {
            "0003": {"coolpoint_pattern": "反杀, 掉马"},
            "7": {"patterns": ["翻车", "反杀"]},
        }
    }
    meta3 = get_chapter_meta_entry(state, 3)
    assert meta3["coolpoint_patterns"] == ["反杀", "掉马"]

    meta7 = get_chapter_meta_entry(state, 7)
    assert meta7["coolpoint_patterns"] == ["翻车", "反杀"]


def test_normalize_state_runtime_sections():
    state = {
        "plot_threads": {
            "foreshadowing": [
                {"content": "伏笔A", "status": "active", "tier": "decor", "chapter": 11, "target": 99},
                "invalid",
            ]
        },
        "chapter_meta": {
            1: {"cool_point_pattern": "打脸|翻车"},
            "bad": "invalid",
        },
    }

    normalized = normalize_state_runtime_sections(state)
    assert len(normalized["plot_threads"]["foreshadowing"]) == 1
    first = normalized["plot_threads"]["foreshadowing"][0]
    assert first["status"] == FORESHADOWING_STATUS_PENDING
    assert first["tier"] == FORESHADOWING_TIER_DECOR
    assert first["planted_chapter"] == 11
    assert first["target_chapter"] == 99

    chapter_meta = normalize_chapter_meta(normalized["chapter_meta"])
    assert "1" in chapter_meta
    assert chapter_meta["1"]["coolpoint_patterns"] == ["打脸", "翻车"]


def test_normalize_story_memory_adds_stable_ids_and_limits():
    raw = {
        "version": "1",
        "last_consolidated_chapter": "8",
        "characters": {
            "萧炎": {
                "current_state": "斗王",
                "last_update_chapter": 8,
                "milestones": [{"ch": 8, "event": "突破"} for _ in range(12)],
            }
        },
        "plot_threads": [
            {"content": "玄铁令", "status": "active", "tier": "core", "chapter": 8},
        ],
        "recent_events": [
            {"ch": 8, "event": "突破"},
        ],
        "structured_change_ledger": [
            {"ch": 8, "entity_id": "xiaoyan", "field": "灵石", "old": "100", "new": "150"},
        ],
        "chapter_snapshots": [
            {"chapter": 8, "saved_at": "2026-03-27T10:00:00Z", "protagonist": "萧炎"},
        ],
        "meta": {"source": "test"},
    }

    normalized = normalize_story_memory(raw)
    assert normalized["characters"]["萧炎"]["milestones"][-1]["milestone_id"]
    assert normalized["plot_threads"][0]["story_memory_id"]
    assert normalized["plot_threads"][0]["foreshadowing_id"]
    assert normalized["recent_events"][0]["event_id"]
    assert normalized["structured_change_ledger"][0]["change_id"]
    assert normalized["structured_change_ledger"][0]["delta"] == 50.0
    assert normalized["chapter_snapshots"][0]["story_memory_id"]
    assert len(normalized["characters"]["萧炎"]["milestones"]) == 10


def test_normalize_story_memory_archives_stale_and_resolved_items():
    raw = {
        "version": "1",
        "last_consolidated_chapter": 10,
        "characters": {},
        "plot_threads": [
            {"content": "过期伏笔", "status": "已回收", "resolved_chapter": 5, "chapter": 1},
            {"content": "新伏笔", "status": "active", "chapter": 9},
        ],
        "recent_events": [{"ch": i, "event": f"事件{i}"} for i in range(1, 55)],
        "structured_change_ledger": [
            {"ch": 3, "entity_id": "old", "field": "气氛", "old": "A", "new": "B", "memory_score": 40, "memory_tier": "working"},
            {"ch": 9, "entity_id": "new", "field": "状态", "old": "B", "new": "C", "memory_score": 85, "memory_tier": "consolidated"},
        ],
        "chapter_snapshots": [{"chapter": i, "saved_at": "2026-03-27T10:00:00Z"} for i in range(1, 25)],
        "meta": {},
    }

    normalized = normalize_story_memory(raw)
    assert normalized["plot_threads"][0]["content"] == "新伏笔"
    assert normalized["archive"]["plot_threads"][0]["content"] == "过期伏笔"
    assert len(normalized["recent_events"]) == 50
    assert len(normalized["archive"]["recent_events"]) == 4
    assert len(normalized["structured_change_ledger"]) == 1
    assert normalized["structured_change_ledger"][0]["entity_id"] == "new"
    assert normalized["archive"]["structured_change_ledger"][0]["entity_id"] == "old"
    assert len(normalized["chapter_snapshots"]) == 20
    assert len(normalized["archive"]["chapter_snapshots"]) == 4


def test_change_kind_and_significance_are_generic():
    relation_change = {
        "entity_id": "a",
        "field": "关系",
        "reason": "关键转折",
    }
    goal_change = {
        "entity_id": "b",
        "field": "目标",
        "reason": "任务推进",
    }
    timeline_change = {
        "entity_id": "d",
        "field": "时间",
        "reason": "次日推进",
    }
    generic_change = {
        "entity_id": "c",
        "field": "气氛",
        "reason": "日常过场",
    }

    assert infer_change_kind(relation_change) == "relationship_change"
    assert infer_change_kind(goal_change) == "goal_change"
    assert infer_change_kind(timeline_change) == "timeline_change"
    assert infer_change_kind(generic_change) == "state_change"

    relation_score = score_change_significance(relation_change)
    generic_score = score_change_significance(generic_change)

    assert relation_score["memory_tier"] in {"episodic", "consolidated"}
    assert relation_score["memory_score"] > generic_score["memory_score"]
    assert generic_score["should_consolidate"] is False


def test_memory_tier_rank_orders_consolidated_first():
    assert memory_tier_rank("consolidated") < memory_tier_rank("episodic") < memory_tier_rank("working")
    assert memory_tier_rank("unknown") == memory_tier_rank("working")
