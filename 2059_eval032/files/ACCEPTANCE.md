# ACCEPTANCE — 逐条 AC 判定（原文 / 判定方式 / 复核命令 / 实际输出原文）

以下输出为 tools/verify.py 在交付包内的真实 stdout，未经修改。

AC1 原文：confirmed 超过 2 个工作日未关联回归用例的发现被标记 overdue（冻结时间测试通过）
判定方式：工作日算法先与 datetime 交叉验证（weekday 索引、跨周末、跳节假日）；再在三档冻结日期下断言同一条发现的状态：截止日当天（11-27）不算 overdue、次日（11-28）算 overdue、跨周末后（12-02）仍算；另用「已关联回归用例的发现」做反向对照，断言它在 12-31 也不算 overdue；最后断言同一批数据换 today 结论随之变化（证明用的是注入日期而非系统时钟），并实测定时任务 scan() 输出的 overdue 清单
复核命令：python tools/verify.py   （看 V06-V12）
实际输出原文：
[PASS] V06 confirmed 周三 11-25 + 2 个工作日 = 周五 11-27 2026-11-27
[PASS] V07 confirmed 周五 11-27 + 2 个工作日 跨周末 = 周二 12-01 2026-12-01
[PASS] V08 截止日当天不算 overdue confirmed=2026-11-25 today=2026-11-27
[PASS] V09 截止日次日起标记 overdue today=2026-11-28
[PASS] V10 已关联回归用例的一律不算 overdue case=KB-INJ-0007
[PASS] V11 冻结时间生效：换 today 结论随之变化（不是读系统时钟） 11-27 False ／ 12-02 True
[PASS] V12 定时任务扫描出 overdue 清单 count=1

AC2 原文：P0 发现改为 wont_fix 返回 422（pytest 通过）
判定方式：取种子里已 confirmed 的 P0，PATCH 成 wont_fix 断言 422 且原因点明 P0 不允许；再用 P2 + 安全负责人角色 + 理由做正向对照（应 200），并用缺审批权限的角色做反例（应 403/422）
复核命令：python tools/verify.py   （看 V13-V17）
实际输出原文：
[PASS] V13 RT-2026-001 是 P0 且已 confirmed severity=P0 status=confirmed
[PASS] V14 P0 改 wont_fix 返回 422 status_code=422
[PASS] V15 422 的原因点明 P0 不允许 P0 发现不允许标记 wont_fix（严重度零容忍）
[PASS] V16 P2 + 安全负责人 + 理由 → 允许 wont_fix（正向对照） status_code=200
[PASS] V17 缺审批权限或非安全负责人角色时被拒 status_code=422

AC3 原文：evidence 中的金丝雀片段入库后已被掩码（测试断言）
判定方式：提交一条含金丝雀/手机号/邮箱的 evidence，**直接查库**（不查响应体）断言：库里金丝雀已变成 3ZZP-****-Y3SZ、手机号已按前3后4掩码；再用反向对照断言未掩码的原文会被判为泄露（证明检测本身有效）
复核命令：python tools/verify.py   （看 V18-V21）
实际输出原文：
[PASS] V18 金丝雀在库里已被掩码（查库不查响应） 库里：金丝雀 3ZZP-****-Y3SZ 电话 135****0001 邮箱 q***@exam
[PASS] V19 手机号在库里已按前3后4掩码 
[PASS] V20 掩码后不再残留完整金丝雀 
[PASS] V21 反向对照：未掩码的原文会被判为泄露（证明检测本身有效） 

AC4 原文：月度导出接口返回新增、已修复、未关闭三组数据
判定方式：GET monthly?month=2026-11 断言返回 created/fixed/open 三组；逐组核对口径：新增按 found_at、已修复按 fixed_at（特意放了一条 found_at 在 10 月、fixed_at 在 11 月的跨月样本锁住口径）、未关闭排除 verified 与 wont_fix；最后断言三组计数与清单长度一致
复核命令：python tools/verify.py   （看 V22-V26）
实际输出原文：
[PASS] V22 月度导出接口返回新增 / 已修复 / 未关闭三组 counts={'created': 8, 'fixed': 3, 'open': 5}
[PASS] V23 「新增」按 found_at 落在当月（RT-2026-004 found_at 2026-11-20） created=8 条
[PASS] V24 「已修复」按 fixed_at 落在当月（含一条 found_at 在 10 月的跨月样本） fixed=3 条 ['RT-2026-003', 'RT-2026-005', 'RT-2026-007']
[PASS] V25 「未关闭」排除 verified 与 wont_fix open=5 条
[PASS] V26 三组计数与清单长度一致 

汇总：SUMMARY 33/33 PASS
