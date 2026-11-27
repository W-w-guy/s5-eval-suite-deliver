# -*- coding: utf-8 -*-
"""三个接口 + 权限校验。用接口桩代替 S2-IAM（工单允许）。"""
from __future__ import annotations
import os
import uuid
from typing import Optional
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select, func
from app.db import (SessionLocal, EvalSuite, EvalCase, EvalCaseReview, EvalRun)
from app import engine as eng

app = FastAPI(title="eval case double review", version="1.0.0")


class ReviewBody(BaseModel):
    verdict: str
    point_comments: Optional[dict] = None
    comment: Optional[str] = None


def current_user(x_user_id: str = Header(default=""),
                 x_permissions: str = Header(default="")):
    """S2-IAM 对接点：真实环境由 IAM 下发身份与权限，本单用请求头模拟。"""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="missing X-User-Id")
    perms = [p.strip() for p in x_permissions.split(",") if p.strip()]
    return {"user_id": x_user_id, "permissions": perms}


@app.post("/api/eval/cases/{case_id}/reviews")
def create_review(case_id: str, body: ReviewBody, u=Depends(current_user)):
    if not eng.can_review(u["permissions"]):
        raise HTTPException(status_code=403, detail="eval.case.review required")
    s = SessionLocal()
    try:
        case = s.get(EvalCase, uuid.UUID(case_id))
        if case is None or case.deleted_at is not None:
            raise HTTPException(status_code=404, detail="case not found")
        if body.verdict not in (eng.APPROVE, eng.REVISE, eng.REMOVE):
            raise HTTPException(status_code=422,
                                detail="verdict must be approve/revise/remove")
        r = EvalCaseReview(
            id=uuid.uuid4(), org_id=case.org_id, site_id=case.site_id,
            case_id=case.id, reviewer_id=uuid.UUID(u["user_id"]),
            verdict=body.verdict, point_comments=body.point_comments or {},
            comment=body.comment, case_hash=case.content_hash,
            created_by=uuid.UUID(u["user_id"]))
        s.add(r); s.flush()
        rows = s.execute(select(EvalCaseReview)
                         .where(EvalCaseReview.case_id == case.id,
                                EvalCaseReview.deleted_at.is_(None))
                         .order_by(EvalCaseReview.created_at)).scalars().all()
        verdicts = [{"reviewer_id": str(x.reviewer_id), "verdict": x.verdict} for x in rows]
        status, approvers = eng.decide_status(
            verdicts, current_hash=case.content_hash, reviewed_hash=case.reviewed_hash)
        case.review_status = status
        if status == eng.STATUS_REVIEWED:
            case.reviewed_hash = case.content_hash
        s.commit()
        return {"case_id": str(case.id), "review_id": str(r.id),
                "review_status": status, "approvers": approvers,
                "required": eng.REQUIRED_APPROVERS}
    finally:
        s.close()


@app.get("/api/eval/suites")
def list_suites(u=Depends(current_user)):
    s = SessionLocal()
    try:
        out = []
        suites = s.execute(select(EvalSuite)
                           .where(EvalSuite.deleted_at.is_(None))
                           .order_by(EvalSuite.key)).scalars().all()
        for su in suites:
            total = s.execute(select(func.count()).select_from(EvalCase)
                              .where(EvalCase.suite_id == su.id,
                                     EvalCase.deleted_at.is_(None))).scalar()
            reviewed = s.execute(select(func.count()).select_from(EvalCase)
                                 .where(EvalCase.suite_id == su.id,
                                        EvalCase.deleted_at.is_(None),
                                        EvalCase.review_status == eng.STATUS_REVIEWED)
                                 ).scalar()
            passed = s.execute(select(func.count()).select_from(EvalRun)
                               .join(EvalCase, EvalRun.case_id == EvalCase.id)
                               .where(EvalCase.suite_id == su.id,
                                      EvalRun.passed == "true")).scalar()
            out.append({"id": str(su.id), "key": su.key, "name": su.name,
                        "case_count": total, "reviewed_count": reviewed,
                        "latest_pass_rate": (round(passed / total, 4) if total else None)})
        return {"items": out}
    finally:
        s.close()


@app.get("/api/eval/cases/{case_id}")
def get_case(case_id: str, u=Depends(current_user)):
    """{case_id} 段同时接受 UUID 与 case_key。

    工单只给了 3 个接口，但前端路由是 /eval/suites/:key/cases/:case_key，
    必须能按 case_key 取详情；与其新增第 4 个接口，不如让这一段兼容两种写法。
    """
    s = SessionLocal()
    try:
        try:
            cid = uuid.UUID(case_id)
        except ValueError:
            cid = None
        if cid is not None:
            case = s.get(EvalCase, cid)
        else:
            case = s.execute(select(EvalCase).where(
                EvalCase.case_key == case_id,
                EvalCase.deleted_at.is_(None))).scalars().first()
        if case is None or case.deleted_at is not None:
            raise HTTPException(status_code=404, detail="case not found")
        runs = s.execute(select(EvalRun).where(EvalRun.case_id == case.id)
                         .order_by(EvalRun.at.desc()).limit(3)).scalars().all()
        revs = s.execute(select(EvalCaseReview)
                         .where(EvalCaseReview.case_id == case.id,
                                EvalCaseReview.deleted_at.is_(None))
                         .order_by(EvalCaseReview.created_at.desc())).scalars().all()
        return {"id": str(case.id), "case_key": case.case_key,
                "input": case.input_text, "context": case.context,
                "points": case.points, "content_hash": case.content_hash,
                "review_status": case.review_status,
                "recent_runs": [{"at": r.at.isoformat(), "output": r.output,
                                 "hits": r.hits, "passed": r.passed} for r in runs],
                "reviews": [{"reviewer_id": str(x.reviewer_id), "verdict": x.verdict,
                             "point_comments": x.point_comments, "comment": x.comment}
                            for x in revs]}
    finally:
        s.close()


# 建表由 alembic 迁移负责（见 app/schema.py），启动时不再 create_all——
# 两者并存会导致 buyer 先跑测试再跑迁移时 DuplicateTable。


# ---- 前端托管：构建产物存在时由后端直接 serve，前端走 BrowserRouter 需要回退到 index.html ----
_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "frontend", "dist")
if os.path.isdir(os.path.join(_DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "assets/")):
        raise HTTPException(status_code=404, detail="not found")
    index = os.path.join(_DIST, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="frontend not built")
