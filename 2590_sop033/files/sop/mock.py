"""mock · 本单依赖的 S2-CRM / S2-SPACE / S1-SOP 接口桩
官方说明「依赖其他工单的接口时，用接口桩或 mock 先行，并在 README 写明对接点」，
所以这里的每个类都标注了真实接口的对接点。"""
from copy import deepcopy


class Notebook:
    """记录所有出站调用，供测试断言。"""
    def __init__(self):
        self.calls = []
    def add(self, api, **kw):
        self.calls.append(dict(api=api, **kw))
        return self.calls[-1]
    def apis(self):
        return [c["api"] for c in self.calls]


class MembershipRepo:
    """【对接点】S2-CRM membership 表：id/org_id/health_score/is_key_member/
    expire_at/lifecycle_status/churn_warning_at。本 mock 只读，不写。"""
    def __init__(self, rows, notebook=None):
        self._rows = {r["id"]: deepcopy(r) for r in rows}
        self.nb = notebook or Notebook()
    def all(self):
        return [deepcopy(r) for r in self._rows.values()]
    def get(self, mid):
        r = self._rows.get(mid)
        return deepcopy(r) if r else None
    def query(self, name, **params):
        """命名查询。本单用到 membership_expiring_within(days=N)。"""
        self.nb.add("query", name=name, params=params)
        if name == "membership_expiring_within":
            days = int(params["days"])
            base = params["now"]
            out = []
            for r in self._rows.values():
                exp = r["expire_at"]
                delta = (exp - base).total_seconds() / 86400.0
                if 0 < delta <= days:
                    out.append(deepcopy(r))
                elif r.get("churn_warning_at") and delta > 0 and r not in out:
                    out.append(deepcopy(r))
            return out
        raise ValueError(f"unknown query {name}")


class CrmWriteGuard:
    """【本单 AC4 的关键】会员生命周期状态的唯一写入方是员工在 CRM 中确认。
    这里故意提供一个会抛错的写入口，任何 SOP 引擎试图改 status 都会被记录并拦截。"""
    def __init__(self, notebook=None):
        self.nb = notebook or Notebook()
        self.blocked = []
    def update_lifecycle_status(self, membership_id, status, operator):
        self.blocked.append(dict(membership_id=membership_id, status=status, operator=operator))
        raise PermissionError("SOP 引擎不得修改会员生命周期状态，须由员工在 CRM 中确认")


class KnowledgeGapApi:
    """【对接点】知识库 S3-KB：POST /api/v1/kb/gaps 创建知识缺口。"""
    def __init__(self, notebook):
        self.nb = notebook
    def create_gap(self, title, source_instance, source_step):
        self.nb.add("kb.gap.create", title=title, instance=source_instance, step=source_step)
        return {"gap_id": "gap-mock-1", "title": title}


class TodoApi:
    """【对接点】SOP 工作台待办：批量转交 POST /api/v1/sop/todos/transfer。"""
    def __init__(self, notebook, todos):
        self.nb = notebook
        self.todos = [dict(t) for t in todos]
    def open_todos_of(self, staff_id):
        return [t for t in self.todos if t.get("assignee") == staff_id and t.get("state") == "open"]
    def transfer_all(self, from_staff, to_map):
        n = 0
        for t in self.todos:
            if t.get("assignee") == from_staff and t.get("state") == "open":
                t["assignee"] = to_map.get(t.get("category"), to_map.get("*"))
                t["state"] = "open"
                n += 1
        self.nb.add("sop.todo.transfer", from_staff=from_staff, count=n)
        return n


class Notifier:
    """【对接点】消息中心：站内信 / 企业微信。"""
    def __init__(self, notebook):
        self.nb = notebook
        self.sent = []
    def notify(self, to_role, title, body="", channel="inapp"):
        msg = dict(to=to_role, title=title, body=body, channel=channel)
        self.sent.append(msg)
        self.nb.add("notify", to=to_role, title=title, channel=channel)
        return msg
