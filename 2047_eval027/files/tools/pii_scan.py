# -*- coding: utf-8 -*-
"""薄壳：真正的实现已移到 guardrail/pii_scan.py。用法不变：python tools/pii_scan.py"""
import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from guardrail.pii_scan import main
if __name__ == "__main__":
    sys.exit(main())
