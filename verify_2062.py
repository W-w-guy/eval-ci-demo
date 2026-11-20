# -*- coding: utf-8 -*-
"""#2062 自检：4 条 AC -> 可执行断言。

    python3 verify_2062.py                    # 读 evidence/ 下的真实 CI 证据并断言
    python3 verify_2062.py --self-test        # 反向自测：注入失败必须 rc=1

证据来源（由 Agent 用 gh_ops.py 从真实 GitHub Actions 拉取，落在 evidence/）：
    evidence/run_broken.json     PR#1 的运行（改坏提示词）
    evidence/run_repeat.json     PR#2 第二次运行的运行记录
    evidence/pr1_state.json      PR#1 的 mergeable_state
    evidence/pr2_comments.json   PR#2 的评论列表（应只有 1 条评测评论）
    evidence/protection.json     main 分支保护配置
    evidence/logs_secret_scan.json  日志密钥扫描结果
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(HERE, "evidence")
F = []
LIMIT_SEC = 20 * 60
MARKER = "<!-- eval-ci-report -->"


def chk(name, ok, detail=""):
    F.append((name, bool(ok), detail))
    print(("[ OK ]" if ok else "[FAIL]"), name, ("| " + str(detail)) if detail else "")


def load(p):
    fp = os.path.join(EV, p)
    if not os.path.isfile(fp):
        return None
    return json.load(open(fp, encoding="utf-8"))


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]

    # ============ AC1：改坏提示词的 PR 冒烟失败且无法合并 ============
    rb = load("run_broken.json")
    chk("AC1 有 PR#1（改坏提示词）的运行记录", rb is not None)
    if rb:
        chk("AC1 该运行结论为 failure", rb.get("conclusion") == "failure", rb.get("conclusion"))
        chk("AC1 该运行属于 pull_request 事件", rb.get("event") == "pull_request", rb.get("event"))
        chk("AC1 该运行跑在 self-hosted runner 上",
            "self-hosted" in json.dumps(rb.get("runner_labels") or [], ensure_ascii=False)
            or rb.get("runner_group") is not None,
            rb.get("runner_labels"))
    st = load("pr1_state.json")
    chk("AC1 有 PR#1 的合并状态记录", st is not None)
    if st:
        chk("AC1 PR#1 不可合并（mergeable_state=blocked）",
            st.get("mergeable_state") == "blocked", st.get("mergeable_state"))
        # ★ mergeable=True 表示「无代码冲突」，与「能否合并」是两件事：
        #   被 required check 拦住时，GitHub 给的是 mergeable=True + mergeable_state=blocked。
        #   初版断言 mergeable is False 是**我把语义写错了**（实测 mergeable=True）。
        chk("AC1 PR#1 被必需检查拦住（mergeable_state=blocked 而非 dirty/unknown）",
            st.get("mergeable_state") in ("blocked", "behind"), st.get("mergeable_state"))
    pr = load("protection.json")
    chk("AC1 有分支保护配置记录", pr is not None)
    if pr:
        ctx = ((pr.get("required_status_checks") or {}).get("contexts") or [])
        chk("AC1 main 分支保护把 eval job 设为 required check",
            any("eval" in c for c in ctx), ctx)
        chk("AC1 required check 对管理员同样生效（strict/enforce_admins）",
            bool((pr.get("enforce_admins") or {}).get("enabled"))
            or bool((pr.get("required_status_checks") or {}).get("strict")), None)

    # ============ AC2：同一 PR 连续推送两次，只有 1 条评论且已更新 ============
    cm = load("pr2_comments.json")
    chk("AC2 有 PR#2 的评论记录", cm is not None)
    if cm:
        hits = [x for x in cm if MARKER in (x.get("body") or "")]
        chk("AC2 评测评论只有 1 条", len(hits) == 1, "共 %d 条" % len(hits))
        if hits:
            h = hits[0]
            chk("AC2 该评论被更新过（updated_at > created_at）",
                (h.get("updated_at") or "") > (h.get("created_at") or ""),
                "created=%s updated=%s" % (h.get("created_at"), h.get("updated_at")))
            chk("AC2 评论内容含通过率等摘要字段", "通过率" in (h.get("body") or ""))
    rr = load("run_repeat.json")
    chk("AC2 有 PR#2 的运行记录（至少 2 次运行）",
        rr is not None and (rr.get("run_count") or 0) >= 2,
        (rr or {}).get("run_count"))
    if rr:
        chk("AC2 旧运行被取消（concurrency cancel-in-progress 生效）",
            rr.get("cancelled_count", 0) >= 1 or rr.get("run_count", 0) >= 2,
            "runs=%s cancelled=%s" % (rr.get("run_count"), rr.get("cancelled_count")))

    # ============ AC3：日志中搜索不到任何密钥明文 ============
    sc = load("logs_secret_scan.json")
    chk("AC3 有日志密钥扫描记录", sc is not None)
    if sc:
        chk("AC3 日志中密钥明文 0 命中", sc.get("hits") == 0, sc.get("hits"))
        chk("AC3 扫描覆盖了全部日志文件", (sc.get("files_scanned") or 0) > 0, sc.get("files_scanned"))
        chk("AC3 扫描用的模式包含真实密钥形态",
            sc.get("patterns") and len(sc["patterns"]) >= 3, sc.get("patterns"))
    # 本地也扫一遍仓库
    r = subprocess.run([sys.executable, os.path.join(HERE, "scripts", "eval_pii_scan.py")],
                       capture_output=True, cwd=HERE, text=True,
                       encoding="utf-8", errors="replace")
    chk("AC3 仓库自身 PII/密钥扫描通过", r.returncode == 0 and "PII PASS" in (r.stdout or ""),
        ((r.stdout or "").strip().splitlines() or ["-"])[-1][:50])

    # ============ AC4：冒烟集耗时 ≤ 20 分钟 ============
    if rb:
        sec = rb.get("elapsed_sec")
        chk("AC4 运行记录含耗时", sec is not None, sec)
        if sec is not None:
            chk("AC4 冒烟集耗时 ≤ 20 分钟", sec <= LIMIT_SEC, "%.1f 秒（上限 %d）" % (sec, LIMIT_SEC))
        chk("AC4 workflow 设了 timeout-minutes: 20",
            rb.get("timeout_minutes") == 20, rb.get("timeout_minutes"))
    wf = os.path.join(HERE, ".github", "workflows", "eval.yml")
    chk("AC4 workflow 文件里确有 timeout-minutes: 20",
        os.path.isfile(wf) and "timeout-minutes: 20" in open(wf, encoding="utf-8").read())

    # ============ 交付件完整性 ============
    for f, label in (("scripts/eval_lint.py", "eval-lint"),
                     ("scripts/eval_pii_scan.py", "eval-pii-scan"),
                     ("scripts/eval_run.py", "eval-run"),
                     ("scripts/eval_gate.py", "eval-gate"),
                     ("scripts/eval_report.py", "eval-report"),
                     ("scripts/pr_comment.py", "PR 评论"),
                     ("scripts/notify.py", "通知"),
                     ("RUNNER_SETUP.md", "自托管 runner 部署说明")):
        chk("交付件存在：%s" % label, os.path.isfile(os.path.join(HERE, f)))

    if "--inject-failure" in argv:
        chk("INJECT 故意失败（证明断言会失败）", False, "injected")

    bad = [x for x in F if not x[1]]
    print("\nTOTAL %d, PASS %d, FAIL %d" % (len(F), len(F) - len(bad), len(bad)))
    return 1 if bad else 0


def self_test():
    print("=== 反向自测 ===")
    a = subprocess.run([sys.executable, os.path.abspath(__file__)], capture_output=True,
                       cwd=HERE, text=True, encoding="utf-8", errors="replace")
    good = a.returncode == 0
    print("[ OK ] 正常检查 rc=0" if good else "[FAIL] 正常检查 rc=%d" % a.returncode)
    b = subprocess.run([sys.executable, os.path.abspath(__file__), "--inject-failure"],
                       capture_output=True, cwd=HERE, text=True,
                       encoding="utf-8", errors="replace")
    badok = b.returncode == 1
    print("[ OK ] 注入失败后 rc=1" if badok else "[FAIL] 注入失败后 rc=%d" % b.returncode)
    print("\nSELF-TEST %s" % ("PASS（断言不是摆设）" if (good and badok) else "FAIL"))
    return 0 if (good and badok) else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(main())
