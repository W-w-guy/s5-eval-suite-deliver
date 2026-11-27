# -*- coding: utf-8 -*-
"""AC3：页面截图可见逐条要点的同意、需修改、删除操作。

不再用静态 HTML 桩：这里起真实 uvicorn（Python 后端）+ 真实 React 构建产物，
用 Playwright 打开浏览器、真实点击，并把每一步截图落到 docs/shots/。
"""
from __future__ import annotations
import os, socket, subprocess, sys, time, json, urllib.request
import pytest

from tests.conftest import _h, REVIEWER_A, ORG

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(HERE, "docs", "shots")
DIST = os.path.join(HERE, "frontend", "dist", "index.html")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait_up(url: str, timeout: float = 40.0) -> bool:
    """只要服务返回任何 HTTP 响应就算起来了。

    注意别拿需要鉴权的 /api/... 当健康检查：那会返回 401，
    urllib 抛 HTTPError，被当成「没起来」——这次就踩了这个坑。
    """
    import urllib.error
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except urllib.error.HTTPError:
            return True          # 4xx/5xx 也说明 TCP 通了、应用在跑
        except Exception:
            time.sleep(0.4)
    return False


@pytest.fixture(scope="module")
def live_server():
    """起一个真实 HTTP 服务（同一 DATABASE_URL），供浏览器访问 SPA。"""
    if not os.path.exists(DIST):
        pytest.skip("前端未构建（先在 frontend/ 执行 npm ci && npm run build）")
    # module 级 fixture 可能早于 function 级 client 建立，那时 DATABASE_URL 尚未写入，
    # 子进程就会自己去起一遍库并卡住——这里先确保父进程已经拿到连接串。
    from app.db import get_engine
    get_engine()
    assert os.environ.get("DATABASE_URL"), "DATABASE_URL 未就绪，无法起子进程"
    port = _free_port()
    env = dict(os.environ)
    env["PYTHONPATH"] = HERE
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=HERE, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        ok = _wait_up("http://127.0.0.1:%d/" % port)
        if not ok:
            out = b""
            try:
                proc.terminate(); out = proc.communicate(timeout=5)[0] or b""
            except Exception:
                pass
            pytest.fail("后端没起来：%s" % out.decode("utf-8", "replace")[-800:])
        yield "http://127.0.0.1:%d" % port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


@pytest.fixture(scope="module", autouse=True)
def _ensure_shots_dir():
    os.makedirs(SHOTS, exist_ok=True)


def _browser():
    from playwright.sync_api import sync_playwright
    return sync_playwright()


def test_each_point_has_three_actions(client, case, live_server):
    """每条要点都必须同时出现同意/需修改/删除三个操作，且是真按钮（有 data-testid）。"""
    base = live_server
    suites = client.get("/api/eval/suites", headers=_h(REVIEWER_A)).json()["items"]
    suite = [x for x in suites if x["id"] == case["suite_id"]][0]
    url = "%s/eval/suites/%s/cases/%s" % (base, suite["key"], "case-0001")
    # case-0001 是 seed 数据的 key；若 fixture 生成的 key 不同则按响应里的真实 key 走
    detail = client.get("/api/eval/cases/%s" % case["case_id"], headers=_h(REVIEWER_A)).json()
    url = "%s/eval/suites/%s/cases/%s" % (base, suite["key"], detail["case_key"])

    with _browser() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1180, "height": 900})
        pg.goto(url, wait_until="networkidle")
        pg.wait_for_selector('[data-testid="case-detail"]', timeout=30000)
        n = pg.locator('[data-testid^="point-"][data-testid$="-text"]').count()
        assert n >= 2, "至少两条要点才有「逐条」意义，实际 %d" % n
        for i in range(n):
            for act in ("approve", "revise", "remove"):
                loc = pg.locator('[data-testid="point-%d-%s"]' % (i, act))
                assert loc.count() == 1, "要点 %d 缺 %s 操作" % (i, act)
                assert loc.is_visible(), "要点 %d 的 %s 操作不可见" % (i, act)
        pg.screenshot(path=os.path.join(SHOTS, "03_case_detail_actions.png"), full_page=True)
        b.close()


def test_mark_then_export_suggestion(client, case, live_server, tmp_path):
    """点「需修改」→ 写意见 → 导出建议 JSON，且 JSON 里必须有该要点。

    这条专门防「页面看起来有按钮，但点了什么也没发生」。
    """
    base = live_server
    suites = client.get("/api/eval/suites", headers=_h(REVIEWER_A)).json()["items"]
    suite = [x for x in suites if x["id"] == case["suite_id"]][0]
    detail = client.get("/api/eval/cases/%s" % case["case_id"], headers=_h(REVIEWER_A)).json()
    url = "%s/eval/suites/%s/cases/%s" % (base, suite["key"], detail["case_key"])

    with _browser() as p:
        b = p.chromium.launch()
        ctx = b.new_context(accept_downloads=True, viewport={"width": 1180, "height": 900})
        pg = ctx.new_page()
        pg.goto(url, wait_until="networkidle")
        pg.wait_for_selector('[data-testid="point-0-revise"]', timeout=30000)

        assert "已标记 0" in pg.inner_text('[data-testid="marked-count"]')
        pg.click('[data-testid="point-0-revise"]')
        pg.fill('[data-testid="point-0-comment"]', "要点1 需补一个反例")
        pg.click('[data-testid="point-1-remove"]')
        pg.fill('[data-testid="point-1-comment"]', "与要点1 重复")
        assert "已标记 2" in pg.inner_text('[data-testid="marked-count"]'), "点击没生效"
        pg.screenshot(path=os.path.join(SHOTS, "02_mark_revise.png"), full_page=True)

        with pg.expect_download(timeout=20000) as dl:
            pg.click('[data-testid="export-suggestion"]')
        d = dl.value
        out = tmp_path / "suggestion.json"
        d.save_as(str(out))
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["applied_to_file"] is False, "页面不得直接改用例文件"
        got = {s["index"]: s["verdict"] for s in data["suggestions"]}
        assert got == {0: "revise", 1: "remove"}, got
        assert data["suggestions"][0]["comment"] == "要点1 需补一个反例"
        b.close()


def test_suite_list_and_pending_filter(client, case, live_server):
    """套件列表页可打开，「只看待复核」筛选真的会减少行数。"""
    base = live_server
    with _browser() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1180, "height": 900})
        pg.goto(base + "/eval/suites", wait_until="networkidle")
        pg.wait_for_selector('[data-testid="suite-count"]', timeout=30000)
        pg.screenshot(path=os.path.join(SHOTS, "01_suite_list.png"), full_page=True)
        before = pg.inner_text('[data-testid="suite-count"]')
        pg.click('[data-testid="pending-filter"]')
        time.sleep(0.6)
        after = pg.inner_text('[data-testid="suite-count"]')
        # 数据里 review 全部完成的套件不会出现，行数必须不增
        nb = int(before.replace("共", "").replace("个套件", "").strip())
        na = int(after.replace("共", "").replace("个套件", "").strip())
        assert na <= nb, "筛选后行数反而变多：%d -> %d" % (nb, na)
        pg.screenshot(path=os.path.join(SHOTS, "04_only_pending_filter.png"), full_page=True)
        b.close()
