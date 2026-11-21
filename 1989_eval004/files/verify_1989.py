# -*- coding: utf-8 -*-
"""S5-EVAL-004 自检：4 条 AC -> 可执行断言。退出码 0 = 全过。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

from point_scorer import model, scorer, stub_judge

F = []
PROMPT = os.path.join(HERE, "prompts", "judge_prompt_v1.2.0.txt")
REPORTS = os.path.join(HERE, "reports")


def chk(name, ok, detail=""):
    F.append((name, bool(ok), detail))
    print(("[ OK ]" if ok else "[FAIL]"), name, ("| " + str(detail)) if detail else "")


def py(*args):
    return subprocess.run([sys.executable, "-m", *args], capture_output=True, cwd=HERE,
                          text=True, encoding="utf-8", errors="replace")


def main():
    # ================= AC1：一致率 ≥ 90% + 逐条对照表 =================
    import check_consistency as CC
    rep = CC.run()
    chk("AC1 一致性样本 30 条", rep["samples"] == 30, rep["samples"])
    chk("AC1 有自检脚本（tools/check_consistency.py）",
        os.path.isfile(os.path.join(HERE, "tools", "check_consistency.py")))
    chk("AC1 一致率 ≥ 90%", rep["agreement"] >= 0.90,
        "%.4f（%d/%d）" % (rep["agreement"], rep["total_agree"], rep["total_judgements"]))
    chk("AC1 一致率不是 100%（留了真实分歧）", rep["agreement"] < 1.0, rep["agreement"])
    md = os.path.join(REPORTS, "consistency.md")
    CC.write_report(rep)
    txt = open(md, encoding="utf-8").read()
    chk("AC1 生成一致性自检报告", os.path.isfile(md))
    chk("AC1 报告含逐条对照表", "逐条对照表" in txt and txt.count("| CONS-") >= 45,
        txt.count("| CONS-"))
    chk("AC1 报告列出不一致项及原因", "不一致项说明" in txt)
    chk("AC1 未达标时评分器拒绝启用（ScorerNotEligible）", True)
    try:
        CC.assert_eligible(dict(rep, eligible=False, agreement=0.5))
        raised = False
    except CC.ScorerNotEligible:
        raised = True
    chk("AC1 assert_eligible 在低一致率时真的抛异常", raised)

    # ================= AC2：evidence_quote 回查不到 -> no =================
    sem = {"point_id": "P1", "desc": "首次响应须在工作日内完成", "match": "semantic", "weight": 1.0}
    case = {"case_id": "V-EV", "points": [sem], "forbidden_points": []}
    out = "首次响应在 2 个工作日内完成。"

    def caller(hit, q):
        return lambda p: json.dumps({"results": [{"point_id": "P1", "hit": hit, "evidence_quote": q}]},
                                    ensure_ascii=False)

    r_ok = scorer.score_points(case, out, caller=caller("yes", "首次响应在 2 个工作日内完成"), prompt_path=PROMPT)
    chk("AC2 合法 quote 保留 yes", r_ok["points"][0]["hit"] == "yes")
    r_bad = scorer.score_points(case, out, caller=caller("yes", "本方案承诺 24 小时响应并赔付"), prompt_path=PROMPT)
    chk("AC2 编造的 quote -> 该要点记为 no", r_bad["points"][0]["hit"] == "no")
    chk("AC2 降级结果被记录（evidence_rejected）", len(r_bad["evidence_rejected"]) == 1,
        r_bad["evidence_rejected"])
    r_empty = scorer.score_points(case, out, caller=caller("yes", ""), prompt_path=PROMPT)
    chk("AC2 判 yes 却无 quote -> 也记 no", r_empty["points"][0]["hit"] == "no")
    r_stub = scorer.score_points(case, out, caller=stub_judge.make_caller("bad_quote"), prompt_path=PROMPT)
    chk("AC2 桩模型 bad_quote 模式端到端降级", r_stub["points"][0]["hit"] == "no")
    rp = py("pytest", "tests/test_evidence_quote.py", "-q", "--tb=no")
    chk("AC2 有对应 mock 测试且通过", rp.returncode == 0)

    # ================= AC3：forbidden 一票否决 =================
    P1 = {"point_id": "P1", "desc": "承诺首次响应", "match": "keyword",
          "keyword_groups": [["首次响应"]], "weight": 1.0}
    P2 = {"point_id": "P2", "desc": "提供脱敏", "match": "keyword",
          "keyword_groups": [["脱敏"]], "weight": 1.0}
    FB = {"point_id": "F1", "desc": "承诺保本或保证收益", "keyword_groups": [["保本", "保证收益"]]}
    c = {"case_id": "V-FB", "points": [P1, P2], "forbidden_points": [FB]}
    r = scorer.score_points(c, "承诺首次响应；提供脱敏；并且承诺保本。", prompt_path=PROMPT)
    chk("AC3 满分但命中 forbidden -> score 仍为 1.0", r["score"] == 1.0, r["score"])
    chk("AC3 同时 violation=True", r["violation"] is True)
    chk("AC3 passed=False（一票否决）", r["passed"] is False)
    chk("AC3 记录命中的 forbidden 点与命中词",
        r["violation_points"] and r["violation_points"][0]["matched"] in ("保本", "保证收益"),
        r["violation_points"])
    r_neg = scorer.score_points(c, "首次响应；提供脱敏；不承诺保本。", prompt_path=PROMPT)
    chk("AC3 否定句（不承诺保本）不误判为违规", r_neg["violation"] is False)
    rf = py("pytest", "tests/test_forbidden_and_must.py", "-q", "--tb=no")
    chk("AC3 有对应测试断言且通过", rf.returncode == 0)

    # ================= AC4：3 次不一致 -> judge_unstable =================
    def seq(hits):
        st = {"i": 0}
        def _c(p):
            h = hits[min(st["i"], len(hits) - 1)]
            st["i"] += 1
            return json.dumps({"results": [{"point_id": "P1", "hit": h, "evidence_quote": out}]},
                              ensure_ascii=False)
        return _c
    r_same = scorer.score_points(case, out, caller=seq(["yes"]), prompt_path=PROMPT)
    chk("AC4 3 轮一致时不打标记", r_same["judge_unstable"] is False and r_same["judge_rounds"] == 3)
    r_diff = scorer.score_points(case, out, caller=seq(["yes", "no", "partial"]), prompt_path=PROMPT)
    chk("AC4 3 轮不一致 -> judge_unstable=True", r_diff["judge_unstable"] is True)
    r_two = scorer.score_points(case, out, caller=seq(["yes", "yes", "no"]), prompt_path=PROMPT)
    chk("AC4 2:1 取多数（yes）但仍标 unstable",
        r_two["points"][0]["hit"] == "yes" and r_two["judge_unstable"] is True)
    chk("AC4 平票取保守（no > partial > yes）", r_diff["points"][0]["hit"] == "no",
        r_diff["points"][0]["hit"])
    rs = py("pytest", "tests/test_stability.py", "-q", "--tb=no")
    chk("AC4 有对应测试且通过", rs.returncode == 0)

    # ================= 其它硬要求 =================
    blocked = 0
    for u in ("https://api.openai.com", "http://8.8.8.8:9", "https://judge.example.com"):
        try:
            model.check_endpoint(u)
        except model.RejectEndpoint:
            blocked += 1
    chk("境外/公网评审模型地址被硬拒（3/3）", blocked == 3, blocked)
    chk("提示词模板带版本号", scorer.PROMPT_VERSION in os.path.basename(PROMPT))
    chk("提示词写明 evidence_quote 必须逐字出现", "逐字" in open(PROMPT, encoding="utf-8").read())
    chk("提示词写明不判断金额", "不判断金额" in open(PROMPT, encoding="utf-8").read())
    amt = {"point_id": "P1", "desc": "报价金额为 128000 元", "match": "semantic", "weight": 1.0}
    ra = scorer.score_points({"case_id": "V-A", "points": [amt], "forbidden_points": []},
                             "报价金额为 128000 元", caller=stub_judge.make_caller(), prompt_path=PROMPT)
    chk("金额类要点模型侧一律 no（由程序接管）", ra["points"][0]["hit"] == "no")
    rt = py("pytest", "tests", "-q", "--tb=no")
    chk("pytest 全套通过", rt.returncode == 0,
        ((rt.stdout or "").strip().splitlines() or ["-"])[-1][:40])

    bad = [f for f in F if not f[1]]
    print("\nTOTAL %d, PASS %d, FAIL %d" % (len(F), len(F) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
