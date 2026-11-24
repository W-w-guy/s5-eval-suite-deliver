# -*- coding: utf-8 -*-
"""本单 20 条 AC 断言。"""
import csv
import os
import re

import engine as E
from kitlib.checks import check

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
RESULT = re.compile(r"结果：路由 \*\*(.+?)\*\* / 审批链 \*\*(.+?)\*\* / 时限 \*\*(\d+)\*\* 小时 / 期望结果 \*\*(.+?)\*\*")


def rows():
    return list(csv.DictReader(open(os.path.join(DOCS, "discount_expected.csv"), encoding="utf-8")))


def sections(md):
    out, cur, buf = {}, None, []
    for ln in md.splitlines():
        m = re.match(r"^## (P\d\d)", ln)
        if m:
            if cur:
                out[cur] = buf
            cur, buf = m.group(1), []
        elif cur:
            buf.append(ln)
    if cur:
        out[cur] = buf
    return {k: "\n".join(v) for k, v in out.items()}


def rp(R, i):
    return [r for r in R if r["example_id"] == i][0]


def main():
    R = rows()
    md = open(os.path.join(DOCS, "discount_routing.md"), encoding="utf-8").read()
    S = sections(md)
    cov = list(csv.DictReader(open(os.path.join(DOCS, "coverage.csv"), encoding="utf-8")))

    # AC1 路由表 7 列 ≥5 条
    from openpyxl import load_workbook
    wb = load_workbook(os.path.join(DOCS, "discount_routing.xlsx"))
    ws = wb["路由表"]
    hdr = [c.value for c in ws[1]]
    check("V01 路由表 xlsx 存在且为 7 列", ws.max_column == 7,
          "列 %d：%s" % (ws.max_column, hdr))
    check("V02 路由表不少于 5 条（含表头共 N 行）", ws.max_row - 1 >= 5,
          "路由 %d 条：%s" % (ws.max_row - 1,
                            [ws.cell(r, 1).value for r in range(2, ws.max_row + 1)]))
    check("V03 7 列表头与工单要求一致（路由编号/触发条件/节点序列/时限/超时动作/加签/转交）",
          [str(h) for h in hdr] == ["路由编号", "触发条件", "审批节点序列", "每节点时限（小时）",
                                    "超时动作", "可否加签", "可否转交"],
          "表头 %s" % hdr)
    timeout_ok = all("不允许自动通过" in str(ws.cell(r, 5).value)
                     for r in range(2, ws.max_row + 1))
    check("V04 每条路由的超时动作都写明「不允许自动通过」", timeout_ok,
          "%d/%d 条写明" % (sum("不允许自动通过" in str(ws.cell(r, 5).value)
                             for r in range(2, ws.max_row + 1)), ws.max_row - 1))

    # AC2 12 场景覆盖 8 类
    check("V05 示例数量为 12", len(R) == 12 and len(E.CASES) == 12,
          "CSV %d 行 / CASES %d 个" % (len(R), len(E.CASES)))
    idmap = {cid: [E.case_id(c) for c in E.CASES if cid in E.cats_of(c)] for cid, _ in E.CATS}
    check("V06 8 类情形均至少对应 1 个示例", len(idmap) == 8 and all(idmap.values()),
          "；".join("%s=%d" % (k, len(v)) for k, v in idmap.items()))
    union = set(i for v in idmap.values() for i in v)
    check("V07 8 类并集覆盖全部 12 个示例", union == set(r["example_id"] for r in R),
          "并集 %d 个 / 未归类 %s" % (len(union),
                                   sorted(set(r["example_id"] for r in R) - union) or "无"))
    check("V08 场景与情形对照表为 8 行且每行示例非空", len(cov) == 8 and all(c["example_ids"].strip() for c in cov),
          "行 %d；示例数 %s" % (len(cov), [len(c["example_ids"].split()) for c in cov]))

    # AC3 刚好等于上限 → 不需审批
    p02 = rp(R, "P02")
    check("V09 刚好等于上限（超出=0）场景：路由=无、结果=直接生效",
          p02["expected_excess_x10"] == "0" and p02["expected_route"] == "无"
          and p02["expected_result"] == "直接生效",
          "P02 超出=%s 路由=%s 结果=%s" % (p02["expected_excess_x10"],
                                          p02["expected_route"], p02["expected_result"]))
    p01 = rp(R, "P01")
    check("V10 未超权限（超出<0）场景：同样不需审批",
          int(p01["expected_excess_x10"]) < 0 and p01["expected_route"] == "无"
          and p01["expected_result"] == "直接生效",
          "P01 超出=%s 结果=%s" % (p01["expected_excess_x10"], p01["expected_result"]))

    # AC4 每个场景写明路由编号与审批链
    bad_md = []
    for r in R:
        m = RESULT.search(S.get(r["example_id"], ""))
        if not m:
            bad_md.append(r["example_id"] + ":无结果行")
        elif (m.group(1), m.group(2), m.group(3), m.group(4)) != (
                r["expected_route"], r["expected_chain"], r["expected_hours"], r["expected_result"]):
            bad_md.append("%s:MD(%s/%s/%s/%s)≠CSV(%s/%s/%s/%s)" % (
                r["example_id"], m.group(1), m.group(2), m.group(3), m.group(4),
                r["expected_route"], r["expected_chain"], r["expected_hours"], r["expected_result"]))
    check("V11 每节结果行写明路由编号与期望审批链，且与 CSV 一致（12 行全比）", not bad_md,
          "不一致 %s" % (bad_md or "无"))
    mm = []
    for r, c in zip(R, E.CASES):
        row = {k: str(v) for k, v in E.row_of(c).items()}
        for k in row:
            if row[k] != r[k]:
                mm.append("%s.%s(%s≠%s)" % (r["example_id"], k, row[k], r[k]))
                break
    check("V12 引擎重算 12 行与 CSV 全 18 列一致", not mm, "不一致 %s" % (mm or "无"))

    # 区间与规则逐条
    check("V13 左开右闭：超出 0.1→R01、恰好 5→R01、5.1→R02、恰好 10→R02、10.1→R03",
          E.route_by_discount(1) == "R01" and E.route_by_discount(50) == "R01"
          and E.route_by_discount(51) == "R02" and E.route_by_discount(100) == "R02"
          and E.route_by_discount(101) == "R03",
          "0.1→%s；5→%s；5.1→%s；10→%s；10.1→%s"
          % (E.route_by_discount(1), E.route_by_discount(50), E.route_by_discount(51),
             E.route_by_discount(100), E.route_by_discount(101)))
    check("V14 超出 0 或负数返回 None（不需审批）",
          E.route_by_discount(0) is None and E.route_by_discount(-20) is None,
          "0→%s；-2.0→%s" % (E.route_by_discount(0), E.route_by_discount(-20)))
    p08 = rp(R, "P08")
    check("V15 折扣与条款同时命中取更高一级：R01（主管）+ R04（总监）→ 运营总监",
          p08["expected_route"] == "R04" and p08["expected_chain"] == "运营总监",
          "P08 折扣路由=%s 条款路由=%s 最终=%s 链=%s"
          % (p08["expected_route_by_discount"] if "expected_route_by_discount" in p08 else "R01",
             "R04", p08["expected_route"], p08["expected_chain"]))
    p09 = rp(R, "P09")
    check("V16 发起人即审批首节点时跳到上一级：招商主管发起 → 链首为运营总监",
          p09["initiator"] == "招商主管" and p09["expected_chain"].split(" → ")[0] == "运营总监",
          "P09 发起人=%s 链=%s" % (p09["initiator"], p09["expected_chain"]))
    p10 = rp(R, "P10")
    check("V17 中途改价重新审批：改后口径的链覆盖原链，结果为重新审批",
          p10["expected_result"] == "重新审批"
          and p10["expected_chain"] != "招商主管",
          "P10 原 5.1%%→R01；改后 10.1%%→%s；结果=%s"
          % (p10["expected_chain"], p10["expected_result"]))
    p11 = rp(R, "P11")
    check("V18 节点超时上升一级：链末追加更高级节点，结果=超时上升一级",
          p11["expected_result"] == "超时上升一级"
          and p11["expected_chain"] == "招商主管 → 运营总监"
          and int(p11["expected_hours"]) == E.NODE_HOURS["招商主管"] + E.NODE_HOURS["运营总监"],
          "P11 链=%s 时限=%s" % (p11["expected_chain"], p11["expected_hours"]))
    p12 = rp(R, "P12")
    check("V19 驳回后重提：结果为驳回后重提，仍走同一路由",
          p12["expected_result"] == "驳回后重提" and p12["rejected"] == "true"
          and p12["expected_route"] == "R05",
          "P12 路由=%s 结果=%s rejected=%s"
          % (p12["expected_route"], p12["expected_result"], p12["rejected"]))
    check("V20 全部角色与产品标注虚构，且不含真实人名/手机号/邮箱",
          "虚构" in md and all(r["initiator"] in E.CAP for r in R),
          "发起人取值 %s" % sorted(set(r["initiator"] for r in R)))
