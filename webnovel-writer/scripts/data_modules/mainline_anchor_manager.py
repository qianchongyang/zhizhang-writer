#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MainlineAnchorManager - 主线锚点与阶段承诺模型

从 总纲.md 和 第X卷-节拍表.md 中抽取主线锚点，
形成"阶段承诺"最小结构，用于动态调纲时的约束保护。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DataModulesConfig, get_config

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class PhaseCommitment:
    """
    阶段承诺结构 - 动态调纲时必须遵守的约束

    Attributes:
        anchor_id: 锚点唯一标识
        scope: 锚点范围 - book(全书) / volume(单卷) / window(活动窗口)
        must_reach: 必须达成的目标（允许动态调整路径，不允许改目标）
        must_not_break: 不可打破的约束（不允许任何漂移）
        target_chapter_range: 目标章节范围 [start, end]
        related_entities: 相关的实体列表（角色/物品/地点等）
        related_foreshadowing: 相关的伏笔ID列表
    """
    anchor_id: str
    scope: str  # "book" | "volume" | "window"
    must_reach: str
    must_not_break: List[str] = field(default_factory=list)
    target_chapter_range: tuple[int, int] = (0, 0)
    related_entities: List[str] = field(default_factory=list)
    related_foreshadowing: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "scope": self.scope,
            "must_reach": self.must_reach,
            "must_not_break": self.must_not_break,
            "target_chapter_range": list(self.target_chapter_range),
            "related_entities": self.related_entities,
            "related_foreshadowing": self.related_foreshadowing,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseCommitment":
        rng = data.get("target_chapter_range", [0, 0])
        if isinstance(rng, list) and len(rng) == 2:
            rng = tuple(rng)
        else:
            rng = (0, 0)
        return cls(
            anchor_id=data.get("anchor_id", ""),
            scope=data.get("scope", "window"),
            must_reach=data.get("must_reach", ""),
            must_not_break=data.get("must_not_break", []),
            target_chapter_range=rng,
            related_entities=data.get("related_entities", []),
            related_foreshadowing=data.get("related_foreshadowing", []),
        )


@dataclass
class AdjustmentDeclaration:
    """
    自动调纲时的声明结构 - 所有自动插入的副本或重排必须声明

    Attributes:
        mainline_service_reason: 该调整服务主线的原因
        return_to_mainline_by: 回归主线的目标章节
    """
    mainline_service_reason: str
    return_to_mainline_by: int  # 章节号

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mainline_service_reason": self.mainline_service_reason,
            "return_to_mainline_by": self.return_to_mainline_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdjustmentDeclaration":
        return cls(
            mainline_service_reason=data.get("mainline_service_reason", ""),
            return_to_mainline_by=data.get("return_to_mainline_by", 0),
        )


# =============================================================================
# MainlineAnchorManager
# =============================================================================

class MainlineAnchorManager:
    """
    主线锚点管理器

    职责：
    1. 从总纲.md 和 第X卷-节拍表.md 抽取主线锚点
    2. 维护锚点列表和阶段承诺
    3. 提供锚点查询接口
    4. 验证动态调纲是否遵守锚点约束
    """

    def __init__(self, config: Optional[DataModulesConfig] = None):
        self.config = config or get_config()
        self._book_anchors: List[PhaseCommitment] = []
        self._volume_anchors: Dict[int, List[PhaseCommitment]] = {}  # volume_id -> anchors
        self._window_anchors: List[PhaseCommitment] = []
        self._last_load_error: Optional[str] = None

    # -------------------------------------------------------------------------
    # Loading / Extraction
    # -------------------------------------------------------------------------

    def load_anchors(self) -> None:
        """
        从大纲文件加载所有锚点
        """
        self._book_anchors = []
        self._volume_anchors = {}
        self._window_anchors = []
        self._last_load_error = None

        # 1. 加载总纲锚点
        self._extract_book_anchors()

        # 2. 扫描所有卷节拍表并提取锚点
        self._extract_all_volume_anchors()

    def _extract_book_anchors(self) -> None:
        """从 总纲.md 提取全书锚点"""
        outline_dir = self.config.outline_dir
        zonggang_file = outline_dir / "总纲.md"

        if not zonggang_file.exists():
            logger.debug("总纲.md not found, skipping book anchors")
            return

        try:
            content = zonggang_file.read_text(encoding="utf-8")
            anchors = self._parse_book_anchors(content)
            self._book_anchors = anchors
            logger.info(f"Extracted {len(anchors)} book-level anchors from 总纲.md")
        except Exception as e:
            self._last_load_error = f"Failed to parse 总纲.md: {e}"
            logger.warning(self._last_load_error)

    def _parse_book_anchors(self, content: str) -> List[PhaseCommitment]:
        """
        解析总纲.md 内容，提取全书级锚点

        锚点来源：
        - 核心主线（主线目标、主要阻力）
        - 关键爽点里程碑
        - 伏笔表中的核心伏笔
        """
        anchors = []

        # 提取主线目标
        mainline_match = re.search(r"## 核心主线\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if mainline_match:
            mainline_section = mainline_match.group(1)
            goal_match = re.search(r"主线目标[：:]\s*(.+?)(?=\n|- |\Z)", mainline_section, re.DOTALL)
            resistance_match = re.search(r"主要阻力[：:]\s*(.+?)(?=\n|- |\Z)", mainline_section, re.DOTALL)

            if goal_match:
                anchors.append(PhaseCommitment(
                    anchor_id="book_mainline_goal",
                    scope="book",
                    must_reach=goal_match.group(1).strip(),
                    must_not_break=["不可偏离主线方向"],
                    target_chapter_range=(1, 9999),
                ))

        # 提取卷划分表，建立章节范围映射
        volume_ranges = self._extract_volume_ranges(content)

        # 提取主角成长线作为全书锚点
        growth_match = re.search(r"## 主角成长线\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if growth_match:
            growth_section = growth_match.group(1)
            start_match = re.search(r"起点状态[：:]\s*(.+)", growth_section)
            milestones_match = re.search(r"关键跃迁节点[：:]\s*(.+)", growth_section)
            endpoint_match = re.search(r"终局定位[：:]\s*(.+)", growth_section)

            milestones = []
            if milestones_match:
                milestones = [m.strip() for m in re.split(r"[、，,]", milestones_match.group(1)) if m.strip()]

            anchors.append(PhaseCommitment(
                anchor_id="book_growth_line",
                scope="book",
                must_reach=endpoint_match.group(1).strip() if endpoint_match else "完成成长",
                must_not_break=[
                    "主角核心性格不可改变",
                    "成长方向不可逆转",
                ],
                target_chapter_range=(1, 9999),
                related_entities=self._extract_entities_from_section(growth_section),
            ))

        # 提取关键爽点里程碑
        milestones_match = re.search(r"## 关键爽点里程碑\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if milestones_match:
            milestones_section = milestones_match.group(1)
            # 解析 "第X章：描述" 格式
            for ch_match in re.finditer(r"第(\d+)[章节][：:](.+)", milestones_section):
                chapter = int(ch_match.group(1))
                description = ch_match.group(2).strip()
                anchors.append(PhaseCommitment(
                    anchor_id=f"book_milestone_ch{chapter}",
                    scope="book",
                    must_reach=description,
                    target_chapter_range=(chapter, chapter),
                ))

        # 提取伏笔表中的核心伏笔
        foreshadow_match = re.search(r"## 伏笔表\s*\n\|.*?\n\|[-| ]+\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if foreshadow_match:
            foreshadow_section = foreshadow_match.group(1)
            for line in foreshadow_section.strip().split("\n"):
                if not line.strip() or line.startswith("|"):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4:
                    content_text, set_ch, reveal_ch, tier = parts[0], parts[1], parts[2], parts[3]
                    if tier in ["核心", "重要"]:
                        try:
                            reveal_chapter = int(reveal_ch) if reveal_ch.strip().isdigit() else None
                            if reveal_chapter:
                                anchors.append(PhaseCommitment(
                                    anchor_id=f"book_foreshadow_{set_ch.strip()}",
                                    scope="book",
                                    must_reach=f"伏笔回收：{content_text}",
                                    target_chapter_range=(reveal_chapter, reveal_chapter),
                                    related_foreshadowing=[content_text],
                                ))
                        except (ValueError, IndexError):
                            continue

        return anchors

    def _extract_volume_ranges(self, content: str) -> Dict[int, tuple[int, int]]:
        """从总纲中提取卷划分表，建立卷号到章节范围的映射"""
        ranges = {}
        table_match = re.search(r"## 卷划分\s*\n\|.*?\n\|[-| ]+\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if table_match:
            table_section = table_match.group(1)
            for line in table_section.strip().split("\n"):
                if not line.strip() or line.startswith("|"):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    try:
                        vol_num = int(parts[0])
                        ch_range = parts[2]  # like "1-50"
                        if "-" in ch_range:
                            start, end = ch_range.split("-")
                            ranges[vol_num] = (int(start.strip()), int(end.strip()))
                    except (ValueError, IndexError):
                        continue
        return ranges

    def _extract_all_volume_anchors(self) -> None:
        """扫描所有 第X卷-节拍表.md 文件并提取锚点"""
        outline_dir = self.config.outline_dir

        if not outline_dir.exists():
            return

        # 匹配卷节拍表文件
        for f in outline_dir.iterdir():
            if f.is_file() and re.match(r"第(\d+)卷-节拍表\.md", f.name):
                try:
                    content = f.read_text(encoding="utf-8")
                    vol_num = int(re.search(r"第(\d+)卷", f.name).group(1))
                    anchors = self._parse_volume_anchors(content, vol_num)
                    self._volume_anchors[vol_num] = anchors
                    logger.info(f"Extracted {len(anchors)} volume-level anchors from {f.name}")
                except Exception as e:
                    logger.warning(f"Failed to parse {f.name}: {e}")

    def _parse_volume_anchors(self, content: str, volume_num: int) -> List[PhaseCommitment]:
        """
        解析 第X卷-节拍表.md 内容，提取卷级锚点

        锚点来源：
        - 开卷承诺（Promise）
        - 催化事件（Catalyst）
        - 中段反转
        - 卷末最低谷（All Is Lost）
        - 卷末大兑现（Payoff）
        """
        anchors = []

        # 提取章节范围
        range_match = re.search(r"章节范围[：:]\s*第?\s*(\d+)\s*-?\s*第?\s*(\d+)\s*章", content)
        if range_match:
            start_ch = int(range_match.group(1))
            end_ch = int(range_match.group(2))
        else:
            start_ch, end_ch = 0, 0

        chapter_range = (start_ch, end_ch)

        # 提取核心冲突和卷末高潮
        conflict_match = re.search(r"核心冲突[：:]\s*(.+)", content)
        climix_match = re.search(r"卷末高潮[：:]\s*(.+)", content)

        # 1. 开卷承诺（Promise） - 必须达成的读者承诺
        promise_match = re.search(r"## \d+\) 开卷承诺（Promise\）(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if promise_match:
            promise_section = promise_match.group(1)
            reader_promise = re.search(r"本卷读者承诺[（(][^）)]*[）)][：:]\s*(.+)", promise_section)
            payoff_types = re.search(r"主要兑现类型[（(][^）)]*[）)][：:]\s*(.+)", promise_section)

            if reader_promise:
                anchors.append(PhaseCommitment(
                    anchor_id=f"vol{volume_num}_promise",
                    scope="volume",
                    must_reach=reader_promise.group(1).strip(),
                    must_not_break=["必须兑现开卷承诺的爽点/悬念/情绪"],
                    target_chapter_range=chapter_range,
                ))

        # 2. 催化事件（Catalyst）- 不可逆变化
        catalyst_match = re.search(r"## \d+\) 催化事件（Catalyst）(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if catalyst_match:
            catalyst_section = catalyst_match.group(1)
            irreversible_match = re.search(r"不可逆变化[：:]\s*(.+)", catalyst_section)

            if irreversible_match:
                anchors.append(PhaseCommitment(
                    anchor_id=f"vol{volume_num}_catalyst",
                    scope="volume",
                    must_reach=catalyst_section.strip().split("\n")[0],  # 事件本身
                    must_not_break=[f"不可逆变化：{irreversible_match.group(1).strip()}"],
                    target_chapter_range=chapter_range,
                ))

        # 3. 中段反转 - 不可打破的认知/代价约束
        reversal_match = re.search(r"## \d+\) 中段反转（必填）(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if reversal_match:
            reversal_section = reversal_match.group(1)
            new_cognition = re.search(r"反转带来的新认知/新代价[：:]\s*(.+)", reversal_section)

            if new_cognition and "无" not in new_cognition.group(1):
                anchors.append(PhaseCommitment(
                    anchor_id=f"vol{volume_num}_reversal",
                    scope="volume",
                    must_reach="中段反转必须发生",
                    must_not_break=[f"新认知/代价约束：{new_cognition.group(1).strip()}"],
                    target_chapter_range=chapter_range,
                ))

        # 4. 卷末最低谷（All Is Lost）
        allislost_match = re.search(r"## \d+\) 卷末最低谷（All Is Lost）(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if allislost_match:
            allislost_section = allislost_match.group(1)
            event_match = re.search(r"最低谷事件[：:]\s*(.+)", allislost_section)
            cost_match = re.search(r"代价[：:]\s*(.+)", allislost_section)

            if event_match:
                anchors.append(PhaseCommitment(
                    anchor_id=f"vol{volume_num}_allislost",
                    scope="volume",
                    must_reach=event_match.group(1).strip(),
                    must_not_break=[f"最低谷代价：{cost_match.group(1).strip()}"] if cost_match else [],
                    target_chapter_range=chapter_range,
                ))

        # 5. 卷末大兑现 + 新钩子（Payoff + Next Promise）
        payoff_match = re.search(r"## \d+\) 卷末大兑现 \+ 新钩子（Payoff \+ Next Promise）(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if payoff_match:
            payoff_section = payoff_match.group(1)
            payoff_items = re.search(r"本卷兑现[（(][^）)]*[）)][：:]\s*(.+)", payoff_section)
            next_hook = re.search(r"新钩子[（(][^）)]*[）)][：:]\s*(.+)", payoff_section)

            if payoff_items:
                anchors.append(PhaseCommitment(
                    anchor_id=f"vol{volume_num}_payoff",
                    scope="volume",
                    must_reach=payoff_items.group(1).strip(),
                    must_not_break=["卷末必须完成大兑现"],
                    target_chapter_range=chapter_range,
                ))

            if next_hook:
                anchors.append(PhaseCommitment(
                    anchor_id=f"vol{volume_num}_next_hook",
                    scope="volume",
                    must_reach=next_hook.group(1).strip(),
                    must_not_break=["必须设置有效钩子引导下一卷"],
                    target_chapter_range=chapter_range,
                ))

        # 6. 如果有核心冲突，也作为锚点
        if conflict_match:
            anchors.append(PhaseCommitment(
                anchor_id=f"vol{volume_num}_conflict",
                scope="volume",
                must_reach=conflict_match.group(1).strip(),
                target_chapter_range=chapter_range,
            ))

        return anchors

    def _extract_entities_from_section(self, section: str) -> List[str]:
        """从文本段落中简单提取实体（角色名等）"""
        entities = []
        # 简单策略：提取引号或书名号内的内容
        for match in re.finditer(r"《([^》]+)》|「([^」]+)」|『([^』]+)』", section):
            for group in match.groups():
                if group:
                    entities.append(group.strip())
        return entities

    # -------------------------------------------------------------------------
    # Query Interface
    # -------------------------------------------------------------------------

    def get_anchors_for_chapter(self, chapter: int, volume: Optional[int] = None) -> List[PhaseCommitment]:
        """
        获取指定章节适用的锚点

        Args:
            chapter: 章节号
            volume: 卷号（可选，如果不提供则搜索所有卷）

        Returns:
            适用的锚点列表（按 scope 优先级排序：book > volume > window）
        """
        result = []

        # 全书锚点一定适用
        for anchor in self._book_anchors:
            start, end = anchor.target_chapter_range
            if start <= chapter <= end or (start == 0 and end == 0):
                result.append(anchor)

        # 如果提供了卷号，只检查该卷
        if volume is not None:
            vol_anchors = self._volume_anchors.get(volume, [])
            for anchor in vol_anchors:
                start, end = anchor.target_chapter_range
                if start <= chapter <= end or (start == 0 and end == 0):
                    result.append(anchor)
        else:
            # 否则检查所有卷
            for vol_anchors in self._volume_anchors.values():
                for anchor in vol_anchors:
                    start, end = anchor.target_chapter_range
                    if start <= chapter <= end or (start == 0 and end == 0):
                        result.append(anchor)

        # 窗口锚点
        for anchor in self._window_anchors:
            start, end = anchor.target_chapter_range
            if start <= chapter <= end:
                result.append(anchor)

        return result

    def get_volume_anchors(self, volume: int) -> List[PhaseCommitment]:
        """获取指定卷的所有锚点"""
        return self._volume_anchors.get(volume, [])

    def get_book_anchors(self) -> List[PhaseCommitment]:
        """获取全书锚点"""
        return self._book_anchors

    def get_all_anchors(self) -> List[PhaseCommitment]:
        """获取所有锚点"""
        result = list(self._book_anchors)
        for vol_anchors in self._volume_anchors.values():
            result.extend(vol_anchors)
        result.extend(self._window_anchors)
        return result

    # -------------------------------------------------------------------------
    # Validation Interface
    # -------------------------------------------------------------------------

    def validate_adjustment(
        self,
        adjustment_type: str,
        affected_chapters: List[int],
        declaration: Optional[AdjustmentDeclaration] = None,
    ) -> tuple[bool, List[str]]:
        """
        验证动态调纲是否遵守锚点约束

        Args:
            adjustment_type: 调整类型（minor_reorder / insert_arc / window_extend / block_for_manual_review）
            affected_chapters: 受影响的章节列表
            declaration: 调整声明（如果无法提供声明，则不允许自动调纲）

        Returns:
            (is_valid, violation_reasons)
        """
        violations = []

        # 如果无法判断回归点，自动调纲必须降级为"只生成风险预警，不自动落盘"
        if declaration is None and adjustment_type in ("insert_arc", "window_extend"):
            return False, ["无法判断回归点：自动调纲必须降级为风险预警，不自动落盘"]

        if declaration is not None:
            # 检查回归点是否在锚点范围内
            if declaration.return_to_mainline_by > 0:
                for anchor in self.get_all_anchors():
                    start, end = anchor.target_chapter_range
                    if start <= declaration.return_to_mainline_by <= end:
                        # 回归点在锚点范围内，有效
                        pass
                    elif declaration.return_to_mainline_by > end:
                        violations.append(
                            f"回归点（第{declaration.return_to_mainline_by}章）超出锚点范围（第{start}-{end}章）"
                        )

        # 检查 must_not_break 约束是否被违反
        for chapter in affected_chapters:
            anchors = self.get_anchors_for_chapter(chapter)
            for anchor in anchors:
                for constraint in anchor.must_not_break:
                    if "不可" in constraint or "不允许" in constraint:
                        # 这里只是预警，实际约束由调纲引擎判断
                        pass

        return len(violations) == 0, violations

    def check_mainline_integrity(
        self,
        chapter: int,
        window_start: int,
        window_end: int,
    ) -> tuple[bool, List[str]]:
        """
        检查活动窗口是否偏离主线锚点

        Args:
            chapter: 当前章节号
            window_start: 窗口起始章节
            window_end: 窗口结束章节

        Returns:
            (is_integr, warning_messages)
        """
        warnings = []
        anchors = self.get_anchors_for_chapter(chapter)

        for anchor in anchors:
            # 检查是否有必须在特定章节达成的目标
            start, end = anchor.target_chapter_range
            if anchor.scope in ("book", "volume"):
                # 全书/卷锚点：确保窗口覆盖了目标章节
                if anchor.target_chapter_range != (0, 0):
                    if window_end < end:
                        warnings.append(
                            f"锚点 {anchor.anchor_id} 的目标章节（第{end}章）超出当前窗口范围"
                        )

        return len(warnings) == 0, warnings

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def get_anchor_snapshot(self) -> Dict[str, Any]:
        """获取锚点快照，用于持久化"""
        return {
            "book_anchors": [a.to_dict() for a in self._book_anchors],
            "volume_anchors": {
                str(vol): [a.to_dict() for a in anchors]
                for vol, anchors in self._volume_anchors.items()
            },
            "window_anchors": [a.to_dict() for a in self._window_anchors],
            "last_load_error": self._last_load_error,
        }

    def load_anchor_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """从快照加载锚点"""
        self._book_anchors = [
            PhaseCommitment.from_dict(a) for a in snapshot.get("book_anchors", [])
        ]
        self._volume_anchors = {
            int(vol): [PhaseCommitment.from_dict(a) for a in anchors]
            for vol, anchors in snapshot.get("volume_anchors", {}).items()
        }
        self._window_anchors = [
            PhaseCommitment.from_dict(a) for a in snapshot.get("window_anchors", [])
        ]
        self._last_load_error = snapshot.get("last_load_error")

    def add_window_anchor(self, anchor: PhaseCommitment) -> None:
        """添加窗口级锚点"""
        anchor.scope = "window"
        self._window_anchors.append(anchor)

    def clear_window_anchors(self) -> None:
        """清除所有窗口级锚点"""
        self._window_anchors = []

    @property
    def last_load_error(self) -> Optional[str]:
        """返回上次加载锚点时的错误信息"""
        return self._last_load_error


# =============================================================================
# Factory & Utilities
# =============================================================================

def create_mainline_anchor_manager(config: Optional[DataModulesConfig] = None) -> MainlineAnchorManager:
    """
    创建主线锚点管理器并加载锚点

    Args:
        config: 可选配置对象

    Returns:
        已加载锚点的 MainlineAnchorManager 实例
    """
    manager = MainlineAnchorManager(config)
    manager.load_anchors()
    return manager


def extract_anchors_from_outline_file(file_path: Path, config: Optional[DataModulesConfig] = None) -> List[PhaseCommitment]:
    """
    从指定大纲文件提取锚点

    Args:
        file_path: 大纲文件路径
        config: 可选配置对象，用于确定项目根目录

    Returns:
        提取的锚点列表
    """
    if not file_path.exists():
        return []

    content = file_path.read_text(encoding="utf-8")

    # 判断文件类型
    if "总纲" in file_path.name:
        manager = MainlineAnchorManager(config)
        return manager._parse_book_anchors(content)
    elif "节拍表" in file_path.name:
        vol_match = re.search(r"第(\d+)卷", file_path.name)
        volume_num = int(vol_match.group(1)) if vol_match else 0
        manager = MainlineAnchorManager(config)
        return manager._parse_volume_anchors(content, volume_num)

    return []
