# -*- coding: utf-8 -*-
"""新会员入会引导 SOP 引擎 + 配套材料（全部虚构数据，仅用于本单交付）。

口径（虚构）：
  · 岗位：会员成功顾问（主）、前台、财务专员、运营主管
  · 话术 3 版分别用于企业微信 / 短信 / 邮件，**每版不超过 150 字**，一律使用变量占位
    字数口径：变量占位不计入正文（{企业名称} 记 0 字），同时另查含变量的原始长度也不超限——
    两条都过才算合规（乐观口径过、严格口径不过 = 客户粘到短信里就超长）。
  · 入会资料：4 项必填 + 4 项可选，逐项写明用途与不提供的替代方案
  · 每个步骤 2~4 条可勾选检查项
  · 能力卡共建：10 个引导问题，用于把会员能力沉淀成可撮合的结构化标签
  · 时间口径：work=工作日 09:00–18:00 内消耗；natural=自然时间
"""
from datetime import datetime

from kitlib import sop

WORK = (9, 18)
HOLIDAYS = ()
ROLES = ["会员成功顾问", "前台", "财务专员", "运营主管"]
SMS_LIMIT = 150          # 工单硬要求：每版不超过 150 字

# 入会资料清单：必填 4 项 + 可选 4 项
MATERIALS = [
    dict(id="M01", name="营业执照副本", required=True, why="用于主体资格核验与合同签约主体确认",
         fallback="暂未取得可先提供统一社会信用代码与注册名称，5 个工作日内补交扫描件"),
    dict(id="M02", name="联系人名单", required=True, why="用于开通企业管理员账号与日常对接",
         fallback="可先提供 1 名主联系人，其余在首次登录后由管理员自助添加"),
    dict(id="M03", name="开票信息", required=True, why="用于会员费开票与对账",
         fallback="如需先开通后补票，可填写《延后开票说明》，30 天内补齐"),
    dict(id="M04", name="门禁登记信息", required=True, why="用于生成门禁权限与访客邀请码",
         fallback="可先采集最少必要信息（姓名、所属企业、人数），证件号一律不收"),
    dict(id="M05", name="企业 Logo", required=False, why="用于会员空间导视与线上会员目录展示",
         fallback="暂不提供则使用文字简称占位，后续补交可替换，不影响入会"),
    dict(id="M06", name="官网或公众号链接", required=False, why="用于会员目录补充展示",
         fallback="不提供不影响入会"),
    dict(id="M07", name="企业简介（200 字内）", required=False, why="用于会员目录与撮合匹配",
         fallback="不提供则由能力卡问答自动生成摘要"),
    dict(id="M08", name="特殊需求说明", required=False, why="用于提前准备无障碍、停车、餐饮等配套",
         fallback="不提供按标准配套安排"),
]

# 能力卡共建 10 个引导问题
CARD_QUESTIONS = [
    "贵司的主营业务用一句话怎么描述？",
    "目前在产业里处于哪个环节（上游/中游/下游/服务方）？",
    "最希望在这栋楼里遇到什么样的企业？（客户/供应商/合作方/同行）",
    "贵司能对外提供什么资源或能力？（可作为别人的供给）",
    "近期最想解决的一个业务难题是什么？",
    "团队规模与关键岗位构成大概是什么样？",
    "过去一年有没有成功撮合或合作的案例可以匿名分享？",
    "对会员活动有什么偏好？（行业沙龙/路演/闭门会/培训）",
    "希望我们多久跟进一次比较合适？",
    "除办公空间外，还希望平台提供哪类服务？",
]

# 话术 3 版（企业微信 / 短信 / 邮件），每版 ≤150 字，均用变量占位
SCRIPTS = [
    dict(id="W01", kind="欢迎话术", scene="入会欢迎", channel="企业微信", version="企业微信版",
         vars=["联系人", "企业名称", "顾问", "会员编号"], limit=SMS_LIMIT,
         body="{联系人}您好，我是{企业名称}会员空间的会员成功顾问{顾问}。"
              "恭喜贵司已完成入会，会员编号{会员编号}。"
              "接下来我会协助您完成资料提交、门禁开通与能力卡共建。"
              "有任何问题随时找我。"),
    dict(id="W02", kind="欢迎话术", scene="入会欢迎", channel="短信", version="短信版",
         vars=["联系人", "企业名称", "顾问"], limit=SMS_LIMIT,
         body="【{企业名称}】{联系人}您好，入会已完成。我是会员成功顾问{顾问}，"
              "稍后为您开通门禁与账号，资料清单一并发送。回复本短信即可联系我。"),
    dict(id="W03", kind="欢迎话术", scene="入会欢迎", channel="邮件", version="邮件版",
         vars=["联系人", "企业名称", "顾问", "会员编号", "资料链接"], limit=SMS_LIMIT,
         body="{联系人}您好：欢迎{企业名称}加入会员空间（会员编号{会员编号}）。"
              "请查收入会资料清单{资料链接}，4 项必填材料提交后即可开通门禁。"
              "我是您的专属顾问{顾问}。"),
]

# 能力卡引导问题也做成带变量的引导话术（用于开场）
CARD_SCRIPT = dict(
    id="C01", kind="引导话术", scene="能力卡共建", channel="面谈", version="开场版",
    vars=["联系人", "企业名称"], limit=None,
    body="{联系人}您好，今天想用 10 个问题把{企业名称}的能力梳理成一张卡，"
         "方便我们后续帮您做撮合。您怎么方便怎么答，我来记录。")

D = datetime
CATS = [
    ("J1", "入会邀请与欢迎话术（3 渠道，均 ≤150 字）"),
    ("J2", "必填资料收集与替代方案"),
    ("J3", "可选资料与不提供的处理"),
    ("J4", "资料审核与退回补正"),
    ("J5", "门禁与账号开通（最少必要信息）"),
    ("J6", "能力卡共建 10 问"),
    ("J7", "首次引导与空间熟悉"),
    ("J8", "30 天回访与满意度确认"),
]

STEPS = [
    dict(id="S01", cats=["J1"], name="入会邀请与欢迎", role="会员成功顾问", support=["运营主管"],
         tmode="work", hrs=2, desc="入会审批通过后 2 个工作小时内发出欢迎消息",
         outputs=["三渠道欢迎消息各 1 条（企业微信/短信/邮件）",
                  "会员编号与专属顾问姓名",
                  "资料清单链接"],
         checklist=["三个渠道是否都已发出",
                    "会员编号是否已生成并告知",
                    "资料清单链接是否可正常打开"]),
    dict(id="S02", cats=["J2"], name="必填资料收集", role="会员成功顾问", support=["财务专员"],
         tmode="work", hrs=8, desc="1 个工作日内收齐 4 项必填材料，缺项须给替代方案",
         outputs=["4 项必填材料：营业执照副本、联系人名单、开票信息、门禁登记信息",
                  "缺项替代方案记录（每项缺什么、替代方式、补交期限）"],
         checklist=["营业执照副本是否已归档并核验主体名称",
                    "联系人名单是否已录入管理员账号",
                    "开票信息是否已交财务专员",
                    "门禁登记是否只采集最少必要信息（不含证件号）"]),
    dict(id="S03", cats=["J3"], name="可选资料说明", role="会员成功顾问", support=[],
         tmode="work", hrs=4, desc="收集必填项时一并说明 4 项可选材料，明确不影响入会",
         outputs=["可选材料清单：Logo、官网/公众号链接、企业简介、特殊需求说明",
                  "会员对可选材料的取舍确认"],
         checklist=["是否说明了可选材料不影响入会",
                    "是否记录了会员的取舍结果"]),
    dict(id="S04", cats=["J4"], name="资料审核与退回补正", role="运营主管", support=["会员成功顾问"],
         tmode="work", hrs=8, desc="收到材料后 1 个工作日内完成审核；不合格一次性退回并写明补正点",
         outputs=["审核结论：通过 / 退回补正（附补正清单）",
                  "补正后复审记录"],
         checklist=["是否在 1 个工作日内给出审核结论",
                    "退回时是否一次性列全补正点（不挤牙膏）",
                    "补正后是否已复审"]),
    dict(id="S05", cats=["J5"], name="门禁与账号开通", role="前台", support=["会员成功顾问"],
         tmode="work", hrs=8, desc="审核通过后 1 个工作日内开通门禁与管理账号",
         outputs=["门禁权限：人数、有效期、访客邀请码规则",
                  "管理员账号：主联系人 1 个 + 自助添加名额",
                  "开通回执：已通知会员并确认可用"],
         checklist=["门禁人数是否与联系人名单一致",
                    "是否只采集最少必要信息（姓名/所属企业/人数）",
                    "开通后是否取得会员「可用」确认"]),
    dict(id="S06", cats=["J6"], name="能力卡共建访谈", role="会员成功顾问", support=["运营主管"],
         tmode="work", hrs=8, desc="开通后 1 个工作日内完成 10 问访谈并生成能力卡",
         outputs=["能力卡：主营业务、产业环节、期望对接方、可提供资源、近期难题等字段",
                  "10 个引导问题的回答记录（未答项标注待补）"],
         checklist=["10 个问题是否逐一提问并记录",
                    "未答项是否标注待补",
                    "能力卡是否经会员确认后才入库"]),
    dict(id="S07", cats=["J7"], name="首次到访引导", role="前台", support=["会员成功顾问"],
         tmode="work", hrs=2, desc="会员首次到访时 2 个工作小时内完成空间熟悉引导",
         outputs=["引导记录：动线（前台→工位→会议室→共享空间）、门禁使用、访客邀请实操",
                  "首次到访问题清单"],
         checklist=["是否带会员走完主要动线",
                    "是否演示了访客邀请码的生成",
                    "会员提出的问题是否已记录并跟进"]),
    dict(id="S08", cats=["J8"], name="30 天回访", role="会员成功顾问", support=[],
         tmode="natural", hrs=720, desc="入会满 30 天（自然日）时回访一次",
         outputs=["回访记录：使用情况、满意度、待办事项",
                  "若能力卡需更新，记录更新点"],
         checklist=["是否在满 30 天时完成回访",
                    "满意度是否已记录",
                    "能力卡是否需要更新是否已判断"]),
]

COLS = ["step_id", "step_name", "role", "support", "tmode", "limit_value", "sla_desc",
        "output_count", "checklist_count", "cat", "expected_due", "expected_outputs"]


def due(start, val, tmode):
    if tmode == "natural":
        return sop.deadline(start, val, work=None)
    return sop.deadline(start, val, work=WORK, workdays_only=True, holidays=HOLIDAYS)


BASE = datetime(2026, 5, 6, 10, 0)   # 虚构：周三 10:00 入会审批通过

CASES = []
for s in STEPS:
    c = dict(s)
    c["start"] = BASE
    CASES.append(c)


def case_id(c):
    return c["id"]


def cats_of(c):
    return c["cats"]


def row_of(c):
    d = due(c["start"], c["hrs"], c["tmode"])
    return dict(step_id=c["id"], step_name=c["name"], role=c["role"],
                support="、".join(c.get("support") or []) or "无", tmode=c["tmode"],
                limit_value=c["hrs"], sla_desc=c["desc"],
                output_count=len(c["outputs"]), checklist_count=len(c["checklist"]),
                cat="、".join(c["cats"]), expected_due=d.strftime("%Y-%m-%dT%H:%M"),
                expected_outputs=" / ".join(c["outputs"]))
