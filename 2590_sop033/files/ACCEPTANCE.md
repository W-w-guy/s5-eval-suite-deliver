# ACCEPTANCE.md · 2590 S3-SOP-033「续约预警」模板配置

> 用途：把工单的 4 条验收标准逐条落成「原文 / 判定方式 / 复核命令 / 实际输出原文」四元组。
> 平台复核只读文本、不执行代码（runtime_verified=false），所以每条都**贴真跑输出原文**，不写「已通过」三个字。
> 全部示例数据虚构；包内不含客户名称；本文件中的命令均可在本目录直接执行。

---

## AC1 原文

> sop-lint 检查通过，导入后可以成功发布

**判定方式**

1. `sop/lint.py` 对 `templates/renewal.json` 报 **0 error / 0 warn**（退出码 0）。
2. 「可以成功发布」落到引擎侧的实际动作：`Engine([tpl], ...)` 能加载并注册该模板 —— 加载失败会抛异常，加载成功即代表模板结构可被运行时接受。
3. 这两点是**两个独立判定**：lint 是静态规则校验，Engine 加载是运行时接受；只过其中一个不算过。

**复核命令**

```bash
python -m sop.lint templates/renewal.json      # 期望 rc=0
python tests/test_renewal_ac.py                # 内含 AC1.4「引擎可加载模板」
```

**实际输出原文**

```
$ python -m sop.lint templates/renewal.json
PASS renewal.json  0 error / 0 warn

$ python tests/test_renewal_ac.py
PASS  AC1.1 sop-lint 无 ERROR
PASS  AC1.2 template_id/version/target_object 齐备
PASS  AC1.3 触发为定时每日 09:00 且去重 120 天
PASS  AC1.4 引擎可加载模板（可发布）
```

**约束与边界**（判定口径写死在测试里，不是口头约定）

- 模板必须 `template_id` / `version` / `target_object` 三项齐备，缺一项 lint 报 E0xx。
- 触发必须是 `schedule` + 6 段 cron 且时刻等于 09:00；去重窗口必须是整数 120，写成 `"120"` 字符串报 E014。
- 契约字段在 `sop/schema.json` 里定义，lint 读 schema 而不是读测试里的期望值——**改 schema 会让 lint 与测试同时变，不会出现「测试跟着实现改」的假通过**。

---

## AC2 原文

> 冻结时间测试：会籍到期前 90 天的虚构会员在当天 09:00 被触发，120 天内不重复触发

**判定方式**

用 `sop/clock.py:FrozenClock` 冻结虚拟时钟（不读系统时间，产物可复现），逐项断言：

1. 会籍到期前 90 天（`expire_at=2026-05-31`，基准日 `2026-03-02 09:00`）的会员 → 当天 09:00 **必须**生成 1 个实例。
2. 触发走命名查询 `membership_expiring_within(days=90)`，且**已进入流失预警**的会员同样命中。
3. 同日再次调度 → 不重复生成（同日幂等）。
4. 第 119 天 → 仍在去重窗口内，不生成。
5. 第 120 天（满）→ 窗口关闭；第 121 天 → 可再次触发。

**复核命令**

```bash
python tests/test_renewal_ac.py     # AC2.1 ~ AC2.8
```

**实际输出原文**

```
PASS  AC2.1 09:00 定时任务命中并生成实例
PASS  AC2.2 命中命名查询 membership_expiring_within(days=90)
PASS  AC2.3 实例绑定 membership 对象且第一步已派给会员经理
PASS  AC2.4 同日再次调度不重复生成
PASS  AC2.5 119 天后仍在去重窗口内，不生成
PASS  AC2.6 121 天后去重窗口已过
PASS  AC2.7 119 天仍在窗口内
PASS  AC2.8 满 120 天窗口关闭
```

**约束与边界**

- **基准日固定为 2026-03-02（周一）**，不取运行时 today —— 否则每天跑出来的产物都不同，断言写不死、也证明不了「当天 09:00」。
- 边界是**双边**的：119 天在窗口内、120 天恰好关闭、121 天可再触发。只测「119 不触发」会漏掉「窗口是不是永远不会关」这类单边错误。
- 反例自证：把 `dedupe_days` 改成 1 → 隔 2 天必须出现第 2 个实例；对照原件隔 2 天只有 1 个（变异测试里两条都跑）。

---

## AC3 原文

> 健康分 ≥ 40 的非重点会员第③步自动跳过（测试）

**判定方式**

第③步是**条件步骤**（`conditional=true`），条件为「重点会员 或 健康分 < 40」。四种组合全部断言，不抽样：

| 会员 | 健康分 | 第③步期望 |
|---|---|---|
| 非重点 | 40（边界值） | **跳过** |
| 非重点 | 39 | 生成 |
| 重点 | 60 | 生成 |
| 重点 | 39 | 生成 |

另断言：跳过后**必须记下跳过原因**，且第④步被正常激活（不是整条流程停摆）。

**复核命令**

```bash
python tests/test_renewal_ac.py     # AC3.1 ~ AC3.5
python tests/mutate.py              # 「条件改坏后健康分 39 的第③步被误跳过」
```

**实际输出原文**

```
PASS  AC3.1 非重点且健康分>=40 → 第③步 skipped
PASS  AC3.2 跳过原因已记录
PASS  AC3.3 跳过后第④步被激活
PASS  AC3.4 重点会员 → 第③步必须生成
PASS  AC3.5 健康分 39<40 → 第③步必须生成

（变异）
检出  renewal: 条件改坏后健康分 39 的第③步被误跳过
```

**约束与边界**

- **40 是边界值，必须测「等于 40」**。写成 `>` 而不是 `>=` 时，健康分恰好 40 的会员会被误生成第③步 —— AC3.1 就是卡这个点。
- 跳过不等于终结：跳过后第④步仍要激活，否则「自动跳过」退化成「流程中断」。
- 边界反向也要测：重点会员 / 健康分 39 两种「必须生成」的情形，防止条件被写成恒 False（那样会一直跳，看起来也「符合」跳过要求）。

---

## AC4 原文

> 第⑤步完成后会员生命周期状态未被系统修改（测试）

**判定方式**

这是**「不该做的事」类断言**，判定要点是**有没有发生写入**，而不是「结果看起来对不对」：

1. 完成第⑤步后，`membership.lifecycle_status` 仍为 `active`。
2. SOP 引擎**从未调用过 CRM 的生命周期写入接口**（用 mock 记录调用轨迹，断言调用次数 = 0）。
3. 引擎持有的对象副本也未改状态（排除「只在内存里改了、没落库」这种假绿）。
4. **排除假通过**：另建一个会拒绝 SOP 侧写入的 CRM mock，断言它确实会拒绝 —— 否则「写入 0 次」可能只是因为 mock 根本没接上。

**复核命令**

```bash
python tests/test_renewal_ac.py     # AC4.1 ~ AC4.6
```

**实际输出原文**

```
PASS  AC4.1 第⑤步已完成
PASS  AC4.2 实例状态 done
PASS  AC4.3 SOP 引擎未调用 CRM 生命周期写入接口
PASS  AC4.4 membership.lifecycle_status 仍为 active
PASS  AC4.5 引擎对象副本也未改状态
PASS  AC4.6 CRM 守卫确实会拒绝 SOP 侧写入（排除假通过）
```

**约束与边界**

- 只断言「状态还是 active」不够：如果引擎压根没接上 CRM，「没改」就毫无意义。所以 AC4.6 专门证明守卫**会**拒绝，让 AC4.3 的「0 次调用」有意义。
- 第⑤步的输出只做记录：续约 / 流失（**原因必填**）/ 延期。选了流失但没填原因 → 拒绝完成（见 EX8）。
- 会员生命周期状态由员工在 CRM 中确认，**系统不自动修改** —— 这条在模板里体现为模板不含任何 `crm.lifecycle.*` 写操作，lint 侧也不允许出现。

---

## 附：扩展断言（工单未点名，但属于「模板配置」的应有之义）

`python tests/test_renewal_ac.py` 另跑 9 项（EX1~EX8），全部 PASS：

```
PASS  EX1 第①步截止 = 触发后 3 个工作日 18:00
PASS  EX2 第②步截止 = 完成后 5 个工作日（周一 03-02 +5 工作日 = 周一 03-09）
PASS  EX3 第④步锚定 object.expire_at - 30 自然日
PASS  EX4 第⑤步锚定 object.expire_at - 7 自然日
PASS  EX5 收到 membership.renewed 后实例被取消
PASS  EX6 未完成待办一并取消
PASS  EX7 缺必填输出时拒绝完成第①步
PASS  EX8 选流失未填原因时拒绝完成第⑤步
```

合计 **31 项：PASS 31 / FAIL 0**。

## 附：本包**没有**做的事（如实列出）

- 不实现 S2-CRM 的会员对象与 S2-SPACE 的租约到期任务：按工单「可先用接口桩或 mock」，本包用 `sop/mock.py` 提供 `MembershipRepo` / `Notebook` / `Notifier` / `TodoApi` 四个桩，**不是**接客户真实系统。
- 不实现 AI 关怀建议生成：第②步的 `ai_care_draft` 按工单要求为占位字段，本阶段人工填写。
- 不实现报价计算：第④步只记录关联的报价单编号，金额由报价模块按价格规则表计算，本步骤不填金额。
- 不覆盖另外 6 个 SOP 模板（handoff/visit/onboard/matchmaking/event/offboarding）：本包只交 #2590 一单。
