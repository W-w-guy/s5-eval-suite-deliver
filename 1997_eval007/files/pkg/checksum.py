# -*- coding: utf-8 -*-
"""PII 校验位算法：身份证(ISO 7064 MOD 11-2)、银行卡(Luhn)、统一社会信用代码(GB 32100)。

只做纯计算，不做匹配——匹配在 detector.py，便于单测与变异。
"""
from __future__ import annotations

ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
ID_CHECK = "10X98765432"

# GB 32100 用的字符集：去掉了 I O S V Z 五个易混字符
USCC_CHARSET = "0123456789ABCDEFGHJKLMNPQRTUWXY"
USCC_WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)


def id_card_ok(s: str) -> bool:
    """18 位身份证：前 17 位为数字，第 18 位为校验位（可能是 X）。"""
    if len(s) != 18:
        return False
    body, chk = s[:17], s[17].upper()
    if not body.isdigit():
        return False
    total = sum(int(body[i]) * ID_WEIGHTS[i] for i in range(17))
    return ID_CHECK[total % 11] == chk


def luhn_ok(s: str) -> bool:
    """银行卡号 Luhn 校验（自右向左，偶数位翻倍）。"""
    digits = [int(c) for c in s if c.isdigit()]
    if len(digits) < 12:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def uscc_ok(s: str) -> bool:
    """18 位统一社会信用代码的校验位。"""
    if len(s) != 18:
        return False
    body, chk = s[:17].upper(), s[17].upper()
    if any(c not in USCC_CHARSET for c in body):
        return False
    total = sum(USCC_CHARSET.index(body[i]) * USCC_WEIGHTS[i] for i in range(17))
    expect = 31 - (total % 31)
    if expect == 31:
        expect = 0
    return USCC_CHARSET[expect] == chk


def id_card_check_char(body17: str) -> str:
    total = sum(int(body17[i]) * ID_WEIGHTS[i] for i in range(17))
    return ID_CHECK[total % 11]


def uscc_check_char(body17: str) -> str:
    body17 = body17.upper()
    total = sum(USCC_CHARSET.index(body17[i]) * USCC_WEIGHTS[i] for i in range(17))
    expect = 31 - (total % 31)
    if expect == 31:
        expect = 0
    return USCC_CHARSET[expect]


def luhn_check_digit(partial: str) -> str:
    """给不带校验位的号段补出正确的末位，用于构造正例夹具。"""
    for d in "0123456789":
        if luhn_ok(partial + d):
            return d
    raise ValueError("no luhn digit")
