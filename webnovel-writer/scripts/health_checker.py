# -*- coding: utf-8 -*-
"""
连载健康检查器 - v5.23

功能：定期检查连载状态一致性，发现问题并报告

使用方式：
    python health_checker.py --chapter 50
    python health_checker.py --range 1-100
    python health_checker.py --auto  # 每10章自动体检
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dataclasses import dataclass


@dataclass
class HealthIssue:
    """健康问题"""
    severity: str  # critical / high / medium / low
    category: str  # 问题类别
    description: str  # 问题描述
    location: str  # 位置
    suggestion: str  # 修复建议


@dataclass
class HealthReport:
    """健康检查报告"""
    chapter_range: Tuple[int, int]
    checked_at: str
    overall_status: str  # healthy / warning / critical
    issues: List[HealthIssue] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "high")

    @property
    def medium_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "medium")

    @property
    def low_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "low")


class HealthChecker:
    """连载健康检查器"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.webnovel_dir = self.project_root / ".webnovel"
        self.state_file = self.webnovel_dir / "state.json"
        self.index_db = self.webnovel_dir / "index.db"
        self.story_memory_file = self.webnovel_dir / "memory" / "story_memory.json"

    def check(self, start_chapter: int, end_chapter: int) -> HealthReport:
        """
        执行健康检查

        Args:
            start_chapter: 起始章节
            end_chapter: 结束章节

        Returns:
            健康报告
        """
        issues: List[HealthIssue] = []
        stats: Dict[str, Any] = {}

        # 1. 检查 state.json 的一致性
        state_issues = self._check_state_consistency(start_chapter, end_chapter)
        issues.extend(state_issues)

        # 2. 检查 index.db 与 state.json 的一致性
        index_issues = self._check_index_consistency(start_chapter, end_chapter)
        issues.extend(index_issues)

        # 3. 检查 story_memory.json 的一致性
        memory_issues = self._check_memory_consistency(start_chapter, end_chapter)
        issues.extend(memory_issues)

        # 4. 检查章节文件的存在性和连续性
        chapter_issues = self._check_chapter_continuity(start_chapter, end_chapter)
        issues.extend(chapter_issues)

        # 5. 检查伏笔回收情况
        foreshadowing_issues = self._check_foreshadowing(start_chapter, end_chapter)
        issues.extend(foreshadowing_issues)

        # 计算统计信息
        stats = self._collect_stats(start_chapter, end_chapter)

        # 确定总体状态
        if issues:
            critical_count = sum(1 for i in issues if i.severity == "critical")
            high_count = sum(1 for i in issues if i.severity == "high")
            if critical_count > 0:
                overall_status = "critical"
            elif high_count > 0:
                overall_status = "warning"
            else:
                overall_status = "healthy"
        else:
            overall_status = "healthy"

        return HealthReport(
            chapter_range=(start_chapter, end_chapter),
            checked_at=datetime.now().isoformat(),
            overall_status=overall_status,
            issues=issues,
            stats=stats,
        )

    def _check_state_consistency(self, start: int, end: int) -> List[HealthIssue]:
        """检查 state.json 的一致性"""
        issues = []

        if not self.state_file.exists():
            return [HealthIssue(
                severity="critical",
                category="STATE_MISSING",
                description="state.json 文件不存在",
                location="state.json",
                suggestion="运行初始化命令创建 state.json",
            )]

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except json.JSONDecodeError:
            return [HealthIssue(
                severity="critical",
                category="STATE_CORRUPT",
                description="state.json 文件损坏",
                location="state.json",
                suggestion="检查 state.json 文件格式",
            )]

        # 检查当前章节是否在范围内
        current_chapter = state.get("current_chapter", 0)
        if current_chapter < start or current_chapter > end:
            issues.append(HealthIssue(
                severity="medium",
                category="STATE_CHAPTER_MISMATCH",
                description=f"当前章节 {current_chapter} 不在检查范围 {start}-{end} 内",
                location="state.json",
                suggestion="更新 current_chapter 或调整检查范围",
            ))

        # 检查角色状态的一致性
        characters = state.get("characters", {})
        for char_id, char_data in characters.items():
            if not isinstance(char_data, dict):
                continue

            # 检查是否有境界越权
            realm = char_data.get("realm") or char_data.get("境界", "")
            if realm and "筑基" in str(realm):
                # 检查是否与时间线冲突
                pass

        return issues

    def _check_index_consistency(self, start: int, end: int) -> List[HealthIssue]:
        """检查 index.db 与 state.json 的一致性"""
        issues = []

        if not self.index_db.exists():
            return [HealthIssue(
                severity="medium",
                category="INDEX_MISSING",
                description="index.db 文件不存在",
                location="index.db",
                suggestion="运行索引重建命令",
            )]

        try:
            conn = sqlite3.connect(str(self.index_db))
            cursor = conn.cursor()

            # 检查实体数量一致性
            cursor.execute("SELECT COUNT(*) FROM entities")
            entity_count = cursor.fetchone()[0]

            # 检查 state.json 中的角色数量
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                char_count = len(state.get("characters", {}))

                # 允许一定误差（因为 index 可能包含已删除实体）
                if abs(entity_count - char_count) > char_count * 0.5:
                    issues.append(HealthIssue(
                        severity="low",
                        category="INDEX_ENTITIES_MISMATCH",
                        description=f"index.db 实体数 ({entity_count}) 与 state.json 角色数 ({char_count}) 差异较大",
                        location="index.db",
                        suggestion="考虑重建索引",
                    ))

            # 检查章节记录
            cursor.execute("""
                SELECT COUNT(*) FROM chapter_meta
                WHERE chapter >= ? AND chapter <= ?
            """, (start, end))
            chapter_count = cursor.fetchone()[0]
            expected_count = end - start + 1

            if chapter_count < expected_count * 0.8:
                issues.append(HealthIssue(
                    severity="medium",
                    category="INDEX_CHAPTER_MISSING",
                    description=f"index.db 中只有 {chapter_count}/{expected_count} 章的元数据",
                    location="index.db",
                    suggestion="运行索引重建命令补充缺失章节",
                ))

            conn.close()

        except sqlite3.Error as e:
            issues.append(HealthIssue(
                severity="high",
                category="INDEX_ERROR",
                description=f"index.db 读取错误: {e}",
                location="index.db",
                suggestion="检查数据库文件是否损坏",
            ))

        return issues

    def _check_memory_consistency(self, start: int, end: int) -> List[HealthIssue]:
        """检查 story_memory.json 的一致性"""
        issues = []

        if not self.story_memory_file.exists():
            return [HealthIssue(
                severity="low",
                category="MEMORY_MISSING",
                description="story_memory.json 文件不存在",
                location="story_memory.json",
                suggestion="story_memory 可能在首次写作后创建",
            )]

        try:
            with open(self.story_memory_file, 'r', encoding='utf-8') as f:
                memory = json.load(f)

            # 检查章节快照是否缺失
            snapshots = memory.get("chapter_snapshots", [])
            snapshot_chapters = set(s.get("chapter") for s in snapshots if isinstance(s, dict))

            missing_chapters = []
            for ch in range(start, end + 1):
                if ch not in snapshot_chapters and ch <= (snapshot_chapters.max() if snapshot_chapters else 0):
                    missing_chapters.append(ch)

            if missing_chapters:
                issues.append(HealthIssue(
                    severity="low",
                    category="MEMORY_SNAPSHOT_MISSING",
                    description=f"缺少 {len(missing_chapters)} 章的快照: {missing_chapters[:5]}...",
                    location="story_memory.json",
                    suggestion="继续写作会自动补充快照",
                ))

        except json.JSONDecodeError:
            issues.append(HealthIssue(
                severity="high",
                category="MEMORY_CORRUPT",
                description="story_memory.json 文件损坏",
                location="story_memory.json",
                suggestion="检查文件格式或从备份恢复",
            ))

        return issues

    def _check_chapter_continuity(self, start: int, end: int) -> List[HealthIssue]:
        """检查章节文件的连续性"""
        issues = []
        chapters_dir = self.project_root / "正文"

        if not chapters_dir.exists():
            return [HealthIssue(
                severity="critical",
                category="CHAPTER_DIR_MISSING",
                description="正文目录不存在",
                location="正文/",
                suggestion="检查项目目录结构",
            )]

        missing_chapters = []
        for ch in range(start, end + 1):
            # 尝试多种文件名格式
            chapter_file = None
            for pattern in [
                chapters_dir / f"第{ch:04d}章.md",
                chapters_dir / f"第{ch}章.md",
            ]:
                if pattern.exists():
                    chapter_file = pattern
                    break

            if not chapter_file:
                missing_chapters.append(ch)

        if missing_chapters:
            issues.append(HealthIssue(
                severity="medium",
                category="CHAPTER_MISSING",
                description=f"缺少 {len(missing_chapters)} 章文件: {missing_chapters[:5]}...",
                location="正文/",
                suggestion="检查章节文件是否被删除或重命名",
            ))

        return issues

    def _check_foreshadowing(self, start: int, end: int) -> List[HealthIssue]:
        """检查伏笔回收情况"""
        issues = []

        if not self.story_memory_file.exists():
            return issues

        try:
            with open(self.story_memory_file, 'r', encoding='utf-8') as f:
                memory = json.load(f)

            # 检查过期未回收的伏笔
            plot_threads = memory.get("plot_threads", [])
            overdue_count = 0

            for thread in plot_threads:
                if not isinstance(thread, dict):
                    continue

                status = thread.get("status", "")
                if status in ["未回收", "pending", "进行中"]:
                    due_chapter = thread.get("due_chapter") or thread.get("target_chapter", 999999)
                    if due_chapter < start:
                        overdue_count += 1

            if overdue_count > 0:
                issues.append(HealthIssue(
                    severity="medium",
                    category="FORESHADOWING_OVERDUE",
                    description=f"有 {overdue_count} 个伏笔已过期但未回收",
                    location="story_memory.json",
                    suggestion="检查是否需要回收这些伏笔",
                ))

        except (json.JSONDecodeError, IOError):
            pass

        return issues

    def _collect_stats(self, start: int, end: int) -> Dict[str, Any]:
        """收集统计信息"""
        stats = {
            "checked_chapters": end - start + 1,
            "state_file_exists": self.state_file.exists(),
            "index_db_exists": self.index_db.exists(),
            "memory_file_exists": self.story_memory_file.exists(),
        }

        # 收集章节文件信息
        chapters_dir = self.project_root / "正文"
        if chapters_dir.exists():
            chapter_files = list(chapters_dir.glob("第*.md")) + list(chapters_dir.glob("第*章.md"))
            stats["chapter_file_count"] = len(chapter_files)

        # 收集 state.json 信息
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                stats["current_chapter"] = state.get("current_chapter", 0)
                stats["character_count"] = len(state.get("characters", {}))
                stats["relationship_count"] = len(state.get("relationships", []))
            except (json.JSONDecodeError, IOError):
                pass

        return stats

    def generate_report(self, report: HealthReport) -> str:
        """生成可读的报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("连载健康检查报告")
        lines.append("=" * 60)
        lines.append(f"检查范围: 第 {report.chapter_range[0]} - {report.chapter_range[1]} 章")
        lines.append(f"检查时间: {report.checked_at}")
        lines.append(f"总体状态: {report.overall_status.upper()}")
        lines.append("")

        # 统计
        lines.append("-" * 60)
        lines.append("【统计信息】")
        lines.append("-" * 60)
        for key, value in report.stats.items():
            lines.append(f"  {key}: {value}")
        lines.append("")

        # 问题汇总
        lines.append("-" * 60)
        lines.append("【问题汇总】")
        lines.append("-" * 60)
        if report.issues:
            lines.append(f"  Critical: {report.critical_count}")
            lines.append(f"  High: {report.high_count}")
            lines.append(f"  Medium: {report.medium_count}")
            lines.append(f"  Low: {report.low_count}")
            lines.append("")

            for i, issue in enumerate(report.issues, 1):
                lines.append(f"  [{i}] {issue.category} ({issue.severity})")
                lines.append(f"      位置: {issue.location}")
                lines.append(f"      描述: {issue.description}")
                lines.append(f"      建议: {issue.suggestion}")
                lines.append("")
        else:
            lines.append("  无问题 ✓")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="连载健康检查器 v5.23")
    parser.add_argument("--project-root", default=None, help="项目根目录")
    parser.add_argument("--chapter", type=int, help="检查到指定章节")
    parser.add_argument("--range", type=str, help="检查范围，如 '1-100'")
    parser.add_argument("--auto", action="store_true", help="每10章自动体检")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题")

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

    checker = HealthChecker(project_root)

    # 确定检查范围
    if args.range:
        start, end = map(int, args.range.split('-'))
    elif args.chapter:
        # 默认检查最近 10 章
        start = max(1, args.chapter - 9)
        end = args.chapter
    elif args.auto:
        # 每 10 章自动体检
        # 从 state.json 读取当前章节
        state_file = Path(project_root) / ".webnovel" / "state.json"
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            current_chapter = state.get("current_chapter", 0)
        else:
            current_chapter = 0

        start = max(1, (current_chapter // 10) * 10 - 9)
        end = current_chapter
    else:
        print("错误: 必须指定 --chapter 或 --range 或 --auto")
        sys.exit(1)

    # 执行检查
    report = checker.check(start, end)

    if args.json:
        # 输出 JSON 格式
        output = {
            "chapter_range": list(report.chapter_range),
            "checked_at": report.checked_at,
            "overall_status": report.overall_status,
            "issue_count": {
                "critical": report.critical_count,
                "high": report.high_count,
                "medium": report.medium_count,
                "low": report.low_count,
            },
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "description": i.description,
                    "location": i.location,
                    "suggestion": i.suggestion,
                }
                for i in report.issues
            ],
            "stats": report.stats,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(checker.generate_report(report))

    # 返回适当的退出码
    if report.overall_status == "critical":
        sys.exit(2)
    elif report.overall_status == "warning":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
