# -*- coding: utf-8 -*-
"""状态机与业务规则。

状态：new → confirmed → fixing → fixed → verified
                     ↘ wont_fix（需审批 + 理由，P0 禁止）
verified 只能由「验证运行自动触发」或「安全负责人手动确认并填 run_id」进入。
"""
STATUSES = ("new", "confirmed", "fixing", "fixed", "verified", "wont_fix")
SEVERITIES = ("P0", "P1", "P2")

# ---- 行为开关（集中此处，便于变异测试锚定） ----
P0_CANNOT_WONT_FIX = True
WONT_FIX_NEEDS_APPROVAL = True
VERIFIED_NEEDS_RUN_ID = True
ENFORCE_TRANSITION = True

PERM_WRITE = "eval.redteam.write"
PERM_APPROVE = "eval.redteam.approve"
APPROVER_ROLE = "security_lead"      # HTTP 头只能承载 ASCII，中文仅作展示名
ROLE_LABELS = {"security_lead": "安全负责人",
               "evaluation_engineer": "评测工程师"}

# 合法迁移表
TRANSITIONS = {
    "new": {"confirmed", "wont_fix"},
    "confirmed": {"fixing", "wont_fix"},
    "fixing": {"fixed", "wont_fix"},
    "fixed": {"verified", "fixing"},
    "verified": set(),
    "wont_fix": set(),
}


class RuleError(ValueError):
    """业务规则拒绝。422 用它；403 用 PermissionError；409 用 StateConflict。"""


class PermissionError_(PermissionError):
    """权限不足（403）。"""


class StateConflict(ValueError):
    """状态冲突（409）。"""


def check_transition(cur, nxt):
    if not ENFORCE_TRANSITION:
        return
    if nxt not in STATUSES:
        raise RuleError("未知状态 %r" % (nxt,))
    if nxt == cur:
        raise RuleError("状态未变化（当前已是 %s）" % cur)
    allowed = TRANSITIONS.get(cur, set())
    if nxt not in allowed:
        raise RuleError("不允许从 %s 迁移到 %s（允许：%s）"
                        % (cur, nxt, sorted(allowed) or "无"))


def check_wont_fix(finding, reason, approved_by_role):
    """wont_fix：P0 禁止；必须审批 + 写理由。"""
    if finding["severity"] == "P0" and P0_CANNOT_WONT_FIX:
        raise RuleError("P0 发现不允许标记 wont_fix（严重度零容忍）")
    if WONT_FIX_NEEDS_APPROVAL:
        if not str(reason or "").strip():
            raise RuleError("wont_fix 必须填写理由")
        if str(approved_by_role or "").strip() != APPROVER_ROLE:
            raise RuleError("wont_fix 需 %s 审批，当前审批角色为 %r"
                            % (APPROVER_ROLE, approved_by_role))
    return True


def check_verified(finding, run_id, trigger):
    """verified 的两种进入方式：验证运行自动触发，或安全负责人手动确认并填 run_id。"""
    if not VERIFIED_NEEDS_RUN_ID:
        return True
    if not str(run_id or "").strip():
        raise RuleError("进入 verified 必须填写验证运行 run_id")
    if trigger not in ("auto_run", "manual"):
        raise RuleError("trigger 只能是 auto_run 或 manual")
    if trigger == "manual" and finding.get("status") != "fixed":
        raise RuleError("手动确认只能从 fixed 迁移到 verified")
    return True


def check_permission(perms, need):
    if need not in (perms or ()):
        raise PermissionError_("缺少权限 %s" % need)
    return True
