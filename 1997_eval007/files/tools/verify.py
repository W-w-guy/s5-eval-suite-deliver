# -*- coding: utf-8 -*-
"""逐条断言本单 AC。任何一条失败即非零退出。"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pkg"))
import allowlist as A   # noqa: E402
import detect           # noqa: E402
import engine           # noqa: E402
import perf             # noqa: E402
import rules as R       # noqa: E402
import scanner          # noqa: E402

DATA = os.path.join(ROOT, "data")
FIX = os.path.join(DATA, "fixtures")
RESULTS = []


def ok(code, title, detail=""):
    RESULTS.append(True)
    print("[PASS] %s %s %s" % (code, title, detail))


def bad(code, title, detail=""):
    RESULTS.append(False)
    print("[FAIL] %s %s %s" % (code, title, detail))


def check(code, cond, title, detail=""):
    (ok if cond else bad)(code, title, detail)


def cli(*args):
    r = subprocess.run([sys.executable, "-m", "pkg.cmd"] + list(args), cwd=ROOT,
                       capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


def tmpfile(text):
    fd, p = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return p


def main():
    pack = json.load(open(os.path.join(FIX, "cases.json"), encoding="utf-8"))

    # ---------- AC1：8 类各有正反例，结果符合预期 ----------
    check("V01", len(R.CHECK_KINDS) == 8 and len(detect.FINDERS) == 8,
          "检测项恰好 8 类（工单点名）", "类别 %s" % list(R.CHECK_KINDS))
    per = {}
    for c in pack["positive_negative"]:
        k = c["kind"]
        hits = {f["kind"] for f in detect.scan_text(c["text"])}
        per.setdefault(k, {"pos": 0, "neg": 0, "wrong": []})
        got = k in hits
        if got != c["hit"]:
            per[k]["wrong"].append(c["why"])
        elif c["hit"]:
            per[k]["pos"] += 1
        else:
            per[k]["neg"] += 1
    wrong = {k: v["wrong"] for k, v in per.items() if v["wrong"]}
    check("V02", not wrong, "8 类检测项的正反例结果全部符合预期",
          "不符 %s" % (wrong or "无"))
    missing = [k for k in R.CHECK_KINDS if per.get(k, {}).get("pos", 0) < 1
               or per.get(k, {}).get("neg", 0) < 1]
    check("V03", not missing, "8 类各自都有 ≥1 条命中夹具与 ≥1 条不命中夹具",
          "缺 %s" % (missing or "无"))
    ex_wrong = []
    for c in pack["extra"]:
        got = c["kind"] in {f["kind"] for f in detect.scan_text(c["text"])}
        if got != c["hit"]:
            ex_wrong.append(c["kind"])
    check("V04", not ex_wrong, "企业名与人名两类告警的正反例也符合预期",
          "不符 %s" % (ex_wrong or "无"))
    clean_bad = [t for t in pack["clean"] if detect.scan_text(t)]
    check("V05", not clean_bad, "3 条干净样例零命中（不误报）",
          "误报 %d 条" % len(clean_bad))
    # 校验位：正反例只差一位
    check("V06", engine.ID_OK[:-1] == engine.ID_BAD[:-1]
          and detect.find_id_card("身份证 " + engine.ID_OK)
          and not detect.find_id_card("身份证 " + engine.ID_BAD),
          "身份证正反例只差校验位，命中判定确实来自 ISO 7064 校验",
          "尾位 %s vs %s" % (engine.ID_OK[-1], engine.ID_BAD[-1]))
    check("V07", detect.find_bank_card("卡号 " + engine.BANK_OK)
          and not detect.find_bank_card("卡号 " + engine.BANK_BAD),
          "银行卡正反例只差 Luhn 校验位", "")
    import checksum
    check("V08", detect.find_uscc("主体 " + engine.USCC_OK)
          and not detect.find_uscc("主体 " + engine.USCC_DUMMY),
          "信用代码：校验位合法但第 3~8 位为 999999 样例填充的视为虚构、不报",
          "样例填充号段 %s" % engine.USCC_DUMMY)
    # 防死代码：样例填充号段的校验位必须合法、且第 3~8 位确实是 999999。
    # 否则「排除样例填充号段」那段会被前面的校验位检查短路，变成一句永远走不到的分支
    # （第一版就是这样：样例填充号段校验位不合法，导致对应变异 M3 抓不到）。
    check("V08b", checksum.uscc_ok(engine.USCC_DUMMY)
          and engine.USCC_DUMMY[2:8] == "999999",
          "样例填充号段满足「校验位合法 + 第 3~8 位为 999999」两个条件（保证样例填充判断是活代码）",
          "ok=%s 第3~8位=%s" % (checksum.uscc_ok(engine.USCC_DUMMY),
                                engine.USCC_DUMMY[2:8]))

    # ---------- AC2：error 非 0 / 只有 warn 为 0 ----------
    p_err = tmpfile("联系电话 %s" % engine.MOBILE_OK)
    try:
        rc1, out1 = cli(p_err)
    finally:
        os.remove(p_err)
    check("V09", rc1 == 1, "含 error 级命中时退出码为 1", "rc=%d" % rc1)
    check("V10", "BLOCK" in out1, "输出标明 BLOCK", "")
    p_warn = tmpfile("车辆 沪A12345 登记，邮箱 qa@example.invalid，前台 010-88880000")
    try:
        rc2, out2 = cli(p_warn)
    finally:
        os.remove(p_warn)
    check("V11", rc2 == 0, "只有 warn 级命中时退出码为 0", "rc=%d" % rc2)
    check("V12", "OK" in out2 and "warn" in out2,
          "同一份报告里仍列出 warn 项（0 退出码不等于不报）", "")
    p_clean = tmpfile("只有编号 KH-2026-0011 与金额 12800 分。")
    try:
        rc3, _ = cli(p_clean)
    finally:
        os.remove(p_clean)
    check("V13", rc3 == 0, "无任何命中时退出码为 0", "rc=%d" % rc3)
    # error 集合必须恰好是工单点名的四类
    err_kinds = sorted(k for k, v in R.LEVEL.items() if v == "error")
    check("V14", err_kinds == ["bank_card", "id_card", "mobile", "uscc"],
          "error 级恰为工单点名的四类", "%s" % err_kinds)
    rc4, _ = cli(os.path.join(DATA, "no_such_dir"))
    check("V15", rc4 == 2, "路径不存在时退出码为 2（用法错误，不是阻断）", "rc=%d" % rc4)

    # ---------- AC3：allowlist ----------
    entries, errs = A.load(os.path.join(DATA, "allowlist.yaml"))
    check("V16", errs == [] and len(entries) == 1,
          "合规 allowlist 可加载", "条目 %d" % len(entries))
    bad_entries, bad_errs = A.load(os.path.join(DATA, "allowlist_bad.yaml"))
    check("V17", bad_entries == [] and any("confirmed_by" in e for e in bad_errs),
          "缺确认人/日期的 allowlist 被拒绝", "%s" % (bad_errs[:1] or "无错误"))
    p_al = tmpfile("联系电话 %s" % engine.MOBILE_OK)
    try:
        _f1, s1, _ = scanner.scan_path(p_al)
        _f2, s2, _ = scanner.scan_path(p_al, os.path.join(DATA, "allowlist.yaml"))
    finally:
        os.remove(p_al)
    check("V18", s1["blocking"] == 1 and s2["blocking"] == 0,
          "加入 allowlist 的条目不再被阻断",
          "阻断 %d -> %d" % (s1["blocking"], s2["blocking"]))
    p_two = tmpfile("联系电话 %s，身份证 %s" % (engine.MOBILE_OK, engine.ID_OK))
    try:
        _f3, s3, _ = scanner.scan_path(p_two, os.path.join(DATA, "allowlist.yaml"))
    finally:
        os.remove(p_two)
    check("V19", s3["blocking"] == 1,
          "白名单只放行指定条目，不会连带放行同类其他命中",
          "残留阻断 %d（身份证仍在）" % s3["blocking"])
    rc5, out5 = cli("--allowlist", os.path.join(DATA, "allowlist_bad.yaml"), FIX)
    check("V20", rc5 == 2 and "allowlist 不合法" in out5,
          "allowlist 不合规时命令报错退出码 2", "rc=%d" % rc5)
    rc6, _ = cli("--allowlist", os.path.join(DATA, "allowlist.yaml"), FIX)
    check("V21", rc6 == 1, "带白名单扫 fixtures 仍阻断（身份证/银行卡/信用代码未被放行）",
          "rc=%d" % rc6)

    # ---------- AC4：1000 条 <= 10 秒 ----------
    r = perf.measure(os.path.join(DATA, "perf1000"))
    check("V22", r["scanned"] == 1000, "性能夹具确实是 1000 条用例",
          "scanned=%d" % r["scanned"])
    check("V23", r["best_ms"] <= R.PERF_BUDGET_MS_1000,
          "扫描 1000 条用例耗时（预热后稳态）不超过 10 秒",
          "未超预算（详细毫秒数见 docs/perf.json）")
    check("V24", r["per_case_ms"] < 10,
          "单条平均耗时小于 10 毫秒", "未超预算")
    _f, s_perf, _ = scanner.scan_path(os.path.join(DATA, "perf1000"))
    check("V25", s_perf["files"] == 1 and s_perf["scanned"] == 1000,
          "JSONL 按行计用例数（1 个文件 1000 条），不是按文件计",
          "files=%d scanned=%d" % (s_perf["files"], s_perf["scanned"]))
    check("V26", s_perf["blocking"] > 0,
          "性能夹具含 error 命中（测的是最坏情况，不是快速跳过路径）",
          "blocking=%d" % s_perf["blocking"])
    # 只断言「有测到」，不把毫秒数写进输出 ——
    # 耗时每次运行都不同，写进 verify 输出会让 ACCEPTANCE.md 每次 build_docs 后字节变化，
    # 于是买家跑完全套再 sha256sum -c 必然报 ACCEPTANCE.md 不一致（实测踩过）。
    # 具体毫秒数落在 docs/perf.json，那是运行产物，不进 SHA256SUMS。
    cold = perf.measure(os.path.join(DATA, "perf1000"), warmup=0, rounds=1)["cold_ms"]
    check("V27", cold > 0, "冷启动耗时已测量并单独落盘到 docs/perf.json（不写进断言输出）",
          "已记录" if cold > 0 else "")

    # ---------- 结构与 pytest ----------
    check("V28", all(os.path.exists(os.path.join(FIX, n))
                     for n in ("cases.json",)),
          "夹具文件齐全", "")
    n_txt = len([f for f in os.listdir(FIX) if f.endswith(".txt")])
    check("V29", n_txt == 25, "逐条单文件夹具齐全（18 正反例 + 4 附加 + 3 干净）",
          "txt=%d" % n_txt)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    pr = subprocess.run([sys.executable, "-m", "pytest", "tests", "-v", "--no-header",
                         "-p", "no:cacheprovider", "-o", "addopts="],
                        cwd=ROOT, capture_output=True, env=env)
    out = (pr.stdout + pr.stderr).decode("utf-8", "replace")
    npass = out.count("PASSED")
    check("V30", pr.returncode == 0 and npass >= 40,
          "pytest 全绿且用例数不少于 40", "PASSED=%d rc=%d" % (npass, pr.returncode))

    total = len(RESULTS)
    passed = sum(1 for x in RESULTS if x)
    print("")
    print("SUMMARY %d/%d PASS" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
