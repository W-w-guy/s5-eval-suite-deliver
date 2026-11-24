# -*- coding: utf-8 -*-
"""客服转人工 SOP 引擎 + 转接规则与响应时限（全部虚构数据，仅用于本单交付）。

口径（虚构）：
  · 工作时间：工作日（周一~周五）09:00–18:00，不含节假日表
  · 非工作时间：工作日 18:00–次日 09:00、周末、节假日
  · 双时段响应时限（首次响应）——同一个时长，两种起算点：
      - 普通转接 30 分钟 / 紧急转接 15 分钟（涉及他人信息、合同承诺）
      - 工作时间提出：就地起算（如周三 10:00 → 10:30）
      - 非工作时间提出：顺延到下一工作日 09:00 起算（如周三 19:00 → 周四 09:30）
    实现上只用一个「工作时段时间」口径：时长只在工作日 09:00–18:00 内消耗，
    非工作时间自动顺延，因此不必为夜间/周末各写一条分支。
  · 待办生成：每次转接生成一条待办，指派给接手岗位，超时未响应则升级
  · 超时升级：一级 → 值班主管；二级 → 客服负责人
  · 处理完成后必须回写知识缺口（管家答不上来的原因与建议补充的知识条目）
"""
from datetime import datetime

from kitlib import sop

WORK = (9, 18)
HOLIDAYS = ()          # 本单无节假日口径，留空以便扩展
ROLES = ["管家组客服", "客服值班", "招商顾问", "招商主管", "数据合规专员", "值班主管", "客服负责人"]

# 响应时限档位：code -> (小时数, 说明)
SLA_TIERS = {
    "normal": (0.5, "普通转接：30 分钟"),
    "urgent": (0.25, "紧急转接：15 分钟"),
}

# 转接规则表：触发条件 → 接手岗位
RULES = [
    dict(id="R01", trigger="小程序管家答不上来（连续 2 轮未解决或明确表示不确定）",
         role="管家组客服", tier="normal", backwrite=True,
         note="管家先做一次自查，仍无答案才转；转接时带上会话摘要与已尝试的答案"),
    dict(id="R02", trigger="会员主动要求人工", role="客服值班", tier="normal", backwrite=False,
         note="不得劝阻或二次引导回管家；直接生成待办"),
    dict(id="R03", trigger="问题涉及价格谈判（折扣、报价口径、付款方式）",
         role="招商顾问", tier="normal", backwrite=False,
         note="客服不得给出任何报价口径，只做转接"),
    dict(id="R04", trigger="问题涉及合同承诺（条款、免租期、押金、违约）",
         role="招商主管", tier="urgent", backwrite=False,
         note="合同承诺具法律后果，按紧急档 15 分钟"),
    dict(id="R05", trigger="问题涉及他人信息（查询他人会员资料、联系方式、合同）",
         role="数据合规专员", tier="urgent", backwrite=True,
         note="涉及他人信息一律紧急档，且同时记录一次越权尝试"),
    dict(id="R06", trigger="同一会话二次转接或会员明确表达不满", role="值班主管", tier="normal",
         backwrite=True, note="用于兜住流程内无解的情形"),
]

# 处理流程图
FLOW_NODES = [
    ("C1", "管家会话中"),
    ("C2", "命中转接触发条件"),
    ("C3", "生成待办并指派接手岗位"),
    ("C4", "按双时段时限首次响应"),
    ("C5", "人工处理中"),
    ("C6", "超时未响应"),
    ("C7", "升级值班主管"),
    ("C8", "升级客服负责人"),
    ("C9", "处理完成"),
    ("C10", "回写知识缺口"),
    ("C11", "会话关闭"),
]
FLOW_EDGES = [
    ("C1", "C2", "命中 R01~R06 任一触发条件"),
    ("C1", "C1", "未命中触发条件，继续由管家应答"),
    ("C2", "C3", "记录触发规则编号与接手岗位"),
    ("C3", "C4", "待办已生成并指派"),
    ("C4", "C5", "接手人在时限内首次响应"),
    ("C4", "C6", "到达双时段时限仍未响应"),
    ("C6", "C7", "一级：升级到值班主管"),
    ("C7", "C8", "再审未响应或已二次超时"),
    ("C5", "C9", "问题处理完毕"),
    ("C9", "C10", "本次由转接解决或管家曾答不上来"),
    ("C10", "C11", "知识缺口已回写"),
    ("C9", "C11", "无需回写的场景（如会员主动要求人工且已解决）"),
]

# 8 个判定示例：不同起点时段 × 不同档位
D = datetime
CATS = [
    ("N1", "工作时间转接（30 分钟档）"),
    ("N2", "工作时间·紧急转接（15 分钟档）"),
    ("N3", "非工作时间转接：夜间 18:00 后"),
    ("N4", "非工作时间转接：周末"),
    ("N5", "非工作时间顺延跨周末（周五夜）"),
    ("N6", "待办生成与接手岗位指派"),
    ("N7", "超时升级（一级到值班主管）"),
    ("N8", "处理完成后回写知识缺口"),
]

CASES = [
    dict(id="P01", cats=["N1", "N6"], rule="R01", start=D(2026, 5, 6, 10, 0),
         scene="周三 10:00，会员问的问题管家答不上来 → R01 管家组客服，30 分钟档"),
    dict(id="P02", cats=["N1"], rule="R02", start=D(2026, 5, 6, 14, 30),
         scene="周三 14:30，会员主动要求人工 → R02 客服值班，30 分钟档"),
    dict(id="P03", cats=["N2"], rule="R04", start=D(2026, 5, 6, 11, 0),
         scene="周三 11:00，会员问免租期条款（合同承诺）→ R04 招商主管，15 分钟紧急档"),
    dict(id="P04", cats=["N2"], rule="R05", start=D(2026, 5, 6, 16, 50),
         scene="周三 16:50，会员要求查他人合同（涉及他人信息）→ R05 数据合规专员，15 分钟紧急档"),
    dict(id="P05", cats=["N3"], rule="R01", start=D(2026, 5, 6, 19, 0),
         scene="周三 19:00 夜间提出，管家答不上来 → 顺延到周四 09:00 起 2 小时内"),
    dict(id="P06", cats=["N4"], rule="R03", start=D(2026, 5, 9, 10, 0),
         scene="周六 10:00 提出，涉及价格谈判 → 顺延到周一 09:00 起 2 小时内"),
    dict(id="P07", cats=["N5"], rule="R02", start=D(2026, 5, 8, 21, 30),
         scene="周五 21:30 提出，会员要求人工 → 跨周末顺延到周一 09:00 起 2 小时内"),
    dict(id="P08", cats=["N7", "N8"], rule="R01", start=D(2026, 5, 6, 9, 20),
         scene="周三 09:20 转接，接手人超时未响应 → 升级值班主管；处理后须回写知识缺口"),
]

COLS = ["example_id", "scene", "rule_id", "trigger", "role", "tier", "sla_hours",
        "shift", "start_at", "contact_policy", "expected_due", "expected_shift_label",
        "expected_backwrite", "expected_escalate_to"]


def tier_hours(tier):
    return SLA_TIERS[tier][0]


def shift_of(start):
    """判断起点落在哪个时段。"""
    if start.weekday() >= 5:
        return "offwork"
    if start.date().isoformat() in HOLIDAYS:
        return "offwork"
    if WORK[0] <= start.hour < WORK[1]:
        return "work"
    return "offwork"


def due(start, tier):
    """双时段响应时限：统一用「工作时段时间」口径推算，非工作时间自动顺延。"""
    h = tier_hours(tier)
    d = sop.deadline(start, h, work=WORK, workdays_only=True, holidays=HOLIDAYS)
    return d


def label_of(start, tier, d):
    """同一时长、两种表述：工作时间就地起算，非工作时间顺延到下一工作日。

    时长本身不变（30 分钟 / 15 分钟），区别只在「从哪一刻开始消耗」——
    这正是双时段口径的核心：时长只在工作日 09:00–18:00 内走。
    """
    sh = shift_of(start)
    mins = int(round(tier_hours(tier) * 60))
    if sh == "work":
        return "工作时间转接，%d 分钟内首次响应（%s 前）" % (mins, d.strftime("%H:%M"))
    return "非工作时间转接，顺延至下一工作日 09:00 起 %d 分钟内（%s 前）首次响应" % (
        mins, d.strftime("%H:%M"))


def rule_of(rid):
    for r in RULES:
        if r["id"] == rid:
            return r
    return None


def evaluate(c):
    r = rule_of(c["rule"])
    tier = r["tier"]
    d = due(c["start"], tier)
    sh = shift_of(c["start"])
    esc = "值班主管" if c["id"] == "P08" else "（未触发超时）"
    return dict(rule_id=r["id"], trigger=r["trigger"], role=r["role"], tier=tier,
                sla_hours=tier_hours(tier), shift=sh,
                due=d.strftime("%Y-%m-%dT%H:%M"), shift_label=label_of(c["start"], tier, d),
                backwrite=("是" if r["backwrite"] else "否"), escalate=esc,
                contact_policy="客服只转接不承诺；价格与合同一律由接手岗位对外")


def case_id(c):
    return c["id"]


def cats_of(c):
    return c["cats"]


def row_of(c):
    e = evaluate(c)
    return dict(example_id=c["id"], scene=c["scene"], rule_id=e["rule_id"],
                trigger=e["trigger"], role=e["role"], tier=e["tier"],
                sla_hours=e["sla_hours"], shift=e["shift"],
                start_at=c["start"].strftime("%Y-%m-%dT%H:%M"),
                contact_policy=e["contact_policy"],
                expected_due=e["due"], expected_shift_label=e["shift_label"],
                expected_backwrite=e["backwrite"], expected_escalate_to=e["escalate"])


# 知识缺口回写字段（交付要求）
BACKWRITE_FIELDS = [
    ("gap_id", "缺口编号", "自动生成，形如 KG-YYYYMMDD-NN"),
    ("question", "会员原问题", "脱敏后原文，不含会员姓名、手机号与合同金额"),
    ("attempted", "管家已尝试的答案", "最多 3 条，逐条标注置信度"),
    ("fail_reason", "答不上的原因", "枚举：知识库缺失 / 条目过时 / 问题歧义 / 超出范围"),
    ("suggest", "建议补充的知识条目", "一句话，须可被知识库直接采纳"),
    ("rule_id", "触发的转接规则", "R01~R06"),
    ("owner", "回写责任人", "接手岗位，处理完成后 1 个工作日内提交"),
]
