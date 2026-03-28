# project_memory.json 设计

用于保存长期可复用的写作模式，由 `/webnovel-learn` 写入。

## 示例

```json
{
  "patterns": [
    {
      "pattern_type": "hook",
      "description": "危机钩设计：悬念拉满",
      "source_chapter": 100,
      "learned_at": "2026-02-02T12:00:00Z"
    }
  ],
  "technique_patterns": [],
  "technique_execution_history": [],
  "technique_summary": {
    "effective": [],
    "fatigue": [],
    "last_updated": ""
  }
}
```

## 字段说明
- patterns: 已验证的写作模式列表
  - pattern_type: hook / pacing / dialogue / payoff / emotion
  - description: 可复用描述
  - source_chapter: 来源章节
  - learned_at: 记录时间
- technique_patterns: 技巧模式账本（按项目沉淀）
  - technique_id: 技巧唯一标识
  - type: hook / coolpoint / technique
  - genre_scope: 适用题材
  - scene_role: build_up / confront / release
  - effectiveness: effective / neutral / fatigue
- technique_execution_history: 最近章节的技巧执行记录
- technique_summary: 当前项目内的有效技巧与疲劳技巧摘要
