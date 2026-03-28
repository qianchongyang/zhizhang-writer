# RAG 与配置说明

## RAG 检索架构

```text
查询 → QueryRouter(auto) → vector / bm25 / hybrid / graph_hybrid
                     └→ RRF 融合 + Rerank → Top-K
```

默认模型：

- Embedding：`Qwen/Qwen3-Embedding-8B`
- Reranker：`jina-reranker-v3`

## 环境变量加载顺序

1. 进程环境变量（最高优先级）
2. 书项目根目录下的 `.env`
3. 用户级全局：`~/.claude/webnovel-writer/.env`

## 上下文硬闸门相关配置（DataModulesConfig）

- `context_require_chapter_outline`（默认 `true`）
  - 是否强制要求章节大纲存在
- `context_require_chapter_contract`（默认 `true`）
  - 是否强制要求最小章节契约（目标/冲突/动作/结果/代价/钩子）
- `context_min_state_changes_per_chapter`（默认 `0`）
  - 每章最小状态变化信号阈值，`0` 表示不强制

建议：先保持默认；当项目进入中后期、需要更强可追踪性时，再将 `context_min_state_changes_per_chapter` 提升到 `1`。

## `.env` 最小配置

```bash
EMBED_BASE_URL=https://api-inference.modelscope.cn/v1
EMBED_MODEL=Qwen/Qwen3-Embedding-8B
EMBED_API_KEY=your_embed_api_key

RERANK_BASE_URL=https://api.jina.ai/v1
RERANK_MODEL=jina-reranker-v3
RERANK_API_KEY=your_rerank_api_key
```

说明：

- 未配置 Embedding Key 时，语义检索会回退到 BM25。
- 推荐每本书单独配置 `${PROJECT_ROOT}/.env`，避免多项目串配置。
- 统一通过 `webnovel.py` 入口调用 RAG 能避免参数顺序/路径解析问题。
