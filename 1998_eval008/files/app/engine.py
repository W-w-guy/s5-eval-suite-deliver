# -*- coding: utf-8 -*-
"""复核规则引擎：纯函数，不碰数据库，便于单测与变异测试。

工单规则原文：
  同一用例须有 2 名不同评审人 approve 才变为 reviewed；
  任一 revise 或 remove 则变为 needs_change；
  用例文件内容变更（eval-sync 检测到 hash 变化）后复核状态自动重置。
"""
from __future__ import annotations

REQUIRED_APPROVERS = 2
APPROVE = "approve"
REVISE = "revise"
REMOVE = "remove"
BLOCKING = (REVISE, REMOVE)

STATUS_REVIEWED = "reviewed"
STATUS_NEEDS_CHANGE = "needs_change"
STATUS_PENDING = "pending"


def decide_status(verdicts, current_hash=None, reviewed_hash=None):
    """由一份用例的全部复核记录（按时间升序）推导状态。

    verdicts: list[dict]，每项 {"reviewer_id": str, "verdict": str}
    返回 (status, approvers)
    """
    # 文件改过 -> 强制回到待复核（工单第 3 条规则）
    if current_hash is not None and reviewed_hash is not None and current_hash != reviewed_hash:
        return STATUS_PENDING, []
    if any(v["verdict"] in BLOCKING for v in verdicts):
        return STATUS_NEEDS_CHANGE, sorted({v["reviewer_id"] for v in verdicts
                                            if v["verdict"] == APPROVE})
    approvers = sorted({v["reviewer_id"] for v in verdicts if v["verdict"] == APPROVE})
    # 关键：去重后的不同评审人数，不是记录条数
    if len(approvers) >= REQUIRED_APPROVERS:
        return STATUS_REVIEWED, approvers
    return STATUS_PENDING, approvers


def reset_on_hash_change(old_hash, new_hash, status):
    """eval-sync 检测到 hash 变化时的状态迁移。"""
    if old_hash is not None and new_hash is not None and old_hash != new_hash:
        return STATUS_PENDING
    return status


def can_review(permissions):
    """只有 eval.case.review 权限可评审。"""
    return "eval.case.review" in (permissions or ())
