# 情报简报评测集 intel_brief.triage（#2022 · S5-EVAL-017）

## 一句话
35 条情报简报评测用例（常规 20 / 高相似干扰 10 / 全部与画像无关 5），每条 context 含 8~20 篇虚构资讯，
配 pairwise F1、分类准确率、NDCG@5 三项计算脚本与 runner，另有两项 forbidden 检查。

## 目录
```
files/                  明文全文（平台复核只读文本、不解压 zip，看这里）
files/ACCEPTANCE.md     四条 AC 逐条：判定方式 / 复核命令 / 实际输出原文
files/DATA_PROVENANCE.md 生成脚本 sha256、种子、重跑命令、pii 证据、局限
files/data/cases.jsonl  35 条用例（gold 聚类/分类/前5、画像）
files/contexts/*.json   35 份资讯 context（8~20 篇/份）
files/tools/gen_cases.py 用例与 context 生成器（同源，gold 可取证）
files/tools/metrics.py  三项指标 + 簇对齐 + forbidden
files/tools/eval_run.py runner（echo mock：只用 context 与画像，不读 gold）
files/tools/lint.py     eval-lint + eval-pii-scan（AC1 的两个独立命令）
files/reports/          评测报告（生成物，不参与校验和）
triage2022_deliver.zip  完整交付包（49 条校验和）
verify_logs/            Ubuntu 24.04 真机实跑原始日志
```

## 怎么跑（解压后包根目录）
```bash
python verify_2022.py                 # 29 项 AC 断言，rc=0 全过
python tools/lint.py                  # eval-lint + eval-pii-scan
python tools/eval_run.py              # 三项指标 + 报告
python tools/eval_run.py --break-cluster   # 打掉聚类，rc=1（证明指标可证伪）
python tools/eval_run.py --break-order
python tools/eval_run.py --leak
python -m pytest tests -q             # 24 项
```

## 实测
| 指标 | 实测 | 门槛 |
|---|---|---|
| 聚类 pairwise F1 | 0.8763 | ≥0.80 |
| 分类准确率 | 0.8843 | ≥0.80 |
| 排序 NDCG@5 | 0.8607 | ≥0.80 |
| forbidden：同事件出现两次 | 0 | 0 |
| forbidden：context 外资讯 | 0 | 0 |
| 全无关样本输出「本期无高相关资讯」 | 5/5 | 5/5 |

双平台：Windows Py3.11.7 与 Ubuntu Py3.12.3 均 verify 29/29、pytest 24 passed、校验和 49/49，
且重跑 `tools/gen_cases.py` 后校验和仍 49/49（幂等，跨平台字节一致）。
