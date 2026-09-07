# Notion 任务评测

一级任务列表：`configs/task_lists/finalpool/c-notion.txt`，独立组成 C-notion，包含全部 8 个 Notion 任务。这些任务已从 C-local、C-remote 清单移除，五组之间不重复。

**Notion 任务必须串行运行，不能开任务并发。** 每次只执行一个任务，等它的 preprocess、agent 和 evaluation 全部结束后，再开始下一个。运行参数必须显式设置 `workers=1`；也不能同时启动多个 C-notion 作业，包括不同模型或不同 checkout 的作业。

| 任务 | 需要 Poste | 除 Notion 外的主要依赖 |
| --- | --- | --- |
| `experiments-recordings` | 否 | W&B |
| `notion-find-job` | 是 | Poste 邮件、Google Maps、浏览器 |
| `notion-hr` | 是 | Poste 邮件、文件系统、PDF 工具 |
| `notion-movies` | 否 | 浏览器、网页抓取 |
| `notion-personal-website` | 否 | 文件系统、Word 工具 |
| `oil-price` | 否 | Yahoo Finance |
| `quantitative-financial-analysis` | 否 | Yahoo Finance、Google Sheets/Drive（Google OAuth） |
| `task-tracker` | 否 | GitHub |

其中只有 `notion-find-job`、`notion-hr` 需要本地 Poste 邮件服务。只运行其余六个任务时可跳过 Poste 部署；整份列表也不需要部署 Canvas、WooCommerce 或 Kubernetes。若与 C-local 共用实例，两组仍共享 Poste，任一组使用邮件服务时都不能重建它；分组本身不隔离邮箱状态。

`quantitative-financial-analysis` 的预处理先初始化 Google Drive/Sheets，再复制 Notion 的 `Quant Research` 页面；agent 写行情表格及 Notion 链接/评论，评分检查两边结果。它需要 Google OAuth 和 Notion 两套认证，不能因为历史记录先报 Google 凭据缺 `token` 就省略 Notion 配置。

## 部署与检查

在仓库根目录执行：

```bash
# 预览，不部署
bash global_preparation/deploy_notion_containers.sh --dry-run

# 已有 Poste 时先检查；不会重建或清空邮件
bash global_preparation/deploy_notion_containers.sh --check

# 首次部署，或需要重置这套邮件环境时执行
bash global_preparation/deploy_notion_containers.sh
```

默认部署复用 `deployment/poste/scripts/setup.sh start true`：重建 `poste<instance_suffix>`，清空当前仓库的 `deployment/poste/data/`、`deployment/poste/configs/`，按原流程创建邮箱账号。它仍创建原流程的整批账号，没有另写一套两任务账号初始化逻辑。不要在其他任务使用同一 Poste 时执行重建。

如果原环境使用 `deploy_containers.sh false`，这里也传 `false`。它控制原有 Dovecot/Haraka 配置步骤：

```bash
bash global_preparation/deploy_notion_containers.sh false
```

容器运行时、实例后缀沿用现有配置；服务检查从容器实际端口映射读取端口。`ports_config.yaml` 的映射仍需通过原来的 `apply_port_numbers.py` 流程应用，单改 YAML 不会改写任务代码。

新脚本检查账号初始化统计、HTTP 响应、IMAP/SMTP 协议响应；`--check` 只检查现有服务响应。等待默认 180 秒，可用 `POSTE_READY_TIMEOUT_SECONDS` 调整。检查不发送邮件，也不验证 Notion 登录、邮箱登录或任务最终得分。失败退出非零，保留 Poste 现场供排查；不会自动重复重建。

## 运行任务列表

仍需准备普通 Notion integration 配置、源页面/评测页面、`configs/.mcp-auth` 中的 Notion OAuth 授权，以及表中各任务所需的其他服务配置。页面清理/复制与任务邮箱清理由各自 preprocess 执行。

Notion 任务共享 OAuth 刷新状态与页面操作流程，并发可能造成刷新锁等待超时和状态竞争。按以下命令逐个运行任务：

```bash
bash scripts/run_parallel_task_list.sh \
  --task-list configs/task_lists/finalpool/c-notion.txt \
  dumps/notion-run1 \
  glm-5.2 unified 1
```

最后的 `1` 是 workers，不能省略；wrapper 默认值为 10，不适用于 Notion。可以替换模型名和 provider，但 workers 保持为 1。这个参数只限制当前进程，因此其他终端或模型作业也必须等当前 Notion 作业结束后再启动。

需要多轮时，在同一个命令中使用 `--attempts`，保持每轮任务串行、轮次之间顺序执行：

```bash
bash scripts/run_parallel_task_list.sh \
  --attempts 3 \
  --task-list configs/task_lists/finalpool/c-notion.txt \
  dumps/notion-experiment \
  glm-5.2 unified 1
```

这里不要加 `--deploy-before-attempt`：该选项仍然调用完整的 `global_preparation/deploy_containers.sh`。已有可用 Poste 时不必每轮重建；不同实验使用不同 dump 路径，并依次运行。最小部署不隔离共享邮箱、远程 Notion 页面或 OAuth 状态。
