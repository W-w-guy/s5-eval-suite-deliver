# -*- coding: utf-8 -*-
"""变异测试：证明 sop-lint 与引擎不是「怎么改都通过」。
A 部分：对 renewal.json 注入一批结构性缺陷，lint 必须报 ERROR。
B 部分：对 renewal 做引擎行为变异，行为必须随配置一起失效。
每条变异都必须被检出；未被检出的即校验器盲区。
运行：python tests/mutate.py"""
import copy, glob, json, os, sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from sop import lint, clock as C, mock as M
from sop.engine import Engine

TEMPLATE_DIR = os.path.join(ROOT, "templates")
TEMPLATES = {os.path.basename(p)[:-5]: json.load(open(p, encoding="utf-8"))
             for p in sorted(glob.glob(os.path.join(TEMPLATE_DIR, "*.json")))}
PASS = 0
FAIL = 0
MISSES = []

def ok(desc):
    global PASS
    PASS += 1
    print(f"  检出  {desc}")

def miss(desc):
    global FAIL
    FAIL += 1
    MISSES.append(desc)
    print(f"  漏检  {desc}  <<< 盲区")


class _Del:
    def __repr__(self):
        return "<DEL>"
DEL = _Del()


def setpath(obj, path, val):
    parts = path.split(".")
    cur = obj
    for p in parts[:-1]:
        if p.isdigit():
            cur = cur[int(p)]
        else:
            cur = cur[p]
    last = parts[-1]
    if last.isdigit():
        cur[int(last)] = val
    elif val is DEL:
        cur.pop(last, None)
    else:
        cur[last] = val
    return obj


def mutations_for(name):
    """返回 [(描述, 变异函数)]。结构性缺陷对每个模板都成立，故逐个模板各跑一遍。"""
    n_steps = len(TEMPLATES[name]["steps"])
    tpl = TEMPLATES[name]
    trg = tpl["trigger"]
    out = [
        ("删掉 trigger", lambda t: setpath(t, "trigger", DEL)),
        ("trigger.type 改成非法值", lambda t: setpath(t, "trigger.type", "cron")),
        ("example_data_virtual 置 false",
         lambda t: setpath(t, "example_data_virtual", False)),
        ("steps 清空", lambda t: setpath(t, "steps", [])),
        ("metric 换成空串", lambda t: setpath(t, "metric", "")),
        ("步骤 id 重复", lambda t: setpath(t, f"steps.1.id", t["steps"][0]["id"])),
        ("删掉第 1 步 role", lambda t: setpath(t, "steps.0.role", DEL)),
        ("第 1 步升级方式改成 email", lambda t: setpath(t, "steps.0.escalate", "email")),
        ("第 1 步时限单位改成 hour", lambda t: setpath(t, "steps.0.due.unit", "hour")),
        ("第 1 步时限锚点改成 made_up",
         lambda t: setpath(t, "steps.0.due.anchor", "object.made_up")),
        ("第 1 步 offset 改成字符串", lambda t: setpath(t, "steps.0.due.offset", "3")),
        ("非条件步骤硬塞 condition", lambda t: setpath(t, "steps.0.condition", "object.x > 0")),
        ("话术里写入真实手机号",
         lambda t: setpath(t, "scripts", dict(t.get("scripts") or {}, _probe="联系 13812345678"))),  # pii-scan:allow negative-fixture
        ("话术里写入真实邮箱",
         lambda t: setpath(t, "scripts", dict(t.get("scripts") or {}, _probe="发 lisi@qq.com"))),  # pii-scan:allow negative-fixture
    ]
    if trg.get("type") == "schedule":
        out += [
            ("定时触发删掉 cron", lambda t: setpath(t, "trigger.cron", DEL)),
            ("cron 段数不足", lambda t: setpath(t, "trigger.cron", "0 9 *")),
            ("去重窗口改成 0", lambda t: setpath(t, "trigger.dedupe_days", 0)),
            ("去重窗口改成字符串", lambda t: setpath(t, "trigger.dedupe_days", "120")),
            ("cancel_on 写成中文", lambda t: setpath(t, "trigger.cancel_on", "会员续约")),
        ]
    else:
        out += [
            ("事件名不合规", lambda t: setpath(t, "trigger.event", "membershipActivated")),
            ("cancel_on 写成中文", lambda t: setpath(t, "trigger.cancel_on", "会员续约")),
        ]
    # 条件步骤：删掉 condition 必须报错
    for i, st in enumerate(tpl["steps"]):
        if st.get("conditional"):
            out.append((f"第 {st['id']} 步（条件步骤）删掉 condition",
                        lambda t, i=i: setpath(t, f"steps.{i}.condition", DEL)))
            break
    # 人工跳过标记：只声明 skip_reason_required 而未声明 allow_skip
    for i, st in enumerate(tpl["steps"]):
        if st.get("allow_skip"):
            out.append((f"第 {st['id']} 步只声明 skip_reason_required",
                        lambda t, i=i: setpath(t, f"steps.{i}.allow_skip", DEL)))
            break
    return out


def run_lint_mutations():
    for name, tpl in TEMPLATES.items():
        print(f"[{name}]")
        base_errs = [x for x in lint.lint(copy.deepcopy(tpl)) if x.level == "ERROR"]
        if base_errs:
            miss(f"{name} 原件本身就有 ERROR: {base_errs[0]}")
            continue
        for desc, fn in mutations_for(name):
            t = fn(copy.deepcopy(tpl))
            fs = [x for x in lint.lint(t) if x.level == "ERROR"]
            if fs:
                ok(f"{name}: {desc} -> {fs[0].code}")
            else:
                miss(f"{name}: {desc}")


# ---------------- B 部分：引擎行为变异 ----------------
def world(tpl, objects, now, effects=None):
    nb = M.Notebook()
    clk = C.FrozenClock(now)
    eng = Engine([tpl], objects, clk, notifier=M.Notifier(nb), effects=effects or {})
    return eng, clk, nb


def run_engine_mutations():
    # 1) renewal：cron 改到 10:00 → 09:00 不再触发
    tpl = copy.deepcopy(TEMPLATES["renewal"])
    setpath(tpl, "trigger.cron", "0 10 * * *")
    nb = M.Notebook()
    repo = M.MembershipRepo([dict(id="m1", org_id="o", site_id="s", health_score=60,
                                  is_key_member=False, expire_at=datetime(2026, 5, 31),
                                  lifecycle_status="active", churn_warning_at=None)], nb)
    eng, clk, _ = world(tpl, {"membership": {"m1": repo.all()[0]}}, "2026-03-02 09:00")
    eng.tick({"membership_expiring_within": repo})
    ok("renewal: cron 改到 10:00 后 09:00 不再触发") if not eng.instances else miss("renewal: cron 改到 10:00 后仍触发")

    # 2) renewal：去重窗口改 1 天 → 隔 2 天重复生成；原模板不重复
    def mk(dedupe):
        t = copy.deepcopy(TEMPLATES["renewal"])
        setpath(t, "trigger.dedupe_days", dedupe)
        nb2 = M.Notebook()
        r = M.MembershipRepo([dict(id="m1", org_id="o", site_id="s", health_score=60,
                                   is_key_member=False, expire_at=datetime(2026, 5, 31),
                                   lifecycle_status="active", churn_warning_at=None)], nb2)
        e, c, _ = world(t, {"membership": {"m1": r.all()[0]}}, "2026-03-02 09:00")
        e.tick({"membership_expiring_within": r})
        c.set("2026-03-04 09:00")
        e.tick({"membership_expiring_within": r})
        return len(e.instances)
    ok("renewal: 去重窗口改 1 天后隔 2 天重复生成") if mk(1) >= 2 else miss("renewal: 去重窗口改 1 天后仍只生成 1 个")
    ok("renewal: 对照原模板隔 2 天仍只有 1 个实例") if mk(120) == 1 else miss("renewal: 原模板隔 2 天出现了重复实例")

    # 3) renewal：取消条件删掉 → membership.renewed 不再取消
    t = copy.deepcopy(TEMPLATES["renewal"])
    setpath(t, "trigger.cancel_on", DEL)
    nb = M.Notebook()
    repo = M.MembershipRepo([dict(id="m1", org_id="o", site_id="s", health_score=60,
                                  is_key_member=False, expire_at=datetime(2026, 5, 31),
                                  lifecycle_status="active", churn_warning_at=None)], nb)
    eng, _, _ = world(t, {"membership": {"m1": repo.all()[0]}}, "2026-03-02 09:00")
    eng.tick({"membership_expiring_within": repo})
    inst = list(eng.instances.values())[0]
    eng.handle_event("membership.renewed", "m1")
    ok("renewal: 删掉 cancel_on 后续约事件不再取消实例") if inst.state == "active" else miss("renewal: 删掉 cancel_on 后仍被取消")

    # 4) renewal：第③步条件改成只看重点会员 → 健康分 39 被误跳过
    t = copy.deepcopy(TEMPLATES["renewal"])
    setpath(t, "steps.2.condition", "object.is_key_member")
    nb = M.Notebook()
    repo = M.MembershipRepo([dict(id="m1", org_id="o", site_id="s", health_score=39,
                                  is_key_member=False, expire_at=datetime(2026, 5, 31),
                                  lifecycle_status="active", churn_warning_at=None)], nb)
    eng, _, _ = world(t, {"membership": {"m1": repo.all()[0]}}, "2026-03-02 09:00")
    eng.tick({"membership_expiring_within": repo})
    i = list(eng.instances.values())[0]
    eng.complete_step(i.id, 1, {"health_score_snapshot": 39, "interactions_90d": 1,
                                "risk_reason": ["其他"], "renewal_intent": "犹豫"})
    eng.complete_step(i.id, 2, {"care_action": "高层拜访", "plan_date": "d",
                                "ai_care_draft": "x"})
    ok("renewal: 条件改坏后健康分 39 的第③步被误跳过") if i.step(3)["state"] == "skipped" else miss("renewal: 条件改坏后第③步仍生成")

if __name__ == "__main__":
    print("=" * 66)
    print(f"A. 静态校验变异（1 个模板 × 结构性缺陷，期望 lint 报 ERROR）")
    run_lint_mutations()
    print("B. 引擎行为变异（期望行为随配置一起失效）")
    run_engine_mutations()
    print("=" * 66)
    print(f"变异断言 {PASS + FAIL} 条：检出 {PASS} / 漏检 {FAIL}")
    if MISSES:
        print("盲区清单：")
        for m in MISSES:
            print("  -", m)
    else:
        print("全部变异均被检出，校验器无盲区")
    sys.exit(0 if FAIL == 0 else 1)
