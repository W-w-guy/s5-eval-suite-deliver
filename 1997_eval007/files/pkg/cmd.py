# -*- coding: utf-8 -*-
"""eval-pii-scan 命令入口。

用法：
    python -m pkg.cmd <path> [--allowlist <file>] [--json] [--report <file>]

退出码（AC2）：
    0  没有 error 级命中（可能只有 warn）
    1  存在 error 级命中（手机号 / 身份证 / 银行卡 / 疑似真实信用代码）→ 阻断 CI
    2  用法或配置错误（路径不存在、allowlist 格式不合规）
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import scanner   # noqa: E402

ROOT = os.path.dirname(_HERE)
RC_OK, RC_BLOCK, RC_ERR = 0, 1, 2


def build_parser():
    ap = argparse.ArgumentParser(prog="eval-pii-scan", description="评测数据虚构性扫描")
    ap.add_argument("path", help="要扫描的文件或目录")
    ap.add_argument("--allowlist", default=None, help="allowlist.yaml 路径")
    ap.add_argument("--report", default=None, help="把 Markdown 报告写到该文件")
    ap.add_argument("--json", action="store_true", help="额外打印机器可读摘要")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not os.path.exists(args.path):
        print("[eval-pii-scan] 路径不存在：%s" % args.path, file=sys.stderr)
        return RC_ERR

    findings, stats, errors = scanner.scan_path(args.path, args.allowlist)
    if errors:
        print("[eval-pii-scan] allowlist 不合法：", file=sys.stderr)
        for e in errors:
            print("  - %s" % e, file=sys.stderr)
        return RC_ERR

    md = scanner.report(findings, stats)
    print(md)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
    if args.json:
        print(json.dumps({"scanned": stats["scanned"], "files": stats["files"],
                          "blocking": stats["blocking"],
                          "warnings": stats["warnings"],
                          "allowlist_entries": stats["allowlist_entries"],
                          "by_kind": stats["by_kind"]},
                         ensure_ascii=False, indent=1))
    print("[eval-pii-scan] 扫描 %d 个单元：error %d ｜ warn %d -> %s"
          % (stats["scanned"], stats["blocking"], stats["warnings"],
             "BLOCK" if stats["blocking"] else "OK"), file=sys.stderr)
    return RC_BLOCK if stats["blocking"] else RC_OK


if __name__ == "__main__":
    sys.exit(main())
