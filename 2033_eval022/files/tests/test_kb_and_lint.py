# -*- coding: utf-8 -*-
"""AC1（空实例导入）与 AC2（50 条分布 + eval-lint / eval-pii-scan 通过）。"""
import os
import sqlite3
import subprocess
import sys

import eval_lint
import import_kb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_import_on_empty_instance(tmp_path):
    db = str(tmp_path / "kb.sqlite3")
    conn = import_kb.connect(db)
    import_kb.schema(conn)
    assert import_kb.count(conn) == 0                 # 空实例
    n = import_kb.import_all(conn, verbose=False)
    assert n == 120
    assert import_kb.count(conn) == 120
    secs = conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    assert secs == 720


def test_import_refuses_non_empty_when_expect_empty(tmp_path):
    db = str(tmp_path / "kb.sqlite3")
    conn = import_kb.connect(db)
    import_kb.schema(conn)
    import_kb.import_all(conn, verbose=False)
    conn.close()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "import_kb.py"),
                        "--db", db, "--expect-empty"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 2                           # 非空 -> 拒绝，而不是重复导入


def test_docs_have_required_fields():
    rows = [l for l in os.listdir(os.path.join(ROOT, "kb_docs")) if l.endswith(".md")]
    assert len(rows) == 120
    t = open(os.path.join(ROOT, "kb_docs", "SP-001.md"), encoding="utf-8").read()
    for k in ("doc_id:", "title:", "updated:", "visibility:"):
        assert k in t


def test_lint_passes_on_shipped_cases():
    errs, stat = eval_lint.lint()
    assert errs == [], errs[:5]
    assert stat["dist"] == {"single_doc": 20, "multi_doc": 12, "numeric_date": 10, "paraphrase": 8}


def test_lint_catches_bad_gold_doc():
    cases = eval_lint.load_cases()
    bad = dict(cases[0], gold_doc_ids=["SP-999"])
    errs, _ = eval_lint.lint([bad] + cases[1:])
    assert any("不存在于知识库" in e for e in errs)


def test_lint_catches_fabricated_answer_point():
    cases = eval_lint.load_cases()
    bad = dict(cases[0], answer_points=["这句话在文档里根本不存在"] * 3)
    errs, _ = eval_lint.lint([bad] + cases[1:])
    assert any("无法在任何 gold 文档中逐字找到" in e for e in errs)


def test_lint_catches_wrong_distribution():
    cases = eval_lint.load_cases()
    bad = [dict(c, type="single_doc") for c in cases]
    errs, _ = eval_lint.lint(bad)
    assert any("数量" in e for e in errs)


def test_pii_scan_passes():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "eval_pii_scan.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout
    assert "PII PASS" in r.stdout


def test_pii_scan_ignores_binary_but_still_catches_text(tmp_path):
    """验收方常见做法：把交付包 zip 放在同目录里再解压。压缩流里的随机字节
    会被宽松邮箱正则拼成假命中，必须跳过；同时文本里的真邮箱一个都不能漏。

    字符串在运行时拼接，避免测试源文件自身被扫描器命中（自指陷阱）。
    """
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import eval_pii_scan

    at = chr(64)  # "@"，避免本文件自身出现完整邮箱形态
    fake_mail = "b" + at + "o.VqLcm"
    real_mail = "zhang.wei" + at + "realcorp.cn"

    blob = bytearray(fake_mail.encode() + b"\x00\xff\xfe13" + b"3" * 8)
    (tmp_path / "fake.zip").write_bytes(bytes(blob))
    hits, skipped = eval_pii_scan.scan(str(tmp_path))
    assert hits == [], hits
    assert "fake.zip" in skipped

    # 反向用例：同目录下放一个真邮箱的文本文件，必须被抓到（证明跳二进制没把检查蒙住）
    (tmp_path / "leak.txt").write_text("联系人 " + real_mail, encoding="utf-8")
    hits2, _ = eval_pii_scan.scan(str(tmp_path))
    assert any(h["kind"] == "邮箱" for h in hits2), hits2
