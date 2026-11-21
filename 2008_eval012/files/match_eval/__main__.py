# -*- coding: utf-8 -*-
"""评测 runner。

被测工具（echo mock）：
  · 打分筛掉 opt_out / 利益冲突的资源（这正是陷阱用例要考的）
  · 按 行业=服务类型=阶段=站点 的匹配度排序，取前 3
  · 为前 3 各写一句带字段值的理由

--break-optout 让它忽略 opt_out/冲突（模拟「没读这两个字段」），
--break-reason 让它编造理由里的字段值，两者都用于证明指标能抓到缺陷。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from match_eval import metrics as M

DATA = os.path.join(HERE, "data", "cases.jsonl")
REPORTS = os.path.join(HERE, "reports")
TOPK = 3
NO_MATCH = "暂无合适匹配"


def load_cases():
    return [json.loads(l) for l in open(DATA, encoding="utf-8") if l.strip()]


def load_ctx(case):
    return json.load(open(os.path.join(HERE, case["context_file"]), encoding="utf-8"))["candidates"]


def score_candidate(need, c, ignore_exclusion=False):
    """打分。**核心匹配（行业 + 服务类型）是必要条件**，阶段与站点只是加分。

    ★ 为什么必须设这个必要条件：只按加权总分排序时，一个行业与服务类型都不对、
    只是站点相同的资源仍能拿到 1.0 分 > 0，于是「无合适资源」用例永远不会输出
    「暂无合适匹配」（实测 6/6 全错）。必要条件写清楚，语义才不会漂。
    """
    if not ignore_exclusion and (c.get("opt_out") or need["member_id"] in (c.get("conflict_with") or [])):
        return -1.0
    core = 0
    if c.get("industry") == need["industry"]:
        core += 1
    if c.get("service_type") == need["service_type"]:
        core += 1
    if core == 0:
        return 0.0                      # 核心一项都不匹配 -> 不算候选
    s = float(core) * 3.0
    if c.get("stage_pref") == need["stage"]:
        s += 1.5
    if c.get("site") == need["site"]:
        s += 1.0
    return s


def make_reason(c, fake=False):
    if fake:
        return ("行业：医疗器械代理，服务类型：法律咨询，阶段：天使轮。"
                "（该理由的字段值与候选资源实际字段不符）")
    return ("行业：%s，服务类型：%s，阶段：%s，站点：%s，与需求方向一致。"
            % (c.get("industry"), c.get("service_type"), c.get("stage_pref"), c.get("site")))


def predict(case, ignore_exclusion=False, fake_reason=False):
    need = case["need"]
    cands = load_ctx(case)
    scored = [(score_candidate(need, c, ignore_exclusion), c) for c in cands]
    scored.sort(key=lambda x: (-x[0], x[1]["resource_id"]))
    ranked = [c["resource_id"] for s, c in scored if s > 0][:TOPK]
    by_id = {c["resource_id"]: c for c in cands}
    reasons = {rid: make_reason(by_id[rid], fake_reason) for rid in ranked}
    return {"ranked": ranked, "reasons": reasons, "by_id": by_id,
            "no_match": (not ranked)}


def evaluate_case(case, ignore_exclusion=False, fake_reason=False):
    p = predict(case, ignore_exclusion, fake_reason)
    gold = case["gold_resources"]
    forb = {f["resource_id"] for f in case["forbidden_points"]}
    violated = [r for r in p["ranked"] if r in forb]
    r3 = M.recall_at_k(gold, p["ranked"], TOPK) if gold else None
    mr = M.mrr(gold, p["ranked"]) if gold else None
    ps = M.point_score(p["reasons"], p["by_id"], gold, TOPK) if gold else None
    return {
        "case_id": case["case_id"], "kind": case["kind"],
        "ranked": p["ranked"], "gold": gold,
        "recall_at_3": r3, "mrr": mr,
        "reason_score": ps["score"] if ps else None,
        "reason_detail": ps["detail"] if ps else [],
        "forbidden_violated": violated,
        "no_match_pred": p["no_match"],
        "expect_no_match": case["expect_no_match"],
    }


def aggregate(rows):
    with_gold = [r for r in rows if r["gold"]]
    none_cases = [r for r in rows if not r["gold"]]
    m = {
        "cases": len(rows),
        "with_gold": len(with_gold),
        "no_gold": len(none_cases),
        "recall_at_3": round(sum(r["recall_at_3"] for r in with_gold) / len(with_gold), 6)
                        if with_gold else 0.0,
        "mrr": round(sum(r["mrr"] for r in with_gold) / len(with_gold), 6) if with_gold else 0.0,
        "reason_support": round(sum(r["reason_score"] for r in with_gold) / len(with_gold), 6)
                          if with_gold else 0.0,
        "forbidden_violations": sum(len(r["forbidden_violated"]) for r in rows),
        "no_match_correct": sum(1 for r in none_cases if r["no_match_pred"]),
        "thresholds": dict(M.THRESH),
    }
    m["fails"] = [M.LABELS[k] + " %.4f < %.2f" % (m[k], M.THRESH[k])
                  for k in M.THRESH if not M.check(k, m[k])]
    if m["forbidden_violations"]:
        m["fails"].append("推荐了被排除的资源（opt_out 或利益冲突）%d 次" % m["forbidden_violations"])
    if none_cases and m["no_match_correct"] < len(none_cases):
        m["fails"].append("无合适资源用例未输出「暂无合适匹配」%d/%d"
                          % (len(none_cases) - m["no_match_correct"], len(none_cases)))
    return m


def write_report(m, rows, path_md, path_json):
    os.makedirs(os.path.dirname(path_md), exist_ok=True)
    L = ["# 招商 AI 资源匹配评测报告", "",
         "> 企业与资源全部虚构；被测输出只进复核队列、不得直接对外发送；推荐不涉及报价，"
         "AI 不计算金额。", "",
         "## 一、三项指标", "", "| 指标 | 实测 | 门槛 | 判定 |", "|---|---|---|---|"]
    for k in ("recall_at_3", "mrr", "reason_support"):
        L.append("| %s | %.4f | ≥%.2f | %s |" % (M.LABELS[k], m[k], M.THRESH[k],
                                                "通过" if M.check(k, m[k]) else "**未通过**"))
    L += ["", "## 二、陷阱与无匹配", "",
          "| 项 | 值 |", "|---|---|",
          "| 推荐了被排除资源（opt_out / 利益冲突） | %d 次 |" % m["forbidden_violations"],
          "| 无合适资源用例数 | %d |" % m["no_gold"],
          "| 其中正确输出「暂无合适匹配」 | %d |" % m["no_match_correct"], "",
          "## 三、分布", "",
          "| 类型 | 条数 |", "|---|---|"]
    from collections import Counter
    for k, v in Counter(r["kind"] for r in rows).items():
        L.append("| %s | %d |" % (k, v))
    L += ["", "## 四、判定", "",
          "**%s**" % ("未达标：" + "；".join(m["fails"]) if m["fails"] else "全部达标"), "",
          "## 五、逐条结果", "",
          "| 用例 | 类型 | recall@3 | MRR | 理由有据 | 违规 |", "|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s | %s | %s | %s | %s |" % (
            r["case_id"], r["kind"],
            "-" if r["recall_at_3"] is None else "%.4f" % r["recall_at_3"],
            "-" if r["mrr"] is None else "%.4f" % r["mrr"],
            "-" if r["reason_score"] is None else "%.4f" % r["reason_score"],
            ",".join(r["forbidden_violated"]) or "-"))
    open(path_md, "w", encoding="utf-8").write("\n".join(L))
    json.dump({"metrics": m, "rows": rows}, open(path_json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return path_md


def main(argv=None):
    ap = argparse.ArgumentParser(prog="match_eval")
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--break-optout", action="store_true", help="忽略 opt_out 与利益冲突")
    ap.add_argument("--break-reason", action="store_true", help="理由里编造字段值")
    a = ap.parse_args(argv)
    cases = load_cases()
    rows = [evaluate_case(c, a.break_optout, a.break_reason) for c in cases]
    m = aggregate(rows)
    suffix = "" if not (a.break_optout or a.break_reason) else "_broken"
    md = os.path.join(REPORTS, "match_%s%s.md" % (a.tag, suffix))
    write_report(m, rows, md, md[:-3] + ".json")
    print("cases=%d with_gold=%d no_gold=%d" % (m["cases"], m["with_gold"], m["no_gold"]))
    print("recall@3=%.4f mrr=%.4f reason=%.4f forbidden=%d no_match=%d/%d"
          % (m["recall_at_3"], m["mrr"], m["reason_support"],
             m["forbidden_violations"], m["no_match_correct"], m["no_gold"]))
    print("report=%s" % md)
    if m["fails"]:
        print("THRESHOLD NOT MET: " + "；".join(m["fails"]))
        return 1
    print("THRESHOLD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
