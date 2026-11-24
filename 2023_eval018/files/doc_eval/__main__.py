# -*- coding: utf-8 -*-
"""文档自动化评测 runner。

链路：载体读取（docx / PDF 文字层 / 扫描件 OCR 桩）-> 被测工具（echo mock，正则抽取）
-> 自检标红 -> 指标（字段准确率 / 错字段标红召回 / 错而未标红的 critical）-> 报告。

--break-flag      识别错了却不标红（模拟"只输出值、不做自检"）
--break-accuracy  故意抽错日期写法
两者用于证明指标能抓到缺陷（可证伪）。
"""
import argparse, json, os, re, sys, zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from doc_eval import metrics as M

DATA = os.path.join(HERE, "data", "cases.jsonl")
PLAIN = os.path.join(HERE, "data", "plain")
REPORTS = os.path.join(HERE, "reports")

RULES = {
    "contract_no": [r"合同编号[：:]\s*(\S+)", r"^合同\s+(\S+)\s*$"],
    "party_a_name": [r"甲方（采购方）[：:]\s*(\S+)", r"甲方[：:]\s*([^（\n]+?)（"],
    "party_a_code": [r"甲方统一社会信用代码[：:]\s*(\S+)", r"甲方[：:]\s*\S+?（(\d{18})）"],
    "party_b_name": [r"乙方（服务提供方）[：:]\s*(\S+)", r"乙方[：:]\s*([^（\n]+?)（"],
    "party_b_code": [r"乙方统一社会信用代码[：:]\s*(\S+)", r"乙方[：:]\s*\S+?（(\d{18})）"],
    "service_start": [r"服务期限[：:]\s*(\d{4}-\d{2}-\d{2})", r"服务期\s*(\d{4}-\d{2}-\d{2})\s*至"],
    "service_end": [r"至\s*(\d{4}-\d{2}-\d{2})"],
    "amount_ex_tax": [r"不含税金额[：:]\s*([\d,\.]+)", r"不含税\s*([\d,\.]+)\s*元\s*税率",
                      r"\|\s*本期服务费[^|]*\|\s*([\d,\.]+)\s*\|"],
    "tax_rate": [r"税率[：:]\s*(\d+)", r"税率\s*(\d+)%", r"\|\s*本期服务费[^|]*\|[^|]*\|\s*(\d+)%"],
    "amount_tax": [r"税额[：:]\s*([\d,\.]+)", r"税额\s*([\d,\.]+)\s*元",
                   r"\|\s*本期服务费[^|]*\|[^|]*\|[^|]*\|\s*([\d,\.]+)\s*\|"],
    "amount_total": [r"含税总金额（小写）[：:]\s*([\d,\.]+)", r"含税\s*([\d,\.]+)\s*元$",
                     r"\|\s*本期服务费[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*([\d,\.]+)\s*\|"],
    "payment_terms": [r"付款方式[：:]\s*(.+)", r"付款[：:]\s*(.+)"],
    "sign_date": [r"签订日期[：:]\s*(\S+)", r"签订\s*(\d{4}-\d{2}-\d{2})"],
    "page_count": [r"合同页数[：:]\s*(\d+)\s*页", r"共\s*(\d+)\s*页"],
}

CRITICAL_NAMES = ("party_a_code", "party_b_code", "amount_total", "amount_ex_tax",
                  "service_start", "service_end")


def load_cases():
    return [json.loads(l) for l in open(DATA, encoding="utf-8") if l.strip()]


def _docx_text(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def read_contract(c):
    """按载体读取正文。扫描件没有文字层，走 OCR 桩（读取与位图同源的文本）。"""
    path = os.path.join(HERE, c["file"].replace("/", os.sep))
    if c["carrier"] == "docx":
        return _docx_text(path), "docx"
    if c["carrier"] == "text_pdf":
        try:
            import pypdf
            return pypdf.PdfReader(path).pages[0].extract_text(), "pdf_text"
        except Exception:
            raise SystemExit("读取 text_pdf 需要 pypdf：pip install pypdf")
    # scanned_pdf：真实 OCR 不在本评测集范围内，用与渲染源同源的文本模拟 OCR 输出
    with open(os.path.join(PLAIN, c["case_id"] + ".txt"), encoding="utf-8") as f:
        return f.read(), "ocr_stub"


def _campaign(rx, text):
    """返回该正则的全部候选值（去重、保序）——用于判定字段是否歧义。"""
    seen = []
    for m in rx.finditer(text):
        v = m.group(1).strip()
        if v not in seen:
            seen.append(v)
    return seen


def extract(text, break_accuracy=False):
    """每条字段按规则链依次尝试，取【第一条有命中】的规则的全部候选值。"""
    out, cand = {}, {}
    for f, pats in RULES.items():
        vs = []
        for pat in pats:
            vs = _campaign(re.compile(pat, re.M), text)
            if vs:
                break
        cand[f] = vs
        out[f] = vs[0] if vs else None
    out["seal_present"] = ("盖章：有" in text) or bool(re.search(r"盖章\s+有", text))
    if break_accuracy and out.get("service_start"):
        out["service_start"] = out["service_start"].replace("-03", "-04")
    return out, cand


def self_check(pred, cand, text):
    """保守自检：哪些字段应被标红。

    规则（通用，不含任何按用例名硬编码的判断）：
      · 关键字段为空 -> 标红
      · 信用代码不是 18 位或第 3-8 位不是 999999（本套件虚构约定）-> 标红
      · 含税总额 != 不含税 + 税额 -> 标红 amount_total
      · 同一字段在正文里有多个不同候选值（歧义）-> 标红该字段
      · 印章缺失 -> 标红
    """
    flagged = set()
    for f in ("contract_no", "party_a_code", "party_b_code", "amount_total",
              "service_start", "service_end", "page_count"):
        if not pred.get(f):
            flagged.add(f)
    for f in ("party_a_code", "party_b_code"):
        v = pred.get(f) or ""
        if len(v) != 18 or v[2:8] != "999999" or not re.fullmatch(r"[0-9A-Z]{18}", v):
            flagged.add(f)
    for f in cand:
        if len(cand.get(f) or []) > 1:
            flagged.add(f)
    for f in list(RULES) + ["seal_present"]:
        if not pred.get(f):
            flagged.add(f)
    for f, v in pred.items():
        if isinstance(v, str) and re.search(r"[\u25a0\u25a1\ufffd?]", v):
            flagged.add(f)
    try:
        ex, tax, tot = (float(str(pred.get(k) or 0).replace(",", ""))
                        for k in ("amount_ex_tax", "amount_tax", "amount_total"))
        if abs(ex + tax - tot) > 0.01:
            flagged.add("amount_total")
    except Exception:
        flagged.add("amount_total")
    if not pred.get("seal_present"):
        flagged.add("seal_present")
    return flagged


def evaluate_case(c, break_flag=False, break_accuracy=False):
    text, how = read_contract(c)
    pred, cand = extract(text, break_accuracy)
    flagged = self_check(pred, cand, text) if not break_flag else set()
    fa = M.field_accuracy(c["gold"], pred)
    fr = M.flag_recall(c["gold"], pred, flagged)
    crit = c["critical_fields"]
    return {"case_id": c["case_id"], "kind": c["kind"], "layout": c["layout"],
            "carrier": c["carrier"], "read_as": how,
            "field_accuracy": fa["accuracy"], "per_field": fa["per_field"],
            "flag_recall": fr["recall"], "wrong_fields": fr["wrong_fields"],
            "wrong_unflagged": fr["wrong_unflagged"],
            "critical_unflagged": [f for f in fr["wrong_unflagged"] if f in crit],
            "right_but_flagged": fr["right_but_flagged"]}


def aggregate(rows):
    n = len(rows)
    m = {"cases": n,
         "field_accuracy": round(sum(r["field_accuracy"] for r in rows) / n, 6) if n else 0.0,
         "flag_recall": round(sum(r["flag_recall"] for r in rows) / n, 6) if n else 0.0,
         "critical_unflagged_total": sum(len(r["critical_unflagged"]) for r in rows),
         "wrong_total": sum(len(r["wrong_fields"]) for r in rows),
         "wrong_unflagged_total": sum(len(r["wrong_unflagged"]) for r in rows),
         "false_flag_total": sum(len(r["right_but_flagged"]) for r in rows),
         "thresholds": dict(M.THRESH)}
    m["fails"] = [M.LABELS[k] + " %.4f < %.2f" % (m[k], M.THRESH[k])
                  for k in M.THRESH if not M.check(k, m[k])]
    if m["critical_unflagged_total"]:
        m["fails"].append("错而未标红的 critical 字段 %d 个（目标 0）"
                          % m["critical_unflagged_total"])
    return m


def write_report(m, rows, path_md, path_json):
    os.makedirs(os.path.dirname(path_md), exist_ok=True)
    L = ["# 文档自动化评测报告 doc_auto.contract_fields", "",
         "> 全部合同虚构；统一社会信用代码第 3–8 位固定 999999（不存在的区划码）；"
         "被测输出只进人工复核队列、不得直接对外发送；AI 不计算金额。", "",
         "## 一、两项指标", "", "| 指标 | 实测 | 门槛 | 判定 |", "|---|---|---|---|"]
    for k in ("field_accuracy", "flag_recall"):
        L.append("| %s | %.4f | ≥%.2f | %s |" % (M.LABELS[k], m[k], M.THRESH[k],
                                                "通过" if M.check(k, m[k]) else "**未通过**"))
    L += ["", "## 二、标红统计", "",
          "| 项 | 值 |", "|---|---|",
          "| 识别错误的字段总数 | %d |" % m["wrong_total"],
          "| 其中未标红 | %d |" % m["wrong_unflagged_total"],
          "| **错而未标红的 critical 字段** | **%d**（目标 0） |" % m["critical_unflagged_total"],
          "| 识别正确却被标红（误报） | %d |" % m["false_flag_total"], "",
          "## 三、按字段的准确率", "",
          "| 字段 | 正确 | 总数 | 准确率 |", "|---|---|---|---|"]
    from collections import Counter
    ok_c, tot_c = Counter(), Counter()
    for r in rows:
        for f, v in r["per_field"].items():
            tot_c[f] += 1
            ok_c[f] += 1 if v["ok"] else 0
    for f in sorted(tot_c, key=lambda x: ok_c[x] / tot_c[x]):
        L.append("| %s | %d | %d | %.4f |" % (f, ok_c[f], tot_c[f], ok_c[f] / tot_c[f]))
    L += ["", "## 四、错而未标红明细（单列，供人工复核）", "",
          "| 用例 | 类型 | 未标红字段 | 其中 critical |", "|---|---|---|---|"]
    any_row = False
    for r in rows:
        if r["wrong_unflagged"]:
            any_row = True
            L.append("| %s | %s | %s | %s |" % (
                r["case_id"], r["kind"], ", ".join(r["wrong_unflagged"]),
                ", ".join(r["critical_unflagged"]) or "-"))
    if not any_row:
        L.append("| - | - | 无 | - |")
    L += ["", "## 五、判定", "",
          "**%s**" % ("未达标：" + "；".join(m["fails"]) if m["fails"] else "全部达标"), "",
          "## 六、按版式/载体的准确率", "",
          "| 维度 | 值 | 用例数 | 字段准确率 |", "|---|---|---|---|"]
    for key in ("layout", "carrier"):
        groups = {}
        for r in rows:
            groups.setdefault(r[key], []).append(r)
        for k, g in sorted(groups.items()):
            L.append("| %s | %s | %d | %.4f |" % (
                key, k, len(g), sum(x["field_accuracy"] for x in g) / len(g)))
    open(path_md, "w", encoding="utf-8").write("\n".join(L))
    json.dump({"metrics": m, "rows": rows}, open(path_json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return path_md


def main(argv=None):
    ap = argparse.ArgumentParser(prog="doc_eval")
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--break-flag", action="store_true")
    ap.add_argument("--break-accuracy", action="store_true")
    a = ap.parse_args(argv)
    rows = [evaluate_case(c, a.break_flag, a.break_accuracy) for c in load_cases()]
    m = aggregate(rows)
    suffix = "" if not (a.break_flag or a.break_accuracy) else "_broken"
    md = os.path.join(REPORTS, "doc_%s%s.md" % (a.tag, suffix))
    write_report(m, rows, md, md[:-3] + ".json")
    print("cases=%d field_acc=%.4f flag_recall=%.4f critical_unflagged=%d wrong=%d false_flag=%d"
          % (m["cases"], m["field_accuracy"], m["flag_recall"],
             m["critical_unflagged_total"], m["wrong_total"], m["false_flag_total"]))
    print("report=%s" % md)
    if m["fails"]:
        print("THRESHOLD NOT MET: " + "；".join(m["fails"]))
        return 1
    print("THRESHOLD OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
