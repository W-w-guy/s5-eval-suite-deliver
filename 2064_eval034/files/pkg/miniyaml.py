# -*- coding: utf-8 -*-
"""极简 YAML 子集解析器（无第三方依赖）。

只支持本套件 suite.yaml 用到的子集：
  - 缩进表示层级（空格，2 的倍数）
  - `key: value` 标量
  - `key:` 后接缩进块（映射或列表）
  - `- item` 列表项，可带 `key: value` 或裸标量
  - 值支持 int / float / true / false / null / 引号字符串 / 裸字符串
不支持的语法（锚点、多行块、流式 {}[]）一律抛 MiniYamlError，不静默猜测。
"""
import re


class MiniYamlError(ValueError):
    pass


def _scalar(s):
    s = s.strip()
    if not s:
        return ""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    low = s.lower()
    if low == "null":
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    if s[0] in "{[&*!|>":
        raise MiniYamlError("不支持的 YAML 语法: %r" % s)
    return s


def loads(text):
    raw = []
    for ln, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent % 2:
            raise MiniYamlError("第 %d 行缩进不是 2 的倍数" % ln)
        raw.append((indent, stripped.rstrip(), ln))
    if not raw:
        return None
    val, pos = _block(raw, 0, raw[0][0])
    if pos != len(raw):
        raise MiniYamlError("第 %d 行存在多余内容" % raw[pos][2])
    return val


def _block(raw, pos, indent):
    if raw[pos][1].startswith("- "):
        return _seq(raw, pos, indent)
    return _map(raw, pos, indent)


def _seq(raw, pos, indent):
    out = []
    while pos < len(raw) and raw[pos][0] == indent and raw[pos][1].startswith("- "):
        body = raw[pos][1][2:].strip()
        pos += 1
        if ":" in body and not body.startswith(("\"", "'")):
            k, _, v = body.partition(":")
            item = {k.strip(): _scalar(v)}
            while pos < len(raw) and raw[pos][0] > indent:
                sub_indent = raw[pos][0]
                sub, pos = _map(raw, pos, sub_indent)
                item.update(sub)
            out.append(item)
        else:
            out.append(_scalar(body))
    return out, pos


def _map(raw, pos, indent):
    out = {}
    while pos < len(raw) and raw[pos][0] == indent:
        line = raw[pos][1]
        if line.startswith("- "):
            break
        if ":" not in line:
            raise MiniYamlError("第 %d 行缺少冒号: %r" % (raw[pos][2], line))
        k, _, v = line.partition(":")
        k = k.strip()
        pos += 1
        if v.strip():
            out[k] = _scalar(v)
        elif pos < len(raw) and raw[pos][0] > indent:
            out[k], pos = _block(raw, pos, raw[pos][0])
        else:
            out[k] = None
    return out, pos


def safe_load(text):
    return loads(text)
