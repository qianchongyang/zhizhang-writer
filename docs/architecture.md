# 系统架构与模块设计

## 核心理念

### 防幻觉三定律

| 定律 | 说明 | 执行方式 |
|------|------|---------|
| **大纲即法律** | 遵循大纲，不擅自发挥 | Context Agent 强制加载章节大纲 |
| **设定即物理** | 遵守设定，不自相矛盾 | Consistency Checker 实时校验 |
| **发明需识别** | 新实体必须入库管理 | Data Agent 自动提取并消歧 |

### Strand Weave 节奏系统

| Strand | 含义 | 理想占比 | 说明 |
|--------|------|---------|------|
| **Quest** | 主线剧情 | 60% | 推动核心冲突 |
| **Fire** | 感情线 | 20% | 人物关系发展 |
| **Constellation** | 世界观扩展 | 20% | 背景/势力/设定 |

节奏红线：

- Quest 连续不超过 5 章
- Fire 断档不超过 10 章
- Constellation 断档不超过 15 章

## 总体架构图

```text
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                           │
├─────────────────────────────────────────────────────────────┤
│  Skills (7个): init / plan / write / review / query / ... │
├─────────────────────────────────────────────────────────────┤
│  Agents (8个): Context / Data / 多维 Checker               │
├─────────────────────────────────────────────────────────────┤
│  Data Layer: state.json / index.db / vectors.db /          │
│              story_memory.json / project_memory.json /     │
│              story_technique_blueprint.json                │
└─────────────────────────────────────────────────────────────┘
```

## 三层结构

### 控制面

- `author_intent`：长期创作目标与硬约束
- `current_focus`：最近 1-3 章必须拉回的重点
- `chapter_intent`：本章任务书，是 Context Agent 的标准产物
- `chapter_technique_plan`：本章技巧编排，约束 Step 2A 的结构化输入

控制面只负责“本章该写什么、不能偏到哪”，不是事实源。

### 技巧策略层

- `story_technique_blueprint.json`：项目级技巧事实源
- `project_memory.json`：项目内已验证有效/疲劳的技巧记忆

该层负责回答“本书适合用什么技巧、哪些技巧已经过度使用、这一章优先怎么落位”。

### 真相层

- `state.json`：当前工作态
- `story_memory.json`：跨章节稳定记忆、情感弧线、归档
- `index.db`：历史索引、状态变化、关系
- `vectors.db`：语义召回

真相层是可追溯事实来源，控制面与运行层都要以它为准。

### 运行层

- `context_manager / extract_chapter_context`：把控制面、真相层和大纲编译成可写作上下文
- `technique_blueprint.py`：把题材、记忆、读者信号编译成技巧蓝图与章节技巧编排
- `workflow_manager`：记录 `workflow_trace`
- `dashboard`：展示任务书、召回、风险、记忆健康和运行阶段

运行层负责“编译、展示、追溯”，不应私自篡改事实。

## 双 Agent 架构

### Context Agent（读）

职责：在写作前构建“创作任务书”，提供本章上下文、约束和追读力策略。

### Data Agent（写）

职责：从正文提取实体与状态变化，更新 `state.json`、`index.db`、`vectors.db` 与 `story_memory.json`，保证数据链闭环。

`story_memory.json` 负责承载跨章节稳定记忆，包括角色阶段摘要、伏笔状态、近章事件、结构化变化账本、情感弧线与归档层；`state.json` 继续承载当前工作态，`index.db` 和 `vectors.db` 继续负责历史索引与语义召回。

## 分组审查架构

### 核心审查器（始终执行）

| Checker | 检查重点 |
|---------|---------|
| consistency-checker | 设定一致性（战力/地点/时间线/外貌） |
| continuity-checker | 场景与叙事连贯性 |
| ooc-checker | 人物行为是否偏离人设 |

### 条件审查器（auto 路由命中时执行）

| Checker | 检查重点 |
|---------|---------|
| reader-pull-checker | 钩子强度、期待管理、追读力 |
| high-point-checker | 爽点密度、质量、兑现后余波 |
| pacing-checker | Strand 比例、断档、信息密度 |

**审查分组执行规则：**
- 核心审查器 → 结果写入 `rev1_ch{NNNN}.json`
- 条件审查器 → 结果写入 `rev2_ch{NNNN}.json`
- 两组结果合并后落库，并汇总 `technique_execution`
