#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Outline Runtime tests
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from data_modules.outline_runtime import (
    OutlineRuntime,
    OutlineAdjustment,
    OutlineNode,
    MainlineAnchor,
    NodeDependency,
    normalize_outline_runtime,
    normalize_outline_adjustment,
    load_outline_runtime,
    save_outline_runtime,
    load_outline_adjustments,
    append_outline_adjustment,
    get_last_adjustment_id,
    sync_runtime_version_from_adjustments,
    ensure_outline_runtime,
    _default_runtime_dict,
)


class TestNodeDependency:
    def test_default_empty(self):
        dep = NodeDependency()
        assert dep.character_state is None
        assert dep.item_state is None
        assert dep.relationship_state is None
        assert dep.foreshadowing is None
        assert dep.prior_chapter is None

    def test_with_values(self):
        dep = NodeDependency(
            character_state="主角已解锁炼丹能力",
            item_state="获得九转还魂丹",
            relationship_state="与师父关系从陌生到信任",
            foreshadowing="第一章埋下的剑灵伏笔",
            prior_chapter=5,
        )
        assert dep.character_state == "主角已解锁炼丹能力"
        assert dep.prior_chapter == 5


class TestOutlineNode:
    def test_default_chapter_node(self):
        node = OutlineNode(
            chapter=10,
            title="第十章 逆袭",
            goal="主角突破境界",
            conflict="心魔阻碍",
            cost="消耗十年寿元",
            hook="神秘老者出现",
        )
        assert node.chapter == 10
        assert node.node_type == "chapter"
        assert node.mainline_anchor_refs == []
        assert node.dependencies.prior_chapter is None

    def test_arc_node(self):
        node = OutlineNode(
            chapter=5,
            title="感情线爆发弧",
            goal="感情线推进",
            conflict="误会与分离",
            cost="关系倒退",
            hook="女主离开",
            node_type="arc",
        )
        assert node.node_type == "arc"


class TestMainlineAnchor:
    def test_basic(self):
        anchor = MainlineAnchor(
            anchor_id="anchor_001",
            chapter=20,
            label="主线-第一次生死危机",
            description="主角第一次面临生死考验",
        )
        assert anchor.anchor_id == "anchor_001"
        assert anchor.chapter == 20


class TestOutlineRuntime:
    def test_default_values(self):
        runtime = OutlineRuntime()
        assert runtime.active_volume == 1
        assert runtime.active_window_start == 1
        assert runtime.active_window_end == 50
        assert runtime.window_version == 0
        assert runtime.baseline_anchor_version == 0
        assert runtime.last_adjustment_chapter is None
        assert runtime.last_adjustment_type is None
        assert runtime.last_applied_adjustment_id is None
        assert runtime.return_to_mainline_by is None
        assert runtime.window_status == "active"
        assert runtime.mainline_anchors == []
        assert runtime.active_nodes == []

    def test_with_nodes_and_anchors(self):
        node = OutlineNode(
            chapter=10,
            title="test",
            goal="goal",
            conflict="conflict",
            cost="cost",
            hook="hook",
        )
        anchor = MainlineAnchor(
            anchor_id="a1",
            chapter=10,
            label="test",
            description="desc",
        )
        runtime = OutlineRuntime(
            active_volume=2,
            active_window_start=51,
            active_window_end=100,
            active_nodes=[node],
            mainline_anchors=[anchor],
        )
        assert runtime.active_volume == 2
        assert runtime.active_window_start == 51
        assert len(runtime.active_nodes) == 1
        assert len(runtime.mainline_anchors) == 1


class TestOutlineAdjustment:
    def test_minimal_record(self):
        adj = OutlineAdjustment(
            trigger_chapter=15,
            adjustment_type="insert",
            reason="情节需要",
            impact_preview="增加一场战斗",
            before_window={"start": 10, "end": 20, "version": 1},
            after_window={"start": 10, "end": 21, "version": 2},
        )
        assert adj.trigger_chapter == 15
        assert adj.adjustment_type == "insert"
        assert adj.adjustment_id is not None
        assert adj.written_at is not None
        assert adj.return_to_mainline_by is None

    def test_full_record(self):
        adj = OutlineAdjustment(
            trigger_chapter=20,
            adjustment_type="split",
            reason="支线展开",
            impact_preview="章节延长",
            mainline_service_reason="扩展世界观",
            return_to_mainline_by=30,
            before_window={"start": 15, "end": 25, "version": 2},
            after_window={"start": 15, "end": 30, "version": 3},
        )
        assert adj.mainline_service_reason == "扩展世界观"
        assert adj.return_to_mainline_by == 30


class TestNormalizeOutlineRuntime:
    def test_empty_dict_returns_defaults(self):
        result = normalize_outline_runtime({})
        assert result["active_volume"] == 1
        assert result["window_status"] == "active"
        assert result["mainline_anchors"] == []

    def test_non_dict_returns_defaults(self):
        result = normalize_outline_runtime("invalid")
        assert isinstance(result, dict)
        assert result["active_volume"] == 1

    def test_partial_data_filled(self):
        data = {"active_window_start": 10}
        result = normalize_outline_runtime(data)
        assert result["active_window_start"] == 10
        assert result["active_window_end"] == 50  # defaulted
        assert result["active_volume"] == 1  # defaulted

    def test_wrong_types_corrected(self):
        data = {
            "active_volume": "2",  # should be int
            "active_window_start": 5.0,  # should be int
        }
        result = normalize_outline_runtime(data)
        assert isinstance(result["active_volume"], int)
        assert result["active_volume"] == 2
        assert isinstance(result["active_window_start"], int)


class TestNormalizeOutlineAdjustment:
    def test_missing_required_field_raises(self):
        with pytest.raises(ValueError, match="missing required field"):
            normalize_outline_adjustment({"trigger_chapter": 1})

    def test_valid_record(self):
        data = {
            "trigger_chapter": 10,
            "adjustment_type": "insert",
            "reason": "test",
            "impact_preview": "test",
            "before_window": {"start": 1, "end": 10},
            "after_window": {"start": 1, "end": 11},
        }
        result = normalize_outline_adjustment(data)
        assert result["adjustment_id"] is not None
        assert result["written_at"] is not None

    def test_wrong_type_raises(self):
        with pytest.raises(ValueError):
            normalize_outline_adjustment("not a dict")


class TestLoadSaveOutlineRuntime:
    def test_save_and_load_empty_runtime(self, tmp_path):
        runtime = OutlineRuntime()
        runtime_file = tmp_path / "outline_runtime.json"

        save_outline_runtime(runtime_file, runtime)
        assert runtime_file.exists()

        loaded = load_outline_runtime(runtime_file)
        assert loaded.active_volume == 1
        assert loaded.window_version == 0

    def test_save_and_load_with_data(self, tmp_path):
        node = OutlineNode(
            chapter=5,
            title="第五章",
            goal="goal",
            conflict="conflict",
            cost="cost",
            hook="hook",
        )
        runtime = OutlineRuntime(
            active_volume=1,
            active_window_start=1,
            active_window_end=20,
            window_version=3,
            active_nodes=[node],
        )
        runtime_file = tmp_path / "outline_runtime.json"

        save_outline_runtime(runtime_file, runtime)
        loaded = load_outline_runtime(runtime_file)

        assert loaded.active_volume == 1
        assert loaded.active_window_end == 20
        assert loaded.window_version == 3
        assert len(loaded.active_nodes) == 1
        assert loaded.active_nodes[0].chapter == 5

    def test_load_nonexistent_file_returns_default(self, tmp_path):
        runtime_file = tmp_path / "nonexistent.json"
        loaded = load_outline_runtime(runtime_file)
        assert loaded.active_volume == 1
        assert loaded.window_status == "active"

    def test_load_corrupted_file_returns_default(self, tmp_path):
        runtime_file = tmp_path / "corrupted.json"
        runtime_file.write_text("{invalid json", encoding="utf-8")
        loaded = load_outline_runtime(runtime_file)
        assert loaded.active_volume == 1


class TestLoadSaveAdjustments:
    def test_append_and_load_single(self, tmp_path):
        adj_file = tmp_path / "adjustments.jsonl"
        adj = OutlineAdjustment(
            trigger_chapter=10,
            adjustment_type="insert",
            reason="test",
            impact_preview="test impact",
            before_window={"start": 1, "end": 10, "version": 0},
            after_window={"start": 1, "end": 11, "version": 1},
        )

        adj_id = append_outline_adjustment(adj_file, adj)
        assert adj_id == adj.adjustment_id
        assert adj_file.exists()

        loaded = load_outline_adjustments(adj_file)
        assert len(loaded) == 1
        assert loaded[0].trigger_chapter == 10
        assert loaded[0].adjustment_id == adj_id

    def test_append_multiple_and_load(self, tmp_path):
        adj_file = tmp_path / "adjustments.jsonl"

        for i in range(3):
            adj = OutlineAdjustment(
                trigger_chapter=i * 10,
                adjustment_type="insert",
                reason=f"test {i}",
                impact_preview="test",
                before_window={"start": i * 10, "end": (i + 1) * 10, "version": i},
                after_window={"start": i * 10, "end": (i + 1) * 10 + 1, "version": i + 1},
            )
            append_outline_adjustment(adj_file, adj)

        loaded = load_outline_adjustments(adj_file)
        assert len(loaded) == 3
        assert loaded[0].trigger_chapter == 0
        assert loaded[1].trigger_chapter == 10
        assert loaded[2].trigger_chapter == 20

    def test_load_empty_file(self, tmp_path):
        adj_file = tmp_path / "empty.jsonl"
        adj_file.write_text("", encoding="utf-8")
        loaded = load_outline_adjustments(adj_file)
        assert loaded == []

    def test_load_nonexistent_file(self, tmp_path):
        adj_file = tmp_path / "nonexistent.jsonl"
        loaded = load_outline_adjustments(adj_file)
        assert loaded == []


class TestGetLastAdjustmentId:
    def test_empty_file(self, tmp_path):
        adj_file = tmp_path / "empty.jsonl"
        adj_file.write_text("", encoding="utf-8")
        assert get_last_adjustment_id(adj_file) is None

    def test_nonexistent_file(self, tmp_path):
        adj_file = tmp_path / "nonexistent.jsonl"
        assert get_last_adjustment_id(adj_file) is None

    def test_with_records(self, tmp_path):
        adj_file = tmp_path / "adjustments.jsonl"
        adj = OutlineAdjustment(
            trigger_chapter=10,
            adjustment_type="insert",
            reason="test",
            impact_preview="test",
            before_window={"start": 1, "end": 10, "version": 0},
            after_window={"start": 1, "end": 11, "version": 1},
        )
        append_outline_adjustment(adj_file, adj)

        last_id = get_last_adjustment_id(adj_file)
        assert last_id == adj.adjustment_id


class TestSyncRuntimeVersionFromAdjustments:
    def test_sync_from_jsonl(self, tmp_path):
        runtime_file = tmp_path / "outline_runtime.json"
        adj_file = tmp_path / "adjustments.jsonl"

        # 1. 先追加 adjustment（这会触发 version 增长）
        adj = OutlineAdjustment(
            trigger_chapter=10,
            adjustment_type="insert",
            reason="test",
            impact_preview="test",
            before_window={"start": 1, "end": 10, "version": 0},
            after_window={"start": 1, "end": 15, "version": 1},
        )
        append_outline_adjustment(adj_file, adj)

        # 2. 用空的 runtime 文件测试同步
        runtime = sync_runtime_version_from_adjustments(runtime_file, adj_file)

        assert runtime.last_applied_adjustment_id == adj.adjustment_id
        assert runtime.window_version == 1
        assert runtime.active_window_end == 15

    def test_no_adjustments_no_crash(self, tmp_path):
        runtime_file = tmp_path / "outline_runtime.json"
        adj_file = tmp_path / "adjustments.jsonl"

        # 不创建任何 adjustment 文件
        runtime = sync_runtime_version_from_adjustments(runtime_file, adj_file)
        assert runtime.window_version == 0


class TestEnsureOutlineRuntime:
    def test_new_project(self, tmp_path):
        """新项目应该创建默认运行时"""
        # 确保 .webnovel 目录存在
        webnovel_dir = tmp_path / ".webnovel"
        webnovel_dir.mkdir(exist_ok=True)

        runtime = ensure_outline_runtime(tmp_path)

        assert runtime.active_volume == 1
        assert runtime.active_window_start == 1
        assert runtime.active_window_end == 50
        assert runtime.window_version == 0

    def test_existing_project_with_adjustments(self, tmp_path):
        """已有项目应该从 JSONL 同步"""
        # 设置项目结构
        webnovel_dir = tmp_path / ".webnovel"
        webnovel_dir.mkdir(exist_ok=True)

        runtime_file = webnovel_dir / "outline_runtime.json"
        adj_file = webnovel_dir / "outline_adjustments.jsonl"

        # 创建初始 runtime
        initial_runtime = OutlineRuntime(window_version=0)
        save_outline_runtime(runtime_file, initial_runtime)

        # 追加 adjustment
        adj = OutlineAdjustment(
            trigger_chapter=20,
            adjustment_type="modify",
            reason="情节调整",
            impact_preview="扩展窗口",
            before_window={"start": 1, "end": 30, "version": 0},
            after_window={"start": 1, "end": 35, "version": 1},
        )
        append_outline_adjustment(adj_file, adj)

        # 确保目录存在（ensure_dirs）
        runtime = ensure_outline_runtime(tmp_path)

        assert runtime.last_applied_adjustment_id == adj.adjustment_id
        assert runtime.window_version == 1

    def test_existing_project_missing_runtime_file(self, tmp_path):
        """只有 adjustment 文件的情况"""
        webnovel_dir = tmp_path / ".webnovel"
        webnovel_dir.mkdir(exist_ok=True)

        adj_file = webnovel_dir / "outline_adjustments.jsonl"

        adj = OutlineAdjustment(
            trigger_chapter=5,
            adjustment_type="insert",
            reason="插入章节",
            impact_preview="新增内容",
            before_window={"start": 1, "end": 10, "version": 0},
            after_window={"start": 1, "end": 11, "version": 1},
        )
        append_outline_adjustment(adj_file, adj)

        runtime = ensure_outline_runtime(tmp_path)
        assert runtime.last_applied_adjustment_id == adj.adjustment_id


class TestIntegration:
    """集成测试：验证完整流程"""

    def test_full_adjustment_flow(self, tmp_path):
        """模拟完整的调纲流程"""
        runtime_file = tmp_path / "outline_runtime.json"
        adj_file = tmp_path / "adjustments.jsonl"

        # 1. 初始化
        runtime = OutlineRuntime()
        save_outline_runtime(runtime_file, runtime)
        assert runtime.window_version == 0

        # 2. 第一次调整
        adj1 = OutlineAdjustment(
            trigger_chapter=10,
            adjustment_type="insert",
            reason="插入副本章节",
            impact_preview="新增第10.5章",
            before_window={"start": 1, "end": 20, "version": 0},
            after_window={"start": 1, "end": 21, "version": 1},
        )
        append_outline_adjustment(adj_file, adj1)

        # 3. 同步 runtime
        runtime = sync_runtime_version_from_adjustments(runtime_file, adj_file)
        assert runtime.window_version == 1
        assert runtime.active_window_end == 21
        assert runtime.last_applied_adjustment_id == adj1.adjustment_id

        # 4. 第二次调整
        adj2 = OutlineAdjustment(
            trigger_chapter=15,
            adjustment_type="delete",
            reason="删除冗余章节",
            impact_preview="删除第15章",
            before_window={"start": 1, "end": 21, "version": 1},
            after_window={"start": 1, "end": 20, "version": 2},
        )
        append_outline_adjustment(adj_file, adj2)

        # 5. 再次同步
        runtime = sync_runtime_version_from_adjustments(runtime_file, adj_file)
        assert runtime.window_version == 2
        assert runtime.last_applied_adjustment_id == adj2.adjustment_id

        # 6. 验证 JSONL 顺序
        adjustments = load_outline_adjustments(adj_file)
        assert len(adjustments) == 2
        assert adjustments[0].adjustment_id == adj1.adjustment_id
        assert adjustments[1].adjustment_id == adj2.adjustment_id

    def test_backward_compatibility(self, tmp_path):
        """测试向后兼容性：旧文件缺字段不崩溃"""
        runtime_file = tmp_path / "outline_runtime.json"

        # 模拟旧版本文件（只有部分字段）
        old_data = {
            "active_volume": 1,
            "active_window_start": 5,
            # 缺其他字段
        }
        runtime_file.write_text(json.dumps(old_data), encoding="utf-8")

        loaded = load_outline_runtime(runtime_file)
        assert loaded.active_volume == 1
        assert loaded.active_window_start == 5
        # 缺失字段应该被填充默认值
        assert loaded.window_status == "active"
        assert loaded.active_window_end == 50  # default

    def test_empty_project_load(self, tmp_path):
        """空项目应该能安全加载，不因缺字段崩溃"""
        runtime_file = tmp_path / "outline_runtime.json"
        adj_file = tmp_path / "adjustments.jsonl"

        # 两者都不存在
        runtime = sync_runtime_version_from_adjustments(runtime_file, adj_file)
        assert runtime.active_volume == 1
        assert runtime.window_version == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
