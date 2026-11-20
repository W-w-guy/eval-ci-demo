# -*- coding: utf-8 -*-
"""pr_comment：在 PR 里发 Markdown 摘要评论；同一 PR 只保留 1 条并更新。

    python3 scripts/pr_comment.py --repo owner/name --pr 12 --body-file reports/summary.md --marker "<!-- eval-ci-report -->"

AC 要求：「同一 PR 连续推送两次，PR 中只有 1 条评测评论且内容已更新」。
实现：用 marker 注释做锚点 —— 先查已有评论里含该 marker 的那条，
      有则 PATCH 更新，无则 POST 新建。
不依赖任何第三方 action（避免引外部依赖）。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


def token():
    for k in ("GH_TOKEN", "GITHUB_TOKEN"):
        v = os.environ.get(k)
        if v:
            return v.strip()
    return ""


def call(method, path, body=None):
    tok = token()
    if not tok:
        raise SystemExit("没有 GH_TOKEN/GITHUB_TOKEN")
    req = urllib.request.Request(API + path, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "eval-ci")
    data = json.dumps(body).encode() if body is not None else None
    if data:
        req.add_header("Content-Type", "application/json")
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(req, data, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pr", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--marker", default="<!-- eval-ci-report -->")
    a = ap.parse_args(argv)

    body = open(a.body_file, encoding="utf-8").read()
    if a.marker not in body:
        body = a.marker + "\n" + body

    # 找同一条（含 marker 的）
    existing = None
    page = 1
    while True:
        c, d = call("GET", "/repos/%s/issues/%s/comments?per_page=100&page=%d" % (a.repo, a.pr, page))
        if c != 200 or not isinstance(d, list):
            print("读评论失败：%s %s" % (c, str(d)[:120]))
            return 1
        for cm in d:
            if a.marker in (cm.get("body") or ""):
                existing = cm
                break
        if existing or len(d) < 100:
            break
        page += 1

    if existing:
        c, d = call("PATCH", "/repos/%s/issues/comments/%s" % (a.repo, existing["id"]), {"body": body})
        action = "updated"
    else:
        c, d = call("POST", "/repos/%s/issues/%s/comments" % (a.repo, a.pr), {"body": body})
        action = "created"

    if c in (200, 201):
        print("comment %s: id=%s url=%s" % (action, d.get("id"), d.get("html_url")))
        return 0
    print("评论失败：%s %s" % (c, str(d)[:200]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
