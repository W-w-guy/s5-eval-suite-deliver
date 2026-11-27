# CROSS_PLATFORM — 双平台实跑与产物一致性

本单的核心断言需要**真 PostgreSQL**，因此以 Ubuntu 侧真跑为准；
Windows 侧无可用 PG 实例，如实记录为「未跑」而不是「通过」。

## 环境

| 平台 | 版本 | 能否跑真库断言 |
| --- | --- | --- |
| Windows 11 | Python 3.11.7 / **无 PostgreSQL** | 否 —— 只跑纯逻辑测试（53 项） |
| Ubuntu 24.04 | Python 3.12.3 / PostgreSQL 16.2 / psycopg2 2.9.13 / alembic 1.20.1 | 是 —— 全套 33 条断言 + 77 项 pytest + 15 处变异 |

## 两侧结果

| 项 | Windows | Ubuntu |
| --- | --- | --- |
| `tests/test_workdays.py` | 19 passed | 19 passed |
| `tests/test_rules.py` | 34 passed | 34 passed |
| `tests/test_api.py`（需真库） | 未跑 | 24 passed |
| `tools/verify.py` | 未跑（需真库） | **SUMMARY 33/33 PASS** |
| `tools/mutate.py` | 未跑（需真库） | **CAUGHT 15 / MISSED 0 / INVALID 0** |
| `python -m compileall` | 全通过 | 全通过 |

## 数据库证据（Ubuntu）

- `show server_version` → **16.2**（真 PostgreSQL，非 sqlite 模拟）
- 建表方式 → `DROP SCHEMA public CASCADE` 之后 `alembic upgrade head`
- `alembic_version` → **0001**
- 查 `information_schema.tables` → `redteam_finding` / `redteam_monthly_archive` / `alembic_version`
- `redteam_finding` 24 列，含统一约定的 org_id / site_id / created_at / created_by / updated_at / deleted_at

## 哪些不纳入 SHA256SUMS

- `verify_logs/` —— 实跑日志快照，随运行变化。
- `data/overdue_snapshot.json` —— 定时任务产物（本包默认不写）。

## 本单踩到并修掉的三个环境问题

1. **pgserver 的 handle 被回收后 PG 会停**：`get_server()` 返回的对象一旦被 GC，
   服务就停止监听，后续连接报 `socket ... failed: No such file or directory`。
   修法：用一个常驻 keeper 进程持有 handle。
2. **`alembic.ini` 必须纯 ASCII**：Alembic 用系统 locale 读该文件（zh-CN Windows 是 GBK），
   里面写中文注释会在跑任何迁移之前就 `UnicodeDecodeError`。
3. **HTTP 头不能承载中文**：角色名原本写成「安全负责人」，放进 `X-Role` 后在
   httpx 层直接 `UnicodeEncodeError: 'ascii' codec can't encode`。
   改成 ASCII 角色码（`security_lead`），中文只作展示名。
