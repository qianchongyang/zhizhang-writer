#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OutlineWindowParser - Parse volume outlines into structured activity window nodes.

This module extracts structured chapter nodes from volume detailed outline files
(第X卷-详细大纲.md), providing a higher-level interface than raw text slicing.

Usage:
    nodes = parse_volume_outline_nodes(volume_outline_path, volume_num)
    node = find_chapter_node(nodes, chapter_num)
    if node:
        print(f"Chapter {node.chapter}: {node.title}")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class OutlineNode:
    """
    结构化章节节点 - 从卷详细大纲解析出的单章大纲单元

    Attributes:
        chapter: 章节号
        title: 章节标题
        goal: 目标 (goal)
        conflict: 冲突/阻力 (conflict)
        action: 动作/行动 (action)
        result: 结果/产出 (result)
        cost: 代价 (cost)
        hook: 钩子/悬念 (hook)
        strand: Strand 类型 (quest/fire/constellation)
        state_changes: 状态变化列表
        raw_text: 原始 Markdown 文本
        source_file: 来源文件路径
    """
    chapter: int
    title: str = ""
    goal: str = ""
    conflict: str = ""
    action: str = ""
    result: str = ""
    cost: str = ""
    hook: str = ""
    strand: str = ""  # "quest" | "fire" | "constellation" | ""
    state_changes: List[str] = field(default_factory=list)
    raw_text: str = ""
    source_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutlineNode":
        """从字典创建实例"""
        return cls(
            chapter=int(data.get("chapter", 0)),
            title=str(data.get("title", "")),
            goal=str(data.get("goal", "")),
            conflict=str(data.get("conflict", "")),
            action=str(data.get("action", "")),
            result=str(data.get("result", "")),
            cost=str(data.get("cost", "")),
            hook=str(data.get("hook", "")),
            strand=str(data.get("strand", "")),
            state_changes=list(data.get("state_changes", [])),
            raw_text=str(data.get("raw_text", "")),
            source_file=str(data.get("source_file", "")),
        )

    def to_runtime_dict(self) -> Dict[str, Any]:
        """转换为运行时层格式 (outline_runtime.json)"""
        return {
            "chapter": self.chapter,
            "title": self.title,
            "goal": self.goal,
            "conflict": self.conflict,
            "action": self.action,
            "result": self.result,
            "cost": self.cost,
            "hook": self.hook,
            "strand": self.strand,
            "state_changes": self.state_changes,
        }

    @classmethod
    def from_runtime_dict(cls, data: Dict[str, Any]) -> "OutlineNode":
        """从运行时层格式创建实例"""
        return cls(
            chapter=int(data.get("chapter", 0)),
            title=str(data.get("title", "")),
            goal=str(data.get("goal", "")),
            conflict=str(data.get("conflict", "")),
            action=str(data.get("action", "")),
            result=str(data.get("result", "")),
            cost=str(data.get("cost", "")),
            hook=str(data.get("hook", "")),
            strand=str(data.get("strand", "")),
            state_changes=list(data.get("state_changes", [])),
            raw_text="",
            source_file="",
        )

    @property
    def is_complete(self) -> bool:
        """检查节点是否包含完整的章节契约字段"""
        required_fields = [self.goal, self.conflict, self.action, self.result, self.cost, self.hook]
        return all(field.strip() for field in required_fields)

    @property
    def contract_text(self) -> str:
        """生成符合旧接口格式的章节契约文本"""
        lines = [f"### 第{self.chapter}章：{self.title}"]
        if self.goal:
            lines.append(f"目标：{self.goal}")
        if self.conflict:
            lines.append(f"冲突：{self.conflict}")
        if self.action:
            lines.append(f"动作：{self.action}")
        if self.result:
            lines.append(f"结果：{self.result}")
        if self.cost:
            lines.append(f"代价：{self.cost}")
        if self.hook:
            lines.append(f"钩子：{self.hook}")
        if self.strand:
            lines.append(f"Strand：{self.strand}")
        return "\n".join(lines)


@dataclass
class OutlineParseError:
    """解析错误结构"""
    chapter: int
    error_type: str  # "missing_title" | "parse_failed" | "invalid_format"
    message: str
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OutlineWindow:
    """
    活动窗口 - 从卷详细大纲解析出的完整窗口结构

    Attributes:
        volume_num: 卷号
        nodes: 章节节点列表
        errors: 解析错误列表
        source_file: 来源文件路径
        node_count: 节点总数
        valid_count: 有效节点数
    """
    volume_num: int
    nodes: List[OutlineNode] = field(default_factory=list)
    errors: List[OutlineParseError] = field(default_factory=list)
    source_file: str = ""

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def valid_count(self) -> int:
        return sum(1 for node in self.nodes if node.is_complete)

    def get_node(self, chapter: int) -> Optional[OutlineNode]:
        """根据章节号查找节点"""
        for node in self.nodes:
            if node.chapter == chapter:
                return node
        return None

    def to_runtime_dict(self) -> Dict[str, Any]:
        """转换为运行时层格式"""
        return {
            "volume": self.volume_num,
            "nodes": [node.to_runtime_dict() for node in self.nodes],
            "source_file": self.source_file,
        }


# =============================================================================
# Parsing Constants
# =============================================================================

_CHAPTER_TITLE_RE = re.compile(
    r"^###\s*第\s*(\d+)\s*章\s*[：:]\s*(.+)$",
    re.MULTILINE
)

_CONTRACT_FIELD_PATTERNS = {
    "goal": re.compile(r"^[-*\s]*(?:目标|目的)\s*[：:]\s*(.+)$", re.MULTILINE),
    "conflict": re.compile(r"^[-*\s]*(?:冲突|阻力|对手)\s*[：:]\s*(.+)$", re.MULTILINE),
    "action": re.compile(r"^[-*\s]*(?:动作|行动|计划)\s*[：:]\s*(.+)$", re.MULTILINE),
    "result": re.compile(r"^[-*\s]*(?:结果|产出|变化)\s*[：:]\s*(.+)$", re.MULTILINE),
    "cost": re.compile(r"^[-*\s]*(?:代价|损失|牺牲)\s*[：:]\s*(.+)$", re.MULTILINE),
    "hook": re.compile(r"^[-*\s]*(?:钩子|悬念|未解|反问)\s*[：:]\s*(.+)$", re.MULTILINE),
    "strand": re.compile(r"^[-*\s]*(?:Strand|strand|主线|感情线|世界观)\s*[：:]\s*(.+)$", re.MULTILINE),
}

_STATE_CHANGE_KEYWORDS = (
    "提升", "下降", "获得", "失去", "突破", "暴露", "结盟", "破裂",
    "离开", "到达", "转移", "受伤", "升级", "进入", "退出", "成功", "失败",
)


# =============================================================================
# Core Parsing Functions
# =============================================================================

def parse_chapter_section(section_text: str, default_chapter: int = 0) -> tuple[Optional[OutlineNode], Optional[OutlineParseError]]:
    """
    解析单个章节段落文本为 OutlineNode

    Args:
        section_text: 章节段落原始文本
        default_chapter: 默认章节号（当无法从标题提取时使用）

    Returns:
        (OutlineNode, None) 如果解析成功
        (None, OutlineParseError) 如果解析失败
    """
    # 提取章节号和标题
    title_match = _CHAPTER_TITLE_RE.search(section_text)
    if not title_match:
        # 尝试从 ### 标题行提取章节号
        alt_match = re.search(r"^###\s*第\s*(\d+)\s*章", section_text, re.MULTILINE)
        if alt_match:
            chapter = int(alt_match.group(1))
            # 提取标题后续内容
            title_line = re.search(r"^###\s*第\s*\d+\s*章[：:]\s*(.+)$", section_text, re.MULTILINE)
            title = title_line.group(1).strip() if title_line else ""
        else:
            return None, OutlineParseError(
                chapter=default_chapter,
                error_type="missing_title",
                message="无法从章节标题提取章节号和标题",
                raw_text=section_text[:200],
            )
    else:
        chapter = int(title_match.group(1))
        title = title_match.group(2).strip()

    # 提取各字段
    node_dict: Dict[str, str] = {
        "chapter": chapter,
        "title": title,
        "goal": "",
        "conflict": "",
        "action": "",
        "result": "",
        "cost": "",
        "hook": "",
        "strand": "",
        "state_changes": [],
        "raw_text": section_text,
    }

    for field_name, pattern in _CONTRACT_FIELD_PATTERNS.items():
        match = pattern.search(section_text)
        if match:
            node_dict[field_name] = match.group(1).strip()

    # 提取状态变化关键词
    state_changes: List[str] = []
    for keyword in _STATE_CHANGE_KEYWORDS:
        if keyword in section_text:
            state_changes.append(keyword)
    node_dict["state_changes"] = state_changes

    # 创建节点
    node = OutlineNode(**node_dict)
    return node, None


def split_volume_outline_sections(content: str) -> List[tuple[int, str]]:
    """
    将卷详细大纲内容分割为单个章节段落

    Returns:
        [(chapter_num, section_text), ...] 列表
    """
    sections: List[tuple[int, str]] = []

    # 使用正则表达式分割章节
    # 匹配 "### 第N章：标题" 作为新章节的开始
    pattern = r"(?=^###\s*第\s*\d+\s*章[：:])"

    # 分割文本
    parts = re.split(pattern, content, flags=re.MULTILINE)
    parts = [p.strip() for p in parts if p.strip()]

    for part in parts:
        # 提取章节号
        match = re.search(r"第\s*(\d+)\s*章", part)
        if match:
            chapter = int(match.group(1))
            sections.append((chapter, part))

    return sections


def parse_volume_outline_content(
    content: str,
    volume_num: int,
    source_file: str = "",
) -> OutlineWindow:
    """
    解析卷详细大纲的完整内容

    Args:
        content: 卷详细大纲的原始文本内容
        volume_num: 卷号
        source_file: 来源文件路径（用于错误报告）

    Returns:
        OutlineWindow 对象，包含所有解析出的节点和错误
    """
    window = OutlineWindow(volume_num=volume_num, source_file=source_file)

    # 分割章节段落
    sections = split_volume_outline_sections(content)

    for chapter, section_text in sections:
        node, error = parse_chapter_section(section_text, default_chapter=chapter)
        if node:
            node.source_file = source_file
            window.nodes.append(node)
        elif error:
            error.source_file = source_file
            window.errors.append(error)

    # 按章节号排序
    window.nodes.sort(key=lambda n: n.chapter)

    return window


def parse_volume_outline_file(
    file_path: Union[str, Path],
    volume_num: Optional[int] = None,
) -> OutlineWindow:
    """
    解析卷详细大纲文件

    Args:
        file_path: 卷详细大纲文件路径
        volume_num: 卷号（如果为None，则从文件名自动提取）

    Returns:
        OutlineWindow 对象

    Raises:
        FileNotFoundError: 如果文件不存在
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"卷详细大纲文件不存在: {file_path}")

    content = path.read_text(encoding="utf-8")

    # 从文件名提取卷号
    if volume_num is None:
        match = re.search(r"第\s*(\d+)\s*卷", path.name)
        if match:
            volume_num = int(match.group(1))
        else:
            volume_num = 0

    return parse_volume_outline_content(content, volume_num, source_file=str(path))


def find_chapter_node(
    nodes: List[OutlineNode],
    chapter: int,
) -> Optional[OutlineNode]:
    """
    在节点列表中查找指定章节的节点

    Args:
        nodes: OutlineNode 列表
        chapter: 要查找的章节号

    Returns:
        找到的 OutlineNode 或 None
    """
    for node in nodes:
        if node.chapter == chapter:
            return node
    return None


def load_volume_outline_window(
    project_root: Path,
    volume_num: int,
) -> Optional[OutlineWindow]:
    """
    加载指定卷的活动窗口

    Args:
        project_root: 项目根目录
        volume_num: 卷号

    Returns:
        OutlineWindow 对象，如果文件不存在则返回 None
    """
    outline_dir = project_root / "大纲"
    candidates = [
        outline_dir / f"第{volume_num}卷-详细大纲.md",
        outline_dir / f"第{volume_num}卷 - 详细大纲.md",
        outline_dir / f"第{volume_num}卷 详细大纲.md",
    ]

    for candidate in candidates:
        if candidate.exists():
            return parse_volume_outline_file(candidate, volume_num)

    return None


def load_chapter_outline_node(
    project_root: Path,
    chapter: int,
) -> tuple[Optional[OutlineNode], str]:
    """
    加载单个章节的 OutlineNode

    First tries to load from runtime layer (outline_runtime.json),
    then falls back to parsing from volume outline.

    Args:
        project_root: 项目根目录
        chapter: 章节号

    Returns:
        (OutlineNode, source) 如果找到
        (None, error_message) 如果未找到
    """
    # 1. 首先尝试从 outline_runtime.json 加载（运行时层）
    runtime_path = project_root / ".webnovel" / "outline_runtime.json"
    if runtime_path.exists():
        try:
            runtime_data = json.loads(runtime_path.read_text(encoding="utf-8"))
            nodes_data = runtime_data.get("nodes", [])
            for node_data in nodes_data:
                if int(node_data.get("chapter", 0)) == chapter:
                    node = OutlineNode.from_runtime_dict(node_data)
                    node.source_file = str(runtime_path)
                    return node, "runtime"
        except (json.JSONDecodeError, KeyError):
            pass

    # 2. 回退到卷详细大纲解析
    # 尝试确定章节所属的卷
    from chapter_outline_loader import volume_num_for_chapter_from_state, volume_num_for_chapter

    vol_num = volume_num_for_chapter_from_state(project_root, chapter)
    if vol_num is None:
        vol_num = volume_num_for_chapter(chapter)

    window = load_volume_outline_window(project_root, vol_num)
    if window is None:
        return None, f"未找到大纲文件"

    node = window.get_node(chapter)
    if node is None:
        return None, f"未找到第{chapter}章大纲"

    return node, "volume"


# =============================================================================
# Runtime Layer Utilities
# =============================================================================

def load_outline_runtime(project_root: Path) -> Optional[Dict[str, Any]]:
    """
    加载 outline_runtime.json 运行时层数据

    Args:
        project_root: 项目根目录

    Returns:
        运行时层数据字典，如果不存在则返回 None
    """
    runtime_path = project_root / ".webnovel" / "outline_runtime.json"
    if not runtime_path.exists():
        return None

    try:
        return json.loads(runtime_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_outline_runtime(
    project_root: Path,
    window: OutlineWindow,
) -> None:
    """
    保存活动窗口到 outline_runtime.json

    Args:
        project_root: 项目根目录
        window: OutlineWindow 对象
    """
    runtime_path = project_root / ".webnovel" / "outline_runtime.json"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)

    data = window.to_runtime_dict()
    runtime_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_active_window_node(
    project_root: Path,
    chapter: int,
) -> tuple[Optional[OutlineNode], str]:
    """
    获取当前活动窗口中的章节节点（优先从运行时层）

    这是 ContextManager 写前优先调用的接口。

    Args:
        project_root: 项目根目录
        chapter: 章节号

    Returns:
        (OutlineNode, source) 如果找到，source 可能是 "runtime" 或 "volume"
        (None, error_message) 如果未找到
    """
    return load_chapter_outline_node(project_root, chapter)


# =============================================================================
# Validation Utilities
# =============================================================================

def validate_outline_node(node: OutlineNode) -> List[str]:
    """
    验证节点是否满足章节契约要求

    Args:
        node: OutlineNode 对象

    Returns:
        缺失字段列表，如果为空则表示验证通过
    """
    missing: List[str] = []

    if not node.goal.strip():
        missing.append("目标")
    if not node.conflict.strip():
        missing.append("冲突")
    if not node.action.strip():
        missing.append("动作")
    if not node.result.strip():
        missing.append("结果")
    if not node.cost.strip():
        missing.append("代价")
    if not node.hook.strip():
        missing.append("钩子")

    return missing


def node_to_outline_text(node: OutlineNode) -> str:
    """
    将 OutlineNode 转换回旧接口格式的文本（用于兼容）

    Args:
        node: OutlineNode 对象

    Returns:
        符合旧接口格式的大纲文本
    """
    return node.contract_text


# =============================================================================
# Factory Functions
# =============================================================================

def create_outline_window_from_nodes(
    nodes: List[OutlineNode],
    volume_num: int,
    source_file: str = "",
) -> OutlineWindow:
    """
    从节点列表创建 OutlineWindow

    Args:
        nodes: OutlineNode 列表
        volume_num: 卷号
        source_file: 来源文件路径

    Returns:
        OutlineWindow 对象
    """
    return OutlineWindow(
        volume_num=volume_num,
        nodes=nodes,
        errors=[],
        source_file=source_file,
    )
