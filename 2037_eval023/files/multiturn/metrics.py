# -*- coding: utf-8 -*-
"""指标层：多轮对话评测（#2037）。

三项指标（对应单子的评分口径）：
  final_point_hit     最后一轮答案要点命中率（每组按要点评分）
  checkpoint_pass     中间关键轮次（must 要点）的通过率
  forbidden_violation 违反 forbidden_points 的次数（沿用错误前提 / 话题串味）

★ 第三个指标是「反例指标」：它不是越高越好，必须为 0。
   只看前两个指标，一个「每轮都把上一轮答案再抄一遍」的实现也能拿高分 ——
   那正是单子 forbidden_points 要禁的行为。
"""
from __future__ import annotations

import re

THRESH = {
    "final_point_hit": 0.80,
    "checkpoint_pass": 1.00,
}
FORBIDDEN_LIMIT = 0          # 必须为 0

LABELS = {
    "final_point_hit": "最后一轮要点命中率",
    "checkpoint_pass": "中间检查点通过率",
    "forbidden_violations": "forbidden 违反次数",
}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def point_hit(point: str, answer: str) -> bool:
    """要点命中：要点里的数字都要出现，且字符二元组覆盖 >= 0.5。

    对空要点返回 True（没有要点等于没有可失分的项）。
    """
    pn, an = norm(point), norm(answer)
    if not pn:
        return True
    for n in re.findall(r"\d+(?:\.\d+)?", pn):
        if n not in an:
            return False
    chars = re.findall(r"[\u4e00-\u9fa5]", pn)
    grams = {"".join(chars[i:i + 2]) for i in range(len(chars) - 1)}
    if not grams:
        return pn in an
    return sum(1 for g in grams if g in an) / len(grams) >= 0.5


def final_point_hit_rate(case: dict, answer: str) -> dict:
    pts = (case.get("final_expect") or {}).get("answer_points") or []
    hits = [p for p in pts if point_hit(p, answer)]
    return {"total": len(pts), "hit": len(hits),
            "value": round(len(hits) / len(pts), 6) if pts else 1.0,
            "missed": [p for p in pts if p not in hits]}


def checkpoint_pass_rate(case: dict, turn_outputs: dict) -> dict:
    """turn_outputs: {turn_index: 答案文本}。检查点轮必须命中它的 must_points。"""
    cps = [(i, t) for i, t in enumerate(case.get("turns") or []) if t.get("checkpoint")]
    if not cps:
        return {"total": 0, "ok": 0, "value": 1.0, "failed": []}
    failed = []
    for i, t in cps:
        ans = turn_outputs.get(i, "")
        bad = [p for p in (t.get("must_points") or []) if not point_hit(p, ans)]
        if bad:
            failed.append({"turn": i, "missed": bad})
    return {"total": len(cps), "ok": len(cps) - len(failed),
            "value": round((len(cps) - len(failed)) / len(cps), 6), "failed": failed}


def forbidden_violations(case: dict, turn_outputs: dict) -> list:
    """检查 forbidden_points。

    三类判定（与用例里的 type 对应）：
      stale_premise / stale_premise_value —— 纠正后仍出现旧实体的值
      topic_bleed                        —— 当前回答里混入上一话题的答案
      wrong_entity / stale_condition     —— 这里只做「关键词出现」的粗查，
                                            精查需要语义模型（已写进局限）
    """
    out = []
    all_ans = " ".join(str(v) for v in (turn_outputs or {}).values())
    # 纠正类只看「纠正之后」的轮次：纠正前的轮次出现旧值是正确的
    last_correction = -1
    for i, t in enumerate(case.get("turns") or []):
        txt = t.get("text") or ""
        if t.get("role") == "user" and ("不是这个" in txt or "我说的是" in txt):
            last_correction = i
    # ★ 纠正轮**自己**的答案也必须在「纠正之后」的范围内：
    #   用户说完「不是这个，是 B」以后，本轮回答就应当按 B 作答。
    #   写成 `i > last_correction` 会把纠正轮本身排除掉，于是纠正轮答错也发现不了
    #   （实测：单测里纠正轮的违规被漏检）。
    after = {i: v for i, v in (turn_outputs or {}).items() if i >= last_correction}
    after_txt = " ".join(str(v) for v in after.values())
    for fb in (case.get("forbidden_points") or []):
        t = fb.get("type", "")
        if t in ("stale_premise_value",):
            v = fb.get("wrong_value") or ""
            if v and norm(v) in norm(after_txt):
                out.append({"type": t, "desc": fb.get("desc"), "found": v})
        elif t in ("stale_premise",):
            e = fb.get("wrong_entity") or ""
            # 纠正后仍提到旧实体（且不是在被纠正的那一轮复述里）
            if e and norm(e) in norm(after_txt):
                out.append({"type": t, "desc": fb.get("desc"), "found": e})
        elif t == "topic_bleed":
            # 混入上一话题：看当前轮答案里是否出现了别的文档 id
            if "FAQ-" in after_txt or "FQ-" in after_txt:
                out.append({"type": t, "desc": fb.get("desc"), "found": "其他话题内容"})
    return out


def aggregate(rows: list) -> dict:
    n = len(rows)
    m = {"cases": n}
    for k in THRESH:
        m[k] = round(sum(r.get(k, 0.0) for r in rows) / n, 6) if n else 0.0
    m["forbidden_violations"] = sum(len(r.get("violations") or []) for r in rows)
    m["thresholds"] = dict(THRESH)
    m["forbidden_limit"] = FORBIDDEN_LIMIT
    m["fails"] = []
    for k in THRESH:
        if m[k] < THRESH[k]:
            m["fails"].append("%s %.4f < %.2f" % (LABELS[k], m[k], THRESH[k]))
    if m["forbidden_violations"] > FORBIDDEN_LIMIT:
        m["fails"].append("forbidden 违反 %d 次（要求 0）" % m["forbidden_violations"])
    return m
