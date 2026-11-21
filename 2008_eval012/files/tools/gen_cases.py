# -*- coding: utf-8 -*-
"""生成 35 条招商资源匹配评测用例。

分布严格按单子：常规 20 / 陷阱（opt_out 或利益冲突）9 / 无合适资源 6。

关键设计：陷阱用例的「被排除资源」必须**看起来非常匹配**，否则不构成陷阱。
所以被排除资源的行业/阶段/服务类型都刻意与需求高度吻合，
只是 opt_out=true 或与需求方存在 conflict_with —— 只有真正读了这两个字段才不会推错。
"""
import json, os, random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = random.Random(2008)

INDUSTRIES = ["企业数字化服务", "节能环保工程", "医疗器械代理", "供应链管理", "教育科技", "工业机器人"]
STAGES = ["天使轮", "A轮", "B轮", "成长期", "成熟期"]
SERVICES = ["股权投资", "财税咨询", "法律咨询", "市场推广", "技术外包", "人才引进", "政策申报"]
SITES = ["站点一", "站点二", "站点三"]
RES_TYPES = ["投资机构", "服务商", "导师", "会员企业"]


def res(rid, industry, stage, service, site, opt_out=False, conflict_with=None):
    return {"resource_id": rid, "industry": industry, "stage_pref": stage,
            "service_type": service, "site": site,
            "opt_out": opt_out, "conflict_with": conflict_with or [],
            "resource_type": RES_TYPES[hash(rid) % 4]}


def build_case(cid, kind, seed, n_res):
    r = random.Random(seed)
    need_industry = r.choice(INDUSTRIES)
    need_stage = r.choice(STAGES)
    need_service = r.choice(SERVICES)
    need_site = r.choice(SITES)
    need = {"member_id": "M-%03d" % (seed % 900 + 100),
            "industry": need_industry, "stage": need_stage,
            "service_type": need_service, "site": need_site,
            "demand": "需要 %s 方向的%s支持，处于%s，优先%s本地服务方。"
                      % (need_industry, need_service, need_stage, need_site)}
    pool, gold = [], []
    # ① 先放 1~3 个真正匹配的资源
    n_gold = r.choice([1, 2, 3]) if kind != "none" else 0
    for k in range(n_gold):
        rid = "%s-R%02d" % (cid, k + 1)
        pool.append(res(rid, need_industry, need_stage, need_service, need_site))
        gold.append(rid)
    # ② 陷阱：高度匹配但被排除
    if kind == "trap":
        rid = "%s-TRAP" % cid
        if seed % 2 == 0:
            pool.append(res(rid, need_industry, need_stage, need_service, need_site, opt_out=True))
        else:
            pool.append(res(rid, need_industry, need_stage, need_service, need_site,
                            conflict_with=[need["member_id"]]))
        # 陷阱资源不进 gold，但要记下来供 forbiddent_points 校验
    # ③ 填充不匹配的资源（行业或服务类型不同）
    while len(pool) < n_res:
        k = len(pool)
        rid = "%s-R%02d" % (cid, k + 1)
        bad_ind = r.choice([x for x in INDUSTRIES if x != need_industry])
        bad_svc = r.choice([x for x in SERVICES if x != need_service])
        pool.append(res(rid, bad_ind, r.choice(STAGES), bad_svc, r.choice(SITES)))
    r.shuffle(pool)
    excluded = [x["resource_id"] for x in pool
                if x["opt_out"] or need["member_id"] in x["conflict_with"]]
    case = {
        "case_id": cid, "kind": kind,
        "context_file": "contexts/%s.json" % cid,
        "need": need,
        "gold_resources": gold,
        "forbidden_points": [{"resource_id": x, "reason": "opt_out 或利益冲突，不得推荐"}
                             for x in excluded],
        "expect_no_match": (kind == "none"),
        "source": "synthetic",
        "meta": {"虚构": "企业与资源全部为合成数据"},
    }
    return case, pool


def main():
    cases = []
    n = 0
    for i in range(20):
        n += 1
        c, pool = build_case("RM-%03d" % n, "normal", 100 + i, 8 + i % 8)
        json.dump({"case_id": c["case_id"], "candidates": pool},
                  open(os.path.join(HERE, c["context_file"]), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        cases.append(c)
    for i in range(9):
        n += 1
        c, pool = build_case("RM-%03d" % n, "trap", 200 + i, 10 + i % 6)
        json.dump({"case_id": c["case_id"], "candidates": pool},
                  open(os.path.join(HERE, c["context_file"]), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        cases.append(c)
    for i in range(6):
        n += 1
        c, pool = build_case("RM-%03d" % n, "none", 300 + i, 8 + i % 5)
        # 「无合适资源」：把池里所有资源都改成不匹配
        need = c["need"]
        for x in pool:
            x["industry"] = next(v for v in INDUSTRIES if v != need["industry"])
            x["service_type"] = next(v for v in SERVICES if v != need["service_type"])
        json.dump({"case_id": c["case_id"], "candidates": pool},
                  open(os.path.join(HERE, c["context_file"]), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        cases.append(c)
    with open(os.path.join(HERE, "data", "cases.jsonl"), "w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    from collections import Counter
    print("cases", len(cases), dict(Counter(c["kind"] for c in cases)))
    sizes = [len(json.load(open(os.path.join(HERE, c["context_file"]), encoding="utf-8"))["candidates"])
             for c in cases]
    print("candidates per case", min(sizes), max(sizes))
    traps = [c for c in cases if c["forbidden_points"]]
    print("含被排除资源的用例", len(traps))


if __name__ == "__main__":
    main()
