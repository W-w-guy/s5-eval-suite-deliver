# -*- coding: utf-8 -*-
"""扫描目录或单个文件，汇总结果并决定退出码。

退出码：0 无 error 级命中（可能只有 warn）/ 1 有 error 级命中 / 2 用法或配置错误
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import allowlist as A   # noqa: E402
import detect           # noqa: E402
import rules as R       # noqa: E402

RC_OK, RC_BLOCK, RC_ERR = 0, 1, 2
TEXT_EXT = {".txt", ".md", ".json", ".jsonl", ".csv", ".yaml", ".yml", ".py"}
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache"}


def iter_files(path):
    if os.path.isfile(path):
        yield path
        return
    for dp, dns, fns in os.walk(path):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                yield os.path.join(dp, fn)


def _units(fp, txt):
    """把一个文件拆成「扫描单元」（文件, 文本）。

    .jsonl 按行拆成用例：工单说的是「扫描 1000 条用例」，
    用例本来就以 JSONL 一行一条存放，因此计数单位是行而不是文件。
    """
    if not fp.lower().endswith(".jsonl"):
        yield fp, txt
        return
    for ln, line in enumerate(txt.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            yield "%s#L%d" % (fp, ln), line
            continue
        if isinstance(obj, dict):
            parts = [str(obj[k]) for k in ("text", "input", "output", "content")
                     if isinstance(obj.get(k), str)]
            yield "%s#L%d" % (fp, ln), " ".join(parts) or line
        else:
            yield "%s#L%d" % (fp, ln), line


def scan_path(path, allow_path=None):
    """返回 (findings, stats, errors)。stats["scanned"] 是扫描单元数（JSONL 按行计）。"""
    errors = []
    entries = []
    if allow_path:
        try:
            entries, errs = A.load(allow_path)
            errors.extend(errs)
        except A.AllowlistError as e:
            errors.append(str(e))

    findings, scanned, files = [], 0, 0
    for fp in iter_files(path):
        try:
            txt = open(fp, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        files += 1
        for unit_name, unit_text in _units(fp, txt):
            scanned += 1
            for f in detect.scan_text(unit_text):
                g = dict(f)
                g["file"] = unit_name.replace(os.sep, "/")
                findings.append(g)
    findings = A.apply(findings, entries)
    block = A.blocking(findings)
    warn = A.warning(findings)
    stats = {"scanned": scanned, "files": files, "findings": len(findings),
             "blocking": len(block), "warnings": len(warn),
             "allowlist_entries": len(entries),
             "by_kind": {k: sum(1 for f in block if f["kind"] == k) for k in R.CHECK_KINDS}}
    return findings, stats, errors


def report(findings, stats):
    L = ["# eval-pii-scan 报告", "",
         "| 项 | 值 |", "| --- | --- |",
         "| 扫描文件数 | %d |" % stats["scanned"],
         "| 命中总数 | %d |" % stats["findings"],
         "| **error 级（阻断）** | **%d** |" % stats["blocking"],
         "| warn 级 | %d |" % stats["warnings"],
         "| allowlist 条目 | %d |" % stats["allowlist_entries"], ""]
    if stats["blocking"]:
        L += ["## 阻断项（error）", "", "| 类别 | 文件 | 片段 | 依据 |",
              "| --- | --- | --- | --- |"]
        for f in findings:
            if f["level"] == "error" and not f["allowed"]:
                L.append("| %s | %s | `%s` | %s |"
                         % (f["kind"], f["file"], f["text"], f["evidence"]))
        L.append("")
    if stats["warnings"]:
        L += ["## 告警项（warn）", "", "| 类别 | 文件 | 片段 | 依据 |",
              "| --- | --- | --- | --- |"]
        seen = set()
        for f in findings:
            if f["level"] == "warn" and not f["allowed"]:
                key = (f["kind"], f["text"])
                if key in seen:
                    continue
                seen.add(key)
                L.append("| %s | %s | `%s` | %s |"
                         % (f["kind"], f["file"], f["text"], f["evidence"]))
        L.append("")
    allowed = [f for f in findings if f["allowed"]]
    if allowed:
        L += ["## 已由 allowlist 放行", ""]
        L += ["- `%s`（%s）" % (f["text"], f["kind"]) for f in allowed[:15]]
        L.append("")
    return "\n".join(L)
