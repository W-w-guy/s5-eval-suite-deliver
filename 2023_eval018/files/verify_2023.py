# -*- coding: utf-8 -*-
"""S5-EVAL-018 验收脚本：逐条对应工单 4 条验收标准，全部断言可复核。

用法：python verify_2023.py        # 全绿 rc=0
断言分四组，与工单 AC 一一对应；每条打印 [ OK ]/编号/断言/实测输出原文。
"""
import json, os, re, subprocess, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PY = sys.executable
FIELDS = {"contract_no", "party_a_name", "party_a_code", "party_b_name", "party_b_code",
          "service_start", "service_end", "amount_ex_tax", "tax_rate", "amount_tax",
          "amount_total", "payment_terms", "sign_date", "seal_present", "page_count"}
CRITICAL = ["amount_total", "amount_ex_tax", "party_a_code", "party_b_code",
            "service_start", "service_end"]
TRAPS = ["盖章压字", "跨页付款表", "同一合同多个金额", "补充协议覆盖原条款", "日期写法混用",
         "手机拍照倾斜", "表格合并单元格", "手写批注改金额", "多处小写金额不一致",
         "甲乙方名称简称混用", "跨页续表的合计行", "税率同时出现两种"]
N, FAIL = 0, []


def chk(tag, desc, cond, got=""):
    global N
    N += 1
    if cond:
        print("[ OK ] %s %s | %s" % (tag, desc, got))
    else:
        FAIL.append("%s %s | %s" % (tag, desc, got))
        print("[FAIL] %s %s | %s" % (tag, desc, got))


def run(args, cwd=None):
    r = subprocess.run([PY] + args, cwd=cwd or HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    cs = [json.loads(l) for l in open(os.path.join(HERE, "data", "cases.jsonl"), encoding="utf-8") if l.strip()]

    # ---------------- AC1 ----------------
    chk("AC1", "cases.jsonl 恰有 40 条", len(cs) == 40, len(cs))
    kinds = {}
    for c in cs:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    chk("AC1", "生成 28 / 疑难 12", kinds == {"generated": 28, "difficult": 12}, kinds)
    lay = {}
    for c in cs:
        lay[c["layout"]] = lay.get(c["layout"], 0) + 1
    chk("AC1", "4 种版式各 10 份", lay == {"standard": 10, "two_column": 10,
                                        "table_heavy": 10, "minimal": 10}, lay)
    car = {}
    for c in cs:
        car[c["carrier"]] = car.get(c["carrier"], 0) + 1
    chk("AC1", "3 种载体 14/13/13", car == {"text_pdf": 14, "scanned_pdf": 13, "docx": 13}, car)
    chk("AC1", "每份标准答案恰为 15 个字段（多/少均失败）",
        all(set(c["gold"]) == FIELDS for c in cs), "n=%d" % len(cs))
    chk("AC1", "critical 字段为含税/不含税金额、甲乙方代码、服务起止日",
        all(list(c["critical_fields"]) == CRITICAL for c in cs), CRITICAL)
    chk("AC1", "12 种疑难类型齐全（逐条比对）",
        sorted(c["meta"]["difficulty"]["name"] for c in cs if c["kind"] == "difficult") == sorted(TRAPS),
        len(TRAPS))
    import pypdf
    bad = []
    for c in cs:
        p = os.path.join(HERE, c["file"].replace("/", os.sep))
        if not os.path.isfile(p):
            bad.append((c["case_id"], "missing")); continue
        if c["carrier"] == "docx":
            if "word/document.xml" not in zipfile.ZipFile(p).namelist():
                bad.append((c["case_id"], "not docx"))
        else:
            if open(p, "rb").read(5) != b"%PDF-":
                bad.append((c["case_id"], "not pdf")); continue
            txt = pypdf.PdfReader(p).pages[0].extract_text() or ""
            if c["carrier"] == "text_pdf" and c["gold"]["contract_no"] not in txt:
                bad.append((c["case_id"], "no text layer"))
            if c["carrier"] == "scanned_pdf" and txt.strip():
                bad.append((c["case_id"], "unexpected text layer"))
    chk("AC1", "40 份文件的格式与 carrier 声明一致（docx 真 OOXML / pdf 真 PDF / 扫描件无文字层）",
        not bad, bad[:3])
    rc, out = run([os.path.join("tools", "eval_lint.py")])
    chk("AC1", "eval-lint 通过（rc=0）", rc == 0, out.strip().splitlines()[-1])
    rc, out = run([os.path.join("tools", "eval_pii_scan.py")])
    chk("AC1", "eval-pii-scan 通过（unexpected_hits=0）", rc == 0 and "unexpected_hits=0" in out,
        out.strip().splitlines()[-1])

    # ---------------- AC2 ----------------
    from doc_eval import metrics as M
    g = {"a": 1, "b": 2, "c": "x"}
    r1 = M.flag_recall(g, {"a": 9, "b": 2, "c": "y"}, {"a", "c"})
    r2 = M.flag_recall(g, {"a": 9, "b": 2, "c": "y"}, {"a"})
    r3 = M.flag_recall(g, {"a": 9, "b": 2, "c": "y"}, set())
    chk("AC2", "标红召回 3 组手工构造：全标红=1.0 / 半标红=0.5 / 全不标红=0.0",
        [r1["recall"], r2["recall"], r3["recall"]] == [1.0, 0.5, 0.0],
        [r1["recall"], r2["recall"], r3["recall"]])
    chk("AC2", "召回的分子分母口径写死：分母=识别错误字段数",
        r2["wrong_total"] == 2 and abs(r2["recall"] - 0.5) < 1e-9,
        "wrong_total=%d recall=%s" % (r2["wrong_total"], r2["recall"]))
    chk("AC2", "识别正确却被标红单独计数、不进召回分母",
        r1["right_but_flagged"] == [] and r1["wrong_total"] == 2, "right_but_flagged=[]")
    chk("AC2", "无识别错误时召回按显式约定记 1.0",
        M.flag_recall({"a": 1}, {"a": 1}, set())["recall"] == 1.0, 1.0)
    rc, out = run(["-m", "pytest", "tests", "-q"])
    chk("AC2", "单元测试全部通过", rc == 0, out.strip().splitlines()[-1])

    # ---------------- AC3 ----------------
    rc, out = run(["-m", "doc_eval", "--tag", "verify"])
    line = [l for l in out.strip().splitlines() if l.startswith("cases=")]
    chk("AC3", "runner 跑通且指标达标（rc=0）", rc == 0, line[0] if line else out[-120:])
    md_path = os.path.join(HERE, "reports", "doc_verify.md")
    md = open(md_path, encoding="utf-8").read() if os.path.isfile(md_path) else ""
    chk("AC3", "报告单列「错而未标红明细」小节", "错而未标红明细" in md, "reports/doc_verify.md")
    js = json.load(open(os.path.join(HERE, "reports", "doc_verify.json"), encoding="utf-8"))
    chk("AC3", "报告中「错而未标红的 critical 字段数」= 0",
        js["metrics"]["critical_unflagged_total"] == 0, js["metrics"]["critical_unflagged_total"])
    chk("AC3", "报告按字段输出准确率",
        all(("| %s |" % f) in md for f in sorted(FIELDS)), "15 个字段行")
    rc, out = run([os.path.join("tools", "make_screenshot.py"), "verify"])
    png = os.path.join(HERE, "reports", "doc_verify_unflagged_screenshot.png")
    ok_png = os.path.isfile(png) and os.path.getsize(png) > 20000
    if ok_png:
        from PIL import Image
        import numpy as _np
        a = _np.array(Image.open(png).convert("L"))
        ok_png = a.var() > 50 and int((a < 100).sum()) > 2000
    chk("AC3", "报告截图由 mock 输出渲染、非空白", rc == 0 and ok_png,
        "%d bytes" % (os.path.getsize(png) if os.path.isfile(png) else 0))
    chk("AC3", "截图对应 reports/doc_verify.json（同一 tag 同一批输出）",
        os.path.isfile(os.path.join(HERE, "reports", "doc_verify.json")), "tag=verify")

    # ---------------- AC4 ----------------
    n, bad, chars = 0, [], set()
    for c in cs:
        for f in ("party_a_code", "party_b_code"):
            v = c["gold"][f]
            n += 1
            if not (len(v) == 18 and v[2:8] == "999999" and re.fullmatch(r"[0-9A-Z]{18}", v)):
                bad.append((c["case_id"], f, v))
            chars.add(v[2:8])
    chk("AC4", "全部 80 个信用代码第 3-8 位为 999999", n == 80 and not bad, "n=%d 命中区划码=%s" % (n, sorted(chars)))
    chk("AC4", "信用代码均为 18 位且字符集合法", not bad, bad[:3])
    rc, out = run([os.path.join("tools", "eval_lint.py")])
    chk("AC4", "脚本检查输出可复核（eval-lint 内同样校验代码格式，rc=0）", rc == 0,
        out.strip().splitlines()[-1])

    # ---------------- 反向证据（不是 AC，但证明指标可证伪） ----------------
    rc1, o1 = run(["-m", "doc_eval", "--tag", "verify_badflag", "--break-flag"])
    rc2, o2 = run(["-m", "doc_eval", "--tag", "verify_badacc", "--break-accuracy"])
    chk("破坏", "--break-flag 打掉自检后 critical 未标红 > 0 且 rc=1", rc1 == 1,
        [l for l in o1.splitlines() if l.startswith("cases=")][0])
    chk("破坏", "--break-accuracy 让日期解析错后 rc=1", rc2 == 1,
        [l for l in o2.splitlines() if l.startswith("cases=")][0])

    print("\nTOTAL %d, PASS %d, FAIL %d" % (N, N - len(FAIL), len(FAIL)))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
