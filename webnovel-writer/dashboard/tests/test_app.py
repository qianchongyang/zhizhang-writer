from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from dashboard.app import create_app


def _build_project_root(tmp_path: Path) -> Path:
    root = tmp_path / "novel-project"
    webnovel = root / ".webnovel"
    outline_dir = root / "大纲"
    webnovel.mkdir(parents=True, exist_ok=True)
    outline_dir.mkdir(parents=True, exist_ok=True)

    (webnovel / "state.json").write_text(
        json.dumps(
            {
                "project_info": {
                    "title": "测试项目",
                    "genre": "xuanhuan",
                    "target_words": 100000,
                    "target_chapters": 10,
                },
                "progress": {
                    "current_chapter": 1,
                    "current_volume": 1,
                    "total_words": 1234,
                    "volumes_planned": [{"volume": 1, "chapters_range": "1-10"}],
                },
                "protagonist_state": {
                    "name": "萧炎",
                    "location": {"current": "宗门"},
                    "power": {"realm": "筑基"},
                },
                "strand_tracker": {
                    "current_dominant": "quest",
                    "history": [{"chapter": 1, "strand": "quest"}],
                },
                "chapter_meta": {},
                "disambiguation_warnings": [],
                "disambiguation_pending": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (webnovel / "story_memory.json").write_text(
        json.dumps(
            {
                "version": "1",
                "last_consolidated_chapter": 1,
                "last_consolidated_at": "2026-03-27T10:00:00Z",
                "characters": {
                    "萧炎": {"current_state": "宗门修行", "last_update_chapter": 1}
                },
                "plot_threads": [
                    {"name": "身世线索", "status": "active", "tier": "核心", "urgency": 90}
                ],
                "recent_events": [{"ch": 1, "event": "入门测试"}],
                "structured_change_ledger": [
                    {
                        "ch": 1,
                        "entity_id": "xiaoyan",
                        "field": "状态",
                        "old_value": "新手",
                        "new_value": "入门",
                        "memory_score": 80,
                        "memory_tier": "consolidated",
                    }
                ],
                "chapter_snapshots": [],
                "meta": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (outline_dir / "第1卷-详细大纲.md").write_text("### 第1章：测试标题\n测试大纲", encoding="utf-8")
    return root


def test_dashboard_summary_returns_cockpit_data(tmp_path):
    root = _build_project_root(tmp_path)
    app = create_app(root)
    client = TestClient(app)

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200

    data = response.json()
    assert data["project_info"]["title"] == "测试项目"
    assert "测试大纲" in data["chapter_outline"]
    assert data["memory_health"]["current_chapter"] == 1
    assert "recall_policy" in data["story_recall"]
    assert isinstance(data["story_recall"]["priority_foreshadowing"], list)
    assert "diagnostics" in data
