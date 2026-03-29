# 织章 Zhizhang Writer

[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-purple.svg)](https://claude.ai/claude-code)

`织章 Zhizhang Writer` 是一个面向长篇网文创作的辅助系统，围绕“大纲约束、上下文召回、状态追踪、章节审查”构建，帮助创作者在长周期连载中降低遗忘、幻觉和前后冲突。

本仓库基于 `lingfengQAQ/webnovel-writer` fork 并二次开发，保留 GPL-3.0 开源协议，同时作为独立品牌持续维护。

## 快速开始

### 1. 安装插件

> 下面是发布后的示例，实际仓库地址请替换成你的公开地址。

```bash
claude plugin marketplace add <YOUR_GITHUB_USERNAME>/zhizhang-writer --scope user
claude plugin install zhizhang-writer@zhizhang-marketplace --scope user
```

仅当前项目生效时，将 `--scope user` 改为 `--scope project`。

### 2. 初始化项目

```bash
/zhizhang-init
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
- 想在 Claude Code 上搭建写作工作流的人
- 想参与二次开发和 PR 贡献的人

## 核心能力

- 大纲即法律，写前先过硬闸门
- 设定即物理，避免前后冲突
- 发明需识别，新实体自动入库
- 双 Agent 协作：Context Agent + Data Agent
- 六维并行审查：爽点、一致性、节奏、人设、连贯性、追读力
- 记忆与召回：状态、伏笔、章节摘要、语义索引
- Dashboard：只读运行面板，便于排障和复盘

## 文档导航

- [新手 / 进阶 / 高级与开源协作指南](docs/open-source-guide.md)
- [架构与模块](docs/architecture.md)
- [命令详解](docs/commands.md)
- [RAG 与配置](docs/rag-and-config.md)
- [题材模板](docs/genres.md)
- [运维与恢复](docs/operations.md)
- [文档中心](docs/README.md)

## 命令兼容说明

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

## 开源协作

如果你想贡献代码，先看 [CONTRIBUTING.md](CONTRIBUTING.md)。

如果你发现安全边界问题，先看 [SECURITY.md](SECURITY.md)。

## 来源与致谢

- 本项目基于 `lingfengQAQ/webnovel-writer` fork 并二次开发
- 保留原项目 GPL-3.0 开源协议
- 感谢原项目的基础实现与灵感来源

## 开源协议

本项目使用 `GPL v3` 协议，详见 `LICENSE`。
