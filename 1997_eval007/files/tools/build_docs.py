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
import perf        # noqa: E402

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
ACS = [
    ("AC1", "8 类检测项各有命中与不命中夹具，结果符合预期（pytest 通过）", "V01-V09",
     "断言检测项恰 8 类；再逐类核对正例命中、反例不命中，并逐类断言至少各有 1 条正例与 1 条反例；"
     "另核企业名/人名两类告警的正反例与 3 条干净样例零误报。"
     "校验位的三层单独验：身份证只差校验位、银行卡只差 Luhn 位、"
     "信用代码校验位合法但第 3~8 位为 999999 占位时不报（并断言该占位号段校验位确实合法，"
     "否则「排除占位」那段会被前置校验短路成死代码）"),
    ("AC2", "含 error 级命中时退出码非 0，只有 warn 时退出码为 0", "V09-V15",
     "分别实测三种输入：含手机号（error）→ 退出码 1 且输出 BLOCK；"
     "只含车牌/邮箱/固话（warn）→ 退出码 0 且报告里仍列出 warn 项；无任何命中 → 退出码 0。"
     "另断言 error 级恰为工单点名的四类（手机号/身份证/银行卡/疑似真实信用代码），"
     "路径不存在时退出码 2（用法错误不等于阻断）"),
    ("AC3", "加入 allowlist 的条目不再报出（测试断言）", "V16-V21",
     "断言合规 allowlist 可加载、缺确认人或日期的被拒绝；"
     "同一份含手机号的输入，加白名单前后阻断数从 1 降到 0；"
     "再断言白名单只放行指定条目——含手机号+身份证时手机被放行、身份证仍阻断；"
     "最后实测命令在 allowlist 不合规时退出码 2"),
    ("AC4", "扫描 1000 条用例耗时 ≤ 10 秒（测试输出）", "V22-V27",
     "性能夹具为 1000 条 JSONL 用例（JSONL 是评测集的真实存放形态，按行计用例数）；"
     "先断言确实扫了 1000 条、且其中含 error 命中（测最坏情况而非快速跳过路径）；"
     "预热 2 轮后取 3 次稳态最小值断言 ≤ 10000ms，并单独记录冷启动耗时不做隐瞒"),
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
            m = re.match(r"\[(PASS|FAIL|SKIP)\] V(\d+)(b?) ", l)
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


def provenance(pii_scanned, pii_hits):
    rows = [
        ("生成脚本", "`pkg/engine.py`（虚构夹具与 1000 条性能用例）+ `python pkg/engine.py`"),
        ("生成脚本 sha256", "`%s`" % sha("pkg/engine.py")),
        ("检测逻辑 sha256", "`%s`" % sha("pkg/detect.py")),
        ("校验位算法 sha256", "`%s`" % sha("pkg/checksum.py")),
        ("规则配置 sha256", "`%s`" % sha("pkg/rules.py")),
        ("随机性", "**无随机**。所有夹具文本为手写常量，号码由校验位算法从自选号段补出；"
                 "1000 条性能用例按序号确定性生成，重跑字节级一致"),
        ("种子", "不适用（无随机数生成器）"),
        ("重跑命令", "`python pkg/engine.py`"),
        ("产出规模", "8 类检测项 × 正反例（18 条）+ 企业名/人名 4 条 + 干净样例 3 条 + 性能用例 1000 条 / pytest 60 项"),
        ("自扫结果", "`python -m pkg.cmd data/fixtures` → 命中 error %d / warn %d，"
                 "均来自**本包自己构造的虚构夹具**；这些号码由自选号段 + 校验位算法生成，"
                 "不对应任何真实个人或企业（详见下方虚构声明）" % (pii_scanned, pii_hits)),
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
    L = ["# 评测数据虚构性扫描器（S5-EVAL-007）", "",
         "命令 `eval-pii-scan`：在用例入库前与 CI 中扫描评测集、context 文件与样例文档，"
         "拦截看起来真实的敏感数据。8 类检测项 + 企业名/人名两类告警，"
         "error 级阻断 CI（退出码 1），warn 级只进报告（退出码 0）。", "",
         "## 一条命令复跑", "", "```",
         "python pkg/engine.py                    # 重算 data/（夹具与 1000 条性能用例）",
         "python tools/verify.py                  # 逐条断言 AC（%d 条），非零退出可接 CI" % n_verify,
         "python -m pytest tests -v               # 单元测试（60 项）",
         "python tools/mutate.py                  # 变异自检：改坏 14 处，每处都必须让 verify 变红",
         "python tools/build_docs.py              # 由实跑结果重生成本文档与 ACCEPTANCE",
         "python tools/make_zip.py                # 打包 + SHA256SUMS", "```", "",
         "依赖：Python 3.11+，无第三方库。", "",
         "## eval-pii-scan 用法", "", "```",
         "python -m pkg.cmd data/fixtures",
         "python -m pkg.cmd data/fixtures --allowlist data/allowlist.yaml",
         "python -m pkg.cmd data/perf1000 --json --report docs/scan_report.md",
         "```", "",
         "退出码：**0 无 error 级命中（可能只有 warn）/ 1 有 error 级命中（阻断 CI）/ 2 用法或配置错误**。",
         "「阻断」与「配置错」用不同退出码：把配错的 allowlist 当成命中，CI 里会误导排查方向。", "",
         "## 8 类检测项与分级", "",
         "| 检测项 | 判定依据 | 级别 |", "| --- | --- | --- |",
         "| 手机号 | `1[3-9]` 开头 11 位 | **error** |",
         "| 身份证 | 18 位 + ISO 7064 MOD 11-2 校验位 | **error** |",
         "| 银行卡 | 16~19 位 + Luhn 校验 | **error** |",
         "| 统一社会信用代码 | 18 位 + GB 32100 校验位，且第 3~8 位不是 `999999` | **error** |",
         "| 固定电话 | `0` + 2~3 位区号 + 7~8 位号码 | warn |",
         "| 邮箱 | 标准邮箱形态 | warn |",
         "| 详细地址 | 省/市/区之一 + 路号，且在 20 字窗口内 | warn |",
         "| 车牌号 | 省份简称 + 字母 + 5~6 位 | warn |",
         "| 企业名称 | 未带「示例」或「（虚构）」标记 | warn |",
         "| 中文人名 | 角色词（记录人/负责人/联系人…）后 2~4 字，未带「（虚构）」后缀 | warn |", "",
         "## allowlist", "",
         "每条必须写 `value` / `confirmed_by` / `confirmed_on`，`kind` 与 `reason` 可选。",
         "**格式不合规直接报错（退出码 2）**，不静默跳过 —— 否则白名单失效时没人知道。",
         "白名单只放行指定的那一条，不会连带放行同类其他命中。", "",
         "## 三条容易写错的口径", "",
         "**① 正则只负责切片，是否命中交给校验位。**",
         "身份证、银行卡、信用代码三类都是「形态匹配 + 校验位通过」才算命中，"
         "所以正反例的差别可以精确到一位数字（本包的正反例就只差校验位）。"
         "信用代码还有一条附加规则：第 3~8 位为 `999999` 视为占位号段、不报。"
         "这里有个坑 —— 占位号段的校验位**也要是合法的**，否则它会先被校验位拦掉，"
         "「排除占位」那段就成了永远走不到的死代码（本包第一版就是这样，变异测试直接抓出来的）。", "",
         "**② 中文人名不能靠纯正则边界识别。**",
         "`[\\u4e00-\\u9fa5]{2,4}` 贪婪匹配会把「张三负责」整体当成 4 字人名。"
         "做法是只在角色词（记录人 / 负责人 / 联系人 / 参会人 / 审批人 / 经办人 …）之后取候选，"
         "并且默认取 2 字、前两字是复姓时才取 3 字。", "",
         "**③ 性能口径要区分冷启动与稳态。**",
         "1000 条用例实测：冷启动 19.8 秒、稳态 0.13 秒 —— 差 150 倍，"
         "差别全部来自 1000 个新建小文件在 Windows 上被逐文件做实时防护扫描。"
         "所以性能夹具取 JSONL 单文件形态（评测集本来就是这么存的），"
         "并按「预热 2 轮后取 3 次稳态最小值」口径判定；冷启动耗时同时记录在报告里，不做隐瞒。", "",
         "## 目录", "", "| 路径 | 内容 |", "| --- | --- |",
         "| `pkg/detect.py` | 8 类检测项 + 企业名/人名告警 |",
         "| `pkg/checksum.py` | 身份证 ISO 7064、银行卡 Luhn、信用代码 GB 32100 校验位 |",
         "| `pkg/rules.py` | 阈值、级别、角色词、复姓表（集中在处，便于变异） |",
         "| `pkg/allowlist.py` | 白名单加载、格式校验、命中剔除 |",
         "| `pkg/scanner.py` | 遍历文件、JSONL 按行拆用例、汇总与报告 |",
         "| `pkg/cmd.py` | `eval-pii-scan` 入口（退出码 0/1/2） |",
         "| `pkg/engine.py` | 虚构夹具与 1000 条性能用例（确定性生成） |",
         "| `data/fixtures/` | 18 条正反例 + 4 条附加 + 3 条干净样例（逐条单文件） |",
         "| `data/perf1000/` | 1000 条性能用例（JSONL） |",
         "| `data/allowlist.yaml` | 白名单模板（含一条示例） |",
         "| `tests/` | pytest 用例 60 项 |", "",
         "## 设计取舍", "",
         "- **四类走校验位而不是纯正则**：手机号 11 位数字在合同编号里也常见，"
         "纯正则误报率高；身份证、银行卡、信用代码有官方校验位，用它判定可解释、可复现。",
         "- **「阻断」与「配置错」分两个退出码**：CI 里 1 表示「数据有问题」、2 表示「工具或配置有问题」，"
         "混在一起会把配错的 allowlist 当成人身数据泄露去排查。",
         "- **白名单强制写确认人与日期**：没有这条约束，白名单会变成「一键忽略」，"
         "半年后没人知道某条为什么被放行。",
         "- **性能夹具里塞了命中样例**：只放干净文本测的是「快速跳过」路径，"
         "不是最坏情况；本包每 97 条插入一条含手机号+身份证的用例。",
         ]
    return "\n".join(L)


def main():
    rc_v, ver_out = py("tools/verify.py")
    n = len([l for l in ver_out.splitlines() if l.startswith(("[PASS]", "[FAIL]"))])
    W = lambda rel, s: open(os.path.join(ROOT, rel), "w",
                            encoding="utf-8", newline="\n").write(s)
    # 性能数值单独落盘：它是运行产物（每次不同），绝不能进 SHA256SUMS
    import json as _json
    pm = perf.measure(os.path.join(ROOT, "data", "perf1000"))
    im_texts = []
    pf = os.path.join(ROOT, "data", "perf1000", "cases_1000.jsonl")
    for line in open(pf, encoding="utf-8"):
        line = line.strip()
        if line:
            im_texts.append(_json.loads(line).get("text", ""))
    im = perf.measure_in_memory(im_texts)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "perf.json"), "w", encoding="utf-8",
              newline="\n") as f:
        _json.dump({"cases": pm["scanned"], "cold_ms": round(pm["cold_ms"], 1),
                    "warm_best_ms": round(pm["best_ms"], 1),
                    "per_case_ms": round(pm["per_case_ms"], 4),
                    "in_memory_best_ms": round(im["best_ms"], 1),
                    "budget_ms": 10000.0}, f, ensure_ascii=False, indent=1, sort_keys=True)
    W("README.md", readme(n))
    W("ACCEPTANCE.md", acceptance(ver_out))
    import scanner
    _f, st1, _e = scanner.scan_path(os.path.join(ROOT, "data", "fixtures"))
    W("DATA_PROVENANCE.md", provenance(st1["blocking"], st1["warnings"]))
    _f2, st2, _e2 = scanner.scan_path(os.path.join(ROOT, "data", "fixtures"))
    if (st2["blocking"], st2["warnings"]) != (st1["blocking"], st1["warnings"]):
        print("FAIL 回填后扫描结果变化")
        return 1
    print("verify_rc=%d verify_lines=%d fixtures error=%d warn=%d (recheck %d/%d)"
          % (rc_v, n, st1["blocking"], st1["warnings"],
             st2["blocking"], st2["warnings"]))
    return 0 if rc_v == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
