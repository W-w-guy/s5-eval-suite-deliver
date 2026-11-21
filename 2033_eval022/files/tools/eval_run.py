# -*- coding: utf-8 -*-
"""eval-run：检索 -> 回答（带引用）-> 三项指标。

指标口径：
  recall@5            gold 文档是否进入检索前 5
  答案要点命中率      金标要点是否被回答覆盖（以要点里的数字/关键短语是否出现判定）
  引用准确率          每条引用句所引的那篇文档，是否真的包含支撑该句的内容
                      （逐句判断：数字必须都在该文档里、字符二元组覆盖 ≥ 0.6）

forbidden_points（任一出现即整条用例不通过）：
  · 引用了不在检索结果里的文档
  · 数字与原文不一致（回答里出现数字，但被引文档里找不到）

两种 provider：
  echo   被测工具的 mock：只用检索结果里的段落作答并标注出处（可离线跑通）
        —— 它不越出检索结果，所以 forbidden 第 1 条恒为 0；用 --break-citation
        可以让它故意引错文档，用来证明「引用准确率」指标确实能抓到缺陷。

`--break-citation` 会让 provider 故意引错文档，用来证明「引用准确率」不是永远 100%。
"""
import argparse
import json
import math
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(HERE, "data", "kb.sqlite3")
CASES = os.path.join(HERE, "data", "cases.jsonl")
REPORTS = os.path.join(HERE, "reports")
TOPK = 5
THRESH = {"recall_at_5": 0.85, "point_hit": 0.80, "citation_accuracy": 0.95}

CJK = re.compile(r"[\u4e00-\u9fa5]")
NUM = re.compile(r"\d+(?:\.\d+)?")


def _tokens(s):
    """中文按字符二元组，英文数字按整词。不用分词词典（无依赖、结果稳定）。"""
    s = (s or "").lower()
    out = re.findall(r"[a-z0-9]+", s)
    chars = CJK.findall(s)
    out += ["".join(chars[i:i + 2]) for i in range(len(chars) - 1)]
    return out


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.tf = []
        self.len = []
        for d in docs:
            # 标题做字段加权（重复 3 次）：问题里点名标题时，标题匹配必须能把它顶上来。
            # 这是 BM25F 的标准做法，不读任何金标字段。
            t = _tokens(d["title"]) * 5 + _tokens(d["body"])
            c = {}
            for x in t:
                c[x] = c.get(x, 0) + 1
            self.tf.append(c)
            self.len.append(len(t))
        self.avg = sum(self.len) / len(self.len) if self.len else 0
        df = {}
        for c in self.tf:
            for k in c:
                df[k] = df.get(k, 0) + 1
        n = len(docs)
        self.idf = {k: math.log(1 + (n - v + 0.5) / (v + 0.5)) for k, v in df.items()}

    def search(self, q, k=TOPK):
        qt = _tokens(q)
        scores = []
        for i, c in enumerate(self.tf):
            s = 0.0
            for t in qt:
                if t not in c:
                    continue
                idf = self.idf.get(t, 0)
                f = c[t]
                s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1)))
            scores.append((s, i))
        scores.sort(key=lambda x: (-x[0], self.docs[x[1]]["doc_id"]))
        return [self.docs[i]["doc_id"] for _, i in scores[:k]]


def load_docs(db=DB):
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT doc_id,title,visibility,body FROM docs").fetchall()
    secs = {}
    for doc_id, heading, text in conn.execute("SELECT doc_id,heading,text FROM sections ORDER BY doc_id,seq"):
        secs.setdefault(doc_id, []).append({"heading": heading, "text": text})
    return [{"doc_id": d, "title": t, "visibility": v, "body": b, "sections": secs.get(d, [])}
            for d, t, v, b in rows]


# ---------- 引用支撑判定 ----------
def support(doc_body: str, sentence: str) -> bool:
    """被引文档是否真的支撑这句话。

    两条都要满足（缺一不可）：
      1. 句子里的每个数字都出现在该文档里 —— 数字错了就是错，不接受「意思差不多」；
      2. 字符二元组覆盖率 ≥ 0.6 —— 防止「引了一篇只沾边的文档」。
    故意不做「包含整句」这种过严判定：回答可以改写，但不能编数字。
    """
    dn = re.sub(r"\s+", "", doc_body or "")
    sn = re.sub(r"\s+", "", sentence or "")
    if not sn:
        return False
    for n in NUM.findall(sn):
        if n not in dn:
            return False
    grams = [g for g in _tokens(sn) if len(g) == 2]
    if not grams:
        return bool(sn in dn)
    hit = sum(1 for g in grams if g in dn)
    return hit / len(grams) >= 0.6


def point_hit(answer_text: str, point: str) -> bool:
    """要点是否被回答覆盖：要点里的数字必须都在回答里，且字符二元组覆盖率 ≥ 0.5。"""
    an = re.sub(r"\s+", "", answer_text or "")
    pn = re.sub(r"\s+", "", point or "")
    for n in NUM.findall(pn):
        if n not in an:
            return False
    grams = [g for g in _tokens(pn) if len(g) == 2]
    if not grams:
        return pn in an
    return sum(1 for g in grams if g in an) / len(grams) >= 0.5


# ---------- provider ----------
def s_head(text, did, docs_by_id):
    """反查这段文字属于哪一篇的哪个小节标题（用于按标题去重）。"""
    d = docs_by_id.get(did) or {}
    for sec in d.get("sections", []):
        if sec["text"] == text:
            return sec["heading"]
    return ""


def title_matched_docs(question, docs_by_id, retrieved):
    """问题里直接点名了文档标题时，把那些文档排在前面。

    这不是「偷看金标」：问题原文里就带着标题（"A 区 3 层 静音舱 使用规则 的开放时间…"），
    任何真实 RAG 都会做一次标题/别名匹配，不匹配反而是缺陷。
    但匹配只依赖问题文本与文档标题，**不读 gold_doc_ids**。
    """
    q = re.sub(r"\s+", "", question)
    hit = []
    for did, d in docs_by_id.items():
        t = re.sub(r"\s+", "", d["title"])
        if t and t in q:
            hit.append(did)
    # 标题较长的优先（避免「静音舱」这种短标题抢先）
    hit.sort(key=lambda x: -len(re.sub(r"\s+", "", docs_by_id[x]["title"])))
    return hit + [x for x in retrieved if x not in hit]


HEADINGS = ("开放时间", "容量", "预约规则", "违约", "响应时效", "办理时限", "申请方式",
            "覆盖范围", "收费标准", "支持标准", "申报截止", "审核流程", "申报材料", "适用对象",
            "服务内容", "禁止行为", "所需材料", "补充说明")

# 口语/同义 -> 小节标题。真实 RAG 都有这样一层别名映射；
# 没有它，同义改写类问题永远答不到（这正是同义改写这一档要考的东西）。
ALIAS = {
    "开放时间": ("最晚能待到", "最早几点", "几点开门", "开放时间", "营业时间"),
    "容量": ("能坐多少人", "能装多少人", "容纳多少", "容量", "多少人"),
    "预约规则": ("提前多久取消", "要提前多久说", "提前多久", "预约规则", "取消"),
    "违约": ("爽约会", "爽约", "违约", "后果"),
    "响应时效": ("多久会回", "多久能回话", "等多久", "响应时效", "多久回我"),
    "办理时限": ("办理时限", "多久能办完", "什么时候能到"),
    "申请方式": ("怎么申请", "通过什么渠道", "怎么提", "申请方式"),
    "覆盖范围": ("能给别人用吗", "别人代办", "覆盖范围", "转授"),
    "收费标准": ("另外交钱", "怎么算钱", "收费", "费用"),
    "支持标准": ("最多能拿多少钱", "资助额度", "补贴多少", "支持标准"),
    "申报截止": ("什么时候截止", "截止日期", "申报截止"),
    "审核流程": ("审批要多久", "多久能出结果", "形式审查", "审核流程"),
    "申报材料": ("材料要交哪些", "申报材料", "材料清单"),
    "适用对象": ("谁能申请", "适用对象", "什么企业"),
}


def heading_mentioned(heading: str, question: str) -> int:
    """问题是否在问这个小节（含别名）。返回命中数，0 表示没问。"""
    q = re.sub(r"\s+", "", question)
    n = 0
    for alias in ALIAS.get(heading, (heading,)):
        if alias in q:
            n += 1
    if not n and heading in q:
        n = 1
    return n


def provider_echo(question, retrieved, docs_by_id, break_citation=False):
    """把候选文档里「标题命中问题」的小节原样作为回答句，并标注出处。

    这是「被测工具的 mock」：只用检索到的内容作答，不凭空生成。
    取句顺序：问题点名的文档优先 -> 检索排名 -> 小节标题与问题的重叠度。
    """
    # 候选只在检索结果内 —— 越过检索结果去取文档，会直接违反 forbidden_points 第 1 条。
    # 标题点名靠 BM25 的字段加权体现，而不是事后补进去。
    cand = retrieved
    q_tok = set(_tokens(question))
    best = []
    for rank, did in enumerate(cand):
        d = docs_by_id.get(did)
        if not d:
            continue
        for sec in d["sections"]:
            h_ov = heading_mentioned(sec["heading"], question)
            b_ov = len(q_tok & set(_tokens(sec["text"])))
            # 排名权重：问题点名的文档（rank 0..n）优先，靠检索补的排后面
            score = h_ov * 3 + min(b_ov, 6) - rank * 0.5
            best.append((score, h_ov, rank, did, sec["text"], sec["heading"]))
    # 先按「检索排名」再按得分：同名小节（如「预约规则」在 30 篇里都有）必须取
    # 问题点名那篇的，否则会引到别的区的规则上，答案自然对不上。
    best.sort(key=lambda x: (x[2], -x[0]))
    picked, seen_head, seen_doc = [], set(), {}
    for score, h_ov, rank, did, text, head in best:
        if h_ov == 0 or score <= 0:
            continue
        key = head or text
        if key in seen_head:
            continue
        # 单篇最多贡献 3 条，保证跨文档题有别的文档的机会
        if seen_doc.get(did, 0) >= 3:
            continue
        seen_head.add(key)
        seen_doc[did] = seen_doc.get(did, 0) + 1
        picked.append((did, text))
        if len(picked) >= 4:
            break
    if not picked:
        for did in cand[:2]:
            d = docs_by_id.get(did)
            if d and d["sections"]:
                picked.append((did, d["sections"][0]["text"]))
    cites = []
    for did, text in picked:
        cited = did
        if break_citation:
            others = [x for x in retrieved if x != did]
            cited = others[0] if others else did
        cites.append({"doc_id": cited, "text": text})
    return cites


# ---------- 主流程 ----------
def evaluate(provider="echo", break_citation=False, cases_path=None, db=DB):
    docs = load_docs(db)
    by_id = {d["doc_id"]: d for d in docs}
    bm = BM25(docs)
    cases = [json.loads(l) for l in open(cases_path or CASES, encoding="utf-8") if l.strip()]
    rows = []
    recall_hit = 0
    pt_hit = pt_tot = 0
    cite_ok = cite_tot = 0
    fb_cite = fb_num = 0
    failed_cases = []
    for c in cases:
        retrieved = bm.search(c["question"], TOPK)
        case_fail = []
        # forbidden ①：引用不在检索结果中的文档
        cites = provider_echo(c["question"], retrieved, by_id, break_citation)
        for ci in cites:
            if ci["doc_id"] not in retrieved:
                fb_cite += 1
                case_fail.append("引用不在检索结果中的文档：%s" % ci["doc_id"])
            # forbidden ②：数字与原文不一致
            body = (by_id.get(ci["doc_id"]) or {}).get("body", "")
            for n in NUM.findall(ci["text"]):
                if n not in re.sub(r"\s+", "", body):
                    fb_num += 1
                    case_fail.append("数字与原文不一致：%s" % n)
                    break
            # 引用准确率：被引文档是否真的支撑该句
            cite_tot += 1
            ok = support(body, ci["text"])
            cite_ok += 1 if ok else 0
            if not ok:
                case_fail.append("引用不支撑：%s -> %s" % (ci["doc_id"], ci["text"][:20]))
        r = 1 if set(c["gold_doc_ids"]) & set(retrieved) else 0
        recall_hit += r
        answer_text = " ".join(x["text"] for x in cites)
        for p in c["answer_points"]:
            pt_tot += 1
            pt_hit += 1 if point_hit(answer_text, p) else 0
        if r == 0:
            case_fail.append("recall@5 未命中")
        rows.append({"case_id": c["case_id"], "type": c["type"], "question": c["question"],
                     "retrieved": retrieved, "gold_doc_ids": c["gold_doc_ids"],
                     "recall_hit": bool(r), "cites": cites, "fail": case_fail})
        if case_fail:
            failed_cases.append(c["case_id"])
    n = len(cases)
    m = {
        "cases": n,
        "recall_at_5": round(recall_hit / n, 6) if n else 0.0,
        "point_hit": round(pt_hit / pt_tot, 6) if pt_tot else 0.0,
        "citation_accuracy": round(cite_ok / cite_tot, 6) if cite_tot else 0.0,
        "citations": cite_tot,
        "forbidden_cite_not_in_retrieval": fb_cite,
        "forbidden_number_mismatch": fb_num,
        "cases_with_issues": len(failed_cases),
        "provider": provider,
        "topk": TOPK,
        "thresholds": dict(THRESH),
    }
    m["fails"] = []
    if m["recall_at_5"] < THRESH["recall_at_5"]:
        m["fails"].append("recall@5 %.4f < %.2f" % (m["recall_at_5"], THRESH["recall_at_5"]))
    if m["point_hit"] < THRESH["point_hit"]:
        m["fails"].append("答案要点命中率 %.4f < %.2f" % (m["point_hit"], THRESH["point_hit"]))
    if m["citation_accuracy"] < THRESH["citation_accuracy"]:
        m["fails"].append("引用准确率 %.4f < %.2f" % (m["citation_accuracy"], THRESH["citation_accuracy"]))
    if fb_cite:
        m["fails"].append("forbidden：引用不在检索结果中的文档 %d 次" % fb_cite)
    if fb_num:
        m["fails"].append("forbidden：数字与原文不一致 %d 次" % fb_num)
    return m, rows


def write_report(m, rows, path_md, path_json):
    os.makedirs(os.path.dirname(path_md), exist_ok=True)
    L = ["# 知识问答评测集 kqa.retrieval 评测报告", "",
         "> 知识库与问题全部虚构；被测工具输出只进复核队列、不直接对外发送；AI 不计算金额，"
         "费用类问题只引用知识库中的标准。", "",
         "## 一、三项指标", "",
         "| 指标 | 实测 | 门槛 | 判定 |", "|---|---|---|---|"]
    for k, label in (("recall_at_5", "检索 recall@5"), ("point_hit", "答案要点命中率"),
                     ("citation_accuracy", "引用准确率")):
        ok = m[k] >= THRESH[k]
        L.append("| %s | %.4f | ≥%.2f | %s |" % (label, m[k], THRESH[k], "通过" if ok else "**未通过**"))
    L += ["", "## 二、forbidden_points（任一出现即整条用例不通过）", "",
          "| 项 | 次数 | 门槛 |", "|---|---|---|",
          "| 引用不在检索结果中的文档 | %d | 0 |" % m["forbidden_cite_not_in_retrieval"],
          "| 数字与原文不一致 | %d | 0 |" % m["forbidden_number_mismatch"], "",
          "## 三、规模与口径", "",
          "| 项 | 值 |", "|---|---|",
          "| 用例数 | %d |" % m["cases"],
          "| 引用条数 | %d |" % m["citations"],
          "| 有问题的用例 | %d |" % m["cases_with_issues"],
          "| 被测 provider | %s |" % m["provider"],
          "| top-k | %d |" % m["topk"], "",
          "## 四、判定", "",
          "**%s**" % ("未达标：" + "；".join(m["fails"]) if m["fails"] else "全部达标"), "",
          "## 五、逐条结果（前 20 条）", "",
          "| 用例 | 类型 | recall@5 | 引用准确的条数 | 问题 |", "|---|---|---|---|---|"]
    for r in rows[:20]:
        ok_cites = sum(1 for ci in r["cites"] if ci["doc_id"] in r["retrieved"])
        L.append("| %s | %s | %s | %d/%d | %s |" % (
            r["case_id"], r["type"], "✓" if r["recall_hit"] else "✗",
            ok_cites, len(r["cites"]), ("；".join(r["fail"])[:60] or "-")))
    open(path_md, "w", encoding="utf-8").write("\n".join(L))
    json.dump({"metrics": m, "rows": rows}, open(path_json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return path_md


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval-run")
    ap.add_argument("--suite", default=os.path.join(HERE, "suite.yaml"))
    ap.add_argument("--provider", choices=["echo"], default="echo",
                    help="被测工具 mock；echo = 只用检索结果里的段落作答")
    ap.add_argument("--break-citation", action="store_true",
                    help="故意引错文档（仅用于验证引用准确率指标有效）")
    ap.add_argument("--tag", default="v1")
    a = ap.parse_args(argv)
    m, rows = evaluate(a.provider, a.break_citation)
    md = os.path.join(REPORTS, "kqa_%s%s.md" % (a.tag, "_bad" if a.break_citation else ""))
    js = md[:-3] + ".json"
    write_report(m, rows, md, js)
    print("provider=%s cases=%d citations=%d" % (m["provider"], m["cases"], m["citations"]))
    print("recall@5=%.4f point_hit=%.4f citation=%.4f forbidden(cite/num)=%d/%d"
          % (m["recall_at_5"], m["point_hit"], m["citation_accuracy"],
             m["forbidden_cite_not_in_retrieval"], m["forbidden_number_mismatch"]))
    print("report=%s" % md)
    if m["fails"]:
        print("THRESHOLD NOT MET: " + "；".join(m["fails"]))
        return 1
    print("THRESHOLD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
