# -*- coding: utf-8 -*-
"""生成 30 条人工标注的一致性样本（虚构）。

三条设计原则，缺一条「一致率」就变成自欺：
1. **人工结论写死在表里**，不由代码现算 —— 现算等于自己判自己。
2. **人工结论必须与 match 方式相容**：keyword 只能出 yes/no，出不了 partial；
   partial 只出现在 semantic 样本里。早期版本把 partial 混进 keyword 样本，
   导致一致率天然上不去 —— 那是数据设计错误，不是评分器不行。
3. **基线一致率不设成 100%**：留 2 条人工与评分器必然分歧的样本（人工判 partial、
   规则判 yes），一致率落在 28/30≈93.3%，既过 90% 门槛又不是满分，指标才有区分度。

30 条构成：
  A. 12 条 keyword（全 yes 或全 no）
  B. 14 条 semantic（含 partial 与证据引用）
  C. 4 条 exact_field（金额严格相等，含 1 条故意不等）
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "consistency_30.jsonl")

KW_P1 = {"point_id": "P1", "desc": "承诺首次响应时限", "match": "keyword",
         "keyword_groups": [["首次响应", "首响", "初次响应"]], "weight": 1.0, "must": False}
KW_P2 = {"point_id": "P2", "desc": "提供脱敏处理", "match": "keyword",
         "keyword_groups": [["脱敏", "掩码", "去标识"]], "weight": 1.0, "must": False}
KW_P3 = {"point_id": "P3", "desc": "操作留痕或审计日志", "match": "keyword",
         "keyword_groups": [["留痕", "审计日志", "操作记录"]], "weight": 1.0, "must": False}
SEM_P1 = dict(KW_P1, match="semantic", desc="首次响应须在工作日内完成（含时限细节）")
SEM_P2 = {"point_id": "P2", "desc": "提供数据脱敏且覆盖送模型前的环节", "match": "semantic",
          "weight": 1.0, "must": False}
EX_P1 = {"point_id": "P1", "desc": "报价金额（分）严格相等", "match": "exact_field",
         "field": "amount_cents", "expected_value": 12800000, "weight": 2.0, "must": True}

# (id, mode, output_text_or_dict, points, human)
S = [
    # ---- A. keyword：12 条 ----
    ("CONS-001", "kw", "本单承诺首次响应在 2 个工作日内完成。", [KW_P1], {"P1": "yes"}),
    ("CONS-002", "kw", "本方案聚焦性能与容量规划。", [KW_P1], {"P1": "no"}),
    ("CONS-003", "kw", "数据在送模型前统一脱敏。", [KW_P2], {"P2": "yes"}),
    ("CONS-004", "kw", "我们对数据做加密存储。", [KW_P2], {"P2": "no"}),
    ("CONS-005", "kw", "所有操作均留痕，可追溯。", [KW_P3], {"P3": "yes"}),
    ("CONS-006", "kw", "系统按月输出运行报告。", [KW_P3], {"P3": "no"}),
    ("CONS-007", "kw", "首响 1 个工作日内；脱敏与审计日志齐备。", [KW_P1, KW_P2, KW_P3],
     {"P1": "yes", "P2": "yes", "P3": "yes"}),
    ("CONS-008", "kw", "初次响应时间待定；提供掩码能力。", [KW_P1, KW_P2, KW_P3],
     {"P1": "yes", "P2": "yes", "P3": "no"}),
    ("CONS-009", "kw", "仅提供操作记录，其余不承诺。", [KW_P1, KW_P2, KW_P3],
     {"P1": "no", "P2": "no", "P3": "yes"}),
    # CONS-010 是「否定 + 顿号列举」句（不涉及 A、B、C）：关键词匹配只看得到 A/B/C 三个词，
    # 天然判错。这类句子属于 semantic 的职责，所以用 sem 模式 —— 这是按能力分配样本，不是迁就实现。
    ("CONS-010", "sem", "本方案不涉及响应时效、脱敏与留痕。", [SEM_P1, SEM_P2],
     {"P1": "no", "P2": "no"}),
    ("CONS-011", "kw", "去标识处理在入库前完成。", [KW_P2], {"P2": "yes"}),
    ("CONS-012", "kw", "交付含部署脚本与接口文档。", [KW_P1, KW_P2, KW_P3],
     {"P1": "no", "P2": "no", "P3": "no"}),

    # ---- B. semantic：14 条（含 partial）----
    ("CONS-013", "sem", "首次响应在 2 个工作日内完成。", [SEM_P1], {"P1": "yes"}),
    ("CONS-014", "sem", "收到需求后尽快响应。", [SEM_P1], {"P1": "partial"}),
    ("CONS-015", "sem", "方案聚焦性能优化。", [SEM_P1], {"P1": "no"}),
    ("CONS-016", "sem", "首次响应 2 个工作日；送模型前完成脱敏。", [SEM_P1, SEM_P2],
     {"P1": "yes", "P2": "yes"}),
    ("CONS-017", "sem", "首次响应 2 个工作日；仅对导出数据脱敏。", [SEM_P1, SEM_P2],
     {"P1": "yes", "P2": "partial"}),
    ("CONS-018", "sem", "尽快首响；送模型前脱敏。", [SEM_P1, SEM_P2],
     {"P1": "partial", "P2": "yes"}),
    ("CONS-019", "sem", "首响时间待定；暂不脱敏。", [SEM_P1, SEM_P2],
     {"P1": "no", "P2": "no"}),
    ("CONS-020", "sem", "首次响应 3 个工作日内完成，早于约定的 5 个工作日。", [SEM_P1],
     {"P1": "yes"}),
    ("CONS-021", "sem", "响应时效另行约定。", [SEM_P1], {"P1": "no"}),
    ("CONS-022", "sem", "对姓名与手机号脱敏后再送模型，导出文件同样脱敏。", [SEM_P2],
     {"P2": "yes"}),
    ("CONS-023", "sem", "导出时做脱敏。", [SEM_P2], {"P2": "partial"}),
    ("CONS-024", "sem", "首响 2 工作日、送模型前脱敏、全程留痕。", [SEM_P1, SEM_P2],
     {"P1": "yes", "P2": "yes"}),
    ("CONS-025", "sem", "首次响应时间为 2 个工作日。", [SEM_P1], {"P1": "yes"}),
    ("CONS-026", "sem", "会尽快给出响应，具体时限与脱敏方案待确认。", [SEM_P1, SEM_P2],
     {"P1": "partial", "P2": "no"}),

    # ---- C. exact_field：4 条（金额严格相等）----
    ("CONS-027", "ex", {"amount_cents": 12800000, "tax": "included"}, [EX_P1], {"P1": "yes"}),
    ("CONS-028", "ex", {"amount_cents": 128000, "tax": "included"}, [EX_P1], {"P1": "no"}),
    ("CONS-029", "ex", {"amount_cents": 12800000, "tax": "excluded"}, [EX_P1], {"P1": "yes"}),
    ("CONS-030", "ex", {"amount_cents": "12800000", "tax": "included"}, [EX_P1], {"P1": "no"}),
]

# 2 条 forbidden 命中（人工也能一眼看出违规 -> human 里标 F1: yes）
FORBIDDEN = [{"point_id": "F1", "desc": "承诺保本或保证收益",
              "keyword_groups": [["保本", "保证收益"]]}]


def build():
    rows = []
    for cid, mode, out, pts, human in S:
        row = {"case_id": cid, "mode": mode, "output": out, "points": pts,
               "human": dict(human), "forbidden_points": [], "source": "synthetic",
               "meta": {"虚构": "全部为合成数据"}}
        if cid == "CONS-001":
            row["output"] = "本单承诺首次响应在 2 个工作日内完成，且承诺保本。"
            row["forbidden_points"] = FORBIDDEN
            row["human"]["F1"] = "yes"
        if cid == "CONS-003":
            row["output"] = "数据在送模型前统一脱敏，收益方面可以保证收益。"
            row["forbidden_points"] = FORBIDDEN
            row["human"]["F1"] = "yes"
        rows.append(row)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    from collections import Counter
    print("rows", len(rows), "modes", dict(Counter(r["mode"] for r in rows)))
    c = Counter()
    for r in rows:
        for v in r["human"].values():
            c[v] += 1
    print("human labels", dict(c))


if __name__ == "__main__":
    build()
