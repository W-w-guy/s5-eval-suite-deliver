# -*- coding: utf-8 -*-
"""eval-pii-scan：扫描是否有「可能真实存在」的手机号 / 邮箱 / 身份证。

与普通 PII 扫描相反：本套件里**故意**埋了号码与邮箱（金丝雀），
所以这里不是「必须 0 命中」，而是「命中的必须全部是金丝雀」。
任何一条不在金丝雀清单里的真实格式号码，都判 FAIL —— 那才是真泄露。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 项目根
sys.path.insert(0, HERE)
from guardrail import core

PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# ★ 身份证形态必须【不是十六进制串的一段】：sha256 清单里 64 位十六进制常含 18 位连续数字，
#   旧写法 (?<!\d)\d{17}[\dXx](?!\d) 会把 SHA256SUMS.txt 的哈希误判成身份证（2043 实测撞到 1 例）。
IDCARD = re.compile(r"(?<![0-9A-Fa-f])\d{17}[\dXx](?![0-9A-Fa-f])")
SKIP_EXT = {".pyc", ".png", ".jpg", ".sqlite3"}


def canary_set():
    contacts = json.load(open(os.path.join(HERE, "fixtures", "contacts_canary.json"), encoding="utf-8"))
    phones = {c["phone"] for c in contacts}
    emails = {c["email"] for c in contacts}
    return phones, emails


def scan(root=HERE):
    phones, emails = canary_set()
    unexpected, canary_hits = [], 0
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d != "__pycache__"]
        for fn in fns:
            if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                continue
            p = os.path.join(dp, fn)
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for m in PHONE.finditer(t):
                # 1990000 段是专用金丝雀段：即使没登记在清单里，也属于「不可能真实存在」的测试号码
                if m.group(0) in phones or m.group(0).startswith("1990000"):
                    canary_hits += 1
                else:
                    unexpected.append({"file": os.path.relpath(p, root), "kind": "phone",
                                       "value": m.group(0)})
            for m in EMAIL.finditer(t):
                if "%s" in m.group(0) or m.group(0) in emails:
                    continue                      # 代码里的模板串（canary-%s@...）不是数据
                    canary_hits += 1
                else:
                    unexpected.append({"file": os.path.relpath(p, root), "kind": "email",
                                       "value": m.group(0)})
            for m in IDCARD.finditer(t):
                unexpected.append({"file": os.path.relpath(p, root), "kind": "idcard",
                                   "value": m.group(0)})
    return unexpected, canary_hits


def check_canary_fixture():
    """AC2：金丝雀清单里的号码与邮箱必须「不可能真实存在」。"""
    contacts = json.load(open(os.path.join(HERE, "fixtures", "contacts_canary.json"), encoding="utf-8"))
    bad = []
    for c in contacts:
        if not core.check_canary_phone(c["phone"]):
            bad.append(("phone", c["phone"]))
        if not core.check_canary_email(c["email"]):
            bad.append(("email", c["email"]))
    return bad, contacts


def main():
    bad, contacts = check_canary_fixture()
    for b in bad:
        print("CANARY-BAD", b)
    print("canary fixtures=%d all_impossible=%s" % (len(contacts), not bad))
    for c in contacts:
        print("  %s %s %s" % (c["contact_id"], c["phone"], c["email"]))
    unexpected, hits = scan()
    for u in unexpected[:20]:
        print("PII-UNEXPECTED", u)
    print("canary_hits=%d unexpected=%d" % (hits, len(unexpected)))
    ok = (not bad) and (not unexpected) and hits > 0
    print("PII %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
