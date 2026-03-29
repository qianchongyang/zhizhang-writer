# 提交代码规则

这份规则用于本地开发、提交流程和后续协作，目标是让仓库保持可读、可回滚、可发布。

## 1. 分支规则

- 新功能优先使用 `codex/<short-topic>` 分支
- 文档改动可以使用 `docs/<short-topic>`
- 修复类改动可以使用 `fix/<short-topic>`
- 不要在 `main` 上直接堆大改动

## 2. 暂存规则

- 只暂存本次任务需要的文件
- 混合工作区时，不要无脑 `git add -A`
- 不确定是否该提交时，先 `git status` 再拆分
- 本地工作台文件、密钥、聊天记录、草稿默认不进仓库
- 过程文档默认放在 `docs/private/`，不要放回公开的 `docs/notes/` 或 `docs/plans/`

## 3. 提交信息规则

- 使用短、明确、可检索的提交信息
- 推荐格式：
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `chore: ...`
  - `refactor: ...`
- 一次提交只做一类事情，避免把多个主题揉在一起
- 如果这次提交会影响用户可见行为，最好同步补一条 `docs/CHANGELOG.md` 记录

## 4. 发布前检查

在提交公开内容前，至少确认：

- README 的安装示例可读
- README 里的 Claude 安装路径优先、文档索引清楚
- 插件元数据和 marketplace 元数据一致
- 没有把 `.env`、`*.key`、`*.pem`、`credentials.json` 提交进去
- `docs/private/沟通记录/` 之类的内部内容没有进入公开入口
- `docs/private/` 里的过程文档没有进入公开入口
- 新命令 `zhizhang-*` 与旧命令 `webnovel-*` 的兼容说明已经写清楚
- 变更日志 `docs/CHANGELOG.md` 已经补上对应条目

## 5. 推荐验证

对文档与元数据改动，建议至少跑：

```bash
python3 -m py_compile webnovel-writer/scripts/webnovel.py webnovel-writer/scripts/zhizhang.py webnovel-writer/scripts/data_modules/webnovel.py webnovel-writer/scripts/data_modules/zhizhang.py webnovel-writer/scripts/sync_plugin_version.py
```

```bash
python3 - <<'PY'
import json
for path in ['.claude-plugin/marketplace.json','webnovel-writer/.claude-plugin/plugin.json']:
    with open(path, 'r', encoding='utf-8-sig') as f:
        json.load(f)
print('json ok')
PY
```

如果涉及文档首页，建议再人工检查一遍 README 是否还有旧仓库地址残留。
如果涉及频繁更新，建议检查 `docs/CHANGELOG.md` 是否按条目记录，而不是把多次变更合并成一条大段。

## 6. PR 合并后

如果上游流程需要回到本地环境，建议按下面顺序：

1. `git checkout main`
2. `git pull mine main`
3. `claude plugin update zhizhang-writer@zhizhang-marketplace --scope user`
4. `claude plugin list`

如果插件版本变化明显，再检查 README、`plugin.json` 和 `marketplace.json` 是否同步。
