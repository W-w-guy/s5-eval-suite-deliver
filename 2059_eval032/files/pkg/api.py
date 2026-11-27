# -*- coding: utf-8 -*-
"""红队发现登记与跟踪接口。

权限从请求头取（由 S2-IAM 注入，本单用桩）：
  X-Permissions: 逗号分隔的权限串
  X-Role: 当前用户角色
  X-Operator: 当前操作人（用于审计与「审批人不能是最后编辑人」这类判断）
"""
import json
import os
import sys
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, select

import redact
import state as S
import workdays as W
from pkg.db import get_session
from pkg.models import RedteamFinding

app = FastAPI(title="Redteam Findings API", version="1.0.0")

DEFAULT_ORG = "org-demo"


def _ctx(request):
    perms = [p.strip() for p in (request.headers.get("X-Permissions") or "").split(",") if p.strip()]
    return {"perms": perms, "role": request.headers.get("X-Role"),
            "operator": request.headers.get("X-Operator"),
            "org_id": request.headers.get("X-Org") or DEFAULT_ORG}


def _err(code, detail, status):
    raise HTTPException(status_code=status, detail=detail)


def _row_to_dict(r, today=None):
    has_case = bool(r.regression_case_key)
    d = {
        "id": str(r.id), "finding_no": r.finding_no, "title": r.title,
        "tool": r.tool, "technique": r.technique, "severity": r.severity,
        "status": r.status, "repro_steps": r.repro_steps,
        "evidence": r.evidence, "owner_role": r.owner_role,
        "found_at": str(r.found_at), "confirmed_at": str(r.confirmed_at) if r.confirmed_at else None,
        "fixed_at": str(r.fixed_at) if r.fixed_at else None,
        "verified_run_id": r.verified_run_id,
        "regression_case_key": r.regression_case_key,
        "wont_fix_reason": r.wont_fix_reason,
        "approved_by_role": r.approved_by_role,
    }
    if today and r.status == "confirmed":
        d["overdue"] = W.is_overdue(
            str(r.confirmed_at) if r.confirmed_at else None, today, has_case)
    else:
        d["overdue"] = False
    return d


def _next_finding_no(sess, org_id, year):
    prefix = "RT-%d-" % year
    rows = sess.execute(
        select(RedteamFinding.finding_no).where(
            and_(RedteamFinding.org_id == org_id,
                 RedteamFinding.finding_no.like(prefix + "%")))
    ).scalars().all()
    nums = []
    for no in rows:
        try:
            nums.append(int(no.rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return prefix + "%03d" % (max(nums) + 1 if nums else 1)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/api/eval/redteam-findings", status_code=201)
async def create_finding(request: Request):
    ctx = _ctx(request)
    try:
        S.check_permission(ctx["perms"], S.PERM_WRITE)
    except PermissionError as e:
        _err(403, str(e), 403)
    body = await request.json()

    need = ("title", "tool", "technique", "severity", "repro_steps", "evidence", "owner_role")
    miss = [k for k in need if not str(body.get(k) or "").strip()]
    if miss:
        _err(422, "缺少必填字段 %s" % miss, 422)
    if body["severity"] not in S.SEVERITIES:
        _err(422, "severity 只能是 %s" % (S.SEVERITIES,), 422)

    # AC3：evidence 入库前掩码
    masked, hits = redact.mask_or_raise("evidence", body["evidence"])
    canary = body.get("canary")

    org = ctx["org_id"]
    year = int(str(body.get("found_at") or W.clock.BASE_TODAY)[:4])
    with get_session() as sess:
        no = _next_finding_no(sess, org, year)
        r = RedteamFinding(
            finding_no=no, title=body["title"], tool=body["tool"],
            technique=body["technique"], severity=body["severity"],
            status="new", repro_steps=body["repro_steps"], evidence=masked,
            evidence_canary=canary, owner_role=body["owner_role"],
            found_at=body.get("found_at") or W.clock.BASE_TODAY,
            org_id=org, site_id=body.get("site_id"),
            created_by=ctx["operator"] or "unknown",
        )
        sess.add(r)
        sess.flush()
        out = _row_to_dict(r)
    out["redacted_rules"] = hits
    return out


@app.get("/api/eval/redteam-findings")
def list_findings(request: Request, tool: str | None = None,
                  severity: str | None = None, status: str | None = None,
                  today: str | None = None):
    ctx = _ctx(request)
    today = today or W.clock.BASE_TODAY
    with get_session() as sess:
        q = select(RedteamFinding).where(RedteamFinding.org_id == ctx["org_id"],
                                         RedteamFinding.deleted_at.is_(None))
        if tool:
            q = q.where(RedteamFinding.tool == tool)
        if severity:
            q = q.where(RedteamFinding.severity == severity)
        if status:
            q = q.where(RedteamFinding.status == status)
        rows = sess.execute(q.order_by(RedteamFinding.finding_no)).scalars().all()
        return {"items": [_row_to_dict(r, today) for r in rows], "total": len(rows),
                "today": today}


@app.patch("/api/eval/redteam-findings/{finding_id}")
async def patch_finding(finding_id: str, request: Request):
    ctx = _ctx(request)
    try:
        S.check_permission(ctx["perms"], S.PERM_WRITE)
    except PermissionError as e:
        _err(403, str(e), 403)
    body = await request.json()

    with get_session() as sess:
        r = sess.get(RedteamFinding, finding_id)
        if r is None or r.org_id != ctx["org_id"] or r.deleted_at is not None:
            _err(404, "发现不存在", 404)
        cur = r.status
        nxt = body.get("status") or cur
        # 只有显式给了 status 才走状态机校验。
        # 只改 evidence / regression_case_key 这类字段时不算状态迁移 ——
        # 第一版无条件调 check_transition，导致「补证据」「关联回归用例」
        # 这两种纯字段更新被判成「状态未变化」而 422。
        if "status" in body:
            try:
                S.check_transition(cur, nxt)
            except S.RuleError as e:
                _err(422, str(e), 422)

        if nxt == "wont_fix":
            # AC2：P0 改为 wont_fix 返回 422
            try:
                S.check_permission(ctx["perms"], S.PERM_APPROVE)
            except PermissionError as e:
                _err(403, str(e), 403)
            try:
                S.check_wont_fix({"severity": r.severity}, body.get("wont_fix_reason"),
                                 ctx["role"])
            except S.RuleError as e:
                _err(422, str(e), 422)
            r.wont_fix_reason = body["wont_fix_reason"]
            r.approved_by_role = ctx["role"]

        if nxt == "verified":
            try:
                S.check_verified({"status": cur}, body.get("verified_run_id"),
                                 body.get("trigger") or "manual")
            except S.RuleError as e:
                _err(422, str(e), 422)
            r.verified_run_id = body["verified_run_id"]

        if nxt == "confirmed" and not r.confirmed_at:
            r.confirmed_at = body.get("confirmed_at") or W.clock.BASE_TODAY
        if nxt == "fixed":
            r.fixed_at = body.get("fixed_at") or W.clock.BASE_TODAY
        if "regression_case_key" in body:
            r.regression_case_key = body["regression_case_key"]
        if "evidence" in body:
            r.evidence, _h = redact.mask_or_raise("evidence", body["evidence"])
        r.status = nxt
        sess.flush()
        return _row_to_dict(r, body.get("today") or W.clock.BASE_TODAY)


@app.get("/api/eval/redteam-findings/monthly")
def monthly(request: Request, month: str = Query(pattern=r"^\d{4}-\d{2}$")):
    """AC4：返回新增、已修复、未关闭三组数据。"""
    ctx = _ctx(request)
    y, m = month.split("-")
    start = "%s-%s-01" % (y, m)
    if int(m) == 12:
        nxt = "%d-01-01" % (int(y) + 1)
    else:
        nxt = "%s-%02d-01" % (y, int(m) + 1)

    with get_session() as sess:
        base = select(RedteamFinding).where(
            RedteamFinding.org_id == ctx["org_id"],
            RedteamFinding.deleted_at.is_(None))
        rows = sess.execute(base).scalars().all()

    def in_month(d):
        return d is not None and start <= str(d) < nxt

    created = [r for r in rows if in_month(r.found_at)]
    fixed = [r for r in rows if in_month(r.fixed_at)]
    open_ = [r for r in rows if start <= str(r.found_at) < nxt
             and r.status not in ("verified", "wont_fix")]
    return {"month": month,
            "created": [_row_to_dict(r) for r in created],
            "fixed": [_row_to_dict(r) for r in fixed],
            "open": [_row_to_dict(r) for r in open_],
            "counts": {"created": len(created), "fixed": len(fixed), "open": len(open_)}}


@app.get("/openapi.json", include_in_schema=False)
def openapi_override():
    spec = app.openapi()
    return JSONResponse(spec)
