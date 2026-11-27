# -*- coding: utf-8 -*-
"""eval-baseline 命令入口：set / show / compare。

用法：
    python -m pkg.cmd set --run BASE_V1 --reason "首版基线" --permissions eval.baseline.set
    python -m pkg.cmd show
    python -m pkg.cmd compare --run CUR_DROP4
    python -m pkg.cmd compare --run CUR_FLAKY --json

退出码：
    0 判定通过 / set 与 show 成功
    1 判定为退化失败（或 warn 之外的失败）
    2 基线不合法、权限不足、理由缺失、找不到运行 —— 属「命令报错」，不是「判定失败」
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import baseline as B   # noqa: E402
import clock           # noqa: E402

ROOT = os.path.dirname(_HERE)
RC_OK, RC_FAIL, RC_ERR = 0, 1, 2


def _load_run(runs_dir, run_id):
    fp = os.path.join(runs_dir, run_id + ".json")
    if not os.path.exists(fp):
        raise B.BaselineError("找不到运行记录：%s" % fp)
    return json.load(open(fp, encoding="utf-8"))


def build_parser():
    ap = argparse.ArgumentParser(prog="eval-baseline", description="回归基线与退化判定")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("set", help="把某次运行设为当前基线")
    s.add_argument("--run", required=True)
    s.add_argument("--reason", default="")
    s.add_argument("--permissions", default="")
    s.add_argument("--suite", default=os.path.join(ROOT, "data", "suite.yaml"))
    s.add_argument("--runs-dir", default=os.path.join(ROOT, "data", "runs"))

    w = sub.add_parser("show", help="显示当前基线")
    w.add_argument("--baseline", default=os.path.join(ROOT, "data", "baselines", "kb_qa.yaml"))

    c = sub.add_parser("compare", help="本次运行与基线比较并判定")
    c.add_argument("--run", required=True)
    c.add_argument("--baseline-run", default="BASE_V1")
    c.add_argument("--today", default=clock.BASE_TODAY)
    c.add_argument("--suite", default=os.path.join(ROOT, "data", "suite.yaml"))
    c.add_argument("--runs-dir", default=os.path.join(ROOT, "data", "runs"))
    c.add_argument("--json", action="store_true")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.cmd == "show":
        try:
            doc = B.show(args.baseline)
        except (B.BaselineError, OSError) as e:
            print("[eval-baseline] %s" % e, file=sys.stderr)
            return RC_ERR
        print("suite: %s" % doc.get("suite"))
        print("baseline_run: %s" % doc.get("baseline_run"))
        print("reason: %s" % doc.get("reason"))
        print("set_by: %s" % doc.get("set_by"))
        print("set_at: %s" % doc.get("set_at"))
        return RC_OK

    try:
        suite, rules, doc = B.load_suite(args.suite)
    except (B.BaselineError, OSError) as e:
        print("[eval-baseline] 套件配置不合法：%s" % e, file=sys.stderr)
        return RC_ERR

    try:
        run = _load_run(args.runs_dir, args.run)
    except B.BaselineError as e:
        print("[eval-baseline] %s" % e, file=sys.stderr)
        return RC_ERR

    if args.cmd == "set":
        perms = [x.strip() for x in (args.permissions or "").split(",") if x.strip()]
        try:
            B.check_settable(run, suite, perms, args.reason)
        except B.BaselineError as e:
            print("[eval-baseline] 拒绝设置基线：%s" % e, file=sys.stderr)
            return RC_ERR
        print("已设置基线：suite=%s run=%s（suite_version=%s，%d 条用例）"
              % (suite["name"], run["run_id"], run["suite_version"], len(run["cases"])))
        print("理由：%s" % args.reason)
        return RC_OK

    # compare
    try:
        base_run = _load_run(args.runs_dir, args.baseline_run)
        clock.parse_day(args.today)
    except (B.BaselineError, clock.ClockError) as e:
        print("[eval-baseline] %s" % e, file=sys.stderr)
        return RC_ERR

    try:
        res = B.compare(base_run, run, rules)
    except B.BaselineError as e:
        print("[eval-baseline] 基线不可用：%s" % e, file=sys.stderr)
        return RC_ERR

    print(B.markdown(res, args.today))
    if args.json:
        body = {
            "base_run": res["base_run"], "cur_run": res["cur_run"],
            "verdict": res["verdict"],
            "pass_rate": {k: float(v) for k, v in res["pass_rate"].items()},
            "score": {k: float(v) for k, v in res["score"].items()},
            "scope": {k: v for k, v in res["scope"].items()
                      if k not in ("only_in_baseline_keys", "only_in_current_keys")},
            "regressions": res["regressions"], "fixes": res["fixes"],
            "flaky": [f["case_key"] for f in res["flaky"]],
            "must_flips": res["must_flips"], "reasons": res["reasons"],
        }
        print(json.dumps(body, ensure_ascii=False, indent=1))
    return RC_OK if res["verdict"] in ("pass", "warn") else RC_FAIL


if __name__ == "__main__":
    sys.exit(main())
