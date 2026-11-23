# 2590 · S3-SOP-033 首批 SOP 模板配置：续约预警

本包交付 S3-SOP-033「续约预警」的 **SOP 模板配置**、**步骤说明文档**、**关怀话术文本**与**集成测试**，对应工单四项交付物。

- 模板：`sop/templates/renewal.json`（5 步、4 本字典、4 条话术；工单指定路径）
- 说明：`docs/steps-renewal.md`（75 行逐步说明，含每步的时限锚点与判定口径）
- 话术：`docs/scripts-renewal.md`（4 段）
- 测试：`tests/test_renewal_ac.py`（43 项，覆盖 4 条 AC + 8 项扩展 + 返工补的 12 项，含 3 项文档一致性断言）
- 校验器：`sop/lint.py`（`python -m sop.lint`）、`tests/mutate.py`（变异测试）

## 运行与测试方法

**依赖：仅 Python 3.8+ 标准库，无任何第三方包。** 不需要装 fastapi / pytest / zoneinfo 数据，干净机器即可跑。

```bash
cd files
python verify.py            # 一键：lint + AC 43 项 + 变异测试   期望 rc=0
```

分步跑：

```bash
python -m sop.lint sop/templates/renewal.json   # 静态校验，期望 "PASS renewal.json  0 error / 0 warn"
python tests/test_renewal_ac.py             # AC 集成测试，期望 "合计 43 项：PASS 43 / FAIL 0"
python tests/mutate.py                      # 变异测试，期望 "变异断言 29 条：检出 29 / 漏检 0"
python tools/pii_scan.py                    # pii 扫描，期望 "unexpected=0 ... PII PASS"
```

重跑生成器（应与包内文件逐字节相同）：

```bash
python tools/build_renewal.py
```


## 跨平台一致性（实测踩到一个真缺陷，已修）

本包要求两平台产出**逐字节相同**，实测在这里抓到过一处真问题：

```
同一份 tools/build_renewal.py
  Windows  产出 renewal.json = 6,658 字节  sha256 0d26b9d3…
  Ubuntu   产出 renewal.json = 6,465 字节  sha256 4f1d6e04…
  差值 193 字节 = 文件行数 → 正是 Windows 文本模式默认把 \n 写成 CRLF
```

修法：生成器写文件时显式 `newline="\n"`。修后（本轮返工重新实测）：

```
Windows  sop/templates/renewal.json  6,440 字节  sha256 8420dcb9e8f1c3807042e12e717e182aec9f2cbfb2a61fbe76cf366d1b9d6bf1
Ubuntu   sop/templates/renewal.json  6,440 字节  sha256 8420dcb9e8f1c3807042e12e717e182aec9f2cbfb2a61fbe76cf366d1b9d6bf1
cmp 结果 IDENTICAL
```

**为什么这条值得写进 README**：如果只在 Windows 上验证，`重跑生成器产出与包内一致` 这条断言在 Ubuntu 上会直接失败——买家一跑就 mismatch，而我们在自己机器上看到的是全绿。包内全部文本文件统一为 LF，`SHA256SUMS` 列 17 个受校验文件（不列自身），两平台 `sha256sum -c` 均 17/17 OK。

**注意**：`SHA256SUMS` 不列自身（列了 `sha256sum -c` 恒有 1 条 FAIL），`__pycache__` 不参与校验。

## 生成本文件的顺序陷阱（本轮踩到，如实记录）

`SHA256SUMS` 必须在**所有文件改完之后**才生成。本轮我先算了校验和，之后又去给 `DATA_PROVENANCE.md` 里抄出来的命中字符串打码，导致 Ubuntu 上 `sha256sum -c` 报 `DATA_PROVENANCE.md: FAILED`。这类错在本机不会自己冒出来——只有真去 `-c` 一遍才看得见。

## 已实测的双平台结果

| 平台 | Python | verify | AC | 变异 | pii |
|---|---|---|---|---|---|
| Windows 10 (22631) | 3.11.7 | 3/3 | 43/43 PASS | 29/29 检出 | unexpected=0 |
| Ubuntu 24.04 | 3.12.3 | 3/3 | 43/43 PASS | 29/29 检出 | unexpected=0 |

原始日志在 `../verify_logs/`：`WINDOWS_{verify,lint,ac,mutate,pii,gen}.log` 与 `UBUNTU_{verify,lint,ac,mutate,pii,gen,sha256sum}.log`，含 `ENV_*.txt` 平台信息。

## 目录结构

```
files/
├── verify.py                  一键验证
├── ACCEPTANCE.md              4 条 AC 的四元组（原文/判定方式/复核命令/实际输出原文）
├── DATA_PROVENANCE.md         数据来源与可复核性
├── README.md                  本文件
├── sop/templates/renewal.json 交付主件（工单指定路径）
├── docs/steps-renewal.md      步骤说明文档
├── docs/scripts-renewal.md    关怀话术文本
├── sop/                       模板运行时（engine/clock/lint/mock/schema）
├── tools/build_renewal.py     生成器
└── tests/                     AC 集成测试 + 变异测试
```

## 集成对接点（README 要求写明）

按工单【依赖】「可先用接口桩或 mock」，本包用 `sop/mock.py` 提供四个桩，接入客户真实系统时替换它们即可，模板与测试不用改：

| 桩 | 位置 | 对接目标 | 替换方式 |
|---|---|---|---|
| `MembershipRepo` | `sop/mock.py` | S2-CRM 会员对象 | 实现同名 `find_expiring(days)` / `all()` / `get(id)` 即可 |
| `TodoApi` | `sop/mock.py` | 工作台待办 | 实现 `create` / `close` / `transfer_all` |
| `Notifier` | `sop/mock.py` | 通知渠道 | 实现 `send(role, text)` |
| `Notebook` | `sop/mock.py` | 引擎事件与审计落库 | 实现 `append(kind, payload)` |

引擎入口 `sop/engine.py:Engine([tpl], objects, clock, notifier=..., effects=...)`，模板格式由 `sop/schema.json` 定义。

## 数据与保密

- 全部示例数据虚构，无真实个人信息 / 企业信息。`python tools/pii_scan.py` 实测 `unexpected=0`。
- 交付物中不出现客户名称（全文扫描 0 命中）。
- 本单信息仅用于完成本单。

## 已知局限（如实列出）

- 只交 #2590 一单，不含另外 6 个 SOP 模板。
- 第②步 `ai_care_draft` 为占位字段（工单要求「后续阶段接入」），本阶段人工填写。
- 第④步只记录报价单编号，不计算金额（金额由报价模块按价格规则表计算）。
- 时间锚点用固定基准日 2026-03-02 以便产物可复现；接入真实站点时把 `FrozenClock` 换成系统时钟即可，规则不变。
