#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for outline_window_parser module

验证活动窗口节点解析功能。
"""

import json
import pytest
from pathlib import Path


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_volume_outline_content():
    """标准卷详细大纲内容"""
    return """# 第1卷 详细大纲

## 卷首语
本卷讲述主角在宗门中的成长历程。

### 第1章：觉醒测试
目标：确认主角资质低下
冲突：家族长老的轻视
动作：参加觉醒仪式
结果：意外触发金手指
代价：消耗家族资源
钩子：仪式背后暗藏玄机
Strand：quest

### 第2章：初入宗门
目标：拜入外门
冲突：资质不足被刁难
动作：用金手指展示潜力
结果：获得长老关注，破例收入门下
代价：暴露部分实力，引来嫉妒
钩子：宗门内部有派系争斗
Strand：quest

### 第3章：宗门小比
目标：在宗门小比中取得名次
冲突：对手暗中使绊子
动作：正面迎战+金手指辅助
结果：获胜但被质疑使用禁术
代价：被执法堂调查
钩子：调查背后有更大阴谋
Strand：quest

### 第5章：秘境探索
目标：探索上古秘境
冲突：秘境中有守护兽
动作：组队进入
结果：获得秘境传承
代价：队友受伤，需要闭关
钩子：传承中隐藏着更大秘密
Strand：constellation
"""


@pytest.fixture
def incomplete_volume_outline_content():
    """不完整的卷大纲（缺少章节4）"""
    return """# 第2卷 详细大纲

### 第10章：新的开始
目标：离开宗门游历
冲突：路上遇到劫匪
动作：击败劫匪
结果：获得劫匪藏宝图
代价：引来更多麻烦
钩子：藏宝图指向未知之地

### 第11章：遗迹探险
目标：探索古遗迹
冲突：遗迹中有机关陷阱
动作：谨慎探索
结果：触发机关
代价：受伤
钩子：遗迹深处有神秘存在

### 第15章：回归宗门
目标：返回宗门
冲突：宗门发生大变
动作：调查真相
结果：发现宗门被渗透
代价：身份暴露
钩子：幕后黑手是谁？
"""


@pytest.fixture
def minimal_outline_content():
    """只有标题的章节大纲"""
    return """# 第3卷 详细大纲

### 第20章：开始
这是一个只有标题的章节

### 第21章：继续
目标：继续推进
冲突：阻力
动作：行动
结果：结果
代价：代价
钩子：悬念
"""


# =============================================================================
# Test: OutlineNode Dataclass
# =============================================================================

def test_outline_node_to_dict():
    """测试 OutlineNode.to_dict() 方法"""
    from data_modules.outline_window_parser import OutlineNode

    node = OutlineNode(
        chapter=1,
        title="测试章节",
        goal="测试目标",
        conflict="测试冲突",
        action="测试动作",
        result="测试结果",
        cost="测试代价",
        hook="测试钩子",
        strand="quest",
        state_changes=["突破", "升级"],
        raw_text="原始文本",
        source_file="test.md",
    )

    result = node.to_dict()

    assert result["chapter"] == 1
    assert result["title"] == "测试章节"
    assert result["goal"] == "测试目标"
    assert result["strand"] == "quest"
    assert result["state_changes"] == ["突破", "升级"]


def test_outline_node_from_dict():
    """测试 OutlineNode.from_dict() 方法"""
    from data_modules.outline_window_parser import OutlineNode

    data = {
        "chapter": 2,
        "title": "from_dict测试",
        "goal": "目标",
        "conflict": "冲突",
        "action": "动作",
        "result": "结果",
        "cost": "代价",
        "hook": "钩子",
        "strand": "fire",
        "state_changes": ["获得"],
        "raw_text": "",
        "source_file": "",
    }

    node = OutlineNode.from_dict(data)

    assert node.chapter == 2
    assert node.title == "from_dict测试"
    assert node.strand == "fire"
    assert node.state_changes == ["获得"]


def test_outline_node_is_complete():
    """测试 OutlineNode.is_complete 属性"""
    from data_modules.outline_window_parser import OutlineNode

    # 完整节点
    complete_node = OutlineNode(
        chapter=1,
        title="完整节点",
        goal="目标",
        conflict="冲突",
        action="动作",
        result="结果",
        cost="代价",
        hook="钩子",
    )
    assert complete_node.is_complete is True

    # 不完整节点（缺少 goal）
    incomplete_node = OutlineNode(
        chapter=2,
        title="不完整节点",
        goal="",
        conflict="冲突",
        action="动作",
        result="结果",
        cost="代价",
        hook="钩子",
    )
    assert incomplete_node.is_complete is False


def test_outline_node_contract_text():
    """测试 OutlineNode.contract_text 属性"""
    from data_modules.outline_window_parser import OutlineNode

    node = OutlineNode(
        chapter=1,
        title="测试章节",
        goal="测试目标",
        conflict="测试冲突",
        action="测试动作",
        result="测试结果",
        cost="测试代价",
        hook="测试钩子",
        strand="quest",
    )

    text = node.contract_text

    assert "### 第1章：测试章节" in text
    assert "目标：测试目标" in text
    assert "冲突：测试冲突" in text
    assert "Strand：quest" in text


def test_outline_node_to_runtime_dict():
    """测试 OutlineNode.to_runtime_dict() 方法"""
    from data_modules.outline_window_parser import OutlineNode

    node = OutlineNode(
        chapter=1,
        title="运行时测试",
        goal="目标",
        conflict="冲突",
        action="动作",
        result="结果",
        cost="代价",
        hook="钩子",
        strand="quest",
        state_changes=["突破"],
        raw_text="原始文本",
        source_file="test.md",
    )

    runtime = node.to_runtime_dict()

    assert "raw_text" not in runtime  # 运行时格式不包含 raw_text
    assert "source_file" not in runtime
    assert runtime["chapter"] == 1
    assert runtime["goal"] == "目标"


# =============================================================================
# Test: OutlineWindow Dataclass
# =============================================================================

def test_outline_window_properties(sample_volume_outline_content):
    """测试 OutlineWindow 的属性"""
    from data_modules.outline_window_parser import (
        parse_volume_outline_content,
        OutlineWindow,
    )

    window = parse_volume_outline_content(sample_volume_outline_content, volume_num=1)

    assert window.volume_num == 1
    assert window.node_count == 4
    assert window.valid_count == 4  # 所有节点都是完整的


def test_outline_window_get_node(sample_volume_outline_content):
    """测试 OutlineWindow.get_node() 方法"""
    from data_modules.outline_window_parser import parse_volume_outline_content

    window = parse_volume_outline_content(sample_volume_outline_content, volume_num=1)

    node = window.get_node(1)
    assert node is not None
    assert node.chapter == 1
    assert node.title == "觉醒测试"

    missing_node = window.get_node(99)
    assert missing_node is None


def test_outline_window_get_node_with_missing_chapter(incomplete_volume_outline_content):
    """测试 OutlineWindow.get_node() 方法处理缺失章节"""
    from data_modules.outline_window_parser import parse_volume_outline_content

    window = parse_volume_outline_content(incomplete_volume_outline_content, volume_num=2)

    # 章节 10, 11, 15 存在
    assert window.get_node(10) is not None
    assert window.get_node(11) is not None
    assert window.get_node(15) is not None

    # 章节 12, 13, 14 不存在
    assert window.get_node(12) is None
    assert window.get_node(13) is None
    assert window.get_node(14) is None


def test_outline_window_to_runtime_dict(sample_volume_outline_content):
    """测试 OutlineWindow.to_runtime_dict() 方法"""
    from data_modules.outline_window_parser import parse_volume_outline_content

    window = parse_volume_outline_content(sample_volume_outline_content, volume_num=1)

    runtime = window.to_runtime_dict()

    assert runtime["volume"] == 1
    assert len(runtime["nodes"]) == 4
    assert runtime["nodes"][0]["chapter"] == 1


# =============================================================================
# Test: Parsing Functions
# =============================================================================

def test_parse_chapter_section_valid():
    """测试 parse_chapter_section 解析有效章节"""
    from data_modules.outline_window_parser import parse_chapter_section

    section = """### 第1章：测试标题
目标：测试目标
冲突：测试冲突
动作：测试动作
结果：测试结果
代价：测试代价
钩子：测试钩子
Strand：quest
"""

    node, error = parse_chapter_section(section)

    assert error is None
    assert node is not None
    assert node.chapter == 1
    assert node.title == "测试标题"
    assert node.goal == "测试目标"
    assert node.strand == "quest"


def test_parse_chapter_section_extracts_state_changes():
    """测试 parse_chapter_section 提取状态变化"""
    from data_modules.outline_window_parser import parse_chapter_section

    section = """### 第2章：状态变化测试
目标：获得突破
冲突：遭遇强敌
动作：苦战
结果：成功突破
代价：受伤
钩子：突破后实力大增
"""

    node, error = parse_chapter_section(section)

    assert error is None
    assert node is not None
    assert "突破" in node.state_changes
    assert "受伤" in node.state_changes


def test_parse_chapter_section_missing_title():
    """测试 parse_chapter_section 处理缺失标题的情况"""
    from data_modules.outline_window_parser import parse_chapter_section

    section = """这是一个没有章节标题的文本
目标：目标
"""

    node, error = parse_chapter_section(section)

    assert node is None
    assert error is not None
    assert error.error_type == "missing_title"


def test_split_volume_outline_sections(sample_volume_outline_content):
    """测试 split_volume_outline_sections 函数"""
    from data_modules.outline_window_parser import split_volume_outline_sections

    sections = split_volume_outline_sections(sample_volume_outline_content)

    assert len(sections) == 4
    assert sections[0][0] == 1  # chapter number
    assert sections[1][0] == 2
    assert sections[2][0] == 3
    assert sections[3][0] == 5  # 注意：第4章缺失


def test_parse_volume_outline_content(sample_volume_outline_content):
    """测试 parse_volume_outline_content 函数"""
    from data_modules.outline_window_parser import parse_volume_outline_content

    window = parse_volume_outline_content(sample_volume_outline_content, volume_num=1)

    assert window.volume_num == 1
    assert window.node_count == 4
    assert window.errors == []  # 不应有错误

    # 验证节点顺序
    assert window.nodes[0].chapter == 1
    assert window.nodes[1].chapter == 2
    assert window.nodes[2].chapter == 3
    assert window.nodes[3].chapter == 5


def test_parse_volume_outline_content_with_missing_chapters(incomplete_volume_outline_content):
    """测试 parse_volume_outline_content 处理缺失章节"""
    from data_modules.outline_window_parser import parse_volume_outline_content

    window = parse_volume_outline_content(incomplete_volume_outline_content, volume_num=2)

    assert window.volume_num == 2
    assert window.node_count == 3  # 只有 10, 11, 15
    assert window.errors == []  # 不应有错误


def test_parse_volume_outline_file(tmp_path, sample_volume_outline_content):
    """测试 parse_volume_outline_file 函数"""
    from data_modules.outline_window_parser import parse_volume_outline_file

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    outline_file = outline_dir / "第1卷-详细大纲.md"
    outline_file.write_text(sample_volume_outline_content, encoding="utf-8")

    window = parse_volume_outline_file(outline_file)

    assert window.volume_num == 1
    assert window.node_count == 4


def test_parse_volume_outline_file_not_found(tmp_path):
    """测试 parse_volume_outline_file 处理文件不存在"""
    from data_modules.outline_window_parser import parse_volume_outline_file

    with pytest.raises(FileNotFoundError):
        parse_volume_outline_file(tmp_path / "不存在的文件.md")


# =============================================================================
# Test: find_chapter_node
# =============================================================================

def test_find_chapter_node():
    """测试 find_chapter_node 函数"""
    from data_modules.outline_window_parser import (
        OutlineNode,
        find_chapter_node,
    )

    nodes = [
        OutlineNode(chapter=1, title="第1章"),
        OutlineNode(chapter=2, title="第2章"),
        OutlineNode(chapter=5, title="第5章"),
    ]

    found = find_chapter_node(nodes, 2)
    assert found is not None
    assert found.chapter == 2

    not_found = find_chapter_node(nodes, 99)
    assert not_found is None


# =============================================================================
# Test: load_volume_outline_window
# =============================================================================

def test_load_volume_outline_window(tmp_path, sample_volume_outline_content):
    """测试 load_volume_outline_window 函数"""
    from data_modules.outline_window_parser import load_volume_outline_window

    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷-详细大纲.md").write_text(sample_volume_outline_content, encoding="utf-8")

    window = load_volume_outline_window(tmp_path, 1)

    assert window is not None
    assert window.node_count == 4


def test_load_volume_outline_window_not_found(tmp_path):
    """测试 load_volume_outline_window 处理文件不存在"""
    from data_modules.outline_window_parser import load_volume_outline_window

    window = load_volume_outline_window(tmp_path, 99)

    assert window is None


# =============================================================================
# Test: load_chapter_outline_node
# =============================================================================

def test_load_chapter_outline_node_from_runtime(tmp_path):
    """测试 load_chapter_outline_node 从运行时层加载"""
    from data_modules.outline_window_parser import load_chapter_outline_node

    # 创建 .webnovel 目录和 outline_runtime.json
    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = webnovel_dir / "outline_runtime.json"
    runtime_file.write_text(
        json.dumps({
            "volume": 1,
            "nodes": [
                {"chapter": 1, "title": "运行时章节", "goal": "运行时目标"}
            ]
        }, ensure_ascii=False),
        encoding="utf-8"
    )

    node, source = load_chapter_outline_node(tmp_path, 1)

    assert node is not None
    assert source == "runtime"
    assert node.chapter == 1
    assert node.title == "运行时章节"


def test_load_chapter_outline_node_from_volume(tmp_path, sample_volume_outline_content):
    """测试 load_chapter_outline_node 从卷大纲加载"""
    from data_modules.outline_window_parser import load_chapter_outline_node

    # 不创建 outline_runtime.json，直接创建卷大纲
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷-详细大纲.md").write_text(sample_volume_outline_content, encoding="utf-8")

    node, source = load_chapter_outline_node(tmp_path, 1)

    assert node is not None
    assert source == "volume"
    assert node.chapter == 1
    assert node.title == "觉醒测试"


def test_load_chapter_outline_node_not_found(tmp_path):
    """测试 load_chapter_outline_node 处理章节不存在"""
    from data_modules.outline_window_parser import load_chapter_outline_node

    # 创建空的卷大纲
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷-详细大纲.md").write_text("# 第1卷 详细大纲\n", encoding="utf-8")

    node, source = load_chapter_outline_node(tmp_path, 999)

    assert node is None
    assert "未找到" in source


# =============================================================================
# Test: Runtime Layer Utilities
# =============================================================================

def test_load_outline_runtime_exists(tmp_path):
    """测试 load_outline_runtime 检测存在"""
    from data_modules.outline_window_parser import load_outline_runtime

    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = webnovel_dir / "outline_runtime.json"
    runtime_file.write_text(
        json.dumps({"volume": 1, "nodes": []}),
        encoding="utf-8"
    )

    result = load_outline_runtime(tmp_path)

    assert result is not None
    assert result["volume"] == 1


def test_load_outline_runtime_not_exists(tmp_path):
    """测试 load_outline_runtime 检测不存在"""
    from data_modules.outline_window_parser import load_outline_runtime

    result = load_outline_runtime(tmp_path)

    assert result is None


def test_save_and_load_outline_runtime(tmp_path, sample_volume_outline_content):
    """测试 save_outline_runtime 和 load_outline_runtime 配对使用"""
    from data_modules.outline_window_parser import (
        parse_volume_outline_content,
        save_outline_runtime,
        load_outline_runtime,
    )

    # 解析大纲
    window = parse_volume_outline_content(sample_volume_outline_content, volume_num=1)

    # 保存到运行时层
    save_outline_runtime(tmp_path, window)

    # 重新加载
    loaded = load_outline_runtime(tmp_path)

    assert loaded is not None
    assert loaded["volume"] == 1
    assert len(loaded["nodes"]) == 4


# =============================================================================
# Test: Validation Utilities
# =============================================================================

def test_validate_outline_node_complete():
    """测试 validate_outline_node 验证完整节点"""
    from data_modules.outline_window_parser import (
        OutlineNode,
        validate_outline_node,
    )

    complete_node = OutlineNode(
        chapter=1,
        title="完整节点",
        goal="目标",
        conflict="冲突",
        action="动作",
        result="结果",
        cost="代价",
        hook="钩子",
    )

    missing = validate_outline_node(complete_node)

    assert missing == []


def test_validate_outline_node_incomplete():
    """测试 validate_outline_node 验证不完整节点"""
    from data_modules.outline_window_parser import (
        OutlineNode,
        validate_outline_node,
    )

    incomplete_node = OutlineNode(
        chapter=1,
        title="不完整节点",
        goal="目标",
        conflict="",  # 缺少冲突
        action="动作",
        result="结果",
        cost="代价",
        hook="钩子",
    )

    missing = validate_outline_node(incomplete_node)

    assert "冲突" in missing


def test_node_to_outline_text():
    """测试 node_to_outline_text 函数"""
    from data_modules.outline_window_parser import (
        OutlineNode,
        node_to_outline_text,
    )

    node = OutlineNode(
        chapter=1,
        title="转换测试",
        goal="目标",
        conflict="冲突",
        action="动作",
        result="结果",
        cost="代价",
        hook="钩子",
    )

    text = node_to_outline_text(node)

    assert "### 第1章：转换测试" in text
    assert "目标：目标" in text
    assert "冲突：冲突" in text


# =============================================================================
# Test: get_active_window_node
# =============================================================================

def test_get_active_window_node_prefers_runtime(tmp_path):
    """测试 get_active_window_node 优先使用运行时层"""
    from data_modules.outline_window_parser import get_active_window_node

    # 创建 .webnovel 目录和 outline_runtime.json
    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = webnovel_dir / "outline_runtime.json"
    runtime_file.write_text(
        json.dumps({
            "volume": 1,
            "nodes": [
                {"chapter": 1, "title": "运行时节点", "goal": "运行时目标"}
            ]
        }, ensure_ascii=False),
        encoding="utf-8"
    )

    # 同时创建卷大纲（但运行时层应该被优先使用）
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷-详细大纲.md").write_text(
        "### 第1章：卷大纲节点\n目标：卷目标\n冲突：卷冲突\n动作：卷动作\n结果：卷结果\n代价：卷代价\n钩子：卷钩子",
        encoding="utf-8"
    )

    node, source = get_active_window_node(tmp_path, 1)

    assert node is not None
    assert source == "runtime"
    assert node.title == "运行时节点"


# =============================================================================
# Test: Error Handling
# =============================================================================

def test_parse_volume_outline_handles_empty_content():
    """测试 parse_volume_outline_content 处理空内容"""
    from data_modules.outline_window_parser import parse_volume_outline_content

    window = parse_volume_outline_content("", volume_num=1)

    assert window.node_count == 0
    assert window.errors == []


def test_parse_volume_outline_handles_only_headers():
    """测试 parse_volume_outline_content 处理只有标题的情况"""
    from data_modules.outline_window_parser import parse_volume_outline_content

    content = """# 第1卷 详细大纲

## 卷首语
这是一个卷首语。

### 第1章：只有标题
"""

    window = parse_volume_outline_content(content, volume_num=1)

    assert window.node_count == 1
    # 第1章节点存在但不完整
    node = window.get_node(1)
    assert node is not None
    assert node.title == "只有标题"


# =============================================================================
# Test: Edge Cases
# =============================================================================

def test_chapter_number_extraction_variants():
    """测试章节号提取的各种变体"""
    from data_modules.outline_window_parser import parse_chapter_section

    variants = [
        ("### 第1章：标准格式", 1),
        ("### 第12章：两位数", 12),
        ("### 第 3 章：带空格", 3),
        ("### 第123章：多数字", 123),
    ]

    for text, expected_chapter in variants:
        section = f"{text}\n目标：目标\n冲突：冲突\n动作：动作\n结果：结果\n代价：代价\n钩子：钩子"
        node, error = parse_chapter_section(section)
        assert error is None, f"Failed to parse: {text}"
        assert node.chapter == expected_chapter, f"Expected {expected_chapter}, got {node.chapter}"


def test_strand_extraction_variants():
    """测试 Strand 字段的各种变体"""
    from data_modules.outline_window_parser import parse_chapter_section

    variants = [
        ("Strand：quest", "quest"),
        ("Strand：fire", "fire"),
        ("Strand：constellation", "constellation"),
        ("strand：fire", "fire"),
        ("主线：quest", "quest"),
        ("感情线：fire", "fire"),
        ("世界观：constellation", "constellation"),
    ]

    for text, expected_strand in variants:
        section = f"### 第1章：Strand测试\n目标：目标\n{text}\n冲突：冲突\n动作：动作\n结果：结果\n代价：代价\n钩子：钩子"
        node, error = parse_chapter_section(section)
        assert error is None, f"Failed to parse: {text}"
        assert node.strand == expected_strand, f"Expected {expected_strand}, got {node.strand}"
