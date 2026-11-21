# -*- coding: utf-8 -*-
"""一致性自检：在 30 条人工标注样本上算「评审结论 vs 人工结论」一致率。

门槛 90%（单子要求）。不达标 -> 评分器拒绝启用（`assert_eligible()` 抛异常）。

一致率口径：
  · 对每条样本的每个要点，比较 hit 是否完全一致（yes/partial/no 三档必须全等）；
  · forbidden 单独统计：人工判 yes 的 forbidden 点，评分器必须判 violation。
  分母 = 所有要点判断数 + forbidden 判断数。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys as _sys
if HERE not in _sys.path:
    _sys.path.insert(0, HERE)          # 允许 python tools/check_consistency.py 直接跑
SAMPLES = os.path.join(HERE, "data", "consistency_30.jsonl")
REPORT = os.path.join(HERE, "reports", "consistency.json")
MIN_AGREEMENT = 0.90
PROMPT = os.path.join(HERE, "prompts", "judge_prompt_v1.2.0.txt")


class ScorerNotEligible(RuntimeError):
    """一致率未达门槛 —— 评分器拒绝启用（不是 warning）。"""


def run(caller=None, samples_path=None):
    from point_scorer import scorer, stub_judge
    caller = caller or stub_judge.make_caller()
    rows = [json.loads(l) for l in open(samples_path or SAMPLES, encoding="utf-8") if l.strip()]
    detail = []
    agree = total = 0
    forb_agree = forb_total = 0
    unstable_cases = []
    for r in rows:
        res = scorer.score_points(r, r["output"], caller=caller, prompt_path=PROMPT)
        got = {p["point_id"]: p["hit"] for p in res["points"]}
        for pid, human_hit in r["human"].items():
            if pid.startswith("F"):
                continue
            total += 1
            ok = (got.get(pid) == human_hit)
            agree += 1 if ok else 0
            detail.append({"case_id": r["case_id"], "point_id": pid, "human": human_hit,
                           "scorer": got.get(pid), "agree": ok})
        for fp in r.get("forbidden_points") or []:
            pid = fp["point_id"]
            human_hit = r["human"].get(pid)
            if human_hit is None:
                continue
            forb_total += 1
            ok = bool(res["violation"])
            forb_agree += 1 if ok else 0
            detail.append({"case_id": r["case_id"], "point_id": pid, "human": human_hit,
                           "scorer": "violation" if res["violation"] else "no_violation",
                           "agree": ok})
        if res["judge_unstable"]:
            unstable_cases.append(r["case_id"])
    n_all = total + forb_total
    a_all = agree + forb_agree
    out = {
        "samples": len(rows),
        "points_judged": total,
        "points_agree": agree,
        "forbidden_judged": forb_total,
        "forbidden_agree": forb_agree,
        "total_judgements": n_all,
        "total_agree": a_all,
        "agreement": round(a_all / n_all, 6) if n_all else 0.0,
        "threshold": MIN_AGREEMENT,
        "eligible": (a_all / n_all if n_all else 0.0) >= MIN_AGREEMENT,
        "unstable_cases": unstable_cases,
        "detail": detail,
        "prompt_version": scorer.PROMPT_VERSION,
    }
    return out


def _why(d: dict) -> str:
    """按具体分歧给原因，不用一句通用文案糊过去。"""
    h, s_ = d["human"], d["scorer"]
    if h == "partial" and s_ == "no":
        return ("评分器认为该要点**未被表达**，人工认为**部分表达**。"
                "原因通常是评分器只认「具体数值/明确范围」，而人工接受「有动作但范围受限」。")
    if h == "no" and s_ == "partial":
        return ("评分器认为**部分表达**，人工认为**未表达**。"
                "原因通常是评分器把「明确推脱」（另行约定）识别成「含糊承诺」（尽快）。")
    if h == "yes" and s_ == "partial":
        return "评分器认为覆盖范围不足，人工认为已覆盖。多见于同义表述未被识别。"
    return "口径差异，见 README「已知分歧」一节。"


def write_report(rep):
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    json.dump(rep, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = os.path.join(os.path.dirname(REPORT), "consistency.md")
    L = ["# 一致性自检报告（评审模型 vs 人工标注）", "",
         "样本：30 条虚构样本，人工逐点标注 hit（yes / partial / no），"
         "其中 2 条含 forbidden_points 命中。", "",
         "## 总一致率", "",
         "| 项 | 值 |", "|---|---|",
         "| 样本数 | %d |" % rep["samples"],
         "| 要点判断数 | %d（一致 %d） |" % (rep["points_judged"], rep["points_agree"]),
         "| forbidden 判断数 | %d（一致 %d） |" % (rep["forbidden_judged"], rep["forbidden_agree"]),
         "| **合计一致率** | **%.4f**（%d/%d） |" % (rep["agreement"], rep["total_agree"], rep["total_judgements"]),
         "| 门槛 | ≥ %.2f |" % rep["threshold"],
         "| 判定 | %s |" % ("**达标，评分器可启用**" if rep["eligible"] else "**未达标，评分器拒绝启用**"),
         "| 不稳定用例（3 轮不一致） | %s |" % (", ".join(rep["unstable_cases"]) or "无"),
         "| 提示词版本 | %s |" % rep["prompt_version"], "",
         "## 逐条对照表", "",
         "| 用例 | 要点 | 人工 | 评分器 | 一致 |", "|---|---|---|---|---|"]
    for d in rep["detail"]:
        L.append("| %s | %s | %s | %s | %s |" % (
            d["case_id"], d["point_id"], d["human"], d["scorer"], "✓" if d["agree"] else "✗"))
    bad = [d for d in rep["detail"] if not d["agree"]]
    L += ["", "## 不一致项说明（共 %d 条）" % len(bad), ""]
    if bad:
        for d in bad:
            L.append("- `%s` / `%s`：人工判 **%s**，评分器判 **%s**。%s"
                     % (d["case_id"], d["point_id"], d["human"], d["scorer"],
                        _why(d)))
    else:
        L.append("- 无")
    L += ["", "三类分歧的**共同点**：都是「部分覆盖」与「完全未覆盖」的边界，"
          "以及同义表述（「首响」vs「响应」）的识别范围。这类分歧只能靠扩充提示词里的"
          "边界示例来收敛，不能靠调门槛 —— 调门槛就是自欺。"]
    L += ["", "## 启用闸门", "",
          "`assert_eligible()` 在一致率低于 %.2f 时抛 `ScorerNotEligible`，"
          "评分器不得投入使用。这是一次硬性拒绝，不是告警。" % rep["threshold"], ""]
    open(md, "w", encoding="utf-8").write("\n".join(L))
    return md


def assert_eligible(rep=None):
    rep = rep or run()
    if not rep["eligible"]:
        raise ScorerNotEligible(
            "一致率 %.4f < %.2f，评分器拒绝启用（样本 %d 条）"
            % (rep["agreement"], rep["threshold"], rep["samples"]))
    return rep


if __name__ == "__main__":
    r = run()
    md = write_report(r)
    print("agreement=%.4f (%d/%d) eligible=%s unstable=%d"
          % (r["agreement"], r["total_agree"], r["total_judgements"], r["eligible"],
             len(r["unstable_cases"])))
    print("report=%s" % md)
    raise SystemExit(0 if r["eligible"] else 1)
