#!/usr/bin/env python3
"""
批量写作控制器
支持批量章节写入、进度跟踪、异常处理
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

class BatchWriter:
    def __init__(self, project_root: Path, from_chapter: int, to_chapter: int,
                 night_mode: bool = False, max_calls: int = 1400):
        self.project_root = project_root
        self.from_chapter = from_chapter
        self.to_chapter = to_chapter
        self.night_mode = night_mode
        self.max_calls = max_calls
        self.current_chapter = from_chapter
        self.completed_chapters: List[int] = []
        self.failed_chapters: List[Dict] = []
        self.total_calls = 0

        self.batch_file = project_root / ".webnovel" / "workflow_batch.json"

    def load_progress(self):
        """从文件加载进度"""
        if self.batch_file.exists():
            with open(self.batch_file) as f:
                data = json.load(f)
            self.current_chapter = data.get("current_chapter", self.from_chapter)
            self.completed_chapters = data.get("completed_chapters", [])
            self.failed_chapters = data.get("failed_chapters", [])
            self.total_calls = data.get("total_calls_used", 0)

    def save_progress(self):
        """保存进度到文件"""
        data = {
            "batch_id": f"batch_{datetime.now().strftime('%Y%m%d')}_{self.from_chapter}_{self.to_chapter}",
            "started_at": datetime.now().isoformat(),
            "from_chapter": self.from_chapter,
            "to_chapter": self.to_chapter,
            "current_chapter": self.current_chapter,
            "completed_chapters": self.completed_chapters,
            "failed_chapters": self.failed_chapters,
            "status": "running",
            "total_calls_used": self.total_calls,
            "max_calls": self.max_calls
        }
        self.batch_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.batch_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def check_quota(self) -> bool:
        """检查额度是否充足"""
        if not self.night_mode:
            return True
        remaining = self.max_calls - self.total_calls
        return remaining >= 50  # 留50次余量

    def run(self):
        """执行批量写作"""
        print("批量写作开始")
        self.load_progress()

        while self.current_chapter <= self.to_chapter:
            if not self.check_quota():
                print(f"额度不足，停止批量写作")
                break

            chapter = self.current_chapter
            print(f"\n开始写入第 {chapter} 章")

            try:
                # 这里先简单模拟，后续Task 2会实现真正的调用
                self.completed_chapters.append(chapter)
                self.current_chapter += 1
                self.save_progress()
                time.sleep(1)

            except KeyboardInterrupt:
                print("\n用户中断批量写作")
                self.save_progress()
                break
            except Exception as e:
                print(f"异常: {e}")
                self.save_progress()
                break

        self.save_progress()
        self.print_summary()

    def print_summary(self):
        """打印批量写作摘要"""
        print(f"\n批量写作完成")
        print(f"完成章节: {len(self.completed_chapters)}")
        print(f"失败章节: {len(self.failed_chapters)}")
        print(f"总调用次数: {self.total_calls}")


if __name__ == "__main__":
    # 测试入口
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--from", dest="from_chapter", type=int, required=True)
    parser.add_argument("--to", dest="to_chapter", type=int, required=True)
    parser.add_argument("--night-mode", action="store_true")
    parser.add_argument("--max-calls", type=int, default=1400)
    args = parser.parse_args()

    writer = BatchWriter(
        Path(args.project_root),
        args.from_chapter,
        args.to_chapter,
        args.night_mode,
        args.max_calls
    )
    writer.run()