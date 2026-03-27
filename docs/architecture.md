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
│              story_memory.json                             │
└─────────────────────────────────────────────────────────────┘
```

## 三层结构

### 控制面

- `author_intent`：长期创作目标与硬约束
- `current_focus`：最近 1-3 章必须拉回的重点
- `chapter_intent`：本章任务书，是 Context Agent 的标准产物

控制面只负责“本章该写什么、不能偏到哪”，不是事实源。

### 真相层

- `state.json`：当前工作态
- `story_memory.json`：跨章节稳定记忆、情感弧线、归档
- `index.db`：历史索引、状态变化、关系
- `vectors.db`：语义召回

真相层是可追溯事实来源，控制面与运行层都要以它为准。

### 运行层

- `context_manager / extract_chapter_context`：把控制面、真相层和大纲编译成可写作上下文
- `workflow_manager`：记录 `workflow_trace`
- `dashboard`：展示任务书、召回、风险、记忆健康和运行阶段

运行层负责“编译、展示、追溯”，不应私自篡改事实。

## 双 Agent 架构

### Context Agent（读）

职责：在写作前构建“创作任务书”，提供本章上下文、约束和追读力策略。

### Data Agent（写）

职责：从正文提取实体与状态变化，更新 `state.json`、`index.db`、`vectors.db` 与 `story_memory.json`，保证数据链闭环。

`story_memory.json` 负责承载跨章节稳定记忆，包括角色阶段摘要、伏笔状态、近章事件、结构化变化账本、情感弧线与归档层；`state.json` 继续承载当前工作态，`index.db` 和 `vectors.db` 继续负责历史索引与语义召回。

## 六维并行审查

| Checker | 检查重点 |
|---------|---------|
| High-point Checker | 爽点密度与质量 |
| Consistency Checker | 设定一致性（战力/地点/时间线） |
| Pacing Checker | Strand 比例与断档 |
| OOC Checker | 人物行为是否偏离人设 |
| Continuity Checker | 场景与叙事连贯性 |
| Reader-pull Checker | 钩子强度、期待管理、追读力 |
