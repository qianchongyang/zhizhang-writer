#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态大纲运行层 (Outline Runtime) - 最小数据契约

定义动态调纲运行时需要持久化的核心对象：
- outline_runtime.json: 活动窗口状态
- outline_adjustments.jsonl: 调纲操作日志
- outline_history/: 历史快照目录

Architecture Decision:
- window_version 增长由 JSONL 成功追加 adjustment_id 触发，不由 runtime 写入触发
- outline_runtime.json 与大纲/第X卷-详细大纲.md 的最新有效版本可通过 last_applied_adjustment_id 对齐
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Schema 定义
# ============================================================================


class NodeDependency(BaseModel):
    """节点依赖最小集合"""
    model_config = ConfigDict(extra="allow")

    character_state: Optional[str] = None  # 角色状态引用
    item_state: Optional[str] = None  # 物品状态引用
    relationship_state: Optional[str] = None  # 关系状态引用
    foreshadowing: Optional[str] = None  # 伏笔引用
    prior_chapter: Optional[int] = None  # 前置章节号


class OutlineNode(BaseModel):
    """大纲节点（章节或弧线）"""
    model_config = ConfigDict(extra="allow")

    chapter: int  # 章节号
    title: str  # 标题
    goal: str  # 目标
    conflict: str  # 冲突
    cost: str  # 代价
    hook: str  # 钩子
    dependencies: NodeDependency = Field(default_factory=NodeDependency)  # 依赖
    node_type: str = "chapter"  # node_type: chapter / arc
    mainline_anchor_refs: List[str] = Field(default_factory=list)  # 主线锚点引用


class MainlineAnchor(BaseModel):
    """主线锚点"""
    model_config = ConfigDict(extra="allow")

    anchor_id: str  # 锚点唯一标识
    chapter: int  # 锚点所在章节
    label: str  # 锚点标签
    description: str  # 锚点描述


class OutlineRuntime(BaseModel):
    """动态大纲运行层运行时状态"""
    model_config = ConfigDict(extra="allow")

    # 活动窗口
    active_volume: int = 1  # 当前卷号
    active_window_start: int = 1  # 活动窗口起始章节
    active_window_end: int = 50  # 活动窗口结束章节

    # 版本控制
    window_version: int = 0  # 窗口版本（由 JSONL 追加触发增长）
    baseline_anchor_version: int = 0  # 基线锚点版本
    last_adjustment_chapter: Optional[int] = None  # 最后调整章节
    last_adjustment_type: Optional[str] = None  # 最后调整类型
    last_applied_adjustment_id: Optional[str] = None  # 最后应用的调整ID（用于对齐大纲文件）

    # 回归主线
    return_to_mainline_by: Optional[int] = None  # 计划回归主线的章节号

    # 状态
    window_status: str = "active"  # active / closed / merged

    # 主线锚点
    mainline_anchors: List[MainlineAnchor] = Field(default_factory=list)

    # 活动节点
    active_nodes: List[OutlineNode] = Field(default_factory=list)


class OutlineAdjustment(BaseModel):
    """单次大纲调整记录"""
    model_config = ConfigDict(extra="allow")

    # 触发信息
    adjustment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trigger_chapter: int  # 触发调整的章节
    adjustment_type: str  # 调整类型：insert / delete / modify / split / merge
    reason: str  # 调整原因
    impact_preview: str  # 影响预览

    # 主线服务
    mainline_service_reason: Optional[str] = None  # 主线服务说明
    return_to_mainline_by: Optional[int] = None  # 计划回归主线的章节号

    # 窗口变化
    before_window: Dict[str, Any]  # 调整前窗口 {start, end, version}
    after_window: Dict[str, Any]  # 调整后窗口 {start, end, version}

    # 元信息
    written_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ============================================================================
# 归一化函数
# ============================================================================


def normalize_outline_runtime(data: Dict[str, Any]) -> Dict[str, Any]:
    """归一化 outline_runtime.json 数据，确保字段完整且类型正确"""
    if not isinstance(data, dict):
        return _default_runtime_dict()

    # 确保数值字段
    data.setdefault("active_volume", 1)
    data.setdefault("active_window_start", 1)
    data.setdefault("active_window_end", 50)
    data.setdefault("window_version", 0)
    data.setdefault("baseline_anchor_version", 0)
    data.setdefault("last_adjustment_chapter", None)
    data.setdefault("last_adjustment_type", None)
    data.setdefault("last_applied_adjustment_id", None)
    data.setdefault("return_to_mainline_by", None)
    data.setdefault("window_status", "active")
    data.setdefault("mainline_anchors", [])
    data.setdefault("active_nodes", [])

    # 类型校验
    for key in ["active_volume", "active_window_start", "active_window_end",
                "window_version", "baseline_anchor_version"]:
        if key in data and not isinstance(data[key], int):
            data[key] = int(data[key])

    for key in ["last_adjustment_chapter", "return_to_mainline_by"]:
        if key in data and data[key] is not None and not isinstance(data[key], int):
            data[key] = int(data[key])

    return data


def normalize_outline_adjustment(data: Dict[str, Any]) -> Dict[str, Any]:
    """归一化单条 adjustment 记录"""
    if not isinstance(data, dict):
        raise ValueError("adjustment record must be a dict")

    required = ["trigger_chapter", "adjustment_type", "reason", "impact_preview",
                "before_window", "after_window"]
    for field in required:
        if field not in data:
            raise ValueError(f"missing required field: {field}")

    # 确保元字段
    data.setdefault("adjustment_id", str(uuid.uuid4()))
    data.setdefault("mainline_service_reason", None)
    data.setdefault("return_to_mainline_by", None)
    data.setdefault(
        "written_at",
        datetime.now(timezone.utc).isoformat()
    )

    return data


# ============================================================================
# 默认值
# ============================================================================


def _default_runtime_dict() -> Dict[str, Any]:
    """返回默认运行时状态字典"""
    return {
        "active_volume": 1,
        "active_window_start": 1,
        "active_window_end": 50,
        "window_version": 0,
        "baseline_anchor_version": 0,
        "last_adjustment_chapter": None,
        "last_adjustment_type": None,
        "last_applied_adjustment_id": None,
        "return_to_mainline_by": None,
        "window_status": "active",
        "mainline_anchors": [],
        "active_nodes": [],
    }


def _default_node_dependency() -> Dict[str, Any]:
    """返回默认节点依赖字典"""
    return {
        "character_state": None,
        "item_state": None,
        "relationship_state": None,
        "foreshadowing": None,
        "prior_chapter": None,
    }


# ============================================================================
# 读写接口
# ============================================================================


def load_outline_runtime(runtime_file: Path) -> OutlineRuntime:
    """加载 outline_runtime.json，支持空文件与缺字段"""
    if not runtime_file.exists():
        return OutlineRuntime()

    try:
        raw = json.loads(runtime_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        # 文件损坏或为空时，返回默认状态
        return OutlineRuntime()

    normalized = normalize_outline_runtime(raw)
    return OutlineRuntime.model_validate(normalized)


def save_outline_runtime(runtime_file: Path, runtime: OutlineRuntime) -> None:
    """安全写入 outline_runtime.json（原子化写入）"""
    runtime_file.parent.mkdir(parents=True, exist_ok=True)

    # 转换为 dict
    data = runtime.model_dump(mode="json", exclude_none=False)

    # 原子化写入
    temp_path = runtime_file.with_suffix(".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(runtime_file)


def load_outline_adjustments(adjustments_file: Path) -> List[OutlineAdjustment]:
    """加载 outline_adjustments.jsonl（按行读取 JSONL）"""
    if not adjustments_file.exists():
        return []

    records = []
    for line in adjustments_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            normalized = normalize_outline_adjustment(record)
            records.append(OutlineAdjustment.model_validate(normalized))
        except (json.JSONDecodeError, ValueError):
            # 跳过损坏的行
            continue

    return records


def append_outline_adjustment(
    adjustments_file: Path,
    adjustment: OutlineAdjustment
) -> str:
    """追加单条 adjustment 到 JSONL 文件，返回 adjustment_id

    注意：根据 Architecture Decision，这是触发 window_version 增长的唯一入口。
    """
    adjustments_file.parent.mkdir(parents=True, exist_ok=True)

    data = adjustment.model_dump(mode="json", exclude_none=False)
    line = json.dumps(data, ensure_ascii=False)

    # 原子化追加：先写临时文件再追加
    temp_path = adjustments_file.with_suffix(".jsonl.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(line + "\n")

    # 追加到原文件
    with open(adjustments_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    # 删除临时文件
    if temp_path.exists():
        temp_path.unlink()

    return adjustment.adjustment_id


def get_last_adjustment_id(adjustments_file: Path) -> Optional[str]:
    """获取 JSONL 最后一条记录的 adjustment_id"""
    if not adjustments_file.exists():
        return None

    lines = adjustments_file.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            return record.get("adjustment_id")
        except json.JSONDecodeError:
            continue

    return None


def sync_runtime_version_from_adjustments(
    runtime_file: Path,
    adjustments_file: Path
) -> OutlineRuntime:
    """根据 JSONL 文件同步 runtime 版本信息

    用于在加载 runtime 时确保 version 与 JSONL 对齐。
    """
    runtime = load_outline_runtime(runtime_file)
    last_id = get_last_adjustment_id(adjustments_file)

    if last_id and runtime.last_applied_adjustment_id != last_id:
        # 从 JSONL 读取最新一条记录获取版本信息
        adjustments = load_outline_adjustments(adjustments_file)
        if adjustments:
            latest = adjustments[-1]
            runtime.last_applied_adjustment_id = latest.adjustment_id
            runtime.window_version = latest.after_window.get("version", runtime.window_version)
            runtime.active_window_start = latest.after_window.get("start", runtime.active_window_start)
            runtime.active_window_end = latest.after_window.get("end", runtime.active_window_end)

    return runtime


# ============================================================================
# 初始化接口
# ============================================================================


def ensure_outline_runtime(project_root: Path) -> OutlineRuntime:
    """确保项目具备动态大纲运行层文件，返回运行时状态

    兼容新项目初始化与已有项目加载。
    """
    from .config import get_config

    config = get_config(project_root)
    config.ensure_dirs()

    runtime_file = config.outline_runtime_file
    adjustments_file = config.outline_adjustments_file

    # 如果 adjustment 文件存在，从 JSONL 同步版本
    if adjustments_file.exists():
        # 从 JSONL 同步后的 runtime（runtime_file 可能存在也可能不存在）
        runtime = sync_runtime_version_from_adjustments(runtime_file, adjustments_file)
        # 如果 runtime 文件不存在，保存同步后的版本
        if not runtime_file.exists():
            save_outline_runtime(runtime_file, runtime)
    else:
        # 新项目：创建默认状态
        runtime = OutlineRuntime()
        save_outline_runtime(runtime_file, runtime)

    return runtime
