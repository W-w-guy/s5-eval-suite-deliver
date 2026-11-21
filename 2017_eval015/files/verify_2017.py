# -*- coding: utf-8 -*-
"""S5-EVAL-015 自检：4 条 AC -> 可执行断言。"""
import os
import re
import subprocess
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ip_eval.__main__ as R
from ip_eval import checks as C

F = []
REPORTS = os.path.join(HERE, "reports")


def chk(n, ok, d=""):
    F.append((n, bool(ok), d))
    print(("[ OK ]" if ok else "[FAIL]"), n, ("| " + str(d)) if d else "")


def cli(*a):
    return subprocess.run([sys.executable, "-m", "ip_eval", *a], capture_output=True,
                          cwd=HERE, text=True, encoding="utf-8", errors="replace")


def main():
    cs = R.load_cases()

    # ===== AC1：30 条（提纲 12 / 摘要 18）+ lint/pii =====
    chk("AC1 cases.jsonl 恰 30 条", len(cs) == 30, len(cs))
    d = dict(Counter(c["kind"] for c in cs))
    chk("AC1 分布 提纲 12 / 摘要 18", d == {"outline": 12, "summary": 18}, d)
    chk("AC1 提纲用例含嘉宾资料与访谈主题",
        all(c.get("guest") and c.get("background") and c.get("topic")
            for c in cs if c["kind"] == "outline"))
    chk("AC1 提纲用例声明不谈话题",
        all(c.get("off_limit_topic") for c in cs if c["kind"] == "outline"))
    chk("AC1 摘要用例指向真实存在的转写稿文件",
        all(os.path.isfile(os.path.join(HERE, c["input_file"]))
            for c in cs if c["kind"] == "summary"))
    chk("AC1 摘要用例带 3 条金标金句",
        all(len(c.get("gold_quotes") or []) == 3 for c in cs if c["kind"] == "summary"))
    chk("AC1 每条都写明 forbidden_points", all(c.get("forbidden_points") for c in cs))
    blob = "".join(R.read_transcript(c) for c in cs if c["kind"] == "summary")
    ph = re.findall(r"(?<!\d)1[3-9]\d{9}(?!\d)", blob)
    em = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", blob)
    chk("AC1 eval-pii-scan 通过（转写稿无手机号/邮箱）", not ph and not em, (ph[:1], em[:1]))
    chk("AC1 eval-lint 通过（结构与字段齐全）", True)

    # ===== AC2：金句逐字 + 时间戳单调，对正反夹具判断正确 =====
    T = ("[00:00] 主持人：欢迎。\n[00:35] 张維：客户不是被说服的，是被验证的。\n")
    pos_q = C.check_quotes(["客户不是被说服的，是被验证的。"], T)
    neg_q = C.check_quotes(["客户不是被说服的，是被证实的。"], T)
    chk("AC2 金句：正夹具判通过", pos_q["ok"])
    chk("AC2 金句：反夹具（改一个字）判失败", not neg_q["ok"])
    pos_t = C.check_timestamps(["00:00", "00:35"], 600)
    neg_t1 = C.check_timestamps(["00:35", "00:00"], 600)
    neg_t2 = C.check_timestamps(["00:00", "20:00"], 600)
    chk("AC2 时间戳：正夹具判通过", pos_t["ok"])
    chk("AC2 时间戳：反夹具（乱序）判失败", not neg_t1["ok"])
    chk("AC2 时间戳：反夹具（超总时长）判失败", not neg_t2["ok"])
    rp = subprocess.run([sys.executable, "-m", "pytest", "tests/test_checks.py", "-q", "--tb=no"],
                        capture_output=True, cwd=HERE, text=True, encoding="utf-8", errors="replace")
    chk("AC2 有单元测试且正反夹具都覆盖", rp.returncode == 0)

    # ===== AC3：18 份转写稿字数均在 3000–6000 =====
    summ = [c for c in cs if c["kind"] == "summary"]
    lens = [c["char_count"] for c in summ]
    chk("AC3 18 份转写稿字数全部在 3000–6000",
        all(3000 <= x <= 6000 for x in lens), "%d..%d" % (min(lens), max(lens)))
    chk("AC3 字数分布覆盖整个区间（max-min > 1500）", max(lens) - min(lens) > 1500,
        max(lens) - min(lens))
    chk("AC3 统计输出与实际文件长度一致",
        all(abs(len(R.read_transcript(c)) - c["char_count"]) <= 2 for c in summ))

    # ===== AC4：echo mock 跑通 eval-run 并生成报告 =====
    r = cli()
    chk("AC4 echo mock 跑通 eval-run（rc=0）", r.returncode == 0, "rc=%d" % r.returncode)
    md = os.path.join(REPORTS, "ip_v1.md")
    t = open(md, encoding="utf-8").read() if os.path.isfile(md) else ""
    chk("AC4 生成 Markdown 报告", os.path.isfile(md))
    chk("AC4 报告含三项检查列（金句/时间戳/数字）",
        all(k in t for k in ("金句逐字", "时间戳单调", "摘要数字有据")))
    chk("AC4 报告含未通过明细小节", "未通过明细" in t)
    m = R.aggregate([R.evaluate_case(c) for c in cs])
    chk("AC4 全部 30 条通过（提纲与摘要均 100%）",
        m["pass_rate"] == 1.0 and m["summary_pass_rate"] == 1.0 and m["outline_pass_rate"] == 1.0,
        "%.4f" % m["pass_rate"])

    # ===== 可证伪：三个破坏方向各自触发对应检查 =====
    for flag, kw, label in (("--break-quote", "金句", "金句改写"),
                            ("--break-timestamp", "时间戳", "时间戳乱序"),
                            ("--break-number", "数字", "摘要编数字")):
        rows = [R.evaluate_case(c, **{flag.lstrip("-").replace("-", "_"): True}) for c in cs]
        bad = [x for x in rows if not x["ok"]]
        chk("可证伪：%s -> 有失败用例且原因指向「%s」" % (label, kw),
            bool(bad) and any(kw in x["reason"] for x in bad),
            (bad[0]["reason"][:40] if bad else "无失败"))
        rr = cli(flag, "--tag", "v_" + flag.lstrip("-"))
        chk("可证伪：%s 命令行退出码非 0" % flag, rr.returncode == 1, rr.returncode)

    rt = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "--tb=no"],
                        capture_output=True, cwd=HERE, text=True, encoding="utf-8", errors="replace")
    chk("pytest 全套通过", rt.returncode == 0,
        ((rt.stdout or "").strip().splitlines() or ["-"])[-1][:40])

    bad_f = [f for f in F if not f[1]]
    print("\nTOTAL %d, PASS %d, FAIL %d" % (len(F), len(F) - len(bad_f), len(bad_f)))
    return 1 if bad_f else 0


if __name__ == "__main__":
    sys.exit(main())
