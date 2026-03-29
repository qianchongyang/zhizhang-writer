# 版本变更日志

本文档记录所有正式版本的变更内容，也会补充当前正在发生的对外可见更新。

## 记录规则

- 每次对外可见更新尽量单独成条，不要把几次改动合并成一大段
- 条目里尽量写清楚：变更内容、影响范围、涉及文件、验证方式
- 首页、安装路径、命令、元数据、文档索引这些可见变化，都应该记录
- 只记录结论和结果，不记录内部争论过程

## 2026-03-29：首页与日志规范升级

### 1. 首页改成 Claude 优先入口

- `README.md` 增加了 Claude 安装与更新入口，安装后可直接运行 `/zhizhang-menu`
- 首页的“快速开始”改成更明确的 3 步上手：安装、初始化、开始写作
- 首页补了快速导航，方便用户直接跳到命令、文档索引和更新日志

**影响范围**

- 新用户第一次打开仓库时能更快找到 Claude 安装方式
- 旧用户仍可继续沿用 `webnovel-*` 兼容命令

**验证方式**

- 手动检查 README 中的安装命令、锚点链接和入口顺序

### 2. 文档索引改成目录式导航

- `docs/README.md` 补充了“新手 / 进阶 / 高级 / 目录导览”四层结构
- 增加了 `docs/CHANGELOG.md` 的阅读入口，避免更新日志被埋在角落
- 明确说明哪些文档是正式对外文档，哪些属于内部草稿边界

**影响范围**

- 用户可以先看索引，再决定要不要深入架构或运维文档

**验证方式**

- 手动检查 `docs/README.md` 的链接顺序和目录说明是否完整

### 3. 提交规则补充更新日志要求

- `docs/commit-rules.md` 增加了“用户可见变更要同步更新 changelog”的规则
- 发布前检查项补充了 README 入口优先级和变更日志条目要求

**影响范围**

- 后续高频更新时，不容易漏记对外可见变化

**验证方式**

- 检查提交前规则是否足以覆盖首页、命令和文档变更

## 2026-03-29：Claude 安装门槛收口

### 1. 安装说明改成“无需 clone、无需自有 GitHub”

- `README.md` 和 `docs/open-source-guide.md` 的安装段都改成了官方发布源 + 安装命令的形式
- 新说明明确写出：用户只要能运行 Claude Code，就可以按命令安装，不需要先理解仓库克隆
- 首页和新手指南都强调 GitHub 只是公开发布源，不是使用前置门槛

**影响范围**

- 新手第一次安装时不容易被 GitHub、fork、clone 这些概念打断
- 更适合作为 Claude 插件的首页入口

**验证方式**

- 手动检查 README 和新手指南的安装段是否足够短、足够直接

## 2026-03-29：安装说明再压缩

### 1. 普通用户只看两条命令

- `README.md` 的安装段改成“普通用户直接复制这两条”
- `docs/open-source-guide.md` 的新手步骤也同步成更短的版本
- 安装后统一直接进 `/zhizhang-menu`，不再先要求用户理解更多概念

**影响范围**

- 首页更像开箱即用入口
- 新用户更少被说明文字打断

**验证方式**

- 手动检查 README 和新手指南是否只保留最短路径

---

## v5.24.0 (2026-03-28)

**经营化版**

### 核心升级
- 新增 `reader_feedback.py` 读者反馈模块，支持手工输入反馈
- 反馈类型：钩子太弱/节奏太慢/角色OOC/文笔问题/其他
- 新增连载模板：日更模板/周更模板
- 新增 `get_actionable_suggestions()` 生成可操作建议反哺写作

### 配置更新
- `reader_feedback_enabled`: 是否启用读者反馈
- `reader_pull_warning_threshold`: 追读力预警阈值
- `reader_pull_critical_threshold`: 追读力危急阈值

### 使用方式
```bash
python reader_feedback.py --add --chapter 50 --type "钩子太弱" --content "第三章结尾的钩子不够吸引人"
python reader_feedback.py --list --chapter 50
python reader_feedback.py --stats
python reader_feedback.py --suggestions
python reader_feedback.py --templates
```

---

## v5.23.0 (2026-03-28)

**稳定性版**

### 核心升级
- 新增 `health_checker.py` 连ol健康检查器，每10章自动体检
- 新增 `consistency_repair.py` 一致性修复脚本
- 检查 state.json、index.db、story_memory.json 三方一致性
- 支持 Git 版本控制的快照与回滚

### 健康检查项
| 检查项 | 严重度 |
|--------|--------|
| state.json 存在性 | critical |
| index.db 与 state 一致性 | high |
| story_memory 完整性 | medium |
| 章节文件连续性 | medium |
| 伏笔回收过期 | medium |

### 使用方式
```bash
python health_checker.py --chapter 50
python health_checker.py --range 1-100
python health_checker.py --auto

python consistency_repair.py --dry-run
python consistency_repair.py --fix
```

---

## v5.22.0 (2026-03-28)

**提速版（Turbo 模式）**

### 核心升级
- 新增 `--turbo` 模式：Step 1→2A→3→5→6，跳过润色
- 审查并行化：核心3个审查器并行执行
- 上下文热缓存：缓存近3章上下文，TTL 1小时

### 性能目标
- `--turbo` 平均耗时下降 ≥ 50%
- 与标准模式相比质量下降 ≤ 8 分

### 模式对比
| 模式 | 步骤 | 审查器 |
|------|------|--------|
| 标准 | 1→2A→2B→3→4→5→6 | 6个串行 |
| `--fast` | 1→2A→3→4→5→6 | 6个串行 |
| `--turbo` | 1→2A→3→5→6 | 核心3个并行 |
| `--minimal` | 1→2A→3→4→5→6 | 核心3个串行 |

---

## v5.21.0 (2026-03-28)

**去AI味版**

### 核心升级
- 新增 `anti_ai_checker.py` Anti-AI 检查器
- 7层检测规则：词汇/句式/形容词/成语/对白/段落/标点
- 200+ 高风险词汇库
- AI味惩罚分机制（封顶30分）
- 局部重写触发器

### 量化阈值
| 指标 | 通过线 | 致命线 |
|------|-------|--------|
| 因果连接词密度 | ≤2次/千字 | ≥5次/千字 |
| 总结归纳词密度 | ≤1次/千字 | ≥3次/千字 |
| 三段式枚举句 | 0处 | ≥1处 |
| 短句占比 | 25-45% | <15% 或 >60% |

### 触发重写条件（满足任一）
1. 致命线命中 ≥1 项
2. 通过线命中 ≥3 项
3. 高风险词汇命中 ≥10 处

---

## v5.20.0 (2026-03-28)

**止血版**

### 核心升级
- 章纲硬闸门：缺失大纲直接阻断
- 最小章节契约：目标/冲突/动作/结果/代价/钩子
- 状态变化约束：可识别变化词检测

### 写前硬闸门（v5.20）
- 必须存在本章可用大纲
- 大纲需满足最小章节契约
- 可选状态变化阈值

---

## v5.18.0 (2026-03-27)

**时序记忆增强**

### 核心升级
- `IndexManager` 新增时序窗口查询能力：按章节范围聚合章节切片、状态变化、关系事件和出场记录
- `ContextManager` 写前召回接入 `story_recall.temporal_window`，可按最近章节窗口补充连续性事实
- `extract_chapter_context` 文本输出新增“时序窗口召回”块，写前任务书能直接看到最近窗口变化
- Dashboard “记忆与召回”页新增时序窗口摘要，默认展示章节范围、最近变化和关系事件

### 体验优化
- 长篇章节数增长后，写前上下文不再只依赖稳定记忆和归档，能补回最近几章的即时事实
- 记忆页继续保持快扫模式，但现在可直接看到最近章节窗口的核心变化，不需要切到全量数据页

### 验证
- `test_data_modules.py`
- `test_context_manager.py`
- `test_extract_chapter_context.py`
- `dashboard/tests/test_app.py`
- `dashboard/frontend npm run build`

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
