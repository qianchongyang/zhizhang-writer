#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutlineImpactAnalyzer - 影响范围分析器

在真正修改后续活动窗口前，先分析影响范围，避免黑盒自动改纲。

职责：
1. 读取当前章正文结果、chapter_meta、review_summary
2. 读取最近摘要、活动窗口节点、主线锚点、真相层状态
3. 输出结构化 impact_preview

影响分析关注：
- 当前章结果是否与后续章节预设冲突
- 当前章是否生成了需要完整展开的副本段
- 是否存在关系跃迁过快、承诺太大、节奏过硬压缩
- 是否存在前置条件不满足的问题

Architecture Decision:
- Python 负责归并已有事实和结构对象
- "是否真的要调"由规则 + Agent 混合判断（Python 归并冲突信号，Agent 解释是否值得改纲）
- 先不引入完整因果图，只做"轻量依赖 + 真相层比对"
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .config import DataModulesConfig, get_config
from .outline_runtime import (
    OutlineRuntime,
    OutlineNode,
    NodeDependency,
    load_outline_runtime,
)
from .mainline_anchor_manager import MainlineAnchorManager, PhaseCommitment

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class ImpactPreview:
    """
    影响预览结构 - 动态调纲决策的前置分析结果

    Attributes:
        needs_adjustment: 是否需要调整大纲
        adjustment_type: 调整类型
            - none: 不需要调整
            - minor_reorder: 轻微重排（不影响窗口范围）
            - insert_arc: 插入弧线（需要扩展窗口）
            - window_extend: 窗口扩展
            - block_for_manual_review: 阻塞，需人工审查
        reason: 调整原因摘要
        affected_chapters: 受影响的章节列表
        affected_entities: 受影响的实体列表
        affected_foreshadowing: 受影响的伏笔列表
        timeline_risk: 时间线风险描述
        mainline_risk: 主线风险描述
        recommended_return_to_mainline_by: 推荐回归主线的章节号（可选）
        conflict_signals: 冲突信号列表（用于 Agent 决策）
        prerequisite_gaps: 前置条件缺口列表
        relationship_jump_signals: 关系跃迁信号列表
        copy_segment_signals: 副本段信号列表
    """
    needs_adjustment: bool = False
    adjustment_type: str = "none"  # none / minor_reorder / insert_arc / window_extend / block_for_manual_review
    reason: str = ""
    affected_chapters: List[int] = field(default_factory=list)
    affected_entities: List[str] = field(default_factory=list)
    affected_foreshadowing: List[str] = field(default_factory=list)
    timeline_risk: str = ""
    mainline_risk: str = ""
    recommended_return_to_mainline_by: Optional[int] = None
    conflict_signals: List[str] = field(default_factory=list)
    prerequisite_gaps: List[str] = field(default_factory=list)
    relationship_jump_signals: List[str] = field(default_factory=list)
    copy_segment_signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "needs_adjustment": self.needs_adjustment,
            "adjustment_type": self.adjustment_type,
            "reason": self.reason,
            "affected_chapters": self.affected_chapters,
            "affected_entities": self.affected_entities,
            "affected_foreshadowing": self.affected_foreshadowing,
            "timeline_risk": self.timeline_risk,
            "mainline_risk": self.mainline_risk,
            "recommended_return_to_mainline_by": self.recommended_return_to_mainline_by,
            "conflict_signals": self.conflict_signals,
            "prerequisite_gaps": self.prerequisite_gaps,
            "relationship_jump_signals": self.relationship_jump_signals,
            "copy_segment_signals": self.copy_segment_signals,
        }


# ============================================================================
# 分析规则常量
# ============================================================================

# 关系跃迁风险阈值：超过此数量的关系变化认为是"跃迁"
RELATIONSHIP_JUMP_THRESHOLD = 2

# 承诺过大风险关键词
COMMITMENT_OVERLOAD_KEYWORDS = [
    "必须", "一定", "绝对", "无条件", "无论如何",
    "代价", "交换", "誓约", "契约", "永生",
]

# 节奏压缩风险：单章内超过此数量的目标变化
PACING_COMPRESSION_THRESHOLD = 3

# 主线偏离风险信号关键词
MAINLINE_DEVIATION_KEYWORDS = [
    "偏离", "背离", "绕道", "拖延", "搁置",
    "推迟", "延后", "暂停", "搁置",
]

# 副本段信号关键词
COPY_SEGMENT_KEYWORDS = [
    "副本", "支线", "番外", "独立事件", "单独故事",
    "分支剧情", "另外的故事", "另一边",
]

# 时间线矛盾信号
TIMELINE_CONTRADICTION_KEYWORDS = [
    "前一天", "后一天", "时间不对", "顺序错误",
    "矛盾", "不一致", "冲突",
]


# ============================================================================
# OutlineImpactAnalyzer
# ============================================================================


class OutlineImpactAnalyzer:
    """
    影响范围分析器

    职责：
    1. 归并当前章结果、真相层状态、活动窗口、主线锚点
    2. 检测冲突信号、前置条件缺口、关系跃迁、副本段
    3. 输出结构化 impact_preview 供 Agent 决策
    """

    def __init__(self, config: Optional[DataModulesConfig] = None):
        self.config = config or get_config()
        self._state: Dict[str, Any] = {}
        self._story_memory: Dict[str, Any] = {}
        self._outline_runtime: Optional[OutlineRuntime] = None
        self._mainline_anchors: List[PhaseCommitment] = []
        self._recent_summaries: List[Dict[str, Any]] = []
        self._chapter_meta: Dict[str, Any] = {}
        self._review_summary: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Input Setters
    # -------------------------------------------------------------------------

    def set_chapter_result(self, chapter: int, chapter_result: Dict[str, Any]) -> None:
        """
        设置当前章节结果

        Args:
            chapter: 章节号
            chapter_result: 章节结果，包含:
                - text: 正文文本
                - entities_appeared: 出场实体
                - state_changes: 状态变化
                - relationships_new: 新关系
                - chapter_meta: 章节元数据
        """
        self._current_chapter = chapter
        self._chapter_result = chapter_result
        self._chapter_meta = chapter_result.get("chapter_meta", {})

    def set_review_summary(self, review_summary: Dict[str, Any]) -> None:
        """设置章节审查总结"""
        self._review_summary = review_summary

    def set_recent_summaries(self, summaries: List[Dict[str, Any]]) -> None:
        """
        设置最近章节摘要

        Args:
            summaries: 最近章节摘要列表，每项包含 chapter 和 summary
        """
        self._recent_summaries = summaries

    def set_outline_runtime(self, runtime: OutlineRuntime) -> None:
        """设置活动窗口运行时状态"""
        self._outline_runtime = runtime

    def set_mainline_anchors(self, anchors: List[PhaseCommitment]) -> None:
        """设置主线锚点列表"""
        self._mainline_anchors = anchors

    def set_state(self, state: Dict[str, Any]) -> None:
        """设置真相层状态（state.json）"""
        self._state = state

    def set_story_memory(self, story_memory: Dict[str, Any]) -> None:
        """设置故事记忆层"""
        self._story_memory = story_memory

    # -------------------------------------------------------------------------
    # Analysis Methods
    # -------------------------------------------------------------------------

    def analyze(self) -> ImpactPreview:
        """
        执行完整影响分析

        Returns:
            ImpactPreview: 结构化影响预览
        """
        if not hasattr(self, "_chapter_result"):
            return ImpactPreview(reason="未设置章节结果，无法分析")

        # 1. 检测冲突信号
        conflict_signals = self._detect_conflict_signals()

        # 2. 检测关系跃迁
        relationship_jump_signals = self._detect_relationship_jumps()

        # 3. 检测副本段信号
        copy_segment_signals = self._detect_copy_segments()

        # 4. 检测前置条件缺口
        prerequisite_gaps = self._detect_prerequisite_gaps()

        # 5. 检测承诺过大
        commitment_overload_signals = self._detect_commitment_overload()

        # 6. 检测时间线风险
        timeline_risk = self._detect_timeline_risk()

        # 7. 检测主线偏离风险
        mainline_risk = self._detect_mainline_risk()

        # 8. 收集受影响章节
        affected_chapters = self._collect_affected_chapters()

        # 9. 收集受影响实体
        affected_entities = self._collect_affected_entities()

        # 10. 收集受影响伏笔
        affected_foreshadowing = self._collect_affected_foreshadowing()

        # 11. 计算推荐回归主线章节
        recommended_return = self._compute_recommended_return()

        # 12. 综合判断调整类型
        adjustment_type, reason = self._determine_adjustment_type(
            conflict_signals=conflict_signals,
            relationship_jump_signals=relationship_jump_signals,
            copy_segment_signals=copy_segment_signals,
            prerequisite_gaps=prerequisite_gaps,
            commitment_overload_signals=commitment_overload_signals,
            timeline_risk=timeline_risk,
            mainline_risk=mainline_risk,
        )

        needs_adjustment = adjustment_type != "none"

        return ImpactPreview(
            needs_adjustment=needs_adjustment,
            adjustment_type=adjustment_type,
            reason=reason,
            affected_chapters=affected_chapters,
            affected_entities=affected_entities,
            affected_foreshadowing=affected_foreshadowing,
            timeline_risk=timeline_risk,
            mainline_risk=mainline_risk,
            recommended_return_to_mainline_by=recommended_return,
            conflict_signals=conflict_signals,
            prerequisite_gaps=prerequisite_gaps,
            relationship_jump_signals=relationship_jump_signals,
            copy_segment_signals=copy_segment_signals,
        )

    def _detect_conflict_signals(self) -> List[str]:
        """
        检测当前章结果是否与后续章节预设冲突

        Returns:
            冲突信号列表
        """
        signals = []
        chapter_text = self._chapter_result.get("text", "")
        chapter_goal = self._chapter_meta.get("goal", "")

        if not chapter_text:
            return signals

        # 检查当前章目标是否与窗口内后续节点预设冲突
        if self._outline_runtime:
            for node in (self._outline_runtime.active_nodes or []):
                if node.chapter <= self._current_chapter:
                    continue

                # 检测目标冲突
                node_goal = getattr(node, "goal", "") or ""
                if node_goal and chapter_goal:
                    if self._is_goal_conflict(chapter_goal, node_goal):
                        signals.append(
                            f"目标冲突: 本章目标『{chapter_goal[:20]}』与第{node.chapter}章目标『{node_goal[:20]}』可能冲突"
                        )

                # 检测依赖未满足
                deps = getattr(node, "dependencies", None)
                if deps and isinstance(deps, NodeDependency):
                    prior = deps.prior_chapter
                    if prior and prior >= self._current_chapter:
                        signals.append(
                            f"前置未满足: 第{node.chapter}章依赖第{prior}章，但当前为第{self._current_chapter}章"
                        )

        # 检测 state_changes 与已有状态的冲突
        state_changes = self._chapter_result.get("state_changes", []) or []
        for change in state_changes:
            entity_id = change.get("entity_id", "")
            field = change.get("field", "")
            new_value = change.get("new", change.get("new_value", ""))

            # 检测真实性冲突（通过 story_memory 比对）
            conflict = self._check_state_conflict(entity_id, field, new_value)
            if conflict:
                signals.append(conflict)

        return signals

    def _is_goal_conflict(self, goal1: str, goal2: str) -> bool:
        """检测两个目标是否冲突（简单字符串匹配）"""
        goal1_lower = goal1.lower()
        goal2_lower = goal2.lower()

        # 互斥关键词检测
        # 冲突检测：如果 kw1 出现在 goal1 且 kw2 出现在 goal2（或反之），则为冲突
        mutex_pairs = [
            ("战斗", "和解"),
            ("攻击", "逃跑"),
            ("攻击", "和解"),  # 攻击 vs 和解
            ("杀死", "拯救"),
            ("破坏", "保护"),
            ("分离", "团聚"),
        ]
        for kw1, kw2 in mutex_pairs:
            # kw1 in goal1, kw2 in goal2 -> 冲突
            if kw1 in goal1_lower and kw2 in goal2_lower:
                return True
            # kw2 in goal1, kw1 in goal2 -> 冲突
            if kw2 in goal1_lower and kw1 in goal2_lower:
                return True

        return False

    def _check_state_conflict(self, entity_id: str, field: str, new_value: Any) -> Optional[str]:
        """检查状态变化是否与已有状态冲突"""
        if not entity_id or not field:
            return None

        # 从 story_memory 中查找实体历史状态
        characters = self._story_memory.get("characters", {})
        if entity_id in characters:
            entity_data = characters[entity_id]
            current_state = str(entity_data.get("current_state", ""))
            if current_state and new_value:
                # 简单检测：如果新值明显与当前状态矛盾
                if str(new_value) in current_state and current_state != str(new_value):
                    return None  # 正常的状态更新

        return None

    def _detect_relationship_jumps(self) -> List[str]:
        """
        检测关系跃迁是否过快

        Returns:
            关系跃迁信号列表
        """
        signals = []

        new_relationships = self._chapter_result.get("relationships_new", []) or []
        if not new_relationships:
            return signals

        # 统计本章新关系数量
        rel_count = len(new_relationships)
        if rel_count >= RELATIONSHIP_JUMP_THRESHOLD:
            rel_types = [r.get("type", "") for r in new_relationships]
            signals.append(
                f"关系跃迁过快: 本章新增 {rel_count} 条关系，类型包括 {'/'.join(rel_types[:3])}"
            )

        # 检测关系类型突变
        for rel in new_relationships:
            rel_type = rel.get("type", "")
            from_entity = rel.get("from", "") or rel.get("from_entity", "")
            to_entity = rel.get("to", "") or rel.get("to_entity", "")

            # 突变关系类型检测
            jump_types = ["敌对→友好", "陌生→亲密", "仇恨→爱慕"]
            if any(jump in rel_type for jump in jump_types):
                signals.append(
                    f"关系类型突变: {from_entity}→{to_entity} 关系变为『{rel_type}』"
                )

        return signals

    def _detect_copy_segments(self) -> List[str]:
        """
        检测当前章是否生成了需要完整展开的副本段

        Returns:
            副本段信号列表
        """
        signals = []
        chapter_text = self._chapter_result.get("text", "")

        if not chapter_text:
            return signals

        text_lower = chapter_text.lower()

        # 检测副本段关键词
        for keyword in COPY_SEGMENT_KEYWORDS:
            if keyword in text_lower:
                # 提取包含关键词的句子
                sentences = re.split(r'[。！？\n]', chapter_text)
                for sent in sentences:
                    if keyword in sent.lower():
                        signals.append(f"潜在副本段: 关键词『{keyword}』出现在『{sent[:30]}』")
                        break

        # 检测是否出现"另一边"、"与此同时"等并列叙事信号
        parallel_markers = ["另一边", "与此同时", "另外一边", "镜头一转", "视角转换"]
        for marker in parallel_markers:
            if marker in chapter_text:
                signals.append(f"并列叙事: 检测到『{marker}』，可能开启副本段")

        return signals

    def _detect_prerequisite_gaps(self) -> List[str]:
        """
        检测是否存在前置条件不满足的问题

        Returns:
            前置条件缺口列表
        """
        signals = []

        # 从 outline_runtime 检测窗口内节点的前置依赖
        if self._outline_runtime:
            for node in (self._outline_runtime.active_nodes or []):
                if node.chapter != self._current_chapter:
                    continue

                deps = getattr(node, "dependencies", None)
                if deps and isinstance(deps, NodeDependency):
                    # 检查角色状态依赖
                    if deps.character_state:
                        if not self._check_character_state_exists(deps.character_state):
                            signals.append(
                                f"角色状态前置未满足: 需要『{deps.character_state}』"
                            )

                    # 检查物品状态依赖
                    if deps.item_state:
                        if not self._check_item_state_exists(deps.item_state):
                            signals.append(
                                f"物品状态前置未满足: 需要『{deps.item_state}』"
                            )

                    # 检查关系状态依赖
                    if deps.relationship_state:
                        if not self._check_relationship_exists(deps.relationship_state):
                            signals.append(
                                f"关系状态前置未满足: 需要『{deps.relationship_state}』"
                            )

                    # 检查伏笔依赖
                    if deps.foreshadowing:
                        if not self._check_foreshadowing_exists(deps.foreshadowing):
                            signals.append(
                                f"伏笔前置未满足: 需要伏笔『{deps.foreshadowing}』已埋设"
                            )

                    # 检查章节依赖
                    if deps.prior_chapter:
                        if deps.prior_chapter > self._current_chapter:
                            signals.append(
                                f"章节前置未满足: 需要第{deps.prior_chapter}章已完成"
                            )

        return signals

    def _check_character_state_exists(self, state_ref: str) -> bool:
        """检查角色状态引用是否存在"""
        if not state_ref:
            return True
        characters = self._story_memory.get("characters", {})
        for name, data in characters.items():
            current = str(data.get("current_state", ""))
            if state_ref in current:
                return True
        return False

    def _check_item_state_exists(self, item_ref: str) -> bool:
        """检查物品状态引用是否存在"""
        if not item_ref:
            return True
        item_states = self._state.get("item_states", {})
        for item_id, state_data in item_states.items():
            if item_ref == item_id or item_ref in str(state_data):
                return True
        return False

    def _check_relationship_exists(self, rel_ref: str) -> bool:
        """检查关系状态引用是否存在"""
        if not rel_ref:
            return True
        structured_rels = self._state.get("structured_relationships", [])
        for rel in structured_rels:
            rel_desc = f"{rel.get('from_entity', '')}-{rel.get('type', '')}-{rel.get('to_entity', '')}"
            if rel_ref in rel_desc:
                return True
        return False

    def _check_foreshadowing_exists(self, foreshadow_ref: str) -> bool:
        """检查伏笔引用是否存在"""
        if not foreshadow_ref:
            return True
        plot_threads = self._story_memory.get("plot_threads", [])
        for thread in plot_threads:
            content = str(thread.get("content", ""))
            if foreshadow_ref in content:
                return True
        return False

    def _detect_commitment_overload(self) -> List[str]:
        """
        检测承诺是否过大

        Returns:
            承诺过大信号列表
        """
        signals = []
        chapter_text = self._chapter_result.get("text", "")

        if not chapter_text:
            return signals

        # 检测承诺关键词密度
        commitment_count = 0
        for keyword in COMMITMENT_OVERLOAD_KEYWORDS:
            commitment_count += chapter_text.count(keyword)

        if commitment_count >= PACING_COMPRESSION_THRESHOLD:
            signals.append(
                f"承诺过大风险: 本章包含 {commitment_count} 个承诺类关键词"
            )

        # 检测 chapter_meta 中的 cost/代价
        cost = self._chapter_meta.get("cost", "")
        if cost:
            signals.append(f"高代价承诺: 本章代价为『{cost[:30]}』")

        return signals

    def _detect_timeline_risk(self) -> str:
        """
        检测时间线风险

        Returns:
            时间线风险描述
        """
        # 检测时间状态矛盾
        time_states = self._state.get("time_states", {})
        chronological_order = time_states.get("chronological_order", "consistent")

        if chronological_order == "violated":
            return "时间线逆流：检测到日期顺序矛盾"

        # 检测章节间时间跳跃
        if self._outline_runtime:
            window_start = self._outline_runtime.active_window_start
            window_end = self._outline_runtime.active_window_end

            # 如果活动窗口跨越过多章节，可能存在时间线风险
            window_span = window_end - window_start
            if window_span > 30:
                return f"时间线风险：活动窗口跨度达 {window_span} 章，可能存在时间线压缩"

        # 检测 review_summary 中的时间线问题
        review_issues = self._review_summary.get("issues", [])
        for issue in review_issues:
            issue_text = str(issue)
            if any(kw in issue_text for kw in TIMELINE_CONTRADICTION_KEYWORDS):
                return f"时间线风险：审查发现时间矛盾『{issue_text[:30]}』"

        return ""

    def _detect_mainline_risk(self) -> str:
        """
        检测主线偏离风险

        Returns:
            主线偏离风险描述
        """
        chapter_text = self._chapter_result.get("text", "")

        if not chapter_text:
            return ""

        # 检测主线偏离关键词
        deviation_count = 0
        for keyword in MAINLINE_DEVIATION_KEYWORDS:
            deviation_count += chapter_text.count(keyword)

        if deviation_count >= 2:
            return f"主线偏离风险：检测到 {deviation_count} 个偏离信号"

        # 检测是否长时间未推进主线（通过 strand_tracker）
        strand_tracker = self._state.get("strand_tracker", {})
        chapters_since_switch = strand_tracker.get("chapters_since_switch", 0)

        if chapters_since_switch > 15:
            return f"主线偏离风险：已连续 {chapters_since_switch} 章未切换到主线"

        # 检测主线锚点覆盖
        if self._mainline_anchors:
            current_chapter = getattr(self, "_current_chapter", 0)
            unmet_anchors = []

            for anchor in self._mainline_anchors:
                start, end = anchor.target_chapter_range
                if start <= current_chapter <= end:
                    # 检查锚点是否在本章被满足
                    if not self._is_anchor_satisfied(anchor):
                        unmet_anchors.append(anchor.anchor_id)

            if unmet_anchors:
                return f"主线锚点未满足: {', '.join(unmet_anchors[:3])}"

        return ""

    def _is_anchor_satisfied(self, anchor: PhaseCommitment) -> bool:
        """检查锚点是否在当前章节被满足"""
        # 简单实现：检查 must_reach 内容是否出现在本章
        chapter_text = self._chapter_result.get("text", "")
        if not chapter_text:
            return True

        must_reach = anchor.must_reach
        if must_reach and must_reach in chapter_text:
            return True

        return False

    def _collect_affected_chapters(self) -> List[int]:
        """收集受影响章节列表"""
        affected = []
        current_chapter = getattr(self, "_current_chapter", 0)

        # 当前章之后的所有窗口内节点
        if self._outline_runtime:
            for node in (self._outline_runtime.active_nodes or []):
                if node.chapter > current_chapter:
                    if node.chapter not in affected:
                        affected.append(node.chapter)

        # 排序
        affected.sort()
        return affected

    def _collect_affected_entities(self) -> List[str]:
        """收集受影响实体列表"""
        entities: Set[str] = set()

        # 从 state_changes 提取
        state_changes = self._chapter_result.get("state_changes", []) or []
        for change in state_changes:
            entity_id = change.get("entity_id", "")
            if entity_id:
                entities.add(entity_id)

        # 从 relationships_new 提取
        relationships = self._chapter_result.get("relationships_new", []) or []
        for rel in relationships:
            from_e = rel.get("from", "") or rel.get("from_entity", "")
            to_e = rel.get("to", "") or rel.get("to_entity", "")
            if from_e:
                entities.add(from_e)
            if to_e:
                entities.add(to_e)

        # 从活动窗口节点依赖提取
        if self._outline_runtime:
            for node in (self._outline_runtime.active_nodes or []):
                deps = getattr(node, "dependencies", None)
                if deps and isinstance(deps, NodeDependency):
                    # 尝试从依赖中提取实体
                    # 注意：这里只是简单提取，实际应该更精确
                    pass

        return sorted(list(entities))

    def _collect_affected_foreshadowing(self) -> List[str]:
        """收集受影响伏笔列表"""
        foreshadowing: Set[str] = set()

        # 从 chapter_meta 中提取伏笔更新
        foreshadow_updates = self._chapter_meta.get("foreshadowing_updates", []) or []
        for update in foreshadow_updates:
            content = update.get("content", "")
            if content:
                foreshadowing.add(content)

        # 从活动窗口节点依赖中提取
        if self._outline_runtime:
            for node in (self._outline_runtime.active_nodes or []):
                deps = getattr(node, "dependencies", None)
                if deps and isinstance(deps, NodeDependency):
                    fs_ref = deps.foreshadowing
                    if fs_ref:
                        foreshadowing.add(fs_ref)

        # 从主线锚点相关伏笔提取
        for anchor in self._mainline_anchors:
            for fs in anchor.related_foreshadowing:
                foreshadowing.add(fs)

        return sorted(list(foreshadowing))

    def _compute_recommended_return(self) -> Optional[int]:
        """
        计算推荐回归主线的章节号

        Returns:
            推荐回归章节号，如果无需回归则返回 None
        """
        if not self._mainline_anchors:
            return None

        current_chapter = getattr(self, "_current_chapter", 0)

        # 找到最近的未满足的主线锚点
        # 未满足 = current_chapter 不在锚点范围内，或者锚点已过（end < current_chapter）
        incomplete_anchors = []
        for anchor in self._mainline_anchors:
            start, end = anchor.target_chapter_range
            if not (start <= current_chapter <= end):
                # 锚点未满足
                incomplete_anchors.append((end, anchor.anchor_id))

        if not incomplete_anchors:
            return None

        # 按 end 排序，返回最近的
        incomplete_anchors.sort(key=lambda x: x[0])
        return incomplete_anchors[0][0]

    def _determine_adjustment_type(
        self,
        conflict_signals: List[str],
        relationship_jump_signals: List[str],
        copy_segment_signals: List[str],
        prerequisite_gaps: List[str],
        commitment_overload_signals: List[str],
        timeline_risk: str,
        mainline_risk: str,
    ) -> tuple[str, str]:
        """
        综合所有信号，判断需要何种调整

        Returns:
            (adjustment_type, reason)
        """
        # 阻塞级风险：时间线矛盾或主线完全偏离
        if timeline_risk and "矛盾" in timeline_risk:
            return "block_for_manual_review", f"时间线矛盾严重: {timeline_risk}"

        if mainline_risk and "完全偏离" in mainline_risk:
            return "block_for_manual_review", f"主线严重偏离: {mainline_risk}"

        # 插入弧线级：检测到副本段
        if len(copy_segment_signals) >= 2:
            return "insert_arc", f"检测到副本段需展开: {'; '.join(copy_segment_signals[:2])}"

        # 窗口扩展级：关系跃迁 + 承诺过大
        if relationship_jump_signals and commitment_overload_signals:
            return "window_extend", f"关系跃迁+承诺过大: {'; '.join(relationship_jump_signals[:1])}"

        # 轻微重排级：存在前置条件缺口或冲突信号
        if prerequisite_gaps:
            return "minor_reorder", f"前置条件缺口: {'; '.join(prerequisite_gaps[:2])}"

        if conflict_signals:
            return "minor_reorder", f"存在冲突信号: {'; '.join(conflict_signals[:2])}"

        # 无需调整
        return "none", "未检测到显著影响"


# ============================================================================
# Factory & Utilities
# ============================================================================


def create_impact_analyzer(
    config: Optional[DataModulesConfig] = None,
    chapter: Optional[int] = None,
    chapter_result: Optional[Dict[str, Any]] = None,
) -> OutlineImpactAnalyzer:
    """
    创建影响分析器并填充必要数据

    Args:
        config: 配置对象
        chapter: 章节号
        chapter_result: 章节结果

    Returns:
        已填充数据的 OutlineImpactAnalyzer 实例
    """
    from .state_validator import normalize_story_memory

    analyzer = OutlineImpactAnalyzer(config)

    if chapter and chapter_result:
        analyzer.set_chapter_result(chapter, chapter_result)

        # 加载 state
        state_file = config.state_file if config else None
        if state_file and state_file.exists():
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
                analyzer.set_state(state)
            except Exception:
                pass

        # 加载 story_memory
        if config:
            story_memory_path = config.story_memory_file
            if story_memory_path and story_memory_path.exists():
                try:
                    raw = json.loads(story_memory_path.read_text(encoding="utf-8"))
                    story_memory = normalize_story_memory(raw)
                    analyzer.set_story_memory(story_memory)
                except Exception:
                    pass

        # 加载 outline_runtime
        if config:
            runtime_file = config.outline_runtime_file
            if runtime_file:
                runtime = load_outline_runtime(runtime_file)
                analyzer.set_outline_runtime(runtime)

    return analyzer


# ============================================================================
# CLI Interface
# ============================================================================


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Outline Impact Analyzer CLI")
    parser.add_argument("--project-root", type=str, help="项目根目录")
    parser.add_argument("--chapter", type=int, required=True, help="章节号")
    parser.add_argument("--chapter-result", type=str, required=True, help="章节结果 JSON")
    parser.add_argument("--review-summary", type=str, default="{}", help="审查总结 JSON")
    parser.add_argument("--output-file", type=str, default=None, help="输出到文件")

    args = parser.parse_args()

    # 初始化
    config = None
    if args.project_root:
        from .config import DataModulesConfig
        config = DataModulesConfig.from_project_root(args.project_root)

    # 解析 chapter_result
    try:
        chapter_result = json.loads(args.chapter_result)
    except json.JSONDecodeError:
        print("ERROR: Invalid chapter_result JSON", file=sys.stderr)
        sys.exit(1)

    # 解析 review_summary
    try:
        review_summary = json.loads(args.review_summary)
    except json.JSONDecodeError:
        review_summary = {}

    # 创建分析器
    analyzer = create_impact_analyzer(config, args.chapter, chapter_result)
    analyzer.set_review_summary(review_summary)

    # 加载主线锚点
    if config:
        from .mainline_anchor_manager import MainlineAnchorManager
        anchor_manager = MainlineAnchorManager(config)
        anchor_manager.load_anchors()
        analyzer.set_mainline_anchors(anchor_manager.get_all_anchors())

    # 执行分析
    impact_preview = analyzer.analyze()

    # 输出
    if args.output_file:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(impact_preview.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"Impact preview written to {args.output_file}", file=sys.stderr)
    else:
        print(json.dumps(impact_preview.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
