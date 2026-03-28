#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path


def test_extract_state_summary_accepts_dominant_key(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import extract_state_summary

    state = {
        "progress": {"current_chapter": 12, "total_words": 12345},
        "protagonist_state": {
            "power": {"realm": "筑基", "layer": 2},
            "location": "宗门",
            "golden_finger": {"name": "系统", "level": 1},
        },
        "strand_tracker": {
            "history": [
                {"chapter": 10, "dominant": "quest"},
                {"chapter": 11, "dominant": "fire"},
            ]
        },
    }

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    (webnovel_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    text = extract_state_summary(tmp_path)
    assert "Ch10:quest" in text
    assert "Ch11:fire" in text


def test_extract_chapter_outline_supports_hyphen_filename(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import extract_chapter_outline

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷-详细大纲.md").write_text("### 第1章：测试标题\n测试大纲", encoding="utf-8")

    outline = extract_chapter_outline(tmp_path, 1)
    assert "### 第1章：测试标题" in outline
    assert "测试大纲" in outline


def test_extract_chapter_outline_prefers_state_volume_mapping(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import extract_chapter_outline

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "progress": {
            "volumes_planned": [
                {"volume": 1, "chapters_range": "1-10"},
                {"volume": 2, "chapters_range": "11-20"},
            ]
        }
    }
    (webnovel_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第2卷-详细大纲.md").write_text("### 第12章：V2标题\nV2大纲", encoding="utf-8")

    outline = extract_chapter_outline(tmp_path, 12)
    assert "### 第12章：V2标题" in outline
    assert "V2大纲" in outline


def test_extract_chapter_outline_falls_back_when_state_has_no_match(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import extract_chapter_outline

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    state = {"progress": {"volumes_planned": [{"volume": 1, "chapters_range": "1-10"}]}}
    (webnovel_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第2卷-详细大纲.md").write_text("### 第60章：V2标题\nV2大纲", encoding="utf-8")

    outline = extract_chapter_outline(tmp_path, 60)
    assert "### 第60章：V2标题" in outline
    assert "V2大纲" in outline


def test_build_chapter_context_payload_includes_contract_sections(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import build_chapter_context_payload
    from data_modules.config import DataModulesConfig
    from data_modules.index_manager import IndexManager, ChapterReadingPowerMeta, ReviewMetrics

    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()

    state = {
        "project": {"genre": "xuanhuan"},
        "progress": {"current_chapter": 3, "total_words": 9000},
        "protagonist_state": {
            "power": {"realm": "筑基", "layer": 2},
            "location": "宗门",
            "golden_finger": {"name": "系统", "level": 1},
        },
        "strand_tracker": {"history": [{"chapter": 2, "dominant": "quest"}]},
        "chapter_meta": {},
        "disambiguation_warnings": [],
        "disambiguation_pending": [],
    }
    (cfg.webnovel_dir / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    summaries_dir = cfg.webnovel_dir / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    (summaries_dir / "ch0002.md").write_text("## 剧情摘要\n上一章总结", encoding="utf-8")
    (cfg.webnovel_dir / "project_memory.json").write_text(
        json.dumps({"patterns": [{"pattern_type": "hook", "description": "危机钩"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (cfg.webnovel_dir / "memory").mkdir(parents=True, exist_ok=True)
    (cfg.webnovel_dir / "memory" / "story_memory.json").write_text(
        json.dumps(
            {
                "version": "1",
                "last_consolidated_chapter": 2,
                "last_consolidated_at": "2026-03-27T10:00:00Z",
                "characters": {"主角": {"current_state": "闭关", "last_update_chapter": 2}},
                "emotional_arcs": {
                    "主角": [
                        {
                            "chapter": 2,
                            "emotional_state": "压抑",
                            "emotional_trend": "down",
                            "trigger_event": "旧伤复发",
                        }
                    ]
                },
                "plot_threads": [{"name": "玄铁令", "status": "pending", "urgency": 88}],
                "recent_events": [{"ch": 2, "event": "突破"}],
                "chapter_snapshots": [],
                "meta": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷 详细大纲.md").write_text("### 第3章：测试标题\n测试大纲", encoding="utf-8")

    refs_dir = tmp_path / ".claude" / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "genre-profiles.md").write_text("## xuanhuan\n- 升级线清晰", encoding="utf-8")
    (refs_dir / "reading-power-taxonomy.md").write_text("## xuanhuan\n- 悬念钩优先", encoding="utf-8")
    cfg.current_focus_file.write_text(
        json.dumps(
            {
                "title": "回收旧线索",
                "goal": "本章必须拉回玄铁令",
                "must_resolve": ["确认玄铁令来历"],
                "hard_constraints": ["禁止扩写新支线"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    idx = IndexManager(cfg)
    idx.save_chapter_reading_power(
        ChapterReadingPowerMeta(chapter=2, hook_type="悬念钩", hook_strength="strong", coolpoint_patterns=["身份掉马"])
    )
    idx.save_review_metrics(
        ReviewMetrics(start_chapter=1, end_chapter=2, overall_score=71, dimension_scores={"plot": 71})
    )

    payload = build_chapter_context_payload(tmp_path, 3)
    assert payload["context_contract_version"] == "v3"
    assert payload.get("context_weight_stage") in {"early", "mid", "late"}
    assert payload["memory"]["project_memory"]["patterns"][0]["description"] == "危机钩"
    assert payload["story_technique_blueprint"]["primary_profile"] == "xianxia"
    assert payload["chapter_technique_plan"]["opening_hook"]
    assert payload["chapter_technique_plan"]["paragraph_rhythm"] == [
        "trigger",
        "reaction",
        "action",
        "result",
        "aftermath",
    ]
    assert payload["story_recall"]["priority_foreshadowing"][0]["name"] == "玄铁令"
    assert payload["story_recall"]["emotional_focus"][0]["emotional_state"] == "压抑"
    assert payload["chapter_intent"]["focus_title"] == "回收旧线索"
    assert "确认玄铁令来历" in payload["chapter_intent"]["must_resolve"]
    assert "writing_guidance" in payload
    assert isinstance(payload["writing_guidance"].get("guidance_items"), list)
    assert isinstance(payload["writing_guidance"].get("checklist"), list)
    assert isinstance(payload["writing_guidance"].get("checklist_score"), dict)
    assert payload["genre_profile"].get("genre") == "xuanhuan"
    assert "rag_assist" in payload
    assert isinstance(payload["rag_assist"], dict)
    assert payload["rag_assist"].get("invoked") is False


def test_render_text_contains_writing_guidance_section(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import _render_text

    payload = {
        "chapter": 10,
        "outline": "旧玉佩线索重现，大纲要求追查来历。",
        "previous_summaries": ["### 第9章摘要\n上一章"],
        "state_summary": "状态",
        "context_contract_version": "v3",
        "context_weight_stage": "early",
        "chapter_intent": {
            "focus_title": "拉回主线",
            "chapter_goal": "追查旧玉佩来历并回收旧债",
            "must_resolve": ["确认旧玉佩来源"],
            "story_risks": ["若拖延回收，主线张力会继续分散"],
            "hard_constraints": ["不要引入新组织"],
            "priority_memory": ["玄铁令伏笔"],
        },
        "story_recall": {
            "last_consolidated_chapter": 9,
            "recall_policy": {
                "mode": "boost",
                "should_recall_story_memory": True,
                "signal_count": 5,
                "consolidation_gap": 4,
                "reasons": ["archive_needed"],
            },
            "priority_foreshadowing": [{"name": "玄铁令", "urgency": 88}],
            "recent_events": [{"ch": 9, "event": "突破"}],
            "character_focus": [{"name": "萧炎", "current_state": "斗王", "last_update_chapter": 9}],
            "emotional_focus": [{"name": "萧炎", "emotional_state": "压抑", "trigger_event": "旧伤复发"}],
            "structured_change_focus": [{"ch": 9, "entity_id": "xiaoyan", "field": "灵石", "change_kind": "resource_change", "old_value": "100", "new_value": "150", "delta": 50}],
            "temporal_window": {
                "from_chapter": 7,
                "to_chapter": 9,
                "chapters": [{"chapter": 9, "title": "第9章：旧线回响"}],
                "state_changes": [{"chapter": 9, "entity_id": "xiaoyan", "field": "realm", "old_value": "斗者", "new_value": "斗师"}],
                "relationship_events": [{"chapter": 9, "from_entity": "xiaoyan", "to_entity": "yaolao", "type": "师徒"}],
            },
            "archive_recall": {
                "plot_threads": [{"content": "旧玉佩来历", "memory_tier": "archive", "archive_score": 3}],
                "recent_events": [{"ch": 5, "event": "找到旧玉佩"}],
                "structured_change_focus": [{"ch": 5, "entity_id": "yupei", "field": "来历", "memory_tier": "archive", "archive_score": 2}],
            },
        },
        "reader_signal": {"review_trend": {"overall_avg": 72}, "low_score_ranges": [{"start_chapter": 8, "end_chapter": 9}]},
        "genre_profile": {
            "genre": "xuanhuan",
            "genres": ["xuanhuan", "realistic"],
            "composite_hints": ["以玄幻主线推进，同时保留现实议题表达"],
            "reference_hints": ["升级线清晰"],
        },
        "writing_guidance": {
            "guidance_items": ["先修低分", "钩子差异化"],
            "checklist": [
                {
                    "id": "fix_low_score_range",
                    "label": "修复低分区间问题",
                    "weight": 1.4,
                    "required": True,
                    "source": "reader_signal.low_score_ranges",
                    "verify_hint": "至少完成1处冲突升级",
                }
            ],
            "checklist_score": {
                "score": 81.5,
                "completion_rate": 0.66,
                "required_completion_rate": 0.75,
            },
            "methodology": {
                "enabled": True,
                "framework": "digital-serial-v1",
                "pilot": "xianxia",
                "genre_profile_key": "xianxia",
                "chapter_stage": "confront",
                "observability": {
                    "next_reason_clarity": 78.0,
                    "anchor_effectiveness": 74.0,
                    "rhythm_naturalness": 72.0,
                },
                "signals": {"risk_flags": ["pattern_overuse_watch"]},
            },
        },
        "chapter_technique_plan": {
            "scene_role": "confront",
            "opening_hook": "旧玉佩刚一出现就被人当众认出",
            "mid_payoffs": ["先证明玉佩线索真实", "让旧债方先暴露敌意"],
            "climax_patterns": ["身份掉马", "反派翻车"],
            "ending_hook": "旧玉佩背后的真正主人在章末现身",
            "paragraph_rhythm": ["trigger", "reaction", "action", "result", "aftermath"],
            "anti_template_constraints": ["不要用连续三段解释性对白交代设定"],
        },
        "story_technique_blueprint": {
            "primary_profile": "xianxia",
            "generalized_strategy": False,
            "genre_strategy": {
                "hook_pool": ["悬念钩", "危机钩"],
                "coolpoint_pool": ["身份掉马", "反派翻车"],
            },
            "anti_template_constraints": ["禁止连续重复同构打脸"],
        },
    }

    text = _render_text(payload)
    assert "## 本章任务书" in text
    assert "追查旧玉佩来历并回收旧债" in text
    assert "## 高优先级召回" in text
    assert "玄铁令" in text
    assert "- 归档召回:" in text
    assert "- 情绪弧线:" in text
    assert "- 时序窗口召回:" in text
    assert "范围: Ch.7 ~ Ch.9" in text
    assert "窗口状态变化" in text
    assert "萧炎: 压抑 / stable（触发: 旧伤复发" in text
    assert "旧玉佩来历" in text
    assert "结构化变化账本" in text
    assert "## 写作执行建议" in text
    assert "先修低分" in text
    assert "## Contract (v3)" in text
    assert "- 上下文阶段权重: early" in text
    assert "### 执行检查清单（可评分）" in text
    assert "- 总权重: 1.40" in text
    assert "[必做][w=1.4] 修复低分区间问题" in text
    assert "### 执行评分" in text
    assert "- 评分: 81.5" in text
    assert "- 复合题材: xuanhuan + realistic" in text
    assert "## 长篇方法论策略" in text
    assert "- 适用题材: xianxia" in text
    assert "next_reason=78.0" in text
    assert "## 章节技巧编排" in text
    assert "旧玉佩刚一出现就被人当众认出" in text
    assert "trigger → reaction → action → result → aftermath" in text
    assert "## 项目技巧蓝图" in text
    assert "- 主题材画像: xianxia" in text
    assert "- 爽点池: 身份掉马, 反派翻车" in text


def test_render_text_contains_rag_assist_section_when_hits_exist(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from extract_chapter_context import _render_text

    payload = {
        "chapter": 12,
        "outline": "测试大纲",
        "previous_summaries": [],
        "state_summary": "状态",
        "context_contract_version": "v2",
        "reader_signal": {},
        "genre_profile": {},
        "writing_guidance": {},
        "rag_assist": {
            "invoked": True,
            "mode": "auto",
            "intent": "relationship",
            "query": "第12章 人物关系与动机：萧炎与药老发生冲突",
            "hits": [
                {
                    "chapter": 9,
                    "scene_index": 2,
                    "source": "graph_hybrid",
                    "score": 0.91,
                    "content": "萧炎与药老在修炼方向上发生分歧。",
                }
            ],
        },
    }

    text = _render_text(payload)
    assert "## RAG 检索线索" in text
    assert "- 模式: auto" in text
    assert "[graph_hybrid]" in text
    assert "萧炎与药老" in text
