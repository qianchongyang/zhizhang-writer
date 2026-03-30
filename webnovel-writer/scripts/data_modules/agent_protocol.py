#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent output protocol helpers.

Provides:
- stable file naming for agent outputs
- checksum calculation and verification
- atomic JSON writes
- context payload serializer for agent middleware
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .config import DataModulesConfig


PROTOCOL_VERSION = "1.0"
DEFAULT_OUTPUT_SUBDIR = Path(".webnovel") / "tmp" / "agent_outputs"

_FILE_PREFIX = {
    "context": "ctx",
    "review_group_1": "rev1",
    "review_group_2": "rev2",
    "review_merged": "review_merged",
    "data_write": "data",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def protocol_output_dir(config: DataModulesConfig) -> Path:
    return config.webnovel_dir / "tmp" / "agent_outputs"


def protocol_filename(payload_type: str, chapter: int) -> str:
    prefix = _FILE_PREFIX.get(payload_type)
    if not prefix:
        raise ValueError(f"unsupported agent payload type: {payload_type}")
    return f"{prefix}_ch{int(chapter):04d}.json"


def protocol_path(config: DataModulesConfig, payload_type: str, chapter: int) -> Path:
    return protocol_output_dir(config) / protocol_filename(payload_type, chapter)


def _canonical_json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_checksum(payload: Dict[str, Any]) -> str:
    canonical = copy.deepcopy(payload)
    canonical.pop("checksum", None)
    digest = hashlib.sha256(_canonical_json_bytes(canonical)).hexdigest()
    return f"sha256:{digest}"


def with_checksum(payload: Dict[str, Any]) -> Dict[str, Any]:
    enriched = copy.deepcopy(payload)
    enriched["checksum"] = compute_checksum(enriched)
    return enriched


def verify_checksum(payload: Dict[str, Any]) -> bool:
    actual = payload.get("checksum")
    if not isinstance(actual, str) or not actual:
        return False
    expected = compute_checksum(payload)
    return actual == expected


def write_protocol_json(path: Path, payload: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    final_payload = with_checksum(payload)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(final_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    return path


def read_protocol_json(path: Path, *, verify: bool = True) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if verify and not verify_checksum(payload):
        raise ValueError(f"checksum verification failed: {path}")
    return payload


def _section_content(payload: Dict[str, Any], name: str) -> Dict[str, Any]:
    section = (payload.get("sections") or {}).get(name) or {}
    content = section.get("content") or {}
    return content if isinstance(content, dict) else {}


def _section_text(payload: Dict[str, Any], name: str) -> str:
    section = (payload.get("sections") or {}).get(name) or {}
    text = section.get("text") or ""
    return str(text)


def serialize_context_payload(
    payload: Dict[str, Any],
    *,
    project_root: Path,
    chapter: int,
) -> Dict[str, Any]:
    chapter_intent = _section_content(payload, "chapter_intent")
    chapter_technique_plan = _section_content(payload, "chapter_technique_plan")
    writing_guidance = _section_content(payload, "writing_guidance")
    genre_profile = _section_content(payload, "genre_profile")
    reader_signal = _section_content(payload, "reader_signal")
    memory = _section_content(payload, "memory")
    story_recall = _section_content(payload, "story_recall")
    core = _section_content(payload, "core")
    scene = _section_content(payload, "scene")
    meta = payload.get("meta") or {}

    protocol_payload = {
        "version": PROTOCOL_VERSION,
        "type": "context",
        "chapter": int(chapter),
        "timestamp": utc_timestamp(),
        "source": {
            "project_root": str(project_root),
            "template": str(payload.get("template") or ""),
            "snapshot_used": bool(meta.get("snapshot_used", False)),
            "context_weight_stage": meta.get("context_weight_stage"),
            "context_contract_version": meta.get("context_contract_version"),
        },
        "task_summary": {
            "focus_title": chapter_intent.get("focus_title"),
            "chapter_goal": chapter_intent.get("chapter_goal"),
            "must_resolve": chapter_intent.get("must_resolve") or [],
            "story_risks": chapter_intent.get("story_risks") or [],
            "priority_memory": chapter_intent.get("priority_memory") or [],
        },
        "constraints": {
            "hard_constraints": chapter_intent.get("hard_constraints") or [],
            "current_focus": memory.get("current_focus") or {},
            "author_intent": memory.get("author_intent") or {},
            "priority_foreshadowing": story_recall.get("priority_foreshadowing") or [],
            "location_context": scene.get("location_context") or {},
        },
        "style_guide": {
            "guidance_items": writing_guidance.get("guidance_items") or [],
            "strategy_card": writing_guidance.get("strategy_card") or {},
            "genre_profile": genre_profile,
            "reader_signal": reader_signal,
            "chapter_technique_plan": chapter_technique_plan,
        },
        "context_contract": {
            "chapter_outline": core.get("chapter_outline") or "",
            "recent_summaries": core.get("recent_summaries") or [],
            "recent_meta": core.get("recent_meta") or [],
            "story_recall": story_recall,
        },
        "writing_prompt": {
            "core_text": _section_text(payload, "core"),
            "scene_text": _section_text(payload, "scene"),
            "chapter_intent_text": _section_text(payload, "chapter_intent"),
            "chapter_technique_plan_text": _section_text(payload, "chapter_technique_plan"),
            "writing_guidance_text": _section_text(payload, "writing_guidance"),
        },
    }
    return with_checksum(protocol_payload)


def serialize_review_payload(
    review_payload: Dict[str, Any],
    *,
    chapter: int,
    group: str = "merged",
) -> Dict[str, Any]:
    payload_type = {
        "rev1": "review_group_1",
        "rev2": "review_group_2",
        "merged": "review_merged",
    }.get(group, "review_merged")
    severity_counts = review_payload.get("severity_counts") or {}
    anti_ai = review_payload.get("anti_ai") or {}
    protocol_payload = {
        "version": PROTOCOL_VERSION,
        "type": payload_type,
        "chapter": int(chapter),
        "timestamp": utc_timestamp(),
        "group": group,
        "overall_score": review_payload.get("overall_score"),
        "severity_counts": {
            "critical": int(severity_counts.get("critical", 0) or 0),
            "high": int(severity_counts.get("high", 0) or 0),
            "medium": int(severity_counts.get("medium", 0) or 0),
            "low": int(severity_counts.get("low", 0) or 0),
        },
        "issues": review_payload.get("issues") or [],
        "recommendations": review_payload.get("recommendations") or [],
        "summary": review_payload.get("summary") or "",
        "anti_ai": {
            "pass": anti_ai.get("pass"),
            "penalty": anti_ai.get("penalty"),
            "rewrite_required": anti_ai.get("rewrite_required"),
        } if anti_ai else {},
    }
    return with_checksum(protocol_payload)


def serialize_data_write_payload(
    write_payload: Dict[str, Any],
    *,
    chapter: int,
) -> Dict[str, Any]:
    artifacts = write_payload.get("artifacts") or {}
    protocol_payload = {
        "version": PROTOCOL_VERSION,
        "type": "data_write",
        "chapter": int(chapter),
        "timestamp": utc_timestamp(),
        "state_updated": bool(write_payload.get("state_updated", False)),
        "index_updated": bool(write_payload.get("index_updated", False)),
        "summary_written": bool(write_payload.get("summary_written", False)),
        "rag_indexed": bool(write_payload.get("rag_indexed", False)),
        "artifacts": artifacts if isinstance(artifacts, dict) else {},
    }
    return with_checksum(protocol_payload)
