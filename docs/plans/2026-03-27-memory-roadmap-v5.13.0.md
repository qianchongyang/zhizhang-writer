# Memory Roadmap v5.13.0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让通用记忆系统从“可记、可召回、可归档”进一步升级为“可裁决、可回放、可按需召回归档层”，解决当前记忆系统在冲突消解、归档复用和阈值调参上的最后一批短板。

**Architecture:** 采用两条主线并行推进。第一条是“归档层可召回”，让 `story_memory.archive` 在特定条件下参与写前召回，但不会污染高优先级活跃记忆；第二条是“记忆权威度与证据链”，为关键记忆补齐来源、证据章节、最后校验章节和置信度，使 `state.json`、`index.db`、`story_memory.json` 三者冲突时有稳定裁决依据。整个版本保持现有 `state.json / index.db / vectors.db / story_memory.json` 底座不变，只增强记忆选择与裁决层。

**Tech Stack:** Python, JSON, SQLite, existing `ContextManager`, `StateManager`, `state_validator.py`, `status_reporter.py`, pytest

---

## Version Plan

| 版本 | 核心目标 | 验证方式 |
|------|----------|----------|
| v5.13.0 | 归档层可召回 | 写第50章时能按条件召回归档伏笔/事件 |
| v5.13.0 | 记忆权威度与证据链 | 冲突记忆可通过证据与来源裁决 |
| v5.13.0 | 阈值配置化 | 召回与归档阈值可通过配置调整 |

---

### Task 1: 设计归档层的可召回契约

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/state_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_state_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - 归档层存在已回收伏笔时，Context Agent 可按条件召回
  - 归档层存在旧事件/旧变化时，只有在当前章节相关时才进入上下文
  - 归档层不会无条件覆盖活跃层内容

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_state_validator.py \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py -v
```

**Step 3: 实现最小归档召回**

- 为 `story_memory.archive` 增加统一读取入口
- 在 `ContextManager._build_story_recall()` 中增加归档候选池
- 归档召回只在以下条件下触发：
  - 当前章节与最近总结章节间隔过大
  - 活跃层命中不足
  - 当前章节存在相关角色/伏笔/变化信号
- 归档召回输出需单独标记 `memory_tier=archive`

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_state_validator.py \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/state_validator.py webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/data_modules/tests/test_state_validator.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py
git commit -m "feat(memory): allow archive layer to participate in recall"
```

---

### Task 2: 为关键记忆补齐权威度与证据链

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/state_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_state_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - 关键记忆必须保留 `source_of_truth`
  - 关键记忆必须保留 `evidence_chapters`
  - 冲突数据可通过 `confidence` 与最近验证章节判断优先级

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_state_validator.py \
  webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py -v
```

**Step 3: 实现最小证据链**

- 在 `story_memory` 归一化时补充：
  - `source_of_truth`
  - `confidence`
  - `evidence_chapters`
  - `last_verified_chapter`
- 在写入 `story_memory` 时，尽量把章节来源与变化来源写清
- 为冲突裁决准备“最近验证优先、证据完整优先、置信度高优先”的基础规则

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_state_validator.py \
  webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/state_validator.py webnovel-writer/scripts/data_modules/state_manager.py webnovel-writer/scripts/data_modules/tests/test_state_validator.py webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py
git commit -m "feat(memory): add evidence chain for key memory"
```

---

### Task 3: 让记忆冲突裁决可解释

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/status_reporter.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_status_reporter.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - 同一事实在 state / index / story_memory 三处冲突时，能输出裁决依据
  - 健康报告能显示当前冲突来源与裁决状态

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 3: 实现最小裁决说明**

- 在 `story_recall` 或 `memory` 输出中增加：
  - `source_of_truth`
  - `last_verified_chapter`
  - `confidence`
- 在健康报告中增加冲突提示：
  - 哪条记忆更可信
  - 为什么更可信
  - 是否需要人工复核

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/status_reporter.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_status_reporter.py
git commit -m "feat(memory): make memory conflict resolution explainable"
```

---

### Task 4: 让归档与召回阈值可配置

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/config.py`
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/state_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_state_validator.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - 归档阈值可通过 config 调整
  - 召回阈值可通过 config 调整
  - 不同项目根能采用不同的默认阈值

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_state_validator.py -v
```

**Step 3: 实现最小配置化**

- 将以下阈值抽出为 config：
  - `archive_stale_gap`
  - `tier_limit`
  - `change_ledger_limit`
  - `memory_recall_gap`
- 保留默认值，不破坏旧项目行为

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_state_validator.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/config.py webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/data_modules/state_validator.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_state_validator.py
git commit -m "feat(memory): make memory thresholds configurable"
```

---

### Task 5: v5.13.0 版本收口与文档同步

**Files:**
- Modify: `README.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/architecture.md`
- Modify: `docs/commands.md`
- Modify: `docs/notes/2026-03-27-记忆系统升级-深度评估.md`
- Modify: `docs/notes/2026-03-27-记忆系统升级需求-实施版.md`

**Step 1: 写失败测试**

- 无新增代码测试时，至少补文档验收项：
  - 归档层参与召回
  - 权威度与证据链存在
  - 阈值可配置

**Step 2: 跑回归确认**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_state_validator.py \
  webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py \
  webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 3: 收口文档**

- 更新 README 中版本说明
- 更新 CHANGELOG 中对应版本记录
- 更新架构文档与命令文档中的记忆链路说明
- 更新评估与实施文档中的下一阶段计划

**Step 4: 提交**

```bash
git add README.md docs/CHANGELOG.md docs/architecture.md docs/commands.md docs/notes/2026-03-27-记忆系统升级-深度评估.md docs/notes/2026-03-27-记忆系统升级需求-实施版.md
git commit -m "docs(memory): close v5.13.0 roadmap"
```
