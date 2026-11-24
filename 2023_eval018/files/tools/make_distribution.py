# -*- coding: utf-8 -*-
"""生成分布统计表（dist/distribution.csv + dist/distribution.md），仅依赖 stdlib。"""
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "dist")


def main():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "data", "cases.jsonl"), encoding="utf-8") if l.strip()]
    os.makedirs(OUT, exist_ok=True)
    lines = [("总计", "全部", len(rows))]
    for key, label in (("kind", "类型"), ("source", "来源"), ("layout", "版式"), ("carrier", "载体")):
        c = Counter(r.get(key) for r in rows)
        for k in sorted(c):
            lines.append((label, k, c[k]))
    dial = Counter(((r.get("meta") or {}).get("difficulty") or {}).get("name") for r in rows
                   if r.get("kind") == "difficult")
    for k in sorted(dial):
        lines.append(("疑难类型", k, dial[k]))
    with open(os.path.join(OUT, "distribution.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("维度,取值,数量\n")
        for a, b, c in lines:
            f.write("%s,%s,%d\n" % (a, b, c))
    md = ["# 分布统计表 doc_auto.contract_fields", "", "| 维度 | 取值 | 数量 |", "|---|---|---|"]
    for a, b, c in lines:
        md.append("| %s | %s | %d |" % (a, b, c))
    md += ["", "合计 %d 份：生成 28 + 疑难 12；4 种版式各 10 份；3 种载体 14/13/13。" % len(rows)]
    open(os.path.join(OUT, "distribution.md"), "w", encoding="utf-8", newline="\n").write("\n".join(md) + "\n")
    print("distribution: rows=%d dims=6 -> dist/distribution.csv, dist/distribution.md" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
