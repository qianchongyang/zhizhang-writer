# -*- coding: utf-8 -*-
"""
读者反馈模块 - v5.24

功能：支持手工输入读者反馈，反哺写作决策

使用方式：
    python reader_feedback.py --add --chapter 50 --type "钩子太弱" --content "第三章结尾的钩子不够吸引人"
    python reader_feedback.py --list --chapter 50
    python reader_feedback.py --stats
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dataclasses import dataclass


@dataclass
class Feedback:
    """读者反馈"""
    id: str
    chapter: int
    type: str  # 钩子太弱/节奏太慢/角色OOC/文笔问题/其他
    content: str
    source: str  # 读者/编辑/作者
    created_at: str
    tags: List[str] = field(default_factory=list)
    chapter_title: Optional[str] = None


@dataclass
class FeedbackStats:
    """反馈统计"""
    total_count: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_chapter: Dict[int, int] = field(default_factory=dict)
    recent_trends: List[Dict[str, Any]] = field(default_factory=list)


class ReaderFeedback:
    """读者反馈管理器"""

    FEEDBACK_DIR = "reader_feedback"
    FEEDBACK_FILE = "feedback.json"
    TEMPLATES_FILE = "serial_templates.json"

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.feedback_dir = self.project_root / ".webnovel" / self.FEEDBACK_DIR
        self.feedback_file = self.feedback_dir / self.FEEDBACK_FILE
        self.templates_file = self.feedback_dir / self.TEMPLATES_FILE

        self.feedback_dir.mkdir(parents=True, exist_ok=True)

        # 初始化文件
        if not self.feedback_file.exists():
            self._save_feedback([])
        if not self.templates_file.exists():
            self._save_templates(self._default_templates())

    # =========================================================================
    # 反馈管理
    # =========================================================================

    def add_feedback(
        self,
        chapter: int,
        feedback_type: str,
        content: str,
        source: str = "读者",
        tags: Optional[List[str]] = None,
        chapter_title: Optional[str] = None,
    ) -> Feedback:
        """
        添加反馈

        Args:
            chapter: 章节号
            feedback_type: 反馈类型
            content: 反馈内容
            source: 来源（读者/编辑/作者）
            tags: 标签
            chapter_title: 章节标题

        Returns:
            创建的反馈对象
        """
        feedbacks = self._load_feedback()

        feedback = Feedback(
            id=self._generate_id(),
            chapter=chapter,
            type=feedback_type,
            content=content,
            source=source,
            created_at=datetime.now().isoformat(),
            tags=tags or [],
            chapter_title=chapter_title,
        )

        feedbacks.append(asdict(feedback))
        self._save_feedback(feedbacks)

        return feedback

    def list_feedback(
        self,
        chapter: Optional[int] = None,
        feedback_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> List[Feedback]:
        """
        列出反馈

        Args:
            chapter: 筛选指定章节
            feedback_type: 筛选指定类型
            source: 筛选指定来源
            limit: 返回数量限制

        Returns:
            反馈列表
        """
        feedbacks = self._load_feedback()

        results = []
        for f in feedbacks:
            if chapter is not None and f.get("chapter") != chapter:
                continue
            if feedback_type is not None and f.get("type") != feedback_type:
                continue
            if source is not None and f.get("source") != source:
                continue
            results.append(Feedback(**f))

        # 按时间倒序
        results.sort(key=lambda x: x.created_at, reverse=True)

        return results[:limit]

    def get_feedback_by_chapter(self, chapter: int) -> List[Feedback]:
        """获取指定章节的所有反馈"""
        return self.list_feedback(chapter=chapter, limit=100)

    def delete_feedback(self, feedback_id: str) -> bool:
        """删除反馈"""
        feedbacks = self._load_feedback()
        original_count = len(feedbacks)

        feedbacks = [f for f in feedbacks if f.get("id") != feedback_id]

        if len(feedbacks) < original_count:
            self._save_feedback(feedbacks)
            return True
        return False

    # =========================================================================
    # 统计分析
    # =========================================================================

    def get_stats(self, recent_chapters: int = 10) -> FeedbackStats:
        """
        获取反馈统计

        Args:
            recent_chapters: 统计最近 N 章

        Returns:
            统计信息
        """
        feedbacks = self._load_feedback()

        stats = FeedbackStats()
        stats.total_count = len(feedbacks)

        # 按类型统计
        for f in feedbacks:
            ftype = f.get("type", "其他")
            stats.by_type[ftype] = stats.by_type.get(ftype, 0) + 1

        # 按章节统计
        for f in feedbacks:
            ch = f.get("chapter", 0)
            stats.by_chapter[ch] = stats.by_chapter.get(ch, 0) + 1

        # 最近趋势（按周聚合）
        weekly: Dict[str, List] = {}
        for f in feedbacks:
            created = f.get("created_at", "")
            if not created:
                continue
            # 提取周（ISO 周）
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                week_key = dt.strftime("%Y-W%W")
                if week_key not in weekly:
                    weekly[week_key] = []
                weekly[week_key].append(f)
            except (ValueError, TypeError):
                continue

        # 转换为趋势列表
        for week in sorted(weekly.keys(), reverse=True)[:8]:
            week_feedbacks = weekly[week]
            stats.recent_trends.append({
                "week": week,
                "count": len(week_feedbacks),
                "by_type": {
                    ftype: sum(1 for f in week_feedbacks if f.get("type") == ftype)
                    for ftype in set(f.get("type") for f in week_feedbacks)
                },
            })

        return stats

    def get_actionable_suggestions(self) -> List[Dict[str, Any]]:
        """
        获取可操作的建议（用于反哺写作）

        Returns:
            可操作的建议列表
        """
        feedbacks = self.list_feedback(limit=100)
        suggestions = []

        # 按类型聚合
        by_type: Dict[str, List[Feedback]] = {}
        for f in feedbacks:
            if f.type not in by_type:
                by_type[f.type] = []
            by_type[f.type].append(f)

        for ftype, type_feedbacks in by_type.items():
            if len(type_feedbacks) >= 2:
                # 同一类型出现多次，值得关注
                suggestions.append({
                    "type": ftype,
                    "count": len(type_feedbacks),
                    "chapters": list(set(f.chapter for f in type_feedbacks)),
                    "summary": f"最近有 {len(type_feedbacks)} 条关于「{ftype}」的反馈",
                    "recommendation": self._get_recommendation(ftype),
                })

        return suggestions

    def _get_recommendation(self, feedback_type: str) -> str:
        """根据反馈类型给出建议"""
        recommendations = {
            "钩子太弱": "建议加强章末钩子设计，使用「危机钩」或「渴望钩」",
            "节奏太慢": "建议减少说明性文字，增加事件密度",
            "角色OOC": "建议回顾角色设定，确保行为符合人设",
            "文笔问题": "建议使用更口语化的表达，减少总结腔",
            "其他": "建议结合具体反馈内容调整",
        }
        return recommendations.get(feedback_type, "建议根据具体反馈内容调整")

    # =========================================================================
    # 连ol模板
    # =========================================================================

    def list_templates(self) -> List[Dict[str, Any]]:
        """列出所有连载模板"""
        return self._load_templates()

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取指定模板"""
        templates = self._load_templates()
        for t in templates:
            if t.get("id") == template_id:
                return t
        return None

    def save_template(self, template: Dict[str, Any]) -> bool:
        """保存模板"""
        templates = self._load_templates()

        # 检查是否已存在
        template_id = template.get("id")
        for i, t in enumerate(templates):
            if t.get("id") == template_id:
                templates[i] = template
                self._save_templates(templates)
                return True

        # 新增
        templates.append(template)
        self._save_templates(templates)
        return True

    def delete_template(self, template_id: str) -> bool:
        """删除模板"""
        templates = self._load_templates()
        original_count = len(templates)

        templates = [t for t in templates if t.get("id") != template_id]

        if len(templates) < original_count:
            self._save_templates(templates)
            return True
        return False

    def _default_templates(self) -> List[Dict[str, Any]]:
        """默认连载模板"""
        return [
            {
                "id": "daily",
                "name": "日更模板",
                "description": "每天2-3章的日更模式",
                "chapters_per_day": 3,
                "rest_days": [5],  # 周五休息
                "target_word_count": 6000,  # 每天目标字数
                "chapters_per_week": 18,
                "hooks_per_chapter": 1,
                "micropayoff_density": "high",
                "cool_point_interval": 3,  # 每3章一个爽点
            },
            {
                "id": "weekly",
                "name": "周更模板",
                "description": "每天1章的周更模式",
                "chapters_per_day": 1,
                "rest_days": [],  # 无休息
                "target_word_count": 2500,  # 每天目标字数
                "chapters_per_week": 7,
                "hooks_per_chapter": 1,
                "micropayoff_density": "medium",
                "cool_point_interval": 5,  # 每5章一个爽点
            },
        ]

    # =========================================================================
    # 私有方法
    # =========================================================================

    def _load_feedback(self) -> List[Dict[str, Any]]:
        """加载反馈列表"""
        if not self.feedback_file.exists():
            return []
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save_feedback(self, feedbacks: List[Dict[str, Any]]):
        """保存反馈列表"""
        with open(self.feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedbacks, f, ensure_ascii=False, indent=2)

    def _load_templates(self) -> List[Dict[str, Any]]:
        """加载模板列表"""
        if not self.templates_file.exists():
            return self._default_templates()
        try:
            with open(self.templates_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return self._default_templates()

    def _save_templates(self, templates: List[Dict[str, Any]]):
        """保存模板列表"""
        with open(self.templates_file, 'w', encoding='utf-8') as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)

    def _generate_id(self) -> str:
        """生成唯一 ID"""
        import uuid
        return str(uuid.uuid4())[:8]


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="读者反馈模块 v5.24")
    parser.add_argument("--project-root", default=None, help="项目根目录")
    parser.add_argument("--add", action="store_true", help="添加反馈")
    parser.add_argument("--list", action="store_true", help="列出反馈")
    parser.add_argument("--stats", action="store_true", help="统计信息")
    parser.add_argument("--suggestions", action="store_true", help="可操作建议")
    parser.add_argument("--templates", action="store_true", help="列出模板")
    parser.add_argument("--chapter", type=int, help="章节号")
    parser.add_argument("--type", type=str, help="反馈类型")
    parser.add_argument("--content", type=str, help="反馈内容")
    parser.add_argument("--source", type=str, default="读者", help="来源")
    parser.add_argument("--delete", type=str, help="删除反馈ID")
    parser.add_argument("--json", action="store_true", help="输出JSON")

    args = parser.parse_args()

    # 确定项目根目录
    if args.project_root:
        project_root = args.project_root
    else:
        try:
            from project_locator import resolve_project_root
        except ImportError:
            from scripts.project_locator import resolve_project_root
        project_root = str(resolve_project_root())

    manager = ReaderFeedback(project_root)

    # 处理命令
    if args.add:
        if not args.type or not args.content:
            print("错误: --add 需要 --type 和 --content")
            sys.exit(1)

        feedback = manager.add_feedback(
            chapter=args.chapter or 0,
            feedback_type=args.type,
            content=args.content,
            source=args.source,
        )

        if args.json:
            print(json.dumps(asdict(feedback), ensure_ascii=False, indent=2))
        else:
            print(f"✓ 添加反馈成功 (ID: {feedback.id})")

    elif args.list:
        feedbacks = manager.list_feedback(
            chapter=args.chapter,
            feedback_type=args.type,
            source=args.source,
        )

        if args.json:
            print(json.dumps([asdict(f) for f in feedbacks], ensure_ascii=False, indent=2))
        else:
            if not feedbacks:
                print("无反馈")
            else:
                for f in feedbacks:
                    print(f"[{f.id}] 第{f.chapter}章 | {f.type} | {f.source} | {f.created_at[:10]}")
                    print(f"    {f.content[:80]}...")
                    print()

    elif args.stats:
        stats = manager.get_stats()

        if args.json:
            print(json.dumps(asdict(stats), ensure_ascii=False, indent=2))
        else:
            print("=" * 50)
            print("读者反馈统计")
            print("=" * 50)
            print(f"总反馈数: {stats.total_count}")
            print(f"按类型: {stats.by_type}")
            print(f"按章节: {stats.by_chapter}")
            print()
            print("最近趋势:")
            for trend in stats.recent_trends[:4]:
                print(f"  {trend['week']}: {trend['count']}条 {trend['by_type']}")

    elif args.suggestions:
        suggestions = manager.get_actionable_suggestions()

        if args.json:
            print(json.dumps(suggestions, ensure_ascii=False, indent=2))
        else:
            if not suggestions:
                print("暂无足够数据生成建议")
            else:
                print("=" * 50)
                print("可操作建议")
                print("=" * 50)
                for s in suggestions:
                    print(f"[{s['type']}] {s['summary']}")
                    print(f"  建议: {s['recommendation']}")
                    print(f"  涉及章节: {s['chapters']}")
                    print()

    elif args.templates:
        templates = manager.list_templates()

        if args.json:
            print(json.dumps(templates, ensure_ascii=False, indent=2))
        else:
            print("=" * 50)
            print("连载模板")
            print("=" * 50)
            for t in templates:
                print(f"[{t['id']}] {t['name']}")
                print(f"    {t['description']}")
                print(f"    日更目标: {t.get('chapters_per_day', 1)}章/天, {t.get('target_word_count', 0)}字/天")
                print()

    elif args.delete:
        if manager.delete_feedback(args.delete):
            print(f"✓ 删除反馈成功")
        else:
            print(f"✗ 未找到反馈: {args.delete}")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
