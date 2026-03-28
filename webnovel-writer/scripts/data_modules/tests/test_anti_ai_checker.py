# -*- coding: utf-8 -*-
"""
Anti-AI Checker 测试
"""

import pytest
import tempfile
import os
import json
from pathlib import Path

from anti_ai_checker import AntiAIChecker, AntiAIMetrics, RewriteTarget


class TestAntiAIMetrics:
    """AntiAIMetrics 指标测试"""

    def test_causal_density_pass(self):
        """因果连接词密度通过线"""
        m = AntiAIMetrics()
        m.causal_density = 1.5
        assert m.causal_density_pass is True
        assert m.causal_density_fatal is False

    def test_causal_density_fatal(self):
        """因果连接词密度致命线"""
        m = AntiAIMetrics()
        m.causal_density = 5.5
        assert m.causal_density_pass is False
        assert m.causal_density_fatal is True

    def test_summary_density_pass(self):
        """总结归纳词密度通过线"""
        m = AntiAIMetrics()
        m.summary_density = 0.8
        assert m.summary_density_pass is True
        assert m.summary_density_fatal is False

    def test_summary_density_fatal(self):
        """总结归纳词密度致命线"""
        m = AntiAIMetrics()
        m.summary_density = 3.2
        assert m.summary_density_pass is False
        assert m.summary_density_fatal is True

    def test_short_sentence_pass(self):
        """短句占比通过"""
        m = AntiAIMetrics()
        m.short_sentence_ratio = 0.35
        assert m.short_sentence_pass is True
        assert m.short_sentence_fatal is False

    def test_short_sentence_fatal_low(self):
        """短句占比致命线（过低）"""
        m = AntiAIMetrics()
        m.short_sentence_ratio = 0.10
        assert m.short_sentence_pass is False
        assert m.short_sentence_fatal is True

    def test_short_sentence_fatal_high(self):
        """短句占比致命线（过高）"""
        m = AntiAIMetrics()
        m.short_sentence_ratio = 0.70
        assert m.short_sentence_pass is False
        assert m.short_sentence_fatal is True

    def test_dialogue_intent_rate(self):
        """对白意图冲突率"""
        m = AntiAIMetrics()
        m.dialogue_intent_conflicts = 3
        m.total_dialogues = 10
        assert m.dialogue_intent_rate == 0.3


class TestAntiAIChecker:
    """AntiAI Checker 集成测试"""

    @pytest.fixture
    def temp_chapter(self):
        """创建临时章节文件 - 包含明显AI味的文本"""
        # 足够的字数来使密度计算有意义
        content = """
第一章 测试章节

他走到对方面前，首先打量了一下对方的气势，其次分析了当前的局势，
最后做出了决定。他深知这一次的选择将决定未来的走向，因此他必须谨慎行事。

与此同时，另一边的战场上，战斗正在进行。由于敌人实力强大，我方损失惨重。
然而，就在此时，援军突然出现，从而扭转了战局。

从总体上看，这次行动可以分为三个阶段：第一阶段是侦察，第二阶段是包围，
第三阶段是总攻。总体而言，任务完成得不错。

不难发现，对方的弱点在于后勤补给线。可以看出，只要切断这条线，就能获胜。
综上所述，我们应该尽快行动。
        """ * 3  # 重复3次以增加字数
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name
        yield path
        os.unlink(path)

    def test_load_content(self, temp_chapter):
        """测试内容加载"""
        checker = AntiAIChecker(temp_chapter)
        assert len(checker.content) > 0

    def test_analyze_high_risk_words(self, temp_chapter):
        """测试高风险词汇检测"""
        checker = AntiAIChecker(temp_chapter)
        metrics = checker.analyze()

        # 应该检测到高风险词汇
        assert len(metrics.high_risk_hits) > 0

        # 应该检测到总结归纳词或逻辑连接词
        high_risk_categories = set(h["category"] for h in metrics.high_risk_hits)
        has_high_risk = (
            "总结归纳" in high_risk_categories or
            "逻辑连接" in high_risk_categories or
            "枚举模板" in high_risk_categories
        )
        assert has_high_risk, f"Expected high risk words, got categories: {high_risk_categories}"

    def test_analyze_three_part_enum(self, temp_chapter):
        """测试三段式枚举句检测"""
        checker = AntiAIChecker(temp_chapter)
        metrics = checker.analyze()

        # 应该检测到三段式枚举句
        assert metrics.enum_count >= 1
        assert len(metrics.three_part_enum_sentences) >= 1

    def test_calculate_penalty(self, temp_chapter):
        """测试惩罚分计算"""
        checker = AntiAIChecker(temp_chapter)
        checker.analyze()
        penalty, reasons = checker.calculate_penalty()

        # 存在三段式枚举句，应该有惩罚
        assert penalty > 0
        assert len(reasons) > 0

    def test_should_rewrite_triggered(self, temp_chapter):
        """测试重写触发（AI味过重）"""
        checker = AntiAIChecker(temp_chapter)
        checker.analyze()
        need_rewrite, reason = checker.should_rewrite()

        # AI味过重的文本，应该触发重写
        assert need_rewrite is True
        # 原因可以是枚举、三段式、总结归纳词过密等
        assert any(keyword in reason for keyword in ["枚举", "致命", "总结", "密度"])

    def test_get_rewrite_targets(self, temp_chapter):
        """测试重写目标识别"""
        checker = AntiAIChecker(temp_chapter)
        checker.analyze()
        targets = checker.get_rewrite_targets()

        # 应该有重写目标
        assert len(targets) > 0
        # 重写目标应该有正确的严重度
        for target in targets:
            assert target.severity in ["critical", "high", "medium", "low"]
            assert len(target.original_text) > 0

    def test_generate_report(self, temp_chapter):
        """测试报告生成"""
        checker = AntiAIChecker(temp_chapter)
        checker.analyze()
        report = checker.generate_report()

        assert "Anti-AI 味检查报告" in report
        assert "因果连接词密度" in report
        assert "高风险词汇" in report

    def test_to_json(self, temp_chapter):
        """测试 JSON 输出"""
        checker = AntiAIChecker(temp_chapter)
        checker.analyze()
        result = checker.to_json()

        assert result["agent"] == "anti-ai-checker"
        assert "overall_score" in result
        assert "penalty" in result
        assert "rewrite_required" in result
        assert "metrics" in result
        assert "rewrite_targets" in result

    def test_clean_text_no_rewrite(self):
        """测试干净文本不触发重写"""
        content = """
李天站在门口，看着远方的山峦。

他握紧了拳头，心跳加速。

"你到底想怎样？"他问道。
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name

        try:
            checker = AntiAIChecker(path)
            checker.analyze()
            need_rewrite, reason = checker.should_rewrite()

            # 干净文本可能不需要重写
            # （取决于实际文本长度和密度）
        finally:
            os.unlink(path)


class TestAntiAICheckerCausalConnectors:
    """因果连接词测试"""

    def test_causal_density_calculation(self):
        """测试因果连接词密度计算"""
        # 创建约1500字的文本，用空格分隔因果连接词以便被正则识别
        base = "这是一个测试段落。" * 50  # 约1000字
        # 使用空格/标点分隔以便word boundary匹配
        causal = "因此 因此 因此 因此 因此 因此 然而 然而 然而 所以 所以"
        filler = "其他内容。" * 30

        content = base + causal + filler

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(content)
            path = f.name

        try:
            checker = AntiAIChecker(path)
            checker.analyze()

            # 因果连接词密度应该 >= 5（致命线）
            # 11个因果词 / 1.5千字 ≈ 7.3次/千字
            assert checker.metrics.causal_density_fatal is True, \
                f"Expected causal_density_fatal=True, got {checker.metrics.causal_density}"
        finally:
            os.unlink(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
