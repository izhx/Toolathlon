# finalpool task debug 进展跟踪

- 初始化日期：2026-09-04
- 分组来源：[finalpool 四组 task list](../configs/task_lists/finalpool/)
- 环境错误来源：[lwx-env-error.md](lwx-env-error.md)：仅覆盖 260812 GLM-5.1 两个批次，并只统计从工具消息提取到的环境错误；本表中的“—”表示该文档未点名，不代表已证明没有环境问题。
- 可跑性来源：[task-inventory-and-runnability.md](task-inventory-and-runnability.md)：3.1–4 节为历史评测分类，不能代替本次个人实跑。
- “我跑通情况”是独立人工进度列。当前未提供可唯一对应的个人运行结果目录，因此初始化为“⬜ 待填写”。建议填写为“✅ PASS（run/日期）”“❌ FAIL（错误摘要）”或“🚧 BLOCKED（阻塞项）”。

## task inventory 分类说明

表格里的 `3.1`、`3.2` 等编号，指向 [task-inventory-and-runnability.md](task-inventory-and-runnability.md) 的章节，是根据历史评测结果划分的**可跑性分类**。它和本文的 A、B、C-local、C-remote **执行分组不是同一个维度**：执行分组描述网络、写操作和共享基础设施风险，可跑性分类描述历史运行结果。

| 标记 | 具体含义 | 使用时应如何理解 |
|---|---|---|
| `3.1` | 稳定可跑：GLM-5.3 两轮均 PASS，共 37 个 | 有较强的历史跑通证据，但不保证当前模型、凭据和环境一定通过 |
| `3.2` | 不稳定，共 8 个：两个 GLM-5.3 批次结果不一致 | 多数是一轮 PASS、一轮 FAIL；`cooking-guidance` 是例外，为 PASS / NO_EVAL。可优先重跑确认 |
| `3.3 A` | 有历史运行，但从未通过；主要归因于环境或凭据，共 12 个 | 优先修外部服务、网络、超时、凭据或基础设施，再判断模型能力。这里的 A 是 3.3 的子类，不是“A 无网络依赖”执行组 |
| `3.3 B` | 有历史运行，但从未通过；主要归因于模型能力或任务难度，共 14 个 | 环境错误证据不足，优先检查 agent 行为和任务完成质量；`interview-report` 曾由 telechat 偶然跑通一次 |
| `3.4` | 无有效评测产出，共 2 个 | preprocess 或评测器没有产生可判定结果，不能算模型 FAIL，需要先修评测链路 |
| `4` | 未验证，共 35 个 | 不在历史 73 任务子集中，没有对应实跑记录；表示“未知”，不表示 FAIL |
| `5.1 低外部依赖` | 不依赖文档列出的高风险外部服务 | 这是附加属性，可与 `3.1`–`4` 中任一可跑性分类同时出现 |
| `smoke test` | 文档建议的“低外部依赖且稳定通过”子集 | 适合环境自检；原文交集清单存在 `paper-checker` 漏项，本文保留原文口径并单独提示 |
| `第 6 节冲突约束` | 一对任务共享外部账户状态，不能并发执行 | 只限制调度方式，不代表任务本身 FAIL 或不可跑 |

结果术语：`PASS` 表示 `eval_res.json` 中 `pass == true`；`FAIL` 表示 `pass == false`；`NO_EVAL` 表示缺少或无法读取有效评测结果，常见于 preprocess 失败、容器超时或评测器未启动。

## 总体统计

| 分组 | 任务数 | env-error 有记录 | env-error 未提及 | task inventory 分类 | 我跑通情况 |
|---|---:|---:|---:|---|---|
| A：无网络依赖 | 15 | 0 | 15 | 3.1=8；3.2=1；3.3 B=6 | 待填写=15 |
| B：网络只读 | 30 | 13 | 17 | 3.1=12；3.2=4；3.3 A=8；3.3 B=1；4=5 | 待填写=30 |
| C-local：本地基础设施写 | 35 | 11 | 24 | 3.1=15；3.2=3；3.3 A=2；3.3 B=5；4=10 | 待填写=35 |
| C-remote：远端写 | 28 | 8 | 20 | 3.1=2；3.3 A=2；3.3 B=2；3.4=2；4=20 | 待填写=28 |
| **合计** | **108** | **32** | **76** | **3.1=37；3.2=8；3.3 A=12；3.3 B=14；3.4=2；4=35** | **待填写=108** |

> 文档一致性提示：`paper-checker` 同时出现在 task inventory 的 3.1 和 5.1，但第 242 行声称的“两者交集”清单漏掉了它；本表仍按两个原始清单记录，不擅自改写为 smoke test 成员。

## A：无网络依赖（15）

统计：env-error 有记录 0，未提及 15；task inventory：3.1=8；3.2=1；3.3 B=6；我跑通情况：待填写 15。

| 任务 | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|
| `arrange-workspace` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ⬜ 待填写 |
| `cooking-guidance` | — | 3.2 不稳定：260821 PASS，260826 NO_EVAL<br>跨 5 批次：3 次有效评测均 PASS，另 2 次 NO_EVAL<br>5.1 低外部依赖 | ⬜ 待填写 |
| `courses-ta-hws` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `detect-revised-terms` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ⬜ 待填写 |
| `dietary-health` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `excel-data-transformation` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `excel-market-research` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `imagenet` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ⬜ 待填写 |
| `interview-report` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>telechat 曾偶然 PASS；属极低通过率，并非完全不可跑<br>5.1 低外部依赖 | ⬜ 待填写 |
| `paper-checker` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖 | ⬜ 待填写 |
| `ppt-analysis` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 5/5 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `privacy-desensitization` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ⬜ 待填写 |
| `reimbursement-form-filler` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `sales-accounting` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `university-course-selection` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ⬜ 待填写 |

## B：网络只读（30）

统计：env-error 有记录 13，未提及 17；task inventory：3.1=12；3.2=4；3.3 A=8；3.3 B=1；4=5；我跑通情况：待填写 30。

| 任务 | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|
| `academic-pdf-report` | — | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ⬜ 待填写 |
| `add-bibtex` | 🔴 必现：Playwright 页面加载 60s 超时 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `course-schedule` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `cvpr-research` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `find-alita-paper` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 4/5 PASS | ⬜ 待填写 |
| `git-milestone` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `git-repo` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `hk-top-conf` | 🟡 偶发：Prompt 超长 400 | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ⬜ 待填写 |
| `identify-all-songs` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `invoice-org` | 🔴 必现：Yahoo Finance API 429 限流 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | ⬜ 待填写 |
| `ipad-edu-price` | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ⬜ 待填写 |
| `language-school` | 🔴 必现：Playwright 页面加载 60s 超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ⬜ 待填写 |
| `latex-prompt-box` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ⬜ 待填写 |
| `logical-datasets-collection` | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ⬜ 待填写 |
| `mrbeast-analysis` | 🔴 必现：Hugging Face 读取或 SSL 握手超时<br>🔴 必现：API Key 无效 | 3.2 不稳定：260821 PASS，260826 FAIL<br>文档判断多为环境抖动，重跑可能捞回 | ⬜ 待填写 |
| `nvidia-market` | 🔴 必现：Yahoo Finance API 429 限流<br>🔴 必现：Playwright 页面加载 60s 超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | ⬜ 待填写 |
| `nvidia-stock-analysis` | 🔴 必现：Yahoo Finance API 429 限流<br>🔴 必现：Playwright 页面加载 60s 超时<br>🔴 必现：API Key 无效<br>🟡 偶发：MCP 工具执行错误 -32603<br>🟡 偶发：Python 依赖缺失或 ABI 不匹配 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | ⬜ 待填写 |
| `profile-update-online` | 🔴 必现：Playwright 页面加载 60s 超时 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `search-ca-school` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `shopping-helper` | 🔴 必现：Yahoo Finance API 429 限流<br>🔴 必现：Playwright 页面加载 60s 超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ⬜ 待填写 |
| `stock-build-position` | 🔴 必现：Yahoo Finance API 429 限流 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `subway-planning` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `travel-exchange` | 🔴 必现：Yahoo Finance API 429 限流 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | ⬜ 待填写 |
| `trip-adviser` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `trip-itinerary-generator` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `upenn-campus-route` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `wandb-best-score` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `wandb-shortest-length` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `yahoo-analysis` | 🔴 必现：Yahoo Finance API 429 限流 | 3.2 不稳定：260821 PASS，260826 FAIL<br>文档判断多为环境抖动，重跑可能捞回 | ⬜ 待填写 |
| `youtube-repo` | 🔴 必现：API Key 无效 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |

## C-local：本地基础设施写（35）

统计：env-error 有记录 11，未提及 24；task inventory：3.1=15；3.2=3；3.3 A=2；3.3 B=5；4=10；我跑通情况：待填写 35。

| 任务 | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|
| `apply-phd-email` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `canvas-arrange-exam` | 🟡 偶发：IMAP 认证失败 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `canvas-art-manager` | 🟡 偶发：IMAP 认证失败<br>🟡 偶发：DNS 解析失败<br>🟡 偶发：MCP 工具执行错误 -32603<br>🟡 偶发：网络连接拒绝或中断 | 3.3 B 从未通过：模型能力/任务难度为主 | ⬜ 待填写 |
| `canvas-art-quiz` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 4/5 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ⬜ 待填写 |
| `canvas-do-quiz` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖<br>第 6 节冲突约束：不可与 `canvas-submit-late-work` 并发 | ⬜ 待填写 |
| `canvas-homework-grader-python` | 🟡 偶发：IMAP 认证失败 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 4/5 PASS | ⬜ 待填写 |
| `canvas-list-test` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ⬜ 待填写 |
| `canvas-new-students-notification` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖 | ⬜ 待填写 |
| `canvas-submit-late-work` | 🟡 偶发：IMAP 认证失败<br>🟡 偶发：SMTP 发送失败 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>第 6 节冲突约束：不可与 `canvas-do-quiz` 并发 | ⬜ 待填写 |
| `course-assistant` | 🟡 偶发：IMAP 认证失败 | 3.3 B 从未通过：模型能力/任务难度为主 | ⬜ 待填写 |
| `email-paper-homepage` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `filter-low-selling-products` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `git-bug-hunt` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 4/5 PASS | ⬜ 待填写 |
| `inventory-sync` | 🟡 偶发：Prompt 超长 400 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `k8s-deployment-cleanup` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `k8s-mysql` | 🟡 偶发：MCP 工具执行错误 -32603 | 3.2 不稳定：260821 PASS，260826 FAIL<br>文档判断多为环境抖动，重跑可能捞回 | ⬜ 待填写 |
| `k8s-pr-preview-testing` | 🟡 偶发：MCP 工具执行错误 -32603 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `k8s-redis-helm-upgrade` | 🟡 偶发：MCP 工具执行错误 -32603<br>🟡 偶发：Docker Registry 5xx / ImagePullBackOff<br>🟡 偶发：网络连接拒绝或中断 | 3.3 A 从未通过：环境/凭据问题为主<br>Docker Registry 5xx / ImagePullBackOff | ⬜ 待填写 |
| `k8s-safety-audit` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `landing-task-reminder` | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ⬜ 待填写 |
| `meeting-assign` | 🟡 偶发：IMAP 认证失败<br>🟡 偶发：SMTP 发送失败 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `notion-find-job` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `notion-hr` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | ⬜ 待填写 |
| `payable-invoice-checker` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `set-conf-cr-ddl` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id<br>第 6 节冲突约束：不可与 `student-interview` 并发 | ⬜ 待填写 |
| `sla-timeout-monitor` | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ⬜ 待填写 |
| `student-interview` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id<br>第 6 节冲突约束：不可与 `set-conf-cr-ddl` 并发 | ⬜ 待填写 |
| `travel-expense-reimbursement` | — | 3.3 B 从未通过：模型能力/任务难度为主 | ⬜ 待填写 |
| `update-material-inventory` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `woocommerce-customer-survey` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id<br>第 6 节冲突约束：不可与 `woocommerce-product-recall` 并发 | ⬜ 待填写 |
| `woocommerce-new-product` | 🟡 偶发：IMAP 认证失败<br>🟡 偶发：SMTP 发送失败<br>🟡 偶发：网络连接拒绝或中断 | 3.3 A 从未通过：环境/凭据问题为主<br>IMAP/SMTP 抖动或连接拒绝 | ⬜ 待填写 |
| `woocommerce-new-welcome` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `woocommerce-product-recall` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id<br>第 6 节冲突约束：不可与 `woocommerce-customer-survey` 并发 | ⬜ 待填写 |
| `woocommerce-stock-alert` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `woocommerce-update-cover` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |

## C-remote：远端写（28）

统计：env-error 有记录 8，未提及 20；task inventory：3.1=2；3.3 A=2；3.3 B=2；3.4=2；4=20；我跑通情况：待填写 28。

| 任务 | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|
| `ab-testing` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `academic-warning` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `dataset-license-issue` | — | 3.4 无有效评测产出：5 批次均 NO_EVAL<br>第 6 节冲突约束：不可与 `huggingface-upload` 并发 | ⬜ 待填写 |
| `experiments-recordings` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | ⬜ 待填写 |
| `fillout-online-forms` | 🔴 必现：Google OAuth credentials 缺字段 | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `flagged-transactions` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `game-statistics` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `gdp-cr5-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `huggingface-upload` | 🟡 偶发：Python 依赖缺失或 ABI 不匹配 | 3.3 A 从未通过：环境/凭据问题为主<br>Hugging Face 客户端 read timeout 10/15s<br>第 6 节冲突约束：不可与 `dataset-license-issue` 并发 | ⬜ 待填写 |
| `inter-final-performance-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `investment-decision-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `live-transactions` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `llm-training-dataset` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `machine-operating` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `merge-hf-datasets` | 🔴 必现：Hugging Face 读取或 SSL 握手超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Hugging Face 客户端 read timeout 10/15s | ⬜ 待填写 |
| `music-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `nhl-b2b-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `notion-movies` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | ⬜ 待填写 |
| `notion-personal-website` | 🟡 偶发：preprocess 阶段卡死 | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | ⬜ 待填写 |
| `oil-price` | 🟡 偶发：Notion refresh lock 争用（含疑似间接影响） | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用<br>历史环境曾出现 preprocess fail | ⬜ 待填写 |
| `personal-website-construct` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ⬜ 待填写 |
| `price-comparison` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id<br>另有 466 个派生变体全部 NO_EVAL，疑似评测器问题 | ⬜ 待填写 |
| `quantitative-financial-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
| `sync-todo-to-readme` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ⬜ 待填写 |
| `task-tracker` | 🟡 偶发：preprocess 阶段卡死<br>🟡 偶发：Notion refresh lock 争用（含疑似间接影响） | 3.4 无有效评测产出：5 批次均 NO_EVAL；preprocess 持续卡死，疑似 Notion refresh lock | ⬜ 待填写 |
| `train-ticket-plan` | 🟡 偶发：MCP server 启动超时（rail_12306） | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `verl-dataset` | 🔴 必现：Hugging Face 读取或 SSL 握手超时 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ⬜ 待填写 |
| `vlm-history-completer` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ⬜ 待填写 |
