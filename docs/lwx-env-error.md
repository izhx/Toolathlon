# 260812 GLM-5.1 finalpool 环境问题汇总

**分析对象**：
- 批次1：`results/260812_results_glm-5.1/finalpool/`（79 个 task）
- 批次2：`results/260812_results_glm-5.1_11/finalpool/`（11 个 task，疑似重跑集）

**分析口径**：仅统计 `preprocess != fail` 的 task；从 `traj_log.json` 中 `role="tool"` 消息里提取真实错误行；模型行为错误（eval=False 但工具正常）不计入。

**必现 / 偶发标记**：
- 🔴 **必现**：跨批次稳定复现，或与外部凭据/账户/代码相关（重跑仍会出）
- 🟡 **偶发**：受外部服务临时状态、并发限流、网络抖动影响，重跑可能消失

---

## 两批次环境问题总表

| # | 类型 | 问题类别 | 具体报错特征 | 批次1 (`glm-5.1`) 受影响 task | 批次2 (`glm-5.1_11`) 受影响 task | 合计 | 修复方向 |
|---|---|---|---|---|---|---|---|
| 1 | 🟡 偶发 | **IMAP 认证失败** | `IMAP login failed: [UNAVAILABLE] Temporary authentication failure. [mcp.com:...]` | canvas-arrange-exam, canvas-art-manager, canvas-homework-grader-python, canvas-submit-late-work, course-assistant, meeting-assign, woocommerce-new-product (**7**) | — | 7 | mcp.com 邮件服务限流；单账户串行 + 指数退避 |
| 2 | 🟡 偶发 | **SMTP 发送失败** | `Error sending email: Connection unexpectedly closed` / `(450, ESERVFAIL)` | canvas-submit-late-work, meeting-assign, woocommerce-new-product (**3**) | — | 3 | 同上，跟 IMAP 一起修 |
| 3 | 🟡 偶发 | **DNS 解析失败** | `Name or service not known` (`mail.mcp.com`, `imap.mcp.com`) | canvas-art-manager (**1**) | — | 1 | 检查容器 /etc/hosts、DNS 配置 |
| 4 | 🔴 **必现** | **上游 API 429 限流** | `Too Many Requests. Rate limited.`（Yahoo Finance） | invoice-org, nvidia-market, nvidia-stock-analysis, shopping-helper, stock-build-position, travel-exchange, yahoo-analysis (**7**) | — | 7 | yfinance MCP 加令牌桶/共享缓存 |
| 5 | 🔴 **必现** | **HuggingFace 读超时** | `ReadTimeout: huggingface.co ... read timeout=10/15` + SSL handshake timeout | merge-hf-datasets, mrbeast-analysis, verl-dataset (**3**) | — | 3 | 加大 timeout（≥60s），或本地镜像 |
| 6 | 🔴 **必现** | **Playwright 页面超时** | `page.goto: Timeout 60000ms exceeded` (Amazon/Nasdaq/scribd 等) | add-bibtex, language-school, nvidia-market, nvidia-stock-analysis, profile-update-online, shopping-helper (**6**) | — | 6 | 加大超时、换加载策略、UA |
| 7 | 🔴 **必现** | **API Key 无效** | `API key not valid`（YouTube / FMP / Docker registry） | mrbeast-analysis, youtube-repo, nvidia-stock-analysis (**3**) | — | 3 | 更新对应 provider key |
| 8 | 🟡 偶发 | **Prompt 超长 400** | `litellm.BadRequestError: Prompt 超长` | hk-top-conf, inventory-sync (**2**) | — | 2 | 工具响应截断/摘要 |
| 9 | 🟡 偶发 | **MCP server 启动超时** | `Error initializing MCP server: Timed out ... 20.0 seconds` (rail_12306) | train-ticket-plan (**1**) | — | 1 | 加大启动超时；npm 依赖预装 |
| 10 | 🟡 偶发 | **MCP 工具执行错误** | `McpError -32603: ...`（k8s helm/kubectl/exec） | k8s-mysql, k8s-pr-preview-testing, k8s-redis-helm-upgrade, canvas-art-manager, nvidia-stock-analysis (**5**) | — | 5 | k8s MCP 稳定性 + 镜像预拉 |
| 11 | 🟡 偶发 | **Docker Registry 5xx** | `HEAD ... registry-1.docker.io ...: 500 Internal Server Error` + `ImagePullBackOff` | k8s-redis-helm-upgrade (**1**) | — | 1 | 本地镜像仓库缓存（bitnami/redis 等） |
| 12 | 🟡 偶发 | **网络连接被拒/中断** | `Connection refused` / `Connection reset` | canvas-art-manager, k8s-redis-helm-upgrade, woocommerce-new-product (**3**) | — | 3 | 排查代理/容器网络 |
| 13 | 🟡 偶发 | **Python 依赖缺失/ABI 不匹配** | `ModuleNotFoundError: yfinance` / `undefined symbol: PyDict_GetItemRef` (Py3.13 → Py3.12) | huggingface-upload, nvidia-stock-analysis (**2**) | — | 2 | 容器 image 预装/重新编译 |
| 14 | 🟡 偶发 | **preprocess 阶段卡死** | 无 traj_log 生成；running 状态超时 | notion-personal-website, task-tracker (**2**) | task-tracker (**1**，第 2 次复现) | 2 unique | 加 preprocess 超时；清陈旧 lock |
| 15 | 🟡 偶发 | **Notion refresh lock 争用** | `notion_official refresh lock contended for >600s` | oil-price (preprocess-fail，未计入)、间接影响多个 | 疑似仍是 task-tracker 卡死主因 | — | 跑前清 `*.lock`；批量前预热 token |
| 16 | 🔴 **必现** | **Google OAuth 凭据缺字段** | `Authorized user info was not in the expected format, missing fields refresh_token, client_secret, client_id` | — | fillout-online-forms (**1**) | 1 | 重新走 OAuth 生成完整 credentials JSON |

---

## 必现问题（🔴 需优先修复）

这些问题**只要触发对应工具/服务就会出**，与外部临时状态无关，重跑不会自愈：

| # | 问题 | 根因性质 | 修复优先级 |
|---|---|---|---|
| 4 | Yahoo Finance 429 限流 | yfinance 官方公共接口对 IP 限流，任何并行/密集调用都会触发 | 🔴 高（影响 7 个 task） |
| 5 | HuggingFace 读超时 | 客户端 `read timeout=10/15` 太短，跨国链路稳定 timeout | 🔴 高 |
| 6 | Playwright 页面超时 | Amazon/Nasdaq/scribd 反爬 + 页面重，60s 不够 | 🔴 高（影响 6 个 task） |
| 7 | API Key 无效 | YouTube/FMP 的 key 本身失效或未配置 | 🔴 高（不修永远失败） |
| 16 | Google OAuth 凭据缺字段 | `credentials.json` 结构不完整，只要跑到就失败 | 🔴 高 |

## 偶发问题（🟡 依外部条件变化）

这些在批次2 完全没复现，属于**外部服务临时状态 / 并发抖动**，可以通过重试或分散负载缓解，但不一定每次都能修根本：

| # | 问题 | 触发条件 |
|---|---|---|
| 1–3 | IMAP/SMTP/DNS（mcp.com 邮件服务） | 并发多账户短时间大量登录被临时封 |
| 8 | Prompt 超长 400 | 特定 task 输出恰好超过模型 context |
| 9 | MCP server 启动超时（rail_12306） | npm 拉包/启动瞬时慢 |
| 10 | MCP 工具执行 -32603 错误 | 集群/依赖临时状态 |
| 11 | Docker Registry 5xx | Docker Hub 自身 500，纯外部抖动 |
| 12 | 连接被拒/中断 | 网络抖动 |
| 13 | Python 依赖缺失/ABI 不匹配 | 特定容器镜像状态，重装后可修复 |
| 14 | preprocess 卡死 | 多数是 Notion lock 引起（见 15） |
| 15 | Notion refresh lock 争用 | 并发跑多任务时抢锁 |

---

## 关键观察

1. **批次2 大幅收敛**：批次1 大量出现的**邮件类（10 个）、限流类（7 个）、超时类（9 个）** 在批次2 完全没复现——要么是外部服务恢复，要么是重跑集有意避开。
2. **持续未解决的顽疾**：
   - `task-tracker` preprocess **两次都卡死**（1.5 小时超时）——高度怀疑是 Notion refresh lock。
   - Google OAuth 是**批次2 新暴露**的问题。
3. **必现 vs 偶发的意义**：跑批次3 前，先把**🔴 必现问题**里的第 7、16 修掉（key / OAuth），第 4、5、6 通过加超时/加缓存/加限流缓解——这样能一次性稳定拿回 20+ 个 task 的稳定性。

---

## 立即可做的排查命令

```bash
# 1. task-tracker preprocess 卡在哪
ls /data01/lwx/Toolathlon/tasks/finalpool/task-tracker/preprocess/
cat /data01/lwx/Toolathlon/tasks/finalpool/task-tracker/preprocess/main.py

# 2. Google auth 状态
ls -la /data01/lwx/Toolathlon/configs/.mcp-auth/ | grep -iE 'google|oauth|token'

# 3. 清陈旧锁（>5 分钟未释放的）
find /data01/lwx/Toolathlon/configs/.mcp-auth/ -name "*.lock" -mmin +5 -delete
```
