# -*- coding: utf-8 -*-
"""生成 deliverable：templates/renewal.json（S3-SOP-033 续约预警）
模板内容依据工单【本单范围】逐条落地；示例数据全部虚构。"""
import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

T = {
  "template_id": "S3-SOP-033-renewal",
  "name": "续约预警",
  "version": "1.0.0",
  "stage": "Stage iii 业务框架与小程序",
  "module": "SOP 引擎与工作台",
  "owner_role": "会员经理",
  "target_object": "membership",
  "example_data_virtual": True,
  "metric": {"name": "续约率", "formula": "已续约会籍数 / 触发预警会籍数", "window_days": 90},
  "trigger": {
    "type": "schedule",
    "cron": "0 9 * * *",
    "timezone": "Asia/Shanghai",
    "query": "membership_expiring_within",
    "query_days": 90,
    "query_note": "已进入流失预警的会员同样命中（query 侧已并入 churn_warning_at 分支）",
    "dedupe_days": 120,
    "cancel_on": "membership.renewed",
    "not_duplicate_with": "租约到期前 60 / 30 天的续约任务由 S2-SPACE 生成，本模板不重复生成"
  },
  "escalate_policy": {"default": "remind_only",
    "note": "本模板只做提醒，升级由会籍 SLA 统一负责，避免重复通知"},
  "dictionaries": {
    "risk_reason": ["续约价格敏感", "服务价值感知不足", "对接人变更", "业务收缩",
                    "场地需求变化", "竞品接触", "内部决策链变化", "其他"],
    "renewal_intent": ["明确续约", "倾向续约", "犹豫", "倾向流失", "明确不续约"],
    "care_action": ["高层拜访", "资源对接沙龙", "增值服务体验", "专属权益升级",
                    "价格方案沟通", "需求复盘会"],
    "outcome": ["续约", "流失", "延期"]
  },
  "scripts": {
    "step1_diagnose": "您好{联系人}，我是{企业名称}的会员经理。会籍还有约三个月到期，想约您二十分钟聊聊这一年的使用感受，也听听下一步的规划。",
    "step2_care": "{联系人}您好，根据上次沟通，我们为您准备了一份关怀方案：{关怀动作}，计划日期 {计划日期}。不合适的话我们再调。",
    "step4_quote": "续约方案里涉及的金额由报价模块按价格规则表统一计算，我这边不口头报价，稍后把关联的报价单编号发给您核对。",
    "step5_confirm": "{联系人}您好，续约相关的事项已记录完毕。最终会籍状态会由我们在 CRM 中确认后同步给您，以系统记录为准。"
  },
  "steps": []
}

def step(i, name, role, anchor, off, unit, guidance, outputs=None, required=None,
         checklist=None, conditional=False, condition=None, skill=None,
         escalate="remind_only", cascade_skip=False, blocking_rule=None):
    d = {"id": i, "name": name, "role": role,
         "due": {"anchor": anchor, "offset": off, "unit": unit},
         "escalate": escalate, "guidance": guidance}
    if outputs: d["outputs"] = outputs
    # required 默认与 outputs 相同；显式传一份更短的清单 = 该步存在占位输出但不必填
    req = outputs if required is None else required
    if req: d["required_outputs"] = req
    if checklist: d["checklist"] = checklist
    if conditional:
        d["conditional"] = True
        d["condition"] = condition
    if cascade_skip: d["cascade_skip"] = True
    if skill: d["skill_hint"] = skill
    if blocking_rule: d["blocking_rule"] = blocking_rule
    return d

S1 = step(1, "原因诊断", "会员经理", "trigger", 3, "work_day",
  "查看会籍剩余期限与历史消费，进入会员 360 视图导出健康分快照与近 90 天互动次数；"
  "按 risk_reason 字典多选勾选风险原因，给出续约意向判断。判断依据必须写清，不凭印象。",
  outputs=["health_score_snapshot", "interactions_90d", "risk_reason", "renewal_intent"],
  checklist=["已核对会籍到期日与合同编号", "已查看近 90 天互动与工单记录"],
  skill="会员经理 · 客户档案与满意度记录")

S2 = step(2, "关怀方案", "会员经理", "trigger", 5, "work_day",
  "依据第①步的风险原因拟定关怀动作与计划日期，写入关怀方案并同步给会员。"
  "AI 关怀建议草稿为占位字段 ai_care_draft，本阶段由人工填写，后续阶段接入生成服务后替换。",
  outputs=["care_action", "plan_date", "ai_care_draft"],
  # ai_care_draft 是占位字段（工单：AI 关怀建议草稿为占位，后续阶段接入），
  # 不列入 required_outputs —— 不填它也能完成第②步。
  required=["care_action", "plan_date"],
  checklist=["关怀动作已从字典中选择", "计划日期已与会员确认"])

S3 = step(3, "管理层介入", "运营主管", "trigger", 1, "work_day",
  "重点会员或健康分低于 40 时生成本步骤，由运营主管与会员经理共同确定介入方式并记录。"
  "非重点会员且健康分不低于 40 时本步骤自动跳过，并在实例中记录跳过原因。",
  outputs=["intervention_decision"],
  conditional=True,
  condition="object.is_key_member or object.health_score < 40",
  cascade_skip=False)

S4 = step(4, "续约方案与报价", "会员经理与招商顾问", "object.expire_at", -30, "natural_day",
  "在会籍到期前 30 个自然日形成续约方案并关联报价单。"
  "金额只能来自报价模块按价格规则表计算的结果，本步骤只记录报价单编号，不填写任何金额。",
  outputs=["quote_id"],
  checklist=["报价单已由报价模块生成", "本步骤未手工填写金额"])

S5 = step(5, "续约结果确认", "会员经理", "object.expire_at", -7, "natural_day",
  "在会籍到期前 7 个自然日确认续约结果：续约 / 流失 / 延期。"
  "选择流失时必须填写流失原因。本步骤只做记录，会员生命周期状态由员工在 CRM 中确认，"
  "SOP 引擎不自动修改该状态。",
  outputs=["outcome"],
  checklist=["结果已与会员确认", "会员生命周期状态未由本系统修改"],
  blocking_rule={"when": "object.outcome == '流失' and not object.loss_reason",
                 "message": "选择流失时必须填写流失原因"})

T["steps"] = [S1, S2, S3, S4, S5]


if __name__ == "__main__":
    # 工单指定路径：sop/templates/renewal.json
    out = os.path.join(HERE, "sop", "templates", "renewal.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    # newline="\n" 是必须的：Windows 文本模式默认把 \n 写成 CRLF，
    # 同一份脚本在两平台产出的 sha256 会不同（实测 6658B vs 6465B，差 193 字节 = 行数）。
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(T, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("wrote", out, os.path.getsize(out), "bytes,", len(T["steps"]), "steps")
