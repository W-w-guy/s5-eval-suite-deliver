# -*- coding: utf-8 -*-
"""生成自带的最小虚构站点 + 金标（12 篇）。

数据设计直接服务于指标能否真的被测出来：
  · 前 8 篇组成 4 组「跨来源转载」（每组 2 篇）：组内**正文主干完全相同**，第 2 篇只改标题与开头一句。
    这样归组 F1 才有意义 —— 若组内文本毫无关系，金标就自相矛盾，指标永远上不去。
  · 后 4 篇各自独立（不同支持方向、不同金额），避免被误合并。
  · 1 篇（a006）缺正确原文链接 -> 应被直接丢弃，不进核对队列。
  · robots 禁止 /admin/ 与 /articles/draft/，且这两个目录真实存在，专门用来验证「不抓」。
  · 声明发布日期用 <meta name="publish-date">，正文里也有「截止：YYYY年M月D日」供抽取。
"""
import json, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(HERE, "site")
HOST = "gov-a.example"
PAGES = 12

# 组定义：(组编号 or None, 支持方向, 金额规则, 截止日期, 栏目)
GROUPS = [
    ("C00", "数字化转型", "按不超过项目实际投入 30% 的比例给予支持，单个项目最高 200 万元", "2026-04-20", "政策通知"),
    ("C00", "数字化转型", "按不超过项目实际投入 30% 的比例给予支持，单个项目最高 200 万元", "2026-04-20", "政策通知"),
    ("C01", "绿色低碳改造", "按实际支出的 50% 予以补助，单家企业年度累计不超过 80 万元", "2026-05-18", "政策通知"),
    ("C01", "绿色低碳改造", "按实际支出的 50% 予以补助，单家企业年度累计不超过 80 万元", "2026-05-18", "政策通知"),
    ("C02", "产业空间提质", "对首次认定企业给予一次性 20 万元奖励", "2026-06-15", "公示公告"),
    ("C02", "产业空间提质", "对首次认定企业给予一次性 20 万元奖励", "2026-06-15", "公示公告"),
    ("C03", "中小企业培育", "按不超过项目实际投入 30% 的比例给予支持，单个项目最高 200 万元", "2026-07-13", "行业动态"),
    ("C03", "中小企业培育", "按不超过项目实际投入 30% 的比例给予支持，单个项目最高 200 万元", "2026-07-13", "行业动态"),
    (None, "数字供应链", "按实际支出的 40% 予以补助，单家企业年度累计不超过 120 万元", "2026-08-10", "活动通知"),
    (None, "工业软件", "对首次认定企业给予一次性 30 万元奖励", "2026-09-07", "政策通知"),
    (None, "智能装备", "按不超过项目实际投入 25% 的比例给予支持，单个项目最高 150 万元", "2026-10-05", "公示公告"),
    (None, "绿色能源", "按实际支出的 60% 予以补助，单家企业年度累计不超过 60 万元", "2026-11-02", "行业动态"),
]
PUB = ["2026-03-02", "2026-03-02", "2026-03-16", "2026-03-16", "2026-04-01", "2026-04-01",
       "2026-04-15", "2026-04-15", "2026-05-06", "2026-05-20", "2026-06-03", "2026-06-17"]
# 每组的共同开头（组内第 2 篇改成另一句改写开头，但主干保持一致）
OPEN_STD = "为贯彻落实示例市产业高质量发展有关部署，现将本批次有关事项通知如下。"
OPEN_REWRITE = "现将本批次有关事项通知如下，请各有关单位按要求组织申报。"
# 缺原文链接的那篇必须落在「独立篇」上（idx 8..11），不能落进转载组 ——
# 否则该组在预测侧只剩 1 篇，永远无法成组，归组召回率会被数据结构性地压低。
NO_LINK_IDX = 8          # IT-009


def body_paragraphs(idx):
    grp, direction, money, deadline, kind = GROUPS[idx]
    first = OPEN_REWRITE if (grp and idx % 2 == 1) else OPEN_STD
    y, m, d = deadline.split("-")
    if kind == "行业动态":
        # 行业动态是新闻体：没有「申报条件/申报截止」这些通知结构，
        # 否则分类器无法与政策通知区分（真实数据里也不会这样混）。
        ps = [first,
              "一、本期观察聚焦%s领域的进展与案例。" % direction,
              "二、资金支持方面，%s。" % money,
              "三、受访企业普遍关注落地周期，其中%s前完成签约的占比最高。" % deadline,
              "四、下一步将围绕该领域组织专题交流，具体安排另行发布。",
              "五、联系方式：010-XXXX-XXXX（示例号码，各字符为占位，不指向真实机构）。"]
        return ps
    ps = [first,
          "一、支持方向：%s项目。" % direction,
          "二、申报条件：在本市注册登记、具有独立法人资格且成立满 2 年；未被列入严重失信主体名单。",
          "三、支持标准：%s。" % money,
          "四、申报截止：%s 年 %d 月 %d 日。" % (y, int(m), int(d)),
          "五、申报方式：通过示例市产业服务平台在线填报，无需纸质材料。"]
    if kind == "公示公告":
        ps.insert(3, "拟支持名单：示例云启科技有限公司（虚构）、示例智联科技（虚构）。")
    if kind == "活动通知":
        ps.insert(1, "一、活动安排：09:30 签到，10:00 开始，会期一天。")
    ps.append("六、联系方式：010-XXXX-XXXX（示例号码，各字符为占位，不指向真实机构）。")
    if idx == NO_LINK_IDX:
        ps.append("原文链接：（链接已失效，未保留正确原文地址）")
    return ps


def title_of(idx):
    grp, direction, money, deadline, kind = GROUPS[idx]
    return "%s 2026 年第%d批%s项目" % ({"政策通知": "关于组织申报", "公示公告": "关于公示",
                                   "行业动态": "关于发布", "活动通知": "关于举办"}[kind],
                                 idx + 1, direction)


def page_html(idx):
    ps = body_paragraphs(idx)
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{title} - 示例市产业发展促进局</title>
<meta name="agency" content="示例市产业发展促进局">
<meta name="publish-date" content="{pub}">
</head><body>
<header><h1>示例市产业发展促进局</h1><nav><a href="/page-1.html">列表</a></nav></header>
<article>
<h2>{title}</h2>
{body}
</article>
<footer><p>本页全部内容为虚构测试数据，域名使用 example 保留域名。</p></footer>
</body></html>""".format(title=title_of(idx), pub=PUB[idx],
                        body="\n".join("<p>%s</p>" % p for p in ps))


def main():
    for d in ("articles", "admin", "articles/draft"):
        os.makedirs(os.path.join(SITE, HOST, d), exist_ok=True)
    for i in range(PAGES):
        open(os.path.join(SITE, HOST, "articles", "a%03d.html" % (i + 1)), "w", encoding="utf-8", newline="\n").write(page_html(i))
    for pg in range(2):
        items = "".join('<li><a href="/articles/a%03d.html">%s</a></li>' % (k + 1, title_of(k))
                        for k in range(pg * 6, pg * 6 + 6))
        nav = " ".join('<a href="/page-%d.html">%d</a>' % (k + 1, k + 1) for k in range(2))
        open(os.path.join(SITE, HOST, "page-%d.html" % (pg + 1)), "w", encoding="utf-8", newline="\n").write(
            '<!doctype html><html><head><meta charset="utf-8"><title>列表页 第%d页</title></head><body>'
            '<h1>示例市产业发展促进局</h1><p>翻页：%s</p><ul>%s</ul>'
            '<p><a href="/admin/settings.html">后台入口（robots 禁止抓取）</a></p>'
            '</body></html>' % (pg + 1, nav, items + ('<li><a href="/articles/draft/d001.html">草稿（robots 禁止抓取）</a></li>' if pg == 0 else '')))
    open(os.path.join(SITE, HOST, "index.html"), "w", encoding="utf-8", newline="\n").write(
        '<!doctype html><html><head><meta charset="utf-8"><title>首页</title></head><body>'
        '<ul><li><a href="/page-1.html">列表</a></li><li><a href="/rss.xml">RSS</a></li></ul></body></html>')
    rss = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           '<title>示例市产业发展促进局</title><link>http://%s/</link><description>虚构测试来源</description>' % HOST]
    for i in range(PAGES):
        rss.append('<item><title>%s</title><link>http://%s/articles/a%03d.html</link>'
                   '<guid>http://%s/articles/a%03d.html</guid><pubDate>%sT09:00:00+08:00</pubDate></item>'
                   % (title_of(i), HOST, i + 1, HOST, i + 1, PUB[i]))
    rss.append('</channel></rss>')
    open(os.path.join(SITE, HOST, "rss.xml"), "w", encoding="utf-8", newline="\n").write("\n".join(rss))
    open(os.path.join(SITE, HOST, "robots.txt"), "w", encoding="utf-8", newline="\n").write(
        "User-agent: *\nDisallow: /admin/\nDisallow: /articles/draft/\nAllow: /\n")
    open(os.path.join(SITE, HOST, "admin", "settings.html"), "w", encoding="utf-8", newline="\n").write(
        '<!doctype html><html><head><meta charset="utf-8"><title>后台配置（禁止抓取）</title></head>'
        '<body><article><h2>后台配置</h2><p>本页在 robots 中禁止抓取，任何抓取都算违规。</p></article></body></html>')
    open(os.path.join(SITE, HOST, "articles", "draft", "d001.html"), "w", encoding="utf-8", newline="\n").write(
        '<!doctype html><html><head><meta charset="utf-8"><title>草稿（禁止抓取）</title></head>'
        '<body><article><h2>草稿</h2><p>未发布草稿，robots 禁止抓取。</p></article></body></html>')

    gold = []
    for i in range(PAGES):
        grp, direction, money, deadline, kind = GROUPS[i]
        gold.append({
            "case_id": "IT-%03d" % (i + 1),
            "url": "http://%s/articles/a%03d.html" % (HOST, i + 1),
            "title": title_of(i),
            "body_gold": "\n".join(body_paragraphs(i)),
            "publish_date": PUB[i],
            # 行业动态是新闻体，没有「申报截止」这一概念 —— 标 _abstain，指标不计入分母。
            # 若硬塞一个日期进金标，测的就成了「能不能从新闻里抽出不存在的截止日」。
            "deadline": ("_abstain" if kind == "行业动态" else deadline),
            "policy_type": {"政策通知": "policy_notice", "公示公告": "public_listing",
                            "行业动态": "industry_news", "活动通知": "event"}[kind],
            "cluster_id": grp or "_abstain",
            "key_facts": [money],
            "has_original_link": (i != NO_LINK_IDX),
        })
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    with open(os.path.join(HERE, "data", "gold.jsonl"), "w", encoding="utf-8", newline="\n") as fh:
        for g in gold:
            fh.write(json.dumps(g, ensure_ascii=False, sort_keys=True) + "\n")
    json.dump({"disallowed": ["/admin/", "/articles/draft/"],
               "probe_urls": ["http://%s/admin/settings.html" % HOST,
                              "http://%s/articles/draft/d001.html" % HOST]},
              open(os.path.join(HERE, "data", "robots_probe.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    print("pages", PAGES, "gold", len(gold),
          "clusters", dict(Counter(g["cluster_id"] for g in gold)))


if __name__ == "__main__":
    main()
