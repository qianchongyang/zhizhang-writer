"""
Webnovel Dashboard - FastAPI 主应用

仅提供 GET 接口（严格只读）；所有文件读取经过 path_guard 防穿越校验。
"""

import asyncio
import json
import sys
import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .path_guard import safe_resolve
from .watcher import FileWatcher

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
_project_root: Path | None = None
_watcher = FileWatcher()

STATIC_DIR = Path(__file__).parent / "frontend" / "dist"


def _get_project_root() -> Path:
    if _project_root is None:
        raise HTTPException(status_code=500, detail="项目根目录未配置")
    return _project_root


def _webnovel_dir() -> Path:
    return _get_project_root() / ".webnovel"


def _ensure_plugin_scripts_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    scripts_dir_str = str(scripts_dir)
    if scripts_dir.exists() and scripts_dir_str not in sys.path:
        sys.path.insert(0, scripts_dir_str)


# ---------------------------------------------------------------------------
# 应用工厂
# ---------------------------------------------------------------------------

def create_app(project_root: str | Path | None = None) -> FastAPI:
    global _project_root

    if project_root:
        _project_root = Path(project_root).resolve()

    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        webnovel = _webnovel_dir()
        if webnovel.is_dir():
            _watcher.start(webnovel, asyncio.get_running_loop())
        try:
            yield
        finally:
            _watcher.stop()

    app = FastAPI(title="Webnovel Dashboard", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # ===========================================================
    # API：项目元信息
    # ===========================================================

    @app.get("/api/project/info")
    def project_info():
        """返回 state.json 完整内容（只读）。"""
        state_path = _webnovel_dir() / "state.json"
        if not state_path.is_file():
            raise HTTPException(404, "state.json 不存在")
        return json.loads(state_path.read_text(encoding="utf-8"))

    @app.get("/api/dashboard/summary")
    def dashboard_summary():
        """返回写作驾驶舱所需的聚合只读数据。"""
        root = _get_project_root()
        _ensure_plugin_scripts_path()
        state = _load_json_optional(_webnovel_dir() / "state.json")
        story_memory = _load_json_optional(_webnovel_dir() / "memory" / "story_memory.json")
        chapter = int((state.get("progress") or {}).get("current_chapter") or 0)
        if chapter <= 0:
            chapter = 1

        summary: Dict[str, Any] = {
            "project_info": (state.get("project_info") or {}) if isinstance(state, dict) else {},
            "progress": state.get("progress") if isinstance(state, dict) else {},
            "protagonist_state": state.get("protagonist_state") if isinstance(state, dict) else {},
            "strand_tracker": state.get("strand_tracker") if isinstance(state, dict) else {},
            "chapter": chapter,
            "chapter_outline": "",
            "chapter_intent": {},
            "story_recall": {},
            "memory_health": {},
            "writing_guidance": {},
            "reader_signal": {},
            "genre_profile": {},
            "style_fatigue": {},
            "workflow_trace": _load_workflow_trace(),
            "workflow_timeline": _load_workflow_timeline(),
            "diagnostics": {"degraded": False, "reason": ""},
        }

        try:
            from scripts.data_modules.config import DataModulesConfig
            from scripts.data_modules.context_manager import ContextManager

            config = DataModulesConfig.from_project_root(root)
            config.ensure_dirs()
            context = ContextManager(config).build_context(
                chapter,
                use_snapshot=False,
                save_snapshot=False,
            )
            sections = context.get("sections") or {}
            core = sections.get("core", {}).get("content") or {}
            story_recall = sections.get("story_recall", {}).get("content") or {}
            chapter_intent = sections.get("chapter_intent", {}).get("content") or {}
            writing_guidance = sections.get("writing_guidance", {}).get("content") or {}
            reader_signal = sections.get("reader_signal", {}).get("content") or {}
            genre_profile = sections.get("genre_profile", {}).get("content") or {}

            summary.update(
                {
                    "chapter_outline": str(core.get("chapter_outline") or ""),
                    "recent_summaries": core.get("recent_summaries") or [],
                    "recent_meta": core.get("recent_meta") or [],
                    "chapter_intent": chapter_intent,
                    "story_recall": story_recall,
                    "writing_guidance": writing_guidance,
                    "reader_signal": reader_signal,
                    "genre_profile": genre_profile,
                    "memory_health": _build_memory_health(state, story_recall),
                    "style_fatigue": _build_style_fatigue_signal(state),
                }
            )
        except Exception as exc:  # pragma: no cover - dashboard should degrade gracefully
            summary["chapter_outline"] = _fallback_chapter_outline(root, chapter)
            fallback_recall = _build_fallback_story_recall(state, story_memory)
            summary["story_recall"] = fallback_recall
            summary["memory_health"] = _build_memory_health(state, fallback_recall)
            summary["chapter_intent"] = _build_fallback_chapter_intent(state, chapter, summary["chapter_outline"], fallback_recall)
            summary["style_fatigue"] = _build_style_fatigue_signal(state)
            summary["diagnostics"] = {"degraded": True, "reason": str(exc)}

        if not summary.get("chapter_outline"):
            summary["chapter_outline"] = _fallback_chapter_outline(root, chapter)
        if not summary.get("chapter_intent"):
            summary["chapter_intent"] = _build_fallback_chapter_intent(state, chapter, summary["chapter_outline"], summary.get("story_recall") or {})

        return summary

    # ===========================================================
    # API：实体数据库（index.db 只读查询）
    # ===========================================================

    def _get_db() -> sqlite3.Connection:
        db_path = _webnovel_dir() / "index.db"
        if not db_path.is_file():
            raise HTTPException(404, "index.db 不存在")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _fetchall_safe(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict]:
        """执行只读查询；若目标表不存在（旧库），返回空列表。"""
        try:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            raise HTTPException(status_code=500, detail=f"数据库查询失败: {exc}") from exc

    @app.get("/api/entities")
    def list_entities(
        entity_type: Optional[str] = Query(None, alias="type"),
        include_archived: bool = False,
    ):
        """列出所有实体（可按类型过滤）。"""
        with closing(_get_db()) as conn:
            q = "SELECT * FROM entities"
            params: list = []
            clauses: list[str] = []
            if entity_type:
                clauses.append("type = ?")
                params.append(entity_type)
            if not include_archived:
                clauses.append("is_archived = 0")
            if clauses:
                q += " WHERE " + " AND ".join(clauses)
            q += " ORDER BY last_appearance DESC"
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/entities/{entity_id}")
    def get_entity(entity_id: str):
        with closing(_get_db()) as conn:
            row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
            if not row:
                raise HTTPException(404, "实体不存在")
            return dict(row)

    @app.get("/api/relationships")
    def list_relationships(entity: Optional[str] = None, limit: int = 200):
        with closing(_get_db()) as conn:
            if entity:
                rows = conn.execute(
                    "SELECT * FROM relationships WHERE from_entity = ? OR to_entity = ? ORDER BY chapter DESC LIMIT ?",
                    (entity, entity, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM relationships ORDER BY chapter DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/relationship-events")
    def list_relationship_events(
        entity: Optional[str] = None,
        from_chapter: Optional[int] = None,
        to_chapter: Optional[int] = None,
        limit: int = 200,
    ):
        with closing(_get_db()) as conn:
            q = "SELECT * FROM relationship_events"
            params: list = []
            clauses: list[str] = []
            if entity:
                clauses.append("(from_entity = ? OR to_entity = ?)")
                params.extend([entity, entity])
            if from_chapter is not None:
                clauses.append("chapter >= ?")
                params.append(from_chapter)
            if to_chapter is not None:
                clauses.append("chapter <= ?")
                params.append(to_chapter)
            if clauses:
                q += " WHERE " + " AND ".join(clauses)
            q += " ORDER BY chapter DESC, id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/chapters")
    def list_chapters():
        with closing(_get_db()) as conn:
            rows = conn.execute("SELECT * FROM chapters ORDER BY chapter ASC").fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/scenes")
    def list_scenes(chapter: Optional[int] = None, limit: int = 500):
        with closing(_get_db()) as conn:
            if chapter is not None:
                rows = conn.execute(
                    "SELECT * FROM scenes WHERE chapter = ? ORDER BY scene_index ASC", (chapter,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM scenes ORDER BY chapter ASC, scene_index ASC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/reading-power")
    def list_reading_power(limit: int = 50):
        with closing(_get_db()) as conn:
            rows = conn.execute(
                "SELECT * FROM chapter_reading_power ORDER BY chapter DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/review-metrics")
    def list_review_metrics(limit: int = 20):
        with closing(_get_db()) as conn:
            rows = conn.execute(
                "SELECT * FROM review_metrics ORDER BY end_chapter DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/state-changes")
    def list_state_changes(entity: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if entity:
                rows = conn.execute(
                    "SELECT * FROM state_changes WHERE entity_id = ? ORDER BY chapter DESC LIMIT ?",
                    (entity, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM state_changes ORDER BY chapter DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/aliases")
    def list_aliases(entity: Optional[str] = None):
        with closing(_get_db()) as conn:
            if entity:
                rows = conn.execute(
                    "SELECT * FROM aliases WHERE entity_id = ?", (entity,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM aliases").fetchall()
            return [dict(r) for r in rows]

    # ===========================================================
    # API：扩展表（v5.3+ / v5.4+）
    # ===========================================================

    @app.get("/api/overrides")
    def list_overrides(status: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if status:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM override_contracts WHERE status = ? ORDER BY chapter DESC LIMIT ?",
                    (status, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM override_contracts ORDER BY chapter DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/debts")
    def list_debts(status: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if status:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM chase_debt WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM chase_debt ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/debt-events")
    def list_debt_events(debt_id: Optional[int] = None, limit: int = 200):
        with closing(_get_db()) as conn:
            if debt_id is not None:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM debt_events WHERE debt_id = ? ORDER BY chapter DESC, id DESC LIMIT ?",
                    (debt_id, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM debt_events ORDER BY chapter DESC, id DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/invalid-facts")
    def list_invalid_facts(status: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if status:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM invalid_facts WHERE status = ? ORDER BY marked_at DESC LIMIT ?",
                    (status, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM invalid_facts ORDER BY marked_at DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/rag-queries")
    def list_rag_queries(query_type: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if query_type:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM rag_query_log WHERE query_type = ? ORDER BY created_at DESC LIMIT ?",
                    (query_type, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM rag_query_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/tool-stats")
    def list_tool_stats(tool_name: Optional[str] = None, limit: int = 200):
        with closing(_get_db()) as conn:
            if tool_name:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM tool_call_stats WHERE tool_name = ? ORDER BY created_at DESC LIMIT ?",
                    (tool_name, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM tool_call_stats ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/checklist-scores")
    def list_checklist_scores(limit: int = 100):
        with closing(_get_db()) as conn:
            return _fetchall_safe(
                conn,
                "SELECT * FROM writing_checklist_scores ORDER BY chapter DESC LIMIT ?",
                (limit,),
            )

    # ===========================================================
    # API：文档浏览（正文/大纲/设定集 —— 只读）
    # ===========================================================

    @app.get("/api/files/tree")
    def file_tree():
        """列出 正文/、大纲/、设定集/ 三个目录的树结构。"""
        root = _get_project_root()
        result = {}
        for folder_name in ("正文", "大纲", "设定集"):
            folder = root / folder_name
            if not folder.is_dir():
                result[folder_name] = []
                continue
            result[folder_name] = _walk_tree(folder, root)
        return result

    @app.get("/api/files/read")
    def file_read(path: str):
        """只读读取一个文件内容（限 正文/大纲/设定集 目录）。"""
        root = _get_project_root()
        resolved = safe_resolve(root, path)

        # 二次限制：只允许三大目录
        allowed_parents = [root / n for n in ("正文", "大纲", "设定集")]
        if not any(_is_child(resolved, p) for p in allowed_parents):
            raise HTTPException(403, "仅允许读取 正文/大纲/设定集 目录下的文件")

        if not resolved.is_file():
            raise HTTPException(404, "文件不存在")

        # 文本文件直接读；其他情况返回占位信息
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = "[二进制文件，无法预览]"

        return {"path": path, "content": content}

    # ===========================================================
    # SSE：实时变更推送
    # ===========================================================

    @app.get("/api/events")
    async def sse():
        """Server-Sent Events 端点，推送 .webnovel/ 下的文件变更。"""
        q = _watcher.subscribe()

        async def _gen():
            try:
                while True:
                    msg = await q.get()
                    yield f"data: {msg}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                _watcher.unsubscribe(q)

        return StreamingResponse(_gen(), media_type="text/event-stream")

    # ===========================================================
    # 前端静态文件托管
    # ===========================================================

    if STATIC_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

        @app.get("/{full_path:path}")
        def serve_spa(full_path: str):
            """SPA fallback：任何非 /api 路径都返回 index.html。"""
            index = STATIC_DIR / "index.html"
            if index.is_file():
                return FileResponse(str(index))
            raise HTTPException(404, "前端尚未构建")
    else:
        @app.get("/")
        def no_frontend():
            return HTMLResponse(
                "<h2>Webnovel Dashboard API is running</h2>"
                "<p>前端尚未构建。请先在 <code>dashboard/frontend</code> 目录执行 <code>npm run build</code>。</p>"
                '<p>API 文档：<a href="/docs">/docs</a></p>'
            )

    return app


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _walk_tree(folder: Path, root: Path) -> list[dict]:
    items = []
    for child in sorted(folder.iterdir()):
        rel = str(child.relative_to(root)).replace("\\", "/")
        if child.is_dir():
            items.append({"name": child.name, "type": "dir", "path": rel, "children": _walk_tree(child, root)})
        else:
            items.append({"name": child.name, "type": "file", "path": rel, "size": child.stat().st_size})
    return items


def _is_child(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _load_json_optional(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _load_workflow_trace() -> Dict[str, Any]:
    workflow_state = _load_json_optional(_webnovel_dir() / "workflow_state.json")
    current_task = workflow_state.get("current_task") if isinstance(workflow_state, dict) else {}
    if isinstance(current_task, dict) and current_task.get("workflow_trace"):
        return dict(current_task.get("workflow_trace") or {})
    last_stable = workflow_state.get("last_stable_state") if isinstance(workflow_state, dict) else {}
    if isinstance(last_stable, dict) and last_stable.get("workflow_trace"):
        return dict(last_stable.get("workflow_trace") or {})
    return {}


def _load_workflow_timeline() -> list[Dict[str, Any]]:
    workflow_state = _load_json_optional(_webnovel_dir() / "workflow_state.json")
    timeline: list[Dict[str, Any]] = []
    current_task = workflow_state.get("current_task") if isinstance(workflow_state, dict) else {}
    if isinstance(current_task, dict):
        for step in current_task.get("completed_steps") or []:
            if isinstance(step, dict):
                timeline.append(
                    {
                        "id": step.get("id"),
                        "name": step.get("name"),
                        "status": step.get("status"),
                        "updated_at": step.get("completed_at") or step.get("started_at"),
                    }
                )
        current_step = current_task.get("current_step")
        if isinstance(current_step, dict):
            timeline.append(
                {
                    "id": current_step.get("id"),
                    "name": current_step.get("name"),
                    "status": current_step.get("status"),
                    "updated_at": current_step.get("started_at"),
                }
            )
        if not timeline and isinstance(current_task.get("workflow_trace"), dict):
            trace = current_task.get("workflow_trace") or {}
            timeline.append(
                {
                    "id": trace.get("stage"),
                    "name": trace.get("stage"),
                    "status": trace.get("status"),
                    "updated_at": trace.get("updated_at"),
                }
            )
    if timeline:
        return timeline[-6:]
    history = workflow_state.get("history") if isinstance(workflow_state, dict) else []
    if isinstance(history, list) and history:
        last = history[-1] if isinstance(history[-1], dict) else {}
        trace = last.get("workflow_trace") if isinstance(last, dict) else {}
        if isinstance(trace, dict) and trace:
            return [
                {
                    "id": trace.get("stage"),
                    "name": trace.get("stage"),
                    "status": trace.get("status"),
                    "updated_at": trace.get("updated_at") or last.get("completed_at"),
                }
            ]
    return []


def _fallback_chapter_outline(project_root: Path, chapter: int) -> str:
    try:
        from chapter_outline_loader import load_chapter_outline
    except Exception:
        return ""
    try:
        return load_chapter_outline(project_root, chapter, max_chars=1500)
    except Exception:
        return ""


def _build_memory_health(state: Dict[str, Any], story_recall: Dict[str, Any]) -> Dict[str, Any]:
    recall_policy = story_recall.get("recall_policy") or {}
    priority_foreshadowing = story_recall.get("priority_foreshadowing") or []
    recent_events = story_recall.get("recent_events") or []
    character_focus = story_recall.get("character_focus") or []
    emotional_focus = story_recall.get("emotional_focus") or []
    structured_change_focus = story_recall.get("structured_change_focus") or []
    archive_recall = story_recall.get("archive_recall") or {}
    archive_counts = {
        "plot_threads": len(archive_recall.get("plot_threads") or []),
        "recent_events": len(archive_recall.get("recent_events") or []),
        "structured_change_focus": len(archive_recall.get("structured_change_focus") or []),
    }

    last_consolidated_chapter = int(story_recall.get("last_consolidated_chapter") or 0)
    current_chapter = int((state.get("progress") or {}).get("current_chapter") or 0)
    consolidation_gap = int(recall_policy.get("consolidation_gap") or max(0, current_chapter - last_consolidated_chapter))
    stale = consolidation_gap >= 3
    status = "healthy"
    if stale and not archive_recall:
        status = "lagging"
    elif len(priority_foreshadowing) >= 5 or len(structured_change_focus) >= 4:
        status = "busy"

    return {
        "status": status,
        "current_chapter": current_chapter,
        "last_consolidated_chapter": last_consolidated_chapter,
        "consolidation_gap": consolidation_gap,
        "should_recall_story_memory": bool(recall_policy.get("should_recall_story_memory")),
        "recall_mode": recall_policy.get("mode", "normal"),
        "signal_count": int(recall_policy.get("signal_count") or 0),
        "tier_counts": recall_policy.get("tier_counts") or {},
        "priority_foreshadowing_count": len(priority_foreshadowing),
        "recent_events_count": len(recent_events),
        "character_focus_count": len(character_focus),
        "emotional_focus_count": len(emotional_focus),
        "structured_change_count": len(structured_change_focus),
        "archive_available": bool(archive_recall),
        "archive_counts": archive_counts,
        "memory_stale": stale,
    }


def _build_fallback_chapter_intent(
    state: Dict[str, Any],
    chapter: int,
    chapter_outline: str,
    story_recall: Dict[str, Any],
) -> Dict[str, Any]:
    must_resolve = [
        str(item.get("name") or item.get("content") or item.get("event") or "").strip()
        for item in (story_recall.get("priority_foreshadowing") or [])[:3]
        if isinstance(item, dict)
    ]
    story_risks: list[str] = []
    recall_policy = story_recall.get("recall_policy") or {}
    consolidation_gap = int(recall_policy.get("consolidation_gap") or 0)
    if consolidation_gap >= 3:
        story_risks.append(f"记忆整理滞后 {consolidation_gap} 章")
    if len(must_resolve) >= 3:
        story_risks.append("高优先级伏笔较多")
    return {
        "chapter": chapter,
        "focus_title": "",
        "chapter_goal": str(chapter_outline or "").strip()[:120],
        "must_resolve": [item for item in must_resolve if item],
        "priority_memory": [],
        "story_risks": story_risks,
        "hard_constraints": [],
    }


def _build_style_fatigue_signal(state: Dict[str, Any]) -> Dict[str, Any]:
    chapter_meta = (state.get("chapter_meta") or {}) if isinstance(state, dict) else {}
    if not isinstance(chapter_meta, dict):
        return {"count": 0, "status": "clean", "issues": []}
    latest_key = sorted(chapter_meta.keys())[-1] if chapter_meta else ""
    latest_meta = chapter_meta.get(latest_key) or {}
    issues = latest_meta.get("style_fatigue") or []
    if not isinstance(issues, list):
        issues = []
    count = len(issues)
    status = "clean"
    type_counts: Dict[str, int] = {}
    for item in issues:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or item.get("issue_type") or "generic")
        type_counts[item_type] = int(type_counts.get(item_type) or 0) + 1
    if count >= 3:
        status = "warn"
    elif count > 0:
        status = "notice"
    return {
        "count": count,
        "status": status,
        "type_counts": type_counts,
        "dominant_type": max(type_counts, key=type_counts.get) if type_counts else "",
        "issues": issues[:5],
    }


def _build_fallback_story_recall(state: Dict[str, Any], story_memory: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(story_memory, dict):
        story_memory = {}

    characters = story_memory.get("characters") if isinstance(story_memory.get("characters"), dict) else {}
    plot_threads = story_memory.get("plot_threads") if isinstance(story_memory.get("plot_threads"), list) else []
    recent_events = story_memory.get("recent_events") if isinstance(story_memory.get("recent_events"), list) else []
    change_ledger = (
        story_memory.get("structured_change_ledger")
        if isinstance(story_memory.get("structured_change_ledger"), list)
        else story_memory.get("numeric_ledger")
        if isinstance(story_memory.get("numeric_ledger"), list)
        else []
    )
    archive = story_memory.get("archive") if isinstance(story_memory.get("archive"), dict) else {}
    emotional_arcs = story_memory.get("emotional_arcs") if isinstance(story_memory.get("emotional_arcs"), dict) else {}

    protagonist_name = ""
    protagonist_state = state.get("protagonist_state", {}) if isinstance(state, dict) else {}
    if isinstance(protagonist_state, dict):
        protagonist_name = str(protagonist_state.get("name") or "").strip()

    active_foreshadowing = []
    for item in plot_threads:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").lower()
        if status and status not in {"pending", "active", "未回收"}:
            continue
        active_foreshadowing.append(item)

    character_focus = []
    if protagonist_name and protagonist_name in characters and isinstance(characters.get(protagonist_name), dict):
        protagonist_entry = dict(characters.get(protagonist_name) or {})
        character_focus.append(
            {
                "name": protagonist_name,
                "current_state": protagonist_entry.get("current_state", ""),
                "last_update_chapter": protagonist_entry.get("last_update_chapter", 0),
            }
        )
    for name, info in list(characters.items())[:4]:
        if name == protagonist_name or not isinstance(info, dict):
            continue
        character_focus.append(
            {
                "name": str(name),
                "current_state": info.get("current_state", ""),
                "last_update_chapter": info.get("last_update_chapter", 0),
            }
        )

    emotional_focus = []
    for name in [protagonist_name] + [str(item.get("name") or "") for item in character_focus]:
        rows = emotional_arcs.get(name) or []
        if not isinstance(rows, list) or not rows:
            continue
        latest = rows[-1]
        if not isinstance(latest, dict):
            continue
        emotional_focus.append(
            {
                "name": name,
                "emotional_state": latest.get("emotional_state", ""),
                "emotional_trend": latest.get("emotional_trend", "stable"),
                "trigger_event": latest.get("trigger_event", ""),
                "chapter": latest.get("chapter", 0),
            }
        )

    structured_change_focus = []
    for item in change_ledger[:5]:
        if not isinstance(item, dict):
            continue
        structured_change_focus.append(
            {
                "ch": item.get("ch", 0),
                "entity_id": item.get("entity_id", ""),
                "field": item.get("field", ""),
                "change_kind": item.get("change_kind") or item.get("type") or "state_change",
                "memory_score": item.get("memory_score", 0),
                "memory_tier": item.get("memory_tier", "working"),
                "old_value": item.get("old_value"),
                "new_value": item.get("new_value"),
                "delta": item.get("delta"),
            }
        )

    archive_recall = {
        "plot_threads": [dict(item, memory_tier="archive", archive_score=1) for item in (archive.get("plot_threads") or [])[:2] if isinstance(item, dict)],
        "recent_events": [dict(item, memory_tier="archive", archive_score=1) for item in (archive.get("recent_events") or [])[:2] if isinstance(item, dict)],
        "structured_change_focus": [dict(item, memory_tier="archive", archive_score=1) for item in (archive.get("structured_change_ledger") or [])[:2] if isinstance(item, dict)],
    }

    return {
        "version": str(story_memory.get("version", "")),
        "last_consolidated_chapter": int(story_memory.get("last_consolidated_chapter") or 0),
        "last_consolidated_at": str(story_memory.get("last_consolidated_at", "")),
        "recall_policy": {
            "mode": "normal" if not story_memory else "boost",
            "should_recall_story_memory": bool(story_memory),
            "reasons": ["fallback_story_memory"],
            "signal_count": len(active_foreshadowing) + len(character_focus) + len(structured_change_focus) + len(recent_events) + len(emotional_focus),
            "consolidation_gap": max(0, int((state.get("progress") or {}).get("current_chapter") or 0) - int(story_memory.get("last_consolidated_chapter") or 0)),
            "tier_counts": {
                "consolidated": len([item for item in structured_change_focus if str(item.get("memory_tier")) == "consolidated"]),
                "episodic": len([item for item in structured_change_focus if str(item.get("memory_tier")) == "episodic"]),
                "working": len([item for item in structured_change_focus if str(item.get("memory_tier")) == "working"]),
            },
        },
        "priority_foreshadowing": active_foreshadowing[:5],
        "recent_events": recent_events[-5:],
        "character_focus": character_focus[:5],
        "emotional_focus": emotional_focus[:3],
        "structured_change_focus": structured_change_focus[:5],
        "archive_recall": archive_recall if any(archive_recall.values()) else {},
    }
