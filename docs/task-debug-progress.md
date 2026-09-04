# finalpool task debug 进展跟踪

- 初始化日期：2026-09-04
- 分组来源：[finalpool 四组 task list](../configs/task_lists/finalpool/)
- 环境错误来源：[lwx-env-error.md](lwx-env-error.md)：仅覆盖 260812 GLM-5.1 两个批次，并只统计从工具消息提取到的环境错误；本表中的“—”表示该文档未点名，不代表已证明没有环境问题。
- 可跑性来源：[task-inventory-and-runnability.md](task-inventory-and-runnability.md)：3.1–4 节为历史评测分类，不能代替本次个人实跑。
- “我跑通情况”是独立人工进度列。当前未提供可唯一对应的个人运行结果目录，因此初始化为“⬜ 待填写”。建议填写为“✅ PASS（run/日期）”“❌ FAIL（错误摘要）”或“🚧 BLOCKED（阻塞项）”。
- 个人实跑来源：A 组 15 个任务已按 GLM-5.2 实跑结果填写（run glm-5.2/260903，结果目录 [results/glm-5.2/](../results/glm-5.2/)，分析见 [ANALYSIS_glm-5.2.md](../results/glm-5.2/ANALYSIS_glm-5.2.md)）。B 组 30 个任务已按 GLM-5.2 实跑结果填写（run glm-5.2/260904，dump 目录 [parallel_debug_glm52_bnet/](../parallel_debug_glm52_bnet/)，并发 4；PASS 13/FAIL 7/NO_EVAL 10，尚未做逐项四层核验）。`🟠 NO_EVAL` 表示跑满 max_turns 未产出可判定结果。C-remote 组 28 个任务已按 GLM-5.2 实跑结果填写（run glm-5.2/260904，dump 到 [results/glm-5.2/](../results/glm-5.2/)，并发 8；PASS 3/FAIL 3/NO_EVAL 22，其中 21 个为 preprocess 阶段失败/卡住、未进入 agent 执行）。C-local 组尚未个人实跑，保持“⬜ 待填写”。

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
| A：无网络依赖 | 15 | 0 | 15 | 3.1=8；3.2=1；3.3 B=6 | PASS 7；FAIL 7；NO_EVAL 1 |
| B：网络只读 | 30 | 13 | 17 | 3.1=12；3.2=4；3.3 A=8；3.3 B=1；4=5 | PASS 13；FAIL 7；NO_EVAL 10 |
| C-local：本地基础设施写 | 35 | 11 | 24 | 3.1=15；3.2=3；3.3 A=2；3.3 B=5；4=10 | 待填写=35 |
| C-remote：远端写 | 28 | 8 | 20 | 3.1=2；3.3 A=2；3.3 B=2；3.4=2；4=20 | PASS 3；FAIL 3；NO_EVAL 22 |
| **合计** | **108** | **32** | **76** | **3.1=37；3.2=8；3.3 A=12；3.3 B=14；3.4=2；4=35** | **PASS 23；FAIL 17；NO_EVAL 33；待填写 35** |

> 文档一致性提示：`paper-checker` 同时出现在 task inventory 的 3.1 和 5.1，但第 242 行声称的“两者交集”清单漏掉了它；本表仍按两个原始清单记录，不擅自改写为 smoke test 成员。

## A：无网络依赖（15）

统计：env-error 有记录 0，未提及 15；task inventory：3.1=8；3.2=1；3.3 B=6；我跑通情况：✅ PASS 7、❌ FAIL 7、🟠 NO_EVAL 1（run glm-5.2/260903，源自 [ANALYSIS_glm-5.2.md](../results/glm-5.2/ANALYSIS_glm-5.2.md)）。经四层核验（preprocess 15/15、无容器崩溃、无 API/网络错误、所需工具均成功返回真实数据），**8 项失败/未完成全部为 agent 能力或效率问题，无 infra 问题**。

| 任务 | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|
| `arrange-workspace` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>2 文件归错目录（`cv-gboeing.pdf` 与 `Internship_application_form.xlsx` 对调）；能力问题，非 infra |
| `cooking-guidance` | — | 3.2 不稳定：260821 PASS，260826 NO_EVAL<br>跨 5 批次：3 次有效评测均 PASS，另 2 次 NO_EVAL<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>现有食材覆盖率仅 25%，未达 ≥50% 硬约束；能力问题，非 infra |
| `courses-ta-hws` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `detect-revised-terms` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>法条期限"三个月内"误改"九十日内"，且多输出一行（幻觉性添加）；能力问题，非 infra |
| `dietary-health` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `excel-data-transformation` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `excel-market-research` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `imagenet` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>`survey.tex` 内容不符（表格数值幻改，agent 277 / gt 253 字符）；能力问题，非 infra |
| `interview-report` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>telechat 曾偶然 PASS；属极低通过率，并非完全不可跑<br>5.1 低外部依赖 | ✅ NO_EVAL（run glm-5.2/260903）<br>跑满 max_turns（100 turn/178 调用）未产出：前 ~70 轮耗在首个 docx，`recommend.txt` 未写；效率问题，非 infra |
| `paper-checker` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>唯一错误：交叉引用 `\autoref{tab:compute-cost}` 误写为 `tab:api-benchmarks`（`5_tradeoff.tex`）；能力问题，非 infra |
| `ppt-analysis` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 5/5 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `privacy-desensitization` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>over-masking：13/27 文件因掩盖清单外账号数字而不符（0 漏标，`/hidden/` 用对）；能力问题，非 infra |
| `reimbursement-form-filler` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `sales-accounting` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260903） |
| `university-course-selection` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260903）<br>4 个排课方案各错 11 处，24 种排列全不匹配（约束求解系统性偏差）；能力问题，非 infra |

## B：网络只读（30）

统计：env-error 有记录 13，未提及 17；task inventory：3.1=12；3.2=4；3.3 A=8；3.3 B=1；4=5；我跑通情况：✅ PASS 13、❌ FAIL 7、🟠 NO_EVAL 10（run glm-5.2/260904，dump 目录 [parallel_debug_glm52_bnet/](../parallel_debug_glm52_bnet/)，并发 4、单任务超时 5400s，全部 30/30 完成，无 preprocess/容器失败与超时）。`🟠 NO_EVAL` 表示跑满 max_turns 未产出可判定结果（`pass=null`）。

> NO_EVAL 根因（基于逐任务扫描 traj_log.json + run.log 的错误签名，非四层深核）：10 个 NO_EVAL **全部为 infra 主导，无一例指向模型能力**。
> - **Yahoo Finance 429 限流（6 个）**：`invoice-org`(226×)、`stock-build-position`(233×)、`travel-exchange`(229×)、`nvidia-market`(212×)、`yahoo-analysis`(204×)、`nvidia-stock-analysis`(94×)——agent 明确识别到限流并反复重试等待，直至耗尽 max_turns。
> - **Playwright 页面加载失败/超时（4 个）**：`trip-itinerary-generator`（page.goto net::ERR_TIMED_OUT，louvre.fr）、`language-school`（178× 导航超时/ERR_CONNECTION_RESET）、`hk-top-conf`（ERR_NETWORK_CHANGED，iclr.cc）、`search-ca-school`（ERR_NETWORK_CHANGED，csrankings.org，另叠加 Google Maps「invalid API key」）。
> 均与 lwx-env-error / task inventory 记录的外部依赖问题一致。要彻底定性仍建议核对容器日志，但当前证据已足以判为 infra 阻塞而非能力问题。

| 任务 | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|
| `academic-pdf-report` | — | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ✅ PASS（run glm-5.2/260904） |
| `add-bibtex` | 🔴 必现：Playwright 页面加载 60s 超时 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ FAIL（run glm-5.2/260904）<br>57 条 bibtex 内容不符：作者列表截断为"and others"（应列全）、会议名缺限定词（"ICLR" vs "the ninth ICLR"）、标题大小写、缺 `journal` 字段、cite key 命名不一致（`roziere2023codellama` vs `roziere2023code`）；能力问题，非 infra |
| `course-schedule` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ FAIL（run glm-5.2/260904）<br>课程名漏合并：`算法分析与设计-01班` 应为 `算法分析与设计-01、02班`；能力问题，非 infra |
| `cvpr-research` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |
| `find-alita-paper` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>跨全部 5 个批次 4/5 PASS | ✅ PASS（run glm-5.2/260904） |
| `git-milestone` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260904） |
| `git-repo` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260904） |
| `hk-top-conf` | 🟡 偶发：Prompt 超长 400 | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因≈infra：轨迹多次 Playwright 页面资源加载失败（net::ERR_NETWORK_CHANGED，iclr.cc）；命中的“401”为论文标题含 Unauthorized 的误报 |
| `identify-all-songs` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |
| `invoice-org` | 🔴 必现：Yahoo Finance API 429 限流 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 226 次 Yahoo Finance「Rate limited」429，与 env-error 记录一致 |
| `ipad-edu-price` | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ✅ PASS（run glm-5.2/260904） |
| `language-school` | 🔴 必现：Playwright 页面加载 60s 超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因≈infra：轨迹 178 次页面导航超时/中断（net::ERR_CONNECTION_RESET 等），与 env-error 记录一致 |
| `latex-prompt-box` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260904）<br>填充内容不符合任一可接受的 Simple Prompt 渲染格式（起始不匹配）；能力问题，非 infra |
| `logical-datasets-collection` | — | 3.2 不稳定：260821 FAIL，260826 PASS<br>文档判断多为环境抖动，重跑可能捞回 | ✅ FAIL（run glm-5.2/260904）<br>表格内容或格式与 groundtruth 不符（local check: Table content or format does not match）；能力问题，非 infra |
| `mrbeast-analysis` | 🔴 必现：Hugging Face 读取或 SSL 握手超时<br>🔴 必现：API Key 无效 | 3.2 不稳定：260821 PASS，260826 FAIL<br>文档判断多为环境抖动，重跑可能捞回 | ✅ FAIL（run glm-5.2/260904）<br>Detail_Lists 表 duration_seconds 单值不符（agent 924 / gt 1019），其余 (32,7) 结构一致；数据准确性/能力问题，非 infra（youtube MCP 仅首次 init 超时后恢复） |
| `nvidia-market` | 🔴 必现：Yahoo Finance API 429 限流<br>🔴 必现：Playwright 页面加载 60s 超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 212 次 Yahoo Finance 429 限流，与 env-error 记录一致 |
| `nvidia-stock-analysis` | 🔴 必现：Yahoo Finance API 429 限流<br>🔴 必现：Playwright 页面加载 60s 超时<br>🔴 必现：API Key 无效<br>🟡 偶发：MCP 工具执行错误 -32603<br>🟡 偶发：Python 依赖缺失或 ABI 不匹配 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 94 次 Yahoo Finance 429 限流，与 env-error 记录一致 |
| `profile-update-online` | 🔴 必现：Playwright 页面加载 60s 超时 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |
| `search-ca-school` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra/凭据：轨迹 56 次页面加载失败（net::ERR_NETWORK_CHANGED，csrankings.org）+ Google Maps geocoding「invalid API key」 |
| `shopping-helper` | 🔴 必现：Yahoo Finance API 429 限流<br>🔴 必现：Playwright 页面加载 60s 超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Playwright page.goto 60s 超时及目标站反爬 | ✅ FAIL（run glm-5.2/260904）<br>评测器实时抓取 Amazon 成功，3 个商品提交价均与实时页价不符（364.63≠379.99；172.72≠180.0×2），0/3 通过；价格数据不符，非 infra |
| `stock-build-position` | 🔴 必现：Yahoo Finance API 429 限流 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 233 次 Yahoo Finance 429 限流，与 env-error 记录一致 |
| `subway-planning` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ✅ PASS（run glm-5.2/260904） |
| `travel-exchange` | 🔴 必现：Yahoo Finance API 429 限流 | 3.3 A 从未通过：环境/凭据问题为主<br>Yahoo Finance 公共接口 IP 限流 429 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 229 次 Yahoo Finance「Too Many Requests」429，与 env-error 记录一致 |
| `trip-adviser` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ✅ PASS（run glm-5.2/260904） |
| `trip-itinerary-generator` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因≈infra：轨迹 98 次 page.goto net::ERR_TIMED_OUT（louvre.fr 等目标站页面加载超时） |
| `upenn-campus-route` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | ❌ FAIL（run glm-5.2/260904）<br>路线格式校验通过，但评测器获取步行时间的外部接口返回空（JSON decode error: line 1 col 0）→ "Failed to get walking time"，评测中断；根因=infra（评测侧外部地图接口），非模型能力 |
| `wandb-best-score` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260904） |
| `wandb-shortest-length` | — | 3.1 稳定可跑：GLM-5.3 两轮均 PASS<br>5.1 低外部依赖<br>列入文档 smoke test 集 | ✅ PASS（run glm-5.2/260904） |
| `yahoo-analysis` | 🔴 必现：Yahoo Finance API 429 限流 | 3.2 不稳定：260821 PASS，260826 FAIL<br>文档判断多为环境抖动，重跑可能捞回 | 🟠 NO_EVAL（run glm-5.2/260904）<br>跑满 max_turns 未产出可判定结果<br>根因=infra：轨迹 204 次 Yahoo Finance 429 限流，与 env-error 记录一致 |
| `youtube-repo` | 🔴 必现：API Key 无效 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |

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

统计：env-error 有记录 8，未提及 20；task inventory：3.1=2；3.3 A=2；3.3 B=2；3.4=2；4=20；我跑通情况：✅ PASS 3、❌ FAIL 3、🟠 NO_EVAL 22（run glm-5.2/260904，dump 到 [results/glm-5.2/](../results/glm-5.2/)，并发 8）。

> 说明与根因：本组 28 个任务里**只有 7 个真正进入 agent 执行**（过了 preprocess），其余 **21 个在 preprocess 阶段直接失败/卡住**，从未运行模型。
> - **PASS 3**：`dataset-license-issue`、`sync-todo-to-readme`、`verl-dataset`。
> - **FAIL 3（均能力问题，非 infra）**：`huggingface-upload`（漏传 figures/*.png）、`merge-hf-datasets`（工具参数类型字符串截断）、`personal-website-construct`（about.md 缺 “PhD candidate”）。
> - **NO_EVAL 22（全部 infra/配置，非模型能力）**：其中 21 个为 preprocess 失败 + 1 个（`train-ticket-plan`）agent 启动时 MCP 仅连上 3/4（rail_12306 未连）。preprocess 失败按签名归类：缺 GCP 服务账号密钥 `configs/gcp-service_account.keys.json`（7 个）、缺 Notion `files/duplicated_page_id.txt`（4 个）、配置模板 `KeyError 'token'`（7 个）、Google OAuth 缺字段（`fillout-online-forms`）、generic returncode 1（`investment-decision-analysis`）、preprocess 卡住未完成（`notion-personal-website`）。
> 补上 `configs/gcp-service_account.keys.json` 等凭据/配置文件后，这 21 个 preprocess-fail 任务应可重新进入执行。
>
> 注意：`results/glm-5.2/` 目录同时包含 A 组（run glm-5.2/260903）旧结果，脚本尾部聚合统计是 A+C 混合值；本表数字为按 `c-remote-write.txt` 清单逐任务读取 eval_res.json 单独统计所得。

| 任务 | lwx-env-error 描述 | task inventory 描述 | 我跑通情况 |
|---|---|---|---|
| `ab-testing` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺凭据文件 `configs/gcp-service_account.keys.json`（GCP 服务账号密钥）；根因=infra |
| `academic-warning` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `dataset-license-issue` | — | 3.4 无有效评测产出：5 批次均 NO_EVAL<br>第 6 节冲突约束：不可与 `huggingface-upload` 并发 | ✅ PASS（run glm-5.2/260904） |
| `experiments-recordings` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `files/duplicated_page_id.txt`（Notion）；根因=infra |
| `fillout-online-forms` | 🔴 必现：Google OAuth credentials 缺字段 | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：Google OAuth 授权信息缺字段 client_id/client_secret；根因=infra/凭据 |
| `flagged-transactions` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `game-statistics` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `gdp-cr5-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：配置模板 KeyError `token`；根因=infra |
| `huggingface-upload` | 🟡 偶发：Python 依赖缺失或 ABI 不匹配 | 3.3 A 从未通过：环境/凭据问题为主<br>Hugging Face 客户端 read timeout 10/15s<br>第 6 节冲突约束：不可与 `dataset-license-issue` 并发 | ✅ FAIL（run glm-5.2/260904）<br>仓库已建、README/config.json/pytorch_model.bin 均匹配，但漏传 figures/fig1–3.png；能力问题，非 infra |
| `inter-final-performance-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：配置模板 KeyError `token`；根因=infra |
| `investment-decision-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败（returncode 1）；根因=infra |
| `live-transactions` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `llm-training-dataset` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：配置模板 KeyError `token`；根因=infra |
| `machine-operating` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `configs/gcp-service_account.keys.json`；根因=infra |
| `merge-hf-datasets` | 🔴 必现：Hugging Face 读取或 SSL 握手超时 | 3.3 A 从未通过：环境/凭据问题为主<br>Hugging Face 客户端 read timeout 10/15s | ✅ FAIL（run glm-5.2/260904）<br>xlam_18 工具参数类型字符串被截断（`List[Union[int, float]]` 输出成 `List[Union[int`）；能力问题，非 infra |
| `music-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：配置模板 KeyError `token`；根因=infra |
| `nhl-b2b-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：配置模板 KeyError `token`；根因=infra |
| `notion-movies` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `files/duplicated_page_id.txt`（Notion）；根因=infra |
| `notion-personal-website` | 🟡 偶发：preprocess 阶段卡死 | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 卡住未完成（超时/中断，status=running）；根因=infra |
| `oil-price` | 🟡 偶发：Notion refresh lock 争用（含疑似间接影响） | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Notion refresh lock 争用<br>历史环境曾出现 preprocess fail | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `files/duplicated_page_id.txt`（Notion）；根因=infra |
| `personal-website-construct` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ FAIL（run glm-5.2/260904）<br>远端 about.md 缺必需信息 “PhD candidate”；能力问题，非 infra |
| `price-comparison` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id<br>另有 466 个派生变体全部 NO_EVAL，疑似评测器问题 | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：GCP 默认凭据缺失（DefaultCredentialsError）；根因=infra |
| `quantitative-financial-analysis` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：配置模板 KeyError `token`；根因=infra |
| `sync-todo-to-readme` | — | 3.3 B 从未通过：模型能力/任务难度为主<br>5.1 低外部依赖 | ✅ PASS（run glm-5.2/260904） |
| `task-tracker` | 🟡 偶发：preprocess 阶段卡死<br>🟡 偶发：Notion refresh lock 争用（含疑似间接影响） | 3.4 无有效评测产出：5 批次均 NO_EVAL；preprocess 持续卡死，疑似 Notion refresh lock | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：缺 `files/duplicated_page_id.txt`（Notion）；根因=infra |
| `train-ticket-plan` | 🟡 偶发：MCP server 启动超时（rail_12306） | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | 🟠 NO_EVAL（run glm-5.2/260904）<br>running failed：MCP 仅连上 3/4（rail_12306 未连接），agent 阶段直接失败；根因=infra（MCP 启动） |
| `verl-dataset` | 🔴 必现：Hugging Face 读取或 SSL 握手超时 | 3.1 稳定可跑：GLM-5.3 两轮均 PASS | ✅ PASS（run glm-5.2/260904） |
| `vlm-history-completer` | — | 第 4 节未验证：无历史实跑记录<br>已知阻塞：Google OAuth credentials 缺 refresh_token / client_secret / client_id | 🟠 NO_EVAL（run glm-5.2/260904）<br>preprocess 失败：配置模板 KeyError `token`；根因=infra |
