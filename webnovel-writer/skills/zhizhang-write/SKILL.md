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

## 动态大纲扩展（Step 5.5A / Step 5.5B）

`/zhizhang-write` 完整流程包含 Step 5.5A 和 Step 5.5B：

```
Step 1 → 2A → 2B → 3 → 4 → 5 → 5.5A → 5.5B → 6
```

### Step 5.5A：影响预览

在 Data Agent (Step 5) 完成后，执行影响范围分析：
- Python 层运行 `OutlineImpactAnalyzer.analyze()`
- 生成 `ImpactPreview` 结构化输出
- 检测冲突信号、关系跃迁、副本段、前置条件缺口

### Step 5.5B：动态调纲决策

基于 `ImpactPreview` 执行结构化决策：
- LLM 分析影响信号并输出 `DynamicOutlineDecision`
- Python 层执行 Contract 校验
- 通过后更新 `outline_runtime`，失败则降级处理

### 硬约束

- **禁止修改总纲锚点**
- **禁止推翻已写事实**
- **insert_arc 必须提供 mainline_service_reason**

详细协议见：`references/dynamic-outline-contract.md`
