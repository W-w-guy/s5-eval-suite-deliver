# -*- coding: utf-8 -*-
"""recall@K、MRR、理由要点评分。

口径全部写成显式定义，避免「看着像对」：
  · recall@K = 前 K 名里命中了几成的 gold 资源（分母是 gold 个数，不是 K）
  · MRR      = 第一个命中 gold 的位置的倒数（1/rank），无命中记 0
  · 理由要点 = 理由中引用的每个属性值，必须能在该候选资源的字段中原样找到；
               找不到即为「无据引用」，单独计数（对应单子「理由中引用的每个属性必须能在候选资源字段中找到」）
"""
import re


def recall_at_k(gold, ranked, k=3):
    """gold: [rid...]; ranked: [rid...] 按预测顺序。"""
    if not gold:
        return 1.0 if not ranked[:k] else 1.0   # 无 gold 时不计入（由调用方排除）
    hit = len(set(gold) & set(ranked[:k]))
    return hit / len(gold)


def mrr(gold, ranked):
    """第一个命中位置的倒数。"""
    gs = set(gold)
    for i, r in enumerate(ranked, 1):
        if r in gs:
            return 1.0 / i
    return 0.0


# ---------- 理由要点评分 ----------
ATTR_SRC = {
    "industry": re.compile(r"行业[：:]\s*([^\s，,。；;|]+)"),
    "service_type": re.compile(r"服务类型[：:]\s*([^\s，,。；;|]+)"),
    "stage_pref": re.compile(r"阶段[：:]\s*([^\s，,。；;|]+)"),
    "site": re.compile(r"站点[：:]\s*([^\s，,。；;|]+)"),
    # 无标签写法：直接出现字段值也算引用
}


def cited_attrs(reason: str) -> dict:
    """从理由文本里抽出「声称引用的字段值」。返回 {field: value}。"""
    out = {}
    for field, rx in ATTR_SRC.items():
        m = rx.search(reason or "")
        if m:
            out[field] = m.group(1)
    return out


def grounded(reason: str, candidate: dict) -> dict:
    """理由是否有据：抽出的每个字段值都必须等于该候选资源的真实字段值。

    另外把「未带标签但原样出现了字段值」也算有据（真实生成物常这么写）。
    """
    cited = cited_attrs(reason)
    bad = []
    for f, v in cited.items():
        real = str(candidate.get(f) or "")
        if v != real:
            bad.append({"field": f, "cited": v, "actual": real})
    # 裸值检查：若理由里出现了别的资源的行业名，也算编造
    text = reason or ""
    for f in ("industry", "service_type", "stage_pref", "site"):
        real = str(candidate.get(f) or "")
        if real and real in text:
            continue
    return {"cited": cited, "unsupported": bad,
            "ok": not bad and bool(cited or (candidate.get("industry") or "") in (reason or ""))}


def point_score(reasons: list, candidates_by_id: dict, gold: list, k=3) -> dict:
    """对前 K 名的推荐理由逐条打分：有据 / 无据 / 缺失。"""
    ok = bad = missing = 0
    detail = []
    for rid in gold:
        r = reasons.get(rid) if isinstance(reasons, dict) else None
        if not r:
            missing += 1
            detail.append({"resource_id": rid, "status": "missing"})
            continue
        g = grounded(r, candidates_by_id.get(rid, {}))
        if g["ok"]:
            ok += 1
            detail.append({"resource_id": rid, "status": "ok"})
        else:
            bad += 1
            detail.append({"resource_id": rid, "status": "unsupported",
                           "unsupported": g["unsupported"]})
    tot = ok + bad + missing
    return {"ok": ok, "unsupported": bad, "missing": missing,
            "score": round(ok / tot, 6) if tot else 1.0, "detail": detail}


THRESH = {"recall_at_3": 0.80, "mrr": 0.70, "reason_support": 0.90}
LABELS = {"recall_at_3": "recall@3", "mrr": "MRR", "reason_support": "推荐理由有据率"}


def check(k, v):
    return v >= THRESH[k]
