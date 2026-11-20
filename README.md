# 回归评测接入 CI（#2062）

## 一句话
`eval.yml` + 6 个脚本，把「PR 冒烟（每工具 10 条 + 全部 P0）/ 夜间全量 / 手动指定套件」
接成一条流水线，跑在**自托管 runner** 上（数据与被测服务不出客户网络），
失败即拦合并，同一 PR 只保留 1 条评测评论。

## 目录
```
.github/workflows/eval.yml   CI 主流程（20 分钟超时 / concurrency 取消旧运行）
scripts/eval_lint.py         结构校验
scripts/eval_pii_scan.py     PII + 疑似密钥扫描
scripts/eval_run.py          按套件跑评测，输出 reports/run.json
scripts/eval_gate.py         护栏（P0）+ 回归门槛，失败 rc=1
scripts/eval_report.py       生成 report.html 与 summary.md
scripts/pr_comment.py        PR 评论（同 marker 更新，不重复新增）
scripts/notify.py            夜间失败站内通知
prompts/summarize.v1.txt     正常提示词（STRATEGY: echo）
prompts/summarize.v2-broken.txt  故意改坏的提示词（用于演示冒烟失败）
evals/suites/regression/     60 条普通用例
evals/suites/guardrail/      6 条 P0 护栏用例
evals/baseline.json          回归基线（通过率 100%）
reports/                     运行产物（run.json / summary.md / report.html）
RUNNER_SETUP.md              自托管 runner 部署说明
```

## 关键设计（对应 4 条 AC）

| AC | 实现 |
|---|---|
| ①改坏提示词 → 冒烟失败且无法合并 | `prompts/` 在 `paths` 触发列表里；改坏后 P0 与普通用例全挂 → `eval_gate` rc=1 → required check 拦住 PR |
| ②同一 PR 推两次只有 1 条评论且已更新 | `pr_comment.py` 用 `<!-- eval-ci-report -->` 作锚点，先查后 PATCH，不新建 |
| ③日志搜不到密钥明文 | 密钥只从 `secrets` 注入，`::add-mask::` 保护；`eval_pii_scan.py` 额外扫疑似密钥形态 |
| ④冒烟集 ≤20 分钟 | `timeout-minutes: 20`；`run.json` 记录实测耗时 |

**冒烟抽样是确定性的**：固定种子 `20261121`，每工具抽 10 条 + 全部 P0。
同一 PR 的两次运行跑的是同一批用例，结果可比。

## 本地全链路验证（不依赖 CI，已实跑）

```bash
python3 scripts/eval_lint.py       # LINT PASS（66 条用例，2 个套件）
python3 scripts/eval_pii_scan.py   # PII PASS（hits=0，含疑似密钥扫描）
python3 scripts/eval_run.py --suite smoke --record reports/run.json
python3 scripts/eval_gate.py --run-report reports/run.json
python3 scripts/eval_report.py --run-report reports/run.json --out reports
```

实测结果：

| 场景 | 结果 |
|---|---|
| 正常提示词（v1） | 56 条用例 **56/56 通过，100.00%**，GATE PASS |
| 改坏提示词（v2-broken） | **0/56 通过，0.00%**，6 条 P0 全挂，GATE FAIL（rc=1） |

按工具分布（冒烟）：guard_access 13/13、guard_leak 13/13、intel_summarize 10/10、
lead_enrich 10/10、visit_minutes 10/10。

## 已知局限
- 被测工具的 `invoke()` 是**本地纯函数桩**（不写真实复核队列、不对外发送）。
  真实环境应换成 `POST /internal/eval/{tool}/invoke`（评测模式），接口形态已在代码注释标出。
- 冒烟抽样覆盖 5 个工具 × 10 条 + 6 条 P0，样本量只够做"改动是否破坏既有能力"的冒烟，
  不用于评估绝对质量。
- `eval_pii_scan.py` 的"疑似密钥"正则会误报测试夹具里的假 key，已用 `SAFE` 白名单过滤，
  新增夹具时若被误拦，往 `SAFE` 里加占位前缀即可。
