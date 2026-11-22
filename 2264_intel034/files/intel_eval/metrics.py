# -*- coding: utf-8 -*-
"""11 项指标 + 相似度与 NDCG 等基础函数。

每个函数只做一件事，且都能被「手算用例」逐一验证（AC4 要求每个指标 ≥2 个手算用例）。
"""
import math
import re

URL_RE = re.compile(r"https?://\S+|www\.\S+")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
LANDLINE_RE = re.compile(r"(?<!\d)0\d{2,3}-\d{7,8}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
DATE_RE = re.compile(r"(\d{4})\s*[年\-/]\s*(\d{1,2})\s*[月\-/]\s*(\d{1,2})")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")


# ---------------- 基础 ----------------
def norm_text(s: str) -> str:
    """统一空白与全半角标点，供相似度比较。"""
    s = (s or "").replace("\u3000", " ")
    s = re.sub(r"[，,、；;：:]", " ", s)
    s = re.sub(r"[。．.！!？?]", " ", s)
    # 空白一律删除（而不是压成一个空格）：只做「同一句话有无空格」的归一化，
    # 否则 "a，b。c" 归一化后是 "a b c"（5 字），与 "abc"（3 字）比相似度会凭空掉到 0.75。
    return re.sub(r"\s+", "", s)


def text_similarity(a: str, b: str) -> float:
    """归一化字符级 LCS 比例 = 2*LCS / (len(a)+len(b))。

    为什么不用 difflib.SequenceMatcher.ratio()：它基于最长匹配块总数，
    当提取结果把整段正文丢掉、只留一句时仍可能给出 0.5 以上的分。
    LCS 比例在这种「大面积缺失」上掉得更实。
    """
    a, b = norm_text(a), norm_text(b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    n, m = len(a), len(b)
    if n * m > 4_000_000:                     # 太长时退化为前缀比例，避免 O(n*m) 爆内存
        k = 0
        while k < min(n, m) and a[k] == b[k]:
            k += 1
        return 2 * k / (n + m)
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        ai = a[i - 1]
        for j in range(1, m + 1):
            cur[j] = prev[j - 1] + 1 if ai == b[j - 1] else (prev[j] if prev[j] >= cur[j - 1] else cur[j - 1])
        prev = cur
    return 2 * prev[m] / (n + m)


def pairwise_f1(gold_groups: list, pred_groups: list) -> dict:
    """归组 pair 级 F1。gold_groups / pred_groups 均为 [{id: set(成员)}]。

    按「同一组内任意两点算一对」展开成 pair 集合，再算 P/R/F1。
    误合并（merge_errors）= 预测的同组 pair 里，金标中不同组的对数。
    """
    def pairs(groups):
        s = set()
        for g in groups:
            m = sorted(g)
            for i in range(len(m)):
                for j in range(i + 1, len(m)):
                    s.add((m[i], m[j]))
        return s

    gp, pp = pairs(gold_groups), pairs(pred_groups)
    tp = len(gp & pp)
    p = tp / len(pp) if pp else 0.0
    r = tp / len(gp) if gp else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 6), "recall": round(r, 6), "f1": round(f1, 6),
            "tp": tp, "gold_pairs": len(gp), "pred_pairs": len(pp),
            "merge_errors": len(pp - gp)}


def ndcg_at_k(gold_rank: list, pred_rank: list, k: int = 5) -> float:
    """NDCG@k，相关性取金标名次（越高越相关），指数增益 2^rel - 1。"""
    rel = {d: (len(gold_rank) - i) for i, d in enumerate(gold_rank)}
    def dcg(seq):
        s = 0.0
        for i, d in enumerate(seq[:k], 1):
            r = rel.get(d, 0)
            s += (2 ** r - 1) / math.log2(i + 1)
        return s
    ideal = dcg(gold_rank)
    if ideal == 0:
        return 1.0 if not pred_rank else 0.0
    return round(dcg(pred_rank) / ideal, 6)


def pii_hits(text: str) -> list:
    """联系方式残留：手机号 / 座机 / 邮箱。占位写法（含 X 与 example 域名）不算。"""
    out = []
    for m in PHONE_RE.finditer(text or ""):
        out.append(("mobile", m.group(0)))
    for m in LANDLINE_RE.finditer(text or ""):
        seg = m.group(0)
        if "X" in seg.upper():
            continue
        out.append(("landline", seg))
    for m in EMAIL_RE.finditer(text or ""):
        out.append(("email", m.group(0)))
    return out


def urls_in(text: str) -> list:
    return URL_RE.findall(text or "")


def dates_in(text: str) -> list:
    return ["%04d-%02d-%02d" % (int(a), int(b), int(c)) for a, b, c in DATE_RE.findall(text or "")]


def numbers_in(text: str) -> list:
    return NUM_RE.findall(text or "")


# ---------------- 11 项指标 ----------------
def m01_body_similarity(pairs: list) -> float:
    """正文提取平均相似度。pairs = [(提取正文, 黄金正文)]"""
    if not pairs:
        return 0.0
    return round(sum(text_similarity(a, b) for a, b in pairs) / len(pairs), 6)


def m02_publish_date_accuracy(pairs: list) -> float:
    """发布日期准确率。pairs = [(预测日期, 金标日期)]，金标 _abstain 的不计入分母。"""
    pairs = [(a, b) for a, b in pairs if b and b != "_abstain"]
    if not pairs:
        return 1.0
    return round(sum(1 for a, b in pairs if a == b) / len(pairs), 6)


def m03_group_f1(gold_groups: list, pred_groups: list) -> dict:
    return pairwise_f1(gold_groups, pred_groups)


def m04_policy_type_accuracy(pairs: list) -> float:
    pairs = [(a, b) for a, b in pairs if b and b != "_abstain"]
    if not pairs:
        return 1.0
    return round(sum(1 for a, b in pairs if a == b) / len(pairs), 6)


def m05_deadline_accuracy(pairs: list) -> float:
    pairs = [(a, b) for a, b in pairs if b and b != "_abstain"]
    if not pairs:
        return 1.0
    return round(sum(1 for a, b in pairs if a == b) / len(pairs), 6)


def m06_key_fact_coverage(pairs: list) -> float:
    """摘要关键事实覆盖率。pairs = [(摘要, [关键事实原文...])]

    一条关键事实算覆盖 = 它的「数字/日期成分」全部出现在摘要里。
    只比字面包含会太松（摘要里出现「按照比例」就算命中），所以要求数字与日期一致。
    """
    total = hit = 0
    for summary, facts in pairs:
        for f in (facts or []):
            if not f or f == "_abstain":
                continue
            total += 1
            toks = set(dates_in(f)) | set(numbers_in(f))
            if not toks:
                if norm_text(f)[:20] in norm_text(summary):
                    hit += 1
                continue
            if all((t in summary) for t in toks):
                hit += 1
    return round(hit / total, 6) if total else 1.0


def m07_numeric_mismatch_flagged(cases: list) -> float:
    """摘要中与原文不一致的数字/日期被核对项标出的比例。

    cases = [{summary, body, flagged:[...]}]。先算出「应标出」的项：
    摘要里出现、但原文里找不到的日期与数字。再算其中被 flagged 覆盖的比例。
    """
    need = flagged = 0
    for c in cases:
        s, b = c["summary"], c["body"]
        bad_dates = [x for x in dates_in(s) if x not in b]
        # 先剔除已判过的日期串再抽数字，否则 "2026-01-01" 会被拆成 2026/01/01 重复计数。
        s_wo_dates = DATE_RE.sub(" ", s)
        bad_nums = [x for x in numbers_in(s_wo_dates) if x not in b]
        bad = bad_dates + bad_nums
        fl = set(c.get("flagged") or [])
        for x in bad:
            need += 1
            if x in fl:
                flagged += 1
    return round(flagged / need, 6) if need else 1.0


def m08_no_link_into_queue(entries: list) -> int:
    """无原文链接却进了核对队列的条目数（应为 0）。entries = [{has_original_link, queued}]"""
    return sum(1 for e in entries if (not e.get("has_original_link")) and e.get("queued"))


def m09_robots_violations(fetcher) -> int:
    return fetcher.robots_violations()


def m10_urls_in_summary(summaries: list) -> int:
    return sum(len(urls_in(s)) for s in summaries)


def m11_pii_residue(texts: list) -> int:
    return sum(len(pii_hits(t)) for t in texts)


THRESHOLDS = {
    "body_similarity": (">=", 0.95),
    "publish_date_accuracy": (">=", 0.98),
    "group_f1": (">=", 0.95),
    "merge_errors": ("==", 0),
    "policy_type_accuracy": (">=", 0.85),
    "deadline_accuracy": (">=", 0.90),
    "key_fact_coverage": (">=", 0.80),
    "numeric_flagged_ratio": ("==", 1.0),
    "no_link_into_queue": ("==", 0),
    "robots_violations": ("==", 0),
    "urls_in_summary": ("==", 0),
    "pii_residue": ("==", 0),
}
LABELS = {
    "body_similarity": "正文提取平均相似度",
    "publish_date_accuracy": "发布日期准确率",
    "group_f1": "转载归组 F1",
    "merge_errors": "误合并数",
    "policy_type_accuracy": "policy_type 准确率",
    "deadline_accuracy": "截止日期准确率",
    "key_fact_coverage": "摘要关键事实覆盖率",
    "numeric_flagged_ratio": "不一致数字/日期被标出比例",
    "no_link_into_queue": "无原文链接进入核对队列数",
    "robots_violations": "robots 禁止路径被抓取数",
    "urls_in_summary": "摘要含 URL 数",
    "pii_residue": "送模型文本联系方式残留",
}


def check_threshold(key: str, value) -> bool:
    op, th = THRESHOLDS[key]
    if op == ">=":
        return value >= th
    if op == "<=":
        return value <= th
    return value == th
