# -*- coding: utf-8 -*-
"""逐条断言本单 AC。任何一条失败即非零退出。

AC1/AC2/AC3 的浏览器侧证据来自 tools/shots.py（真 Chromium 抓图 + 读 DOM）；
AC4 的「没有任何外部域名请求」来自同一次运行记录的 network.json。
缺 node/npm/playwright 时**判 FAIL 而不是静默跳过** —— 否则「没跑」会被当成「通过」。
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import mockdata   # noqa: E402

DATA = os.path.join(ROOT, "data")
FE = os.path.join(ROOT, "frontend")
DOCS = os.path.join(ROOT, "docs")
SHOTS = os.path.join(DOCS, "shots")
RESULTS = []


def ok(code, title, detail=""):
    RESULTS.append(True)
    print("[PASS] %s %s %s" % (code, title, detail))


def bad(code, title, detail=""):
    RESULTS.append(False)
    print("[FAIL] %s %s %s" % (code, title, detail))


def check(code, cond, title, detail=""):
    (ok if cond else bad)(code, title, detail)


def run(cmd, cwd, timeout=900):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout,
                       env=dict(os.environ, CI="1", PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def main():
    payload = json.load(open(os.path.join(DATA, "mock.json"), encoding="utf-8"))

    # ---------- 数据结构 ----------
    rows = payload["summary"]["by_tool"]
    normal = [r for r in rows if not r["low_sample"]]
    low = [r for r in rows if r["low_sample"]]
    check("V01", len(normal) == 7, "mock 覆盖 7 个正常工具（工单要求至少 7 个）",
          "实测 %d 个" % len(normal))
    check("V02", len(low) == 1, "mock 覆盖 1 个 low_sample 分组",
          "%s（样本 %d）" % (low[0]["tool_key"], low[0]["samples"]) if low else "")
    check("V03", all(r["samples"] >= 20 for r in normal)
          and all(r["samples"] < 20 for r in low),
          "low_sample 标记与样本数一致（<20 才算 low）",
          "正常最小 %d ／ low 最大 %d"
          % (min(r["samples"] for r in normal), max(r["samples"] for r in low)))
    check("V04", set(payload) >= {"summary", "trend_day", "trend_week", "rejected",
                                  "prompt_compare", "tools"},
          "4 个查询接口的 mock 数据齐全", "%s" % sorted(payload))
    check("V05", len(payload["trend_day"]["points"]) == 14
          and len(payload["trend_week"]["points"]) == 6,
          "日视图 14 个点、周视图 6 个点（两种视图数据不同）",
          "day=%d week=%d" % (len(payload["trend_day"]["points"]),
                              len(payload["trend_week"]["points"])))
    check("V06", len(payload["prompt_compare"]["rows"]) == 9,
          "提示词版本对比：3 个工具 × 3 个版本",
          "行数 %d" % len(payload["prompt_compare"]["rows"]))
    ver_dates = {r["version"]: r["released_on"] for r in payload["prompt_compare"]["rows"]}
    check("V07", ver_dates == {"v1": "2026-09-15", "v2": "2026-10-20", "v3": "2026-11-18"},
          "版本对比表带发布日期", "%s" % ver_dates)

    # ---------- AC3 的数据侧：下钻接口不返回正文 ----------
    forbidden = {"body", "content", "text", "draft_body", "draft_content"}
    rej = payload["rejected"]["rows"]
    keys = set()
    for r in rej:
        keys |= set(r)
    check("V08", not (keys & forbidden) and len(rej) > 0,
          "下钻接口返回的字段里没有正文（只有 draft_id/场景/原因/时间）",
          "字段 %s" % sorted(keys))
    check("V09", keys == {"draft_id", "tool_key", "scenario", "reject_reason",
                          "rejected_at"},
          "下钻字段集合与设计一致", "%s" % sorted(keys))
    check("V10", "正文" in payload["rejected"]["note"],
          "接口响应里写明「不返回正文、查看正文需跳转并按权限校验」",
          payload["rejected"]["note"][:40])

    # ---------- 前端工程结构 ----------
    pkg = json.load(open(os.path.join(FE, "package.json"), encoding="utf-8"))
    deps = set(pkg.get("dependencies", {}))
    check("V11", {"react", "react-dom", "tdesign-react"} <= deps,
          "前端用 React + TDesign（不是静态 HTML 桩）", "%s" % sorted(deps))
    check("V12", "vitest" in pkg.get("devDependencies", {}),
          "装了 Vitest", "")
    check("V13", not (deps & {"echarts", "chart.js", "recharts", "highcharts"}),
          "未引入图表库依赖（图表为内联 SVG 自绘，天然不依赖 CDN）", "")
    tsx = []
    for dp, dns, fns in os.walk(os.path.join(FE, "src")):
        dns[:] = [d for d in dns if d != "__tests__"]
        tsx += [f for f in fns if f.endswith((".tsx", ".ts"))]
    check("V14", len(tsx) >= 5, "源码文件齐全（TypeScript 组件与页面）", "%d 个" % len(tsx))
    pages = os.listdir(os.path.join(FE, "src", "pages"))
    check("V15", sorted(pages) == ["QualityBoard.tsx", "RejectedList.tsx"],
          "两个真路由页面：看板 + 下钻", "%s" % sorted(pages))

    # ---------- 依赖与构建 ----------
    npm = shutil.which("npm")
    node = shutil.which("node")
    check("V16", bool(node and npm), "环境有 node 与 npm（真构建与真跑测试的前提）",
          "node=%s" % (node or "缺"))
    nm = os.path.join(FE, "node_modules")
    if not os.path.isdir(nm):
        rc, out = run([npm, "ci", "--silent"], FE) if npm else (1, "no npm")
        check("V17", rc == 0, "npm ci 安装依赖成功", "rc=%d" % rc)
    else:
        ok("V17", "node_modules 已存在（clean 环境应能 npm ci 重建）", "")
    dist = os.path.join(FE, "dist")
    rc, out = run([npm, "run", "build"], FE) if npm else (1, "no npm")
    check("V18", rc == 0 and os.path.isdir(dist), "vite build 成功产出 dist",
          "rc=%d" % rc)
    idx = os.path.join(dist, "index.html")
    check("V19", os.path.exists(idx), "dist/index.html 存在", "")
    if os.path.exists(idx):
        h = open(idx, encoding="utf-8").read().lower()
        check("V20", "http://" not in h and "https://" not in h,
              "dist/index.html 里没有外部链接（不引用 CDN）", "")

    # ---------- Vitest ----------
    # 用 --reporter=verbose 拿逐条结果：默认 reporter 在非 TTY 下只打进度点，
    # 解析 "N passed" 可能拿到 0（pytest 那边踩过同一个坑）。
    rc, out = run([npm, "test", "--", "--reporter=verbose"], FE) if npm else (1, "no npm")
    import re
    check("V21", rc == 0 and "Test Files" in out, "Vitest 全绿", "rc=%d" % rc)
    m = re.search(r"Tests\s+(\d+) passed", out)
    n_tests = int(m.group(1)) if m else out.count("✓")
    check("V22", n_tests >= 12, "Vitest 用例数不少于 12", "passed=%d" % n_tests)

    # ---------- 真浏览器截图 + 网络域名 ----------
    rows_shot = None
    try:
        import shots as SH
        info = SH.capture()
        rows_shot = info
    except Exception as e:  # noqa: BLE001
        info = None
        print("    (shots.py 异常：%s)" % e)
    check("V23", info is not None, "真 Chromium 抓图成功（缺 playwright 即判失败，不跳过）", "")
    if info:
        check("V24", len(info["shots"]) == 3, "日视图 / 周视图 / 下钻页三张截图齐全",
              "%s" % info["shots"])
        check("V25", info["week_label"] == "week", "点击「按周」后界面切到 week",
              "label=%s" % info["week_label"])
        check("V26", info["external_hosts"] == [],
              "页面加载时**没有任何外部域名请求**（AC4 核心）",
              "主机 %s；请求 %d 个" % (info["hosts"], info["request_count"]))
        check("V27", info["bars_visible"] >= 7,
              "条形图中可见的工具条数 ≥7", "实测 %d 条" % info["bars_visible"])
        check("V28", info["low_sample_hints"] == 1,
              "low_sample 分组显示提示文案（DOM 里读到 %d 处）" % 1,
              "实测 %d 处" % info["low_sample_hints"])
        check("V29", info["drill_columns"] == ["draft_id", "scenario",
                                               "reject_reason", "rejected_at"],
              "下钻页表格恰好 4 列，无正文字段",
              "%s" % info["drill_columns"])
        check("V30", info["forbidden_fields_in_table"] == [],
              "下钻页列键里没有正文字段", "")

    # 截图确实存在且非空（用常量编号，不在循环里复用同一个号）
    names = ("01_board_day.png", "02_board_week.png", "03_drilldown.png")
    sizes = {}
    for name in names:
        fp = os.path.join(SHOTS, name)
        sizes[name] = os.path.getsize(fp) if os.path.exists(fp) else 0
    empty = [n for n, s in sizes.items() if s <= 8000]
    check("V31", not empty, "三张截图都非空白（>8KB）",
          "字节数 %s" % {k: v for k, v in sizes.items()})
    check("V32", len(set(sizes.values())) > 1,
          "三张截图内容不同（不是同一张复制三次）", "%s" % sorted(set(sizes.values())))

    total = len(RESULTS)
    passed = sum(1 for x in RESULTS if x)
    print("")
    print("SUMMARY %d/%d PASS" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
