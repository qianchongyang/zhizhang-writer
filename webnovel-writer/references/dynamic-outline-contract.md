# Dynamic Outline Agent - 结构化输入输出协议

## 目标

把"是否插副本、插几章、怎么回主线"的创意判断交给 Agent/LLM，但输出必须可被 Python 安全消费。

## 协议版本

- **Version**: 1.0
- **Last Updated**: 2026-03-29
- **Status**: Phase 1 - LLM Structured Output + Contract Validation

---

## 核心原则（硬约束）

> 以下约束必须在 Contract 校验层强制执行，违反则降级为"不自动落盘，只记录告警"。

1. **不允许修改总纲锚点**：输出中不得包含对 `mainline_anchors` 的任何变更指令
2. **不允许推翻已写事实**：不得要求修改 `chapter <= current_chapter` 的任何已写内容
3. **不允许插入无主线服务理由的副本**：每个 `insert_arc` 操作必须提供 `mainline_service_reason`

---

## 输入协议（Agent 消费）

### 1. ImpactPreview（来自 outline_impact_analyzer.py）

```json
{
  "needs_adjustment": boolean,
  "adjustment_type": "none" | "minor_reorder" | "insert_arc" | "window_extend" | "block_for_manual_review",
  "reason": "string",
  "affected_chapters": ["int"],
  "affected_entities": ["string"],
  "affected_foreshadowing": ["string"],
  "timeline_risk": "string",
  "mainline_risk": "string",
  "recommended_return_to_mainline_by": "int | null",
  "conflict_signals": ["string"],
  "prerequisite_gaps": ["string"],
  "relationship_jump_signals": ["string"],
  "copy_segment_signals": ["string"]
}
```

### 2. 当前上下文

| 字段 | 类型 | 说明 |
|------|------|------|
| `current_chapter` | int | 当前章节号 |
| `active_window_start` | int | 活动窗口起始章节 |
| `active_window_end` | int | 活动窗口结束章节 |
| `mainline_anchors` | list | 主线锚点列表（不可修改） |
| `outline_nodes` | list | 大纲节点列表 |

---

## 输出协议（Python 消费）

### DynamicOutlineDecision

```json
{
  "decision": "no_change" | "minor_reorder" | "insert_arc" | "window_extend" | "block_for_manual_review",
  "reason": "string",
  "mainline_service_reason": "string (required when decision=insert_arc)",
  "return_to_mainline_by": "int | null",
  "updated_window": {
    "window_start": "int",
    "window_end": "int",
    "delta_chapters": "int (新增章节数)"
  },
  "timeline_patch": {
    "patch_type": "none" | "extend" | "compress" | "shift",
    "affected_chapters": ["int"],
    "description": "string"
  },
  "beat_patch": {
    "added_beats": [
      {
        "beat_id": "string",
        "chapter": "int",
        "beat_type": "string",
        "description": "string",
        "mainline_service": "string"
      }
    ],
    "removed_beats": ["int"],
    "modified_beats": [
      {
        "original_chapter": "int",
        "new_chapter": "int",
        "reason": "string"
      }
    ]
  },
  "risk_notes": "string"
}
```

### 字段说明

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `decision` | 是 | enum | 核心决策类型 |
| `reason` | 是 | string | 决策原因摘要 |
| `mainline_service_reason` | 条件 | string | `decision=insert_arc` 时必填，说明副本对主线的服务价值 |
| `return_to_mainline_by` | 否 | int | 推荐回归主线的章节号 |
| `updated_window` | 否 | object | 窗口调整信息（仅当 decision != no_change 时有效） |
| `timeline_patch` | 否 | object | 时间线补丁信息 |
| `beat_patch` | 否 | object | 节拍补丁信息 |
| `risk_notes` | 否 | string | 风险备注 |

### Decision 类型

| 决策 | 说明 | 何时使用 |
|------|------|---------|
| `no_change` | 不改变大纲 | 无显著影响或风险过低 |
| `minor_reorder` | 轻微重排 | 前置条件缺口、少量冲突信号 |
| `insert_arc` | 插入弧线/副本 | 检测到需要完整展开的副本段 |
| `window_extend` | 扩展活动窗口 | 关系跃迁+承诺过大，需更多章节消化 |
| `block_for_manual_review` | 阻塞，人工审查 | 时间线矛盾、主线严重偏离 |

---

## Contract 校验规则

### 校验级别 1：Schema 校验（Python 层）

```python
# 伪代码
def validate_contract(output: dict) -> tuple[bool, list[str]]:
    errors = []

    # 必须字段校验
    required_fields = ["decision", "reason"]
    for field in required_fields:
        if field not in output:
            errors.append(f"Missing required field: {field}")

    # decision 枚举校验
    valid_decisions = ["no_change", "minor_reorder", "insert_arc", "window_extend", "block_for_manual_review"]
    if output.get("decision") not in valid_decisions:
        errors.append(f"Invalid decision: {output['decision']}")

    # insert_arc 必须提供 mainline_service_reason
    if output.get("decision") == "insert_arc":
        if not output.get("mainline_service_reason"):
            errors.append("insert_arc requires mainline_service_reason")

    return len(errors) == 0, errors
```

### 校验级别 2：硬约束校验

```python
# 伪代码
def validate_hard_constraints(output: dict, context: dict) -> tuple[bool, list[str]]:
    errors = []

    # 禁止修改总纲锚点
    if "mainline_anchor_modifications" in output:
        errors.append("Forbidden: Cannot modify mainline anchors")

    # 禁止修改已写章节
    current_chapter = context.get("current_chapter", 0)
    beat_patch = output.get("beat_patch", {})
    for removed in beat_patch.get("removed_beats", []):
        if removed <= current_chapter:
            errors.append(f"Forbidden: Cannot modify written chapter {removed}")

    # insert_arc 必须有主线服务理由
    if output.get("decision") == "insert_arc":
        if not output.get("mainline_service_reason"):
            errors.append("insert_arc requires non-empty mainline_service_reason")

    return len(errors) == 0, errors
```

### 降级策略

当校验失败时：
- **不自动落盘**：不执行 outline_runtime 更新
- **记录告警**：将错误写入 `observability/dynamic_outline_warnings.jsonl`
- **返回原状态**：保持 `updated_window` 为原值

---

## 与 ImpactPreview 的对齐

| ImpactPreview 字段 | DynamicOutlineDecision 字段 | 对齐说明 |
|-------------------|---------------------------|---------|
| `adjustment_type` | `decision` | 值域映射：`none`→`no_change`，其余直接映射 |
| `reason` | `reason` | 直接复用 |
| `recommended_return_to_mainline_by` | `return_to_mainline_by` | 直接复用 |
| `affected_chapters` | `updated_window.affected_chapters` | 包装在 `updated_window` 内 |
| `copy_segment_signals` | `beat_patch.added_beats` | 转换为节拍结构 |
| `conflict_signals` | `risk_notes` | 合并到风险备注 |
| - | `mainline_service_reason` | 新增：insert_arc 专用 |
| - | `timeline_patch` | 新增：时间线补丁 |

---

## 执行流程（Step 5.5A / Step 5.5B）

### Step 5.5A：影响预览（Impact Preview）

**输入**：
- 当前章节结果（正文、state_changes、relationships_new）
- `ImpactPreview`（来自 `outline_impact_analyzer.py`）
- 活动窗口节点

**输出**：
- 影响预览摘要（供 Step 5.5B 消费）
- 受影响章节/实体/伏笔列表

**执行方式**：
- Python 层执行 `OutlineImpactAnalyzer.analyze()`
- 结果以结构化形式传递给 LLM

### Step 5.5B：动态调纲决策（Dynamic Outline Decision）

**输入**：
- `ImpactPreview`（来自 Step 5.5A）
- 当前上下文（大纲、窗口、主线锚点）

**LLM 决策任务**：
1. 分析 `ImpactPreview` 中的信号
2. 判断是否需要调整
3. 若需要，决定调整类型和范围
4. 输出符合 `DynamicOutlineDecision` schema 的结构化结果

**输出**：
- 符合 `DynamicOutlineDecision` 的结构化 JSON
- Python 层执行 Contract 校验
- 通过后更新 `outline_runtime`，失败则降级处理

---

## 文件位置

- Contract 定义：`references/dynamic-outline-contract.md`
- 影响分析器：`scripts/data_modules/outline_impact_analyzer.py`
- 运行时状态：`outline_runtime`（内存/文件）
- 告警日志：`observability/dynamic_outline_warnings.jsonl`

---

## Phase 2 预留

Phase 2 将引入独立的 `DynamicOutlineAgent`，届时：
- Step 5.5A/5.5B 将由独立 Agent 执行
- Contract 将扩展更多字段（如 `creative_license_notes`）
- 将支持更复杂的副本结构（多副本嵌套）

---

## 验证方式

- 文档审查为主
- 后续集成测试验证 Contract 被正确消费
- Python 层单元测试验证校验逻辑
