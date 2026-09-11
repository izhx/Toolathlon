# wandb 高保真模拟可行性与设计

作者：领域 agent `/root/wandb`；分析会话 `gpt-6-astra / xhigh`，与统筹核验的实际会话一致。查阅日期：2026-09-10。已读原始需求、shared、service-template、总体报告、synthesis-design、validation-plan 和 `docs/mcp-analysis.md`；未发现仓库祖先及报告目录中适用的 AGENTS.md。本文只做文档和源码只读分析，没有启动 MCP、导入业务配置、执行上游测试、初始化账号或进行真实服务写入。F/D/A/U、M/B/X、I/S/C/T/D/P 遵循 [shared.md](../shared.md)。非原作者 `/root/snowflake` 已于 2026-09-10 以 `gpt-6-astra / xhigh` 完成全篇交叉审查；作者已按两项 P2 问题 WB-01/WB-02 修订，证据及残余 U 见第 9 节。

**结论（D）：六个原生工具的接口可按固定依赖准确复现；业务核心采用代码实现的 GraphQL/Weave/报告状态和共享 HTTP 入口。原生 `query_wandb_support_bot` 适合受来源约束的在线 LLM 对照。全 GraphQL 后端 schema、历史采样、媒体与报告副作用、Weave 查询差异是主要难点，不能将六个工具理解为六个简单响应模板。**

## 1. 范围、版本与入口

### 1.1 已核版本与字节

本文 `W:` 指 [lockon-n/wandb-mcp-server 固定提交](https://github.com/lockon-n/wandb-mcp-server/tree/83f6d7fe2ad2e6b6278aef4a792f35dd765fd315) 内 `src/wandb_mcp_server/`。本次临时读取位置为 `/tmp/toolathlon-mcp-audit-xmv3srz8/wandb`；固定 URL 才是可长期定位的证据。外部源码、发布包、官方文档均查阅于 2026-09-10。

| 坐标 | 已核事实 F | 不能据此断言的内容 U |
|---|---|---|
| Toolathlon 安装基线 | `global_preparation/install_env.sh:202` 固定 `83f6d7fe2ad2e6b6278aef4a792f35dd765fd315`；上游 `pyproject.toml:1-17` 项目版本 0.1.0，依赖采用下限 | `uv tool install` 不证明实际镜像依赖等于仓库 lock |
| 固定源码字节 | 重新只读下载 [codeload archive](https://codeload.github.com/lockon-n/wandb-mcp-server/tar.gz/83f6d7fe2ad2e6b6278aef4a792f35dd765fd315)，SHA-256 `4d1c7534e2955728f495680d6ccd5c68a08fc553e1fb9f936925323f14342522`；归档 43 个普通文件，临时目录已有的 34 个逐字节全部相同，另 9 个未保存 | 不是整个目录完整克隆；没有读取或复制归档中的凭据文件内容 |
| 核心源码摘要 | `W:server.py` SHA-256 `90b1fe5817c20f4e0b88c8716b971821b8c882610295522e3d265e49351b54e9`；`W:mcp_tools/query_wandb_gql.py` 为 `78f565b7a4916e39b1ac29e55eebdb867e42ef2a0a1c12bf8cd7502b4d07d2f6` | 尚无真实 `initialize/tools/list` 运行快照 |
| 上游锁文件 | 只读解析归档 [uv.lock](https://github.com/lockon-n/wandb-mcp-server/blob/83f6d7fe2ad2e6b6278aef4a792f35dd765fd315/uv.lock)：GraphQL-core 3.2.3（554）、MCP 1.3.0（852）、Pydantic 2.10.6（1237）、wandb 0.19.8（1891）、wandb-workspaces 0.1.12（1984）、Weave 0.51.59（1997） | 这是可复现候选依赖 profile，不能覆盖 SaaS 后端版本 |
| 本仓库 X 层 SDK | `uv.lock:3551-3552` 与本机 `.venv/lib/python3.12/site-packages/wandb-0.21.1.dist-info/METADATA:1-3` 均为 wandb 0.21.1 | X 层与 MCP 独立安装依赖可能不同；不能混称统一版本 |
| YAML | `configs/mcp_servers/wandb.yaml:4-16` 为 stdio、`uvx --from wandb-mcp-server wandb_mcp_server`、API key、workspace cwd、10 秒 client session timeout、缓存 tools list | 启动命令没有写 commit；实际解析包及运行镜像待取 manifest 核验 |

### 1.2 M/B/X 与公网

| 层/入口 | 范围、状态、认证与路由 | 证据 |
|---|---|---|
| M | 固定注册 6 个工具，全部无只读/toolset 可见性开关。工具名包括 `query_wandb_tool`、两个 Weave 工具、项目发现、报告创建、支持机器人 | `W:server.py:73-194` |
| B Models | `wandb.Api().client.execute` 接受 GraphQL 操作字符串；项目、run/history/summary、artifact/registry、sweep、report/view、viewer/team 是已说明的能力族。后端允许的其他 query/mutation 也可到达，须靠后端 schema 和 ACL 冻结范围，不能用 finalpool 限缩 | `W:mcp_tools/query_wandb_gql.py:19-116,223,565-634` |
| B Weave | `/calls/stream_query` JSONL 和 `/calls/query_stats` JSON；共享 `entity/project`、calls/trace tree、op/object refs、反馈、成本和权限 | `W:weave_api/client.py:60-116`；`W:mcp_tools/count_traces.py:177-304` |
| B 报告 | `wandb.init` → 可选 `wandb.log(wandb.Html(...))` → workspaces Report 保存 → `wandb.finish`；包含 run、项目、媒体和 view 状态 | `W:mcp_tools/create_report.py:132-195`；workspaces 0.1.12 `reports/v2/interface.py:3045-3078` |
| B 支持机器人 | 每调用 GET `/status`，initialized 真时 POST `/chat/query`，提交 question 和固定 application。仅接收问题，不传 entity/project/run 状态或聊天历史 | `W:mcp_tools/query_wandbot.py:36-106` |
| X 初始化/评测 | W&B 两个 CSV 任务无 W&B preprocess；experiments-recordings preprocess 调用 Notion 删除/复制入口；其 evaluator 用 wandb SDK 列 runs、扫描 history，再与 Notion 内容比对 | `tasks/finalpool/experiments-recordings/preprocess/main.py:25-50`；`evaluation/main.py:79-132,355-385` |
| X 潜在 SDK/CLI/HTTP/浏览器 | 三个任务都声明 terminal；SDK 的 runs/history、报告回读、artifact 文件 URL 和 HTML 本地文件输入应接同一后端。没有已核实的当前任务 W&B CLI 写入轨迹；未来 CLI/训练上传为显式扩展 profile | 三份 `task_config.json:1-9`；本机 SDK `apis/public/api.py:293-350` |

框架由 `utils/mcp/tool_servers.py:50-99` 读取 YAML，`utils/roles/task_agent.py:465-551` 连接并枚举模型工具。模型侧是 `wandb_` 加原始工具名；真实 dispatch 名不变，见 `utils/openai_agents_monkey_patch/tool_name_aliases.py:21-28`。同一原始结果还经过 harness 的 content JSON 包装和超长输出文件化，见 `custom_mcp_util.py:176-229`，须保留双层快照。

**路由不能只改一个 base URL（F/D）：** Models SDK 支持 base_url，当前官方 [Api 文档](https://docs.wandb.ai/models/ref/python/public-api/api)及本机 SDK `apis/public/api.py:285-350` 支持此结论。count 读取 `WEAVE_TRACE_SERVER_URL`（`W:mcp_tools/count_traces.py:272-275`），但 query 的模块级 `TraceService()`（`W:mcp_tools/query_weave.py:9`）最终客户端默认固定 `https://trace.wandb.ai`（`W:weave_api/client.py:24-58`），没有读取该环境变量。支持机器人独立读取 `WANDBOT_BASE_URL`，默认为源码中的 Modal 服务。保留原 MCP 的路线需增加仅改变 transport 的可审查适配，或用独立服务入口 facade；必须证明每个入口确实进入同一 episode。

生产原配置需要 Models、Weave、support bot 等公网业务服务；报告/媒体 URL 还可能访问对象存储及页面资源。安装下载、agent 模型 API、仿真模型 API另记。`wandb.Html` 在 SDK 0.19.8 默认注入指向 `https://app.wandb.ai/normalize.css` 的样式链接，生成文件并不等于渲染时无公网，见 [SDK 0.19.8 html.py:29-74](https://github.com/wandb/wandb/blob/v0.19.8/wandb/sdk/data_types/html.py#L29)。本地/内网后端本身不算公网；自控 LLM 仍有算力成本。CLI 启动执行 `wandb.setup/login`，缺 API key 会失败；Weave 模块初始化也检查 key，因此不通过启动服务采集本次 schema（`W:server.py:197-249`；`W:weave_api/client.py:45-53`）。

### 1.3 当前任务与轨迹边界

全部声明成员为 `wandb-best-score`、`wandb-shortest-length`、`experiments-recordings`。前两者从实验日志产生本地 CSV；第三者把实验结果写入 Notion。前两者 evaluator 分别使用代码内固定期望值和 groundtruth CSV（`wandb-best-score/evaluation/main.py:11-58`；`wandb-shortest-length/evaluation/main.py:11-94`），不能充当合成新状态的通用 oracle。第三者实时 `Api().runs`、按显示名分组、`scan_history(page_size=2000)`，并吞掉部分历史读取异常（`experiments-recordings/evaluation/main.py:88-132`），所以无异常或旧任务通过不足以证明 MCP/SDK 同态。

本次扫描三任务目录、`utils/app_specific`、仓库可见 JSON/JSONL/log 名称及可能的 dumps/results 目录，没有找到可直接用于本服务的真实 Toolathlon 工具轨迹或全工具快照。上游 `tests/` 仅作样例源码证据；其中会调用模型 API，并有 session 结束聚合 Weave 记录的代码（`tests/test_query_wandbot.py:32-46,200`；`tests/conftest.py:86-105`），未执行。下文“当前使用”只指任务需求或 SDK 代码证明，不能伪装成观测到的 MCP 工具调用。

## 2. 工具与能力清单

### 2.1 全部六工具及输入契约

下表按注册签名列出全部参数，`!` 是必填；未标 `!` 均为可省略且有列出的默认值。`object` 没有内层固定 schema；`array<any>` 不应改成更严格的 `array<string>`。注册未使用 Field 的 min/max、字符串正则或 Literal/enum；文案里的建议不是输入 schema 的硬校验。原始说明完整保留固定常量，不能只用下表短述替换，否则改变工具选择行为。

| 原始工具名 / 属性 | 说明与全部输入 | 输出与状态依赖 | 当前使用 / 未来价值 / 证据 |
|---|---|---|---|
| `query_wandb_tool` / 读、写、管理，依操作 | 任意 Models GraphQL，强调 Models 与 Weave 区分、run ID 与 displayName、JSONString filters、connection 分页。`query!: string`；`variables: object\|null=null`；`max_items: integer=100`；`items_per_page: integer=20` | Python dict，成功为 SDK 执行后的选中字段字典；错误可为 `errors:[{message,...}]`；涉及请求选择的全部实体与权限 | 三任务均有 Models 读取需求，具体调用未观测；未来涵盖 query/mutation、图关系与多对象查询。`W:server.py:144-153`；说明 `mcp_tools/query_wandb_gql.py:19-522` |
| `query_weave_traces_tool` / 读 | trace/metadata/cost 检索；`entity_name!: string`，`project_name!: string`；`filters: object={}`；`sort_by: string="started_at"`；`sort_direction: string="desc"`；`limit: integer=10000000`；`include_costs: boolean=true`；`include_feedback: boolean=true`；`columns: array<any>=[]`；`expand_columns: array<any>=[]`；`truncate_length: integer=200`；`return_full_data: boolean=false`；`metadata_only: boolean=false` | JSON string，顶层 `metadata` 与 `traces`；metadata 有 total_traces/token_counts/time_range/status_summary/op_distribution；traces 可为 null、WeaveTrace 或保留的 dict | 当前无已核使用；未来 LLM 可观测性、评测样本/父子调用、成本与性能分析。`W:server.py:73-113`；说明 `mcp_tools/query_weave.py:11-278`；`weave_api/models.py:108-157` |
| `count_weave_traces_tool` / 读 | count/root count；`entity_name!: string`，`project_name!: string`；`filters: object\|null=null` | JSON string `{total_count,root_traces_count}`；同条件先 count 再强制 trace_roots_only=true count；错误为普通字符串 `Error counting traces: ...` | 当前无已核使用；用于查询规划、父子覆盖和结果完整性检查。`W:server.py:116-141`；说明 `mcp_tools/count_traces.py:14-114` |
| `create_wandb_report_tool` / 写 | 保存已提供文本与 HTML；说明要求用户明确要求保存报告并返回链接。`entity_name!: string`，`project_name!: string`，`title!: string`；`description: string\|null=null`；`markdown_report_text: string=""`；`plots_html: object<string,string>\|string\|null=null` | 普通 string，`The report was saved here: <url>`，附 processing details；不是裸 URL 或自定义 success JSON；依赖项目、run、媒体、report/view | 当前需求未要求 W&B 写；未来实验比较、研究归档、跨服务交付。`W:server.py:156-184`；说明 `mcp_tools/create_report.py:22-79` |
| `query_wandb_entity_projects` / 读 | 发现用户/团队项目；`entity: string\|null=null` | dict：entity 名映射项目列表，每项 name/entity/description/visibility/created_at/updated_at/tags | 当前可能发现项目但无轨迹实证；未来多团队、多项目和权限定位。`W:server.py:187-189`；`mcp_tools/list_wandb_entities_projects.py:6-104` |
| `query_wandb_support_bot` / 原生生成式问答 | W&B Models/Weave 产品帮助；`question!: string`，无 history/entity/project 参数、无长度下限或 maxLength | dict `{answer,sources}`；sources 保证 list 外形但内部项未强类型验证；answer 值原样转交 | 当前无已核使用；未来版本化文档、SDK 排错和产品能力帮助。`W:server.py:192-194`；`mcp_tools/query_wandbot.py:7-133` |

**说明与实现差异（F）必须入契约样例：** GraphQL 文案 items_per_page=50，注册签名=20；Weave 文案 limit=None、return_full_data=True，签名为 10000000/False；count 文案开头声称 storage bytes，实际只返回两种计数；项目列表文案同时允许不传 entity 和要求先向用户取得 entity，但实现 null 时会查询 viewer 的 entity+teams；报告文案不建议 JSON 字符串，handler 却尝试 json.loads。这些不是让模拟器自选“合理默认”的理由。

全部原始说明可按 AST 常量核对，其字符数分别为 GraphQL 23780、Weave query 14294、count 4300、report 2612、entity projects 1484、support bot 903。长说明、例子中的工具别名拼写和错误建议属于 agent 可见输入；不能在统计工具数时漏掉，也不能因过长擅自缩写。精确 `title/anyOf/additionalProperties` 等 schema 元数据仍需固定 Pydantic 版本下的安全 tools snapshot；本阶段没有声称已取得该运行快照。

### 2.2 输出、错误、资源与协议

上游锁 MCP 1.3.0 的 [发布包](https://pypi.org/project/mcp/1.3.0/) 源码已只读核对：`mcp/server/fastmcp/tools/base.py:53-65` 用 Pydantic `model_json_schema()` 从签名构建输入；`fastmcp/server.py:542-564` 将 dict JSON 化、string 保留，最终均为单个 TextContent。该服务没有主动返回 image/audio/resource 内容、outputSchema 或 structuredContent。GraphQL JSON dict、Weave JSON string、报告普通 string 应分别比较内部数据，但 MCP 最外层都是 text。返回类型注解不等于强制输出校验。

同包 `mcp/server/lowlevel/server.py:409-420` 把正常返回包装为 `isError:false`，异常包装为 text+`isError:true`；`fastmcp/tools/base.py:71-83` 增加工具执行错误前缀。因此 report、Weave query、entity 异常走 error content；GraphQL 自行捕获的 `errors`、count error string、support bot answer error 则可以是 `isError:false`。unknown tool 也经框架异常路径返回，不能改为统一 JSON-RPC unknown-method。参数 Pydantic 校验/JSON 预解析层与后端错误层必须分开；具体 coercion/unknown-key 行为以固定依赖反例校准，不能从手写签名推定 strict 拒绝。

源码没有 `@mcp.resource`、`@mcp.prompt` 或 resource template 注册。MCP 1.3.0 FastMCP 仍注册这些列表 handler（`fastmcp/server.py:172-180,214-235,510-527`），所以目标是空资源/模板/提示列表，不能宣称协议完全没有相应 capability。六工具默认一次列出；GraphQL cursor、Weave offset 是业务分页，不是 MCP tools/list 游标。实际 initialize 协商版本与依赖升级后的附加元数据为 U。

### 2.3 GraphQL 的真实开放面与自动分页

`query_wandb_tool` 无 AST read-only 检查、无 query 名允许列表，说明明确提 query/mutation（`W:mcp_tools/query_wandb_gql.py:98,223`），实际 `api.client.execute` 直接执行。**不能称 GraphQL 只读。** SDK 0.19.8 存在 `upsertBucket`、`deleteRun` 的真实操作定义，见 [runs.py:513-555](https://github.com/wandb/wandb/blob/v0.19.8/wandb/apis/public/runs.py#L513)；workspaces 0.1.12 定义 `upsertView`。这些证明合理写状态族及后端操作样例，并不证明当前租户准许全部 mutation。完整 schema、mutation 参数、权限、nullability、enum、对象删除影响仍须未来在受控后端冻结；不凭工具 description 猜全平台功能。

支持核心需要真正解析 selection sets、别名、变量类型、fragment、JSONString、嵌套对象/连接和 GraphQL 错误，不能按字符串关键词返回固定字典。实体同名、run `name` ID 与 `displayName`、summaryMetrics/config JSON string 和 history 数据必须区分；文案常见 8 字符 run ID 不是 wrapper 的格式校验规则。Reports、artifacts/files、registry 关系和 sweeps 等属于未来合理查询边界，不因三个任务只比较指标而省略状态模型。

分页是 wrapper 算法而非透明后端行为（`W:mcp_tools/query_wandb_gql.py:525-994`）：

1. 初页复制 variables，寻找 limit/first/count 键并调整值；没有时添加 limit，但初始 query AST 未自动增加 first 参数（592-620）。没有检测到 connection 会直接返回首结果，文案的“缺 connection 必定报错”不由此实现保证（636-640）。
2. 检测所有 `edges/pageInfo{endCursor,hasNextPage}` 路径，但只聚合第一条（642-645）；后页 AST 可能给多个路径加参数（713-721）。嵌套在 list 内路径、alias/fragment、多连接共享 cursor、已有 first/after 字面量或其他变量名需专项反例，不能承诺通用自动全分页。
3. 按 node.id 去重，缺 ID 时保留；max_items 截断并可能把 hasNextPage 强制 false（667-707,790-814）。这不是后端无更多数据的证明。
4. 初始解析/请求错误返回 errors；后页失败可能只留下局部结果、日志及改写 pageInfo，未把错误全部显式传回（762-877）。应保留真实包装做兼容回归，但训练和独立 oracle 不能把其作为全集。
5. 没有区分 mutation 后再分页：若 mutation 返回可分页连接，重发整个操作存在再次副作用的静态风险，尚无真实执行记录。未来差分须先选不会破坏共享资源的隔离样例；模拟 profile 不能静默把非幂等操作改为幂等。

### 2.4 Weave、报告和支持机器人的细化边界

**Weave（F）：** query 用 50 条 chunks，offset 聚合；metadata_only 仍取回原始数据再计算，total_traces 是本次取回集合的大小（`W:server.py:90-105`；`weave_api/service.py:595-653`；`processors.py:324-334`）。token_counts 对 inputs/output 的字符串表示做 tokenizer 计数，不是模型实际计费 usage（processors.py:111-176）；latency/status 还有 synthetic 投影。

**成本排序的条件化缺陷（F/U，WB-01）：** 首阶段按 `started_at desc` 一次请求最多 1000000 条、`columns=["id","summary"]`、`include_costs=true`，直接使用客户端原始结果（`weave_api/service.py:699-713`）。但 `TraceProcessor.get_cost` 只读顶层 `costs`，没有可转换成本时返回 `0.0`（[processors.py:472-496](https://github.com/lockon-n/wandb-mcp-server/blob/83f6d7fe2ad2e6b6278aef4a792f35dd765fd315/src/wandb_mcp_server/weave_api/processors.py#L472)）；因此 `is not None` 条件不排除缺失成本或零成本行（service.py:720-724）。若响应仅有嵌套 `summary.weave.costs`，所有排序键均为 0，Python 稳定排序保留首阶段响应次序，再据此选 ID 取详情；不能称为正确的成本 top-k。顶层有效成本会参与排序，但仍受百万候选上限及两阶段快照差异影响；若顶层与嵌套同时存在，首阶段只使用顶层。实际后端在上述 columns/include_costs 条件下返回何种形状仍 U，此结论是固定源码的条件推导，不是已观测故障（service.py:726-782；共享 F29）。

**trace 身份与时间投影（F/D，WB-02）：** call/span `id`、整条调用链 `trace_id` 和父调用 `parent_id` 的字段语义不同，字段值不要求两两不同。固定处理器在缺 `trace_id` 且有 `id` 时回填 `trace_id=id`；缺 `started_at` 时补 `datetime.now().isoformat()`，非法 ISO 时间字符串转换失败时补 `datetime.now()`（[processors.py:406-426](https://github.com/lockon-n/wandb-mcp-server/blob/83f6d7fe2ad2e6b6278aef4a792f35dd765fd315/src/wandb_mcp_server/weave_api/processors.py#L406)）。这些兼容输出不证明真实 trace 身份或发生时间改变；columns 省略字段也可能触发回填。D：权威 trace 图分别保存三字段和原时间，parent 不能指向自身、父子边须合法且无环；回填与 now 只作用于响应副本，记录所用时钟值供回放，不能倒灌权威状态。

query 的直接 filters 为 trace_roots_only/op_names/op_names_prefix/trace_ids/trace_parent_ids/parent_ids/call_ids，singular op_name/trace_id 转换；复杂 filters 包括 op_name_contains/display_name/display_name_contains、status、time_range、wb_run_id、latency、attributes、has_exception（`weave_api/query_builder.py:146-407,410-516`）。attributes 支持点路径和比较；数值比较转换 double；lt/lte 由逻辑 not 组合实现。时间为 start 包含/end 排除、秒精度；非法日期返回 0 并可能被忽略。通配符被转 contains，不能称正则引擎。status 实际比较 `summary.weave.status`，has_exception 比较 exception null，二者不应当同一条件。

count 对 op_names/trace_ids 合并，另支持 input_refs/output_refs/wb_user_ids/wb_run_ids（`mcp_tools/count_traces.py:192-269`），与 query 的映射并不完全相同。只在归一后的相同有效 predicate、权限和快照下要求 query/count 一致。忽略未知 filter、无效列转 warning、fallback sort 和 $contains 分支的实际偏差见第 6 节，不另造超出源码的“智能纠错”。

**报告（F）：** plots_html 字符串先解析 JSON，失败时作为 raw HTML 放入 chart；JSON 解析结果没有先保证是 dict，某些合法 JSON 字符串可能到 `.items()` 才失败（`W:mcp_tools/create_report.py:106-150`）。Markdown 只识别 H1/H2/H3、TOC 和合并段落（247-287）；不是完整 Markdown 渲染，也不负责写分析结论。`edit_report` 函数存在（198-244）但未注册为 MCP 工具；不能增加同名可见工具。

workspaces 0.1.12 [发布包](https://pypi.org/project/wandb-workspaces/0.1.12/) SHA-256 `a59767794ab13ea3d5cbbc7cef5ca55c370497c7c81834b30ab6005ebe318e1c`；`reports/v2/interface.py:3045-3078` 的 save 会检查/必要时创建项目，再经 `gql.upsert_view` 保存 view/spec，URL 由 id 与 app_url 派生（3021-3043）。这种源码允许的项目创建是合法副作用，不能与模拟器任意补齐资源混为一谈。`wandb.init/log/save/finish` 不是一笔整体事务；异常路径无 finally finish，可能留下 run/media/已建项目。HTML 可是本地路径：SDK 0.19.8 `html.py:29-37` 对存在的字符串路径读取文件，随后注入样式、写媒体临时文件。应纳入 workspace/blob 路由及字节验证，不能只保存参数字面量。

**支持机器人（F/U）：** `/status` timeout=20 秒，query timeout=40 秒；status JSON 缺 initialized/无法解码、offline、query 缺 answer/sources、请求超时/HTTP 异常都有不同 answer 文本，sources=[]（`W:mcp_tools/query_wandbot.py:36-133`）。sources 非 list 时包为 list，answer 类型未再校验；没有真实对话持久化接口。默认 hosted backend 的具体模型、文档版本、引用项内部格式、检索覆盖与收费尚未核验。[官方 WandBot 仓库](https://github.com/wandb/wandbot) 当前 README 描述检索、query enhancement、rerank、回答生成等模块，但不能把该 HEAD 或其模型配置当作固定 Modal 部署的版本。客户端 10 秒 timeout 与内部 20/40 秒并不一致，需分别测 harness 超时和后端运行结束，不把超时当作业务未发生。

## 3. 领域状态模型

以下为 D，除明示源码字段外不是对全部 SaaS schema 的断言。每资源主键同时带不可由 agent 任意指定的 episode/generation，外部可见 ID 保持服务形状。

| 实体与持久化真值 | 关系、不变量和派生值 | 多入口需求 |
|---|---|---|
| Principal、Entity、TeamMembership、Project | user/team entity、角色、项目 visibility、成员与对象 ACL；项目名在 entity 内解析，显示名不等于身份；时间/权限版本单列 | viewer、projects、GraphQL、SDK 同一权限视图；不可见对象不从目录泄漏 |
| Run、Config、Summary、HistoryRow、RunEvent | run ID、内部 GraphQL id、displayName、state、group/jobType、tags、notes、created/updated；history 保存 step/timestamp/typed values 与缺失；summary 的生成策略或显式更新独立保存 | GraphQL raw JSONString 与 SDK dict 是同一值的不同投影；history/scan/sampled 共享行真值 |
| ArtifactCollection、ArtifactVersion、Alias、ArtifactFile、RunArtifactEdge、RegistryLink | 版本内容 digest、类型、state、file path/size/bytes、别名指向版本；输入/输出 run provenance、registry link；删除/alias 迁移按已核 profile 维护引用 | GraphQL metadata/files、SDK download、HTTP 签名/本地 URL 指向同字节；不能 URL 成功但对象不存在 |
| Sweep、SweepRunEdge | config、状态、关联 runs；读取 sweep 不表示执行了超参搜索；状态只有真实执行事件或已验证的初始化历史推进 | GraphQL/SDK 可查询已记录实验；启动训练/Launch/scheduler 若未实现明确不支持 |
| ReportView、Block、PanelGrid、Media、ReportRunLink | report id/name/title/description/spec/revision；有限 Markdown 投影、媒体键、HTML 输入/加工后 bytes；每次合法创建分配身份 | create tool、GraphQL view、workspaces from_url、媒体 HTTP 共用；报告输入内容不被自动改写 |
| WeaveCall、TraceTree、OpVersion、ObjectRef、Feedback、CostRecord | 分别保存 call id、trace_id、parent_id、project_id、op URI/version、原 started/ended、exception、inputs/output/attributes/summary、wb_run_id/user_id、deleted_at；字段值不强制两两不同，parent 不得指向自身，合法父子边无环，跨 run 映射显式 | stream query/count、expanded refs、SDK 使用同一真值；响应中的 trace_id/now 回填不改真值；删对象是否仍可展开按后端 profile 校准 |
| SupportCorpus、DocumentVersion、SourceSpan、ServiceStatus、AnswerRecord | 文档版本/hash/URL/片段、检索索引版本、状态故障计划；回答关联 question、来源、模型/prompt/validator、输出 hash；生成记录不写实验状态 | support tool 和本地 support HTTP 共用；没有向该工具加入私有 run 查询入口 |

计数、过滤、排序、聚合、URL 和 token 统计可以派生，但必须携带所用状态版本；不能让摘要成为真值。Run history 不能用 summary 的最后一个值代替，也不能把缺字段、null、零、NaN/非有限数约定混在一起。MCP description 中的 summary/history 例子可能与实际后端演进不同，未来以确定 SDK+schema+差分记录确定类型。

报告是多提交边界：项目检查/创建、run 创建、每份媒体上传、report view 保存、run 完成分别记事件。中途出错只保留确已提交的前缀；不能假设自动删除 run，也不能自动重试创建时消除重复报告。并发时 SDK 全局 active run、缓存、环境变量和 Weave 全局 TraceService 是进程边界风险，优先隔离 server/session，身份由 gateway 绑定，避免在同一进程动态切换不同 episode 的全局认证。

时间设计保存原始时区/精度和规范化 instant，日志异步到达、媒体上传完成、索引水位、run state 与 heartbeat 分开。Weave 已有 trace/evaluation 结果是记录数据，可合法预生成完整历史；对 agent 新请求执行训练、调用模型或评测，必须有对应执行组件/提交的运行结果，否则明确不支持，不能将预生成数值伪装成刚刚执行。

## 4. 代表性交互序列

以下 D 均超出固定答案轨迹；每序列可变换合法工具顺序，并由独立状态导出验证。涉及未来真实写入仅列计划。

| 序列 | 断言与错误恢复 |
|---|---|
| 项目发现 → 相似 displayName 过滤 → 单 run ID 读 → GraphQL 更新 tags/config → SDK 再读 → 删除 run → 目录/关联再查 | displayName 可重名；ID 稳定；更新只作用授权 run；被删资源和 artifact 关系按冻结删除策略变化。错误 run ID 不自动创建；先修正参数再执行 |
| 多项目 GraphQL alias/fragment 查询 → max_items 分页 → 对目标对象逐个操作 → 交换发现工具顺序 | 底层 connection 与 wrapper 聚合分别断言；首连接/多连接缺陷不能被全集 oracle 隐藏；批处理 partial failure 不误当整体成功 |
| SDK 初始化/日志历史 → MCP 查询 summary/history → SDK scan_history → 改稀疏 metric 与采样策略 | exact scan 的行集/step 与 sampledHistory 区分；相同 step 跨多个 run 不合并身份；未产生训练事件不凭空出现新指标 |
| GraphQL artifact 元数据/版本与 files → HTTP 获取字节 → 给 HF/Notion 传递引用或复制 → 更新 alias 后再读旧版本 | digest/文件 hash 一致；引用与复制不同；跨服务 ACL 不继承；旧版本内容保持，失效 URL 不返回假成功 |
| 创建含 text+多 HTML 图的 report → GraphQL/SDK 查询 view → 按媒体 URL 读取 → 改 report 再读 | Markdown 投影、panel/media 键、真实 run 副作用符合源码；修改只能经已支持的 GraphQL/SDK，不虚增 edit MCP 工具；没有 LLM 代写结论 |
| report 第 2 份媒体上传失败 / save 后响应丢失 → 查 run/media/view → agent 判断再提交 | 已成功的前缀保持；后续失败不回滚全部；重复提交按真实非幂等语义产生结果。验收检查未 finish run 与重复 report，不依赖成功文案 |
| Weave count → 按 root/parent/call_id 查询 → 选 columns → expand refs → 成本排序 → 比较反馈 | 同等 effective predicate 的 count/query 关系成立；metadata 为返回子集；分别断言 WB-01 的成本形状/排序及两阶段快照、WB-02 的响应回填与未变权威 trace 图；status 和 exception 条件不硬等价 |
| 受限主体读不可见项目 → 有权主体/正确项目操作 → 支持机器人询问该版本 API 用法 → 重试原合法调用 | 只允许任务明确授权的身份；bot 能解释公开 API 用法，不能透露隐藏资源、评分答案或替 agent 改调用；问题本身不能给额外 ACL |

## 5. 候选实现与推荐

| 路线 | I/S/C/T/D/P 影响 | 开发、运行与维护取舍 |
|---|---|---|
| 保留固定 MCP、替换本地 Models/Weave/support HTTP | I 最易保持说明/包装/分页 quirks；S/C 仍需完整核心 resolver、SDK 传输和 blob；T 必须独立 ACL/异步；D 可扩展；P 受 wrapper 全量聚合影响 | 固定协议维护少，但 GraphQL+SDK run/file-stream/media 后端成本高；Weave URL 钩子缺口必须显式 transport 适配 |
| 有状态 MCP facade + 共用本地 HTTP | 可准确复刻六工具并保持 X 同态；容易按 profile 管理不支持；若只做 MCP 不做 HTTP，C 明显失败 | **首选 D**：代码业务内核，M façade 或保留可复用 wrapper，必要 SDK/HTTP 接同一状态；独立双契约回归防漂移 |
| SDK/client 适配 | 减少早期完整 HTTP 协议成本；X 的方法、分页和返回对象仍要匹配；任意 SDK 版本/CLI 不自动覆盖 | **备选 D**：固定 0.19.8/0.21.1 方法族适配用于过渡，保留方法/版本 manifest；不能用 monkeypatch evaluator 直接返回参考答案 |
| 官方 W&B Self-Managed | 实际业务服务可减少语义复刻，Models/Weave 仍需与 MCP 基线版本对照；episode 重置/clone/ACL 扩容不自动解决 | 官方 [要求文档](https://docs.wandb.ai/platform/hosting/self-managed/requirements)说明需要有效 license、Kubernetes、MySQL/Redis、对象存储，Weave 另需 ClickHouse；不是可无条件替换的轻量免费模拟器。许可证、版本、隔离和规模成本待确认，不在本阶段部署 |
| 普通关系库/JSON store、现成实验追踪软件 | 只可复用存储/事务/对象存储；不能据相似实体名认定兼容 GraphQL、Weave、报告 | 不推荐把 MLflow 等产品直接称作 W&B 兼容后端；本次未核实到覆盖六工具及 X 的即用模拟器 |
| 静态 fixture/真实回放 | I 适合 golden/error 样例；S/C/T 对新组合失效；D 有模板泄漏风险，P 高 | 仅作脱敏记录/差分/回放辅助；不得固定 query→答案或绑定 finalpool 次序 |
| LLM 主导响应与状态提案 | 自然语言 D 较强，原生 bot 可探索；GraphQL/计数/历史/ACL 的 I/S/C/T 仍需完整外部校验，P/稳定性受模型制约 | 不推荐全六工具在线 LLM；否则状态/解析校验成本没有省下，还增加每次查询成本 |
| 混合 | 非生成读写走代码，初始化内容可 LLM，support bot 用确定性检索/缓存与受来源约束生成 | **整体推荐 D**；按同语义验收比较有效轨迹成本，若 bot 无净收益保留代码答案路线 |

目标向量分别为：I 固定六工具与依赖后可准确；S GraphQL 已验子 schema/Weave/报告可准确、长尾分期；C 范围内 MCP+SDK+HTTP 可准确、完整 CLI/UI 为 U；T 核心 ACL/时间/失败可准确，云端最终一致与限额为近似待校准；D 多 seed/业务文本可丰富，真实分布未测；P 设计可扩展但尚无吞吐数据。此向量与总体报告相同含义，不能据文档完成称运行高保真。

## 6. 保真缺口与取舍

| 能力/差异 | 类别与证据 | 错误学习风险及控制 |
|---|---|---|
| 六工具契约与包装 | 可准确，固定 W server+MCP 1.3.0；实际运行依赖 U | 错误默认、改 JSON 层级或漏说明导致参数/工具选择变化；双快照、每字段负例 |
| 完整 GraphQL schema 与 mutation | 分期/U；wrapper 是开放操作字符串，不能穷尽后端 | 关键词“query”替代真正执行、mutation 假成功；明确支持的 types/fields/args/input/enums/mutations，不支持走可识别模拟错误，不能空结果 |
| GraphQL 自动分页 | 源码可复现；多连接/fragment/list/固定 after/截断/后页失败需运行反例 | 将 partial 当全集、重复 mutation；oracle 查独立底层集合，缺陷样例隔离，不静默修复 profile |
| history/summary/sample | 原始行可准确；采样/压缩/异步汇总近似需校准 | 用 sample 证明最优值、缺字段自动补零；使用 exact scan 样例与独立稀疏矩阵，采样带独立策略版本 |
| Weave filters/status | 可复现 wrapper；`query_builder.py:221-257,321-395` | description 把 status 与异常混为一谈；日期错而过滤被忽略；单键 attributes `$contains` 先落入比较分支，但 create_comparison_operation 不实现 contains（71-119,328-358），可能被忽略。此为静态缺陷发现，尚无运行验证；显式对比 effective predicate |
| Weave query/count filter 分歧 | 可复现，`query_builder.py:434-516` 对比 `count_traces.py:192-269` | 认为所有 filters 在两工具含义一致；对 input/output refs、wb_user_ids/run_ids、op pattern 分别验；只有等价条件才用计数守恒 |
| 列投影/排序/limit | 可复现部分；service.py:92-206,238-317,599-608 | 无效列被 warning 代替，转换为 WeaveTrace 时可丢额外字段；无效 sort fallback；limit=0 按 truthiness 变成不限而非零行。版本隔离、边界与输出快照 |
| Weave 成本排序 WB-01 | 条件化源码缺陷已核，后端原始形状 U；service.py:699-782、processors.py:472-496 | 顶层 costs 读取与 id/summary 首阶段不匹配；缺失/零均为 0.0，不能宣称筛掉无成本；仅嵌套成本时按首阶段次序选 ID，未保证成本 top-k。四类成本反例与独立真值排序分别验证兼容投影/业务偏差，不只测百万候选上限 |
| Weave 身份/时间回填 WB-02 | 可复现处理器分支；processors.py:406-426 | 将回填 trace_id=id 当权威链身份、将 now 当真实开始时间会破坏追踪；columns 省字段、缺时间与非法时间字符串分别测试。响应副本可回填，权威字段/parent 边/原时间不被改写，图仍无自父与环 |
| Weave metadata/truncation | 可复现但不是平台计费语义；processors.py:131-176,324-365,420-459 | 把 tokenizer 统计当 billing tokens；截断 ID/值当完整事实。权威状态保留原值，兼容投影、每次 now 观察值和时钟映射可重放 |
| report 处理/项目自动创建/媒体 | 核心可准确；真正页面渲染、SDK 后台上传结束条件与全 spec 为分期/U | 报告无副作用、HTML原样保存、失败全回滚等错误规律；逐提交故障和 bytes/hash/SDK readback；不按标题去重 |
| Weave refs/成本/反馈 | 状态可准确，expanded refs 和 SaaS 定价历史细节需差分 | 伪造模型调用结果、随意更改 costs；保存输入/输出/usage/price provenance；无执行组件就不接执行任务 |
| 权限/一致性/限流 | 核心约束可准确，租户政策/plan/精细错误 U | 所有人全权、列表隐藏等于禁止 ID 读、重试必成功；按主体/资源/操作矩阵和虚拟故障校准，不写死一个公共频率 |
| 原生 support bot | 契约可准确；回答相关性/覆盖/文风/延迟为近似/U | 模型从问题编不存在资源、假来源、越版本回答、过度解题；仅版本文档来源、独立事实核验与盲审 |

源码已存在的弱校验不是模拟器额外容忍非法参数的授权：忠实 profile 要记录被忽略/转换的路径，修正 profile 要另命名。已支持范围不应返回 mock 自创“成功”；未实现的真实合法能力使用单独可识别不支持错误并在 manifest 中标明。不能因为实际 wrapper 某些错误返回普通文本，就把“不支持”藏成空项目/零计数。

WB-01/WB-02 的 D 政策：`wandb-mcp-83f6d7f-compat` 按真实首阶段响应复现顶层成本读取、缺失归零、稳定排序及身份/时间回填，轨迹标记缺陷条件和偏差，不把兼容通过当业务成本排序或 trace 身份正确。`wandb-mcp-fixed-<revision>` 只能在未来实际修复并经过差分后启用；需先核定成本来源/缺失与零的区别，再定义排序、字段缺省和非法时间处理，不在本文假定修复后规则。两类 profile 都禁止回填写回权威图，保留独立成本/trace oracle；本阶段仅修正文档，没有修改 wrapper。

## 7. LLM 仿真可行性

### 7.1 职责与一致性

代码主导可可靠实现参数投影、GraphQL AST/类型/resolver、数值/排序/分页、ID/ACL、report parser、媒体字节、状态提交和重放。LLM 适合初始化组织背景、run notes、已有报告/实验说明、trace 内非结构化业务文本，以及原生 support bot 的解释性回答；初始化生成指标也必须受生成模型约束并标为历史初态，不能冒称执行实测。

LLM 主导方案可在有限 schema 内提出字段选择或变更，但不能仅凭历史聊天维持世界：调用+鉴权后的相关状态 → 有来源的响应/受限 patch 提案 → 独立 schema/权限/引用/数值/版本检查 → 按真实提交单元执行 → 从提交态渲染。GraphQL 结果必须来自确定性 resolver，LLM 无权决定过滤真值；将每个结果重新验算的成本接近代码实现，故不推荐用它替代核心查询。报告工具只存储/转换输入，不增加 LLM 代写分析；若用户已提供不存在的 HTML 文件路径，应保持该 SDK 的输入处理结果，不能悄悄创造文件。

相关状态检索按 GraphQL selection+predicate、ACL 与 cursor 快照取得完整候选集，直接读取带父级与版本；Weave 要含 parent/ref 依赖、实际有效 filter、sort 候选。大状态使用索引与 blob 引用；分页结果过大交确定性路径或明确资源限制，不把截断摘要当全集。提案不能对未读取对象写入；冲突废弃提案、重取版本，再按真实并发语义处理。内部修复最多 1 次（A），只修提案结构，不修 agent 原始非法操作；失败不提交并单列为仿真故障。

支持机器人只需要冻结语料、文档来源、服务状态与已生成答复日志，不需要项目业务 patch。每句涉及产品事实的回答需来源 span 与文档版本；URL 存在和 span 对应由代码检查，**“引文存在”不等于“引文支持结论”**，语义支持由独立审定事实集、不同评审者/人审检查。不能向 bot 提供隐藏评分目标、实验答案、最优调用轨迹或私有 run 状态；正常产品文档中的代码用法和错误排查属于原服务职责，可以回答。

重复资源读取要求同一状态一致；原生生成式问答允许措辞变化，但事实、来源与服务版本不能漂移。回放直接使用保存的 AnswerRecord，不重采样。cache key 含 profile、corpus/index 版本、question、必要身份/权限语义、服务状态、模型/prompt/validator 版本；改变语料或权限后旧答复不跨版本混用。业务文档中的指令文本不能改写模拟器规则。

### 7.2 三路线成本与规模（A，非测量/报价）

| 路线 | 每工具额外模型次数与上下文规划 | 相对成本 |
|---|---|---|
| 纯代码核心+检索模板 bot | 核心 0；bot 0 生成调用，检索可用本地词法索引；若选 embedding/reranker 另计 | 固定规则/GraphQL 开发成本高但调用成本低；模板覆盖长尾问题可能不足，需把拒答计入有效率 |
| 全部 LLM 主导 | 典型 1 提案 + 平均 r 修复，若另用模型验证再加调用；相关状态可从 4k 增到 32k+ token，图/历史不适合塞满上下文 | 初期样例快，但校验器仍需业务规则；重复查询有模型费和幻觉废弃成本，长期通常更贵，需实测而非先验认定 |
| 推荐混合 | 核心 0；只有 support bot miss 进入 1 次生成+至多1修复；规划 2k–16k 输入、0.5k–2k 输出；初始化长文提前批量生成 | 把模型花在原生生成行为，缓存和代码快速路径降低调用比例；检索、验证、人审、失败重跑不能漏计 |

设 N 为工具数、f 为在线 LLM 比例、h 为同版本合法缓存命中率、r 为平均额外修复次数，模型费 `N*f*(1-h)*(1+r)*(Tin*pin+Tout*pout)/10^6`。若每次加独立模型评审，单独加其 token 与调用项，不能免费计算。总成本还包含开发/维护、CPU/DB/blob、语料准备/embedding、人工盲审和失败废弃；比较单位应是**通过独立验收的轨迹**。

示例采用共享文档的虚构价格 pin=$2/M、pout=$8/M；bot Tin=6000、Tout=1000、r=0.1、h=0，则每 LLM bot 调用约 $0.022；100 万总工具调用且 f=5% 时约 $1100，全部进入模型约 $22000。这不是供应商报价或测量。Tin 翻倍使输入部分翻倍；若需要 query expansion/rerank 模型、审查或重试，按实际链条增加。规划模型往返 3 秒、100 tool/s、f=.05、r=.1 时约 16.5 个模型在途；f=1 时约330，另有检索/排队尾延迟。相同问题在缓存全部命中时的漂亮数字不能替代未见问题成本。

记录每能力投入工时和每有效输出总成本；LLM bot 可能节省模板编写，但不能省语料/version、来源验证与盲测。降低成本顺序：初始化预生成 → 非生成确定性快速路径 → 版本缓存 → 独立 episode 批处理 → 通过保真门槛后再选模型 → 高频稳定行为转代码；不因吞吐目标删权限或来源检查。

### 7.3 原生支持机器人对照试点：确认总体与 validation 的范围

**确认采用总体/validation 选定的 `query_wandb_support_bot`（D），范围保持一个原生 question→answer/sources 工具及其两个 HTTP 路由。** 不新增报告代写能力，不代替 agent 分析私有 runs，不生成指标或执行结果。试点能比较自然语言响应的覆盖/开发工时/来源质量与长期合成成本；不能证明 LLM 的 GraphQL、SQL 或写事务正确性。

三组使用相同冻结文档 bytes、版本/date、候选来源集合、question 集、MCP/HTTP 输出包装和同一独立 oracle：A 代码词法检索+有限模板/原文摘录；B LLM 主导回答组织+确定性来源/契约外壳，检索预算明确；C 缓存/简单事实模板快速路径+检索到证据时 LLM 综合。若 B 增加 query expansion、embedding 或 rerank，计入资源并做同检索器消融，避免把检索改进误称为 LLM 生成收益。版本相同仍保持 question 结构与主题 holdout，不能仅替换实体名称。

| 试点分层 | 独立检查与不能忽略的失败 |
|---|---|
| 工具/HTTP 契约 | 六工具完整快照中该工具仍存在；只传 question/application；status initialized false/缺字段/无效 JSON、query timeout/HTTP错误/缺answer或sources、scalar sources 包列表均做黄金样例；错误包装与 isError 分层不改变 |
| 已知事实与组合问法 | 单段事实、跨段整合、API 参数比较、同义改写、多语言、合法公开排错；按问题所需事实清单计算完整率/正确率，不因少答就获得虚假低幻觉率 |
| 未见问题/错误前提 | 测试主题、文档版本和组合结构独立留出；不存在 API/参数、旧版和新版冲突、仅语料外可答问题、需要真实项目数据的问题；要求说明证据不足或缺数据，不自动编事实 |
| 引用与答案幻觉 | URL 必须属于 corpus、定位 span 必须存在、claim 必须被该 span 支持；人工盲审与独立事实标签查“真链接但不支持答案”、捏造方法名/默认值/指标；同 LLM 自评不算验收 |
| 注入与答案泄露 | 恶意文档段落、问题请求忽略规则或“伪造成功”，不获任务 groundtruth、私有 run 或额外工具；正常公开 SDK 用法可回答，不能用全面拒答掩盖功能不足 |
| 重复/版本/长序列 | 固定状态重复问答比事实和引用，不要求自由文本字节相等；录制重放必须字节/hash一致；变更文档版本后缓存失效；100–1000问长序列不得出现私有资源/世界状态漂移 |
| 质量/成本/迁移 | 同门槛下报告事实错误、遗漏、来源错误、适当拒答、错误拒答、过度解题、p50/p95/p99、模型次数/token/重试、人工成本、每有效回答/轨迹成本；按主题cluster给区间，未见集与缓存集分别统计 |

当前仅静态证明原生工具和 HTTP 契约，没有真实 hosted bot 响应记录。未来先取得受控且版本可标记的只读问答记录，校准回答长度、来源项结构、拒答/帮助程度和真实故障；冻结语料对照本身只证明受约束替代方案的质量，不证明 hosted SaaS 回答分布高保真。真实 bot 使用何语料/模型不可得时保留 U，不能给出伪造模型名、延迟或通过率。门槛依 [validation-plan.md](../validation-plan.md) G0/G4；若无独立质量/成本净收益，不保留在线 LLM 路径。

## 8. 合成、验证与分期

### 8.1 多样环境、任务与独立 oracle

按 seed/config 生成 0/1/页边界/多页的项目与 runs、不同长度的稀疏 history、多峰/非单调曲线、失败/中断/恢复 run、同显示名不同 ID、指标名近似、artifact 多版本与 alias、report/HTML 长内容、Weave 深浅 trace tree、缺失成本/反馈、ACL 和时间差异。不能每个环境只有一条最优 run、固定最高值位置、固定命名编码答案。Weave 状态同时含成功、异常、未结束 calls；cost/usage/feedback 需要内部一致，但指标分布参数是生成假设而非真实流量统计。

从状态生成任务时选业务目标谓词和授权范围；从任务约束生成状态时先证明存在合法操作路径，再加入不改变目标的干扰。任务生成器可保存私有期望结果，环境与 bot 不接收它。跨服务任务用 source resource/version/hash 标记复制或引用。任务允许 exact scan、GraphQL 过滤、其他合法多步路径得到相同结果，评测不要求固定工具顺序。

oracle 独立读取状态导出、history row/blob、图边/审计日志；不调用同一个 GraphQL resolver 自算答案。报告检查 view/spec、媒体实际字节与额外 run/project 副作用，不能只看 URL；指标任务由另写的精确计算程序读取原始行，以小型手算矩阵验证该程序。保留同名 run 分组、缺字段、tie-break、不同 step、summary 与 history 不同等反例。注入分页漏项、数值变动、错 alias、空成功、丢媒体、跨 ACL 读、bot 真链接假结论，要求 oracle 检出。

WB-01/WB-02 增补的独立反例（D，尚未运行）：下表的原始响应是显式构造的测试输入，不假定真实后端一定采用该形状。固定处理器输出与权威成本/trace 图分别验收；参考排序/图检查不得调用 `get_cost` 或复用被测投影函数。

| 反例 | 兼容输出预期与独立断言 |
|---|---|
| 顶层成本 | 首阶段顺序为 newer、older，`costs.model.total_cost` 分别 1、99，desc/limit=1 应选 older；同时提供不同嵌套成本时，兼容排序仍只读顶层。独立按原始顶层值手算；第二阶段按已选 ID 回读 |
| 仅嵌套成本 | 同一首阶段顺序，仅 `summary.weave.costs.model.total_cost` 含 1、99，兼容键均为 0，desc/limit=1 选 newer；独立成本 oracle 得到 older 更贵，必须检出业务排序偏差，不能把该差异规范化掉 |
| 缺失与零成本 | 一行没有 costs，一行有顶层有效 0；二者均保留且键为 0，稳定排序维持输入次序。独立真值分别标 missing 与 zero；缺失不得凭兼容 0.0 被写成实际零成本 |
| columns 省略 trace_id | 权威图含 root/child，共有真实 trace_id；响应 columns 投影只保留 child 的 id 而省 trace_id，处理器可回填为 child id。比较完整读取与列投影两输出，并核权威 trace_id、parent 关系及状态 hash 未变；parent 指自身/环仍须被独立图 oracle 检出 |
| 缺失/非法 started_at | 分别给省略 started_at、非法字符串、合法 ISO 三种原始投影；前两种按源码使用 now，第三种保持其 instant。冻结并记录每次 now 观察值，回放应复现响应；查询前后的权威时间/图不变，不能让回填改变后续过滤和排序 |

将四类成本形状与有/无指定 columns 交叉组合，并加入两阶段间资源变化、同键顺序与候选上限；compat 记录可预测缺陷，fixed 只按其未来已冻结的新契约验收。主训练采纳需独立评估这些缺陷轨迹的迁移影响。

### 8.2 验证分层与真实差分条件

| 层 | 本阶段状态 | 后续设计 |
|---|---|---|
| A0 契约/源码 | 六工具签名、处理路径、固定字节、部分依赖发布包已核 | 冻结实际 runtime 和空资源/提示快照；原始 MCP+模型可见输出双 golden；description/default 差异完整登记 |
| A1 现成真实记录 | 未找到可用 Toolathlon 轨迹 | 取得带版本/主体/前态的已有记录才复用；单响应不推断所有合法行为 |
| A2 受控真实差分 | 未执行 | 专用 entity/project、角色、对象/费用额度、允许操作清单；后续另行授权真实写入。先记录 backend schema/SDK handshake，再 core query/mutation/report 多提交/Weave/问答差分；不得触碰共享基准项目 |
| A3 状态/组合 | 设计未实现 | 参数 null/0/负数/极值、JSONString 类型、alias/fragment、多连接/页后错误、多步 report、中途网络丢失、Weave filter 等价域、WB-01 成本四形状及 WB-02 列/时间回填反例、snapshot读取，独立 invariant checker |
| A4 新结构/规模 | 设计未执行 | 未见操作图、30+ seeds、100–1000步、1→10→100→1000 episode 梯度；独立统计硬错误、数据分布、延迟/成本 |

差分映射保留 run ID/internal id/displayName 三者关系、report URL→view、Weave parent/trace/ref 图和文件 bytes；不能简单删除所有 ID/time。GraphQL 按 selection 的类型/字段/错误包装比较；集合只有无序契约才排序。时间保留原精度与边界，计数/step/digest 不使用宽松 epsilon；模型计费 costs 与 wrapper 浮点投影的容差分别定义。分页对后端真值与 wrapper 聚合分别判定，不把 wrapper 强制 hasNextPage=false 当真实全集。support bot 比事实/来源/帮助范围，不要求 SaaS 自由文本逐字相同。

### 8.3 隔离、恢复与优先级

共享机制可复用 episode principal 映射、事务/日志、虚拟时间、blob、版本 manifest、LLM 网关/来源记录；GraphQL resolver/schema、history/sampling、Weave filters/成本、报告 parser/spec 必须独立。按 episode 隔离 MCP 进程或固定会话，SDK缓存/API key/base URL 不混用；存储、游标、索引、签名URL、doc cache全部带 episode/generation。不可变语料/文件字节可内容寻址共享，但权限边不共享。

快照包含项目/ACL、history/summary、artifact aliases/bytes、report/media/run关系、Weave tree/ref/cost、索引水位、服务状态、虚拟时钟和模型日志。reset 换 generation 使旧 cursor/异步提交失效；崩溃恢复按每个真实提交边界复原，响应丢失不得自动再创建。大 history 用列式/分区读取、blob 流式传输；wrapper 的 metadata全扫描/成本百万候选限制单独计内存和吞吐，不能为扩容暗改业务结果。

| 批次/优先级 | 能力与迁移价值 | 扩大门槛 |
|---|---|---|
| P0 契约/核心共享状态 | 六工具可见性/说明/全部输入输出；项目/主体、run/history/summary、GraphQL类型与真正过滤分页、核心 mutation、report文本+媒体+副作用、必要SDK readback；包含写和错误恢复 | G0/G1：支持子 schema 清单与负例；真实差分尚无则不发高保真声明 |
| P1 多样领域与原生问答 | artifact/version/files/alias、sweep/registry读取及已核mutation、Weave query/count/ref/cost/反馈、跨服务文件/报告、多顺序组合；support bot三路线对照 | G2–G4：新结构、状态一致/隔离、独立问答质量与成本门槛 |
| P2 开放长尾与执行入口 | 扩展后端GraphQL types/mutations、完整历史采样策略、报告高级spec/浏览器、CLI写/完整上传、复杂Weave扩展、必要真实执行组件 | G5：先补固定schema、真实反例/执行产物和独立oracle再扩容；训练/Launch/在线模型执行不以LLM猜结果替代 |

本分期是交付 profile，不是永久忽略已暴露能力。所有六工具的目标边界及开放 GraphQL 长尾持续保留在矩阵和 U 清单；现有 finalpool 数量仅提供回归案例。

## 9. 待确认与审查记录

| 待确认/审查事项 | 需要的证据与处理 |
|---|---|
| 实际任务镜像 MCP/Weave/wandb/workspaces/MCP/Pydantic 版本与协商协议 | 离线读取安装 manifest；之后在隔离认证/无业务初始化环境采集全快照。当前仅固定源码/lock候选，不写“部署已核” |
| 完整 Models GraphQL schema、mutation、角色错误与并发语义 | 专用后端版本/租户下 schema snapshot、allow/deny矩阵、非幂等/部分失败差分；不从description推断完整平台 |
| GraphQL自动分页与Weave静态缺陷真实表现 | 多连接/fragment/已有cursor、attributes contains、status/exception、无效列和limit=0等受控反例；WB-01 首阶段 columns/include_costs 下的实际成本形状、WB-02 后端缺字段/非法时间是否可达仍 U；源码兼容和修复 profile 分开 |
| report真实后端范围 | 核对SDK上传/stream/签名URL、run状态/复用、项目创建、workspaces view回读、部分失败；明确每步提交，不能只有report表 |
| Weave URL共享与多入口身份 | 测 count/query/SDK 分别到本地同一episode；只设置 WEAVE_TRACE_SERVER_URL 不足已作为F报告给统筹 |
| hosted support bot来源/语料/模型/内部sources结构/分布 | 取得带部署时间的真实只读记录；官方 WandBot HEAD 不等于 hosted版本。总体/validation 原生工具试点范围已核对一致，新增严格来源支持与未见问题分层 |
| 现成自控服务与经济性 | Self-Managed license、版本、Weave支持/资源需求、episode clone能力及运维成本，均未部署核验 |
| 跨报告状态与公共发现 | 已向统筹提交：六工具、依赖锁/包装、Weave两URL、GraphQL分页缺陷、report run/media/project多提交；公共文档由统筹复核合并 |
| 非原作者交叉审查 | 2026-09-10，`/root/snowflake`，同一 `gpt-6-astra / xhigh` 会话（统筹核验）完成全篇审查；六工具全参数/说明/hash、三任务/SDK、MCP 1.3 包装、GraphQL 开放面/分页、报告多提交、候选与原生 bot 对照等无其他实质问题。作者仅修本文；最终闭环由统筹在 review-ledger 登记 |
| WB-01 / P2 / 已修订 | 非原作者发现且统筹重读固定源：service.py:699-735 的原始 id/summary 首阶段与 processors.py:472-496 顶层 get_cost/缺失返回 0.0；原文“筛掉无成本”错误。§2.4/§6/§8/CSV 已改为条件化排序缺陷，增加顶层/嵌套/缺失/零反例、独立 oracle 及兼容/修复 profile；后端实际响应形状与运行表现继续 U，共享 F29 已登记 |
| WB-02 / P2 / 已修订 | 非原作者发现：processors.py:406-412 在缺 trace_id 时由 id 回填，缺 started_at 补 now；420-426 对非法 ISO 字符串也补 now。已撤销三 ID 值必须不同的断言，§2.4/§3/§6/§8/CSV 区分权威图与响应副本，保留合法 parent/无自父/无环约束，增加 columns 省 trace_id 及缺/非法时间反例；真实可达性和时钟分布继续 U |

## 10. 能力矩阵行

```csv
object,tool_or_capability,version,operation_type,state_dependencies,proposed_method,llm_role,fidelity_gap,verification_method,priority,evidence
wandb,query_wandb_tool:GraphQL-contract,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,read/write/manage,GraphQL schema and principal and selected state,typed GraphQL engine plus MCP wrapper,none,backend full schema and runtime dependencies U,tools snapshot and AST/type negative cases,P0,W:server.py:144-153;W:mcp_tools/query_wandb_gql.py:565-634
wandb,query_wandb_tool:pagination,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,read/write,connection cursor and node ID and mutation effects,preserve fixed paginator plus authoritative backend,none,first connection only and truncation or later-page partial errors,differential multi-connection and fault tests,P0,W:mcp_tools/query_wandb_gql.py:636-888
wandb,Models:run-history-summary,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,read/write,project run ID displayName typed history and ACL,shared state and exact resolver/SDK adapter,initial notes only,history sampling and async summaries U,independent raw-row oracle and SDK scan cross-read,P0,W:mcp_tools/query_wandb_gql.py:75-116;tasks/finalpool/experiments-recordings/evaluation/main.py:88-132
wandb,Models:GraphQL-mutations,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,write/manage,typed input ACL run/project/view lifecycle,validated per-mutation state transitions,none,complete mutation schema and deletion/concurrency behavior U,controlled create/update/delete and independent state audit,P0,W:mcp_tools/query_wandb_gql.py:98;wandb0.19.8:apis/public/runs.py:513-555
wandb,Models:artifacts-registry-sweeps,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,read/write/manage,version alias digest file run links sweep and ACL,GraphQL resolvers plus versioned blob state,initial descriptions only,full resolver and execution lifecycle phased,alias/version/file hash and graph invariants,P1,W:mcp_tools/query_wandb_gql.py:19-33;W:mcp_tools/query_wandb_gql.py:455-489
wandb,query_wandb_entity_projects,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,read,viewer teams projects and ACL,preserve SDK projection from shared state,none,description vs optional entity and dependency project fields,viewer/team/project and ACL cross-read,P0,W:server.py:187-189;W:mcp_tools/list_wandb_entities_projects.py:52-104
wandb,query_weave_traces_tool,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,read,authoritative calls trace parent graph times refs costs feedback and effective filters,JSONL backend plus separate compat or future fixed projection,initial trace text only,WB-01 top-level costs only missing=zero nested-only keeps input order; WB-02 trace_id=id and now fallbacks are response-only; runtime shape U,four cost-shape counterexamples plus omitted-column and missing-invalid-time cases with independent raw-cost and trace-graph oracle,P1,W:server.py:73-113;W:weave_api/service.py:699-782;W:weave_api/processors.py:406-426 and 472-496
wandb,count_weave_traces_tool,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,read,calls parent IDs filters and ACL,query_stats against shared call state,none,filters differ from query and no advertised storage-size return,count conservation on equivalent predicates,P1,W:server.py:116-141;W:mcp_tools/count_traces.py:177-304
wandb,create_wandb_report_tool,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,write,project run media report view and ACL,deterministic parser plus multi-step persistence,none; no report ghostwriting,project/run/media side effects and HTML processing or partial failure,SDK/view readback and per-step fault injection,P0,W:server.py:156-184;W:mcp_tools/create_report.py:106-195
wandb,Reports:SDK-save-and-HTML,wandb0.19.8+wandb-workspaces0.1.12,read/write,workspace files media bytes view spec and project,SDK/HTTP transport and content-addressed blob,none,upload/stream/UI routes and dependency differences U,file hashes and project/run/view consistency,P0,workspaces0.1.12:reports/v2/interface.py:3045-3078;wandb0.19.8:sdk/data_types/html.py:29-74
wandb,query_wandb_support_bot,83f6d7fe2ad2e6b6278aef4a792f35dd765fd315,native-generation,question corpus version source spans and service status,code retrieval vs source-constrained LLM vs hybrid,public documentation answer only,hosted corpus/model/source item schema and distribution U,heldout facts/sources and blinded review plus HTTP error golden,P1,W:server.py:192-194;W:mcp_tools/query_wandbot.py:36-133
wandb,SDK-HTTP-multi-entry,wandb0.21.1+83f6d7f,read/write,episode principal same Models/Weave/report state,versioned SDK/HTTP adapters and explicit route bindings,none,count/query base URL mismatch and SDK global state,all-entry route audit and cross-read/write invariants,P0,configs/mcp_servers/wandb.yaml:4-16;W:weave_api/client.py:45-85;W:mcp_tools/count_traces.py:272-275
wandb,protocol-errors-resources-prompts,MCP1.3.0+83f6d7f,protocol,schema description content and handler registration,fixed MCP transport and dual harness snapshots,none,runtime negotiated version U and wrapped errors can be isError false,all-six tool/output/error snapshots plus empty lists,P0,mcp1.3.0:server/fastmcp/server.py:172-192;server/lowlevel/server.py:409-420;utils/openai_agents_monkey_patch/custom_mcp_util.py:176-229
```
