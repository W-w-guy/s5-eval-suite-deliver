# 评测用例双人复核：评审接口与评审页面

S5-EVAL-008 · 会员空间平台。本目录是可直接复跑的完整交付件：
后端 3 个接口 + Alembic 迁移、前端 React + TDesign 两个页面、pytest 与 Vitest 两套测试、
变异自测、真实浏览器截图。

## 目录

| 路径 | 作用 |
|---|---|
| `app/engine.py` | 复核规则纯函数（不碰 DB，单测与变异改的是它） |
| `app/main.py` | 三个接口 + 前端静态托管 |
| `app/db.py` | ORM 与数据库接入（优先 `DATABASE_URL`，否则起内嵌 PG） |
| `app/schema.py` | 建表唯一入口：重置 schema + 跑 alembic 迁移链 |
| `alembic/versions/0000_baseline.py` | 上游既有三表（套件 / 用例 / 运行） |
| `alembic/versions/0001_eval_case_review.py` | 本单新增：复核记录表 |
| `tests/` | 17 项 pytest，按 AC1~AC4 + 契约分文件 |
| `frontend/src/pages/` | 两个页面：套件列表 `/eval/suites`、用例详情 `/eval/suites/:key/cases/:case_key` |
| `frontend/src/__tests__/` | 10 项 Vitest（建议 JSON 4 项 + 页面交互 6 项） |
| `tools/mutate.py` | 变异自测：把规则改坏，验证断言真的会红 |
| `tools/seed_demo.py` | 生成虚构演示数据 |
| `docs/shots/` | 4 张页面截图（真实渲染） |
| `verify.py` | 一条命令跑完全部检查 |

## 复跑

```bash
pip install -r requirements.txt
python -m playwright install chromium

cd frontend && npm ci && npm run build && npm test && cd ..

python verify.py --require-pg --require-node
```

有现成 PostgreSQL 时：`DATABASE_URL=postgresql://user:pass@host:5432/db python verify.py`

只跑后端（本机没有 node 时）：`python verify.py --require-pg`
（此时前端 Vitest 记 SKIP，不冒充通过；`frontend/dist` 用随包产物。）

## 前端

```bash
cd frontend
npm ci
npm run dev      # 开发：vite，/api 代理到 127.0.0.1:8000
npm run build    # 构建到 frontend/dist，由后端直接 serve
npm test         # Vitest
```

两个路由：

- `/eval/suites` —— 套件列表，显示用例数 / 已复核数 / 待复核数 / 最近通过率，带「只看待复核」开关
- `/eval/suites/:suite_key/cases/:case_key` —— 用例详情，逐条要点标 同意 / 需修改 / 删除 并写意见

**页面不直接改用例文件**：只导出 `eval-case-suggestion/v1` 格式的修改建议 JSON
（含 `applied_to_file: false` 与 `content_hash`），由维护者改文件后提 PR。
这是工单明确要求的分工，也是「导出建议」而不是「保存」的原因。

### 权限

真实环境由 S2-IAM 下发身份与权限；本单用请求头 `X-User-Id` / `X-Permissions` 模拟对接点。
只有 `eval.case.review` 能评审，接口层返回 403，页面层同步禁用三个操作与提交/导出按钮。

### 一个接口兼容两种取法

工单只给了 3 个接口，但前端路由用的是 `:case_key`。为了不擅自新增第 4 个接口，
`GET /api/eval/cases/{id}` 的路径段同时接受 UUID 与 case_key（先按 UUID 解析，失败再按 case_key 查）。

## 单独跑某条验收标准

```bash
python -m pytest tests/test_ac1_double_review.py -v   # AC1 双人复核
python -m pytest tests/test_ac2_hash_reset.py -v      # AC2 hash 变化重置
python -m pytest tests/test_ac3_page.py -v            # AC3 页面三操作（真浏览器）
python -m pytest tests/test_ac4_authz.py -v           # AC4 无权限 403
cd frontend && npx vitest run                         # 前端 10 项
```

## 变异自测

```bash
python tools/mutate.py
```

判据三条：改坏后测试必须红、还原后必须重新全绿、锚点找不到要报 INVALID
（锚点没命中等于变异本身失效，不能记作「抓到」）。
前端变异会先重建 `dist` 再跑，否则浏览器跑的是旧包，会假绿。

## 三条业务规则

1. 同一评审人重复 approve 不会让用例变为 reviewed，两名**不同**评审人 approve 才变
2. 用例文件内容 hash 变化后，复核状态重置为待复核
3. 任一 revise 或 remove 使状态变 needs_change；remove 单独出现同样阻断

## 设计说明

**建表权归 alembic，app 启动不再 `create_all`。**
两者并存时，先跑测试再跑迁移会 DuplicateTable。测试 fixture 也走同一条迁移链
（`app/schema.py::reset_and_migrate`），这样测的是迁移真正建出来的表，
而不是 ORM 声明里的表——schema 漂移不会被悄悄放过。

## 环境

Windows 11 + Python 3.11.7 + PostgreSQL 16.2（pgserver 内嵌）+ Chromium 159
Ubuntu 24 + Python 3.12.3 + PostgreSQL 16.2（pgserver 内嵌）+ Chromium 159 + Node 18.19.1
两侧 `verify.py` 均 12/12 PASS、0 SKIP。
