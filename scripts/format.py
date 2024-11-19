#!/usr/bin/env python
"""
使用ruff格式化代码，并删除未使用的imports

Usage:
    ./scripts/format.py
或Pycharm中右键执行
"""

import os
import sys

CMD = "fast lint --skip-mypy"
TOOL = ("poetry", "pdm", "uv", "")[0]

parent = os.path.abspath(os.path.dirname(__file__))
work_dir = os.path.dirname(parent)
if os.getcwd() != work_dir:
    os.chdir(work_dir)  # 确保位于项目根目录（pyproject.toml所在目录）

# 带工具前缀，以便未激活虚拟环境时，也能执行该脚本
cmd = (TOOL and f"{TOOL} run ") + CMD
if os.system(cmd) != 0:
    sys.exit(1)
