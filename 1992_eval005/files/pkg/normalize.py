# -*- coding: utf-8 -*-
"""字段类型归一化：8 种类型各自一个函数，返回可比较的规范值或抛 NormalizeError。

归一化只做「等价写法统一」，不做任何业务容差 —— 金额、费率一律整数严格相等。
"""
import re
import unicodedata


class NormalizeError(ValueError):
    """输入无法按该字段类型归一化（类型不符或格式非法）。"""


# 全角→半角、去零宽字符，交由 NFKC 统一处理
ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)

STAMP_RE = re.compile(r"^(\d{4})\D*(\d{1,2})\D*(\d{1,2})\D*$")


def norm_string(v):
    """去首尾空白、内部连续空白折叠、全半角统一、英文大小写不敏感。"""
    if v is None:
        raise NormalizeError("string 不允许 None")
    s = unicodedata.normalize("NFKC", str(v).translate(ZERO_WIDTH))
    s = re.sub(r"\s+", " ", s).strip()
    return s.casefold()


def norm_date(v):
    """多种写法统一为 ISO（YYYY-MM-DD）。支持 2026-05-06 / 2026/5/6 / 2026年5月6日 / 20260506。"""
    if v is None:
        raise NormalizeError("date 不允许 None")
    s = unicodedata.normalize("NFKC", str(v).translate(ZERO_WIDTH)).strip()
    m = STAMP_RE.match(s)
    if not m:
        raise NormalizeError("date 格式无法识别: %r" % v)
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        raise NormalizeError("date 越界: %r" % v)
    return "%04d-%02d-%02d" % (y, mo, d)


def _strict_int(v, name):
    """整数严格相等：拒绝 bool、拒绝小数、拒绝字符串。"""
    if isinstance(v, bool):
        raise NormalizeError("%s 不接受布尔值" % name)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        raise NormalizeError("%s 不接受浮点数（浮点会引入精度误差）: %r" % (name, v))
    if isinstance(v, str) and re.fullmatch(r"-?\d+", v.strip()):
        return int(v.strip())
    raise NormalizeError("%s 必须是整数: %r" % (name, v))


def norm_money_fen(v):
    """金额以「分」存整数；不设任何容差。"""
    return _strict_int(v, "money_fen")


def norm_rate_bp(v):
    """费率以「基点」存整数；不设任何容差。"""
    return _strict_int(v, "rate_bp")


def norm_uscc(v):
    """统一社会信用代码：转大写后去空白，长度必须 18 位。"""
    if v is None:
        raise NormalizeError("uscc 不允许 None")
    s = unicodedata.normalize("NFKC", str(v).translate(ZERO_WIDTH))
    s = re.sub(r"\s+", "", s).upper()
    if len(s) != 18:
        raise NormalizeError("uscc 长度必须 18 位，实得 %d" % len(s))
    return s


def norm_enum(v, mapping):
    """按映射表把别名收敛成规范值；映射表里没有的按原文 casefold 保留。"""
    if v is None:
        raise NormalizeError("enum 不允许 None")
    raw = norm_string(v)
    return mapping.get(raw, raw)


def norm_scalar(ftype, v, schema_entry):
    if ftype == "string":
        return norm_string(v)
    if ftype == "date":
        return norm_date(v)
    if ftype == "money_fen":
        return norm_money_fen(v)
    if ftype == "rate_bp":
        return norm_rate_bp(v)
    if ftype == "uscc":
        return norm_uscc(v)
    if ftype == "enum":
        return norm_enum(v, schema_entry.get("mapping") or {})
    raise NormalizeError("非标量类型: %r" % ftype)


SCALAR_TYPES = ("string", "date", "money_fen", "rate_bp", "uscc", "enum")
CONTAINER_TYPES = ("list", "summary")
ALL_TYPES = SCALAR_TYPES + CONTAINER_TYPES
