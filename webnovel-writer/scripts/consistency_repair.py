# -*- coding: utf-8 -*-
"""
一致性修复脚本 - v5.23

功能：修复 state.json、index.db、story_memory.json 之间的一致性问题

使用方式：
    python consistency_repair.py --dry-run  # 只检查不修复
    python consistency_repair.py --fix       # 检查并修复
    python consistency_repair.py --full      # 完整重建索引
"""

from __future__ import annotations

import json
import re
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dataclasses import dataclass, field


@dataclass
class RepairAction:
    """修复动作"""
    target: str  # state.json / index.db / story_memory.json
    action_type: str  # create / update / delete / rebuild
    description: str
    before: Optional[Any] = None
    after: Optional[Any] = None


@dataclass
class RepairReport:
    """修复报告"""
    fixed_at: str
    actions: List[RepairAction] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def fixed_count(self) -> int:
        return len(self.actions)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class ConsistencyRepair:
    """一致性修复器"""

    def __init__(self, project_root: str, dry_run: bool = True):
        self.project_root = Path(project_root)
        self.webnovel_dir = self.project_root / ".webnovel"
        self.state_file = self.webnovel_dir / "state.json"
        self.index_db = self.webnovel_dir / "index.db"
        self.story_memory_file = self.webnovel_dir / "memory" / "story_memory.json"
        self.dry_run = dry_run

        self.state: Optional[Dict] = None
        self.index_conn: Optional[sqlite3.Connection] = None
        self.memory: Optional[Dict] = None

    def load(self) -> bool:
        """加载所有数据源"""
        try:
            # 加载 state.json
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)

            # 连接 index.db
            if self.index_db.exists():
                self.index_conn = sqlite3.connect(str(self.index_db))

            # 加载 story_memory.json
            if self.story_memory_file.exists():
                with open(self.story_memory_file, 'r', encoding='utf-8') as f:
                    self.memory = json.load(f)

            return True
        except Exception as e:
            print(f"加载数据失败: {e}")
            return False

    def close(self):
        """关闭连接"""
        if self.index_conn:
            self.index_conn.close()

    def repair(self) -> RepairReport:
        """
        执行一致性修复

        Returns:
            修复报告
        """
        report = RepairReport(fixed_at=datetime.now().isoformat())

        if not self.load():
            report.errors.append("加载数据失败")
            return report

        try:
            # 1. 修复 state.json 与 index.db 之间的不一致
            self._repair_state_index(report)

            # 2. 修复 state.json 与 story_memory 之间的不一致
            self._repair_state_memory(report)

            # 3. 修复 index.db 中的孤立实体
            self._repair_orphan_entities(report)

            # 4. 修复 story_memory 中的过期数据
            self._repair_stale_memory(report)

        finally:
            self.close()

        return report

    def _repair_state_index(self, report: RepairReport):
        """修复 state.json 与 index.db 之间的不一致"""
        if not self.state or not self.index_conn:
            return

        state_chars = set(self.state.get("characters", {}).keys())
        index_entities = self._get_index_entities()

        # 检查 index 中有但 state 中没有的实体
        for entity_id in index_entities:
            if entity_id not in state_chars:
                report.actions.append(RepairAction(
                    target="index.db",
                    action_type="delete",
                    description=f"删除孤立的实体: {entity_id}",
                    before=entity_id,
                ))
                if not self.dry_run:
                    self._delete_index_entity(entity_id)

        # 检查 state 中有但 index 中没有的实体
        for char_id in state_chars:
            if char_id not in index_entities:
                char_data = self.state["characters"][char_id]
                report.actions.append(RepairAction(
                    target="index.db",
                    action_type="create",
                    description=f"添加缺失的实体到索引: {char_id}",
                    before=None,
                    after=char_data,
                ))
                if not self.dry_run:
                    self._add_index_entity(char_id, char_data)

    def _repair_state_memory(self, report: RepairReport):
        """修复 state.json 与 story_memory 之间的不一致"""
        if not self.state or not self.memory:
            return

        # 检查 chapter_snapshots 是否缺失
        memory_snapshots = self.memory.get("chapter_snapshots", [])
        snapshot_chapters = set(s.get("chapter") for s in memory_snapshots if isinstance(s, dict))

        current_chapter = self.state.get("current_chapter", 0)

        # 补充缺失的快照
        for ch in range(1, current_chapter + 1):
            if ch not in snapshot_chapters:
                # 尝试从章节文件或 index.db 获取快照
                snapshot = self._generate_snapshot(ch)
                if snapshot:
                    report.actions.append(RepairAction(
                        target="story_memory.json",
                        action_type="create",
                        description=f"补充缺失的章节快照: 第{ch}章",
                        before=None,
                        after=snapshot,
                    ))
                    if not self.dry_run:
                        self._add_memory_snapshot(snapshot)

    def _repair_orphan_entities(self, report: RepairReport):
        """修复 index.db 中的孤立实体（没有被任何章节引用）"""
        if not self.index_conn:
            return

        cursor = self.index_conn.cursor()

        # 获取所有实体
        cursor.execute("SELECT id FROM entities")
        all_entities = set(row[0] for row in cursor.fetchall())

        # 获取所有被引用的实体
        cursor.execute("SELECT DISTINCT entity_id FROM chapter_entities")
        referenced = set(row[0] for row in cursor.fetchall())

        # 孤立实体
        orphans = all_entities - referenced

        for orphan_id in orphans:
            report.actions.append(RepairAction(
                target="index.db",
                action_type="delete",
                description=f"删除孤立实体（无章节引用）: {orphan_id}",
                before=orphan_id,
            ))
            if not self.dry_run:
                self._delete_index_entity(orphan_id)

        cursor.close()

    def _repair_stale_memory(self, report: RepairReport):
        """修复 story_memory 中的过期数据"""
        if not self.memory:
            return

        # 清理过期的 recent_events
        recent_events = self.memory.get("recent_events", [])
        if len(recent_events) > 50:
            stale = recent_events[50:]
            report.actions.append(RepairAction(
                target="story_memory.json",
                action_type="delete",
                description=f"清理 {len(stale)} 条过期的 recent_events",
                before=f"共 {len(recent_events)} 条",
                after="保留最近 50 条",
            ))
            if not self.dry_run:
                self.memory["recent_events"] = recent_events[:50]

        # 清理过期的 chapter_snapshots
        snapshots = self.memory.get("chapter_snapshots", [])
        current_chapter = self.state.get("current_chapter", 0) if self.state else 0
        if current_chapter > 100:
            # 保留最近 100 章的快照
            recent_snapshots = [s for s in snapshots if isinstance(s, dict) and s.get("chapter", 0) > current_chapter - 100]
            if len(recent_snapshots) < len(snapshots):
                removed = len(snapshots) - len(recent_snapshots)
                report.actions.append(RepairAction(
                    target="story_memory.json",
                    action_type="delete",
                    description=f"清理 {removed} 个过期的 chapter_snapshots",
                    before=f"共 {len(snapshots)} 个",
                    after=f"保留 {len(recent_snapshots)} 个",
                ))
                if not self.dry_run:
                    self.memory["chapter_snapshots"] = recent_snapshots

    def _get_index_entities(self) -> Set[str]:
        """获取 index.db 中的所有实体 ID"""
        if not self.index_conn:
            return set()

        cursor = self.index_conn.cursor()
        cursor.execute("SELECT id FROM entities")
        entities = set(row[0] for row in cursor.fetchall())
        cursor.close()
        return entities

    def _delete_index_entity(self, entity_id: str):
        """从 index.db 删除实体"""
        if not self.index_conn:
            return

        cursor = self.index_conn.cursor()
        cursor.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
        cursor.execute("DELETE FROM chapter_entities WHERE entity_id = ?", (entity_id,))
        self.index_conn.commit()
        cursor.close()

    def _add_index_entity(self, entity_id: str, entity_data: Dict):
        """添加实体到 index.db"""
        if not self.index_conn:
            return

        cursor = self.index_conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO entities (id, name, type, tier, aliases, attributes, first_appearance, last_appearance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entity_id,
            entity_data.get("name", entity_id),
            entity_data.get("type", "角色"),
            entity_data.get("tier", "装饰"),
            json.dumps(entity_data.get("aliases", []), ensure_ascii=False),
            json.dumps(entity_data.get("attributes", {}), ensure_ascii=False),
            entity_data.get("first_appearance", 0),
            entity_data.get("last_appearance", 0),
        ))
        self.index_conn.commit()
        cursor.close()

    def _generate_snapshot(self, chapter: int) -> Optional[Dict]:
        """生成章节快照"""
        # 尝试从正文文件读取
        chapters_dir = self.project_root / "正文"
        for pattern in [chapters_dir / f"第{chapter:04d}章.md", chapters_dir / f"第{chapter}章.md"]:
            if pattern.exists():
                with open(pattern, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 简单提取标题（第一个 # 后面内容）
                    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                    title = title_match.group(1) if title_match else f"第{chapter}章"

                    return {
                        "chapter": chapter,
                        "title": title,
                        "word_count": len(content),
                        "created_at": datetime.now().isoformat(),
                    }
        return None

    def _add_memory_snapshot(self, snapshot: Dict):
        """添加快照到 story_memory"""
        if not self.memory:
            return

        if "chapter_snapshots" not in self.memory:
            self.memory["chapter_snapshots"] = []

        self.memory["chapter_snapshots"].append(snapshot)

        # 保存
        with open(self.story_memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

    def generate_report(self, report: RepairReport) -> str:
        """生成可读的报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("一致性修复报告")
        lines.append("=" * 60)
        lines.append(f"执行时间: {report.fixed_at}")
        lines.append(f"模式: {'预览（dry-run）' if self.dry_run else '实际修复'}")
        lines.append("")

        if report.actions:
            lines.append("-" * 60)
            lines.append(f"【修复动作】共 {report.fixed_count} 项")
            lines.append("-" * 60)
            for i, action in enumerate(report.actions, 1):
                lines.append(f"  [{i}] {action.description}")
                lines.append(f"      目标: {action.target}, 类型: {action.action_type}")
                if action.before:
                    lines.append(f"      修复前: {str(action.before)[:50]}...")
                if action.after:
                    lines.append(f"      修复后: {str(action.after)[:50]}...")
            lines.append("")
        else:
            lines.append("  无需修复 ✓")
            lines.append("")

        if report.errors:
            lines.append("-" * 60)
            lines.append(f"【错误】共 {report.error_count} 项")
            lines.append("-" * 60)
            for i, error in enumerate(report.errors, 1):
                lines.append(f"  [{i}] {error}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="一致性修复脚本 v5.23")
    parser.add_argument("--project-root", default=None, help="项目根目录")
    parser.add_argument("--dry-run", action="store_true", default=True, help="只检查不修复（默认）")
    parser.add_argument("--fix", action="store_true", help="检查并修复")
    parser.add_argument("--full", action="store_true", help="完整重建索引")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")

    args = parser.parse_args()

    # 确定项目根目录
    if args.project_root:
        project_root = args.project_root
    else:
        from project_locator import resolve_project_root
        project_root = str(resolve_project_root())

    dry_run = not args.fix
    repair = ConsistencyRepair(project_root, dry_run=dry_run)

    print(f"正在检查一致性... ({'预览模式' if dry_run else '修复模式'})")

    report = repair.repair()

    if args.json:
        output = {
            "fixed_at": report.fixed_at,
            "mode": "dry-run" if dry_run else "fix",
            "actions": [
                {
                    "target": a.target,
                    "action_type": a.action_type,
                    "description": a.description,
                }
                for a in report.actions
            ],
            "errors": report.errors,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(repair.generate_report(report))

    # 保存修复后的 memory
    if not dry_run and report.fixed_count > 0:
        # memory 已经在 repair过程中保存
        print(f"\n已执行 {report.fixed_count} 项修复")

    if report.error_count > 0:
        sys.exit(1)
    elif report.fixed_count > 0 and dry_run:
        print("\n提示: 使用 --fix 参数实际执行修复")
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
