# -*- coding: utf-8 -*-
"""真实截图：起 uvicorn -> 从真接口取 JSON -> 注入静态渲染页 -> Playwright 截图。

为什么用静态渲染页而不是直接截 React 应用：本机没有 node/npm，
无法执行 vite build（README 里已如实写明）。React 与 TS 源码在 web/src/，
本页与它共用同一份数据契约与同一组 data-testid，所以截出来的操作项是等价的。

产出：docs/shots/*.png，并在控制台打印每张图的字节数与断言结果。
"""
from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
PORT = 8099


def fetch(path):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path),
                                 headers={"X-User-Id": "shot", "X-Permissions": "eval.case.review"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def main():
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    out = os.path.join(HERE, "docs", "shots")
    os.makedirs(out, exist_ok=True)
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                            "--port", str(PORT), "--log-level", "warning"], cwd=HERE)
    try:
        for _ in range(40):
            try:
                fetch("/api/eval/suites"); break
            except Exception:
                time.sleep(0.5)
        else:
            raise SystemExit("uvicorn 未起来")

        suites = fetch("/api/eval/suites")
        # 本单的三个接口里没有「列出某套件全部用例」这个口（工单未要求），
        # 所以这里用例 id 取自数据库，接口数据仍全部走 HTTP 取，截图不伪造接口返回。
        from app.db import SessionLocal, EvalCase
        s = SessionLocal()
        try:
            rows = s.query(EvalCase).order_by(EvalCase.case_key).all()
            first = rows[0]
            cid1 = str(first.id)
        finally:
            s.close()

        detail1 = fetch("/api/eval/cases/" + cid1)

        # 把真接口返回存一份，供 AC3 的 pytest 断言复用（避免测试自造数据）
        with open(os.path.join(out, "fixture_case.json"), "w", encoding="utf-8") as fh:
            json.dump(detail1, fh, ensure_ascii=False, indent=1)

        tpl = open(os.path.join(HERE, "web", "static", "render.html"), encoding="utf-8").read()
        page_suites = os.path.join(HERE, "web", "static", "_suites.html")
        page_detail = os.path.join(HERE, "web", "static", "_detail.html")
        open(page_suites, "w", encoding="utf-8").write(
            tpl.replace("__DATA__", json.dumps({"mode": "suites", "suites": suites["items"]},
                                               ensure_ascii=False)))
        open(page_detail, "w", encoding="utf-8").write(
            tpl.replace("__DATA__", json.dumps({"mode": "detail", "case": detail1},
                                               ensure_ascii=False)))

        from playwright.sync_api import sync_playwright
        results = []
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1080, "height": 900})

            pg.goto("file:///" + page_suites.replace("\\", "/"))
            pg.wait_for_selector('[data-testid="suite-table"]')
            f1 = os.path.join(out, "01_suite_list.png")
            pg.screenshot(path=f1, full_page=True)

            pg.goto("file:///" + page_detail.replace("\\", "/"))
            pg.wait_for_selector('[data-testid="point-0"]')
            # 断言：每条要点的三个操作都在，且可见
            pts = pg.locator('[data-testid^="point-"][data-testid$="approve"]').count()
            revise = pg.locator('[data-testid$="-revise"]').count()
            remove = pg.locator('[data-testid$="-remove"]').count()
            assert pts == len(detail1["points"]), (pts, len(detail1["points"]))
            assert revise == pts and remove == pts, (revise, remove, pts)
            f2 = os.path.join(out, "02_case_detail_actions.png")
            pg.screenshot(path=f2, full_page=True)

            # 标记一条「需修改」+ 一条「删除」，展示意见输入框出现
            pg.click('[data-testid="point-1-revise"]')
            pg.fill('[data-testid="point-1-comment"]', "该要点缺少查询入口的说明，建议补一句小程序活动页路径。")
            pg.fill('[data-testid="case-comment"]', "整体结构可用，第 2 条要点需补充可操作路径。")
            f3 = os.path.join(out, "03_mark_revise.png")
            pg.screenshot(path=f3, full_page=True)

            # 「只看待复核」筛选（筛出仍为同意的要点）
            pg.click('[data-testid="point-2-remove"]')
            pg.fill('[data-testid="point-2-comment"]', "该要点与第 1 条重复，建议删除。")
            pg.check('[data-testid="only-pending"]')
            f4 = os.path.join(out, "04_only_pending_filter.png")
            pg.screenshot(path=f4, full_page=True)
            b.close()

        for f in (f1, f2, f3, f4):
            results.append((os.path.basename(f), os.path.getsize(f)))
        print("POINTS", len(detail1["points"]),
              "| approve/revise/remove per point all present =", pts, revise, remove)
        for n, sz in results:
            print("SHOT %-32s %7d bytes" % (n, sz))
        print("OK 4 screenshots")
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except Exception:
            srv.kill()


if __name__ == "__main__":
    main()
