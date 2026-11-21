# -*- coding: utf-8 -*-
"""S5-EVAL-022 自检：4 条 AC -> 可执行断言。退出码 0 = 全过。"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

import eval_lint, eval_run, import_kb

F = []
REPORTS = os.path.join(HERE, "reports")


def chk(name, ok, detail=""):
    F.append((name, bool(ok), detail))
    print(("[ OK ]" if ok else "[FAIL]"), name, ("| " + str(detail)) if detail else "")


def py(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, cwd=HERE,
                          text=True, encoding="utf-8", errors="replace")


def main():
    # ================= AC1：120 篇 + 导入脚本在空实例上成功 =================
    docs = [f for f in os.listdir(os.path.join(HERE, "kb_docs")) if f.endswith(".md")]
    chk("AC1 知识文档恰有 120 篇", len(docs) == 120, len(docs))
    tmpdb = os.path.join(HERE, "data", "_verify_kb.sqlite3")
    if os.path.isfile(tmpdb):
        os.remove(tmpdb)
    r = py(os.path.join(HERE, "tools", "import_kb.py"), "--db", tmpdb, "--expect-empty")
    out = r.stdout or ""
    chk("AC1 导入脚本在空实例上执行成功（rc=0）", r.returncode == 0, "rc=%d" % r.returncode)
    chk("AC1 命令输出显示导入前为空", "before: docs=0" in out, out.splitlines()[:1])
    chk("AC1 命令输出显示导入后 120 篇", "after : docs=120" in out, "after" in out)
    conn = import_kb.connect(tmpdb)
    chk("AC1 实例内 doc 数确为 120", import_kb.count(conn) == 120, import_kb.count(conn))
    fields_ok = True
    for d in ("SP-001", "SV-001", "PL-001", "FQ-001"):
        row = conn.execute("SELECT doc_id,title,updated,visibility FROM docs WHERE doc_id=?", (d,)).fetchone()
        if not row or not all(row):
            fields_ok = False
    chk("AC1 每篇带 doc_id/标题/更新日期/可见范围", fields_ok)
    vis = dict(conn.execute("SELECT visibility, COUNT(*) FROM docs GROUP BY visibility").fetchall())
    chk("AC1 可见范围标签存在且非单一值", len(vis) >= 2, vis)
    conn.close()
    os.remove(tmpdb)

    # ================= AC2：50 条 + 分布 + lint/pii 通过 =================
    cases = eval_lint.load_cases()
    chk("AC2 cases.jsonl 恰有 50 条", len(cases) == 50, len(cases))
    errs, stat = eval_lint.lint()
    chk("AC2 4 类分布 20/12/10/8", stat["dist"] == {"single_doc": 20, "multi_doc": 12,
                                                   "numeric_date": 10, "paraphrase": 8}, stat["dist"])
    chk("AC2 eval-lint 通过（0 错误）", not errs, errs[:2])
    r = py(os.path.join(HERE, "tools", "eval_lint.py"))
    chk("AC2 eval-lint 命令行 rc=0 且打印 PASS", r.returncode == 0 and "LINT PASS" in (r.stdout or ""))
    r = py(os.path.join(HERE, "tools", "eval_pii_scan.py"))
    chk("AC2 eval-pii-scan 通过（0 命中）", r.returncode == 0 and "PII PASS" in (r.stdout or ""),
        (r.stdout or "").strip().splitlines()[-1:])
    chk("AC2 lint 能抓到坏金标（gold 文档不存在）",
        any("不存在于知识库" in e for e in
            eval_lint.lint([dict(cases[0], gold_doc_ids=["SP-999"])] + cases[1:])[0]))
    chk("AC2 lint 能抓到凭空编造的答案要点",
        any("无法在任何 gold 文档中逐字找到" in e for e in
            eval_lint.lint([dict(cases[0], answer_points=["凭空编造的一句"] * 3)] + cases[1:])[0]))

    # ================= AC3：gold_doc_ids 都能在知识文档中找到 =================
    db_docs = {d["doc_id"] for d in eval_run.load_docs()}
    missing = [(c["case_id"], g) for c in cases for g in c["gold_doc_ids"] if g not in db_docs]
    chk("AC3 每条用例的 gold_doc_ids 都能在知识库中找到", not missing, missing[:3])
    chk("AC3 每条 gold_doc_ids 数量在 1~3", all(1 <= len(c["gold_doc_ids"]) <= 3 for c in cases))
    chk("AC3 每条 answer_points 数量在 3~5", all(3 <= len(c["answer_points"]) <= 5 for c in cases))
    # 要点必须能在其 gold 文档中逐字找到
    by_id = {d["doc_id"]: d for d in eval_run.load_docs()}
    bad_pts = []
    for c in cases:
        blob = re.sub(r"\s+", "", " ".join(by_id[g]["body"] for g in c["gold_doc_ids"]))
        for p in c["answer_points"]:
            if re.sub(r"\s+", "", p) not in blob:
                bad_pts.append((c["case_id"], p[:20]))
    chk("AC3 每个答案要点都能在 gold 文档里逐字找到", not bad_pts, bad_pts[:3])

    # ================= AC4：echo mock 跑通 eval-run，报告显示 recall@5 与引用准确率 =================
    r = py(os.path.join(HERE, "tools", "eval_run.py"))
    chk("AC4 用 echo mock 跑通 eval-run（rc=0）", r.returncode == 0, "rc=%d" % r.returncode)
    chk("AC4 输出含 recall@5 与 citation", "recall@5=" in (r.stdout or "")
        and "citation=" in (r.stdout or ""))
    md = os.path.join(REPORTS, "kqa_v1.md")
    chk("AC4 生成 Markdown 报告", os.path.isfile(md))
    t = open(md, encoding="utf-8").read() if os.path.isfile(md) else ""
    chk("AC4 报告写明「检索 recall@5」", "检索 recall@5" in t)
    chk("AC4 报告写明「引用准确率」", "引用准确率" in t)
    chk("AC4 报告写明「答案要点命中率」", "答案要点命中率" in t)
    chk("AC4 报告列出 forbidden_points 两项", "引用不在检索结果中的文档" in t
        and "数字与原文不一致" in t)
    m, _ = eval_run.evaluate()
    chk("AC4 三项指标均达标",
        m["recall_at_5"] >= 0.85 and m["point_hit"] >= 0.80 and m["citation_accuracy"] >= 0.95,
        "recall=%.4f point=%.4f cite=%.4f" % (m["recall_at_5"], m["point_hit"], m["citation_accuracy"]))
    chk("AC4 forbidden 两项均为 0",
        m["forbidden_cite_not_in_retrieval"] == 0 and m["forbidden_number_mismatch"] == 0)
    # 指标可被证伪：故意引错 -> 必须掉下来
    mb, _ = eval_run.evaluate(break_citation=True)
    chk("AC4 引用准确率可被证伪（--break-citation 时 <0.95 且触发 forbidden）",
        mb["citation_accuracy"] < 0.95 and mb["forbidden_number_mismatch"] > 0,
        "cite=%.4f num=%d" % (mb["citation_accuracy"], mb["forbidden_number_mismatch"]))
    rt = py("-m", "pytest", "tests", "-q", "--tb=no")
    chk("AC4 pytest 全套通过", rt.returncode == 0,
        ((rt.stdout or "").strip().splitlines() or ["-"])[-1][:40])

    bad = [f for f in F if not f[1]]
    print("\nTOTAL %d, PASS %d, FAIL %d" % (len(F), len(F) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
