# -*- coding: utf-8 -*-
"""评测集端到端测试：结构（工单全集）、载体真实性、指标口径、破坏开关可证伪。"""
import json, os, re, subprocess, sys, zipfile
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import doc_eval.__main__ as R

FIELDS = {"contract_no", "party_a_name", "party_a_code", "party_b_name", "party_b_code",
          "service_start", "service_end", "amount_ex_tax", "tax_rate", "amount_tax",
          "amount_total", "payment_terms", "sign_date", "seal_present", "page_count"}
CRITICAL = ["amount_total", "amount_ex_tax", "party_a_code", "party_b_code",
            "service_start", "service_end"]
TRAPS = ["盖章压字", "跨页付款表", "同一合同多个金额", "补充协议覆盖原条款", "日期写法混用",
         "手机拍照倾斜", "表格合并单元格", "手写批注改金额", "多处小写金额不一致",
         "甲乙方名称简称混用", "跨页续表的合计行", "税率同时出现两种"]


def cs():
    return R.load_cases()


def test_dataset_shape_hardcoded():
    """条数与分布硬编码：28 生成 + 12 疑难；4 版式各 10；3 载体 14/13/13。"""
    rows = cs()
    assert len(rows) == 40
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    assert kinds == {"generated": 28, "difficult": 12}, kinds
    lay = {}
    for r in rows:
        lay[r["layout"]] = lay.get(r["layout"], 0) + 1
    assert lay == {"standard": 10, "two_column": 10, "table_heavy": 10, "minimal": 10}, lay
    car = {}
    for r in rows:
        car[r["carrier"]] = car.get(r["carrier"], 0) + 1
    assert car == {"text_pdf": 14, "scanned_pdf": 13, "docx": 13}, car


def test_gold_is_exactly_15_fields():
    """标准答案必须恰好 15 个字段：多一个（含内部下划线键）或少一个都失败。"""
    for c in cs():
        assert set(c["gold"]) == FIELDS, (c["case_id"], sorted(set(c["gold"]) ^ FIELDS))
        assert list(c["critical_fields"]) == CRITICAL, c["case_id"]


def test_carrier_files_are_real_and_match_declared_type():
    """40 份文件真实存在，且格式与 carrier 声明一致（不是改个后缀）。"""
    import pypdf
    for c in cs():
        p = os.path.join(ROOT, c["file"].replace("/", os.sep))
        assert os.path.isfile(p), p
        if c["carrier"] == "docx":
            assert p.endswith(".docx")
            assert "word/document.xml" in zipfile.ZipFile(p).namelist()
        else:
            assert p.endswith(".pdf")
            raw = open(p, "rb").read(5)
            assert raw == b"%PDF-", (c["case_id"], raw)
            txt = pypdf.PdfReader(p).pages[0].extract_text() or ""
            if c["carrier"] == "text_pdf":
                assert c["gold"]["contract_no"] in txt, (c["case_id"], txt[:80])
            else:
                assert txt.strip() == "", (c["case_id"], "扫描件不应有文字层")


def test_codes_use_nonexistent_division():
    """80 个信用代码全部 18 位且第 3-8 位为 999999（硬编码总数 80）。"""
    n = 0
    for c in cs():
        for f in ("party_a_code", "party_b_code"):
            v = c["gold"][f]
            assert len(v) == 18 and v[2:8] == "999999", (c["case_id"], v)
            assert re.fullmatch(r"[0-9A-Z]{18}", v), (c["case_id"], v)
            n += 1
    assert n == 80, n


def test_difficult_cases_cover_all_12_traps():
    got = [(c["meta"]["difficulty"]["name"]) for c in cs() if c["kind"] == "difficult"]
    assert sorted(got) == sorted(TRAPS), got


def test_no_formatting_artifacts_and_no_pii_shape():
    for c in cs():
        s = json.dumps(c, ensure_ascii=False)
        assert "%%" not in s, c["case_id"]
        assert not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", s), c["case_id"]
        assert not re.search(r"(?<![\w.])[\w.]+@[\w.]+\.\w+", s), c["case_id"]


def test_lint_and_pii_scan_pass():
    for tool in ("tools/eval_lint.py", "tools/eval_pii_scan.py"):
        r = subprocess.run([sys.executable, os.path.join(ROOT, tool)], cwd=ROOT,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert r.returncode == 0, (tool, r.stdout[-500:], r.stderr[-300:])


def test_metrics_pass_default():
    rows = [R.evaluate_case(c) for c in cs()]
    m = R.aggregate(rows)
    assert m["field_accuracy"] >= 0.90, m["field_accuracy"]
    assert m["flag_recall"] >= 0.95, m["flag_recall"]
    assert m["critical_unflagged_total"] == 0, m["critical_unflagged_total"]
    assert m["fails"] == []


def test_break_flag_makes_recall_drop():
    rows = [R.evaluate_case(c, break_flag=True) for c in cs()]
    m = R.aggregate(rows)
    assert m["critical_unflagged_total"] > 0, "关闭自检后必须出现错而未标红"


def test_break_accuracy_makes_date_errors():
    rows = [R.evaluate_case(c, break_accuracy=True) for c in cs()]
    m = R.aggregate(rows)
    assert m["field_accuracy"] < 0.99
    assert m["critical_unflagged_total"] > 0


def test_report_has_unflagged_section_and_screenshot():
    r = subprocess.run([sys.executable, "-m", "doc_eval", "--tag", "pytest"], cwd=ROOT,
                       capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout[-400:]
    md = open(os.path.join(ROOT, "reports", "doc_pytest.md"), encoding="utf-8").read()
    assert "错而未标红明细" in md
    r2 = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_screenshot.py"), "pytest"],
                        cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    assert r2.returncode == 0, r2.stderr[-300:]
    png = os.path.join(ROOT, "reports", "doc_pytest_unflagged_screenshot.png")
    assert os.path.getsize(png) > 20000
