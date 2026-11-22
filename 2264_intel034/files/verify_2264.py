# -*- coding: utf-8 -*-
"""S5-INTEL-034 自检：4 条 AC -> 可执行断言。退出码 0 = 全过。

跑法：python verify_2264.py
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from intel_eval import guard, metrics

F = []
REPORTS = os.path.join(HERE, "reports")


def chk(name, ok, detail=""):
    F.append((name, bool(ok), detail))
    print(("[ OK ]" if ok else "[FAIL]"), name, ("| " + str(detail)) if detail else "")


def py(*args, env=None):
    e = dict(os.environ)
    e.pop(guard.RESOLVER_VAR, None)
    e.pop(guard.ENV_VAR, None)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, "-m", *args], capture_output=True,
                          cwd=HERE, text=True, encoding="utf-8", errors="replace", env=e)


METRIC_KEYS = ["body_similarity", "publish_date_accuracy", "group_f1", "merge_errors",
               "policy_type_accuracy", "deadline_accuracy", "key_fact_coverage",
               "numeric_flagged_ratio", "no_link_into_queue", "robots_violations",
               "urls_in_summary", "pii_residue"]


def main():
    # ================= AC1：跑起来生成 md + json，11 项指标齐全 =================
    r = py("intel_eval", "run", "--prompt-set", "verify")
    chk("AC1 run 退出码 0（门槛全过）", r.returncode == 0, "rc=%d" % r.returncode)
    md_p = os.path.join(REPORTS, "intel_verify.md")
    js_p = os.path.join(REPORTS, "intel_verify.json")
    chk("AC1 生成 Markdown 报告", os.path.isfile(md_p))
    chk("AC1 生成 JSON 报告", os.path.isfile(js_p))
    d = json.load(open(js_p, encoding="utf-8")) if os.path.isfile(js_p) else {"metrics": {}}
    m = d.get("metrics", {})
    missing = [k for k in METRIC_KEYS if k not in m]
    chk("AC1 JSON 里 11 项指标齐全（含归组 F1 的误合并约束）", not missing, missing)
    md = open(md_p, encoding="utf-8").read() if os.path.isfile(md_p) else ""
    chk("AC1 Markdown 报告标题含「11 项指标」", "11 项指标与门槛" in md)
    rows = len(re.findall(r"^\| \d+ \| ", md, re.M))
    chk("AC1 Markdown 表格确实是 11 行指标", rows == 11, rows)
    # merge_errors 不是独立指标（它并入第 3 项「转载归组 F1 且误合并为 0」），单独检查字样。
    for k in METRIC_KEYS:
        if k in metrics.LABELS and k != "merge_errors":
            chk("AC1 报告标注「%s」" % metrics.LABELS[k], metrics.LABELS[k] in md)
    chk("AC1 报告同时给出归组误合并数", "误合并" in md)
    chk("AC1 报告注明样例全部虚构", "样例全部虚构" in md)
    chk("AC1 报告写明 AI 输出进复核队列、不对外发送", "不得直接对外发送" in md)
    # 门槛真的全部达标
    fails = [k for k in METRIC_KEYS if not metrics.check_threshold(k, m.get(k))]
    chk("AC1 基线 11 项门槛全部达标", not fails, fails)

    # ================= AC2：生产 + INTEL_TEST_RESOLVER -> 拒绝启动 =================
    try:
        guard.assert_safe_to_start("production", "gov-a.example=127.0.0.1:8099")
        blocked = False
    except guard.UnsafeConfigError:
        blocked = True
    chk("AC2 生产环境设置解析覆盖时直接抛错（fail-closed）", blocked)
    r2 = py("intel_eval", "run", "--prompt-set", "refuse",
            env={guard.ENV_VAR: "production", guard.RESOLVER_VAR: "gov-a.example=127.0.0.1:8099"})
    chk("AC2 CLI 在生产+覆盖时退出码 3 且打印 REFUSE TO START",
        r2.returncode == 3 and "REFUSE TO START" in r2.stderr, r2.returncode)
    chk("AC2 拒绝启动时不产出报告",
        not os.path.isfile(os.path.join(REPORTS, "intel_refuse.md")))
    r3 = py("pytest", "tests/test_guard_robots_cli.py", "-q", "-k", "guard", "--tb=no")
    chk("AC2 有对应测试且通过", r3.returncode == 0, (r3.stdout or "").strip().splitlines()[-1:])

    # ================= AC3：人为让 robots 禁止路径被抓 -> 退出码非 0 =================
    r4 = py("intel_eval", "run", "--prompt-set", "bad", "--ignore-robots")
    chk("AC3 违反 robots 时退出码非 0", r4.returncode != 0, r4.returncode)
    chk("AC3 输出点名「robots 禁止路径被抓取数」", "robots 禁止路径被抓取数" in (r4.stdout or ""))
    db = json.load(open(os.path.join(REPORTS, "intel_bad.json"), encoding="utf-8"))
    chk("AC3 报告里 robots_violations >= 1", db["metrics"]["robots_violations"] >= 1,
        db["metrics"]["robots_violations"])
    chk("AC3 正常运行时 robots_violations == 0", m.get("robots_violations") == 0)
    r5 = py("pytest", "tests/test_guard_robots_cli.py", "-q", "-k", "robots", "--tb=no")
    chk("AC3 有对应测试且通过", r5.returncode == 0)

    # ================= AC4：每个指标 >= 2 个手算用例 =================
    rc = py("pytest", "tests", "--co")
    ids = [l for l in (rc.stdout or "").splitlines() if "::" in l]
    per = {}
    for i in ids:
        mm = re.search(r"(test_m\d\d)_", i)
        if mm:
            per[mm.group(1)] = per.get(mm.group(1), 0) + 1
    chk("AC4 11 个指标都有对应用例", len(per) == 11, sorted(per))
    thin = {k: v for k, v in per.items() if v < 2}
    chk("AC4 每个指标至少 2 个手算用例", not thin, thin)
    chk("AC4 手算用例总数 >= 22", sum(per.values()) >= 22, sum(per.values()))
    rt = py("pytest", "tests", "-q", "--tb=no")
    chk("AC4 全部单元测试通过", rt.returncode == 0,
        ((rt.stdout or "").strip().splitlines() or ["-"])[-1][:60])

    bad = [f for f in F if not f[1]]
    print("\nTOTAL %d, PASS %d, FAIL %d" % (len(F), len(F) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
