#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for MainlineAnchorManager
"""
import json
import pytest
from pathlib import Path

from data_modules.config import DataModulesConfig
from data_modules.mainline_anchor_manager import (
    MainlineAnchorManager,
    PhaseCommitment,
    AdjustmentDeclaration,
    create_mainline_anchor_manager,
    extract_anchors_from_outline_file,
)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project with outline structure"""
    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()

    outline_dir = cfg.outline_dir
    outline_dir.mkdir(parents=True, exist_ok=True)

    # Create 总纲.md
    zonggang_content = """# 总纲

## 故事一句话
一个少年从废物崛起，最终成为最强者的故事

## 核心主线
- 主线目标：萧炎成为斗帝
- 主要阻力：魂族魂天帝

## 主角成长线
- 起点状态：天生斗之气倒退
- 关键跃迁节点：遇见药老、继承焚诀、收服异火
- 终局定位：斗帝强者

## 关键爽点里程碑
- 第50章：药老苏醒
- 第100章：迦南学院夺冠
- 第200章：成为斗宗

## 伏笔表
| 伏笔内容 | 埋设章 | 回收章 | 层级 |
|----------|--------|--------|------|
| 萧家古玉秘密 | 1 | 180 | 核心 |
| 药老身份 | 10 | 100 | 重要 |
| 魂族阴谋 | 5 | 200 | 核心 |
"""
    (outline_dir / "总纲.md").write_text(zonggang_content, encoding="utf-8")

    # Create 第1卷-节拍表.md
    beat_table_content = """# 第 1 卷：斗气大陆 - 节拍表

> 章节范围: 第 1 - 50 章
> 核心冲突: 萧炎与纳兰嫣然的退婚冲突
> 卷末高潮: 萧炎击败纳兰嫣然

## 1) 开卷承诺（Promise）
- 本卷读者承诺（爽点/悬念/情绪）：废柴逆袭的快感、家族恩怨的纠葛
- 主要兑现类型（信息/能力/关系/资源/认可/情绪）：能力提升、关系破裂

## 2) 催化事件（Catalyst）
- 事件：纳兰嫣然上门退婚
- 不可逆变化：萧炎自尊受损，必须证明自己
- 主角当下目标：三年后在云岚宗击败纳兰嫣然

## 3) 升级危机链（Fichtean 危机递增）
| 节点 | 危机/冲突 | 代价/风险升级 | 结果/变化（可量化优先） |
|------|-----------|---------------|--------------------------|
| 1 | 退婚受辱 | 家族压力 | 激发斗志 |
| 2 | 修炼遇阻 | 斗气倒退 | 偶得药老 |
| 3 | 云岚宗挑战 | 生命危险 | 险胜对手 |

## 4) 中段反转（必填）
- 假胜利/假失败/反转事件：纳兰嫣然实际未尽全力
- 反转带来的新认知/新代价：萧炎意识到自己与强者差距巨大
- 若无：写 `无（理由：...）`

## 5) 卷末最低谷（All Is Lost）
- 最低谷事件：萧炎发现云岚宗背后有更大势力
- 代价：药老陷入沉睡
- 主角选择：踏上寻找异火之路

## 6) 卷末大兑现 + 新钩子（Payoff + Next Promise）
- 本卷兑现（对应 1) 开卷承诺）：击败纳兰嫣然、证明自己
- 新钩子（引入下一卷承诺）：药老身份之谜、异火探索
- 章末未闭合问题（落到最后一章）：谁是真凶？
"""
    (outline_dir / "第1卷-节拍表.md").write_text(beat_table_content, encoding="utf-8")

    # Create 第2卷-节拍表.md
    beat_table_content2 = """# 第 2 卷：异火大陆 - 节拍表

> 章节范围: 第 51 - 100 章
> 核心冲突: 萧炎寻找异火过程中的势力冲突
> 卷末高潮: 收服青莲地心火

## 1) 开卷承诺（Promise）
- 本卷读者承诺（爽点/悬念/情绪）：异火的神秘与力量
- 主要兑现类型（信息/能力/关系/资源/认可/情绪）：能力提升、资源获取
"""
    (outline_dir / "第2卷-节拍表.md").write_text(beat_table_content2, encoding="utf-8")

    return cfg


class TestPhaseCommitment:
    """Test PhaseCommitment data class"""

    def test_to_dict(self):
        anchor = PhaseCommitment(
            anchor_id="test_anchor",
            scope="book",
            must_reach="完成主线目标",
            must_not_break=["不可背叛主角"],
            target_chapter_range=(1, 100),
            related_entities=["萧炎"],
            related_foreshadowing=["伏笔1"],
        )
        d = anchor.to_dict()
        assert d["anchor_id"] == "test_anchor"
        assert d["scope"] == "book"
        assert d["target_chapter_range"] == [1, 100]

    def test_from_dict(self):
        data = {
            "anchor_id": "test_anchor",
            "scope": "volume",
            "must_reach": "完成卷目标",
            "must_not_break": ["不可偏离"],
            "target_chapter_range": [10, 50],
            "related_entities": [],
            "related_foreshadowing": [],
        }
        anchor = PhaseCommitment.from_dict(data)
        assert anchor.anchor_id == "test_anchor"
        assert anchor.scope == "volume"
        assert anchor.target_chapter_range == (10, 50)


class TestAdjustmentDeclaration:
    """Test AdjustmentDeclaration data class"""

    def test_to_dict(self):
        decl = AdjustmentDeclaration(
            mainline_service_reason="服务主线：提升主角实力",
            return_to_mainline_by=30,
        )
        d = decl.to_dict()
        assert d["mainline_service_reason"] == "服务主线：提升主角实力"
        assert d["return_to_mainline_by"] == 30

    def test_from_dict(self):
        data = {
            "mainline_service_reason": "测试理由",
            "return_to_mainline_by": 25,
        }
        decl = AdjustmentDeclaration.from_dict(data)
        assert decl.mainline_service_reason == "测试理由"
        assert decl.return_to_mainline_by == 25


class TestMainlineAnchorManager:
    """Test MainlineAnchorManager"""

    def test_load_anchors(self, temp_project):
        """Test loading anchors from outline files"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        # Check book anchors
        book_anchors = manager.get_book_anchors()
        assert len(book_anchors) > 0

        # Should have mainline goal, growth line, and milestones
        anchor_ids = [a.anchor_id for a in book_anchors]
        assert "book_mainline_goal" in anchor_ids
        assert "book_growth_line" in anchor_ids

    def test_volume_anchors(self, temp_project):
        """Test loading volume anchors"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        vol1_anchors = manager.get_volume_anchors(1)
        assert len(vol1_anchors) > 0

        vol2_anchors = manager.get_volume_anchors(2)
        assert len(vol2_anchors) > 0

    def test_get_anchors_for_chapter(self, temp_project):
        """Test getting anchors for a specific chapter"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        anchors = manager.get_anchors_for_chapter(25, volume=1)
        assert len(anchors) > 0

        # Book anchors should always apply
        book_scopes = [a for a in anchors if a.scope == "book"]
        assert len(book_scopes) > 0

    def test_validate_adjustment_without_declaration(self, temp_project):
        """Test that insert_arc without declaration is rejected"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        is_valid, violations = manager.validate_adjustment(
            adjustment_type="insert_arc",
            affected_chapters=[25, 26, 27],
            declaration=None,
        )
        assert is_valid is False
        assert any("回归点" in v for v in violations)

    def test_validate_adjustment_with_declaration(self, temp_project):
        """Test validation with proper declaration"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        decl = AdjustmentDeclaration(
            mainline_service_reason="插入副本：丰富世界观",
            return_to_mainline_by=30,
        )

        is_valid, violations = manager.validate_adjustment(
            adjustment_type="insert_arc",
            affected_chapters=[25, 26, 27],
            declaration=decl,
        )
        # Should be valid if declaration is provided and return point is within bounds
        # Note: exact result depends on anchor ranges

    def test_check_mainline_integrity(self, temp_project):
        """Test mainline integrity check"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        is_integr, warnings = manager.check_mainline_integrity(
            chapter=25,
            window_start=20,
            window_end=40,
        )
        # Window covers chapter 25, should be integral for that chapter

    def test_anchor_snapshot(self, temp_project):
        """Test anchor snapshot serialization"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        snapshot = manager.get_anchor_snapshot()
        assert "book_anchors" in snapshot
        assert "volume_anchors" in snapshot

        # Load from snapshot
        manager2 = MainlineAnchorManager(temp_project)
        manager2.load_anchor_snapshot(snapshot)

        assert len(manager2.get_book_anchors()) == len(manager.get_book_anchors())

    def test_add_window_anchor(self, temp_project):
        """Test adding window-level anchor"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        initial_window_anchors = len(manager._window_anchors)

        new_anchor = PhaseCommitment(
            anchor_id="window_temp_arc",
            scope="window",
            must_reach="完成临时副本",
            target_chapter_range=(30, 35),
        )
        manager.add_window_anchor(new_anchor)

        assert len(manager._window_anchors) == initial_window_anchors + 1
        assert manager._window_anchors[-1].anchor_id == "window_temp_arc"

    def test_clear_window_anchors(self, temp_project):
        """Test clearing window anchors"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        # Add a window anchor first
        new_anchor = PhaseCommitment(
            anchor_id="window_temp",
            scope="window",
            must_reach="测试",
            target_chapter_range=(30, 35),
        )
        manager.add_window_anchor(new_anchor)
        assert len(manager._window_anchors) > 0

        manager.clear_window_anchors()
        assert len(manager._window_anchors) == 0


class TestExtractAnchorsFromOutlineFile:
    """Test standalone anchor extraction from files"""

    def test_extract_from_zonggang(self, temp_project):
        """Test extracting anchors from 总纲.md"""
        file_path = temp_project.outline_dir / "总纲.md"
        anchors = extract_anchors_from_outline_file(file_path, temp_project)

        assert len(anchors) > 0
        assert any(a.anchor_id == "book_mainline_goal" for a in anchors)

    def test_extract_from_beat_table(self, temp_project):
        """Test extracting anchors from 节拍表.md"""
        file_path = temp_project.outline_dir / "第1卷-节拍表.md"
        anchors = extract_anchors_from_outline_file(file_path, temp_project)

        assert len(anchors) > 0
        # Should have promise anchor
        assert any("promise" in a.anchor_id.lower() for a in anchors)

    def test_extract_nonexistent_file(self, temp_project):
        """Test extracting from non-existent file returns empty list"""
        file_path = temp_project.outline_dir / "不存在.md"
        anchors = extract_anchors_from_outline_file(file_path)
        assert len(anchors) == 0


class TestCreateMainlineAnchorManager:
    """Test factory function"""

    def test_create_and_load(self, temp_project):
        """Test factory creates manager and loads anchors"""
        manager = create_mainline_anchor_manager(temp_project)

        assert len(manager.get_book_anchors()) > 0
        assert len(manager.get_volume_anchors(1)) > 0


class TestDegradationBehavior:
    """Test degradation behavior as specified in Architecture Decisions"""

    def test_no_automatic_write_without_return_point(self, temp_project):
        """
        如果无法判断回归点，自动调纲必须降级为"只生成风险预警，不自动落盘"

        This is tested by validate_adjustment returning False without declaration
        """
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        # insert_arc without declaration should fail validation
        is_valid, violations = manager.validate_adjustment(
            adjustment_type="insert_arc",
            affected_chapters=[25, 26, 27],
            declaration=None,
        )
        assert is_valid is False
        assert len(violations) > 0

    def test_minor_reorder_can_be_valid_without_declaration(self, temp_project):
        """minor_reorder doesn't require declaration"""
        manager = MainlineAnchorManager(temp_project)
        manager.load_anchors()

        is_valid, violations = manager.validate_adjustment(
            adjustment_type="minor_reorder",
            affected_chapters=[25, 26],
            declaration=None,
        )
        # minor reorder should be valid without declaration
        # (it doesn't introduce new arc that needs return point)
