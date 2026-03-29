#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutlineMutationEngine Tests

测试大纲写回引擎的原子性、失败回滚、版本增长等核心行为。
"""

import json
import sys
from pathlib import Path

import pytest

# 确保从 worktree 目录运行时可以导入
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class TestMutationRequest:
    """MutationRequest 数据结构测试"""

    def test_mutation_request_default_values(self):
        from data_modules.outline_mutation_engine import MutationRequest

        request = MutationRequest(
            action_type="minor_reorder",
            trigger_chapter=5,
            reason="测试原因",
            impact_preview="影响预览",
        )

        assert request.action_type == "minor_reorder"
        assert request.trigger_chapter == 5
        assert request.reason == "测试原因"
        assert request.impact_preview == "影响预览"
        assert request.affected_chapters == []
        assert request.new_window_start is None
        assert request.new_window_end is None
        assert request.new_arc_node is None
        assert request.declaration is None

    def test_mutation_request_with_declaration(self):
        from data_modules.outline_mutation_engine import MutationRequest
        from data_modules.mainline_anchor_manager import AdjustmentDeclaration

        declaration = AdjustmentDeclaration(
            mainline_service_reason="服务主线原因",
            return_to_mainline_by=20,
        )

        request = MutationRequest(
            action_type="insert_arc",
            trigger_chapter=10,
            reason="插入弧线",
            impact_preview="扩展窗口",
            affected_chapters=[10, 11, 12],
            new_window_end=60,
            declaration=declaration,
        )

        assert request.declaration.mainline_service_reason == "服务主线原因"
        assert request.declaration.return_to_mainline_by == 20


class TestMutationResult:
    """MutationResult 数据结构测试"""

    def test_mutation_result_success(self):
        from data_modules.outline_mutation_engine import MutationResult

        result = MutationResult(
            success=True,
            adjustment_id="test-123",
            affected_chapters=[5, 6, 7],
            before_window={"start": 1, "end": 50, "version": 0},
            after_window={"start": 1, "end": 60, "version": 1},
        )

        assert result.success is True
        assert result.adjustment_id == "test-123"
        assert result.rolled_back is False
        assert result.error is None

    def test_mutation_result_rollback(self):
        from data_modules.outline_mutation_engine import MutationResult

        result = MutationResult(
            success=False,
            adjustment_id="test-456",
            error="markdown_write_failed",
            rolled_back=True,
            rollback_reason="markdown_write_failed",
        )

        assert result.success is False
        assert result.rolled_back is True
        assert result.rollback_reason == "markdown_write_failed"


class TestAdjustmentRecord:
    """AdjustmentRecord 数据结构测试"""

    def test_adjustment_record_creation(self):
        from data_modules.outline_mutation_engine import AdjustmentRecord

        record = AdjustmentRecord(
            adjustment_id="rec-001",
            status="pending",
            trigger_chapter=5,
            adjustment_type="minor_reorder",
            reason="测试",
            impact_preview="小调整",
            before_window={"start": 1, "end": 50, "version": 0},
            after_window={"start": 1, "end": 50, "version": 1},
            written_at="2026-03-29T10:00:00Z",
        )

        assert record.adjustment_id == "rec-001"
        assert record.status == "pending"
        assert record.adjustment_type == "minor_reorder"


class TestOutlineMutationEngine:
    """OutlineMutationEngine 核心逻辑测试"""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """创建临时项目"""
        from data_modules.config import DataModulesConfig

        cfg = DataModulesConfig.from_project_root(tmp_path)
        cfg.ensure_dirs()

        # 创建初始运行时文件
        runtime_file = cfg.outline_runtime_file
        runtime_data = {
            "active_volume": 1,
            "active_window_start": 1,
            "active_window_end": 50,
            "window_version": 0,
            "baseline_anchor_version": 0,
            "window_status": "active",
            "mainline_anchors": [],
            "active_nodes": [],
        }
        runtime_file.write_text(json.dumps(runtime_data, ensure_ascii=False, indent=2))

        return cfg

    @pytest.fixture
    def engine(self, temp_project):
        """创建写回引擎"""
        from data_modules.outline_mutation_engine import OutlineMutationEngine
        return OutlineMutationEngine(temp_project)

    def test_engine_initialization(self, engine, temp_project):
        """引擎初始化测试"""
        assert engine.config is not None
        assert engine.config.outline_runtime_file == temp_project.outline_runtime_file

    def test_get_window_snapshot(self, engine, temp_project):
        """窗口快照测试"""
        from data_modules.outline_runtime import load_outline_runtime

        runtime = load_outline_runtime(temp_project.outline_runtime_file)
        snapshot = engine._get_window_snapshot(runtime)

        assert snapshot["start"] == 1
        assert snapshot["end"] == 50
        assert snapshot["version"] == 0
        assert snapshot["volume"] == 1

    def test_compute_new_state_minor_reorder(self, engine, temp_project):
        """minor_reorder 状态计算"""
        from data_modules.outline_runtime import load_outline_runtime
        from data_modules.outline_mutation_engine import MutationRequest

        runtime = load_outline_runtime(temp_project.outline_runtime_file)
        request = MutationRequest(
            action_type="minor_reorder",
            trigger_chapter=10,
            reason="调整顺序",
            impact_preview="不影响窗口",
        )

        new_window, new_nodes = engine._compute_new_state(runtime, request)

        assert new_window["start"] == 1
        assert new_window["end"] == 50
        assert new_nodes == []

    def test_compute_new_state_window_extend(self, engine, temp_project):
        """window_extend 状态计算"""
        from data_modules.outline_runtime import load_outline_runtime
        from data_modules.outline_mutation_engine import MutationRequest

        runtime = load_outline_runtime(temp_project.outline_runtime_file)
        request = MutationRequest(
            action_type="window_extend",
            trigger_chapter=45,
            reason="需要扩展窗口",
            impact_preview="窗口向后扩展",
            new_window_end=70,
        )

        new_window, new_nodes = engine._compute_new_state(runtime, request)

        assert new_window["start"] == 1
        assert new_window["end"] == 70
        assert new_nodes == []

    def test_compute_new_state_insert_arc(self, engine, temp_project):
        """insert_arc 状态计算"""
        from data_modules.outline_runtime import load_outline_runtime
        from data_modules.outline_mutation_engine import MutationRequest
        from data_modules.outline_runtime import OutlineNode

        runtime = load_outline_runtime(temp_project.outline_runtime_file)
        new_arc = OutlineNode(
            chapter=55,
            title="新弧线",
            goal="目标",
            conflict="冲突",
            cost="代价",
            hook="钩子",
        )
        request = MutationRequest(
            action_type="insert_arc",
            trigger_chapter=50,
            reason="插入新弧线",
            impact_preview="添加55章新弧线",
            new_arc_node=new_arc,
        )

        new_window, new_nodes = engine._compute_new_state(runtime, request)

        assert len(new_nodes) == 1
        assert new_nodes[0].chapter == 55
        assert new_window["end"] == 50  # 默认不扩展，除非指定

    def test_execute_mutation_minor_reorder(self, engine, temp_project):
        """执行 minor_reorder 调纲"""
        from data_modules.outline_mutation_engine import MutationRequest

        request = MutationRequest(
            action_type="minor_reorder",
            trigger_chapter=10,
            reason="调整章节顺序",
            impact_preview="小调整",
        )

        result = engine.execute_mutation(request)

        assert result.success is True
        assert result.adjustment_id is not None
        assert result.before_window["version"] == 0
        assert result.after_window["version"] == 1

    def test_execute_mutation_window_extend(self, engine, temp_project):
        """执行 window_extend 调纲"""
        from data_modules.outline_mutation_engine import MutationRequest

        request = MutationRequest(
            action_type="window_extend",
            trigger_chapter=48,
            reason="窗口快到边界",
            impact_preview="扩展到70章",
            new_window_end=70,
        )

        result = engine.execute_mutation(request)

        assert result.success is True
        assert result.after_window["end"] == 70

    def test_execute_mutation_invalid_action(self, engine, temp_project):
        """无效 action_type 测试"""
        from data_modules.outline_mutation_engine import MutationRequest

        request = MutationRequest(
            action_type="invalid_action",
            trigger_chapter=10,
            reason="无效动作",
            impact_preview="",
        )

        result = engine.execute_mutation(request)

        assert result.success is False
        assert "Invalid action_type" in result.error

    def test_version_increment_on_jsonl_append(self, engine, temp_project):
        """验证 version 增长由 JSONL 追加触发"""
        from data_modules.outline_runtime import load_outline_runtime

        # 初始版本
        runtime = load_outline_runtime(temp_project.outline_runtime_file)
        assert runtime.window_version == 0

        # 执行调纲
        from data_modules.outline_mutation_engine import MutationRequest

        request = MutationRequest(
            action_type="minor_reorder",
            trigger_chapter=5,
            reason="测试",
            impact_preview="",
        )
        engine.execute_mutation(request)

        # 检查 JSONL
        jsonl_file = temp_project.outline_adjustments_file
        assert jsonl_file.exists()

        lines = jsonl_file.read_text().splitlines()
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record["after_window"]["version"] == 1

        # 检查 runtime
        runtime = load_outline_runtime(temp_project.outline_runtime_file)
        assert runtime.window_version == 1
        assert runtime.last_applied_adjustment_id == record["adjustment_id"]

    def test_atomic_write_sequence(self, engine, temp_project):
        """验证原子写顺序"""
        from data_modules.outline_mutation_engine import MutationRequest

        request = MutationRequest(
            action_type="window_extend",
            trigger_chapter=10,
            reason="测试原子性",
            impact_preview="扩展窗口",
            new_window_end=80,
        )

        result = engine.execute_mutation(request)

        assert result.success is True

        # 验证 runtime 文件存在且格式正确
        runtime_file = temp_project.outline_runtime_file
        assert runtime_file.exists()

        data = json.loads(runtime_file.read_text())
        assert data["active_window_end"] == 80

        # 验证 JSONL 有记录
        jsonl_file = temp_project.outline_adjustments_file
        assert jsonl_file.exists()

    def test_rollback_on_markdown_failure(self, engine, temp_project):
        """Markdown 写回失败时回滚 runtime"""
        from data_modules.outline_mutation_engine import MutationRequest
        from data_modules.outline_runtime import load_outline_runtime

        # 创建一个会导致 Markdown 更新失败的场景
        # 修改 engine 的 _update_markdown_outline 方法使其返回 False

        original_update = engine._update_markdown_outline

        def failing_update(*args, **kwargs):
            return False

        engine._update_markdown_outline = failing_update

        request = MutationRequest(
            action_type="window_extend",
            trigger_chapter=10,
            reason="触发回滚",
            impact_preview="会失败",
            new_window_end=90,
        )

        result = engine.execute_mutation(request)

        # 应该回滚
        assert result.success is False
        assert result.rolled_back is True

        # runtime 应该回滚到之前的状态
        runtime = load_outline_runtime(temp_project.outline_runtime_file)
        assert runtime.active_window_end == 50  # 原始值

        # JSONL 应该有 rollback 记录
        jsonl_file = temp_project.outline_adjustments_file
        lines = jsonl_file.read_text().splitlines()
        last_record = json.loads(lines[-1])
        assert last_record.get("status") == "rolled_back"

    def test_get_last_adjustment_id(self, engine, temp_project):
        """获取最后 adjustment_id"""
        from data_modules.outline_mutation_engine import MutationRequest

        # 空文件
        assert engine._get_last_adjustment_id() is None

        # 添加记录
        request = MutationRequest(
            action_type="minor_reorder",
            trigger_chapter=5,
            reason="first",
            impact_preview="",
        )
        engine.execute_mutation(request)

        last_id = engine._get_last_adjustment_id()
        assert last_id is not None
        assert len(last_id) > 0


class TestExecuteAdjustment:
    """execute_adjustment 快捷函数测试"""

    def test_execute_adjustment_basic(self, tmp_path):
        """快捷函数基本测试"""
        from data_modules.config import DataModulesConfig
        from data_modules.outline_mutation_engine import execute_adjustment, MutationRequest

        cfg = DataModulesConfig.from_project_root(tmp_path)
        cfg.ensure_dirs()

        # 初始化 runtime
        runtime_file = cfg.outline_runtime_file
        runtime_data = {
            "active_volume": 1,
            "active_window_start": 1,
            "active_window_end": 50,
            "window_version": 0,
            "baseline_anchor_version": 0,
            "window_status": "active",
            "mainline_anchors": [],
            "active_nodes": [],
        }
        runtime_file.write_text(json.dumps(runtime_data, ensure_ascii=False, indent=2))

        request = MutationRequest(
            action_type="minor_reorder",
            trigger_chapter=10,
            reason="快捷函数测试",
            impact_preview="",
        )

        result = execute_adjustment(request, cfg)

        assert result.success is True
        assert result.adjustment_id is not None


class TestCreateMutationEngine:
    """create_mutation_engine 工厂函数测试"""

    def test_create_engine_basic(self, tmp_path):
        """工厂函数基本测试"""
        from data_modules.config import DataModulesConfig
        from data_modules.outline_mutation_engine import create_mutation_engine

        cfg = DataModulesConfig.from_project_root(tmp_path)
        cfg.ensure_dirs()

        engine = create_mutation_engine(cfg)

        assert engine.config is cfg
        assert engine.anchor_manager is None

    def test_create_engine_with_anchor_manager(self, tmp_path):
        """带锚点管理器的工厂函数测试"""
        from data_modules.config import DataModulesConfig
        from data_modules.outline_mutation_engine import create_mutation_engine
        from data_modules.mainline_anchor_manager import MainlineAnchorManager

        cfg = DataModulesConfig.from_project_root(tmp_path)
        cfg.ensure_dirs()

        anchor_manager = MainlineAnchorManager(cfg)

        engine = create_mutation_engine(cfg, anchor_manager)

        assert engine.anchor_manager is anchor_manager


class TestValidActions:
    """有效动作类型测试"""

    def test_valid_actions(self):
        """验证有效动作列表"""
        from data_modules.outline_mutation_engine import OutlineMutationEngine

        assert "minor_reorder" in OutlineMutationEngine.VALID_ACTIONS
        assert "insert_arc" in OutlineMutationEngine.VALID_ACTIONS
        assert "window_extend" in OutlineMutationEngine.VALID_ACTIONS
        assert "manual_block" in OutlineMutationEngine.VALID_ACTIONS
        assert len(OutlineMutationEngine.VALID_ACTIONS) == 4


class TestWindowVersionIncrement:
    """window_version 增长规则测试"""

    def test_version_triggered_by_jsonl_append(self, tmp_path):
        """验证 version 增长由 JSONL 追加触发"""
        from data_modules.config import DataModulesConfig
        from data_modules.outline_mutation_engine import OutlineMutationEngine, MutationRequest
        from data_modules.outline_runtime import load_outline_runtime

        cfg = DataModulesConfig.from_project_root(tmp_path)
        cfg.ensure_dirs()

        # 初始化 runtime（version=0）
        runtime_file = cfg.outline_runtime_file
        runtime_data = {
            "active_volume": 1,
            "active_window_start": 1,
            "active_window_end": 50,
            "window_version": 0,
            "baseline_anchor_version": 0,
            "window_status": "active",
            "mainline_anchors": [],
            "active_nodes": [],
        }
        runtime_file.write_text(json.dumps(runtime_data, ensure_ascii=False, indent=2))

        engine = OutlineMutationEngine(cfg)

        # 执行调纲
        request = MutationRequest(
            action_type="minor_reorder",
            trigger_chapter=5,
            reason="version 测试",
            impact_preview="",
        )
        engine.execute_mutation(request)

        # 验证 JSONL 中的 version 已增长
        jsonl_file = cfg.outline_adjustments_file
        assert jsonl_file.exists()
        lines = jsonl_file.read_text().splitlines()
        record = json.loads(lines[0])
        assert record["after_window"]["version"] == 1

        # 验证 runtime 的 version 也已增长（因为原子替换）
        runtime = load_outline_runtime(runtime_file)
        assert runtime.window_version == 1

    def test_multiple_adjustments_increment_version(self, tmp_path):
        """多次调纲累加 version"""
        from data_modules.config import DataModulesConfig
        from data_modules.outline_mutation_engine import OutlineMutationEngine, MutationRequest

        cfg = DataModulesConfig.from_project_root(tmp_path)
        cfg.ensure_dirs()

        # 初始化 runtime
        runtime_file = cfg.outline_runtime_file
        runtime_data = {
            "active_volume": 1,
            "active_window_start": 1,
            "active_window_end": 50,
            "window_version": 0,
            "baseline_anchor_version": 0,
            "window_status": "active",
            "mainline_anchors": [],
            "active_nodes": [],
        }
        runtime_file.write_text(json.dumps(runtime_data, ensure_ascii=False, indent=2))

        engine = OutlineMutationEngine(cfg)

        # 第一次调纲
        request1 = MutationRequest(
            action_type="minor_reorder",
            trigger_chapter=5,
            reason="第一次",
            impact_preview="",
        )
        result1 = engine.execute_mutation(request1)
        assert result1.success is True

        # 第二次调纲
        request2 = MutationRequest(
            action_type="window_extend",
            trigger_chapter=10,
            reason="第二次",
            impact_preview="",
            new_window_end=60,
        )
        result2 = engine.execute_mutation(request2)
        assert result2.success is True

        # 验证 JSONL 有两条记录
        jsonl_file = cfg.outline_adjustments_file
        lines = jsonl_file.read_text().splitlines()
        assert len(lines) == 2

        # 验证第二条记录的 version 是 2
        record2 = json.loads(lines[1])
        assert record2["after_window"]["version"] == 2


class TestCLI:
    """CLI 接口测试"""

    def test_cli_import(self):
        """测试模块可以正常导入"""
        from data_modules import outline_mutation_engine
        assert hasattr(outline_mutation_engine, "OutlineMutationEngine")
        assert hasattr(outline_mutation_engine, "MutationRequest")
        assert hasattr(outline_mutation_engine, "MutationResult")
        assert hasattr(outline_mutation_engine, "create_mutation_engine")
        assert hasattr(outline_mutation_engine, "execute_adjustment")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
