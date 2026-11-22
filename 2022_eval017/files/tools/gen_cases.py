# -*- coding: utf-8 -*-
"""生成 35 条情报简报评测用例（含 context 内的虚构资讯）。

分布严格按单子要求：常规 20 / 高相似干扰 10 / 全部与画像无关 5。

关键设计：**同一事件的多来源报道必须「措辞不同、发布时间不同」**。
如果同事件文本几乎一样，聚类就退化成字符串比对，pairwise F1 没有区分度。
所以同一事件的不同来源用不同的表述模板与不同的日期，但共享可识别的事实三元组
（主体 + 动作 + 关键数字），聚类只能靠这些事实去连。
"""
import json, os, random

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = random.Random(2022)

CATS = ["政策", "融资", "行业动态", "活动", "竞品"]
INDUSTRIES = ["企业数字化服务", "节能环保工程", "医疗器械代理", "供应链管理", "教育科技", "工业机器人"]
AREAS = ["示例市", "近江新区", "南山工业园", "临港片区", "西溪板块"]
SOURCES = ["示例日报", "示例产业观察", "示例协会通讯", "示例财经", "示例政务网", "示例园区之窗"]

# ---- 事件素材池：每个事件是一个 (主体, 动作, 关键数字/要素, 类别) ----
EVENTS = [
    ("示例云栈科技", "完成 A 轮融资", "金额 1.2 亿元", "融资"),
    ("示例智联数据", "发布行业白皮书", "覆盖 120 家企业", "行业动态"),
    ("示例绿源节能", "中标园区改造项目", "合同 3400 万元", "竞品"),
    ("示例市产业局", "出台数字化转型补贴政策", "最高补助 200 万元", "政策"),
    ("示例星河传媒", "举办产业对接会", "参会 180 人", "活动"),
    ("示例衡远咨询", "开设第二办公室", "面积 900 平米", "行业动态"),
    ("示例锐思医疗", "获得二类器械注册证", "编号示例-2026-A", "行业动态"),
    ("示例海纳物流", "完成 B 轮融资", "金额 2.6 亿元", "融资"),
    ("示例同创教育", "上线企业培训平台", "首批 40 门课", "行业动态"),
    ("示例新程机器人", "发布协作机器人新品", "负载 12 公斤", "竞品"),
    ("示例合诚律所", "发布合规指引", "覆盖 8 类场景", "行业动态"),
    ("示例市税务局", "调整研发费用加计扣除口径", "比例提高至 100%", "政策"),
    ("示例云栈科技", "与示例海纳物流签约合作", "合同 800 万元", "竞品"),
    ("示例智联数据", "获评专精特新企业", "有效期三年", "行业动态"),
    ("示例市人才办", "发布人才公寓配套办法", "提供 300 套", "政策"),
    ("示例绿源节能", "举办低碳技术论坛", "参会 260 人", "活动"),
    ("示例星河传媒", "获得内容制作资质", "许可编号示例-2026-C", "行业动态"),
    ("示例衡远咨询", "与示例同创教育达成合作", "联合课程 12 门", "竞品"),
    ("示例锐思医疗", "完成 C 轮融资", "金额 4.1 亿元", "融资"),
    ("示例海纳物流", "启用自动化分拣中心", "日处理 12 万件", "行业动态"),
]

# 同一事件的多种表述（措辞不同、日期不同、来源不同）
TEMPLATES = [
    "{src}消息，{who}{act}，{num}。相关人士表示这将影响{area}的相关业务。",
    "据{src}报道，{who}近日{act}，{num}，具体细节已在公告中披露。",
    "{area}方面确认，{who}{act}，{num}，后续将按计划推进。",
    "记者获悉，{who}{act}，{num}。此事项已在{src}上公示。",
]


def make_news(ev_idx, src_idx, day, variant=0, fake=False):
    who, act, num, cat = EVENTS[ev_idx]
    tpl = TEMPLATES[(variant + src_idx) % len(TEMPLATES)]
    area = AREAS[(ev_idx + src_idx) % len(AREAS)]
    src = SOURCES[src_idx % len(SOURCES)]
    if fake:
        # 干扰项：措辞与主事件高度相似，但**只描述另一件事**。
        # 早期版本把两个事件揉进一句（"A 做了 X，与 B 此前做了 Y 并非同一事项"），
        # 导致分类信号混乱、聚类也容易误并 —— 那是指标被数据设计污染，不是工具不行。
        e2 = (ev_idx + 7) % len(EVENTS)
        who2, act2, num2, _ = EVENTS[e2]
        tpl2 = TEMPLATES[(variant + src_idx) % len(TEMPLATES)]
        text = tpl2.format(src=src, who=who2, act=act2, num=num2, area=area)
    else:
        text = tpl.format(src=src, who=who, act=act, num=num, area=area)
    return {"news_id": "N%s" % ("X%02d" % day if False else "%03d%02d" % (ev_idx, src_idx)),
            "date": "2026-%02d-%02d" % (3 + (day % 6), 1 + (day * 3) % 27),
            "source": src, "text": text}


def build_case(cid, kind, n_news, seed):
    r = random.Random(seed)
    news, gold_clusters, gold_cat, img_industry = [], {}, {}, r.choice(INDUSTRIES)
    # 选 4~6 个事件，每个事件 2~4 篇多来源
    evs = r.sample(range(len(EVENTS)), k=min(6, max(4, n_news // 3)))
    ev_order = []
    for k, e in enumerate(evs):
        cnt = 2 if n_news < 12 else r.choice([2, 2, 3, 4])
        day = seed + k
        cluster_id = "E%02d" % (k + 1)
        ev_order.append((cluster_id, e))
        for v in range(cnt):
            n = make_news(e, v + k, day + v, variant=v)
            n["news_id"] = "%s-%02d" % (cid, len(news) + 1)
            news.append(n)
            gold_clusters.setdefault(cluster_id, []).append(n["news_id"])
        gold_cat[cluster_id] = EVENTS[e][3]
    # 干扰项：标题相似但事件不同
    while len(news) < n_news:
        e = r.randrange(len(EVENTS))
        n = make_news(e, r.randrange(len(SOURCES)), seed + len(news), variant=1, fake=True)
        n["news_id"] = "%s-%02d" % (cid, len(news) + 1)
        news.append(n)
        cl = "E%02d" % (len(gold_clusters) + 1)
        gold_clusters[cl] = [n["news_id"]]
        # ★ 干扰项的类别必须取它真实所属事件（EVENTS[(e+7)%N]）的类别。
        #   早期版本一律写「行业动态」，等于给金标塞了错答案 —— 分类准确率被数据结构性地压低。
        gold_cat[cl] = EVENTS[(e + 7) % len(EVENTS)][3]
    news = news[:n_news]
    # 清理：只保留真正出现在 news 里的簇
    ids = {n["news_id"] for n in news}
    gold_clusters = {k: [x for x in v if x in ids] for k, v in gold_clusters.items()}
    gold_clusters = {k: v for k, v in gold_clusters.items() if v}
    gold_cat = {k: gold_cat[k] for k in gold_clusters}

    # 画像：与某些事件相关的行业
    profile = {"industry": img_industry, "areas": r.sample(AREAS, 2),
               "interests": r.sample(CATS, 3)}
    # 相关度打分：事件类别在 interests 内 + 主体/区域与画像匹配 -> 分数
    # ★ 簇号与事件必须显式对应（clusters 里可能因裁剪丢掉空簇，不能靠 zip 猜）
    scored = []
    for cl, e in ev_order:
        if cl not in gold_clusters:
            continue                             # 该事件被裁剪掉了，不参与打分
        who, act, num, cat = EVENTS[e]
        s = 0
        if cat in profile["interests"]:
            s += 3
        if any(a in act or a in who for a in profile["areas"]):
            s += 2
        if img_industry[:2] in who or img_industry[:2] in act:
            s += 2
        s += (len(gold_clusters[cl]) - 1) * 0.5      # 多来源报道的事件更重要
        scored.append((cl, round(s, 1)))
    scored.sort(key=lambda x: -x[1])
    relevant = [c for c, s in scored if s > 0]
    gold_top5 = [c for c, s in scored[:5] if s > 0]

    if kind == "irrelevant":
        # 全部与画像无关：期望输出「本期无高相关资讯」。
        # ★ interests 必须为空：资讯池覆盖了政策/融资/行业动态/活动/竞品全部类别，
        #   只要 interests 非空就必然有事件命中，那这个档位就测不出东西。
        #   相关性只剩「画像行业是否出现在正文」一条判据，而行业是池外的深海养殖装备。
        profile = {"industry": "深海养殖装备", "areas": ["示例市"], "interests": []}
        gold_top5 = []
        relevant = []
    return {
        "case_id": cid, "kind": kind,
        "context_file": "contexts/%s.json" % cid,
        "profile": profile,
        "gold_clusters": gold_clusters,
        "gold_category": gold_cat,
        "gold_top5": gold_top5,
        "gold_relevant_clusters": relevant,
        "expect_no_relevant": (kind == "irrelevant"),
        "source": "synthetic",
        "meta": {"虚构": "资讯全部为合成数据"},
        "_news": news,
    }


def main():
    cases = []
    n = 0
    for i in range(20):
        n += 1
        cases.append(build_case("IB-01%02d" % (i + 1), "normal", 8 + (i % 7), 100 + i))
    for i in range(10):
        n += 1
        cases.append(build_case("IB-02%02d" % (i + 1), "high_similarity", 14 + (i % 7), 200 + i))
    for i in range(5):
        n += 1
        cases.append(build_case("IB-03%02d" % (i + 1), "irrelevant", 8 + (i % 6), 300 + i))
    assert len(cases) == 35, len(cases)

    with open(os.path.join(HERE, "data", "cases.jsonl"), "w", encoding="utf-8", newline="\n") as fh:
        for c in cases:
            ctx = c.pop("_news")
            with open(os.path.join(HERE, c["context_file"]), "w", encoding="utf-8", newline="\n") as cf:
                json.dump({"case_id": c["case_id"], "news": ctx}, cf, ensure_ascii=False, indent=1)
            fh.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    from collections import Counter
    print("cases", len(cases), dict(Counter(c["kind"] for c in cases)))
    sizes = []
    for c in cases:
        ctx = json.load(open(os.path.join(HERE, c["context_file"]), encoding="utf-8"))
        sizes.append(len(ctx["news"]))
    print("news per case", min(sizes), max(sizes))
    print("no_relevant cases", sum(1 for c in cases if c["expect_no_relevant"]))


if __name__ == "__main__":
    main()
