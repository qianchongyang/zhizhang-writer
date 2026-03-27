# Memory Roadmap v5.10.0 - v5.12.0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 逐步把通用记忆引擎从“已记录”升级到“会召回、会分层、会遗忘”，让 Context Agent 在写前主动使用 `story_memory`，并在容量、健康与过期清理上形成闭环。

**Architecture:** 采用三阶段渐进式方案。`v5.10.0` 先打通 `story_memory` 到 Context Agent 的写前召回通路，确保稳定记忆能进入本章上下文；`v5.11.0` 再把召回逻辑按 `memory_tier` 做差异化编排，减少低价值信息干扰；`v5.12.0` 最后补齐健康报告、容量上限、过期清理与遗忘策略。整个过程保持 `state.json / index.db / vectors.db / story_memory.json` 的现有底座不变，只在召回与整理编排层做增量升级。

**Tech Stack:** Python, JSON, SQLite, existing `DataModulesConfig`, `ContextManager`, `StateManager`, `status_reporter.py`, `extract_chapter_context.py`, pytest

---

## Version Plan

| 版本 | 核心目标 | 验证方式 |
|------|----------|----------|
| v5.10.0 | 召回接口接入 Context Agent | 写第50章前验证召回内容准确性 |
| v5.11.0 | `memory_tier` 差异化召回 | 按 `consolidated → episodic → working` 顺序验证召回 |
| v5.12.0 | 健康报告 + 遗忘机制 | 验证容量超限淘汰、过期伏笔清理 |

---

### Task 1: 固化 v5.10.0 召回边界与触发规则

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/extract_chapter_context.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py`

**Step 1: 写失败测试**

- 新增测试，覆盖以下场景：
  - 章节上下文未包含 `story_memory` 时应仍可回退
  - 存在 `story_memory` 时应优先注入高价值记忆
  - 不同章节长度与上下文预算下，召回块应稳定输出

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py -k story_memory -v
```

**Step 3: 实现最小召回接入**

- 从 `story_memory.json` 读取：
  - `characters.current_state`
  - `recent_events`
  - `plot_threads`
  - `structured_change_ledger` 中的高分项
- 形成 `story_recall` 注入块
- 触发条件改为动态策略，不再写死 `chapter > 10`
- 召回优先级按“高价值、未解决、近期相关”排序

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/extract_chapter_context.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py
git commit -m "feat(memory): connect story memory recall to context agent"
```

---

### Task 2: 让 v5.10.0 召回结果可解释、可回退

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/status_reporter.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_status_reporter.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - `story_memory` 损坏或缺失时自动降级到现有召回路径
  - 健康报告中可看到召回来源与命中情况

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 3: 实现最小回退逻辑**

- `story_memory` 读取失败时，不阻塞写作
- 输出召回降级说明
- 健康报告补充“召回来源”与“最近一次整理章号”

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/status_reporter.py webnovel-writer/scripts/data_modules/tests/test_status_reporter.py
git commit -m "feat(memory): add recall fallback and explainability"
```

---

### Task 3: v5.11.0 差异化召回编排

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/state_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_state_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - `consolidated` 记忆优先于 `episodic`
  - `episodic` 优先于 `working`
  - 同层级内按 `memory_score`、相关角色、章节距离排序

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_state_validator.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py -v
```

**Step 3: 实现最小分层召回**

- 在 `score_change_significance()` 的基础上，稳定使用 `memory_tier`
- 召回编排改成：
  - `consolidated`
  - `episodic`
  - `working`
- 同时限制每层输出数量，避免低价值信息挤占上下文

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_state_validator.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/data_modules/state_validator.py webnovel-writer/scripts/data_modules/tests/test_state_validator.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py
git commit -m "feat(memory): prioritize recall by memory tier"
```

---

### Task 4: v5.11.0 召回质量保护

**Files:**
- Modify: `webnovel-writer/scripts/extract_chapter_context.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - 召回结果中重复项应折叠
  - 低分记忆不应挤入高优先级块
  - 输出格式应能看出 tier 与 score

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -v
```

**Step 3: 实现最小质量保护**

- 在章节上下文输出中标明 `change_kind / memory_tier / memory_score`
- 折叠重复召回项
- 低分项只在预算充足时输出

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/extract_chapter_context.py webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py
git commit -m "feat(memory): improve context recall output quality"
```

---

### Task 5: v5.12.0 健康报告升级

**Files:**
- Modify: `webnovel-writer/scripts/status_reporter.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_status_reporter.py`
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - 健康报告显示容量趋势
  - 健康报告显示过期伏笔数量
  - 健康报告显示最近一次清理章号

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 3: 实现最小健康指标**

- 输出以下指标：
  - 结构化变化条目数
  - 已沉淀变化条目数
  - 未回收伏笔数
  - 最近整理章号
  - 容量余量

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/status_reporter.py webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/data_modules/tests/test_status_reporter.py
git commit -m "feat(memory): add memory health reporting"
```

---

### Task 6: v5.12.0 遗忘与清理机制

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/state_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_state_validator.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - `structured_change_ledger` 超限时自动截断
  - 过期且已回收伏笔可从活跃层移出
  - 长期无变化的低价值记忆可进入归档层

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py webnovel-writer/scripts/data_modules/tests/test_state_validator.py -v
```

**Step 3: 实现最小遗忘策略**

- 设定容量上限
- 老旧低分记忆优先清理
- 伏笔在“回收后 + 足够稳定期”再进入归档
- 保持可重建，清理不影响主写作流程

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py webnovel-writer/scripts/data_modules/tests/test_state_validator.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/state_manager.py webnovel-writer/scripts/data_modules/state_validator.py webnovel-writer/scripts/data_modules/tests/test_state_manager_extra.py webnovel-writer/scripts/data_modules/tests/test_state_validator.py
git commit -m "feat(memory): add retention and forgetting policy"
```

---

### Task 7: v5.12.0 端到端回归与文档收口

**Files:**
- Modify: `README.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/architecture.md`
- Modify: `docs/commands.md`
- Modify: `docs/notes/2026-03-27-记忆系统升级-深度评估.md`（如需补充遗忘机制结论）
- Modify: `docs/notes/2026-03-27-记忆系统升级需求-实施版.md`（如需补充 v5.12 完成标准）

**Step 1: 写失败测试**

- 无新增代码测试时，至少补文档验收项：
  - v5.10.0 召回通路接通
  - v5.11.0 分层召回生效
  - v5.12.0 遗忘与健康报告生效

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
- 更新 v5.10.0 到 v5.12.0 路线备注，确保未来执行可追踪

**Step 4: 提交**

```bash
git add README.md docs/CHANGELOG.md docs/architecture.md docs/commands.md docs/notes/2026-03-27-记忆系统升级-深度评估.md docs/notes/2026-03-27-记忆系统升级需求-实施版.md
git commit -m "docs(memory): close roadmap through v5.12.0"
```
