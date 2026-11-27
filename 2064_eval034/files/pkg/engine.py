# -*- coding: utf-8 -*-
"""虚构数据源：套件定义、基线运行、以及一组当前运行场景。

全部按下标确定性生成（前 N 个通过），无随机数。

口径（显式写死，不留默契）：
  regression = 基线通过、本次失败
  fix        = 基线失败、本次通过
  must 翻转  = 该 regression 用例里至少有一个 must 要点从 hit=True 变成 hit=False
  flaky      = regression 用例重跑 2 次中任意一次通过 -> 不计入退化，单列
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)

# ---- 默认判定规则（工单给的默认值；suite.yaml 可覆盖） ----
DEFAULT_RULES = {
    "max_pass_rate_drop_pp": 3,      # 通过率下降超过 3 个百分点 -> 失败
    "max_must_flips": 3,             # must 翻转用例数 >= 3 -> 失败
    "score_drop_warn": 0.05,         # 平均分下降超过 0.05 -> warn
    "flaky_reruns": 2,               # regression 用例重跑次数
}
SET_PERMISSION = "eval.baseline.set"
SUITE = "kb_qa"
V1 = "v1"
V2 = "v2"
TAGS = ("extraction", "reasoning", "format")

BASE_PASSED = 115          # 基线 115/125 = 92.0000%
BASE_TOTAL = 125


def _points(i, passed, must_follows=True):
    """每个用例三个要点；第 2 个是 must。

    must 要点的命中与「用例是否通过」是**解耦**的：只有每第 3 条（i % 3 == 0）的
    must 才跟随 passed，其余用例即使判定失败，must 要点本身也仍是命中的
    —— 真实评测里用例失败常因非 must 要点失分。这样「通过率降幅」与「must 翻转」
    是两条独立的判据，用一个场景失败不会同时触发另一条（否则无法区分是哪条起作用）。
    """
    must_hit = bool(passed) if (must_follows and i % 3 == 0) else True
    return [
        {"key": "cite", "must": False, "hit": True},
        {"key": "answer", "must": True, "hit": must_hit},
        {"key": "format", "must": False, "hit": True},
    ]


def _cases(total, n_pass, prefix="KB", version_extra_tag=None):
    out = []
    for i in range(1, total + 1):
        passed = i <= n_pass
        out.append({
            "case_key": "%s-%03d" % (prefix, i),
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "tags": [TAGS[i % len(TAGS)]],
            "points": _points(i, passed),
        })
    return out


def baseline_run():
    return {"run_id": "BASE_V1", "suite": SUITE, "suite_version": V1,
            "status": "completed", "errors": [], "started_at": "2026-11-20T02:00:00Z",
            "cases": _cases(BASE_TOTAL, BASE_PASSED)}


def cur_drop4():
    """AC1 失败侧：111/125 = 88.8%? 不 —— 用 172/200 太散，改为 110/125 = 88%。
    115 -> 110 差 5 条；通过率 88.0000%，降 4.0000pp > 3 -> 失败。"""
    return {"run_id": "CUR_DROP4", "suite": SUITE, "suite_version": V1,
            "status": "completed", "errors": [], "started_at": "2026-11-26T02:00:00Z",
            "cases": _cases(BASE_TOTAL, 110)}


def cur_drop2():
    """AC1 通过侧：113/125 = 90.4000%，降 1.6000pp <= 3 -> 通过。"""
    return {"run_id": "CUR_DROP2", "suite": SUITE, "suite_version": V1,
            "status": "completed", "errors": [], "started_at": "2026-11-26T02:00:00Z",
            "cases": _cases(BASE_TOTAL, 113)}


def cur_round():
    """取整探针：111/125 = 88.8000%，基线 92.0000%，降 3.2000pp。

    3.2 > 3 应判失败；若实现写成 round(drop) 会得 3，3 > 3 为假 -> 假通过。
    """
    return {"run_id": "CUR_ROUND", "suite": SUITE, "suite_version": V1,
            "status": "completed", "errors": [], "started_at": "2026-11-26T02:00:00Z",
            "cases": _cases(BASE_TOTAL, 111)}


def cur_mustflip():
    """独立验证 must 翻转判据：通过率不降（drop=0），但有 3 条 must 翻转 -> 失败。

    翻转取 KB-105 / KB-111 / KB-114（基线里都通过，且都满足 i % 3 == 0，must 跟随 passed），
    再把 3 条原本失败的改成通过，使通过率仍为 115/125 = 92%。
    """
    cur_cases = _cases(BASE_TOTAL, BASE_PASSED)
    flip = {"KB-105", "KB-111", "KB-114"}
    for c in cur_cases:
        if c["case_key"] in flip:
            c["passed"] = False
            c["score"] = 0.0
            c["points"] = _points(int(c["case_key"].split("-")[1]), False)
    fill = [c for c in cur_cases if not c["passed"] and c["case_key"] not in flip]
    for c in fill[:3]:
        c["passed"] = True
        c["score"] = 1.0
        c["points"] = _points(int(c["case_key"].split("-")[1]), True)
    return {"run_id": "CUR_MUSTFLIP", "suite": SUITE, "suite_version": V1,
            "status": "completed", "errors": [], "started_at": "2026-11-26T02:00:00Z",
            "cases": cur_cases}


def cur_better():
    """优于基线：120/125 = 96.0000%。"""
    return {"run_id": "CUR_BETTER", "suite": SUITE, "suite_version": V1,
            "status": "completed", "errors": [], "started_at": "2026-11-26T02:00:00Z",
            "cases": _cases(BASE_TOTAL, 120)}


def _flaky_cases():
    """AC2：3 个 regression 用例都含 must 要点翻转，重跑后 2 个通过 -> flaky。

    构造：基线通过 KB-001..115；本次把 KB-113/114/115 改为失败（真 regression），
    再把原本失败的 KB-116/117 改为通过（fix），通过率 114/125 = 91.2%，
    比基线 92% 只降 0.8pp —— 所以「不判失败」只能来自 must 翻转数从 3 降到 1。
    """
    cur_cases = _cases(BASE_TOTAL, BASE_PASSED)
    flip = {"KB-113", "KB-114", "KB-115"}
    fix = {"KB-116", "KB-117"}
    for c in cur_cases:
        if c["case_key"] in flip:
            c["passed"] = False
            c["score"] = 0.0
            c["points"] = _points(0, False)
        elif c["case_key"] in fix:
            c["passed"] = True
            c["score"] = 1.0
            c["points"] = _points(0, True)
    return {"run_id": "CUR_FLAKY", "suite": SUITE, "suite_version": V1,
            "status": "completed", "errors": [], "started_at": "2026-11-26T02:00:00Z",
            "cases": cur_cases, "reruns": {
                "KB-113": [False, True],     # 重跑 2 次有 1 次通过 -> flaky
                "KB-114": [True, False],     # 同上 -> flaky
                "KB-115": [False, False],    # 两次都失败 -> 真 regression
            }}


def cur_ver_diff():
    """AC3：suite_version 不同（v2），删掉 12 条、新增 10 条 -> 只比共有的 113 条。"""
    cur = _cases(BASE_TOTAL, 112)
    kept = [c for c in cur if c["case_key"] not in
            {"KB-%03d" % i for i in range(114, 126)}]           # 删除 12 条
    for i in range(1, 11):                                       # 新增 10 条
        kept.append({"case_key": "KB-NEW-%02d" % i, "passed": False, "score": 0.0,
                     "tags": ["extraction"], "points": _points(0, False)})
    return {"run_id": "CUR_VER_DIFF", "suite": SUITE, "suite_version": V2,
            "status": "completed", "errors": [], "started_at": "2026-11-26T02:00:00Z",
            "cases": kept}


def run_error_status():
    """AC4 之一：status=failed 的运行不能当基线。"""
    r = baseline_run()
    r.update({"run_id": "BASE_FAILED", "status": "failed"})
    return r


def run_error_errors():
    """AC4 之二：status=completed 但 errors 非空也不能当基线。"""
    r = baseline_run()
    r.update({"run_id": "BASE_WITH_ERRORS", "errors": ["3 条用例执行异常"]})
    return r


def run_ver_diff_base():
    """基线本身是 v2，用于反向验证 AC3。"""
    r = baseline_run()
    r.update({"run_id": "BASE_V2", "suite_version": V2})
    return r


SCENARIOS = [
    ("CUR_DROP4", cur_drop4, "fail", "通过率降 4.0000pp > 3（AC1 失败侧）"),
    ("CUR_DROP2", cur_drop2, "pass", "通过率降 1.6000pp <= 3（AC1 通过侧）"),
    ("CUR_ROUND", cur_round, "fail", "降 3.2000pp（取整探针，round 成 3 会假通过）"),
    ("CUR_MUSTFLIP", cur_mustflip, "fail", "通过率不降但 must 翻转 3 条（独立验证 must 判据）"),
    ("CUR_FLAKY", _flaky_cases, "pass", "3 条翻转中 2 条 flaky，有效 must 翻转 1 < 3（AC2）"),
    ("CUR_VER_DIFF", cur_ver_diff, "pass", "v2 与 v1 只比共有用例（AC3）"),
    ("CUR_BETTER", cur_better, "pass", "优于基线"),
    ("BASE_FAILED", run_error_status, "error", "status=failed 不可作基线（AC4）"),
    ("BASE_WITH_ERRORS", run_error_errors, "error", "errors 非空不可作基线（AC4）"),
]

SUITE_YAML = """# 能力类回归套件配置（虚构；护栏类判定由 EVAL-031 负责）
suite:
  name: kb_qa
  version: v1
  note: "知识问答能力回归，三档 tag：extraction / reasoning / format"
baseline_rules:
  max_pass_rate_drop_pp: 3
  max_must_flips: 3
  score_drop_warn: 0.05
  flaky_reruns: 2
suggest_update:
  consecutive_better_runs: 3
  auto_update: false
"""


def write_all(outdir=None):
    out = outdir or os.path.join(ROOT, "data")
    os.makedirs(os.path.join(out, "runs"), exist_ok=True)
    os.makedirs(os.path.join(out, "baselines"), exist_ok=True)
    n = 0
    for name, fn, _k, _w in SCENARIOS:
        r = fn()
        r.pop("_base_for_reference", None)
        with open(os.path.join(out, "runs", name + ".json"), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(r, f, ensure_ascii=False, indent=1, sort_keys=True)
        n += len(r["cases"])
    b = baseline_run()
    with open(os.path.join(out, "runs", "BASE_V1.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(b, f, ensure_ascii=False, indent=1, sort_keys=True)
    with open(os.path.join(out, "suite.yaml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(SUITE_YAML)
    with open(os.path.join(out, "baselines", "kb_qa.yaml"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("suite: kb_qa\nbaseline_run: BASE_V1\nreason: \"首版基线\"\n"
                "set_by: \"质量负责人\"\nset_at: \"2026-11-20\"\n")
    return len(SCENARIOS), n


if __name__ == "__main__":
    a, b = write_all()
    print("WROTE runs=%d cases=%d" % (a, b))
