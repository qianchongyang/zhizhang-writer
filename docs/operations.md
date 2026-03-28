# 项目结构与运维

## 目录层级（真实运行）

在 Claude Code + Marketplace 安装下，至少有 4 层概念：

1. `WORKSPACE_ROOT`（Claude 工作区根，通常是 `${CLAUDE_PROJECT_DIR}`）
2. `WORKSPACE_ROOT/.claude/`（工作区级指针与配置）
3. `PROJECT_ROOT`（真实小说项目根，`/webnovel-init` 按书名创建）
4. `CLAUDE_PLUGIN_ROOT`（插件缓存目录，不在项目内）

### A) Workspace 目录（含 `.claude`）

```text
workspace-root/
├── .claude/
│   ├── .webnovel-current-project   # 指向当前小说项目根
│   └── settings.json
├── 小说A/
├── 小说B/
└── ...
```

### B) 小说项目目录（`PROJECT_ROOT`）

```text
project-root/
├── .webnovel/            # 运行时数据（state/index/vectors/summaries/control）
├── 正文/                  # 正文章节
├── 大纲/                  # 总纲与卷纲
└── 设定集/                # 世界观、角色、力量体系
```

### `.webnovel/` 关键运行时文件

```text
.webnovel/
├── state.json
├── project_memory.json
├── story_technique_blueprint.json
├── control/
│   ├── chapter_intents/
│   └── chapter_technique_plans/
├── memory/
│   └── story_memory.json
├── summaries/
├── snapshots/
├── index.db
├── rag.db
└── vectors.db
```

- `story_technique_blueprint.json`：项目级技巧蓝图，初始化生成，旧项目可懒生成
- `project_memory.json`：项目级技巧记忆，记录有效/疲劳技巧与近章执行结果
- `control/chapter_technique_plans/`：章节技巧编排缓存，供 Step 2A 直接消费

## 插件目录（Marketplace 安装）

插件不在小说项目目录内，而在 Claude 插件缓存目录。运行时统一用 `CLAUDE_PLUGIN_ROOT` 引用：

```text
${CLAUDE_PLUGIN_ROOT}/
├── skills/
├── agents/
├── scripts/
└── references/
```

### C) 用户级全局映射（兜底）

当工作区没有可用指针时，会使用用户级 registry 做 `workspace -> current_project_root` 映射：

```text
${CLAUDE_HOME:-~/.claude}/webnovel-writer/workspaces.json
```

## 模拟目录实测（2026-03-03）

基于 `D:\wk\novel skill\plugin-sim-20260303-012048` 的实际结果：

- `WORKSPACE_ROOT`：`D:\wk\novel skill\plugin-sim-20260303-012048`
- 指针文件：`D:\wk\novel skill\plugin-sim-20260303-012048\.claude\.webnovel-current-project`
- 指针内容：`D:\wk\novel skill\plugin-sim-20260303-012048\凡人资本论-二测`
- 已创建项目示例：`凡人资本论/`、`凡人资本论-二测/`

## 常用运维命令

统一前置（手动 CLI 场景）：

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

### 预检

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" preflight
```

### 绑定当前项目指针

当工作区内有多个项目时，可手动绑定当前指针：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" use "${PROJECT_ROOT}"
```

### 检查技巧运行时文件

```bash
ls "${PROJECT_ROOT}/.webnovel/story_technique_blueprint.json"
ls "${PROJECT_ROOT}/.webnovel/project_memory.json"
ls "${PROJECT_ROOT}/.webnovel/control/chapter_technique_plans"
```

### 检查章节上下文硬闸门（v5.20）

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  extract-context --chapter 12 --format text
```

若失败，优先检查：

1. `大纲/` 是否存在第 12 章可解析内容
2. 该章是否具备最小章节契约：目标/冲突/动作/结果/代价/钩子
3. 若项目开启状态变化阈值，是否包含可追踪变化词（突破/失去/结盟/暴露/受伤等）

### 索引重建

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index process-chapter --chapter 1
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index stats
```

### 健康报告

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" status -- --focus all
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" status -- --focus urgency
```

### 向量重建

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" rag index-chapter --chapter 1
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" rag stats
```

### 审查指标落库

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index save-review-metrics --data "@${PROJECT_ROOT}/.webnovel/tmp/review_metrics.json"
```

### 审查结果合并（分组审查）

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  merge \
  --group1 "${PROJECT_ROOT}/.webnovel/tmp/agent_outputs/rev1_ch{NNNN}.json" \
  --group2 "${PROJECT_ROOT}/.webnovel/tmp/agent_outputs/rev2_ch{NNNN}.json" \
  --output "${PROJECT_ROOT}/.webnovel/tmp/merged/review_merged_ch{NNNN}.json"
```

合并后的结果现在会额外带出 `technique_execution`，用于：

- 回写 `project_memory.json`
- 驱动后续章节的技巧疲劳规避
- 给润色阶段提供“说明腔 / 余波缺失 / 同构重复”信号

## Step 5 状态变化后置校验（v5.20 C1）

`state process-chapter` 在 Data Agent 提取后会做最小状态变化检查：

- 若状态变化不足：
  - `chapter_meta.{NNNN}.progress_flags` 写入 `insufficient_state_change`
  - `chapter_meta.{NNNN}.progress_warnings` 写入修复建议
  - CLI `warnings` 返回“推进不足”提示

示例（手动排查）：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  state process-chapter --chapter 12 --data "@${PROJECT_ROOT}/.webnovel/tmp/data_agent_result.json"
```

### 旧项目升级自检

首次对旧项目执行 `/webnovel-plan` 或 `/webnovel-write` 后，应确认以下文件已自动补齐：

```bash
test -f "${PROJECT_ROOT}/.webnovel/story_technique_blueprint.json"
test -f "${PROJECT_ROOT}/.webnovel/project_memory.json"
```

若未生成，先跑一次预检，再检查 `state.json` 中题材字段是否存在。

### 测试入口

```bash
pwsh "${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.ps1" -Mode smoke
pwsh "${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.ps1" -Mode full
```
