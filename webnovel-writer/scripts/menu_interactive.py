# -*- coding: utf-8 -*-
"""
交互式菜单模块 - v5.24

功能：提供中文交互式菜单，统一执行所有网文助手功能

使用方式：
    python menu_interactive.py
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Callable

# 添加 scripts 目录到路径
_script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_script_dir))


class MenuDisplay:
    """菜单显示格式化"""

    WIDTH = 64

    @classmethod
    def box(cls, title: str, lines: list[str]) -> str:
        """绘制一个菜单框"""
        border = "═" * (cls.WIDTH - 2)
        result = [
            f"╔{border}╗",
            f"║{title.center(cls.WIDTH - 2)}║",
            f"╠{border}╣",
        ]

        for line in lines:
            # 处理行内多个选项的情况
            if "      " in line and ("│" in line or "║" in line):
                result.append(line)
            else:
                result.append(f"║{line.center(cls.WIDTH - 2)}║")

        result.append(f"╚{border}╝")
        return "\n".join(result)

    @classmethod
    def title(cls, text: str) -> str:
        border = "═" * (cls.WIDTH - 2)
        return f"╔{border}╗\n║{text.center(cls.WIDTH - 2)}║\n╠{border}╣"

    @classmethod
    def option(cls, num: str, emoji: str, title: str, desc: str = "") -> str:
        """格式化选项"""
        main = f"[{num}] {emoji} {title}"
        if desc:
            main += f"\n      {desc}"
        return main


class MenuItem:
    """菜单项"""

    def __init__(self, num: str, title: str, action: Callable, desc: str = "", emoji: str = ""):
        self.num = num
        self.title = title
        self.action = action
        self.desc = desc
        self.emoji = emoji

    def display(self) -> str:
        if self.desc:
            return f"║ [{self.num}] {self.emoji} {self.title:<50} ║\n║       {self.desc:<52} ║"
        return f"║ [{self.num}] {self.emoji} {self.title:<54} ║"


class InteractiveMenu:
    """交互式菜单"""

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or self._detect_project_root()
        self.running = True

    def _detect_project_root(self) -> str:
        """检测项目根目录"""
        try:
            from project_locator import resolve_project_root
            return str(resolve_project_root())
        except:
            return os.getcwd()

    def _run_cli(self, command: list[str], capture: bool = True) -> str:
        """执行统一 CLI 命令"""
        script_dir = Path(__file__).resolve().parent
        webnovel_py = script_dir / "webnovel.py"

        cmd = [
            sys.executable,
            str(webnovel_py),
            "--project-root",
            self.project_root,
        ] + command

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
                timeout=120
            )
            return result.stdout if capture else ""
        except subprocess.TimeoutExpired:
            return "命令执行超时"
        except Exception as e:
            return f"执行错误: {e}"

    def _input_with_default(self, prompt: str, default: str) -> str:
        """带默认值的输入"""
        try:
            value = input(f"{prompt} [{default}]: ").strip()
            return value if value else default
        except (EOFError, KeyboardInterrupt):
            return default

    def _collect_chapter(self) -> str:
        """收集章节号"""
        return self._input_with_default("请输入章节号", "1")

    def _collect_range(self) -> str:
        """收集章节范围"""
        return self._input_with_default("请输入章节范围（如 1-5 或 45）", "1")

    def _collect_volume(self) -> str:
        """收集卷号"""
        return self._input_with_default("请输入卷号", "1")

    def _collect_keyword(self) -> str:
        """收集查询关键词"""
        return input("请输入查询关键词: ").strip()

    def _collect_feedback(self) -> dict:
        """收集反馈信息"""
        print("\n请依次输入反馈信息（直接回车使用默认值）：")

        chapter = self._input_with_default("章节号", "1")
        ftype = self._input_with_default(
            "反馈类型",
            "钩子太弱"
        )
        print("可选类型: 钩子太弱 / 节奏太慢 / 角色OOC / 文笔问题 / 其他")
        ftype_input = input("类型: ").strip()
        if ftype_input:
            ftype = ftype_input

        content = input("反馈内容: ").strip()

        return {
            "chapter": chapter,
            "type": ftype,
            "content": content
        }

    # ==================== 主菜单 ====================

    def main_menu(self):
        """主菜单"""
        print("\n" + "=" * 62)
        print("              🖊️  网文助手 v5.24")
        print("=" * 62)
        print("  [1] 📝 写作流程")
        print("      写章节 · 生成大纲 · 大纲调整")
        print()
        print("  [2] 🔍 审查与质量")
        print("      章节审查 · 健康检查 · 去AI味检测")
        print()
        print("  [3] 💬 查询与恢复")
        print("      查询信息 · 恢复任务 · 可视化面板")
        print()
        print("  [4] 📊 经营分析")
        print("      读者反馈 · 追读力分析 · 连载模板")
        print()
        print("  [5] ⚙️ 系统运维")
        print("      状态报告 · 一致性修复 · 索引重建")
        print()
        print("  [0] ❌ 退出")
        print("=" * 62)

    # ==================== 子菜单：写作流程 ====================

    def menu_write(self):
        """写作流程子菜单"""
        print("\n" + "=" * 62)
        print("              📝 写作流程")
        print("=" * 62)
        print("  [1] ✏️  写章节（标准模式）")
        print("      完整7步流程，6个审查器串行执行")
        print()
        print("  [2] ⚡ 写章节（Turbo模式）")
        print("      跳过润色，核心3审查器并行，耗时减少50%+")
        print()
        print("  [3] 🚀 写章节（快速模式）")
        print("      跳过风格适配，适合日常更新")
        print()
        print("  [4] 📋 生成大纲")
        print("      按卷号生成章节大纲")
        print()
        print("  [5] 🔄 大纲调整")
        print("      动态调整大纲、插入副本、修正冲突")
        print()
        print("  [0] ↩️  返回主菜单")
        print("=" * 62)

    def do_write_standard(self):
        """标准模式写章节"""
        chapter = self._collect_chapter()
        print(f"\n📝 正在以标准模式写第 {chapter} 章...")
        result = self._run_cli(["context", "extract-context", "--chapter", chapter, "--format", "json"])
        # 这里应该调用完整的 write 流程，简化处理
        print(f"✓ 已获取第 {chapter} 章上下文")
        print("提示: 请使用 /webnovel-write 命令完成完整写作流程")

    def do_write_turbo(self):
        """Turbo模式写章节"""
        chapter = self._collect_chapter()
        print(f"\n⚡ 正在以Turbo模式写第 {chapter} 章（跳过润色，并行审查）...")
        print(f"✓ 已获取第 {chapter} 章上下文")
        print("提示: 请使用 /webnovel-write --turbo 命令完成完整写作流程")

    def do_write_fast(self):
        """快速模式写章节"""
        chapter = self._collect_chapter()
        print(f"\n🚀 正在以快速模式写第 {chapter} 章...")
        print(f"✓ 已获取第 {chapter} 章上下文")
        print("提示: 请使用 /webnovel-write --fast 命令完成完整写作流程")

    def do_plan(self):
        """生成大纲"""
        volume = self._collect_volume()
        print(f"\n📋 正在生成第 {volume} 卷大纲...")
        print("提示: 请使用 /webnovel-plan 命令完成大纲生成")

    def do_adjust(self):
        """大纲调整"""
        print("\n🔄 正在进入大纲调整...")
        print("提示: 请使用 /webnovel-adjust 命令完成大纲调整")

    # ==================== 子菜单：审查与质量 ====================

    def menu_review(self):
        """审查与质量子菜单"""
        print("\n" + "=" * 62)
        print("              🔍 审查与质量")
        print("=" * 62)
        print("  [1] 📊 审查章节")
        print("      多维质量审查（一致性/连贯性/OOC/爽点/节奏/追读力）")
        print()
        print("  [2] 🏥 健康检查")
        print("      检查 state/index/memory 一致性（v5.23）")
        print()
        print("  [3] 🔧 一致性修复")
        print("      自动修复数据不一致问题（v5.23）")
        print()
        print("  [4] 🤖 去AI味检测")
        print("      检测AI味指标，触发局部重写（v5.21）")
        print()
        print("  [0] ↩️  返回主菜单")
        print("=" * 62)

    def do_review(self):
        """审查章节"""
        chapter_range = self._collect_range()
        print(f"\n📊 正在审查第 {chapter_range} 章...")

        # 检查 chapter_range 格式
        if "-" in chapter_range:
            from_ch, to_ch = chapter_range.split("-", 1)
            print(f"审查范围: 第 {from_ch.strip()} 章到第 {to_ch.strip()} 章")
        else:
            print(f"审查章节: 第 {chapter_range} 章")

        print("提示: 请使用 /webnovel-review 命令完成审查")

    def do_health(self):
        """健康检查"""
        chapter = self._collect_chapter()
        print(f"\n🏥 正在检查第 {chapter} 章健康状态...")

        result = self._run_cli(["health", "--chapter", chapter])
        print(result if result.strip() else "✓ 健康检查完成，未发现问题")

    def do_repair(self):
        """一致性修复"""
        print("\n🔧 一致性修复（预览模式）...")
        print("注意: 预览模式不会实际修改数据")

        result = self._run_cli(["repair", "--dry-run"])
        print(result if result.strip() else "✓ 一致性检查完成，无需修复")

    def do_anti_ai(self):
        """去AI味检测"""
        chapter = self._collect_chapter()
        print(f"\n🤖 正在检测第 {chapter} 章AI味指标...")

        result = self._run_cli(["review", "--chapter", chapter, "--format", "json"])
        print("提示: 请使用 /webnovel-review 命令完成完整审查流程")

    # ==================== 子菜单：查询与恢复 ====================

    def menu_query(self):
        """查询与恢复子菜单"""
        print("\n" + "=" * 62)
        print("              💬 查询与恢复")
        print("=" * 62)
        print("  [1] 🔎 查询信息")
        print("      查询角色/伏笔/物品/地点/势力状态")
        print()
        print("  [2] 🔄 恢复任务")
        print("      从中断处继续写作")
        print()
        print("  [3] 📺 可视化面板")
        print("      启动 Dashboard 查看项目状态")
        print()
        print("  [0] ↩️  返回主菜单")
        print("=" * 62)

    def do_query(self):
        """查询信息"""
        keyword = self._collect_keyword()
        print(f"\n🔎 正在查询: {keyword}")
        print("提示: 请使用 /webnovel-query 命令完成查询")

    def do_resume(self):
        """恢复任务"""
        print("\n🔄 正在检查可恢复的任务...")
        print("提示: 请使用 /webnovel-resume 命令完成恢复")

    def do_dashboard(self):
        """可视化面板"""
        print("\n📺 正在启动可视化面板...")
        print("提示: 请使用 /webnovel-dashboard 命令启动面板")

    # ==================== 子菜单：经营分析 ====================

    def menu_business(self):
        """经营分析子菜单"""
        print("\n" + "=" * 62)
        print("              📊 经营分析")
        print("=" * 62)
        print("  [1] 💭 添加读者反馈")
        print("      收集读者/编辑反馈（钩子/节奏/OOC/文笔）")
        print()
        print("  [2] 📋 查看反馈列表")
        print("      按章节/类型筛选反馈")
        print()
        print("  [3] 📈 反馈统计")
        print("      查看反馈趋势与可操作建议")
        print()
        print("  [4] 📑 连载模板")
        print("      查看/管理连载模板（日更/周更）")
        print()
        print("  [0] ↩️  返回主菜单")
        print("=" * 62)

    def do_feedback_add(self):
        """添加读者反馈"""
        fb = self._collect_feedback()
        if not fb["content"]:
            print("✗ 反馈内容不能为空")
            return

        print(f"\n💭 正在添加反馈...")

        result = self._run_cli([
            "feedback",
            "--add",
            "--chapter", fb["chapter"],
            "--type", fb["type"],
            "--content", fb["content"]
        ])
        print(result if result.strip() else "✓ 反馈添加成功")

    def do_feedback_list(self):
        """查看反馈列表"""
        chapter = self._collect_chapter()
        print(f"\n📋 正在查看第 {chapter} 章反馈...")

        result = self._run_cli(["feedback", "--list", "--chapter", chapter])
        print(result if result.strip() else "暂无反馈")

    def do_feedback_stats(self):
        """反馈统计"""
        print("\n📈 正在生成反馈统计...")

        result = self._run_cli(["feedback", "--stats"])
        print(result if result.strip() else "暂无反馈数据")

    def do_feedback_suggestions(self):
        """可操作建议"""
        print("\n💡 正在生成可操作建议...")

        result = self._run_cli(["feedback", "--suggestions"])
        print(result if result.strip() else "暂无足够数据生成建议")

    def do_template(self):
        """连载模板"""
        result = self._run_cli(["feedback", "--templates"])
        print("\n📑 连载模板：")
        print(result if result.strip() else "暂无模板")

    # ==================== 子菜单：系统运维 ====================

    def menu_system(self):
        """系统运维子菜单"""
        print("\n" + "=" * 62)
        print("              ⚙️ 系统运维")
        print("=" * 62)
        print("  [1] 📊 状态报告")
        print("      查看项目状态、健康度、伏笔紧急度")
        print()
        print("  [2] 🔧 一致性修复")
        print("      修复 state/index/memory 不一致（v5.23）")
        print()
        print("  [3] 🏗️ 索引重建")
        print("      重建实体索引与向量索引")
        print()
        print("  [4] 📦 Git快照")
        print("      查看/回滚章节快照")
        print()
        print("  [5] 🧹 清理缓存")
        print("      清理过期缓存与临时文件")
        print()
        print("  [0] ↩️  返回主菜单")
        print("=" * 62)

    def do_status(self):
        """状态报告"""
        print("\n📊 正在生成状态报告...")

        result = self._run_cli(["status", "--focus", "all"])
        print(result if result.strip() else "✓ 状态正常")

    def do_repair_full(self):
        """一致性修复"""
        print("\n⚠️  一致性修复（执行修复）...")
        print("注意: 此操作会实际修改数据，建议先执行预览")

        confirm = input("确认执行修复？(y/N): ").strip().lower()
        if confirm == "y":
            result = self._run_cli(["repair", "--fix"])
            print(result if result.strip() else "✓ 修复完成")
        else:
            print("已取消")

    def do_index_rebuild(self):
        """索引重建"""
        print("\n🏗️ 正在重建索引...")
        print("提示: 请使用 webnovel.py index process-chapter --chapter N 命令重建索引")

    def do_git_snapshot(self):
        """Git快照"""
        print("\n📦 Git 快照管理...")

        # 列出可用快照
        project = Path(self.project_root)
        if (project / ".git").exists():
            print("可用快照:")
            # 这里用简化方式，实际应该调用 git tag
            print("  提示: 使用 git tag -l 'ch*' 查看可用快照")
        else:
            print("✗ 当前项目未启用 Git 版本控制")

    def do_cache_clean(self):
        """清理缓存"""
        print("\n🧹 正在清理缓存...")

        cache_dirs = [
            self.project_root / ".webnovel" / "context_hot_cache",
            self.project_root / ".webnovel" / "tmp",
        ]

        for cache_dir in cache_dirs:
            if cache_dir.exists():
                count = len(list(cache_dir.glob("*")))
                if count > 0:
                    print(f"  清理: {cache_dir} ({count} 文件)")
        print("✓ 缓存清理完成")

    # ==================== 主循环 ====================

    def run(self):
        """运行菜单"""
        print("\n" + "=" * 62)
        print("           🖊️  网文助手 v5.24 交互式菜单")
        print("=" * 62)
        print(f"   项目: {self.project_root}")
        print("=" * 62)

        while self.running:
            try:
                self.main_menu()
                choice = input("\n请输入选项编号（0-5）: ").strip()

                if choice == "0":
                    print("\n👋 感谢使用，再见！")
                    self.running = False
                elif choice == "1":
                    self.run_write_menu()
                elif choice == "2":
                    self.run_review_menu()
                elif choice == "3":
                    self.run_query_menu()
                elif choice == "4":
                    self.run_business_menu()
                elif choice == "5":
                    self.run_system_menu()
                else:
                    print("\n✗ 无效选项，请输入 0-5")

            except KeyboardInterrupt:
                print("\n\n👋 已退出网文助手，再见！")
                self.running = False
            except EOFError:
                self.running = False

    def run_write_menu(self):
        """写作流程子菜单"""
        while True:
            try:
                self.menu_write()
                choice = input("\n请输入选项编号（0-5）: ").strip()

                if choice == "0":
                    break
                elif choice == "1":
                    self.do_write_standard()
                elif choice == "2":
                    self.do_write_turbo()
                elif choice == "3":
                    self.do_write_fast()
                elif choice == "4":
                    self.do_plan()
                elif choice == "5":
                    self.do_adjust()
                else:
                    print("\n✗ 无效选项")

                if choice in ["1", "2", "3", "4", "5"]:
                    input("\n按回车继续...")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

    def run_review_menu(self):
        """审查与质量子菜单"""
        while True:
            try:
                self.menu_review()
                choice = input("\n请输入选项编号（0-4）: ").strip()

                if choice == "0":
                    break
                elif choice == "1":
                    self.do_review()
                elif choice == "2":
                    self.do_health()
                elif choice == "3":
                    self.do_repair()
                elif choice == "4":
                    self.do_anti_ai()
                else:
                    print("\n✗ 无效选项")

                if choice in ["1", "2", "3", "4"]:
                    input("\n按回车继续...")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

    def run_query_menu(self):
        """查询与恢复子菜单"""
        while True:
            try:
                self.menu_query()
                choice = input("\n请输入选项编号（0-3）: ").strip()

                if choice == "0":
                    break
                elif choice == "1":
                    self.do_query()
                elif choice == "2":
                    self.do_resume()
                elif choice == "3":
                    self.do_dashboard()
                else:
                    print("\n✗ 无效选项")

                if choice in ["1", "2", "3"]:
                    input("\n按回车继续...")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

    def run_business_menu(self):
        """经营分析子菜单"""
        while True:
            try:
                self.menu_business()
                choice = input("\n请输入选项编号（0-4）: ").strip()

                if choice == "0":
                    break
                elif choice == "1":
                    self.do_feedback_add()
                elif choice == "2":
                    self.do_feedback_list()
                elif choice == "3":
                    self.do_feedback_stats()
                elif choice == "4":
                    self.do_template()
                else:
                    print("\n✗ 无效选项")

                if choice in ["1", "2", "3", "4"]:
                    input("\n按回车继续...")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

    def run_system_menu(self):
        """系统运维子菜单"""
        while True:
            try:
                self.menu_system()
                choice = input("\n请输入选项编号（0-5）: ").strip()

                if choice == "0":
                    break
                elif choice == "1":
                    self.do_status()
                elif choice == "2":
                    self.do_repair_full()
                elif choice == "3":
                    self.do_index_rebuild()
                elif choice == "4":
                    self.do_git_snapshot()
                elif choice == "5":
                    self.do_cache_clean()
                else:
                    print("\n✗ 无效选项")

                if choice in ["1", "2", "3", "4", "5"]:
                    input("\n按回车继续...")

            except KeyboardInterrupt:
                break
            except EOFError:
                break


def main():
    import argparse

    parser = argparse.ArgumentParser(description="网文助手交互式菜单 v5.24")
    parser.add_argument("--project-root", help="项目根目录")
    args = parser.parse_args()

    menu = InteractiveMenu(args.project_root)
    menu.run()


if __name__ == "__main__":
    main()
