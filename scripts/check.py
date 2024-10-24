#!/usr/bin/env python
"""
使用ruff进行格式检查，如果通过了再使用mypy检查类型注解
这两个都检查通过了，再用bandit检查代码安全性

注：只检查，不修改代码。如需格式化代码，可用./scripts/format.py

Usage::
    ./scripts/check.py

或Pycharm中右键直接运行
"""

import os
import sys

CMD = "fast check"
TOOL = ("poetry", "pdm", "")[0]
parent = os.path.abspath(os.path.dirname(__file__))
work_dir = os.path.dirname(parent)
if os.getcwd() != work_dir:
    os.chdir(work_dir)

cmd = "{} run {}".format(TOOL, CMD) if TOOL else CMD
if os.system(cmd) != 0:
    print("\033[1m Please run './scripts/format.py' to auto-fix style issues \033[0m")
    sys.exit(1)

if "--bandit" in sys.argv:
    package_name = os.path.basename(work_dir).replace("-", "_")
    cmd = "{}bandit -r {}".format(TOOL and f"{TOOL} run ", package_name)
    print("-->", cmd)
    if os.system(cmd) != 0:
        sys.exit(1)
print("Done.")
