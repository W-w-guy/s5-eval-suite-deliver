import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
PROMPT = os.path.join(ROOT, "prompts", "judge_prompt_v1.2.0.txt")

import pytest


@pytest.fixture
def prompt_path():
    return PROMPT
