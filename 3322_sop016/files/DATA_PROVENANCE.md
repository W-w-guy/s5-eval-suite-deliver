# DATA_PROVENANCE — 数据来源与可复核性

本交付包**不含任何真实个人信息或企业信息**。全部示例数据由脚本生成，可完整重放。

| 项 | 值 |
| --- | --- |
| 生成脚本 | `pkg/engine.py`（示例定义与业务规则）+ `tools/gen.py`（写出 docs/） |
| 生成脚本 sha256 | `b8a29eed475ac86c7e45ceb463eb7a0a8bf4e884df9b7426c6b4ff4ee6d3b6a1` |
| 渲染脚本 sha256 | `08a59cb834942c0b5e70fd1b8dce3f3bec1ced76b173c02a666bac113d844140` |
| 随机性 | **无随机**。规则、示例与时间为手写固定常量；响应截止由纯 naive datetime 推算（不依赖系统 tzdata）；同一脚本在任何机器重跑产出字节级一致（已在 Windows 与 Ubuntu 两侧核对 sha256） |
| 种子 | 不适用（无随机数生成器） |
| 重跑命令 | `python tools/gen.py` |
| 产出规模 | 6 条转接规则 / 8 个响应时限示例 / 8 类情形 / 流程图 11 节点 12 条带条件边 / 知识缺口 7 字段 / CSV 8 行 14 列 |
| PII 扫描 | `python tools/pii_scan.py` → `scanned=31 hits=0`（手机号 / 邮箱 / 身份证 / 银行卡 四类正则） |

## 虚构声明

岗位、时段、时限与条款均为虚构；示例中不含会员姓名、手机号与真实企业信息。
