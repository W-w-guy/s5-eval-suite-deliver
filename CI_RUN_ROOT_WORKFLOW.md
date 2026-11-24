# 根目录 CI 工作流的实际跑通记录

对应 #2264 第二轮返工要求 B：「附一次根目录这份工作流实际跑通的记录，
要能看出评测一步是因门槛达标而通过的」。

本记录为**按 `.github/workflows/intel-eval.yml` 的步骤在本地逐条执行**的完整输出
（对方给出的两种形式之一）。执行目录 = 该工作流 `working-directory` 指定的
`2264_intel034/files`，环境变量含该工作流声明的 `APP_ENV=test`。

## 一、执行环境

| 项 | 值 |
|---|---|
| 源码 | 交付仓 commit `9da6490` 的干净导出（`git ls-files` 全量复制，非原地目录） |
| Windows | Python 3.11.7 |
| Ubuntu | Python 3.12.3（VM，`ubuntu-latest` 同为 3.12） |
| 工作目录 | `2264_intel034/files`（与工作流 `defaults.run.working-directory` 一致） |
| 环境变量 | `APP_ENV=test`（与工作流 `env:` 一致） |

## 二、步骤与退出码（与工作流逐条对应）

| # | 工作流步骤 | 命令 | Windows rc | Ubuntu rc |
|---|---|---|---|---|
| 1 | `actions/checkout@v4` | 干净导出源码 | — | — |
| 2 | `actions/setup-python@v5` | 3.12 | 本机 3.11.7 | 3.12.3 |
| 3 | 单元测试（含每指标 >=2 手算用例） | `python -m pytest tests -q` | **0** | **0** |
| 4 | 评测（任一门槛不达标则本步失败） | `python -m intel_eval run --prompt-set v2` | **0** | **0** |
| 5 | 自检 | `python verify_2264.py` | **0** | **0** |
| 6 | 上传报告 | `upload-artifact@v4` | 见第八节 | — |

评测一步用的是 `--prompt-set v2`，即 `intel_eval/extract.py` 的 `PROMPT_SETS` 中**存在**的键，
与包内那份 `.github/workflows/intel-eval.yml` 完全一致（返工前根目录那份误写为不存在的 `ci`）。

## 三、步骤 3：单元测试（Windows，rc=0）

```
........................................................................ [ 91%]
.......                                                                  [100%]
```

Ubuntu：`python3 -m pytest tests -q` → 末尾 `.......  [100%]`，`RC_PYTEST=0`。

## 四、步骤 4：评测（Windows，rc=0）—— 门槛达标的关键证据

```
prompt_set=v2 entries=11 dropped=1 queued=0 crawl=discovered
  body_similarity          1.0        OK
  publish_date_accuracy    1.0        OK
  group_f1                 1.0        OK
  merge_errors             0          OK
  policy_type_accuracy     1.0        OK
  deadline_accuracy        1.0        OK
  key_fact_coverage        1.0        OK
  numeric_flagged_ratio    1.0        OK
  no_link_into_queue       0          OK
  robots_violations        0          OK
  urls_in_summary          0          OK
  pii_residue              0          OK
report=E:\Python\Agent_1\work\clawhunt\_ciroot_r2_1795498323\2264_intel034\files\reports\intel_v2.md
THRESHOLD OK
```

**如何看出「因门槛达标而通过」**：输出逐项列出 11 项指标及 `OK/FAIL` 判定，
最后一行 `THRESHOLD OK` 才返回 0。任何一项不达标会打印 `THRESHOLD NOT MET: <项名>` 并返回 1
（下一节给出该反例的实测）。因此 rc=0 不等于「跑完了」，而是「11 项门槛全部达标」。

Ubuntu 同一命令输出完全一致（指标值、`THRESHOLD OK`、`RC_EVAL=0`）：

```
prompt_set=v2 entries=11 dropped=1 queued=0 crawl=discovered
  body_similarity          1.0        OK
  publish_date_accuracy    1.0        OK
  group_f1                 1.0        OK
  merge_errors             0          OK
  policy_type_accuracy     1.0        OK
  deadline_accuracy        1.0        OK
  key_fact_coverage        1.0        OK
  numeric_flagged_ratio    1.0        OK
  no_link_into_queue       0          OK
  robots_violations        0          OK
  urls_in_summary          0          OK
  pii_residue              0          OK
report=/home/a/ciroot_r2/2264_intel034/files/reports/intel_v2.md
THRESHOLD OK
RC_EVAL=0
```

## 五、步骤 5：自检（Windows，rc=0）

```
[ OK ] AC1 run 退出码 0（门槛全过） | rc=0
[ OK ] AC1 生成 Markdown 报告 
[ OK ] AC1 生成 JSON 报告 
[ OK ] AC1 JSON 里 11 项指标齐全（含归组 F1 的误合并约束） 
[ OK ] AC1 Markdown 报告标题含「11 项指标」 
[ OK ] AC1 Markdown 表格确实是 11 行指标 | 11
[ OK ] AC1 报告标注「正文提取平均相似度」 
[ OK ] AC1 报告标注「发布日期准确率」 
[ OK ] AC1 报告标注「转载归组 F1」 
[ OK ] AC1 报告标注「policy_type 准确率」 
[ OK ] AC1 报告标注「截止日期准确率」 
[ OK ] AC1 报告标注「摘要关键事实覆盖率」 
[ OK ] AC1 报告标注「不一致数字/日期被标出比例」 
[ OK ] AC1 报告标注「无原文链接进入核对队列数」 
[ OK ] AC1 报告标注「robots 禁止路径被抓取数」 
[ OK ] AC1 报告标注「摘要含 URL 数」 
[ OK ] AC1 报告标注「送模型文本联系方式残留」 
[ OK ] AC1 报告同时给出归组误合并数 
[ OK ] AC1 报告注明样例全部虚构 
[ OK ] AC1 报告写明 AI 输出进复核队列、不对外发送 
[ OK ] AC1 基线 11 项门槛全部达标 
[ OK ] AC2 生产环境设置解析覆盖时直接抛错（fail-closed） 
[ OK ] AC2 CLI 在生产+覆盖时退出码 3 且打印 REFUSE TO START | 3
[ OK ] AC2 拒绝启动时不产出报告 
[ OK ] AC2 有对应测试且通过 | ['..................                                                       [100%]']
[ OK ] AC3 违反 robots 时退出码非 0 | 1
[ OK ] AC3 输出点名「robots 禁止路径被抓取数」 
[ OK ] AC3 报告里 robots_violations >= 1 | 2
[ OK ] AC3 正常运行时 robots_violations == 0 
[ OK ] AC3 有对应测试且通过 
[ OK ] AC4 11 个指标都有对应用例 | ['test_m01', 'test_m02', 'test_m03', 'test_m04', 'test_m05', 'test_m06', 'test_m07', 'test_m08', 'test_m09', 'test_m10', 'test_m11']
[ OK ] AC4 每个指标至少 2 个手算用例 
[ OK ] AC4 手算用例总数 >= 22 | 47
[ OK ] AC4 全部单元测试通过 | .......                                                     

TOTAL 34, PASS 34, FAIL 0
```

Ubuntu：`TOTAL 34, PASS 34, FAIL 0`，`RC_VERIFY=0`。

## 六、AC3 反例：人为让 robots 禁止路径被抓取 → 退出码非 0

订单验收 3 要求「人为让一个 robots 禁止路径被抓取后 CI 任务退出码非 0」。
若只给一张 rc=0 的绿图，无法证明门槛真的会拦；所以这里给出**注入侧**的实测：

```
$ APP_ENV=test python -m intel_eval run --prompt-set ci_bad --ignore-robots
prompt_set=ci_bad entries=11 dropped=1 queued=0 crawl=discovered
  body_similarity          1.0        OK
  publish_date_accuracy    1.0        OK
  group_f1                 1.0        OK
  merge_errors             0          OK
  policy_type_accuracy     1.0        OK
  deadline_accuracy        1.0        OK
  key_fact_coverage        1.0        OK
  numeric_flagged_ratio    1.0        OK
  no_link_into_queue       0          OK
  robots_violations        2          FAIL
  urls_in_summary          0          OK
  pii_residue              0          OK
report=E:\Python\Agent_1\work\clawhunt\_ciroot_r2_1795498323\2264_intel034\files\reports\intel_ci_bad.md
THRESHOLD NOT MET: robots 禁止路径被抓取数
```

Windows rc=**1**，Ubuntu rc=**1**（`RC_BAD=1`）。两平台都是
`robots_violations 2 FAIL` → `THRESHOLD NOT MET: robots 禁止路径被抓取数` → 退出码 1。
即「评测一步会让 CI 变红」这件事在本工作流里是可被触发的，不是恒绿。

## 七、跨平台产物一致性（同一份 v2 报告两平台逐字节相同）

| 文件 | 大小 | sha256（Windows） | sha256（Ubuntu） |
|---|---|---|---|
| `reports/intel_v2.md` | 1724 B | `8d2e33e454d9bc84301df31cc95abed7dc1ef94391642398ddef0cc130544e6a` | 同左 |
| `reports/intel_v2.json` | 1092 B | `d79548ee8071fa6016b2556556aadb8b4c1ed3e1932f5e5029b45c9add374a21` | 同左 |

且两者都与仓内已提交的 `reports/intel_v2.*` 哈希相同（`git show HEAD:...` 实测），
说明重跑是确定性复现，不是覆盖出另一份内容。

## 八、为什么这份记录是「本地按步骤执行」而不是 Actions 运行链接

本轮改动（把根目录工作流的评测一步由 `ci` 改为 `v2`，并补全两份文件的差异说明）
**尚未推送到交付仓**，因此暂无对应的 Actions 运行记录。推上去之后可补一条
`workflow_dispatch` 运行链接作为等价凭证；GitHub 侧只需 `actions:read` 权限即可取到。
在此之前，本文件作为「照其步骤在本地运行的完整输出」提交，两种形式对方均已声明可接受。

补充一处与 CI 平台相关的已知差异：包内那份在「上传报告」一步带 `continue-on-error: true`，
根目录这份**没有**这一行——即本仓自证时若上传 artifact 因网络抖动失败，本次运行会变红。
这是刻意保留的，便于在自证时暴露真实问题；不影响评测一步的门槛判定。

## 九、复跑命令（照抄即可）

```bash
cd <仓库根>/2264_intel034/files        # 对应工作流的 working-directory
export APP_ENV=test                    # 对应工作流的 env
python -m pytest tests -q              # 期望 rc=0
python -m intel_eval run --prompt-set v2   # 期望 rc=0 且打印 THRESHOLD OK
python verify_2264.py                  # 期望 TOTAL 34, PASS 34, FAIL 0

# AC3 反例（应失败）
python -m intel_eval run --prompt-set ci_bad --ignore-robots   # 期望 rc=1
```


## 十、旁证：命令不是我手抄的，是直接从这份 YAML 解析出来执行的

上面各节是人工按步骤敲的。为排除「抄错命令」的可能，另做了一次 **YAML 自解析执行**：
用 `yaml.safe_load` 读入本文件，取 `defaults.run.working-directory` 作为工作目录、
取 `jobs.eval.env` 作为环境变量，再把每个 `steps[].run` 原样执行（`uses:` 步骤跳过）。

解析结果与执行结果：

```
defaults.run.working-directory = 2264_intel034/files
jobs.eval.env                  = {'APP_ENV': 'test'}

SKIP(uses: actions/checkout@v4)      | actions/checkout@v4
SKIP(uses: actions/setup-python@v5)  | actions/setup-python@v5
rc=0                                 | 单元测试（含每指标 >=2 手算用例）
rc=0                                 | 评测（任一门槛不达标则本步失败，PR 被拦截）
rc=0                                 | 自检
SKIP(uses: actions/upload-artifact@v4) | 上传报告
```

其中「评测」一步由 YAML 读出的命令原样执行，输出与第四节一致：

```
prompt_set=v2 entries=11 dropped=1 queued=0 crawl=discovered
  body_similarity          1.0        OK
  publish_date_accuracy    1.0        OK
  group_f1                 1.0        OK
  merge_errors             0          OK
  policy_type_accuracy     1.0        OK
  deadline_accuracy        1.0        OK
  key_fact_coverage        1.0        OK
  numeric_flagged_ratio    1.0        OK
  no_link_into_queue       0          OK
  robots_violations        0          OK
  urls_in_summary          0          OK
  pii_residue              0          OK
THRESHOLD OK
```

即：**这份工作流文件里的命令本身就能跑完，评测一步因 11 项门槛全部达标而 rc=0。**


## 十一、随附的原始日志（两平台各一份，均为逐字节原文件）

| 文件 | 大小 | sha256 | 内容 |
|---|---|---|---|
| `CI_logs_root_workflow/WINDOWS_steps.log` | 4,024 B | `7528bd13c92f3e1d77e3311f2324ffbdd832fa6fa4c71ac3aea759f36fa19649` | Windows 侧四步原始输出（含各步 rc） |
| `CI_logs_root_workflow/UBUNTU_steps.log` | 3,789 B | `d2c59e5df0778031c5544ad831a6e5e368ca39a4c1e994370d73743af8889c7e` | Ubuntu 侧四步原始输出（含各步 rc） |

两份都是运行时就地生成的原文件，未做任何内容改动：
Windows 那份只把 CRLF 统一为 LF（原文件是 CRLF，统一后行数与内容不变）；
Ubuntu 那份本来就是 LF，逐字节原样。

**校验方式**（买家可自查两平台日志是否与本文一致）：

```bash
sha256sum CI_logs_root_workflow/*.log
# 应为上表两个值
wc -c CI_logs_root_workflow/*.log
# 4024 / 3789
grep -c "^===== rc=" CI_logs_root_workflow/UBUNTU_steps.log   # 4（四步各一条）
grep -n "THRESHOLD OK"  CI_logs_root_workflow/*.log            # 各 1 处：门槛达标才有的行
grep -n "THRESHOLD NOT MET" CI_logs_root_workflow/*.log        # 各 1 处：AC3 反例
```

`UBUNTU_steps.log` 里评测一步的 rc 与门槛判定：

```
===== $ python3 -m intel_eval run --prompt-set v2
...
THRESHOLD OK
===== rc=0
===== $ python3 -m intel_eval run --prompt-set ci_bad --ignore-robots
...
  robots_violations        2          FAIL
THRESHOLD NOT MET: robots 禁止路径被抓取数
===== rc=1
```

即同一份日志里同时有「达标 → rc=0」与「注入故障 → rc=1」两侧，可对照。

---
生成时间：2026-11-24（UTC）｜源码 commit：`9da6490` + 本轮两处文档/工作流修正
