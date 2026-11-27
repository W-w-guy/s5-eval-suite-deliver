# -*- coding: utf-8 -*-
"""在真 Chromium 里打开页面、抓图、并记录全部网络请求域名（AC4 的硬证据）。

流程：
  1) 起一个本地静态服务，托管 frontend/dist 与 data/mock.json；
  2) Playwright 打开页面，记录每一个 request 的 URL 与域名；
  3) 点「按周」再抓一张（日/周两种视图）；点某个工具进下钻页再抓一张；
  4) 断言：所有请求的域名都在 {127.0.0.1, localhost} 内；
  5) 把截图与网络清单写到 docs/shots/ 与 docs/network.json。

缺 Playwright 时抛 ShotUnavailable（由 verify.py 判定 FAIL 而不是静默跳过）。
"""
import http.server
import json
import os
import socketserver
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
DIST = os.path.join(ROOT, "frontend", "dist")
SHOTS = os.path.join(ROOT, "docs", "shots")
ALLOWED_HOSTS = ("127.0.0.1", "localhost")


class ShotUnavailable(RuntimeError):
    pass


def _serve():
    """在后台起一个静态服务：/dist/* 与 /mock.json。"""
    import functools

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    mock = os.path.join(ROOT, "data", "mock.json")

    class Router(Handler):
        def translate_path(self, path):
            path = path.split("?")[0].split("#")[0]
            if path in ("/mock.json", "/mock"):
                return mock
            rel = path.lstrip("/") or "index.html"
            return os.path.join(DIST, rel)

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Router)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


def capture():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # noqa: BLE001
        raise ShotUnavailable("未安装 playwright：%s" % e)

    if not os.path.isdir(DIST):
        raise ShotUnavailable("frontend/dist 不存在，请先 npm run build")

    os.makedirs(SHOTS, exist_ok=True)
    httpd, port = _serve()
    base = "http://127.0.0.1:%d/" % port
    requests, hosts = [], set()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 1600})

            def on_req(req):
                requests.append(req.url)
                hosts.add(req.url.split("/")[2].split(":")[0])

            page.on("request", on_req)
            page.goto(base, wait_until="networkidle")
            page.wait_for_selector('[data-testid="tool-bar-chart"]')

            # 计数必须在看板页做，切到下钻页后条形图已卸载
            n_bars = page.locator('[data-testid^="bar-"]').count()
            n_low_hint = page.locator('[data-testid^="low-sample-hint-"]').count()
            board_html = page.content().lower()
            page.screenshot(path=os.path.join(SHOTS, "01_board_day.png"), full_page=True)

            page.click("text=按周")
            page.wait_for_timeout(500)
            week_label = page.locator('[data-testid="trend-granularity"]').inner_text()
            page.screenshot(path=os.path.join(SHOTS, "02_board_week.png"), full_page=True)

            page.click('[data-testid="drill-meeting_minutes"]')
            page.wait_for_selector('[data-testid="rejected-table"]')
            drill_cols = page.eval_on_selector_all(
                '[data-testid="rejected-table"] th[data-colkey]',
                "els => els.map(e => e.getAttribute('data-colkey'))")
            drill_rows = page.locator('[data-testid="rejected-table"] tbody tr').count()
            # 正文字段判定：看表格的列键，不做整页子串匹配（会命中 <body> 标签）
            forbidden = [c for c in drill_cols
                         if c in ("body", "content", "text", "draft_body", "draft_content")]
            page.screenshot(path=os.path.join(SHOTS, "03_drilldown.png"), full_page=True)
            browser.close()
    finally:
        httpd.shutdown()

    bad = sorted(h for h in hosts if h not in ALLOWED_HOSTS)
    info = {"base": base, "request_count": len(requests),
            "hosts": sorted(hosts), "external_hosts": bad,
            "bars_visible": n_bars, "low_sample_hints": n_low_hint,
            "week_label": week_label, "drill_columns": drill_cols,
            "drill_rows": drill_rows,
            "forbidden_fields_in_table": forbidden,
            "shots": sorted(os.listdir(SHOTS))}
    with open(os.path.join(ROOT, "docs", "network.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump({"requests": requests, **info}, f, ensure_ascii=False,
                  indent=1, sort_keys=True)
    return info


if __name__ == "__main__":
    print(json.dumps(capture(), ensure_ascii=False, indent=1))
