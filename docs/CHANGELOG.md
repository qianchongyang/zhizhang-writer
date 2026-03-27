# 版本变更日志

本文档记录所有正式版本的变更内容。

---

## v5.17.0 (2026-03-27)

**InkOS 启发链路收口**

### 核心升级
- 新增控制面运行时对象：`author_intent`、`current_focus`、`chapter_intent`
- `ContextManager` 现在会稳定产出本章任务书：`chapter_goal / must_resolve / priority_memory / story_risks / hard_constraints`
- `story_memory` 新增独立 `emotional_arcs` 层，写前召回会带出当前角色情绪状态和最近转折
- `Data Agent` 数据链支持 `observer_output -> reflector_delta -> validator -> state_manager` 的渐进式两阶段模式
- `workflow_manager` 新增 `workflow_trace`，可在 dashboard 与恢复链路中追踪当前阶段
- Dashboard summary 接入任务书、语言疲劳信号和 workflow trace，首页能直接看到本章 focus 与风险

### 审查与质量
- 新增轻量去 AI 味信号 `style_fatigue`，覆盖重复表达、模板化动作和总结式叙述
- `status_reporter` 现在会显示情绪弧线角色数、语言疲劳告警数和情绪长期未更新提示

### 文档与契约
- 新增运行时模板：`author_intent.md`、`current_focus.md`、`chapter-intent.md`
- 更新 `context-agent`、`data-agent` 和 `Step 1.5 Contract`，把控制面、情绪弧线、Observer/Reflector 契约写入文档

### 验证
- `test_context_manager.py`
- `test_extract_chapter_context.py`
- `test_state_manager_extra.py`
- `test_status_reporter.py`
- `test_workflow_manager.py`
- `dashboard/tests/test_app.py`
- `dashboard/frontend npm run build`

## v5.13.3 (2026-03-27)

**记忆页页内快跳**

### 核心升级
- `/webnovel-dashboard` 的“记忆与召回”页新增页内快跳，支持一键定位到高优先级召回、归档召回、记忆健康和写作建议
- 记忆页继续保持摘要优先，但现在可以更快从总览切到对应详情，减少手动滚动

### 体验优化
- 更适合连续写作时快速核对某一块记忆
- 详情仍保留折叠式结构，避免页面回到“信息堆叠”

### 验证
- `dashboard/tests/test_app.py`
- `dashboard/frontend npm run build`

## v5.13.2 (2026-03-27)

**记忆页快扫优化**

### 核心升级
- `/webnovel-dashboard` 的“记忆与召回”页改为摘要优先：先看召回模式、归档可用、未回收伏笔和写作评分，再展开详情
- 归档伏笔、归档事件、归档变化改为折叠式详情，降低噪音，不抢主视线
- 新增记忆页快捷按钮，可直接回到写作驾驶舱或切到全量数据页

### 体验优化
- 记忆页默认更适合快速扫一眼做写作决策
- 排查与追溯细节仍保留在可展开区域，不影响主流程

### 验证
- `dashboard/frontend npm run build`

## v5.13.1 (2026-03-27)

**写作驾驶舱重构**

### 核心升级
- `/webnovel-dashboard` 首页重排为写作驾驶舱，优先展示本章大纲、高优先级召回、记忆健康与写作建议
- 新增 `dashboard/summary` 只读聚合接口，统一返回首页所需的驾驶舱数据
- 新增“记忆与召回”入口，集中展示 `story_recall`、`archive_recall` 和记忆健康

### 体验优化
- 保留实体、图谱、章节、文件、追读力等二级数据页
- Dashboard 在 `story_memory` 缺失或部分链路降级时仍可工作
- 首页与写作流程对齐，从“看数据”升级为“看决策”

### 验证
- `dashboard/tests/test_app.py`
- `dashboard/frontend npm run build`

## v5.12.0 (2026-03-27)

**归档层与遗忘机制**

### 核心升级
- `story_memory` 新增归档层，支持将过期已回收伏笔、旧事件、低价值变化移出活跃层
- 结构化变化账本支持容量控制，超限自动截断并进入归档
- 记忆健康报告新增归档统计与容量余量，方便判断是否需要整理

### 行为变化
- 活跃召回仍优先使用高价值、近期、未回收内容
- 已回收且足够陈旧的伏笔将从活跃层退出，但保留在归档层可追溯
- 低价值且过旧的结构化变化默认不再占用主召回预算

### 验证
- `test_state_validator.py`
- `test_status_reporter.py`
- `test_state_manager_extra.py`

---

## v5.11.0 (2026-03-27)

**memory_tier 差异化召回**

### 核心升级
- `structured_change_ledger` 按 memory_tier 分层召回
- 三层优先顺序：consolidated(≥80分) → episodic(≥60分) → working(<60分)
- 每层召回限制：consolidated(2条) / episodic(2条) / working(1条)
- 优先召回高价值、结构化变化，减少 LLM 推断负担

### 召回策略
- `memory_tier_rank()` 函数提供 tier 排序权重
- 按 memory_score 和 delta 二次排序，确保重要变化优先召回

---

## v5.10.0 (2026-03-27)

**Context Agent 写前召回接入**

### 核心升级
- `_build_story_recall()` 方法：构建写前优先召回层
- 新增 recall_policy：off / normal / boost 三种模式
- 触发 boost 模式条件：未回收伏笔≥3 或 consolidation_gap≥3

### 召回内容
- `priority_foreshadowing`：未回收伏笔（按 tier/urgency 排序）
- `character_focus`：主角+4个高频角色当前状态
- `structured_change_focus`：结构化变化（按 tier/score 排序）
- `recent_events`：近5章事件

### 验证
- `test_context_manager.py`：召回策略测试
- `test_state_validator.py`：memory_score 计算测试

---

## v5.9.0 (2026-03-27)

**通用记忆引擎升级**

### 核心升级
- 新增 `story_memory.json` 作为跨章节稳定记忆层
- 引入 `structured_change_ledger` 记录通用结构化变化，不再限定为数值变化
- 增加 `change_kind / memory_score / memory_tier`，用于记忆分层与写前召回排序
- 写前上下文、章节上下文输出和健康报告统一接入记忆层

### 兼容性
- 保留 `numeric_ledger` / `numeric_change_id` 作为旧数据兼容入口
- 旧项目可直接升级，不需要重建全部底座

### 文档更新
- 更新 README 版本说明
- 更新架构文档与命令文档中的记忆层说明

---

## v5.8.0 (2026-03-27)

**NovelAI 调研与音频封面预留**

### 调研成果
- 研究了 [jacobbeasley/novelai](https://github.com/jacobbeasley/novelai) 的小说撰写流程
- 分析了 Jinja2 模板分步执行、JSON 自修复、重试机制等核心设计
- 评估了 MiniMAX TTS HD（5小时/月，11000次）用于音频书生成的可行性

### 可借鉴能力（待实现）
- JSON 自修复：让 LLM 直接修正设定冲突（而非只报错）
- Refine 反向利用：把 Checker 问题列表变成优化指令
- 重试机制：审查/润色失败时自动重试
- 音频书生成：基于 MiniMAX TTS 的多角色音色 + 背景音乐

### 音频封面预留
- MiniMAX TTS HD（speech-02-hd）：<10,000字符/次，适合小说正文朗读
- MiniMAX Music-2.5：最长5分钟，可生成氛围音乐/片头曲
- MiniMAX image-01：120次/月，可生成章节封面图

---

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

---

## v5.6.2 (2026-03-26)

**写作约束与审核增强**

### 写作约束新增
- `references/shared/core-constraints.md`: 新增禁止具体日期写法规则
  - 禁止："仙历3021年，三月十五日"
  - 允许：相对时间（晨/午/夜/三日后）
- `references/shared/core-constraints.md`: 新增关系跳跃禁止规则

### 审核增强
- `skills/webnovel-review/SKILL.md`: 增加情节自然度检查
  - 自动检测关系跳跃、巧合过多、节奏太快
  - 触发条件满足时建议使用 `/webnovel-adjust`

### 铺垫章节插入
- `skills/webnovel-adjust/SKILL.md`: 新增铺垫章节自动插入功能
  - 支持关系铺垫（3-5章）
  - 支持事件铺垫（2-3章）
  - 支持副本扩展（5-10章）
  - 章节编号自动调整
  - 时间线、节拍表同步更新

---

## v5.6.1 (2026-03-26)

**动态大纲调整机制**

### 新增功能
- `skills/webnovel-adjust/SKILL.md`: 新增 `/webnovel-adjust` Skill
  - 支持动态调整大纲（修改章节内容、插入副本、修正冲突）
  - 自动检测时间逆流、物品凭空出现、境界矛盾、倒计时跳跃

### 冲突检测规则
| 冲突类型 | 检测逻辑 |
|---------|---------|
| 时间逆流 | 新时间 < 上一章时间 且 未标注闪回 |
| 物品凭空出现 | 物品在后续章节才首次出现但被使用 |
| 境界矛盾 | 境界变化不符合修炼逻辑 |
| 倒计时跳跃 | 倒计时非连续递减 |

---

## v5.6.0 (2026-03-26)

**状态追踪 + 变更检测系统**

### Phase 1 - Schema 扩展
- `state_manager.py`: 新增 `character_states` 追踪角色外貌/穿着/性别表达
- `state_manager.py`: 新增 `item_states` 追踪物品数量状态
- `state_manager.py`: 新增 `time_states` 追踪时间线状态
- 新增方法: `detect_character_state_change()`, `detect_item_quantity_change()`, `_is_date_earlier()`

### Phase 2 - Data Agent 增强
- `data-agent.md`: 新增 B-2 角色状态提取（外貌/穿着/性别表达）
- `data-agent.md`: 新增 B-3 物品数量提取
- `data-agent.md`: 新增 B-4 时间标记提取
- `schemas.py`: `DataAgentOutput` 新增三个状态字段

### Phase 3 - Consistency Checker 升级
- `consistency-checker.md`: 新增 APPEARANCE_CHANGE 检测
- `consistency-checker.md`: 新增 ITEM_QUANTITY_CHANGE 检测
- `consistency-checker.md`: 新增 TIMELINE_REGRESSION 检测
- `consistency-checker.md`: 新增 GENDER_IDENTITY_CONFLICT 检测
- 新增结构化修复指引模板

### 基础设施
- `.gitignore`: 新增敏感文件保护规则
- `CLAUDE.md`: 添加 GitHub PR 更新规则
- `plugin.json` / `marketplace.json`: 版本升级 5.5.4 → 5.6.0
- `README.md`: 更新版本说明

---

## v5.5.4 (2026-03-25)

**写作链提示词优化**

- 补齐写作链提示词强约束（流程硬约束、中文思维写作约束、Step 职责边界）
- 统一中文化审查/润色/Agent 报告文案
- 清理文档内部版本号与版本历史，降低与插件发版版本混淆

---

## v5.5.3 (2026-03-23)

**预检命令与编码优化**

- 新增统一 `preflight` 预检命令
- 写作链 CLI 示例统一为 UTF-8 运行方式
- 收口文档中的长 shell 预检片段，降低 Windows 终端乱码风险

---

## v5.5.2 (2026-03-22)

**大纲与文件名同步**

- 支持将详细大纲中的章节名同步到正文文件名
- 修复 workflow_manager 在无参 find_project_root monkeypatch 下的兼容性问题

---

## v5.5.1 (2026-03-21)

**命令文档补齐**

- 修复卷级单文件大纲在上下文快照中的章节提取问题
- 补齐命令文档中遗漏的 `/webnovel-dashboard` 与 `/webnovel-learn`

---

## v5.5.0 (2026-03-20)

**可视化 Dashboard**

- 新增只读可视化 Dashboard Skill（`/webnovel-dashboard`）
- 支持实时刷新能力
- 支持插件目录启动与预构建前端分发

---

## v5.4.4 (2026-03-18)

**Plugin Marketplace**

- 引入官方 Plugin Marketplace 安装机制
- 统一修复 Skills/Agents/References 的 CLI 调用（`CLAUDE_PLUGIN_ROOT` 单路径）
- 透传命令统一使用 `--`

---

## v5.4.3 (2026-03-15)

**RAG 增强**

- 增强智能 RAG 上下文辅助（`auto/graph_hybrid` 回退 BM25）

---

## v5.4.0 (2026-03-10)

**追读力系统**

- 引入追读力系统（Hook / Cool-point / 微兑现 / 债务追踪）
