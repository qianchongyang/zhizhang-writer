# -*- coding: utf-8 -*-
"""
Anti-AI Checker v5.21 - 去AI味指标检测器

功能：检测文本中的 AI 味痕迹，计算惩罚分，触发局部重写

基于 polish-guide.md 的 7 层 Anti-AI 规则体系

使用方法：
    python anti_ai_checker.py --chapter 123
    python anti_ai_checker.py --chapter 123 --json
    python anti_ai_checker.py --chapter 123 --focus-layer 1
"""

from __future__ import annotations

import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# ============================================================================
# 7 层 Anti-AI 规则定义
# ============================================================================

# 第1层：高风险词汇（按类别分组）
_HIGH_RISK_WORDS: Dict[str, List[str]] = {
    # A. 总结归纳词（22）
    "总结归纳": [
        "综合", "总之", "总而言之", "由此可见", "可以看出", "不难发现",
        "归根结底", "说到底", "总体来看", "从这个角度看", "换句话说",
        "简而言之", "概括来说", "可以说", "由此得出", "结论是",
        "最终可知", "总的来说", "总括起来", "整体而言", "总体上", "综上",
    ],
    # B. 枚举模板词（24）
    "枚举模板": [
        "首先", "其次", "再次", "最后", "第一", "第二", "第三",
        "其一", "其二", "其三", "一方面", "另一方面", "再者",
        "此外", "另外", "同时", "接着", "然后", "随后",
        "紧接着", "最后一步", "下一步", "第一点", "第二点",
    ],
    # C. 书面学术腔（24）
    "书面学术腔": [
        "某种程度上", "本质上", "意义上", "维度上", "层面上",
        "在于", "体现为", "构成了", "形成了", "实现了", "完成了",
        "进行了", "展开了", "推动了", "促进了", "提供了", "具备了",
        "拥有了", "达成了", "呈现出", "表现出", "反映出", "蕴含着", "折射出",
    ],
    # D. 逻辑连接滥用词（22）
    "逻辑连接": [
        "因此", "因而", "所以", "由于", "然而", "不过", "但是",
        "与此同时", "同样地", "对应地", "相应地", "进一步", "更进一步",
        "从而", "进而", "于是", "结果是", "于是乎", "故而", "由此",
        "相较之下", "反过来说",
    ],
    # E. 情绪直述词（22）
    "情绪直述": [
        "非常愤怒", "非常开心", "非常难过", "心中五味杂陈", "百感交集",
        "情绪复杂", "内心震撼", "不由得感慨", "感到无奈", "感到痛苦",
        "感到欣慰", "感到恐惧", "深受触动", "心潮起伏", "心情沉重",
        "心情复杂", "心里一暖", "心里一沉", "心中一紧", "不禁一愣",
        "不由一怔", "内心一震",
    ],
    # F. 动作套话（22）
    "动作套话": [
        "皱起眉头", "叹了口气", "深吸一口气", "缓缓开口", "沉声说道",
        "淡淡说道", "冷冷说道", "轻声说道", "嘴角上扬", "嘴角抽了抽",
        "眼神一凝", "目光一闪", "身形一滞", "脚步一顿", "浑身一震",
        "心头一跳", "不由自主后退半步", "猛地转身", "抬手一挥",
        "缓缓点头", "轻轻摇头", "下意识后退",
    ],
    # G. 环境套话（22）
    "环境套话": [
        "空气仿佛凝固", "气氛骤然紧张", "气压陡然下降", "夜色如墨",
        "月色如水", "寒风刺骨", "四周一片寂静", "死一般的寂静",
        "时间仿佛静止", "空间仿佛扭曲", "房间里弥漫着", "唯一的光源",
        "摇摇欲坠", "压抑得让人喘不过气", "沉默像潮水", "空气中充满了",
        "一切都显得", "世界仿佛", "就在这一刻", "忽然之间", "刹那间", "顷刻之间",
    ],
    # H. 叙事填充词（22）
    "叙事填充": [
        "事实上", "实际上", "某种意义上", "严格来说", "客观而言",
        "主观上", "一般来说", "通常情况下", "在这种情况下", "在这个时候",
        "在此基础上", "在这个意义上", "从某种角度", "对于他来说",
        "对她而言", "这意味着", "这说明", "这代表着", "这并不奇怪",
        "并非偶然", "不可否认", "毋庸置疑",
    ],
    # I. 抽象空泛词（22）
    "抽象空泛": [
        "命运", "成长", "蜕变", "升华", "价值", "意义", "抉择",
        "坚持", "信念", "初心", "希望", "绝望", "勇气", "正义",
        "邪恶", "真实", "虚伪", "复杂", "深刻", "宏大", "渺小", "沉重",
    ],
    # J. 机械开场/收尾词（24）
    "机械开场收尾": [
        "故事要从", "让我们把视线", "镜头转到", "与此同时在另一边",
        "回到现在", "再说回", "这一切都要从", "他并不知道",
        "命运的齿轮开始转动", "新的篇章开始了", "未完待续",
        "故事才刚刚开始", "真正的考验还在后面", "一场风暴即将来临",
        "更大的阴谋正在酝酿", "这只是开始", "答案尚未揭晓",
        "未来会怎样", "谁也不知道", "他深知", "她明白",
        "可他不知道的是", "可她不知道的是", "然而一切才刚开始",
    ],
}

# 第8层：中文AI高频词汇黑名单（网文特有问题）
_AI_BLACKLIST_WORDS = [
    "此外", "至关重要", "深入探讨", "强调", "持久的", "增强",
    "培养", "获得", "突出", "相互作用", "复杂", "复杂性",
    "格局", "关键性的", "展示", "证明", "宝贵的", "充满活力的",
]

# 所有高风险词汇合并
_ALL_HIGH_RISK_WORDS: List[str] = []
for words in _HIGH_RISK_WORDS.values():
    _ALL_HIGH_RISK_WORDS.extend(words)
_ALL_HIGH_RISK_WORDS.extend(_AI_BLACKLIST_WORDS)


# ============================================================================
# 量化阈值定义
# ============================================================================

@dataclass
class AntiAIMetrics:
    """Anti-AI 指标结果"""
    # 密度指标（次/千字）
    causal_density: float = 0.0        # 因果连接词密度
    summary_density: float = 0.0       # 总结归纳词密度
    enum_count: int = 0                 # 三段式枚举句数量

    # 占比指标
    short_sentence_ratio: float = 0.0   # 短句(≤10字)占比
    pause_word_density: float = 0.0     # 停顿词密度

    # 计数指标
    physiological_reactions: int = 0    # 生理反应描写处数
    dialogue_intent_conflicts: int = 0   # 有意图冲突的对白数
    total_dialogues: int = 0             # 总对白数

    # 高风险命中
    high_risk_hits: List[Dict[str, Any]] = field(default_factory=list)
    three_part_enum_sentences: List[str] = field(default_factory=list)

    # 派生属性
    @property
    def dialogue_intent_rate(self) -> float:
        """对白意图冲突率"""
        if self.total_dialogues == 0:
            return 1.0
        return self.dialogue_intent_conflicts / self.total_dialogues

    @property
    def causal_density_pass(self) -> bool:
        return self.causal_density <= 2.0

    @property
    def causal_density_fatal(self) -> bool:
        return self.causal_density >= 5.0

    @property
    def summary_density_pass(self) -> bool:
        return self.summary_density <= 1.0

    @property
    def summary_density_fatal(self) -> bool:
        return self.summary_density >= 3.0

    @property
    def short_sentence_pass(self) -> bool:
        return 0.25 <= self.short_sentence_ratio <= 0.45

    @property
    def short_sentence_fatal(self) -> bool:
        return self.short_sentence_ratio < 0.15 or self.short_sentence_ratio > 0.60

    @property
    def pause_word_pass(self) -> bool:
        return 1.0 <= self.pause_word_density <= 2.0

    @property
    def pause_word_fatal(self) -> bool:
        return self.pause_word_density < 0.5

    @property
    def enum_pass(self) -> bool:
        return self.enum_count == 0

    @property
    def enum_fatal(self) -> bool:
        return self.enum_count >= 1

    @property
    def physiology_pass(self) -> bool:
        return self.physiological_reactions >= 1


@dataclass
class RewriteTarget:
    """局部重写目标"""
    location: str          # 位置描述（如"第3段"、"第5-7句"）
    original_text: str      # 原始文本（最多200字）
    issue_type: str         # 问题类型：HIGH_RISK_WORD / ENUM_PATTERN / etc.
    severity: str           # 严重度：critical / high / medium
    rewrite_hint: str       # 改写提示


# ============================================================================
# Anti-AI Checker 主类
# ============================================================================

class AntiAIChecker:
    """Anti-AI 味检测器"""

    # 因果连接词（用于密度计算）
    CAUSAL_CONNECTORS = {"因此", "然而", "所以", "由于", "因而", "从而", "于是", "故而"}

    # 停顿词
    PAUSE_WORDS = {"……", "...", "——", "——", "～"}

    # 短句阈值
    SHORT_SENTENCE_THRESHOLD = 10

    def __init__(self, chapter_file: str):
        """
        初始化检测器

        Args:
            chapter_file: 章节文件路径
        """
        self.chapter_file = chapter_file
        self.content: str = ""
        self.metrics: Optional[AntiAIMetrics] = None
        self._load_content()

    def _load_content(self) -> None:
        """加载章节内容"""
        path = Path(self.chapter_file)
        if not path.exists():
            raise FileNotFoundError(f"章节文件不存在: {self.chapter_file}")

        with open(path, 'r', encoding='utf-8') as f:
            self.content = f.read()

    def _count_words(self, text: str) -> int:
        """统计字数（去除空白）"""
        return len(re.sub(r'\s+', '', text))

    def _split_sentences(self, text: str) -> List[str]:
        """拆分句子"""
        # 按常见句子结束符拆分
        sentences = re.split(r'[。！？\n]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _split_paragraphs(self, text: str) -> List[str]:
        """拆分段落"""
        return [p.strip() for p in text.split('\n\n') if p.strip()]

    def _detect_high_risk_words(self) -> List[Dict[str, Any]]:
        """检测高风险词汇"""
        hits = []
        for word in _ALL_HIGH_RISK_WORDS:
            # 使用单词边界匹配
            pattern = rf'\b{re.escape(word)}\b'
            matches = list(re.finditer(pattern, self.content))
            if matches:
                for match in matches:
                    # 获取上下文（前后50字）
                    start = max(0, match.start() - 50)
                    end = min(len(self.content), match.end() + 50)
                    context = self.content[start:end]

                    # 分类
                    category = "其他"
                    for cat, words in _HIGH_RISK_WORDS.items():
                        if word in words:
                            category = cat
                            break
                    if word in _AI_BLACKLIST_WORDS and category == "其他":
                        category = "AI黑名单"

                    hits.append({
                        "word": word,
                        "category": category,
                        "position": match.start(),
                        "context": context,
                    })
        return hits

    def _detect_three_part_enum(self) -> List[str]:
        """检测三段式枚举句（首先/其次/最后）"""
        sentences = self._split_sentences(self.content)
        enum_sentences = []

        for sentence in sentences:
            # 检测是否包含"首先"、"其次"、"最后"序列
            has_first = bool(re.search(r'首先', sentence))
            has_second = bool(re.search(r'其次', sentence))
            has_last = bool(re.search(r'最后', sentence))

            if has_first and has_second and has_last:
                enum_sentences.append(sentence[:100] + "..." if len(sentence) > 100 else sentence)
            elif has_first and has_second:
                enum_sentences.append(sentence[:100] + "..." if len(sentence) > 100 else sentence)
            elif has_first and has_last:
                enum_sentences.append(sentence[:100] + "..." if len(sentence) > 100 else sentence)

        return enum_sentences

    def _count_causal_connectors(self) -> int:
        """统计因果连接词"""
        count = 0
        for connector in self.CAUSAL_CONNECTORS:
            count += len(re.findall(rf'\b{connector}\b', self.content))
        return count

    def _count_summary_words(self) -> int:
        """统计总结归纳词"""
        count = 0
        for word in _HIGH_RISK_WORDS["总结归纳"]:
            count += len(re.findall(rf'\b{word}\b', self.content))
        return count

    def _count_pause_words(self) -> int:
        """统计停顿词"""
        count = 0
        for pause in self.PAUSE_WORDS:
            count += self.content.count(pause)
        return count

    def _calculate_short_sentence_ratio(self) -> float:
        """计算短句占比"""
        sentences = self._split_sentences(self.content)
        if not sentences:
            return 0.0

        short_count = sum(1 for s in sentences if self._count_words(s) <= self.SHORT_SENTENCE_THRESHOLD)
        return short_count / len(sentences)

    def _detect_physiological_reactions(self) -> int:
        """检测生理反应描写"""
        # 常见的生理反应关键词
        physiological_keywords = [
            "手心", "额头", "后背", "脊背", "喉咙", "指尖",
            "心跳", "呼吸", "屏住", "攥紧", "指节", "掌心",
            "发紧", "发麻", "发烫", "发白", "发青",
        ]

        count = 0
        paragraphs = self._split_paragraphs(self.content)
        for para in paragraphs:
            if any(kw in para for kw in physiological_keywords):
                count += 1
        return count

    def _detect_dialogue_intents(self) -> Tuple[int, int]:
        """检测对白意图冲突"""
        # 提取所有对白
        dialogues = re.findall(r'"([^"]+)"|"([^"]+)"|『([^』]+)』', self.content)

        total = len(dialogues)
        conflicts = 0

        # 对白意图冲突的特征：
        # 1. 问号结尾但没有任何问询词（反问/质问）
        # 2. 感叹号但上下文没有情绪铺垫
        # 3. 连续短句对白（争吵/对峙）

        for dialogue in dialogues:
            text = dialogue[0] or dialogue[1] or dialogue[2]  # 提取实际文本
            text = text.strip()

            if not text:
                continue

            # 检测反问/质问（意图冲突）
            if text.endswith('?') or text.endswith('？') or '?' in text:
                # 有问号但没有明确的问询词
                if not any(w in text for w in ['吗', '呢', '怎么', '为什么', '是不是', '要不要']):
                    conflicts += 1
            # 检测短句对峙
            elif len(text) < 15 and ('！' in text or '!' in text or '。' not in text):
                conflicts += 1

        return conflicts, total

    def analyze(self) -> AntiAIMetrics:
        """执行完整分析"""
        metrics = AntiAIMetrics()
        word_count = self._count_words(self.content)
        thousand_chars = word_count / 1000

        # 1. 高风险词汇检测
        metrics.high_risk_hits = self._detect_high_risk_words()

        # 2. 三段式枚举句
        metrics.three_part_enum_sentences = self._detect_three_part_enum()
        metrics.enum_count = len(metrics.three_part_enum_sentences)

        # 3. 因果连接词密度
        causal_count = self._count_causal_connectors()
        metrics.causal_density = causal_count / thousand_chars if thousand_chars > 0 else 0

        # 4. 总结归纳词密度
        summary_count = self._count_summary_words()
        metrics.summary_density = summary_count / thousand_chars if thousand_chars > 0 else 0

        # 5. 停顿词密度（/500字）
        pause_count = self._count_pause_words()
        five_hundred_chars = word_count / 500
        metrics.pause_word_density = pause_count / five_hundred_chars if five_hundred_chars > 0 else 0

        # 6. 短句占比
        metrics.short_sentence_ratio = self._calculate_short_sentence_ratio()

        # 7. 生理反应描写
        metrics.physiological_reactions = self._detect_physiological_reactions()

        # 8. 对白意图冲突
        conflicts, total = self._detect_dialogue_intents()
        metrics.dialogue_intent_conflicts = conflicts
        metrics.total_dialogues = total

        self.metrics = metrics
        return metrics

    def calculate_penalty(self) -> Tuple[int, List[str]]:
        """
        计算 AI 味惩罚分

        Returns:
            (惩罚分, 原因列表)
        """
        if self.metrics is None:
            self.analyze()

        penalty = 0
        reasons = []

        # 致命线 - 每项扣15分
        fatal_hits = 0
        if self.metrics.causal_density_fatal:
            fatal_hits += 1
            reasons.append(f"因果连接词密度过高 ({self.metrics.causal_density:.1f}次/千字)")
        if self.metrics.summary_density_fatal:
            fatal_hits += 1
            reasons.append(f"总结归纳词密度过高 ({self.metrics.summary_density:.1f}次/千字)")
        if self.metrics.enum_fatal:
            fatal_hits += 1
            reasons.append(f"存在三段式枚举句 ({self.metrics.enum_count}处)")
        if self.metrics.short_sentence_fatal:
            fatal_hits += 1
            reasons.append(f"短句占比异常 ({self.metrics.short_sentence_ratio:.1%})")

        penalty += fatal_hits * 15

        # 通过线命中 - 每项扣5分
        pass_hits = 0
        if not self.metrics.causal_density_pass and not self.metrics.causal_density_fatal:
            pass_hits += 1
            reasons.append(f"因果连接词密度偏高 ({self.metrics.causal_density:.1f}次/千字)")
        if not self.metrics.summary_density_pass and not self.metrics.summary_density_fatal:
            pass_hits += 1
            reasons.append(f"总结归纳词密度偏高 ({self.metrics.summary_density:.1f}次/千字)")
        if not self.metrics.pause_word_pass and not self.metrics.pause_word_fatal:
            pass_hits += 1
            reasons.append(f"停顿词密度不足 ({self.metrics.pause_word_density:.1f}次/500字)")
        if not self.metrics.physiology_pass:
            pass_hits += 1
            reasons.append(f"生理反应描写不足 ({self.metrics.physiological_reactions}处)")

        penalty += pass_hits * 5

        # 高风险词汇命中 - 每5个扣3分
        high_risk_penalty = (len(self.metrics.high_risk_hits) // 5) * 3
        penalty += high_risk_penalty
        if high_risk_penalty > 0:
            reasons.append(f"高风险词汇命中 {len(self.metrics.high_risk_hits)} 处")

        # 封顶惩罚分为30分
        penalty = min(penalty, 30)

        return penalty, reasons

    def should_rewrite(self) -> Tuple[bool, str]:
        """
        判断是否需要触发局部重写

        Returns:
            (是否需要重写, 原因)
        """
        if self.metrics is None:
            self.analyze()

        # 致命线命中 >= 1 项
        if self.metrics.causal_density_fatal:
            return True, "因果连接词密度超过致命线"
        if self.metrics.summary_density_fatal:
            return True, "总结归纳词密度超过致命线"
        if self.metrics.enum_fatal:
            return True, "存在三段式枚举句"
        if self.metrics.short_sentence_fatal:
            return True, "短句占比超过致命线"

        # 通过线命中 >= 3 项
        pass_hits = 0
        if not self.metrics.causal_density_pass:
            pass_hits += 1
        if not self.metrics.summary_density_pass:
            pass_hits += 1
        if not self.metrics.pause_word_pass:
            pass_hits += 1
        if not self.metrics.physiology_pass:
            pass_hits += 1

        if pass_hits >= 3:
            return True, f"通过线命中 {pass_hits} 项"

        # 高风险词汇命中 >= 10 处
        if len(self.metrics.high_risk_hits) >= 10:
            return True, f"高风险词汇命中 {len(self.metrics.high_risk_hits)} 处"

        return False, "无需重写"

    def get_rewrite_targets(self) -> List[RewriteTarget]:
        """
        获取需要局部重写的目标列表

        Returns:
            RewriteTarget 列表，按严重度降序排列
        """
        if self.metrics is None:
            self.analyze()

        targets: List[RewriteTarget] = []

        # 1. 高风险词汇命中 - 提取上下文作为重写目标
        for i, hit in enumerate(self.metrics.high_risk_hits[:20]):  # 最多20个
            pos = hit["position"]
            # 获取前后各50字的上下文
            start = max(0, pos - 50)
            end = min(len(self.content), pos + len(hit["word"]) + 50)
            context = self.content[start:end]

            targets.append(RewriteTarget(
                location=f"高风险词 #{i+1} (第{pos}字附近)",
                original_text=context,
                issue_type=f"HIGH_RISK_{hit['category']}",
                severity="high" if hit["category"] in ["枚举模板", "总结归纳", "逻辑连接"] else "medium",
                rewrite_hint=f"替换高风险词「{hit['word']}」为更自然的表达",
            ))

        # 2. 三段式枚举句
        paragraphs = self._split_paragraphs(self.content)
        for i, enum_sent in enumerate(self.metrics.three_part_enum_sentences):
            # 找到包含该枚举句的段落
            para_idx = -1
            for j, para in enumerate(paragraphs):
                if enum_sent[:50] in para:
                    para_idx = j
                    break

            targets.append(RewriteTarget(
                location=f"第{para_idx+1}段" if para_idx >= 0 else "全文",
                original_text=enum_sent[:200] + "..." if len(enum_sent) > 200 else enum_sent,
                issue_type="THREE_PART_ENUM",
                severity="critical",
                rewrite_hint="将三段式枚举改为更自然的叙事节奏",
            ))

        # 3. 按严重度排序
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        targets.sort(key=lambda t: severity_order.get(t.severity, 3))

        return targets

    def generate_report(self) -> str:
        """生成检查报告"""
        if self.metrics is None:
            self.analyze()

        penalty, reasons = self.calculate_penalty()
        need_rewrite, rewrite_reason = self.should_rewrite()

        report = []
        report.append("=" * 60)
        report.append("Anti-AI 味检查报告")
        report.append("=" * 60)
        report.append(f"\n章节文件: {self.chapter_file}")
        report.append(f"字数: {self._count_words(self.content)}")

        # 量化指标
        report.append("\n" + "-" * 60)
        report.append("【量化指标】")
        report.append("-" * 60)

        m = self.metrics
        report.append(f"因果连接词密度: {m.causal_density:.2f}次/千字 "
                     f"[{'✅' if m.causal_density_pass else '⚠️' if not m.causal_density_fatal else '❌'}]")
        report.append(f"总结归纳词密度: {m.summary_density:.2f}次/千字 "
                     f"[{'✅' if m.summary_density_pass else '⚠️' if not m.summary_density_fatal else '❌'}]")
        report.append(f"停顿词密度: {m.pause_word_density:.2f}次/500字 "
                     f"[{'✅' if m.pause_word_pass else '⚠️' if not m.pause_word_fatal else '❌'}]")
        report.append(f"短句占比: {m.short_sentence_ratio:.1%} "
                     f"[{'✅' if m.short_sentence_pass else '⚠️' if not m.short_sentence_fatal else '❌'}]")
        report.append(f"三段式枚举句: {m.enum_count}处 "
                     f"[{'✅' if m.enum_pass else '❌'}]")
        report.append(f"生理反应描写: {m.physiological_reactions}处 "
                     f"[{'✅' if m.physiology_pass else '❌'}]")
        report.append(f"对白意图冲突率: {m.dialogue_intent_rate:.1%} ({m.dialogue_intent_conflicts}/{m.total_dialogues})")

        # 高风险词汇统计
        report.append("\n" + "-" * 60)
        report.append("【高风险词汇统计】")
        report.append("-" * 60)
        category_counts: Dict[str, int] = {}
        for hit in m.high_risk_hits:
            cat = hit["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1

        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            report.append(f"  {cat}: {count}处")

        if m.high_risk_hits:
            report.append(f"\n总计高风险词汇: {len(m.high_risk_hits)} 处")

        # 惩罚分
        report.append("\n" + "-" * 60)
        report.append("【AI味惩罚分】")
        report.append("-" * 60)
        report.append(f"惩罚总分: {penalty}/30")

        if reasons:
            report.append("\n扣分原因:")
            for reason in reasons:
                report.append(f"  - {reason}")
        else:
            report.append("无")

        # 重写建议
        report.append("\n" + "-" * 60)
        report.append("【重写判断】")
        report.append("-" * 60)
        report.append(f"{'⚠️ 需要局部重写' if need_rewrite else '✅ 无需重写'}")
        if need_rewrite:
            report.append(f"原因: {rewrite_reason}")

        report.append("\n" + "=" * 60)
        return "\n".join(report)

    def to_json(self) -> Dict[str, Any]:
        """输出 JSON 格式结果"""
        if self.metrics is None:
            self.analyze()

        penalty, reasons = self.calculate_penalty()
        need_rewrite, rewrite_reason = self.should_rewrite()
        rewrite_targets = self.get_rewrite_targets() if need_rewrite else []

        return {
            "agent": "anti-ai-checker",
            "chapter": self._extract_chapter_number(),
            "overall_score": max(0, 100 - penalty),
            "pass": not need_rewrite,
            "issues": self._generate_issues(reasons),
            "metrics": {
                "causal_density": round(self.metrics.causal_density, 2),
                "summary_density": round(self.metrics.summary_density, 2),
                "pause_word_density": round(self.metrics.pause_word_density, 2),
                "short_sentence_ratio": round(self.metrics.short_sentence_ratio, 2),
                "enum_count": self.metrics.enum_count,
                "physiological_reactions": self.metrics.physiological_reactions,
                "dialogue_intent_rate": round(self.metrics.dialogue_intent_rate, 2),
                "high_risk_word_count": len(self.metrics.high_risk_hits),
            },
            "penalty": penalty,
            "rewrite_required": need_rewrite,
            "rewrite_reason": rewrite_reason,
            "rewrite_targets": [
                {
                    "location": t.location,
                    "original_text": t.original_text,
                    "issue_type": t.issue_type,
                    "severity": t.severity,
                    "rewrite_hint": t.rewrite_hint,
                }
                for t in rewrite_targets
            ],
            "summary": f"AI味惩罚分: {penalty}/30, {'需要重写' if need_rewrite else '通过'}",
        }

    def _extract_chapter_number(self) -> int:
        """从文件名提取章节号"""
        match = re.search(r'第(\d+)章', self.chapter_file)
        return int(match.group(1)) if match else 0

    def _generate_issues(self, reasons: List[str]) -> List[Dict[str, Any]]:
        """生成 issues 列表"""
        issues = []
        for i, reason in enumerate(reasons):
            issues.append({
                "id": f"ANTI_AI_{i+1:03d}",
                "type": "AI_FLAVOR",
                "severity": "high" if "致命" in reason or "枚举" in reason else "medium",
                "location": "全文",
                "description": reason,
                "suggestion": "按 Anti-AI 改写算法处理",
                "can_override": False,
            })
        return issues


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Anti-AI 味检查工具 v5.21",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python anti_ai_checker.py --chapter 123
  python anti_ai_checker.py --chapter 123 --json
  python anti_ai_checker.py --chapter 123 --file "正文/第0123章-标题.md"
        """.strip(),
    )

    parser.add_argument("--chapter", type=int, help="章节号（自动定位文件）")
    parser.add_argument("--file", type=str, help="章节文件路径（优先级高于 --chapter）")
    parser.add_argument("--project-root", type=str, default=None, help="项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--focus-layer", type=int, choices=[1, 2, 3, 4, 5, 6, 7, 8],
                       help="聚焦特定层级检查")

    args = parser.parse_args()

    # 定位章节文件
    if args.file:
        chapter_file = args.file
    elif args.chapter:
        # 尝试多种可能的文件名格式
        project_root = args.project_root or Path.cwd()
        patterns = [
            Path(project_root) / "正文" / f"第{args.chapter:04d}章.md",
            Path(project_root) / "正文" / f"第{args.chapter}章.md",
            Path(project_root) / f"第{args.chapter:04d}章.md",
        ]
        chapter_file = None
        for pattern in patterns:
            if pattern.exists():
                chapter_file = str(pattern)
                break

        if not chapter_file:
            print(f"❌ 找不到第 {args.chapter} 章文件")
            print(f"   尝试了以下路径:")
            for p in patterns:
                print(f"   - {p}")
            exit(1)
    else:
        print("❌ 必须指定 --chapter 或 --file")
        exit(1)

    # 执行检查
    try:
        checker = AntiAIChecker(chapter_file)
        checker.analyze()

        if args.json:
            result = checker.to_json()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(checker.generate_report())

    except FileNotFoundError as e:
        print(f"❌ {e}")
        exit(1)
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
