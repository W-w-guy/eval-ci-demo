# -*- coding: utf-8 -*-
"""eval-lint：用例与套件结构校验。

    python3 scripts/eval_lint.py

失败 -> 退出码 1（CI 会拦）。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITES = os.path.join(ROOT, "evals", "suites")
MIN_CASES = 3


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main():
    errs = []
    total = 0
    if not os.path.isdir(SUITES):
        errs.append("缺 evals/suites 目录")
    else:
        for suite in sorted(os.listdir(SUITES)):
            d = os.path.join(SUITES, suite)
            if not os.path.isdir(d):
                continue
            files = [f for f in os.listdir(d) if f.endswith(".jsonl")]
            if not files:
                errs.append("%s 下没有 .jsonl 用例文件" % suite)
                continue
            for f in files:
                p = os.path.join(d, f)
                try:
                    rows = load(p)
                except Exception as e:
                    errs.append("%s/%s 解析失败：%s" % (suite, f, e))
                    continue
                total += len(rows)
                if len(rows) < MIN_CASES:
                    errs.append("%s/%s 只有 %d 条（至少 %d）" % (suite, f, len(rows), MIN_CASES))
                ids = [r.get("case_id") for r in rows]
                if any(not i for i in ids):
                    errs.append("%s/%s 存在空 case_id" % (suite, f))
                if len(set(ids)) != len(ids):
                    errs.append("%s/%s case_id 重复" % (suite, f))
                for r in rows:
                    if "input" not in r or "expect" not in r:
                        errs.append("%s/%s 用例 %s 缺 input/expect" % (suite, f, r.get("case_id")))
    for e in errs[:30]:
        print("LINT", e)
    print("cases=%d errors=%d" % (total, len(errs)))
    print("LINT %s" % ("PASS" if not errs else "FAIL"))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
