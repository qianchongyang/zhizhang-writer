#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import workflow_manager

    return workflow_manager


def test_workflow_lifecycle_and_trace(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 7})
    module.start_step("Step 1", "Context")
    module.complete_step("Step 1", json.dumps({"state_json_modified": True}, ensure_ascii=False))
    module.complete_task(json.dumps({"review_completed": True}, ensure_ascii=False))

    state = module.load_state()
    assert state["current_task"] is None
    assert state["history"][-1]["status"] == module.TASK_STATUS_COMPLETED
    assert state["last_stable_state"]["artifacts"]["review_completed"] is True
    assert state["last_stable_state"]["workflow_trace"]["status"] == module.TASK_STATUS_COMPLETED
    assert state["history"][-1]["workflow_trace"]["stage"] == "task_completed"

    trace_path = module.get_call_trace_path()
    assert trace_path.exists()
    lines = trace_path.read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line)["event"] for line in lines if line.strip()]
    assert "task_started" in events
    assert "step_started" in events
    assert "step_completed" in events
    assert "task_completed" in events


def test_workflow_completed_state_derives_artifacts(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 13})
    module.start_step("Step 1", "Context")
    module.complete_step("Step 1", json.dumps({"ok": True}, ensure_ascii=False))
    module.start_step("Step 2A", "Draft")
    module.complete_step("Step 2A", json.dumps({"ok": True}, ensure_ascii=False))
    module.start_step("Step 2B", "Draft polish")
    module.complete_step("Step 2B", json.dumps({"ok": True}, ensure_ascii=False))
    module.start_step("Step 3", "Review")
    module.complete_step("Step 3", json.dumps({"ok": True}, ensure_ascii=False))
    module.start_step("Step 4", "Polish")
    module.complete_step("Step 4", json.dumps({"ok": True}, ensure_ascii=False))
    module.start_step("Step 5", "Data Agent")
    module.complete_step("Step 5", json.dumps({"ok": True}, ensure_ascii=False))
    module.complete_task(json.dumps({"ok": True}, ensure_ascii=False))

    state = module.load_state()
    artifacts = state["last_stable_state"]["artifacts"]
    assert artifacts["review_completed"] is True
    assert artifacts["state_json_modified"] is True
    assert artifacts["entities_appeared"] is True


def test_start_task_reentry_increments_retry(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 8})
    module.start_task("webnovel-write", {"chapter_num": 8})

    state = module.load_state()
    task = state["current_task"]
    assert task is not None
    assert task["status"] == module.TASK_STATUS_RUNNING
    assert int(task.get("retry_count", 0)) >= 1
    assert task["workflow_trace"]["status"] == module.TASK_STATUS_RUNNING


def test_complete_step_rejects_mismatch_step_id(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 9})
    module.start_step("Step 2A", "Draft")
    module.complete_step("Step 2B")

    state = module.load_state()
    current_step = state["current_task"]["current_step"]
    assert current_step is not None
    assert current_step["id"] == "Step 2A"
    assert current_step["status"] == module.STEP_STATUS_RUNNING


def test_workflow_step_owner_and_order_violation_trace(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    assert module.expected_step_owner("webnovel-write", "Step 1") == "context-agent"
    assert module.expected_step_owner("webnovel-write", "Step 5") == "data-agent"

    module.start_task("webnovel-write", {"chapter_num": 12})
    module.start_step("Step 3", "Review")

    state = module.load_state()
    assert state["current_task"]["workflow_trace"]["stage"] == "Step 3"
    assert state["current_task"]["workflow_trace"]["status"] == module.STEP_STATUS_RUNNING

    trace_path = module.get_call_trace_path()
    lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    events = [row.get("event") for row in lines]
    assert "step_order_violation" in events

    step_started = [row for row in lines if row.get("event") == "step_started"]
    assert step_started
    assert step_started[-1].get("payload", {}).get("expected_owner") == "review-agents"


def test_safe_append_call_trace_logs_failure(monkeypatch, caplog):
    module = _load_module()

    def _raise_trace_error(event, payload=None):
        raise RuntimeError("trace failure")

    monkeypatch.setattr(module, "append_call_trace", _raise_trace_error)

    with caplog.at_level(logging.WARNING):
        module.safe_append_call_trace("unit_test_event", {"ok": True})

    message_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "failed to append call trace" in message_text
    assert "unit_test_event" in message_text


def test_get_workflow_paths_support_zero_arg_find_project_root(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "_cli_project_root", None)
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    assert module.get_workflow_state_path() == tmp_path / ".webnovel" / "workflow_state.json"
    assert module.get_call_trace_path() == tmp_path / ".webnovel" / "observability" / "call_trace.jsonl"


def test_workflow_reentry_does_not_duplicate_history(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 20})
    module.start_task("webnovel-write", {"chapter_num": 20})
    module.start_task("webnovel-write", {"chapter_num": 20})

    state = module.load_state()
    assert isinstance(state.get("history"), list)
    assert len(state.get("history")) == 0

    task = state.get("current_task") or {}
    assert int(task.get("retry_count", 0)) >= 2
    assert task.get("workflow_trace", {}).get("status") == module.TASK_STATUS_RUNNING


def test_cleanup_artifacts_requires_confirm(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    draft_path = module.default_chapter_draft_path(tmp_path, 7)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text("draft", encoding="utf-8")

    git_called = {"count": 0}

    def _fake_run(*args, **kwargs):
        git_called["count"] += 1
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    preview = module.cleanup_artifacts(7, confirm=False)

    assert draft_path.exists()
    assert git_called["count"] == 0
    assert any(item.startswith("[预览]") for item in preview)


def test_cleanup_artifacts_confirm_deletes_with_backup(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    draft_path = module.default_chapter_draft_path(tmp_path, 8)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text("draft", encoding="utf-8")

    git_called = {"count": 0, "cmd": None}

    def _fake_run(cmd, **kwargs):
        git_called["count"] += 1
        git_called["cmd"] = cmd
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    cleaned = module.cleanup_artifacts(8, confirm=True)

    assert not draft_path.exists()
    assert git_called["count"] == 1
    assert git_called["cmd"] == ["git", "reset", "HEAD", "."]
    assert any("Git 暂存区已清理" in item for item in cleaned)

    backup_dir = tmp_path / ".webnovel" / "recovery_backups"
    backups = list(backup_dir.glob("ch0008-*"))
    assert backups


def test_workflow_normalizes_protocol_artifacts(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from data_modules.agent_protocol import write_protocol_json

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    review_path = tmp_path / ".webnovel" / "tmp" / "agent_outputs" / "review_merged_ch0012.json"
    data_path = tmp_path / ".webnovel" / "tmp" / "agent_outputs" / "data_ch0012.json"

    write_protocol_json(
        review_path,
        {
            "version": "1.0",
            "type": "review_merged",
            "chapter": 12,
            "timestamp": "2026-03-30T00:00:00Z",
            "anti_ai": {"pass": True, "penalty": 5, "rewrite_required": False},
        },
    )
    write_protocol_json(
        data_path,
        {
            "version": "1.0",
            "type": "data_write",
            "chapter": 12,
            "timestamp": "2026-03-30T00:00:00Z",
            "state_updated": True,
            "index_updated": True,
            "summary_written": True,
            "rag_indexed": False,
            "artifacts": {"summary": ".webnovel/summaries/ch0012.md"},
        },
    )

    module.start_task("webnovel-write", {"chapter_num": 12})
    module.start_step("Step 3", "Review")
    module.complete_step("Step 3", json.dumps({"review_protocol": str(review_path)}, ensure_ascii=False))
    module.start_step("Step 5", "Data Agent")
    module.complete_step("Step 5", json.dumps({"data_protocol": str(data_path)}, ensure_ascii=False))
    module.complete_task(json.dumps({"review_protocol": str(review_path), "data_protocol": str(data_path)}, ensure_ascii=False))

    state = module.load_state()
    artifacts = state["last_stable_state"]["artifacts"]
    assert artifacts["review_completed"] is True
    assert artifacts["anti_ai_pass"] is True
    assert artifacts["anti_ai_penalty"] == 5
    assert artifacts["state_json_modified"] is True
    assert artifacts["index_updated"] is True
    assert artifacts["summary_written"] is True
    assert artifacts["protocol_outputs"]["review"]["verified"] is True
    assert artifacts["protocol_outputs"]["data_write"]["verified"] is True


def test_outline_blocked_prevents_step6_start(tmp_path, monkeypatch):
    """Test that Step 6 is blocked when outline_blocked is set."""
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 10})
    module.start_step("Step 1", "Context")
    module.complete_step("Step 1")

    # Complete up to Step 5.5B
    for step_id in ["Step 2A", "Step 2B", "Step 3", "Step 4", "Step 5", "Step 5.5A", "Step 5.5B"]:
        module.start_step(step_id, step_id)
        module.complete_step(step_id)

    # Set outline blocked
    module.set_outline_blocked(module.OUTLINE_STATUS_BLOCKED_FAILED)

    # Verify outline_blocked is set
    state = module.load_state()
    assert state["current_task"]["outline_blocked"] == module.OUTLINE_STATUS_BLOCKED_FAILED

    # Try to start Step 6 - should be blocked
    module.start_step("Step 6", "Git Backup")

    # Step 6 should NOT have started - current_step should still be None
    state = module.load_state()
    assert state["current_task"]["current_step"] is None

    # Verify git_status.completed is NOT set
    assert state["current_task"]["artifacts"].get("git_status") != {"completed": True}


def test_outline_blocked_manual_review_prevents_step6(tmp_path, monkeypatch):
    """Test that Step 6 is blocked when outline is blocked for manual review."""
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 10})
    module.start_step("Step 1", "Context")
    module.complete_step("Step 1")

    # Complete up to Step 5
    for step_id in ["Step 2A", "Step 2B", "Step 3", "Step 4", "Step 5"]:
        module.start_step(step_id, step_id)
        module.complete_step(step_id)

    # Set outline blocked for manual review
    module.set_outline_blocked(module.OUTLINE_STATUS_BLOCKED_MANUAL_REVIEW)

    # Verify outline_blocked is set
    state = module.load_state()
    assert state["current_task"]["outline_blocked"] == module.OUTLINE_STATUS_BLOCKED_MANUAL_REVIEW

    # Try to start Step 6 - should be blocked
    module.start_step("Step 6", "Git Backup")

    # Step 6 should NOT have started
    state = module.load_state()
    assert state["current_task"]["current_step"] is None


def test_clear_outline_blocked_allows_step6(tmp_path, monkeypatch):
    """Test that clearing outline_blocked allows Step 6 to proceed."""
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 10})
    module.start_step("Step 1", "Context")
    module.complete_step("Step 1")

    # Complete up to Step 5.5B
    for step_id in ["Step 2A", "Step 2B", "Step 3", "Step 4", "Step 5", "Step 5.5A", "Step 5.5B"]:
        module.start_step(step_id, step_id)
        module.complete_step(step_id)

    # Set then clear outline blocked
    module.set_outline_blocked(module.OUTLINE_STATUS_BLOCKED_FAILED)
    module.clear_outline_blocked()

    # Verify outline_blocked is cleared
    state = module.load_state()
    assert state["current_task"]["outline_blocked"] == module.OUTLINE_STATUS_OK

    # Now Step 6 should be allowed
    module.start_step("Step 6", "Git Backup")

    state = module.load_state()
    assert state["current_task"]["current_step"] is not None
    assert state["current_task"]["current_step"]["id"] == "Step 6"


def test_new_task_initializes_outline_blocked(tmp_path, monkeypatch):
    """Test that a new task initializes outline_blocked to OK."""
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 10})

    state = module.load_state()
    assert state["current_task"]["outline_blocked"] == module.OUTLINE_STATUS_OK


def test_analyze_recovery_options_no_skip_for_55ab(tmp_path, monkeypatch):
    """Test that analyze_recovery_options does not offer skip option for Step 5.5A/5.5B."""
    module = _load_module()
    monkeypatch.setattr(module, "find_project_root", lambda: tmp_path)

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)

    module.start_task("webnovel-write", {"chapter_num": 10})
    module.start_step("Step 1", "Context")
    module.complete_step("Step 1")
    module.start_step("Step 5.5A", "Impact Preview")

    interrupt = module.detect_interruption()
    options = module.analyze_recovery_options(interrupt)

    # Should not have "跳过动态调纲" option
    labels = [opt.get("label") for opt in options]
    assert "跳过动态调纲" not in labels

    # Should have option to restart or terminate for manual review
    assert any("从 Step 5.5A 重新开始" in label for label in labels) or any("终止任务" in label for label in labels)
