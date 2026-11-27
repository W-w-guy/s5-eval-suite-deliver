# -*- coding: utf-8 -*-
"""AC2 退出码 + AC3 allowlist + AC4 性能。"""
import json
import os
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import allowlist as A   # noqa: E402
import clock           # noqa: E402
import engine          # noqa: E402
import perf            # noqa: E402
import scanner         # noqa: E402

DATA = os.path.join(ROOT, "data")


def cli(*args):
    r = subprocess.run([sys.executable, "-m", "pkg.cmd"] + list(args), cwd=ROOT,
                       capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def tmpfile(text, suffix=".txt"):
    fd, p = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return p


# ---------- AC2：error 非 0 / 只有 warn 为 0 ----------
def test_error_hit_returns_nonzero():
    p = tmpfile("联系电话 %s" % engine.MOBILE_OK)
    try:
        rc, out = cli(p)
        assert rc == 1 and "BLOCK" in out
    finally:
        os.remove(p)


def test_only_warn_returns_zero():
    """只有 warn 级（车牌 / 邮箱 / 固话 / 地址）时退出码必须是 0。"""
    p = tmpfile("车辆 沪A12345 登记，邮箱 qa@example.invalid，前台 010-88880000")
    try:
        rc, out = cli(p)
        assert rc == 0, out[-300:]
        assert "OK" in out
    finally:
        os.remove(p)


def test_clean_returns_zero():
    p = tmpfile("只有编号 KH-2026-0011 与金额 12800 分。")
    try:
        assert cli(p)[0] == 0
    finally:
        os.remove(p)


def test_missing_path_returns_two():
    assert cli(os.path.join(DATA, "no_such_dir"))[0] == 2


def test_fixtures_dir_blocks():
    rc, out = cli(os.path.join(DATA, "fixtures"))
    assert rc == 1 and "阻断项" in out


# ---------- AC3：allowlist ----------
def test_allowlist_load_requires_confirmer_and_date():
    entries, errs = A.load(os.path.join(DATA, "allowlist_bad.yaml"))
    assert entries == [] and errs and "confirmed_by" in errs[0]


def test_allowlist_valid_entries_load():
    entries, errs = A.load(os.path.join(DATA, "allowlist.yaml"))
    assert errs == [] and len(entries) == 1
    assert entries[0]["value"] == "13500000001"
    assert entries[0]["confirmed_by"]


def test_allowlist_removes_entry_from_findings():
    p = tmpfile("联系电话 %s" % engine.MOBILE_OK)
    try:
        before, s1, _ = scanner.scan_path(p)
        after, s2, _ = scanner.scan_path(p, os.path.join(DATA, "allowlist.yaml"))
        assert s1["blocking"] == 1
        assert s2["blocking"] == 0
        assert any(f.get("allowed") for f in after)
    finally:
        os.remove(p)


def test_allowlist_cannot_hide_other_kinds():
    """白名单只放行指定 value，不会连带放行别的命中。"""
    p = tmpfile("联系电话 %s，身份证 %s" % (engine.MOBILE_OK, engine.ID_OK))
    try:
        _f, s, _ = scanner.scan_path(p, os.path.join(DATA, "allowlist.yaml"))
        assert s["blocking"] == 1                # 手机被放行，身份证仍在
    finally:
        os.remove(p)


def test_allowlist_bad_file_returns_two():
    rc, out = cli("--allowlist", os.path.join(DATA, "allowlist_bad.yaml"),
                  os.path.join(DATA, "fixtures"))
    assert rc == 2 and "allowlist 不合法" in out


def test_allowlist_warn_entry_also_filtered():
    """warn 级条目进白名单后也不再出现在报告里。"""
    fd, ap = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        f.write("allowlist:\n  - value: \"沪A12345\"\n    kind: plate\n"
                "    confirmed_by: \"质量负责人\"\n    confirmed_on: \"2026-11-27\"\n")
    p = tmpfile("车辆 沪A12345 登记")
    try:
        _f, s1, _ = scanner.scan_path(p)
        _f2, s2, _ = scanner.scan_path(p, ap)
        assert s1["warnings"] == 1 and s2["warnings"] == 0
    finally:
        os.remove(p)
        os.remove(ap)


# ---------- AC4：1000 条 <= 10 秒 ----------
def test_perf_1000_cases_under_budget():
    """预热后稳态必须远低于 10 秒；同时断言确实扫了 1000 个用例。"""
    r = perf.measure(os.path.join(DATA, "perf1000"))
    assert r["scanned"] == 1000
    assert r["best_ms"] <= 10000, "稳态 %.0f ms 超预算" % r["best_ms"]


def test_perf_cold_start_also_recorded():
    """冷启动也必须记录（不隐瞒首次磁盘/杀软开销）。"""
    r = perf.measure(os.path.join(DATA, "perf1000"), warmup=0, rounds=1)
    assert r["cold_ms"] > 0
    assert r["per_case_ms"] >= 0


def test_perf_jsonl_counts_by_line_not_file():
    """JSONL 计数单位是行（用例），不是文件。"""
    r = perf.measure(os.path.join(DATA, "perf1000"))
    assert r["scanned"] == 1000
    _f, s, _ = scanner.scan_path(os.path.join(DATA, "perf1000"))
    assert s["files"] == 1 and s["scanned"] == 1000


def test_perf_fixture_covers_hit_branch():
    """性能夹具里必须含命中样例，否则测不到最坏情况。"""
    _f, s, _ = scanner.scan_path(os.path.join(DATA, "perf1000"))
    assert s["blocking"] > 0
