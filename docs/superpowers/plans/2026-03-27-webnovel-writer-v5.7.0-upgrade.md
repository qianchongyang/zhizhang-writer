# webnovel-writer v5.7.0 升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 webnovel-writer 系统进行三个方向的升级：字数检查系统、质量报告总分层、references 参考资料扩展

**Architecture:**
- Phase 1（字数检查）: 新增 `references/word-count-rules.md`，在 Context Agent 输出字数建议，在审查时强制检查
- Phase 2（质量总分）: 扩展 `checker-output-schema.md`，增加总分计算和各维度权重
- Phase 3（references 扩展）: 新增 5 个参考资料文件，扩展 core-constraints.md

**Tech Stack:** Markdown 参考文件、JSON Schema、Python 脚本

---

## 文件修改清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `references/word-count-rules.md` | 新增 | 字数检查规则定义 |
| `references/checker-output-schema.md` | 扩展 | 增加 total_score/grade/权重配置 |
| `references/chapter-guide.md` | 新增 | 章节写作核心要点 |
| `references/hook-techniques.md` | 新增 | 悬念设置技巧 |
| `references/quality-checklist.md` | 新增 | 80分质量检查清单 |
| `references/plot-structures.md` | 新增 | 情节结构模板 |
| `references/dialogue-writing.md` | 新增 | 对话写作规范 |
| `references/shared/core-constraints.md` | 扩展 | 引入四大核心法则 |
| `webnovel-writer/.claude-plugin/plugin.json` | 修改 | 版本号 5.6.2 → 5.7.0 |
| `.claude-plugin/marketplace.json` | 修改 | 版本号更新 |
| `README.md` | 修改 | 更新日志 |
| `docs/CHANGELOG.md` | 修改 | 添加 v5.7.0 变更记录 |

---

## Phase 1: 字数检查系统

### Task 1: 创建 word-count-rules.md

**Files:**
- Create: `webnovel-writer/references/word-count-rules.md`

- [ ] **Step 1: 创建文件**

```markdown
---
name: word-count-rules
purpose: 章节字数检查标准与异常处理指引
---

# 字数检查规则

## 字数标准

| 等级 | 字数范围 | 处理方式 |
|------|---------|---------|
| 优秀 | 2000-2500 字 | 直接通过 |
| 合格 | 1800-2000 字 | 轻微警告 |
| 警告 | 1500-1800 字 | 强制警告 |
| 不合格 | <1500 字 | MUST_FIX |
| 超出 | >3000 字 | 建议拆分（非强制） |

## 各题材字数偏好

| 题材 | 推荐字数 | 说明 |
|------|---------|------|
| 玄幻/修仙 | 2000-2500 | 标准 |
| 都市异能 | 2000-2500 | 标准 |
| 言情 | 1800-2200 | 略短 |
| 悬疑 | 2000-2500 | 标准 |
| 轻小说 | 1500-2000 | 略短 |

## 字数异常处理

### 字数不足 (<1500)

**判定**: MUST_FIX，不得进入下一步

**修复建议**:
- 扩展场景描写（环境、动作、表情）
- 增加对话深度（意图、试探、反应）
- 补充细节（物品、氛围、心理）

### 字数超出 (>3000)

**判定**: 建议拆分，不强制阻断

**拆分原则**:
- 3000-4000 字：考虑拆分 2 章
- >4000 字：建议拆分 2-3 章

## Context Agent 字数建议输出

在 Step 1 输出中加入：
```
本章建议字数：2000-2500 字
题材偏好：玄幻修仙
章节类型：标准剧情章
```

## 审查时字数检查

审查报告 `metrics` 中加入：
```json
{
  "metrics": {
    "word_count": 2156,
    "word_count_status": "优秀",
    "word_count_issue": null
  }
}
```

状态枚举：`excellent` | `acceptable` | `warning` | `must_fix` | `oversized`
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/references/word-count-rules.md
git commit -m "feat: 新增字数检查规则 word-count-rules.md"
```

---

### Task 2: 集成字数检查到 webnovel-write

**Files:**
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`

- [ ] **Step 1: 在 Step 1 (Context Agent) 中添加字数建议输出**

在 `webnovel-write/SKILL.md` 的 Step 1 部分，找到"输出"段落，加入：

```
- 字数建议输出（来自 word-count-rules.md）：
  - 本章建议字数范围
  - 题材字数偏好
  - 章节类型对应的字数期望
```

- [ ] **Step 2: 在 Step 3 审查指标中加入字数检查**

在 `webnovel-write/SKILL.md` 的 Step 3 部分，找到 `review_metrics` 字段定义，加入：

```json
{
  "word_count": 2156,
  "word_count_status": "excellent",
  "word_count_issue": null
}
```

- [ ] **Step 3: 提交**

```bash
git add webnovel-writer/skills/webnovel-write/SKILL.md
git commit -m "feat: 集成字数检查到 webnovel-write"
```

---

### Task 3: 集成字数检查到 webnovel-review

**Files:**
- Modify: `webnovel-writer/skills/webnovel-review/SKILL.md`

- [ ] **Step 1: 在 Step 4 审查报告生成部分加入字数检查**

在审查报告 markdown 模板中加入：

```markdown
## 字数检查
- 字数：{word_count} 字
- 状态：{word_count_status}
- 建议：{word_count_issue 或 "无"}
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/skills/webnovel-review/SKILL.md
git commit -m "feat: 集成字数检查到 webnovel-review"
```

---

## Phase 2: 质量报告总分层

### Task 4: 扩展 checker-output-schema.md

**Files:**
- Modify: `webnovel-writer/references/checker-output-schema.md`

- [ ] **Step 1: 添加总分和等级字段**

在 JSON Schema 定义后添加：

```markdown
## 总分汇总扩展

### 新增字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `total_score` | int | 否 | 总分 (0-80)，由汇总层计算 |
| `grade` | string | 否 | 等级：优秀/合格/需修改/不合格 |
| `dimension_scores` | object | 否 | 各维度得分 |
| `weighted_score` | float | 否 | 加权总分 |

### 各维度权重配置

| 维度 | 权重 | 满分 |
|------|------|------|
| 追读力 (Reader Pull) | 20% | 16 分 |
| 爽点密度 (High-point) | 20% | 16 分 |
| 节奏 (Pacing) | 15% | 12 分 |
| 连贯性 (Consistency) | 20% | 16 分 |
| OOC 检查 | 15% | 12 分 |
| 叙事连贯 (Continuity) | 10% | 8 分 |
| **合计** | 100% | 80 分 |

### 交付等级

| 分数 | 等级 | 动作 |
|------|------|------|
| ≥70 | 优秀 | 可直接交付 |
| 60-69 | 合格 | 轻微修改后交付 |
| 50-59 | 需修改 | 主要问题需修复 |
| <50 | 不合格 | 必须大改 |

### 汇总格式扩展

在 `汇总格式` 部分扩展：

```json
{
  "chapter": 100,
  "checkers": {
    "reader-pull-checker": {"score": 85, "pass": true, "critical": 0, "high": 1},
    "high-point-checker": {"score": 80, "pass": true, "critical": 0, "high": 0},
    "consistency-checker": {"score": 90, "pass": true, "critical": 0, "high": 0},
    "ooc-checker": {"score": 75, "pass": true, "critical": 0, "high": 1},
    "continuity-checker": {"score": 85, "pass": true, "critical": 0, "high": 0},
    "pacing-checker": {"score": 80, "pass": true, "critical": 0, "high": 0}
  },
  "overall": {
    "score": 82.5,
    "total_score": 66,
    "grade": "合格",
    "dimension_scores": {
      "追读力": 16,
      "爽点密度": 16,
      "节奏": 12,
      "连贯性": 16,
      "OOC": 12,
      "叙事连贯": 8
    },
    "pass": true,
    "critical_total": 0,
    "high_total": 2,
    "can_proceed": true
  }
}
```

**计算公式**：
```python
total_score = (
    reader_pull_score * 0.20 +
    high_point_score * 0.20 +
    pacing_score * 0.15 +
    consistency_score * 0.20 +
    ooc_score * 0.15 +
    continuity_score * 0.10
)
```
注意：checker 输出的是 0-100 分，需要转换为 80 分制权重分
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/references/checker-output-schema.md
git commit -m "feat: 扩展 checker-output-schema.md 增加总分汇总"
```

---

### Task 5: 更新 webnovel-review 的总分汇总逻辑

**Files:**
- Modify: `webnovel-writer/skills/webnovel-review/SKILL.md`

- [ ] **Step 1: 在 Step 4 生成审查报告时加入总分计算**

在报告结构中加入总分汇总部分：

```markdown
## 综合评分

| 维度 | 得分 | 满分 |
|------|------|------|
| 追读力 | {追读力得分} | 16 分 |
| 爽点密度 | {爽点密度得分} | 16 分 |
| 节奏 | {节奏得分} | 12 分 |
| 连贯性 | {连贯性得分} | 16 分 |
| OOC | {OOC得分} | 12 分 |
| 叙事连贯 | {叙事连贯得分} | 8 分 |
| **总分** | **{总分}/80** | 80 分 |

**等级**: {优秀/合格/需修改/不合格}

### 交付建议
- ≥70：可直接交付
- 60-69：轻微修改后交付
- 50-59：主要问题需修复
- <50：必须大改
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/skills/webnovel-review/SKILL.md
git commit -m "feat: 更新审查报告增加总分汇总显示"
```

---

## Phase 3: references 参考资料扩展

### Task 6: 创建 chapter-guide.md

**Files:**
- Create: `webnovel-writer/references/chapter-guide.md`

- [ ] **Step 1: 创建文件**

```markdown
---
name: chapter-guide
purpose: 章节写作核心要点，供写作时参考
---

# 章节写作核心要点

## 前 20% 法则

**前 20% 决定生死**：读者在开头部分决定是否继续阅读。

必须立即：
- 建立紧张感
- 包含重大事件
- 产生情感冲击

## 十种强力开头技巧

| 技巧 | 描述 | 示例 |
|------|------|------|
| 行动中开场 | 从冲突高潮开始 | "刀光闪过，他已倒在血泊中。" |
| 反常情境 | 呈现不合理场景 | "太阳从西边升起，街上空无一人。" |
| 震撼对话 | 一句话制造冲击 | ""你确定要这么做？"她笑着举起了枪。" |
| 倒计时开场 | 时间压力 | "还有三分钟，炸弹就会爆炸。" |
| 危机时刻 | 最大危机逼近 | "城门即将失守，援军却迟迟未到。" |
| 背叛开场 | 信任崩塌 | "他最信任的人，正站在敌人身边。" |
| 重大选择 | 道德困境 | "救一个人还是救一百人？" |
| 谜团浮现 | 神秘现象 | "监控显示她在房间里，但房间里空无一人。" |
| 重大发现 | 关键线索 | "这封信揭开了尘封十年的真相。" |
| 结局预告 | 预示未来 | "多年后，他回忆起那天，依然心有余悸。" |

## 标准结构

| 阶段 | 占比 | 内容 |
|------|------|------|
| 开头钩子 | 20% | 建立场景、引入冲突 |
| 发展推进 | 50-60% | 深化冲突、积累张力 |
| 高潮时刻 | 15-20% | 冲突爆发、关键转折 |
| 结尾钩子 | 5-10% | 留下悬念、驱动下一章 |

## 节奏控制

- **紧张与缓解交替**：避免持续高强度或低密度
- **脉冲节奏**：每 800-1400 字一个脉冲（短章至少一次实质变化）
- **节拍切换**：动作场景 ↔ 对话场景 ↔ 心理场景

## 检查标准

每章至少满足：
1. ✅ 包含一个不可删除的核心事件
2. ✅ 对话必须推动情节或揭示人物
3. ✅ 有明确的开始和结束（即使结束于悬念）
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/references/chapter-guide.md
git commit -m "feat: 新增 chapter-guide.md 章节写作指南"
```

---

### Task 7: 创建 hook-techniques.md

**Files:**
- Create: `webnovel-writer/references/hook-techniques.md`

- [ ] **Step 1: 创建文件**

```markdown
---
name: hook-techniques
purpose: 悬念设置技巧，供写作和审查时参考
---

# 悬念设置技巧

## 十种经典悬念钩子

| 类型 | 描述 | 读者反应 |
|------|------|---------|
| 突然揭示 | 出乎意料的信息改变现状 | "为什么？" |
| 紧急危机 | 迫在眉睫的危险 | "他必须马上行动" |
| 未完成动作 | 动作被打断，结果未知 | "接下来会发生什么？" |
| 身份反转 | 某人不是我们以为的那样 | "原来是这样！" |
| 两难选择 | 都不理想的选项中做决定 | "他会选哪个？" |
| 神秘物品 | 发现意义不明的东西 | "这是什么意思？" |
| 时间限制 | 明确时限、资源不足 | "来得及吗？" |
| 承诺/威胁 | 明确意图和伤害威胁 | "他会信守承诺吗？" |
| 离奇消失 | 不可能的行为，缺乏解释 | "怎么做到的？" |
| 言外之意 | 表面正常但暗示深层信息 | "他真正想说什么？" |

## 悬念强度等级

| 等级 | 类型 | 读者反应 | 适用位置 |
|-----|------|---------|---------|
| L1 | 好奇悬念 | "这很有趣" | 中间章节 |
| L2 | 关切悬念 | "接下来会发生什么" | 中间章节 |
| L3 | 迫切悬念 | "他必须马上行动" | 高潮章节 |
| L4 | 生存悬念 | "他会活下去吗" | 高潮/结局前 |
| L5 | 终极悬念 | "一切到底是什么意思" | 全书结尾 |

## 章节间悬念连接

### 伏笔技巧
- 早期埋下不起眼的细节
- 让读者忽略其重要性
- 后期揭示时造成"原来如此"效果

### 悬念升级
- 后续悬念应比前一个更强或更深入
- 避免悬念强度原地踏步

### 多线悬念
- 同时维持多条悬念线
- 主线、人物线、关系线、时间线

## 悬念设置禁忌

| 禁忌 | 说明 | 后果 |
|------|------|------|
| 虚假悬念 | 制造紧张但结果是误会 | 读者失去信任 |
| 机械降神 | 突然出现从未提及的解决方案 | 破坏公平性 |
| 过度留白 | 太多未回答问题 | 读者疲劳 |
| 低风险钩子 | 结尾事件不够重要 | 驱动力不足 |

**原则**：每章至少回答一个旧悬念

## 题材适配

| 题材 | 偏好钩子类型 | 强度建议 |
|------|-------------|---------|
| 悬疑 | 突然揭示、神秘物品 | strong |
| 言情 | 两难选择、言外之意 | medium→strong |
| 爽文 | 紧急危机、承诺/威胁 | strong |
| 玄幻 | 身份反转、时间限制 | strong |
| 都市 | 突然揭示、紧急危机 | medium→strong |
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/references/hook-techniques.md
git commit -m "feat: 新增 hook-techniques.md 悬念技巧"
```

---

### Task 8: 创建 quality-checklist.md

**Files:**
- Create: `webnovel-writer/references/quality-checklist.md`

- [ ] **Step 1: 创建文件**

```markdown
---
name: quality-checklist
purpose: 80分质量检查清单，供审查时参考
---

# 质量检查清单 (80分制)

## 评分结构

| 检查维度 | 分值 | 及格线 |
|----------|------|--------|
| 基础要素 | 10 分 | 6 分 |
| 开篇钩子 | 10 分 | 6 分 |
| 情节推进 | 15 分 | 9 分 |
| 人物一致性 | 10 分 | 6 分 |
| 对话有效性 | 10 分 | 6 分 |
| 悬念技巧 | 10 分 | 6 分 |
| 展示而非讲述 | 5 分 | 3 分 |
| 节奏控制 | 5 分 | 3 分 |
| 语言质量 | 5 分 | 3 分 |
| 连贯性 | 10 分 | 6 分 |
| **合计** | **80 分** | **48 分** |

## 各维度检查标准

### 基础要素 (10分)

| 得分 | 标准 |
|------|------|
| 10 | 标题准确、字数达标（2000-2500）、内容完整 |
| 8 | 标题准确、字数略偏、内容完整 |
| 6 | 标题或字数有问题，但内容完整 |
| <6 | 严重缺失 |

### 开篇钩子 (10分)

| 得分 | 标准 |
|------|------|
| 10 | 前200字内建立强烈紧张感或悬念 |
| 8 | 前400字内建立有效钩子 |
| 6 | 开篇平淡但有推进 |
| <6 | 开头冗长无重点 |

### 情节推进 (15分)

| 得分 | 标准 |
|------|------|
| 15 | 冲突明确、张力充足、推进有力 |
| 12 | 有冲突和推进，节奏良好 |
| 9 | 有推进但冲突不明显 |
| <9 | 无明显推进或冲突 |

### 人物一致性 (10分)

| 得分 | 标准 |
|------|------|
| 10 | 行为、对话、反应完全符合人设 |
| 8 | 偶有轻微偏离但整体可信 |
| 6 | 有偏离但可解释 |
| <6 | 严重OOC |

### 对话有效性 (10分)

| 得分 | 标准 |
|------|------|
| 10 | 对话推动情节、揭示性格、无纯说明 |
| 8 | 对话有效，偶有说明性对话 |
| 6 | 有对话但部分为纯说明 |
| <6 | 对话空洞或说明过多 |

### 悬念技巧 (10分)

| 得分 | 标准 |
|------|------|
| 10 | 悬念强烈、承上启下、等级得当 |
| 8 | 有悬念但强度可以更好 |
| 6 | 有悬念但承上启下不足 |
| <6 | 悬念薄弱或断裂 |

### 展示而非讲述 (5分)

| 得分 | 标准 |
|------|------|
| 5 | 完全通过动作/对话/反应展现 |
| 4 | 偶有直接陈述但不影响 |
| 3 | 有展示也有讲述，比例尚可 |
| <3 | 大量直接陈述 |

### 节奏控制 (5分)

| 得分 | 标准 |
|------|------|
| 5 | 紧张与缓解交替、脉冲清晰 |
| 4 | 节奏良好，偶有拖沓 |
| 3 | 有节奏问题但可接受 |
| <3 | 节奏混乱或持续拖沓 |

### 语言质量 (5分)

| 得分 | 标准 |
|------|------|
| 5 | 无AI味、语言流畅、有网文风格 |
| 4 | 偶有AI味但整体可读 |
| 3 | 有明显AI味或翻译腔 |
| <3 | AI味严重 |

### 连贯性 (10分)

| 得分 | 标准 |
|------|------|
| 10 | 时间/地点/人物完全连贯 |
| 8 | 偶有轻微跳跃但整体连贯 |
| 6 | 有跳跃但不影响理解 |
| <6 | 连贯性问题影响阅读 |

## 交付标准

| 分数 | 等级 | 动作 |
|------|------|------|
| ≥70 | 优秀 | 可直接交付 |
| 60-69 | 合格 | 轻微修改后交付 |
| 50-59 | 需修改 | 主要问题需修复 |
| <48 | 不合格 | 必须大改 |
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/references/quality-checklist.md
git commit -m "feat: 新增 quality-checklist.md 80分质量清单"
```

---

### Task 9: 创建 plot-structures.md

**Files:**
- Create: `webnovel-writer/references/plot-structures.md`

- [ ] **Step 1: 创建文件**

```markdown
---
name: plot-structures
purpose: 情节结构模板，供大纲规划时参考
---

# 情节结构模板

## 三幕结构（标准剧情）

| 幕 | 占比 | 内容 |
|---|------|------|
| 第一幕 | 25% | 建置（引入世界、人物、冲突） |
| 第二幕 | 50% | 对抗（主角面对阻碍、成长） |
| 第三幕 | 25% | 解决（高潮、解决冲突） |

### 网文适配

网文通常拉长第二幕：
- 第一幕：10-15%
- 第二幕：60-70%（可包含多个副本/支线）
- 第三幕：15-25%

## 起承转合（中国古典叙事）

| 阶段 | 内容 | 网文应用 |
|------|------|---------|
| 起 | 开端、引入 | 新副本开启、新人物登场 |
| 承 | 发展、积累 | 矛盾积累、能力成长 |
| 转 | 转折、高潮 | 重大揭示、关键战斗 |
| 合 | 结局、收束 | 阶段解决、新悬念引入 |

## 英雄之旅（成长型故事）

| 阶段 | 内容 |
|------|------|
| 普通世界 | 主角在日常中 |
| 冒险召唤 | 收到挑战/任务 |
| 拒绝召唤 | 犹豫/准备 |
| 遇见导师 | 获得指引/能力 |
| 跨越门槛 | 进入新世界 |
| 考验/盟友/敌人 | 成长、结交、树敌 |
| 接近洞穴 | 面临重大挑战 |
| 严峻考验 | 最大挑战 |
| 获得奖励 | 成功/收获 |
| 回去的路 | 带着收获返回 |

## 五段式（单元剧）

| 段 | 内容 |
|----|------|
| A | 建立场景和人物 |
| B | 出现第一个问题 |
| C | 尝试解决问题 |
| D | 出现更大问题 |
| E | 解决并过渡 |

## 副本结构（网文常用）

```
副本名称：[副本名称]

【进入条件】
- 触发原因：
- 参与门槛：

【副本目标】
- 主目标：
- 支线目标：

【副本阶段】
- 第一阶段：[内容]
- 第二阶段：[内容]
- 第三阶段：[BOSS/高潮]

【奖励】
- 能力提升：
- 物品获得：
- 关系变化：

【副本收尾】
- 本章悬念：
- 下章钩子：
```

## 节奏模板

### 升级型节奏（玄幻/修仙）

```
修炼境界：练气 → 筑基 → 金丹 → 元婴 → ...

每境界节奏：
- 突破前：积累/危机（3-5章）
- 突破时：高潮（1-2章）
- 突破后：巩固/新挑战（2-3章）
```

### 言情型节奏

```
感情阶段：陌生 → 认识 → 暧昧 → 确认 → 危机 → 和解

每阶段节奏：
- 接触：2-3章
- 暧昧：3-5章
- 确认：1-2章
- 危机：3-5章
- 和解：2-3章
```

### 悬疑型节奏

```
真相揭露节奏：
- 每5-8章一个小真相
- 每15-20章一个中真相
- 末尾揭露终极真相
```
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/references/plot-structures.md
git commit -m "feat: 新增 plot-structures.md 情节结构模板"
```

---

### Task 10: 创建 dialogue-writing.md

**Files:**
- Create: `webnovel-writer/references/dialogue-writing.md`

- [ ] **Step 1: 创建文件**

```markdown
---
name: dialogue-writing
purpose: 对话写作规范，供写作和审查时参考
---

# 对话写作规范

## 核心原则

### 1. 意图驱动

每句对话必须有明确目的：

| 意图类型 | 说明 | 示例 |
|---------|------|------|
| 试探 | 探测对方意图 | "你最近怎么老是躲着我？" |
| 回避 | 转移话题、隐藏信息 | "今天天气真好啊。" |
| 施压 | 逼迫对方做决定 | "你到底答不答应？" |
| 诱导 | 引导对方说出想要的答案 | "所以你也觉得这样做不对？" |
| 揭示 | 透露关键信息 | "其实，我一直在找你。" |
| 对抗 | 直接冲突 | "你以为你是谁？" |

### 2. 性格体现

对话风格必须反映人物性格：

| 性格 | 对话特征 |
|------|---------|
| 高冷 | 简短、惜字如金、反问多 |
| 热血 | 直接、感叹多、动作描写穿插 |
| 腹黑 | 话里有话、表面客气、暗藏机锋 |
| 温柔 | 语气柔和、关心多、商量口吻 |
| 傲娇 | 嘴硬心软、口是心非 |
| 话痨 | 啰嗦、旁支细节多、爱解释 |

### 3. 信息传递

对话必须推进情节或揭示人物：

**好的对话**：
```
"那把刀，你从哪里得到的？"他盯着她手中的武器。
她没有回答，只是把刀收进鞘中。
"和王家的事有关？"他的声音沉了下去。
```

**坏的对话**（纯说明）：
```
"我们认识很久了。"他说。
"是啊，已经十年了。"她回答。
"从大学开始。"他补充道。
```

### 4. 避免说明

不用对话做纯说明：

| ❌ 错误 | ✅ 正确 |
|--------|--------|
| "我是你爸爸的朋友。" | 直接叫出名字或用动作暗示关系 |
| "这件事很严重。" | 用情绪/反应暗示严重性 |
| "我很担心你。" | 用行为展示担心（皱眉/欲言又止） |

## 对话标签使用

### 避免过度使用

| ❌ 过度使用 | ✅ 精简使用 |
|-----------|-----------|
| 他说、她说、他说、她笑着说 | 善用动作/心理替代标签 |
| X说："..." Y说："..." | 用性格差异让读者区分说话者 |

### 替代标签的方式

```markdown
# 动作替代
他的手握紧："我不会让你得逞。"

# 心理替代
她心里一沉，嘴上却道："随便你。"

# 场景/氛围替代
房间里安静得能听见呼吸。"......"他终于开口，"我错了。"
```

## 对话节奏

### 短对话 vs 长对话

| 类型 | 使用场景 | 示例长度 |
|------|---------|---------|
| 短对话 | 冲突、紧张、快节奏 | 2-5字/句 |
| 长对话 | 解释、谈判、情感 | 1-3句/段 |

### 节奏控制技巧

- 冲突时：短句、打断、省略号
- 温情时：长句、细节、描写
- 悬疑时：留白、反问、沉默

## 常见问题

### 问题1：对话格式化

❌ "你好吗？"他问。
❌ "我很好。"她回答。
❌ "那就好。"他说。

✅ "你好吗？"他问。
✅ 她沉默片刻，才道："......好。"
✅ 他松了口气，没再追问。

### 问题2：角色对话同质化

所有角色说话方式一样 → 给每个角色设计独特的说话习惯

### 问题3：对话承担太多信息

一段对话里塞入太多背景/解释 → 拆分到多段，用动作/反应间隔

## 审查检查项

- [ ] 对话是否有明确意图？
- [ ] 对话风格是否符合人物性格？
- [ ] 是否有纯说明性对话（应改为动作/心理）？
- [ ] 说话标签是否过度使用？
- [ ] 对话节奏是否符合当前场景？
- [ ] 读者能区分谁在说话吗？
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/references/dialogue-writing.md
git commit -m "feat: 新增 dialogue-writing.md 对话写作规范"
```

---

### Task 11: 扩展 core-constraints.md

**Files:**
- Modify: `webnovel-writer/references/shared/core-constraints.md`

- [ ] **Step 1: 在核心法则部分添加四大法则**

找到文件中的"三大定律"部分，在其后添加：

```markdown
## 四大核心法则

| 法则 | 说明 | 执行方式 |
|------|------|---------|
| **展示而非讲述** | 用动作和对话表现，不直接陈述 | 审查时检查是否有大量直接陈述 |
| **冲突驱动剧情** | 每章必须有冲突或转折 | 审查时检查是否有明确冲突 |
| **悬念承上启下** | 每章结尾必须留下钩子 | 审查时检查章末钩子强度 |
| **开头即高潮** | 前20%必须极其吸引人 | 审查时检查开篇钩子 |

### 展示而非讲述 示例

❌ 直接陈述："他很生气。"
✅ 展示："他攥紧拳头，指节发白，猛地将茶杯摔在地上。"

❌ 直接陈述："她很担心他。"
✅ 展示："她站在窗边，目光始终落在门口，手指无意识地绞着衣角。"

### 冲突驱动 示例

每章必须包含以下之一：
- 外部冲突（敌人、困难、阻碍）
- 内部冲突（心理挣扎、两难选择）
- 关系冲突（误解、背叛、立场对立）

### 悬念承上启下 示例

上章悬念 → 本章回应（可部分）→ 新悬念
"她消失在雾中——第三章她再次出现时，身边多了一个人。"

### 开头即高潮 示例

前200字内必须：
- 引入一个核心冲突或悬念
- 建立主要人物的当前状态
- 制造阅读动力
```

- [ ] **Step 2: 提交**

```bash
git add webnovel-writer/references/shared/core-constraints.md
git commit -m "feat: core-constraints.md 引入四大核心法则"
```

---

## Phase 4: 版本升级

### Task 12: 更新版本号和文档

**Files:**
- Modify: `webnovel-writer/.claude-plugin/plugin.json`
- Modify: `webnovel-writer/.claude-plugin/marketplace.json`
- Modify: `README.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 更新 plugin.json 版本号**

```json
{
  "name": "webnovel-writer",
  "version": "5.7.0",
  ...
}
```

- [ ] **Step 2: 更新 marketplace.json 版本号**

找到 marketplace.json 中的版本号，更新为 5.7.0

- [ ] **Step 3: 更新 README.md**

在版本历史部分添加：
```markdown
## v5.7.0 (2026-03-27)

**字数检查系统 + 质量总分 + references 扩展**

### 新增功能
- `references/word-count-rules.md`: 字数检查规则
- `references/chapter-guide.md`: 章节写作指南
- `references/hook-techniques.md`: 悬念设置技巧
- `references/quality-checklist.md`: 80分质量清单
- `references/plot-structures.md`: 情节结构模板
- `references/dialogue-writing.md`: 对话写作规范

### 升级功能
- `checker-output-schema.md`: 增加总分汇总（80分制）
- `core-constraints.md`: 引入四大核心法则
- `webnovel-write`: 集成字数检查
- `webnovel-review`: 集成字数检查和总分汇总
```

- [ ] **Step 4: 更新 docs/CHANGELOG.md**

在顶部添加：
```markdown
## v5.7.0 (2026-03-27)

**字数检查系统 + 质量总分 + references 扩展**

### Phase 1: 字数检查系统
- `references/word-count-rules.md`: 新增字数检查规则
- `webnovel-write/SKILL.md`: Step 1 输出字数建议
- `webnovel-review/SKILL.md`: 审查时强制字数检查

### Phase 2: 质量报告总分层
- `references/checker-output-schema.md`: 增加总分汇总
- `webnovel-review/SKILL.md`: 80分制总分显示

### Phase 3: references 参考资料扩展
- `references/chapter-guide.md`: 章节写作指南（10种开头技巧）
- `references/hook-techniques.md`: 悬念设置技巧（10种钩子 + 5级强度）
- `references/quality-checklist.md`: 80分质量检查清单
- `references/plot-structures.md`: 情节结构模板
- `references/dialogue-writing.md`: 对话写作规范
- `references/shared/core-constraints.md`: 引入四大核心法则
```

- [ ] **Step 5: 提交**

```bash
git add webnovel-writer/.claude-plugin/plugin.json
git add webnovel-writer/.claude-plugin/marketplace.json
git add README.md
git add docs/CHANGELOG.md
git commit -m "chore: 升级版本号到 v5.7.0"
```

---

## 总结

实施顺序：
1. Phase 1（Task 1-3）：字数检查系统
2. Phase 2（Task 4-5）：质量总分
3. Phase 3（Task 6-11）：references 扩展
4. Phase 4（Task 12）：版本升级

共计：12 个 Task，预计 12 次提交
