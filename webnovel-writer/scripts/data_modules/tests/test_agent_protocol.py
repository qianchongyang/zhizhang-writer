#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path

import pytest

from data_modules.agent_protocol import (
    compute_checksum,
    protocol_filename,
    read_protocol_json,
    serialize_context_payload,
    serialize_data_write_payload,
    serialize_review_payload,
    verify_checksum,
    write_protocol_json,
)
from data_modules.context_manager import ContextManager


@pytest.fixture
def temp_project(tmp_path):
    from data_modules.config import DataModulesConfig

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


def test_protocol_filename_for_context():
    assert protocol_filename("context", 12) == "ctx_ch0012.json"


def test_write_and_read_protocol_json_roundtrip(tmp_path):
    payload = {
        "version": "1.0",
        "type": "context",
        "chapter": 12,
        "timestamp": "2026-03-30T00:00:00Z",
        "task_summary": {"chapter_goal": "推进主线"},
    }
    output = tmp_path / "ctx_ch0012.json"
    write_protocol_json(output, payload)

    loaded = read_protocol_json(output)
    assert loaded["chapter"] == 12
    assert loaded["checksum"].startswith("sha256:")
    assert verify_checksum(loaded) is True


def test_serialize_context_payload_extracts_stable_contract(temp_project):
    manager = ContextManager(temp_project)
    payload = manager.build_context(1, use_snapshot=False, save_snapshot=False)

    serialized = serialize_context_payload(payload, project_root=temp_project.project_root, chapter=1)

    assert serialized["type"] == "context"
    assert serialized["chapter"] == 1
    assert serialized["source"]["project_root"] == str(temp_project.project_root)
    assert "chapter_goal" in serialized["task_summary"]
    assert "hard_constraints" in serialized["constraints"]
    assert "chapter_outline" in serialized["context_contract"]
    assert "core_text" in serialized["writing_prompt"]
    assert verify_checksum(serialized) is True


def test_context_manager_output_file_writes_protocol_payload(temp_project, monkeypatch, tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    import data_modules.context_manager as context_manager_module

    output_path = tmp_path / "ctx_ch0001.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "context_manager",
            "--project-root",
            str(temp_project.project_root),
            "--chapter",
            "1",
            "--output-file",
            str(output_path),
        ],
    )

    context_manager_module.main()

    written = read_protocol_json(output_path)
    assert written["type"] == "context"
    assert written["chapter"] == 1
    assert written["source"]["project_root"] == str(temp_project.project_root)
    assert compute_checksum(written) == written["checksum"]


def test_extract_context_output_file_writes_protocol_payload(temp_project, monkeypatch, tmp_path):
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    import extract_chapter_context as extract_chapter_context_module

    output_path = tmp_path / "ctx_extract_ch0001.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "extract_chapter_context",
            "--project-root",
            str(temp_project.project_root),
            "--chapter",
            "1",
            "--format",
            "json",
            "--output-file",
            str(output_path),
        ],
    )

    extract_chapter_context_module.main()

    written = read_protocol_json(output_path)
    assert written["type"] == "context"
    assert written["chapter"] == 1
    assert written["source"]["project_root"] == str(temp_project.project_root)


def test_serialize_review_payload_includes_anti_ai_summary():
    payload = serialize_review_payload(
        {
            "overall_score": 82,
            "severity_counts": {"high": 1, "medium": 2},
            "issues": [{"id": "X"}],
            "recommendations": ["补一段铺垫"],
            "anti_ai": {"pass": True, "penalty": 5, "rewrite_required": False},
        },
        chapter=12,
        group="merged",
    )
    assert payload["type"] == "review_merged"
    assert payload["anti_ai"]["pass"] is True
    assert payload["severity_counts"]["high"] == 1
    assert verify_checksum(payload) is True


def test_serialize_data_write_payload():
    payload = serialize_data_write_payload(
        {
            "state_updated": True,
            "index_updated": True,
            "summary_written": True,
            "rag_indexed": False,
            "artifacts": {"summary": ".webnovel/summaries/ch0012.md"},
        },
        chapter=12,
    )
    assert payload["type"] == "data_write"
    assert payload["state_updated"] is True
    assert payload["artifacts"]["summary"].endswith("ch0012.md")
    assert verify_checksum(payload) is True
