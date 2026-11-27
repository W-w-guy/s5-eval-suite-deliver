# -*- coding: utf-8 -*-
"""测试夹具：每个 session 干净建库（DROP SCHEMA + Alembic），并灌入种子数据。

★ 不在 teardown 里 drop_all：pytest 子进程结束会把父进程依赖的库对象搞乱，
  而每次 session 开始都 reset_schema（自带 DROP SCHEMA IF EXISTS），本身就是幂等的。
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pkg"))

import redact          # noqa: E402
import state as S      # noqa: E402
import workdays as W   # noqa: E402


def _seeds():
    return json.load(open(os.path.join(ROOT, "data", "seeds.json"), encoding="utf-8"))


@pytest.fixture(scope="session")
def seeds():
    return _seeds()


@pytest.fixture(scope="session")
def db():
    """整库重置 + 灌种子。scope=session，避免每个用例重复迁移。"""
    from pkg.db import get_session, reset_schema
    from pkg.models import RedteamFinding
    reset_schema()

    s = _seeds()
    with get_session() as sess:
        y = "2026"
        for i, seed in enumerate(s["seeds"], 1):
            masked, _hits = redact.redact(seed["evidence"])
            sess.add(RedteamFinding(
                finding_no="RT-%s-%03d" % (y, i), title=seed["title"],
                tool=seed["tool"], technique=seed["technique"],
                severity=seed["severity"], status=seed["status"],
                repro_steps="步骤：1) 构造输入 2) 观察输出 3) 记录差异",
                evidence=masked, evidence_canary=seed["canary"],
                owner_role=seed["owner_role"], found_at=seed["found_at"],
                confirmed_at=seed.get("confirmed_at"),
                fixed_at=seed.get("fixed_at"),
                verified_run_id=seed.get("verified_run_id"),
                regression_case_key=seed.get("regression_case_key"),
                wont_fix_reason=seed.get("wont_fix_reason"),
                approved_by_role=seed.get("approved_by_role"),
                org_id=s["org"], created_by=s["operator"],
            ))
    return True


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient
    from pkg.api import app
    return TestClient(app)


@pytest.fixture()
def hdr(seeds):
    """写权限 + 安全负责人角色。"""
    return {"X-Permissions": "%s,%s" % (S.PERM_WRITE, S.PERM_APPROVE),
            "X-Role": seeds["roles"]["sec"],
            "X-Operator": "tester.sec",
            "X-Org": seeds["org"]}


@pytest.fixture()
def hdr_eng(seeds):
    """只有写权限、角色是评测工程师（不能审批）。"""
    return {"X-Permissions": S.PERM_WRITE,
            "X-Role": seeds["roles"]["eng"],
            "X-Operator": "tester.eng",
            "X-Org": seeds["org"]}
