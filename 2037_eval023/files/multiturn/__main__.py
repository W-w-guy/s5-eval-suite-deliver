# -*- coding: utf-8 -*-
"""runner：多轮对话评测（#2037）

    python -m multiturn                       # 全量评测，全达标 rc=0
    python -m multiturn --break-history       # 破坏开关：不带历史（指代/纠正必失败）
    python -m multiturn --break-stale         # 破坏开关：纠正后仍沿用旧前提（forbidden 必触发）
    python -m multiturn --tag v2

★ 这个 runner 的「被测工具」是 echo mock：按轮次依次调用，并把历史带上。
  历史记为 [{role, text}] 列表，模拟真实接口的多轮上下文传递。
  --break-history 让它**不传历史** —— 这是多轮能力最典型的失效形态，
  指代消解与纠正类必须因此失败，否则说明评测集没有真正考到多轮。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")
FACTS = os.path.join(DATA, "facts_mt.json")

from . import metrics as M      # noqa: E402


def load_cases(path=None):
    p = path or os.path.join(DATA, "cases.jsonl")
    if not os.path.isfile(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def load_facts():
    if not os.path.isfile(FACTS):
        return {}
    rows = json.load(open(FACTS, encoding="utf-8"))
    return {r["doc_id"]: r for r in rows}


# ---------------- echo mock：按轮次作答 ----------------
TITLE_RE = re.compile(r"《([^》]+)》")


def find_doc_by_title(facts: dict, title: str):
    t = re.sub(r"\s+", "", title or "")
    for d in facts.values():
        if re.sub(r"\s+", "", d["title"]) == t:
            return d
    return None


def answer_turn(turn_text: str, history: list, facts: dict, break_history=False):
    """被测工具的 mock。

    策略：
      1) 取历史里**最近一次被提到的文档**（这就是多轮能力）；
      2) 若当前轮自己点名了新文档，则以新文档为准（纠正/切换）；
      3) 按问题里的关键词挑对应小节作答。
    """
    hist = [] if break_history else list(history or [])
    # 收集历史里出现过的文档（按时间正序，去重保序）
    mentioned, seen = [], set()
    for h in hist:
        for title in TITLE_RE.findall(h.get("text") or ""):
            d = find_doc_by_title(facts, title)
            if d and d["doc_id"] not in seen:
                seen.add(d["doc_id"])
                mentioned.append(d)
    ctx_doc = mentioned[-1] if mentioned else None
    # 「回到刚才那个 / 回到之前」-> 指上一个话题，而不是当前这个
    if any(k in (turn_text or "") for k in ("回到刚才", "回到之前", "刚才那个", "前面那个")):
        if len(mentioned) >= 2:
            ctx_doc = mentioned[-2]
    # 当前轮点名 -> 覆盖上下文（这就是「纠正」与「切换」能被正确处理的原因）
    for title in TITLE_RE.findall(turn_text or ""):
        d = find_doc_by_title(facts, title)
        if d:
            ctx_doc = d
    if not ctx_doc:
        return "抱歉，我不确定你指的是哪份资料。"
    # 挑小节
    keymap = [("开放时间", ("开放", "几点", "最晚", "最早")),
              ("容量", ("容纳", "多少人", "容量", "坐多少")),
              ("预约规则", ("预约", "提前", "取消")),
              ("违约", ("违约", "爽约")),
              ("响应时效", ("响应", "多久回", "多久能回")),
              ("收费标准", ("收费", "费用", "交钱", "算钱")),
              ("支持标准", ("支持", "补助", "多少钱", "额度")),
              ("申报截止", ("截止", "什么时候截")),
              ("审核流程", ("审批", "流程", "多久能出结果")),
              ("适用对象", ("谁能申请", "适用对象", "什么企业")),
              ("覆盖范围", ("能给", "别人", "转授")),
              ("答复", ("怎么答", "怎么办理"))]
    parts = []
    for sec, kws in keymap:
        if any(k in (turn_text or "") for k in kws) and sec in ctx_doc["body"]:
            parts.append(ctx_doc["body"][sec])
    if not parts:
        # 没识别出具体小节 -> 给标题 + 第一段（保证有话可说，但不虚构）
        first = next(iter(ctx_doc["body"].values()), "")
        parts.append("《%s》：%s" % (ctx_doc["title"], first))
    return " ".join(parts)


def run_case(case: dict, facts: dict, break_history=False, break_stale=False):
    history, outs = [], {}
    stale_doc = None
    for fb in case.get("forbidden_points") or []:
        if fb.get("type") == "stale_premise":
            stale_doc = fb.get("wrong_entity")
    for i, t in enumerate(case["turns"]):
        if t["role"] == "user":
            if break_stale and stale_doc and i >= 2:
                # 破坏开关：纠正后仍按旧前提作答
                d = facts.get(stale_doc) or {}
                ans = d.get("body", {}).get("开放时间", "（旧前提）")
                ans = ans + " " + d.get("body", {}).get("容量", "")
            else:
                ans = answer_turn(t["text"], history, facts, break_history)
            outs[i] = ans
            history.append({"role": "user", "text": t["text"]})
            history.append({"role": "assistant", "text": ans})
        else:
            # 用例里预置的 assistant 轮也进历史（它是「上一轮的答案」）
            outs[i] = t.get("text") or ""
            history.append({"role": "assistant", "text": outs[i]})
    last = max(outs) if outs else 0
    return {
        "case_id": case["case_id"], "kind": case["kind"],
        "turn_outputs": outs,
        "final_answer": outs.get(last, ""),
    }


def evaluate(case, facts, **kw):
    r = run_case(case, facts, **kw)
    fh = M.final_point_hit_rate(case, r["final_answer"])
    cp = M.checkpoint_pass_rate(case, r["turn_outputs"])
    vio = M.forbidden_violations(case, r["turn_outputs"])
    return {"case_id": case["case_id"], "kind": case["kind"],
            "final_point_hit": fh["value"], "checkpoint_pass": cp["value"],
            "violations": vio,
            "_fh": fh, "_cp": cp, "_outs": r["turn_outputs"]}


def write_report(m, rows, path_md, path_json, extra):
    os.makedirs(os.path.dirname(path_md), exist_ok=True)
    L = ["# 知识问答多轮对话评测报告（#2037）", "",
         "> 复用 EVAL-022 的虚构知识库夹具（120 篇）；对话与知识全部虚构；"
         "被测输出只进复核队列、不直接对外发送；AI 不计算金额。", "",
         "## 一、三项指标", "", "| 指标 | 实测 | 门槛 | 判定 |", "|---|---|---|---|"]
    for k in ("final_point_hit", "checkpoint_pass"):
        L.append("| %s | %.4f | ≥%.2f | %s |"
                 % (M.LABELS[k], m[k], m["thresholds"][k],
                    "通过" if m[k] >= m["thresholds"][k] else "**未通过**"))
    L.append("| %s | %d | 必须 0 | %s |"
             % (M.LABELS["forbidden_violations"], m["forbidden_violations"],
                "通过" if m["forbidden_violations"] == 0 else "**未通过**"))
    L += ["", "## 二、分布", "", "| 类型 | 组数 |", "|---|---|"]
    from collections import Counter
    for k, v in Counter(r["kind"] for r in rows).items():
        L.append("| %s | %d |" % (k, v))
    L += ["", "## 三、按轮次可见的检查点", "",
          "| 用例 | 轮数 | 检查点轮 | 通过 |", "|---|---|---|---|"]
    for r in rows[:30]:
        L.append("| %s | %d | %s | %s |"
                 % (r["case_id"], extra["turns"].get(r["case_id"], 0),
                    ",".join(str(x["turn"] + 1) for x in (r["_cp"].get("failed") or [])) or "全部",
                    "✓" if r["checkpoint_pass"] == 1.0 else "✗"))
    L += ["", "## 四、判定", "",
          "**%s**" % ("未达标：" + "；".join(m["fails"]) if m["fails"] else "全部达标"), ""]
    open(path_md, "w", encoding="utf-8").write("\n".join(L))
    json.dump({"metrics": m, "rows": [{k: v for k, v in r.items()} for r in rows]},
              open(path_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path_md


def main(argv=None):
    ap = argparse.ArgumentParser(prog="multiturn")
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--break-history", action="store_true",
                    help="破坏开关：不传历史（指代消解/纠正必失败）")
    ap.add_argument("--break-stale", action="store_true",
                    help="破坏开关：纠正后仍沿用旧前提（forbidden 必触发）")
    a = ap.parse_args(argv)
    cases = load_cases()
    facts = load_facts()
    if not cases:
        print("缺 data/cases.jsonl", file=sys.stderr)
        return 2
    rows = [evaluate(c, facts, break_history=a.break_history, break_stale=a.break_stale)
            for c in cases]
    m = M.aggregate(rows)
    extra = {"turns": {c["case_id"]: len(c["turns"]) for c in cases},
             "cases": len(cases), "facts": len(facts),
             "break_history": a.break_history, "break_stale": a.break_stale}
    suffix = "" if not (a.break_history or a.break_stale) else "_broken"
    md = os.path.join(REPORTS, "mt_%s%s.md" % (a.tag, suffix))
    write_report(m, rows, md, md[:-3] + ".json", extra)
    print("cases=%d facts=%d" % (len(cases), len(facts)))
    print("  final_point_hit    %.4f" % m["final_point_hit"])
    print("  checkpoint_pass    %.4f" % m["checkpoint_pass"])
    print("  forbidden          %d" % m["forbidden_violations"])
    print("report=%s" % md)
    if m["fails"]:
        print("THRESHOLD NOT MET: " + "；".join(m["fails"]))
        return 1
    print("THRESHOLD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
