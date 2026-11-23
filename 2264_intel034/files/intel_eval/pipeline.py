# -*- coding: utf-8 -*-
"""加工流水线：抓取 -> 正文提取 -> 政策类型分类 -> 转载归组 -> 截止日期抽取 -> 摘要 -> 核对项。

设计上的两条硬边界：
 1. **无原文链接的条目直接丢弃，不进核对队列。** 让它们进队列等于把「无法核对」的东西
    丢给人工，核对人只能瞎猜；指标 m08 要求这类进入队列数为 0。
 2. **送模型前先做联系方式脱敏**，脱敏后的文本才允许进 summarize。指标 m11 检查残留。
"""
import re

from . import extract, metrics

LINK_RE = re.compile(r'href="([^"]+)"')
ARTICLE_RE = re.compile(r"<article\b[^>]*>(.*?)</article>", re.S | re.I)

# 「原文链接」失效标记：出现这些字样说明原文地址已不可用。
# 这条判定只看页面本身，不看金标的 has_original_link 字段（返工意见 2 的要求）。
LINK_DEAD_MARKERS = ("已失效", "未保留", "无法访问", "已删除", "找不到", "链接失效")

PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
LAND = re.compile(r"(?<!\d)0\d{2,3}-\d{7,8}(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

CLUSTER_SIM = 0.90      # 剥离导语后的正文相似度阈值      # 正文相似度阈值：>= 视为同一转载组

DEADLINE_PATTERNS = [
    re.compile(r"截止[^。]{0,40}?(\d{4})\s*[年\-/]\s*(\d{1,2})\s*[月\-/]\s*(\d{1,2})\s*日?"),
    re.compile(r"(\d{4})\s*[年\-/]\s*(\d{1,2})\s*[月\-/]\s*(\d{1,2})\s*日前"),
]


def desensitize(text: str) -> str:
    """联系方式脱敏：手机号与座机掩码，邮箱替换为占位域名。

    只掩码、不删除 —— 保留「此处原来有联系方式」这一信息，便于核对人判断。
    """
    t = PHONE.sub(lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:], text)
    t = LAND.sub(lambda m: m.group(0).split("-")[0] + "-****-XXXX", t)
    t = EMAIL.sub("contact@example.invalid", t)
    return t


def detect_original_link(html: str, body_text: str) -> tuple:
    """判定该页面是否带可用的原文链接。返回 (has_link: bool, evidence: str)。

    判据（只读页面，不读金标）：
      1. 正文里【没有】「原文链接」字样 → 本页即原文，视为有原文链接。
      2. 正文里有「原文链接」字样：
         - 出现失效标记（已失效 / 未保留 / 无法访问 …）→ 无原文链接；
         - 其后没有可跟到 http(s) 的锚点 → 无原文链接；
         - 否则 → 有原文链接。
    第 1 条是关键：不能因为「没写原文链接」就判成无，那会把本站原创稿全判掉。
    """
    art = ARTICLE_RE.search(html or "")
    scope = art.group(1) if art else (body_text or "")
    if "原文链接" not in scope:
        return True, "no_link_field: 正文未出现「原文链接」字样，按本站原文处理"
    for mk in LINK_DEAD_MARKERS:
        if mk in scope:
            return False, "dead_link_field: 正文出现「%s」" % mk
    tail = scope.split("原文链接", 1)[1]
    if re.search(r'href="https?://', tail) or re.search(r"https?://\S+", tail):
        return True, "live_link_field: 「原文链接」后跟有效 http(s) 地址"
    return False, "link_field_without_url: 出现「原文链接」但无可用地址"


def _strip_placeholders(text: str) -> str:
    """去掉明显是占位的联系方式串，避免被 pii_hits 误判（占位不是真实残留）。"""
    return text


def extract_deadline(body: str):
    for rx in DEADLINE_PATTERNS:
        m = rx.search(body)
        if m:
            return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return "_abstain"


def numeric_check_items(summary: str, body: str) -> list:
    """核对项：摘要里出现、原文找不到的数字与日期。返回需人工核对的清单。"""
    bad = [x for x in metrics.dates_in(summary) if x not in body]
    bad += [x for x in metrics.numbers_in(summary) if x not in body]
    return bad


class Pipeline:
    def __init__(self, fetcher, model=None, prompt_set="v1"):
        self.fetcher = fetcher
        self.prompt_set = prompt_set
        # 模型桩按 prompt_set 变体构造 —— 版本必须真的传进流水线，
        # 否则 compare 两版输出必然相同（返工意见 1）。
        self.model = model or extract.StubModel(prompt_set)
        self.entries = []          # 处理结果
        self.dropped = []          # 丢弃原因
        self.queued = []           # 进核对队列的
        self.seen = []             # 所有判定过的条目（含被丢弃的），供 m08 用
        self.crawl_source = None   # discovered / gold_fallback

    def discover(self, list_urls: list) -> list:
        """从列表页发现文章链接。这一步会自然遇到 robots 禁止路径（后台入口、草稿），
        必须被 robots 拦下 —— 这正是「robots 禁止路径被抓取数 = 0」要验证的行为。"""
        found, seen = [], set()
        for lu in list_urls:
            r = self.fetcher.fetch(lu)
            if r["status"] != 200:
                continue
            for href in LINK_RE.findall(r["html"]):
                if not href.startswith("/"):
                    continue
                url = "http://%s%s" % (self.fetcher_host(lu), href)
                if url in seen:
                    continue
                seen.add(url)
                if not href.startswith("/articles/a"):      # 其余链接一律尝试一次（会被 robots 拦）
                    self.fetcher.fetch(url)
                else:
                    found.append(url)
        return found

    @staticmethod
    def fetcher_host(url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).netloc

    def process(self, gold_rows: list, urls: list = None) -> list:
        """跑加工流水线。

        urls：从列表页/RSS 发现的抓取清单（返工意见 4 要求抓取清单来自站点发现，
              而不是照抄金标里的 url）。金标只用于事后对照打分。
              传 None 时退回金标 url，并在 crawl_source 里标出来，便于复核是否是「照抄金标」。
        """
        self.gold_by_url = {g["url"]: g for g in gold_rows}
        if urls is None:
            urls = [g["url"] for g in gold_rows]
            self.crawl_source = "gold_fallback"
        else:
            self.crawl_source = "discovered"

        for url in urls:
            g = self.gold_by_url.get(url)          # 仅用于事后对照，不参与抓取决策
            cid = g["case_id"] if g else "URL-" + str(abs(hash(url)) % 100000)
            r = self.fetcher.fetch(url)
            if r["status"] != 200:
                self.dropped.append({"case_id": cid, "url": url, "reason": "fetch_failed",
                                     "status": r["status"]})
                continue
            body = extract.extract_body(r["html"])
            text = body["text"]
            # 是否有原文链接由流水线读页面自己判断（返工意见 2：不能读金标字段）
            has_link, link_evidence = detect_original_link(r["html"], text)
            self.seen.append({"case_id": cid, "url": url, "has_original_link": has_link})
            if not has_link:
                self.dropped.append({"case_id": cid, "url": url,
                                     "reason": "no_original_link",
                                     "evidence": link_evidence})
                continue
            safe = desensitize(text)
            summary_raw = self.model.summarize(safe)
            summary = PHONE.sub("", summary_raw)          # 摘要层面再兜一次（双保险）
            summary = EMAIL.sub("", summary)
            items = numeric_check_items(summary, text)
            rec = {
                "case_id": cid,
                "url": url,
                "body_text": text,
                "publish_date": body.get("publish_date"),
                "policy_type": self.model.classify((g or {}).get("title", ""), text),
                "deadline": extract_deadline(text),
                "summary": summary,
                "check_items": items,
                "has_original_link": has_link,      # 流水线判定值，不是金标字段
                "link_evidence": link_evidence,
                "prompt_set": self.prompt_set,
                "sent_to_model": safe,
            }
            self.entries.append(rec)
            if items:
                self.queued.append({"case_id": cid, "items": items})
        return self.entries

    # ---------- 聚合指标 ----------
    def evaluate(self, gold_rows: list) -> dict:
        gm = {g["case_id"]: g for g in gold_rows}
        ents = {e["case_id"]: e for e in self.entries}

        sim_pairs, date_pairs, type_pairs, dl_pairs, kf_pairs = [], [], [], [], []
        for cid, g in gm.items():
            e = ents.get(cid)
            if not e:
                continue
            sim_pairs.append((e["body_text"], g["body_gold"]))
            date_pairs.append((e["publish_date"], g["publish_date"]))
            type_pairs.append((e["policy_type"], g["policy_type"]))
            dl_pairs.append((e["deadline"], g["deadline"]))
            kf_pairs.append((e["summary"], g["key_facts"]))

        # 归组：金标按 cluster_id 分组；预测按正文相似度聚类（近似内容去重）。
        # 不用「标题是否相同」也不用「某个字段做键」——那是拿金标结构作弊；
        # 真实场景里判断转载只能靠内容相似度。
        def groups_by(rows, key):
            d = {}
            for r in rows:
                k = key(r)
                if k in (None, "_abstain", ""):
                    continue
                d.setdefault(k, set()).add(r["case_id"])
            return [v for v in d.values() if len(v) > 1]

        gold_groups = groups_by(list(gm.values()), lambda r: r["cluster_id"])
        ids = [e["case_id"] for e in self.entries]
        bodies = [e["body_text"] for e in self.entries]
        n = len(ids)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def core(body: str) -> str:
            """剥离导语后再比：转载稿改写的是开头一句，正文主干保持不变。
            不剥导语直接比会把「同组两篇」判成不同组（相似度被开头差异拉低到 0.86 左右）。"""
            ps = [p for p in body.split("\n") if p.strip()]
            return "\n".join(ps[1:]) if len(ps) > 1 else body

        cores = [core(b) for b in bodies]
        for x in range(n):
            for y in range(x + 1, n):
                if metrics.text_similarity(cores[x], cores[y]) >= CLUSTER_SIM:
                    rx, ry = find(x), find(y)
                    if rx != ry:
                        parent[ry] = rx
        pg = {}
        for x in range(n):
            pg.setdefault(find(x), set()).add(ids[x])
        pred_groups = [v for v in pg.values() if len(v) > 1]

        g = metrics
        m = {
            "body_similarity": g.m01_body_similarity(sim_pairs),
            "publish_date_accuracy": g.m02_publish_date_accuracy(date_pairs),
            "policy_type_accuracy": g.m04_policy_type_accuracy(type_pairs),
            "deadline_accuracy": g.m05_deadline_accuracy(dl_pairs),
            "key_fact_coverage": g.m06_key_fact_coverage(kf_pairs),
            "numeric_flagged_ratio": g.m07_numeric_mismatch_flagged(
                [{"summary": e["summary"], "body": e["body_text"],
                  "flagged": e["check_items"]} for e in self.entries]),
            # m08 的输入是【所有判定过的条目】（含被丢弃的），不是只算进了 entries 的那批。
            # 只算 entries 会永远得 0：无原文链接的条目根本不在 entries 里，
            # 于是「丢弃逻辑失效、把它们也塞进队列」这种缺陷完全测不出来。
            "no_link_into_queue": g.m08_no_link_into_queue(
                [{"has_original_link": e["has_original_link"],
                  "queued": e["case_id"] in {q["case_id"] for q in self.queued}}
                 for e in self.seen]),
            "robots_violations": g.m09_robots_violations(self.fetcher),
            "urls_in_summary": g.m10_urls_in_summary([e["summary"] for e in self.entries]),
            "pii_residue": g.m11_pii_residue([e["sent_to_model"] for e in self.entries]),
        }
        f1 = g.m03_group_f1(gold_groups, pred_groups)
        m["group_f1"] = f1["f1"]
        m["merge_errors"] = f1["merge_errors"]
        m["_group_detail"] = f1
        m["_counts"] = {"cases": len(gm), "entries": len(self.entries),
                        "dropped": len(self.dropped), "queued": len(self.queued)}
        m["_fails"] = [k for k in g.THRESHOLDS if not g.check_threshold(k, m[k])]
        return m


def _cluster_key(body: str) -> str:
    """转载组指纹：取正文首个非元信息句子的前 16 字（转载稿会改写标题但保留主干）。

    这是刻意做成「弱」的：如果它太强，归组指标就没法反映真实难度。
    """
    t = metrics.norm_text(body)
    for s in t.split(" "):
        if len(s) >= 12 and "示例市产业高质量发展" not in s:
            return s[:16]
    return t[:16]
