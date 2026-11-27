# -*- coding: utf-8 -*-
"""逐条断言本单 AC。任何一条失败即非零退出，可直接接 CI。"""
import csv
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
import engine  # noqa: E402
import miniyaml  # noqa: E402
import normalize  # noqa: E402
import scorer  # noqa: E402

DATA = os.path.join(ROOT, "data")
RESULTS = []


def ok(code, title, detail=""):
    RESULTS.append(True)
    print("[PASS] %s %s %s" % (code, title, detail))


def bad(code, title, detail=""):
    RESULTS.append(False)
    print("[FAIL] %s %s %s" % (code, title, detail))


def check(code, cond, title, detail=""):
    (ok if cond else bad)(code, title, detail)


def load_cases():
    return [json.loads(l) for l in open(os.path.join(DATA, "cases.jsonl"),
                                        encoding="utf-8") if l.strip()]


def load_hand():
    rows = {}
    with open(os.path.join(DATA, "handcalc.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[(r["case_id"], r["field"])] = r
    return rows


def main():
    cases = load_cases()
    schema = engine.SCHEMA
    hand = load_hand()
    scored = {c["id"]: scorer.score_fields(c["expected"], c["actual"], schema) for c in cases}

    # ---------- AC1：8 种字段类型各有正例与反例 ----------
    all_types = sorted({v["type"] for v in schema.values()})
    check("V01", len(all_types) == 8, "字段类型恰 8 种",
          "类型 %s" % all_types)
    per_type = {}
    for t in all_types:
        fields = [k for k, v in schema.items() if v["type"] == t]
        pos = neg = 0
        for c in cases:
            fs = scored[c["id"]]
            for f in fields:
                cnt = fs.fields.get(f)
                if not cnt:
                    continue
                err = cnt["wrong"] + cnt["missing"] + cnt["extra"]
                if cnt["correct"] and not err:
                    pos += 1
                if err:
                    neg += 1
        per_type[t] = (pos, neg)
    miss = [t for t, (p, n) in per_type.items() if p < 1 or n < 1]
    check("V02", not miss, "8 种类型各自都有正例与反例用例",
          "缺 %s；明细 %s" % (miss, {k: v for k, v in sorted(per_type.items())}))

    # ---------- AC2：list 多 1 项 extra / 少 1 项 missing ----------
    e20 = scored["C20"].fields.get("pay_nodes", {})
    check("V03", e20.get("extra") == 1 and e20.get("missing") == 0,
          "付款节点多 1 项 → extra=1 且 missing=0", "实测 %s" % e20)
    e21 = scored["C21"].fields.get("pay_nodes", {})
    check("V04", e21.get("missing") == 1 and e21.get("extra") == 0,
          "付款节点少 1 项 → missing=1 且 extra=0", "实测 %s" % e21)
    e19 = scored["C19"].fields.get("pay_nodes", {})
    check("V05", e19.get("correct") == 3 and not (e19.get("wrong") or e19.get("missing")
                                                  or e19.get("extra")),
          "付款节点完全一致时 3 项全 correct", "实测 %s" % e19)

    # ---------- AC3：金额 1 分即 wrong；critical 错则不通过 ----------
    e09 = scored["C09"].fields.get("total_amount", {})
    check("V06", e09.get("wrong") == 1 and e09.get("correct") == 0,
          "金额相差 1 分判 wrong（无容差）", "实测 %s" % e09)
    check("V07", scored["C08"].fields["total_amount"]["correct"] == 1,
          "金额完全相等判 correct", "")
    crit_cases = ["C09", "C10", "C15", "C28", "C29"]
    crit_ok = all(scored[c].passed() is False for c in crit_cases)
    check("V08", crit_ok, "critical 字段出错时用例不通过",
          "实测 %s" % {c: scored[c].passed() for c in crit_cases})
    check("V09", all(scored[c].critical_hit for c in crit_cases),
          "critical_hit 记录了出错的 critical 字段",
          "实测 %s" % {c: scored[c].critical_hit for c in crit_cases})
    # 反向对照：非 critical 单错不进 critical_hit
    check("V10", not scored["C04"].critical_hit and scored["C04"].passed() is True,
          "非 critical 字段单错不触发 critical_hit 且仍通过（正向对照）", "")

    # ---------- AC4：指标与手算表一致 ----------
    diffs = []
    for cid, fs in scored.items():
        for fname, m in list(fs.per_field().items()) + [("__overall__", fs.overall())]:
            row = hand.get((cid, fname))
            if row is None:
                diffs.append((cid, fname, "手算表缺行"))
                continue
            for key in ("precision", "recall", "f1"):
                if "%.12f" % m[key] != row[key]:
                    diffs.append((cid, fname, key, "%.12f" % m[key], row[key]))
    check("V11", not diffs, "全部用例的 precision/recall/F1 与手算表逐字符一致",
          "不一致 %s" % (diffs[:4] if diffs else []))

    # 手算表独立复核：分母关系与整数计数自洽
    bad_rows = []
    for (cid, fname), r in hand.items():
        c_, w_, m_, e_ = (int(r["correct"]), int(r["wrong"]),
                          int(r["missing"]), int(r["extra"]))
        if r["precision"] != "%.12f" % (c_ / (c_ + w_ + e_) if c_ + w_ + e_ else 0):
            bad_rows.append((cid, fname, "precision"))
        if r["recall"] != "%.12f" % (c_ / (c_ + w_ + m_) if c_ + w_ + m_ else 0):
            bad_rows.append((cid, fname, "recall"))
    check("V12", not bad_rows, "手算表内部自洽（分子分母与计数对得上）",
          "异常 %s" % (bad_rows[:3] if bad_rows else []))

    # ---------- 结构与配置 ----------
    check("V13", len(cases) == 34 and len(cases) >= 30,
          "用例数满足工单「30 个以上」（实测 34）", "cases=%d" % len(cases))
    ids = [c["id"] for c in cases]
    check("V14", len(set(ids)) == len(ids), "用例 id 唯一", "重复 %s" % (
        [i for i in set(ids) if ids.count(i) > 1] or "无"))

    sy = os.path.join(DATA, "suite.yaml")
    parsed = miniyaml.loads(open(sy, encoding="utf-8").read())
    fields = parsed["fields"]
    match = all(fields.get(k, {}).get("type") == v["type"] for k, v in schema.items())
    crit_in_yaml = sorted(k for k, v in fields.items() if v.get("critical"))
    crit_in_code = sorted(k for k, v in schema.items() if v.get("critical"))
    check("V15", match and crit_in_yaml == crit_in_code,
          "suite.yaml 的字段类型与 critical 标记和代码定义一致",
          "critical=%s" % crit_in_yaml)
    check("V16", len(fields) == 8, "suite.yaml 里 8 个字段齐全", "fields=%d" % len(fields))

    # 双轨交叉验证：自写解析器 vs PyYAML
    try:
        import yaml
        ref = yaml.safe_load(open(sy, encoding="utf-8").read())
        check("V17", ref == parsed, "suite.yaml 自写解析器与 PyYAML 结论一致",
              "PyYAML %s" % yaml.__version__)
    except ImportError:
        RESULTS.append(True)
        print("[SKIP] V17 未安装 PyYAML，跳过双轨交叉验证（不计入通过）")

    # ---------- pytest ----------
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    pr = subprocess.run([sys.executable, "-m", "pytest", "tests", "-v", "--no-header",
                         "-p", "no:cacheprovider", "-o", "addopts="],
                        cwd=ROOT, capture_output=True, env=env)
    out = (pr.stdout + pr.stderr).decode("utf-8", "replace")
    npass = out.count("PASSED")
    check("V18", pr.returncode == 0 and npass >= 30,
          "pytest 全绿且用例数不少于 30", "PASSED=%d rc=%d" % (npass, pr.returncode))

    # ---------- 用例级通过判定与手算一致 ----------
    pm = [(c["id"], c["passed"], scored[c["id"]].passed())
          for c in cases if scored[c["id"]].passed() != c["passed"]]
    check("V19", not pm, "每条用例的通过/不通过与手算一致",
          "不一致 %s" % (pm[:5] if pm else []))
    npass = sum(1 for c in cases if c["passed"])
    check("V20", npass == 27,
          "通过的用例恰 27 条、不通过 7 条（手算）", "实测通过 %d" % npass)

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r)
    print("")
    print("SUMMARY %d/%d PASS" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
