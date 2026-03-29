#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zhizhang 统一入口脚本。

这是 `webnovel.py` 的新命名兼容层，便于对外文档和新品牌命名统一。
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from runtime_compat import enable_windows_utf8_stdio
except ImportError:
    from scripts.runtime_compat import enable_windows_utf8_stdio


def main() -> None:
    scripts_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts_dir))

    from data_modules.zhizhang import main as _main

    _main()


if __name__ == "__main__":
    enable_windows_utf8_stdio(skip_in_pytest=True)
    main()
