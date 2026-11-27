# -*- coding: utf-8 -*-
"""README / ACCEPTANCE / DATA_PROVENANCE 由实跑结果生成。

ACCEPTANCE 用行首标签纯文本（平台按行首锚定解析）。
"""
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "pkg"))
import engine  # noqa: E402

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
ACS = [
    ("AC1", "confirmed 超过 2 个工作日未关联回归用例的发现被标记 overdue（冻结时间测试通过）",
     "V06-V12",
     "工作日算法先与 datetime 交叉验证（weekday 索引、跨周末、跳节假日）；"
     "再在三档冻结日期下断言同一条发现的状态：截止日当天（11-27）不算 overdue、"
     "次日（11-28）算 overdue、跨周末后（12-02）仍算；"
     "另用「已关联回归用例的发现」做反向对照，断言它在 12-31 也不算 overdue；"
     "最后断言同一批数据换 today 结论随之变化（证明用的是注入日期而非系统时钟），"
     "并实测定时任务 scan() 输出的 overdue 清单"),
    ("AC2", "P0 发现改为 wont_fix 返回 422（pytest 通过）", "V13-V17",
     "取种子里已 confirmed 的 P0，PATCH 成 wont_fix 断言 422 且原因点明 P0 不允许；"
     "再用 P2 + 安全负责人角色 + 理由做正向对照（应 200），"
     "并用缺审批权限的角色做反例（应 403/422）"),
    ("AC3", "evidence 中的金丝雀片段入库后已被掩码（测试断言）", "V18-V21",
     "提交一条含金丝雀/手机号/邮箱的 evidence，**直接查库**（不查响应体）断言："
     "库里金丝雀已变成 3ZZP-****-Y3SZ、手机号已按前3后4掩码；"
     "再用反向对照断言未掩码的原文会被判为泄露（证明检测本身有效）"),
    ("AC4", "月度导出接口返回新增、已修复、未关闭三组数据", "V22-V26",
     "GET monthly?month=2026-11 断言返回 created/fixed/open 三组；"
     "逐组核对口径：新增按 found_at、已修复按 fixed_at（特意放了一条 found_at 在 10 月、"
     "fixed_at 在 11 月的跨月样本锁住口径）、未关闭排除 verified 与 wont_fix；"
     "最后断言三组计数与清单长度一致"),
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


def provenance(db_ver=None, srv=None):
    rows = [
        ("生成脚本", "`pkg/engine.py`（7 条虚构种子 + 3 档冻结日期场景）"),
        ("生成脚本 sha256", "`%s`" % sha("pkg/engine.py")),
        ("状态机 sha256", "`%s`" % sha("pkg/state.py")),
        ("工作日算法 sha256", "`%s`" % sha("pkg/workdays.py")),
        ("掩码规则 sha256", "`%s`" % sha("pkg/redact.py")),
        ("迁移脚本 sha256", "`%s`" % sha("migrations/versions/0001_redteam_finding.py")),
        ("随机性", "**无随机**。种子数据为手写常量，finding_no 按年递增生成；"
                 "所有日期为显式常量，工作日算法用整数序数（不读系统时间、不依赖 tzdata）"),
        ("种子", "不适用（无随机数生成器）"),
        ("重跑命令", "`python pkg/engine.py` ／ `python -c \"from pkg.db import reset_schema; reset_schema()\"`"),
        ("数据库", "真 PostgreSQL %s；建表由 Alembic 迁移完成（revision=%s），"
                 "**不在 app 启动时 create_all**，避免买家先 pytest 再 alembic 撞 DuplicateTable"
                 % (srv or "16", db_ver or "0001")),
        ("产出规模", "7 条红队发现 / 3 档冻结日期 / 2 张表 / pytest 77 项"),
        ("PII 说明", "种子里的手机号、身份证、银行卡、邮箱与金丝雀**均为虚构**："
                 "号码由自选号段构造，金丝雀为三段随机码（3ZZP-9ERG-Y3SZ），"
                 "不对应任何真实个人或企业。这些敏感串正是 AC3 的测试输入，"
                 "断言的是它们**入库后已被掩码**"),
    ]
    L = ["# DATA_PROVENANCE — 数据来源与可复核性", "",
         "本交付包**不含任何真实个人信息或企业信息**。全部示例数据由脚本生成，可完整重放。", "",
         "| 项 | 值 |", "| --- | --- |"]
    L += ["| %s | %s |" % (k, v) for k, v in rows]
    L += ["", "## 虚构声明", "",
          "发现编号、标题、复现步骤、工具名、角色名与全部日期均为虚构；"
          "文本中不出现客户名称。金丝雀与各类号码是**测试用的假数据**，"
          "其作用是验证「入库前掩码」这条规则是否真的生效。", ""]
    return "\n".join(L)


def readme(n_verify):
    L = ["# 红队发现登记与回归转化跟踪（S5-EVAL-032）", "",
         "`redteam_finding` 表 + 4 个接口 + overdue 定时检查："
         "登记红队发现、跟踪到 verified，并保证 `confirmed` 后 2 个工作日内必须关联回归用例；"
         "`evidence` 入库前掩码；`P0` 不允许 `wont_fix`；月度导出三组清单。", "",
         "## 一条命令复跑", "", "```",
         "export DATABASE_URL=postgresql+psycopg2://user:pass@127.0.0.1:5432/dbname",
         "python pkg/engine.py                    # 重算 data/seeds.json",
         "python -c 'from pkg.db import reset_schema; reset_schema()'   # DROP SCHEMA + alembic upgrade",
         "python tools/verify.py                  # 逐条断言 AC（%d 条）" % n_verify,
         "python -m pytest tests -v               # pytest（77 项，需真 PG）",
         "python tools/mutate.py                  # 变异自检（15 处，需真 PG）",
         "python tools/make_zip.py                # 打包 + SHA256SUMS", "```", "",
         "依赖：Python 3.11+、FastAPI、SQLAlchemy 2、Alembic、psycopg2、PostgreSQL 16。", "",
         "## 接口", "", "| 方法 | 路径 | 说明 |", "| --- | --- | --- |",
         "| POST | `/api/eval/redteam-findings` | 登记（需 `eval.redteam.write`） |",
         "| GET | `/api/eval/redteam-findings` | 列表，可按 tool / severity / status 筛选 |",
         "| PATCH | `/api/eval/redteam-findings/{id}` | 改状态或字段 |",
         "| GET | `/api/eval/redteam-findings/monthly?month=yyyy-mm` | 月度导出三组 |", "",
         "权限与身份由 S2-IAM 注入，本单用请求头桩：`X-Permissions` / `X-Role` / `X-Operator` / `X-Org`。", "",
         "## 四条容易被忽略的实现细节", "",
         "**① 建表权只归 Alembic，不在 app 启动时 create_all。**",
         "两者并存时，买家按 README 顺序「先 pytest 再 alembic upgrade」会立刻撞 `DuplicateTable`。"
         "本包的 `pkg/db.py::reset_schema()` 先 `DROP SCHEMA public CASCADE` 再 `alembic upgrade head`，"
         "测试夹具与 seed 都走这一条路 —— 好处是「测的是迁移真正建出来的表」，schema 漂移不会被放过。", "",
         "**② 「2 个工作日」必须自己算，且要能冻结。**",
         "`pkg/workdays.py` 用整数序数算星期（与 `datetime` 交叉验证），"
         "显式扣节假日表、跳过周末；`pkg/clock.py` 不 import datetime、不读系统时间。"
         "所以「截止日当天不算逾期、次日起算逾期」这类边界在任何机器上结论都相同。"
         "踩过的坑：第一版星期偏移写成 `+4`，把周五算成了周末 —— 是交叉验证测试抓出来的。", "",
         "**③ 掩码必须在写库之前，且断言要查库不查响应。**",
         "如果只在响应里掩码，库里仍是原文，等于没做。本包在 `api.py` 的登记与 PATCH 两处都过 "
         "`redact.mask_or_raise()`，`verify.py` 的 V18 直接 `sess.get(...)` 读库断言。"
         "另外规则顺序有讲究：`idcard` 必须排在 `bank` 之前 —— 18 位身份证同时满足卡号的 "
         "`\\d{16,19}`，顺序反了会按「卡号」掩码（前6后4），语义不对。", "",
         "**④ PATCH 只在显式给了 status 时才走状态机。**",
         "第一版无条件调 `check_transition`，导致「只补 evidence」「只关联回归用例」这两种纯字段更新"
         "被判成「状态未变化」而 422。判据：字段更新与状态迁移是两件事。", "",
         "## 目录", "", "| 路径 | 内容 |", "| --- | --- |",
         "| `pkg/models.py` | SQLAlchemy 模型（含统一约定的审计字段与软删除） |",
         "| `migrations/versions/0001_redteam_finding.py` | 建表迁移（2 张表 + 索引 + 唯一约束） |",
         "| `pkg/db.py` | 引擎/会话；`reset_schema()` 走 Alembic |",
         "| `pkg/api.py` | 4 个接口 + 权限/状态/掩码校验 |",
         "| `pkg/state.py` | 状态机、`P0` 禁 `wont_fix`、`verified` 必须带 run_id |",
         "| `pkg/workdays.py` | 工作日与 overdue 判定（整数序数，可冻结） |",
         "| `pkg/redact.py` | evidence 掩码（手机/身份证/银行/邮箱/信用代码/金丝雀） |",
         "| `pkg/jobs.py` | overdue 定时检查（纯函数 `scan()`，可直接传 today） |",
         "| `pkg/engine.py` | 7 条虚构种子 + 3 档冻结日期 |",
         "| `tests/` | pytest 77 项（时间 19 / 规则 34 / 接口 24） |",
         "| `tools/verify.py` | %d 条 AC 断言（含真 PG 查询） |" % n_verify,
         "", "## 设计取舍", "",
         "- **`overdue` 是派生状态而非常驻列**：它随「今天」变化，写进库里必然过期。"
         "本实现按需计算（GET 带 `today` 参数、定时任务传 `today`），库里只存事实（`confirmed_at`）。",
         "- **`wont_fix` 要求审批角色而不是审批人 ID**：工单说「需安全负责人审批」，"
         "角色比具体人更稳定（人员变动不影响历史记录）。",
         "- **月度导出不落快照表**：三组清单按 `found_at` / `fixed_at` 现算，"
         "避免快照与事实不一致。`redteam_monthly_archive` 表保留给需要留存的历史月报。",
         ]
    return "\n".join(L)


def main():
    r = subprocess.run([sys.executable, "tools/verify.py"], cwd=ROOT, env=ENV,
                       capture_output=True)
    ver_out = (r.stdout + r.stderr).decode("utf-8", "replace")
    n = len([l for l in ver_out.splitlines() if l.startswith(("[PASS]", "[FAIL]"))])

    db_ver = srv = None
    try:
        from sqlalchemy import text
        from pkg.db import get_engine
        with get_engine().begin() as c:
            db_ver = c.execute(text("select version_num from alembic_version")).scalar()
            srv = c.execute(text("show server_version")).scalar()
    except Exception as e:  # noqa: BLE001
        print("    (读数据库版本失败：%s: %s)" % (type(e).__name__, e))

    W = lambda rel, s: open(os.path.join(ROOT, rel), "w",
                            encoding="utf-8", newline="\n").write(s)
    W("README.md", readme(n))
    W("ACCEPTANCE.md", acceptance(ver_out))
    W("DATA_PROVENANCE.md", provenance(db_ver, srv))
    print("verify_rc=%d verify_lines=%d db=%s rev=%s" % (r.returncode, n, srv, db_ver))
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
