# -*- coding: utf-8 -*-
"""交付件的数据源：字段 schema、34 个虚构用例、以及**手工填写的期望计数**。

关键约定：本文件里的 `hand` 是人工逐条核对后写死的计数，**不调用 scorer 计算**。
scorer 自己算出的计数与这里比对 —— 两条路径独立，任一处错都会被抓到。
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)

SCHEMA = {
    "contract_no": {"type": "string"},
    "sign_date": {"type": "date"},
    "total_amount": {"type": "money_fen", "critical": True},
    "tax_rate": {"type": "rate_bp"},
    "buyer_uscc": {"type": "uscc", "critical": True},
    "pay_cycle": {"type": "enum",
                  "mapping": {"月结": "monthly", "月结30天": "monthly", "季度": "quarterly",
                              "quarterly": "quarterly", "monthly": "monthly"}},
    "pay_nodes": {"type": "list", "key": "seq"},
    "summary": {"type": "summary"},
}

PASS_THRESHOLD = 0.8

# 虚构固定常量（无随机）
NODES3 = [
    {"seq": 1, "ratio_bp": 3000, "due": "2026-06-01"},
    {"seq": 2, "ratio_bp": 4000, "due": "2026-09-01"},
    {"seq": 3, "ratio_bp": 3000, "due": "2026-12-01"},
]
USCC = "91310000MA1FL2XY3K"
BEST = {
    "contract_no": "HT-2026-0011",
    "sign_date": "2026-05-06",
    "total_amount": 1280000,
    "tax_rate": 600,
    "buyer_uscc": USCC,
    "pay_cycle": "monthly",
    "pay_nodes": NODES3,
    "summary": ["付款方式为分期", "含税总价固定", "逾期按日计息"],
}


def case(cid, title, expected, actual, hand, passed, why=""):
    return {"id": cid, "title": title, "expected": expected, "actual": actual,
            "hand": hand, "passed": passed, "why": why}


def _merge(**kw):
    d = dict(BEST)
    d.update(kw)
    return d


def build_cases():
    C = []
    add = C.append
    full = {"contract_no": (1, 0, 0, 0), "sign_date": (1, 0, 0, 0),
            "total_amount": (1, 0, 0, 0), "tax_rate": (1, 0, 0, 0),
            "buyer_uscc": (1, 0, 0, 0), "pay_cycle": (1, 0, 0, 0),
            "pay_nodes": (3, 0, 0, 0), "summary": (3, 0, 0, 0)}

    def h(**over):
        d = {k: list(v) for k, v in full.items()}
        for k, v in over.items():
            d[k.replace("__", "-")] = list(v)
        return d

    # ---- string：正例 3 ----
    add(case("C01", "全字段完全一致（基准）", BEST, BEST, h(), True, "8 类型全对"))
    add(case("C02", "string 全半角与大小写差异视为相等", BEST,
             _merge(contract_no=" ｈｔ－2026－0011 "),
             h(contract_no=[1, 0, 0, 0]), True, "NFKC + casefold"))
    add(case("C03", "string 内部多余空白折叠后相等", BEST,
             _merge(contract_no="HT-2026-0011"), h(), True, "空白折叠"))
    # ---- string：反例 1 ----
    add(case("C04", "string 内容不同判 wrong", BEST,
             _merge(contract_no="HT-2026-0012"),
             h(contract_no=[0, 1, 0, 0]), True, "字符串不等"))
    # ---- date：正例 2 ----
    add(case("C05", "date 斜杠分隔写法归一后相等", BEST,
             _merge(sign_date="2026/5/6"), h(), True, "多写法统一 ISO"))
    add(case("C06", "date 中文写法归一后相等", BEST,
             _merge(sign_date="2026年5月6日"), h(), True, "中文日期"))
    # ---- date：反例 1 ----
    add(case("C07", "date 差一天判 wrong", BEST,
             _merge(sign_date="2026-05-07"),
             h(sign_date=[0, 1, 0, 0]), True, "日期不等"))
    # ---- money：正例 1 / 反例 2（AC3 核心） ----
    add(case("C08", "money 整数严格相等", BEST, BEST, h(), True, ""))
    add(case("C09", "money 相差 1 分即判 wrong（critical 生效）", BEST,
             _merge(total_amount=1280001),
             h(total_amount=[0, 1, 0, 0]), False, "1 分不容差"))
    add(case("C10", "money 用浮点表示时拒绝归一化并判 wrong", BEST,
             _merge(total_amount=12800.0),
             h(total_amount=[0, 1, 0, 0]), False, "浮点被拒"))
    # ---- rate：正例 1 / 反例 1 ----
    add(case("C11", "rate_bp 整数严格相等", BEST, BEST, h(), True, ""))
    add(case("C12", "rate_bp 相差 1 个基点判 wrong", BEST,
             _merge(tax_rate=601),
             h(tax_rate=[0, 1, 0, 0]), True, "1bp 不容差"))
    # ---- uscc：正例 2 / 反例 1 ----
    add(case("C13", "uscc 小写归一后相等", BEST,
             _merge(buyer_uscc=USCC.lower()), h(), True, "转大写"))
    add(case("C14", "uscc 带空格归一后相等", BEST,
             _merge(buyer_uscc=" " + USCC[:9] + " " + USCC[9:] + " "), h(), True, "去空白"))
    add(case("C15", "uscc 只错一位即判 wrong（critical 生效）", BEST,
             _merge(buyer_uscc=USCC[:-1] + "M"),
             h(buyer_uscc=[0, 1, 0, 0]), False, "critical"))
    # ---- enum：正例 2 / 反例 1 ----
    add(case("C16", "enum 别名 月结30天 归一到 monthly", BEST,
             _merge(pay_cycle="月结30天"), h(), True, "映射表"))
    add(case("C17", "enum 别名 季度 归一到 quarterly（期望改季度）", _merge(pay_cycle="quarterly"),
             _merge(pay_cycle="季度"), h(pay_cycle=[1, 0, 0, 0]), True, "映射表"))
    add(case("C18", "enum 落到不同规范值判 wrong", BEST,
             _merge(pay_cycle="季度"),
             h(pay_cycle=[0, 1, 0, 0]), True, "规范值不同"))
    # ---- list：正例 1 / 反例 3（AC2 核心） ----
    add(case("C19", "list 三节点完全一致", BEST, BEST, h(), True, ""))
    add(case("C20", "list 多 1 项记 extra（AC2）", BEST,
             _merge(pay_nodes=NODES3 + [{"seq": 4, "ratio_bp": 0, "due": "2027-01-01"}]),
             h(pay_nodes=[3, 0, 0, 1]), True, "多一项=extra"))
    add(case("C21", "list 少 1 项记 missing（AC2）", BEST,
             _merge(pay_nodes=NODES3[:2]),
             h(pay_nodes=[2, 0, 1, 0]), True, "少一项=missing"))
    add(case("C22", "list 同 seq 但金额不同判 wrong", BEST,
             _merge(pay_nodes=[NODES3[0], dict(NODES3[1], ratio_bp=3900), NODES3[2]]),
             h(pay_nodes=[2, 1, 0, 0]), True, "逐项比对"))
    # ---- summary：正例 2 / 反例 2 ----
    add(case("C23", "summary 结构化要点全中", BEST, BEST, h(), True, ""))
    add(case("C24", "summary 少一个要点记 missing", BEST,
             _merge(summary=BEST["summary"][:2]),
             h(summary=[2, 0, 1, 0]), True, "要点缺失"))
    add(case("C25", "summary 自由文本按要点命中计 recall", BEST,
             _merge(summary="本合同付款方式为分期，含税总价固定，逾期按日计息。"), h(), True,
             "文本口径"))
    add(case("C26", "summary 结构化多出无关要点记 extra", BEST,
             _merge(summary=BEST["summary"] + ["附赠一次场地使用"]),
             h(summary=[3, 0, 0, 1]), True, "多要点=extra"))
    # ---- 缺失 / 类型错误 ----
    add(case("C27", "字段整体缺失记 missing", BEST,
             {k: v for k, v in BEST.items() if k != "tax_rate"},
             h(tax_rate=[0, 0, 1, 0]), True, "缺字段"))
    add(case("C28", "money 字段缺失（critical）→ 用例不通过", BEST,
             {k: v for k, v in BEST.items() if k != "total_amount"},
             h(total_amount=[0, 0, 1, 0]), False, "critical missing"))
    add(case("C29", "uscc 长度不足 → 归一化失败判 wrong", BEST,
             _merge(buyer_uscc="91310000MA"), h(buyer_uscc=[0, 1, 0, 0]), False, "长度校验"))
    # ---- 非 critical 单错：F1 仍过阈值 → 通过 ----
    add(case("C30", "仅 1 个非 critical 字段错，F1 高于阈值仍通过", BEST,
             _merge(contract_no="HT-2026-9911"),
             h(contract_no=[0, 1, 0, 0]), True, "阈值 0.8"))
    # ---- 多错：F1 低于阈值 → 不通过 ----
    add(case("C31", "多个非 critical 字段错，F1 低于阈值不通过", BEST,
             _merge(contract_no="X1", sign_date="2030-01-01", tax_rate=999,
                    pay_cycle="季度", pay_nodes=NODES3[:1], summary=["无关"]),
             h(contract_no=[0, 1, 0, 0], sign_date=[0, 1, 0, 0], tax_rate=[0, 1, 0, 0],
               pay_cycle=[0, 1, 0, 0], pay_nodes=[1, 0, 2, 0], summary=[0, 0, 3, 1]),
             False, "F1 低"))
    # ---- AC1：8 种类型各自的正反例都在上面覆盖，这里补全「全对+全错」对照 ----
    add(case("C32", "所有字段都不一致（全错对照）", BEST,
             {"contract_no": "Z", "sign_date": "2030-12-31", "total_amount": 1,
              "tax_rate": 1, "buyer_uscc": "91310000AAAAAAAAAA", "pay_cycle": "quarterly",
              "pay_nodes": [{"seq": 9, "ratio_bp": 1, "due": "2030-01-01"}],
              "summary": ["全不相干"]},
             h(contract_no=[0, 1, 0, 0], sign_date=[0, 1, 0, 0], total_amount=[0, 1, 0, 0],
               tax_rate=[0, 1, 0, 0], buyer_uscc=[0, 1, 0, 0], pay_cycle=[0, 1, 0, 0],
               pay_nodes=[0, 0, 3, 1], summary=[0, 0, 3, 1]),
             False, "全错"))
    # ---- 边界：空数组 ----
    add(case("C33", "list 期望为空且实际为空 → 无计数不报错", _merge(pay_nodes=[]),
             _merge(pay_nodes=[]), h(pay_nodes=[0, 0, 0, 0]), True, "空数组"))
    add(case("C34", "list 期望为空但实际有 2 项 → 2 个 extra", _merge(pay_nodes=[]),
             _merge(pay_nodes=NODES3[:2]), h(pay_nodes=[0, 0, 0, 2]), True, "全 extra"))
    return C


def write_all(outdir=None):
    """把 schema 与用例写到 data/ 下（JSON + jsonl），返回写入清单。"""
    out = outdir or os.path.join(ROOT, "data")
    os.makedirs(os.path.join(out, "fixtures"), exist_ok=True)
    cases = build_cases()
    with open(os.path.join(out, "cases.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    with open(os.path.join(out, "field_schema.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(SCHEMA, f, ensure_ascii=False, indent=1, sort_keys=True)
    for c in cases:
        with open(os.path.join(out, "fixtures", c["id"] + ".json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(c, f, ensure_ascii=False, indent=1, sort_keys=True)
    return len(cases)


if __name__ == "__main__":
    n = write_all()
    print("WROTE cases=%d fields=%d" % (n, len(SCHEMA)))
