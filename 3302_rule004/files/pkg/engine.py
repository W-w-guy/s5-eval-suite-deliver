# -*- coding: utf-8 -*-
"""折扣审批路由引擎 + 12 个审批场景（全部虚构数据，仅用于本单交付）。

口径（均为虚构值）：
  百分点数值内部以「百分点 × 10」的整数表示（51 = 5.1 个百分点），避免浮点误差。
  角色折扣上限：招商业务员 5.0；招商主管 10.0；运营总监 15.0；总经理 20.0（百分点×10：50/100/150/200）
  超出 = 折扣率 − 发起人上限；**等于上限（超出 = 0）不需要审批**。
  折扣区间判定（左开右闭）：
    0 < 超出 ≤ 5      → R01 招商主管
    5 < 超出 ≤ 10     → R02 运营总监
    超出 > 10         → R03 总经理
  特殊条款路由（命中即需审批）：
    免押金 → R04 运营总监；延期付款 → R05 运营总监；免租期 > 30 天 → R06 总经理
  同时命中折扣与特殊条款：取两者中**层级更高**的一条，不叠加串行。
  审批人与发起人为同一角色：跳过该节点，从下一节点起（即跳到上一级）。
  节点超时：自动上升一级（提醒为主），**任何情况下不允许自动通过**。
  中途修改报价：按修改后口径**重新走审批**，原审批作废。
"""
from fractions import Fraction as F

LEVEL = {"招商主管": 1, "运营总监": 2, "总经理": 3}
NODE_HOURS = {"招商主管": 24, "运营总监": 12, "总经理": 6}
CAP = {"招商业务员": 50, "招商主管": 100, "运营总监": 150, "总经理": 200}

ROUTES = [
    dict(id="R01", cond="折扣超出 0~5 个百分点（0 < 超出 ≤ 5）", chain=("招商主管",),
         clause=None, hi=50, lo=0),
    dict(id="R02", cond="折扣超出 5~10 个百分点（5 < 超出 ≤ 10）", chain=("运营总监",),
         clause=None, hi=100, lo=50),
    dict(id="R03", cond="折扣超出 10 个百分点以上（超出 > 10）", chain=("总经理",),
         clause=None, hi=None, lo=100),
    dict(id="R04", cond="含特殊条款：免押金", chain=("运营总监",), clause="免押金",
         hi=None, lo=None),
    dict(id="R05", cond="含特殊条款：延期付款", chain=("运营总监",), clause="延期付款",
         hi=None, lo=None),
    dict(id="R06", cond="含特殊条款：免租期超过 30 天", chain=("总经理",), clause="免租期超过 30 天",
         hi=None, lo=None),
]

CLAUSES = ["免押金", "延期付款", "免租期超过 30 天"]


def pct(x10):
    """百分点×10 → 展示字符串。"""
    return ("%d.%d" % (x10 // 10, x10 % 10)) if x10 % 10 else ("%d" % (x10 // 10))


def route_by_discount(excess_x10):
    """左开右闭：恰好等于区间上界仍留在本档。返回路由编号或 None（不需审批）。"""
    if excess_x10 <= 0:
        return None
    for r in ROUTES[:3]:
        if r["hi"] is None or excess_x10 <= r["hi"]:
            return r["id"]
    return None


def route_by_clause(clause):
    if not clause:
        return None
    for r in ROUTES[3:]:
        if r["clause"] == clause:
            return r["id"]
    return None


def route_of(rid):
    for r in ROUTES:
        if r["id"] == rid:
            return r
    return None


def top_level(rids):
    """多条命中时取层级最高的一条。"""
    best, bl = None, -1
    for rid in rids:
        if rid is None:
            continue
        r = route_of(rid)
        lv = max(LEVEL[n] for n in r["chain"])
        if lv > bl:
            best, bl = rid, lv
    return best


def skip_same_role(chain, initiator):
    """审批链首个节点与发起人同角色时跳过，从下一节点起。"""
    ch = list(chain)
    if ch and ch[0] == initiator:
        ch = ch[1:]
        if not ch:
            lv = LEVEL[chain[0]] + 1
            up = [k for k, v in LEVEL.items() if v == lv]
            ch = [up[0]] if up else ["总经理"]
    return tuple(ch)


def advance(chain):
    """超时上升一级：在链末追加下一级。"""
    lv = max(LEVEL[n] for n in chain)
    up = [k for k, v in LEVEL.items() if v == lv + 1]
    return tuple(chain) + (up[0],) if up else tuple(chain)


def evaluate(c):
    cap = CAP[c["initiator"]]
    exc = c["disc_x10"] - cap
    by_d = route_by_discount(exc)
    by_c = route_by_clause(c.get("clause"))
    rid = top_level([by_d, by_c])
    if rid is None:
        return dict(cap_x10=cap, excess_x10=exc, route="无", chain="（无需审批）",
                    chain_len=0, hours=0, overflow=False, result="直接生效",
                    route_by_discount=str(by_d or "无"), route_by_clause=str(by_c or "无"),
                    note="折扣 %s%% 未超出%s上限 %s%%，且无特殊条款 → 不需审批，直接生效"
                         % (pct(c["disc_x10"]), c["initiator"], pct(cap)))

    r = route_of(rid)
    chain = skip_same_role(r["chain"], c["initiator"])
    hours = sum(NODE_HOURS[n] for n in chain)
    result = "待审批"
    note = "命中 %s（%s）" % (rid, r["cond"])
    if by_d and by_c and by_d != by_c:
        note += "；同时命中折扣路由 %s 与条款路由 %s，取层级更高的 %s，不叠加" % (by_d, by_c, rid)
    if r["chain"][0] == c["initiator"]:
        note += "；审批首节点与发起人同角色（%s），跳过该节点" % c["initiator"]

    if c.get("revised_x10") is not None:
        exc2 = c["revised_x10"] - cap
        rid2 = route_by_discount(exc2)
        r2 = route_of(rid2) if rid2 else None
        chain = skip_same_role(r2["chain"], c["initiator"]) if r2 else ("（无需审批）",)
        hours = sum(NODE_HOURS[n] for n in chain) if r2 else 0
        result = "重新审批"
        note += "；审批中途发起人将折扣从 %s%% 改为 %s%%，原审批作废，按新口径重新走（%s）" % (
            pct(c["disc_x10"]), pct(c["revised_x10"]), rid2 or "无需审批")
        rid = rid2 or "无"
        if not rid2:
            return dict(cap_x10=cap, excess_x10=exc2, route="无", chain="（无需审批）",
                        chain_len=0, hours=0, overflow=False, result="直接生效",
                        route_by_discount="无", route_by_clause=str(by_c or "无"),
                        note=note)

    if c.get("rejected"):
        result = "驳回后重提"
        note += "；上一轮被驳回，重提后按原路由重新审批"
    if c.get("timeout"):
        chain2 = advance(chain)
        note += "；节点 %s 超时 %d 小时未处理 → 自动上升一级到 %s（不允许自动通过）" % (
            chain[-1], NODE_HOURS[chain[-1]], chain2[-1])
        chain = chain2
        hours = sum(NODE_HOURS[n] for n in chain)
        result = "超时上升一级"

    return dict(cap_x10=cap, excess_x10=exc, route=rid,
                chain=" → ".join(chain), chain_len=len(chain), hours=hours,
                overflow=bool(c.get("overflow", False)), result=result,
                route_by_discount=str(by_d or "无"), route_by_clause=str(by_c or "无"),
                note=note)


CATS = [
    ("D1", "未超权限直接生效"),
    ("D2", "刚好等于上限（不需审批）"),
    ("D3", "超出 0.1 个百分点"),
    ("D4", "同时命中折扣与特殊条款时取更高一级"),
    ("D5", "审批人与发起人为同一人时跳到上一级"),
    ("D6", "审批中途发起人修改报价导致重新审批"),
    ("D7", "节点超时上升一级"),
    ("D8", "驳回后重提"),
]

CASES = [
    dict(id="P01", cats=["D1"], initiator="招商业务员", product="B 级独立办公室", months=12,
         disc_x10=30, clause=None,
         scene="招商业务员报价折扣 3.0%，未超其 5.0% 上限，无特殊条款"),
    dict(id="P02", cats=["D2"], initiator="招商业务员", product="B 级独立办公室", months=18,
         disc_x10=50, clause=None,
         scene="招商业务员报价折扣**恰好 5.0%**，等于其上限，按口径不需审批"),
    dict(id="P03", cats=["D3"], initiator="招商业务员", product="A 级独立办公室", months=24,
         disc_x10=51, clause=None,
         scene="招商业务员报价折扣 5.1%，**只超出 0.1 个百分点**，须走 R01"),
    dict(id="P04", cats=["D3"], initiator="招商业务员", product="B 级独立办公室", months=12,
         disc_x10=100, clause=None,
         scene="招商业务员报价折扣 10.0%，超出**恰好 5 个百分点**，左开右闭仍落 R01"),
    dict(id="P05", cats=["D3"], initiator="招商业务员", product="A 级独立办公室", months=36,
         disc_x10=101, clause=None,
         scene="招商业务员报价折扣 10.1%，超出 5.1 个百分点，跨到 R02"),
    dict(id="P06", cats=["D3"], initiator="招商业务员", product="A 级独立办公室", months=24,
         disc_x10=150, clause=None,
         scene="招商业务员报价折扣 15.0%，超出**恰好 10 个百分点**，仍落 R02 未越到 R03"),
    dict(id="P07", cats=["D3"], initiator="招商业务员", product="整层办公室", months=36,
         disc_x10=151, clause=None,
         scene="招商业务员报价折扣 15.1%，超出 10.1 个百分点，落 R03 总经理"),
    dict(id="P08", cats=["D4"], initiator="招商业务员", product="A 级独立办公室", months=24,
         disc_x10=51, clause="免押金",
         scene="折扣 5.1%（本应 R01 招商主管）**同时**含免押金条款（R04 运营总监），取更高一级"),
    dict(id="P09", cats=["D5"], initiator="招商主管", product="A 级独立办公室", months=24,
         disc_x10=101, clause=None,
         scene="发起人本身是招商主管，折扣 10.1% 命中 R01 首节点即招商主管 → 跳到运营总监"),
    dict(id="P10", cats=["D6"], initiator="招商业务员", product="B 级独立办公室", months=18,
         disc_x10=51, clause=None, revised_x10=101,
         scene="原报价折扣 5.1% 走 R01；审批中途发起人改为 10.1%，须按新口径重新审批"),
    dict(id="P11", cats=["D7"], initiator="招商业务员", product="A 级独立办公室", months=24,
         disc_x10=51, clause=None, timeout=True,
         scene="折扣 5.1% 走 R01，招商主管节点超时未处理 → 自动上升一级到运营总监"),
    dict(id="P12", cats=["D8"], initiator="招商业务员", product="B 级独立办公室", months=12,
         disc_x10=80, clause="延期付款", rejected=True,
         scene="折扣 8.0% 且含延期付款条款，首次被驳回，重提后重新审批"),
]

COLS = [
    "example_id", "scene", "initiator", "cap_x10", "product", "months", "disc_x10",
    "clause", "revised_x10", "timeout", "rejected",
    "expected_excess_x10", "expected_route", "expected_chain", "expected_chain_len",
    "expected_hours", "expected_result", "expected_note",
]


def case_id(c):
    return c["id"]


def cats_of(c):
    return c["cats"]


def row_of(c):
    e = evaluate(c)
    r = dict(example_id=c["id"], scene=c["scene"], initiator=c["initiator"],
             cap_x10=e["cap_x10"], product=c["product"], months=c["months"],
             disc_x10=c["disc_x10"], clause=(c.get("clause") or ""),
             revised_x10=("" if c.get("revised_x10") is None else c["revised_x10"]),
             timeout=("true" if c.get("timeout") else "false"),
             rejected=("true" if c.get("rejected") else "false"))
    for k in ("excess_x10", "route", "chain", "chain_len", "hours", "result", "note"):
        r["expected_" + k] = e[k]
    return {k: r[k] for k in COLS}
