# -*- coding: utf-8 -*-
"""生成 30 条用例（提纲 12 / 摘要 18）与 18 份 3000–6000 字虚构转写稿。

转写稿带时间戳（[mm:ss]），且是**原创虚构**（嘉宾、企业、经历全为合成）。
字数严格控制在该区间内 —— 单子明确要求，且太短测不出「摘要压缩率」，太长超出模型上下文。

每份转写稿都埋了：
  · 若干可作「金句」的原句（短、判断性强、可逐字引用）
  · 一个「不谈话题」标记（嘉宾资料里声明，转写稿里出现该话题的段落）
  · 若干数字（年份、人数、金额）供「摘要数字必须出现在转写稿中」这条检查
"""
import json, os, random, re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "transcripts")
R = random.Random(2017)

GUESTS = [
    ("张維（虚构）", "示例云栈科技创始人", "2016 年起做企业数字化服务，团队从 3 人扩到 120 人"),
    ("李澜（虚构）", "示例绿源节能联合创始人", "2018 年从地产转行做节能改造，服务过 60 家园区"),
    ("王锐（虚构）", "示例海纳物流 CTO", "十年供应链系统经验，主导过三次系统重构"),
    ("赵敏（虚构）", "示例同创教育 CEO", "从线下培训转型线上，学员从 2000 到 8 万"),
    ("陈曦（虚构）", "示例锐思医疗创始人", "医疗器械注册与合规出身，做过 14 个二类器械注册"),
    ("刘畅（虚构）", "示例星河传媒主理人", "内容营销十年，服务过 40 个消费品牌"),
]
TOPICS = ["创业第一年最难的决策", "团队从 10 人到 100 人的组织变化", "如何在红海里找到细分切口",
          "第一次融资踩过的坑", "产品与销售谁先谁后", "如何判断一个市场是否值得进"]
ROUGH = ["20244567", "12044789", "36271600", "8901234", "55000000", "128000"]
# 可作金句的判断句（短、完整、可逐字引用）
QUOTE_POOL = [
    "创业第一年最重要的不是找到方向，而是找到愿意为你的方向付钱的人。",
    "组织变大以后，创始人最大的敌人是自己的信息量。",
    "我们花了两年才明白，客户不是被说服的，是被验证的。",
    "融资不是终点，是让你有资格继续试错的工具。",
    "所有看起来突然的爆发，背后都有三年没人看见的准备。",
    "不要问市场有多大，要问你能拿下多少。",
    "招人最贵的成本不是工资，是招错之后的调整成本。",
    "产品做减法比做加法难十倍。",
    "客户流失之前，服务体验早就开始变差了。",
    "一个健康的生意，是客户主动帮你介绍客户。",
]
# 不谈话题（嘉宾资料里声明，转写稿里出现但不该被展开）
OFF_LIMIT = [
    ("上一家公司离职的具体原因", "涉及第三方，不便展开"),
    ("正在进行的融资细节", "处于静默期，不能透露"),
    ("与某合作伙伴的纠纷", "已进入法律程序，不讨论"),
]


def build_transcript(idx, layout_seed):
    """生成一份 3000–6000 字的虚构转写稿。"""
    r = random.Random(layout_seed)
    name, role, bg = GUESTS[idx % len(GUESTS)]
    topic = TOPICS[idx % len(TOPICS)]
    off, off_reason = OFF_LIMIT[idx % len(OFF_LIMIT)]
    paras = []
    t = 0
    sections = []
    # 开场
    paras.append("[00:00] 主持人：欢迎收听「示例播客」，今天请到的是%s，%s。%s。" % (name, role, bg))
    paras.append("[00:35] %s：谢谢邀请，很高兴聊聊%s这个话题。" % (name, topic))
    sections.append((0, "开场与嘉宾介绍"))
    # 三个主体板块
    heads = [("第一段经历", topic, "起步阶段"), ("踩过的坑", "最失败的一次尝试", "转折"), ("方法论", "现在怎么做", "复盘")]
    for k, (h1, h2, h3) in enumerate(heads):
        t += 240
        paras.append("[%02d:%02d] 主持人：我们先从%s聊起，%s。" % (t // 60, t % 60, h1, h2))
        sections.append((t, h1))
        for j in range(9):
            t += r.choice([35, 42, 48, 55])
            body = r.choice([
                "我们当时只有 %d 个人，一个月做 %d 个项目，靠的是把一个细分需求做到极致。" % (3 + j, 2 + j * 3),
                "那段时间我每天见 %d 个客户，连续 %d 天没休息。" % (2 + j % 4, 10 + j),
                "第一次重构花了 %d 个月，线上事故从每月 %d 次降到 %d 次。" % (2 + j % 3, 8 - j % 4, 1),
                "我们把服务拆成 %d 个环节，每个环节都有明确的交付物。" % (5 + j % 4),
                "客户规模从 %d 家增长到 %d 家，靠的不是投放，是复购。" % (10 + j, 40 + j * 6),
                "我印象最深的是 %d 年那次，整个团队只剩下 %d 个月的现金。" % (2019 + j % 5, 3 + j % 4),
                "我们把报价从 %d 元提到 %d 元，反而成交率更高了。" % (20000 + j * 1000, 35000 + j * 2000),
                "复盘的时候我们发现，%d%% 的问题都出在需求确认这一步。" % (60 + j * 3),
                "那 %d 个客户里，有 %d 个后来成了我们的介绍人。" % (30 + j, 11 + j % 7),
            ])
            paras.append("[%02d:%02d] %s：%s" % (t // 60, t % 60, name, body))
            if j % 4 == 1:
                q = QUOTE_POOL[(idx * 3 + k * 4 + j) % len(QUOTE_POOL)]
                paras.append("[%02d:%02d] %s：%s" % (t // 60 + 1, (t + 7) % 60, name, q))
                t += 7
    # 不在谈的话题（出现但不展开）
    t += 200
    paras.append("[%02d:%02d] 主持人：很多听众关心%s。" % (t // 60, t % 60, off))
    sections.append((t, "其他"))
    paras.append("[%02d:%02d] %s：这个%s，我们跳过去吧。" % (t // 60, (t + 20) % 60, name, off_reason))
    # 收尾
    t += 180
    paras.append("[%02d:%02d] 主持人：最后一个问题，给刚开始的创业者一句建议。" % (t // 60, t % 60))
    paras.append("[%02d:%02d] %s：%s" % (t // 60, (t + 25) % 60, name, QUOTE_POOL[(idx + 4) % len(QUOTE_POOL)]))
    sections.append((t, "收尾"))
    total = t + 60
    return {"guest": name, "role": role, "background": bg, "topic": topic,
            "off_limit": off, "off_limit_reason": off_reason,
            "raw": "\n".join(paras), "sections": sections, "duration_sec": total}


def pad_to_range(text, lo=3000, hi=6000, idx=0, target=None):
    """把转写稿字数补到目标值，且必须落在 3000–6000 区间内。

    ★ 初版只补到 >=3000 就停，结果 18 份全落在 3001–3035 —— 名义上「都在区间内」，
      实际上没覆盖 3000–6000 的分布。评测集的「字数区间」如果只取端点附近，
      就测不出摘要压缩率在长稿上的表现。改为按 idx 均分到整个区间。
    """
    r = random.Random(9000 + idx)
    lo = max(lo, target or lo)
    hi = hi if not target else max(target, lo)
    filler = [
        "主持人：这块能不能再举一个具体例子？",
        "嘉宾：可以。当时有个客户是 %d 人的团队，需求很分散，我们先把流程切成 %d 段才理清。" % (r.randint(30, 200), r.randint(4, 9)),
        "主持人：那他们后来用起来了吗？",
        "嘉宾：用了，%d 个月之后续约，还介绍了两个同行过来。" % r.randint(3, 18),
        "主持人：听起来关键是先把边界划清楚。",
        "嘉宾：对，边界清楚之后，剩下的就是执行。" ,
    ]
    lines = text.split("\n")
    extra = 0
    while len("\n".join(lines)) < lo:
        lines.append(filler[extra % len(filler)])
        extra += 1
    out = "\n".join(lines)
    if len(out) > hi:
        out = out[:hi]
        # 保证不截断在行中间
        out = out[:out.rfind("\n")] if "\n" in out else out
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    cases = []
    # 18 份摘要用例
    summaries = []
    for i in range(18):
        d = build_transcript(i, 3000 + i)
        # 18 份均匀铺满 3000–6000：3200, 3370, ... 约每份 +165 字
        target = 3200 + int(i * (5600 - 3200) / 17)
        d["raw"] = pad_to_range(d["raw"], idx=i, target=target)
        cid = "IP-S%02d" % (i + 1)
        path = "data/transcripts/%s.txt" % cid
        open(os.path.join(HERE, path), "w", encoding="utf-8").write(d["raw"])
        # 金句：从稿子里挑真实存在的完整句（必须是原句，不能改写）
        sents = [s.strip() for s in d["raw"].replace("[", "").split("\n") if s.strip()]
        quotes = [s for s in sents if s.split("：", 1)[-1] in QUOTE_POOL][:3]
        if len(quotes) < 3:
            quotes = (quotes + [s for s in sents if len(s) > 20 and "主持人" not in s])[:3]
        # 时间戳形如 [mm:ss]，用正则精确取，不要靠 split（会把 "00]" 也当成分秒）
        gold_ts = sorted({int(m.group(1)) * 60 + int(m.group(2))
                          for m in re.finditer(r"\[(\d{2}):(\d{2})\]", d["raw"])})
        nums = sorted(set(re.findall(r"\d{2,}", d["raw"])))
        cases.append({
            "case_id": cid, "kind": "summary",
            "input_file": path,
            "char_count": len(d["raw"]),
            "guest": d["guest"], "off_limit_topic": d["off_limit"],
            "duration_sec": max(gold_ts) if gold_ts else 600,
            "gold_quotes": quotes,
            "gold_timestamps": gold_ts[:40],
            "allowed_numbers": nums[:200],
            "forbidden_points": [{"type": "fabricated_content", "desc": "摘要添加嘉宾没说过的话"},
                                 {"type": "off_limit_expansion",
                                  "desc": "在「%s」上展开" % d["off_limit"]}],
            "source": "synthetic",
            "meta": {"虚构": "转写稿为原创合成内容"},
        })
    # 12 份提纲用例
    for i in range(12):
        d = build_transcript(i, 5000 + i)
        cid = "IP-O%02d" % (i + 1)
        cases.append({
            "case_id": cid, "kind": "outline",
            "guest": d["guest"], "role": d["role"], "background": d["background"],
            "topic": d["topic"], "off_limit_topic": d["off_limit"],
            "expect": {"opening": True, "sections": "3–5 个问题板块", "followups_per_section": 2},
            "off_limit_topics": [d["off_limit"]],
            "forbidden_points": [{"type": "off_limit_expansion",
                                  "desc": "在不谈话题上展开：%s" % d["off_limit"]},
                                 {"type": "off_profile_drift",
                                  "desc": "问题未围绕嘉宾资料中的经历展开"}],
            "source": "synthetic",
            "meta": {"虚构": "嘉宾资料为合成内容"},
        })
    with open(os.path.join(HERE, "data", "cases.jsonl"), "w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n")
    from collections import Counter
    print("cases", len(cases), dict(Counter(c["kind"] for c in cases)))
    cc = [c["char_count"] for c in cases if c["kind"] == "summary"]
    print("转写字数 min/max", min(cc), max(cc), "全部在 3000–6000:", all(3000 <= x <= 6000 for x in cc))


if __name__ == "__main__":
    main()
