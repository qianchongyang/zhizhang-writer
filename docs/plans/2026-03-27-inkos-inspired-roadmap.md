# Inkos-Inspired Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 吸收 `inkos` 在控制面、流程编译化、审计回路和记忆前置上的长处，把 `webnovel-writer` 从“有功能的写作工具”进一步收口成“可编译、可审计、可追溯”的长篇创作系统。

**Architecture:** 本计划不照搬 `inkos` 的多 Agent 重架构，而是在现有 `Context Agent + Data Agent + state/story_memory/dashboard` 底座上增加三条主线：控制面、工作流编译链、可追溯运行层。控制面负责管理创作意图与章节任务；工作流编译链负责把意图、记忆、约束合成为本章任务书；运行层负责把上下文、审计、召回和风险在 Dashboard 中可见化。

**Tech Stack:** Python, JSON, SQLite, Markdown, existing agents/skills, React dashboard, pytest

---

## Scope

**做什么**
- 引入“控制面 / 真相层 / 运行层”术语和落地结构
- 增强章节任务书，使其成为写作链的标准输入
- 让 Dashboard 展示任务书、召回、审计和风险，而不只是数据视图
- 为记忆链和审计链补充追溯信息

**暂不做**
- 不增加 10-agent 架构
- 不迁移 PostgreSQL 或重做底层存储
- 不大改现有 `/webnovel-write` 入口语义

## Version Outline

| 版本 | 核心目标 | 对齐 inkos 的启发 |
|------|----------|-------------------|
| v5.14.0 | 建立控制面与章节任务书契约 | `author_intent / current_focus / chapter intent` |
| v5.15.0 | 写作链编译化与运行轨迹 | `plan -> compose -> draft -> audit -> revise` |
| v5.16.0 | Dashboard 展示任务书、审计与风险 | Web UI 作为编译结果展示面 |
| v5.17.0 | 记忆与审计可追溯 | 记忆检索前置、审计驱动修订 |

---

### Task 1: 建立控制面文档和运行时契约

**Files:**
- Create: `docs/notes/control-plane.md`
- Create: `webnovel-writer/templates/runtime/author_intent.md`
- Create: `webnovel-writer/templates/runtime/current_focus.md`
- Create: `webnovel-writer/templates/runtime/chapter-intent.md`
- Modify: `docs/architecture.md`
- Modify: `README.md`

**Step 1: 写文档草案**

- 定义三层结构：
  - 控制面：`author_intent / current_focus / chapter_intent`
  - 真相层：`state / story_memory / index / vectors`
  - 运行层：`context / audit / dashboard / traces`

**Step 2: 补模板**

- 为运行时模板补齐字段：
  - `目标`
  - `不能写什么`
  - `必须回收什么`
  - `本章风险`
  - `重点角色`
  - `重点记忆`

**Step 3: 更新架构文档**

- 在架构文档中明确三层关系和数据流
- 说明控制面不是事实来源，事实仍以真相层为准

**Step 4: 自检**

Run:

```bash
rg -n "控制面|真相层|运行层|chapter intent|author_intent|current_focus" docs README.md webnovel-writer/templates
```

Expected: 新术语和模板路径都能被检索到

**Step 5: 提交**

```bash
git add docs/notes/control-plane.md docs/architecture.md README.md webnovel-writer/templates/runtime
git commit -m "docs(workflow): define control plane and runtime intent templates"
```

---

### Task 2: 让 Context Agent 产出标准章节任务书

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/extract_chapter_context.py`
- Modify: `webnovel-writer/agents/context-agent.md`
- Modify: `webnovel-writer/skills/webnovel-write/references/step-1.5-contract.md`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py`

**Step 1: 写失败测试**

- 覆盖：
  - 上下文输出中必须包含章节目标
  - 必须包含“本章风险”和“必须回收项”
  - 当 `story_memory` 存在关键召回时，任务书中必须体现

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -v
```

**Step 3: 实现最小任务书**

- 在 `ContextManager` 输出中增加标准任务书块：
  - `chapter_goal`
  - `must_resolve`
  - `hard_constraints`
  - `story_risks`
  - `priority_memory`
- 在文本渲染时把这些内容固定成清晰块，而不是散落在上下文里

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/extract_chapter_context.py webnovel-writer/agents/context-agent.md webnovel-writer/skills/webnovel-write/references/step-1.5-contract.md webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_extract_chapter_context.py
git commit -m "feat(context): emit structured chapter intent brief"
```

---

### Task 3: 为写作链增加运行轨迹和阶段状态

**Files:**
- Modify: `webnovel-writer/scripts/workflow_manager.py`
- Modify: `webnovel-writer/scripts/status_reporter.py`
- Modify: `webnovel-writer/scripts/data_modules/state_manager.py`
- Modify: `webnovel-writer/scripts/tests/test_workflow_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_status_reporter.py`

**Step 1: 写失败测试**

- 覆盖：
  - 每次 `/webnovel-write` 运行都记录阶段状态
  - 失败时可知道卡在 `context / draft / audit / revise` 哪一步
  - 状态报告可展示最后一次运行轨迹

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/tests/test_workflow_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 3: 实现最小运行轨迹**

- 增加运行时 trace：
  - `run_id`
  - `stage`
  - `status`
  - `updated_at`
  - `chapter`
- 将最新 trace 写入 `.webnovel` 运行态或状态报告可读取的位置

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/tests/test_workflow_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/workflow_manager.py webnovel-writer/scripts/status_reporter.py webnovel-writer/scripts/data_modules/state_manager.py webnovel-writer/scripts/tests/test_workflow_manager.py webnovel-writer/scripts/data_modules/tests/test_status_reporter.py
git commit -m "feat(workflow): record write pipeline trace states"
```

---

### Task 4: 让 Dashboard 展示任务书和运行风险

**Files:**
- Modify: `webnovel-writer/dashboard/app.py`
- Modify: `webnovel-writer/dashboard/frontend/src/App.jsx`
- Modify: `webnovel-writer/dashboard/frontend/src/index.css`
- Modify: `webnovel-writer/dashboard/tests/test_app.py`
- Modify: `docs/commands.md`
- Modify: `README.md`

**Step 1: 写失败测试**

- 覆盖：
  - Dashboard summary 接口返回章节任务书关键字段
  - 首页能显示“本章任务 / 本章风险 / 必须回收项”
  - 运行轨迹状态可以在首页或辅助块中看到

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer python3 -m pytest -o addopts='' \
  webnovel-writer/dashboard/tests/test_app.py -v
```

**Step 3: 实现最小驾驶舱增强**

- 在 summary API 中补：
  - `chapter_intent`
  - `story_risks`
  - `must_resolve`
  - `workflow_trace`
- 前端首页增加一个任务书区块
- 风险和回收项采用摘要优先，细节折叠

**Step 4: 跑测试与构建**

```bash
PYTHONPATH=webnovel-writer python3 -m pytest -o addopts='' \
  webnovel-writer/dashboard/tests/test_app.py -v
npm --prefix webnovel-writer/dashboard/frontend run build
```

**Step 5: 提交**

```bash
git add webnovel-writer/dashboard/app.py webnovel-writer/dashboard/frontend/src/App.jsx webnovel-writer/dashboard/frontend/src/index.css webnovel-writer/dashboard/tests/test_app.py docs/commands.md README.md
git commit -m "feat(dashboard): surface chapter intent and workflow risk"
```

---

### Task 5: 让记忆和审计具备追溯关系

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/context_manager.py`
- Modify: `webnovel-writer/scripts/status_reporter.py`
- Modify: `webnovel-writer/scripts/data_modules/state_validator.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_context_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/tests/test_status_reporter.py`

**Step 1: 写失败测试**

- 覆盖：
  - 召回条目能显示来源与证据章节
  - 风险提示能指向具体记忆或审计结论
  - 状态报告能看见最近一次重要冲突或审计失败点

**Step 2: 跑测试确认失败**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 3: 实现最小追溯**

- 让 recall 输出保留：
  - `source_of_truth`
  - `evidence_chapters`
  - `last_verified_chapter`
- 让风险提示能关联到具体条目，而不是泛泛提示

**Step 4: 跑测试确认通过**

```bash
PYTHONPATH=webnovel-writer/scripts python3 -m pytest \
  webnovel-writer/scripts/data_modules/tests/test_context_manager.py \
  webnovel-writer/scripts/data_modules/tests/test_status_reporter.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/scripts/data_modules/context_manager.py webnovel-writer/scripts/status_reporter.py webnovel-writer/scripts/data_modules/state_validator.py webnovel-writer/scripts/data_modules/tests/test_context_manager.py webnovel-writer/scripts/data_modules/tests/test_status_reporter.py
git commit -m "feat(memory): connect recall evidence with audit risk"
```

---

## Success Criteria

- 写前上下文不再只是“资料拼盘”，而是明确的章节任务书
- Dashboard 首页能直接看见任务、风险、回收项和运行状态
- 写作失败或质量下滑时，能快速定位是记忆、上下文还是审计链的问题
- 记忆召回和审计结论能互相指向，形成闭环

## Risks

- 如果字段一次性加太多，任务书会重新膨胀成噪音
- 如果运行轨迹写入方式选错，可能污染现有状态文件或增加恢复复杂度
- Dashboard 若展示过多原始信息，会再次退化成“数据仓库”

## Notes

- 保持现有双 Agent 架构，不为追求形式而引入过多 Agent
- 优先做“可解释、可观察、可回退”，而不是先扩数据库或扩规则数量
- 每个任务都应先写测试，再写最小实现，再提交

