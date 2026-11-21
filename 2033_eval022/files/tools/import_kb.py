# -*- coding: utf-8 -*-
"""把 120 篇虚构知识文档一键导入「知识库测试实例」（SQLite）。

为什么用 SQLite 而不是假装有个知识库：
AC 要求「导入脚本在**空**知识库实例上执行成功」。要让这句话可验证，
就必须有一个真实可查的实例：空 -> 导入 -> 计数 -> 可检索。
SQLite 是标准库自带，不引入任何依赖，且删除文件即可回到「空实例」。
"""
import argparse
import glob
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(HERE, "kb_docs")
DB = os.path.join(HERE, "data", "kb.sqlite3")

FM = re.compile(r"^---\n(.*?)\n---\n", re.S)


def parse(path):
    raw = open(path, encoding="utf-8").read()
    m = FM.match(raw)
    if not m:
        raise ValueError("%s 缺 YAML front matter" % os.path.basename(path))
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    body = raw[m.end():]
    # 剥掉一级标题，正文只留小节
    body = re.sub(r"^#\s+.*?\n", "", body, count=1)
    sections = []
    cur = None
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("## "):
            cur = {"heading": s[3:].strip(), "text": []}
            sections.append(cur)
        elif cur is not None:
            cur["text"].append(s)
    for sec in sections:
        sec["text"] = "\n".join(sec["text"])
    return {"doc_id": meta["doc_id"], "title": meta["title"],
            "updated": meta["updated"], "visibility": meta.get("visibility", "all"),
            "body": body.strip(), "sections": sections}


def connect(db=None):
    return sqlite3.connect(db or DB)


def schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS docs (
      doc_id TEXT PRIMARY KEY, title TEXT NOT NULL, updated TEXT NOT NULL,
      visibility TEXT NOT NULL, body TEXT NOT NULL, source_path TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sections (
      doc_id TEXT NOT NULL, seq INTEGER NOT NULL, heading TEXT NOT NULL, text TEXT NOT NULL,
      PRIMARY KEY (doc_id, seq));
    """)
    conn.commit()


def count(conn):
    return conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]


def import_all(conn, pattern=None, verbose=True):
    files = sorted(glob.glob(os.path.join(DOCS, pattern or "*.md")))
    for p in files:
        d = parse(p)
        conn.execute("INSERT OR REPLACE INTO docs(doc_id,title,updated,visibility,body,source_path)"
                     " VALUES(?,?,?,?,?,?)",
                     (d["doc_id"], d["title"], d["updated"], d["visibility"], d["body"],
                      os.path.relpath(p, HERE)))
        conn.execute("DELETE FROM sections WHERE doc_id=?", (d["doc_id"],))
        for i, s in enumerate(d["sections"], 1):
            conn.execute("INSERT INTO sections(doc_id,seq,heading,text) VALUES(?,?,?,?)",
                         (d["doc_id"], i, s["heading"], s["text"]))
    conn.commit()
    if verbose:
        print("imported %d files; docs=%d sections=%d" % (
            len(files), count(conn), conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]))
    return len(files)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="import_kb")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--expect-empty", action="store_true",
                    help="断言目标实例是空的（AC1 要求「空知识库实例」）")
    ap.add_argument("--reset", action="store_true", help="删掉已有库文件，回到空实例")
    a = ap.parse_args(argv)
    if a.reset and os.path.isfile(a.db):
        os.remove(a.db)
        print("reset: removed %s" % a.db)
    conn = connect(a.db)
    schema(conn)
    before = count(conn)
    print("before: docs=%d" % before)
    if a.expect_empty and before != 0:
        print("FAIL: 目标实例非空（docs=%d），AC1 要求空实例" % before, file=sys.stderr)
        return 2
    import_all(conn)
    after = count(conn)
    vis = dict(conn.execute("SELECT visibility, COUNT(*) FROM docs GROUP BY visibility").fetchall())
    print("after : docs=%d visibility=%s" % (after, vis))
    ok = after == 120
    print("import %s" % ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
