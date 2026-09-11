# snowflake 高保真模拟可行性与设计

> 作者：领域 agent `/root/snowflake`；创建配置为 `gpt-6-astra / xhigh`，由统筹记录工具回执。非原作者 `/root/github` 已完成交叉审查；SF-01/P2 已由原作者按固定源码补充，未做运行验证。查阅日期：2026-09-10；仓库 HEAD：`ef7ab5928062defc0dc2a91a4c26ddebccb1a6a7`。已读原始要求、[shared.md](../shared.md)、[service-template.md](../service-template.md)、[google-cloud 报告](google-cloud.md)、公共合成/验证设计及 `docs/mcp-analysis.md`；仓库及祖先目录未发现适用 AGENTS.md。F=已核实事实，D=设计，A=规划假设，U=待确认。本阶段只读源码/公开资料并编写本文，没有导入配置、读取密钥内容、启动 MCP/初始化/benchmark、安装或运行模拟器、访问真实业务服务。

**结论（D）：接口层可以按固定版本较准确复现；SQL 与跨入口状态可在明确的语义范围内达到较高保真，但不能直接用 DuckDB、SQLite 或 Snowpark 本地测试替换 Snowflake。** 首选代码驱动的 Snowflake 语义层与共享执行后端，复用经过差分验证的协议/SQL 组件，LLM 用于提前生成业务文本和环境数据。全部 14 个注册工具都是设计边界，任意 SQL 的长尾能力分阶段扩展；源码包装缺陷与后端正确语义分别建 profile，禁止以假成功掩盖缺口。

## 1. 范围、版本与入口

### 1.1 固定来源与核验边界

本文缩写引用下列固定文件；行号指对应提交文件，不依赖临时下载目录：

| 缩写 | 固定来源与内容 |
|---|---|
| S | [server.py](https://github.com/lockon-n/mcp-snowflake-server/blob/bca38f3ef5305ac53b9935bd09edbfac442b6a36/src/mcp_snowflake_server/server.py)：工具注册/handler、目录限制、resources/prompts，1–1081 |
| B | [db_client.py](https://github.com/lockon-n/mcp-snowflake-server/blob/bca38f3ef5305ac53b9935bd09edbfac442b6a36/src/mcp_snowflake_server/db_client.py)：Snowpark 会话、SQL collect、memo，1–109 |
| Z | [serialization.py](https://github.com/lockon-n/mcp-snowflake-server/blob/bca38f3ef5305ac53b9935bd09edbfac442b6a36/src/mcp_snowflake_server/serialization.py)：YAML/JSON 类型转换，1–69 |
| W | [write_detector.py](https://github.com/lockon-n/mcp-snowflake-server/blob/bca38f3ef5305ac53b9935bd09edbfac442b6a36/src/mcp_snowflake_server/write_detector.py)：sqlparse 写操作检测，1–98 |
| E | [__init__.py](https://github.com/lockon-n/mcp-snowflake-server/blob/bca38f3ef5305ac53b9935bd09edbfac442b6a36/src/mcp_snowflake_server/__init__.py)：CLI、环境/TOML 连接配置，1–224 |
| P | [pyproject.toml](https://github.com/lockon-n/mcp-snowflake-server/blob/bca38f3ef5305ac53b9935bd09edbfac442b6a36/pyproject.toml)：包版本 0.4.0、依赖与入口，1–30 |

F：对已有固定源码的上述 6 个文件逐字节比较了 GitHub raw URL，全部一致；S 的 SHA-256 为 `6295831fe391fb7020bbd9d585c281aa19173159b3afea2caa1a2b5c19c8a279`。`global_preparation/install_env.sh:209` 固定安装该 commit，第三方 `lockon-n` fork 调用 Snowflake 官方 SDK，不是 Snowflake 官方发布的 MCP。`configs/mcp_servers/snowflake.yaml:7-29` 启动裸 `uvx mcp_snowflake_server`，所以安装基线不能证明实际任务镜像解析出的版本。

F：P:8–16 要求 MCP>=1.0.0、Connector>=3.12.0 且 <3.14.0、Snowpark>=1.26.0、sqlparse>=0.5.3，缺少完整锁定。仓库 X 层锁为 Connector 3.16.0、Snowpark 1.36.0（`uv.lock:3125-3126,3184-3185`）。**M 的 uv tool 环境与 X 的仓库环境不能当成同一个依赖集合**；完整 MCP 校验行为、协议协商、SDK 返回 Python 类型与实际镜像版本仍为 U。

### 1.2 M/B/X 三层与公网

| 层 | 本次确认的范围 | 不自动纳入/仍需声明的边界 |
|---|---|---|
| M | 5 个查询/发现工具、1 个 memo 工具、8 个写/管理工具；resources 和空 prompt 集合；stdio | 不是仅 SELECT、INSERT 和现有四任务。SQL 参数是通用执行入口，不能枚举几条 SQL 代替语义实现 |
| B | account→database→schema→table/view/column、typed rows、SQL 名称解析、权限、会话/事务/warehouse/query；SQL 可触及 stage/file format/COPY、tasks、函数等 | 不默认复刻计费、真实分布式计算拓扑、Snowsight、组织管理全部功能。SQL 长尾必须有显式 profile 和拒绝规则 |
| X | 初始化中的 MCP 和 Connector；评测中的 Connector/DictCursor、日期/Decimal；未来声明的 Snowpark/Connector/SQL API/CLI 与 stage 文件传输 | 新入口不是自动已支持。SDK transport、HTTP、CLI 逐项验收；它们访问同一对象时必须共享权威状态 |

F：YAML:10–27 传 account、warehouse、user、private_key_path、role、database、schema、allowed_databases，并开启 `--allow_write` 与 `--exclude-json-results`；cwd 为 agent workspace，timeout=120 秒，缓存工具列表。E:159–204 从环境、CLI、可选 TOML 组连接参数：TOML 优先于 CLI，CLI 优先于环境；TOML 的两个参数必须成对；启动断言必须存在 database/schema。B:31–48 在 MCP 进程读 PEM 文件并转换为 DER；不需要将真实密钥搬入 mock，设计中把入口凭据映射到模拟 principal。

F：MCP 的目录允许列表并非后端 RBAC。S:44–78 的检查/SQL 提取简单，`create_table` 没有数据库允许列表检查（S:620–627）；`read_query` 的黑名单不是完整的只读 SQL 分析器（W:10–17）。因此即使关闭 `allow_write`，也不能据此承诺所有合法调用无写入；真实效果还由 SQL 和角色权限决定。D：后端独立做权限判定，同时保留包装差异，不能靠 MCP 网关检查保护 SDK 入口。

公网：真实业务连接/认证依赖 Snowflake 公网服务；设计业务后端、SQL 执行、stage 与结果传输在本地或自控内网。安装下载、agent 模型 API、可选仿真 LLM API分别记录。外部 stage 的 S3/GCS/Azure URL、外部函数、包下载/外部访问集成是额外公网能力，默认不得回落真实网络。PEM、工作目录、PUT/GET 的本地文件访问与公网是不同维度。

### 1.3 当前任务、共享状态和轨迹

F：逐个 JSON 扫描得到完整四个声明成员，均同时使用 emails；下表是源码使用线索，不是实际调用成功证明。

| 任务 | Snowflake 业务与入口 | 关键证据（相对 `tasks/finalpool/<任务>/`） |
|---|---|---|
| landing-task-reminder | 员工层级、入职日期、公共/组内任务、分配标志；初始化和评测直接 Connector，agent 用 MCP | `preprocess/main.py:73-151` 建库/表、批量 INSERT、DATE/BOOLEAN；`evaluation/main.py:77-115` 查询；`:423-429` 用数据库当前时间覆盖评测 launch_time |
| payable-invoice-checker | 发票/付款金额、欠款标志及列 COMMENT；初始化用 MCP，评测用 Connector | `preprocess/create_snowflake_db.py:474-517` drop/create、DECIMAL 表；`evaluation/check_snowflake.py:80-109` SELECT/INFORMATION_SCHEMA.COLUMNS；`:159-218` 数据保持与注释检查 |
| sla-timeout-monitor | 用户等级/联系人、工单、首响时间和 SLA；初始化用 MCP，评测以邮件与私有 groundtruth 为主 | `preprocess/create_snowflake_db.py:380-405,409-455` 管理/建表/CURRENT_TIMESTAMP；`evaluation/main.py:30-60,74-76` 邮件验证；不能据其邮件通过证明 SQL 正确 |
| travel-expense-reimbursement | 联系人、报销表、自动编号、DATE/NUMBER(18,2)，邮件内容输入→DB | `preprocess/create_snowflake_db.py:216-246,267-280` MCP 建库/表；`evaluation/main.py:1-7,58-89,122-164,166-208` Connector、Decimal 归一、逐字段及联系人保持检查 |

F：`utils/app_specific/snowflake/client.py:10,18-54` 从全局 token 模块构建 Connector 参数；`:60-119` 的每次 helper 调用新建连接、fetch/commit/rollback 后关闭。MCP manager 则支持局部 token 覆盖（`utils/mcp/tool_servers.py:50-101`）。因此“替换 YAML 的账号”不足以覆盖 X：同一 episode 的全局 SDK、局部 MCP、预处理独立进程都要明确路由。**共享业务表不等于共享 session**：X helper 中一次 `USE` 不会改变下次新连接，M 的持久 Snowpark session 内则可保持上下文，直到重连。

`utils/app_specific/snowflake/helpers.py:8-22` 使用 fully qualified/quoted table 与 count 查询；模板中有 PK/UNIQUE/FK 不意味着 Snowflake 标准表强制这些约束，见 §6。当前任务的日期、邮件状态和数据库时钟需由共享虚拟 clock 协调，但 SMTP/IMAP 状态机不属于本报告实现范围。

本次在仓库通过 `rg --files` 检索 dump、trajectory、tool_call、agent JSON/JSONL，没有发现可用于 Snowflake 的真实 MCP 调用轨迹；其他任务的 groundtruth 文件不是轨迹。没有将 pass 率、逐工具使用频次、真实错误分布或镜像运行情况列为已验证。

## 2. 工具与能力清单

### 2.1 完整工具契约

F：S:726–965 静态注册 **14** 工具，AST 已逐个核对。表内中文为说明语义摘要；完整原始 description、各属性 description 和 JSON Schema 见固定 S 行段。所有输入根类型都是 object；下列出现的参数均为必填，`list_databases` 无参数。没有工具参数默认值、enum、长度/数值界限、数组 minItems/uniqueItems，也没有 `additionalProperties:false`；不能擅自把说明中的“SELECT”当 schema 限制。嵌套 tables object 只要求 `name,definition`，额外键未由 schema 明令禁止。SDK 是否执行 schema 验证/何种错误包装需要锁定 MCP 依赖后取快照。

| 原始名 / 说明摘要 | 参数和额外处理 | 返回内容 | 属性、状态 / 当前使用与未来价值 | 证据 |
|---|---|---|---|---|
| `list_databases` 列可用数据库 | `{}`；INFORMATION_SCHEMA 查询后按 allowed/exclude patterns 过滤 | 数据包装：`type,data_id,data`；行含 DATABASE_NAME | R；catalog/role/session；发现型任务可用但未见轨迹；未来多库定位 | 注册 S:727–735；handler :90–130 |
| `list_schemas` 列指定库 schemas | `database:string`；先检查原输入允许列表，再把 SQL 数据库大写 | 数据包装另含 `database`；SCHEMA_NAME | R；catalog/ACL；未来 schema 选择 | S:736–750；:133–176 |
| `list_tables` 列库/schema 表 | `database:string,schema:string`；schema 转大写作过滤条件 | 数据包装另含 `database,schema`；TABLE_CATALOG/TABLE_SCHEMA/TABLE_NAME/COMMENT | R；tables/views metadata；未来目录探索、相似名区分 | S:751–763；:179–229 |
| `describe_table` 表结构 | `table_name:string`，说明要求 `database.schema.table`；实际按 `.` split，少于 3 段错误，前三段大写 | 包装另含 `database,schema,table`；COLUMN_NAME/COLUMN_DEFAULT/IS_NULLABLE/DATA_TYPE/COMMENT | R；columns/default/comment；现有列注释相关，未来类型驱动查询 | S:764–778；:232–277 |
| `read_query` 执行 SELECT | `query:string`；write_detector 检查，再简单提取数据库；没有行数/timeout 参数 | 数据包装；任意查询实际 collect 的字典行，空集例外见下文 | R/E，不能据名称保证后端无副作用；四任务查询族及初始化显式使用；未来 JOIN/窗口/JSON/信息模式 | S:779–788；:280–312；W:19–98 |
| `append_insight` 添加分析 memo | `insight:string` | handler 意图为 TextContent 确认并发 resource-updated；当前 dispatch 参数错误导致错误文本 | W-local；session memo；当前无使用证据；未来分析记录，缺陷见 §2.3 | S:789–804；:315–321、:1043–1050 |
| `write_query` 执行 INSERT/UPDATE/DELETE | `query:string`；实际仅拒绝 strip 后以 SELECT 开头的语句，其余送 SQL 执行，包含合理 DDL/会话控制范围 | 单 TextContent，`str(results)` 的 Python list/dict repr；没有 `data_id` 字段 | W/E/A；rows/catalog/session；四任务更新/初始化；未来 MERGE、管理与事务 | S:805–815；:324–337 |
| `create_table` 新建表 | `query:string`；要求 strip/upper 后以 `CREATE TABLE` 开头，因此拒绝 `CREATE OR REPLACE TABLE`；没有 allowed_databases 检查 | 单 TextContent，创建成功及生成的 data_id；不返回实际结果行 | W/A；catalog、types、session；三任务初始化显式调用；未来建模/CTAS | S:816–826；:620–627 |
| `create_databases` 批量建库 | `databases:array[string]`；逐项 allowed 检查，不允许的变 warning；先查询已有库，逐项执行 | 单 TextContent，多行 warnings/成功/失败；可部分成功 | W/A；catalog、owner；三任务初始化；未来隔离工作区准备 | S:827–843；:340–381 |
| `drop_databases` 批量删库 | `databases:array[string]`；任何 allowed 失败在执行前终止整次；不存在的 warning | 同上，多行文本；实际删除逐项执行 | W/A；对象层级/依赖/会话；三任务初始化；未来生命周期恢复 | S:844–860；:384–420 |
| `create_schemas` 批量建 schema | `database:string,schemas:array[string]`；检查库；已有项 warning | 单 TextContent；元数据查询失败立即返回，之后逐项成功/失败 | W/A；catalog/ACL；当前无明确使用证据；未来命名空间规划 | S:861–881；:423–463 |
| `drop_schemas` 批量删 schema | 同上；不存在项 warning | 单 TextContent，多行结果，非批次事务 | W/A；对象依赖；未来安全清理与重建 | S:882–902；:466–506 |
| `create_tables` 批量建表 | `database:string,schema:string,tables:array[oneOf(string,{name:string,definition:string})]`；从 SQL 正则提取表名，再做区分大小写的字符串 replace | 单 TextContent；空 schema 在 TABLE_NAME 预检失败，不执行首表创建；非空目录才进入多行 warnings/成功/失败/非法表定义；不保证 SQL 实际落到声明 schema | W/A/E；catalog/types；当前无明确使用证据；未来多表建模，限定包装缺陷 profile | S:903–939；:509–571 |
| `drop_tables` 批量删表 | `database:string,schema:string,tables:array[string]`；元数据检查，逐项 DROP | 单 TextContent；空 schema 预检失败；非空目录进入逐项结果/不存在 warning | W/A；catalog/依赖；未来删除/错误恢复 | S:940–964；:574–617 |

`tables` 中 schema 没有禁止空数组、重复项或额外属性。批量工具只在开始抓取已有对象集合，成功后不更新该集合（S:363–375、443–457、529–565 等），同一输入重复名可能第二次失败；不能统一改造成幂等、原子或“全部成功”。发现工具的 SQL 没有 ORDER BY，也没有 MCP cursor；返回完整 collect，SQL 层 LIMIT/OFFSET/keyset 是另一件事。

### 2.2 输出、可见性、资源和协议

F：五个读/发现 handler 将业务 dict 序列化为 YAML **TextContent**；默认再加 EmbeddedResource，其 `uri=data://<uuid>`、mimeType=`application/json`、text 为同一 dict 的 JSON（S:113–129 等）。`--exclude-json-results` 只移除 EmbeddedResource，YAML 的 `data_id` 仍存在；源码仍先计算 JSON 再判断开关（S:118–121、300–303），因此 JSON 序列化失败不能因关闭输出就自动避免。写工具返回上述专用文本，不统一套数据 dict。handler 没有声明输出 schema、annotations、structuredContent，也不返回图片。

F：B:79–87 每次 collect 全量结果并生成新的 UUID4，**这个 data_id 不是 Snowflake query ID**，没有保存结果缓存。查询零行被改成 `[{status: success, message: Query executed successfully}]`，不是空数组；它只是包装哨兵，不应写进真实表或被 oracle 当业务行。没有 MCP 层分页/截断；大内容由 harness 后续截断并落文件（`utils/openai_agents_monkey_patch/custom_mcp_util.py:188-229`），属于另一个进程边界。

F：Z:14–24,54–69 将 Decimal 转 float，date 转 ISO，YAML float NaN 转 null；JSON 原生 float 的编码不必经过 default serializer，因此不能笼统声称两种输出对 NaN 一致。TIME/binary/特殊 SDK 对象没有完整自定义覆盖，其实际类型和出错模式 U；原始 Decimal/时间精度必须由权威状态保留，不能让模型可见的有损包装污染 X 层。

| 配置/协议项 | 固定实现行为 |
|---|---|
| `allow_write=False` 默认 | 隐藏 8 个 `tags=[write]` 的工具，剩 6；显式排除工具在此基础上再过滤。`append_insight` 没有 write tag（S:967–972） |
| `--exclude_tools` 默认 `[]` | 按名称从 tools/list 去除；直接调用返回 excluded 文本（S:1023–1024），不同于 unknown tool |
| `--prefetch` 默认 False | 启动查询配置 database/schema 表和列，保存 `tables_info`。CLI help 称禁用 list_tables/describe_table，但实际过滤没有此分支；14/6 计数不因此减少（E:60–71；S:630–659,723–724,967–972） |
| 默认 `runtime_config.json` | 从 cwd 读 `exclude_patterns`，缺失仅日志；列表按大小写不敏感的子串隐藏数据库/schema/table；不是 glob、不是访问控制（S:686–714、各列表 handler） |
| `resources/list` | 正常路径包含 `memo://insights`，text/plain；prefetch 成功时另有 `context://table/<name>`，text/plain。空 schema 可触发预取 string→keys 异常而不能正常列出 memo；成功目录快照不随后续 DDL 自动刷新（S:977–997；§2.3） |
| `resources/read` | memo 返回内存 insight 格式文本；context 返回 prefetch YAML；未知 table/resource 抛 ValueError。**没有 data:// UUID 的读取分支**，也未注册 resource template（S:999–1010；B:97–109） |
| prompts | list 返回空；get 任意 name 抛 Unknown prompt（S:1012–1018） |
| 通知/订阅 | append handler 意图发送 memo resource-updated；没有显式业务 subscribe/unsubscribe handler。能力声明由 MCP SDK 的 get_capabilities 默认参数生成；实际协商快照 U（S:320,1073–1079） |
| harness | 模型名如 `snowflake_read_query`；原始 dispatch 保留 `read_query`。模型收到 content item 的 JSON 表示，顶层 isError/structuredContent 不独立透传，见 shared F04–F06 |

资源虽然协议注册，当前 TaskAgent 主路径主要枚举工具，不证明 memo/context 自动进入模型上下文（`utils/roles/task_agent.py:465-551`）。未来 resource-aware client 应单独验收，不能偷偷增加普通 SQL 工具的上下文。

### 2.3 错误和固定版本缺陷

F：S:30–39 的装饰器把 handler 异常转成 `Error: <message>` 的 TextContent 列表，不设置 `isError:true`；missing、拒写、允许列表和 unknown tool 走这个 handler 层路径。批量操作内部错误常被转成 Failed/Warning 文本。输入 schema 在 SDK 层的验证、资源/prompts 抛错的 JSON-RPC code/结构尚需固定依赖快照，不能以 handler 推定其完整包络。`call_tool_with_retry` 只重试异常（`utils/mcp/tool_servers.py:453-486`），这类文本错误通常不会触发它的异常重试。

F：`append_insight` 注册可见，但 handler 签名 S:315 只接受 `exclude_json_results`，dispatch S:1049–1050 对非列表工具还传 `allowed_databases`，没有 `**kwargs` 接收。因而该固定源码路径在追加前发生 TypeError，成为错误文本；memo 保持不变。S:51–78 对 `USE DATABASE DB` 提取为 `DATABASE`、对 `CREATE DATABASE IF NOT EXISTS DB` 提取为 `IF`，三段名称仅取首次正则匹配，不能正确处理全部引用、引号和嵌套；这是静态可确定的解析逻辑，不是实测绕过记录。

F（SF-01/P2，空目录链式缺陷）：B:79–87 将 SQL 空结果改成 `[{"status":"success","message":"Query executed successfully"}]`，没有 `TABLE_NAME`。`create_tables` 在 S:529–535 查询既有表后逐行取 `row["TABLE_NAME"]`；目标 schema 没有可见表时产生 KeyError，返回 `Failed to check existing tables ...` 的 TextContent，**尚未进入 S:537 的建表循环，不能批建第一张表**。`drop_tables` 的 S:595–600 同理，在空目录时先失败，不能声称必定走到逐表不存在 warning。这里失败属于 wrapper 把空 SQL 行集当目录行的结果，不是 Snowflake 拒绝空 schema，也不是应该在后端补一张虚构表。

F：同一空结果哨兵进入 prefetch 的 S:647–653 时读取/删除 TABLE_NAME 失败，S:657–659 捕获后返回 string；后续 resources/list 的 S:987–994 对该 string 调 `tables_info.keys()` 又失败，不能声称空 schema 或预取失败时仍正常返回 memo 列表。其他 prefetch 异常也可能产生同一后续错误。数据库/目录查询成功后发生序列化错误与 SQL 执行失败须区分：前者可能已产生查询历史或写入副作用。

D：建立 `source-bca38f3` 严格兼容 profile 与未来经过独立审批/版本化的修复 profile；修复 profile 不是本轮对现有任务的修改。空集哨兵及空目录批建/批删/资源枚举链式失败、Decimal 有损展示、memo 错误、目录大小写/替换缺陷分别保留回归样例和质量标签。修复 profile 应在目录消费者边界识别实际空行集/改正投影，并确保预取返回合法结构；不能用伪造 TABLE_NAME 或预建 dummy 表使严格 profile 获得本不存在的成功。主要迁移训练不能无标注混入依赖这些缺陷的成功路径。有效但暂未支持的 Snowflake SQL 返回明确的模拟器能力错误，不能伪装平台语法错误，更不能返回空表或 success。

## 3. 领域状态模型

D：一个 episode 内所有入口访问同一权威数据库状态，session 是其中独立实体。metadata/审计可以复用公共存储；SQL 行与类型由执行后端维护，派生目录必须来自同一 committed catalog，避免建表、INFORMATION_SCHEMA、describe 和 SDK 各维护一份表清单。

| 实体 | 必须保存的字段/关系 | 生命周期、派生与一致性 |
|---|---|---|
| Account/Principal/Role/Grant | episode/account、user、角色继承、对象 privilege、ownership、warehouse USAGE/OPERATE、会话默认配置 | grant/revoke 后各入口一致；M allowlist 与 B RBAC 分开；INFORMATION_SCHEMA 按当前权限派生 |
| Database/Schema/Relation | 不可见内部稳定 ID、精确名称及 quoted 标志、parent、owner/comment、kind、列序、defaults、constraints、DDL 版本 | 表/视图/临时表区别；rename 保身份、drop/create 新身份；PUBLIC/INFORMATION_SCHEMA 规则按真实 profile；删除影响依赖与活跃会话 |
| Typed rows | column schema、精确 NUMBER 系数/scale、字符串/bytes、SQL NULL、DATE/TIME/三种 TIMESTAMP、VARIANT 类型标签/JSON null/缺失 | 值与类型均保存；SQL cast/排序/聚合由引擎；不能把 Decimal float 或 YAML 的 null 当内部真值 |
| Session | session ID、principal、当前 role/warehouse/database/schema、TIMEZONE、AUTOCOMMIT、TIMESTAMP_TYPE_MAPPING、标识符/格式参数、变量、临时对象、事务、last query | M 与每个 X connection 独立；关闭/重连影响临时状态，持久表继续存在；操作日志关联 session |
| Transaction/Query | transaction/read snapshot、写集合、query ID、提交边界、SQL/参数/role、state/error、typed result/metadata、rowcount、时间、取消/超时 | DML/DDL 边界按 Snowflake；query ID 与 MCP data_id 分离；结果保留/RESULT_SCAN 权限和期限可派生 |
| Warehouse/Task | warehouse 状态/auto_resume/大小/配额；task 定义、owner、schedule/dependencies、suspended/started、run history | 查询执行前检查 warehouse/权限；任务只有真实执行组件完成后能成功；没有按轮询次数自动成功 |
| Stage/FileFormat/StageObject | internal/external、db/schema/name、URL→本地资源映射、ACL、format/options、blob hash/size/compression、上传记录、load history | COPY、LIST、PUT/GET、remove 和表数据一致；external stage 的权限身份与 Cloud bucket ACL 不能直接合并 |
| MCP memo/prefetch/projection | MCP process/session identity、insights 顺序、prefetch snapshot/版本、每调用 data_id、原始输出 | memo/context 属于 client 会话资源；按真实生命周期恢复或重置，不能误当 account 全局表；严格 profile 的 memo 缺陷仍保留 |

持久化 catalog、rows、grants、stage bytes/load history、query/task commit/审计、episode 时钟和配置。INFORMATION_SCHEMA、统计计数、目录结果由可见状态派生；memo、临时表与事务可存恢复日志但仍保持 session 范围。快照必须同时覆盖 metadata、SQL 数据版本、blob 引用和调度队列。ID/URL 可以复用公共机制，Snowflake quoted 名称解析、DDL 隐式提交和 VARIANT 不能复用 GoogleSQL 业务实现。

## 4. 代表性交互序列

D：以下按操作图生成多种合法顺序并设置独立状态断言；当前四任务仅作回归。阶段尚未支持的语义会令任务生成器选择其他合法 profile，不能按答案补全返回。

| 序列 | 工具/入口与变化 | 必须验证的断言 |
|---|---|---|
| 多库建模→发现→迁移→删 | create_databases→create_schemas→空目录 create_tables 失败；严格 profile 可由具有权限的合法 create_table 或 write_query 的 CREATE TABLE 建首表，再进入非空目录的批量操作→发现/读写→删除 | 严格 profile 预检失败前后都没有新表；不伪造目录行。合法替代还须符合 CREATE TABLE 前缀、数据库允许列表及 RBAC；metadata 与 typed rows 同源；批量操作仅保留实际成功对象。修复 profile 才单独验证空 schema 直接批建 |
| 分页定位→批量更新 | read_query 按唯一复合键 ORDER BY/LIMIT/keyset 分页→JOIN 干扰表→MERGE/UPDATE→SDK 全量核验；随机在页之间插入独立读 | 同一快照下分页不漏不重；数据变化时按真实隔离语义比较；M 不增加不存在的 cursor 字段 |
| 标识符错误→改正 | CREATE TABLE 带 quoted 混合大小写/点号→错误引用→按实际名称用 read_query 查询；另对 describe_table 包装缺陷单独回归 | 引号敏感性由 catalog 保证；不能自动把错误名改正；M 目录缺陷不应污染 SQL 引擎正确解析 |
| 精确财务更新→事务观察 | M session BEGIN→金额/状态两步 DML→另一 Connector session 读取→ROLLBACK；再提交；另插入 DDL 隐式提交分支 | 其他 session 不见未提交值；自己的写可见；DDL 提交边界正确，不能靠“所有操作一事务”简化 |
| 权限拒绝→合法替代 | 低权限角色 list/read→写拒绝→使用任务授权且已存在的角色或输出只读报告→再次查询 | 不自动授予权限/创建缺失表；拒绝后无非法变更；SDK 与 MCP 角色可见性相同 |
| 半结构化清洗→多入口 | Connector 写 VARIANT 中 SQL NULL/JSON null/缺键/嵌套数组→M FLATTEN/TRY_CAST/聚合→建结果表→Connector typed fetch | 三类缺失不混淆、精度不丢；结果基于所有相关行，不按模型上下文截断 |
| 文件→stage→COPY→回读 | 本地 CSV/Parquet 经 SDK/声明可用 SQL 上传 internal stage→LIST→COPY INTO→M 查询；重复加载、错误行和中断分支 | bytes/hash、行数、file format、load history、FORCE/ON_ERROR/部分完成一致；重试不总无副作用 |
| 跨 Cloud 对象与 SQL | Cloud 下载对象→本地已授权文件→Snowflake stage/COPY→汇总→本地文件/邮件传递；或显式支持的 external GCS stage | 跨服务记录来源版本/hash；不把 gs:// 自动当 Snowflake 内部 stage；Cloud principal 与 Snowflake storage integration 各鉴权 |
| Warehouse/任务执行 | 查询遇 suspended 且不可 auto resume→合法管理路径恢复→执行→query history/result；task schedule→run→结果表→取消/失败 | 执行和结果表有因果证据；取消竞态、时间推进和角色正确；P2/P3 条件语义不冒充当前专用 MCP 工具 |
| MCP 资源与会话 | resources/list/read→append_insight→memo 再读→prefetch 后 DDL→context 再读→新连接 | 严格 profile append 为错误且 memo 不变；空 schema prefetch 返回错误 string 后 resources/list 失败，不当成成功空资源列表；修复 profile 单独验证正常 memo/空目录及追加/通知；成功 prefetch 的旧快照与 fresh SQL 目录区别明确 |

同一业务允许 SQL 聚合或先取数据在本地计算等多路径，前提权限与输出约束满足；评分不要求某个工具调用次数。跨服务消息只在未来隔离模拟环境执行，本轮不发送邮件。

## 5. 候选实现与推荐

### 5.1 现成组件的实际覆盖

以下资料均查阅 2026-09-10。厂商/维护者声明只证明其公开范围，未做安装、SDK 连通或 SQL 差分。

| 候选 | 官方/维护者证据与实际覆盖 | 精确缺口与本项目用途 |
|---|---|---|
| Snowflake 官方 Snowpark local testing | [官方说明](https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally)：DataFrame 本地操作、部分函数/UDF、内存 stage；明确不支持 raw `Session.sql`、异步、query history，状态不跨 session 持久 | M 的核心就是 `session.sql(query).collect()`，不能直接替代；文档建议按 SQL 文本 mock 返回仅适合单元样例，不适合未知任务。stage 默认假定已存在也违背本项目资源生命周期要求。只可辅助局部 DataFrame 测试 |
| fakesnow 开源模拟器 | 固定 [commit 57c35e39fc045dbca36fb8d58c8a3d69543484f2](https://github.com/tekumara/fakesnow/tree/57c35e39fc045dbca36fb8d58c8a3d69543484f2)，pyproject 自报 0.11.16，DuckDB~=1.5.5、SQLGlot~=30.17.0。维护者 [README:287–324](https://github.com/tekumara/fakesnow/blob/57c35e39fc045dbca36fb8d58c8a3d69543484f2/README.md#L287) 声明标准 SQL/cursors、information schema、多库、绑定、comments、pandas、result batches、HTTP server；日期/regex/半结构化/stages/COPY 部分支持，无 ACL 和 stored procedures | 可以作为协议/SQL 工程起点，不能作为无需改造的完整后端。MCP 所锁老 Connector+Snowpark 和 X 新 Connector 两套兼容性 U；有独立 HTTP server 能跨进程共享，比仅 in-process patch 更适合本仓库 |
| fakesnow 源码中额外边界 | [conn.py:27–104](https://github.com/tekumara/fakesnow/blob/57c35e39fc045dbca36fb8d58c8a3d69543484f2/fakesnow/conn.py#L27) 默认自动创建连接指定的 database/schema，名称大写且底层不区分 quoted case；[cursor.py:439–466](https://github.com/tekumara/fakesnow/blob/57c35e39fc045dbca36fb8d58c8a3d69543484f2/fakesnow/cursor.py#L439) 的 DDL 提交适配处于 `not autocommit` 分支，不能据此证明所有显式 BEGIN 组合正确 | 默认自动补库/schema 必须关闭/前置验证；quoted 名称需映射独立内部 ID；事务单列差分。不得启用任意 `nop_regexes` 伪造成功；clustering 被转 no-op（[ddl.py:99–105](https://github.com/tekumara/fakesnow/blob/57c35e39fc045dbca36fb8d58c8a3d69543484f2/fakesnow/transforms/ddl.py#L99)），在补齐可观察 cluster-key 元数据之前必须拒绝；只允许明确省略物理布局/性能优化，不能省略可读状态变化 |
| fakesnow 文件/COPY | [copy_into.py:210–263](https://github.com/tekumara/fakesnow/blob/57c35e39fc045dbca36fb8d58c8a3d69543484f2/fakesnow/copy_into.py#L210) 的显式 FILE_FORMAT 支持 CSV/PARQUET，缺 TYPE 或其他类型报不支持；ON_ERROR 只接受 ABORT_STATEMENT；stage 未找到报错（:296–316）。[server.py:74–79](https://github.com/tekumara/fakesnow/blob/57c35e39fc045dbca36fb8d58c8a3d69543484f2/fakesnow/server.py#L74) 将 stage array binding threshold=0，注释承认 PUT 支持不足 | 不据“支持 COPY”推断 JSON/AVRO/ORC/XML、所有加载错误策略、unload、GCS/Azure 或文件传输都可用。默认 S3 可用 AWS credential chain，模拟环境需显式本地 endpoint 与模拟凭据，不允许真实 fallback |
| LocalStack for Snowflake | [Feature Coverage](https://docs.localstack.cloud/snowflake/feature-coverage/) 明列 database/schema/table 基础操作、stage 与 COPY/GET/LIST/PUT/REMOVE、warehouse 和 task 多操作；同时列 TABLE TRUNCATE/UNDROP、ROLE GRANT/REVOKE 为不支持，external table 全项不支持。SQL functions 另有 [独立覆盖表](https://docs.localstack.cloud/snowflake/sql-functions/) | 可作为更广 API/CLI/Snowpark 候选，但勾选不证明具体参数、ACL、DDL 事务、精确 SQL 结果。动态文档未绑定镜像 digest，精确版本 U；[Quickstart](https://docs.localstack.cloud/snowflake/getting-started/quickstart/) 要 LocalStack Auth Token，许可/授权服务公网及离线运行条件待核验，不作为开源或完全离线的既定结论 |
| DuckDB + SQLGlot 自建适配 | DuckDB 1.5 [numeric](https://duckdb.org/docs/current/sql/data_types/numeric) 可用 DECIMAL，但除法返回浮点；[identifiers](https://duckdb.org/docs/current/sql/dialect/keywords_and_identifiers) 连 quoted 标识符也不区分大小写。SQLGlot [官方文档](https://sqlglot.com/sqlglot.html) 支持 Snowflake 转译并提供 unsupported error 配置，但转换是增量覆盖 | 作为关系执行内核可用，必须增加 Snowflake 语法/类型检查、quoted 名称映射、精确除法/scale、session/catalog/权限、函数语义。SQLGlot 不是服务执行器，转换成功不是行为等价。固定候选依赖版本后再评估，不用其输出独自生成期望答案 |
| SQLite / PostgreSQL | SQLite [类型说明](https://www.sqlite.org/datatype3.html)：动态 affinity、INTEGER/REAL/TEXT/BLOB 等，STRICT 也不提供 Snowflake NUMBER/TIMESTAMP/VARIANT 语义；公共设计的 PostgreSQL 只承担 metadata/事务存储 | 二者可存模拟器状态，不能直接暴露为 Snowflake SQL 后端；否则金额、布尔、时间、DDL/约束和信息模式的差异会训练错误行为 |

### 5.2 架构比较和选择

D：成本以相对投入表示，没有实测人日/吞吐。I/S/C/T/D/P 对应共享保真六维；“可精确”均需验收后才能成为发布声明。

| 路线 | 保真与成本判断 | 结论 |
|---|---|---|
| 保留固定 MCP，替换其 Snowpark/Connector 后端为本地 HTTP 服务 | I 最容易保留原始注册/包装；S 取决于 SQL 语义层；C 可让初始化/评测共用；T 必须补 ACL/session；D 由生成器；P 主要 CPU/内存/IO。协议兼容开发和双 SDK 维护成本较高 | **首选设计**：固定 MCP + 有明确 profile 的本地 SQL 服务；先比较 fakesnow HTTP 基础与自建适配，不假定候选可直接上线 |
| 保留 MCP handler，受控 SDK/client adapter→同一后端 RPC | I 接近原实现；绕过专有 wire 降首期成本；X 需 Connector cursor/DictCursor/commit/rowcount 和 Snowpark Row 转换；跨进程不能只 monkeypatch 一个解释器 | 备选/首期验证路径。必须明确支持的 SDK surface，未知方法报不支持，不吞掉 SQL |
| 有状态替代 MCP server | 容易加入可控时钟、取消和日志；重写 schema/错误/资源包装有 I 漂移，且不能省 X；若只替 MCP，C 不合格 | 仅当保留原 server 的接缝代价较高时使用，契约快照驱动；不是为四任务写专用工具 |
| 只做本地 HTTP/SQL API server | 有利于未修改 SDK/CLI 多入口，结果类型/Arrow/chunks/login/异步皆需对应协议。HTTP 协议与 MCP 是两层，不保证其中一层完成就全覆盖 | 随实际 X profile 扩展；官方 SQL API 不等同于 Python Connector 私有协议 |
| fixture/录制回放 | I 包装可作 golden；无法接受新 SQL、变更顺序或大规模新状态，S/C 弱，不能支持未来多样任务 | 仅用于契约/错误/已记录事务差分，不在线按任务匹配响应 |
| LLM 主导 SQL/响应/状态 | 初稿看似快，但精确计算、类型、全表检索、权限、事务都需独立执行器重算；一旦补齐校验，开发/运行成为双重系统，S/C/T 风险高、P 成本大 | 不作生产 SQL 主路径；受限实验也必须证明完整结果与终态，不靠 LLM 自评 |
| 代码执行 + LLM 预生成内容 | I/S/C/T 由代码；D 的业务领域和文本变化可受益；在线调用通常 0 次仿真模型，规模稳定 | **推荐整体路线**。文本只在初始化或真实允许的新内容创建时生成；工具读取不自动写分析/建议 |

两条首选接入方式都指向相同 authority：session/cursor→Snowflake 语义校验→已验收 SQL 执行组件/catalog→提交→SDK 行类型→原 MCP 序列化。对合法但未支持操作先返回 profile 明确的不支持，保留能力缺口；不会把 SQL 交给 LLM 猜一个成功结果。

## 6. 保真缺口与取舍

### 6.1 SQL 和服务语义支持边界

以下是 D 的分期目标；官方引用是 F，尚无本地运行等价证明。先制定按语法节点、函数签名、输入类型/边界、session 参数组合的支持表，支持任意合法组合中的已验收子集，而不是已知 SQL 文本 allowlist。

| 能力 | 核心语义及证据 | 实现层级/偏差风险与检查 |
|---|---|---|
| 查询方言 | P1：SELECT/CTE、JOIN、子查询、CASE、GROUP/HAVING、窗口/QUALIFY、ORDER/LIMIT、CAST/TRY_CAST、常用字符串/日期函数；P2 扩大 PIVOT/UNPIVOT、LATERAL/FLATTEN、数组/对象；P3 长尾函数/高级数据类型 | 代码执行、语法/类型先验；只转函数名会错隐式转换、窗口 frame、排序 NULL。Snowflake→AST→内部执行必须有独立反例；不接受 DuckDB 专有 SQL 为合法 Snowflake |
| NULL 与空值 | SQL NULL 的三值逻辑、IS NULL、COUNT(*)/COUNT(col)、聚合空集、NOT IN 含 NULL、外连接；空字符串/0/false/无行不是同一事物 | 可较准确复现，P1；小关系穷举。M 空集哨兵只在输出投影，X 与权威 rows 保持真空集；不得让哨兵参与 JOIN/COUNT |
| NUMBER/DECIMAL | Snowflake NUMBER 默认 (38,0)，最大精度 38、scale 37；DECIMAL/NUMERIC 同义；INTEGER 别名不是固定 32/64 位（[官方 numeric](https://docs.snowflake.com/en/sql-reference/data-types-numeric)） | P1 必须保留 exact arithmetic、溢出/舍入、结果 precision/scale；DuckDB DECIMAL 除法不等价，Z 的 float 输出也不等于后端 float。用大于 2^53 整数、进位、小数分摊、聚合后 cast 验证 |
| FLOAT/NaN/序列化 | Snowflake FLOAT 为 64 位，并定义特殊 NaN 比较（同上官方 numeric）；Z 对 YAML/JSON NaN 的路径不同 | 代码实现并保留原始值；NaN/inf/负零须独立边界。不能统一所有数值为 float 或所有 NaN 为 SQL NULL。新 DECFLOAT 等后端类型与老 Connector/Snowpark 兼容性 U，不从新官网推定 M 已正确支持 |
| 时间 | DATE/TIME、TIMESTAMP_NTZ wallclock、LTZ 与 session TIMEZONE、TZ 记录 offset；TIMESTAMP_TYPE_MAPPING 默认 NTZ，fraction precision 0–9（[官方 datetime](https://docs.snowflake.com/en/sql-reference/data-types-datetime)） | P1 常用三类型与虚拟日期/时区，P2 扩大格式/纳秒/边界函数。TZ 不是永久保存 IANA zone；月份跨 DST 不应由库偷偷重算为 LTZ 行为。SDK Python datetime 与纳秒返回精度 U；M/X 类型及显示分层对比 |
| VARIANT/OBJECT/ARRAY | VARIANT 保存值与类型；SQL NULL 与 JSON null 不同（[半结构化类型](https://docs.snowflake.com/en/sql-reference/data-types-semistructured)）；PARSE_JSON 的空输入、重复键参数和类型转换需专门处理（[函数文档](https://docs.snowflake.com/en/sql-reference/functions/parse_json)） | P1 受限合法 JSON 与 NULL 三分，P2 FLATTEN/路径/类型函数；缺键和 SQL NULL/JSON null 不用单个 Python None 表示。不能以 SQLite JSON/DuckDB STRUCT 直接等同 |
| 标识符与 catalog | 未引用名称大写，双引号默认保留大小写/支持点与转义；QUOTED_IDENTIFIERS_IGNORE_CASE 会改变解析（[官方 identifiers](https://docs.snowflake.com/en/sql-reference/identifiers-syntax)） | P1 即需完整基本解析；内部 ID 映射能绕开 DuckDB quoted case 不敏感。M describe 的 split/upper 缺陷只在 wrapper；INFORMATION_SCHEMA 的列类型/顺序/注释/权限与 SHOW 结果各自验收 |
| DDL/约束 | CREATE/ALTER/RENAME/DROP、defaults、comment、CTAS、temporary/transient/permanent；标准表 PK/FK/UNIQUE 不强制，NOT NULL 强制；hybrid tables 不同（[约束文档](https://docs.snowflake.com/en/sql-reference/constraints-overview)） | P1 标准表核心，P2 views/sequences/历史，P3 hybrid/高级策略。不能把“状态不变量”误解为替标准表强制外键；生成器可以保证业务关系，但服务必须允许真实可接受的重复 PK。CHECK 等新增语义需 dated profile |
| DML/MERGE | INSERT/UPDATE/DELETE、批量、MERGE 匹配重复/非确定行为、affected rows、失败不应无条件全批吞错 | P1 核心 DML，P2 扩 MERGE/复杂更新；独立前后多重集合、行计数、副作用约束。不能用最后一条 SQL 返回成功代替之前部分执行结果 |
| 事务/会话 | DDL 单独事务且提交活动事务；AUTOCOMMIT/BEGIN/COMMIT/ROLLBACK；READ COMMITTED 每语句可见已提交态及自己的写（[官方 transactions](https://docs.snowflake.com/en/sql-reference/transactions)） | P1 事务基本组合，P2 并发/锁/错误恢复。不能把 DuckDB snapshot isolation 或公共 PostgreSQL SERIALIZABLE 直接当 Snowflake 行为；B 同步 collect、1800 秒会话重建也要区分协议兼容与调度设计 |
| Warehouse/query/job | warehouse 必需场景、USAGE/OPERATE、suspend/resume/auto_resume/配额（[官方 warehouse](https://docs.snowflake.com/en/user-guide/warehouses-tasks)）；Connector async/query ID/cancel 是额外 X 能力（[Connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-example)） | P1 执行前权限/warehouse 条件与 query ledger；P2 运行/超时/取消/排队。M 无专用 job tool，collect 默认同步，不伪造异步句柄；查询时间/credit 估计可近似，但执行结果/是否提交不能近似 |
| Query result/history | SQL 可用 query history/RESULT_SCAN 等服务特有能力；[RESULT_SCAN](https://docs.snowflake.com/en/sql-reference/functions/result_scan) 的访问/结果保留规则不同于普通表 | P2；真 query ID/result snapshot/owner/session 关联。M 随机 data_id 不可充当 sfqid，更不能凭 data:// URL 声称可读取保存结果 |
| Stage/COPY/对象存储 | internal named/user/table stage 与 external storage，FILE_FORMAT、压缩/CSV/JSON/Parquet、错误策略、FILES/PATTERN、load history/FORCE；[COPY INTO table](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table) | P2 初始 internal stage+CSV/Parquet+受限错误策略，P3 扩格式/外部源/unload/notifications。M 任意 SQL 可能送 COPY/PUT/GET/CALL，但固定 Snowpark/Connector 实际可用组合 U；每类先验证再开放，禁止 silent no-op |
| Tasks/procedures/高级平台 | SQL 可以定义任务及其执行计划（[CREATE TASK](https://docs.snowflake.com/en/sql-reference/sql/create-task)）；有程序执行、streams/pipes、time travel/cloning、Cortex/外部函数等长尾 | P3 按合理任务价值择能力扩展。仅元数据 CRUD 不等于执行；未提供真实解释器/隔离执行组件的代码或 SQL procedure 明确不支持。billing/物理集群实现可省，但影响工具观察的状态/错误不可省 |

### 6.2 近似与训练风险

可较准确复现：固定 schema/工具说明、文本包装、catalog 基础、session ID/权限、typed 核心 SQL、真实变更后的跨入口可见性。可近似且必须标注：warehouse 调度时延、成本统计、规模性能、业务文本分布；近似不能改变最终行集或许可结果。分期高成本：完整 Snowflake 方言、复杂类型/函数、程序执行、stage/error/loading 全组合、time travel 与并发异常。证据不足：实际镜像、MCP input-validation 版本、SDK raw types/错误、远端时延/账号策略。

典型错误规律及检测：总自动建库→遗漏资源准备（缺库连接/查询负例）；所有写都成功→忽略权限/约束（拒绝前后 hash）；PK 都强制→错误使用标准表约束（标准/hybrid 对照）；DDL 都可回滚→丢失事务模型（BEGIN→DML→DDL→ROLLBACK）；Decimal 全 float→学错财务结果（精确 oracle）；空集=success 行→把包装当数据（M/X 双检查）；CREATE 表字符串自动改写→学错名称解析（quoted/大小写/CTAS 反例）；对未支持 SQL 使用 LLM 给答案→学到不存在函数和虚构行（AST+独立执行+零幻觉准入）。

B:50–55 的注释说不设置 database/schema，但实际将完整 `connection_config` 交 Session builder；没有过滤这些键。后续 `USE WAREHOUSE` 没有 collect；[官方 Snowpark 1.36.0 的 Session.sql 源码:2774–2788](https://github.com/snowflakedb/snowpark-python/blob/v1.36.0/src/snowflake/snowpark/session.py#L2774) 明确为 lazy，不能把该语句视为已执行。B:19,68–75 的 1800 秒重连可能重置当前 session 参数/临时状态；实际 M resolved SDK 行为需受控验证，不能据注释固定 mock 初始化上下文。

## 7. LLM 仿真可行性

### 7.1 职责与可验证性

D：推荐**代码主导、内容预生成的混合路线**。LLM 适合按预先生成的 schema/合法关系提出公司、客户、产品、发票备注、工单描述、JSON 业务内容、column comments 和干扰文本；也可辅助离线提出覆盖 SQL 边界的场景，由独立执行器验证。数据中嵌入的提示/命令始终视为业务文本。

LLM 不适合决定 SELECT 行集/聚合金额、SQL 是否成功、affected rows、权限、catalog 是否存在、事务可见性、ID、分页排序、stage bytes/hash、任务执行完成。`append_insight` 真实意图是保存 agent 提交文本，仿真器不得额外替 agent 写分析；read_query 的说明不提供 SQL 纠错服务，不能偷偷修复 SQL 或补表。解释复杂 SQL 也不能只靠模型，因为要证明解释正确仍需类型检查与独立执行。

| 路线 | LLM 可决定的部分 | 硬校验与长期成本 |
|---|---|---|
| 代码 | 无在线 LLM；规则生成内容/数据，确定性执行 SQL | 前期方言/协议开发较高；可缓存并稳定扩展，运行成本 CPU/存储/IO |
| LLM 主导 | 候选可提响应/受限状态变化，但所有已有值必须带来源、结果必须执行验证；仅为对照研究 | 若 SQL 要重算才能验对，模型不能省执行器；还要 prompt、版本、漂移检测与重试。长表不可能靠完整上下文读取；开发节省不确定、百万调用成本高 |
| 混合 | 初始化文本及受限业务数据提案；在线 SQL/目录/写入全代码；可选离线长尾场景生成 | 生成内容写入合法初态后反复读相同状态；按环境摊销费用。主路径不增加工具延迟，最易验证内容多样性是否有收益 |

### 7.2 若评估在线 LLM，必须具备的状态流程

调用+session/profile→确定性 schema/权限/SQL 解析→读取所需 catalog、所有相关 typed 行/索引、事务快照与版本→LLM 提案→外部规则/执行器逐字段核对→按真实单语句/批量边界提交→从提交态渲染响应。模型不能获取任务答案、oracle 目标行集合或成功轨迹。

对 SQL，相关状态不是“检索几个相似行”：范围由查询计划决定，负查询必须检查完整对应索引；大行集使用真实执行后端，模型只见已授权结构/必要引用，摘要不得作为数值真值。若提案需要全部行才能验证，检索/分块完成后仍交执行器，不允许上下文超限时忽略行。schema、权限或 SQL 本身非法直接返回真实错误，不送模型重解释。

提案必须携带读版本、值来源、受影响主键/内部行 ID 和受限变更；缺引用/数值不一致不提交。至多一次内部修复（A），仅传 validator 发现的问题；仍失败返回显式仿真基础设施错误并隔离训练样本。并发冲突重取真实快照后按服务语义处理；批量 DDL 仍逐项提交，不能为 LLM 操作统一包一层原子事务。响应不能先发 success 再异步尝试提交。

缓存键包括 episode、profile、principal/role/ACL 版本、session 参数、SQL/绑定、读快照、虚拟时间和模型/prompt 版本；CURRENT_TIMESTAMP、变量/临时表/RESULT_SCAN 不可沿用仅 SQL 文本缓存。记录输入状态引用/hash、模型版本/prompt、输出、校验、重试和最终事件/响应；回放使用已记录输出与状态事件，不重新采样模型，固定 temperature 不构成复现证明。

独立验证应覆盖同状态重复读、长序列漂移、写后所有入口读取、数值和行来源、无权限/缺表/无效参数诱导、JSON 内恶意指令、过度成功与附加解题提示。采用非同源规则、人工审定小表、受控真实记录与人工盲审；不能用同一个仿真 LLM 自评。

### 7.3 规模成本和对照试点

A：代码工具路径每调用 0 次仿真模型；在线 LLM 路线按 1 次提案、最多 1 次修复估算；混合初始化每个业务数据块若干次、在线通常 0 次。采用公共公式 `N*f*(1+r)*(Tin*Pin+Tout*Pout)/1e6`；Pin/Pout 为每百万 token 费率，另加初始化、独立验证和失败废弃成本。

与公共设计保持同一**虚构规划参数**：N=100 万、Tin=8k、Tout=1k、r=0.1，Pin=$2/Pout=$8 时全在线约 $26,400；每调用约 $0.0264。不是供应商报价或实测；更长查询状态/修复会线性或更快放大成本。模型调用平均 3 秒则 100 tool/s 的全在线路径约需 330 个在途请求、880k input tokens/s；尾延迟和 SQL/校验另计。混合预生成费用约为生成块数×单块费用，不能虚称 f=0 就没有初始化模型费。

前期开发比较按契约适配、SQL 规则、SDK/HTTP、生成器、validator、差分语料、模型 prompt/回放分别记工时；LLM 主导省不了精确执行与权限/事务组件，可能增加双重维护。降本采用提前内容生成、按 immutable snapshot 缓存、批量独立 episode、确定性高频路径；仿真模型型号按试点评估，不因分析作者使用 astra 就预设部署也用 astra。

建议 LLM 对照：同一已验收 SQL/profile 和 schema/关系分布，两组分别用规则模板或 LLM 生成工单/交易备注/商品描述/JSON 噪声。硬 validator 检查引用、长度、类型与任务可解性；在未见业务领域和 JOIN 图上盲测真实迁移、文本重复/名称泄题、幻觉引用、有效轨迹成本。这能评估**内容合成价值**，不能证明 LLM 在线算 SQL 可行。若研究后者，只在小表、少量确定函数、独立手算 oracle 的隔离试验中比较三路线，任一错误行/非法接受/越权即不进入训练；不将该实验宣传为全 Snowflake 仿真。

## 8. 合成、验证与分期

### 8.1 多样初态与任务对应

D：按 seed 独立采样 account/库/schema 数、表/视图数量、行数、列名/quoted 名称、业务领域、join 图、NULL 密度/重复键/长字符串、NUMBER 精度/scale、时区/DST、VARIANT 缺键/深度、角色/warehouse、stage 文件大小/格式/坏行、历史与事务冲突。0/1/页边界/大表分层；业务约束生成合法主干，再加不影响可解性的干扰。不用固定 `target_*` 名称或表顺序泄露答案，也不能把未强制的标准表 PK 当生成器唯一现实分布。

环境先行：从合法初态提业务谓词任务；约束先行：构造需要的表/角色/权限/文件，再独立验证存在至少一条正确路径。任务生成器可看私有目标，模拟器只接世界状态；oracle 目标不进入 SQL 响应或仿真 prompt。可解检查还应验证工具 profile 可观察性：精确大金额若只被有损 M 包装观察，须提供合法无损路径或判定不适合该 profile，不能让 oracle 要求 agent 不可能得到的精度。

组合采样包括多库查找、事务后恢复、目录与直接 SQL 交叉、多入口写后读、缺表/权限恢复、stage 导入、跨服务文件传递、JSON 清洗、业务约束变化；按 SQL 能力族、JOIN 拓扑、调用图和业务领域留独立 holdout。允许与参考 SQL 不同的正确查询，只按最终 typed 数据/业务结果和副作用判断。

### 8.2 独立 oracle 与差分验证

| 验证面 | 设计用例、独立依据和准入 |
|---|---|
| 契约 | 固定 14 工具的 name/description/schema、6/14/exclude/prefetch 配置矩阵、YAML/EmbeddedResource/专用写文本、empty/large/error；原始 MCP 与 harness 投影双 golden。空 schema prefetch→错误 string→resources/list keys 失败与非空成功快照成对验证；MCP SDK input validation、resource error code、通知能力先补离线固定环境快照 |
| 核心 SQL | 由另一实现/作者给出的 typed 小关系枚举、精确 Decimal 和三值逻辑 oracle、官方边界例子；JOIN 多重集合/COUNT/NULL/窗口/日期/quoted identifiers/非法 cast。禁止执行引擎与 oracle 共用同一 SQLGlot 转译作为唯一依据 |
| 状态/目录 | 建库/表/改列/comment/default/rename/drop 后独立 catalog snapshot 与 Connector/MCP 交叉；拒绝写后检查无变更；标准表 PK 重复与 NOT NULL 拒绝对照；batch 重复名/中途失败不误判原子性；空 schema 的 create_tables/drop_tables 预检失败且零 DDL 副作用；合法 create_table/write_query 建首表后再测批量，修复 profile 的直接批建另立期望 |
| 事务/会话 | 两个 session 交叉 BEGIN/DML/读/commit/rollback/DDL；AUTOCOMMIT 两种、USE/角色切换、临时表同名遮蔽、1800 秒重连；对合法 READ COMMITTED 历史做检查，不强制所有事务可串行化 |
| 多入口 | MCP→Connector、Connector→M、初始化独立 MCP→agent MCP→eval Connector；Cursor/DictCursor/rowcount/Decimal/date 对照；M 随机 data_id 与真实 query ID 分开；同库名不同 episode 零串读 |
| Stage/执行 | 独立 bytes hash、CSV/Parquet/JSON parser 与目标表 oracle；重复 COPY/坏文件/ON_ERROR/FORCE/load history；warehouse suspended/权限/超时、query cancel 和 task run 需真实执行证据 |
| 未见组合/质量 | 多 seed、相似名称、未知 JOIN 图、不同正确顺序、读写混排、100–1,000 步序列；文本来源/分布盲审，监测资源幻觉、非法接受、成功偏差、答案泄漏与请求结果/提交态分歧 |
| 故障/隔离 | 提交前后断开、序列化失败、响应丢失、重启/clone/reset、旧 job/cursor generation；独立日志重建 state hash。不能因看见 Error 文本就假定 SQL 未提交，也不能对非幂等 INSERT 无条件重试 |
| 成本 | 同 profile/规模/语义门槛比较代码/LLM/混合有效轨迹成本、吞吐、p50/p95、CPU/RAM、读写 bytes、token/修复率；未过保真门槛不比较“便宜成功率” |

独立 oracle 读取只读 typed snapshot、提交事件、blob 与必要的第二入口，不用 `success` 或 agent 总结。对 oracle 做 mutation：漏 WHERE、NULL 当 0、少一行/重复行、Decimal 舍入、假 commit、丢 comment、跨 session 错状态、DDL 回滚、越权写、stage 不写 bytes，要求评测拒绝。现有 finalpool 评测中金额 tolerance/邮件验证只是局部回归，不足以证明完整 SQL 保真。

未来真实差分需要独立 Snowflake 测试 account 或严格限定数据库、角色/warehouse、合成数据、可执行管理与写入清单、费用/调用/文件大小限制和脱敏记录；本阶段只设计，不执行。固定 MCP+两 SDK 版本+账号/session 参数→相同逻辑初态→合法/非法操作图→收集每步原始响应、typed 结果与独立终态→按能力解释差异→保留未用于调参的 holdout。

动态 ID 以一致双射比较并保留引用；M data_id 与 query ID 用两张映射表。时间字段按 NTZ/LTZ/TZ、时区和精度比较，CURRENT_TIMESTAMP 以受控 clock 为基准；没有 ORDER BY 按多重集合，有 ORDER BY 按完整排序/同键不确定规则。数值/NULL/rowcount/ACL/提交副作用不得用宽泛容差消掉；仅网络耗时/系统统计可以声明近似。已有记录只能验证其覆盖的契约/路径，目前没有可用 Snowflake 记录，因此真实差分仍为 U。

### 8.3 并发、隔离和复现

episode 有独立 account/authority namespace、generation、principal/session map、SQL 数据文件/进程或分片、stage roots、clock、query/task 队列。不能仅在数据库名加前缀：SQL 的 SHOW/INFORMATION_SCHEMA、未限定名称、临时表、results cache、SDK login、stage 路径都必须隔离。初期每 episode 独立执行 worker/数据库快照最易审计，后续再用分片多租户；不能让 DuckDB 的跨进程文件写锁替代服务层并发协议。

共享不可变 blob/seed snapshot 用 copy-on-write；冻结或协调未提交事务与在途 job 后取一致快照。记录软件/语义/生成器/oracle 版本、依赖 hash、seed、clock、调度顺序、session 配置、原始/规范化 SQL、绑定、结果类型/元数据和 commit 事件。reset 创建新 generation 并拒绝旧 session/job 回写；只重启 MCP 不能重置 Connector 可见表。恢复响应丢失用提交收据诊断，用户重发的非幂等写仍按真实行为处理。

瓶颈是同步 collect 的事件循环阻塞/大结果内存、SQL 聚合和精度计算、catalog metadata 查询、stage IO/压缩、持久写锁、结果缓存/回放体积，及在线 LLM 的 token 配额。用独立 worker、结果分块存储、只在完成 collect 后保留真实 M 投影、内容去重和批量生成降成本；不能为了吞吐返回截短 rows 却不标明。

### 8.4 分期与验收门槛

| 阶段 | 范围/迁移价值 | 门槛（D，尚未执行） |
|---|---|---|
| P0 契约与路由 | 14 工具/资源/prompt 快照、配置组合、strict/fixed profile 决策、双 SDK 路由、typed authority、权限/session/clock/oracle 骨架 | 所有工具契约有来源；固定缺陷逐项解释；未知能力明确失败；M/X 同 episode 可交叉观察，跨 episode 无串扰 |
| P1 SQL 核心试点 | 多库/schema/table 基础、读/写/建删/列注释、NULL/NUMBER/日期/quoted identifiers、JOIN/聚合/窗口、基础事务、warehouse 条件；未支持长尾列明 | 接口/typed 结果/权限/终态无未解释差异；关键负例和组合 oracle 检出所有注入错误；受控真实差分后才宣称较高保真 |
| P2 组合扩展 | VARIANT/FLATTEN、MERGE、views/sequences、复杂事务并发、query history/result、stage/COPY 和基础 async/cancel；SDK/CLI 扩 surface | 各新增函数/输入边界有独立期望；文件 bytes/load history 一致；类型/事务/quoted 名称不被候选引擎弱化 |
| P3 长尾与规模 | task/procedure 的受限真实执行、外部 stage/unload/time travel/cloning、更多类型/函数、跨 Cloud 工作流；1→10→100→1,000 episode 梯度 | 新语义先真实差分；未见操作图和长序列通过；snapshot/reset/replay hash 一致；性能测量保留相同权限和精度语义 |

Snowflake 适合作为首轮通用表格试点之后的 **SQL 精度+事务+多入口** 专项试点：既有财务/工单样例，又能构造未见分析任务。其主试点验证执行一致性，LLM 内容价值用 §7 的独立对照，不能把“代码 SQL 通过”外推成“LLM 算 SQL 通过”。优先级由迁移风险/验证成本决定，不按现有四任务覆盖率排序。

## 9. 待确认与审查记录

| 项目 | 当前证据/下一步 |
|---|---|
| 实际运行镜像/依赖 | U：裸 uvx 的实际包 provenance、MCP SDK/sqlparse/Serializer/Snowpark/Connector resolved versions；源码固定不等于运行验证 |
| MCP 原始快照 | U：input schema 校验 coercion/错误包络、isError 默认、resources 能力、prompt/resource 未知错误、协商 protocol version；应在不会触达业务后端的固定依赖环境采集 |
| SDK 类型和执行边界 | U：Snowpark 与 Connector 对 NUMBER/TIME/binary/VARIANT/纳秒、重复列名/asDict、多个 SQL statement、COPY/PUT/GET/CALL 的实际接受与传输；不因任意 query 参数推定后端均可用 |
| 账号/session/warehouse | U：默认 role/时区/仓库 auto_resume、信息模式当前库前提、重连、锁/异步/取消、错误 SQLSTATE/errno 和真实延迟分布 |
| fakesnow 候选 | F：固定源码/README 已核；U：双版本 SDK、Snowpark connect、HTTP chunks/Arrow、quoted 名称修正、ACL/事务/精度/COPY、克隆吞吐未验；自动补库和 no-op 必须消除或显式限定 |
| LocalStack 候选 | F：官方覆盖表明确缺项；U：镜像版本/digest、授权/离线要求、真实参数覆盖与执行语义/成本，无部署验证 |
| 调用记录 | 仓库检索未发现 Snowflake 真实轨迹；没有以现有输出伪充后端差分；将来需要受控合成账户记录 |
| 公共发现已上报 | 14 工具；memo dispatch TypeError；空集哨兵/Decimal 投影；prefetch help 与过滤不符；M 与 X 两套 SDK/session/凭据路由；Snowflake 标准表约束不能套公共“强 FK”模型 |
| 作者处理原则 | 仅本文，未修改任务或 mock；严格源码兼容和未来修复 profile 分开，动态服务规范按查阅日期标注；公共材料由统筹复核后合并 |
| 非原作者交叉审查 | 2026-09-10，`/root/github`（gpt-6-astra / xhigh）完成审查；SF-01/P2 指出 B:79–87 的空集哨兵使 S:529–535/595–600 的 TABLE_NAME 预检失败，并触发 S:647–659→987–994 的 prefetch/resources 链式失败。原作者重读固定源，已补 §2.1–2.3、§4、§8 和矩阵，严格/修复 profile 分开；统筹复核合入 shared F26。审查对 14 工具、6 个固定源码文件、fakesnow/Snowpark/LocalStack 候选、SQL/LLM/成本及独立 oracle 未提出其他实质问题；其余 U 保留，静态审查不代替业务运行验证。 |

## 10. 能力矩阵行

```csv
object,tool_or_capability,version,operation_type,state_dependencies,proposed_method,llm_role,fidelity_gap,verification_method,priority,evidence
snowflake,list_databases_list_schemas_list_tables,bca38f3ef5305ac53b9935bd09edbfac442b6a36,R,catalog role session allowlist exclusion_patterns,real_MCP plus shared_SQL_catalog,seed_comments_only,case_inconsistent_allowlist and no_pagination; INFORMATION_SCHEMA_visibility,contract_snapshot plus SDK_catalog_cross_read,P1,S:90-229; S:727-763
snowflake,describe_table,bca38f3ef5305ac53b9935bd09edbfac442b6a36,R,column_types_defaults_comments quoted_names,real_MCP plus shared_catalog,seed_comments_only,split_dot_and_uppercase_wrapper_breaks_quoted_names,quoted_identifier_cases plus independent_metadata_oracle,P1,S:232-277; S:764-778
snowflake,read_query_core_SQL,bca38f3ef5305ac53b9935bd09edbfac442b6a36,R/E,typed_rows catalog role session warehouse,verified_Snowflake_semantics plus SQL_executor,initial_business_content,finite_SQL_profile; empty_rows_sentinel; Decimal_float_projection,independent_typed_oracle plus real_Snowflake_differential,P1,S:280-312; B:68-87; Z:14-69
snowflake,write_query_DML_DDL_session,bca38f3ef5305ac53b9935bd09edbfac442b6a36,W/E/A,rows catalog session transaction privileges,deterministic_executor plus session_state,none,description_narrower_than_dispatch; SELECT_prefix_only; allowlist_parser_gaps,commit_history plus multi_session_differential,P1,S:324-337; W:10-98
snowflake,create_table,bca38f3ef5305ac53b9935bd09edbfac442b6a36,W/A,catalog types defaults session role,real_MCP plus SQL_DDL,none,CREATE_TABLE_prefix_restriction; no_allowed_database_check,DDL_metadata_rows_and_permission_oracle,P1,S:620-627; S:816-826
snowflake,create_databases_drop_databases,bca38f3ef5305ac53b9935bd09edbfac442b6a36,W/A,database_hierarchy ownership dependencies,deterministic_catalog_DDL,none,asymmetric_allowlist_errors; partial_batch_and_duplicate_names,per_item_commit_log plus independent_catalog,P1,S:340-420; S:827-860
snowflake,create_schemas_drop_schemas,bca38f3ef5305ac53b9935bd09edbfac442b6a36,W/A,database_schema_hierarchy ACL,deterministic_catalog_DDL,none,precheck_snapshot_not_refreshed; partial_success,mixed_valid_invalid_batches plus SDK_reads,P1,S:423-506; S:861-902
snowflake,create_tables_drop_tables,bca38f3ef5305ac53b9935bd09edbfac442b6a36,W/A/E,catalog SQL_definition dependencies role,real_MCP plus verified_DDL_backend,none,empty_catalog_sentinel_causes_TABLE_NAME_precheck_failure; regex_case_replace_target_gaps,empty_schema_zero_DDL_then_legal_first_table plus independent_catalog,P1,B:79-87; S:529-535; S:595-600; S:903-964
snowflake,append_insight_and_memo_resource,bca38f3ef5305ac53b9935bd09edbfac442b6a36,W_local/R,mcp_session_memo notification_state,strict_profile_error; fixed_profile_deterministic_append,none,unexpected_allowed_databases_kwarg_prevents_append,signature_audit plus error_and_unchanged_memo_snapshot,P0,S:315-321; S:977-1010; S:1043-1050
snowflake,prefetch_context_resources_and_prompts,bca38f3ef5305ac53b9935bd09edbfac442b6a36,R,mcp_process_prefetch_catalog_snapshot,real_MCP plus session_snapshot,none,empty_catalog_sentinel_to_error_string_to_keys_failure; stale_prefetch; help_visibility_gap; data_URI_not_readable,empty_schema_resource_failure plus nonempty_config_contract_matrix,P0,B:79-87; S:647-659; S:987-994; S:967-1018
snowflake,SQL_NUMBER_NULL_TIME_VARIANT_identifiers,bca38f3ef5305ac53b9935bd09edbfac442b6a36,R/W/E,typed_rows precision_scale timezone name_resolution,semantic_adapter plus verified_execution_kernel,seed_text_and_JSON_only,DuckDB_SQLite_not_equivalent; serializer_loss_separate_from_state,exact_decimal_3VL_time_and_quoted_oracles,P1_P2,Z:14-69; official_Snowflake_types_identifiers_docs_2026-09-10
snowflake,SQL_transactions_warehouse_query_history,bca38f3ef5305ac53b9935bd09edbfac442b6a36,E/A,session transaction warehouse query_result role clock,deterministic_state_machine plus actual_SQL_execution,none,DDL_implicit_commit_READ_COMMITTED_and_reconnect; MCP_data_id_not_sfqid,multi_session_history plus real_differential,P1_P2,B:19-87; official_transactions_and_warehouse_docs_2026-09-10
snowflake,SQL_stage_COPY_PUT_GET_external_storage,bca38f3ef5305ac53b9935bd09edbfac442b6a36,R/W/E,stage file_format bytes ACL load_history,blob_API plus format_parser_SQL_loader,seed_file_content_only,M_SDK_acceptance_pending; fakesnow_partial_formats_and_ON_ERROR,byte_hash_independent_parser_and_load_history_oracle,P2_P3,S:324-337; fakesnow_57c35e3_copy_into.py:210-263
snowflake,SQL_tasks_procedures_and_advanced_features,bca38f3ef5305ac53b9935bd09edbfac442b6a36,E/A,definition role schedule execution_runtime history,staged_real_executor_or_explicit_unsupported,scenario_generation_only,not_dedicated_MCP_tools; no_fake_execution_success,execution_artifacts plus state_history_and_controlled_real_cases,P3,S:324-337; official_CREATE_TASK_docs_2026-09-10
snowflake,X_Connector_Snowpark_initialization_evaluation,repository_ef7ab5928062defc0dc2a91a4c26ddebccb1a6a7,R/W/E/A,shared_authority separate_sessions global_and_local_principals,local_HTTP_or_SDK_adapter_to_same_backend,none,M_Connector_below_3.14_vs_X_3.16; helper_new_connection_each_call,M_X_cross_read_and_commit_visibility_isolation,P0,utils/app_specific/snowflake/client.py:10-119; uv.lock:3125-3126; P:8-16
```
