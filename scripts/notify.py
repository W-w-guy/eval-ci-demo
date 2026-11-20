# -*- coding: utf-8 -*-
"""notify：夜间全量失败时调用站内通知接口桩。

    python3 scripts/notify.py --url https://stub/notify --text "夜间全量回归失败"

★ 密钥（URL）从环境变量注入，本脚本不打印它。
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="")
    ap.add_argument("--text", required=True)
    a = ap.parse_args(argv)
    if not a.url:
        print("没有通知地址（NOTIFY_WEBHOOK 未配置），跳过")
        return 0
    req = urllib.request.Request(a.url, method="POST",
                                 data=json.dumps({"text": a.text}).encode())
    req.add_header("Content-Type", "application/json")
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(req, timeout=15) as r:
            print("notify ok: %s" % r.status)
            return 0
    except urllib.error.HTTPError as e:
        print("notify http %s" % e.code)
        return 1
    except Exception as e:
        print("notify error: %s" % type(e).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
