# -*- coding: utf-8 -*-
"""通用用例：示例逐条比对 CSV 期望值（引擎重算 == 已交付期望值）。"""
import csv
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pkg"))
import engine as E  # noqa: E402

SPEC = json.load(open(os.path.join(ROOT, "spec.json"), encoding="utf-8"))
CSV_PATH = os.path.join(ROOT, "docs", SPEC["csv"])
KEYS = [k for k in SPEC["cols"] if k.startswith("expected_")]


def load():
    return {r[SPEC["id_col"]]: r for r in csv.DictReader(open(CSV_PATH, encoding="utf-8"))}


def test_row_count():
    assert len(load()) == len(E.CASES)


@pytest.mark.parametrize("case", E.CASES, ids=[E.case_id(c) for c in E.CASES])
def test_case_matches_csv(case):
    exp = load()[E.case_id(case)]
    row = E.row_of(case)
    for k in KEYS:
        assert str(row[k]) == str(exp[k]), k
