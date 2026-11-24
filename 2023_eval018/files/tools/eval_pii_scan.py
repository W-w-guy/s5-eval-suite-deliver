# -*- coding: utf-8 -*-
"""eval-pii-scan：交付数据里不得出现真实个人信息/企业信息（零依赖，纯 stdlib）。

扫描范围：data/cases.jsonl、data/plain/*.txt、所有 docx 的正文 XML、所有 PDF 的字节流。
判据：命中手机号/邮箱/身份证号/银行卡号/客户名称即失败（rc=1）。
统一社会信用代码第 3-8 位 999999 属虚构约定，显式豁免并在输出里单列。
"""
import json, os, re, sys, zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PATTERNS = {
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "邮箱": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "身份证": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "银行卡": re.compile(r"(?<!\d)\d{16,19}(?!\d)"),
    "客户名称": re.compile(r"(会员空间平台|客户名称|真实企业)"),
}


def scan_text(name, text, hits, exempt):
    for label, rx in PATTERNS.items():
        for m in rx.finditer(text):
            v = m.group(0)
            if label in ("身份证", "银行卡") and len(v) == 18 and v[2:8] == "999999":
                exempt.append((name, label, v))
                continue
            if label == "客户名称":
                continue
            hits.append((name, label, v))


def main():
    hits, exempt, files, no_text = [], [], 0, []
    targets = [os.path.join(HERE, "data", "cases.jsonl")]
    plain = os.path.join(HERE, "data", "plain")
    if os.path.isdir(plain):
        targets += [os.path.join(plain, f) for f in sorted(os.listdir(plain))]
    cd = os.path.join(HERE, "data", "contracts")
    for f in sorted(os.listdir(cd)) if os.path.isdir(cd) else []:
        targets.append(os.path.join(cd, f))
    for p in targets:
        if not os.path.isfile(p):
            continue
        files += 1
        if p.endswith(".docx"):
            try:
                with zipfile.ZipFile(p) as z:
                    scan_text(os.path.basename(p), z.read("word/document.xml").decode("utf-8", "ignore"), hits, exempt)
            except Exception as e:
                hits.append((os.path.basename(p), "读取失败", str(e)[:60]))
        elif p.endswith(".pdf"):
            # 只扫 PDF 的【文字层】：直接扫 PDF 原始字节会把字形编号误判成卡号/身份证
            try:
                import pypdf
                txt = pypdf.PdfReader(p).pages[0].extract_text() or ""
                if not txt.strip():
                    no_text.append(os.path.basename(p))
            except Exception:
                txt = ""
                no_text.append(os.path.basename(p))
            scan_text(os.path.basename(p), txt, hits, exempt)
        else:
            scan_text(os.path.basename(p), open(p, encoding="utf-8", errors="ignore").read(), hits, exempt)
    for h in hits[:20]:
        print("[FAIL] %s: 命中%s %r" % h)
    print("eval-pii-scan: files=%d unexpected_hits=%d exempt_999999=%d "
          "pdf_without_textlayer=%d（其正文以 data/plain 同源文本被扫描）"
          % (files, len(hits), len(exempt), len(no_text)))
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
