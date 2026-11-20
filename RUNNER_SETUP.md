# 自托管 Runner 部署说明

## 为什么必须用自托管
单子要求「评测数据与被测服务不出客户网络」。GitHub 托管 runner 会让数据出网，
因此用客户云内的机器注册为 self-hosted runner。

## 机器要求
- Linux x64（Ubuntu 22.04 / 24.04 实测）
- 2 核 / 4G 起（再跑被测服务容器建议 4 核 / 8G）
- 能访问：`github.com`、`api.github.com`、`pip` 源（装依赖）
- **不需要**公网入向端口：runner 是主动出向长轮询

## 注册步骤（三行）

```bash
# 1) 取一次性注册令牌（1 小时有效，仓库管理员在 GitHub 上取）
#    Settings -> Actions -> Runners -> New self-hosted runner
#    或用 API：POST /repos/{owner}/{repo}/actions/runners/registration-token

# 2) 配置（--labels 决定 workflow 里 runs-on 怎么选到它）
./config.sh --url https://github.com/{owner}/{repo} \
            --token {REGISTRATION_TOKEN} \
            --labels self-hosted,linux,eval-runner \
            --unattended --replace

# 3) 装成系统服务（开机自启、崩溃自拉）
sudo ./svc.sh install
sudo ./svc.sh start
```

## workflow 如何选中它
`eval.yml` 里写的是：
```yaml
runs-on: [self-hosted, linux, eval-runner]
```
三个标签必须都在 runner 上（`self-hosted` 与 `linux` 是自动标签，`eval-runner` 是自定义）。

## 数据不出网的证据
1. runner 部署在客户内网机器上，代码 checkout 后本地运行；
2. 被测服务由同一台机器上的 `docker compose` 启动（`--profile eval`），只监听 127.0.0.1；
3. 模型地址来自 `secrets.EVAL_MODEL_URL`，指向内网网关；
4. 出网流量只有 GitHub 的作业调度长轮询（不含业务数据）。

## 密钥处理
| 名称 | 来源 | 用途 |
|---|---|---|
| `EVAL_MODEL_KEY` | CI secrets | 评测模式调用被测服务 |
| `EVAL_MODEL_URL` | CI secrets | 内网模型网关地址 |
| `NOTIFY_WEBHOOK` | CI secrets | 夜间失败通知 |
| `GITHUB_TOKEN` | Actions 自动注入 | PR 评论 |

workflow 里对每个密钥都做 `::add-mask::`，且脚本不打印任何密钥值。
`eval_pii_scan.py` 在打包前额外扫一遍「疑似密钥明文」（`sk-` / `gh*_` / `hvs.` / `AKIA` 形态）。

## 分支保护（阻止合并）
`main` 分支需开：
- Require status checks to pass before merging
- 勾选 `eval / eval`（workflow 名 / job 名）
- Require branches to be up to date before merging

## 排查
| 现象 | 原因 |
|---|---|
| job 一直 queued | runner 标签不匹配，或 runner 离线 |
| 推 workflow 文件 403 | PAT 缺 `Workflows: Read and write` |
| 分支保护 API 403 | PAT 缺 `Administration: Read and write` |
| 评论发不出 | PAT 缺 `Issues: Read and write` |
