# 控制面说明

`webnovel-writer` 当前把写作链拆成三层：

- 控制面：`author_intent / current_focus / chapter_intent`
- 真相层：`state / story_memory / index / vectors`
- 运行层：`context / workflow / dashboard`

## 原则

- 控制面负责“本章写什么、不能偏到哪”
- 真相层负责“真实发生了什么”
- 运行层负责“如何把控制面与真相层编译给模型”

## 控制面对象

### `author_intent`

长期创作目标，适合保存：

- 主线承诺
- 长期风格边界
- 不可突破的硬约束

### `current_focus`

最近 1-3 章要拉回的内容，适合保存：

- 必须回收的伏笔
- 近期应强化的冲突
- 明确禁止扩写的方向

### `chapter_intent`

本章任务书，由 `ContextManager` 动态生成，最小包含：

- `chapter_goal`
- `must_resolve`
- `priority_memory`
- `story_risks`
- `hard_constraints`

## 注意

控制面不是事实源。  
若控制面与 `state.json / story_memory.json / index.db` 冲突，以真相层为准。
