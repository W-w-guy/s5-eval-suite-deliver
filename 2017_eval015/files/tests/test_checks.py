# -*- coding: utf-8 -*-
"""AC2：金句逐字检查与时间戳单调检查对**正反夹具**判断正确。

关键是「正反都要测」：只测通过，等于没测。
"""
import pytest

from ip_eval import checks as C

TRANSCRIPT = """[00:00] 主持人：欢迎收听。
[00:35] 张維：创业第一年最重要的不是找到方向，而是找到愿意为你的方向付钱的人。
[03:20] 张維：我们花了两年才明白，客户不是被说服的，是被验证的。
"""

# ---------- 金句 ----------
def test_quotes_positive():
    r = C.check_quotes(["创业第一年最重要的不是找到方向，而是找到愿意为你的方向付钱的人。"], TRANSCRIPT)
    assert r["ok"] and not r["bad"]


def test_quotes_negative_paraphrase():
    """把「愿意为你的方向付钱」改成「愿意买你的东西」-> 逐字检查必须判失败。"""
    r = C.check_quotes(["创业第一年最重要的不是找到方向，而是愿意买你的东西的人。"], TRANSCRIPT)
    assert not r["ok"] and r["bad"]


def test_quotes_negative_one_char_changed():
    r = C.check_quotes(["我们花了两年才明白，客户不是被说服的，是被证实的。"], TRANSCRIPT)
    assert not r["ok"]


def test_quotes_ignores_whitespace():
    r = C.check_quotes(["我们花了两年才明白， 客户不是被说服的，是被验证的。"], TRANSCRIPT)
    assert r["ok"]


def test_quotes_empty_is_bad():
    assert not C.check_quotes([""], TRANSCRIPT)["ok"]


# ---------- 时间戳 ----------
def test_timestamps_positive():
    r = C.check_timestamps(["00:00", "00:35", "03:20"], duration_sec=600)
    assert r["ok"], r


def test_timestamps_negative_not_monotonic():
    r = C.check_timestamps(["00:00", "03:20", "00:35"], duration_sec=600)
    assert not r["ok"] and any("单调" in p for p in r["problems"])


def test_timestamps_negative_over_duration():
    r = C.check_timestamps(["00:00", "20:00"], duration_sec=600)
    assert not r["ok"] and any("超过总时长" in p for p in r["problems"])


def test_timestamps_negative_duplicate():
    r = C.check_timestamps(["00:00", "00:00"], duration_sec=600)
    assert not r["ok"] and any("重复" in p for p in r["problems"])


def test_timestamps_negative_unparseable():
    r = C.check_timestamps(["abc"], duration_sec=600)
    assert not r["ok"] and any("无法解析" in p for p in r["problems"])


def test_timestamps_accepts_dict_sections():
    """章节对象 {"ts": "03:20"} 也要能解析 —— 初版只处理字符串，导致摘要用例全判失败。"""
    r = C.check_timestamps([{"ts": "00:00", "title": "a"}, {"ts": "03:20", "title": "b"}],
                           duration_sec=600)
    assert r["ok"], r


def test_timestamps_accepts_int_seconds():
    assert C.check_timestamps([0, 200, 400], duration_sec=600)["ok"]


# ---------- 摘要数字 ----------
def test_summary_numbers_positive():
    r = C.check_summary_numbers("团队从 3 人扩到 120 人，用了 2 年。", "团队从 3 人扩到 120 人，用了 2 年。")
    assert r["ok"]


def test_summary_numbers_negative():
    r = C.check_summary_numbers("规模增长 999999 倍。", TRANSCRIPT)
    assert not r["ok"] and "999999" in r["bad"]


def test_summary_numbers_no_numbers_is_ok():
    assert C.check_summary_numbers("没有数字的摘要。", TRANSCRIPT)["ok"]


# ---------- 提纲 ----------
CASE = {"off_limit_topic": "正在进行的融资细节"}


def test_outline_positive():
    out = {"opening": "欢迎张維。",
           "sections": [{"title": "起步", "followups": ["a", "b"]},
                        {"title": "坑", "followups": ["c", "d"]},
                        {"title": "方法", "followups": ["e", "f"]}]}
    assert C.check_outline_output(CASE, out)["ok"]


def test_outline_negative_off_limit():
    out = {"opening": "欢迎。",
           "sections": [{"title": "正在进行的融资细节", "followups": ["a", "b"]},
                        {"title": "坑", "followups": ["c", "d"]},
                        {"title": "方法", "followups": ["e", "f"]}]}
    r = C.check_outline_output(CASE, out)
    assert not r["ok"] and any("不谈话题" in p for p in r["problems"])


def test_outline_negative_wrong_section_count():
    out = {"opening": "x", "sections": [{"title": "a", "followups": ["1", "2"]}]}
    r = C.check_outline_output(CASE, out)
    assert not r["ok"] and any("3–5" in p for p in r["problems"])


def test_outline_negative_followups_not_two():
    out = {"opening": "x", "sections": [{"title": "a", "followups": ["1"]},
                                        {"title": "b", "followups": ["1", "2"]},
                                        {"title": "c", "followups": ["1", "2"]}]}
    r = C.check_outline_output(CASE, out)
    assert not r["ok"] and any("追问数" in p for p in r["problems"])


def test_eval_lint_catches_broken_case():
    """lint 不是恒真：结构缺失必须报错。"""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
    import eval_lint
    cases = eval_lint.load()
    bad = dict(cases[0], forbidden_points=[])
    errs, _ = eval_lint.lint([bad] + cases[1:])
    assert any("forbidden_points" in e for e in errs), errs[:3]


def test_eval_pii_scan_catches_real_email(tmp_path):
    """pii 不是恒真：文本里出现真邮箱必须被抓到（地址运行时拼接，避免自指）。"""
    import sys as _s, os as _o
    _s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.dirname(_o.path.abspath(__file__))), "tools"))
    import eval_pii_scan
    at = chr(64)
    real = "li.na" + at + "somecorp.cn"
    f = tmp_path / "leak.txt"
    f.write_text("联系人 " + real, encoding="utf-8")
    t = f.read_text(encoding="utf-8")
    hits = [m.group(0) for rx in eval_pii_scan.PAT.values() for m in rx.finditer(t)]
    hits = [h for h in hits if not any(s in h for s in eval_pii_scan.SAFE)]
    assert any("@" in h for h in hits), hits
