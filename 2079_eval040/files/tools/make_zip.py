# -*- coding: utf-8 -*-
"""打包 + SHA256SUMS。四条跨平台坑在此一次性掐死：
  1) 文本一律 newline="\n" 写，避免 Windows CRLF 造成两侧字节不同；
  2) SHA256SUMS 不列自身（列了 sha256sum -c 恒有 1 条 FAIL）；
  3) 生成物与运行日志不进校验和（买家跑一遍就 mismatch）；
  4) zip 条目固定 date_time / create_system / STORED，使两侧字节可比。
"""
import hashlib
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", "report", "node_modules"}
SKIP_FILES = {"SHA256SUMS.txt"}
# 运行期日志：随运行变化，不进校验和
# 运行产物不进校验和：dist 每次构建都变、docs/shots 与 network.json 每次运行都变。
# 它们仍然打进 zip（买家可直接预览），只是不参与 sha256sum -c。
SKIP_SUMS_PREFIX = ("verify_logs/", "frontend/dist/", "docs/shots/", "docs/network.json")
FIXED_DT = (2026, 1, 1, 0, 0, 0)


def sha(fp):
    h = hashlib.sha256()
    h.update(open(fp, "rb").read())
    return h.hexdigest()


def walk(root):
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            if fn in SKIP_FILES or fn.endswith(".pyc"):
                continue
            fp = os.path.join(dp, fn)
            yield fp, os.path.relpath(fp, root).replace(os.sep, "/")


def write_sums(root, items):
    rows = [(sha(fp), rel) for fp, rel in items
            if not rel.startswith(SKIP_SUMS_PREFIX)]
    path = os.path.join(root, "SHA256SUMS.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for h, rel in rows:
            f.write("%s  %s\n" % (h, rel))
        f.write("# 本文件不列出自身；verify_logs/ 为实跑日志快照，不参与校验。\n")
    return path, len(rows)


def build(root, zip_path):
    items = list(walk(root))
    non_ascii = [rel for _, rel in items if not rel.isascii()]
    if non_ascii:
        print("NON-ASCII FILENAME", non_ascii)
        return 2
    sums, n = write_sums(root, items)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as z:
        for fp, rel in items + [(sums, "SHA256SUMS.txt")]:
            zi = zipfile.ZipInfo(rel, date_time=FIXED_DT)
            zi.create_system = 0
            zi.compress_type = zipfile.ZIP_STORED
            zi.external_attr = 0o600 << 16
            z.writestr(zi, open(fp, "rb").read())
    print("FILES %d  SHA256SUMS %d  ZIP %d bytes  sha256 %s"
          % (len(items) + 1, n, os.path.getsize(zip_path), sha(zip_path)))
    return 0


def verify_sums(root):
    path = os.path.join(root, "SHA256SUMS.txt")
    n, bad = 0, []
    for ln in open(path, encoding="utf-8"):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        n += 1
        h, _, rel = ln.partition("  ")
        fp = os.path.join(root, rel)
        if not os.path.exists(fp) or sha(fp) != h:
            bad.append(rel)
    return n, bad


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(ROOT), os.path.basename(ROOT) + ".zip")
    sys.exit(build(ROOT, out))
