# Webnovel Dashboard Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把现有只读 Dashboard 升级为“写作驾驶舱 + 记忆与召回页 + 数据二级页”，让首页优先展示本章决策信息，并把记忆、健康与归档信息集中管理。

**Architecture:** 前端保留 React + Vite 的单页结构，但把首页从“数据总览”重排为写作驾驶舱；后端补一个只读聚合接口，降低首页拼装复杂度；同时新增“记忆与召回”页，集中展示 `story_memory`、`story_recall`、`archive` 和 `memory_health`。整个改造保持 Dashboard 只读，不影响现有实体、图谱、章节、文件和追读力页面。

**Tech Stack:** Python, FastAPI, React, Vite, JSON, SQLite, pytest, existing `dashboard/app.py`, `dashboard/frontend/src/App.jsx`, `dashboard/frontend/src/api.js`

---

## Version Plan

| 版本 | 核心目标 | 验证方式 |
|------|----------|----------|
| dashboard-redesign | 首页改成写作驾驶舱 | 打开面板第一屏能看到本章决策信息 |
| dashboard-redesign | 新增记忆与召回页 | 能查看 `story_memory / archive / memory_health` |
| dashboard-redesign | 保留二级数据页 | 旧的实体/图谱/章节/文件/追读力页仍可使用 |

---

### Task 1: 为 Dashboard 首页重排写失败测试

**Files:**
- Modify: `webnovel-writer/dashboard/frontend/src/App.jsx`
- Modify: `webnovel-writer/dashboard/frontend/src/api.js`
- Add or Modify: `webnovel-writer/dashboard/frontend/src/__tests__/App.test.jsx`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - 首页默认显示“写作驾驶舱”模块，而不是旧式数据总览
  - 首页展示本章大纲摘要、高优先级召回、记忆健康、未回收伏笔
  - 首页存在空数据时仍能渲染空状态

**Step 2: 跑测试确认失败**

```bash
cd webnovel-writer/dashboard/frontend
npm test
```

**Step 3: 写最小实现**

- 先把首页拆成独立组件骨架：
  - `WritingDashboard`
  - `ChapterBriefCard`
  - `MemoryRecallCard`
  - `MemoryHealthCard`
  - `QuickActionCard`
- 让首页优先显示驾驶舱卡片

**Step 4: 跑测试确认通过**

```bash
cd webnovel-writer/dashboard/frontend
npm test
```

**Step 5: 提交**

```bash
git add webnovel-writer/dashboard/frontend/src/App.jsx webnovel-writer/dashboard/frontend/src/api.js webnovel-writer/dashboard/frontend/src/__tests__/App.test.jsx
git commit -m "feat(dashboard): redesign home as writing cockpit"
```

---

### Task 2: 新增 Dashboard 聚合接口

**Files:**
- Modify: `webnovel-writer/dashboard/app.py`
- Add or Modify: `webnovel-writer/dashboard/tests/test_app.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - `/api/dashboard/summary` 返回首页所需的聚合结构
  - 聚合结构包含：
    - `project_info`
    - `chapter_outline`
    - `story_recall`
    - `memory_health`
    - `writing_guidance`
    - `archive_recall`

**Step 2: 跑测试确认失败**

```bash
pytest webnovel-writer/dashboard/tests/test_app.py -v
```

**Step 3: 写最小实现**

- 在 `dashboard/app.py` 新增只读聚合接口
- 复用现有 `state.json`、`story_memory.json`、`context_manager` 输出逻辑
- 接口失败时返回明确降级信息，不影响其他接口

**Step 4: 跑测试确认通过**

```bash
pytest webnovel-writer/dashboard/tests/test_app.py -v
```

**Step 5: 提交**

```bash
git add webnovel-writer/dashboard/app.py webnovel-writer/dashboard/tests/test_app.py
git commit -m "feat(dashboard): add summary aggregation endpoint"
```

---

### Task 3: 新增“记忆与召回”页面

**Files:**
- Modify: `webnovel-writer/dashboard/frontend/src/App.jsx`
- Modify: `webnovel-writer/dashboard/frontend/src/index.css`
- Add or Modify: `webnovel-writer/dashboard/frontend/src/__tests__/App.test.jsx`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - 侧边栏新增“记忆与召回”入口
  - 页面能展示 `story_recall`
  - 页面能展示 `archive_recall`
  - 页面能按 `memory_tier` 或模块折叠展示内容

**Step 2: 跑测试确认失败**

```bash
cd webnovel-writer/dashboard/frontend
npm test
```

**Step 3: 写最小实现**

- 新建 `MemoryPage` 或 `MemoryAndRecallPage`
- 显示：
  - 召回政策
  - 高优先级召回
  - 归档召回
  - 结构化变化账本
  - 记忆健康

**Step 4: 跑测试确认通过**

```bash
cd webnovel-writer/dashboard/frontend
npm test
```

**Step 5: 提交**

```bash
git add webnovel-writer/dashboard/frontend/src/App.jsx webnovel-writer/dashboard/frontend/src/index.css webnovel-writer/dashboard/frontend/src/__tests__/App.test.jsx
git commit -m "feat(dashboard): add memory and recall page"
```

---

### Task 4: 保留并下沉现有数据页

**Files:**
- Modify: `webnovel-writer/dashboard/frontend/src/App.jsx`
- Modify: `webnovel-writer/dashboard/frontend/src/index.css`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - 现有 `设定词典 / 关系图谱 / 章节一览 / 文档浏览 / 追读力` 仍可访问
  - 首页不再默认进入旧的数据总览卡片

**Step 2: 跑测试确认失败**

```bash
cd webnovel-writer/dashboard/frontend
npm test
```

**Step 3: 写最小实现**

- 调整导航层级：
  - 首页：写作驾驶舱
  - 新增：记忆与召回
  - 二级：实体、图谱、章节、文件、追读力
- 保留现有页面的渲染逻辑，避免一次性重做数据页

**Step 4: 跑测试确认通过**

```bash
cd webnovel-writer/dashboard/frontend
npm test
```

**Step 5: 提交**

```bash
git add webnovel-writer/dashboard/frontend/src/App.jsx webnovel-writer/dashboard/frontend/src/index.css
git commit -m "feat(dashboard): keep data pages as secondary views"
```

---

### Task 5: 让首页对空数据和降级更友好

**Files:**
- Modify: `webnovel-writer/dashboard/frontend/src/App.jsx`
- Modify: `webnovel-writer/dashboard/frontend/src/index.css`
- Modify: `webnovel-writer/dashboard/app.py`

**Step 1: 写失败测试**

- 新增测试，覆盖：
  - `story_memory` 缺失时首页仍可用
  - 聚合接口失败时首页回退到基础项目状态
  - 空状态要明确说明，不显示误导性占位

**Step 2: 跑测试确认失败**

```bash
pytest webnovel-writer/dashboard/tests/test_app.py -v
cd webnovel-writer/dashboard/frontend
npm test
```

**Step 3: 写最小实现**

- 前端增加空态组件
- 后端聚合接口增加降级说明字段
- 首页只依赖最少的关键字段

**Step 4: 跑测试确认通过**

```bash
pytest webnovel-writer/dashboard/tests/test_app.py -v
cd webnovel-writer/dashboard/frontend
npm test
```

**Step 5: 提交**

```bash
git add webnovel-writer/dashboard/app.py webnovel-writer/dashboard/frontend/src/App.jsx webnovel-writer/dashboard/frontend/src/index.css
git commit -m "feat(dashboard): add graceful fallback states"
```

---

### Task 6: 更新文档与版本说明

**Files:**
- Modify: `docs/commands.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `README.md`
- Modify: `webnovel-writer/skills/webnovel-dashboard/SKILL.md`
- Modify: `docs/plans/2026-03-27-dashboard-redesign-design.md`

**Step 1: 写失败测试**

- 无新增行为测试时，至少补一轮文档检查：
  - `/webnovel-dashboard` 的说明要体现写作驾驶舱定位
  - 新增记忆页入口要写入命令文档

**Step 2: 跑回归确认**

```bash
pytest webnovel-writer/dashboard/tests/test_app.py -v
cd webnovel-writer/dashboard/frontend
npm test
```

**Step 3: 更新文档**

- `docs/commands.md` 补 dashboard 新定位
- `skills/webnovel-dashboard/SKILL.md` 补新页面说明
- `README.md` / `CHANGELOG.md` 补版本变化

**Step 4: 跑检查**

- 确认命令文档与面板导航一致
- 确认首页文案不再只强调“数据总览”

**Step 5: 提交**

```bash
git add docs/commands.md docs/CHANGELOG.md README.md webnovel-writer/skills/webnovel-dashboard/SKILL.md docs/plans/2026-03-27-dashboard-redesign-design.md
git commit -m "docs(dashboard): update cockpit redesign documentation"
```

---

## 验收标准

1. 打开 `/webnovel-dashboard` 后，第一屏默认看到写作驾驶舱，而不是旧式总览。
2. 首页能直接看到本章大纲、写作建议、高优先级召回、未回收伏笔和记忆健康。
3. 能进入独立的“记忆与召回”页查看 `story_memory`、`archive`、`recall_policy`。
4. 现有实体、图谱、章节、文件、追读力页面仍然可用。
5. `story_memory` 缺失或损坏时，Dashboard 仍然可以降级显示，不阻塞使用。

## 非目标

- 不把 Dashboard 做成可编辑面板。
- 不在本次重构中改动底层 `state.json / index.db / vectors.db` 存储结构。
- 不把所有数据页都重新设计一遍，先保持二级页稳定。

