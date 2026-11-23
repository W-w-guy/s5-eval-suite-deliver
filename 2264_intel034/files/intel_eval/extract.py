# -*- coding: utf-8 -*-
"""正文提取与摘要生成（模型用桩）。

正文提取：标准库 HTMLParser 取 <article> 内的可见文本，丢弃 nav/header/footer/script/style。
与「黄金正文」的相似度用归一化后的字符级 LCS 比例（见 metrics.text_similarity），
不用 difflib 的 ratio 是因为它对长文本的截断不敏感 —— 会给出「看起来很高」的假分。
"""
from html.parser import HTMLParser

DROP = {"script", "style", "nav", "header", "footer", "noscript"}
# h2 是标题（金标正文不含标题），meta 行是「栏目/发布日期」，两者都不属于正文。
DROP_IN_ROOT = {"h1", "h2", "h3", "h4"}
KEEP_ROOT = "article"


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth_drop = 0
        self.depth_root = 0
        self.in_root = False
        self.parts = []
        self.meta = {}
        self.time_attr = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "meta":
            name = (d.get("name") or "").lower()
            if name in ("agency", "publish-date"):
                self.meta[name] = d.get("content") or ""
        if tag == "time" and d.get("datetime"):
            self.time_attr = d["datetime"]
        if tag in DROP or (self.depth_root and tag in DROP_IN_ROOT):
            self.depth_drop += 1
        if tag == KEEP_ROOT:
            self.in_root = True
            self.depth_root += 1

    def handle_endtag(self, tag):
        if (tag in DROP or tag in DROP_IN_ROOT) and self.depth_drop:
            self.depth_drop -= 1
        if tag == KEEP_ROOT and self.depth_root:
            self.depth_root -= 1
            if not self.depth_root:
                self.in_root = False

    def handle_data(self, data):
        if self.depth_drop:
            return
        if self.depth_root:
            s = data.strip()
            if s:
                self.parts.append(s)


def extract_body(html: str) -> dict:
    """返回 {text, meta, publish_date}。text 为空表示提取失败（不能当成「正文为空」蒙混过关）。"""
    p = _Text()
    p.feed(html)
    return {"text": "\n".join(p.parts), "meta": p.meta,
            "publish_date": p.meta.get("publish-date") or p.time_attr}


# ---------------- 提示词版本（prompt_set） ----------------
# 版本差异必须是【实质】的：不同版本真的走不同规则产出摘要，否则 compare 两版必然相同
# （返工意见 1 就是这一点：原实现只把版本号当文件名，没传进流水线）。
PROMPT_SETS = {
    "v1": {
        "id": "v1",
        "name": "首句基线版",
        "strategy": "first_sentence",
        "max_len": 150,
        "note": "取正文第一句。基线策略，不含金额/比例等关键事实。",
    },
    "v2": {
        "id": "v2",
        "name": "关键事实优先版",
        "strategy": "key_fact_first",
        "max_len": 150,
        "note": "优先取含金额/比例的关键事实句，没有则退回含截止日期的句子，再退回首句。",
    },
    # CI 用版本：策略与 v2 相同，分开命名只为让报告文件与测试产物互不覆盖
    "ci_ok": {"id": "ci_ok", "name": "CI 正常档", "strategy": "key_fact_first",
              "max_len": 150, "note": "CI 正常流程（robots 守规），策略同 v2。"},
    "ci_bad": {"id": "ci_bad", "name": "CI 故障注入档", "strategy": "key_fact_first",
               "max_len": 150, "note": "CI 故意抓 robots 禁止路径，用于证明门槛会让退出码非 0。"},
    # compare 子命令测试用的两个版本（策略不同，保证对比有实质差异）
    "cmp_a": {"id": "cmp_a", "name": "对比档 A", "strategy": "first_sentence",
              "max_len": 150, "note": "首句策略，compare 的低分一侧。"},
    "cmp_b": {"id": "cmp_b", "name": "对比档 B", "strategy": "key_fact_first",
              "max_len": 150, "note": "关键事实策略，compare 的高分一侧。"},
    # 自检脚本用的两个版本名：verify 走全门槛通过档，refuse 只用于「生产拒绝启动」（不会跑到摘要）
    "verify": {"id": "verify", "name": "自检档", "strategy": "key_fact_first",
               "max_len": 150, "note": "verify_2264.py 用，要求 11 项门槛全过。"},
    "refuse": {"id": "refuse", "name": "拒绝启动档", "strategy": "key_fact_first",
               "max_len": 150, "note": "仅用于验证生产配置下拒绝启动，不产出摘要。"},
    "bad": {"id": "bad", "name": "robots 故障注入档", "strategy": "key_fact_first",
            "max_len": 150, "note": "verify_2264.py 用：故意抓 robots 禁止路径，证明门槛让退出码非 0。"},
}


def prompt_set_spec(version: str) -> dict:
    """取提示词版本定义。未知版本直接报错 —— 不静默退回默认值，
    否则 compare 传错版本会「两版相同」，看起来像版本无差异，实为参数没生效。"""
    if version not in PROMPT_SETS:
        raise ValueError("未知 prompt-set %r，可用：%s" % (version, sorted(PROMPT_SETS)))
    return PROMPT_SETS[version]


class StubModel:
    """本地桩模型：不联网，用确定性规则产出摘要与分类。

    桩存在是必要的 —— AC 要求「模型网关可用桩或本地模型」。
    但桩的输出会被指标逐项检查（关键事实覆盖率、URL 数、联系方式残留），
    所以它必须真的从正文里取内容，不能凭空写。

    prompt_set 真的改变行为：v1 取首句、v2 取关键事实句。这是 compare 能比出差异的前提。
    """

    def __init__(self, prompt_set: str = "v1"):
        self.prompt_set = prompt_set
        self.spec = prompt_set_spec(prompt_set)

    def summarize(self, body: str, max_len=None) -> str:
        max_len = max_len or self.spec["max_len"]
        t = " ".join(body.split())
        sents = [s.strip() for s in t.replace("\n", " ").split("。") if s.strip()]
        if self.spec["strategy"] == "first_sentence":
            base = sents[0] if sents else ""
        else:
            # key_fact_first：先取含金额/比例的句子，再退含截止的句子，最后退首句
            base = next((s for s in sents if any(k in s for k in ("万元", "比例", "%"))), None)
            if base is None:
                base = next((s for s in sents if "截止" in s), None)
            if base is None:
                base = sents[0] if sents else ""
        out = base.strip()
        return out if len(out) <= max_len else out[:max_len - 1] + "…"

    def classify(self, title: str, body: str) -> str:
        """按「结构特征」而非「有没有某个词」判定，避免 4 个类别的关键词互相覆盖。

        优先级：公示名单（正文有名单表）> 活动安排（正文有会期）> 申报通知（正文有申报条件）> 行业动态。
        """
        t = title or ""
        b = body or ""
        if "拟支持名单" in b or ("公示" in t and "名单" in b):
            return "public_listing"
        if "活动安排" in b or ("举办" in t and "会期" in b) or "会期一天" in b:
            return "event"
        if "申报条件" in b or "申报截止" in b:
            return "policy_notice"
        return "industry_news"
