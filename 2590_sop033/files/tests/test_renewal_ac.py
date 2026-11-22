# -*- coding: utf-8 -*-
"""2590「续约预警」验收测试：逐条对应工单 AC 1-4，另加边界用例。
运行：python tests/test_renewal_ac.py        退出码 0=全通过"""
import json, os, sys, traceback
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sop import lint, clock as C, mock as M
from sop.engine import Engine

TPL_PATH = os.path.join(ROOT, "templates", "renewal.json")
PASS = 0
FAIL = 0
RESULTS = []

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; RESULTS.append(("PASS", name, detail))
    else:
        FAIL += 1; RESULTS.append(("FAIL", name, detail))

def load():
    return json.load(open(TPL_PATH, encoding="utf-8"))


def make_world(now, expire_at, health=55, key_member=False, mids=("m-001",)):
    """虚构数据世界：一条会籍 + 引擎。"""
    nb = M.Notebook()
    guard = M.CrmWriteGuard(nb)
    rows = []
    for i, mid in enumerate(mids):
        rows.append({"id": mid, "org_id": "org-v", "site_id": "site-v",
                     "health_score": health, "is_key_member": key_member,
                     "expire_at": expire_at, "lifecycle_status": "active",
                     "churn_warning_at": None})
    repo = M.MembershipRepo(rows, nb)
    clk = C.FrozenClock(now)
    tpl = load()
    eng = Engine([tpl], {"membership": {r["id"]: r for r in repo.all()}},
                 clk, notifier=M.Notifier(nb))
    return eng, repo, guard, clk, nb


def test_ac1_lint_and_publish():
    tpl = load()
    fs = lint.lint(tpl)
    errs = [x for x in fs if x.level == "ERROR"]
    check("AC1.1 sop-lint 无 ERROR", not errs, str(errs))
    check("AC1.2 template_id/version/target_object 齐备",
          bool(tpl["template_id"]) and bool(tpl["version"])
          and tpl["target_object"] == "membership")
    check("AC1.3 触发为定时每日 09:00 且去重 120 天",
          tpl["trigger"]["type"] == "schedule"
          and tpl["trigger"]["cron"] == "0 9 * * *"
          and tpl["trigger"]["dedupe_days"] == 120)
    # 「导入后可发布」= 能被引擎无异常加载，且步骤构成完整
    eng, *_ = make_world(datetime(2026, 3, 2, 9, 0), datetime(2026, 5, 31, 0, 0))
    check("AC1.4 引擎可加载模板（可发布）", eng.templates.get(tpl["template_id"]) is not None)


def test_ac2_frozen_clock_trigger_and_dedupe():
    now = datetime(2026, 3, 2, 9, 0)          # 触发当天 09:00
    expire = now + timedelta(days=90)         # 会籍到期前 90 天
    eng, repo, guard, clk, nb = make_world(now, expire)

    ran = eng.tick({"membership_expiring_within": repo})
    check("AC2.1 09:00 定时任务命中并生成实例", len(eng.instances) == 1, str(ran))
    check("AC2.2 命中命名查询 membership_expiring_within(days=90)",
          any(c["api"] == "query" and c.get("name") == "membership_expiring_within"
              and c["params"].get("days") == 90 for c in nb.calls),
          str(nb.apis()))

    inst = list(eng.instances.values())[0]
    check("AC2.3 实例绑定 membership 对象且第一步已派给会员经理",
          inst.object_type == "membership" and inst.object_id == "m-001"
          and inst.steps[0]["state"] == "active"
          and eng.templates[inst.template_id]["steps"][0]["role"] == "会员经理")

    # 120 天内不重复触发
    clk.set("2026-03-02 10:00")
    eng.tick({"membership_expiring_within": repo})
    check("AC2.4 同日再次调度不重复生成", len(eng.instances) == 1, f"{len(eng.instances)}")

    clk.set("2026-06-29 09:00")   # +119 天
    eng.tick({"membership_expiring_within": repo})
    check("AC2.5 119 天后仍在去重窗口内，不生成", len(eng.instances) == 1, f"{len(eng.instances)}")

    tpl = load()
    key = (tpl["template_id"], "m-001")
    clk.set("2026-07-01 09:00")   # +121 天
    check("AC2.6 121 天后去重窗口已过", eng._dedupe_hit(tpl, "m-001") is False)
    clk.set("2026-06-29 09:00")   # +119 天
    check("AC2.7 119 天仍在窗口内", eng._dedupe_hit(tpl, "m-001") is True)
    clk.set("2026-06-30 09:00")   # +120 天，窗口为 [0,120) 半开区间
    check("AC2.8 满 120 天窗口关闭", eng._dedupe_hit(tpl, "m-001") is False)


def test_ac3_skip_management_step():
    now = datetime(2026, 3, 2, 9, 0)
    expire = now + timedelta(days=90)
    # 非重点会员 + 健康分 55（>=40）→ 第③步应跳过
    eng, repo, guard, clk, nb = make_world(now, expire, health=55, key_member=False)
    eng.tick({"membership_expiring_within": repo})
    inst = list(eng.instances.values())[0]
    eng.complete_step(inst.id, 1, {"health_score_snapshot": 55, "interactions_90d": 12,
                                   "risk_reason": ["续约价格敏感"], "renewal_intent": "犹豫"})
    eng.complete_step(inst.id, 2, {"care_action": "高层拜访", "plan_date": "2026-03-10",
                                   "ai_care_draft": "占位草稿"})
    s3 = inst.step(3)
    check("AC3.1 非重点且健康分>=40 → 第③步 skipped", s3["state"] == "skipped", s3["state"])
    check("AC3.2 跳过原因已记录", bool(s3["skip_reason"]), str(s3["skip_reason"]))
    check("AC3.3 跳过后第④步被激活", inst.step(4)["state"] == "active", inst.step(4)["state"])

    # 反例 1：重点会员 → 不跳过
    eng2, repo2, *_ = make_world(now, expire, health=55, key_member=True)
    eng2.tick({"membership_expiring_within": repo2})
    i2 = list(eng2.instances.values())[0]
    eng2.complete_step(i2.id, 1, {"health_score_snapshot": 55, "interactions_90d": 3,
                                  "risk_reason": ["业务收缩"], "renewal_intent": "犹豫"})
    eng2.complete_step(i2.id, 2, {"care_action": "需求复盘会", "plan_date": "2026-03-11",
                                  "ai_care_draft": "占位"})
    check("AC3.4 重点会员 → 第③步必须生成", i2.step(3)["state"] == "active", i2.step(3)["state"])

    # 反例 2：健康分 39 < 40 → 不跳过
    eng3, repo3, *_ = make_world(now, expire, health=39, key_member=False)
    eng3.tick({"membership_expiring_within": repo3})
    i3 = list(eng3.instances.values())[0]
    eng3.complete_step(i3.id, 1, {"health_score_snapshot": 39, "interactions_90d": 1,
                                  "risk_reason": ["服务价值感知不足"], "renewal_intent": "倾向流失"})
    eng3.complete_step(i3.id, 2, {"care_action": "专属权益升级", "plan_date": "2026-03-12",
                                  "ai_care_draft": "占位"})
    check("AC3.5 健康分 39<40 → 第③步必须生成", i3.step(3)["state"] == "active", i3.step(3)["state"])


def test_ac4_lifecycle_untouched():
    now = datetime(2026, 3, 2, 9, 0)
    expire = now + timedelta(days=90)
    eng, repo, guard, clk, nb = make_world(now, expire, health=55)
    eng.tick({"membership_expiring_within": repo})
    inst = list(eng.instances.values())[0]
    eng.complete_step(inst.id, 1, {"health_score_snapshot": 55, "interactions_90d": 8,
                                   "risk_reason": ["对接人变更"], "renewal_intent": "倾向续约"})
    eng.complete_step(inst.id, 2, {"care_action": "资源对接沙龙", "plan_date": "2026-03-15",
                                   "ai_care_draft": "占位"})
    # 第③步被跳过（非重点+健康分55），无需完成
    eng.complete_step(inst.id, 4, {"quote_id": "Q-2026-0001"})
    eng.complete_step(inst.id, 5, {"outcome": "续约"})

    check("AC4.1 第⑤步已完成", inst.step(5)["state"] == "done", inst.step(5)["state"])
    check("AC4.2 实例状态 done", inst.state == "done", inst.state)
    check("AC4.3 SOP 引擎未调用 CRM 生命周期写入接口",
          len(guard.blocked) == 0 and "crm.update_lifecycle_status" not in nb.apis(),
          f"blocked={guard.blocked}")
    check("AC4.4 membership.lifecycle_status 仍为 active",
          repo.get("m-001")["lifecycle_status"] == "active",
          repo.get("m-001")["lifecycle_status"])
    check("AC4.5 引擎对象副本也未改状态",
          eng.obj(eng.templates[inst.template_id], "m-001")["lifecycle_status"] == "active")
    # 正面证明守卫真的会拦（否则 AC4.3 可能是「压根没实现写入」的假通过）
    raised = False
    try:
        guard.update_lifecycle_status("m-001", "renewed", "staff-x")
    except PermissionError:
        raised = True
    check("AC4.6 CRM 守卫确实会拒绝 SOP 侧写入（排除假通过）", raised, str(guard.blocked))


def test_extra_edges():
    now = datetime(2026, 3, 2, 9, 0)
    expire = now + timedelta(days=90)
    # 步骤时限：①+3 工作日、②+5 工作日；④=到期前30自然日、⑤=到期前7自然日
    eng, repo, guard, clk, nb = make_world(now, expire)
    eng.tick({"membership_expiring_within": repo})
    inst = list(eng.instances.values())[0]
    check("EX1 第①步截止 = 触发后 3 个工作日 18:00",
          inst.step(1)["due_at"].date() == datetime(2026, 3, 5).date(),
          str(inst.step(1)["due_at"]))
    eng.complete_step(inst.id, 1, {"health_score_snapshot": 55, "interactions_90d": 8,
                                   "risk_reason": ["其他"], "renewal_intent": "犹豫"})
    check("EX2 第②步截止 = 完成后 5 个工作日（周一 03-02 +5 工作日 = 周一 03-09）",
          inst.step(2)["due_at"].date() == datetime(2026, 3, 9).date(),
          str(inst.step(2)["due_at"]))
    eng.complete_step(inst.id, 2, {"care_action": "高层拜访",
                                   "plan_date": "2026-03-10", "ai_care_draft": "占位"})
    check("EX3 第④步锚定 object.expire_at - 30 自然日",
          inst.step(4)["due_at"] == expire - timedelta(days=30), str(inst.step(4)["due_at"]))
    eng.complete_step(inst.id, 4, {"quote_id": "Q-2026-0001"})
    check("EX4 第⑤步锚定 object.expire_at - 7 自然日",
          inst.step(5)["due_at"] == expire - timedelta(days=7), str(inst.step(5)["due_at"]))

    # 取消：membership.renewed
    eng2, repo2, *_ = make_world(now, expire)
    eng2.tick({"membership_expiring_within": repo2})
    i2 = list(eng2.instances.values())[0]
    eng2.handle_event("membership.renewed", "m-001")
    check("EX5 收到 membership.renewed 后实例被取消", i2.state == "cancelled", i2.state)
    check("EX6 未完成待办一并取消",
          i2.step(1)["state"] == "cancelled", i2.step(1)["state"])

    # 输出校验：不符规则时不得完成
    eng3, repo3, *_ = make_world(now, expire)
    eng3.tick({"membership_expiring_within": repo3})
    i3 = list(eng3.instances.values())[0]
    bad = False
    try:
        eng3.complete_step(i3.id, 1, {"health_score_snapshot": 55})
    except ValueError:
        bad = True
    check("EX7 缺必填输出时拒绝完成第①步", bad)

    # 第⑤步：流失必须填原因
    eng3.complete_step(i3.id, 1, {"health_score_snapshot": 55, "interactions_90d": 5,
                                  "risk_reason": ["其他"], "renewal_intent": "犹豫"})
    eng3.complete_step(i3.id, 2, {"care_action": "高层拜访", "plan_date": "2026-03-10",
                                  "ai_care_draft": "占位"})
    eng3.complete_step(i3.id, 4, {"quote_id": "Q-1"})
    bad2 = False
    try:
        eng3.complete_step(i3.id, 5, {"outcome": "流失"})
    except ValueError:
        bad2 = True
    check("EX8 选流失未填原因时拒绝完成第⑤步", bad2)


def main():
    tests = [test_ac1_lint_and_publish, test_ac2_frozen_clock_trigger_and_dedupe,
             test_ac3_skip_management_step, test_ac4_lifecycle_untouched,
             test_extra_edges]
    for t in tests:
        try:
            t()
        except Exception:
            global FAIL
            FAIL += 1
            RESULTS.append(("FAIL", t.__name__ + " 抛异常", traceback.format_exc().splitlines()[-1]))
    print("=" * 62)
    for st, name, detail in RESULTS:
        print(f"{st}  {name}" + (f"   [{detail}]" if st == "FAIL" and detail else ""))
    print("=" * 62)
    print(f"合计 {PASS + FAIL} 项：PASS {PASS} / FAIL {FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
