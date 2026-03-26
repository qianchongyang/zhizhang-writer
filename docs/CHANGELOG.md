# 版本变更日志

本文档记录所有正式版本的变更内容。

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
