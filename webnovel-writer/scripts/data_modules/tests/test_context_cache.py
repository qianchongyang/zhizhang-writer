# -*- coding: utf-8 -*-
"""
Context Cache 测试
"""

import pytest
import tempfile
import time
import json
from pathlib import Path

from context_cache import ContextCache, CachedChapterContext


class TestCachedChapterContext:
    """CachedChapterContext 数据类测试"""

    def test_create_cached_context(self):
        """测试创建缓存上下文"""
        ctx = CachedChapterContext(
            chapter=10,
            cached_at=time.time(),
            context_hash="abc123",
            sections={"chapter_summary": "测试章节"},
            summary="第10章测试",
            word_count=2156,
            key_events=["事件1", "事件2"],
        )

        assert ctx.chapter == 10
        assert ctx.summary == "第10章测试"
        assert ctx.word_count == 2156
        assert len(ctx.key_events) == 2


class TestContextCache:
    """ContextCache 缓存管理器测试"""

    @pytest.fixture
    def temp_cache_dir(self):
        """创建临时缓存目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_init(self, temp_cache_dir):
        """测试缓存管理器初始化"""
        cache = ContextCache(cache_dir=temp_cache_dir)
        assert cache.cache_dir == temp_cache_dir
        assert temp_cache_dir.exists()

    def test_save_and_get_context(self, temp_cache_dir):
        """测试保存和获取缓存"""
        cache = ContextCache(cache_dir=temp_cache_dir)

        # 保存上下文
        context = {
            "sections": {
                "chapter_summary": {"content": "测试摘要"},
                "recent_events": {"content": "近期事件"},
            }
        }
        result = cache.save_context(
            chapter=10,
            context=context,
            summary="第10章测试",
            word_count=2156,
            key_events=["事件1"],
        )
        assert result is True

        # 获取热缓存
        hot_contexts = cache.get_hot_context(chapter=11, max_chapters=3)
        assert len(hot_contexts) == 1
        assert hot_contexts[0].chapter == 10
        assert hot_contexts[0].summary == "第10章测试"

    def test_cache_expiry(self, temp_cache_dir):
        """测试缓存过期"""
        cache = ContextCache(cache_dir=temp_cache_dir, ttl=1)  # 1秒过期

        # 保存上下文
        context = {"sections": {}}
        cache.save_context(chapter=10, context=context, summary="测试")

        # 立即获取 - 应该存在
        hot_contexts = cache.get_hot_context(chapter=11, max_chapters=3)
        assert len(hot_contexts) == 1

        # 等待过期
        time.sleep(1.5)

        # 再次获取 - 应该过期
        hot_contexts = cache.get_hot_context(chapter=11, max_chapters=3)
        assert len(hot_contexts) == 0

    def test_get_recent_summaries(self, temp_cache_dir):
        """测试获取近章摘要"""
        cache = ContextCache(cache_dir=temp_cache_dir)

        # 保存多章上下文
        for chapter in [8, 9, 10]:
            context = {"sections": {}}
            cache.save_context(
                chapter=chapter,
                context=context,
                summary=f"第{chapter}章",
                word_count=2000 + chapter,
                key_events=[f"事件{chapter}"],
            )

        # 获取近3章摘要
        summaries = cache.get_recent_summaries(chapter=11, max_chapters=3)
        assert len(summaries) == 3
        assert summaries[0]["chapter"] == 10  # 最近的一章
        assert summaries[1]["chapter"] == 9
        assert summaries[2]["chapter"] == 8

    def test_invalidate(self, temp_cache_dir):
        """测试缓存失效"""
        cache = ContextCache(cache_dir=temp_cache_dir)

        # 保存上下文
        context = {"sections": {}}
        cache.save_context(chapter=10, context=context, summary="测试")

        # 确认缓存存在
        hot_contexts = cache.get_hot_context(chapter=11, max_chapters=3)
        assert len(hot_contexts) == 1

        # 使缓存失效
        result = cache.invalidate(10)
        assert result is True

        # 确认缓存已删除
        hot_contexts = cache.get_hot_context(chapter=11, max_chapters=3)
        assert len(hot_contexts) == 0

    def test_clear_all(self, temp_cache_dir):
        """测试清空所有缓存"""
        cache = ContextCache(cache_dir=temp_cache_dir)

        # 保存多章上下文
        for chapter in [8, 9, 10]:
            context = {"sections": {}}
            cache.save_context(chapter=chapter, context=context, summary=f"第{chapter}章")

        # 清空所有缓存
        count = cache.clear_all()
        assert count == 3

        # 确认已清空
        hot_contexts = cache.get_hot_context(chapter=11, max_chapters=3)
        assert len(hot_contexts) == 0

    def test_get_cache_stats(self, temp_cache_dir):
        """测试获取缓存统计"""
        cache = ContextCache(cache_dir=temp_cache_dir)

        # 保存上下文
        for chapter in [8, 9, 10]:
            context = {"sections": {}}
            cache.save_context(chapter=chapter, context=context, summary=f"第{chapter}章")

        # 获取统计
        stats = cache.get_cache_stats()
        assert stats["total_files"] == 3
        assert stats["valid_count"] == 3
        assert stats["expired_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
