# -*- coding: utf-8 -*-
"""变异自检：故意改坏 N 处，每处都必须让 verify_2023.py 变红（rc!=0）。

判据：① 锚点必须命中——找不到要改的片段就报「变异本身失效」，不得安静通过；
      ② 原件必须通过——变异前先跑一次 verify 确认 rc=0。
产物：MUTATION.txt
"""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
SKIP = {"__pycache__", ".pytest_cache", "reports"}


def rm_tree(path):
    """递归删除（不用 shutil 的递归接口，避免误删风险）。"""
    if not os.path.isdir(path):
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            os.remove(os.path.join(root, f))
        for d in dirs:
            os.rmdir(os.path.join(root, d))
    os.rmdir(path)


def copy_tree(dst):
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in SKIP]
        rel = os.path.relpath(root, HERE)
        t = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(t, exist_ok=True)
        for f in files:
            if f.endswith(".pyc"):
                continue
            shutil.copy2(os.path.join(root, f), os.path.join(t, f))


def load(work):
    p = os.path.join(work, "data", "cases.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def save(work, rows):
    p = os.path.join(work, "data", "cases.jsonl")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def run_verify(work):
    r = subprocess.run([PY, "verify_2023.py"], cwd=work, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1200)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


MUTS = [
    ("M1 删掉一条用例", "data/cases.jsonl", None, "drop_last_line", "恰有 40 条"),
    ("M2 gold 多塞一个字段", "data/cases.jsonl", None, "add_extra_gold", "15 个字段"),
    ("M3 扫描件与文字PDF互换文件", "data/cases.jsonl", None, "swap_files", "扫描件无文字层"),
    ("M4 载体声明改成 text_pdf 但文件仍是 docx", "data/cases.jsonl", None, "wrong_carrier", "格式与 carrier 声明一致"),
    ("M5 清空一条疑难的难度说明", "data/cases.jsonl", None, "clear_difficulty", "疑难类型齐全"),
    ("M6 改掉一个信用代码的区划码", "data/cases.jsonl", None, "break_code", "999999"),
    ("M7 召回分母改成全部字段", "doc_eval/metrics.py",
     "wrong, wrong_flagged = [], []", "recall_denominator", "口径写死"),
    ("M8 runner 关闭自检标红", "doc_eval/__main__.py",
     "flagged = self_check(pred, cand, text) if not break_flag else set()", "no_flag", "critical"),
    ("M9 报告删掉「错而未标红明细」小节", "doc_eval/__main__.py",
     "## 四、错而未标红明细（单列，供人工复核）", "drop_section", "错而未标红明细"),
    ("M10 把一条疑难降级成生成用例", "data/cases.jsonl", None, "downgrade_kind", "生成 28 / 疑难 12"),
]


def apply(work, fname, anchor, kind):
    """应用一处变异；锚点找不到时抛 AssertionError（=变异失效）。"""
    if kind in ("drop_last_line", "add_extra_gold", "wrong_carrier", "clear_difficulty",
                "break_code", "downgrade_kind", "swap_files"):
        rows = load(work)
        if kind == "drop_last_line":
            assert rows, "用例为空"
            rows.pop()
        elif kind == "add_extra_gold":
            rows[0]["gold"]["内部备注"] = "不该出现在标准答案里"
        elif kind == "wrong_carrier":
            c = [r for r in rows if r["carrier"] == "docx"][0]
            c["carrier"] = "text_pdf"
        elif kind == "clear_difficulty":
            c = [r for r in rows if r["kind"] == "difficult"][0]
            c["meta"]["difficulty"]["name"] = ""
        elif kind == "break_code":
            v = rows[0]["gold"]["party_a_code"]
            assert len(v) == 18, "代码长度不对，变异无从下手"
            rows[0]["gold"]["party_a_code"] = v[:2] + "123456" + v[8:]
        elif kind == "downgrade_kind":
            c = [r for r in rows if r["kind"] == "difficult"][0]
            c["kind"] = "generated"
        elif kind == "swap_files":
            a = [r for r in rows if r["carrier"] == "text_pdf"][0]
            b = [r for r in rows if r["carrier"] == "scanned_pdf"][0]
            pa = os.path.join(work, a["file"].replace("/", os.sep))
            pb = os.path.join(work, b["file"].replace("/", os.sep))
            da, db = open(pa, "rb").read(), open(pb, "rb").read()
            open(pa, "wb").write(db)
            open(pb, "wb").write(da)
        save(work, rows)
        return True
    p = os.path.join(work, fname.replace("/", os.sep))
    s = open(p, encoding="utf-8").read()
    if anchor not in s:
        raise AssertionError("锚点未命中：%r 不在 %s 里（变异本身失效）" % (anchor[:40], fname))
    if kind == "recall_denominator":
        # 变异：把所有字段都算进召回分母（正确字段也当错误），召回会被稀释
        s = s.replace(anchor, "wrong, wrong_flagged = list(gold.keys()), []\n    _unused = []", 1)
    elif kind == "no_flag":
        s = s.replace(anchor, "flagged = set()", 1)
    elif kind == "drop_section":
        s = s.replace(anchor, "## 四、明细（变异：小节标题被删）", 1)
    open(p, "w", encoding="utf-8").write(s)
    return True


def main():
    out = []
    base_rc, _ = run_verify(HERE)
    out.append("原件 verify: rc=%d %s" % (base_rc, "OK" if base_rc == 0 else "FAIL"))
    print(out[-1])
    if base_rc != 0:
        print("原件不通过，变异自检无意义")
        return 2
    caught = missed = invalid = 0
    for name, fname, anchor, kind, expect in MUTS:
        tmp = tempfile.mkdtemp(prefix="mut_")
        work = os.path.join(tmp, "p")
        copy_tree(work)
        try:
            apply(work, fname, anchor, kind)
        except AssertionError as e:
            invalid += 1
            line = "%-40s [INVALID] %s" % (name, e)
            out.append(line); print(line)
            rm_tree(tmp)
            continue
        rc, o = run_verify(work)
        hit = (rc != 0) and (expect in o)
        if hit:
            caught += 1
        else:
            missed += 1
        line = "%-40s %s rc=%d 期望命中=%r" % (name, "[CAUGHT]" if hit else "[MISSED]", rc, expect)
        out.append(line); print(line)
        rm_tree(tmp)
    total = len(MUTS)
    out.append("")
    out.append("变异 %d 个：CAUGHT %d，MISSED %d，INVALID %d" % (total, caught, missed, invalid))
    out.append("结论：%s" % ("全部被抓住，断言有效" if caught == total else "存在漏抓或失效变异，断言需加强"))
    open(os.path.join(HERE, "MUTATION.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print(out[-2]); print(out[-1])
    return 0 if caught == total else 1


if __name__ == "__main__":
    sys.exit(main())
