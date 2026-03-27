# Memory System v5.9.0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不替换现有 `state.json / index.db / vectors.db` 架构的前提下，新增位于 `PROJECT_ROOT/.webnovel/memory/story_memory.json` 的故事记忆层，并接入写前召回、章节整理、快照失效和健康检查。

**Architecture:** 采用“现有三层数据层 + 新增故事记忆层”的渐进式方案。`state.json` 继续承担运行态权威状态，`index.db` 继续承担结构化历史，`vectors.db` 继续承担语义召回，`story_memory.json` 只保存高价值、可更新、可重建的故事记忆。写前由 Context Manager 读取 `story_memory.json` 并与现有召回结果合并，写后由 Data Agent 根据章节结果做增量写入与周期性整理。`SnapshotManager` 需要把 `story_memory` 版本或整理章号纳入快照失效条件，否则会重复复用旧上下文。

**Tech Stack:** Python, JSON, SQLite, 现有 `StateManager`, `IndexManager`, `RAGAdapter`, `ContextManager`, `update_state.py`

---

### Task 1: 固化需求与边界

**Files:**
- Create: `docs/notes/2026-03-27-记忆系统升级需求-实施版.md`
- Create: `docs/plans/2026-03-27-memory-system-v5.9.0.md`
- Modify: `docs/notes/2026-03-27-记忆系统升级需求.md`（如需补充指向实施版需求的链接）

**Step 1: 检查需求是否能被当前代码基线支持**

- 目标：确认本期不引入 PostgreSQL、图数据库迁移
- 结果：保留 `state.json + index.db + vectors.db` 作为主基线

**Step 2: 定义本期交付边界**

- 目标：明确只做 `story_memory.json`、写前召回、周期整理、健康检查
- 结果：冻结非目标项，避免范围膨胀

**Step 3: 提交文档**

```bash
git add docs/notes/2026-03-27-记忆系统升级需求-实施版.md docs/plans/2026-03-27-memory-system-v5.9.0.md
git commit -m "docs(memory): add implementable spec and v5.9.0 plan"
```

### Task 2: 设计 `story_memory.json` 读写契约

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/snapshot_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py`

**Step 1: 写失败测试**

- 覆盖 `story_memory.json` 缺失、格式错误、空文件三种情况
- 覆盖字段最小结构：`version`、`last_consolidated_chapter`、`characters`、`plot_threads`、`recent_events`
- 覆盖 `build_context()` 复用旧 snapshot 时，`story_memory` 版本变化必须触发重建

**Step 2: 跑测试确认失败**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py -k story_memory -v
```

**Step 3: 实现最小读写能力**

- 新增 `story_memory.json` 加载函数
- 新增缺省初始化与安全降级逻辑
- 新增保存时的原子写入与字段校验
- 新增快照失效签名，至少包含 `version` 和 `last_consolidated_chapter`

**Step 4: 跑测试确认通过**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py -k story_memory -v
pytest webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py -k story_memory -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/data_modules/state_manager.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py
git commit -m "feat(memory): add story memory contract"
```

### Task 3: 接入写前召回

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/extract_chapter_context.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`

**Step 1: 写失败测试**

- 写新章节上下文时，应自动包含：
  - 未回收伏笔
  - 最近 3-5 章重大事件
  - 上章结尾状态
  - 当前相关角色状态

**Step 2: 跑测试确认失败**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py -v
```

**Step 3: 实现最小召回编排**

- 从 `story_memory.json` 读取稳定记忆
- 与现有 `state.json`、`index.db`、`vectors.db` 召回结果合并
- 形成固定的写前注入块
- 保证 `story_memory` 注入优先于快照复用，必要时使 snapshot 失效

**Step 4: 跑测试确认通过**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/extract_chapter_context.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py
git commit -m "feat(memory): inject story memory into chapter context"
```

### Task 4: 接入章节整理流程

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`
- Modify: `webnovel-writer/scripts/update_state.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_data_modules.py`

**Step 1: 写失败测试**

- 每完成 5 章，应触发一次 consolidation
- consolidation 不得阻塞主写作流程
- consolidation 需要更新 `last_consolidated_chapter`

**Step 2: 跑测试确认失败**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py -v
```

**Step 3: 实现最小整理逻辑**

- 仅整理高价值记忆：
  - milestone
  - pending plot threads
  - recent events
  - chapter snapshots
- 采用“先归档，再截断”的容量策略
- 写入 `story_memory.json` 时同步刷新 `last_consolidated_chapter` 与整理时间戳

**Step 4: 跑测试确认通过**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py -v
pytest webnovel-writer/scripts/data_modules/tests/test_data_modules.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/state_manager.py webnovel-writer/scripts/update_state.py webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py webnovel-writer/scripts/data_modules/tests/test_data_modules.py
git commit -m "feat(memory): add periodic story memory consolidation"
```

### Task 5: 数值与伏笔的精确化更新

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/index_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/sql_state_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_data_modules.py`

**Step 1: 写失败测试**

- 数值变化必须保留精确值和来源章节
- 伏笔状态更新必须保留 `pending -> fulfilled` 的生命周期

**Step 2: 跑测试确认失败**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_data_modules.py -k state_changes -v
```

**Step 3: 实现最小增强**

- 明确数值类状态的结构化字段
- 补充伏笔状态机与更新入口
- 保证状态变化可从 `index.db` 追溯

**Step 4: 跑测试确认通过**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_data_modules.py -k state_changes -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/index_manager.py webnovel-writer/scripts/data_modules/sql_state_manager.py webnovel-writer/scripts/data_modules/tests/test_data_modules.py
git commit -m "feat(memory): make numeric and foreshadowing state updates precise"
```

### Task 6: 健康检查与回退

**Files:**
- Modify: `webnovel-writer/scripts/status_reporter.py`
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_status_reporter.py`

**Step 1: 写失败测试**

- 健康检查应输出：
  - 命中率
  - 脏记忆率
  - 漏召回样本
  - 容量趋势
- 当 `story_memory.json` 失效时，应回退到现有召回路径

**Step 2: 跑测试确认失败**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 3: 实现最小检查与回退**

- 增加故事记忆健康摘要
- 增加召回失败降级逻辑
- 增加结构损坏提示

**Step 4: 跑测试确认通过**

```bash
pytest webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/status_reporter.py webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/data_modules/tests/test_status_reporter.py
git commit -m "feat(memory): add health checks and fallback path"
```

### Task 7: 端到端回归验证

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_status_reporter.py`

**Step 1: 准备端到端场景**

- 初始化一个带伏笔、数值变化、章节结尾状态的测试项目

**Step 2: 跑完整流程**

- 写第 1 章到第 6 章
- 触发一次 consolidation
- 在第 7 章写前检查召回注入

**Step 3: 验证结果**

- `story_memory.json` 已生成
- 伏笔状态可更新
- 召回结果包含关键历史信息
- 健康检查有输出

**Step 4: 提交**

```bash
git add webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_status_reporter.py
git commit -m "test(memory): cover end-to-end story memory flow"
```

## Delivery Order

1. 先落文档和契约
2. 再接 `story_memory.json`
3. 再接写前召回
4. 再接周期整理
5. 再补精确数值与伏笔状态
6. 最后补健康检查与端到端回归

## Out of Scope

- PostgreSQL 迁移
- 图数据库引入
- 跨项目记忆共享
- 服务化拆分
