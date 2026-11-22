# -*- coding: utf-8 -*-
"""薄壳：真正的实现已移到 guardrail/lint.py（便于测试 import，避免 tools 目录当包用）。

用法不变：python tools/lint.py 2047
"""
import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from guardrail.lint import main
if __name__ == "__main__":
    sys.exit(main())
