#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
from pathlib import Path

try:
    from chapter_paths import volume_num_for_chapter
except ImportError:  # pragma: no cover
    from scripts.chapter_paths import volume_num_for_chapter


_CHAPTER_RANGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
_OUTLINE_MISSING_PREFIXES = (
    "⚠️ 大纲文件不存在",
    "⚠️ 未找到第",
)

_CHAPTER_CONTRACT_FIELDS = {
    "goal": ("目标", "目的"),
    "conflict": ("冲突", "阻力", "对手"),
    "action": ("动作", "行动", "计划"),
    "result": ("结果", "产出", "变化"),
    "cost": ("代价", "损失", "牺牲"),
    "hook": ("钩子", "悬念", "未解", "反问"),
}

_STATE_CHANGE_KEYWORDS = (
    "提升",
    "下降",
    "获得",
    "失去",
    "突破",
    "暴露",
    "结盟",
    "破裂",
    "离开",
    "到达",
    "转移",
    "受伤",
    "升级",
    "进入",
    "退出",
    "成功",
    "失败",
)


def is_missing_chapter_outline(outline_text: object) -> bool:
    text = str(outline_text or "").strip()
    if not text:
        return True
    return any(text.startswith(prefix) for prefix in _OUTLINE_MISSING_PREFIXES)


def extract_chapter_contract(outline_text: object) -> dict[str, str]:
    text = str(outline_text or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    contract: dict[str, str] = {}
    for line in lines:
        for key, labels in _CHAPTER_CONTRACT_FIELDS.items():
            if key in contract:
                continue
            for label in labels:
                pattern = rf"^[-*\s]*{re.escape(label)}\s*[:：]\s*(.+)$"
                match = re.search(pattern, line)
                if match:
                    contract[key] = match.group(1).strip()
                    break
    return contract


def count_state_change_signals(contract: dict[str, str], outline_text: object) -> int:
    candidates = []
    if isinstance(contract, dict):
        for key in ("result", "cost", "action"):
            value = contract.get(key)
            if value:
                candidates.append(str(value))
    candidates.append(str(outline_text or ""))

    score = 0
    for text in candidates:
        for keyword in _STATE_CHANGE_KEYWORDS:
            if keyword in text:
                score += 1
    return score


def validate_chapter_contract(outline_text: object, min_state_changes: int = 0) -> list[str]:
    if is_missing_chapter_outline(outline_text):
        return ["outline_missing"]

    contract = extract_chapter_contract(outline_text)
    missing: list[str] = []
    for key, labels in _CHAPTER_CONTRACT_FIELDS.items():
        if key not in contract:
            missing.append(labels[0])

    if min_state_changes > 0:
        signals = count_state_change_signals(contract, outline_text)
        if signals < min_state_changes:
            missing.append("状态变化")

    return missing


def _parse_chapters_range(value: object) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = _CHAPTER_RANGE_RE.match(value)
    if not match:
        return None
    try:
        start = int(match.group(1))
        end = int(match.group(2))
    except ValueError:
        return None
    if start <= 0 or end <= 0 or start > end:
        return None
    return start, end


def volume_num_for_chapter_from_state(project_root: Path, chapter_num: int) -> int | None:
    state_path = project_root / ".webnovel" / "state.json"
    if not state_path.exists():
        return None

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(state, dict):
        return None

    progress = state.get("progress")
    if not isinstance(progress, dict):
        return None

    volumes_planned = progress.get("volumes_planned")
    if not isinstance(volumes_planned, list):
        return None

    best: tuple[int, int] | None = None
    for item in volumes_planned:
        if not isinstance(item, dict):
            continue
        volume = item.get("volume")
        if not isinstance(volume, int) or volume <= 0:
            continue
        parsed = _parse_chapters_range(item.get("chapters_range"))
        if not parsed:
            continue
        start, end = parsed
        if start <= chapter_num <= end:
            candidate = (start, volume)
            if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
                best = candidate

    return best[1] if best else None


def _find_split_outline_file(outline_dir: Path, chapter_num: int) -> Path | None:
    patterns = [
        f"第{chapter_num}章*.md",
        f"第{chapter_num:02d}章*.md",
        f"第{chapter_num:03d}章*.md",
        f"第{chapter_num:04d}章*.md",
    ]
    for pattern in patterns:
        matches = sorted(outline_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def _find_volume_outline_file(project_root: Path, chapter_num: int) -> Path | None:
    outline_dir = project_root / "大纲"
    volume_num = volume_num_for_chapter_from_state(project_root, chapter_num) or volume_num_for_chapter(chapter_num)
    candidates = [
        outline_dir / f"第{volume_num}卷-详细大纲.md",
        outline_dir / f"第{volume_num}卷 - 详细大纲.md",
        outline_dir / f"第{volume_num}卷 详细大纲.md",
    ]
    return next((path for path in candidates if path.exists()), None)


def _extract_outline_section(content: str, chapter_num: int) -> str | None:
    patterns = [
        rf"(###\s*第\s*{chapter_num}\s*章(?:[：:][^\n]*)?\n.+?)(?=###\s*第\s*\d+\s*章|##\s|$)",
        rf"(###\s*第{chapter_num}章(?:[：:][^\n]*)?\n.+?)(?=###\s*第\d+章|##\s|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(0).strip()
    return None


def load_chapter_outline(project_root: Path, chapter_num: int, max_chars: int | None = 1500) -> str:
    outline_dir = project_root / "大纲"

    split_outline = _find_split_outline_file(outline_dir, chapter_num)
    if split_outline is not None:
        return split_outline.read_text(encoding="utf-8")

    volume_outline = _find_volume_outline_file(project_root, chapter_num)
    if volume_outline is None:
        return f"⚠️ 大纲文件不存在：第 {chapter_num} 章"

    outline = _extract_outline_section(volume_outline.read_text(encoding="utf-8"), chapter_num)
    if outline is None:
        return f"⚠️ 未找到第 {chapter_num} 章的大纲"

    if max_chars and len(outline) > max_chars:
        return outline[:max_chars] + "\n...(已截断)"
    return outline
