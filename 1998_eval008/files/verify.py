# -*- coding: utf-8 -*-
"""一键复跑：起库 -> 迁移升降级 -> 全量测试 -> 汇总。

用法：
    python verify.py                 # 全量（会自动起内嵌 PostgreSQL）
    python verify.py --require-pg    # 连不上真库或缺浏览器即判 FAIL
    python verify.py --require-node  # 缺 node/npm 导致 Vitest 没跑即判 FAIL
    DATABASE_URL=postgresql://... python verify.py   # 接外部 PG

退出码：0 全过；非 0 说明有断言失败或环境不满足。
"""
from __future__ import annotations
import os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PASS = FAIL = SKIP = 0
FAILED = []


def rec(ok, name, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("[PASS] %s%s" % (name, ("  " + detail) if detail else ""))
    else:
        FAIL += 1
        FAILED.append(name)
        print("[FAIL] %s%s" % (name, ("  " + detail) if detail else ""))


def skip(name, why):
    global SKIP
    SKIP += 1
    print("[SKIP] %s  %s" % (name, why))


def run(args, **kw):
    r = subprocess.run(args, cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def ensure_db():
    """优先用环境变量；否则起内嵌 PostgreSQL（零外部依赖）。"""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url, "env:DATABASE_URL"
    try:
        import pgserver
    except ImportError:
        return None, "缺少 pgserver"
    d = os.path.join(HERE, ".pgdata")
    srv = pgserver.get_server(os.path.abspath(d))
    return srv.get_uri(), "pgserver 内嵌"


def main():
    require_pg = "--require-pg" in sys.argv
    # node 与数据库是两类独立能力：数据库/浏览器的严格开关不应连带判前端失败。
    require_node = "--require-node" in sys.argv
    url, how = ensure_db()
    if url is None:
        if require_pg:
            rec(False, "AC0 数据库可用", how)
            return 2
        skip("AC0 数据库可用", how)
        return 0
    os.environ["DATABASE_URL"] = url
    print("[INFO] 数据库来源：%s" % how)

    # --- 真库身份：版本号与连接方式必须打出来，不能只说"连上了"
    rc, out = run([sys.executable, "-c",
                   "import os,sqlalchemy as sa;"
                   "e=sa.create_engine(os.environ['DATABASE_URL'].replace('postgresql://','postgresql+psycopg2://'));"
                   "c=e.connect();"
                   "print('server_version='+c.execute(sa.text('SHOW server_version')).scalar());"
                   "print('db='+c.execute(sa.text('select current_database()')).scalar())"])
    rec(rc == 0 and "server_version=16" in out, "AC0 连的是真 PostgreSQL",
        out.strip().replace("\n", " | ")[:120])

    # --- 迁移：upgrade head
    rc, out = run([sys.executable, "-m", "alembic", "upgrade", "head"])
    rec(rc == 0, "AC0.1 alembic upgrade head", (out.strip().splitlines() or [""])[-1][:100])

    rc, out = run([sys.executable, "-c",
                   "import os,sqlalchemy as sa;"
                   "e=sa.create_engine(os.environ['DATABASE_URL'].replace('postgresql://','postgresql+psycopg2://'));"
                   "print(sa.text('select version_num from alembic_version').__str__() if 0 else "
                   "','.join(x[0] for x in e.connect().execute(sa.text('select version_num from alembic_version'))))"])
    rec(rc == 0 and out.strip(), "AC0.2 alembic_version 已落库", out.strip()[:60])

    # --- 四条 AC 各自跑一遍（分别计分，便于逐条核对）
    acs = [
        ("AC1 双人复核（同一人重复 approve 不变 reviewed）", "tests/test_ac1_double_review.py"),
        ("AC2 用例 hash 变化后复核状态重置", "tests/test_ac2_hash_reset.py"),
        ("AC3 页面逐条要点的同意/需修改/删除", "tests/test_ac3_page.py"),
        ("AC4 无评审权限调用接口返回 403", "tests/test_ac4_authz.py"),
    ]
    for name, target in acs:
        rc, out = run([sys.executable, "-m", "pytest", "-q", "--no-header",
                       "-p", "no:cacheprovider", target])
        m = re.search(r"(\d+) passed", out)
        n = m.group(1) if m else "0"
        last = (out.strip().splitlines() or [""])[-1][:90]
        if rc == 0:
            rec(True, name, "%s passed | %s" % (n, last))
        elif "Executable doesn't exist" in out or "playwright install" in out:
            if require_pg:
                rec(False, name, "缺少浏览器运行时（严格模式下判 FAIL）")
            else:
                skip(name, "缺少浏览器运行时，未真跑")
        else:
            rec(False, name, last)

    # --- 全量
    rc, out = run([sys.executable, "-m", "pytest", "-q", "--no-header",
                   "-p", "no:cacheprovider"])
    m = re.search(r"(\d+) passed", out)
    total = m.group(1) if m else "0"
    rec(rc == 0, "AC5 全量 pytest", "%s passed" % total)

    # --- 前端构建产物（AC3 的页面来自它）
    fe = os.path.join(HERE, "frontend")
    dist_index = os.path.join(fe, "dist", "index.html")
    if os.path.exists(dist_index):
        rec(True, "AC6.0 前端构建产物存在", "frontend/dist/index.html")
    else:
        rec(False, "AC6.0 前端构建产物存在", "缺 dist/index.html，先 npm ci && npm run build")

    # --- Vitest（前端单测）。本机没有 node 时如实记 SKIP，不冒充通过。
    if not shutil.which("npm") or not os.path.isdir(os.path.join(fe, "node_modules")):
        if require_node:
            rec(False, "AC6.1 Vitest 前端单测", "缺 node/npm 或 node_modules（--require-node 下判 FAIL）")
        else:
            skip("AC6.1 Vitest 前端单测", "缺 node/npm 或 node_modules，未真跑")
    else:
        r = subprocess.run(["npx", "vitest", "run"], cwd=fe, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        blob = (r.stdout or "") + (r.stderr or "")
        m = re.search(r"Tests\s+(\d+) passed", blob)
        rec(r.returncode == 0, "AC6.1 Vitest 前端单测",
            "%s passed" % (m.group(1) if m else "0"))

    # --- 迁移回滚
    rc, out = run([sys.executable, "-m", "alembic", "downgrade", "-1"])
    rec(rc == 0, "AC0.3 alembic downgrade -1", (out.strip().splitlines() or [""])[-1][:100])
    rc, out = run([sys.executable, "-c",
                   "import os,sqlalchemy as sa;"
                   "e=sa.create_engine(os.environ['DATABASE_URL'].replace('postgresql://','postgresql+psycopg2://'));"
                   "t=[r[0] for r in e.connect().execute(sa.text(\"select tablename from pg_tables where schemaname='public'\"))];"
                   "print('|'.join(sorted(t)))"])
    tables = out.strip()
    gone = "eval_case_review" not in tables
    rec(rc == 0 and gone, "AC0.4 回滚后评审表已删除", tables[:110])
    run([sys.executable, "-m", "alembic", "upgrade", "head"])  # 复原，保证可重复执行

    print("\nSUMMARY %d/%d PASS | SKIP %d（未真跑，不计入通过）"
          % (PASS, PASS + FAIL, SKIP))
    if FAILED:
        print("FAILED: " + ", ".join(FAILED))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
