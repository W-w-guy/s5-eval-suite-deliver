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


class StubModel:
    """本地桩模型：不联网，用确定性规则产出摘要与分类。

    桩存在是必要的 —— AC 要求「模型网关可用桩或本地模型」。
    但桩的输出会被指标逐项检查（关键事实覆盖率、URL 数、联系方式残留），
    所以它必须真的从正文里取内容，不能凭空写。
    """

    def summarize(self, body: str, max_len=150) -> str:
        t = " ".join(body.split())
        # 取第一句含「支持 / 比例 / 万元 / 日」的句子作为关键事实句，没有就取首句
        sents = [s.strip() for s in t.replace("\n", " ").split("。") if s.strip()]
        # 先取「含金额/比例」的句子（摘要必须覆盖这类关键事实），没有再退回含「截止」的句子
        key = next((s for s in sents if any(k in s for k in ("万元", "比例", "%"))), None)
        if key is None:
            key = next((s for s in sents if "截止" in s), None)
        base = key or (sents[0] if sents else "")
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
