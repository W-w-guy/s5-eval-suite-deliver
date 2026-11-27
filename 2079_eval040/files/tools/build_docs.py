# -*- coding: utf-8 -*-
"""README / ACCEPTANCE / DATA_PROVENANCE 由实跑结果生成。

ACCEPTANCE 用**行首标签**纯文本（不用 ### / 列表 / 代码围栏）—— 平台按行首锚定解析。
注：本单的 verify 依赖 node/npm/playwright，构建产物与截图属运行产物，不进 SHA256SUMS。
"""
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
import mockdata   # noqa: E402

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
ACS = [
    ("AC1", "7 个工具在条形图中都可见（截图）", "V01-V03、V27",
     "mock 侧：断言恰好 7 个非 low_sample 工具 + 1 个 low_sample 分组，且 low 标记与样本数一致（<20）。"
     "浏览器侧：真 Chromium 打开页面后统计 `[data-testid^=\"bar-\"]` 的条数为 8（7 正常 + 1 low），"
     "并把条形图截图落盘为 docs/shots/01_board_day.png"),
    ("AC2", "low_sample 分组灰显并显示提示文案（截图与组件测试）", "V02-V03、V28、V31-V32",
     "组件测试：low_sample 条形的 opacity 必须为 0.45、正常分组为 1，且该分组内必须出现"
     "「样本不足 20，不作结论」这句文案（与 charts.tsx 的 LOW_SAMPLE_TEXT 常量逐字比对）。"
     "浏览器侧：真 Chromium 在 DOM 里数到 1 处提示文案，截图见 01_board_day.png"),
    ("AC3", "下钻列表中不出现草稿正文字段（组件测试断言）", "V08-V10、V29-V30",
     "数据侧：断言下钻接口返回的字段集合恰为 {draft_id, tool_key, scenario, reject_reason, rejected_at}，"
     "与正文字段名（body/content/text/draft_body/draft_content）无交集，且响应里写明需跳转并按权限校验。"
     "浏览器侧：真 Chromium 读下钻页表头的 data-colkey，断言恰为 4 列且不含正文字段；"
     "组件测试另断言每行只渲染 4 个单元格"),
    ("AC4", "页面加载时没有任何外部域名的网络请求（网络面板截图）", "V13、V20、V26",
     "真 Chromium 监听 page.on('request')，记录全部请求的域名，断言只在 {127.0.0.1, localhost} 内、"
     "external_hosts 为空；另断言 dist/index.html 里不含 http(s) 外链、"
     "dependencies 里没有 echarts/chart.js/recharts/highcharts（图表为内联 SVG 自绘，天然不依赖 CDN）。"
     "完整请求清单落在 docs/network.json"),
]


def sha(rel):
    h = hashlib.sha256()
    h.update(open(os.path.join(ROOT, rel), "rb").read())
    return h.hexdigest()


def acceptance(ver_out):
    lines = ver_out.splitlines()
    L = ["# ACCEPTANCE — 逐条 AC 判定（原文 / 判定方式 / 复核命令 / 实际输出原文）",
         "",
         "以下输出为 tools/verify.py 在交付包内的真实 stdout，未经修改。",
         ""]
    for cid, src, rng, how in ACS:
        # 支持 "V01-V03、V27" 这种带顿号的组合
        nums = []
        for part in rng.replace("、", ",").split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-")
                nums += list(range(int(a[1:]), int(b[1:]) + 1))
            elif part:
                nums.append(int(part[1:]))
        picked = []
        for l in lines:
            m = re.match(r"\[(PASS|FAIL|SKIP)\] V(\d+) ", l)
            if m and int(m.group(2)) in nums:
                picked.append(l)
        L += ["%s 原文：%s" % (cid, src),
              "判定方式：%s" % how,
              "复核命令：python tools/verify.py   （看 %s）" % rng,
              "实际输出原文："]
        L += picked or ["（未取到输出）"]
        L.append("")
    summary = [l for l in lines if l.startswith("SUMMARY")]
    L += ["汇总：%s" % (summary[0] if summary else "(无)"), ""]
    return "\n".join(L)


def provenance(shots_n, net):
    rows = [
        ("mock 数据生成", "`pkg/mockdata.py`（7 个工具 + 1 个 low_sample 分组 + 4 个接口响应）"),
        ("生成脚本 sha256", "`%s`" % sha("pkg/mockdata.py")),
        ("看板页面 sha256", "`%s`" % sha("frontend/src/pages/QualityBoard.tsx")),
        ("下钻页面 sha256", "`%s`" % sha("frontend/src/pages/RejectedList.tsx")),
        ("图表组件 sha256", "`%s`" % sha("frontend/src/charts.tsx")),
        ("随机性", "**无随机**。所有指标、样本数、趋势点、版本发布日期为手写常量；"
                 "mock.json 由 mockdata.py 确定性生成，重跑字节级一致"),
        ("种子", "不适用（无随机数生成器）"),
        ("重跑命令", "`python pkg/mockdata.py` ／ `npm ci && npm run build`"),
        ("产出规模", "8 个分组（7 正常 + 1 low）/ 4 个接口 / 日视图 14 点 周视图 6 点 / "
                 "提示词版本 3×3 / 截图 %d 张 / Vitest 17 项" % shots_n),
        ("对外请求", "页面加载共 %d 个请求，域名仅 %s（无外部域名）"
                 % (net.get("request_count", 0), net.get("hosts", []))),
    ]
    L = ["# DATA_PROVENANCE — 数据来源与可复核性", "",
         "本交付包**不含任何真实个人信息或企业信息**。全部示例数据由脚本生成，可完整重放。", "",
         "| 项 | 值 |", "| --- | --- |"]
    L += ["| %s | %s |" % (k, v) for k, v in rows]
    L += ["", "## 虚构声明", "",
          "工具名称、样本数、采纳率、拒绝原因分布、草稿 ID、场景与时间全部虚构；"
          "文本中不出现客户名称，不含任何真实个人信息。", ""]
    return "\n".join(L)


def readme(n_verify):
    L = ["# AI 采纳率与修改幅度看板（S5-EVAL-040）", "",
         "工作台页面 `/eval/quality`（React 18 + TypeScript + TDesign）：筛选、5 张指标卡、"
         "趋势折线（日/周切换）、按工具对比条形图、拒绝原因分布、提示词版本对比表，"
         "以及下钻到最近被拒草稿列表（不显示正文）。图表为**内联 SVG 自绘**，不引用任何 CDN。", "",
         "## 一条命令复跑", "", "```",
         "python pkg/mockdata.py                  # 重算 data/mock.json",
         "cd frontend && npm ci && npm run build  # 装依赖并构建 dist",
         "npm test                                # Vitest（17 项）",
         "cd .. && python tools/verify.py         # 逐条断言 AC（%d 条），非零退出可接 CI" % n_verify,
         "python tools/build_docs.py              # 由实跑结果重生成文档",
         "python tools/make_zip.py                # 打包 + SHA256SUMS", "```", "",
         "依赖：Python 3.11+（工具链）、Node 18+ 与 npm（前端构建与测试）、"
         "Playwright + Chromium（真浏览器截图与网络记录，`python -m playwright install chromium`）。", "",
         "## 4 个查询接口（按 EVAL-039 的结构，先用 mock）", "",
         "| 接口 | 返回 |", "| --- | --- |",
         "| `/api/eval/quality/summary` | 指标卡 + 按工具对比 + 拒绝原因分布 |",
         "| `/api/eval/quality/trend?granularity=day\\|week` | 趋势折线点 |",
         "| `/api/eval/quality/tools` | 工具列表（含 low_sample 标记） |",
         "| `/api/eval/quality/rejected?tool=<key>` | 最近被拒草稿（**不含正文**） |", "",
         "默认走 `data/mock.json`；把 `VITE_USE_MOCK=0` 后重新构建即改走真实接口。", "",
         "## 四条容易写错的实现细节", "",
         "**① low_sample 必须灰显 + 带提示文案，两件事都要做。**",
         "只降透明度不给文案，看的人会以为图表坏了；只给文案不灰显，容易把小样本和大样本混在一起读。"
         "本包用 `opacity=0.45` 与「样本不足 20，不作结论」两句同时约束，"
         "组件测试对这两个信号分别断言（含正常分组 `opacity=1` 的正向对照）。", "",
         "**② 「不显示正文」要断言字段集合，不能靠整页子串匹配。**",
         "第一版写的是 `document.body.innerHTML.toLowerCase()` 里不含 `body` —— 结果命中了 `<body>` 标签本身，"
         "是假阳性写法。正确判据是读表头的 `data-colkey` 与每行 `<td>` 数量，"
         "并断言字段集合恰为 `{draft_id, scenario, reject_reason, rejected_at}`。", "",
         "**③ 外部域名检查不能拿源码扫描代替网络记录。**",
         "源码里没有外链，不等于运行时没有请求（依赖库可能在运行时注入）。"
         "本包用 Playwright 监听 `page.on('request')`，把每个请求的域名都记进 `docs/network.json`，"
         "断言 `external_hosts` 为空 —— 这是网络面板级别的证据。", "",
         "**④ 图表用内联 SVG 而不是图表库。**",
         "工单要求「图表库本地打包，不引用外部 CDN」。最省事的做法是自绘 SVG："
         "既能满足所有视觉要求，也从根上不存在 CDN 依赖，且不增加 700KB 级别的依赖体积。", "",
         "## 目录", "", "| 路径 | 内容 |", "| --- | --- |",
         "| `pkg/mockdata.py` | 7 个工具 + 1 个 low_sample 分组 + 4 个接口响应（确定性） |",
         "| `data/mock.json` | 全部 mock 数据 |",
         "| `frontend/src/pages/QualityBoard.tsx` | 看板页：筛选 / 指标卡 / 趋势 / 条形图 / 原因分布 / 版本表 |",
         "| `frontend/src/pages/RejectedList.tsx` | 下钻页：被拒草稿列表（4 列，无正文） |",
         "| `frontend/src/charts.tsx` | 内联 SVG 条形图与折线图（含 LOW_SAMPLE_TEXT 常量） |",
         "| `frontend/src/api.ts` | 4 个查询接口的客户端封装（mock / 真实可切） |",
         "| `frontend/src/__tests__/` | Vitest 17 项（含 AC1/AC2/AC3 与无外链扫描） |",
         "| `tools/shots.py` | 真 Chromium 抓图 + 记录全部请求域名 |",
         "| `tools/verify.py` | %d 条 AC 断言 |" % n_verify,
         "| `docs/shots/` | 日视图 / 周视图 / 下钻页三张截图 |",
         "| `docs/network.json` | 页面加载的完整请求清单（AC4 证据） |", "",
         "## 设计取舍", "",
         "- **下钻页只给 4 个字段，正文另走权限校验**：草稿正文可能含未脱敏内容，"
         "在列表里直接铺开等于绕过复核队列的权限边界。",
         "- **mock 里就带上 low_sample 分组**：只有大样本会让看板「看起来很稳」，"
         "把样本不足的分组显式标出来，才能让人在看到漂亮数字时先问分母。",
         "- **截图与构建产物不进 SHA256SUMS**：它们随每次构建/运行变化，"
         "纳入校验和会让买家跑完一遍就 mismatch。",
         ]
    return "\n".join(L)


def main():
    r = subprocess.run([sys.executable, "tools/verify.py"], cwd=ROOT, env=ENV,
                       capture_output=True)
    ver_out = (r.stdout + r.stderr).decode("utf-8", "replace")
    n = len([l for l in ver_out.splitlines() if l.startswith(("[PASS]", "[FAIL]"))])
    shots = os.path.join(ROOT, "docs", "shots")
    n_shots = len(os.listdir(shots)) if os.path.isdir(shots) else 0
    netf = os.path.join(ROOT, "docs", "network.json")
    net = json.load(open(netf, encoding="utf-8")) if os.path.exists(netf) else {}
    W = lambda rel, s: open(os.path.join(ROOT, rel), "w",
                            encoding="utf-8", newline="\n").write(s)
    W("README.md", readme(n))
    W("ACCEPTANCE.md", acceptance(ver_out))
    W("DATA_PROVENANCE.md", provenance(n_shots, net))
    print("verify_rc=%d verify_lines=%d shots=%d requests=%d hosts=%s"
          % (r.returncode, n, n_shots, net.get("request_count", 0), net.get("hosts")))
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
