# 数据来源与可复核性 · doc_auto.contract_fields

本评测集 **不含任何真实企业或个人数据**。下面把「每一条数据从哪来、怎么复核、
种子是多少、重跑是哪条命令」全部写死，任何人都可以独立重算并比对。

## 一、一句话结论

40 份合同全部由仓库内 `tools/gen_contracts.py` 生成（种子固定 `random.Random(2023)`），
合同正文、15 字段标准答案、critical 字段清单三者同源同一份代码产出；
统一社会信用代码第 3–8 位固定 `999999`（不存在的行政区划码），因此不可能对应任何真实企业。

## 二、生成脚本与种子

| 项 | 值 |
|---|---|
| 生成脚本 | `tools/gen_contracts.py` |
| 载体渲染脚本 | `tools/render_carriers.py` |
| 随机种子 | `random.Random(2023)`（唯一随机源） |
| 信用代码派生 | `hashlib.sha256(seed)` 取前 16 位十六进制 → 后 10 位数字，**不用内置 hash()**（避免 PYTHONHASHSEED 造成跨进程不一致） |
| 重跑命令 | `python tools/gen_contracts.py` |
| 产出规模 | 40 份载体文件 + `data/cases.jsonl` + `data/plain/*.txt`，共 83 个文件 |
| 幂等性 | 同一台机器连跑两次，83 个文件 sha256 **逐字节相同**（Windows 与 Ubuntu 各自实测） |

早期版本曾用内置 `hash()` 生成信用代码，导致同一份脚本在不同进程里产出不同代码；
已改为 sha256 派生，并在 `eval-lint` 里校验格式。

## 三、40 份的构成（可逐条核对）

| 维度 | 取值 | 数量 |
|---|---|---|
| 类型 | generated（生成）/ difficult（疑难） | 28 / 12 |
| 版式 | standard / two_column / table_heavy / minimal | 各 10 |
| 载体 | text_pdf / scanned_pdf / docx | 14 / 13 / 13 |
| 疑难类型 | 盖章压字、跨页付款表、同一合同多个金额、补充协议覆盖原条款、日期写法混用、手机拍照倾斜、表格合并单元格、手写批注改金额、多处小写金额不一致、甲乙方名称简称混用、跨页续表的合计行、税率同时出现两种 | 各 1 |

每份疑难的难点说明写在 `cases.jsonl` 的 `meta.difficulty.{name,desc,tag}`，
**不放进 gold**（gold 严格 15 字段，多一个内部键 `eval-lint` 就判失败）。

## 四、载体是真实文件（可自己验）

| carrier | 怎么做的 | 怎么复核 |
|---|---|---|
| text_pdf | 手写 PDF：Type0 / Identity-H + 子集嵌入 TrueType + ToUnicode CMap | `python -c "import pypdf;print(pypdf.PdfReader('data/contracts/CT-001.pdf').pages[0].extract_text())"` 能打出中文原文 |
| scanned_pdf | Pillow 把正文渲染成 150dpi 位图再存 PDF，无文字层；倾斜类真旋转 7° | 同一条命令 `extract_text()` 返回空串 |
| docx | 纯 stdlib `zipfile` 写 OOXML（固定时间戳与 create_system，保证字节可复现） | `zipfile.ZipFile(p).read('word/document.xml')` 含中文 |

`verify_2023.py` 对 40 份逐个断言上述性质（这就是「格式与 carrier 声明一致」那一条）。

## 五、PII 扫描

| 项 | 值 |
|---|---|
| 脚本 | `tools/eval_pii_scan.py` |
| 扫描对象 | `data/cases.jsonl` + `data/plain/*.txt` + 40 份载体文件（docx 解 XML、PDF 只扫文字层）= 83 个文件 |
| 规则 | 手机号 / 邮箱 / 身份证 / 银行卡 |
| 实测 | `files=83 unexpected_hits=0 exempt_999999=432` |
| 为什么 PDF 只扫文字层 | 直接扫 PDF 原始字节会把字形编号误判成卡号（早期实测 110 条假阳性） |
| 为什么有 432 条 exempt | 80 个信用代码 × 多次出现，均因第 3–8 位 999999 而被认定为虚构码，单列不计数 |

## 六、诚实说明的三处局限

1. 被测工具是 **echo mock**，不是真实 OCR/LLM；它证明的是判定链路与指标口径有效。
2. `scanned_pdf` 走 **OCR 桩**，读 `data/plain/` 的同源文本（与位图逐字一致）；
   接入真实 OCR 后替换桩即可，其余不变。
3. **跨平台重新生成时 PDF 字节不同**：Windows 用 simhei、Ubuntu 用 uming，
   嵌入的子集字体不同 → PDF 的 sha256 不同。`data/cases.jsonl` 与 `data/plain/`
   两侧 sha256 完全一致（已实测：`d7f95076…` / `93fa87fe…`）。
   包内附的是 Windows 侧生成的固定产物，买家**无需重新生成**即可直接评分。

## 七、数据与保密三条的落实情况

| 工单要求 | 落实方式 | 核验方式 |
|---|---|---|
| 只用虚构测试数据，不得使用真实个人信息或企业信息 | 全部由种子化生成器产出；甲乙方名为「示例会员企业X有限公司」「示例X服务有限公司」 | `python tools/eval_pii_scan.py`（unexpected_hits=0）+ 第三节构成表 |
| 交付物中不出现客户名称 | 交付件正文统一标题为「服务合同（虚构样例）」；甲乙方均为「示例…有限公司」，未出现委托方名称，也未出现其系统名 | `python tools/eval_pii_scan.py` 内置「客户名称」规则（命中即 rc=1），实测 unexpected_hits=0；另可直接 `grep -ri "会员空" data/ reports/` 应无命中 |
| 本单信息仅用于完成本单 | 交付物内不含工单号以外的项目背景描述；README 只讲本评测集 | 通读 README.md / ACCEPTANCE.md |
