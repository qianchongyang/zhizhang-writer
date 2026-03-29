---
name: zhizhang-write
description: 织章主入口，执行完整章节创作流程（上下文→草稿→审查→润色→数据落盘）。这是用户的常规写作命令。
allowed-tools: Read Write Edit Grep Bash Task
---

# 织章主入口 /zhizhang-write

> **这是用户的常规写作入口命令。**
>
> Python 脚本（如 `webnovel.py`）为内部基础设施，不作为用户的常规操作界面。

## 与 `webnovel-write` 的关系

这是 `webnovel-write` 的新命名别名。请先阅读并遵循 `../webnovel-write/SKILL.md` 中的完整写作流程。

执行原则：
- 新品牌对外使用 `/zhizhang-write`
- 旧兼容命令 `/webnovel-write` 继续可用
- 写作流程、审查流程与数据回写以 `webnovel-write` 的规范为准，包含本地回退式启动逻辑
