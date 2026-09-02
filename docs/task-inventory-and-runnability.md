# Toolathlon 任务盘点与可跑性评估

- 报告日期：2026-09-01
- 任务集：本仓库 `tasks/finalpool`，共 **108** 个任务
- 实跑数据来源：`/data01/lwx/Toolathlon/results/` 下 7 个历史批次（该环境已完成部署，跑过 GLM-5.3 ×2、telechat ×2、id11 ×1，以及两个派生池）
- 判定口径：`eval_res.json` 中 `pass == true` 记 PASS，`pass == false` 记 FAIL，文件缺失或损坏记 NO_EVAL（多为 preprocess 失败、容器硬超时或评测器未启动）

> 注意：历史实跑环境使用的是一个 73 任务的子集，本仓库 `finalpool` 多出 35 个任务（主要是 Google / Notion 系）。这 35 个**没有任何实跑记录**，详见第四节。

---

## 一、总览

| 类别 | 数量 | 占比 |
|---|---|---|
| 稳定可跑（最强模型两轮均 PASS） | 37 | 34% |
| 不稳定（两轮一 PASS 一 FAIL，重跑可捞回） | 8 | 7% |
| 从未通过 — 环境/凭据问题为主 | 12 | 11% |
| 从未通过 — 模型能力/任务难度为主 | 14 | 13% |
| 无有效评测产出（评测器/preprocess 故障） | 2 | 2% |
| **未验证（无任何实跑记录）** | **35** | **32%** |
| 合计 | 108 | |

即：73 个有数据的任务里 37 个稳定可跑；另有 35 个任务的可跑性完全未知。

---

## 二、历史实跑批次

| 批次 | 任务池 | 总数 | PASS | FAIL | NO_EVAL |
|---|---|---|---|---|---|
| `260821_toolathlon_glm5.3_result` | finalpool(73) | 73 | 41 | 29 | 3 |
| `260826_toolathlon_glm5.3_result` | finalpool(73) | 74 | 41 | 28 | 5 |
| `260825_results_telechat3-438b-...` | finalpool(73) | 73 | 5 | 53 | 15 |
| `260826_results_telechat3-438b-...` | finalpool(73) | 73 | 9 | 63 | 1 |
| `260827_results_id11_stage4` | finalpool(73) | 73 | 6 | 65 | 2 |
| `260826_yt_campus_glm5.3_result` | 合成校园池 | 163 | 25 | 126 | 12 |
| `260823_toolathlon_dwm_glm5.3_result` | 派生变体池 | 3895 | 1388 | 1774 | 733 |

GLM-5.3 是目前表现最强的模型（41/73 ≈ 56%），telechat 与 id11 系列显著偏低。下文以 GLM-5.3 两轮作为"任务本身能否跑通"的判定基准，跨模型数据作为稳定性参考。

---

## 三、有实跑数据的 73 个任务

### 3.1 稳定可跑：GLM-5.3 两轮均 PASS（37 个）

当前最可靠的评测子集：

```
add-bibtex
apply-phd-email
canvas-arrange-exam
canvas-art-quiz
canvas-homework-grader-python
canvas-new-students-notification
canvas-submit-late-work
course-schedule
courses-ta-hws
cvpr-research
dietary-health
email-paper-homepage
excel-data-transformation
excel-market-research
filter-low-selling-products
find-alita-paper
git-bug-hunt
git-milestone
git-repo
identify-all-songs
inventory-sync
k8s-deployment-cleanup
k8s-pr-preview-testing
meeting-assign
paper-checker
payable-invoice-checker
ppt-analysis
profile-update-online
reimbursement-form-filler
sales-accounting
stock-build-position
train-ticket-plan
verl-dataset
wandb-best-score
wandb-shortest-length
woocommerce-update-cover
youtube-repo
```

跨全部 5 个批次都稳定的只有 `ppt-analysis`（5/5）与 `cooking-guidance`（3/3，另 2 轮 NO_EVAL）；4/5 档为 `canvas-art-quiz`、`find-alita-paper`、`git-bug-hunt`、`canvas-homework-grader-python`。这说明 37 个中大部分对模型能力敏感 —— 适合当有区分度的评测集，但不适合当"环境健康度自检"用。

### 3.2 不稳定：一轮 PASS 一轮 FAIL（8 个）

多为环境抖动，重跑有较大概率捞回：

| 任务 | 260821 | 260826 |
|---|---|---|
| `cooking-guidance` | PASS | NO_EVAL |
| `ipad-edu-price` | FAIL | PASS |
| `k8s-mysql` | PASS | FAIL |
| `landing-task-reminder` | FAIL | PASS |
| `logical-datasets-collection` | FAIL | PASS |
| `mrbeast-analysis` | PASS | FAIL |
| `sla-timeout-monitor` | FAIL | PASS |
| `yahoo-analysis` | PASS | FAIL |

### 3.3 从未通过（26 个）

**A. 环境/凭据问题为主（12 个，修复后有望恢复）**

| 任务 | 根因 |
|---|---|
| `nvidia-market`、`nvidia-stock-analysis`、`invoice-org`、`travel-exchange` | Yahoo Finance 公共接口 IP 限流 429（必现） |
| `merge-hf-datasets`、`huggingface-upload` | HuggingFace 客户端 read timeout 仅 10/15s，跨国链路稳定超时（必现） |
| `academic-pdf-report`、`language-school`、`shopping-helper`、`hk-top-conf` | Playwright `page.goto` 60s 超时 + 目标站点反爬（必现） |
| `k8s-redis-helm-upgrade` | Docker Registry 5xx + ImagePullBackOff |
| `woocommerce-new-product` | IMAP/SMTP 抖动 + 连接被拒 |

一个佐证：这些任务中的 `nvidia-market`、`nvidia-stock-analysis`、`invoice-org`、`merge-hf-datasets` 在派生变体池里都有相当数量的变体通过（见 4.2 节），说明失败主因是外部服务抖动而非任务不可解。

**B. 模型能力/任务难度为主（14 个）**

```
arrange-workspace              canvas-art-manager        canvas-do-quiz
canvas-list-test               course-assistant          detect-revised-terms
imagenet                       interview-report          latex-prompt-box
personal-website-construct     privacy-desensitization   sync-todo-to-readme
travel-expense-reimbursement   university-course-selection
```

Canvas 测验系列（`canvas-do-quiz`、`canvas-list-test`、`canvas-art-manager`）在失败集的高频工具 Top10 中集中出现，是明确的能力短板方向。`interview-report` 曾在 telechat 一轮偶然 PASS，严格说属极低通过率而非完全不可跑。

### 3.4 无有效评测产出（2 个）

| 任务 | 现象 |
|---|---|
| `task-tracker` | 5 个批次全部 NO_EVAL；preprocess 连续卡死至 1.5h 超时，怀疑 Notion refresh lock 争用 |
| `dataset-license-issue` | 5 个批次全部 NO_EVAL |

这两个属于基础设施故障，不是难度问题，需单独排查。

---

## 四、未验证的 35 个任务

本仓库 `finalpool` 比历史实跑用的子集多出以下 35 个任务，**无任何实跑记录**：

**Google 系（29 个，依赖 google_sheet / google-cloud / google_map / google_calendar / google_forms）**

```
ab-testing                        academic-warning
flagged-transactions              game-statistics
gdp-cr5-analysis                  inter-final-performance-analysis
investment-decision-analysis      k8s-safety-audit
live-transactions                 llm-training-dataset
machine-operating                 music-analysis
nhl-b2b-analysis                  notion-find-job
price-comparison                  quantitative-financial-analysis
search-ca-school                  set-conf-cr-ddl
student-interview                 subway-planning
trip-adviser                      trip-itinerary-generator
update-material-inventory         upenn-campus-route
vlm-history-completer             woocommerce-customer-survey
woocommerce-new-welcome           woocommerce-product-recall
woocommerce-stock-alert
```

已知阻塞：Google OAuth credentials 缺 `refresh_token` / `client_secret` / `client_id` 字段，报错 `Authorized user info was not in the expected format`。这在历史环境中标记为**必现**问题 —— 只要跑到就失败。启用这 29 个任务的前提是重新走一遍 OAuth 生成完整的 credentials JSON。

**Notion 系（5 个）**

```
experiments-recordings   notion-hr   notion-movies
notion-personal-website  oil-price
```

已知阻塞：Notion refresh lock 争用（`notion_official refresh lock contended for >600s`），`oil-price` 在历史环境中曾出现 preprocess fail。同池的 `task-tracker` preprocess 连续两次卡死，高度怀疑同一根因。缓解办法是跑前清理 `configs/.mcp-auth/*.lock`，批量跑之前预热 token。

**其他（1 个）**

`fillout-online-forms` —— 同属 Google OAuth 阻塞。

另有一个交叉项值得注意：`price-comparison` 在派生变体池里跑过 466 个变体，**全部 NO_EVAL**（见 4.2），说明它的评测器本身有问题，不只是 OAuth 阻塞。

### 4.2 派生变体池的旁证数据

历史环境跑过一个从 9 个母任务批量派生的 3895 变体池，可用来判断母任务的"理论可解性"：

| 母任务家族 | 变体数 | PASS | FAIL | NO_EVAL | 通过率 |
|---|---|---|---|---|---|
| `ipad-edu-price` | 462 | 321 | 120 | 21 | 69% |
| `merge-hf-datasets` | 420 | 285 | 94 | 41 | 68% |
| `stock-build-position` | 451 | 269 | 166 | 16 | 60% |
| `yahoo-analysis` | 231 | 133 | 76 | 22 | 58% |
| `verl-dataset` | 384 | 187 | 167 | 30 | 49% |
| `nvidia-market` | 494 | 95 | 363 | 36 | 19% |
| `nvidia-stock-analysis` | 494 | 65 | 378 | 51 | 13% |
| `invoice-org` | 493 | 33 | 410 | 50 | 7% |
| `price-comparison` | 466 | 0 | 0 | **466** | — |

---

## 五、MCP 依赖分布（108 个任务）

按 `task_config.json` 的 `needed_mcp_servers` 统计：

| MCP | 任务数 | | MCP | 任务数 |
|---|---|---|---|---|
| filesystem | 86 | | google_map | 6 |
| terminal | 48 | | arxiv_local | 5 |
| fetch | 25 | | scholarly | 5 |
| playwright_with_chunk | 24 | | huggingface | 5 |
| emails | 24 | | k8s | 5 |
| excel | 23 | | snowflake | 4 |
| pdf-tools | 20 | | wandb | 3 |
| google_sheet | 11 | | youtube-transcript | 3 |
| yahoo-finance | 10 | | howtocook / git / word / youtube / google_calendar / google_forms | 各 2 |
| memory | 9 | | arxiv-latex / web_search / pptx / rail_12306 | 各 1 |
| woocommerce | 9 | | | |
| google-cloud | 8 | | | |
| canvas | 8 | | | |
| notion | 8 | | | |
| github | 7 | | | |

### 5.1 低外部依赖任务（27 个）

不依赖任何高风险外部服务（不含 yahoo-finance / huggingface / playwright / youtube / notion / k8s / woocommerce / emails / snowflake / rail_12306 / web_search / scholarly / google 系），只用 filesystem / terminal / excel / pdf-tools / canvas / memory / github / howtocook / wandb / word / pptx / arxiv-latex / fetch / git：

```
arrange-workspace                canvas-art-quiz              canvas-do-quiz
canvas-list-test                 canvas-new-students-notification
cooking-guidance                 course-schedule              courses-ta-hws
detect-revised-terms             dietary-health               excel-data-transformation
excel-market-research            git-milestone                git-repo
imagenet                         interview-report             latex-prompt-box
paper-checker                    personal-website-construct   ppt-analysis
privacy-desensitization          reimbursement-form-filler    sales-accounting
sync-todo-to-readme              university-course-selection  wandb-best-score
wandb-shortest-length
```

这批受外部网络与凭据影响最小，环境自检和快速回归优先从这里选。取其与 3.1 节的交集（既低依赖又稳定通过）共 13 个：`canvas-art-quiz`、`course-schedule`、`courses-ta-hws`、`dietary-health`、`excel-data-transformation`、`excel-market-research`、`git-milestone`、`git-repo`、`ppt-analysis`、`reimbursement-form-filler`、`sales-accounting`、`wandb-best-score`、`wandb-shortest-length` —— 这是最适合做 smoke test 的一组。

### 5.2 高风险依赖分组（用于安排并发与限流）

| 依赖 | 任务数 | 已知问题与缓解方向 |
|---|---|---|
| emails | 24 | mcp.com 邮件服务并发限登录 → 单账户串行 + 指数退避 |
| playwright_with_chunk | 24 | 超时与反爬 → 加大超时（>60s）、调整加载策略与 UA |
| google 系 | 29 | OAuth credentials 字段缺失（必现）→ 重新生成完整 credentials JSON |
| yahoo-finance | 10 | 公共接口 IP 限流 → 令牌桶 + 共享缓存 |
| woocommerce | 9 | 连接抖动 |
| notion | 8 | refresh lock 争用 → 跑前清 `*.lock`，预热 token |
| huggingface | 5 | read timeout 10/15s 太短 → 提到 ≥60s 或走本地镜像 |
| k8s | 5 | MCP 稳定性 + 镜像预拉 |
| snowflake | 4 | — |
| rail_12306 | 1 | MCP 启动超时 → 加大启动超时、预装 npm 依赖 |

---

## 六、任务冲突约束

`tasks/finalpool/task_conflict.json` 定义了 4 组互斥任务（共享同一外部账户状态，不能并发执行）：

```
set-conf-cr-ddl              / student-interview
huggingface-upload           / dataset-license-issue
woocommerce-customer-survey  / woocommerce-product-recall
canvas-submit-late-work      / canvas-do-quiz
```

本仓库的 108 任务全集完整覆盖这 8 个任务（历史环境的 73 子集只覆盖了其中 4 个），所以并发跑时这 4 组约束全部生效。

---

## 七、运行方式与建议

### 7.1 入口

单任务调试：

```bash
bash scripts/run_single_containerized.sh \
  finalpool/find-alita-paper quickstart ./results/dumps_quick_start <model-name>
```

并行批跑（`scripts/run_parallel.sh` 中 `TASKS_FOLDER="finalpool"` 为硬编码）：

```bash
TASK_LIST=./my_tasks.txt bash scripts/run_parallel.sh \
  <model-name> ./results/<out-dir> unified <workers> \
  lockon0927/toolathlon-task-image:1016beta "" containerized normal toolathlon_default
```

`TASK_LIST` 指向一个每行一个任务名的 txt，可跑任意子集。正式批跑前需执行 `bash global_preparation/deploy_containers.sh true` 重置服务容器。

### 7.2 建议

**要立刻有稳定基线**：用 3.1 节的 37 个任务做 task list。若要先验证环境本身，用 5.1 节末尾那 13 个低依赖 + 稳定通过的任务做 smoke test。

**要扩大可用任务量**，按投入产出排序：

1. **修 Google OAuth credentials** —— 一次性解锁 29 个未验证任务，是单项收益最大的。需要重新走 OAuth 流程生成含 `refresh_token`/`client_secret`/`client_id` 的完整 credentials JSON。
2. **修 HuggingFace read timeout 和 Yahoo Finance 限流** —— 直接影响 6 个已知失败任务，且派生池数据显示这些任务本身可解。
3. **加大 Playwright 超时** —— 影响 4 个任务。
4. **清理 Notion lock 机制** —— 解锁 5 个未验证任务 + 修复 `task-tracker`。

**需要单独排查的评测器/基础设施故障**（产出为空，不是难度问题）：

- `task-tracker` preprocess 卡死（疑 Notion lock）
- `dataset-license-issue` 5 轮零评测产出
- `price-comparison` 466 个派生变体全 NO_EVAL
