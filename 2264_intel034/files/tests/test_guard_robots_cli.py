# -*- coding: utf-8 -*-
"""AC2（生产配置拒绝启动）、AC3（robots 违规导致退出码非 0）、AC1（报告生成）的测试。"""
import json
import os
import subprocess
import sys

import pytest

from intel_eval import fetch, guard

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOLVER = "gov-a.example=127.0.0.1:8099"


def _run(*args, env=None):
    e = dict(os.environ)
    e.pop(guard.RESOLVER_VAR, None)
    e.pop(guard.ENV_VAR, None)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, "-m", "intel_eval", *args],
                          capture_output=True, cwd=ROOT, text=True,
                          encoding="utf-8", errors="replace", env=e)


# ---------------- AC2：生产 + 解析覆盖 = 拒绝启动 ----------------
def test_guard_rejects_production_with_resolver():
    with pytest.raises(guard.UnsafeConfigError):
        guard.assert_safe_to_start("production", RESOLVER)


@pytest.mark.parametrize("env", ["production", "prod", "live", "release"])
def test_guard_rejects_all_production_aliases(env):
    with pytest.raises(guard.UnsafeConfigError):
        guard.assert_safe_to_start(env, RESOLVER)


@pytest.mark.parametrize("env", ["test", "dev", "staging", "", None])
def test_guard_allows_non_production(env):
    assert guard.assert_safe_to_start(env, RESOLVER) == {"gov-a.example": ("127.0.0.1", 8099)}


def test_guard_rejects_public_ip_in_resolver():
    """解析覆盖只允许指向本机/内网；填公网 IP 等于把内部靶场换成外发请求。"""
    with pytest.raises(guard.UnsafeConfigError):
        guard.resolver_map("gov-a.example=8.8.8.8:80")


def test_cli_refuses_to_start_in_production():
    r = _run("run", "--prompt-set", "should_not_run",
             env={guard.ENV_VAR: "production", guard.RESOLVER_VAR: RESOLVER})
    assert r.returncode == 3, r.returncode
    assert "REFUSE TO START" in r.stderr
    assert not os.path.isfile(os.path.join(ROOT, "reports", "intel_should_not_run.md"))


# ---------------- AC3：robots 违规 -> 退出码非 0 ----------------
def test_cli_ok_with_robots_respected():
    r = _run("run", "--prompt-set", "ci_ok")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "THRESHOLD OK" in r.stdout


def test_cli_nonzero_when_robots_violated():
    r = _run("run", "--prompt-set", "ci_bad", "--ignore-robots")
    assert r.returncode == 1, r.returncode
    assert "robots 禁止路径被抓取数" in r.stdout
    d = json.load(open(os.path.join(ROOT, "reports", "intel_ci_bad.json"), encoding="utf-8"))
    assert d["metrics"]["robots_violations"] >= 1


def test_robots_blocks_disallowed_paths():
    """直接测抓取器：禁止路径不发请求，也不计入抓取。"""
    f = fetch.Fetcher({"gov-a.example": ("127.0.0.1", 8099)})
    from intel_eval.__main__ import _serve_site
    srv = _serve_site(8099)
    try:
        r = f.fetch("http://gov-a.example/admin/settings.html")
        assert r["skipped_by_robots"] is True
        assert r["status"] == 0
        assert f.robots_violations() == 0
        assert f.fetched_count() == 0
        # 允许的路径正常抓到
        ok = f.fetch("http://gov-a.example/articles/a001.html")
        assert ok["status"] == 200
        assert f.fetched_count() == 1
    finally:
        srv.shutdown()


def test_ignore_robots_marks_violation():
    from intel_eval.__main__ import _serve_site
    f = fetch.Fetcher({"gov-a.example": ("127.0.0.1", 8099)}, ignore_robots=True)
    srv = _serve_site(8099)
    try:
        r = f.fetch("http://gov-a.example/admin/settings.html")
        assert r["robots_violation"] is True
        assert f.robots_violations() == 1
    finally:
        srv.shutdown()


# ---------------- AC1：报告齐全 ----------------
def test_report_has_11_metrics():
    r = _run("run", "--prompt-set", "ci_ok")
    assert r.returncode == 0
    md = open(os.path.join(ROOT, "reports", "intel_ci_ok.md"), encoding="utf-8").read()
    assert "11 项指标与门槛" in md
    d = json.load(open(os.path.join(ROOT, "reports", "intel_ci_ok.json"), encoding="utf-8"))
    keys = ["body_similarity", "publish_date_accuracy", "group_f1", "merge_errors",
            "policy_type_accuracy", "deadline_accuracy", "key_fact_coverage",
            "numeric_flagged_ratio", "no_link_into_queue", "robots_violations",
            "urls_in_summary", "pii_residue"]
    for k in keys:
        assert k in d["metrics"], k


def test_compare_subcommand():
    _run("run", "--prompt-set", "cmp_a")
    _run("run", "--prompt-set", "cmp_b")
    r = _run("compare", "--a", "cmp_a", "--b", "cmp_b")
    assert r.returncode == 0, r.stdout + r.stderr
    out = os.path.join(ROOT, "reports", "compare_cmp_a_vs_cmp_b.md")
    assert os.path.isfile(out)
    md = open(out, encoding="utf-8").read()
    assert "提示词版本对比" in md and "差值" in md
