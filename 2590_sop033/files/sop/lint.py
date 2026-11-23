"""sop-lint · SOP 模板配置静态校验器（纯标准库，无三方依赖）
用法: python -m sop.lint sop/templates/renewal.json [...]
退出码: 0=全部通过 1=存在 ERROR"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = json.load(open(os.path.join(HERE, "schema.json"), encoding="utf-8"))

class Finding:
    def __init__(self, level, code, path, msg):
        self.level, self.code, self.path, self.msg = level, code, path, msg
    def __repr__(self):
        return f"[{self.level}] {self.code} @{self.path}: {self.msg}"
    def __str__(self):
        return self.__repr__()


def lint(tpl):
    f = []
    _top(tpl, f)
    if any(x.code == "E001" for x in f):
        return f
    _trigger(tpl, f)
    _steps(tpl, f)
    _content(tpl, f)
    return sorted(f, key=lambda x: x.code)


def _top(tpl, f):
    for k in SCHEMA["top_required"]:
        if k not in tpl:
            f.append(Finding("ERROR", "E001", k, f"缺少必填字段 {k}"))
    for k in ("template_id", "name", "version", "target_object", "owner_role"):
        v = tpl.get(k)
        if k in tpl and (not isinstance(v, str) or not v.strip()):
            f.append(Finding("ERROR", "E002", k, f"{k} 必须是非空字符串"))
    m = tpl.get("metric")
    if isinstance(m, dict):
        if not str(m.get("name", "")).strip():
            f.append(Finding("ERROR", "E002", "metric.name", "metric 对象必须含非空 name"))
    elif not (isinstance(m, str) and m.strip()):
        f.append(Finding("ERROR", "E002", "metric", "metric 必须是非空字符串或含 name 的对象"))
    if tpl.get("example_data_virtual") is not True:
        f.append(Finding("ERROR", "E003", "example_data_virtual",
                         "必须显式声明 example_data_virtual=true（只允许虚构示例数据）"))


def _trigger(tpl, f):
    trg = tpl.get("trigger") or {}
    tt = trg.get("type")
    if tt not in SCHEMA["trigger"]["types"]:
        f.append(Finding("ERROR", "E010", "trigger.type", f"未知触发类型 {tt!r}"))
        return
    # cancel_on 与触发类型无关：定时触发的模板同样可被事件取消
    co = trg.get("cancel_on")
    if co is not None and not re.match(SCHEMA["cancel_on_pattern"], co):
        f.append(Finding("ERROR", "E012", "trigger.cancel_on",
                         f"cancel_on 不合规 {co!r}，应为 entity.action"))
    if tt == "event":
        ev = trg.get("event", "")
        if not re.match(SCHEMA["trigger"]["event_pattern"], ev):
            f.append(Finding("ERROR", "E011", "trigger.event",
                             f"事件名不合规 {ev!r}，应为 entity.action"))
    elif tt == "schedule":
        for k in SCHEMA["trigger"]["schedule_required"]:
            if k not in trg:
                f.append(Finding("ERROR", "E013", "trigger." + k, f"定时触发缺少 {k}"))
        dd = trg.get("dedupe_days")
        if dd is not None and (not isinstance(dd, int) or dd <= 0):
            f.append(Finding("ERROR", "E014", "trigger.dedupe_days", "去重窗口必须是正整数天"))
        cr = str(trg.get("cron", ""))
        parts = cr.split()
        ok = len(parts) == 5 and all(
            (p == "*") or (p.lstrip("-").isdigit()) for p in parts)
        if not ok:
            f.append(Finding("ERROR", "E015", "trigger.cron",
                             f"cron 必须是 5 段（分 时 日 月 周），实际 {cr!r}"))


def _steps(tpl, f):
    steps = tpl.get("steps") or []
    if not isinstance(steps, list) or not steps:
        f.append(Finding("ERROR", "E020", "steps", "至少要有 1 个步骤"))
        return
    seen = set()
    for i, st in enumerate(steps):
        p = f"steps[{i}]"
        for k in SCHEMA["step_required"]:
            if k not in st:
                f.append(Finding("ERROR", "E021", p + "." + k, f"步骤缺少必填字段 {k}"))
        sid = st.get("id")
        if sid in seen:
            f.append(Finding("ERROR", "E022", p + ".id", f"步骤 id 重复 {sid!r}"))
        seen.add(sid)
        if sid is not None and sid != i + 1:
            f.append(Finding("ERROR", "E023", p + ".id",
                             f"步骤 id 必须按 1..N 顺序，实际第 {i+1} 个是 {sid!r}"))
        if st.get("escalate") not in SCHEMA["escalate_allowed"]:
            f.append(Finding("ERROR", "E024", p + ".escalate",
                             f"升级方式只能是 {SCHEMA['escalate_allowed']}，实际 {st.get('escalate')!r}"))

        due = st.get("due") or {}
        if due.get("unit") not in SCHEMA["units"]:
            f.append(Finding("ERROR", "E025", p + ".due.unit",
                             f"未知时限单位 {due.get('unit')!r}，允许 {SCHEMA['units']}"))
        if not isinstance(due.get("offset"), (int, float)) or isinstance(due.get("offset"), bool):
            f.append(Finding("ERROR", "E026", p + ".due.offset", "offset 必须为数字"))
        if due.get("anchor") not in SCHEMA["anchors"]:
            f.append(Finding("ERROR", "E027", p + ".due.anchor",
                             f"未知锚点 {due.get('anchor')!r}，允许 {SCHEMA['anchors']}"))
        cond = st.get("condition")
        if st.get("conditional") and not cond:
            f.append(Finding("ERROR", "E028", p + ".condition", "条件步骤必须给出 condition 表达式"))
        if cond and not st.get("conditional"):
            f.append(Finding("ERROR", "E029", p + ".conditional", "给出 condition 的步骤必须标记 conditional=true"))
        if st.get("skip_reason_required") and not st.get("allow_skip"):
            f.append(Finding("ERROR", "E031", p + ".skip_reason_required",
                             "skip_reason_required 必须同时声明 allow_skip=true"))
        if st.get("allow_skip") and st.get("conditional"):
            f.append(Finding("ERROR", "E032", p + ".allow_skip",
                             "allow_skip（人工跳过）与 conditional（条件自动跳过）互斥"))


def _content(tpl, f):
    """内容级检查：占位变量、PII、指引正文、话术、度量。"""
    texts = list(_strings(tpl))
    for pat in SCHEMA["forbidden_pii"]:
        for txt in texts:
            for m in re.findall(pat, txt):
                if not _is_virtual(m):
                    f.append(Finding("ERROR", "E030", "content",
                                     f"检出疑似真实个人信息 {m!r}（只允许虚构示例数据）"))
    for txt in texts:
        for var in re.findall(r"\{([^{}]+)\}", txt):
            if var not in SCHEMA["allowed_vars"]:
                f.append(Finding("WARN", "W030", "content",
                                 f"未知占位变量 {{{var}}}，允许 {SCHEMA['allowed_vars']}"))
    if not tpl.get("metric"):
        f.append(Finding("WARN", "W031", "metric", "建议给出度量口径"))
    for i, st in enumerate(tpl.get("steps") or []):
        if not st.get("guidance") and not st.get("description"):
            f.append(Finding("WARN", "W032", f"steps[{i}]", "步骤缺少指引正文 guidance"))
        if st.get("outputs") is None and st.get("checklist") is None:
            f.append(Finding("WARN", "W033", f"steps[{i}]", "步骤既无 outputs 也无 checklist"))


def _strings(o):
    """只遍历 JSON 里的字符串值——不能对序列化后的整段 JSON 做正则，
    否则每个 {..} 对象都会被当成占位变量（这是 sop-lint 的第一版 bug）。"""
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


def _is_virtual(s):
    """判定命中项是否属于虚构样例（允许放行）：
    - 手机号：尾 4 位为 0000/8888
    - 邮箱：域名为 RFC 2606 保留域（example.* / test.*）
    """
    if re.fullmatch(r"1[3-9]\d{9}", s):
        return s[-4:] in ("0000", "8888")
    if "@" in s:
        dom = s.rsplit("@", 1)[-1].lower()
        return dom in SCHEMA.get("virtual_domains", [])
    return False


def main(argv):
    if not argv:
        print("用法: python -m sop.lint <template.json> [...]")
        return 2
    bad = 0
    for path in argv:
        tpl = json.load(open(path, encoding="utf-8"))
        fs = lint(tpl)
        errs = [x for x in fs if x.level == "ERROR"]
        name = os.path.basename(path)
        if errs:
            bad += 1
            print(f"FAIL {name}  {len(errs)} error / {len(fs)-len(errs)} warn")
            for x in fs:
                print("   ", x)
        else:
            print(f"PASS {name}  0 error / {len(fs)} warn")
            for x in fs:
                print("   ", x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
