# -*- coding: utf-8 -*-
"""逐条断言本单 AC。任何一条失败即非零退出。

需要真 PostgreSQL（DATABASE_URL）。缺库时**判 FAIL 而不是跳过**。
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pkg"))
import redact          # noqa: E402
import state as S      # noqa: E402
import workdays as W   # noqa: E402

DATA = os.path.join(ROOT, "data")
BASE = "/api/eval/redteam-findings"
RESULTS = []


def ok(code, title, detail=""):
    RESULTS.append(True)
    print("[PASS] %s %s %s" % (code, title, detail))


def bad(code, title, detail=""):
    RESULTS.append(False)
    print("[FAIL] %s %s %s" % (code, title, detail))


def check(code, cond, title, detail=""):
    (ok if cond else bad)(code, title, detail)


def main():
    seeds = json.load(open(os.path.join(DATA, "seeds.json"), encoding="utf-8"))
    org, canary = seeds["org"], seeds["canary"]
    SEC, ENG = seeds["roles"]["sec"], seeds["roles"]["eng"]

    # ---------- 环境 ----------
    has_url = bool(os.environ.get("DATABASE_URL"))
    check("V01", has_url, "DATABASE_URL 已设置（真 PostgreSQL）",
          os.environ.get("DATABASE_URL", "").split("@")[-1] if has_url else "未设置")
    if not has_url:
        print("")
        print("SUMMARY %d/%d PASS" % (sum(1 for x in RESULTS if x), len(RESULTS)))
        return 1

    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from pkg.db import get_engine, get_session, reset_schema
    from pkg.models import RedteamFinding
    import pkg.api as API
    import pkg.jobs as JOBS

    # 建库 + 灌种子（与 conftest 同一条路径）
    reset_schema()
    with get_session() as sess:
        for i, s in enumerate(seeds["seeds"], 1):
            masked, _h = redact.redact(s["evidence"])
            sess.add(RedteamFinding(
                finding_no="RT-2026-%03d" % i, title=s["title"], tool=s["tool"],
                technique=s["technique"], severity=s["severity"], status=s["status"],
                repro_steps="步骤：1) 构造输入 2) 观察输出 3) 记录差异",
                evidence=masked, evidence_canary=s["canary"],
                owner_role=s["owner_role"], found_at=s["found_at"],
                confirmed_at=s.get("confirmed_at"), fixed_at=s.get("fixed_at"),
                verified_run_id=s.get("verified_run_id"),
                regression_case_key=s.get("regression_case_key"),
                wont_fix_reason=s.get("wont_fix_reason"),
                approved_by_role=s.get("approved_by_role"),
                org_id=org, created_by=seeds["operator"]))
    client = TestClient(API.app)
    hdr = {"X-Permissions": "%s,%s" % (S.PERM_WRITE, S.PERM_APPROVE),
           "X-Role": SEC, "X-Operator": "verify.sec", "X-Org": org}
    hdr_eng = {"X-Permissions": S.PERM_WRITE, "X-Role": ENG,
               "X-Operator": "verify.eng", "X-Org": org}

    # 按 key 取 finding_no，不硬编码编号 —— 种子顺序调整时编号会位移
    KEY_NO = {"RT-2026-%03d" % (i + 1): s["key"]
              for i, s in enumerate(seeds["seeds"])}
    NO = {v: k for k, v in KEY_NO.items()}

    def items(today=None, **kw):
        p = dict(kw)
        if today:
            p["today"] = today
        r = client.get(BASE, headers=hdr, params=p)
        assert r.status_code == 200, r.text
        return r.json()["items"]

    # ---------- 迁移与表结构 ----------
    with get_engine().begin() as c:
        tables = c.execute(text("select table_name from information_schema.tables "
                               "where table_schema='public' order by 1")).scalars().all()
        ver = c.execute(text("select version_num from alembic_version")).scalar()
        cols = c.execute(text("select column_name from information_schema.columns "
                             "where table_name='redteam_finding' "
                             "order by ordinal_position")).scalars().all()
        srv = c.execute(text("show server_version")).scalar()
    check("V02", "redteam_finding" in tables and "redteam_monthly_archive" in tables,
          "两张表由 Alembic 迁移建出（不是 create_all）", "%s" % tables)
    check("V03", ver == "0001", "alembic_version 已推进到 0001", "version=%s" % ver)
    check("V04", str(srv).startswith("16"), "连的是真 PostgreSQL 16", "server_version=%s" % srv)
    need_cols = ["finding_no", "severity", "status", "evidence", "regression_case_key",
                 "verified_run_id", "wont_fix_reason", "org_id", "site_id",
                 "created_at", "created_by", "updated_at", "deleted_at"]
    miss = [c for c in need_cols if c not in cols]
    check("V05", not miss, "统一约定的审计字段与业务字段齐全", "缺 %s" % (miss or "无"))

    # ---------- AC1：overdue（2 个工作日） ----------
    check("V06", W.overdue_deadline("2026-11-25") == "2026-11-27",
          "confirmed 周三 11-25 + 2 个工作日 = 周五 11-27",
          "%s" % W.overdue_deadline("2026-11-25"))
    check("V07", W.overdue_deadline("2026-11-27") == "2026-12-01",
          "confirmed 周五 11-27 + 2 个工作日 跨周末 = 周二 12-01",
          "%s" % W.overdue_deadline("2026-11-27"))
    on_dl = [x for x in items(today="2026-11-27") if x["finding_no"] == NO["F_P0_CONFIRMED"]][0]
    check("V08", on_dl["overdue"] is False, "截止日当天不算 overdue",
          "confirmed=%s today=2026-11-27" % on_dl["confirmed_at"])
    after = [x for x in items(today="2026-11-28") if x["finding_no"] == NO["F_P0_CONFIRMED"]][0]
    check("V09", after["overdue"] is True, "截止日次日起标记 overdue", "today=2026-11-28")
    with_case = [x for x in items(today="2026-12-31") if x["finding_no"] == NO["F_P0_HAS_CASE"]][0]
    check("V10", with_case["overdue"] is False and with_case["regression_case_key"],
          "已关联回归用例的一律不算 overdue",
          "case=%s" % with_case["regression_case_key"])
    # 冻结时间：同一批数据换 today，结论随之变化
    t1 = {x["finding_no"]: x["overdue"] for x in items(today="2026-11-27")}
    t2 = {x["finding_no"]: x["overdue"] for x in items(today="2026-12-02")}
    check("V11", t1 != t2 and t2[NO["F_P0_CONFIRMED"]] is True,
          "冻结时间生效：换 today 结论随之变化（不是读系统时钟）",
          "11-27 %s ／ 12-02 %s" % (t1[NO["F_P0_CONFIRMED"]], t2[NO["F_P0_CONFIRMED"]]))
    job = JOBS.scan(org_id=org, today="2026-11-28", write_snapshot=False)
    check("V12", NO["F_P0_CONFIRMED"] in [x["finding_no"] for x in job["items"]]
          and job["overdue_count"] == len(job["items"]),
          "定时任务扫描出 overdue 清单", "count=%d" % job["overdue_count"])

    # ---------- AC2：P0 改 wont_fix 返回 422 ----------
    p0 = [x for x in items() if x["finding_no"] == NO["F_P0_CONFIRMED"]][0]
    r = client.patch("%s/%s" % (BASE, p0["id"]), headers=hdr,
                     json={"status": "wont_fix", "wont_fix_reason": "不想修"})
    check("V13", p0["severity"] == "P0", "RT-2026-001 是 P0 且已 confirmed",
          "severity=%s status=%s" % (p0["severity"], p0["status"]))
    check("V14", r.status_code == 422, "P0 改 wont_fix 返回 422",
          "status_code=%d" % r.status_code)
    check("V15", "P0" in r.json().get("detail", ""), "422 的原因点明 P0 不允许",
          r.json().get("detail", "")[:60])
    # 正向对照：P2 + 安全负责人 + 理由 -> 200
    r0 = client.post(BASE, headers=hdr, json={
        "title": "低危对照", "tool": "copy_draft", "technique": "tone",
        "severity": "P2", "repro_steps": "1)", "evidence": "e",
        "owner_role": ENG, "found_at": "2026-11-26"})
    fid = r0.json()["id"]
    client.patch("%s/%s" % (BASE, fid), headers=hdr,
                 json={"status": "confirmed", "confirmed_at": "2026-11-26"})
    r2 = client.patch("%s/%s" % (BASE, fid), headers=hdr,
                      json={"status": "wont_fix", "wont_fix_reason": "影响面极低"})
    check("V16", r2.status_code == 200 and r2.json()["status"] == "wont_fix",
          "P2 + 安全负责人 + 理由 → 允许 wont_fix（正向对照）",
          "status_code=%d" % r2.status_code)
    r3 = client.patch("%s/%s" % (BASE, fid), headers=hdr_eng,
                      json={"status": "wont_fix", "wont_fix_reason": "x"})
    check("V17", r3.status_code in (403, 422),
          "缺审批权限或非安全负责人角色时被拒", "status_code=%d" % r3.status_code)

    # ---------- AC3：evidence 入库后已掩码 ----------
    plain = "金丝雀 %s 电话 13500000001 邮箱 qa_owner@example.invalid" % canary
    r4 = client.post(BASE, headers=hdr, json={
        "title": "带敏感信息", "tool": "kb_answer", "technique": "leak",
        "severity": "P1", "repro_steps": "1)", "evidence": plain,
        "owner_role": ENG, "canary": canary, "found_at": "2026-11-26"})
    fid4 = r4.json()["id"]
    with get_session() as sess:
        stored = sess.get(RedteamFinding, fid4).evidence
    check("V18", canary not in stored, "金丝雀在库里已被掩码（查库不查响应）",
          "库里：%s" % stored[:46])
    check("V19", "13500000001" not in stored and "135****0001" in stored,
          "手机号在库里已按前3后4掩码", "")
    check("V20", redact.leak_of_canary(stored, canary) is False,
          "掩码后不再残留完整金丝雀", "")
    check("V21", redact.leak_of_canary(plain, canary) is True,
          "反向对照：未掩码的原文会被判为泄露（证明检测本身有效）", "")

    # ---------- AC4：月度导出三组 ----------
    r5 = client.get("%s/monthly" % BASE, headers=hdr, params={"month": "2026-11"})
    body = r5.json()
    check("V22", r5.status_code == 200
          and set(body) >= {"created", "fixed", "open", "counts"},
          "月度导出接口返回新增 / 已修复 / 未关闭三组",
          "counts=%s" % body.get("counts"))
    created_no = {x["finding_no"] for x in body["created"]}
    fixed_no = {x["finding_no"] for x in body["fixed"]}
    open_no = {x["finding_no"] for x in body["open"]}
    check("V23", NO["F_P2_NEW"] in created_no,
          "「新增」按 found_at 落在当月（RT-2026-004 found_at 2026-11-20）",
          "created=%d 条" % len(created_no))
    # 用跨月样本锁口径：RT-2026-007 的 found_at 在 10 月、fixed_at 在 11 月，
    # 只有真按 fixed_at 判定它才会出现在 11 月的「已修复」里。
    check("V24", NO["F_P1_FIXED"] in fixed_no and NO["F_P1_FIXED_CROSS"] in fixed_no,
          "「已修复」按 fixed_at 落在当月（含一条 found_at 在 10 月的跨月样本）",
          "fixed=%d 条 %s" % (len(fixed_no), sorted(fixed_no)))
    check("V25", NO["F_P1_VERIFIED"] not in open_no and NO["F_P2_WONTFIX"] not in open_no,
          "「未关闭」排除 verified 与 wont_fix",
          "open=%d 条" % len(open_no))
    check("V26", body["counts"]["created"] == len(body["created"])
          and body["counts"]["fixed"] == len(body["fixed"])
          and body["counts"]["open"] == len(body["open"]),
          "三组计数与清单长度一致", "")

    # ---------- 接口契约与 OpenAPI ----------
    spec = client.get("/openapi.json").json()
    paths = spec.get("paths", {})
    check("V27", BASE in paths and any(p.startswith(BASE + "/{") for p in paths)
          and BASE + "/monthly" in paths,
          "OpenAPI 描述了 POST/GET/PATCH 与 monthly 四个路径", "%d 个路径" % len(paths))
    check("V28", client.get(BASE, headers=hdr, params={"severity": "P0"}
                            ).json()["items"]
          and all(x["severity"] == "P0" for x in items(severity="P0")),
          "按严重度筛选生效", "P0=%d 条" % len(items(severity="P0")))
    check("V29", all(x["tool"] == "kb_answer" for x in items(tool="kb_answer")),
          "按工具筛选生效", "kb_answer=%d 条" % len(items(tool="kb_answer")))
    check("V30", all(x["status"] == "fixed" for x in items(status="fixed")),
          "按状态筛选生效", "fixed=%d 条" % len(items(status="fixed")))
    r6 = client.post(BASE, headers={}, json={"title": "x"})
    check("V31", r6.status_code == 403, "无 eval.redteam.write 时登记被拒 403",
          "status_code=%d" % r6.status_code)

    # ---------- pytest ----------
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    pr = subprocess.run([sys.executable, "-m", "pytest", "tests", "-v", "--no-header",
                         "-p", "no:cacheprovider", "-o", "addopts="],
                        cwd=ROOT, capture_output=True, env=env)
    out = (pr.stdout + pr.stderr).decode("utf-8", "replace")
    npass = out.count("PASSED")
    nskip = out.count("SKIPPED")
    check("V32", pr.returncode == 0 and npass >= 60,
          "pytest 全绿且用例数不少于 60", "PASSED=%d SKIPPED=%d rc=%d"
          % (npass, nskip, pr.returncode))
    check("V33", nskip == 0, "pytest 没有任何 SKIP（跳过不算通过）", "SKIPPED=%d" % nskip)

    total = len(RESULTS)
    passed = sum(1 for x in RESULTS if x)
    print("")
    print("SUMMARY %d/%d PASS" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
