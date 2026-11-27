# 红队发现登记与回归转化跟踪（S5-EVAL-032）

`redteam_finding` 表 + 4 个接口 + overdue 定时检查：登记红队发现、跟踪到 verified，并保证 `confirmed` 后 2 个工作日内必须关联回归用例；`evidence` 入库前掩码；`P0` 不允许 `wont_fix`；月度导出三组清单。

## 一条命令复跑

```
export DATABASE_URL=postgresql+psycopg2://user:pass@127.0.0.1:5432/dbname
python pkg/engine.py                    # 重算 data/seeds.json
python -c 'from pkg.db import reset_schema; reset_schema()'   # DROP SCHEMA + alembic upgrade
python tools/verify.py                  # 逐条断言 AC（33 条）
python -m pytest tests -v               # pytest（77 项，需真 PG）
python tools/mutate.py                  # 变异自检（15 处，需真 PG）
python tools/make_zip.py                # 打包 + SHA256SUMS
```

依赖：Python 3.11+、FastAPI、SQLAlchemy 2、Alembic、psycopg2、PostgreSQL 16。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/eval/redteam-findings` | 登记（需 `eval.redteam.write`） |
| GET | `/api/eval/redteam-findings` | 列表，可按 tool / severity / status 筛选 |
| PATCH | `/api/eval/redteam-findings/{id}` | 改状态或字段 |
| GET | `/api/eval/redteam-findings/monthly?month=yyyy-mm` | 月度导出三组 |

权限与身份由 S2-IAM 注入，本单用请求头桩：`X-Permissions` / `X-Role` / `X-Operator` / `X-Org`。

## 四条容易被忽略的实现细节

**① 建表权只归 Alembic，不在 app 启动时 create_all。**
两者并存时，买家按 README 顺序「先 pytest 再 alembic upgrade」会立刻撞 `DuplicateTable`。本包的 `pkg/db.py::reset_schema()` 先 `DROP SCHEMA public CASCADE` 再 `alembic upgrade head`，测试夹具与 seed 都走这一条路 —— 好处是「测的是迁移真正建出来的表」，schema 漂移不会被放过。

**② 「2 个工作日」必须自己算，且要能冻结。**
`pkg/workdays.py` 用整数序数算星期（与 `datetime` 交叉验证），显式扣节假日表、跳过周末；`pkg/clock.py` 不 import datetime、不读系统时间。所以「截止日当天不算逾期、次日起算逾期」这类边界在任何机器上结论都相同。踩过的坑：第一版星期偏移写成 `+4`，把周五算成了周末 —— 是交叉验证测试抓出来的。

**③ 掩码必须在写库之前，且断言要查库不查响应。**
如果只在响应里掩码，库里仍是原文，等于没做。本包在 `api.py` 的登记与 PATCH 两处都过 `redact.mask_or_raise()`，`verify.py` 的 V18 直接 `sess.get(...)` 读库断言。另外规则顺序有讲究：`idcard` 必须排在 `bank` 之前 —— 18 位身份证同时满足卡号的 `\d{16,19}`，顺序反了会按「卡号」掩码（前6后4），语义不对。

**④ PATCH 只在显式给了 status 时才走状态机。**
第一版无条件调 `check_transition`，导致「只补 evidence」「只关联回归用例」这两种纯字段更新被判成「状态未变化」而 422。判据：字段更新与状态迁移是两件事。

## 目录

| 路径 | 内容 |
| --- | --- |
| `pkg/models.py` | SQLAlchemy 模型（含统一约定的审计字段与软删除） |
| `migrations/versions/0001_redteam_finding.py` | 建表迁移（2 张表 + 索引 + 唯一约束） |
| `pkg/db.py` | 引擎/会话；`reset_schema()` 走 Alembic |
| `pkg/api.py` | 4 个接口 + 权限/状态/掩码校验 |
| `pkg/state.py` | 状态机、`P0` 禁 `wont_fix`、`verified` 必须带 run_id |
| `pkg/workdays.py` | 工作日与 overdue 判定（整数序数，可冻结） |
| `pkg/redact.py` | evidence 掩码（手机/身份证/银行/邮箱/信用代码/金丝雀） |
| `pkg/jobs.py` | overdue 定时检查（纯函数 `scan()`，可直接传 today） |
| `pkg/engine.py` | 7 条虚构种子 + 3 档冻结日期 |
| `tests/` | pytest 77 项（时间 19 / 规则 34 / 接口 24） |
| `tools/verify.py` | 33 条 AC 断言（含真 PG 查询） |

## 设计取舍

- **`overdue` 是派生状态而非常驻列**：它随「今天」变化，写进库里必然过期。本实现按需计算（GET 带 `today` 参数、定时任务传 `today`），库里只存事实（`confirmed_at`）。
- **`wont_fix` 要求审批角色而不是审批人 ID**：工单说「需安全负责人审批」，角色比具体人更稳定（人员变动不影响历史记录）。
- **月度导出不落快照表**：三组清单按 `found_at` / `fixed_at` 现算，避免快照与事实不一致。`redteam_monthly_archive` 表保留给需要留存的历史月报。