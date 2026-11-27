# -*- coding: utf-8 -*-
"""8 类检测项 + 企业名/人名告警。

设计要点：所有校验位判断都走 checksum.py 的纯函数，
正则只负责「候选切片」，是否算命中由校验位决定 —— 这样正反例的差别可解释。
"""
import re

import checksum
import rules as R

CN_DIGITS = "零一二三四五六七八九十百千"
PROVINCES = ("北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
             "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
             "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
             "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门")

RE_MOBILE = re.compile(r"(?<!\d)" + R.MOBILE_PREFIX + r"\d{9}(?!\d)")
RE_LANDLINE = re.compile(r"(?<!\d)0\d{2,3}-?\d{7,8}(?!\d)")
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_ID = re.compile(r"(?<![0-9A-Za-z])\d{17}[\dXx](?![0-9A-Za-z])")
RE_BANK = re.compile(r"(?<!\d)\d{16,19}(?!\d)")
RE_USCC = re.compile(r"(?<![0-9A-Za-z])[0-9A-HJ-NPQRTUWXY]{18}(?![0-9A-Za-z])")
RE_PLATE = re.compile(
    r"(?<![\u4e00-\u9fa5A-Z0-9])"
    r"[\u4e00-\u9fa5][A-Z][\-·]?[A-Z0-9]{5,6}(?![A-Z0-9])")
RE_ROAD = re.compile(r"(路|街|道|巷|弄|大道|胡同)\s*\d{1,5}\s*号")
RE_ORG = re.compile(r"[\u4e00-\u9fa5]{2,12}(有限公司|股份有限公司|集团|研究院|事务所|中心)")


def _mk(kind, text, span, evidence=""):
    return {"kind": kind, "level": R.LEVEL[kind],
            "span": list(span), "text": text[:40], "evidence": evidence}


def find_mobile(text):
    return [_mk("mobile", m.group(0), m.span()) for m in RE_MOBILE.finditer(text)]


def find_landline(text):
    return [_mk("landline", m.group(0), m.span()) for m in RE_LANDLINE.finditer(text)]


def find_email(text):
    return [_mk("email", m.group(0), m.span()) for m in RE_EMAIL.finditer(text)]


def find_id_card(text):
    out = []
    for m in RE_ID.finditer(text):
        s = m.group(0)
        if checksum.id_card_ok(s):
            out.append(_mk("id_card", s, m.span(), "校验位通过"))
    return out


def find_bank_card(text):
    out = []
    for m in RE_BANK.finditer(text):
        s = m.group(0)
        if len(s) < R.BANK_MIN_DIGITS:
            continue
        if checksum.luhn_ok(s):
            out.append(_mk("bank_card", s, m.span(), "Luhn 通过"))
    return out


def find_uscc(text):
    """校验位通过、且第 3~8 位不是 999999 占位段，才视为疑似真实。"""
    out = []
    lo, hi = R.USCC_PLACEHOLDER_RANGE[1], R.USCC_PLACEHOLDER_RANGE[2]
    placeholder = R.USCC_PLACEHOLDER_RANGE[0]
    for m in RE_USCC.finditer(text):
        s = m.group(0).upper()
        if not checksum.uscc_ok(s):
            continue
        if s[lo:hi] == placeholder:
            continue
        out.append(_mk("uscc", s, m.span(), "校验位通过且非占位号段"))
    return out


def find_address(text):
    """省/市/区 之一 + 「路/街/道…+ 数字 + 号」同时出现才算。"""
    if not any(p in text for p in PROVINCES) and "市" not in text and "区" not in text:
        return []
    out = []
    for m in RE_ROAD.finditer(text):
        st = max(0, m.start() - 20)
        seg = text[st:m.end()]
        if len(seg) >= R.ADDRESS_MIN_LEN and ("市" in seg or "区" in seg or "省" in seg
                                              or any(p in seg for p in PROVINCES)):
            out.append(_mk("address", seg, (st, m.end())))
            break
    return out


def find_plate(text):
    return [_mk("plate", m.group(0), m.span()) for m in RE_PLATE.finditer(text)]


def find_org_name(text):
    """企业名称未带「示例」或「（虚构）」标记时告警。"""
    out = []
    for m in RE_ORG.finditer(text):
        s = m.group(0)
        st = max(0, m.start() - 4)
        ctx = text[st:m.end() + 6]
        if any(mk in ctx for mk in R.ORG_MARKERS):
            continue
        out.append(_mk("org_name", s, m.span(), "未带虚构标记"))
    return out


def find_person_name(text):
    """疑似中文人名、且后面不带（虚构）后缀时告警。

    纯正则做中文人名识别会乱命中（"纪要""负责"这类普通词也是 2 字），
    所以只在**角色词之后**取候选：记录人 / 负责人 / 联系人 / 参会人 / 审批人 / 经办人。
    这与工单「2~4 字的疑似中文人名」的意图一致，且误报可控。
    """
    out = []
    seen = set()
    for role in R.PERSON_ROLES:
        for m in re.finditer(re.escape(role) + r"[:：]?\s*([\u4e00-\u9fa5]{2,4})", text):
            cand = m.group(1)
            # 取 2 字；前两字是复姓时取 3 字。不做 4 字贪婪匹配
            # （第一版用 {2,4} 贪婪，把「张三负责」整体当成 4 字人名）。
            s = cand[:3] if cand[:2] in R.COMPOUND_SURNAMES else cand[:2]
            if len(s) < R.PERSON_NAME_MIN or len(s) > R.PERSON_NAME_MAX:
                continue
            tail = text[m.start(1) + len(s):m.start(1) + len(s) + 6]
            if R.PERSON_SUFFIX in tail or "(虚构)" in tail:
                continue
            if s in PROVINCES or s in R.PERSON_STOPWORDS:
                continue
            if s in seen:
                continue
            seen.add(s)
            out.append(_mk("person_name", s, (m.start(1), m.start(1) + len(s)),
                           "未带（虚构）后缀"))
    return out


FINDERS = (
    ("mobile", find_mobile),
    ("landline", find_landline),
    ("email", find_email),
    ("id_card", find_id_card),
    ("bank_card", find_bank_card),
    ("uscc", find_uscc),
    ("address", find_address),
    ("plate", find_plate),
)


def scan_text(text, extra_finders=True):
    """扫描一段文本，返回 Finding 列表（按 span 升序）。"""
    out = []
    for _kind, fn in FINDERS:
        out.extend(fn(text))
    if extra_finders:
        out.extend(find_org_name(text))
        out.extend(find_person_name(text))
    out.sort(key=lambda f: (f["span"][0], f["kind"]))
    return out
