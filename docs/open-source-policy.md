# 文档公开边界

这份文档用于区分哪些内容适合直接开源，哪些内容更适合保留为内部草稿或研发记录。

## 公开发布

建议直接开源并保持长期维护：

- `README.md`
- `docs/README.md`
- `docs/architecture.md`
- `docs/commands.md`
- `docs/rag-and-config.md`
- `docs/genres.md`
- `docs/operations.md`
- `docs/open-source-guide.md`
- `docs/commit-rules.md`
- `docs/CHANGELOG.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `.github/` 下的模板与 workflow

这些文档的特点是：

- 说明项目怎么用
- 说明项目怎么设计
- 说明项目怎么贡献
- 说明项目怎么发布

## 可以保留，但不作为首页推荐入口

这些内容可以留在仓库里做历史记录或研发参考，但不要在 README 或文档中心作为主入口：

- `docs/notes/control-plane.md`
- `docs/notes/*.md`
- `docs/plans/*.md`
- `docs/superpowers/specs/*.md`
- `docs/superpowers/plans/*.md`

这类文档通常包含：

- 方案比较
- 架构决策
- 版本路线图
- 设计验证过程

如果内容已经从“讨论”变成“决策”，可以整理成更正式的 RFC / ADR / Spec 再开源；如果还只是过程稿，建议不要把它们放进首页索引。

## 不建议直接公开

建议保留为内部草稿、工作记录或临时参考，不作为对外主文档：

- `docs/notes/沟通记录/`
- 原始聊天记录
- 反复推翻的 brainstorm 草稿
- 私有复盘
- 带个人判断、未定稿、临时实验性质的文档

## 推荐策略

最稳妥的做法是：

1. `README.md` 只链接公开正式文档
2. `docs/README.md` 只列正式阅读顺序和少量历史入口
3. 过程记录保留本地或留作历史归档，但不要作为首页入口
4. 值得公开的过程文档，整理成 RFC / ADR / 设计说明

## 目录建议

- `docs/`：公开正式文档
- `docs/rfc/`：正式决策文档，适合长期引用
- `docs/adr/`：架构决策记录，适合长期引用
- `docs/notes/`：内部笔记或历史记录，不作为公开首页入口
- `docs/private/`：仅本地使用，不进入公开仓库

## 当前项目建议

对于 `织章` 目前最合适的公开策略是：

- 保留 `docs/architecture.md`、`docs/commands.md`、`docs/operations.md` 作为主干
- 保留 `docs/CHANGELOG.md` 记录每次对外可见更新
- 不把 `docs/notes/沟通记录/` 当成公开入口
- 以后新增内部草稿优先放到 `docs/private/` 或 `.gitignored` 目录
