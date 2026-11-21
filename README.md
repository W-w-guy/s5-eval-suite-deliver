# S5 评测套件交付 · 5 单

会员空间平台 Stage V「评测、红队与质量月报」模块的 5 个评测套件交付件。

**所有数据均为虚构**：企业、资源、嘉宾、访谈转写稿、知识库政策与常见问题全部原创编写，
不含任何真实个人或企业信息。每个包内都有 `eval-pii-scan`（手机号/邮箱/身份证形态）自检，全部 0 命中。
每单另有 `DATA_PROVENANCE.md` 写明生成脚本、种子、重跑命令与扫描证据。

## 一、为什么每单有 `files/` 明文目录

平台复核只读文本、**不执行代码**（`runtime_verified: false`），也解不开 zip。
所以每单同时提供两种形态：

| 形态 | 用途 |
|---|---|
| `<单号>_.../<pkg>_deliver.zip` | 完整交付件，含全部夹具，买家下载后一条命令复跑 |
| `<单号>_.../files/**` | **同样的内容摊成明文**，让复核方直接读到 `cases.jsonl`、`verify_*.py`、报告原文、`ACCEPTANCE.md` |

`files/ACCEPTANCE.md` 是逐条验收对照表：**每条 AC = 判定方式 + 复核命令 + 实际输出原文**。

## 二、索引

| 目录 | 工单 | 交付件 zip | 条目 | 大小 | sha256(前16) | 明文文件数 |
|---|---|---|---|---|---|---|
| `1989_eval004/` | S5-EVAL-004 | `eval1989_deliver.zip` | 23 | 41,743 B | `fcae3fdf699bba57` | 19 |
| `2008_eval012/` | S5-EVAL-012 | `match2008_deliver.zip` | 54 | 51,998 B | `52402160f4fe8b8e` | 18 |
| `2017_eval015/` | S5-EVAL-015 | `ip2017_deliver.zip` | 53 | 84,969 B | `71a0e83caaaaf598` | 35 |
| `2033_eval022/` | S5-EVAL-022 | `kqa2033_deliver.zip` | 147 | 170,180 B | `56234e960b102d95` | 21 |
| `2037_eval023/` | S5-EVAL-023 | `mt2037_deliver.zip` | 145 | 132,907 B | `0d3198c70a51374a` | 23 |

根目录 `SHA256SUMS.txt` 覆盖仓库内每个文件，可逐个校验。

## 三、不跑代码也能核对的关键数字（全部可在 raw 直接读到）

| 单 | 用法 | 直接可数的证据 |
|---|---|---|
| 1989 | `files/data/consistency_30.jsonl` | 30 条一致性样本（kw 11 / sem 15 / ex 4），每条含 `human` 与 `points` |
| 2008 | `files/data/cases.jsonl` | 35 行，分布 normal 20 / trap 9 / none 6 |
| 2017 | `files/data/cases.jsonl` | 30 行，outline 12 / summary 18；`files/data/transcripts/` 18 份转写稿 |
| 2033 | `files/data/cases.jsonl` | 50 行，single_doc 20 / multi_doc 12 / numeric_date 10 / paraphrase 8 |
| 2037 | `files/data/cases.jsonl` | 30 组，每组 4 轮；coref 8 / condition_change 8 / correction 8 / topic_switch 6 |
| 2037 | `files/data/kb_index.jsonl` | 120 篇知识文档的 doc_id / 标题 / 字符数 / sha256 逐行可读 |

## 四、复跑方式（解压 zip 或直接用 files/ 目录）

```bash
python verify_<单号>.py          # 逐条 AC 断言，末行 TOTAL n, PASS n, FAIL 0
python verify_<单号>.py --self-test   # 反向自测：改坏断言必须失败
python -m pytest tests -q        # 单元测试
python tools/provenance.py check --dir .   # 数据来源声明校验（15~16 项）
```

Python 3.11+，零第三方运行时依赖（pytest 仅跑单测需要）。

## 五、数据来源

五单全部**虚构合成，无任何外部来源**：不使用公开数据集、不抓取网页、不使用客户数据。
生成脚本路径与 sha256、随机种子、重跑命令、产出规模、pii 扫描数与命中数，
逐单写在各自的 `DATA_PROVENANCE.md`；校验器带变异自测（改坏哈希 / 写模糊来源 /
删否定断言 / 局限写「无」都必须被抓到）：

```bash
python tools/provenance.py --selftest
```
