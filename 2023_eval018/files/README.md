# S5-EVAL-018 文档自动化评测集 doc_auto.contract_fields

40 份**虚构**合同（生成 28 + 疑难 12）+ 每份 15 个字段的标准答案 + 两项指标脚本
（字段级准确率、**错字段标红召回**）+ 分布统计表 + 报告与「错而未标红」明细截图。

## 一、目录

```
suite_2023.yaml              套件定义（阈值、口径、破坏开关）
data/cases.jsonl             40 条用例：layout / carrier / gold 15 字段 / critical_fields / meta.difficulty
data/contracts/              40 份真实载体文件：14 个 text_pdf、13 个 scanned_pdf、13 个 docx
data/plain/                  40 份合同正文的纯文本（扫描件无文字层，OCR 桩读这里；也是 pii 扫描源）
doc_eval/metrics.py          字段准确率 / 标红召回（含字段值归一）
doc_eval/__main__.py         runner：载体读取 -> 抽取 -> 自检标红 -> 指标 -> 报告
tools/gen_contracts.py       合同与标准答案生成器（同源、确定性）
tools/render_carriers.py     text_pdf / scanned_pdf / docx 三种载体的渲染器
tools/eval_lint.py           结构校验（条数、分布、15 字段、代码格式、载体一致性）
tools/eval_pii_scan.py       个人信息扫描（手机号/邮箱/身份证/银行卡）
tools/make_distribution.py   分布统计表 -> dist/
tools/make_screenshot.py     报告截图 -> reports/*.png（由 json 渲染，非手绘）
tools/mutate.py              变异自检（改坏 10 处，每处都必须让 verify 变红）
tests/                       20 个 pytest
verify_2023.py               4 条 AC 的 26 项断言
dist/                        分布统计表（csv + md）
reports/                     报告 json/md + 截图 png
verify_logs/                 Windows 与 Ubuntu 的实跑日志
```

## 二、怎么跑

```bash
# 依赖：Python 3.11+ / pypdf / Pillow（仅生成与读 PDF 文字层用；runner 对 docx 零依赖）
pip install pypdf Pillow

python -m doc_eval                       # 全达标 rc=0
python -m doc_eval --break-flag          # 关掉自检标红 -> 召回掉、critical 未标红 3 个、rc=1
python -m doc_eval --break-accuracy      # 日期解析错 -> 9 个错而未标红 critical、rc=1
python tools/eval_lint.py                # 结构校验
python tools/eval_pii_scan.py            # 个人信息扫描
python -m pytest tests -q                # 20 项
python verify_2023.py                    # 26 项 AC 断言
python tools/mutate.py                   # 变异自检（约 5 分钟）
python tools/gen_contracts.py            # 重新生成 40 份合同与 cases.jsonl
```

## 三、实测（Windows 11 / Py3.11.7 与 Ubuntu 24.04 / Py3.12.3 一致）

| 指标 | 实测 | 门槛 | 判定 |
|---|---|---|---|
| 字段级准确率 | **0.9900**（594/600 字段次） | ≥0.90 | 通过 |
| 错字段标红召回 | **0.9750** | ≥0.95 | 通过 |
| 错而未标红的 critical 字段 | **0** | 0 | 通过 |
| 识别正确却被标红（误报） | 0 | — | — |

两个破坏开关都能让门槛失败，说明指标可证伪：

| 开关 | 结果 |
|---|---|
| `--break-flag` | 召回 0.9750→**0.9000**、critical 未标红 0→**3**、rc=1 |
| `--break-accuracy` | 准确率 0.9900→**0.9750**、召回→**0.7625**、critical 未标红 0→**9**、rc=1 |

## 四、口径写死在代码里的四件事

**1. 标红召回的分母是「识别错误的字段数」，不是「全部字段数」。**
口径在 `metrics.flag_recall()` 里；识别正确却被标红的，单独记 `right_but_flagged`，
**不进召回分母**（否则误报会伪装成召回高）。

**2. 没有识别错误时召回记 1.0，这是显式约定。**
空集不扣分，写进 `tests/test_metrics.py`，避免以后被人改成 0。

**3. critical 字段固定为 6 个：含税金额、不含税金额、甲乙方统一社会信用代码、服务起止日。**
`eval_lint` 与 `verify_2023.py` 都逐条比对这个清单，不是「至少包含」而是「必须等于」。

**4. 标准答案严格 15 个字段。**
难度说明放在 case 级 `meta.difficulty`，**不放进 gold**——gold 多一个内部键就判失败。

## 五、载体是真实文件，不是改后缀

- `text_pdf`：手写 PDF，Type0/Identity-H + 子集嵌入 TrueType + ToUnicode，
  `pypdf` 能提取出中文原文（verify 断言 `contract_no` 出现在文字层里）。
- `scanned_pdf`：Pillow 把正文画成 150dpi 位图再存 PDF，**无文字层**
  （verify 断言 `extract_text()` 为空）；倾斜类疑难点真的旋转 7 度。
- `docx`：纯 stdlib `zipfile` 写 OOXML（无 python-docx 依赖），
  `word/document.xml` 里的中文可取。

## 六、已知局限（如实写）

1. **被测工具是 echo mock**（正则抽取 + 保守自检），不是真实 OCR/LLM 抽取。
   它证明的是判定链路、指标口径、门槛与可证伪性有效，不代表真实系统的绝对水平。
2. **扫描件的 OCR 不在本评测集范围内**：`scanned_pdf` 走 OCR 桩，读 `data/plain/`
   的同源文本（与位图内容逐字一致）。接入真实 OCR 后应把桩替换成 OCR 输出，
   其余环节不变。
3. **重新生成的跨平台差异**：`gen_contracts.py` 在同一台机器上幂等（连跑两次
   83 个文件逐字节相同，Windows 与 Ubuntu 各自验证过）；**跨平台因系统字体不同，
   PDF 内嵌字体字节不同**，因此 PDF 的 sha256 在两侧不同。`cases.jsonl` 与
   `data/plain/` 的 sha256 两侧完全一致（已实测）。交付包内附的是 Windows 侧生成的
   那份固定产物，买家不需要重新生成数据即可直接评分。
4. **40 份只够验证链路与门槛**，不够估置信区间；样本最少的字段只有 40 次机会。
