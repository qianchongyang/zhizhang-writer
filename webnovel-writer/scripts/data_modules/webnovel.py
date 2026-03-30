#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webnovel / zhizhang 统一入口（面向 skills / agents 的稳定 CLI）

设计目标：
- 只有一个入口命令，避免到处拼 `python -m data_modules.xxx ...` 导致参数位置/引号/路径炸裂。
- 自动解析正确的 book project_root（包含 `.webnovel/state.json` 的目录）。
- 所有写入类命令在解析到 project_root 后，统一前置 `--project-root` 传给具体模块。

典型用法（推荐，不依赖 PYTHONPATH / 不要求 cd）：
  python "<SCRIPTS_DIR>/webnovel.py" preflight
  python "<SCRIPTS_DIR>/webnovel.py" where
  python "<SCRIPTS_DIR>/webnovel.py" use D:\\wk\\xiaoshuo\\凡人资本论
  python "<SCRIPTS_DIR>/webnovel.py" --project-root D:\\wk\\xiaoshuo index stats
  python "<SCRIPTS_DIR>/webnovel.py" --project-root D:\\wk\\xiaoshuo state process-chapter --chapter 100 --data @payload.json
  python "<SCRIPTS_DIR>/webnovel.py" --project-root D:\\wk\\xiaoshuo extract-context --chapter 100 --format json

也支持（不推荐，容易踩 PYTHONPATH/cd/参数顺序坑）：
  python -m data_modules.webnovel where
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .runtime_compat import normalize_windows_path
from project_locator import resolve_project_root, write_current_project_pointer, update_global_registry_current_project


def _scripts_dir() -> Path:
    # data_modules/webnovel.py -> data_modules -> scripts
    return Path(__file__).resolve().parent.parent


def _find_skill_root(plugin_root: Path) -> Path:
    """
    优先识别新品牌技能目录，兼容旧目录。
    """
    candidates = [
        plugin_root / "skills" / "zhizhang-write",
        plugin_root / "skills" / "webnovel-write",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[-1]


def _find_entry_script(scripts_dir: Path) -> Path:
    """
    优先识别新品牌入口脚本，兼容旧入口。
    """
    candidates = [
        scripts_dir / "zhizhang.py",
        scripts_dir / "webnovel.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


def _resolve_root(explicit_project_root: Optional[str]) -> Path:
    # 允许显式传入工作区根目录或书项目根目录
    raw = explicit_project_root
    if raw:
        return resolve_project_root(raw)
    return resolve_project_root()


def _strip_project_root_args(argv: list[str]) -> list[str]:
    """
    下游工具统一由本入口注入 `--project-root`，避免重复传参导致 argparse 报错/歧义。
    """
    out: list[str] = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--project-root":
            i += 2
            continue
        if tok.startswith("--project-root="):
            i += 1
            continue
        out.append(tok)
        i += 1
    return out


def _run_data_module(module: str, argv: list[str]) -> int:
    """
    Import `data_modules.<module>` and call its main(), while isolating sys.argv.
    """
    mod = importlib.import_module(f"data_modules.{module}")
    main = getattr(mod, "main", None)
    if not callable(main):
        raise RuntimeError(f"data_modules.{module} 缺少可调用的 main()")

    old_argv = sys.argv
    try:
        sys.argv = [f"data_modules.{module}"] + argv
        try:
            main()
            return 0
        except SystemExit as e:
            return int(e.code or 0)
    finally:
        sys.argv = old_argv


def _run_script(script_name: str, argv: list[str]) -> int:
    """
    Run a script under `.claude/scripts/` via a subprocess.

    用途：兼容没有 main() 的脚本（例如 workflow_manager.py）。
    """
    script_path = _scripts_dir() / script_name
    if not script_path.is_file():
        raise FileNotFoundError(f"未找到脚本: {script_path}")
    proc = subprocess.run([sys.executable, str(script_path), *argv])
    return int(proc.returncode or 0)


def cmd_review(args: argparse.Namespace) -> int:
    """执行章节审查，生成 review protocol 文件"""
    import json
    import subprocess
    import sys
    from pathlib import Path

    chapter = args.chapter
    project_root = _resolve_root(args.project_root)
    output_file = args.output_file
    output_json = args.json

    if chapter is None:
        print("错误：review 需要 --chapter 参数", file=sys.stderr)
        return 2

    # 调用 anti-ai checker
    anti_ai_args = [
        sys.executable,
        str(Path(__file__).parent.parent / "anti_ai_checker.py"),
        "--chapter", str(chapter),
        "--project-root", str(project_root),
        "--json",
    ]

    proc = subprocess.run(anti_ai_args, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"anti-ai 检查失败: {proc.stderr}", file=sys.stderr)
        return proc.returncode

    try:
        anti_ai_result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(f"anti-ai 输出格式错误: {proc.stdout[:200]}", file=sys.stderr)
        return 2

    # 映射 severity：anti-ai 的 high_risk 映射到 medium/low
    penalty = anti_ai_result.get("penalty", 0)
    high_risk_count = anti_ai_result.get("metrics", {}).get("high_risk_word_count", 0)
    if penalty >= 20:
        severity = "high"
    elif penalty >= 10:
        severity = "medium"
    elif high_risk_count > 0:
        severity = "low"
    else:
        severity = None

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    if severity:
        severity_counts[severity] = high_risk_count

    # 构造 review payload
    review_payload = {
        "overall_score": anti_ai_result.get("overall_score", 0),
        "severity_counts": severity_counts,
        "issues": anti_ai_result.get("issues", []),
        "recommendations": [],
        "summary": anti_ai_result.get("summary", ""),
        "anti_ai": {
            "pass": anti_ai_result.get("pass", False),
            "penalty": penalty,
            "rewrite_required": anti_ai_result.get("rewrite_required", False),
            "rewrite_reason": anti_ai_result.get("rewrite_reason", ""),
            "rewrite_targets": anti_ai_result.get("rewrite_targets", []),
        },
    }

    # 使用 agent_protocol 生成正式协议文件
    from .agent_protocol import serialize_review_payload
    chapter_padded = f"{chapter:04d}"
    protocol_payload = serialize_review_payload(
        review_payload,
        chapter=chapter,
        group="merged",
    )

    # 确定输出路径
    if output_file:
        output_path = Path(output_file)
    else:
        output_path = Path(project_root) / ".webnovel" / "tmp" / "agent_outputs" / f"review_merged_ch{chapter_padded}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 原子写入
    tmp_path = output_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(protocol_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(output_path)

    print(f"审查结果已写入: {output_path}", file=sys.stderr)
    print(f"anti_ai_pass: {protocol_payload['anti_ai']['pass']}", file=sys.stderr)
    print(f"penalty: {protocol_payload['anti_ai']['penalty']}", file=sys.stderr)
    print(f"overall_score: {protocol_payload['overall_score']}", file=sys.stderr)

    if output_json:
        print(json.dumps(protocol_payload, ensure_ascii=False, indent=2))

    return 0


def cmd_review_merge(args: argparse.Namespace) -> int:
    """合并两组审查结果"""
    import json
    from datetime import datetime

    def _as_float(value):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    def _dedupe_append(target, item):
        key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if key not in seen_issue_keys:
            seen_issue_keys.add(key)
            target.append(item)

    def _extract_score(payload):
        candidates = [
            payload.get("overall_score"),
            (payload.get("summary") or {}).get("overall_score") if isinstance(payload.get("summary"), dict) else None,
            (payload.get("综合评分") or {}).get("overall_score") if isinstance(payload.get("综合评分"), dict) else None,
            (payload.get("overall_assessment") or {}).get("overall_score") if isinstance(payload.get("overall_assessment"), dict) else None,
            (payload.get("review_summary") or {}).get("overall_score") if isinstance(payload.get("review_summary"), dict) else None,
        ]
        for candidate in candidates:
            score = _as_float(candidate)
            if score is not None:
                return score
        return None

    def _extract_severity_counts(payload):
        sources = [
            payload.get("severity_counts"),
            (payload.get("summary") or {}),
        ]
        merged = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for source in sources:
            if not isinstance(source, dict):
                continue
            if any(k in source for k in merged):
                for key in merged:
                    merged[key] += int(source.get(key, 0) or 0)
                return merged
            if {"严重违规", "轻微问题"} & set(source.keys()):
                merged["high"] += int(source.get("严重违规", 0) or 0)
                merged["low"] += int(source.get("轻微问题", 0) or 0)
                return merged
        return merged

    def _extract_issues(payload):
        issues = []
        seen_local = set()

        def _append(item):
            key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
            if key in seen_local:
                return
            seen_local.add(key)
            issues.append(item)

        if isinstance(payload.get("issues"), list):
            for item in payload["issues"]:
                _append(item)

        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            nested_issues = value.get("issues")
            if isinstance(nested_issues, list):
                for item in nested_issues:
                    if isinstance(item, dict):
                        enriched = dict(item)
                        enriched.setdefault("checker", key)
                        _append(enriched)
                    else:
                        _append({"checker": key, "message": str(item)})

            if key == "balance_check" and isinstance(value.get("warnings"), list):
                for item in value.get("warnings") or []:
                    _append({"checker": key, "severity": "low", "message": str(item)})

            if key == "overall_assessment" and isinstance(value.get("recommendations"), list):
                for item in value.get("recommendations") or []:
                    _append({"checker": key, "severity": "low", "message": str(item)})

        return issues

    def _extract_dimension_scores(payload):
        dimension_scores = {}
        for key in ("dimension_scores", "dimensions"):
            value = payload.get(key)
            if isinstance(value, dict):
                dimension_scores.update(value)
        return dimension_scores

    group1_path = Path(args.group1)
    group2_path = Path(args.group2)
    output_path = Path(args.output)

    # 读取两个审查组的结果
    with open(group1_path) as f:
        group1 = json.load(f)
    with open(group2_path) as f:
        group2 = json.load(f)

    # 合并 issues / severity / score，兼容不同审查器的输出结构
    merged_issues = []
    seen_issue_keys = set()
    for item in _extract_issues(group1) + _extract_issues(group2):
        _dedupe_append(merged_issues, item)

    merged_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for g in [group1, group2]:
        extracted = _extract_severity_counts(g)
        for k in merged_severity:
            merged_severity[k] += int(extracted.get(k, 0) or 0)

    merged_dimensions = {}
    for g in [group1, group2]:
        merged_dimensions.update(_extract_dimension_scores(g))

    technique_summary = {
        "signals": {},
        "applied": [],
        "failed": [],
    }
    for g in [group1, group2]:
        summary = g.get("technique_execution") or {}
        if not isinstance(summary, dict):
            continue
        for token in summary.get("applied") or []:
            token_text = str(token).strip()
            if token_text and token_text not in technique_summary["applied"]:
                technique_summary["applied"].append(token_text)
        for token in summary.get("failed") or []:
            token_text = str(token).strip()
            if token_text and token_text not in technique_summary["failed"]:
                technique_summary["failed"].append(token_text)
        for key, value in (summary.get("signals") or {}).items():
            technique_summary["signals"][str(key)] = value

    # 计算加权 overall_score：优先用可用分数，避免历史结构不一致导致 0 分
    total_issues = sum(merged_severity.values())
    score_candidates = []
    for g in [group1, group2]:
        score = _extract_score(g)
        if score is not None:
            score_candidates.append(score)

    if score_candidates:
        base_score = sum(score_candidates) / len(score_candidates)
    else:
        base_score = 0.0

    if total_issues > 0:
        # 基于问题严重程度调整分数
        penalty = (
            merged_severity["critical"] * 10
            + merged_severity["high"] * 5
            + merged_severity["medium"] * 2
        )
        if score_candidates:
            overall_score = max(0.0, base_score - penalty / 10)
        else:
            overall_score = max(0.0, 100.0 - penalty)
    else:
        overall_score = base_score

    merged = {
        "version": "1.0",
        "chapter": group1.get("chapter", 0),
        "timestamp": datetime.now().isoformat(),
        "issues": merged_issues,
        "severity_counts": merged_severity,
        "overall_score": round(overall_score, 1),
        "dimension_scores": merged_dimensions,
        "technique_execution": technique_summary,
        "source": {
            "group1": str(group1_path),
            "group2": str(group2_path)
        }
    }
    
    # 写入输出文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    
    print(f"Merged review saved to: {output_path}")
    print(f"Total issues: {total_issues} (critical={merged_severity['critical']}, high={merged_severity['high']}, medium={merged_severity['medium']}, low={merged_severity['low']})")
    print(f"Overall score: {overall_score:.1f}")
    return 0

def cmd_where(args: argparse.Namespace) -> int:
    root = _resolve_root(args.project_root)
    print(str(root))
    return 0


def cmd_batch_query(args: argparse.Namespace) -> int:
    import json
    from .index_manager import IndexManager
    from .config import DataModulesConfig
    from project_locator import resolve_project_root
    
    project_root = _resolve_root(args.project_root)
    config = DataModulesConfig.from_project_root(project_root)
    manager = IndexManager(config)
    
    try:
        queries = json.loads(args.queries)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format: {e}", file=sys.stderr)
        return 1
    
    results = manager.batch_query(queries)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0

def cmd_batch_write(args: argparse.Namespace) -> int:
    import json
    from .index_manager import IndexManager
    from .config import DataModulesConfig
    from project_locator import resolve_project_root

    project_root = _resolve_root(args.project_root)
    config = DataModulesConfig.from_project_root(project_root)
    manager = IndexManager(config)

    try:
        writes = json.loads(args.writes)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format: {e}", file=sys.stderr)
        return 1

    results = manager.batch_write(writes)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0

def _build_preflight_report(explicit_project_root: Optional[str]) -> dict:
    scripts_dir = _scripts_dir().resolve()
    plugin_root = scripts_dir.parent
    skill_root = _find_skill_root(plugin_root)
    entry_script = _find_entry_script(scripts_dir)
    extract_script = scripts_dir / "extract_chapter_context.py"

    checks: list[dict[str, object]] = [
        {"name": "scripts_dir", "ok": scripts_dir.is_dir(), "path": str(scripts_dir)},
        {"name": "entry_script", "ok": entry_script.is_file(), "path": str(entry_script)},
        {"name": "extract_context_script", "ok": extract_script.is_file(), "path": str(extract_script)},
        {"name": "skill_root", "ok": skill_root.is_dir(), "path": str(skill_root)},
    ]

    project_root = ""
    project_root_error = ""
    try:
        resolved_root = _resolve_root(explicit_project_root)
        project_root = str(resolved_root)
        checks.append({"name": "project_root", "ok": True, "path": project_root})
    except Exception as exc:
        project_root_error = str(exc)
        checks.append({"name": "project_root", "ok": False, "path": explicit_project_root or "", "error": project_root_error})

    return {
        "ok": all(bool(item["ok"]) for item in checks),
        "project_root": project_root,
        "scripts_dir": str(scripts_dir),
        "skill_root": str(skill_root),
        "checks": checks,
        "project_root_error": project_root_error,
    }


def cmd_preflight(args: argparse.Namespace) -> int:
    report = _build_preflight_report(args.project_root)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["checks"]:
            status = "OK" if item["ok"] else "ERROR"
            path = item.get("path") or ""
            print(f"{status} {item['name']}: {path}")
            if item.get("error"):
                print(f"  detail: {item['error']}")
    return 0 if report["ok"] else 1


def cmd_use(args: argparse.Namespace) -> int:
    project_root = normalize_windows_path(args.project_root).expanduser()
    try:
        project_root = project_root.resolve()
    except Exception:
        project_root = project_root

    workspace_root: Optional[Path] = None
    if args.workspace_root:
        workspace_root = normalize_windows_path(args.workspace_root).expanduser()
        try:
            workspace_root = workspace_root.resolve()
        except Exception:
            workspace_root = workspace_root

    # 1) 写入工作区指针（若工作区内存在 `.claude/`）
    pointer_file = write_current_project_pointer(project_root, workspace_root=workspace_root)
    if pointer_file is not None:
        print(f"workspace pointer: {pointer_file}")
    else:
        print("workspace pointer: (skipped)")

    # 2) 写入用户级 registry（保证全局安装/空上下文可恢复）
    reg_path = update_global_registry_current_project(workspace_root=workspace_root, project_root=project_root)
    if reg_path is not None:
        print(f"global registry: {reg_path}")
    else:
        print("global registry: (skipped)")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="zhizhang/webnovel unified CLI")
    parser.add_argument("--project-root", help="书项目根目录或工作区根目录（可选，默认自动检测）")

    sub = parser.add_subparsers(dest="tool", required=True)

    p_where = sub.add_parser("where", help="打印解析出的 project_root")
    p_where.set_defaults(func=cmd_where)

    p_preflight = sub.add_parser("preflight", help="校验统一 CLI 运行环境与 project_root")
    p_preflight.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    p_preflight.set_defaults(func=cmd_preflight)

    p_use = sub.add_parser("use", help="绑定当前工作区使用的书项目（写入指针/registry）")
    p_use.add_argument("project_root", help="书项目根目录（必须包含 .webnovel/state.json）")
    p_use.add_argument("--workspace-root", help="工作区根目录（可选；默认由运行环境推断）")
    p_use.set_defaults(func=cmd_use)

    # Pass-through to data modules
    p_index = sub.add_parser("index", help="转发到 index_manager")

    p_batch_query = sub.add_parser("batch-query", help="批量查询接口")
    p_batch_query.add_argument("--queries", required=True, help="JSON 格式的查询列表")
    p_batch_query.set_defaults(func=cmd_batch_query)

    p_batch_write = sub.add_parser("batch-write", help="批量写入接口")
    p_batch_write.add_argument("--writes", required=True, help="JSON 格式的写入列表")
    p_batch_write.set_defaults(func=cmd_batch_write)

    p_index.add_argument("args", nargs=argparse.REMAINDER)

    p_state = sub.add_parser("state", help="转发到 state_manager")
    p_state.add_argument("args", nargs=argparse.REMAINDER)

    p_rag = sub.add_parser("rag", help="转发到 rag_adapter")
    p_rag.add_argument("args", nargs=argparse.REMAINDER)

    p_style = sub.add_parser("style", help="转发到 style_sampler")
    p_style.add_argument("args", nargs=argparse.REMAINDER)

    p_entity = sub.add_parser("entity", help="转发到 entity_linker")
    p_entity.add_argument("args", nargs=argparse.REMAINDER)

    p_context = sub.add_parser("context", help="转发到 context_manager")
    p_context.add_argument("args", nargs=argparse.REMAINDER)

    p_migrate = sub.add_parser("migrate", help="转发到 migrate_state_to_sqlite")
    p_migrate.add_argument("args", nargs=argparse.REMAINDER)

    # Pass-through to scripts
    p_workflow = sub.add_parser("workflow", help="转发到 workflow_manager.py")
    p_workflow.add_argument("args", nargs=argparse.REMAINDER)

    p_status = sub.add_parser("status", help="转发到 status_reporter.py")
    p_status.add_argument("args", nargs=argparse.REMAINDER)

    p_update_state = sub.add_parser("update-state", help="转发到 update_state.py")
    p_update_state.add_argument("args", nargs=argparse.REMAINDER)

    p_backup = sub.add_parser("backup", help="转发到 backup_manager.py")
    p_backup.add_argument("args", nargs=argparse.REMAINDER)

    p_archive = sub.add_parser("archive", help="转发到 archive_manager.py")

    p_review = sub.add_parser("review", help="审查相关工具（支持 anti-AI 质量闸门）")
    p_review.add_argument("--chapter", type=int, required=False, help="目标章节号")
    p_review.add_argument("--type", choices=["anti-ai", "full"], default="anti-ai",
                          help="审查类型：anti-ai 仅去AI味检查，full 全套审查（待实现）")
    p_review.add_argument("--json", action="store_true", help="输出 JSON 格式")
    p_review.add_argument("--output-file", type=str, default=None,
                          help="审查结果输出到指定文件（协议格式）")
    p_review.set_defaults(func=lambda args: 0)  # placeholder, handled below

    p_review_merge = sub.add_parser("merge", parents=[p_review], add_help=False)
    p_review_merge.add_argument("--group1", type=str, required=True, help="第一组审查结果JSON路径")
    p_review_merge.add_argument("--group2", type=str, required=True, help="第二组审查结果JSON路径")
    p_review_merge.add_argument("--output", type=str, required=True, help="合并输出JSON路径")
    p_review_merge.set_defaults(func=cmd_review_merge)
    p_archive.add_argument("args", nargs=argparse.REMAINDER)

    p_init = sub.add_parser("init", help="转发到 init_project.py（初始化项目）")
    p_init.add_argument("args", nargs=argparse.REMAINDER)

    p_extract_context = sub.add_parser("extract-context", help="转发到 extract_chapter_context.py")
    p_extract_context.add_argument("--chapter", type=int, required=True, help="目标章节号")
    p_extract_context.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    p_extract_context.add_argument("--output-file", type=str, default=None, help="输出到指定文件路径（协议输出模式）")

    p_anti_ai = sub.add_parser("anti-ai", help="转发到 anti_ai_checker.py（去AI味检查）")
    p_anti_ai.add_argument("--chapter", type=int, required=False, help="目标章节号")
    p_anti_ai.add_argument("--file", type=str, required=False, help="正文文件路径")
    p_anti_ai.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # v5.23 健康检查
    p_health = sub.add_parser("health", help="转发到 health_checker.py（健康检查）")
    p_health.add_argument("args", nargs=argparse.REMAINDER)

    # v5.23 一致性修复
    p_repair = sub.add_parser("repair", help="转发到 consistency_repair.py（一致性修复）")
    p_repair.add_argument("args", nargs=argparse.REMAINDER)

    # v5.24 读者反馈
    p_feedback = sub.add_parser("feedback", help="转发到 reader_feedback.py（读者反馈）")
    p_feedback.add_argument("args", nargs=argparse.REMAINDER)

    # v5.24 交互式菜单
    p_menu = sub.add_parser("menu", help="启动交互式菜单（导航页与局部工具入口）")

    # 兼容：允许 `--project-root` 出现在任意位置（减少 agents/skills 拼命令的出错率）
    from .cli_args import normalize_global_project_root

    argv = normalize_global_project_root(sys.argv[1:])
    args = parser.parse_args(argv)

    # where/use 直接执行
    if hasattr(args, "func"):
        code = int(args.func(args) or 0)
        raise SystemExit(code)

    tool = args.tool
    rest = list(getattr(args, "args", []) or [])
    # argparse.REMAINDER 可能以 `--` 开头占位，这里去掉
    if rest[:1] == ["--"]:
        rest = rest[1:]
    rest = _strip_project_root_args(rest)

    # init 是创建项目，不应该依赖/注入已存在 project_root
    if tool == "init":
        raise SystemExit(_run_script("init_project.py", rest))

    # 其余工具：统一解析 project_root 后前置给下游
    project_root = _resolve_root(args.project_root)
    forward_args = ["--project-root", str(project_root)]

    if tool == "index":
        if len(rest) > 0 and rest[0] == "batch-query":
            raise SystemExit(cmd_batch_query(args))
        if len(rest) > 0 and rest[0] == "batch-write":
            raise SystemExit(cmd_batch_write(args))
        raise SystemExit(_run_data_module("index_manager", [*forward_args, *rest]))
    elif tool == "batch-query":
        raise SystemExit(cmd_batch_query(args))
    elif tool == "batch-write":
        raise SystemExit(cmd_batch_write(args))
    if tool == "state":
        raise SystemExit(_run_data_module("state_manager", [*forward_args, *rest]))
    if tool == "rag":
        raise SystemExit(_run_data_module("rag_adapter", [*forward_args, *rest]))
    if tool == "style":
        raise SystemExit(_run_data_module("style_sampler", [*forward_args, *rest]))
    if tool == "entity":
        raise SystemExit(_run_data_module("entity_linker", [*forward_args, *rest]))
    if tool == "context":
        raise SystemExit(_run_data_module("context_manager", [*forward_args, *rest]))
    if tool == "migrate":
        raise SystemExit(_run_data_module("migrate_state_to_sqlite", [*forward_args, *rest]))

    if tool == "workflow":
        raise SystemExit(_run_script("workflow_manager.py", [*forward_args, *rest]))
    if tool == "status":
        raise SystemExit(_run_script("status_reporter.py", [*forward_args, *rest]))
    if tool == "update-state":
        raise SystemExit(_run_script("update_state.py", [*forward_args, *rest]))
    if tool == "backup":
        raise SystemExit(_run_script("backup_manager.py", [*forward_args, *rest]))
    if tool == "archive":
        raise SystemExit(_run_script("archive_manager.py", [*forward_args, *rest]))
    if tool == "extract-context":
        return_args = [*forward_args, "--chapter", str(args.chapter), "--format", str(args.format)]
        if args.output_file:
            return_args.extend(["--output-file", str(args.output_file)])
        raise SystemExit(_run_script("extract_chapter_context.py", return_args))
    if tool == "anti-ai":
        anti_ai_args = [*forward_args]
        if args.chapter is not None:
            anti_ai_args.extend(["--chapter", str(args.chapter)])
        if args.file:
            anti_ai_args.extend(["--file", str(args.file)])
        if args.json:
            anti_ai_args.append("--json")
        raise SystemExit(_run_script("anti_ai_checker.py", anti_ai_args))
    if tool == "review":
        if len(rest) > 0 and rest[0] == "merge":
            raise SystemExit(cmd_review_merge(args))
        raise SystemExit(cmd_review(args))

    # v5.23 健康检查
    if tool == "health":
        raise SystemExit(_run_script("health_checker.py", [*forward_args, *rest]))

    # v5.23 一致性修复
    if tool == "repair":
        raise SystemExit(_run_script("consistency_repair.py", [*forward_args, *rest]))

    # v5.24 读者反馈
    if tool == "feedback":
        raise SystemExit(_run_script("reader_feedback.py", [*forward_args, *rest]))

    # v5.24 交互式菜单
    if tool == "menu":
        raise SystemExit(_run_script("menu_interactive.py", [*forward_args]))


    raise SystemExit(2)


if __name__ == "__main__":
    main()
