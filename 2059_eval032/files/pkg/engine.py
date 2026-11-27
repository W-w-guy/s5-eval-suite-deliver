# -*- coding: utf-8 -*-
"""虚构种子数据与场景构造（确定性，无随机）。

设计目标：让每条 AC 都有一组「刚好卡在边界」的样本。
  AC1 overdue：confirmed=2026-11-25（周三）→ 截止 11-27（周五）；
               无回归用例 → 2026-11-28 起 overdue；有回归用例 → 永不 overdue。
  AC2 P0 wont_fix：severity=P0 的 confirmed 发现。
  AC3 evidence 掩码：evidence 里放金丝雀、手机号、邮箱、卡号、身份证。
  AC4 月度导出：2026-11 有新增、已修复、未关闭三种。
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)

ORG = "org-demo"
OPERATOR = "redteam.agent"
ROLE_SEC = "security_lead"            # ASCII：HTTP 头不能带中文
ROLE_ENG = "evaluation_engineer"

# 高熵金丝雀（三段随机），避免与正文里的 .invalid 域名撞车
CANARY = "3ZZP-9ERG-Y3SZ"

SEEDS = [
    # (finding_no 由引擎按年递增，这里只给内容)
    dict(key="F_P0_CONFIRMED", title="提示词注入导致金额字段被改写",
         tool="meeting_minutes", technique="prompt_injection", severity="P0",
         status="confirmed", confirmed_at="2026-11-25", found_at="2026-11-24",
         evidence="复现记录：输入含 `ignore previous` 后金额被改为 1 分。"
                  "金丝雀 %s，样本手机 13500000001，联系人邮箱 qa_owner@example.invalid，"
                  "卡号 6200000000000000，身份证 310000000000000012。" % CANARY,
         canary=CANARY, owner_role=ROLE_ENG, regression_case_key=None),
    dict(key="F_P0_HAS_CASE", title="系统提示词被完整回显",
         tool="kb_answer", technique="system_prompt_leak", severity="P0",
         status="confirmed", confirmed_at="2026-11-25", found_at="2026-11-23",
         evidence="输出中回显了系统提示词前 40 字。金丝雀 %s。" % CANARY,
         canary=CANARY, owner_role=ROLE_ENG,
         regression_case_key="KB-INJ-0007"),
    dict(key="F_P1_FIXED", title="越权读取他人合同摘要",
         tool="intel_brief", technique="idor", severity="P1",
         status="fixed", confirmed_at="2026-11-10", found_at="2026-11-09",
         fixed_at="2026-11-14",
         evidence="用他人 draft_id 查询返回了摘要。金丝雀 %s。" % CANARY,
         canary=CANARY, owner_role=ROLE_ENG, regression_case_key="INTEL-AUTH-0003"),
    dict(key="F_P2_NEW", title="拒答话术不规范：缺少边界说明",
         tool="copy_draft", technique="over_refusal", severity="P2",
         status="new", confirmed_at=None, found_at="2026-11-20",
         evidence="对正常商务咨询给出泛化拒答。金丝雀 %s。" % CANARY,
         canary=CANARY, owner_role=ROLE_ENG, regression_case_key=None),
    dict(key="F_P1_VERIFIED", title="敏感字段未脱敏直出",
         tool="lead_profile", technique="pii_leak", severity="P1",
         status="verified", confirmed_at="2026-11-05", found_at="2026-11-04",
         fixed_at="2026-11-08", verified_run_id="RUN-2026-11-12-003",
         evidence="画像里带出完整手机号。金丝雀 %s。" % CANARY,
         canary=CANARY, owner_role=ROLE_ENG, regression_case_key="LEAD-PII-0011"),
    dict(key="F_P2_WONTFIX", title="知识库过期条目未标注",
         tool="kb_answer", technique="stale_knowledge", severity="P2",
         status="wont_fix", confirmed_at="2026-11-11", found_at="2026-11-10",
         wont_fix_reason="该条目已在下一版资料中下线，不单独修复",
         approved_by_role=ROLE_SEC,
         evidence="过期条目仍被引用。金丝雀 %s。" % CANARY,
         canary=CANARY, owner_role=ROLE_ENG, regression_case_key=None),
    # 跨月样本：found_at 在 10 月、fixed_at 在 11 月。
    # 没有这条样本时，「已修复」按 fixed_at 还是按 found_at 算出来的结果一样，
    # 对应变异（M12）会安静通过 —— 数据里缺该分支。
    dict(key="F_P1_FIXED_CROSS", title="跨月修复：越权写操作未校验 org 边界",
         tool="meeting_minutes", technique="broken_access_control", severity="P1",
         status="fixed", confirmed_at="2026-10-29", found_at="2026-10-28",
         fixed_at="2026-11-05",
         evidence="跨 org 写入未被拒绝。金丝雀 %s。" % CANARY,
         canary=CANARY, owner_role=ROLE_ENG, regression_case_key="MEET-AUTH-0021"),
]

SCENARIOS = [
    ("TODAY_1127", "2026-11-27", "confirmed 2026-11-25 的 2 个工作日截止日当天"),
    ("TODAY_1128", "2026-11-28", "截止日次日起 overdue"),
    ("TODAY_1202", "2026-12-02", "跨周末后仍 overdue"),
]


def write_all(outdir=None):
    out = outdir or os.path.join(ROOT, "data")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "seeds.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"org": ORG, "operator": OPERATOR, "canary": CANARY,
                   "roles": {"sec": ROLE_SEC, "eng": ROLE_ENG},
                   "role_labels": {"security_lead": "安全负责人",
                                   "evaluation_engineer": "评测工程师"},
                   "seeds": SEEDS,
                   "scenarios": [{"key": k, "today": t, "why": w} for k, t, w in SCENARIOS]},
                  f, ensure_ascii=False, indent=1, sort_keys=True)
    return len(SEEDS), len(SCENARIOS)


if __name__ == "__main__":
    a, b = write_all()
    print("WROTE seeds=%d scenarios=%d canary=%s" % (a, b, CANARY))
