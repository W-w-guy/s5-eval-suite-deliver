# -*- coding: utf-8 -*-
"""虚构夹具：8 类检测项各一组「命中 / 不命中」样本，外加 1000 条性能夹具。

关键约束：**正例本身也必须是虚构的**。做法是不用真实号段/真实校验收敛值，
而是用 checksum 的「补校验位」函数从自选号段生成合法号码 ——
号段是手写的，没有对应用户，因此不构成真实个人信息。
"""
import json
import os

import checksum

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)

# ---- 手写号段，再由校验位算法补齐（不含真实归属） ----
MOBILE_OK = "13500000001"          # 1[3-9] 开头 11 位
MOBILE_BAD = "12500000001"         # 第 2 位不是 3-9
ID17 = "31000000000000001"
ID_OK = ID17 + checksum.id_card_check_char(ID17)
ID_BAD = ID17 + ("0" if checksum.id_card_check_char(ID17) != "0" else "1")
BANK_OK = "6200000000000000" + checksum.luhn_check_digit("6200000000000000")
BANK_BAD = BANK_OK[:-1] + ("0" if BANK_OK[-1] != "0" else "1")
USCC_BODY = "91310000MA1FL2XY3"
USCC_OK = USCC_BODY + checksum.uscc_check_char(USCC_BODY)
# 占位号段：前 2 位为 91，第 3~8 位恰为 999999（工单口径），校验位补齐
# —— 校验位必须合法，否则「排除占位号段」这段判断会被前面的校验位检查短路成死代码
USCC_PLACEHOLDER_BODY = "91" + "999999" + "MA1FL2XY3"
USCC_PLACEHOLDER = USCC_PLACEHOLDER_BODY + checksum.uscc_check_char(USCC_PLACEHOLDER_BODY)

FIXTURES = [
    # (类别, 命中?, 说明, 文本)
    ("mobile", True, "1[3-9] 开头 11 位", "联系电话 %s 请联系" % MOBILE_OK),
    ("mobile", False, "第 2 位是 2，不是手机号", "编号 %s 不是手机" % MOBILE_BAD),
    ("landline", True, "区号-号码", "前台电话 010-88880000 转 2"),
    ("landline", False, "没有区号", "编号 88880000 不是固话"),
    ("email", True, "标准邮箱", "发到 qa_owner@example.invalid 即可"),
    ("email", False, "缺少域名点号", "账号 qa_owner@example 不是邮箱"),
    ("id_card", True, "校验位通过", "身份证 %s 已登记" % ID_OK),
    ("id_card", False, "校验位不通过", "身份证 %s 校验失败" % ID_BAD),
    ("bank_card", True, "Luhn 通过", "卡号 %s 用于结算" % BANK_OK),
    ("bank_card", False, "Luhn 不通过", "卡号 %s 校验失败" % BANK_BAD),
    ("uscc", True, "校验位通过且非占位号段", "主体 %s 已备案" % USCC_OK),
    ("uscc", False, "第 3~8 位为 999999 占位", "主体 %s 为占位" % USCC_PLACEHOLDER),
    ("address", True, "省市区 + 路号", "地址：上海市浦东新区示例路 128 号 3 楼"),
    ("address", False, "只有路名没有号", "地址在示例路的某处"),
    ("address", False, "有省市区也有路号，但两者相距超出窗口（不该拼成一条地址）",
     "上海市" + "甲" * 40 + "示例路 128 号"),
    ("plate", True, "标准车牌", "车辆 沪A12345 已登记"),
    ("plate", False, "字形不符", "编号 A12345 不是车牌"),
]

EXTRA = [
    ("org_name", True, "企业名未带虚构标记", "由银河数据科技有限公司承接本单"),
    ("org_name", False, "带（虚构）标记", "由星辰（虚构）科技有限公司承接"),
    ("person_name", True, "人名未带（虚构）后缀", "记录人张三负责本次会议纪要"),
    ("person_name", False, "人名带（虚构）后缀", "记录人李四（虚构）负责纪要"),
]

NEGATIVE_ONLY = [
    "本条文本只有编号 KH-2026-0011 与金额 12800 分，不含任何敏感信息。",
    "会议结论：三条待办已确认，责任角色为招商主管。",
    "统计口径：采纳率 92.5%%，平均修改幅度 0.08。",
]


def write_fixtures(outdir=None):
    out = outdir or os.path.join(ROOT, "data")
    os.makedirs(outdir and os.path.join(out, "fixtures") or os.path.join(out, "fixtures"),
                exist_ok=True)
    pack = {"positive_negative": [], "extra": [], "clean": NEGATIVE_ONLY}
    for kind, hit, why, text in FIXTURES:
        pack["positive_negative"].append({"kind": kind, "hit": hit, "why": why, "text": text})
    for kind, hit, why, text in EXTRA:
        pack["extra"].append({"kind": kind, "hit": hit, "why": why, "text": text})

    d = os.path.join(out, "fixtures")
    with open(os.path.join(d, "cases.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(pack, f, ensure_ascii=False, indent=1, sort_keys=True)

    # 逐条单文件夹具，便于人工核对
    for i, c in enumerate(pack["positive_negative"], 1):
        with open(os.path.join(d, "case_%02d_%s.txt" % (i, c["kind"])),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write(c["text"] + "\n")
    for i, c in enumerate(pack["extra"], 1):
        with open(os.path.join(d, "extra_%02d_%s.txt" % (i, c["kind"])),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write(c["text"] + "\n")
    for i, t in enumerate(NEGATIVE_ONLY, 1):
        with open(os.path.join(d, "clean_%02d.txt" % i), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write(t + "\n")

    # 1000 条性能夹具（AC4）
    # 形态取 JSONL 而不是 1000 个独立 txt：评测集本来就是 JSONL 存，
    # 且 1000 个新建小文件在 Windows 上会触发逐文件实时防护扫描（实测冷扫 19.8s），
    # 那是磁盘/杀软开销而不是扫描器性能，会让买家首次运行 AC4 失败。
    perf_dir = os.path.join(out, "perf1000")
    os.makedirs(perf_dir, exist_ok=True)
    base = ("【虚构】会员入会引导第 %d 条：本次会议记录人王五（虚构），"
            "承接方为示例数据科技有限公司，编号 KH-2026-%04d，金额 %d 分，"
            "结论为按期交付并留档复核。")
    # 每 97 条插入一条含 error 级命中的用例：性能测试必须覆盖命中分支（走完校验位），
    # 否则测的只是「快速跳过」，不是最坏情况。
    with open(os.path.join(perf_dir, "cases_1000.jsonl"), "w",
              encoding="utf-8", newline="\n") as f:
        for i in range(1, 1001):
            text = base % (i, i, 10000 + i)
            if i % 97 == 0:
                text += " 联系电话 %s，身份证 %s。" % (MOBILE_OK, ID_OK)
            f.write(json.dumps({"case_key": "PF-%04d" % i, "text": text},
                               ensure_ascii=False) + "\n")
    return len(FIXTURES), len(EXTRA), 1000


if __name__ == "__main__":
    a, b, c = write_fixtures()
    print("WROTE pn=%d extra=%d perf=%d" % (a, b, c))
