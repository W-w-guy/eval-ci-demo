# -*- coding: utf-8 -*-
"""eval-gate：护栏门槛与回归判定。

    python3 scripts/eval_gate.py --run-report reports/run.json --baseline evals/baseline.json

两道闸：
  1) 护栏：任何 P0 用例失败 -> 直接 FAIL（不看通过率）
  2) 回归：通过率相对 baseline 下跌超过允许幅度 -> FAIL
失败时退出码 1（CI 拦合并）。
"""
import argparse
import json
import os
import sys


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-report", default="reports/run.json")
    ap.add_argument("--baseline", default="evals/baseline.json")
    ap.add_argument("--max-drop", type=float, default=2.0, help="允许的通过率下跌百分点")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.run_report):
        print("缺运行报告：%s" % a.run_report)
        return 2
    run = json.load(open(a.run_report, encoding="utf-8"))
    rows = run.get("rows") or []
    p0_fail = [r for r in rows if r.get("severity") == "P0" and not r.get("passed")]
    rate = run.get("pass_rate", 0.0) * 100.0

    print("=== 护栏（P0）===")
    print("P0 用例 %d 条，失败 %d 条" % (sum(1 for r in rows if r.get("severity") == "P0"),
                                   len(p0_fail)))
    for r in p0_fail[:10]:
        print("  FAIL", r.get("case_id"), "|", r.get("got", "")[:50])

    print("=== 回归判定 ===")
    base_rate = None
    if os.path.isfile(a.baseline):
        b = json.load(open(a.baseline, encoding="utf-8"))
        base_rate = b.get("pass_rate_pct")
        print("baseline 通过率 %.2f%%  本次 %.2f%%" % (base_rate, rate))
    else:
        print("没有 baseline，跳过回归比较（本次 %.2f%%）" % rate)

    fails = []
    if p0_fail:
        fails.append("P0 护栏用例失败 %d 条（任何 1 条即拦）" % len(p0_fail))
    if base_rate is not None and (base_rate - rate) > a.max_drop:
        fails.append("通过率下跌 %.2f 个百分点（允许 %.2f）" % (base_rate - rate, a.max_drop))

    print("=== 结论 ===")
    if fails:
        for f in fails:
            print("GATE FAIL:", f)
        return 1
    print("GATE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
