#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path

from data_modules.agent_protocol import (
    protocol_path,
    serialize_context_payload,
    serialize_data_write_payload,
    serialize_review_payload,
    write_protocol_json,
)
from data_modules.config import DataModulesConfig
from data_modules.context_manager import ContextManager


def _load_workflow_module():
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import workflow_manager

    return workflow_manager


def _make_project(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()
    outline_dir = cfg.outline_dir
    outline_dir.mkdir(parents=True, exist_ok=True)
    outline_lines = ["# 第1卷 详细大纲"]
    for ch in range(1, 6):
        outline_lines.append(f"### 第{ch}章：测试标题{ch}")
        outline_lines.append("目标：推进主线")
        outline_lines.append("冲突：遭遇阻力")
        outline_lines.append("动作：主动调查")
        outline_lines.append("结果：获得线索并突破")
        outline_lines.append("代价：暴露行踪")
        outline_lines.append("钩子：更大危机显现")
        outline_lines.append("")
    (outline_dir / "第1卷-详细大纲.md").write_text("\n".join(outline_lines), encoding="utf-8")
    state = {
        "protagonist_state": {"name": "测试主角", "location": {"current": "测试地点"}},
        "chapter_meta": {"0001": {"hook": "测试钩子"}},
        "progress": {"current_chapter": 1},
    }
    cfg.state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    cfg.current_focus_file.write_text(json.dumps({"focus": "收紧主线"}, ensure_ascii=False), encoding="utf-8")
    cfg.author_intent_file.write_text(json.dumps({"hard_rules": ["不偏离主线"]}, ensure_ascii=False), encoding="utf-8")
    return cfg


def test_write_workflow_smoke_protocol_closed_loop(tmp_path, monkeypatch):
    cfg = _make_project(tmp_path)
    workflow = _load_workflow_module()
    monkeypatch.setattr(workflow, "find_project_root", lambda: tmp_path)

    manager = ContextManager(cfg)
    internal_context = manager.build_context(1, use_snapshot=False, save_snapshot=False)
    context_payload = serialize_context_payload(internal_context, project_root=cfg.project_root, chapter=1)
    context_path = protocol_path(cfg, "context", 1)
    write_protocol_json(context_path, context_payload)

    review_payload = serialize_review_payload(
        {
            "overall_score": 84,
            "severity_counts": {"critical": 0, "high": 1, "medium": 1, "low": 0},
            "issues": [{"id": "ANTI_AI_001", "severity": "medium"}],
            "recommendations": ["补一段情绪承接"],
            "anti_ai": {"pass": True, "penalty": 4, "rewrite_required": False},
        },
        chapter=1,
        group="merged",
    )
    review_path = cfg.webnovel_dir / "tmp" / "merged" / "review_merged_ch0001.json"
    write_protocol_json(review_path, review_payload)

    data_payload = serialize_data_write_payload(
        {
            "state_updated": True,
            "index_updated": True,
            "summary_written": True,
            "rag_indexed": False,
            "artifacts": {"summary": ".webnovel/summaries/ch0001.md"},
        },
        chapter=1,
    )
    data_path = protocol_path(cfg, "data_write", 1)
    write_protocol_json(data_path, data_payload)

    workflow.start_task("webnovel-write", {"chapter_num": 1})
    workflow.start_step("Step 1", "Context Agent")
    workflow.complete_step("Step 1", json.dumps({"context_protocol": str(context_path)}, ensure_ascii=False))
    workflow.start_step("Step 3", "Review")
    workflow.complete_step("Step 3", json.dumps({"review_protocol": str(review_path)}, ensure_ascii=False))
    workflow.start_step("Step 5", "Data Agent")
    workflow.complete_step("Step 5", json.dumps({"data_protocol": str(data_path)}, ensure_ascii=False))
    workflow.complete_task(
        json.dumps(
            {
                "context_protocol": str(context_path),
                "review_protocol": str(review_path),
                "data_protocol": str(data_path),
            },
            ensure_ascii=False,
        )
    )

    state = workflow.load_state()
    stable = state["last_stable_state"]
    artifacts = stable["artifacts"]

    assert stable["command"] == "webnovel-write"
    assert artifacts["context_built"] is True
    assert artifacts["review_completed"] is True
    assert artifacts["anti_ai_pass"] is True
    assert artifacts["state_json_modified"] is True
    assert artifacts["index_updated"] is True
    assert artifacts["summary_written"] is True
    assert artifacts["protocol_outputs"]["context"]["verified"] is True
    assert artifacts["protocol_outputs"]["review"]["verified"] is True
    assert artifacts["protocol_outputs"]["data_write"]["verified"] is True
