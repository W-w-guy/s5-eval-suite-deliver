# -*- coding: utf-8 -*-
"""生成 40 份虚构合同（28 生成 + 12 疑难）与 15 字段标准答案，并输出【真实载体】文件。

确定性：不使用内置 hash()（PYTHONHASHSEED 随机化会让跨进程/跨平台结果不同），
信用代码改用 hashlib.sha256 派生；数值全部来自 random.Random(2023)。
载体：text_pdf（有真实文字层）/ scanned_pdf（纯图像，无文字层）/ docx（OOXML）。
标准答案严格 15 个字段；难度说明放 case 级 meta，不污染 gold。
"""
import hashlib, json, os, random, zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(HERE, "data", "contracts")
PLAIN_DIR = os.path.join(HERE, "data", "plain")
R = random.Random(2023)

FIELDS = ["contract_no", "party_a_name", "party_a_code", "party_b_name", "party_b_code",
          "service_start", "service_end", "amount_ex_tax", "tax_rate", "amount_tax",
          "amount_total", "payment_terms", "sign_date", "seal_present", "page_count"]
CRITICAL = ["amount_total", "amount_ex_tax", "party_a_code", "party_b_code",
            "service_start", "service_end"]
LAYOUTS = ["standard", "two_column", "table_heavy", "minimal"]

DIFFICULTIES = [
    ("盖章压字", "印章覆盖了乙方名称与信用代码的中间字符", "seal_cover"),
    ("跨页付款表", "付款计划表跨第 2/3 页，表头只在第 2 页", "split_table"),
    ("同一合同多个金额", "正文出现 3 个金额：原合同额、补充协议新增额、含税总额", "multi_amount"),
    ("补充协议覆盖原条款", "补充协议把服务截止日推迟 60 天，原日期仍在正文", "addendum"),
    ("日期写法混用", "起止日分别写作中文写法与 DD/MM/YYYY", "mixed_date"),
    ("手机拍照倾斜", "扫描件倾斜 7 度，数字 0/8、1/7 易混", "skew"),
    ("表格合并单元格", "金额单元格跨行合并，值只写在首行", "merged_cell"),
    ("手写批注改金额", "手写把打印金额改动，打印值仍在", "handwrite"),
    ("多处小写金额不一致", "大写金额与小写数字不一致，以大写为准", "cn_amount"),
    ("甲乙方名称简称混用", "首页写全称，正文用简称，标准答案取全称", "abbrev"),
    ("跨页续表的合计行", "合计行在下一页，与明细页分离", "carry_total"),
    ("税率同时出现两种", "正文写 6%，附件写 13%，以正文为准", "two_rates"),
]


def code(seed):
    """18 位统一社会信用代码：第 3-8 位固定 999999（不存在的区划码），后 10 位稳定派生。"""
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16) % 10 ** 10
    return "91%06d%010d" % (999999, h)


def cn_upper(n):
    d = "零壹贰叁肆伍陆柒捌玖"
    units = ["", "拾", "佰", "仟", "万", "拾", "佰", "仟", "亿"]
    out, i = [], 0
    for ch in reversed(str(int(round(n)))):
        out.append((d[int(ch)] + units[i]) if ch != "0" else "")
        i += 1
    return "".join(reversed(out)) + "元整"


def add_days(ymd, n):
    import datetime
    y, m, dd = [int(x) for x in ymd.split("-")]
    return (datetime.date(y, m, dd) + datetime.timedelta(days=n)).isoformat()


def money(v):
    return "{:,.2f}".format(float(v))


def lines_for(g, layout, trap=None):
    """按版式铺合同正文；trap 决定疑难点如何体现在文本里（gold 始终是正确值）。"""
    A, B = g["party_a_name"], g["party_b_name"]
    a_name, b_name = A, B
    a_code, b_code = g["party_a_code"], g["party_b_code"]
    s, e = g["service_start"], g["service_end"]
    if trap == "abbrev":
        b_name = B.replace("有限公司", "")[:6]
    if trap == "seal_cover":
        b_name = B[:4] + "■■" + B[6:]
        b_code = b_code[:8] + "■■■■" + b_code[12:]
    L = []
    if layout == "minimal":
        L.append("合同 %s" % g["contract_no"])
        L.append("甲方：%s（%s）" % (a_name, a_code))
        L.append("乙方：%s（%s）" % (b_name, b_code))
        L.append("服务期 %s 至 %s" % (s, e))
        L.append("不含税 %s 元 税率 %d%% 税额 %s 元 含税 %s 元" % (
            money(g["amount_ex_tax"]), g["tax_rate"], money(g["amount_tax"]), money(g["amount_total"])))
        L.append("付款：%s" % g["payment_terms"])
        L.append("签订 %s 盖章 %s 共 %d 页" % (
            g["sign_date"], "有" if g["seal_present"] else "无", g["page_count"]))
        return L
    L.append("服务合同（虚构样例）")
    L.append("合同编号：%s" % g["contract_no"])
    L.append("甲方（采购方）：%s" % a_name)
    L.append("甲方统一社会信用代码：%s" % a_code)
    L.append("乙方（服务提供方）：%s" % b_name)
    L.append("乙方统一社会信用代码：%s" % b_code)
    if trap == "mixed_date":
        y1, m1, d1 = s.split("-")
        dd, mm, yy = e.split("-")
        L.append("服务期限：%s年%d月%d日 起 至 %s/%s/%s 止" % (y1, int(m1), int(d1), dd, mm, yy))
    else:
        L.append("服务期限：%s 至 %s" % (s, e))
    if trap == "addendum":
        L.append("服务期限（原条款）：%s 至 %s" % (s, g["service_end"]))
        L.append("补充协议：服务截止日由 %s 顺延至 %s，以补充协议为准。" % (g["service_end"], e))
    if layout == "table_heavy":
        L.append("金额明细表（单位：元）：")
        L.append("| 项目 | 不含税金额 | 税率 | 税额 | 含税金额 |")
        if trap == "merged_cell":
            L.append("| 本期服务费（合并单元格，值仅首行） | %s | %d%% | %s | %s |" % (
                money(g["amount_ex_tax"]), g["tax_rate"], money(g["amount_tax"]), money(g["amount_total"])))
            L.append("| （同上，单元格合并，留空） | | | | |")
        else:
            L.append("| 本期服务费 | %s | %d%% | %s | %s |" % (
                money(g["amount_ex_tax"]), g["tax_rate"], money(g["amount_tax"]), money(g["amount_total"])))
    else:
        L.append("不含税金额：%s 元" % money(g["amount_ex_tax"]))
        L.append("税率：%d%%" % g["tax_rate"])
        L.append("税额：%s 元" % money(g["amount_tax"]))
        L.append("含税总金额（小写）：%s 元" % money(g["amount_total"]))
        if trap == "cn_amount":
            L.append("含税总金额（大写）：%s" % cn_upper(g["amount_total"] + 10000))
            L.append("说明：大小写不一致时以大写为准。")
    if trap == "multi_amount":
        L.append("原合同额：%s 元；补充协议新增额：%s 元；本次结算含税总额：%s 元。" % (
            money(g["amount_total"] * 0.6), money(g["amount_total"] * 0.4), money(g["amount_total"])))
    if trap == "handwrite":
        L.append("打印金额：%s 元（手写批注改为 %s 元，以批注为准）" % (
            money(g["amount_total"] - 10000), money(g["amount_total"])))
    if trap == "two_rates":
        L.append("附件一约定税率 13%%（与正文不一致时以正文为准）。")
    if trap == "split_table":
        L.append("付款计划表（续下表，表头仅第 2 页出现）：")
        L.append("| 期次 | 比例 | 金额 |")
        L.append("| 首期 | 50%% | %s |" % money(g["amount_total"] * 0.5))
        L.append("—— 分页（第 2 页）——")
        L.append("| 尾期 | 50%% | %s |" % money(g["amount_total"] * 0.5))
    else:
        L.append("付款方式：%s" % g["payment_terms"])
    if trap == "carry_total":
        L.append("费用明细：")
        L.append("| 项目 | 金额 |")
        L.append("| 实施费 | %s |" % money(g["amount_ex_tax"] * 0.8))
        L.append("—— 分页（续表）——")
        L.append("| 合计（含税） | %s |" % money(g["amount_total"]))
    L.append("签订日期：%s" % g["sign_date"])
    L.append("盖章：%s" % ("有（公章/合同专用章）" if g["seal_present"] else "无"))
    L.append("合同页数：%d 页" % g["page_count"])
    L.append("（本合同为虚构样例，仅用于评测；统一社会信用代码使用不存在的区划码 999999，不对应任何真实企业。）")
    return L


CARRIER_PLAN_NORMAL = ["text_pdf", "scanned_pdf", "docx"]


def build_case(i, kind, trap_idx=None):
    rid = "CT-%03d" % (i + 1)
    layout = LAYOUTS[i % len(LAYOUTS)]
    carrier = CARRIER_PLAN_NORMAL[i % 3]
    if kind == "difficult":
        carrier = CARRIER_PLAN_NORMAL[(trap_idx // 4) % 3]
    ex_tax = 100000 + i * 1300
    rate = [6, 13, 9][i % 3]
    tax = round(ex_tax * rate / 100.0, 2)
    total = round(ex_tax + tax, 2)
    start = "2026-%02d-%02d" % (3 + i % 6, 1 + i % 27)
    end = "2027-%02d-%02d" % (3 + i % 6, 1 + (i * 3) % 27)
    gold = {
        "contract_no": "HT-2026-%04d" % (i + 1),
        "party_a_name": "示例会员企业%s有限公司" % ["甲", "乙", "丙", "丁"][i % 4],
        "party_a_code": code("a%d" % i),
        "party_b_name": "示例%s服务有限公司" % ["云栈", "智联", "绿源", "星河"][i % 4],
        "party_b_code": code("b%d" % i),
        "service_start": start, "service_end": end,
        "amount_ex_tax": ex_tax, "tax_rate": rate,
        "amount_tax": tax, "amount_total": total,
        "payment_terms": "签订后 30 日内支付 50%，验收后 30 日内支付余款",
        "sign_date": "2026-%02d-%02d" % (2 + i % 6, 1 + (i * 5) % 27),
        "seal_present": True, "page_count": 4 + i % 5,
    }
    trap, tname, tdesc = None, None, None
    if kind == "difficult":
        tname, tdesc, trap = DIFFICULTIES[trap_idx]
        if trap == "addendum":
            gold["service_end"] = add_days(end, 60)
        if trap == "two_rates":
            gold["tax_rate"] = 6
            gold["amount_tax"] = round(ex_tax * 0.06, 2)
            gold["amount_total"] = round(ex_tax + gold["amount_tax"], 2)
        if trap == "cn_amount":
            pass
    lines = lines_for(gold, layout, trap)
    ext = {"text_pdf": ".pdf", "scanned_pdf": ".pdf", "docx": ".docx"}[carrier]
    case = {
        "case_id": rid, "kind": "generated" if kind != "difficult" else "difficult",
        "layout": layout, "carrier": carrier,
        "file": "data/contracts/%s%s" % (rid, ext),
        "gold": gold, "critical_fields": list(CRITICAL),
        "source": "s5doc_generator" if kind != "difficult" else "handcrafted",
        "meta": {"虚构": "全部合同为合成数据，不含真实企业或个人信息",
                 "信用代码": "第3-8位固定999999（不存在的区划码）"},
    }
    if tname:
        case["meta"]["difficulty"] = {"name": tname, "desc": tdesc, "tag": trap}
    return case, lines


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(PLAIN_DIR, exist_ok=True)
    import render_carriers as rc
    cases, texts = [], {}
    for i in range(28):
        c, ln = build_case(i, "generated")
        cases.append(c); texts[c["case_id"]] = ln
    for j in range(12):
        c, ln = build_case(28 + j, "difficult", trap_idx=j)
        cases.append(c); texts[c["case_id"]] = ln
    for c in cases:
        ln = texts[c["case_id"]]
        p = os.path.join(HERE, c["file"].replace("/", os.sep))
        trap = (c.get("meta", {}).get("difficulty") or {}).get("tag")
        if c["carrier"] == "docx":
            rc.write_docx(ln, p)
        elif c["carrier"] == "text_pdf":
            rc.write_text_pdf(ln, p)
        else:
            rc.write_scanned_pdf(ln, p, skew=7.0 if trap == "skew" else 0.0)
        with open(os.path.join(PLAIN_DIR, c["case_id"] + ".txt"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("\n".join(ln) + "\n")
        if trap == "skew" and c["carrier"] != "scanned_pdf":
            raise SystemExit("skew 疑难必须用 scanned_pdf 载体")
    with open(os.path.join(HERE, "data", "cases.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    print("生成 %d 份：%s" % (len(cases), json.dumps(
        {"generated": sum(1 for c in cases if c["kind"] == "generated"),
         "difficult": sum(1 for c in cases if c["kind"] == "difficult")}, ensure_ascii=False)))


if __name__ == "__main__":
    main()
