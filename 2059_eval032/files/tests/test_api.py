# -*- coding: utf-8 -*-
"""接口层：登记、筛选、PATCH 规则、月度导出。需要真 PostgreSQL。"""
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

BASE = "/api/eval/redteam-findings"


def _items(client, hdr, **params):
    r = client.get(BASE, headers=hdr, params=params)
    assert r.status_code == 200, r.text
    return r.json()["items"]


def _by_no(client, hdr, no):
    return [x for x in _items(client, hdr) if x["finding_no"] == no][0]


# ---------- 登记 ----------
def test_create_requires_write_permission(client, hdr_eng, seeds):
    r = client.post(BASE, headers={}, json={"title": "x"})
    assert r.status_code == 403
    assert S.PERM_WRITE in r.json()["detail"]


def test_create_requires_fields(client, hdr):
    r = client.post(BASE, headers=hdr, json={"title": "只有标题"})
    assert r.status_code == 422
    assert "缺少必填字段" in r.json()["detail"]


def test_create_rejects_bad_severity(client, hdr):
    r = client.post(BASE, headers=hdr, json={
        "title": "x", "tool": "kb_answer", "technique": "y",
        "severity": "P9", "repro_steps": "s", "evidence": "e", "owner_role": "r"})
    assert r.status_code == 422


def test_create_numbers_findings_incrementally(client, hdr, seeds):
    body = {"title": "新发现", "tool": "kb_answer", "technique": "jailbreak",
            "severity": "P1", "repro_steps": "1) 2) 3)",
            "evidence": "证据文本", "owner_role": "评测工程师",
            "found_at": "2026-11-26"}
    r1 = client.post(BASE, headers=hdr, json=body)
    assert r1.status_code == 201, r1.text
    r2 = client.post(BASE, headers=hdr, json=dict(body, title="新发现 2"))
    assert r2.status_code == 201
    n1, n2 = r1.json()["finding_no"], r2.json()["finding_no"]
    assert n1.startswith("RT-2026-") and n2.startswith("RT-2026-")
    assert int(n2.rsplit("-", 1)[1]) == int(n1.rsplit("-", 1)[1]) + 1


# ---------- AC3：evidence 入库后已掩码 ----------
def test_evidence_masked_in_db_not_just_response(client, hdr, seeds):
    """断言直接查库，不查请求体 —— 请求体里还是原文。"""
    canary = seeds["canary"]
    plain = "金丝雀 %s 电话 13500000001 邮箱 qa@owner.example.invalid" % canary
    r = client.post(BASE, headers=hdr, json={
        "title": "带敏感信息的发现", "tool": "kb_answer", "technique": "leak",
        "severity": "P1", "repro_steps": "1) 2)", "evidence": plain,
        "owner_role": "评测工程师", "canary": canary, "found_at": "2026-11-26"})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]

    from pkg.db import get_session
    from pkg.models import RedteamFinding
    with get_session() as sess:
        row = sess.get(RedteamFinding, fid)
        stored = row.evidence
    assert canary not in stored, "金丝雀必须已被掩码"
    assert "13500000001" not in stored
    assert "135****0001" in stored
    assert redact.leak_of_canary(stored, canary) is False


def test_evidence_masked_on_patch_too(client, hdr, seeds):
    canary = seeds["canary"]
    r = client.post(BASE, headers=hdr, json={
        "title": "补证据", "tool": "kb_answer", "technique": "leak",
        "severity": "P2", "repro_steps": "1)", "evidence": "初始",
        "owner_role": "评测工程师", "found_at": "2026-11-26"})
    fid = r.json()["id"]
    r2 = client.patch("%s/%s" % (BASE, fid), headers=hdr,
                      json={"evidence": "后续补充：金丝雀 %s" % canary})
    assert r2.status_code == 200, r2.text
    assert canary not in r2.json()["evidence"]


# ---------- AC2：P0 改为 wont_fix 返回 422 ----------
def test_p0_to_wont_fix_returns_422(client, hdr, seeds):
    p0 = _by_no(client, hdr, "RT-2026-001")
    assert p0["severity"] == "P0" and p0["status"] == "confirmed"
    r = client.patch("%s/%s" % (BASE, p0["id"]), headers=hdr,
                     json={"status": "wont_fix", "wont_fix_reason": "可以不修"})
    assert r.status_code == 422, r.text
    assert "P0" in r.json()["detail"]


def test_p2_to_wont_fix_allowed_with_approver(client, hdr, seeds):
    """正向对照：P2 + 安全负责人 + 理由 -> 允许。"""
    r = client.post(BASE, headers=hdr, json={
        "title": "低危可忽略", "tool": "copy_draft", "technique": "tone",
        "severity": "P2", "repro_steps": "1)", "evidence": "e",
        "owner_role": "评测工程师", "found_at": "2026-11-26"})
    fid = r.json()["id"]
    client.patch("%s/%s" % (BASE, fid), headers=hdr,
                 json={"status": "confirmed", "confirmed_at": "2026-11-26"})
    r2 = client.patch("%s/%s" % (BASE, fid), headers=hdr,
                      json={"status": "wont_fix", "wont_fix_reason": "影响面极低"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "wont_fix"


def test_wont_fix_without_approve_permission_is_403(client, hdr, hdr_eng, seeds):
    """自建一条 confirmed 的 P2，不依赖种子状态（否则会 skip，而 skip 不算通过）。"""
    r0 = client.post(BASE, headers=hdr, json={
        "title": "无审批权限测试用", "tool": "copy_draft", "technique": "tone",
        "severity": "P2", "repro_steps": "1)", "evidence": "e",
        "owner_role": "evaluation_engineer", "found_at": "2026-11-26"})
    fid = r0.json()["id"]
    client.patch("%s/%s" % (BASE, fid), headers=hdr,
                 json={"status": "confirmed", "confirmed_at": "2026-11-26"})
    r = client.patch("%s/%s" % (BASE, fid), headers=hdr_eng,
                     json={"status": "wont_fix", "wont_fix_reason": "想直接关"})
    assert r.status_code == 403
    assert S.PERM_APPROVE in r.json()["detail"]


# ---------- AC1：overdue ----------
def test_overdue_false_on_deadline_day(client, hdr, seeds):
    items = _items(client, hdr, today="2026-11-27")
    p0 = [x for x in items if x["finding_no"] == "RT-2026-001"][0]
    assert p0["confirmed_at"] == "2026-11-25"
    assert p0["overdue"] is False


def test_overdue_true_after_deadline(client, hdr, seeds):
    items = _items(client, hdr, today="2026-11-28")
    p0 = [x for x in items if x["finding_no"] == "RT-2026-001"][0]
    assert p0["overdue"] is True


def test_has_regression_case_not_overdue(client, hdr, seeds):
    items = _items(client, hdr, today="2026-12-31")
    with_case = [x for x in items if x["finding_no"] == "RT-2026-002"][0]
    assert with_case["regression_case_key"] == "KB-INJ-0007"
    assert with_case["overdue"] is False


def test_linking_regression_case_clears_overdue(client, hdr, seeds):
    """用自建 finding 而不是动种子 —— 改动种子会污染后续的 job_scan 断言
    （第一版就是给 RT-2026-001 关联了用例，导致后面的定时任务测试查不到它）。"""
    r0 = client.post(BASE, headers=hdr, json={
        "title": "待关联回归用例的发现", "tool": "kb_answer", "technique": "t",
        "severity": "P1", "repro_steps": "1)", "evidence": "e",
        "owner_role": "evaluation_engineer", "found_at": "2026-11-20"})
    fid = r0.json()["id"]
    client.patch("%s/%s" % (BASE, fid), headers=hdr,
                 json={"status": "confirmed", "confirmed_at": "2026-11-20"})
    items = _items(client, hdr, today="2026-11-30")
    mine = [x for x in items if x["id"] == fid][0]
    assert mine["overdue"] is True
    r = client.patch("%s/%s" % (BASE, fid), headers=hdr,
                     json={"regression_case_key": "KB-INJ-0099", "today": "2026-11-30"})
    assert r.status_code == 200, r.text
    assert r.json()["overdue"] is False


# ---------- 定时任务 ----------
def test_job_scan_reports_overdue(client, hdr, db, seeds):
    from pkg import jobs
    r = jobs.scan(org_id=seeds["org"], today="2026-11-28", write_snapshot=False)
    nos = [x["finding_no"] for x in r["items"]]
    assert "RT-2026-001" in nos
    assert "RT-2026-002" not in nos        # 已关联回归用例
    assert r["overdue_count"] == len(r["items"])


def test_job_scan_empty_on_deadline_day(db, seeds):
    from pkg import jobs
    r = jobs.scan(org_id=seeds["org"], today="2026-11-27", write_snapshot=False)
    assert all(x["finding_no"] != "RT-2026-001" for x in r["items"])


# ---------- AC4：月度导出三组 ----------
def test_monthly_returns_three_groups(client, hdr, seeds):
    r = client.get("%s/monthly" % BASE, headers=hdr, params={"month": "2026-11"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"created", "fixed", "open", "counts"}
    assert body["counts"]["created"] == len(body["created"])
    assert body["counts"]["fixed"] == len(body["fixed"])
    assert body["counts"]["open"] == len(body["open"])


def test_monthly_created_includes_found_in_month(client, hdr, seeds):
    body = client.get("%s/monthly" % BASE, headers=hdr,
                      params={"month": "2026-11"}).json()
    nos = {x["finding_no"] for x in body["created"]}
    assert "RT-2026-004" in nos      # found_at 2026-11-20


def test_monthly_fixed_includes_fixed_at_in_month(client, hdr, seeds):
    body = client.get("%s/monthly" % BASE, headers=hdr,
                      params={"month": "2026-11"}).json()
    nos = {x["finding_no"] for x in body["fixed"]}
    assert "RT-2026-003" in nos      # fixed_at 2026-11-14


def test_monthly_open_excludes_verified_and_wontfix(client, hdr, seeds):
    body = client.get("%s/monthly" % BASE, headers=hdr,
                      params={"month": "2026-11"}).json()
    nos = {x["finding_no"] for x in body["open"]}
    assert "RT-2026-005" not in nos   # verified
    assert "RT-2026-006" not in nos   # wont_fix


def test_monthly_bad_month_format_is_422(client, hdr, seeds):
    r = client.get("%s/monthly" % BASE, headers=hdr, params={"month": "2026/11"})
    assert r.status_code == 422


# ---------- 筛选 ----------
def test_filter_by_severity(client, hdr, seeds):
    items = _items(client, hdr, severity="P0")
    assert items and all(x["severity"] == "P0" for x in items)


def test_filter_by_tool(client, hdr, seeds):
    items = _items(client, hdr, tool="kb_answer")
    assert items and all(x["tool"] == "kb_answer" for x in items)


def test_filter_by_status(client, hdr, seeds):
    items = _items(client, hdr, status="fixed")
    assert items and all(x["status"] == "fixed" for x in items)


# ---------- OpenAPI ----------
def test_openapi_describes_all_endpoints(client, db):
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert BASE in paths
    assert any(p.startswith(BASE + "/{") for p in paths)
    assert BASE + "/monthly" in paths
    methods = {m for p in paths.values() for m in p}
    assert methods >= {"get", "post", "patch"}
