# -*- coding: utf-8 -*-
"""eval-pii-scan：全仓扫描真实格式的手机号 / 邮箱 / 身份证 / 疑似密钥。

    python3 scripts/eval_pii_scan.py

★ 除了常规 PII，这里还扫「疑似密钥明文」——因为 AC3 要求
   「运行日志中搜索不到任何密钥明文」，那要能在打包前先自查一遍。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = {
    "手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "邮箱": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "身份证": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    # 常见密钥形态：sk- / gh*_ / hvs. / AKIA
    "疑似密钥": re.compile(r"(sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|hvs\.[A-Za-z0-9\-]{20,}|AKIA[0-9A-Z]{16})"),
}
SKIP_EXT = {".pyc", ".png", ".jpg", ".gif", ".zip", ".gz", ".tgz", ".whl"}
SKIP_DIR = {".git", "__pycache__", "node_modules", "reports"}
# 允许出现的占位/示例（不是真值）
SAFE = ("1990000", "example.invalid", "XXXX", "placeholder", "${{", "%s", "<", ">")


def main():
    hits = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIR]
        for fn in fns:
            if os.path.splitext(fn)[1].lower() in SKIP_EXT:
                continue
            p = os.path.join(dp, fn)
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for kind, rx in PAT.items():
                for m in rx.finditer(t):
                    v = m.group(0)
                    if any(s in v for s in SAFE):
                        continue
                    # 环境变量引用不是明文
                    if v.startswith("$") or v.startswith("%"):
                        continue
                    hits.append({"file": os.path.relpath(p, ROOT), "kind": kind, "value": v[:40]})
    for h in hits[:20]:
        print("PII", h)
    print("hits=%d" % len(hits))
    print("PII %s" % ("PASS" if not hits else "FAIL"))
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
