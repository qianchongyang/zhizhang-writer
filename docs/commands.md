# 织章 Zhizhang Writer — 操作手册

> **版本**：v5.25.0
> **命令前缀**：`/zhizhang-*` 为对外别名，内部实现委托 `/webnovel-*`
> **状态说明（2026-03-30）**：本文以 `main` 主线已验证能力为准。动态大纲完整链路尚未并入主线；`/zhizhang-menu` 当前也不是“所有功能的完整执行入口”。

---

## 场景导航

遇到问题时，先看这里：

| 你的目标 | 用哪个命令 | 章节 |
|---------|-----------|------|
| 写一章小说 | `/zhizhang-write 45` | [场景一](#场景一写小说) |
| 第一次建新项目 | `/zhizhang-init` | [场景二](#场景二初始化新项目) |
| 生成卷+章大纲 | `/zhizhang-plan 1` | [场景三](#场景三做大纲规划) |
| 审查已写章节 | `/zhizhang-review 1-10` | [场景四](#场景四审查章节) |
| 查角色/伏笔/状态 | `/zhizhang-query 萧炎` | [场景五](#场景五查询状态) |
| 写了一半中断了 | `/zhizhang-resume` | [场景六](#场景六恢复中断任务) |
| 手动调大纲/插副本 | `/zhizhang-adjust` | [场景七](#场景七调整大纲) |
| 只想看菜单 | `/zhizhang-menu` | 任何时候 |

---

## 场景一：写小说

**命令**：`/zhizhang-write 章号 [flags]`

**适用**：每章正式写作，是最常用的命令。

```
/zhizhang-write 45         # 标准模式，写第45章
/zhizhang-write 45 --fast  # 快速模式，跳过风格适配
/zhizhang-write 45 --turbo # Turbo 模式，追求日更速度
/zhizhang-write 45 --minimal # 极简模式，只做基础检查
```

### 速度与质量

| 模式 | 速度 | 质量 | 适用场景 |
|------|------|------|---------|
| 标准 | ~30分钟 | 最高 | 重要章节、需要存稿 |
| `--fast` | ~20分钟 | 中高 | 日常更新 |
| `--turbo` | ~15分钟 | 中 | 赶进度、日更 |
| `--minimal` | ~10分钟 | 基础 | 草稿测试、快速验证 |

### 标准模式完整流程（Step 0 → Step 6）

```
Step 0: 预检
  └─ 检查项目状态、Git 可用性、断点记录

Step 1: Context Agent（构建创作上下文）
  ├─ 加载 state.json（角色/关系/势力/时间线/伏笔）
  ├─ 加载本章大纲
  ├─ 加载前3章摘要
  ├─ 加载设定集（角色卡/世界观/力量体系）
  ├─ 生成创作任务书（task_summary + constraints + style_guide）
  └─ 输出：ctx_ch0045.json（供 Step 2A 直接消费）

Step 2A: 正文起草（~2000-2500字）
  ├─ 读取 ctx_ch0045.json
  ├─ 按章型（铺压/对抗/释放）生成正文
  └─ 输出：正文/第0045章-{标题}.md

Step 2B: 风格适配
  ├─ 读取 style-adapter.md
  ├─ 消除模板腔/说明腔/机械腔
  └─ 输出：覆盖原文件

Step 3: 六维审查（核心3个始终并行 + 条件3个按需）
  ├─ [始终] consistency-checker  — 战力/地点/时间线/外貌一致性
  ├─ [始终] continuity-checker   — 场景衔接、叙事连贯
  ├─ [始终] ooc-checker          — 人物行为是否偏离人设
  ├─ [按需] reader-pull-checker  — 钩子强度、追读力、说明性对白风险
  ├─ [按需] high-point-checker  — 爽点密度、质量、期待感
  └─ [按需] pacing-checker      — Quest/Fire/Constellation 比例

Step 4: 润色修复
  ├─ critical 问题必须修复
  ├─ high 问题尽量修复
  └─ Anti-AI 终检（判断是否像 AI 写的）

Step 5: Data Agent（数据落盘）
  ├─ B: AI 实体提取（角色/地点/物品/关系）
  ├─ C: 实体消歧
  ├─ D: 写入 state.json + index.db
  ├─ E: 写入章节摘要 summaries/ch0045.md
  ├─ F: AI 场景切片
  ├─ G: RAG 向量索引（已配置Embedding时）
  └─ H: 风格样本（仅 score ≥ 80 时）

Step 5.5A: 动态大纲评估（设计目标，未并入主线）
  ├─ 评估当前窗口是否需要调整
  ├─ 分析插入副本/重排的影响范围
  └─ 若需要调整 → 进入 Step 5.5B

Step 5.5B: 动态大纲执行（设计目标，未并入主线）
  ├─ 扩展活动窗口
  ├─ 插入铺垫章节
  └─ 更新 outline_runtime.json + outline_adjustments.jsonl
  ⚠️ 调纲失败时阻断 Step 6，不产生 Git 提交

Step 6: Git 备份
  └─ git add . && git commit -m "第45章: {标题}"
```

### Turbo 模式特殊说明

`--turbo` 模式下：
- Step 2B（风格适配）跳过
- Step 4（润色）跳过
- 核心 3 审查器并行执行（更快）
- 适合：每日赶更新、不需要精修的章节

### 动态大纲（Step 5.5A/5.5B，设计中）

以下内容描述的是目标形态与动态大纲分支实现方向，不代表 `main` 已具备完整自动链路：

- **Step 5.5A 影响分析**：评估后续窗口是否需要插入副本（铺垫章节）、章节重排、活动窗口扩展
- **Step 5.5B 执行调整**：在影响可接受时自动扩展窗口，同时通过锚点保护确保不偏离主线
- **失败处理**：调纲失败时 `Step 6 Git 提交` 被阻断，runtime 完整回滚，不产生脏数据
- **硬上限**：每次扩窗不超过当前窗口的 1.5 倍

**窗口大小**：
- 默认 25 章（可通过 `.webnovel/project_config.json` 覆盖为其他值）
- 用户覆盖方式：`{"default_window_size": 30}`

---

## 场景二：初始化新项目

**命令**：`/zhizhang-init`

**适用**：第一次开始写新小说，在空目录下创建完整项目骨架。

```
/zhizhang-init
→ 选择题材模板（玄幻/都市/古言等）
→ 输入：小说名称、简介、核心卖点
→ 输入：主角名、金手指类型、金手指风格
→ 输入：女主配置（无/单/多）、反派分层
→ 生成：完整项目骨架
```

### 交互流程（6 Steps）

```
Step 1: 小说基本信息（名称/题材/简介/卖点）
Step 2: 主角设定（姓名/背景/金手指）
Step 3: 女主/反派配置
Step 4: 世界观与力量体系
Step 5: 生成项目结构
Step 6: 确认并写入文件
```

### 初始化产物

```
PROJECT_ROOT/
├── .webnovel/
│   ├── state.json              # 运行时状态（空）
│   ├── project_memory.json     # 项目级技巧记忆
│   ├── story_technique_blueprint.json  # 题材技巧蓝图
│   ├── memory/
│   │   └── story_memory.json   # 跨章节故事记忆
│   └── control/
│       └── chapter_technique_plans/
├── 设定集/
│   ├── 世界观.md
│   ├── 力量体系.md
│   ├── 主角卡.md
│   ├── 金手指设计.md
│   └── 角色库/
├── 大纲/
│   └── 总纲.md                  # 等待填写
└── 正文/                        # 等待章节
```

### init 参数（可选）

| 参数 | 说明 |
|------|------|
| `--target-words` | 目标总字数（默认 2,000,000） |
| `--target-chapters` | 目标总章节数（默认 600） |
| `--protagonist-name` | 主角姓名 |
| `--golden-finger-name` | 金手指称呼 |
| `--golden-finger-type` | 金手指类型（系统流/鉴定流/签到流等） |

---

## 场景三：做大纲规划

**命令**：`/zhizhang-plan [卷号]`

**适用**：
- 写完总纲后，需要细化成具体章节
- 需要在大规模写作前确定每章的核心情节点

```
/zhizhang-plan 1          # 生成第1卷的完整大纲
/zhizhang-plan 1-3        # 批量生成第1-3卷大纲
/zhizhang-plan            # 交互式选择卷范围
```

### 流程（8 Steps）

```
Step 1: 加载项目数据（state.json / 总纲 / 设定集）
Step 2: 补齐设定集基线（从总纲增量）
Step 3: 选择卷并确认范围
Step 4: 生成卷节拍表（节拍表.md）
Step 4.5: 生成卷时间线表（时间线.md）
Step 5: 生成卷骨架（Strand Weave / 爽点密度规划）
Step 6: 批量生成章节大纲（按20章/批）
Step 7: 回写设定集（增量补充）
Step 8: 验证 + 保存 + 更新 state.json
```

### 产出文件

```
大纲/
├── 第1卷.md              # 卷级大纲
├── 第1卷-节拍表.md       # 每章节拍点
├── 第1卷-时间线.md       # 事件时间轴
└── 第1卷-详细大纲.md     # 章节清单
```

---

## 场景四：审查章节

**命令**：`/zhizhang-review 范围`

**适用**：
- 写完一批章节后，想了解整体质量
- 需要找出 continuity / consistency / OOC 问题
- 需要生成质量报告

```
/zhizhang-review 1-5       # 审查第1到5章
/zhizhang-review 45        # 审查单章
/zhizhang-review 10-20    # 批量审查
```

### 审查维度

| 审查器 | 始终执行 | 说明 |
|--------|---------|------|
| consistency-checker | ✅ | 战力/地点/时间线一致性 |
| continuity-checker | ✅ | 场景衔接、叙事连贯 |
| ooc-checker | ✅ | 人物行为是否偏离人设 |
| reader-pull-checker | 按需 | 钩子强度、追读力 |
| high-point-checker | 按需 | 爽点密度与质量 |
| pacing-checker | 按需 | Quest/Fire/Constellation 比例 |

### 输出

- 质量报告：`审查报告/第1-5章审查报告.md`
- 审查指标写入 `index.db`
- critical 问题会暂停并询问处理方式

---

## 场景五：查询状态

**命令**：`/zhizhang-query 关键词`

**适用**：
- 写之前查角色当前状态
- 确认某个伏笔是否已埋下
- 检查某个物品的当前持有者

```
/zhizhang-query 萧炎           # 查询角色状态
/zhizhang-query 伏笔           # 查看所有伏笔
/zhizhang-query 紧急           # 查看紧急伏笔（已到期）
/zhizhang-query 玄天秘境        # 查询地点信息
/zhizhang-query 青龙帮          # 查询势力信息
/zhizhang-query 金手指          # 查询金手指状态
/zhizhang-query 节奏            # 查看 Strand Weave 比例
```

---

## 场景六：恢复中断任务

**命令**：`/zhizhang-resume`

**适用**：
- 写章节时被 Ctrl+C 中断
- Claude Code 会话意外中断
- 网络断连导致 API 调用失败

### 恢复流程

```
Step 1: 检测中断状态（workflow detect）
Step 2: 展示恢复选项
  ├─ 选项A：删除重来（推荐）
  └─ 选项B：Git 回滚
Step 3: 用户确认
Step 4: 执行恢复
Step 5: 继续任务（可选）
```

---

## 场景七：调整大纲

**命令**：`/zhizhang-adjust`

> **注意**：这是调试/极端修复模式。动态大纲完整链路目前未并入 `main`，因此这里不能视为“主线已自动内嵌”的已验证能力。

**适用场景**：
- 调试：大纲存在逻辑错误需要人工定位
- 极端修复：数据损坏等紧急处理
- 手动插入复杂副本链（超出自动处理范围）

### 功能

- 关系铺垫插入（3-5章）
- 事件铺垫插入（2-3章）
- 副本扩展（5-10章）
- 章节重编号（自动更新）
- 时间线同步
- 时间逆流/物品凭空出现/倒计时跳跃 检测与修复

---

## 附录

### A. 交互式菜单

**命令**：`/zhizhang-menu` 或 `/cnw`

文字菜单，可视化程度低的环境下也能用。
当前主线中它更接近导航页与局部工具页，不应视为覆盖所有功能的完整执行入口。

---

### B. 统一 CLI（webnovel.py）

`webnovel.py` 是内核层统一 CLI，提供稳定的底层脚本入口，但不等于所有对外命令都有同名 CLI 子命令。
当前应以 `python webnovel.py --help` 的真实输出为准：

```bash
# 环境校验
python webnovel.py preflight          # 预检环境
python webnovel.py where               # 显示项目路径

# 状态报告
python webnovel.py status --focus all        # 完整健康报告
python webnovel.py status --focus strand     # 节奏分析
python webnovel.py status --focus urgency     # 伏笔紧急度
python webnovel.py status --focus characters  # 角色掉线

# 健康与修复（v5.23）
python webnovel.py health               # 数据一致性检查
python webnovel.py repair              # 自动修复不一致

# 读者反馈（v5.24）
python webnovel.py feedback            # 收集钩子/节奏/OOC/文笔反馈

# 索引管理
python webnovel.py index process-chapter --chapter 45
python webnovel.py rag index-chapter --chapter 45

# Git 备份
python webnovel.py backup "第45章提交"

# 审查合并
python webnovel.py merge --group1 rev1.json --group2 rev2.json --output merged.json
```

说明：
- 当前 `main` 没有 `write` 子命令。
- 当前 `review` 在统一 CLI 中只有占位和 `merge` 相关能力，完整审查流程仍依赖 Skill 编排。
- `/zhizhang-write`、`/zhizhang-review` 是对外协作入口，不等于内核层存在同名完整 CLI。

---

### C. 数据文件说明

| 文件/目录 | 用途 |
|-----------|------|
| `.webnovel/state.json` | 运行时真相（角色状态/关系/势力/时间线/伏笔） |
| `.webnovel/index.db` | SQLite 实体索引（角色/别名/关系/状态变化） |
| `.webnovel/vectors.db` | SQLite RAG 向量（语义检索） |
| `.webnovel/outline_runtime.json` | 动态大纲运行层（主线已存在） |
| `.webnovel/outline_adjustments.jsonl` | 动态大纲调整记录（待完整链路并入主线后再视为稳定能力） |
| `.webnovel/project_config.json` | 项目级配置（可覆盖 default_window_size） |
| `.webnovel/summaries/ch*.md` | 章节摘要（供后续章节消费） |
| `.webnovel/story_memory.json` | 跨章节稳定记忆层 |
| `.webnovel/project_memory.json` | 项目级技巧记忆 |
| `.webnovel/workflow_state.json` | 工作流断点记录 |

---

### D. 参数参考

| 参数 | 可用命令 | 用途 |
|------|---------|------|
| `--turbo` | `/zhizhang-write` | 跳过风格适配+润色，核心3审查器并行，追求日更速度 |
| `--fast` | `/zhizhang-write` | 跳过风格适配，标准流程其余步骤完整执行 |
| `--minimal` | `/zhizhang-write` | 仅核心3审查器，跳过条件审查器 |
| `--focus strand` | status | Strand Weave 节奏分析 |
| `--focus urgency` | status | 伏笔紧急度分析 |
| `--focus characters` | status | 角色掉线分析 |
| `--focus foreshadowing` | status | 伏笔超时分析 |
| `--focus pacing` | status | 爽点节奏分布 |
| `--focus relationships` | status | 人际关系图谱 |

---

### E. 质量分数参考

| 分数 | 等级 | 建议操作 |
|------|------|---------|
| 90-100 | 优秀 | 可直接发布 |
| 80-89 | 良好 | 可发布，有少量优化空间 |
| 70-79 | 中等 | 建议润色后发布 |
| 60-69 | 较差 | 需要大幅修改 |
| <60 | 很差 | 建议重写 |

---

### F. 写作驾驶舱（Dashboard）

**命令**：`/zhizhang-dashboard`

只读可视化面板，查看：
- 写作驾驶舱首页（本章大纲/高优先级召回/记忆健康）
- 记忆与召回（story_recall / archive_recall）
- 章节列表与进度
- 角色关系图谱
- 物品流转记录
- 时间线可视化
- 实体统计

适合：写作决策前排查上下文、实体关系与记忆链路。

---

### G. 批量写作（高级）

面向自动化工作流（日更脚本、CI/CD、无人值守）。
状态说明：批量能力存在脚本实现，但质量闸门尚未完全闭环，当前应按“高级/实验性”理解。

```bash
python webnovel.py batch run --from 10 --to 40
python webnovel.py batch run --from 10 --to 40 --night-mode --max-calls 500
python webnovel.py batch resume
```

---

### H. 项目配置文件

**位置**：`.webnovel/project_config.json`

**用途**：覆盖系统默认值

```json
{
  "default_window_size": 30
}
```

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `default_window_size` | 25 | 动态大纲活动窗口大小（章数） |

---

*最后更新：v5.25.0*
