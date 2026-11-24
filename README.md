# S5 评测套件交付 · 8 单

会员空间平台 Stage V「评测、红队与质量月报」模块的 8 个评测套件交付件。

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
| `2022_eval017/` | S5-EVAL-017 | `triage2022_deliver.zip` | 50 | 108,657 B | `6250140e9bb006fe` | 55 |
| `2043_eval026/` | S5-EVAL-026 | `guard2043_deliver.zip` | 25 | 59,699 B | `821fefbf5cd53629` | 25 |
| `2047_eval027/` | S5-EVAL-027 | `guard2047_deliver.zip` | 25 | 68,584 B | `46a19bdd0460d83b` | 25 |

根目录 `SHA256SUMS.txt` 覆盖仓库内每个文件，可逐个校验。

## 三、不跑代码也能核对的关键数字（全部可在 raw 直接读到）

| 单 | 用法 | 直接可数的证据 |
|---|---|---|
| 1989 | `files/data/consistency_30.jsonl` | 30 条一致性样本（kw 11 / sem 15 / ex 4），每条含 `human` 与 `points` |
| 2008 | `files/data/cases.jsonl` | 35 行，分布 normal 20 / trap 9 / none 6 |
| 2017 | `files/data/cases.jsonl` | 30 行，outline 12 / summary 18；`files/data/transcripts/` 18 份转写稿 |
| 2033 | `files/data/cases.jsonl` | 50 行，single_doc 20 / multi_doc 12 / numeric_date 10 / paraphrase 8 |
| 2037 | `files/data/cases.jsonl` | 30 组，每组 4 轮；coref 8 / condition_change 8 / correction 8 / topic_switch 6 |
| 2022 | `files/data/cases.jsonl` | 35 行，normal 20 / high_similarity 10 / irrelevant 5；`files/contexts/` 35 份，每份 8~20 篇资讯 |
| 2043 | `files/data/guardrail_access_cases.jsonl` | 40 行；越权 30（`_allowed=false`）/ 正向对照 10（`_allowed=true`）；`files/fixtures/docs.json` 10 篇文档金丝雀 |
| 2047 | `files/data/guardrail_leakage_cases.jsonl` | 45 行；6 类手法各 ≥6；`files/fixtures/contacts_canary.json` 6 条金丝雀（1990000 段 + .invalid） |
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

## 六、关于 CI 配置（两处位置，用途不同）

仓库里有两份 `intel-eval.yml`，**用途不同，别混用**：

| 位置 | 用于 | 说明 |
|---|---|---|
| `2264_intel034/files/.github/workflows/intel-eval.yml` | 交给买家 | 假定**包内文件已铺到买家仓库根目录**，无需 `working-directory`；随 zip 一起交付，属交付件本体 |
| `.github/workflows/intel-eval.yml`（本仓根目录） | 本仓自证 | 本仓把交付件放在子目录 `2264_intel034/files/`，故多一行 `defaults.run.working-directory`；仅用于在本仓跑出绿勾 |

**为什么要放根目录**：GitHub 只识别仓库根目录的 `.github/workflows/`。
放在 `2264_intel034/files/.github/workflows/` 下，GitHub 不会执行，等于「配置存在但从不运行」。

### 两份文件的差别（逐处列全，共 4 处）

| # | 差异 | 根目录那份 | 包内那份（给买家） | 原因 |
|---|---|---|---|---|
| 1 | 文件头注释块 | 有（17 行，说明用途与差异） | 无 | 纯说明，不影响运行 |
| 2 | `defaults.run.working-directory` | `2264_intel034/files` | 无 | 本仓交付件在子目录，必须指过去 |
| 3 | 「上传报告」的 `path` | `2264_intel034/files/reports/` | `reports/` | 同 (2)，子目录前缀差异 |
| 4 | 「上传报告」的 `continue-on-error` | 无 | `true` | 包内那份给买家：基础设施抖动不把回归判红；根目录那份用于自证，上传失败就该变红以暴露真实问题 |

另有排版差异：根目录那份在 `name` 之后、`defaults` 区块之后各多一个空行，包内那份没有，不影响运行。

**评测一步的提示词版本两份现在一致**，都是 `v2`（`intel_eval/extract.py` 的 `PROMPT_SETS` 中存在的键）。
该处根目录那份曾误写为不存在的 `ci`，会使评测一步每次都因 `ValueError` 退出、与评测结果好坏无关；
已于 #2264 第二轮返工（rework-r2）修正为 `v2`，与包内那份对齐。复核方式：

```bash
grep -n "prompt-set" .github/workflows/intel-eval.yml 2264_intel034/files/.github/workflows/intel-eval.yml
# 两行都应是 --prompt-set v2
grep -n '"ci"' 2264_intel034/files/intel_eval/extract.py   # 应无输出（PROMPT_SETS 里没有 ci 这个键）
```

### 根目录那份的实际跑通记录

见 `CI_RUN_ROOT_WORKFLOW.md`（本地按该文件步骤逐条执行的完整输出，
含「门槛达标 → 评测一步 rc=0」与 AC3 反例「人为让 robots 禁止路径被抓取 → rc=1」两段）。

**如何迁到买家仓库**：把 `2264_intel034/files/` 下的内容铺到买家仓库根目录，
`intel-eval.yml` 会自动落在 `.github/workflows/`，无需改动；再按需配置
`APP_ENV=test`（CI 属测试环境）即可。数据不出网由 `INTEL_TEST_RESOLVER` fail-closed 保证，
不依赖 GitHub 托管 runner 的位置。

> 注：zip 与 `2264_intel034/` 目录仍逐字节一致；根目录这份 `.github/` 与 `CI_RUN_ROOT_WORKFLOW.md` 是追加物，不属于交付件本体。
