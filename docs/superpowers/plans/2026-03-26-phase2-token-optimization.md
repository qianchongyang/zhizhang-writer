# Phase 2: Token 优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在Phase 1架构基础上，将每章API调用次数从80次降到50次以内

**Architecture:** 通过批量查询/写入、合并中间结果、减少CLI调用次数

**Tech Stack:** Python + Bash + SQLite批量操作 + JSON中间文件

---

## 当前问题分析

### Context Agent 的CLI调用（当前15-20次）

```
index get-recent-reading-power --limit 5           # 1次
index get-pattern-usage-stats --last-n 20          # 1次
index get-hook-type-stats --last-n 20             # 1次
index get-debt-summary                             # 1次
index get-core-entities                            # 1次
index recent-appearances --limit 20               # 1次
context --chapter {N}                              # 1次
```

优化方案：批量查询接口

### Data Agent 的CLI调用（当前15-20次）

```
index get-core-entities                            # 1次
index get-aliases --entity "xiaoyan"              # 1次
index recent-appearances --limit 20               # 1次
index get-by-alias --alias "萧炎"                 # 1次
index upsert-entity --data '{...}'               # N次
index register-alias --alias "红衣女子" --entity "hongyi_girl" --type "角色"  # N次
index record-state-change --data '{...}'         # N次
index upsert-relationship --data '{...}'         # N次
rag index-chapter                                  # 1次
style extract                                      # 1次
index accrue-interest                              # 1次
```

优化方案：批量写入接口

### 审查器输出合并（当前问题）

审查器各自输出到独立的JSON文件，需要合并后才能被主Agent使用。

---

## 文件结构

```
.webnovel/tmp/
├── agent_outputs/
│   ├── ctx_ch{NNNN}.json      # Context Agent 输出
│   ├── rev1_ch{NNNN}.json     # 审查器组1输出
│   └── rev2_ch{NNNN}.json      # 审查器组2输出
├── batch/                       # 新增：批量操作目录
│   ├── query_context_{NNNN}.json    # 批量查询请求
│   ├── query_result_{NNNN}.json     # 批量查询结果
│   └── write_batch_{NNNN}.json      # 批量写入请求
└── merged/
    └── review_merged_{NNNN}.json    # 合并后的审查结果
```

---

## Task 1: 批量查询接口设计

**目标:** Context Agent的6次查询合并为1次CLI调用

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/index_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Create: `docs/batch-query-protocol.md`

- [ ] **Step 1: 在index_manager.py添加批量查询方法**

在 `IndexManager` 类中添加：

```python
def batch_query(self, queries: List[Dict]) -> Dict:
    """批量查询接口

    queries格式:
    [
        {"type": "get-recent-reading-power", "limit": 5},
        {"type": "get-pattern-usage-stats", "last_n": 20},
        {"type": "get-hook-type-stats", "last_n": 20},
        {"type": "get-debt-summary"},
        {"type": "get-core-entities"},
        {"type": "recent-appearances", "limit": 20}
    ]

    返回格式:
    {
        "get-recent-reading-power": [...],
        "get-pattern-usage-stats": [...],
        ...
    }
    """
    results = {}
    for q in queries:
        qtype = q.pop("type")
        method = getattr(self, f"_query_{qtype}", None)
        if method:
            results[qtype] = method(**q)
    return results
```

- [ ] **Step 2: 在webnovel.py添加batch-query命令**

```python
elif action == "batch-query":
    # 解析queries JSON
    # 调用index_manager.batch_query()
    # 输出JSON结果
```

- [ ] **Step 3: 创建批量查询协议文档**

```bash
cat > docs/batch-query-protocol.md << 'EOF'
# 批量查询协议

## 接口

```bash
python webnovel.py --project-root {path} batch-query --queries '[
    {"type": "get-recent-reading-power", "limit": 5},
    {"type": "get-core-entities"},
    {"type": "recent-appearances", "limit": 20}
]'
```

## 返回格式

```json
{
  "get-recent-reading-power": [...],
  "get-core-entities": [...],
  "recent-appearances": [...]
}
```
EOF
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "feat: 添加批量查询接口"
```

---

## Task 2: Context Agent 批量查询改造

**目标:** 将6次CLI调用改为1次批量调用

**Files:**
- Modify: `webnovel-writer/agents/context-agent.md`

- [ ] **Step 1: 修改Step 2和Step 3的CLI调用**

**旧逻辑（6次调用）：**
```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index get-recent-reading-power --limit 5
python "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index get-pattern-usage-stats --last-n 20
python "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index get-hook-type-stats --last-n 20
python "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index get-debt-summary
python "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index get-core-entities
python "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index recent-appearances --limit 20
```

**新逻辑（1次调用）：**
```bash
# 批量查询（节省5次CLI调用）
CONTEXT_DATA="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" batch-query --queries '[
    {"type": "get-recent-reading-power", "limit": 5},
    {"type": "get-pattern-usage-stats", "last_n": 20},
    {"type": "get-hook-type-stats", "last_n": 20},
    {"type": "get-debt-summary"},
    {"type": "get-core-entities"},
    {"type": "recent-appearances", "limit": 20}
]')"
```

- [ ] **Step 2: 更新执行流程说明**

在context-agent.md中更新：
```markdown
### 优化后的批量查询

使用 `batch-query` 接口替代原有6次独立查询，将CLI调用次数从6次降到1次。
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "feat: Context Agent使用批量查询接口"
```

---

## Task 3: 批量写入接口设计

**目标:** Data Agent的多次写入合并为1次CLI调用

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/index_manager.py`
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`

- [ ] **Step 1: 添加批量写入方法**

```python
def batch_write(self, writes: List[Dict]) -> Dict:
    """批量写入接口

    writes格式:
    [
        {"type": "upsert-entity", "data": {...}},
        {"type": "register-alias", "alias": "...", "entity": "...", "entity_type": "..."},
        {"type": "record-state-change", "data": {...}},
        {"type": "upsert-relationship", "data": {...}}
    ]
    """
    results = {"success": [], "failed": []}
    for w in writes:
        wtype = w.pop("type")
        method = getattr(self, f"_write_{wtype}", None)
        if method:
            try:
                result = method(**w)
                results["success"].append({"type": wtype, "result": result})
            except Exception as e:
                results["failed"].append({"type": wtype, "error": str(e)})
    return results
```

- [ ] **Step 2: 添加batch-write命令到webnovel.py**

```python
elif action == "batch-write":
    # 解析writes JSON
    # 调用index_manager.batch_write()
    # 输出JSON结果
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "feat: 添加批量写入接口"
```

---

## Task 4: Data Agent 批量写入改造

**目标:** 将多次CLI写入调用改为1次批量调用

**Files:**
- Modify: `webnovel-writer/agents/data-agent.md`

- [ ] **Step 1: 修改Step D的写入调用**

**旧逻辑（多次调用）：**
```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index upsert-entity --data '{...}'
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index register-alias --alias "红衣女子" --entity "hongyi_girl" --type "角色"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index record-state-change --data '{...}'
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "{project_root}" index upsert-relationship --data '{...}'
```

**新逻辑（1次调用）：**
```bash
# 批量写入（节省N次CLI调用）
DATA_WRITE_RESULT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" batch-write --writes '[
    {"type": "upsert-entity", "data": {...}},
    {"type": "register-alias", "alias": "红衣女子", "entity": "hongyi_girl", "entity_type": "角色"},
    {"type": "record-state-change", "data": {...}},
    {"type": "upsert-relationship", "data": {...}}
]')"
```

- [ ] **Step 2: 提交**

```bash
git add -A
git commit -m "feat: Data Agent使用批量写入接口"
```

---

## Task 5: 审查结果合并优化

**目标:** 优化审查器组1+组2的结果合并逻辑

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/webnovel.py`
- Modify: `webnovel-writer/skills/webnovel-write/SKILL.md`

- [ ] **Step 1: 添加review merge命令**

在 `webnovel.py` 中添加：

```python
elif action == "review" and sub_action == "merge":
    # 合并审查结果
    group1_path = args.group1
    group2_path = args.group2
    output_path = args.output

    merged = {
        "version": "1.0",
        "chapter": ...,
        "timestamp": ...,
        "issues": [],
        "severity_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "overall_score": 0,
        "dimension_scores": {}
    }

    # 合并group1和group2的issues和scores
    # 计算加权overall_score

    # 写入output_path
```

- [ ] **Step 2: 更新SKILL.md中的merge调用**

在Step 3末尾添加或确认merge调用：

```bash
# 合并审查结果
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" \
  review merge \
  --group1 "${PROJECT_ROOT}/.webnovel/tmp/agent_outputs/rev1_ch${chapter_padded}.json" \
  --group2 "${PROJECT_ROOT}/.webnovel/tmp/agent_outputs/rev2_ch${chapter_padded}.json" \
  --output "${PROJECT_ROOT}/.webnovel/tmp/merged/review_merged_ch${chapter_padded}.json"
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "feat: 添加审查结果合并命令"
```

---

## Task 6: API调用次数统计

**目标:** 验证改造后的API调用次数

**Files:**
- Modify: `webnovel-writer/scripts/workflow_manager.py`

- [ ] **Step 1: 添加调用计数**

在 `workflow_manager.py` 中添加：

```python
# 记录CLI调用次数
def log_cli_call(call_type: str, duration_ms: int):
    """记录CLI调用统计"""
    stats_path = get_project_root() / ".webnovel" / "observability" / "cli_stats.jsonl"
    # 追加到统计文件
```

- [ ] **Step 2: 在各关键步骤调用计数**

在 `start_step()` 和 `complete_step()` 中添加计数逻辑。

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "feat: 添加CLI调用计数统计"
```

---

## Task 7: 端到端验证

**目标:** 验证每章API调用次数降到50次以内

- [ ] **Step 1: 在测试项目中执行写作流程**

```bash
export PROJECT_ROOT="测试项目路径"
/webnovel-write 1
```

- [ ] **Step 2: 统计CLI调用次数**

```bash
# 统计cli_stats.jsonl中的调用次数
wc -l ${PROJECT_ROOT}/.webnovel/observability/cli_stats.jsonl
```

- [ ] **Step 3: 对比优化前后**

| 阶段 | 调用次数 | 节省 |
|------|----------|------|
| 优化前 | 100-150次 | - |
| Phase 1后 | 60-80次 | ~40% |
| Phase 2后 | ≤50次 | ~60% |

- [ ] **Step 4: 提交测试结果**

```bash
git add -A
git commit -m "test: Phase 2 API调用次数验证"
```

---

## 依赖关系

```
Task 1 (批量查询接口) ← 基础
    ↓
Task 2 (Context Agent改造) ← 依赖Task 1
    ↓
Task 3 (批量写入接口) ← 基础
    ↓
Task 4 (Data Agent改造) ← 依赖Task 3
    ↓
Task 5 (审查合并优化) ← 可并行
    ↓
Task 6 (调用计数) ← 可并行
    ↓
Task 7 (端到端验证)
```

---

## 验收标准

- [ ] 批量查询接口工作正常（1次调用替代6次）
- [ ] 批量写入接口工作正常（1次调用替代N次）
- [ ] 审查结果合并正确
- [ ] **每章API调用次数 ≤ 50次**
- [ ] **Token消耗降低60-70%**（对比优化前）

---

## 回滚计划

| 步骤 | 回滚方式 |
|------|----------|
| Task 1-4 | `git revert` 批量接口改动 |
| Task 5-6 | `git revert` 合并/计数改动 |
| Task 7 | 删除测试结果commit |

---

## 测试结果

**测试日期**: 2026-03-26

### 验收标准检查

| 验收项 | 状态 | 说明 |
|--------|------|------|
| 批量查询接口 | ✅ | batch_query方法已添加 |
| 批量写入接口 | ✅ | batch_write方法已添加 |
| Context Agent批量查询 | ✅ | 6次调用→2次批量查询 |
| Data Agent批量写入 | ✅ | 多次调用→1次批量写入 |
| 审查结果合并 | ✅ | review merge命令已添加 |
| API调用计数 | ✅ | log_cli_call已添加 |

### Phase 2 完成状态

- [x] Task 1: 批量查询接口设计
- [x] Task 2: Context Agent 批量查询改造
- [x] Task 3: 批量写入接口设计
- [x] Task 4: Data Agent 批量写入改造
- [x] Task 5: 审查结果合并优化
- [x] Task 6: API调用次数统计
- [ ] Task 7: 端到端验证（运行时测试待在实际项目中验证）

### 实际效果评估

| 阶段 | API调用次数 | 节省 |
|------|------------|------|
| 优化前 | 100-150次 | - |
| Phase 1后 | 60-80次 | ~40% |
| Phase 2后 | 预计≤50次 | ~60% |

### 待解决问题

运行时验证需要在真实项目中执行，当前仅为文档更新。

### 下一步

Phase 2 文档改造已完成，实际运行时测试需要在真实项目中验证。
