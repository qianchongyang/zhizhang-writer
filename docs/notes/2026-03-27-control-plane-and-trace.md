# 控制面与运行轨迹落地记录

日期：2026-03-27

## 本轮目标

把 `inkos` 给我们的启发收口成现有双 Agent 架构可执行的一版，不重做底座，只增强：

- 控制面
- 章节任务书
- 情感弧线
- 轻量去 AI 味
- Observer / Reflector 渐进分离
- workflow trace

## 已落地对象

### 控制面

- `author_intent`
- `current_focus`
- `chapter_intent`

存放位置：

- `.webnovel/control/author_intent.json`
- `.webnovel/control/current_focus.json`
- `.webnovel/control/chapter_intents/chapter-XXXX.json`

### 记忆层

`story_memory.json` 新增：

- `emotional_arcs`

该层独立于 `structured_change_ledger`，避免把情绪变化混成普通变化账本。

### 轻量去 AI 味

当前以 `style_fatigue` 形式进入：

- `chapter_meta`
- `review_checkpoints`
- `dashboard summary`
- `status_reporter`

第一阶段只做告警和建议，不自动改写正文。

### 运行轨迹

`workflow_manager` 现在会产出：

- `workflow_trace.run_id`
- `workflow_trace.stage`
- `workflow_trace.status`
- `workflow_trace.chapter`

这层用于 dashboard 展示、恢复判断和后续排障。

## 当前边界

- 没有引入 10-agent 架构
- 没有重做底层存储
- 没有上 SQLite 时序记忆增强
- 没有做重型风格指纹系统

## 后续建议

下一轮最值钱的是：

1. `style_fatigue` 细分成可配置规则
2. 情感弧线补“断层冲突检测”
3. `workflow_trace` 在 dashboard 做更明确的阶段可视化
