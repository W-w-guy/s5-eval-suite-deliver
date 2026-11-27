# -*- coding: utf-8 -*-
"""eval-gate 命令入口。

用法：
    python -m pkg.eval_gate --run <run_id> --policy <file> [--waivers <file>]
                            [--today YYYY-MM-DD] [--runs-dir DIR] [--json]

退出码：0 通过 / 1 失败。Markdown 摘要打到 stdout，可直接贴进 CI 评论。

两种跑法都支持（-m 与直接跑）：
    python -m pkg.eval_gate ...
    python pkg/eval_gate.py ...
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import clock      # noqa: E402
import gate       # noqa: E402
import policy as P  # noqa: E402

ROOT = os.path.dirname(_HERE)


def build_parser():
    ap = argparse.ArgumentParser(prog="eval-gate", description="护栏评测门禁")
    ap.add_argument("--run", required=True, help="run_id（对应 data/runs/<run_id>.json）")
    ap.add_argument("--policy", required=True, help="策略文件路径")
    ap.add_argument("--waivers", default=None, help="豁免文件路径（默认取策略里的 waivers_file）")
    ap.add_argument("--today", default=clock.BASE_TODAY, help="判定日（冻结时间用）")
    ap.add_argument("--runs-dir", default=os.path.join(ROOT, "data", "runs"))
    ap.add_argument("--json", action="store_true", help="额外打印机器可读摘要")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)

    run_path = os.path.join(args.runs_dir, args.run + ".json")
    if not os.path.exists(run_path):
        print("[eval-gate] 找不到运行记录：%s" % run_path, file=sys.stderr)
        return 2
    run = json.load(open(run_path, encoding="utf-8"))

    try:
        g = P.load_policy(args.policy)
    except (P.PolicyError, Exception) as e:  # noqa: BLE001
        print("[eval-gate] 策略文件不合法：%s" % e, file=sys.stderr)
        return 1

    wpath = args.waivers
    if wpath is None:
        rel = g.get("waivers_file") or ""
        wpath = os.path.join(ROOT, rel) if rel else os.path.join(ROOT, "data", "waivers", "waivers.yaml")
    try:
        waivers = P.load_waivers(wpath) if wpath and os.path.exists(wpath) else []
    except Exception as e:  # noqa: BLE001
        print("[eval-gate] 豁免文件不合法：%s" % e, file=sys.stderr)
        return 1

    try:
        clock.parse_day(args.today)
    except clock.ClockError as e:
        print("[eval-gate] --today 不合法：%s" % e, file=sys.stderr)
        return 2

    res = gate.evaluate(run, g, waivers, args.today)
    print(gate.markdown(res, args.today))
    if args.json:
        body = {"run_id": res.run_id, "passed": res.passed, "exit_code": res.exit_code,
                "levels": {k: {"total": v["total"], "passed": v["passed"],
                               "rate": float(v["rate"])}
                           for k, v in res.levels.items()},
                "p2_drop_points": (float(res.p2_drop) if res.p2_drop is not None else None),
                "failures": [c["case_key"] for c in res.failures],
                "waived": [c["case_key"] for c in res.waived],
                "expired": [w["case_key"] for w in res.expired],
                "errors": res.errors}
        print(json.dumps(body, ensure_ascii=False, indent=1))
    return res.exit_code


if __name__ == "__main__":
    sys.exit(main())
