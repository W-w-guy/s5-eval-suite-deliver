# -*- coding: utf-8 -*-
"""生成 120 篇虚构知识文档（4 类各 30 篇）。

为什么是「生成」而不是「手写 120 篇」：
  · 120 篇必须条条有 doc_id / 标题 / 更新日期 / 可见范围，手写必然出错；
  · 用例的 gold_doc_ids 要能落到具体文档上，生成器与用例生成器共用同一份事实表，
    这样「金标文档存在」是结构性的，不靠事后核对。
全部虚构：机构名「示例」，人名「张某」，电话写 010-XXXX-XXXX，金额只出现在知识条文里。
"""
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "kb_docs")
FACTS = os.path.join(HERE, "data", "facts.json")

# 4 个类别，每类 30 篇
CATS = {
    "space_rule": "空间使用规则",
    "service": "服务目录",
    "policy": "政策汇编",
    "faq": "常见问题",
}

# 空间使用规则用的实体
AREAS = ["A 区 3 层", "B 区 5 层", "C 区 2 层", "D 区 1 层", "E 区 4 层"]
ROOMS = ["静音舱", "路演厅", "会议室", "开放工位区", "共享厨房", "洽谈室"]
HOURS = ["07:00-22:00", "08:00-23:00", "09:00-21:00", "06:30-22:30", "07:30-22:00"]
# 服务目录
SERVICES = ["前台代收快递", "会议室预订", "打印复印", "访客登记", "工商注册咨询",
            "财税咨询", "法律咨询", "招聘对接", "政策申报辅导", "IT 网络支持"]
RESP = ["1 个工作日", "2 个工作日", "3 个工作日", "4 小时", "8 小时"]
# 政策汇编
POLICIES = ["小微企业场地补贴", "人才公寓配套", "数字化转型专项", "绿色办公认证",
            "研发费用加计扣除", "首台套设备补助", "稳岗补贴", "知识产权资助",
            "产业空间提质", "中小企业培训补贴"]
# FAQ
FAQS = ["如何申请成为会员", "会籍能否转让", "发票如何开具", "逾期缴费如何处理",
        "访客是否需要预约", "快递代收有无时限", "能否分租工位", "退租需要提前多久"]


def doc(i, cat):
    """返回 (doc_id, title, updated, visibility, body_sections)。body 是 dict，便于生成用例。"""
    n = i % 30
    if cat == "space_rule":
        area = AREAS[n % len(AREAS)]
        room = ROOMS[n % len(ROOMS)]
        hours = HOURS[n % len(HOURS)]
        cap = 20 + n * 3
        body = {
            "开放时间": "%s 的开放时间为 %s，法定节假日按公告调整。" % (area, hours),
            "容量": "%s 的%s 设计容量 %d 人，超出时按先到先得排队。" % (area, room, cap),
            "预约规则": "预订%s 需提前 %d 小时在会员端提交，取消需在开始前 %d 小时操作，否则计一次违约。"
                    % (room, 2 + n % 5, 1 + n % 3),
            "违约": "单月累计 %d 次违约后，次月起停止预约权限 %d 天。" % (3 + n % 4, 7 + n % 8),
            "禁止行为": "禁止在%s 内饮食、吸烟与堆放易燃物；违者按《会员行为准则》第 %d 条处理。" % (room, 3 + n % 5),
            "联系方式": "空间事务请联系前台 010-XXXX-XXXX（示例占位号码）。",
        }
        title = "%s %s 使用规则" % (area, room)
        return "SP-%03d" % (n + 1), title, "2026-%02d-%02d" % (3 + n % 8, 1 + n % 27), "all", body
    if cat == "service":
        svc = SERVICES[n % len(SERVICES)]
        resp = RESP[n % len(RESP)]
        tier = ["基础会籍", "标准会籍", "高级会籍"][n % 3]
        body = {
            "服务内容": "%s 面向%s 会员提供，包含受理、处理与结果反馈三个环节。" % (svc, tier),
            "响应时效": "受理后 %s 内响应；材料不齐的一次性告知补正。" % resp,
            "收费标准": "含在会籍费内，不另行收费；超出范围按《服务价目表》第 %d 项计费。" % (n % 9 + 1),
            "申请方式": "在会员端「服务台」提交工单，或致电 %d 号分机（示例分机号）。" % (100 + n),
            "覆盖范围": "限%s 会员本人及其授权联系人使用，不得转授第三方。" % tier,
            "责任边界": "本服务不替代专业审计与法律意见，最终结论由持证机构出具。",
        }
        title = "%s 服务说明（%s）" % (svc, tier)
        return "SV-%03d" % (n + 1), title, "2026-%02d-%02d" % (4 + n % 7, 2 + n % 26), "all", body
    if cat == "policy":
        pol = POLICIES[n % len(POLICIES)]
        amount = ["最高 20 万元", "最高 50 万元", "按实际支出 30% 补助", "一次性 5 万元",
                  "每平方米 200 元"][n % 5]
        deadline = "2026-%02d-%02d" % (6 + n % 5, 5 + n % 20)
        body = {
            "适用对象": "在本市注册、具有独立法人资格的会员企业，成立满 %d 年。" % (1 + n % 4),
            "支持标准": "%s 的资助额度为%s，同一企业同一年度只可享受一次。" % (pol, amount),
            "申报截止": "%s 批次申报截止 %s，逾期不再受理。" % (pol, deadline),
            "申报材料": "申请表、营业执照复印件、上一年度财务报表、项目佐证材料（各 1 份）。",
            "审核流程": "形式审查（%d 个工作日）→ 专家评审（%d 个工作日）→ 公示 7 个自然日 → 拨付。"
                    % (3 + n % 4, 10 + n % 10),
            "注意事项": "本汇编为虚构示例，仅用于评测，不构成任何真实政策依据。",
        }
        title = "%s 申报指引（2026 版）" % pol
        return "PL-%03d" % (n + 1), title, "2026-%02d-%02d" % (5 + n % 6, 3 + n % 25), "member", body
    # faq
    q = FAQS[n % len(FAQS)]
    body = {
        "问题": q,
        "答复": "%s：请通过会员端或前台办理，办理时间为工作日 09:00-18:00。" % q,
        "所需材料": ["会员编号", "经办人身份证明", "授权书（如代办）"][n % 3],
        "办理时限": "%d 个工作日" % (1 + n % 5),
        "补充说明": "如遇政策调整，以最新公告为准；本问答为虚构示例。",
        "升级路径": "超过时限未处理，可致电 %d 号分机（示例）升级处理。" % (200 + n),
    }
    title = "常见问题：%s" % q
    return "FQ-%03d" % (n + 1), title, "2026-%02d-%02d" % (6 + n % 6, 4 + n % 24), "all", body


def render(doc_id, title, updated, visibility, body):
    lines = ["---",
             "doc_id: %s" % doc_id,
             "title: %s" % title,
             "updated: %s" % updated,
             "visibility: %s" % visibility,
             "---", "",
             "# %s" % title, ""]
    for k, v in body.items():
        lines.append("## %s" % k)
        lines.append("")
        lines.append(v)
        lines.append("")
    return "\n".join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    facts = []
    order = []
    for cat in ("space_rule", "service", "policy", "faq"):
        for i in range(30):
            order.append((cat, i))
    for cat, i in order:
        doc_id, title, updated, vis, body = doc(i, cat)
        open(os.path.join(OUT, "%s.md" % doc_id), "w", encoding="utf-8").write(
            render(doc_id, title, updated, vis, body))
        facts.append({"doc_id": doc_id, "cat": cat, "title": title,
                      "updated": updated, "visibility": vis, "body": body})
    os.makedirs(os.path.dirname(FACTS), exist_ok=True)
    json.dump(facts, open(FACTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("docs", len(facts), dict(Counter(f["cat"] for f in facts)))


if __name__ == "__main__":
    main()
