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
- `docs/notes/control-plane.md`
- `docs/CHANGELOG.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `.github/` 下的模板与 workflow

这些文档的特点是：

- 说明项目怎么用
- 说明项目怎么设计
- 说明项目怎么贡献
- 说明项目怎么发布

## 可以公开，但要整理后再公开

建议先整理成正式设计稿，再公开：

- `docs/plans/*.md`
- `docs/superpowers/specs/*.md`
- `docs/superpowers/plans/*.md`
- `docs/notes/control-plane.md`

这类文档通常包含：

- 方案比较
- 架构决策
- 版本路线图
- 设计验证过程

如果内容已经从“讨论”变成“决策”，可以保留公开；如果还只是过程稿，建议先整理成更正式的 RFC / ADR / Spec 再开源。

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
2. `docs/` 中把正式文档与内部草稿分区
3. 过程记录保留本地，但不要作为首页入口
4. 值得公开的过程文档，整理成 RFC / ADR / 设计说明

## 目录建议

- `docs/`：公开正式文档
- `docs/plans/`：公开可读的设计稿 / 路线图
- `docs/rfc/`：正式决策文档，适合长期引用
- `docs/notes/`：内部笔记，默认不作为公开首页入口
- `docs/private/`：仅本地使用，不进入公开仓库

## 当前项目建议

对于 `织章` 目前最合适的公开策略是：

- 保留 `docs/architecture.md`、`docs/commands.md`、`docs/operations.md` 作为主干
- 保留 `docs/plans/` 里的已收口设计稿
- 不把 `docs/notes/沟通记录/` 当成公开入口
- 以后新增内部草稿优先放到 `docs/private/` 或 `.gitignored` 目录
