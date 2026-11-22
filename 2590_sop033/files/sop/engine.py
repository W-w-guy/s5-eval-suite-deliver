"""engine · SOP 运行时（本单核心）
职责：模板加载 → 触发（event / schedule）→ 去重 → 生成实例 → 步骤状态机
     （条件步骤跳过与级联、按锚点算时限、完成校验、取消）。
设计约束（来自工单）：只用虚构数据；金额以分为单位；不向境外发送数据；
     SOP 引擎不得修改会员生命周期状态（AC4）。"""
import json, os, uuid
from copy import deepcopy
from datetime import datetime, timedelta

from . import clock as C
from . import mock as M

INSTANCE_STATES = ("active", "done", "cancelled")
STEP_STATES = ("pending", "active", "done", "skipped", "cancelled", "blocked")


class Instance:
    def __init__(self, iid, template_id, object_type, object_id, created_at):
        self.id = iid
        self.template_id = template_id
        self.object_type = object_type
        self.object_id = object_id
        self.created_at = created_at
        self.state = "active"
        self.steps = []
        self.ctx = {}
        self.cancel_reason = None
    def step(self, sid):
        for s in self.steps:
            if s["id"] == sid:
                return s
        raise KeyError(f"step {sid} not found")
    def flat(self):
        """表达式求值用的扁平视图：实例字段 + ctx.stepN（供 `instance.step2.need_transfer` 这类条件使用）。"""
        d = self.to_dict()
        d.update(self.ctx)
        return d

    def to_dict(self):
        return dict(id=self.id, template_id=self.template_id,
                    object_type=self.object_type, object_id=self.object_id,
                    created_at=self.created_at.isoformat(), state=self.state,
                    cancel_reason=self.cancel_reason,
                    steps=deepcopy(self.steps), ctx=deepcopy(self.ctx))


def _due_at(step, anchor_dt, obj, clock, holidays):
    """按 due.anchor + offset + unit 计算截止时间。"""
    due = step["due"]
    anchor = due.get("anchor", "trigger")
    off = due.get("offset", 0)
    unit = due.get("unit", "work_day")
    if anchor == "trigger":
        base = anchor_dt
    elif anchor == "step_start":
        base = anchor_dt
    elif anchor.startswith("object."):
        key = anchor.split(".", 1)[1]
        v = obj.get(key)
        if v is None:
            return None
        base = v if isinstance(v, datetime) else datetime.fromisoformat(v)
    else:
        raise ValueError(f"bad anchor {anchor}")
    if unit == "work_hour":
        return C.add_work_hours(base, off, holidays)
    if unit == "work_minute":
        return C.add_work_hours(base, off / 60.0, holidays)
    if unit == "work_day":
        return C.add_work_days(base, off, holidays)
    if unit == "natural_day":
        return C.add_natural_days(base, off, holidays)
    raise ValueError(f"bad unit {unit}")


# 条件表达式允许的只读内建函数（不含 open/eval/import 之类）
SAFE_BUILTINS = {"len": len, "abs": abs, "min": min, "max": max,
                 "all": all, "any": any, "str": str, "int": int,
                 "bool": bool, "float": float, "list": list}

def eval_condition(expr, obj, inst=None):
    """只允许在 object/instance 上做只读表达式求值，禁用内建函数与属性穿透。"""
    if not expr:
        return True
    env = {"object": _RO(obj), "instance": _RO(inst or {})}
    return bool(eval(expr, {"__builtins__": SAFE_BUILTINS}, env))  # noqa: S307


def _wrap(v):
    if isinstance(v, dict):
        return _RO(v)
    if isinstance(v, (list, tuple)):
        return [_wrap(x) for x in v]
    return v


class _RO:
    """只读视图：禁止 .update/.save 之类副作用，属性只能读。"""
    def __init__(self, d):
        self.__dict__["_d"] = d or {}
    def __getattr__(self, k):
        if k.startswith("_"):
            raise AttributeError(k)
        d = self.__dict__["_d"]
        if k in d:
            v = d[k]
            # 嵌套字典递归包装，保证 instance.step2.need_transfer 这类链式访问可用
            return _wrap(v)
        # 缺失字段视为 None：条件表达式里必须能安全引用（如 object.loss_reason）,
        # 否则表达式会抛 AttributeError 而不是判定为假 —— 那会让「流失未填原因」静默通过
        return None


class Engine:
    def __init__(self, templates, objects, clock, notifier=None, holidays=None, effects=None):
        self.templates = {t["template_id"]: t for t in templates}
        self.objects = objects            # {object_type: {id: dict}}
        self.clock = clock
        self.notifier = notifier or M.Notifier(M.Notebook())
        self.holidays = holidays or set()
        self.instances = {}
        self.dedupe_log = {}              # (template_id, object_id) -> [created_at, ...]
        self.events_seen = []
        self.audit = []
        self.effects = effects or {}      # {api 名: callable(inst, spec, data)}

    # ---------- 查询 ----------
    def obj(self, template, object_id):
        return self.objects.get(template["target_object"], {}).get(object_id)

    def active_instances(self):
        return [i for i in self.instances.values() if i.state == "active"]

    def instances_of(self, template_id):
        return [i for i in self.instances.values() if i.template_id == template_id]

    # ---------- 触发 ----------
    def _create(self, tpl, object_id, at, trigger_kind):
        iid = f"{tpl['template_id']}-{object_id}-{len(self.instances)+1}"
        inst = Instance(iid, tpl["template_id"], tpl["target_object"], object_id, at)
        obj = self.obj(tpl, object_id) or {}
        for st in tpl["steps"]:
            inst.steps.append(dict(id=st["id"], name=st["name"], role=st["role"],
                                   state="pending", due_at=None, started_at=None,
                                   completed_at=None, skip_reason=None, data=None))
        self.instances[iid] = inst
        self.dedupe_log.setdefault((tpl["template_id"], object_id), []).append(at)
        self.audit.append(dict(op="create", instance=iid, at=at.isoformat(), by=trigger_kind))
        self._activate_next(inst)
        return inst

    def _activate_next(self, inst):
        """把第一个 pending 步骤激活；条件步骤为假则跳过（可级联），直到遇到可执行步骤或结束。"""
        tpl = self.templates[inst.template_id]
        obj = self.obj(tpl, inst.object_id) or {}
        by_id = {s["id"]: s for s in tpl["steps"]}
        for s in inst.steps:
            if s["state"] != "pending":
                continue
            spec = by_id[s["id"]]
            cond = spec.get("condition")
            if spec.get("conditional") and not eval_condition(cond, obj, inst.flat()):
                self._skip(inst, s, spec, f"condition_false: {cond}", obj)
                continue
            now = self.clock.now()
            s["state"] = "active"
            s["started_at"] = now
            s["due_at"] = _due_at(spec, now, obj, self.clock, self.holidays)
            self.notifier.notify(spec["role"], f"[待办] {spec['name']}",
                                 f"实例 {inst.id} 第 {s['id']} 步")
            return s
        # 没有可执行步骤了
        if all(x["state"] in ("done", "skipped") for x in inst.steps):
            inst.state = "done"
        return None

    def _skip(self, inst, step, spec, reason, obj):
        step["state"] = "skipped"
        step["skip_reason"] = reason
        step["completed_at"] = self.clock.now()
        self.audit.append(dict(op="skip", instance=inst.id, step=step["id"],
                               at=self.clock.now().isoformat(), reason=reason))
        if spec.get("cascade_skip") or spec.get("skip_following"):
            for s2 in inst.steps:
                if s2["id"] > step["id"] and s2["state"] == "pending":
                    sp2 = {x["id"]: x for x in self.templates[inst.template_id]["steps"]}[s2["id"]]
                    self._skip(inst, s2, sp2, f"cascade_after_step_{step['id']}", obj)

    # ---------- 完成步骤 ----------
    def complete_step(self, inst_id, sid, data=None):
        inst = self.instances[inst_id]
        if inst.state != "active":
            raise ValueError(f"instance {inst_id} is {inst.state}, cannot complete")
        st = inst.step(sid)
        if st["state"] != "active":
            raise ValueError(f"step {sid} is {st['state']}, cannot complete")
        spec = {x["id"]: x for x in self.templates[inst.template_id]["steps"]}[sid]
        self._validate_outputs(inst, spec, data or {})
        st["state"] = "done"
        st["completed_at"] = self.clock.now()
        st["data"] = data or {}
        inst.ctx[f"step{sid}"] = data or {}
        self._run_effect(inst, spec, data or {})
        self.audit.append(dict(op="complete", instance=inst.id, step=sid,
                               at=self.clock.now().isoformat()))
        if self._maybe_cancel(inst, spec, data or {}):
            return inst
        self._activate_next(inst)
        return inst

    def _maybe_cancel(self, inst, spec, data):
        """步骤完成时按答案取消实例（如「到访登记选择未到访」）。
        模板用 cancel_if 声明：{when, reason, notify:[roles]}。"""
        ci = spec.get("cancel_if")
        if not ci:
            return False
        if not eval_condition(ci.get("when"), data, inst.flat()):
            return False
        self.cancel(inst, ci.get("reason") or f"cancel_if@{spec['id']}")
        for role in ci.get("notify") or []:
            self.notifier.notify(role, f"[实例取消] {spec['name']}",
                                 f"实例 {inst.id} 因 {ci.get('reason')} 取消")
        return True

    def skip_step(self, inst_id, sid, reason=None):
        """人工跳过（模板须声明 allow_skip）。要求填原因的步骤不给原因即拒绝。"""
        inst = self.instances[inst_id]
        st = inst.step(sid)
        if st["state"] != "active":
            raise ValueError(f"step {sid} is {st['state']}, cannot skip")
        spec = {x["id"]: x for x in self.templates[inst.template_id]["steps"]}[sid]
        if not spec.get("allow_skip"):
            raise ValueError(f"step {sid} 未声明 allow_skip，不允许人工跳过")
        if spec.get("skip_reason_required") and not (reason or "").strip():
            raise ValueError(f"step {sid} 要求填写跳过原因")
        self._skip(inst, st, spec, f"manual: {reason}", self.obj(self.templates[inst.template_id], inst.object_id) or {})
        self._activate_next(inst)
        return inst

    def _run_effect(self, inst, spec, data):
        """步骤完成时的副作用（如调用知识缺口接口）。when 为假则不调用。"""
        eff = spec.get("effect")
        if not eff:
            return
        if eff.get("when") and not eval_condition(eff["when"], data, inst.flat()):
            return
        fn = self.effects.get(eff["api"])
        if fn is None:
            raise RuntimeError(f"效应 {eff['api']} 未注册处理函数")
        fn(inst, spec, data)

    def _validate_outputs(self, inst, spec, data):
        """输出字段校验：required_outputs 全部非空；checklist 全部 true；
        以及模板自定义的 blocking 规则（如「遗留未转交数必须为 0」）。"""
        missing = [k for k in spec.get("required_outputs", [])
                   if data.get(k) in (None, "", [], {})]
        if missing:
            raise ValueError(f"步骤 {spec['id']} 缺少必填输出 {missing}")
        unchecked = [k for k in spec.get("checklist", [])
                     if not data.get("_checklist", {}).get(k, True)]
        if unchecked:
            raise ValueError(f"步骤 {spec['id']} 检查项未完成 {unchecked}")
        rule = spec.get("blocking_rule")
        if rule:
            expr = rule["when"]
            if eval_condition(expr, data, inst.flat()):
                raise ValueError(f"步骤 {spec['id']} 不满足完成条件: {rule['message']}")

    # ---------- 事件 ----------
    def handle_event(self, name, object_id, payload=None):
        payload = payload or {}
        self.events_seen.append((name, object_id, self.clock.now().isoformat()))
        done = []
        for tpl in self.templates.values():
            trg = tpl["trigger"]
            # cancel_on 与触发类型无关：定时触发的模板同样可以被事件取消
            # （首版把这段放在 type=="event" 的 continue 之后，导致 renewal 永不取消）
            if trg.get("cancel_on") == name:
                for inst in self.instances_of(tpl["template_id"]):
                    if inst.object_id == object_id and inst.state == "active":
                        self.cancel(inst, name)
                        done.append(("cancelled", inst.id))
            if trg.get("type") != "event":
                continue
            if trg.get("event") == name:
                if self._dedupe_hit(tpl, object_id):
                    done.append(("deduped", object_id))
                    continue
                inst = self._create(tpl, object_id, self.clock.now(), f"event:{name}")
                done.append(("created", inst.id))
        return done

    def _dedupe_hit(self, tpl, object_id):
        """去重判定：同一模板 + 同一对象，在 dedupe 窗口内已有实例则不再新建。
        event 型的窗口取 trigger.dedupe_days（默认 0=不去重）；schedule 型必填。"""
        days = tpl["trigger"].get("dedupe_days")
        if not days:
            return False
        prev = self.dedupe_log.get((tpl["template_id"], object_id), [])
        now = self.clock.now()
        return any((now - t) < timedelta(days=days) for t in prev)

    def cancel(self, inst, reason):
        inst.state = "cancelled"
        inst.cancel_reason = reason
        for s in inst.steps:
            if s["state"] in ("pending", "active"):
                s["state"] = "cancelled"
        self.audit.append(dict(op="cancel", instance=inst.id,
                               at=self.clock.now().isoformat(), reason=reason))
        return inst

    # ---------- 定时触发 ----------
    def tick(self, repositories):
        """跑一次定时调度：对每个 schedule 模板，若当前时刻命中 cron 的 HH:MM，
        执行命名查询 → 去重 → 逐对象生成实例。repositories: {query_name: repo}"""
        now = self.clock.now()
        ran = []
        for tpl in self.templates.values():
            trg = tpl["trigger"]
            if trg.get("type") != "schedule":
                continue
            if not self._cron_hit(trg["cron"], now):
                continue
            repo = repositories[trg["query"]]
            rows = repo.query(trg["query"], days=trg.get("query_days", 0), now=now)
            made = 0
            for row in rows:
                oid = row["id"]
                if self._dedupe_hit(tpl, oid):
                    continue
                self._create(tpl, oid, now, "schedule")
                made += 1
            ran.append(dict(template=tpl["template_id"], at=now.isoformat(),
                            matched=len(rows), created=made))
        return ran

    @staticmethod
    def _cron_hit(cron, now):
        """支持 'MM HH * * *' 形态（本族只用每日固定时刻）。"""
        parts = cron.split()
        if len(parts) != 5:
            raise ValueError(f"unsupported cron {cron!r}")
        mi, hh = parts[0], parts[1]
        if mi != "*" and int(mi) != now.minute:
            return False
        if hh != "*" and int(hh) != now.hour:
            return False
        return True

    def project_due(self, inst):
        """一次性算出全部步骤的预计截止时间（用于导入后预览时间轴）。
        锚点为 trigger/step_start 的按实例创建时间起算（step_start 为估算值）。"""
        tpl = self.templates[inst.template_id]
        obj = self.obj(tpl, inst.object_id) or {}
        out = {}
        for spec in tpl["steps"]:
            out[spec["id"]] = _due_at(spec, inst.created_at, obj, self.clock, self.holidays)
        return out

    # ---------- 快照 ----------
    def snapshot(self):
        return dict(instances=[i.to_dict() for i in self.instances.values()],
                    audit=deepcopy(self.audit),
                    dedupe={f"{k[0]}|{k[1]}": [t.isoformat() for t in v]
                            for k, v in self.dedupe_log.items()})
