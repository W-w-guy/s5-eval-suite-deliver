# -*- coding: utf-8 -*-
"""S5-EVAL-017 自检：4 条 AC -> 可执行断言。退出码 0 = 全过。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

import eval_run
import metrics as M

F = []
REPORTS = os.path.join(HERE, "reports")


def chk(name, ok, detail=""):
    F.append((name, bool(ok), detail))
    print(("[ OK ]" if ok else "[FAIL]"), name, ("| " + str(detail)) if detail else "")


def py(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, cwd=HERE,
                          text=True, encoding="utf-8", errors="replace")


def main():
    cases = eval_run.load_cases()

    # ================= AC1：35 条 + 3 类分布 + lint/pii =================
    chk("AC1 cases.jsonl 恰有 35 条", len(cases) == 35, len(cases))
    from collections import Counter
    dist = dict(Counter(c["kind"] for c in cases))
    chk("AC1 分布 常规20/高相似干扰10/全无关5",
        dist == {"normal": 20, "high_similarity": 10, "irrelevant": 5}, dist)
    # 先查 context 文件是否存在：文件缺失时 load_context 会抛异常，
    # 那样 verify 崩在半路、AC1 其余项都跑不到，报出来的错也看不出根因。
    missing = [c["case_id"] for c in cases
               if not os.path.isfile(os.path.join(HERE, c["context_file"]))]
    chk("AC1 每条 context 文件都存在", not missing, missing[:5])
    sizes = [len(eval_run.load_context(c)) for c in cases if c["case_id"] not in missing]
    chk("AC1 每条 context 含 8~20 篇资讯", all(8 <= s <= 20 for s in sizes),
        "%d..%d" % (min(sizes), max(sizes)))
    # AC1 要求：eval-lint 与 eval-pii-scan 均通过（命令行工具，不是只在 verify 里内联判断）
    rl = py(os.path.join(HERE, "tools", "lint.py"), "--lint")
    chk("AC1 eval-lint 命令行 rc=0 且打印 PASS",
        rl.returncode == 0 and "LINT PASS" in (rl.stdout or ""),
        (rl.stdout or "").strip().splitlines()[-1] if rl.stdout else rl.stderr[-120:])
    rp = py(os.path.join(HERE, "tools", "lint.py"), "--pii")
    chk("AC1 eval-pii-scan 命令行 rc=0 且打印 PASS",
        rp.returncode == 0 and "PII PASS" in (rp.stdout or ""),
        [x for x in (rp.stdout or "").splitlines() if x.startswith("pii ")][-1:])
    chk("AC1 每条含虚构会员行业画像", all(c.get("profile") and c["profile"].get("industry")
                                   for c in cases))
    chk("AC1 每条含 gold 聚类/分类/前5",
        all(c.get("gold_clusters") and c.get("gold_category") and "gold_top5" in c for c in cases))
    multi = sum(1 for c in cases
                if any(len(v) >= 2 for v in c["gold_clusters"].values()))
    chk("AC1 含同一事件多来源报道的用例（≥30 条）", multi >= 30, multi)
    # 多来源三要素：措辞不同 + 日期不同
    same_event_diff = 0
    for c in cases:
        ctx = {n["news_id"]: n for n in eval_run.load_context(c)}
        for members in c["gold_clusters"].values():
            if len(members) < 2:
                continue
            texts = {ctx[m]["text"] for m in members}
            dates = {ctx[m]["date"] for m in members}
            if len(texts) == len(members) and len(dates) > 1:
                same_event_diff += 1
                break
    chk("AC1 同事件报道措辞与日期都不同（非复制粘贴）", same_event_diff >= 30, same_event_diff)

    # ================= AC2：三项指标脚本 + 门槛 =================
    r = py(os.path.join(HERE, "tools", "eval_run.py"))
    chk("AC2 runner 跑通（rc=0）", r.returncode == 0, "rc=%d" % r.returncode)
    m = eval_run.aggregate([eval_run.evaluate_case(c) for c in cases])
    chk("AC2 聚类 pairwise F1 ≥0.80", m["pairwise_f1"] >= 0.80, "%.4f" % m["pairwise_f1"])
    chk("AC2 分类准确率 ≥0.80", m["category_accuracy"] >= 0.80, "%.4f" % m["category_accuracy"])
    chk("AC2 排序 NDCG@5 ≥0.80", m["ndcg_at_5"] >= 0.80, "%.4f" % m["ndcg_at_5"])
    md = os.path.join(REPORTS, "triage_v1.md")
    t = open(md, encoding="utf-8").read() if os.path.isfile(md) else ""
    chk("AC2 生成报告（md）", os.path.isfile(md))
    for kw in ("聚类 pairwise F1", "分类准确率", "排序 NDCG@5"):
        chk("AC2 报告含「%s」" % kw, kw in t)
    chk("AC2 报告含阈值敏感性表（默认值不是对着答案挑的）", "阈值敏感性" in t)
    # 指标可被证伪
    mb = eval_run.aggregate([eval_run.evaluate_case(c, break_cluster=True) for c in cases])
    chk("AC2 --break-cluster 能打掉 F1（指标可证伪）",
        mb["pairwise_f1"] < 0.80, "%.4f" % mb["pairwise_f1"])
    mo = eval_run.aggregate([eval_run.evaluate_case(c, break_order=True) for c in cases])
    chk("AC2 --break-order 能打掉 NDCG@5", mo["ndcg_at_5"] < 0.80, "%.4f" % mo["ndcg_at_5"])

    # ================= AC3：forbidden 两项 =================
    chk("AC3 forbidden：同一事件出现两次 = 0", m["forbidden_same_event_twice"] == 0)
    chk("AC3 forbidden：context 外资讯 = 0", m["forbidden_outside_context"] == 0)
    ml = eval_run.aggregate([eval_run.evaluate_case(c, leak=True) for c in cases])
    chk("AC3 --leak 能触发 forbidden（检测有效）",
        ml["forbidden_outside_context"] >= 35, ml["forbidden_outside_context"])
    dup = M.forbidden_same_event_twice(["E1", "E2", "E1"])
    chk("AC3 重复事件检测函数手算正确", dup == ["E1"], dup)

    # ================= AC4：全无关样本输出「本期无高相关资讯」 =================
    irr = [c for c in cases if c["expect_no_relevant"]]
    chk("AC4 全无关样本 5 条", len(irr) == 5, len(irr))
    rows = [eval_run.evaluate_case(c) for c in irr]
    chk("AC4 5 条全无关样本的 Top5 均为空（即输出「本期无高相关资讯」）",
        all(not r["pred_top5"] for r in rows),
        [r["pred_top5"] for r in rows])
    chk("AC4 报告里单列无关样本统计",
        "无关样本数" in t and "本期无高相关资讯" in t)

    rt = py("-m", "pytest", "tests", "-q", "--tb=no")
    chk("pytest 全套通过", rt.returncode == 0,
        ((rt.stdout or "").strip().splitlines() or ["-"])[-1][:40])

    bad = [f for f in F if not f[1]]
    print("\nTOTAL %d, PASS %d, FAIL %d" % (len(F), len(F) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
