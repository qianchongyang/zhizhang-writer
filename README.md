# 织章 Zhizhang Writer

[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-purple.svg)](https://claude.ai/claude-code)

`织章 Zhizhang Writer` 是一个基于 Claude Code 的长篇网文创作系统，围绕“大纲约束、上下文召回、状态追踪、章节审查”构建，帮助创作者在长周期连载中降低遗忘、幻觉和前后冲突。

本仓库基于 `lingfengQAQ/webnovel-writer` fork 并二次开发，保留 GPL-3.0 开源协议，同时作为独立品牌持续维护。

## 快速导航

- [Claude 安装与启动](#claude-安装与启动)
- [3 步上手](#3-步上手)
- [适合谁](#适合谁)
- [核心能力](#核心能力)
- [文档索引](#文档索引)
- [命令兼容](#命令兼容)
- [最近更新](#最近更新)
- [贡献与边界](#贡献与边界)
- [来源与致谢](#来源与致谢)

## Claude 安装与启动

`织章` 的安装入口优先围绕 Claude Code 设计。你不需要先 clone 仓库，也不需要先有自己的 GitHub 仓库，只要在 Claude 里复制下面的命令即可。

```bash
# 1. 添加官方发布源
claude plugin marketplace add qianchongyang/zhizhang-writer --scope user

# 2. 安装织章
claude plugin install zhizhang-writer@zhizhang-marketplace --scope user

# 3. 查看已安装插件
claude plugin list
```

如果你已经安装过旧版本，只需要更新：

```bash
claude plugin update zhizhang-writer@zhizhang-marketplace --scope user
```

仅当前项目生效时，把 `--scope user` 改成 `--scope project`。

GitHub 在这里是“公开发布源”，不是使用前置门槛。你只要能运行 Claude Code，就能按上面的命令安装。

安装完成后，先输入：

```bash
/zhizhang-menu
```

它会显示当前可用命令和入口。

## 3 步上手

### 1. 初始化项目

```bash
/zhizhang-init
```

### 2. 查看命令与工作流

```bash
/zhizhang-menu
```

### 3. 开始写作

```bash
/zhizhang-plan 1
/zhizhang-write 1
/zhizhang-review 1-5
```

## 适合谁

- 想把小说做成长篇连载的人
- 需要管理设定、状态、伏笔和章节节奏的人
- 想在 Claude Code 上快速搭建写作工作流的人
- 想参与二次开发和 PR 贡献的人

## 核心能力

- 大纲即法律，写前先过硬闸门
- 设定即物理，避免前后冲突
- 发明需识别，新实体自动入库
- 双 Agent 协作：Context Agent + Data Agent
- 六维并行审查：爽点、一致性、节奏、人设、连贯性、追读力
- 记忆与召回：状态、伏笔、章节摘要、语义索引
- Dashboard：只读运行面板，便于排障和复盘

## 文档索引

如果你只想快速找入口，先看这几份：

- [文档中心](docs/README.md)
- [新手 / 进阶 / 高级与开源协作指南](docs/open-source-guide.md)
- [提交代码规则](docs/commit-rules.md)
- [版本变更日志](docs/CHANGELOG.md)

如果你想继续深入：

- [架构与模块](docs/architecture.md)
- [命令详解](docs/commands.md)
- [RAG 与配置](docs/rag-and-config.md)
- [题材模板](docs/genres.md)
- [运维与恢复](docs/operations.md)

## 命令兼容

为了照顾从旧仓库迁移过来的用户，`webnovel-*` 命令在一段过渡期内建议继续保留为兼容别名。

推荐新用户使用：

- `/zhizhang-init`
- `/zhizhang-plan`
- `/zhizhang-write`
- `/zhizhang-review`
- `/zhizhang-query`
- `/zhizhang-dashboard`
- `/zhizhang-menu`

旧命令示例：

- `/webnovel-init`
- `/webnovel-plan`
- `/webnovel-write`
- `/webnovel-review`
- `/webnovel-query`
- `/webnovel-dashboard`
- `/cnw`

迁移原则：

- 新品牌对外统一为 `织章 / Zhizhang`
- 旧命令作为兼容入口，逐步迁移，不建议立刻删除
- 文档、示例、插件元数据优先使用新命名

## 最近更新

详细更新请看 [版本变更日志](docs/CHANGELOG.md)。这个仓库会把每次对外可见变更拆成更细的条目，方便后续高频维护。

最近几个版本的方向：

- `2026-03-29`：首页改成 Claude 优先入口，增加快速索引和更细的更新日志规范
- `v5.24.0`：新增读者反馈与追读力建议模块
- `v5.23.0`：新增健康检查与一致性修复

## 贡献与边界

如果你想贡献代码，先看 [CONTRIBUTING.md](CONTRIBUTING.md)。

如果你发现安全边界问题，先看 [SECURITY.md](SECURITY.md)。

## 来源与致谢

- 本项目基于 `lingfengQAQ/webnovel-writer` fork 并二次开发
- 保留原项目 GPL-3.0 开源协议
- 感谢原项目的基础实现与灵感来源

## 开源协议

本项目使用 `GPL v3` 协议，详见 `LICENSE`。
