# 新手 / 进阶 / 高级与开源协作指南

这份文档用于把 `织章` 的对外发布方式讲清楚：怎么安装、怎么用、怎么参与贡献、哪些内容不该公开。

---

## 1. 新手：3 步跑起来

### 第一步：安装插件

```bash
# 添加官方发布源
claude plugin marketplace add qianchongyang/zhizhang-writer --scope user

# 安装织章
claude plugin install zhizhang-writer@zhizhang-marketplace --scope user
```

你不需要先 clone 仓库，也不需要自己的 GitHub 账号。这里的 GitHub 只是公开发布源，和“开发者维护仓库”不是一回事。

### 第二步：初始化项目

```bash
/zhizhang-init
```

### 第三步：开始写作

```bash
/zhizhang-plan 1
/zhizhang-write 1
```

如果想做历史章节审查，再补一条：

```bash
/zhizhang-review 1-5
```

---

## 2. 进阶：先理解项目怎么组织

织章的工作流大致分为三层：

- `README.md`：面向新用户的首页说明
- `docs/`：架构、命令、配置、运维等正式文档
- `.webnovel/`：运行时数据，属于小说项目内部状态，不应该直接当成公开文档来写

你如果只是想“把项目跑起来”，优先看：

- `README.md`
- `docs/README.md`
- `docs/operations.md`

你如果想理解系统为什么这样设计，优先看：

- `docs/architecture.md`
- `docs/commands.md`
- `docs/rag-and-config.md`

---

## 3. 高级：二次开发建议

### 3.1 建议先保持命令兼容

旧命令 `webnovel-*` 建议先作为兼容入口保留，新的主命令使用 `zhizhang-*`。

推荐迁移表：

| 旧命令 | 新命令 |
|------|------|
| `/webnovel-init` | `/zhizhang-init` |
| `/webnovel-plan` | `/zhizhang-plan` |
| `/webnovel-write` | `/zhizhang-write` |
| `/webnovel-review` | `/zhizhang-review` |
| `/webnovel-query` | `/zhizhang-query` |
| `/webnovel-dashboard` | `/zhizhang-dashboard` |
| `/cnw` | `/zhizhang-menu` |

建议做法：

- 新用户默认只展示新命令
- 旧命令继续可用，但标注“兼容入口”
- 真正废弃旧命令之前，至少保留一个过渡周期

### 3.2 二次开发优先改哪里

建议的改动顺序：

1. 首页与文档
2. 插件元数据
3. 命令别名
4. 新手示例
5. 内部实现细节

不要一开始就把底层目录和所有命令名一次改完，否则很容易把老用户的入口打断。

### 3.3 如何做 PR 更容易被合并

建议遵守这几条：

- 一个 PR 只做一类事情
- 先补文档，再改实现
- 相关测试一起补
- 不要把个人本地记录、调试残留、密钥提交进来
- 大改动先开 Issue 讨论，再提 PR

### 3.4 仓库协作建议

如果你想让社区更容易贡献，可以再补三个文件：

- `CONTRIBUTING.md`
- `SECURITY.md`
- `.github/pull_request_template.md`

如果你想让本地提交和发布流程更统一，再补一份：

- `docs/commit-rules.md`

这三份文件能显著减少低质量 PR 和沟通成本。

---

## 4. 私密内容边界

不要公开提交这些内容：

- `.env`
- `*.key`
- `*.pem`
- `credentials.json`
- 个人聊天记录
- 私有复盘
- 内部讨论草稿
- 未整理的临时分析文件

建议把这些内容统一放到 `.gitignore` 已忽略目录中的 `docs/private/`，例如：

- `docs/private/`

---

## 5. 适合长期维护的发布方式

推荐你把仓库定位成“个人主仓库 + 公开协作入口”：

- 对外品牌统一
- 对内保留 fork 来源
- 命令迁移分阶段推进
- 文档和示例持续补齐
- PR 接收规则清晰

这样既不会把自己完全锁死在旧项目名里，也不会把迁移成本一次性拉满。
