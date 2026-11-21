# -*- coding: utf-8 -*-
"""端到端：分布、字数、指标达标、三个破坏方向各自触发对应检查。"""
import json
import os
import subprocess
import sys

import ip_eval.__main__ as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_dataset_shape():
    cs = R.load_cases()
    assert len(cs) == 30
    from collections import Counter
    c = Counter(x["kind"] for x in cs)
    assert c == {"outline": 12, "summary": 18}, c


def test_transcript_length_in_range():
    """AC3：18 份转写稿字数均在 3000–6000 字之间。"""
    cs = [c for c in R.load_cases() if c["kind"] == "summary"]
    assert len(cs) == 18
    lens = [c["char_count"] for c in cs]
    assert all(3000 <= x <= 6000 for x in lens), (min(lens), max(lens))
    # 还要真的覆盖分布，不是全挤在端点
    assert max(lens) - min(lens) > 1500, (min(lens), max(lens))


def test_transcript_files_exist_and_match_count():
    for c in R.load_cases():
        if c["kind"] != "summary":
            continue
        text = R.read_transcript(c)
        assert abs(len(text) - c["char_count"]) <= 2, (c["case_id"], len(text), c["char_count"])


def test_summary_boundary_program_is_derived():
    """AC4：程序化检查通过 -> 全达标。"""
    rows = [R.evaluate_case(c) for c in R.load_cases()]
    m = R.aggregate(rows)
    assert m["pass_rate"] == 1.0, m["fails"][:1]
    assert m["summary_pass_rate"] == 1.0
    assert m["outline_pass_rate"] == 1.0


def test_break_quote_triggers_quote_check():
    cs = R.load_cases()
    rows = [R.evaluate_case(c, break_quote=True) for c in cs]
    bad = [r for r in rows if not r["ok"]]
    assert bad
    assert any("金句" in r["reason"] for r in bad)


def test_break_timestamp_triggers_ts_check():
    cs = R.load_cases()
    rows = [R.evaluate_case(c, break_timestamp=True) for c in cs]
    bad = [r for r in rows if not r["ok"]]
    assert bad
    assert any("时间戳" in r["reason"] for r in bad)


def test_break_number_triggers_number_check():
    cs = R.load_cases()
    rows = [R.evaluate_case(c, break_number=True) for c in cs]
    bad = [r for r in rows if not r["ok"]]
    assert bad
    assert any("数字" in r["reason"] for r in bad)


def test_report_has_three_checks():
    cs = R.load_cases()
    rows = [R.evaluate_case(c) for c in cs]
    m = R.aggregate(rows)
    md = os.path.join(ROOT, "reports", "ip_test.md")
    R.write_report(m, rows, md, md[:-3] + ".json")
    t = open(md, encoding="utf-8").read()
    for kw in ("金句逐字", "时间戳单调", "摘要数字有据", "未通过明细"):
        assert kw in t, kw


def test_cli_ok_and_breaks():
    def _cli(*a):
        return subprocess.run([sys.executable, "-m", "ip_eval", *a], capture_output=True,
                              cwd=ROOT, text=True, encoding="utf-8", errors="replace")
    assert _cli().returncode == 0
    assert _cli("--break-quote", "--tag", "ci1").returncode == 1
    assert _cli("--break-timestamp", "--tag", "ci2").returncode == 1
    assert _cli("--break-number", "--tag", "ci3").returncode == 1
