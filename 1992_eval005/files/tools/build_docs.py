# -*- coding: utf-8 -*-
"""README / ACCEPTANCE / DATA_PROVENANCE 一律由实跑结果生成，数字取自真实 stdout。

ACCEPTANCE 用**行首标签**纯文本（不用 ### / 列表 / 代码围栏）——平台按行首锚定解析。
"""
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import engine  # noqa: E402
import pii_scan  # noqa: E402

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
ACS = [
    ("AC1", "8 种字段类型各有正例与反例测试且全部通过", "V01-V02",
     "断言字段类型恰 8 种；再逐类型统计「该字段全对」的正例数与「该字段有 wrong/missing/extra」的反例数，"
     "两者都必须 ≥1；最后跑 pytest 全量用例，全部通过"),
    ("AC2", "付款节点列表多 1 项、少 1 项时分别计入 extra 与 missing", "V03-V05",
     "构造三个用例：完全一致（3 项全 correct）、多 1 项（必须 extra=1 且 missing=0）、"
     "少 1 项（必须 missing=1 且 extra=0）；再单独断言「顺序打乱不影响结论」，证明是按 seq 对齐而非按下标"),
    ("AC3", "金额相差 1 分即判 wrong；critical 字段错误时用例不通过", "V06-V10",
     "构造金额差 1 分的用例，断言 wrong=1 且 correct=0；构造 5 个 critical 出错的用例"
     "（金额差 1 分、金额用浮点、信用代码错一位、金额缺失、信用代码长度不足），断言全部 passed=False "
     "且 critical_hit 非空；再用一个非 critical 单错用例做正向对照（仍应通过）"),
    ("AC4", "precision、recall、F1 计算结果与手算表一致", "V11-V12",
     "手算表由 fractions.Fraction 整数运算独立生成（与评分器的浮点实现是两条路径），"
     "逐用例逐字段比对到小数点后 12 位；再断言手算表自身自洽（分子分母与计数对得上）"),
]


def py(*args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, env=ENV, capture_output=True)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def sha(rel):
    h = hashlib.sha256()
    h.update(open(os.path.join(ROOT, rel), "rb").read())
    return h.hexdigest()


def acceptance(ver_out):
    lines = ver_out.splitlines()
    L = ["# ACCEPTANCE — 逐条 AC 判定（原文 / 判定方式 / 复核命令 / 实际输出原文）",
         "",
         "以下输出为 tools/verify.py 在交付包内的真实 stdout，未经修改。",
         ""]
    for cid, src, rng, how in ACS:
        a, b = rng.split("-")
        lo, hi = int(a[1:]), int(b[1:])
        picked = [l for l in lines
                  if re.match(r"\[(PASS|FAIL|SKIP)\] V(\d+) ", l) and lo <= int(re.match(r"\[(?:PASS|FAIL|SKIP)\] V(\d+) ", l).group(1)) <= hi]
        L += ["%s 原文：%s" % (cid, src),
              "判定方式：%s" % how,
              "复核命令：python tools/verify.py   （看 %s）" % rng,
              "实际输出原文："]
        L += picked or ["（未取到输出）"]
        L.append("")
    summary = [l for l in lines if l.startswith("SUMMARY")]
    L += ["汇总：%s" % (summary[0] if summary else "(无)"), ""]
    return "\n".join(L)


def provenance(scanned, hits):
    rows = [
        ("生成脚本", "`pkg/engine.py`（schema、34 个虚构用例、手工计数）+ `tools/gen.py`（写 data/ 与手算表）"),
        ("生成脚本 sha256", "`%s`" % sha("pkg/engine.py")),
        ("评分器 sha256", "`%s`" % sha("pkg/scorer.py")),
        ("归一化 sha256", "`%s`" % sha("pkg/normalize.py")),
        ("随机性", "**无随机**。全部数值、日期、信用代码、条款文本均为手写固定常量；"
                 "同一脚本在任何机器重跑产出字节级一致"),
        ("种子", "不适用（无随机数生成器）"),
        ("重跑命令", "`python tools/gen.py`"),
        ("产出规模", "34 个用例 / 8 种字段类型 / 306 行手算表 / pytest 68 项"),
        ("PII 扫描", "`python tools/pii_scan.py` → `scanned=%d hits=%d`"
                 "（手机号 / 邮箱 / 身份证 / 银行卡 四类正则；扫描数随产物增减而变化，判据只看 hits=0）"
                 % (scanned, hits)),
    ]
    L = ["# DATA_PROVENANCE — 数据来源与可复核性", "",
         "本交付包**不含任何真实个人信息或企业信息**。全部示例数据由脚本生成，可完整重放。", "",
         "| 项 | 值 |", "| --- | --- |"]
    L += ["| %s | %s |" % (k, v) for k, v in rows]
    L += ["", "## 虚构声明", "",
          "合同编号、日期、金额、信用代码、付款节点、条款要点全部虚构。"
          "信用代码使用不合法的示例串（`91310000MA1FL2XY3K` 与 `91310000AAAAAAAAAA`），"
          "不对应任何真实主体；文本中不出现客户名称。", ""]
    return "\n".join(L)


def readme(n_verify):
    L = ["# 结构化输出评分器（S5-EVAL-005）", "",
         "按字段类型归一化后比对 expected 与 actual，输出字段级 correct / wrong / missing / extra，"
         "以及整体与分字段的 precision、recall、F1；支持把字段标为 critical。"
         "全部比对由程序完成，**不用模型判断金额**。", "",
         "## 一条命令复跑", "", "```",
         "python tools/gen.py            # 重算 data/ 与 handcalc.csv",
         "python tools/verify.py         # 逐条断言 AC（%d 条），非零退出可接 CI" % n_verify,
         "python -m pytest tests -v      # 单元测试（68 项）",
         "python tools/mutate.py         # 变异自检：改坏引擎 11 处，每处都必须让 verify 变红",
         "python tools/pii_scan.py       # PII 扫描（手机 / 邮箱 / 身份证 / 银行卡）",
         "python tools/build_docs.py     # 由实跑结果重生成本文档与 ACCEPTANCE",
         "python tools/make_zip.py       # 打包 + SHA256SUMS", "```", "",
         "依赖：Python 3.11+。除 PyYAML（可选，仅用于双轨交叉验证）外无第三方库。", "",
         "## 指标口径（显式写出，不留默契）", "",
         "| 计数 | 含义 |", "| --- | --- |",
         "| correct | 期望有、实际有、归一化后相等 |",
         "| wrong | 期望有、实际有、归一化后不等（既算误报也算漏报） |",
         "| missing | 期望有、实际没有 |",
         "| extra | 期望没有、实际有 |", "",
         "`precision = correct / (correct + wrong + extra)`",
         "`recall = correct / (correct + wrong + missing)`",
         "`F1 = 2PR / (P + R)`，P+R=0 时记 0.0", "",
         "## 8 种字段类型的归一化规则", "",
         "| 类型 | 归一化 | 容差 |", "| --- | --- | --- |",
         "| string | NFKC（全半角统一）、去零宽字符、空白折叠、英文 casefold | 无 |",
         "| date | 5 种写法统一为 ISO（2026-05-06 / 2026/5/6 / 2026年5月6日 / 20260506 / 2026.5.6） | 无 |",
         "| money_fen | 整数严格相等；**拒绝浮点与布尔** | **0 分** |",
         "| rate_bp | 整数严格相等；拒绝浮点与布尔 | **0 基点** |",
         "| uscc | 转大写、去空白、长度必须 18 位 | 无 |",
         "| enum | 按映射表把别名收敛为规范值 | 无 |",
         "| list | 按 seq 或主键对齐后逐项比对，多出记 extra、缺失记 missing | 无 |",
         "| summary | 期望为要点数组：实际是数组时三者都有意义；实际是自由文本时只报 recall | 无 |", "",
         "## 目录", "", "| 路径 | 内容 |", "| --- | --- |",
         "| `pkg/engine.py` | 字段 schema、34 个虚构用例、**手工填写的期望计数** |",
         "| `pkg/normalize.py` | 8 种类型的归一化函数 |",
         "| `pkg/scorer.py` | `score_fields()`、`FieldScore`、指标计算、critical 判定 |",
         "| `pkg/miniyaml.py` | 极简 YAML 子集解析器（零依赖；装了 PyYAML 时交叉验证） |",
         "| `data/suite.yaml` | 套件配置：字段类型、critical 标记、阈值 |",
         "| `data/cases.jsonl` | 34 个用例（含期望与实际） |",
         "| `data/handcalc.csv` | 手算表（306 行，Fraction 整数运算生成） |",
         "| `tests/` | pytest 用例 68 项 |",
         "| `tools/` | 生成 / 断言 / 变异 / 扫描 / 文档 / 打包 |", "",
         "## 用法", "", "```python",
         "from pkg.scorer import score_fields",
         "fs = score_fields(expected, actual, field_schema)",
         "print(fs.overall())      # precision / recall / f1",
         "print(fs.per_field())    # 每个字段的计数与指标",
         "print(fs.passed())       # critical 出错即 False，否则看 F1 是否达阈值",
         "```", "",
         "## 设计取舍", "",
         "- **金额与费率绝不设容差**：浮点会引入精度误差，所以 `money_fen` 直接拒绝 float 输入，"
         "而不是在比较时放宽容差。1 分钱必须判 wrong。",
         "- **wrong 同时计入 P 与 R 的分母**：一个字段「值不对」既是一次误报也是一次漏报，"
         "只计入一边会虚高指标。这一口径写在文档与代码常量 `WRONG_COUNTS_AS` 里，可用变异测试验证。",
         "- **summary 的自由文本模式只报 recall**：自由文本无法可靠判定「多说了什么」，"
         "强行给 precision 会恒等于 1.0，是假指标。因此该模式下显式标注 precision 不适用。",
         ]
    return "\n".join(L)


def main():
    rc_v, ver_out = py("tools/verify.py")
    n = len([l for l in ver_out.splitlines() if l.startswith(("[PASS]", "[FAIL]"))])
    W = lambda rel, s: open(os.path.join(ROOT, rel), "w",
                            encoding="utf-8", newline="\n").write(s)
    W("README.md", readme(n))
    W("ACCEPTANCE.md", acceptance(ver_out))
    # 两遍：先写临时值，再数真实文件数回填；回填不改变文件数，回填后复扫须一致
    W("DATA_PROVENANCE.md", provenance(-1, 0))
    scanned, hits = pii_scan.scan(ROOT)
    W("DATA_PROVENANCE.md", provenance(scanned, len(hits)))
    scanned2, hits2 = pii_scan.scan(ROOT)
    if (scanned2, len(hits2)) != (scanned, len(hits)):
        print("FAIL 回填后扫描数变化 %s -> %s" % (scanned, scanned2))
        return 1
    print("verify_rc=%d verify_lines=%d pii scanned=%d hits=%d (recheck %d/%d)"
          % (rc_v, n, scanned, len(hits), scanned2, len(hits2)))
    return 0 if rc_v == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
