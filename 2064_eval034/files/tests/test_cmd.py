# -*- coding: utf-8 -*-
"""eval-baseline 命令的退出码契约：0 通过 / 1 判定失败 / 2 命令报错。"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cli(*args):
    r = subprocess.run([sys.executable, "-m", "pkg.cmd"] + list(args), cwd=ROOT,
                       capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def test_show_ok():
    rc, out = cli("show")
    assert rc == 0 and "baseline_run: BASE_V1" in out


def test_compare_fail_rc1():
    rc, out = cli("compare", "--run", "CUR_DROP4")
    assert rc == 1 and "FAIL" in out


def test_compare_pass_rc0():
    assert cli("compare", "--run", "CUR_DROP2")[0] == 0


def test_compare_flaky_rc0():
    assert cli("compare", "--run", "CUR_FLAKY")[0] == 0


def test_compare_version_diff_rc0():
    assert cli("compare", "--run", "CUR_VER_DIFF")[0] == 0


def test_compare_missing_run_rc2():
    assert cli("compare", "--run", "NO_SUCH_RUN")[0] == 2


def test_set_failed_run_rc2():
    rc, out = cli("set", "--run", "BASE_FAILED", "--reason", "x",
                  "--permissions", "eval.baseline.set")
    assert rc == 2 and "拒绝设置基线" in out


def test_set_errors_run_rc2():
    rc, _ = cli("set", "--run", "BASE_WITH_ERRORS", "--reason", "x",
                "--permissions", "eval.baseline.set")
    assert rc == 2


def test_set_valid_rc0():
    assert cli("set", "--run", "BASE_V1", "--reason", "首版基线",
               "--permissions", "eval.baseline.set")[0] == 0


def test_set_no_reason_rc2():
    assert cli("set", "--run", "BASE_V1", "--reason", "",
               "--permissions", "eval.baseline.set")[0] == 2


def test_set_no_permission_rc2():
    assert cli("set", "--run", "BASE_V1", "--reason", "x",
               "--permissions", "read")[0] == 2


def test_compare_json_output():
    rc, out = cli("compare", "--run", "CUR_VER_DIFF", "--json")
    assert rc == 0 and '"compared_cases": 113' in out


def test_compare_bad_today_rc2():
    assert cli("compare", "--run", "CUR_DROP2", "--today", "2026/11/27")[0] == 2
