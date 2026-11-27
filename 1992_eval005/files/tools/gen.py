# -*- coding: utf-8 -*-
"""由引擎重算全部数据产物。

手算表 handcalc.csv 用 fractions.Fraction 整数运算生成（与 scorer 的浮点实现
是两条独立路径），小数固定 12 位，便于逐字符比对。
"""
import csv
import json
import os
import sys
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
import engine  # noqa: E402


def frac_metrics(c, w, m, e):
    """独立实现：分子分母都用整数，最后才转小数。"""
    pden, rden = c + w + e, c + w + m
    p = Fraction(c, pden) if pden else Fraction(0)
    r = Fraction(c, rden) if rden else Fraction(0)
    if p + r == 0:
        f1 = Fraction(0)
    else:
        f1 = 2 * p * r / (p + r)
    return p, r, f1


def fmt(x):
    return "%.12f" % float(x)


def main():
    data = os.path.join(ROOT, "data")
    n = engine.write_all(data)

    # 手算表：逐用例、逐字段 + 整体
    rows = []
    for c in engine.build_cases():
        tot = {"correct": 0, "wrong": 0, "missing": 0, "extra": 0}
        for fname in engine.SCHEMA:
            h = c["hand"].get(fname)
            if h is None:
                continue
            fc, fw, fm, fe = h
            for k, v in zip(("correct", "wrong", "missing", "extra"), h):
                tot[k] += v
            p, r, f1 = frac_metrics(fc, fw, fm, fe)
            rows.append([c["id"], fname, fc, fw, fm, fe,
                         fmt(p), fmt(r), fmt(f1)])
        p, r, f1 = frac_metrics(tot["correct"], tot["wrong"], tot["missing"], tot["extra"])
        rows.append([c["id"], "__overall__", tot["correct"], tot["wrong"],
                     tot["missing"], tot["extra"], fmt(p), fmt(r), fmt(f1)])

    path = os.path.join(data, "handcalc.csv")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "field", "correct", "wrong", "missing", "extra",
                    "precision", "recall", "f1"])
        w.writerows(rows)

    # suite.yaml：字段 schema + critical 标记 + 通过阈值
    lines = ["# 结构化输出评分套件配置（虚构）",
             "suite:",
             "  id: s5-eval-005",
             "  version: v1",
             "  pass_f1_threshold: 0.8",
             "  money_tolerance_fen: 0",
             "  rate_tolerance_bp: 0",
             "fields:"]
    for k, v in engine.SCHEMA.items():
        lines.append("  %s:" % k)
        lines.append("    type: %s" % v["type"])
        if v.get("critical"):
            lines.append("    critical: true")
        if v.get("key"):
            lines.append("    key: %s" % v["key"])
        if v.get("mapping"):
            lines.append("    mapping:")
            for mk, mv in v["mapping"].items():
                lines.append("      %s: %s" % (mk, mv))
    sp = os.path.join(data, "suite.yaml")
    with open(sp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    print("WROTE cases=%d fields=%d handcalc_rows=%d" % (n, len(engine.SCHEMA), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
