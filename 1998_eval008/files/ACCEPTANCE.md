# 验收证据

本文件逐条对应工单【本单范围】与【交付物】两节的要求，给出可复核命令与真实输出原文。
所有输出均为实际运行结果，不是概述。复跑方式见 README.md。

【验收证据（四元组）】

AC1 原文：同一评审人重复 approve 不会让用例变为 reviewed，两名不同评审人 approve 后才变（pytest 通过）
判定方式：同一评审人连发两次 approve，断言 review_status 仍为 pending 且 approvers 去重后只有 1 人；再换第二名评审人 approve，断言变为 reviewed。另配一条「只有 remove、没有 revise」的分支，断言它单独就能让状态变 needs_change。
复核命令：python -m pytest tests/test_ac1_double_review.py -v
实际输出原文：
[PASS] AC1 双人复核（同一人重复 approve 不变 reviewed）  4 passed | ========================= 4 passed, 1 warning in 0.95s =========================

AC2 原文：用例文件 hash 变化后复核状态重置为待复核（测试断言）
判定方式：造一个已 reviewed 的用例，把 content_hash 改成新值，断言 decide_status 返回 pending 并清空 approvers；反向用例断言 hash 未变时状态不动。
复核命令：python -m pytest tests/test_ac2_hash_reset.py -v
实际输出原文：
[PASS] AC2 用例 hash 变化后复核状态重置  2 passed | ========================= 2 passed, 1 warning in 0.94s =========================

AC3 原文：页面截图可见逐条要点的同意、需修改、删除操作
判定方式：起真实 uvicorn + 真实 React 构建产物，用 Playwright 打开浏览器逐条数按钮——每条要点必须同时存在 agree/revise/remove 三个 data-testid 且 is_visible；另跑一条真实点击链路（点需修改→填意见→点删除→断言已标记 2 条→触发下载→解析导出的 JSON 断言 applied_to_file=false 且 verdict 依次为 revise/remove），并截图落盘。
复核命令：python -m pytest tests/test_ac3_page.py -v
实际输出原文：
[PASS] AC3 页面逐条要点的同意/需修改/删除  3 passed | ========================= 3 passed, 1 warning in 7.99s =========================

AC4 原文：无评审权限的用户调用评审接口返回 403
判定方式：用只有 eval.case.read 的身份 POST 评审接口，断言 403；反向用例用带 eval.case.review 的身份同一请求断言 200，防止 403 恒成立。
复核命令：python -m pytest tests/test_ac4_authz.py -v
实际输出原文：
[PASS] AC4 无评审权限调用接口返回 403  4 passed | ========================= 4 passed, 1 warning in 0.88s =========================

AC5 原文：交付物含 pytest 与 Vitest 测试
判定方式：pytest 全量 17 项、Vitest 前端 10 项分别跑一遍，两者都必须 0 失败。
复核命令：python verify.py --require-pg --require-node
实际输出原文：
[PASS] AC5 全量 pytest  17 passed
[PASS] AC6.1 Vitest 前端单测  10 passed
SUMMARY 12/12 PASS | SKIP 0（未真跑，不计入通过）

AC6 原文：复核表迁移（alembic upgrade / downgrade 可执行）
判定方式：对真实 PostgreSQL 16.2 跑 alembic upgrade head，从 alembic_version 表回读版本号；再跑 downgrade -1，从 pg_tables 断言 eval_case_review 已删除（且上游三表仍在）。两步都回读数据库，不只看命令退出码。
复核命令：python verify.py --require-pg
实际输出原文：
[PASS] AC0 连的是真 PostgreSQL  server_version=16.2 | db=postgres
[PASS] AC0.1 alembic upgrade head  INFO  [alembic.runtime.migration] Will assume transactional DDL.
[PASS] AC0.2 alembic_version 已落库  0001_eval_case_review
[PASS] AC0.3 alembic downgrade -1  INFO  [alembic.runtime.migration] Running downgrade 0001_eval_case_review -> 0000_baseline
[PASS] AC0.4 回滚后评审表已删除  alembic_version|eval_case|eval_run|eval_suite

AC7 原文：3 个接口（GET /api/eval/suites、GET /api/eval/cases/{id}、POST /api/eval/cases/{id}/reviews）
判定方式：接口契约测试逐字段核对响应形状——套件必须含 case_count/reviewed_count/latest_pass_rate，用例详情必须含 input/context/points/recent_runs/content_hash/review_status；并断言不存在的用例返回 404。
复核命令：python -m pytest tests/test_contract.py -v
实际输出原文：
[PASS] AC5 全量 pytest  17 passed（含 tests/test_contract.py 4 项）

【变异自测】

仅「测试全绿」不足以证明断言有效：把规则改坏后测试必须变红，否则等于没测。
复核命令：python tools/mutate.py
实际输出原文：
原件（未变异）                                  PASS | ======================== 17 passed, 2 warnings in 8.09s ========================
M1 只需 1 名评审人即可通过                         [CAUGHT]   =================== 2 failed, 15 passed, 2 warnings in 8.19s =========
M2 remove 不再阻断                           [CAUGHT]   =================== 1 failed, 16 passed, 2 warnings in 8.21s =========
M3 按记录条数而非不同评审人去重                        [CAUGHT]   =================== 1 failed, 16 passed, 2 warnings in 8.25s =========
M4 hash 变化不重置                            [CAUGHT]   =================== 1 failed, 16 passed, 2 warnings in 8.28s =========
M5 任何人都可评审                               [CAUGHT]   =================== 2 failed, 15 passed, 2 warnings in 8.25s =========
M6 页面去掉「删除」按钮                            [CAUGHT]   ================== 2 failed, 15 passed, 2 warnings in 38.32s =========
还原后复跑                                    PASS | ======================== 17 passed, 2 warnings in 8.09s =========================

变异 6 个：CAUGHT 6，MISSED 0，INVALID 0

其中 M2 是修过的：第一版用例「先 revise 再 remove」，状态早已是 needs_change，
把 remove 从阻断列表里拿掉也不会变红（MISSED）。补了「只有 remove」的分支后才真正咬住。
M6 改的是前端源码，改完必须先重建 dist 再跑，否则浏览器跑的还是旧包——工具已内置这一步。

【跨平台实测】

同一份交付件（同一个 zip，sha256 相同）在两种平台上各跑一遍：

平台一 · Ubuntu 24 / Python 3.12.3 / PostgreSQL 16.2（pgserver 内嵌）/ Chromium 159 / Node 18.19.1
  完整环境（frontend/node_modules 已装）
  python verify.py --require-pg --require-node
  实际输出原文：
  SUMMARY 12/12 PASS | SKIP 0（未真跑，不计入通过）
  python tools/mutate.py
  实际输出原文：
  变异 6 个：CAUGHT 6，MISSED 0，INVALID 0

平台二 · Windows 11 / Python 3.11.7 / PostgreSQL 16.2（pgserver 内嵌）/ Chromium 159 / 无 node
  干净解压目录（不含 node_modules、不含 .pgdata）
  python verify.py --require-pg
  实际输出原文：
  SUMMARY 11/11 PASS | SKIP 1（未真跑，不计入通过）
  其中 SKIP 的一项是：AC6.1 Vitest 前端单测  缺 node/npm 或 node_modules，未真跑
  python tools/mutate.py
  实际输出原文：
  变异 6 个：CAUGHT 5，MISSED 0，INVALID 0，SKIP 1
  其中 SKIP 的一项是前端变异（M6 需重建 dist，本机无 npm），如实记录为未执行，不计入抓到。

补充：Ubuntu 的干净解压目录（删掉 node_modules 后）同样跑出 11/11 PASS + 1 SKIP，
与 Windows 一致，说明 SKIP 的唯一来源是 node 缺失，不是平台差异导致的其它失败。

跨平台差异只体现在依赖获取方式，不影响业务结论：两平台的 pytest 17 项、
真实浏览器 AC3 3 项、Alembic 升降级 4 项全部通过，变异在有能力跑的地方 100% 抓到。

【校验和治理】

SHA256SUMS 共 43 条（不含自身）。三条排除规则都是踩过坑之后加的：

  1. 不列 SHA256SUMS 自身——列了会让 sha256sum -c 恒有 1 条 FAILED。
  2. 不列 docs/shots/*.png——截图是运行产物：AC3 的测试每次跑都会重新截一遍，
     不同平台、不同字体渲染出的 PNG 字节必然不同。实测把它列进去之后，
     跑完 pytest 再校验立刻报 4 条 FAILED，看起来像文件被篡改，实际只是重新渲染了。
  3. 不列 node_modules / .pgdata / __pycache__ / .pytest_cache——可再生或本地状态。

复核命令与输出：
sha256sum -c SHA256SUMS
实际输出原文：
OK=43/43（0 条 FAILED）

必须在「解压到全新目录之后」再验一遍，否则本地残留会掩盖问题。本节所有数字均来自
全新解压目录里的实测，不是打包目录里的自查。
