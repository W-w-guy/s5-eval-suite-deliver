# -*- coding: utf-8 -*-
"""eval-lint：评测集结构校验（零依赖，纯 stdlib）。rc=0 通过，rc=1 有错。

校验项：条数/类型分布、case_id 唯一、gold 恰为 15 个规定字段（多一个少一个都失败）、
critical 子集关系、载体与文件后缀一致且文件存在、金额/日期/信用代码格式、
难度说明只出现在 meta（不进 gold）、无格式化残留（%%）、按版式与载体覆盖齐全。
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELDS = ["contract_no", "party_a_name", "party_a_code", "party_b_name", "party_b_code",
          "service_start", "service_end", "amount_ex_tax", "tax_rate", "amount_tax",
          "amount_total", "payment_terms", "sign_date", "seal_present", "page_count"]
CRITICAL = ["amount_total", "amount_ex_tax", "party_a_code", "party_b_code",
            "service_start", "service_end"]
LAYOUTS = {"standard", "two_column", "table_heavy", "minimal"}
CARRIERS = {"text_pdf": ".pdf", "scanned_pdf": ".pdf", "docx": ".docx"}
EXPECT = {"generated": 28, "difficult": 12}


def main():
    errs, warns = [], []
    path = os.path.join(HERE, "data", "cases.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    if len(rows) != 40:
        errs.append("用例数应为 40，实际 %d" % len(rows))
    ids = [r.get("case_id") for r in rows]
    if len(set(ids)) != len(ids):
        errs.append("case_id 有重复")
    kinds = {}
    for r in rows:
        cid = r.get("case_id", "?")
        kinds[r.get("kind")] = kinds.get(r.get("kind"), 0) + 1
        if not re.fullmatch(r"CT-\d{3}", cid or ""):
            errs.append("%s: case_id 格式应为 CT-三位数" % cid)
        g = r.get("gold") or {}
        if set(g) != set(FIELDS):
            errs.append("%s: gold 应恰为 15 个字段，实际 %d（多=%s 少=%s）"
                        % (cid, len(g), sorted(set(g) - set(FIELDS)), sorted(set(FIELDS) - set(g))))
        if any(k.startswith("_") for k in g):
            errs.append("%s: gold 里不允许出现下划线前缀的内部字段" % cid)
        if list(r.get("critical_fields") or []) != CRITICAL:
            errs.append("%s: critical_fields 必须等于规定的 6 个字段" % cid)
        if not set(r.get("critical_fields") or []) <= set(FIELDS):
            errs.append("%s: critical_fields 不是 gold 的子集" % cid)
        if r.get("layout") not in LAYOUTS:
            errs.append("%s: layout 非法 %r" % (cid, r.get("layout")))
        carrier = r.get("carrier")
        if carrier not in CARRIERS:
            errs.append("%s: carrier 非法 %r" % (cid, carrier))
        else:
            fp = os.path.join(HERE, str(r.get("file", "")).replace("/", os.sep))
            if not os.path.isfile(fp):
                errs.append("%s: 载体文件不存在 %s" % (cid, r.get("file")))
            elif os.path.splitext(fp)[1] != CARRIERS[carrier]:
                errs.append("%s: 载体 %s 与文件后缀 %s 不一致"
                            % (cid, carrier, os.path.splitext(fp)[1]))
        for f in ("party_a_code", "party_b_code"):
            v = str(g.get(f, ""))
            if not (len(v) == 18 and v[2:8] == "999999" and re.fullmatch(r"[0-9A-Z]{18}", v)):
                errs.append("%s: %s 不是 18 位且第 3-8 位非 999999" % (cid, f))
        for f in ("service_start", "service_end", "sign_date"):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(g.get(f, ""))):
                errs.append("%s: %s 不是 YYYY-MM-DD" % (cid, f))
        for f in ("amount_ex_tax", "amount_tax", "amount_total"):
            if not isinstance(g.get(f), (int, float)):
                errs.append("%s: %s 必须是数值（分/元以数值存）" % (cid, f))
        if r.get("kind") == "difficult":
            d = (r.get("meta") or {}).get("difficulty") or {}
            if not d.get("name") or not d.get("desc"):
                errs.append("%s: 疑难用例必须写明 name 与 desc" % cid)
            if r.get("source") != "handcrafted":
                errs.append("%s: 疑难用例 source 应为 handcrafted" % cid)
        elif r.get("source") != "s5doc_generator":
            errs.append("%s: 生成用例 source 应为 s5doc_generator" % cid)
        if "%%" in json.dumps(r, ensure_ascii=False):
            errs.append("%s: 存在 %% 格式化残留" % cid)
    for k, n in EXPECT.items():
        if kinds.get(k) != n:
            errs.append("%s 应为 %d 条，实际 %s" % (k, n, kinds.get(k)))
    got_layouts = {r["layout"] for r in rows if r.get("layout") in LAYOUTS}
    if got_layouts != LAYOUTS:
        errs.append("版式覆盖不全，缺 %s" % sorted(LAYOUTS - got_layouts))
    got_carriers = {r["carrier"] for r in rows if r.get("carrier") in CARRIERS}
    if got_carriers != set(CARRIERS):
        errs.append("载体覆盖不全，缺 %s" % sorted(set(CARRIERS) - got_carriers))
    for e in errs:
        print("[FAIL] " + e)
    print("eval-lint: cases=%d layouts=%d carriers=%d errors=%d warnings=%d"
          % (len(rows), len(got_layouts), len(got_carriers), len(errs), len(warns)))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
