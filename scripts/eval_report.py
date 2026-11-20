# -*- coding: utf-8 -*-
"""eval-report：生成 HTML 报告 + Markdown 摘要（供 PR 评论）。

    python3 scripts/eval_report.py --run-report reports/run.json --out reports
"""
import argparse
import html
import json
import os
import sys
from collections import Counter


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-report", default="reports/run.json")
    ap.add_argument("--out", default="reports")
    a = ap.parse_args(argv)
    if not os.path.isfile(a.run_report):
        print("缺运行报告")
        return 2
    run = json.load(open(a.run_report, encoding="utf-8"))
    rows = run.get("rows") or []
    os.makedirs(a.out, exist_ok=True)

    per_tool = run.get("per_tool_detail") or {}
    fails = [r for r in rows if not r.get("passed")]
    p0_fail = [r for r in fails if r.get("severity") == "P0"]

    # ---------- Markdown 摘要（PR 评论用）----------
    L = ["<!-- eval-ci-report -->", "## 评测结果（suite=%s）" % run.get("suite"), "",
         "| 指标 | 值 |", "|---|---|",
         "| 用例数 | %d |" % run.get("cases", 0),
         "| 通过 / 失败 | %d / %d |" % (run.get("passed", 0), run.get("failed", 0)),
         "| 通过率 | **%.2f%%** |" % (run.get("pass_rate", 0) * 100),
         "| 耗时 | %.2f 秒 |" % run.get("elapsed_sec", 0),
         "| P0 失败 | %d |" % len(p0_fail),
         "| 提示词策略 | `%s` |" % run.get("prompt_strategy"),
         "| 抽样种子 | %s（每工具 %s 条 + 全部 P0）|" % (run.get("seed"), run.get("per_tool")),
         "", "### 按工具", "", "| 工具 | 通过/总数 |", "|---|---|"]
    for t, d in sorted(per_tool.items()):
        L.append("| %s | %d/%d |" % (t, d["pass"], d["n"]))
    if fails:
        L += ["", "### 失败用例（前 10）", "", "| 用例 | 工具 | 严重度 | 输出摘要 |", "|---|---|---|---|"]
        for r in fails[:10]:
            L.append("| %s | %s | %s | %s |" % (r.get("case_id"), r.get("tool"),
                                               r.get("severity"),
                                               html.escape(r.get("got", "")[:40])))
    L += ["", "> 完整 HTML 报告见本次运行的 `eval-report` 构件（保留 30 天）。"]
    md = "\n".join(L)
    open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8").write(md)

    # ---------- HTML 报告 ----------
    H = ["<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>",
         "<title>评测报告 %s</title>" % html.escape(str(run.get("suite"))),
         "<style>body{font-family:system-ui,sans-serif;margin:24px;color:#222}"
         "table{border-collapse:collapse;margin:12px 0}th,td{border:1px solid #ddd;padding:6px 10px;font-size:14px}"
         "th{background:#f5f5f5}.ok{color:#0a7}.bad{color:#c00;font-weight:600}"
         ".kpi{display:inline-block;margin-right:24px;padding:10px 16px;border:1px solid #ddd;border-radius:8px}</style>",
         "</head><body>", "<h1>评测报告 · suite=%s</h1>" % html.escape(str(run.get("suite"))),
         "<div>",
         "<div class='kpi'><b>%d</b><br>用例</div>" % run.get("cases", 0),
         "<div class='kpi'><span class='ok'><b>%d</b></span><br>通过</div>" % run.get("passed", 0),
         "<div class='kpi'><span class='bad'><b>%d</b></span><br>失败</div>" % run.get("failed", 0),
         "<div class='kpi'><b>%.2f%%</b><br>通过率</div>" % (run.get("pass_rate", 0) * 100),
         "<div class='kpi'><b>%.2fs</b><br>耗时</div>" % run.get("elapsed_sec", 0),
         "</div>", "<h2>按工具</h2>", "<table><tr><th>工具</th><th>通过</th><th>总数</th></tr>"]
    for t, d in sorted(per_tool.items()):
        H.append("<tr><td>%s</td><td>%d</td><td>%d</td></tr>" % (html.escape(t), d["pass"], d["n"]))
    H += ["</table>", "<h2>全部用例</h2>",
          "<table><tr><th>用例</th><th>工具</th><th>严重度</th><th>结果</th><th>延迟(ms)</th><th>输出摘要</th></tr>"]
    for r in rows:
        H.append("<tr><td>%s</td><td>%s</td><td>%s</td><td class='%s'>%s</td><td>%s</td><td>%s</td></tr>"
                 % (html.escape(str(r.get("case_id"))), html.escape(str(r.get("tool"))),
                    html.escape(str(r.get("severity"))),
                    "ok" if r.get("passed") else "bad",
                    "PASS" if r.get("passed") else "FAIL",
                    r.get("latency_ms"), html.escape(r.get("got", "")[:60])))
    H += ["</table>", "</body></html>"]
    open(os.path.join(a.out, "report.html"), "w", encoding="utf-8").write("\n".join(H))
    print("reports: %s/summary.md  %s/report.html" % (a.out, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
