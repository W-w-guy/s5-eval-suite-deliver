# -*- coding: utf-8 -*-
"""evidence 入库前的掩码（复用 EVAL-030 的 redact 口径）。

AC3 要求：evidence 中的金丝雀片段**入库后已被掩码**。
所以掩码必须在写库之前发生 —— 断言也直接查库，不查请求体。

金丝雀用高熵三段式（如 3ZZP-9ERG-Y3SZ）：低熵词（FICT/TEST）会与正文里的
.example.invalid 之类域名撞车，把正常文本误判成泄露。
"""
import re

# ---- 掩码规则（按顺序执行） ----
# 顺序有讲究：idcard 必须在 bank 之前 ——
# 18 位身份证同时满足 bank 的 \d{16,19}，若 bank 先跑，身份证会被按「卡号」掩码
# （前 6 后 4），语义不对；先按身份证掩码后，数字里已含星号，bank 就匹配不上了。
RULES = [
    ("mobile", re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)"), r"\1****\2"),
    ("idcard", re.compile(r"(?<!\w)(\d{4})\d{10}(\d{3}[\dXx])(?!\w)"), r"\1**********\2"),
    ("bank", re.compile(r"(?<!\d)(\d{6})\d{6,9}(\d{4})(?!\d)"), r"\1******\2"),
    ("email", re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"),
     r"\1***\2"),
    ("uscc", re.compile(r"(?<![0-9A-Za-z])([0-9A-HJ-NPQRTUWXY]{4})[0-9A-HJ-NPQRTUWXY]{10}"
                        r"([0-9A-HJ-NPQRTUWXY]{4})(?![0-9A-Za-z])"), r"\1**********\2"),
    ("canary", re.compile(r"([A-Z0-9]{4})-[A-Z0-9]{4}-([A-Z0-9]{4})"), r"\1-****-\2"),
]
CANARY_MIN_RUN = 4          # 行为开关：掩码保留的前后缀长度用（前/后各 4 字符）
REDACT_BEFORE_STORE = True  # 行为开关：入库前是否掩码


def redact(text):
    """返回 (掩码后文本, 命中规则列表)。"""
    if text is None:
        return "", []
    out = str(text)
    hits = []
    for name, rx, repl in RULES:
        new, n = rx.subn(repl, out)
        if n:
            hits.append({"rule": name, "count": n})
            out = new
    return out, hits


def _norm_canary(s):
    """金丝雀归一化：去空白与分隔符、转大写。"""
    return re.sub(r"[\s\-_]", "", str(s)).upper()


def leak_of_canary(text, canary):
    """该文本里是否还残留**完整**的金丝雀（用于断言）。

    判据取「完整金丝雀」而不是「连续 N 字符」：
    掩码后保留的是前 4 与后 4 字符（如 3ZZP-****-Y3SZ），
    若按连续 4 字符判，掩码后的文本永远算泄露，断言就失去意义。
    泄露的定义是**整串金丝雀被原样带出去**。
    """
    if not canary:
        return False
    return _norm_canary(canary) in _norm_canary(text)


def mask_or_raise(field_name, text):
    """入库前的入口：REDACT_BEFORE_STORE 打开时一定掩码。"""
    if not REDACT_BEFORE_STORE:
        return text, []
    return redact(text)
