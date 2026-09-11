# Yahoo Finance 429 限流解决方案调研

调研日期：2026-09-10。对象：当前 Toolathlon 工作树、宿主 `.venv`、仓库固定版本的 Yahoo Finance MCP，以及调研时可访问的上游文档与源码。

**建议先核对代理和运行版本，再减少请求、做全局限速与共享缓存；如果允许固定数据评测，再考虑快照回放。** 单纯增加重试次数，容易让限流持续更久。

本文记录方案与证据，不代表方案已经实施或实际任务已经恢复。调研期间没有修改运行代码、升级依赖或重跑评测。

**当前实现中的具体线索**

当前 finalpool 中有 10 个任务声明使用 `yahoo-finance`：`investment-decision-analysis`、`invoice-org`、`ipad-edu-price`、`nvidia-market`、`nvidia-stock-analysis`、`oil-price`、`quantitative-financial-analysis`、`stock-build-position`、`travel-exchange`、`yahoo-analysis`。该列表来自各任务的 `task_config.json`，表示依赖范围，不表示这 10 个任务都已在本次复现 429。

| 发现 | 证据 | 对方案选择的影响 |
|---|---|---|
| 模型工具和评分器都会产生 Yahoo 请求 | MCP 入口见 [yahoo-finance.yaml](../configs/mcp_servers/yahoo-finance.yaml)；直接调用 yfinance 的评分器包括 [ipad-edu-price](../tasks/finalpool/ipad-edu-price/evaluation/main.py)、[yahoo-analysis](../tasks/finalpool/yahoo-analysis/evaluation/main.py)、[stock-build-position](../tasks/finalpool/stock-build-position/evaluation/main.py)、[investment-decision-analysis](../tasks/finalpool/investment-decision-analysis/evaluation/realtime.py)、[nvidia-stock-analysis](../tasks/finalpool/nvidia-stock-analysis/evaluation/main.py)；[oil-price](../tasks/finalpool/oil-price/evaluation/main.py) 的评分器通过 MCP 查询行情 | 只改 MCP 或只降低任务并发，都可能遗漏请求来源 |
| 单任务内部也有并发 | `stock-build-position/evaluation/main.py` 的 `get_stock_prices_async()` 使用 `ThreadPoolExecutor(max_workers=10)` | `workers=1` 不等于 Yahoo 请求串行 |
| 当前宿主已经使用 curl_cffi | 宿主 `.venv` 实测为 `yfinance 0.2.62`、`curl_cffi 0.11.3`；[uv.lock](../uv.lock) 中 yfinance 也为 `0.2.62`；该版本默认建立 `Session(impersonate="chrome")` | 旧教程中的“加上 curl_cffi”在这里不算新修复；宿主版本不能直接当作任务容器版本 |
| MCP 的行情查询有额外前置请求 | [Dockerfile](../Dockerfile) 固定 MCP 提交 `469103ba1464486cb7b8bd2c1f6355f42ca64a5b`；其历史行情、指定日期价格等工具先检查 `company.isin`。当前 yfinance 的 `get_isin()` 会查询公司信息，并可能访问 Business Insider | 即使行情端点可用，也可能先在额外查询上失败；去掉不必要的 ISIN 检查值得优先测试 |
| 代理不一定传到实际请求进程 | [容器启动脚本](../scripts/run_single_containerized.sh) 没有显式传递代理变量；[Yahoo MCP 配置](../configs/mcp_servers/yahoo-finance.yaml) 没有 `params.env`；当前宿主 MCP SDK 的默认环境变量继承列表不含代理变量 | 需要分别核对宿主、任务容器、MCP 子进程和评分进程；在宿主设置代理不能证明整个链路已经使用代理 |
| 现有通用工具重试不是完整的 429 策略 | [call_tool_with_retry](../utils/mcp/tool_servers.py) 默认捕获异常后间隔 1 秒重试，且直接返回正常取得的工具结果；部分 MCP 错误以文本结果返回 | 需要区分 HTTP 429、工具异常和工具返回的错误文本，避免遗漏限流或层层重试 |

MCP 的额外查询依据是仓库所固定提交的[上游实现](https://github.com/lockon-n/yahoo-finance-mcp/blob/469103ba1464486cb7b8bd2c1f6355f42ca64a5b/server.py#L117)。当前工作树未安装该 `local_servers` 目录，本次没有在运行中的任务容器内核对实际加载文件。

**少量网络探测结果**

使用宿主 `.venv` 中的 `curl_cffi`，模拟 Chrome，串行发起请求且不重试：

| 探测时间（UTC） | 请求条件 | 接口 | 结果 |
|---|---|---|---|
| 2026-09-10 09:56 起 | 保留现有代理环境变量 | `query1.finance.yahoo.com/v8/finance/chart/AAPL`，`range=1d`、`interval=1d` | HTTP 200，返回行情结果且没有 chart error |
| 同一轮，间隔 5 秒 | 保留现有代理环境变量 | `query1.finance.yahoo.com/v1/test/getcrumb` | HTTP 200；未输出 crumb 内容 |
| 2026-09-10 09:58 | 用 `CURLOPT_PROXY=""` 显式禁用代理 | 相同 AAPL 行情接口 | HTTP 403；未进一步判定响应来源 |

libcurl 文档明确说明，空字符串代理配置会覆盖环境变量并禁用代理。[CURLOPT_PROXY 文档](https://curl.se/libcurl/c/CURLOPT_PROXY.html)

这些结果说明当前网络路径会影响可访问性。它们没有在本次复现 429，也不能证明历史 429 的根因，更不能证明任务容器中的完整 MCP 和评分流程已经可用。

**可选解决方案**

| 方案 | 具体做法 | 效果与局限 |
|---|---|---|
| 1. 检查代理传递及出口 | 分别核对宿主、任务容器、MCP 子进程、评分进程的代理配置；必要时使用稳定、低负载的独立出口 | 适合“宿主能访问，任务里失败”。共享代理也可能被其他流量拖累；更换 Docker 容器通常不会自动改变公网出口 |
| 2. 升级并固定依赖版本 | 在独立环境测试新版 yfinance 和匹配的 curl_cffi，再同步实际运行环境 | 调研时上游发布版为 1.7.0；其请求实现增加了 crumb 被限流后继续尝试目标接口的处理，对部分行情请求可能有帮助，但不能消除真正的上游限流 |
| 3. 减少不必要的请求 | 去掉行情查询前不必要的 ISIN 检查；复用 Ticker；一次获取时间区间后在本地切片；只需价格时避免获取完整 `info` | 改动相对小，直接降低请求量。需要保留真实的无效代码、无数据检查；一次工具调用可能对应多个 HTTP 请求 |
| 4. 全局限速和串行调度 | Yahoo 相关任务互斥；降低 evaluator 内部线程数；按实际 HTTP 请求统一限速 | 必须覆盖多个进程、容器和评分器。仅在一个 MCP 里加 `sleep`，覆盖不全 |
| 5. 退避重试和熔断 | 优先遵守 `Retry-After`；否则采用指数退避加随机抖动；连续 429 后暂停整个 Yahoo 请求队列 | 适合短期限流。应限制重试次数，避免 MCP、模型、评分器层层重试；冷却时间还要与 MCP 调用超时协调 |
| 6. 持久化共享结果缓存 | 缓存成功获取的行情、汇率、财报、评级等；相同请求合并；所有调用方复用 | 很适合重复评测。实时价格设置较短有效期，历史数据按版本保存；首次采集仍依赖可用的数据源 |
| 7. 数据快照与本地回放 | 预先采集真实数据，模型工具和 evaluator 使用同一份数据、同一时间基准 | 对已覆盖的数据请求可消除运行期 Yahoo 限流，并提高可复现性。但会改变实时任务的评测条件，需要单独标明；保存原始数据，不能直接回放标准答案 |
| 8. 换用独立数据提供商 | 按任务需求接入有明确配额的数据 API，并适配现有工具输出 | 可摆脱 Yahoo 的请求限制，但需处理字段、时间点、复权和数据来源差异；只改模型工具、评分器仍访问 Yahoo，问题仍在 |

yfinance 1.7.0 的版本信息已通过 [GitHub 发布记录](https://github.com/ranaroussi/yfinance/releases/tag/1.7.0)和 [PyPI](https://pypi.org/project/yfinance/1.7.0/)核对；crumb 限流后的处理依据为[该版本源码](https://github.com/ranaroussi/yfinance/blob/1.7.0/yfinance/data.py#L440)。这属于代码层面的改进依据，本次未安装新版验证效果。

HTTP 429 可以携带 `Retry-After`，但该响应头不是必需项；429 本身也不能确定服务端按 IP、Cookie、凭据还是其他维度计数。设计限速时不能把网上流传的固定请求额度或固定恢复时间当作保证。[RFC 6585 第 4 节](https://www.rfc-editor.org/rfc/rfc6585.txt)

**缓存与重试的实现注意点**

当前 yfinance 的默认持久化缓存主要保存时区和 Cookie，并不是完整行情缓存；配置中的 `cache_tools_list: true` 也只缓存工具列表。[yfinance 缓存文档](https://ranaroussi.github.io/yfinance/advanced/caching.html)

不能直接照搬旧版 `requests_cache.CachedSession` 教程。已检查的 yfinance 0.2.62 和 1.7.0 源码均拒绝这类缓存 Session。保留 curl_cffi 网络层，在应用层或统一数据服务中缓存成功结果，是更适合本仓库评估的方向。[1.7.0 Session 检查](https://github.com/ranaroussi/yfinance/blob/1.7.0/yfinance/data.py#L143)

也可以考察现成的 [yfinance-cache](https://github.com/ValueRaider/yfinance-cache)。它提供持久化缓存和离线模式，但会强制启用价格修复，并调整部分接口和返回列，不能未经数值对照就直接替换评测依赖。

共享结果缓存建议至少考虑以下要求：

- 缓存键包含数据类型、股票或货币代码、日期区间、采样周期、复权参数以及影响返回数据的其他参数。
- 保存数据来源、采集时间、数据截止时间、依赖版本和缓存版本，支持定位评测差异。
- 多进程请求同一份缺失数据时，只让一个采集者访问上游，其余等待同一结果。
- 不把 429 页面、工具错误文本或因限流产生的空表当作成功数据；冷却状态与业务数据分开保存。
- 对同一轮评测需要比较的价格或汇率，让模型和评分器使用同一数据时点，避免缓存命中时间不同带来的差异。

新版 `yf.config.network.retries` 主要处理临时网络异常。检查到的 1.7.0 实现没有提供跨进程的 429 冷却机制，需要在公共请求层额外实现。[配置说明](https://ranaroussi.github.io/yfinance/advanced/config.html)、[重试实现](https://github.com/ranaroussi/yfinance/blob/1.7.0/yfinance/data.py#L473)

本仓库当前的任务冲突锁是 `run_parallel.py` 内的 `asyncio.Lock`，只在一个调度进程内生效。若多个模型、多个 checkout 或多个调度进程共用出口，需要进程间协调的限速器，或者集中到一个数据服务。当前 [task_conflict.json](../tasks/finalpool/task_conflict.json) 尚未配置 Yahoo 任务互斥组。

另外，[Yahoo MCP 配置](../configs/mcp_servers/yahoo-finance.yaml)的调用超时为 60 秒。如果一次工具调用在内部执行长时间冷却，客户端可能先超时并触发更多重试；应将较长冷却交给调度层，或同步设计超时与失败返回机制。

**替代数据源候选**

| 数据源 | 适用方向 | 需要注意 |
|---|---|---|
| [Alpha Vantage](https://www.alphavantage.co/support/) | 股票、基本面、外汇 | 调研时普通免费额度为 25 次/天；官方也提供符合条件的开源或教育项目申请渠道。项目资格和具体数据权限需要申请确认 |
| [Twelve Data](https://support.twelvedata.com/en/articles/5615854-credits) | 多市场行情、外汇及部分基本面 | 按端点和股票数量消耗 credits，财报、机构持仓等可能需要更高套餐；仍需按其公开配额限速 |
| [Frankfurter](https://frankfurter.dev/) | 历史日期的汇率、报销换算 | 无需 API Key，可自建；提供央行日度汇率，与 Yahoo 市场报价不一定相同。公共服务仍有防滥用限速 |

替换前需要按实际任务核对覆盖范围，例如美股、港股、A 股、汇率、历史评级事件、机构持仓、分析师目标价等。能返回股票价格，不代表能覆盖 Yahoo MCP 的全部工具。

数据一致性尤其影响以下任务：

- `yahoo-analysis` 明确使用 `yfinance.Ticker(ticker).upgrades_downgrades` 中的逐条评级记录，并按交易所当地日期筛选。其他提供商的评级统计不能直接等同于这些事件行，见 [guide.md](../tasks/finalpool/yahoo-analysis/initial_workspace/guide.md)。
- `investment-decision-analysis` 的评分数据严格读取 `currentPrice`、`trailingPE`、`targetMeanPrice`，见 [realtime.py](../tasks/finalpool/investment-decision-analysis/evaluation/realtime.py)。
- `travel-exchange` 指定历史行程及 Yahoo 汇率，见 [task.md](../tasks/finalpool/travel-exchange/docs/task.md)。央行日度汇率能否满足要求，需要核对数据来源约束及评分容差。
- `nvidia-stock-analysis` 已对 Basic Trend 使用保存的 Yahoo 数据，但持仓部分仍会调用实时 yfinance。局部快照不等于整个任务脱离 Yahoo，见 [evaluation/main.py](../tasks/finalpool/nvidia-stock-analysis/evaluation/main.py)。

**其他条件性方案**

登录 Yahoo、更新 Cookie、换客户端、浏览器抓取或购买第三方 Yahoo 转发 API，也可以研究，但更适合作为补充：

- 新版 yfinance 已支持设置登录 Cookie；这不能等同于增加请求配额。本次没有核实到登录或购买 Yahoo 网页订阅可以解除 yfinance 429 的保证。[认证文档](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Auth.html)
- 若日志明确显示 Cookie 或 crumb 状态异常，可以在冷却后重建相关会话；频繁清缓存、重建会话也会增加初始化请求，不能替代限速。
- 换一个仍访问 Yahoo 的库、MCP 或浏览器，并不消除上游限制。对于查询网页正常、特定 API 失败的情况，可以用来定位差异，但不应直接当作批量评测的稳定保障。
- 第三方转发服务是否有独立缓存、明确配额、所需字段及稳定性承诺，需要逐家确认；名称包含 Yahoo 不等于 Yahoo 官方服务。
- 独立出口或代理池可能缓解共享出口的拥挤，但无法修复多余请求、错误重试和数据不一致问题；不能承诺更换 IP 后一定恢复。

**建议的实施顺序与验收范围**

1. 在实际任务容器中确认 Python、yfinance、curl_cffi 和 MCP 的实际版本，检查代理是否传到每个发起请求的进程。记录失败端点，区分 crumb、行情、公司信息、评级和持仓。
2. 优先测试移除多余的 ISIN 查询、降低评分器内部并发、阻止连续错误重试；独立验证新版依赖的兼容性后固定版本。
3. 建立跨进程的请求限速与冷却机制，让 MCP 和直接使用 yfinance 的评分器共享成功结果缓存。
4. 如果主要目的是重复比较模型能力，再评估同一时间点的真实数据快照；需要实时数据时，评估稳定出口和独立数据提供商。

验证应至少覆盖历史价格、外汇、公司信息、评级和机构持仓等实际使用的数据类型，并同时覆盖模型工具与评分器。记录实际 HTTP 请求数、429 次数、缓存命中情况、等待时间和返回字段，不能仅凭一次 AAPL 行情查询成功就宣称全部 Yahoo 任务恢复。

**验证边界**：本次确认了当前工作树、宿主依赖、仓库固定 MCP 提交、上游源码与文档，以及上述少量宿主网络请求。历史错误汇总可作为排查线索，但本次没有重新提取原始评测轨迹，没有在实际任务容器中验证修复效果，也没有验证替代提供商对全部 10 个任务的数据覆盖。
