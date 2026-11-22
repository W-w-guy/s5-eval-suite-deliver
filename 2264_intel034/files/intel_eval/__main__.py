# -*- coding: utf-8 -*-
"""CLI：python -m intel_eval run|compare

    python -m intel_eval serve-site --port 8099          # 起自带虚构站点（无 Docker 时用）
    python -m intel_eval run --site http://gov-a.example --prompt-set v1
    python -m intel_eval compare --a v1 --b v2

启动即跑 guard.assert_safe_to_start()：生产环境带 INTEL_TEST_RESOLVER 直接拒绝启动。
"""
import argparse
import functools
import http.server
import json
import os
import socketserver
import sys
import threading

from . import extract, fetch, guard, metrics, pipeline

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")
SITE = os.path.join(ROOT, "site")
DEFAULT_HOST = "gov-a.example"
DEFAULT_PORT = 8099


def load_gold():
    with open(os.path.join(DATA, "gold.jsonl"), encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def resolver_for(port: int) -> str:
    return "%s=127.0.0.1:%d" % (DEFAULT_HOST, port)


def _serve_site(port, quiet=True):
    """起静态站点（纯标准库）。返回 server，调用方可 shutdown。"""
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    directory = os.path.join(SITE, DEFAULT_HOST)
    handler = functools.partial(Quiet, directory=directory)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def build_report_md(m: dict, prompt_set: str) -> str:
    L = ["# 情报简报评测报告（prompt-set=%s）" % prompt_set, "",
         "> 样例全部虚构：域名使用 example 保留域名，企业与人物均不存在。",
         "> 生产中 AI 输出一律进复核队列，不得直接对外发送；AI 不计算任何金额。", "",
         "## 一、11 项指标与门槛", "",
         "| # | 指标 | 实测 | 门槛 | 判定 |", "|---|---|---|---|---|"]
    # 11 项：第 3 项「转载归组 F1 且误合并为 0」含两个数值，合成一行显示、分开判定。
    rows = [
        ("body_similarity", None),
        ("publish_date_accuracy", None),
        ("group_f1", ("merge_errors", "误合并")),
        ("policy_type_accuracy", None),
        ("deadline_accuracy", None),
        ("key_fact_coverage", None),
        ("numeric_flagged_ratio", None),
        ("no_link_into_queue", None),
        ("robots_violations", None),
        ("urls_in_summary", None),
        ("pii_residue", None),
    ]
    for i, (k, extra) in enumerate(rows, 1):
        op, th = metrics.THRESHOLDS[k]
        ok = metrics.check_threshold(k, m[k])
        val = str(m[k])
        th_s = "%s %s" % (op, th)
        if extra:
            ek, elabel = extra
            eop, eth = metrics.THRESHOLDS[ek]
            ok = ok and metrics.check_threshold(ek, m[ek])
            val = "%s（%s %s）" % (val, elabel, m[ek])
            th_s = "%s %s 且 %s %s" % (op, th, eop, eth)
        L.append("| %d | %s | %s | %s | %s |" % (
            i, metrics.LABELS[k], val, th_s, "通过" if ok else "**未通过**"))
    c = m["_counts"]
    L += ["", "## 二、样本与丢弃", "",
          "| 项 | 数量 |", "|---|---|",
          "| 金标用例 | %d |" % c["cases"],
          "| 成功处理条目 | %d |" % c["entries"],
          "| 丢弃（含无原文链接、抓取失败） | %d |" % c["dropped"],
          "| 因数字/日期不一致进核对队列 | %d |" % c["queued"],
          "", "无原文链接的条目**直接丢弃、不进核对队列**（指标第 8 项＝0）。",
          "让它们进队列等于把无法核对的内容丢给人工。", "",
          "## 三、转载归组明细", "",
          "| 项 | 值 |", "|---|---|",
          "| 精确率 | %.6f |" % m["_group_detail"]["precision"],
          "| 召回率 | %.6f |" % m["_group_detail"]["recall"],
          "| F1 | %.6f |" % m["_group_detail"]["f1"],
          "| 误合并对数（应为 0） | %d |" % m["_group_detail"]["merge_errors"],
          "| 金标对数 / 预测对数 | %d / %d |" % (m["_group_detail"]["gold_pairs"],
                                            m["_group_detail"]["pred_pairs"]),
          "", "## 四、门槛汇总", "",
          "**未达标项：%s**" % ("、".join(metrics.LABELS[k] for k in m["_fails"]) if m["_fails"] else "无，全部通过"),
          "",
          "CI 中任一门槛不达标时本命令退出码非 0（1），可直接作为合并拦截条件。", ""]
    return "\n".join(L)


def cmd_run(a):
    guard.assert_safe_to_start()                      # 生产 + 测试解析 = 抛异常，非零退出
    gold = load_gold()
    resolver = fetch.guard.resolver_map() if os.environ.get(guard.RESOLVER_VAR) else {}
    srv = None
    if not resolver:
        # 没配解析覆盖时，自起站点并注入解析映射（仍然是本地 127.0.0.1，不对外）
        srv = _serve_site(a.port)
        resolver = {DEFAULT_HOST: ("127.0.0.1", a.port)}
    f = fetch.Fetcher(resolver, ignore_robots=a.ignore_robots)
    pl = pipeline.Pipeline(f)
    try:
        base_url = a.site.rstrip("/")
        pl.discover([base_url + "/page-1.html", base_url + "/page-2.html"])
        pl.process(gold)
    finally:
        if srv:
            srv.shutdown()
    m = pl.evaluate(gold)
    os.makedirs(REPORTS, exist_ok=True)
    md = os.path.join(REPORTS, "intel_%s.md" % a.prompt_set)
    js = os.path.join(REPORTS, "intel_%s.json" % a.prompt_set)
    open(md, "w", encoding="utf-8", newline="\n").write(build_report_md(m, a.prompt_set))
    json.dump({"prompt_set": a.prompt_set, "metrics": m,
               "dropped": pl.dropped, "queued": pl.queued},
              open(js, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print("prompt_set=%s entries=%d dropped=%d queued=%d" % (
        a.prompt_set, m["_counts"]["entries"], m["_counts"]["dropped"], m["_counts"]["queued"]))
    order = ["body_similarity", "publish_date_accuracy", "group_f1", "merge_errors",
             "policy_type_accuracy", "deadline_accuracy", "key_fact_coverage",
             "numeric_flagged_ratio", "no_link_into_queue", "robots_violations",
             "urls_in_summary", "pii_residue"]
    for k in order:
        print("  %-24s %-10s %s" % (k, m[k], "OK" if metrics.check_threshold(k, m[k]) else "FAIL"))
    print("report=%s" % md)
    if m["_fails"]:
        print("THRESHOLD NOT MET: " + "、".join(metrics.LABELS[k] for k in m["_fails"]))
        return 1
    print("THRESHOLD OK")
    return 0


def cmd_compare(a):
    pa = os.path.join(REPORTS, "intel_%s.json" % a.a)
    pb = os.path.join(REPORTS, "intel_%s.json" % a.b)
    for p in (pa, pb):
        if not os.path.isfile(p):
            print("缺少报告：%s（先跑 run --prompt-set）" % p)
            return 2
    A, B = json.load(open(pa, encoding="utf-8"))["metrics"], json.load(open(pb, encoding="utf-8"))["metrics"]
    keys = list(metrics.THRESHOLDS)
    L = ["# 提示词版本对比 %s vs %s" % (a.a, a.b), "",
         "| 指标 | %s | %s | 差值 | 门槛 | %s | %s |" % (a.a, a.b, a.a, a.b),
         "|---|---|---|---|---|---|---|"]
    better = worse = 0
    for k in keys:
        va, vb = A[k], B[k]
        d = vb - va
        if d > 0:
            better += 1
        elif d < 0:
            worse += 1
        op, th = metrics.THRESHOLDS[k]
        L.append("| %s | %s | %s | %+.6g | %s %s | %s | %s |" % (
            metrics.LABELS[k], va, vb, d, op, th,
            "通过" if metrics.check_threshold(k, va) else "未通过",
            "通过" if metrics.check_threshold(k, vb) else "未通过"))
    L += ["", "总结：%d 项变好，%d 项变差。" % (better, worse), ""]
    out = os.path.join(REPORTS, "compare_%s_vs_%s.md" % (a.a, a.b))
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("\n".join(L))
    print("report=%s" % out)
    return 0


def cmd_serve(a):
    srv = _serve_site(a.port, quiet=False)
    print("serving %s -> http://127.0.0.1:%d" % (DEFAULT_HOST, a.port))
    print("用法：export %s=%s && python -m intel_eval run --site http://%s" % (
        guard.RESOLVER_VAR, resolver_for(a.port), DEFAULT_HOST))
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="intel_eval")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="跑一次完整评测")
    r.add_argument("--site", default="http://%s" % DEFAULT_HOST)
    r.add_argument("--prompt-set", default="v1")
    r.add_argument("--port", type=int, default=DEFAULT_PORT)
    r.add_argument("--ignore-robots", action="store_true",
                   help="故意违反 robots（仅用于验证指标能抓到缺陷）")
    r.set_defaults(func=cmd_run)

    c = sub.add_parser("compare", help="对比两个提示词版本")
    c.add_argument("--a", required=True)
    c.add_argument("--b", required=True)
    c.set_defaults(func=cmd_compare)

    s = sub.add_parser("serve-site", help="起自带虚构站点")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.set_defaults(func=cmd_serve)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except guard.UnsafeConfigError as e:
        print("REFUSE TO START: %s" % e, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
