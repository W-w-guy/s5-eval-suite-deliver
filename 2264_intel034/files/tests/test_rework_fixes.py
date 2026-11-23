# -*- coding: utf-8 -*-
"""返工六条意见的回归测试。

每条意见对应至少一个「缺陷存在时会失败」的断言，并配一条反向验证
（把缺陷重新注入，断言必须变红），避免又写出「功能坏了也通过」的测试。
"""
import json
import os
import subprocess
import sys

import pytest

from intel_eval import extract, metrics as M, pipeline
from intel_eval.fetch import Fetcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ================= 意见 6（minor）：m01_body_similarity 的手算用例 =================
@pytest.mark.parametrize("pairs,expect", [
    # 手算：两对 -> (1.0 + 0.5) / 2 = 0.75
    #   对1 "abc"/"abc" -> LCS=3 -> 2*3/6 = 1.0
    #   对2 "abcd"/"abef" -> LCS=2 -> 2*2/(4+4) = 0.5
    ([("abc", "abc"), ("abcd", "abef")], 0.75),
    # 手算：三对 -> (1.0 + 2/3 + 0.0) / 3 = 0.5555555…
    #   对1 "ab"/"ab" -> 1.0；对2 "abc"/"abd" -> 2*2/6=2/3；对3 "abc"/"" -> 0
    ([("ab", "ab"), ("abc", "abd"), ("abc", "")], round((1.0 + 2 / 3 + 0.0) / 3, 6)),
])
def test_m01_body_similarity_average_handcalc(pairs, expect):
    """m01 是【求平均】的函数，不是 text_similarity。此前只测了后者。
    手算值写在上面的注释里，期望值与实现无关。"""
    assert M.m01_body_similarity(pairs) == expect   # m01 内部 round 到 6 位，期望值同样取 6 位


def test_m01_body_similarity_empty_and_single():
    # 空列表按定义返回 0.0（没有任何样本时不给满分，避免「没测过 = 通过」）
    assert M.m01_body_similarity([]) == 0.0
    # 单对 -> 平均值等于该对本身
    assert M.m01_body_similarity([("xyz", "xyz")]) == 1.0
    # m01 对外 round 到 6 位，期望值同样取 6 位再比（比较的是定义，不是浮点尾数）
    assert M.m01_body_similarity([("abc", "abd")]) == round(2 / 3, 6)


# ================= 意见 1（blocker）：prompt_set 必须真的进流水线 =================
def test_prompt_sets_are_distinct_strategies():
    v1, v2 = extract.prompt_set_spec("v1"), extract.prompt_set_spec("v2")
    assert v1["strategy"] != v2["strategy"], "两个版本策略相同 -> compare 必然无差异"


def test_unknown_prompt_set_raises():
    """未知版本必须报错，不能静默退回默认值 —— 否则传错版本会表现为「两版相同」。"""
    with pytest.raises(ValueError):
        extract.prompt_set_spec("no_such_version")


BODY = ("现将本批次有关事项通知如下。"
        "三、支持标准：按不超过项目实际投入 30% 的比例给予支持，单个项目最高 200 万元。"
        "四、申报截止：2026 年 4 月 20 日。")


def test_stub_model_outputs_differ_by_prompt_set():
    """同一段正文，两个版本必须给出不同摘要。"""
    a = extract.StubModel("v1").summarize(BODY)
    b = extract.StubModel("v2").summarize(BODY)
    assert a != b, "两版摘要相同 -> 版本没生效"
    assert "万元" not in a, "v1 是首句基线，不应含金额"
    assert "万元" in b, "v2 是关键事实优先，必须含金额"


def test_pipeline_carries_prompt_set():
    pl = pipeline.Pipeline(Fetcher({}), prompt_set="v2")
    assert pl.prompt_set == "v2"
    assert pl.model.spec["id"] == "v2"


def test_compare_reports_real_difference(tmp_path):
    """compare 的两份报告必须来自两次真实运行，且指标不同。"""
    env = dict(os.environ, APP_ENV="test")
    for ps in ("v1", "v2"):
        r = subprocess.run([sys.executable, "-m", "intel_eval", "run", "--prompt-set", ps],
                           capture_output=True, cwd=ROOT, text=True, encoding="utf-8",
                           errors="replace", env=env)
        assert r.returncode in (0, 1), r.stdout + r.stderr
    a = json.load(open(os.path.join(ROOT, "reports", "intel_v1.json"), encoding="utf-8"))
    b = json.load(open(os.path.join(ROOT, "reports", "intel_v2.json"), encoding="utf-8"))
    assert a["prompt_set"] == "v1" and b["prompt_set"] == "v2"
    assert a["prompt_spec"]["strategy"] != b["prompt_spec"]["strategy"]
    assert a["metrics"]["key_fact_coverage"] != b["metrics"]["key_fact_coverage"], \
        "两版关键事实覆盖率相同 -> 版本没进流水线"


# ================= 意见 2（major）：has_original_link 由页面判断 =================
def test_detect_original_link_dead():
    html = '<article><p>正文</p><p>原文链接：（链接已失效，未保留正确原文地址）</p></article>'
    has, ev = pipeline.detect_original_link(html, "正文 原文链接：（链接已失效，未保留正确原文地址）")
    assert has is False and "dead_link_field" in ev


def test_detect_original_link_live():
    html = '<article><p>正文</p><p>原文链接：<a href="http://origin.example/a.html">原文</a></p></article>'
    has, ev = pipeline.detect_original_link(html, "正文 原文链接：http://origin.example/a.html")
    assert has is True and "live_link_field" in ev


def test_detect_original_link_absent_field_means_own_article():
    """没写「原文链接」的页面按本站原文处理 —— 否则 11 篇原创稿会被全判掉。"""
    html = "<article><p>为贯彻落实示例市产业高质量发展有关部署。</p></article>"
    has, ev = pipeline.detect_original_link(html, "为贯彻落实示例市产业高质量发展有关部署。")
    assert has is True and "no_link_field" in ev


def test_detect_original_link_no_url():
    html = '<article><p>原文链接：详见纸质材料</p></article>'
    has, ev = pipeline.detect_original_link(html, "原文链接：详见纸质材料")
    assert has is False and "link_field_without_url" in ev


# ================= 意见 3（major）：m07 应标出项独立于流水线核对规则 =================
def test_m07_uses_independent_rule():
    """流水线用原始子串匹配，"150" 在 "1500 万元" 里为真 -> 漏标；
    第二套按数值 token 比对，150 != 1500 -> 应标出。指标因此能掉到 0。"""
    summary, body = "单个项目最高 150 万元。", "三、支持标准：单个项目最高 1500 万元。"
    # 流水线的核对项：认为 150 能在原文里找到，所以不标
    flagged_by_pipeline = pipeline.numeric_check_items(summary, body)
    assert flagged_by_pipeline == [], "流水线本该漏标（这是构造前提）"
    # 第二套规则认定它应被标出
    items = M.independent_mismatch_items(summary, body)
    assert any(it["raw"] == "150" for it in items), items


def test_m07_drops_below_one_when_pipeline_misses():
    """核对环节漏标时，指标必须低于 1.0（此前结构上恒为 1.0）。"""
    cases = [{"summary": "单个项目最高 150 万元。", "body": "单个项目最高 1500 万元。",
              "flagged": []}]                     # 一条都没标
    assert M.m07_numeric_mismatch_flagged(cases) == 0.0


def test_m07_full_marks_when_all_flagged():
    cases = [{"summary": "单个项目最高 150 万元。", "body": "单个项目最高 1500 万元。",
              "flagged": ["150"]}]
    assert M.m07_numeric_mismatch_flagged(cases) == 1.0


def test_m07_partial():
    """两条应标，标了一条 -> 0.5。"""
    cases = [{"summary": "最高 150 万元，比例 30%。",
              "body": "最高 1500 万元，比例 40%。", "flagged": ["150"]}]
    v = M.m07_numeric_mismatch_flagged(cases)
    assert 0.0 < v < 1.0, v


def test_m07_date_triple_tolerates_formatting():
    """日期按三元组比对：写法不同但同一天不该被算成不一致。"""
    items = M.independent_mismatch_items("截止 2026年4月20日。", "截止 2026-04-20。")
    assert items == [], items


# ================= 意见 4（major）：抓取清单来自站点发现 =================
def test_crawl_list_comes_from_discovery():
    """crawl_source 必须是 discovered，且条数与列表页发现的文章数一致。"""
    from intel_eval.__main__ import _serve_site, load_gold
    srv = _serve_site(8099)
    try:
        f = Fetcher({"gov-a.example": ("127.0.0.1", 8099)})
        pl = pipeline.Pipeline(f, prompt_set="v2")
        found = pl.discover(["http://gov-a.example/page-1.html",
                            "http://gov-a.example/page-2.html"])
        assert len(found) >= 10, found
        pl.process(load_gold(), urls=found)
        assert pl.crawl_source == "discovered"
        # 抓到的是列表页发现的 URL，不是金标原样抄的清单
        assert {e["url"] for e in pl.entries} <= set(found)
    finally:
        srv.shutdown()


def test_gold_fallback_is_marked():
    """不传发现清单时，必须把来源标成 gold_fallback，便于复核是否是「照抄金标」。"""
    from intel_eval.__main__ import _serve_site, load_gold
    srv = _serve_site(8099)
    try:
        f = Fetcher({"gov-a.example": ("127.0.0.1", 8099)})
        pl = pipeline.Pipeline(f, prompt_set="v2")
        pl.process(load_gold())
        assert pl.crawl_source == "gold_fallback"
    finally:
        srv.shutdown()


# ================= 意见 2 的端到端：m08 真的会因为丢弃逻辑失效而 > 0 =================
def test_m08_counts_dropped_entries():
    """m08 的输入含被丢弃的条目。若「无原文链接也进队列」则计数 > 0。"""
    entries = [{"has_original_link": False, "queued": True}]
    assert M.m08_no_link_into_queue(entries) == 1
    assert M.m08_no_link_into_queue([{"has_original_link": False, "queued": False}]) == 0
    assert M.m08_no_link_into_queue([{"has_original_link": True, "queued": True}]) == 0
