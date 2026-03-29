# -*- coding: utf-8 -*-
"""
上下文热缓存 (Context Hot Cache) - v5.22

功能：复用近章上下文，加速当前章节的上下文构建

对于 turbo 模式：
- 跳过 Step 2B/4，减少处理步骤
- 复用近 3 章的上下文作为参考
- 核心审查并行执行

使用方式：
    from context_cache import ContextCache
    cache = ContextCache(config)
    cached_context = cache.get_hot_context(chapter=10, max_chapters=3)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from filelock import FileLock

try:
    from security_utils import atomic_write_json
except ImportError:
    from scripts.security_utils import atomic_write_json


@dataclass
class CachedChapterContext:
    """缓存的章节上下文"""
    chapter: int
    cached_at: float  # Unix timestamp
    context_hash: str  # 上下文的哈希值
    sections: Dict[str, Any]  # 上下文各节的内容
    summary: str  # 章节摘要
    word_count: int
    key_events: List[str] = field(default_factory=list)  # 关键事件列表


class ContextCache:
    """上下文热缓存管理器"""

    CACHE_VERSION = "1.0"
    CACHE_DIR = "context_hot_cache"

    def __init__(self, config=None, cache_dir: Optional[Path] = None, ttl: int = 3600):
        """
        初始化缓存管理器

        Args:
            config: DataModulesConfig 实例
            cache_dir: 缓存目录路径
            ttl: 缓存有效期（秒），默认 1 小时
        """
        self.config = config
        self.ttl = ttl

        if cache_dir:
            self.cache_dir = Path(cache_dir)
        elif config:
            from data_modules.config import get_config
            if config is None:
                config = get_config()
            self.cache_dir = config.webnovel_dir / self.CACHE_DIR
        else:
            try:
                from project_locator import resolve_project_root
            except ImportError:
                from scripts.project_locator import resolve_project_root
            root = resolve_project_root()
            self.cache_dir = root / ".webnovel" / self.CACHE_DIR

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock_dir = self.cache_dir / ".locks"
        self._lock_dir.mkdir(exist_ok=True)

    def _cache_path(self, chapter: int) -> Path:
        """获取指定章节的缓存文件路径"""
        return self.cache_dir / f"ch{chapter:04d}_context.json"

    def _lock_path(self, chapter: int) -> Path:
        """获取指定章节的缓存锁路径"""
        return self._lock_dir / f"ch{chapter:04d}.lock"

    def _read_cache(self, chapter: int) -> Optional[CachedChapterContext]:
        """读取指定章节的缓存"""
        path = self._cache_path(chapter)
        if not path.exists():
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return CachedChapterContext(
                chapter=data["chapter"],
                cached_at=data["cached_at"],
                context_hash=data["context_hash"],
                sections=data["sections"],
                summary=data.get("summary", ""),
                word_count=data.get("word_count", 0),
                key_events=data.get("key_events", []),
            )
        except (json.JSONDecodeError, KeyError, IOError):
            return None

    def save_context(
        self,
        chapter: int,
        context: Dict[str, Any],
        summary: str = "",
        word_count: int = 0,
        key_events: Optional[List[str]] = None,
    ) -> bool:
        """
        保存章节上下文到缓存

        Args:
            chapter: 章节号
            context: 上下文数据
            summary: 章节摘要
            word_count: 字数
            key_events: 关键事件列表

        Returns:
            是否保存成功
        """
        import hashlib

        path = self._cache_path(chapter)
        lock = FileLock(str(self._lock_path(chapter)), timeout=10)

        try:
            with lock:
                # 计算上下文的哈希值
                context_str = json.dumps(context, sort_keys=True, ensure_ascii=False)
                context_hash = hashlib.md5(context_str.encode()).hexdigest()[:12]

                data = {
                    "version": self.CACHE_VERSION,
                    "chapter": chapter,
                    "cached_at": time.time(),
                    "context_hash": context_hash,
                    "sections": context.get("sections", {}),
                    "summary": summary,
                    "word_count": word_count,
                    "key_events": key_events or [],
                }

                atomic_write_json(path, data, use_lock=False, backup=False)
                return True
        except Exception:
            return False

    def get_hot_context(
        self,
        chapter: int,
        max_chapters: int = 3,
        max_age: Optional[int] = None
    ) -> List[CachedChapterContext]:
        """
        获取近 N 章的热缓存上下文

        Args:
            chapter: 当前章节号
            max_chapters: 最大缓存章数
            max_age: 缓存最大有效期（秒），默认使用 self.ttl

        Returns:
            缓存的上下文列表，按章节号降序排列
        """
        if max_age is None:
            max_age = self.ttl

        now = time.time()
        cached_contexts: List[CachedChapterContext] = []

        # 从近到远搜索缓存
        for offset in range(1, max_chapters + 1):
            target_chapter = chapter - offset
            if target_chapter <= 0:
                continue

            cached = self._read_cache(target_chapter)
            if cached is None:
                continue

            # 检查缓存是否过期
            if now - cached.cached_at > max_age:
                continue

            cached_contexts.append(cached)

        return cached_contexts

    def get_recent_summaries(self, chapter: int, max_chapters: int = 3) -> List[Dict[str, Any]]:
        """
        获取近 N 章的摘要信息（用于快速构建上下文）

        Args:
            chapter: 当前章节号
            max_chapters: 最大缓存章数

        Returns:
            摘要信息列表
        """
        hot_contexts = self.get_hot_context(chapter, max_chapters)
        return [
            {
                "chapter": ctx.chapter,
                "summary": ctx.summary,
                "word_count": ctx.word_count,
                "key_events": ctx.key_events,
            }
            for ctx in hot_contexts
        ]

    def invalidate(self, chapter: int) -> bool:
        """
        使指定章节的缓存失效

        Args:
            chapter: 章节号

        Returns:
            是否成功删除
        """
        path = self._cache_path(chapter)
        lock = FileLock(str(self._lock_path(chapter)), timeout=10)

        try:
            with lock:
                if path.exists():
                    path.unlink()
                    return True
                return False
        except Exception:
            return False

    def invalidate_range(self, start_chapter: int, end_chapter: int) -> int:
        """
        使指定范围章节的缓存失效

        Args:
            start_chapter: 起始章节号
            end_chapter: 结束章节号

        Returns:
            删除的缓存数量
        """
        count = 0
        for chapter in range(start_chapter, end_chapter + 1):
            if self.invalidate(chapter):
                count += 1
        return count

    def clear_all(self) -> int:
        """
        清空所有缓存

        Returns:
            删除的缓存数量
        """
        count = 0
        for path in self.cache_dir.glob("ch*_context.json"):
            try:
                path.unlink()
                count += 1
            except Exception:
                pass
        return count

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息
        """
        now = time.time()
        cache_files = list(self.cache_dir.glob("ch*_context.json"))

        valid_count = 0
        expired_count = 0
        total_size = 0

        for path in cache_files:
            try:
                size = path.stat().st_size
                total_size += size

                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                cached_at = data.get("cached_at", 0)
                if now - cached_at <= self.ttl:
                    valid_count += 1
                else:
                    expired_count += 1
            except Exception:
                pass

        return {
            "total_files": len(cache_files),
            "valid_count": valid_count,
            "expired_count": expired_count,
            "total_size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
        }
