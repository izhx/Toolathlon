# finalpool 108 任务 网络依赖风险分类

> 依据 `tasks/finalpool/*/task_config.json` 的 `needed_mcp_servers`、`docs/task.md` 的实际操作内容、以及 `token_key_session.py` 的 `*_read_only` 覆盖，对 finalpool 全部 108 个任务做四分类。
> 这里分类只回答「这个任务能不能稳定评测」，不涉及任务本身难度。

## 分类判据

- **A 无网络依赖**：只使用本地 MCP（filesystem / terminal / git / memory / excel / pdf-tools / word / pptx / howtocook）或本地 python，不触网。- **B 有网络依赖、低风险**：只读外部数据（fetch / scholarly / arxiv_local / arxiv-latex / yahoo-finance / google_map / youtube-transcript / web_search / playwright 纯浏览 / github 只读 / wandb 浏览 / youtube 只读）。不改外部状态，偶发限流或超时多半可重试，不易影响评测结果判定。
- **C 有网络依赖、高风险**：对外部服务有「写 / 改状态」操作（发邮件、写云端文档、上传/改仓库、k8s 操作、创建表单/事件/日历、提交表单、写数据库）。会挂真实凭据、有状态冲突、限流或幂等性问题，评测易不稳定。
- **D 当前无法评测**：默认留空。个别任务（强 OAuth、必现缺失凭据、无 run 记录）等确认后再填进来。

某任务只要触到任一「写」操作即归 C；B 里只读任务的 github / youtube / wandb 等均未开写。

---

## A. 无网络依赖（15）

| 任务 | 依赖 | 说明 |
|---|---|---|
| arrange-workspace | filesystem, terminal, pdf-tools, excel | 整理 workspace、填表 |
| cooking-guidance | filesystem, howtocook | 本地菜谱问答 |
| courses-ta-hws | terminal, excel, filesystem | 作业批改统计 |
| detect-revised-terms | filesystem, pdf-tools | 检测论文术语改动 |
| dietary-health | filesystem, howtocook, excel, terminal | 饮食健康分析 |
| excel-data-transformation | excel, filesystem, terminal | 本地 excel 变换 |
| excel-market-research | excel, filesystem, terminal | 本地 excel 市场研究 |
| imagenet | filesystem, pdf-tools | 读论文/本地数据 |
| interview-report | filesystem, word | 面试报告排版 |
| paper-checker | filesystem, terminal | 论文查重/格式检查 |
| ppt-analysis | pptx, filesystem, pdf-tools | 本地 PPT 分析 |
| privacy-desensitization | filesystem, terminal | 本地信息脱敏 |
| reimbursement-form-filler | filesystem, excel, pdf-tools, terminal | 报销单本地填写 |
| sales-accounting | memory, excel, filesystem | 记账 |
| university-course-selection | filesystem, pdf-tools, terminal, excel | 选课本地处理 |

**说明**：latex-prompt-box 用到 `arxiv-latex`（拉 arxiv 源），属网络只读，归到 B。A 全部任务即使断网也能跑。

---

## B. 有网络依赖、低风险（只读，无状态修改）（30）

| 任务 | 依赖 | 说明 |
|---|---|---|
| academic-pdf-report | fetch, arxiv_local, playwright | 读论文信息 |
| add-bibtex | scholarly, playwright, fetch | 拉 bibtex |
| course-schedule | fetch | 读课程日程 |
| cvpr-research | fetch, playwright | 查研究方向 |
| find-alita-paper | arxiv_local, scholarly | 搜论文 |
| git-milestone | fetch | 读公开信息 |
| git-repo | github | 检索 repo，无写覆盖 |
| hk-top-conf | playwright, fetch | 读港校招生页 |
| identify-all-songs | youtube-transcript, playwright, fetch | 读视频列表 |
| invoice-org | yahoo-finance | 读行情 |
| ipad-edu-price | yahoo-finance, playwright, fetch | 比价 |
| language-school | playwright, fetch | 读语言要求 |
| latex-prompt-box | arxiv-latex | 拉 arxiv 源作样式参考 |
| logical-datasets-collection | scholarly, arxiv_local, fetch | 搜+下载 |
| mrbeast-analysis | youtube, youtube-transcript | 只读视频数据，结果写本地 xlsx |
| nvidia-market | yahoo-finance, playwright, fetch | 读行情 |
| nvidia-stock-analysis | yahoo-finance, web_search, playwright | 读行情 |
| profile-update-online | playwright, scholarly, arxiv_local | 读+更新本地 profile |
| search-ca-school | google_map, playwright, fetch | 查校 |
| shopping-helper | playwright | 只读产品页 |
| stock-build-position | yahoo-finance | 读行情 |
| subway-planning | google_map, playwright, fetch | 查线路 |
| travel-exchange | yahoo-finance | 读汇率 |
| trip-adviser | google_map, fetch, playwright | 查地点 |
| trip-itinerary-generator | google_map, playwright | 查景点 |
| upenn-campus-route | google_map, fetch | 查路线 |
| wandb-best-score | wandb | 浏览 run |
| wandb-shortest-length | wandb | 浏览 run |
| yahoo-analysis | yahoo-finance | 读行情 |
| youtube-repo | youtube-transcript, fetch, github | 读视频列表+检索 repo，结果写本地；github 无写覆盖 |

**说明**：B 里所有 github / youtube / wandb / arxiv-latex 使用均为只读（无 `*_read_only="0"` 覆盖），结果写本地文件。偶发限流（如 yahoo 429、playwright 60s 超时、fetch 网络抖动）可重试。

---

## C. 有网络依赖、高风险（有写 / 改状态 / 强限流）（63）

**（说明）** 下列均会「写 / 改外部状态」。同一任务可能命中多个写入口（如 woocommerce 同时发邮件），下方标注其全部写入口，任务只列一次。

| 任务 | 依赖 | 写入口 | 说明 |
|---|---|---|---|
| ab-testing | google-cloud | GCP/BigQuery | 写 storage bucket + 日志 |
| academic-warning | google-cloud | GCP/BigQuery | 写日志 bucket |
| apply-phd-email | emails | 邮件 | 按邮件要求回复提交材料 |
| canvas-arrange-exam | canvas, emails | canvas, 邮件 | 读公告填表，登记考试 |
| canvas-art-manager | canvas, emails | canvas, 邮件 | 创建课程 |
| canvas-art-quiz | canvas | canvas | 创建测验 |
| canvas-do-quiz | canvas | canvas | 提交测验 |
| canvas-homework-grader-python | canvas, emails | canvas, 邮件 | 读取批改并打分 |
| canvas-list-test | canvas | canvas | 登记未提交作业 |
| canvas-new-students-notification | canvas | canvas | 选课+私信 |
| canvas-submit-late-work | canvas, emails | canvas, 邮件 | 补交作业 |
| course-assistant | emails | 邮件 | 发催交通知邮件 |
| dataset-license-issue | huggingface, github, fetch | HF, github | 回复+关闭 issue，更新 HF 页 |
| email-paper-homepage | emails, github | 邮件, github | 改主页+开源状态 |
| experiments-recordings | notion, wandb | notion | 填 notion 实验结果 |
| fillout-online-forms | playwright | 表单 | 提交真实问卷 |
| filter-low-selling-products | woocommerce, emails | woocommerce, 邮件 | 改类目+发邮件 |
| flagged-transactions | google-cloud | GCP/BigQuery | 写审计 xlsx |
| game-statistics | google-cloud | GCP/BigQuery | 写 leaderboard 表 |
| gdp-cr5-analysis | google_sheet, playwright, fetch | gsheet | 新建 sheet 写 CR5 表 |
| git-bug-hunt | emails | 邮件 | 发邮件给提交作者 |
| huggingface-upload | huggingface | HF | 推送 model repo |
| inter-final-performance-analysis | playwright, google_sheet, fetch | gsheet | 填赛事数据 |
| inventory-sync | woocommerce | woocommerce | 同步库存 |
| investment-decision-analysis | yahoo-finance, google_sheet | gsheet | 建 3 个 sheet |
| k8s-deployment-cleanup | k8s, emails | k8s, 邮件 | 停部署+邮件 |
| k8s-mysql | k8s | k8s | 调试集群内数据库 |
| k8s-pr-preview-testing | playwright, k8s | k8s, 交互 | 部署+跑测试 |
| k8s-redis-helm-upgrade | k8s | k8s | helm 升级 |
| k8s-safety-audit | k8s, google_sheet | k8s, gsheet | 审计写 sheet |
| landing-task-reminder | emails, snowflake | 邮件, 库 | 写库+发邮件 |
| live-transactions | google-cloud | GCP/BigQuery | 上传存档+写日志 |
| llm-training-dataset | playwright, google_sheet, scholarly, fetch | gsheet | 整理训练集写入 |
| machine-operating | google-cloud | GCP/BigQuery | 上传报告+写日志 |
| meeting-assign | fetch, emails, playwright | 邮件 | 读日程发邮件 |
| merge-hf-datasets | huggingface | HF | 合并数据集 |
| music-analysis | excel, google_sheet | gsheet | 新 sheet 写分析 |
| nhl-b2b-analysis | google_sheet, filesystem, terminal | gsheet | 新 sheet 写分析 |
| notion-find-job | google_map, notion, emails, playwright | notion, 邮件 | 更新 Job Tracker + 发信 |
| notion-hr | emails, notion | notion, 邮件 | 更新候选人+发信 |
| notion-movies | playwright, notion, fetch | notion | 更新电影页 |
| notion-personal-website | notion | notion | 更新页面 |
| oil-price | yahoo-finance, notion | notion | 读行情写 notion |
| payable-invoice-checker | emails, snowflake | 邮件, 库 | 更新库表+发信 |
| personal-website-construct | memory, github | github | fork 并填主页 |
| price-comparison | google-cloud | GCP/BigQuery | 写结果表 |
| quantitative-financial-analysis | yahoo-finance, google_sheet, notion | gsheet, notion | 写行情+写 notion |
| set-conf-cr-ddl | emails, google_calendar | 邮件, 日历 | 读邮件写日历 |
| sla-timeout-monitor | emails, snowflake | 邮件, 库 | 查库发信 |
| student-interview | emails, google_calendar | 邮件, 日历 | 排面试写日历 |
| sync-todo-to-readme | git, github | github | 更新远程 README |
| task-tracker | github, notion | github, notion | 建分支+更新 notion |
| train-ticket-plan | rail_12306, fetch | 购票 | 12306 查票 |
| travel-expense-reimbursement | emails, snowflake | 邮件, 库 | 写库+发信 |
| update-material-inventory | google_sheet, woocommerce | gsheet, woocommerce | 扣库存+同步可售量 |
| verl-dataset | huggingface, fetch | HF | 下载转格式 |
| vlm-history-completer | playwright, google_sheet, arxiv_local, huggingface, fetch | gsheet, HF | 填列+读模型源 |
| woocommerce-customer-survey | woocommerce, emails, google_forms | woocommerce, 邮件, 表单 | 建表单发问卷 |
| woocommerce-new-product | woocommerce, emails | woocommerce, 邮件 | 发新品/折扣信 |
| woocommerce-new-welcome | woocommerce, google-cloud, emails | woocommerce, 邮件, GCP | 同步客户+欢迎信 |
| woocommerce-product-recall | woocommerce, emails, google_forms | woocommerce, 邮件, 表单 | 下架+召回信+表单 |
| woocommerce-stock-alert | woocommerce, google_sheet, emails | woocommerce, gsheet, 邮件 | 低库存上报发信 |
| woocommerce-update-cover | woocommerce | woocommerce | 改主图 |

**设计说明（为何这些算高风险）**：所有 C 任务都会改动外部真实状态——邮件发出去、云端文档被写、仓库被改、集群被打、表单被提交、数据库表被更新。要么依赖真实凭据（缺凭据必现失败），要么有状态冲突/限流/幂等问题（重试可能产生副作用），因此在「评测稳定性」维度上归为高风险。

---

## D. 当前无法评测

（默认留空，具体任务后面确认后再填。）

---

## 合计校验

A(15) + B(30) + C(63) + D(0) = **108**（与 finalpool 任务目录数一致）

---

## 与评测稳定性强相关的已知风险点

- **`emails`**：真实 SMTP/IMAP，`mcp.com` 有并发限流，多任务并发易 429。
- **`canvas`**：改真实课程/测验状态，需凭据并可能被课程方审计。
- **`google-cloud`（BigQuery/Storage）**：写 bucket/表/日志需真实 GCP 凭据 + `--allowed-*`；配置缺项必现失败。
- **`playwright_with_chunk`**：`page.goto` 60s 超时 + 反爬；纯浏览时偶发不稳定，调用 chunk 分页。
- **`yahoo-finance`**：IP 级 429 较常见。
- **`fetch`（npx-fetch）**：依赖目标站网络通畅。
- **`arxiv_local` / `arxiv-latex`**：需网络下载；`arxiv-latex` 10s 超时偏短。
- **`notion`**：刷新锁争用，并发易失败。
- **`huggingface`**：上传/下载，依赖网络稳定。
- **`google_sheet` / `google_calendar` / `google_forms` / `google_map`**：OAuth 凭据缺 `refresh_token`/`client_secret`/`client_id` 必现失败；`google_map` 只读归 B，其余写归 C。
- **`github`**：默认 `github_read_only="1"`；未开写的任务（如 git-repo / youtube-repo）只读，但若目标 repo 不在 `github_allowed_repos` 里也会失败。
