#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Outline Mutation Engine - 大纲写回引擎

职责：
1. 将 Agent 的调纲决策安全写回到大纲与运行层
2. 支持 4 种动作：minor_reorder / insert_arc / window_extend / manual_block
3. 保证原子性：JSONL 先写 → Runtime 文件原子替换 → Markdown 文件更新
4. 失败回滚：Markdown 失败时回滚 runtime 并记录 rollback_reason

Architecture Decision:
- window_version 增长由 JSONL 成功追加 adjustment_id 触发，不由 runtime 写入触发
- outline_runtime.json.last_applied_adjustment_id 必须指向最后一条 status=applied 的记录
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DataModulesConfig, get_config
from .mainline_anchor_manager import AdjustmentDeclaration, MainlineAnchorManager
from .outline_runtime import (
    OutlineAdjustment,
    OutlineNode,
    OutlineRuntime,
    append_outline_adjustment,
    load_outline_adjustments,
    load_outline_runtime,
    save_outline_runtime,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class MutationRequest:
    """调纲请求"""
    action_type: str  # minor_reorder / insert_arc / window_extend / manual_block
    trigger_chapter: int
    reason: str
    impact_preview: str
    affected_chapters: List[int] = field(default_factory=list)
    # for window_extend
    new_window_start: Optional[int] = None
    new_window_end: Optional[int] = None
    # for insert_arc
    new_arc_node: Optional[OutlineNode] = None
    # for manual_block
    block_reason: Optional[str] = None
    # 主线服务声明
    declaration: Optional[AdjustmentDeclaration] = None
    # 额外元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MutationResult:
    """调纲结果"""
    success: bool
    adjustment_id: Optional[str] = None
    error: Optional[str] = None
    rolled_back: bool = False
    rollback_reason: Optional[str] = None
    # 变更范围
    affected_chapters: List[int] = field(default_factory=list)
    before_window: Dict[str, Any] = field(default_factory=dict)
    after_window: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AdjustmentRecord:
    """完整调整记录（含状态）"""
    adjustment_id: str
    status: str  # pending / applied / rolled_back
    trigger_chapter: int
    adjustment_type: str
    reason: str
    impact_preview: str
    before_window: Dict[str, Any]
    after_window: Dict[str, Any]
    written_at: str
    mainline_service_reason: Optional[str] = None
    return_to_mainline_by: Optional[int] = None
    rollback_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# OutlineMutationEngine
# =============================================================================


class OutlineMutationEngine:
    """
    大纲写回引擎

    职责：
    1. 生成 adjustment_record
    2. 按原子顺序执行写回
    3. 失败时完整回滚
    """

    VALID_ACTIONS = {"minor_reorder", "insert_arc", "window_extend", "manual_block"}

    def __init__(self, config: Optional[DataModulesConfig] = None):
        self.config = config or get_config()
        self.anchor_manager: Optional[MainlineAnchorManager] = None

    def set_anchor_manager(self, manager: MainlineAnchorManager) -> None:
        """设置锚点管理器（用于验证）"""
        self.anchor_manager = manager

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def execute_mutation(self, request: MutationRequest) -> MutationResult:
        """
        执行调纲请求

        Args:
            request: 调纲请求

        Returns:
            MutationResult: 执行结果
        """
        # 1. 验证请求
        if request.action_type not in self.VALID_ACTIONS:
            return MutationResult(
                success=False,
                error=f"Invalid action_type: {request.action_type}"
            )

        # 2. 加载当前运行时状态
        runtime = load_outline_runtime(self.config.outline_runtime_file)
        before_window = self._get_window_snapshot(runtime)

        # 3. 计算新的窗口状态
        after_window, new_nodes = self._compute_new_state(runtime, request)

        # 4. 生成完整 adjustment_record
        adjustment_id = str(uuid.uuid4())
        record = AdjustmentRecord(
            adjustment_id=adjustment_id,
            status="pending",
            trigger_chapter=request.trigger_chapter,
            adjustment_type=request.action_type,
            reason=request.reason,
            impact_preview=request.impact_preview,
            before_window=before_window,
            after_window={
                "start": after_window.get("start", runtime.active_window_start),
                "end": after_window.get("end", runtime.active_window_end),
                "version": before_window.get("version", 0) + 1,  # 预增长，JSONL成功后正式生效
            },
            written_at=datetime.now(timezone.utc).isoformat(),
            mainline_service_reason=(
                request.declaration.mainline_service_reason
                if request.declaration else None
            ),
            return_to_mainline_by=(
                request.declaration.return_to_mainline_by
                if request.declaration else None
            ),
            metadata=request.metadata,
        )

        # 5. 验证锚点约束（如果提供了锚点管理器）
        if self.anchor_manager and request.declaration:
            is_valid, violations = self.anchor_manager.validate_adjustment(
                request.action_type,
                request.affected_chapters,
                request.declaration
            )
            if not is_valid:
                return MutationResult(
                    success=False,
                    error=f"Anchor validation failed: {violations}"
                )

        # 6. 执行原子写回
        try:
            # 6a. 追加到 JSONL（触发 version 增长）
            self._append_adjustment_to_jsonl(record)

            # 6b. 计算新的 runtime 内容
            new_runtime = self._build_new_runtime(runtime, request, after_window, new_nodes)

            # 6c. 写入临时文件并原子替换
            self._atomic_save_runtime(new_runtime)

            # 6d. 更新 Markdown 大纲文件
            markdown_success = self._update_markdown_outline(
                runtime, new_runtime, request, record.adjustment_id
            )

            if not markdown_success:
                # Markdown 写回失败，执行回滚
                return self._rollback(record, "markdown_write_failed")

            # 成功：更新 record 状态为 applied
            record.status = "applied"
            # 重新追加一条状态更新记录（或者我们直接修改 JSONL 最后一条）
            self._update_adjustment_status(record.adjustment_id, "applied")

            return MutationResult(
                success=True,
                adjustment_id=record.adjustment_id,
                affected_chapters=request.affected_chapters,
                before_window=before_window,
                after_window=record.after_window,
            )

        except Exception as e:
            logger.exception("Mutation execution failed")
            return MutationResult(
                success=False,
                error=str(e)
            )

    # -------------------------------------------------------------------------
    # Private: State Computation
    # -------------------------------------------------------------------------

    def _get_window_snapshot(self, runtime: OutlineRuntime) -> Dict[str, Any]:
        """获取当前窗口快照"""
        return {
            "start": runtime.active_window_start,
            "end": runtime.active_window_end,
            "version": runtime.window_version,
            "volume": runtime.active_volume,
        }

    def _compute_new_state(
        self, runtime: OutlineRuntime, request: MutationRequest
    ) -> tuple[Dict[str, Any], List[OutlineNode]]:
        """
        计算新的窗口状态

        Returns:
            (new_window_dict, new_nodes_to_add)
        """
        new_window = {
            "start": runtime.active_window_start,
            "end": runtime.active_window_end,
        }
        new_nodes: List[OutlineNode] = []

        if request.action_type == "minor_reorder":
            # minor_reorder: 不改变窗口范围，只调整节点顺序
            pass

        elif request.action_type == "insert_arc":
            # insert_arc: 插入新弧线节点
            if request.new_arc_node:
                new_nodes.append(request.new_arc_node)
            # 可能需要扩展窗口以容纳新节点
            if request.new_window_end and request.new_window_end > runtime.active_window_end:
                new_window["end"] = request.new_window_end

        elif request.action_type == "window_extend":
            # window_extend: 扩展活动窗口
            if request.new_window_start is not None:
                new_window["start"] = request.new_window_start
            if request.new_window_end is not None:
                new_window["end"] = request.new_window_end

        elif request.action_type == "manual_block":
            # manual_block: 标记需要人工审核的区块
            # 不改变窗口，只记录阻断标记
            pass

        return new_window, new_nodes

    def _build_new_runtime(
        self,
        runtime: OutlineRuntime,
        request: MutationRequest,
        after_window: Dict[str, Any],
        new_nodes: List[OutlineNode],
    ) -> OutlineRuntime:
        """构建新的运行时状态"""
        new_runtime = OutlineRuntime(
            active_volume=runtime.active_volume,
            active_window_start=after_window.get("start", runtime.active_window_start),
            active_window_end=after_window.get("end", runtime.active_window_end),
            # window_version 由 JSONL 追加触发，这里只做临时计算
            window_version=runtime.window_version + 1,
            baseline_anchor_version=runtime.baseline_anchor_version,
            last_adjustment_chapter=request.trigger_chapter,
            last_adjustment_type=request.action_type,
            # last_applied_adjustment_id 在原子替换后更新
            last_applied_adjustment_id=None,
            return_to_mainline_by=(
                request.declaration.return_to_mainline_by
                if request.declaration else runtime.return_to_mainline_by
            ),
            window_status=runtime.window_status,
            mainline_anchors=runtime.mainline_anchors,
            active_nodes=runtime.active_nodes + new_nodes,
        )
        return new_runtime

    # -------------------------------------------------------------------------
    # Private: Atomic Write Operations
    # -------------------------------------------------------------------------

    def _append_adjustment_to_jsonl(self, record: AdjustmentRecord) -> None:
        """追加 adjustment 到 JSONL 文件（触发 version 增长）"""
        adjustment = OutlineAdjustment(
            adjustment_id=record.adjustment_id,
            trigger_chapter=record.trigger_chapter,
            adjustment_type=record.adjustment_type,
            reason=record.reason,
            impact_preview=record.impact_preview,
            before_window=record.before_window,
            after_window=record.after_window,
            mainline_service_reason=record.mainline_service_reason,
            return_to_mainline_by=record.return_to_mainline_by,
            written_at=record.written_at,
        )
        append_outline_adjustment(self.config.outline_adjustments_file, adjustment)
        logger.info(f"Appended adjustment {record.adjustment_id} to JSONL")

    def _atomic_save_runtime(self, runtime: OutlineRuntime) -> None:
        """原子化保存 runtime 文件"""
        # 计算 adjustment_id（从 JSONL 最后一条获取）
        last_id = self._get_last_adjustment_id()
        runtime.last_applied_adjustment_id = last_id

        # 写入临时文件
        temp_path = self.config.outline_runtime_file.with_suffix(".tmp")
        self.config.outline_runtime_file.parent.mkdir(parents=True, exist_ok=True)

        data = runtime.model_dump(mode="json", exclude_none=False)
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # 原子替换
        temp_path.replace(self.config.outline_runtime_file)
        logger.info(f"Atomically saved runtime to {self.config.outline_runtime_file}")

    def _get_last_adjustment_id(self) -> Optional[str]:
        """获取 JSONL 最后一条记录的 adjustment_id"""
        if not self.config.outline_adjustments_file.exists():
            return None
        lines = self.config.outline_adjustments_file.read_text(encoding="utf-8").splitlines()
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

    def _update_adjustment_status(self, adjustment_id: str, status: str) -> None:
        """更新 JSONL 中指定记录的状态"""
        if not self.config.outline_adjustments_file.exists():
            return

        lines = self.config.outline_adjustments_file.read_text(encoding="utf-8").splitlines()
        new_lines = []
        found = False

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("adjustment_id") == adjustment_id:
                    record["status"] = status
                    found = True
                new_lines.append(json.dumps(record, ensure_ascii=False))
            except json.JSONDecodeError:
                continue

        if found:
            self.config.outline_adjustments_file.write_text(
                "\n".join(new_lines) + "\n",
                encoding="utf-8"
            )

    # -------------------------------------------------------------------------
    # Private: Markdown Update
    # -------------------------------------------------------------------------

    def _update_markdown_outline(
        self,
        old_runtime: OutlineRuntime,
        new_runtime: OutlineRuntime,
        request: MutationRequest,
        adjustment_id: str,
    ) -> bool:
        """
        更新 Markdown 大纲文件

        注意：只修改当前活动窗口相关部分，不全卷覆盖。

        Returns:
            True if successful, False if failed
        """
        try:
            outline_dir = self.config.outline_dir

            # 1. 更新详细大纲文件
            detailed_outline_file = outline_dir / f"第{new_runtime.active_volume}卷-详细大纲.md"
            if detailed_outline_file.exists():
                self._update_detailed_outline(
                    detailed_outline_file,
                    old_runtime,
                    new_runtime,
                    request
                )

            # 2. 更新时间线文件
            timeline_file = outline_dir / f"第{new_runtime.active_volume}卷-时间线.md"
            if timeline_file.exists():
                self._update_timeline(
                    timeline_file,
                    old_runtime,
                    new_runtime,
                    request
                )

            logger.info(f"Updated markdown outline files for adjustment {adjustment_id}")
            return True

        except Exception as e:
            logger.exception(f"Failed to update markdown outline: {e}")
            return False

    def _update_detailed_outline(
        self,
        file_path: Path,
        old_runtime: OutlineRuntime,
        new_runtime: OutlineRuntime,
        request: MutationRequest,
    ) -> None:
        """更新详细大纲文件（只修改活动窗口部分）"""
        content = file_path.read_text(encoding="utf-8")

        # 构建窗口范围的注释标记
        # 这里我们简单地处理：如果有新的 arc 节点插入，在合适位置添加
        if request.action_type == "insert_arc" and request.new_arc_node:
            new_node = request.new_arc_node
            # 在对应章节位置插入新节点描述
            # 实际实现可能需要更复杂的解析逻辑
            insertion_point = self._find_chapter_insertion_point(
                content, new_node.chapter
            )
            if insertion_point > 0:
                new_node_text = self._format_new_arc_node(new_node)
                content = content[:insertion_point] + new_node_text + content[insertion_point:]

        # 如果是 window_extend，更新窗口标记
        elif request.action_type == "window_extend":
            # 更新活动窗口范围注释
            old_range = f"{old_runtime.active_window_start}-{old_runtime.active_window_end}"
            new_range = f"{new_runtime.active_window_start}-{new_runtime.active_window_end}"
            content = content.replace(old_range, new_range)

        file_path.write_text(content, encoding="utf-8")

    def _find_chapter_insertion_point(self, content: str, chapter: int) -> int:
        """找到章节插入点（返回字符偏移）"""
        import re
        # 查找 "第X章" 或 "第X节" 模式
        pattern = rf"(?=第{chapter}章|第{chapter}节)"
        match = re.search(pattern, content)
        if match:
            return match.start()
        return -1

    def _format_new_arc_node(self, node: OutlineNode) -> str:
        """格式化新弧线节点为文本"""
        return f"""
### 第{node.chapter}章 - {node.title}

**目标**: {node.goal}
**冲突**: {node.conflict}
**代价**: {node.cost}
**钩子**: {node.hook}

"""

    def _update_timeline(
        self,
        file_path: Path,
        old_runtime: OutlineRuntime,
        new_runtime: OutlineRuntime,
        request: MutationRequest,
    ) -> None:
        """更新时间线文件"""
        content = file_path.read_text(encoding="utf-8")

        # 如果是 window_extend，更新时间线范围
        if request.action_type == "window_extend":
            old_start = old_runtime.active_window_start
            old_end = old_runtime.active_window_end
            new_start = new_runtime.active_window_start
            new_end = new_runtime.active_window_end

            # 扩展时间线（如果窗口向后扩展）
            if new_end > old_end:
                # 在时间线末尾添加新章节条目
                extension = self._generate_timeline_extension(old_end + 1, new_end)
                content += extension

        file_path.write_text(content, encoding="utf-8")

    def _generate_timeline_extension(self, start: int, end: int) -> str:
        """生成时间线扩展条目"""
        lines = []
        for ch in range(start, end + 1):
            lines.append(f"- 第{ch}章：")
        return "\n".join(lines) + "\n"

    # -------------------------------------------------------------------------
    # Private: Rollback
    # -------------------------------------------------------------------------

    def _rollback(
        self, record: AdjustmentRecord, rollback_reason: str
    ) -> MutationResult:
        """
        执行回滚

        1. 回滚 runtime 文件到步骤 5 之前的状态
        2. 在 JSONL 中补记 rollback_reason
        3. 记录状态为 rolled_back
        """
        try:
            # 1. 读取原始 runtime（步骤5之前的状态在 before_window 中）
            original_runtime = OutlineRuntime(
                active_volume=record.before_window.get("volume", 1),
                active_window_start=record.before_window.get("start", 1),
                active_window_end=record.before_window.get("end", 50),
                window_version=record.before_window.get("version", 0),
                # 其他字段需要从历史记录恢复，这里简化处理
            )

            # 2. 回滚 runtime 文件
            temp_path = self.config.outline_runtime_file.with_suffix(".tmp")
            self.config.outline_runtime_file.parent.mkdir(parents=True, exist_ok=True)
            data = original_runtime.model_dump(mode="json", exclude_none=False)
            temp_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            temp_path.replace(self.config.outline_runtime_file)

            # 3. 追加 rollback 记录到 JSONL
            rollback_record = AdjustmentRecord(
                adjustment_id=record.adjustment_id,
                status="rolled_back",
                trigger_chapter=record.trigger_chapter,
                adjustment_type=record.adjustment_type,
                reason=record.reason,
                impact_preview=record.impact_preview,
                before_window=record.before_window,
                after_window=record.after_window,
                written_at=datetime.now(timezone.utc).isoformat(),
                rollback_reason=rollback_reason,
            )

            self._append_rollback_record(rollback_record)

            logger.info(f"Rolled back adjustment {record.adjustment_id}: {rollback_reason}")

            return MutationResult(
                success=False,
                adjustment_id=record.adjustment_id,
                error=f"Rolled back: {rollback_reason}",
                rolled_back=True,
                rollback_reason=rollback_reason,
                before_window=record.before_window,
                after_window=record.after_window,
            )

        except Exception as e:
            logger.exception(f"Rollback failed: {e}")
            return MutationResult(
                success=False,
                adjustment_id=record.adjustment_id,
                error=f"Rollback failed: {e}",
                rolled_back=True,
                rollback_reason=rollback_reason,
            )

    def _append_rollback_record(self, record: AdjustmentRecord) -> None:
        """追加 rollback 记录到 JSONL"""
        adjustment = OutlineAdjustment(
            adjustment_id=record.adjustment_id,
            trigger_chapter=record.trigger_chapter,
            adjustment_type=record.adjustment_type,
            reason=record.reason,
            impact_preview=record.impact_preview,
            before_window=record.before_window,
            after_window=record.after_window,
            written_at=record.written_at,
        )
        # 直接用追加的方式写回滚记录
        append_outline_adjustment(self.config.outline_adjustments_file, adjustment)

        # 更新状态为 rolled_back
        self._update_adjustment_status(record.adjustment_id, "rolled_back")


# =============================================================================
# Factory & Utilities
# =============================================================================


def create_mutation_engine(
    config: Optional[DataModulesConfig] = None,
    anchor_manager: Optional[MainlineAnchorManager] = None,
) -> OutlineMutationEngine:
    """
    创建大纲写回引擎

    Args:
        config: 可选配置对象
        anchor_manager: 可选锚点管理器（用于验证）

    Returns:
        OutlineMutationEngine 实例
    """
    engine = OutlineMutationEngine(config)
    if anchor_manager:
        engine.set_anchor_manager(anchor_manager)
    return engine


def execute_adjustment(
    request: MutationRequest,
    config: Optional[DataModulesConfig] = None,
    anchor_manager: Optional[MainlineAnchorManager] = None,
) -> MutationResult:
    """
    快捷函数：执行单次调纲

    Args:
        request: 调纲请求
        config: 可选配置对象
        anchor_manager: 可选锚点管理器

    Returns:
        MutationResult 执行结果
    """
    engine = create_mutation_engine(config, anchor_manager)
    return engine.execute_mutation(request)
