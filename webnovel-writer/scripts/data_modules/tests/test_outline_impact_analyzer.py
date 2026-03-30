#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutlineImpactAnalyzer Tests
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# 确保从 worktree 目录运行时可以导入
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestImpactPreview:
    """ImpactPreview 数据结构测试"""

    def test_impact_preview_default_values(self):
        from data_modules.outline_impact_analyzer import ImpactPreview

        preview = ImpactPreview()

        assert preview.needs_adjustment is False
        assert preview.adjustment_type == "none"
        assert preview.reason == ""
        assert preview.affected_chapters == []
        assert preview.affected_entities == []
        assert preview.affected_foreshadowing == []
        assert preview.timeline_risk == ""
        assert preview.mainline_risk == ""
        assert preview.recommended_return_to_mainline_by is None

    def test_impact_preview_to_dict(self):
        from data_modules.outline_impact_analyzer import ImpactPreview

        preview = ImpactPreview(
            needs_adjustment=True,
            adjustment_type="minor_reorder",
            reason="测试原因",
            affected_chapters=[5, 6, 7],
            affected_entities=["角色A", "角色B"],
            affected_foreshadowing=["伏笔1"],
            timeline_risk="时间线风险",
            mainline_risk="主线风险",
            recommended_return_to_mainline_by=10,
            conflict_signals=["冲突1"],
            prerequisite_gaps=["前置1"],
            relationship_jump_signals=["关系跃迁1"],
            copy_segment_signals=["副本段1"],
        )

        result = preview.to_dict()

        assert result["needs_adjustment"] is True
        assert result["adjustment_type"] == "minor_reorder"
        assert result["reason"] == "测试原因"
        assert result["affected_chapters"] == [5, 6, 7]
        assert result["affected_entities"] == ["角色A", "角色B"]
        assert result["affected_foreshadowing"] == ["伏笔1"]
        assert result["timeline_risk"] == "时间线风险"
        assert result["mainline_risk"] == "主线风险"
        assert result["recommended_return_to_mainline_by"] == 10
        assert result["conflict_signals"] == ["冲突1"]
        assert result["prerequisite_gaps"] == ["前置1"]
        assert result["relationship_jump_signals"] == ["关系跃迁1"]
        assert result["copy_segment_signals"] == ["副本段1"]


class TestOutlineImpactAnalyzer:
    """OutlineImpactAnalyzer 核心分析逻辑测试"""

    @pytest.fixture
    def temp_project(self, tmp_path):
        from data_modules.config import DataModulesConfig
        cfg = DataModulesConfig.from_project_root(tmp_path)
        cfg.ensure_dirs()
        return cfg

    @pytest.fixture
    def analyzer(self, temp_project):
        from data_modules.outline_impact_analyzer import OutlineImpactAnalyzer
        return OutlineImpactAnalyzer(temp_project)

    def test_analyzer_initialization(self, analyzer):
        """分析器初始化测试"""
        from data_modules.outline_impact_analyzer import ImpactPreview

        result = analyzer.analyze()
        assert isinstance(result, ImpactPreview)
        # 未设置章节结果时，应该返回默认值
        assert result.adjustment_type == "none"

    def test_set_chapter_result(self, analyzer):
        """设置章节结果"""
        chapter_result = {
            "text": "这是测试章节正文",
            "entities_appeared": [
                {"id": "角色A", "type": "角色"}
            ],
            "state_changes": [
                {"entity_id": "角色A", "field": "power", "new": "筑基"}
            ],
            "relationships_new": [
                {"from": "角色A", "to": "角色B", "type": "师徒"}
            ],
            "chapter_meta": {
                "goal": "主角突破筑基",
                "cost": "消耗大量灵力"
            }
        }

        analyzer.set_chapter_result(5, chapter_result)
        assert analyzer._current_chapter == 5
        assert analyzer._chapter_meta["goal"] == "主角突破筑基"

    def test_detect_relationship_jumps(self, analyzer):
        """检测关系跃迁"""
        chapter_result = {
            "text": "两人从此成为好友",
            "relationships_new": [
                {"from": "A", "to": "B", "type": "敌对→友好"},
                {"from": "B", "to": "C", "type": "陌生→亲密"},
            ],
            "chapter_meta": {}
        }

        analyzer.set_chapter_result(5, chapter_result)
        signals = analyzer._detect_relationship_jumps()

        assert len(signals) >= 1
        assert any("关系跃迁" in s or "关系类型突变" in s for s in signals)

    def test_detect_copy_segments(self, analyzer):
        """检测副本段信号"""
        chapter_result = {
            "text": "另一边，主角来到了一个副本空间，这里有独立的故事线。",
            "chapter_meta": {}
        }

        analyzer.set_chapter_result(5, chapter_result)
        signals = analyzer._detect_copy_segments()

        assert len(signals) >= 1
        assert any("副本段" in s or "并列叙事" in s for s in signals)

    def test_detect_commitment_overload(self, analyzer):
        """检测承诺过大"""
        chapter_result = {
            "text": "主角发誓必须打败敌人，无论付出什么代价都要绝对保护她。",
            "chapter_meta": {
                "cost": "牺牲生命"
            }
        }

        analyzer.set_chapter_result(5, chapter_result)
        signals = analyzer._detect_commitment_overload()

        assert len(signals) >= 1
        assert any("承诺" in s for s in signals)

    def test_detect_prerequisite_gaps_no_runtime(self, analyzer):
        """检测前置条件缺口（无活动窗口时）"""
        chapter_result = {
            "text": "测试正文",
            "chapter_meta": {}
        }

        analyzer.set_chapter_result(5, chapter_result)
        gaps = analyzer._detect_prerequisite_gaps()

        # 无活动窗口时，应该没有前置缺口
        assert isinstance(gaps, list)

    def test_collect_affected_entities(self, analyzer):
        """收集受影响实体"""
        chapter_result = {
            "text": "测试",
            "entities_appeared": [
                {"id": "角色A", "type": "角色"},
                {"id": "角色B", "type": "角色"}
            ],
            "state_changes": [
                {"entity_id": "角色A", "field": "level", "new": "10"}
            ],
            "relationships_new": [
                {"from": "角色A", "to": "角色B", "type": "师徒"}
            ],
            "chapter_meta": {}
        }

        analyzer.set_chapter_result(5, chapter_result)
        entities = analyzer._collect_affected_entities()

        assert "角色A" in entities
        assert "角色B" in entities

    def test_collect_affected_chapters(self, analyzer):
        """收集受影响章节"""
        from data_modules.outline_runtime import OutlineRuntime, OutlineNode

        runtime = OutlineRuntime(
            active_window_start=1,
            active_window_end=10,
            active_nodes=[
                OutlineNode(chapter=6, title="节点6", goal="目标6", conflict="冲突", cost="代价", hook="钩子"),
                OutlineNode(chapter=8, title="节点8", goal="目标8", conflict="冲突", cost="代价", hook="钩子"),
            ]
        )

        chapter_result = {
            "text": "测试",
            "chapter_meta": {}
        }

        analyzer.set_chapter_result(5, chapter_result)
        analyzer.set_outline_runtime(runtime)

        chapters = analyzer._collect_affected_chapters()
        assert 6 in chapters
        assert 8 in chapters
        assert 5 not in chapters

    def test_compute_recommended_return(self, analyzer):
        """计算推荐回归主线章节"""
        from data_modules.mainline_anchor_manager import PhaseCommitment

        anchors = [
            PhaseCommitment(
                anchor_id="anchor1",
                scope="volume",
                must_reach="目标1",
                target_chapter_range=(1, 10)
            ),
            PhaseCommitment(
                anchor_id="anchor2",
                scope="volume",
                must_reach="目标2",
                target_chapter_range=(15, 20)
            ),
        ]

        analyzer.set_mainline_anchors(anchors)
        analyzer.set_chapter_result(5, {"text": "测试", "chapter_meta": {}})

        recommended = analyzer._compute_recommended_return()
        assert recommended == 20  # 最近的未满足锚点结束章节

    def test_analyze_no_issues(self, analyzer):
        """分析无显著问题"""
        chapter_result = {
            "text": "这是正常的章节正文，没有异常。",
            "entities_appeared": [],
            "state_changes": [],
            "relationships_new": [],
            "chapter_meta": {}
        }

        analyzer.set_chapter_result(5, chapter_result)
        result = analyzer.analyze()

        assert result.adjustment_type == "none"
        assert result.needs_adjustment is False

    def test_analyze_with_conflicts(self, analyzer):
        """分析存在冲突"""
        from data_modules.outline_runtime import OutlineRuntime, OutlineNode, NodeDependency

        runtime = OutlineRuntime(
            active_window_start=1,
            active_window_end=10,
            active_nodes=[
                OutlineNode(
                    chapter=6,
                    title="节点6",
                    goal="主角死亡",  # 与当前章冲突
                    conflict="冲突",
                    cost="代价",
                    hook="钩子",
                    dependencies=NodeDependency(prior_chapter=10)  # 前置未满足
                ),
            ]
        )

        chapter_result = {
            "text": "主角活了下来",
            "state_changes": [
                {"entity_id": "主角", "field": "status", "new": "活着"}
            ],
            "chapter_meta": {
                "goal": "主角存活"
            }
        }

        analyzer.set_chapter_result(5, chapter_result)
        analyzer.set_outline_runtime(runtime)

        result = analyzer.analyze()

        # 存在前置未满足，应该需要调整
        assert result.needs_adjustment is True


class TestCreateImpactAnalyzer:
    """create_impact_analyzer 工厂函数测试"""

    def test_create_impact_analyzer_basic(self, tmp_path):
        from data_modules.config import DataModulesConfig
        from data_modules.outline_impact_analyzer import create_impact_analyzer

        cfg = DataModulesConfig.from_project_root(tmp_path)
        cfg.ensure_dirs()

        chapter_result = {
            "text": "测试正文",
            "chapter_meta": {}
        }

        analyzer = create_impact_analyzer(cfg, 5, chapter_result)

        assert analyzer._current_chapter == 5
        assert analyzer._chapter_result["text"] == "测试正文"


class TestAnalyzeRules:
    """分析规则常量测试"""

    def test_goal_conflict_detection(self, tmp_path):
        """目标冲突检测"""
        from data_modules.config import DataModulesConfig
        from data_modules.outline_impact_analyzer import OutlineImpactAnalyzer

        cfg = DataModulesConfig.from_project_root(tmp_path)
        analyzer = OutlineImpactAnalyzer(cfg)

        # 战斗 vs 和解 冲突
        assert analyzer._is_goal_conflict("攻击敌人", "与敌人和解") is True
        # 非冲突目标
        assert analyzer._is_goal_conflict("提升实力", "打败BOSS") is False

    def test_state_conflict_check(self, tmp_path):
        """状态冲突检测"""
        from data_modules.config import DataModulesConfig
        from data_modules.outline_impact_analyzer import OutlineImpactAnalyzer

        cfg = DataModulesConfig.from_project_root(tmp_path)
        analyzer = OutlineImpactAnalyzer(cfg)
        analyzer.set_story_memory({
            "characters": {
                "萧炎": {"current_state": "筑基期"}
            }
        })

        # 正常状态更新，不算冲突
        result = analyzer._check_state_conflict("萧炎", "realm", "金丹期")
        # 应该返回 None（无冲突）
        assert result is None


class TestCLI:
    """CLI 接口测试"""

    def test_cli_import(self):
        """测试 CLI 模块可以正常导入"""
        from data_modules import outline_impact_analyzer
        assert hasattr(outline_impact_analyzer, "main")
        assert hasattr(outline_impact_analyzer, "OutlineImpactAnalyzer")
        assert hasattr(outline_impact_analyzer, "ImpactPreview")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
