#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path
from types import SimpleNamespace


def test_cmd_review_merge_normalizes_nested_review_shapes(tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from data_modules.webnovel import cmd_review_merge

    group1 = {
        "check_id": "rev1_ch0013",
        "chapter": 13,
        "summary": {
            "total_issues": 4,
            "critical": 0,
            "high": 2,
            "medium": 1,
            "low": 1,
            "passed": False,
        },
        "power_consistency": {"status": "PASS", "issues": []},
        "location_character_consistency": {
            "status": "PASS",
            "issues": [
                {
                    "severity": "high",
                    "type": "APPEARANCE_DISCREPANCY",
                    "entity": "师妹",
                    "note": "外观描述不一致",
                }
            ],
        },
        "timeline_consistency": {
            "status": "MINOR_ISSUE",
            "issues": [
                {
                    "severity": "medium",
                    "type": "CHAPTER_META_INCONSISTENT",
                    "detail": "chapter_meta记录与正文不符",
                }
            ],
        },
        "state_change_detection": {
            "status": "HIGH_PRIORITY_ISSUE",
            "issues": [
                {
                    "severity": "critical",
                    "type": "CHAPTER_NOT_SYNCED",
                    "entity": "progress.current_chapter",
                    "note": "state.json未同步章节进度",
                }
            ],
        },
        "综合评分": {
            "overall_score": 75,
            "通过": False,
            "严重违规": 2,
            "轻微问题": 2,
        },
    }
    group2 = {
        "checker": "pacing-checker",
        "chapter": 13,
        "overall_assessment": {
            "rhythm_health": "健康",
            "reader_fatigue_risk": "低",
            "recommendations": ["第14章可考虑增加修仙探索内容(Quest线)"],
        },
        "balance_check": {
            "warnings": ["Fire线连续两章出现，需注意不要过度感情戏"],
        },
    }

    group1_path = tmp_path / "rev1.json"
    group2_path = tmp_path / "rev2.json"
    output_path = tmp_path / "merged.json"
    group1_path.write_text(json.dumps(group1, ensure_ascii=False), encoding="utf-8")
    group2_path.write_text(json.dumps(group2, ensure_ascii=False), encoding="utf-8")

    args = SimpleNamespace(group1=str(group1_path), group2=str(group2_path), output=str(output_path))
    assert cmd_review_merge(args) == 0

    merged = json.loads(output_path.read_text(encoding="utf-8"))
    assert merged["overall_score"] > 70
    assert merged["severity_counts"] == {"critical": 0, "high": 2, "medium": 1, "low": 1}
    assert len(merged["issues"]) >= 2
