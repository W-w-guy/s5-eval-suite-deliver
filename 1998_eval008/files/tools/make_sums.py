# -*- coding: utf-8 -*-
"""生成 SHA256SUMS。

三条纪律：
  1. 不列自身（列了会让 sha256sum -c 恒有 1 条 FAIL）
  2. 不列 node_modules / .pgdata / __pycache__ 这类可再生或本地状态
  3. 生成后必须在「解压到全新目录」里再验一遍，否则买家一跑就 mismatch
"""
from __future__ import annotations
import hashlib, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pgdata", ".venv"}
SKIP_FILES = {"SHA256SUMS"}
SUMS_SKIP_EXT = {".xlsx"}          # xlsx 是 zip 容器，字节不稳定，不能进校验和
# 截图是「运行产物」而不是「交付内容」：AC3 的测试每次跑都会重新截一遍，
# 不同平台/不同字体渲染出的 PNG 字节必然不同。若把它列进校验和，
# 买家跑完 pytest 再 sha256sum -c 就会看到 4 条 FAILED，误以为文件被改过。
SKIP_REL_PREFIX = ("docs/shots/",)


def walk():
    for root, dirs, files in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP_FILES:
                continue
            if os.path.splitext(f)[1].lower() in SUMS_SKIP_EXT:
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, HERE).replace(os.sep, "/")
            if rel.startswith(SKIP_REL_PREFIX):
                continue
            yield rel, p


def main():
    lines = []
    for rel, full in walk():
        h = hashlib.sha256()
        with open(full, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        lines.append("%s  %s" % (h.hexdigest(), rel))
    out = os.path.join(HERE, "SHA256SUMS")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("SHA256SUMS: %d 个文件" % len(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
