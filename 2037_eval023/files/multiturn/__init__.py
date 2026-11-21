# -*- coding: utf-8 -*-
"""{TITLE}（#2037）

本包由 deliver_kit 生成。约定：
  · 交付件全部离线可跑，不依赖网络与第三方库（除明确声明的）
  · `python -m multiturn` 是唯一入口，退出码 0=全达标 / 1=有指标未达标 / 2=环境不可用
  · 指标口径写死在 metrics.py，不要在 runner 里另算一套
"""
__version__ = "0.1.0"
PROBLEM_ID = 2037
