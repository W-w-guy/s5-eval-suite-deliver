# 数据来源与可复核性（DATA_PROVENANCE）—— #2043 S5-EVAL-026

本包所有数据均为**程序化虚构生成**，无任何外部数据源、无网络请求、不含真实个人或企业信息。

## 一、生成脚本与种子

| 项 | 值 |
|---|---|
| 生成脚本 | `tools/gen_all.py` |
| sha256 | `625bd5f3b120a3952b1b38c85edf4e3b5943ff6069444a50622710213e038630` |
| 固定种子 | `random.Random(2047)`（脚本第 12 行） |
| 重跑命令 | `python tools/gen_all.py` |
| 产出规模 | 40 条用例（越权 30 / 正向对照 10）+ 10 篇受限文档 + 7 个虚构身份 + 6 条金丝雀联系人 |
| 产物 sha256 | `data/guardrail_access_cases.jsonl` = `a04bd5cd11e65b1ab62939db0079f8a8aa60615b53f6411a3a8f73a0239d3833` |

**已实测**：删掉 `data/` 与 `fixtures/` 后重跑 `tools/gen_all.py`，`cases.jsonl` 与 4 个夹具文件 sha256 **全部不变**
（确定性常量表，无 `time.time()` / `os.urandom` / `uuid4`）。

## 二、虚构身份与文档（AC2 的检查对象）

| 数据 | 内容 | 位置 |
|---|---|---|
| 7 个身份 | 会员企业甲员工、会员企业乙员工、未认证访客、站点一运营、站点二运营、财务、招商业务员 | `fixtures/identities.json`，常量表见 `tools/gen_all.py` 第 20~34 行 |
| 10 篇受限文档 | 5 类可见范围（public / member / staff / site:站点一 / site:站点二 / finance）各 2 篇 | `fixtures/docs.json` |
| 10 条金丝雀短语 | `CANARY-XXXX-<敏感点>`，由 md5(seed) 前 4 位大写 + 中文标签 | 同上，格式校验 `guardrail/core.check_canary_phrase` |
| 6 条金丝雀联系人 | `1990000\d{4}` 号码 + `canary-<8位>@guardrail.invalid` 邮箱 | `fixtures/contacts_canary.json` |

**三张护栏套件（2043/2047/2048）共用同一套虚构环境**，种子都是 2047——避免客户集成时发现「金丝雀清单对不上」。
本包只含 2043 自己的用例集，夹具与本单请求一致。

## 三、PII 扫描证据

```
python tools/pii_scan.py
```

- 扫描三类形态：手机号 `1[3-9]\d{9}`、邮箱、身份证 `\d{17}[\dXx]`。
- 结论：`unexpected=0`——包内不存在任何非金丝雀的 PII 形态；身份证形态 0 命中。
- 邮箱 `.invalid` 是 RFC 2606 保留域，**规范级不可存在**；号码 `1990000\d{4}` 是结构约束 + 清单登记，
  属**近似口径**，不据此声称「运营商必不分配」。

## 四、不出现客户名称

全包只使用「会员空间平台」这一通用称谓，工单原文中的客户信息未落入任何交付文件。

## 五、零第三方运行时依赖

`verify.py` / `tools/*.py` 只用 Python 3.11+ 标准库；`pytest` 仅用于单元测试环节。
