# -*- coding: utf-8 -*-
"""#2037 多轮对话评测集自检：4 条 AC -> 可执行断言。

    python verify_2037.py              # 正常自检，rc=0 = 全过
    python verify_2037.py --self-test  # 反向自测：注入失败必须 rc=1
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

import lint as L                      # noqa: E402
from multiturn import __main__ as R   # noqa: E402
from multiturn import metrics as M    # noqa: E402

PID = 2037
F: list = []


def chk(name, ok, detail=""):
    F.append((name, bool(ok), detail))
    print(("[ OK ]" if ok else "[FAIL]"), name, ("| " + str(detail)) if detail else "")


def cli(*a):
    return subprocess.run([sys.executable, "-m", "multiturn", *a], capture_output=True,
                          cwd=HERE, text=True, encoding="utf-8", errors="replace")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    cases = R.load_cases()
    facts = R.load_facts()

    # ===== AC1：30 组，每组 3–5 轮，四类分布符合说明 =====
    chk("AC1 cases.jsonl 恰 30 组", len(cases) == 30, len(cases))
    turns_n = [len(c["turns"]) for c in cases]
    chk("AC1 每组 3–5 轮", all(3 <= n <= 5 for n in turns_n),
        "min %d / max %d" % (min(turns_n), max(turns_n)))
    dist = dict(Counter(c["kind"] for c in cases))
    chk("AC1 分布 指代8/条件变更8/话题切换6/纠正8",
        dist == {"coref": 8, "condition_change": 8, "topic_switch": 6, "correction": 8}, dist)
    chk("AC1 用例为 turns 数组格式",
        all(isinstance(c.get("turns"), list) and c["turns"]
            and all("role" in t and "text" in t for t in c["turns"]) for c in cases))
    chk("AC1 复用 EVAL-022 知识库夹具（120 篇）", len(facts) == 120, len(facts))
    chk("AC1 每条引用的 kb_doc 都存在于知识库",
        all((not c.get("kb_doc")) or c["kb_doc"] in facts for c in cases))

    # ===== AC2：eval-lint 与 eval-pii-scan 均通过（命令输出）=====
    r = subprocess.run([sys.executable, os.path.join(HERE, "tools", "lint.py")],
                       capture_output=True, cwd=HERE, text=True,
                       encoding="utf-8", errors="replace")
    chk("AC2 eval-lint 命令行 rc=0 且打印 PASS",
        r.returncode == 0 and "LINT PASS" in (r.stdout or ""))
    chk("AC2 eval-pii-scan 命令行通过（0 命中）",
        "PII PASS" in (r.stdout or "") and "PII hits=0" in (r.stdout or ""))
    errs, _, _ = L.lint()
    chk("AC2 lint 内部复核 0 错误", not errs, errs[:2])

    # ===== AC3：8 组纠正类都把被纠正前提写入 forbidden_points（脚本检查）=====
    corr = [c for c in cases if c["kind"] == "correction"]
    chk("AC3 纠正类恰 8 组", len(corr) == 8, len(corr))
    has_stale = [c for c in corr
                 if any(f["type"].startswith("stale_premise") for f in c["forbidden_points"])]
    chk("AC3 8 组纠正类全部写入 stale_premise* 的 forbidden_points",
        len(has_stale) == 8, "%d/8" % len(has_stale))
    # 被纠正的前提要能指名道姓（wrong_entity）与具体值（wrong_value）
    named = [c for c in corr
             if any(f.get("wrong_entity") for f in c["forbidden_points"])]
    valued = [c for c in corr
              if any(f.get("wrong_value") for f in c["forbidden_points"])]
    chk("AC3 每条都指明被纠正的实体（wrong_entity）", len(named) == 8, "%d/8" % len(named))
    chk("AC3 每条都记录被纠正的具体值（wrong_value）", len(valued) == 8, "%d/8" % len(valued))
    # 旧值必须真的不同于纠正后的值，否则 forbidden 检查恒假阳性
    collide = []
    for c in corr:
        wv = next((f.get("wrong_value") for f in c["forbidden_points"]
                   if f.get("wrong_value")), "")
        new_val = (c["final_expect"]["answer_points"] or [""])[0]
        if wv and wv == new_val:
            collide.append(c["case_id"])
    chk("AC3 被纠正的旧值 ≠ 纠正后的新值（防 forbidden 恒假阳性）", not collide, collide)

    # ===== AC4：echo mock 按轮次跑通 eval-run，结果可见每轮检查点 =====
    rr = cli()
    chk("AC4 echo mock 跑通 eval-run（rc=0）", rr.returncode == 0, "rc=%d" % rr.returncode)
    md = os.path.join(HERE, "reports", "mt_v1.md")
    chk("AC4 生成 Markdown 报告", os.path.isfile(md))
    t = open(md, encoding="utf-8").read() if os.path.isfile(md) else ""
    chk("AC4 报告含「中间检查点」小节（逐轮可见）", "按轮次可见的检查点" in t)
    chk("AC4 报告含三项指标", all(k in t for k in
                              ("最后一轮要点命中率", "中间检查点通过率", "forbidden 违反次数")))
    rows = [R.evaluate(c, facts) for c in cases]
    m = M.aggregate(rows)
    chk("AC4 三项指标均达标",
        m["final_point_hit"] >= 0.80 and m["checkpoint_pass"] >= 1.00
        and m["forbidden_violations"] == 0,
        "final=%.4f cp=%.4f forbidden=%d"
        % (m["final_point_hit"], m["checkpoint_pass"], m["forbidden_violations"]))
    # 每轮检查点都能定位到具体轮次
    chk("AC4 每条用例的检查点轮次可定位",
        all(r["_cp"]["total"] >= 1 for r in rows),
        sum(r["_cp"]["total"] for r in rows))

    # ===== 可证伪：两个破坏开关各自触发对应失败 =====
    rb = cli("--break-history", "--tag", "v_bh")
    ob = rb.stdout or ""
    chk("可证伪：不传历史 -> 退出码 1", rb.returncode == 1, "rc=%d" % rb.returncode)
    chk("可证伪：不传历史 -> 最后一轮要点命中率显著下降",
        "final_point_hit    0.2667" in ob or "0.2667" in ob, [x for x in ob.splitlines() if "final_point" in x][:1])
    rs = cli("--break-stale", "--tag", "v_bs")
    os_ = rs.stdout or ""
    chk("可证伪：纠正后沿用旧前提 -> 退出码 1", rs.returncode == 1, "rc=%d" % rs.returncode)
    vio = [x for x in os_.splitlines() if "forbidden" in x]
    chk("可证伪：纠正后沿用旧前提 -> forbidden 触发 8 次",
        any("8" in x for x in vio), vio[:1])

    rt = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "--tb=no"],
                        capture_output=True, cwd=HERE, text=True,
                        encoding="utf-8", errors="replace")
    chk("pytest 全套通过", rt.returncode == 0,
        ((rt.stdout or "").strip().splitlines() or ["-"])[-1][:50])

    if "--inject-failure" in argv:
        chk("INJECT 故意失败（证明断言会失败）", False, "injected")

    bad = [f for f in F if not f[1]]
    print("\nTOTAL %d, PASS %d, FAIL %d" % (len(F), len(F) - len(bad), len(bad)))
    return 1 if bad else 0


def self_test():
    print("=== 反向自测 ===")
    a = subprocess.run([sys.executable, os.path.abspath(__file__)], capture_output=True,
                       cwd=HERE, text=True, encoding="utf-8", errors="replace")
    good = a.returncode == 0
    print("[ OK ] 正常检查 rc=0" if good else "[FAIL] 正常检查 rc=%d" % a.returncode)
    b = subprocess.run([sys.executable, os.path.abspath(__file__), "--inject-failure"],
                       capture_output=True, cwd=HERE, text=True,
                       encoding="utf-8", errors="replace")
    bad = b.returncode == 1
    print("[ OK ] 注入失败后 rc=1" if bad else "[FAIL] 注入失败后 rc=%d" % b.returncode)
    print("\nSELF-TEST %s" % ("PASS（断言不是摆设）" if (good and bad) else "FAIL"))
    return 0 if (good and bad) else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(main())
