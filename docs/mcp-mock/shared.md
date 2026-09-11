# MCP 模拟环境共享事实与设计约定

查阅日期：2026-09-10。阶段：可行性分析与设计；不包含 mock 实现、真实业务写入或运行验证。统筹者维护本文件，领域作者仅维护各自服务报告。

## 证据等级与术语

- **F（事实）**：当前仓库源码、固定提交源码、发布包或明确记录直接支持；写明路径行号/固定 URL、版本与适用配置。静态注册不等于部署中运行过。
- **D（设计）**：建议的环境行为、架构和验收门槛，尚未实现或验证。
- **A（假设）**：成本、规模等规划参数；必须给出敏感性和验证方式。
- **U（待确认）**：没有账号工具快照、运行镜像、完整后端规范或真实调用证据，不能变成确定能力。
- **M 层**：该版本和配置实际暴露的 MCP 工具、资源、提示模板与协议能力。
- **B 层**：支撑 M 层合理操作所需后端语义；平台其余能力不是自动实现范围。
- **X 层**：初始化、评测、SDK、CLI、HTTP、浏览器等额外入口。与 M 层访问同一资源时必须使用同一权威业务状态。
- **profile**：版本、工具清单、权限/可见性开关、支持的语义范围与错误契约的显式组合。缩减 profile 只能作为阶段性交付，不能冒充全量兼容。
- **公网**：互联网服务访问；本机、Docker、内网不算公网。业务后端、agent 模型 API、仿真模型 API、安装下载、外部 URL 获取分别记录。

## 公共框架事实（F）

| 编号 | 结论与适用范围 | 源码证据 | 验证边界 |
|---|---|---|---|
| F01 | MCPServerManager 读取 YAML，以 name 注册，模板包含任务路径及配置；任务局部 token 配置覆盖全局。原始凭据不得进入分析产物。 | `utils/mcp/tool_servers.py:50-101,105-130` | 静态读取；不导入配置 |
| F02 | 当前 manager 创建 stdio/SSE client，工具列表默认缓存，超时可配置；远程 HF/Notion 经 stdio mcp-remote 桥接。 | `utils/mcp/tool_servers.py:72-99`；`configs/mcp_servers/huggingface.yaml:7-15`；`configs/mcp_servers/notion_official.yaml:7-14` | 不声称 manager 原生支持所有传输 |
| F03 | TaskAgent 连接声明的服务，再合并 needed_local_tools；枚举模型工具并记录名称、说明、parameters。 | `utils/roles/task_agent.py:465-551` | finalpool 声明是使用线索，不能替代上游完整注册清单 |
| F04 | 模型侧名称为 server-name + '-' + tool-name 再把连字符替换为下划线；真实 MCP dispatch 保留原工具名；冲突会报错。 | `utils/openai_agents_monkey_patch/tool_name_aliases.py:21-28,85-99`；`utils/openai_agents_monkey_patch/custom_mcp_util.py:123-150` | 本仓库 OpenAI Agents 路径，不外推其他 harness |
| F05 | schema 不含 properties 时补空字典，可选择 strict 转换；调用前按 schema 转回 JSON 字符串中的对象/数组/数值/布尔值。 | `utils/openai_agents_monkey_patch/custom_mcp_util.py:73-120,129-149,159-177` | 这是 harness 行为，不应归为真实服务容忍非法参数 |
| F06 | 返回给模型的是 content item 的 JSON 字符串，单项为对象、多项为数组、无项为 []；该转换没有单独序列化顶层 isError/structuredContent。异常转换为 AgentsException。超长内容写工作目录并截断。 | `utils/openai_agents_monkey_patch/custom_mcp_util.py:176-229` | 原始协议和模型可见输出必须分别验证，不能据模型输出推定原始顶层元数据 |
| F07 | 执行先准备 workspace/preprocess，随后加载任务 token 配置再连接 MCP；token 加载使用 exec_module，不能用 import 做只读能力扫描。 | `utils/roles/task_agent.py:983-1001`；`utils/data_structures/task_config.py:250-258` | 本阶段只用文本/AST/JSON 读取 |
| F08 | 安装脚本固定 Cloud、Forms、Sheets、Notion fork、Snowflake、W&B；GitHub 有 binary commit 记录；YAML 不一定将版本写进启动命令。 | `global_preparation/install_env.sh:202-209,239-243`；`package.json:24`；`local_binary/github-mcp-version.txt:1-5` | 设计基线不是已核实的运行镜像；领域报告核对具体版本 |

现有 `docs/mcp-analysis.md` 已阅读，仅作为线索。其旧 GitHub 任务成员与本次扫描有差异，不能沿用旧列表。当前工作树未发现适用 AGENTS.md（仓库及祖先目录、仓库内扫描），不运行安装脚本或初始化配置。

## 所有服务共同采用的保真标准（D）

保真以向量而非总分表示：**I 接口、S 状态语义、C 跨操作/跨入口一致性、T 身份时间、D 数据分布、P 规模性能**。各维度独立报告“契约可精确 / 限定范围可精确 / 近似 / 分期 / 待确认”，不要写未经验证的百分制分数。

| 维度 | 必须核对/设计的项目 | 改变 agent 学习规律的偏差 | 验收依据 |
|---|---|---|---|
| I 接口 | 原始/模型工具名、说明、schema/required/default/enum/校验；content 类型、必要元数据、错误层级、配置可见性、资源/提示模板、分页协议 | 改名/简写说明影响选工具；宽松参数导致错误参数学习；将 JSON text 换 object 改变解析任务 | 固定版本契约清单、配置组合、原始与模型输出双快照 |
| S 业务 | 实体关系、合法状态转换、删除引用、版本历史、计算/查询执行、批量操作的原子性 | 虚假写入成功、无状态读、伪造 SQL/代码结果 | 独立不变量检查、状态机与反例 |
| C 一致性 | 创建后读、搜索与直接读取、分页/排序/过滤/批量与单项操作、SDK/HTTP/CLI 同资源 | 搜索幻觉资源、跨入口不同 ID/数据 | 可交换操作/组合序列、多入口交叉读写 |
| T 身份时间 | 用户/组织/项目/工作区/角色、无权限与不存在、冲突、重复提交、时区/时间戳、并发、异步状态、限流 | 默认全权限、固定立刻成功、重试必然无副作用 | 权限矩阵、虚拟时钟、并发历史、可控故障 |
| D 分布 | 数量/层级/长内容/缺字段/历史/相似名/重复/干扰/权限/关联数据 | 模板名泄题、没有干扰、固定操作顺序 | 多 seed、分层分布指标、未见结构与人审 |
| P 性能 | episode 隔离/克隆/重置/恢复、吞吐/p95/成本、存储与模型瓶颈 | 为吞吐删约束导致隐性语义降级 | 独立报告性能，不以性能掩盖语义失败 |

未知工具及业务错误应保留已核实服务的真实错误层级；没有具体基线时才按协议规范设计 unknown tool。Calendar 1.0.2 和 Forms 固定 fork 的 handler 都会把 unknown tool 捕获成 text content + isError:true，不能强制改为 JSON-RPC error（见下文 F09）。已知但暂不支持的语义在 profile manifest 明示，并通过该工具真实错误包装返回可识别的不支持错误（若真实服务无对应错误，则标模拟器扩展错误，不能伪装真实错误）。**禁止返回 success 或空结果假装执行。** 最终设计边界仍包含已核实 MCP 的完整合理操作；分期支持必须保留缺口。

## 能力边界（F/U，完整逐工具清单见各服务报告）

| 对象 | 安装/配置基线 | M 层能力族 | 重点 X 层 |
|---|---|---|---|
| google-cloud | `7df9ca22115002e0cea75deec595492c520df3e1` | BigQuery/Storage/Logging/Compute | Google Cloud SDK、SQL、对象文件 |
| google_calendar | `@gongrzhe/server-calendar-autoauth-mcp==1.0.2` lock 基线；YAML 裸 npx，实际部署 U | Calendar/Event | OAuth 文件、Calendar API、时区 |
| google_forms | `96f7fa1ff02b8130105ddc6d98796f3b49c1c574` | Form/Item/Response | OAuth、Drive、HTTP 提交 |
| google_sheet | `mcp-google-sheets==0.4.1` | Sheet/Cell/Spreadsheet/Share | Sheets/Drive API、公式 |
| notion | fork `43f117584206cee47d939207ddbe1ac02732f865`；API header 2022-06-28 | OpenAPI Page/Block/Database/User/Comment | notion_client、远程 notion_official、Playwright |
| snowflake | `bca38f3ef5305ac53b9935bd09edbfac442b6a36`；allow_write | SQL/目录/业务资源 | connector/Snowpark、SQL 会话 |
| wandb | `83f6d7fe2ad2e6b6278aef4a792f35dd765fd315` | 实验/GraphQL/Weave/报告，含写 | SDK、GraphQL、报告保存 |
| github | binary 记录 `ef07feb90b95893767c106067868735d9f550ba6` | 按 toolsets/只读/仓库范围核查完整注册 | REST/GraphQL、Git、CLI、文件 |
| huggingface | 动态远程 `https://huggingface.co/mcp`，匿名快照自报 0.4.18 | 匿名四工具已核，指定账号集合 U；hf_fs 含多命令/路径，见 F22 | Hub SDK/CLI、datasets/Viewer、Git/LFS、raw/resolve 对象下载 |

## 共享架构设计（D）

统一的是基础机制：episode 身份命名空间、持久化事务、按服务分域的 ID/版本、虚拟时钟、内容寻址 blob、快照、调用日志、语义 profile、契约验证。业务规则由各领域独立实现；不把 Calendar recurrence、SQL 执行、Git commit 图或 Notion block 树压成同一 CRUD。

一个 episode 的 MCP/API/SDK 适配入口应路由到同一权威状态；不同 episode 隔离。Google 可共享显式 Principal 与 Drive File 映射，但认证方式、scope 和 Cloud IAM 不自动合并。跨服务引用必须有来源资源 ID/版本/内容摘要以及 ACL 校验，复制内容与共享实时引用分开。

共享业务后端不等于共享所有 MCP/SDK 进程。W&B 的全局 active run、SDK 配置/缓存和模块级 TraceService（W&B 报告 §1/3/8）要求单独检查进程作用域；设计优先将有此状态的 wrapper 绑定固定 episode/主体，不在同一进程动态换凭据。无此耦合且经过隔离验证的后端才共享进程。Git/HF 的客户端缓存、工作树和下载授权同样与可共享的不可变 blob 分开。

LLM 候选链路：调用 + 鉴权后的完整相关状态 → 提案（响应/受限变更集）→ 确定性契约/权限/不变量/版本校验 → 原子提交 → 从提交态渲染最终响应。状态不足时检索/分页，不允许猜测；负查询也须完成对应索引查询。大状态用结构化查询和 blob 引用，摘要不作为真值。冲突重取状态，校验重试有上限，失败不提交。SQL/代码、ID、ACL、分页、精确数值由确定性组件负责；LLM 读取不得发明已有资源。仿真器不接收评分答案或成功轨迹。

这里的原子提交只对应真实服务的一个提交单元。MCP 调用由多个后端操作组成时，保留分步持久化和可见部分失败，例如 Sheets copyTo 后重命名、create 后 Drive 移动、逐收件人分享；GCS move 的 copy+delete 亦同。契约校验重现实际 handler 的默认/投影，不把“广告 schema 更严”擅自提升为新的拒绝规则。LLM 提案不能越过任何一个真实提交/权限边界。

## 已合并的领域发现与冲突处理

以下均经统筹重新读取所引源码/官方资料；不把 agent 消息本身当最终证据。固定源以服务报告所列下载 URL 定位，临时源码目录只用于本次检查。

| 编号 | 公共结论 | 证据与范围 | 处理 |
|---|---|---|---|
| F09 | 错误层级是服务契约的一部分，不能统一改写 unknown tool | Calendar 1.0.2 `build/index.js:276-289`；Forms `96f7fa1` `src/index.ts:182-198` | 二者实际为 text+isError；更新公共标准 |
| F10 | wrapper 的 call_tool_with_retry 只重试异常，直接返回含 isError 的结果 | `utils/mcp/tool_servers.py:453-486` | 初始化日志或“无异常”不能证明业务成功，oracle 必须独立查状态 |
| F11 | Calendar lock 基线可确定为 1.0.2，但部署解析仍未核验 | `package.json:11`；`package-lock.json:1688-1725`；`configs/mcp_servers/google_calendar.yaml:7-10` | 修正初步 U，区分锁版本与运行版本 |
| F12 | Cloud 日志到 BQ 导出工具存在参数签名不匹配，允许列表通过后走异常返回 | 固定 `7df9ca2` 的 `src/server.py:946-955` 与 `src/cloud_logging.py:819-824` | 源码兼容与修复 profile 分开；不伪造成功，不默认用缺陷轨迹训练主能力 |
| F13/U | Forms 默认发布行为存在官方文档时间差：2026-07-22 迁移公告称 2026-06-30 之后 API 新建默认 unpublished；2025-04-08 create 参考页仍描述旧默认 | [迁移公告](https://developers.google.com/workspace/forms/api/guides/api-changes-to-google-forms)、[create 参考](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/create)，均查阅 2026-09-10；wrapper `96f7fa1` `src/index.ts:203-225` 未传该开关 | dated backend profile，publication 与 ACL 分离；实际租户 rollout 待确认，不能用旧任务注释定事实 |
| F14 | 本机 `.venv` 的 Agents 包元数据为 0.0.15，list_tools 实现仅调用一次 session.list_tools 并取 tools，没有跟随 nextCursor | `.venv/lib/python3.12/site-packages/openai_agents-0.0.15.dist-info/METADATA:1-3`；`.venv/lib/python3.12/site-packages/agents/mcp/server.py:132-146`；`uv.lock:2159-2160` | 仅本机包；采集 MCP 全量快照须独立翻页，并与 harness 实际可见列表区分，任务镜像未核验 |
| F15 | Sheets 一个 MCP 操作不保证全回滚；create 的 folder 回显可能与真实父目录不一致 | 0.4.1 `src/mcp_google_sheets/server.py:445-484,734-770,880-930` | 共享层保留 copy/rename、create/move、逐recipient 的不同提交边界；独立 Drive parent/ACL oracle |
| F16 | DRIVE_FOLDER_ID 只影响 list/create 位置，不能当作直接 ID 操作的后端权限 | 同版 `server.py:829-851` 及具体直接 ID 工具见 Sheets 报告 | Google 身份可显式关联，但 folder 过滤与 Drive ACL 分开 |
| F17 | Python 返回 list 不一定成为一个 JSON 数组；本机 mcp 1.9.0 的 FastMCP 递归 flatten list/tuple | `.venv/lib/python3.12/site-packages/mcp-1.9.0.dist-info/METADATA:1-3`；`mcp/server/fastmcp/server.py:872-891` | 只作为已读本机依赖 profile 的事实；服务安装依赖不同，必须按实际 mcp/pydantic 版本取 content 快照 |
| F18 | Notion 固定 fork 能通过 BASE_URL 替换 OpenAPI server；页面允许列表只覆盖部分路径 | `43f1175` 的 `scripts/start-server.ts:16`、`src/init-server.ts:30-33`、`src/openapi-mcp-server/auth/page-access-control.ts:381-408`、`mcp/proxy.ts:169-179` | 优先保留 wrapper 接本地 HTTP；后端 ACL 仍必需，search/comments 等不能因未受 wrapper 限制就拥有全权 |
| F19 | Notion 固定 proxy 的业务/访问错误可表现为 JSON text，无 isError；unknown operation 则在 try 外抛出 | 同版 `src/openapi-mcp-server/mcp/proxy.ts:94-155` | 公共日志保留原始错误与模型投影，不能用是否 isError 单独区分成功 |
| F20 | Snowflake 空结果被包装为 success 哨兵，Decimal 在输出序列化时转 float；append_insight handler 参数与 dispatcher 不符 | `bca38f3` 的 `src/mcp_snowflake_server/db_client.py:79-85`、`serialization.py:20-21`、`server.py:315-321,1043-1050` | 权威 SQL 空行集/DECIMAL 保留准确，MCP 兼容投影单列；append_insight 的已知失败不伪造状态变更 |
| F21 | W&B Weave count/query 的 endpoint 配置不统一；报告创建是 run→media→report 保存→finish 多步操作 | `83f6d7f` 的 `mcp_tools/count_traces.py:272-275`、`mcp_tools/query_weave.py:9`、`weave_api/client.py:56`、`mcp_tools/create_report.py:133-195`（均在 `src/wandb_mcp_server/`） | 单个 WEAVE_TRACE_SERVER_URL 不能使全部入口本地；记录部分写入与异常后未finish，不伪装为单表报告CRUD |
| F22/U | 2026-09-10 11:23:45 UTC 的 HF 匿名协议快照有四工具：hf_whoami、hub_repo_search、hub_repo_details、hf_fs；单页无 nextCursor，server 自报 0.4.18，协商 MCP 2025-06-18 | 本次仅 initialize/initialized/tools/list，无 Authorization/Cookie、无 tools/call；完整公开快照及 SHA256 见 HF 报告 §2 | 匿名工具契约已核；不推定指定账号集合、资源读取行为或部署 commit。hf_fs 是多命令/路径语义族，四工具不等于四个简单动作 |
| F23 | HF 公开源码与当前任务的多个入口独立设置或硬编码 endpoint | 固定 `d7fe9282` 的 `packages/mcp/src/repo-search.ts:133`、`dataset-viewer-inspect.ts:5,172-179`；`tasks/finalpool/dataset-license-issue/evaluation/main.py:124-127` | MCP、Hub SDK、raw/resolve、Dataset Viewer、外部文件分别路由；一个 HF_ENDPOINT 不足以证明全部业务本地化；公开源码不等于远程部署 commit |
| F24/U | GitHub 固定源码使用 Viper 的 read-only 键，无 env key replacer；自动查询 GITHUB_READ-ONLY，与 YAML 的 GITHUB_READ_ONLY 不一致 | `ef07feb` 的 `cmd/github-mcp-server/main.go:65,86,96,107-111`，`go.mod:11`；[Viper v1.20.1](https://github.com/spf13/viper/blob/v1.20.1/viper.go#L413) `viper.go:413-418,437-444,1206-1212`，查阅 2026-09-10 | 固定源码推导的绑定冲突已核；CLI --read-only 可生效，实际 binary/环境 U。旧文档“GitHub 默认只读”不能当已确认运行事实 |
| F25 | GitHub 非空 repo allowlist 只约束当前用户个人仓库，且只有部分工具套 wrapper | `ef07feb` 的 `pkg/github/repo_permission.go:58-95`；各工具注册见 GitHub 报告 §2 | 组织/其他用户仓库通过该 wrapper 后仍受后端 ACL；不能把 allowlist 当 episode 隔离或完整资源授权 |
| F26 | Snowflake 空行集的 success 哨兵会破坏目录消费者：空 schema 的 create_tables/drop_tables 在预检即缺 TABLE_NAME；prefetch 返回错误字符串，resources/list 后续调用 keys 失败 | `bca38f3` 的 `db_client.py:79-87`、`server.py:529-535,595-600,647-659,987-994`（均在 `src/mcp_snowflake_server/`）；非原作者审查发现、统筹重读核实 | 明确源码推导，未做运行调用；兼容 profile 保留失败及单表/SQL 合法替代路径；修复 profile 另标版本，不在后端伪造目录行绕过 |
| F27 | Cloud 的 SDK 下限不固定未知工具名的错误层级；Python MCP SDK v1.11.0 的 FastMCP 将 ToolError 包成 isError=true 工具结果 | [Python SDK v1.11.0 对应提交](https://github.com/modelcontextprotocol/python-sdk/tree/ee54acbfa3d5128598c162241aa54f729659c6a5) 的 `src/mcp/server/fastmcp/server.py:238,274`、`fastmcp/tools/tool_manager.py:79-83`、`lowlevel/server.py:401-407,502-503`；2026-09-10 审查发现、统筹与作者重读 | 未知 tools/call 名与未知 RPC method 分开；Cloud 运行 SDK U，逐 profile 保留实际错误，不能一律宣称 JSON-RPC 拒绝 |
| F28 | W&B workspaces 保存可合法创建缺失项目；HTML 输入可读取本地存在路径，默认注入公网样式链接 | `wandb-workspaces 0.1.12` wheel 中 `reports/v2/interface.py:3045-3078`；[wandb SDK 0.19.8 html.py](https://github.com/wandb/wandb/blob/v0.19.8/wandb/sdk/data_types/html.py#L29) `29-43,59-74`，统筹重取发布包/raw 源核验 | 这是有源码依据的真实副作用，区别于模拟器随意补资源；workspace/blob/HTML 渲染依赖应纳入入口和提交记录 |
| F29 | W&B Weave 成本排序的首阶段直接对原始 id/summary 行读取顶层 costs；get_cost 缺值返回 0.0，is not None 并不排除无成本行 | `83f6d7f` 的 `weave_api/service.py:699-735` 与 `weave_api/processors.py:472-496`；非原作者发现、统筹重读固定源 | 仅含嵌套 summary.weave.costs 的响应会在此阶段被当成 0 排序，不能描述为正确成本 top-k；这是条件化源码推导，实际后端响应 U。缺失/零/嵌套/顶层成本各设反例，兼容与修复 profile 分开 |
| F30 | W&B Weave 输出转换会在缺 trace_id 时令其等于 id，并在缺失/非法 started_at 时填当前时间 | 同固定源 `weave_api/processors.py:402-426`；非原作者发现、统筹重读 | 字段业务角色不同不等于值必须两两不同；兼容投影可回填，权威图/原始时间不可被其倒灌修改。父边无环/不得自指仍由真实域约束检查；记录投影时钟以便回放 |
| F31 | GitHub 固定 create_or_update_file 的 MCP content 是正文字符串；server 转 []byte 后由 Go JSON 编码为 REST 所需 base64 | `ef07feb` 的 `pkg/github/repositories.go:399-401,428-448,465`，非原作者发现并由统筹重读 | M/SDK/REST 的编码层不能混同；M 传入形似 base64 的普通文本仍应保存那些字节，不能由模拟器先解码；Git/raw/REST 三入口 bytes 验证 |
| F32 | GitHub cwes 与其他可选数组的 parser 不同：普通 JSON 入站数组为 []any，OptionalParam[[]string] 的直接类型断言会拒绝提供的数组/null | `ef07feb` 的 `pkg/github/security_advisories.go:94-96`、`server.go:106-119`；mcp-go v0.36.0 `mcp/tools.go:54-72` 由审查者核对，统筹重读本域 handler | 省略 cwes 与提供空数组不同；不能只看广告 array schema 或把其他专用数组 parser 的容忍规则套过来；wire 契约负例与修复 profile 分开 |
| F33 | GitHub 子 issue 重排要求 after_id/before_id 经 OptionalInt 转换后恰好一项非零 | 同提交 `pkg/github/issues.go:640-655`，统筹重读 | 非“至少一个”，也非仅按字段是否出现判断；双给/全省/零/小数转换各验，不能额外强化成只接受 integer 后宣称契约不变 |

Notion 的固定来源补充核验：统筹 2026-09-10 通过固定 raw commit URL 重取 OpenAPI、parser、proxy、page-access-control、http-client、init-server、start-server、package.json 八文件，与本次分析参考逐字节一致。OpenAPI SHA256=`ef9ca3cd4c46c58ee8d9c7ba56b023830b3d5b1ae6c03db91847b239531a7112`；proxy SHA256=`f38e43a8e743f4f32faeed98da49d4ba21bc776f965d9d189dd2aaa5e6fcb993`。这核实源码来源，不等于启动过 server。

关系完整性应区分真实强制与业务预期：例如 Snowflake 标准表的 PK/FK/UNIQUE 元数据不等于强制约束（详见 Snowflake §6 的官方来源）；模拟后端不能因为存储数据库默认支持 FK 就增添真实服务没有的拒绝。episode 内部状态存储的身份/引用约束与用户建表 SQL 的约束执行是两个层次。

“稳定 ID”表示已有引用须可追溯，不表示每个服务字段永远不能合法改变。Forms 的 B/X `UpdateItemRequest` 在 updateMask 含 ID 时可以采用传入 item/question ID，含空 ID 时会生成新 ID（[官方定义](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/batchUpdate#UpdateItemRequest)，2026-09-10 经非原作者审查发现、统筹重读确认）。本版五个 M 工具未直接暴露 updateItem；若 X profile 支持该操作，必须记录版本及旧回答关联，不能将所有 ID 变化统一拒绝为状态漂移。历史响应的具体保留行为仍需受控差分，不能自行重写为新 ID。

版本需要两个独立坐标：**MCP/依赖版本**与**后端政策/行为日期及账户 plan**。API header 不冻结 SaaS 的全部策略；Forms 发布迁移已有 F13 冲突，Notion 当前官方 [request-limits](https://developers.notion.com/reference/request-limits)（查阅 2026-09-10）也区分连接和 workspace 限额及 plan。设计可用可校准的故障/限流 profile，不把旧平均请求数写死为全部账号规律。具体额度不是本次服务实测。

## 协作记录

统筹会话实际 `gpt-6-astra / xhigh`，由本次运行会话 turn_context 的 model/effort 与 collaboration settings 核实；不以全局默认值代替实际值。领域与审查 agent 创建时显式指定相同模型和推理强度，工具回执登记在总体报告。最多 1 位统筹 + 3 位领域/审查 agent；每位领域 agent 一次仅负责一个 MCP。公共文件由统筹独占维护；每批完成后合并事实、通知受影响作者，再交叉审查。
