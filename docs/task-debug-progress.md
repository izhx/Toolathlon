# finalpool task debug 进展跟踪

- 初始化日期：2026-09-04
- 网页版：[可筛选任务总表](task-debug-progress.html)（STATUS 按 ✅ 判断任务能否跑通，与评测 PASS / FAIL 无关）。修改本文后运行 `python3 scripts/generate_task_debug_csv.py`，仅更新 [CSV 数据](task-debug-progress.csv)；HTML 是固定模板，通过静态服务读取 CSV，刷新网页即可，无需重新生成 HTML。
- 分组来源：[finalpool 五组 task list](../configs/task_lists/finalpool/)
- 环境错误来源：[lwx-env-error.md](lwx-env-error.md)：仅覆盖 260812 GLM-5.1 两个批次，并只统计从工具消息提取到的环境错误；本表中的“—”表示该文档未点名，不代表已证明没有环境问题。
- 可跑性来源：[task-inventory-and-runnability.md](task-inventory-and-runnability.md)：3.1–4 节为历史评测分类，不能代替本次个人实跑。
- “我跑通情况”是独立人工进度列。图标表示任务链路是否跑通，后面的 `PASS` / `FAIL` / `NO_EVAL` 保留实际评测结果；已确认仅为能力、策略或效率问题的任务标为 `✅ FAIL` 或 `✅ NO_EVAL`，环境/基础设施阻塞保留 `❌` / `🟠` / `🚧`，未跑任务填“⬜ 待填写”。各组统计按评测结果计数。
- 历史批次来源（以下数量沿用拆分前口径，当前分组统计见下表）：A 组 15 个任务已按 GLM-5.2 实跑结果填写（run glm-5.2/260903，结果目录 [results/glm-5.2/](../results/glm-5.2/)，分析见 [ANALYSIS_glm-5.2.md](../results/glm-5.2/ANALYSIS_glm-5.2.md)）。B 组 30 个任务已按 GLM-5.2 实跑结果填写（run glm-5.2/260904，dump 目录 [results/glm-5.2/](../results/glm-5.2/)（已合并至总目录），并发 4；PASS 13/FAIL 7/NO_EVAL 10，尚未做逐项四层核验）。`🟠 NO_EVAL` 表示跑满 max_turns 未产出可判定结果。原 C-remote 组 28 个任务已按 GLM-5.2 实跑结果填写（run glm-5.2/260904，dump 到 [results/glm-5.2/](../results/glm-5.2/)，并发 8；PASS 3/FAIL 3/NO_EVAL 22，其中 21 个为 preprocess 阶段失败/卡住、未进入 agent 执行）。原 C-local 组已按 GLM-5.2 实跑结果填写 25/35 个任务（run glm-5.2/260905，dump 到 [results/glm-5.2/](../results/glm-5.2/)，并发 10、单任务超时 5400s；PASS 9/FAIL 2/NO_EVAL 14，尚未做逐项四层核验）。其中 14 个 NO_EVAL = 9 个 preprocess 阶段本地容器未就绪失败（Canvas `:50001` 连接拒绝 5 个、WooCommerce `:50003` SSL/连接失败 4 个，未进入 agent 执行）+ 5 个跑满 max_turns（`pass=null`）。注：执行报告 [execution_report_finalpool_glm-5.2_full.json](../results/glm-5.2/execution_report_finalpool_glm-5.2_full.json) 按 pass≠true 口径记为 passed 9 / failed 7 / not_executed 9，本表按 A/B 组一致口径把 5 个 max_turns 归入 NO_EVAL。其余 10 个任务（多为 Notion/Google 依赖）本次未跑，保持“⬜ 待填写”。

## BLOCK 服务依赖标签

`BLOCK` 可同时标注 `Yahoo Finance`、`Google`、`Notion`，记录任务配置声明及预处理/评测涉及的服务。**跑通后保留 BLOCK，STATUS 与依赖标签独立。** 标签不表示服务当前不可用；429、缺凭据、实际失败阶段和未验证情况保留在说明及“我跑通情况”中。`0` 表示未标注这三类依赖，不保证没有其他依赖或阻塞。

直接编辑下方各任务的 BLOCK 列：第一行用英文分号分隔标签，例如 `Yahoo Finance;Google;Notion`；可在 `<br>` 后追加说明。无这三类依赖填 `0`，不能把 `0` 与其他标签混用。导出脚本按固定顺序去重，仅读取显式标签，不根据跑通状态或报错文字重新归类。CSV 与 HTML 从本文更新，网页复选框用于筛选。

网页的任务类别、STATUS、BLOCK 均可多选：同一组内匹配任一选项，某组未选表示不限制该组；不同筛选组及搜索条件须同时满足。例如类别选 C-local 和 C-notion、STATUS 选“不通”和“没跑”，显示这两个类别中不通或没跑的任务；再选 Google 和 Notion，则要求任务还涉及其中任一服务。BLOCK 的 `0` 与服务选项互斥，勾选三个服务可查看所有已标注依赖的任务。顶部统计按任务去重，重置会清空所有选择和搜索。

2026-09-07 核对 108 个任务：Yahoo Finance 10、Google 30、Notion 8，共涉及 43 个任务，标签计数存在重叠。Google 包括声明 Google MCP 的 29 个任务，以及预处理/评测使用 Google 的 `fillout-online-forms`。交叉依赖包括 `quantitative-financial-analysis`（Yahoo Finance + Google + Notion）、`investment-decision-analysis`（Yahoo Finance + Google）、`oil-price`（Yahoo Finance + Notion）、`notion-find-job`（Google + Notion）。`ipad-edu-price` 已跑通，仍保留其任务配置声明的 Yahoo Finance 标签。

## task inventory 分类说明

表格里的 `3.1`、`3.2` 等编号，指向 [task-inventory-and-runnability.md](task-inventory-and-runnability.md) 的章节，是根据历史评测结果划分的**可跑性分类**。它和本文的 A、B、C-local、C-remote、C-notion **执行分组不是同一个维度**：执行分组描述网络、写操作和共享基础设施风险，可跑性分类描述历史运行结果。

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

## Google 依赖与认证说明

2026-09-05 按当前 `task_config.json`、MCP 配置及预处理/评测代码补充。以下数量按声明的 Google MCP 统计；逐任务的服务、凭据和使用阶段写在“task inventory 描述”列。依赖说明不代表当前凭据有效，也不代替“我跑通情况”中的实跑证据。

| Google 工具 | 任务数 | 需要配置什么 | 常见使用阶段 |
|---|---:|---|---|
| `google_map` | 6 | Maps API Key：`google_cloud_console_api_key` → `GOOGLE_MAPS_API_KEY`；按任务调用启用地图相关 API | agent 查询地点/路线；部分评测也调用 Maps |
| `google-cloud` | 8 | `gcp_project_id` + `gcp_service_account_path`；服务账号 JSON 默认 `configs/gcp-service_account.keys.json` | 预处理准备 BigQuery/Storage/Logging 数据，agent 访问，部分评测读取云端结果 |
| `google_sheet` | 11 | OAuth 用户凭据 `configs/google_credentials.json`，需 Sheets + Drive 权限；MCP 路径字段为 `google_oauth2_credentials_path` / `google_oauth2_token_path`；文件夹由任务的 `google_sheets_folder_id` 指定 | 预处理准备文件夹/表格，agent 读写，评测读取 |
| `google_calendar` | 2 | `configs/gcp-oauth.keys.json` + `configs/google_credentials.json`；容器启动脚本复制到容器用户的 `~/.calendar-mcp/`，后者改名为 `credentials.json`；需 Calendar 读写权限 | 预处理清理/初始化日程，agent 创建日程，评测查询 |
| `google_forms` | 2 | OAuth 用户凭据 `configs/google_credentials.json`，需 Forms + Drive 权限；MCP 使用 `google_client_id` / `google_client_secret` / `google_refresh_token` | 预处理清理表单，agent 创建表单，评测读取 |
| **合计** | **29** | **15 个 OAuth + 8 个服务账号 + 6 个 API Key** | 同类凭据可共用，无需逐任务认证 |

另有 `fillout-online-forms`：agent 未声明 Google MCP，但预处理/评测使用 Forms 与 Drive，同样需要 OAuth；它未计入上面的 29 个，但计入 BLOCK 的 30 个 Google 依赖任务。原先将这些任务一律标为“OAuth 缺字段”的记录已按实际依赖更正。9 个尚未实跑的 Google 相关任务标为“Google 配置待核”；BLOCK 保留 Google 标签，可同时包含其他服务，说明中的待核不表示已经确认凭据缺失。

Sheets 的共享预处理函数会直接读取 `token`、`refresh_token`、`token_uri`、`client_id`、`client_secret`、`scopes` 六个字段；Forms 清理函数也读取同一组字段。仅补齐 OAuth 的三个身份/刷新字段仍可能报 `KeyError: token`。Cloud 任务还需具备对应云资源权限，MCP 的 `google_cloud_allowed_*` 按任务配置限制资源范围；Maps Key 和服务账号 JSON 不能替代 OAuth 用户凭据。

依据：[任务清单认证分类](task-inventory-and-runnability.md)、[Maps](../configs/mcp_servers/google_map.yaml)、[Cloud](../configs/mcp_servers/google-cloud.yaml)、[Sheets](../configs/mcp_servers/google_sheet.yaml)、[Forms](../configs/mcp_servers/google_forms.yaml)、[Calendar](../configs/mcp_servers/google_calendar.yaml)、[Calendar 容器凭据复制](../scripts/run_single_containerized.sh)、[Sheets/Drive 凭据读取](../utils/app_specific/googlesheet/drive_helper.py)、[Forms 凭据读取](../utils/app_specific/google_form/ops.py)。

## 总体统计

2026-09-07 起使用五个互斥 task list；下表按当前逐任务记录重算，包含已记录的重跑结果。原批次的结果目录和运行记录没有移动。

| 分组 | 任务数 | env-error 有记录 | env-error 未提及 | task inventory 分类 | 我跑通情况 |
|---|---:|---:|---:|---|---|
| A：无网络依赖 | 15 | 0 | 15 | 3.1=8；3.2=1；3.3 B=6 | PASS 7；FAIL 7；NO_EVAL 1 |
| B：网络只读 | 30 | 13 | 17 | 3.1=12；3.2=4；3.3 A=8；3.3 B=1；4=5 | PASS 13；FAIL 8；NO_EVAL 9 |
| C-local：本地基础设施写 | 33 | 11 | 22 | 3.1=15；3.2=3；3.3 A=2；3.3 B=5；4=8 | PASS 16；FAIL 7；NO_EVAL 2；待填写 8 |
| C-remote：远端写 | 22 | 5 | 17 | 3.1=2；3.3 A=2；3.3 B=2；3.4=1；4=15 | PASS 4；FAIL 3；NO_EVAL 15 |
| C-notion：Notion 写 | 8 | 3 | 5 | 3.4=1；4=7 | NO_EVAL 6；待填写 2 |
| **合计** | **108** | **32** | **76** | **3.1=37；3.2=8；3.3 A=12；3.3 B=14；3.4=2；4=35** | **PASS 40；FAIL 25；NO_EVAL 33；待填写 10** |

> 文档一致性提示：`paper-checker` 同时出现在 task inventory 的 3.1 和 5.1，但第 242 行声称的“两者交集”清单漏掉了它；本表仍按两个原始清单记录，不擅自改写为 smoke test 成员。

## A：无网络依赖（15）

统计：env-error 有记录 0，未提及 15；task inventory：3.1=8；3.2=1；3.3 B=6；我跑通情况：PASS 7；FAIL 7；NO_EVAL 1。

| 任务 | BLOCK | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|---|
| `arrange-workspace` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>2 文件归错目录（`cv-gboeing.pdf` 与 `Internship_application_form.xlsx` 对调）；能力问题，非 infra |
| `cooking-guidance` | 0 | — | 3.2 不稳定：260821 PASS，260826 NO_EVAL<br>跨 5 批次：3 次有效评测均 PASS，另 2 次 NO_EVAL<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>现有食材覆盖率仅 25%，未达 ≥50% 硬约束；能力问题，非 infra |
| `courses-ta-hws` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `detect-revised-terms` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>法条期限"三个月内"误改"九十日内"，且多输出一行（幻觉性添加）；能力问题，非 infra |
| `dietary-health` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `excel-data-transformation` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `excel-market-research` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `imagenet` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>`survey.tex` 内容不符（表格数值幻改，agent 277 / gt 253 字符）；能力问题，非 infra |
| `interview-report` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>telechat 曾偶然 PASS；属极低通过率，并非完全不可跑<br>5.1 低外部依赖 | ✅ NO_EVAL（run glm-5.2/260903）<br>跑满 max_turns（100 turn/178 调用）未产出：前 ~70 轮耗在首个 docx，`recommend.txt` 未写；效率问题，非 infra |
| `paper-checker` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>唯一错误：交叉引用 `\autoref{tab:compute-cost}` 误写为 `tab:api-benchmarks`（`5_tradeoff.tex`）；能力问题，非 infra |
| `ppt-analysis` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 5/5 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `privacy-desensitization` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>over-masking：13/27 文件因掩盖清单外账号数字而不符（0 漏标，`/hidden/` 用对）；能力问题，非 infra |
| `reimbursement-form-filler` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `sales-accounting` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `university-course-selection` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>4 个排课方案各错 11 处，24 种排列全不匹配（约束求解系统性偏差）；能力问题，非 infra |

## B：网络只读（30）

统计：env-error 有记录 13，未提及 17；task inventory：3.1=12；3.2=4；3.3 A=8；3.3 B=1；4=5；我跑通情况：PASS 13；FAIL 8；NO_EVAL 9。

> NO_EVAL 根因（基于逐任务扫描 traj_log.json + run.log 的错误签名，非四层深核）：10 个 NO_EVAL **全部为 infra 主导，无一例指向模型能力**。
> - **Yahoo Finance 429 限流（6 个）**：`invoice-org`(226×)、`stock-build-position`(233×)、`travel-exchange`(229×)、`nvidia-market`(212×)、`yahoo-analysis`(204×)、`nvidia-stock-analysis`(94×)——agent 明确识别到限流并反复重试等待，直至耗尽 max_turns。
> - **Playwright 页面加载失败/超时（4 个）**：`trip-itinerary-generator`（根因实为 Google Maps「invalid API key」致 10/10 Maps 调用失败→回退 playwright；page.goto net::ERR_TIMED_OUT louvre.fr 为副产物）、`language-school`（178× 导航超时/ERR_CONNECTION_RESET）、`hk-top-conf`（ERR_NETWORK_CHANGED，iclr.cc）、`search-ca-school`（ERR_NETWORK_CHANGED，csrankings.org，另叠加 Google Maps「invalid API key」）。
> 均与 lwx-env-error / task inventory 记录的外部依赖问题一致。要彻底定性仍建议核对容器日志，但当前证据已足以判为 infra 阻塞而非能力问题。

| 任务 | BLOCK | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|---|
| `academic-pdf-report` | 0 | — | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ✅ PASS（run glm-5.2/260904） |
| `add-bibtex` | 0 | 🔴 必现：Playwright 页面加载 60s 超时 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ FAIL（run glm-5.2/260904）<br>57 条 bibtex 内容不符：作者列表截断为"and others"（应列全）、会议名缺限定词（"ICLR" vs "the ninth ICLR"）、标题大小写、缺 `journal` 字段、cite key 命名不一致（`roziere2023codellama` vs `roziere2023code`）；能力问题，非 infra |
| `course-schedule` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ FAIL（run glm-5.2/260904）<br>课程名漏合并：`算法分析与设计-01班` 应为 `算法分析与设计-01、02班`；能力问题，非 infra |
| `cvpr-research` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |
| `find-alita-paper` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 4/5 PASS | ✅ PASS（run glm-5.2/260904） |
| `git-milestone` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260904） |
| `git-repo` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260904） |
| `hk-top-conf` | 0 | 🟡 偶发：Prompt 超长 400 | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ✅ NO_EVAL（重跑 glm-5.2（已并入 results/glm-5.2））<br>agent 放弃预期 hover 方案、绕路逆向 papercopilot/GitHub 数据源，三会场分校计数已算出但耗尽 max_turns，未写 result.md/未 claim_done；能力/策略问题，非 infra（本次无网络故障，仅 2 次 terminal MCP 60s 超时） |
| `identify-all-songs` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |
| `invoice-org` | Yahoo Finance<br>原记录（Yahoo Finance 429）：本次记录中的服务／凭据阻塞 | 🔴 必现：Yahoo Finance API 429 限流 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 226 次 Yahoo Finance「Rate limited」429，与 env-error 记录一致 |
| `ipad-edu-price` | Yahoo Finance<br>任务配置声明 Yahoo Finance 工具；已跑通，保留依赖标签 | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ✅ PASS（run glm-5.2/260904） |
| `language-school` | 0 | 🔴 必现：Playwright 页面加载 60s 超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ✅ FAIL（重跑 glm-5.2（已并入 results/glm-5.2））<br>本次页面访问正常并产出结果；Toefl_min_score 填 95≠groundtruth 80（index 4 值不符）；内容/能力问题，非 infra（此前 NO_EVAL 的页面超时本次未复现） |
| `latex-prompt-box` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260904）<br>填充内容不符合任一可接受的 Simple Prompt 渲染格式（起始不匹配）；能力问题，非 infra |
| `logical-datasets-collection` | 0 | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ✅ FAIL（run glm-5.2/260904）<br>表格内容或格式与 groundtruth 不符（local check: Table content or format does not match）；能力问题，非 infra |
| `mrbeast-analysis` | 0 | 🔴 必现：Hugging Face 读取或 SSL 握手超时<br>🔴 必现：API Key 无效 | 3.2 不稳定：260821 PASS，260826 FAIL<br>文档判断多为环境抖动，重跑可能捞回 | ✅ FAIL（run glm-5.2/260904）<br>Detail_Lists 表 duration_seconds 单值不符（agent 924 / gt 1019），其余 (32,7) 结构一致；数据准确性/能力问题，非 infra（youtube MCP 仅首次 init 超时后恢复） |
| `nvidia-market` | Yahoo Finance<br>原记录（Yahoo Finance 429）：本次记录中的服务／凭据阻塞 | 🔴 必现：Yahoo Finance API 429 限流<br>🔴 必现：Playwright 页面加载 60s 超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 212 次 Yahoo Finance 429 限流，与 env-error 记录一致 |
| `nvidia-stock-analysis` | Yahoo Finance<br>原记录（Yahoo Finance 429）：本次记录中的服务／凭据阻塞 | 🔴 必现：Yahoo Finance API 429 限流<br>🔴 必现：Playwright 页面加载 60s 超时<br>🔴 必现：API Key 无效<br>🟡 偶发：MCP 工具执行错误 -32603<br>🟡 偶发：Python 依赖缺失或 ABI 不匹配 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 94 次 Yahoo Finance 429 限流，与 env-error 记录一致 |
| `profile-update-online` | 0 | 🔴 必现：Playwright 页面加载 60s 超时 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |
| `search-ca-school` | Google<br>原记录（Google）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Maps 地图（`google_map`）<br>凭据：API Key，`google_cloud_console_api_key` → `GOOGLE_MAPS_API_KEY`<br>使用阶段：agent 使用 Maps 查学校位置/驾车距离 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra/凭据：轨迹 56 次页面加载失败（net::ERR_NETWORK_CHANGED，csrankings.org）+ Google Maps geocoding「invalid API key」 |
| `shopping-helper` | 0 | 🔴 必现：Playwright 页面加载 60s 超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ✅ FAIL（run glm-5.2/260904）<br>评测器实时抓取 Amazon 成功，3 个商品提交价均与实时页价不符（364.63≠379.99；172.72≠180.0×2），0/3 通过；价格数据不符，非 infra |
| `stock-build-position` | Yahoo Finance<br>原记录（Yahoo Finance 429）：本次记录中的服务／凭据阻塞 | 🔴 必现：Yahoo Finance API 429 限流 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 233 次 Yahoo Finance 429 限流，与 env-error 记录一致 |
| `subway-planning` | Google<br>原记录（Google）：Google Maps API 尚未配置（人工标注） | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Maps 地图（`google_map`）<br>凭据：API Key，`google_cloud_console_api_key` → `GOOGLE_MAPS_API_KEY`<br>使用阶段：agent 可使用 Maps 查询地铁站/路线；已有网页替代完成记录不代表 API Key 有效 | 🟠 PASS（run glm-5.2/260904）<br>当前阻塞：Google Maps API 尚未配置（BLOCK=Google）；按当前配置记为“不通”<br>备注：agent 通过 playwright 抓取公开网页完成，未用上 Google Maps API（`google_cloud_console_api_key` 实为占位符 `"XX"`）；且任务只需 google_map/filesystem/playwright/fetch，不涉及 Google OAuth，原 inventory 的 OAuth-阻塞误挂已更正为 Maps API Key 依赖 |
| `travel-exchange` | Yahoo Finance<br>原记录（Yahoo Finance 429）：本次记录中的服务／凭据阻塞 | 🔴 必现：Yahoo Finance API 429 限流 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 229 次 Yahoo Finance「Too Many Requests」429，与 env-error 记录一致 |
| `trip-adviser` | Google<br>原记录（Google）：Google Maps API 尚未配置（人工标注） | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Maps 地图（`google_map`）<br>凭据：API Key，`google_cloud_console_api_key` → `GOOGLE_MAPS_API_KEY`<br>使用阶段：agent 可使用 Maps 查地点/路线；当前评测的 GoogleMapsMCPClient 为本地模拟实现，PASS 不证明真实 Maps API 可用 | 🟠 PASS（run glm-5.2/260904）<br>当前阻塞：Google Maps API 尚未配置（BLOCK=Google）；按当前配置记为“不通”<br>备注：agent 通过 playwright 抓取公开网页完成，未用上 Google Maps API（`google_cloud_console_api_key` 实为占位符 `"XX"`）；且任务只需 google_map/filesystem/playwright/fetch，不涉及 Google OAuth，原 inventory 的 OAuth-阻塞误挂已更正为 Maps API Key 依赖 |
| `trip-itinerary-generator` | Google<br>原记录（Google）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>**题目明确要求 Maps**：`task_config.needed_mcp_servers` = `[filesystem, google_map, playwright_with_chunk]`；题目需景点间最短步行距离 + 当日营业时间，正是 Maps 能力<br>Google 依赖：Maps 地图（`google_map`）<br>凭据：API Key，`google_cloud_console_api_key` → `GOOGLE_MAPS_API_KEY`<br>使用阶段：agent + 评测均使用 Maps；评测调用 maps_search_places / maps_place_details / maps_distance_matrix | 🟠 NO_EVAL（重跑 glm-5.2（已并入 results/glm-5.2））<br>跑满 max_turns 未产出结果<br>根因=infra/凭据：`google_map` 的 API Key 无效（`google_cloud_console_api_key` 为占位符 `"XX"`），10/10 Maps 调用（search_places/geocode/distance_matrix）均返回「The provided API key is invalid.」；agent 被迫改用 playwright 手动抓 Google Maps/官网（79 次）逐个读营业时间，耗尽预算、未写 Paris_Itinerary.json。page.goto 超时（louvre.fr 等）为回退副产物，非根因（原文档误标为 Playwright 页面超时，已更正） |
| `upenn-campus-route` | Google<br>原记录（Google）：评测器调用 Google Maps 失败；具体原因待核 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Maps 地图（`google_map`）<br>凭据：API Key，`google_cloud_console_api_key` → `GOOGLE_MAPS_API_KEY`<br>使用阶段：agent + 评测均使用 Maps；评测调用 maps_directions 取得步行时间 | ❌ FAIL（run glm-5.2/260904）<br>路线格式校验通过，但评测器获取步行时间的外部接口返回空（JSON decode error: line 1 col 0）→ "Failed to get walking time"，评测中断；根因=infra（评测侧外部地图接口），非模型能力 |
| `wandb-best-score` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260904） |
| `wandb-shortest-length` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260904） |
| `yahoo-analysis` | Yahoo Finance<br>原记录（Yahoo Finance 429）：本次记录中的服务／凭据阻塞 | 🔴 必现：Yahoo Finance API 429 限流 | 3.2 不稳定：260821 PASS，260826 FAIL<br>文档判断多为环境抖动，重跑可能捞回 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 204 次 Yahoo Finance 429 限流，与 env-error 记录一致 |
| `youtube-repo` | 0 | 🔴 必现：API Key 无效 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |

## C-local：本地基础设施写（33）

统计：env-error 有记录 11，未提及 22；task inventory：3.1=15；3.2=3；3.3 A=2；3.3 B=5；4=8；我跑通情况：PASS 16；FAIL 7；NO_EVAL 2；待填写 8。

> C-local 原批次执行画像（run glm-5.2/260905，25 个任务；保留历史记录，当前结果见逐任务表和上方统计）：
> - **9 PASS / 2 FAIL 是真进入了 agent+评测的结果**；`✅ FAIL` 两个均为能力问题（course-assistant 漏发 1 封学生邮件、sla-timeout-monitor 漏发经理提醒邮件），非 infra。
> - **9 个 NO_EVAL 是 preprocess 阶段本地容器未就绪**、未进入 agent：Canvas API `localhost:50001` 连接拒绝（5 个：canvas-new-students-notification / canvas-art-quiz / canvas-homework-grader-python / canvas-submit-late-work / canvas-list-test），WooCommerce `localhost:50003` SSL/连接失败（4 个：woocommerce-new-product / filter-low-selling-products / inventory-sync / woocommerce-update-cover）。→ 需先起稳这两组容器再重跑，与模型能力无关。
> - **5 个 NO_EVAL 是跑满 max_turns**（`pass=null`，`status.json` running=max_turn_exceeded）：canvas-arrange-exam / canvas-art-manager / canvas-do-quiz / k8s-pr-preview-testing / k8s-redis-helm-upgrade。归档重跑后，其中 canvas-art-manager 本轮 PASS、canvas-arrange-exam / canvas-do-quiz 本轮进入评测（FAIL，能力问题）；仅两个 k8s 任务仍 max_turns。
> - **两个 k8s max_turns 已一手核实为 agent 能力/策略问题，非 infra**（此前"偏 infra/未核验"结论更正）；按本表口径记为 `✅ NO_EVAL`，STATUS 为“跑通”，保留未产出评测的结果：
>   - `k8s-pr-preview-testing`：环境可用（Deployment Running、pod 内 curl 正常、Playwright 能加载页面）。死因=①无视 README 要求的 NodePort:30123（评测器从宿主机查），死磕 port-forward（Connection reset×14/refused×8），workspace 的 `service.yaml` 至今仍是 `type: ClusterIP`；②用 Playwright MCP 逐个用例手动复现测试（~45 turn），本可一次跑测试脚本；③`rm -rf SimpleShopping` 误删仓库重 clone；④必交付的 `filled-test-results-report.md` 未生成。MCP -32603 仅 1 次且为自身 namespace 传参错误，可自修。
>   - `k8s-redis-helm-upgrade`：ImagePullBackOff 真实出现 44 次但**无任何 registry 5xx/TLS/timeout 签名**——历史"Docker Registry 5xx 环境故障"定性错误。该 ImagePullBackOff 是任务设计障碍（bitnami→bitnamilegacy 镜像迁移），preprocess 已预加载 `bitnamilegacy/*`（tag `7.2.4-debian-12-r9`）进 kind，正确解离线可达。agent 甚至最终拼对了 override（`image.repository=bitnamilegacy/redis`+`image.tag=7.2.4-debian-12-r9`+`allowInsecureImages=true`+各子镜像），但被 207 处犹豫独白空耗，撞 100 turn 上限前没跑完 upgrade。纯粹决策瘫痪/预算耗尽。

| 任务 | BLOCK | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|---|
| `apply-phd-email` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260905） |
| `canvas-arrange-exam` | 0 | 🟡 偶发：IMAP 认证失败 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ FAIL（run glm-5.2/260907）<br>`exam_schedule.xlsx` 多排 1 门：ENG101（入学考 ≥95 免考）不应列入，agent 10 行 / gt 9 行，9/10 完美匹配（90%）；能力问题，非 infra |
| `canvas-art-manager` | 0 | 🟡 偶发：IMAP 认证失败<br>🟡 偶发：DNS 解析失败<br>🟡 偶发：MCP 工具执行错误 -32603<br>🟡 偶发：网络连接拒绝或中断 | 3.3 B 从未通过：模型能力/任务难度为主 | ✅ PASS（run glm-5.2/260907）<br>此前 260905 因 max_turns NO_EVAL；本轮归档重跑后正常评测通过 |
| `canvas-art-quiz` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 4/5 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260907） |
| `canvas-do-quiz` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖<br>第 6 节冲突约束：不可与 `canvas-submit-late-work` 并发 | ✅ FAIL（run glm-5.2/260907）<br>14 个 quiz 中 13 个满分、漏 1 个未达满分（`Student did not achieve full score on all quizzes 13/14`）；能力问题，非 infra |
| `canvas-homework-grader-python` | 0 | 🟡 偶发：IMAP 认证失败 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 4/5 PASS | ✅ PASS（run glm-5.2/260907） |
| `canvas-list-test` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260907）<br>`quiz_info.csv` 行数不符：agent 10 行 / groundtruth 13 行（列完整、`assignment_info.csv` 完全匹配）；能力问题，非 infra |
| `canvas-new-students-notification` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖 | ✅ PASS（run glm-5.2/260907） |
| `canvas-submit-late-work` | 0 | 🟡 偶发：IMAP 认证失败<br>🟡 偶发：SMTP 发送失败 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>第 6 节冲突约束：不可与 `canvas-do-quiz` 并发 | ✅ PASS（run glm-5.2/260907） |
| `course-assistant` | 0 | 🟡 偶发：IMAP 认证失败 | 3.3 B 从未通过：模型能力/任务难度为主 | ✅ FAIL（run glm-5.2/260905）<br>学生 Michelle Brooks（michelle_brooks26@mcp.com）未收到主题 'nlp-course-emergency' 的通知邮件；其余正例学生与全部负例账户校验均通过；能力问题，非 infra |
| `email-paper-homepage` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260905） |
| `filter-low-selling-products` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ FAIL（run glm-5.2/260907）<br>5 个低销商品仅 1 个移入 Outlet/Clearance，漏移 4 个（Charger v11、Old Sneakers 2022、Tablet Case、Bluetooth Headphone）；能力问题，非 infra |
| `git-bug-hunt` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 4/5 PASS | ✅ PASS（run glm-5.2/260905） |
| `inventory-sync` | 0 | 🟡 偶发：Prompt 超长 400 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260907） |
| `k8s-deployment-cleanup` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260905） |
| `k8s-mysql` | 0 | 🟡 偶发：MCP 工具执行错误 -32603 | 3.2 不稳定：260821 PASS，260826 FAIL<br>文档判断多为环境抖动，重跑可能捞回 | ✅ PASS（run glm-5.2/260905） |
| `k8s-pr-preview-testing` | 0 | 🟡 偶发：MCP 工具执行错误 -32603 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ NO_EVAL（run glm-5.2/260907，归档重跑）<br>跑满 max_turns，**一手核实=agent 策略问题非 infra**：环境可用；死磕 port-forward 未改 NodePort:30123（service.yaml 仍 ClusterIP，Connection reset×14）＋用 Playwright 逐用例手动复现耗光 turn＋误删仓库＋未产出 filled-test-results-report.md。MCP -32603 仅 1 次为自身传参错误可自修 |
| `k8s-redis-helm-upgrade` | 0 | 🟡 偶发：MCP 工具执行错误 -32603<br>🟡 偶发：Docker Registry 5xx / ImagePullBackOff<br>🟡 偶发：网络连接拒绝或中断 | 3.3 A 从未通过：环境/凭据问题为主<br>Docker Registry 5xx / ImagePullBackOff | ✅ NO_EVAL（run glm-5.2/260907，归档重跑）<br>跑满 max_turns，**一手核实=agent 决策瘫痪非 infra**：ImagePullBackOff 真实 44 次但无 registry 5xx/TLS/timeout 签名（历史"Registry 5xx 故障"定性更正）；这是任务设计障碍（bitnami→bitnamilegacy 迁移），preprocess 已预加载 bitnamilegacy/redis:7.2.4-debian-12-r9，正确解离线可达。agent 最终拼对 override（bitnamilegacy+tag 7.2.4+allowInsecureImages）却被 207 处犹豫独白空耗 turn，撞上限前没跑完 |
| `k8s-safety-audit` | Google<br>原记录（Google）：Google 依赖配置待核；个人尚未实跑，未确认凭据缺失 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定<br>Google 配置待核：个人尚未实跑 | ⬜ 待填写 |
| `landing-task-reminder` | 0 | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ✅ PASS（run glm-5.2/260905） |
| `meeting-assign` | 0 | 🟡 偶发：IMAP 认证失败<br>🟡 偶发：SMTP 发送失败 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260905） |
| `payable-invoice-checker` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260905） |
| `set-conf-cr-ddl` | Google<br>原记录（Google）：Google 依赖配置待核；个人尚未实跑，未确认凭据缺失 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Calendar 日历（`google_calendar`）<br>凭据：OAuth；运行环境 `~/.calendar-mcp/gcp-oauth.keys.json` + `~/.calendar-mcp/credentials.json`<br>使用阶段：预处理清理/初始化日程，agent 创建日程，评测查询日程；需 Calendar 读写权限<br>Google 配置待核：个人尚未实跑<br>第 6 节冲突约束：不可与 `student-interview` 并发 | ⬜ 待填写 |
| `sla-timeout-monitor` | 0 | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ✅ FAIL（run glm-5.2/260905）<br>9 封客户道歉邮件与 6 个负例账户校验全部正确，但漏发经理提醒邮件：dhall@mcp.com（4 张工单）未收到 manager reminder；能力问题，非 infra |
| `student-interview` | Google<br>原记录（Google）：Google 依赖配置待核；个人尚未实跑，未确认凭据缺失 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Calendar 日历（`google_calendar`）<br>凭据：OAuth；运行环境 `~/.calendar-mcp/gcp-oauth.keys.json` + `~/.calendar-mcp/credentials.json`<br>使用阶段：预处理清理/初始化日程，agent 创建日程，评测查询日程；需 Calendar 读写权限<br>Google 配置待核：个人尚未实跑<br>第 6 节冲突约束：不可与 `set-conf-cr-ddl` 并发 | ⬜ 待填写 |
| `travel-expense-reimbursement` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主 | ✅ PASS（run glm-5.2/260905） |
| `update-material-inventory` | Google<br>原记录（Google）：Google 依赖配置待核；个人尚未实跑，未确认凭据缺失 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定<br>Google 配置待核：个人尚未实跑 | ⬜ 待填写 |
| `woocommerce-customer-survey` | Google<br>原记录（Google）：Google 依赖配置待核；个人尚未实跑，未确认凭据缺失 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Forms 表单 + Drive 文件管理（`google_forms`）<br>凭据：OAuth `configs/google_credentials.json`；MCP 使用 `google_client_id` / `google_client_secret` / `google_refresh_token`<br>使用阶段：预处理通过 Drive 清理表单，agent 创建表单，评测读取表单；需 Forms/Drive 权限<br>Google 配置待核：个人尚未实跑<br>第 6 节冲突约束：不可与 `woocommerce-product-recall` 并发 | ⬜ 待填写 |
| `woocommerce-new-product` | 0 | 🟡 偶发：IMAP 认证失败<br>🟡 偶发：SMTP 发送失败<br>🟡 偶发：网络连接拒绝或中断 | 3.3 A 从未通过：环境/凭据问题为主<br>IMAP/SMTP 抖动或连接拒绝 | ✅ FAIL（run glm-5.2/260907）<br>商品检测正常（3 新品+4 促销品），但折扣邮件 0/40 未发（要求给全部 40 客户各发 1 封）；agent 漏做群发邮件动作，非 infra |
| `woocommerce-new-welcome` | Google<br>原记录（Google）：Google 依赖配置待核；个人尚未实跑，未确认凭据缺失 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：BigQuery 数据集 `woocommerce_crm`（`google-cloud`）<br>凭据：服务账号 `configs/gcp-service_account.keys.json` + `gcp_project_id` / `gcp_service_account_path`<br>使用阶段：预处理准备云端数据，agent 经 MCP 访问，评测读取云端结果<br>Google 配置待核：个人尚未实跑 | ⬜ 待填写 |
| `woocommerce-product-recall` | Google<br>原记录（Google）：Google 依赖配置待核；个人尚未实跑，未确认凭据缺失 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Forms 表单 + Drive 文件管理（`google_forms`）<br>凭据：OAuth `configs/google_credentials.json`；MCP 使用 `google_client_id` / `google_client_secret` / `google_refresh_token`<br>使用阶段：预处理通过 Drive 清理表单，agent 创建表单，评测读取表单；需 Forms/Drive 权限<br>Google 配置待核：个人尚未实跑<br>第 6 节冲突约束：不可与 `woocommerce-customer-survey` 并发 | ⬜ 待填写 |
| `woocommerce-stock-alert` | Google<br>原记录（Google）：Google 依赖配置待核；个人尚未实跑，未确认凭据缺失 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定<br>Google 配置待核：个人尚未实跑 | ⬜ 待填写 |
| `woocommerce-update-cover` | 0 | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260907） |

## C-remote：远端写（22）

统计：env-error 有记录 5，未提及 17；task inventory：3.1=2；3.3 A=2；3.3 B=2；3.4=1；4=15；我跑通情况：PASS 4；FAIL 3；NO_EVAL 15。

> 原 C-remote 批次画像（拆分前 28 个任务，保留历史来源口径）：**只有 7 个真正进入 agent 执行**（过了 preprocess），其余 **21 个在 preprocess 阶段直接失败/卡住**，从未运行模型。
> - **PASS 3**：`dataset-license-issue`、`sync-todo-to-readme`、`verl-dataset`。
> - **FAIL 3（均能力问题，非 infra）**：`huggingface-upload`（漏传 figures/*.png）、`merge-hf-datasets`（工具参数类型字符串截断）、`personal-website-construct`（about.md 缺 “PhD candidate”）。
> - **NO_EVAL 22（全部 infra/配置，非模型能力）**：其中 21 个为 preprocess 失败 + 1 个（`train-ticket-plan`）agent 启动时 MCP 仅连上 3/4（rail_12306 未连）。preprocess 失败按签名归类：缺 GCP 服务账号密钥 `configs/gcp-service_account.keys.json`（7 个）、缺 Notion `files/duplicated_page_id.txt`（4 个）、Google Sheets/Drive 凭据缺 `token`（`KeyError 'token'`，7 个）、Google OAuth 缺字段（`fillout-online-forms`）、generic returncode 1（`investment-decision-analysis`）、preprocess 卡住未完成（`notion-personal-website`）。
> Google 相关任务需分别补齐服务账号或 OAuth 用户凭据后重跑预处理；其他配置错误和卡住原因仍需逐项排查，不能由补齐一个凭据文件推断这 21 个任务全部恢复。
>
> 注意：`results/glm-5.2/` 现为合并后的总目录，含 A 组（260903）+ B 组（260904）+ C-remote（260904）+ 4 个任务重跑（train-ticket-plan/hk-top-conf/language-school/trip-itinerary-generator，重跑版已覆盖旧版，旧版备份在 `_superseded_by_debug_rerun/`），共 73 个任务；`eval_stats.json` 已按 73 任务重算（24 pass / 18 fail / 31 null）。脚本尾部聚合为全 73 任务混合值；这段为历史批次汇总；当前表格已将其中 6 个任务移入 C-notion，当前分组数字按下方逐任务记录重算。

| 任务 | BLOCK | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|---|
| `ab-testing` | Google<br>原记录（Google）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：BigQuery 数据集 `ab_testing` + Storage 桶 `promo-assets-for-b*` + Logging 日志桶（`google-cloud`）<br>凭据：服务账号 `configs/gcp-service_account.keys.json` + `gcp_project_id` / `gcp_service_account_path`<br>使用阶段：预处理准备云端数据，agent 经 MCP 访问，评测读取云端结果 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺凭据文件 `configs/gcp-service_account.keys.json`（GCP 服务账号密钥）；根因=infra |
| `academic-warning` | Google<br>原记录（Google）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：BigQuery 数据集 `academic_warning` + Logging 日志桶（`google-cloud`）<br>凭据：服务账号 `configs/gcp-service_account.keys.json` + `gcp_project_id` / `gcp_service_account_path`<br>使用阶段：预处理准备云端数据，agent 经 MCP 访问，评测读取云端结果 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `dataset-license-issue` | 0 | — | 3.4 无有效评测产出：5 批次均 NO_EVAL<br>第 6 节冲突约束：不可与 `huggingface-upload` 并发 | ✅ PASS（run glm-5.2/260904） |
| `fillout-online-forms` | Google<br>Google Forms/Drive 用于预处理和评测（agent 未声明 Google MCP）；本次 Google 凭据问题见实跑记录 | 🔴 必现：Google OAuth credentials 缺字段 | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Forms 表单 + Drive 文件管理（未声明 Google MCP）<br>凭据：OAuth `configs/google_credentials.json`；需 Forms/Drive 权限<br>使用阶段：预处理创建表单、评测读取表单/回答；agent 通过浏览器填写<br>历史已知错误：OAuth 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：Google OAuth 授权信息缺字段 client_id/client_secret；根因=infra/凭据 |
| `flagged-transactions` | Google<br>原记录（Google）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：BigQuery 数据集 `all_transactions`（`google-cloud`）<br>凭据：服务账号 `configs/gcp-service_account.keys.json` + `gcp_project_id` / `gcp_service_account_path`<br>使用阶段：预处理准备云端数据，agent 经 MCP 访问 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `game-statistics` | Google<br>原记录（Google）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：BigQuery 数据集 `game_analytics`（`google-cloud`）<br>凭据：服务账号 `configs/gcp-service_account.keys.json` + `gcp_project_id` / `gcp_service_account_path`<br>使用阶段：预处理准备云端数据，agent 经 MCP 访问，评测读取云端结果 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `gdp-cr5-analysis` | Google<br>原记录（Google）：Google 凭据缺 token；已核对预处理代码 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：Google Sheets/Drive 凭据缺 `token`（KeyError；代码直接读取该字段）；根因=infra |
| `huggingface-upload` | 0 | 🟡 偶发：Python 依赖缺失或 ABI 不匹配 | 3.3 A 从未通过：环境/凭据问题为主<br>Hugging Face 客户端 read timeout 10/15s<br>第 6 节冲突约束：不可与 `dataset-license-issue` 并发 | ✅ FAIL（run glm-5.2/260904）<br>仓库已建、README/config.json/pytorch_model.bin 均匹配，但漏传 figures/fig1–3.png；能力问题，非 infra |
| `inter-final-performance-analysis` | Google<br>原记录（Google）：Google 凭据缺 token；已核对预处理代码 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：Google Sheets/Drive 凭据缺 `token`（KeyError；代码直接读取该字段）；根因=infra |
| `investment-decision-analysis` | Yahoo Finance;Google<br>Yahoo 获取行情，Google Sheets/Drive 读写；本次预处理仅记录 returncode 1，具体失败原因待核 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败（returncode 1）；根因=infra |
| `live-transactions` | Google<br>原记录（Google）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：BigQuery 数据集 `transactions_analytics` + Storage 桶 + Logging 日志桶（`google-cloud`）<br>凭据：服务账号 `configs/gcp-service_account.keys.json` + `gcp_project_id` / `gcp_service_account_path`<br>使用阶段：预处理准备云端数据，agent 经 MCP 访问，评测读取云端结果 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `llm-training-dataset` | Google<br>原记录（Google）：Google 凭据缺 token；已核对预处理代码 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：Google Sheets/Drive 凭据缺 `token`（KeyError；代码直接读取该字段）；根因=infra |
| `machine-operating` | Google<br>原记录（Google）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：BigQuery 数据集 `machine_operating` + Storage 桶（`google-cloud`）<br>凭据：服务账号 `configs/gcp-service_account.keys.json` + `gcp_project_id` / `gcp_service_account_path`<br>使用阶段：预处理准备云端数据，agent 经 MCP 访问，评测读取云端结果 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `merge-hf-datasets` | 0 | 🔴 必现：Hugging Face 读取或 SSL 握手超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Hugging Face 客户端 read timeout 10/15s | ✅ FAIL（run glm-5.2/260904）<br>xlam_18 工具参数类型字符串被截断（`List[Union[int, float]]` 输出成 `List[Union[int`）；能力问题，非 infra |
| `music-analysis` | Google<br>原记录（Google）：Google 凭据缺 token；已核对预处理代码 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：Google Sheets/Drive 凭据缺 `token`（KeyError；代码直接读取该字段）；根因=infra |
| `nhl-b2b-analysis` | Google<br>原记录（Google）：Google 凭据缺 token；已核对预处理代码 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：Google Sheets/Drive 凭据缺 `token`（KeyError；代码直接读取该字段）；根因=infra |
| `personal-website-construct` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260904）<br>远端 about.md 缺必需信息 “PhD candidate”；能力问题，非 infra |
| `price-comparison` | Google<br>原记录（Google）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：BigQuery 数据集 `bigquery_pricing_analysis`（`google-cloud`）<br>凭据：服务账号 `configs/gcp-service_account.keys.json` + `gcp_project_id` / `gcp_service_account_path`<br>使用阶段：预处理准备云端数据，agent 经 MCP 访问，评测读取云端结果<br>预处理缺服务账号时回退 ADC；需单独核对默认凭据<br>另有 466 个派生变体全部 NO_EVAL，需排查 GCP 凭据及预处理/评测流程 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：GCP 默认凭据缺失（DefaultCredentialsError）；根因=infra |
| `sync-todo-to-readme` | 0 | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ PASS（run glm-5.2/260904） |
| `train-ticket-plan` | 0 | 🟡 偶发：MCP server 启动超时（rail_12306） | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（重跑 glm-5.2（已并入 results/glm-5.2））<br>本次 rail_12306 MCP 连接正常，preprocess/agent/评测全通过（上次 NO_EVAL 因 MCP 仅连 3/4，属 infra 抖动，重跑捞回） |
| `verl-dataset` | 0 | 🔴 必现：Hugging Face 读取或 SSL 握手超时 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |
| `vlm-history-completer` | Google<br>原记录（Google）：Google 凭据缺 token；已核对预处理代码 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Sheets 表格 + Drive 文件夹（`google_sheet`）<br>凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>使用阶段：预处理准备文件夹/表格，agent 经 MCP 读写，评测读取结果；`google_sheets_folder_id` 由任务配置指定 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：Google Sheets/Drive 凭据缺 `token`（KeyError；代码直接读取该字段）；根因=infra |

## C-notion：Notion 写（8）

统计：env-error 有记录 3，未提及 5；task inventory：3.4=1；4=7；我跑通情况：PASS 3；FAIL 1；NO_EVAL 3；待填写 1。

原 C-local 的 `notion-find-job`、`notion-hr` 与原 C-remote 的其余 6 个任务已移入本组，逐任务描述和个人结果保持原记录。

**2026-09-08 更新（Notion 复制链路根因已解决）**：本组历史上大面积 NO_EVAL 的直接签名是 preprocess 缺 `files/duplicated_page_id.txt`，此前归因于 `notion_official` refresh lock 争用；实测证明**真实根因是无头浏览器登录态失效**，与 refresh lock 无关。定位过程：将 `configs/global_configs.py` 的 `notion_preprocess_with_playwright` 置为 `True`（匹配仓库的无头登录方式，走 playwright 而非 OAuth/mcp-remote 路径）后，REST 阶段全部通过，失败后移到浏览器自动化；此时导航后 URL 带 `?session_sync_attempted=1`，且顶栏 “More” 菜单选择器 90s 不可见——即容器内浏览器会话并未真正登录。重新生成 `configs/notion_state.json`（39 cookie / 3 origin，`token_v2`、`notion_user_id` 位于 `.app.notion.com` 域）后，`?session_sync_attempted=1` 消失，页面复制一次成功。

据此于 260908 用 glm-5.2 重跑 `experiments-recordings`、`notion-hr`、`notion-movies`、`notion-personal-website`、`task-tracker`（workers=5，任务列表 `configs/task_lists/finalpool/tmp-notion-five.txt`）：**preprocess 5/5 全通**，5 个 playwright 会话并发复制无相互干扰。结果 3 PASS / 1 FAIL / 1 NO_EVAL，且剩余 2 个的失败已全部转为能力问题，本组不再有 Notion 侧 infra 阻塞。`oil-price` 同日单跑亦证实 preprocess 通过（其 TIMEOUT 另有原因，见该行）。

只有 `notion-find-job`、`notion-hr` 需要 Poste；它们仍与 C-local 共享邮件服务。部署和并发说明见 [Notion 评测](notion-evaluation.md)。

| 任务 | BLOCK | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|---|
| `experiments-recordings` | Notion<br>原记录（Notion）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | ✅ FAIL（重跑 glm-5.2/260908）<br>preprocess 已通过（重做 Notion 无头登录后修复，见本节说明）；agent 31 步正常收尾，评测判 `pass=false`：产出表格与标准答案不符；根因=能力，非 infra<br>（上次 260904 为 🟠 NO_EVAL：preprocess 失败缺 `files/duplicated_page_id.txt`） |
| `notion-find-job` | Google;Notion<br>Google Maps 查地点/路线，Notion 页面读写；个人尚未实跑，配置待核 | — | 第 4 节未验证：无历史实跑记录<br>Google 依赖：Maps 地图（`google_map`）<br>凭据：API Key，`google_cloud_console_api_key` → `GOOGLE_MAPS_API_KEY`<br>使用阶段：agent 使用 Maps 查地点/路线；另有 Notion 依赖<br>Google 配置待核：个人尚未实跑 | ⬜ 待填写 |
| `notion-hr` | Notion<br>原记录（Notion）：历史已知阻塞；个人尚未实跑 | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | ✅ PASS（run glm-5.2/260908）<br>preprocess/agent/评测全通（首次实跑；重做 Notion 无头登录后 preprocess 一次通过） |
| `notion-movies` | Notion<br>原记录（Notion）：本次记录中的服务／凭据阻塞 | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | ✅ PASS（重跑 glm-5.2/260908）<br>重做 Notion 无头登录后 preprocess 通过，agent/评测全通（上次 260904 为 🟠 NO_EVAL：缺 `files/duplicated_page_id.txt`，属 infra，重跑捞回） |
| `notion-personal-website` | Notion<br>原记录（Notion）：Notion 预处理卡住；具体原因待核 | 🟡 偶发：preprocess 阶段卡死 | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | ✅ PASS（重跑 glm-5.2/260908）<br>重做 Notion 无头登录后 preprocess 通过，agent/评测全通（上次 260904 为 🟠 NO_EVAL：preprocess 卡住未完成，属 infra，重跑捞回） |
| `oil-price` | Yahoo Finance;Notion<br>Yahoo 获取行情，Notion 页面读写；本次预处理缺 duplicated_page_id.txt，后续 Yahoo 尚未验证 | 🟡 偶发：Notion refresh lock 争用（含疑似间接影响） | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用<br>历史环境曾出现 preprocess fail | 🟠 NO_EVAL（重跑 glm-5.2/260908）<br>Notion 侧已修复：重做无头登录后 preprocess 通过，`duplicated_page_id.txt` 正常生成；阻塞点转为 **Yahoo Finance 限流**<br>agent 跑满 5400s TIMEOUT：`yahoo_finance_get_historical_stock_prices` 调用 50 次，52 条返回 `Too Many Requests. Rate limited.`，自 turn 2 起即被限流；agent 用 45 次 `time.sleep(~115s)` 重试（≈86 分钟纯等待）耗尽时间预算<br>根因=上游 Yahoo 对本机 IP 限流（无认证公开接口），非本仓库 infra；需换出口 IP／避开限流窗口后才能验证 Yahoo 部分<br>（上次 260904 为 🟠 NO_EVAL：preprocess 失败缺 `files/duplicated_page_id.txt`） |
| `quantitative-financial-analysis` | Yahoo Finance;Google;Notion<br>Yahoo 获取行情；Google Sheets/Drive 与 Notion 读写；本次失败在 Google 凭据缺 token，尚未进入 Notion 初始化，Yahoo 与 Notion 待验证 | — | 第 4 节未验证：无历史实跑记录<br>依赖：Yahoo Finance 行情 + Google Sheets/Drive + Notion（`Quant Research` 页面）<br>Google 凭据：OAuth `configs/google_credentials.json`；需 Sheets/Drive 权限，预处理直接读取 token 等 6 个字段（见认证说明）<br>Notion 配置：integration key、源/评测父页面，以及 `configs/.mcp-auth` 中供 `notion_official` 复制页面使用的 OAuth 授权<br>使用阶段：预处理先准备 Drive 文件夹，再清理/复制 Notion 页面；agent 写行情表格，并在 Notion 写入表格链接和指定评论；评测检查两边结果；`google_sheets_folder_id` 由任务配置指定<br>本次记录失败在 Google 初始化阶段，尚未执行 Notion 初始化；修好 Google 凭据后仍需验证 Notion；不依赖 Poste | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：Google Sheets/Drive 凭据缺 `token`（KeyError；代码直接读取该字段）；根因=infra |
| `task-tracker` | Notion<br>原记录（Notion）：本次记录中的服务／凭据阻塞 | 🟡 偶发：preprocess 阶段卡死<br>🟡 偶发：Notion refresh lock 争用（含疑似间接影响） | 3.4 无有效评测产出：5 批次均 NO_EVAL；preprocess 持续卡死，疑似 Notion refresh lock | ✅ NO_EVAL（重跑 glm-5.2/260908）<br>preprocess 已通过（重做 Notion 无头登录后修复），失败点已从 infra 转为能力：agent 跑满 100 步 `max_turn_exceeded`，评测未执行（`pass=null`）<br>478 次工具调用中 371 次为逐文件 `github_get_file_contents`（351 个不同路径，占 78%，吃掉 turn 2–73），turn 57–100 又逐个 `github_push_files`，在推最后一批时被切断<br>已核对 GitHub 侧**无限流**：全量输出扫 `rate limit`/`Too Many Requests`/`X-RateLimit`/`retry-after` 均 0 命中，`429` 的 12 次匹配全是 git SHA 误报；真实报错仅 2 条（含 1 条本地 python `json.load`）<br>根因=能力/步数预算，非 infra；建议提高 `MAX_STEPS` 后重跑 |
