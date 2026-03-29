# 文档中心

这个目录放正式对外文档，不放个人聊天记录、私密复盘、密钥说明或临时草稿。

如果你刚接触这个项目，先看 `README.md` 和本页的阅读顺序。

## 建议阅读顺序

1. [README.md](../README.md)
2. [新手 / 进阶 / 高级与开源协作指南](open-source-guide.md)
3. [文档公开边界](open-source-policy.md)
4. [提交代码规则](commit-rules.md)
5. [架构与模块](architecture.md)
6. [命令详解](commands.md)
7. [RAG 与配置](rag-and-config.md)
8. [题材模板](genres.md)
9. [运维与恢复](operations.md)
10. [版本变更日志](CHANGELOG.md)

## 快速索引

### 新手

- `README.md`：Claude 安装、3 步上手、核心能力
- `open-source-guide.md`：新手入门、兼容命令、公开边界

### 进阶

- `architecture.md`：系统架构、双 Agent、审查链路
- `commands.md`：命令工作流与输出结果
- `rag-and-config.md`：RAG 和环境变量配置
- `operations.md`：目录结构、运维、恢复、健康检查

### 高级

- `commit-rules.md`：本地提交、分支、验证和 PR 合并后操作规则
- `open-source-policy.md`：哪些文档适合公开，哪些保持内部
- `CHANGELOG.md`：按更新条目持续记录对外可见变化
- `architecture.md`：控制面 / 真相层 / 运行层
- `commands.md`：批量写作、审查、恢复、数据回写

## 目录导览

- `README.md`：主页，负责第一印象和 Claude 安装入口
- `docs/README.md`：文档索引，负责阅读路径和目录入口
- `docs/CHANGELOG.md`：变更日志，记录每次对外可见更新
- `docs/commit-rules.md`：提交和发布规则，避免把草稿混进公开提交
- `docs/notes/`：历史过程记录与草稿，不作为首页推荐入口
- `docs/plans/`：历史方案和路线图，不作为首页推荐入口

## 约定

- 面向公开仓库的正式说明放在这里
- 个人笔记、私聊记录、调研草稿放在 `.gitignore` 已忽略目录中
- 如果新增对外文档，优先补到这里，再从 `README.md` 链接出去
- 如果新增用户可见变更，优先同步 `CHANGELOG.md`
