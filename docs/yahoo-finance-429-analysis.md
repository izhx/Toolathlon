# Yahoo Finance 429 限流：调用链分析与修复方向

**问题**：finalpool 中依赖 Yahoo Finance 的 task 稳定报 `Too Many Requests. Rate limited.`，导致无法评测（参见 [lwx-env-error.md](lwx-env-error.md) 表格第 4 行，标记为 🔴 必现）。按静态依赖统计，真实暴露面为 **10 个 task**，见文末速查表与口径差异说明。

**本文回答三个问题**：用的是什么 API、是不是公共 API、能不能申请 key 提额。

**结论先行**：用的是 Yahoo Finance 网页的**未公开内部接口**，官方公开 API 已于 2017 年下线。**不存在可申请的 key**，加任何 key 都不会提额。限流在 Yahoo 边缘按**出口 IP** 施加。要修只能走缓存/降频、换出口 IP，或换数据源 / 固化评测数据。

---

## 1. 实际调用链

### Agent 侧

```
configs/mcp_servers/yahoo-finance.yaml
  └─ uv run ${local_servers_paths}/yahoo-finance-mcp/server.py
       (fork: lockon-n/yahoo-finance-mcp，上游 Alex2Yang97/yahoo-finance-mcp)
       └─ yfinance 0.2.62            # pyproject.toml
            └─ HTTP → Yahoo 内部 endpoint
```

`pyproject.toml` 里另有 `mcp-yahoo-finance>=0.1.3`，其 `server.py` 同样是 `yfinance.Ticker(...)` 的薄封装（`Ticker(ticker=symbol, session=self.session).info`），底层出口完全一致。

> 注：`local_servers/` 在 `.gitignore` 中（第 10 行），不随仓库分发，需按 README 单独 clone。

### yfinance 实际打的地址

`.venv/.../yfinance/const.py:1-3`：

| 常量 | 地址 | 用途 |
|---|---|---|
| `_QUERY1_URL_` | `https://query1.finance.yahoo.com` | 行情 / 财报 |
| `_BASE_URL_` | `https://query2.finance.yahoo.com` | 同上（备用域） |
| `_ROOT_URL_` | `https://finance.yahoo.com` | 页面 / cookie |

常用路径：`/v8/finance/chart`（K 线）、`/v10/finance/quoteSummary`（`.info` / 财务）、`/v7/finance/quote`（实时报价）。

此外每个新 session 还要先做一轮 cookie + crumb 握手（`.venv/.../yfinance/data.py`）：

- `https://fc.yahoo.com`（取 cookie，`data.py:197`）
- `https://guce.yahoo.com/consent`、`https://consent.yahoo.com/v2/collectConsent`（同意页，`data.py:257-294`）
- `https://query{1,2}.finance.yahoo.com/v1/test/getcrumb`（取 crumb，`data.py:216`、`data.py:325`）

**握手本身也计入限流**。一旦 crumb 获取失败，yfinance 会重试，容易演变成请求风暴，把 429 放大。

### 评测侧同样直连（关键）

这是"无法评测"而不仅是"agent 跑不动"的根因。10 个 task 在 `task_config.json` 里声明了 `yahoo-finance` 工具：

```
investment-decision-analysis  invoice-org  ipad-edu-price  nvidia-market
nvidia-stock-analysis  oil-price  quantitative-financial-analysis
stock-build-position  travel-exchange  yahoo-analysis
```

其中 **6 个脚本自己 `import yfinance`**，绕开 MCP 直接打上游：

| 文件 | 说明 |
|---|---|
| `tasks/finalpool/yahoo-analysis/evaluation/main.py:4` | 另取 `^GSPC` 作基准，单次评测至少 2 个 ticker |
| `tasks/finalpool/nvidia-stock-analysis/evaluation/main.py` | 含 `main_original.py` |
| `tasks/finalpool/stock-build-position/evaluation/main.py` | |
| `tasks/finalpool/ipad-edu-price/evaluation/main.py` | |
| `tasks/finalpool/investment-decision-analysis/evaluation/realtime.py` | 文件名即说明问题：评测口径是实时价 |

`tasks/finalpool/oil-price/golden/main.py:248-258` 走的是 MCP 工具（`get_historical_stock_prices`）而非 yfinance，属 agent 侧。

于是同一个 task 会**打两遍上游**：agent 执行时打一次，评测时再打一次。并发跑多个 task 时倍数叠加。

### 当前没有任何缓解措施

在 `tasks/`、`utils/`、`scripts/` 全量 grep `requests_cache` / `CachedSession` / `set_tz_cache_location` / `impersonate` / `curl_cffi`：**零命中**。即所有调用都是裸打上游，无缓存、无限速、无退避、无浏览器指纹伪装。

（`curl_cffi` 0.11.3 已作为 yfinance 依赖装在环境里，只是没被显式用上。）

---

## 2. 是公共 API 吗

**不是。** 是"公开可访问但无官方授权"的内部接口：

- `query1/query2.finance.yahoo.com` 是 Yahoo Finance 网页自己的后端，**无公开文档、无 SLA、无鉴权层级**。
- Yahoo 的官方公开 API（YQL finance tables）**2017 年 11 月已下线**，此后未再开放免费官方接口。
- 限流按**出口 IP** 在边缘施加。机房 / 云厂商 IP 段（AWS、GCP、Colab 等）常被预先压低配额，与自身请求量无关。
- 上游 yfinance 明确定位为个人研究用途，使用受 Yahoo ToU 约束。

429 是限流器的**预期行为**，不是 yfinance 的 bug。

---

## 3. 能否申请 key 提额

**不能。** 这些 endpoint 不接受任何 API key，配置了也不会提额。

能拿到 key 的是**别的服务**，换过去需要改写 MCP server —— 不同 host、不同响应 schema，`yfinance` 不认这些 key：

| 方向 | 候选 | 备注 |
|---|---|---|
| 授权的 Yahoo 数据（付费第三方转售） | YH Finance API（financeapi.net）、RapidAPI 上的 Yahoo Finance 系列 | schema 与 yfinance 不兼容 |
| 直接换源（多有免费 key 档） | Alpha Vantage、Finnhub、Twelve Data、Tiingo、Polygon.io、EODHD、marketstack | 需重写工具层 |
| 免 key | Stooq | 覆盖面较窄 |

> ⚠️ 上表为既有知识整理（截至 2026-05），本仓库运行环境的 WebFetch / WebSearch 被网络策略拦截（连 `github.com` 都取不到），**当前定价与额度未经核实**，选型前请自行确认官网。

---

## 4. 修复方向（按性价比排序）

对需要可复现的评测场景，推荐优先级 **B > A > 其余**。

### A. 共享缓存 + 令牌桶

方向与 `docs/lwx-env-error.md` 记录的"yfinance MCP 加令牌桶/共享缓存"一致。

- 在 fork 的 `server.py` 包一层磁盘缓存：同 `(ticker, 窗口, 字段)` 只打一次上游。
- 加**进程间**令牌桶（文件锁 / Redis）限住全局 QPS —— 单进程限速对并发跑多 task 无效。
- 收益：直接砍掉 agent 侧与评测侧的重复请求。

### B. 评测数据固化（最彻底）

把上述 6 个评测脚本的行情依赖改为 fixture 快照或 VCR 式录制回放。

评测的正确性不应依赖上游可用性。`investment-decision-analysis/evaluation/realtime.py` 这个文件名就是结构性隐患的信号。

⚠️ 落地前需逐个确认评测口径：部分 task 可能刻意要比对"当前价"，固定快照会改变语义，需要同步调整判分逻辑或 task 描述。

### C. curl_cffi 浏览器指纹

`mcp_yahoo_finance/server.py:15` 的 `__init__` 已支持传入 session，`curl_cffi` 也已在环境中：

```python
from curl_cffi import requests as cffi_requests
session = cffi_requests.Session(impersonate="chrome")
```

缓解 TLS 指纹检测导致的 crumb 握手失败与重试风暴。**治不了 IP 级限流。**

### D. 串行化 + 指数退避

工具层串行请求；429 走指数退避重试。另将 `yf.set_tz_cache_location()` 指到共享目录，省掉重复的 tz cache 构建请求。

### E. 换出口 IP / 代理池

治 IP 段被预压的情况。但结果不可复现，仅适合应急。

### F. 换数据源

见第 3 节表格。工作量最大，且改变了 task 的工具语义（task 描述里提到 Yahoo Finance 的需同步改），仅在长期需要稳定行情数据时考虑。

---

## 附：受影响 task 速查

| task | agent 侧（MCP） | 评测侧（直连 yfinance） |
|---|---|---|
| yahoo-analysis | ✅ | ✅ |
| nvidia-stock-analysis | ✅ | ✅ |
| stock-build-position | ✅ | ✅ |
| ipad-edu-price | ✅ | ✅ |
| investment-decision-analysis | ✅ | ✅ |
| oil-price | ✅（golden 走 MCP 工具） | — |
| invoice-org | ✅ | — |
| nvidia-market | ✅ | — |
| travel-exchange | ✅ | — |
| quantitative-financial-analysis | ✅ | — |

### 与 `lwx-env-error.md` 的口径差异

`lwx-env-error.md` 把 429 归因到 7 个 task，其中 **`shopping-helper` 与本文清单不符**：它的 `needed_mcp_servers` 只有 `filesystem` 和 `playwright_with_chunk`，并未声明 `yahoo-finance`，评测脚本也不 import yfinance。其 429 更可能来自 Playwright 抓取 Amazon/Nasdaq 时被反爬限流（对应 `lwx-env-error.md` 表格第 6 行也点名了 shopping-helper），属于错误归类。

反过来，本文清单里的 `ipad-edu-price`、`oil-price`、`quantitative-financial-analysis`、`investment-decision-analysis` 未出现在 `lwx-env-error.md` 的 429 行中 —— 该文档只统计了 260812 GLM-5.1 两个批次里**实际提取到**错误行的 task，未点名不等于无风险。

**因此按静态依赖计，Yahoo 侧真实暴露面是 10 个 task，而非 7 个。**
