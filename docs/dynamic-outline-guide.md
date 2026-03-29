# 动态大纲手册

这份手册解释织章的动态大纲是怎么工作的，以及你在日常写作里应该怎么用它。

---

## 1. 动态大纲解决什么问题

长篇连载最容易出问题的地方，不是“第一章写不出来”，而是“写到第 10 章、第 30 章、第 80 章以后，前面的计划已经不够用了”。

动态大纲就是为了解决这个问题：

- 初始大纲只提供主线轮廓，不把每一章死死钉死
- 写作过程中，系统会根据前一章的结果，自动判断后续窗口是否需要扩展、重排或插入副本
- 主线不会被推翻，但后续章纲可以变得更贴合当前剧情
- 如果系统判断偏航过大，会直接阻断提交，避免把错误继续往后写

一句话概括：

> 大纲不是死计划，而是“可调整的主线约束”。

---

## 2. 它的工作原理

动态大纲不是单独一套手工脚本，而是已经嵌进 `/zhizhang-write` 主流程。

### 2.1 初始化阶段

在项目初始化时，织章会先做三件事：

1. 生成总纲，确定整本书的主线方向
2. 生成卷纲，确定每卷的大致走向
3. 创建动态大纲运行层，默认窗口大小为 25 章

这一层的意义是：先给故事一个“活动范围”，而不是把后面几百章写死。

### 2.2 写作阶段

当你执行 `/zhizhang-write 14` 时，主流程大致是：

1. 读取第 14 章大纲和上下文
2. 生成正文
3. 做审查和润色
4. Data Agent 回写状态、摘要、索引
5. 动态大纲模块自动执行影响预览
6. 系统根据影响预览做调纲决策
7. 如果需要，更新运行层和 Markdown 大纲
8. 若调纲失败，阻断 Step 6，避免进入 Git 提交

这意味着：

- 你平时只要继续写下一章
- 不需要手动先跑调纲命令
- 不需要手动操作 Python 脚本

### 2.3 调整的对象

动态大纲改的不是“当前已经写完的正文”，而是“后续活动窗口”。

常见动作有：

- `no_change`：当前窗口不用改
- `minor_reorder`：轻微重排
- `insert_arc`：插入副本或关系弧线
- `window_extend`：扩展窗口
- `block_for_manual_review`：需要人工审查，停止自动继续

---

## 3. 日常怎么用

### 3.1 正常写作

你日常只需要继续使用：

```text
/zhizhang-write 14
/zhizhang-write 15
/zhizhang-write 16
```

织章会在每章完成后自动评估后续窗口是否需要调整。

### 3.2 什么时候需要你手动介入

只有下面几种情况才需要人工处理：

- 系统判定 `block_for_manual_review`
- 你明确想强行改副本结构
- 运行层或大纲文件被外部改坏，需要修复
- 你想做调试，不走正常写作流程

这种情况下，才考虑使用 `/zhizhang-adjust` 之类的调试入口。

### 3.3 新项目怎么开始

推荐顺序是：

```text
/zhizhang-init
/zhizhang-plan 1
/zhizhang-write 1
```

如果你在项目配置里设置了：

```json
{
  "default_window_size": 30
}
```

那么新项目初始化时会按这个窗口大小创建动态大纲运行层。

---

## 4. 你会看到什么结果

动态大纲正常工作时，你会看到这些结果：

- 写下一章后，后续章纲不再是僵死的
- 副本或关系弧线会被自动识别并纳入窗口
- `outline_runtime.json` 会记录当前活动窗口
- `outline_adjustments.jsonl` 会记录每次调整
- 如果调纲失败，流程会停住，不会把错误状态带去 Git 提交

你可以把它理解为：

> 正文是已写事实，动态大纲是“下一段该怎么接”的实时调度层。

---

## 5. 关键文件在哪里

如果你想看系统如何实现动态大纲，可以看这些文件：

- `/Users/zhoukai/code/webnovel-writer/webnovel-writer/scripts/data_modules/outline_runtime.py`
- `/Users/zhoukai/code/webnovel-writer/webnovel-writer/scripts/data_modules/outline_window_parser.py`
- `/Users/zhoukai/code/webnovel-writer/webnovel-writer/scripts/data_modules/outline_impact_analyzer.py`
- `/Users/zhoukai/code/webnovel-writer/webnovel-writer/scripts/data_modules/outline_mutation_engine.py`
- `/Users/zhoukai/code/webnovel-writer/webnovel-writer/scripts/workflow_manager.py`
- `/Users/zhoukai/code/webnovel-writer/webnovel-writer/skills/webnovel-write/SKILL.md`

如果你只是普通使用者，不需要先看这些文件，直接照流程写就行。

---

## 6. 常见问题

### 6.1 为什么第 14 章会提示缺大纲？

通常有两种原因：

- 卷纲里还没覆盖到第 14 章
- 动态窗口还没生成到第 14 章

先检查 `大纲/`，再检查 `.webnovel/outline_runtime.json`。

### 6.2 为什么调纲失败后不能继续？

因为调纲失败说明当前运行层和后续章纲已经不一致了。
继续提交只会把错误固化下来，后面更难修。

### 6.3 我能不能手工改大纲？

可以，但建议只在调试、修复、特殊覆盖场景下做。
正常写作尽量让系统自动调。

### 6.4 默认窗口一定是 25 吗？

默认是 25，但你可以在 `.webnovel/project_config.json` 里覆盖：

```json
{
  "default_window_size": 30
}
```

---

## 7. 推荐的日常工作流

最推荐的日常节奏是：

1. 先看当前章大纲是否覆盖
2. 执行 `/zhizhang-write N`
3. 看审查结论是否需要补强
4. 继续写下一章
5. 如果系统阻断调纲，再处理 `block_for_manual_review`

这样做的好处是：

- 不需要你手工追着大纲改
- 系统会自动围绕主线做调整
- 动态窗口和正文状态能持续一致

---

## 8. 一句话总结

动态大纲的目标不是让故事“更自由地乱跑”，而是让故事在不偏离主线的前提下，能够随着剧情自然生长。

