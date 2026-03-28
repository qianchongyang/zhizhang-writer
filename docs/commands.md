# 从 0 到 100：网文写作全流程指南

本文档描述如何使用 `webnovel-writer` 从零开始完成一部长篇网文（200万字量级）。

---

## 一、项目初始化

### `/webnovel-init`

初始化小说项目，创建标准目录结构和状态文件。

**使用场景：**
- 第一次开始写新小说时
- 在一个空目录下建立网文项目时

**执行后产出：**
```
PROJECT_ROOT/
├── .webnovel/
│   ├── state.json                    # 项目状态文件
│   ├── project_memory.json           # 项目级技巧记忆
│   ├── story_technique_blueprint.json # 项目技巧蓝图
│   ├── control/
│   │   └── chapter_technique_plans/  # 章节技巧编排缓存
│   └── memory/
│       └── story_memory.json         # 跨章节故事记忆（含归档层）
├── 设定集/
│   ├── 世界观.md
│   ├── 角色模板.md
│   └── 力量体系.md
└── 大纲/
    └── 总纲.md
```

**交互流程：**
```
/webnovel-init
→ 输入：小说名称、题材、简介
→ 生成：项目骨架、状态文件、设定模板
→ 自动生成：项目技巧蓝图（hook/coolpoint/反模板/行为模型）
```

---

## 二、建立大纲

### `/webnovel-plan [卷号]`

生成卷级规划与章节大纲。

**使用场景：**
- 写完总纲后，需要细化成具体章节
- 需要在大规模写作前确定每章的核心情节点

**参数：**
- `卷号`：指定要规划的卷，如 `/webnovel-plan 1` 或 `/webnovel-plan 2-3`

**执行后产出：**
```
大纲/
├── 第1卷.md           # 卷级大纲
└── 第1卷/
    ├── 第1章.md
    ├── 第2章.md
    └── ...
```

**输入：**
- 总纲.md（已存在）
- 题材、人设、核心冲突

**输出：**
- 章节数 × 章节大纲（每章 200-500 字的情节点）

---

## 三、写作主流程

### `/webnovel-write [章号]`

执行完整章节创作流程（上下文 → 草稿 → 审查 → 润色 → 数据落盘）。

**参数：**
- `章号`：必填，如 `/webnovel-write 1`

**可选 flags：**
| Flag | 说明 | 适用场景 |
|------|------|---------|
| `--fast` | 快速模式，跳过部分审查 | 赶稿、初稿 |
| `--minimal` | 极简模式，只做基本检查 | 草稿测试 |

**完整流程（标准模式）：**

```
Step 1 - 上下文构建
  → 写前硬闸门（不通过即中断）：
      • 本章必须存在可用大纲
      • 大纲需满足最小章节契约：目标/冲突/动作/结果/代价/钩子
      • 可选状态变化阈值：`context_min_state_changes_per_chapter`
  → Context Agent 加载：
      • 本章大纲
      • 前3章摘要
      • 角色状态（外貌/穿着/关系）
      • 物品状态
      • 时间线
      • 项目技巧蓝图（story_technique_blueprint）
      • 本章追读力策略
      • 章节技巧编排（chapter_technique_plan）

Step 2 - 草稿生成
  → 基于大纲和上下文生成 2000-2500 字正文
  → 优先消费结构化技巧编排：
      • 章型（铺压 / 对抗 / 释放）
      • 开篇钩子 / 章中微兑现 / 高潮模式 / 章末钩子
      • 段落节拍：trigger → reaction → action → result → aftermath

Step 3 - 分组审查
  → 核心审查器（始终执行）：
      • consistency-checker：设定一致性（战力/地点/时间线/外貌）
      • continuity-checker：场景与叙事连贯性
      • ooc-checker：人物行为是否偏离人设/行为模型
  → 条件审查器（auto 路由命中时执行）：
      • reader-pull-checker：钩子强度、期待管理、追读力、说明性对白风险
      • high-point-checker：爽点密度、质量、兑现后余波
      • pacing-checker：Strand 比例、断档、信息密度与动作闭环

Step 4 - 润色优化
  → 根据审查报告针对性优化
  → 保持人设、修复冲突、增强爽点

Step 5 - 数据落盘（Data Agent）
  → 状态回写：
      • 角色状态变化 → state.json
      • 物品状态变化 → state.json
      • 场景/地点 → index.db
      • 势力/门派 → index.db
      • 章节摘要 → summaries/ch{NNNN}.md
      • 技巧执行结果 → project_memory.json
      • 风格样本 → style profiles（仅 score >= 80）
  → RAG 向量索引（可选，未配置时跳过）

完整工作流（7步）：
Step 0 → 预检与上下文最小加载
Step 0.5 → 工作流断点记录
Step 1 → Context Agent（生成创作执行包）
Step 1.5 → 主Agent精简上下文加载
Step 2A → 草稿生成（优先读取 chapter_technique_plan）
Step 2B → 风格适配（--fast/--minimal 跳过）
Step 3 → 分组审查（核心3个 + 条件3个）
Step 4 → 润色（问题修复 + Anti-AI 检测）
Step 5 → Data Agent（状态、索引、技巧记忆回写）
Step 6 → Git 备份（若 Git 可用）
```

**写作模式：**

| 模式 | 速度 | 质量 | 适用 |
|------|------|------|------|
| 标准 | 慢 | 高 | 重要章节、存稿 |
| `--fast` | 中 | 中 | 日常更新 |
| `--minimal` | 快 | 低 | 草稿测试 |

---

## 四、大纲调整

### `/webnovel-adjust`

动态调整大纲，支持插入副本、修正冲突、修改章节内容。

**使用场景：**
- 写到一半发现大纲有问题
- 需要临时插入副本/回忆杀
- 发现时间线矛盾需要修正

**功能：**
- 关系铺垫插入（3-5章）
- 事件铺垫插入（2-3章）
- 副本扩展（5-10章）
- 章节重编号（自动更新）
- 时间线同步

---

## 五、进度审查

### `/webnovel-review [范围]`

对历史章节做多维质量审查，输出质量报告，并汇总技巧执行结果。

**参数：**
- `范围`：章号范围，如 `/webnovel-review 1-5` 或 `/webnovel-review 45`

**审查分组：**

| 分组 | 审查器 | 说明 |
|------|--------|------|
| 核心（始终执行） | consistency-checker | 战力/地点/时间线/外貌一致性 |
| 核心（始终执行） | continuity-checker | 场景衔接、叙事流畅度 |
| 核心（始终执行） | ooc-checker | 人物行为是否符合人设 |
| 条件（auto 命中） | reader-pull-checker | 钩子强度、断章位置、追读力 |
| 条件（auto 命中） | high-point-checker | 爽点密度、质量、期待感、余波层 |
| 条件（auto 命中） | pacing-checker | Quest/Fire/Constellation 比例、信息密度 |

**输出示例：**
```
章节 45 质量报告
总分：85/100

[Core] 核心审查器：
  - consistency: 82/100 - 通过
  - continuity: 85/100 - 通过
  - ooc: 90/100 - 通过

[Extended] 条件审查器：
  - reader-pull: 75/100 - 结尾钩子偏弱，建议增加悬念
  - high-point: 78/100 - 爽点密度不足
  - pacing: 71/100 - Quest 占比偏高，感情线偏弱

[Issues] 问题摘要：
  - critical: 0
  - high: 1 (时间线轻微不一致)
  - medium: 2

[Technique] 技巧执行摘要：
  - applied: hook:悬念钩, coolpoint:身份掉马
  - signals:
      dialogue_exposition_risk: false
      emotion_loop_integrity: true
      aftermath_presence: true
```

---

## 六、信息查询

### `/webnovel-query [关键词]`

查询角色、伏笔、节奏、状态等运行时信息。

**使用场景：**
- 写之前查角色当前状态
- 确认某个伏笔是否已埋下
- 检查某个物品的当前持有者

**示例：**
```bash
/webnovel-query 萧炎           # 查询角色状态
/webnovel-query 伏笔           # 查看所有伏笔
/webnovel-query 紧急            # 查看紧急伏笔（已到期）
/webnovel-query 玄天秘境        # 查询地点信息
/webnovel-query 青龙帮          # 查询势力信息
```

---

## 七、任务恢复

### `/webnovel-resume`

任务中断后自动识别断点并恢复。

**使用场景：**
- 写作被 Ctrl+C 中断
- Claude Code 会话意外中断
- 网络断连导致 API 调用失败

---

## 八、可视化面板

### `/webnovel-dashboard`

启动只读可视化面板，查看项目状态与写作驾驶舱。

**功能：**
- 写作驾驶舱首页：本章大纲、高优先级召回、记忆健康、写作建议
- 记忆与召回页：`story_recall`、`archive_recall`、结构化变化账本
- 章节列表与进度
- 角色关系图谱
- 物品流转记录
- 时间线可视化
- 实体统计

**说明：**
- 默认只读，不会修改项目文件
- 适合写作决策、排查上下文、实体关系与记忆链路

---

## 九、模式学习

### `/webnovel-learn [内容]`

从当前会话或用户输入中提取可复用写作模式。

**使用场景：**
- 发现某个写作技巧很有效，想复用
- 需要记录某个成功的情节设计

**示例：**
```bash
/webnovel-learn "本章的危机钩设计很有效，悬念拉满"
/webnovel-learn "主角升级的节奏把控得很好，每3章一个小高潮"
```

---

## 十、自动化批量写作

### 批量写作命令

自动化连续执行多章节写作，支持夜间模式、质量门控、断点恢复。

```bash
# 从第10章写到第40章
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" \
  --project-root "/path/to/你的小说项目" \
  batch run \
  --from 10 \
  --to 40
```

### 批量写作参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--from` | int | 必填 | 起始章节号 |
| `--to` | int | 必填 | 结束章节号 |
| `--night-mode` | flag | 关闭 | 夜间模式（限制 AI 调用次数） |
| `--max-calls` | int | 1400 | 夜间模式 AI 调用上限 |
| `--min-quality-score` | float | 75.0 | 最低质量分数阈值（低于此值自动停止） |

### 夜间模式

限制 AI 调用次数，适合夜间无人值守：

```bash
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" \
  --project-root "/path/to/你的小说项目" \
  batch run \
  --from 10 \
  --to 40 \
  --night-mode \
  --max-calls 500
```

### 断点恢复

写作中断后，从断点继续：

```bash
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" \
  --project-root "/path/to/你的小说项目" \
  batch resume
```

### 质量等级参考

| 分数范围 | 质量等级 | 建议操作 |
|----------|----------|----------|
| 90-100 | 优秀 | 可直接发布 |
| 80-89 | 良好 | 可发布，有少量优化空间 |
| 70-79 | 中等 | 建议润色后发布 |
| 60-69 | 较差 | 需要大幅修改 |
| <60 | 很差 | 建议重写 |

### 批量写作产物

| 产物 | 位置 | 说明 |
|------|------|------|
| 章节正文 | `正文/第NNNN章-{标题}.md` | 润色后的可发布章节 |
| 审查报告 | `审查报告/第NNNN-NNNN章审查报告.md` | 综合审查结果 |
| 章节摘要 | `.webnovel/summaries/chNNNN.md` | 供后续章节消费的摘要 |
| 状态文件 | `.webnovel/state.json` | 更新的角色/势力/物品状态 |
| 索引文件 | `.webnovel/index.db` | 更新的向量索引 |

### 批量写作最佳实践

1. **首次批量写作**：先跑 3-5 章测试，观察平均得分和 AI 消耗
2. **夜间模式**：建议 `--max-calls 500-800`，留有余量
3. **质量门控**：首次写作建议用默认值 75 分，确认流程稳定后可提高
4. **定期检查**：每隔 10 章检查一次输出质量
5. **及时备份**：定期提交 git，保留历史版本
6. **写前契约检查**：批量前先确认各章大纲具备“目标/冲突/动作/结果/代价/钩子”，避免中途被硬闸门拦截

### 常见失败与修复

- 报错：`缺少可用大纲`
  - 含义：`大纲/` 下未找到对应章节可解析内容
  - 修复：补齐卷纲或章节大纲后重试

- 报错：`大纲缺少关键项`
  - 含义：未满足最小章节契约（目标/冲突/动作/结果/代价/钩子）
  - 修复：在该章大纲中逐项补齐，建议使用 `字段: 内容` 结构

- 报错：`状态变化`
  - 含义：启用最小状态变化阈值时，可识别状态变化信号不足
  - 修复：在动作/结果/代价中加入可追踪变化（如“突破/失去/结盟/暴露/受伤/离开”等）

---

## 十一、工作流程图

```
                    ┌─────────────────┐
                    │  /webnovel-init │ → 初始化项目
                    └────────┬────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │      /webnovel-plan      │ → 生成卷级大纲
              └────────────┬─────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌──────────┐   ┌──────────┐   ┌──────────┐
     │ 第1卷.md │   │ 第2卷.md │   │ 第3卷.md │
     └────┬─────┘   └────┬─────┘   └────┬─────┘
          │              │              │
          ▼              ▼              ▼
    ┌─────────────────────────────────────────┐
    │          /webnovel-write [章号]          │ ← 主循环
    │  ┌────────────────────────────────────┐  │
    │  │ Step 0: 预检与上下文最小加载       │  │
    │  │ Step 0.5: 工作流断点记录           │  │
    │  │ Step 1: Context Agent（创作执行包）│  │
    │  │ Step 1.5: 精简上下文加载           │  │
    │  │ Step 2A: 草稿生成                  │  │
    │  │ Step 2B: 风格适配（可选）          │  │
    │  │ Step 3: 分组审查（核心3+条件3）    │  │
    │  │ Step 4: 润色 + Anti-AI 检测       │  │
    │  │ Step 5: Data Agent（状态回写）     │  │
    │  │ Step 6: Git 备份                  │  │
    │  └────────────────────────────────────┘  │
    └────────────────────┬────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  /webnovel-review   │ → 定期审查（每5-10章）
              │  /webnovel-query    │ → 随时查询
              │  /webnovel-adjust   │ → 按需调整
              └─────────────────────┘
```

**写作模式：**
| 模式 | 跳过步骤 | 说明 |
|------|---------|------|
| 标准 | 无 | 完整7步流程 |
| `--fast` | Step 2B | 跳过风格适配 |
| `--minimal` | Step 2B + 条件审查器 | 只跑核心3个审查器 |

---

## 十二、命令索引

### Skill 命令

| 命令 | 作用 | 使用频率 |
|------|------|---------|
| `/webnovel-init` | 初始化项目 | 1次/项目 |
| `/webnovel-plan [卷号]` | 生成大纲 | 1-3次/卷 |
| `/webnovel-write [章号]` | 写章节 | 多次/天 |
| `/webnovel-review [范围]` | 审查质量 | 定期 |
| `/webnovel-query [关键词]` | 查询信息 | 按需 |
| `/webnovel-adjust` | 调整大纲 | 按需 |
| `/webnovel-resume` | 恢复任务 | 按需 |
| `/webnovel-dashboard` | 可视化面板 | 按需 |
| `/webnovel-learn [内容]` | 记录模式 | 按需 |

### Unified CLI 子命令（工程/运维层）

统一入口：`python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" ...`

| 子命令 | 作用 |
|------|------|
| `preflight` | 环境与路径预检 |
| `where` | 解析并输出当前 project_root |
| `use` | 绑定当前工作区的项目指针 |
| `index/state/rag/context/style/entity/migrate` | 数据与检索链路操作 |
| `workflow/status/update-state/backup/archive` | 运维与状态维护脚本转发 |
| `extract-context` | 导出章节上下文（text/json，受大纲与章节契约硬闸门约束） |
| `merge` | 合并分组审查结果（`rev1/rev2`） |

---

## 十三、写作节奏建议

**日常更新（2000-3000字/天）：**
```bash
/webnovel-write 45 --fast   # 快速模式写草稿
/webnovel-review 44-45      # 写完检查上章质量
/webnovel-query 主角        # 确认状态再写下一章
```

**周末存稿（5000-10000字/天）：**
```bash
/webnovel-write 45          # 标准模式
/webnovel-write 46
/webnovel-write 47
/webnovel-review 45-47     # 批量审查
```

**阶段总结（每20-30章）：**
```bash
/webnovel-review 1-30       # 全面审查前半部分
/webnovel-dashboard         # 查看整体进度
/webnovel-learn "这几章的升级节奏把控..."  # 记录成功模式
```
