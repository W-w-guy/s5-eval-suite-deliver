# -*- coding: utf-8 -*-
"""README / ACCEPTANCE / DATA_PROVENANCE 一律由实跑结果生成。

ACCEPTANCE 用**行首标签**纯文本（不用 ### / 列表 / 代码围栏）—— 平台按行首锚定解析。
"""
import hashlib
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import engine      # noqa: E402
import pii_scan    # noqa: E402

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
ACS = [
    ("AC1", "通过率下降 4 个百分点时判定失败，下降 2 个百分点时通过（pytest 通过）", "V02-V10",
     "构造两个运行：通过率 88%（比基线 92% 降 4.0000pp）与 90.4%（降 1.6000pp）。"
     "断言降幅分别算得恰好 4 与 1.6、前者 verdict=fail、后者 verdict=pass；"
     "并断言两个场景的 must 翻转都没到 3 条，说明失败只能归因于通过率降幅、不是被另一条判据顺带触发；"
     "再用 compare 命令实测退出码（失败 1 / 通过 0）。另加取整探针：降 3.2000pp 必须判失败"),
    ("AC2", "重跑 2 次中有 1 次通过的用例被标为 flaky 而不计入退化（测试断言）", "V11-V18",
     "构造 3 条翻转用例（都含 must 要点），重跑记录为 [False,True] / [True,False] / [False,False]。"
     "断言前两条被标 flaky、只有两次都失败的第三条留在 regression 清单、must 翻转数从 3 降到 1、整体判 pass；"
     "再做一次反向对照：把 FLAKY_EXCLUDED_FROM_REGRESSION 关掉后 must 翻转就是 3 条并判 fail，"
     "证明剔除动作真的起了作用"),
    ("AC3", "suite_version 不同时只比较共有用例，结果中写明比较范围", "V19-V26",
     "构造一份 v2 运行：删掉 12 条、新增 10 条、总 123 条。断言识别出版本不同、"
     "只比较共有 113 条、基线独有 12 条与本次独有 10 条被排除、note 里写明范围；"
     "并对照版本相同的运行比较全部 125 条。再断言新增的 10 条虽全失败但不进 regression 清单，"
     "以及不做共有用例限制时分母会变成 123（与实际 113 不同）"),
    ("AC4", "选择有执行错误的运行作为基线时命令报错", "V27-V34",
     "对两个非法运行分别实测 set 命令：status=failed 与 status=completed 但 errors 非空。"
     "断言两者退出码都是 2（**命令报错**，不是判定失败 1）且输出含明确拒绝原因；"
     "再对合规运行做正向对照（退出码 0）；另断言不填理由、缺 eval.baseline.set 权限同样报错，"
     "以及 compare 遇到有执行错误的基线也会抛错"),
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
        picked = []
        for l in lines:
            m = re.match(r"\[(PASS|FAIL|SKIP)\] V(\d+) ", l)
            if m and lo <= int(m.group(2)) <= hi:
                picked.append(l)
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
        ("生成脚本", "`pkg/engine.py`（套件配置、基线运行、9 个场景）+ 直接入口 `python pkg/engine.py`"),
        ("生成脚本 sha256", "`%s`" % sha("pkg/engine.py")),
        ("判定逻辑 sha256", "`%s`" % sha("pkg/baseline.py")),
        ("命令入口 sha256", "`%s`" % sha("pkg/cmd.py")),
        ("随机性", "**无随机**。所有用例按下标确定性生成（前 N 个通过），"
                 "must 要点是否跟随 passed 也由下标取模决定；重跑产出字节级一致"),
        ("种子", "不适用（无随机数生成器）"),
        ("重跑命令", "`python pkg/engine.py`"),
        ("产出规模", "9 个运行场景 / 998 条用例记录 / 1 份套件配置 / pytest 50 项"),
        ("PII 扫描", "`python tools/pii_scan.py` → `scanned=%d hits=%d`"
                 "（手机号 / 邮箱 / 身份证 / 银行卡 四类正则；扫描数随产物增减而变化，判据只看 hits=0）"
                 % (scanned, hits)),
    ]
    L = ["# DATA_PROVENANCE — 数据来源与可复核性", "",
         "本交付包**不含任何真实个人信息或企业信息**。全部示例数据由脚本生成，可完整重放。", "",
         "| 项 | 值 |", "| --- | --- |"]
    L += ["| %s | %s |" % (k, v) for k, v in rows]
    L += ["", "## 虚构声明", "",
          "用例编号、通过/失败分布、豁免原因与批准人角色、策略变更日志全部虚构；"
          "「质量负责人」等角色为示例岗位名，不对应任何真实人员；文本中不出现客户名称。", ""]
    return "\n".join(L)


def readme(n_verify):
    L = ["# 回归基线管理与能力退化判定（S5-EVAL-034）", "",
         "实现 `eval-baseline set / show / compare` 三个命令与退化判定函数：通过率差、平均分差、"
         "按 tag 的差值、翻转用例清单（regression / fix），含**抖动重跑**与**版本差异**处理。", "",
         "## 一条命令复跑", "", "```",
         "python pkg/engine.py                    # 重算 data/（套件配置、基线、9 个运行场景）",
         "python tools/verify.py                  # 逐条断言 AC（%d 条），非零退出可接 CI" % n_verify,
         "python -m pytest tests -v               # 单元测试（50 项）",
         "python tools/mutate.py                  # 变异自检：改坏 13 处，每处都必须让 verify 变红",
         "python tools/pii_scan.py                # PII 扫描",
         "python tools/build_docs.py              # 由实跑结果重生成本文档与 ACCEPTANCE",
         "python tools/make_zip.py                # 打包 + SHA256SUMS", "```", "",
         "依赖：Python 3.11+，无第三方库（YAML 用自写的极简子集解析器）。", "",
         "## eval-baseline 用法", "", "```",
         "python -m pkg.cmd show",
         "python -m pkg.cmd set --run BASE_V1 --reason \"首版基线\" --permissions eval.baseline.set",
         "python -m pkg.cmd compare --run CUR_DROP4",
         "python -m pkg.cmd compare --run CUR_FLAKY --json",
         "```", "",
         "退出码：**0 通过 / 1 判定为退化失败 / 2 命令报错**（基线不合法、权限不足、理由缺失、找不到运行）。",
         "「命令报错」与「判定失败」是两种不同的退出码 —— 把非法基线当成退化失败会误导排查。", "",
         "## set 的门槛", "",
         "- 必须持有 `eval.baseline.set` 权限；",
         "- 必须填写理由；",
         "- 运行必须与当前套件同名、`suite_version` 相同、`status=completed` 且 `errors` 为空。", "",
         "## 默认判定规则（可在 suite.yaml 覆盖）", "",
         "| 判据 | 默认阈值 | 结果 |", "| --- | --- | --- |",
         "| 通过率下降 | > 3 个百分点 | **fail** |",
         "| must 要点翻转用例数 | >= 3 条 | **fail** |",
         "| 平均分下降 | > 0.05 | **warn** |",
         "| 抖动重跑 | regression 用例重跑 2 次 | 任一次通过即标 flaky |", "",
         "## 三条容易写错的口径", "",
         "**① 通过率与分数差一律用分数精确计算，不先四舍五入再比较。**",
         "`Fraction` 全程参与判定：降 3.2000pp 必须判失败。若写成 `round(drop) > 3`，"
         "3.2 会被舍成 3 从而假通过。`verify.py` 里有一条取整探针专门锁这件事。", "",
         "**② flaky 用例不计入退化，且 `must` 与 `passed` 是解耦的。**",
         "regression 用例重跑 2 次，任一次通过即标 flaky 并单列，既不算 regression 也不算 fix，"
         "也不计入 must 翻转数。另：用例判定失败不等于 must 要点翻转 —— "
         "本包的数据里只有每第 3 条用例的 must 会跟随 passed，其余用例失败多因非 must 要点失分。"
         "这样「通过率降幅」与「must 翻转」是两条独立判据，一个场景失败不会被另一条顺带触发。", "",
         "**③ suite_version 不同时只在共有的 case_key 上比较，并写明范围。**",
         "直接用各自的全量通过率相比，会把「新增用例」和「已删除用例」算进分母，"
         "得出的降幅没有可比性（本包实测：v2 有 123 条、共有只有 113 条）。"
         "结果里会给出 `compared_cases` / `only_in_baseline` / `only_in_current` 与一句范围说明。", "",
         "## 目录", "", "| 路径 | 内容 |", "| --- | --- |",
         "| `pkg/baseline.py` | 基线门槛校验、退化判定、抖动处理、版本交集、Markdown 摘要 |",
         "| `pkg/cmd.py` | `eval-baseline set/show/compare` 入口（退出码 0/1/2） |",
         "| `pkg/engine.py` | 套件配置、基线运行、9 个场景（确定性生成） |",
         "| `pkg/miniyaml.py` | 极简 YAML 子集解析器（零依赖；装了 PyYAML 时交叉验证） |",
         "| `data/suite.yaml` | 套件配置与判定规则 |",
         "| `data/runs/*.json` | 基线与 9 个场景运行记录 |",
         "| `data/baselines/kb_qa.yaml` | 当前基线指针（run + 理由 + 设基人 + 时间） |",
         "| `tests/` | pytest 用例 50 项 |",
         "| `tools/` | 断言 / 变异 / 扫描 / 文档 / 打包 |", "",
         "## 设计取舍", "",
         "- **非法基线与退化失败用不同退出码**：前者是用法错误（2），后者是质量结论（1）。"
         "CI 里把两者混为一谈，会把「配错了基线文件」误报成「能力退化」。",
         "- **豁免型的宽松处理一律做成显式开关**：`FLAKY_EXCLUDED_FROM_REGRESSION`、"
         "`ENFORCE_VERSION_INTERSECTION`、`ENFORCE_BASELINE_RUN_VALID` 都集中在 baseline.py，"
         "变异测试逐条翻转验证它们真的影响结论。",
         "- **建议更新基线但不自动更新**：连续 3 次优于基线时只在报告里给建议。"
         "自动更新会让基线随能力下滑一路跟着降，退化判定失去基准。",
         ]
    return "\n".join(L)


def main():
    rc_v, ver_out = py("tools/verify.py")
    n = len([l for l in ver_out.splitlines() if l.startswith(("[PASS]", "[FAIL]"))])
    W = lambda rel, s: open(os.path.join(ROOT, rel), "w",
                            encoding="utf-8", newline="\n").write(s)
    W("README.md", readme(n))
    W("ACCEPTANCE.md", acceptance(ver_out))
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
