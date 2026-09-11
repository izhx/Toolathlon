# google-cloud 高保真模拟可行性与设计

> 作者：领域 agent `/root/google_cloud`；创建时显式指定 `gpt-6-astra / xhigh`，本次修订沿用同一会话。非原作者审查者：`/root/wandb`，同为 `gpt-6-astra / xhigh`；已完成源码与设计审查，C-01 已由作者修订，统筹复核已闭环。查阅日期：2026-09-10。仓库 HEAD：`ef7ab5928062defc0dc2a91a4c26ddebccb1a6a7`；安装基线：`7df9ca22115002e0cea75deec595492c520df3e1`。已读原始要求、[共享约定](../shared.md)、[统一模板](../service-template.md) 和 `docs/mcp-analysis.md`；未发现适用 AGENTS.md。只读取源码、官方资料并编写本文，未导入任务配置、启动 MCP/benchmark、执行初始化或真实服务写入。F=已核实事实，D=设计，A=规划假设，U=待确认；源码基线不等于实际运行镜像。

**结论（D）：可以形成覆盖全部 39 个注册工具的分期设计；接口包装可较精确复现，BigQuery 必须限定并验证 SQL 语义范围，Storage/Logging/Compute 必须实现相互关联的持久状态。首选代码执行与状态机，辅以 LLM 生成初始业务内容。** 复用现成模拟器能降低成本，但不能直接宣称 IAM、SQL、签名 URL、异步操作与真实云端兼容。严格版本兼容和未来修复版本分别建 profile，缺陷绕过轨迹不自动进入主要训练数据。

## 1. 范围、版本与入口

### 1.1 固定证据与版本差距

以下源码链接固定到安装提交，本文 `S/B/G/L/C` 行号分别指这些文件，不指临时下载目录：

| 引用 | 固定来源与核实内容 |
|---|---|
| S | [src/server.py](https://github.com/lockon-n/google-cloud-mcp/blob/7df9ca22115002e0cea75deec595492c520df3e1/src/server.py)，1–1225；39 个 `@mcp.tool()`，无业务 resource/prompt 注册 |
| B | [src/big_query.py](https://github.com/lockon-n/google-cloud-mcp/blob/7df9ca22115002e0cea75deec595492c520df3e1/src/big_query.py)，20–403；SDK 查询、加载、导出和 jobs |
| G | [src/cloud_storage.py](https://github.com/lockon-n/google-cloud-mcp/blob/7df9ca22115002e0cea75deec595492c520df3e1/src/cloud_storage.py)，18–784；对象与 bucket 管理 |
| L | [src/cloud_logging.py](https://github.com/lockon-n/google-cloud-mcp/blob/7df9ca22115002e0cea75deec595492c520df3e1/src/cloud_logging.py)，20–853；日志数据面与 ConfigServiceV2 |
| C | [src/compute_engine.py](https://github.com/lockon-n/google-cloud-mcp/blob/7df9ca22115002e0cea75deec595492c520df3e1/src/compute_engine.py)，18–381；Instances/Zones/ZoneOperations SDK |
| P | [pyproject.toml](https://github.com/lockon-n/google-cloud-mcp/blob/7df9ca22115002e0cea75deec595492c520df3e1/pyproject.toml)，5–7、34–41、50–54；包自报 1.0.0，依赖仅下界，entry point 为 `src.server:main` |

F：本次通过固定 raw URL 逐字节比较了全部 6 个 `src/*.py` 和 `pyproject.toml`，均与已有下载内容一致；`server.py` SHA-256 为 `856a67cf0d814c253b47cd5d028f7aff6dcfce2461e46753a416c67dd23aff63`。源码来自第三方 `lockon-n`，后端调用 Google 官方 SDK；不是 Google 发布的 MCP server。

F：`global_preparation/install_env.sh:207` 安装上述 commit；`configs/mcp_servers/google-cloud.yaml:4-24` 用裸 `uvx google-cloud-mcp` 启动 stdio，并传项目、凭据文件和四类 allowlist，client timeout=30 秒、缓存工具列表。安装提交固定而启动命令不含提交号，运行环境需另取包 provenance。MCP 包依赖 `mcp>=1.11.0`、BigQuery>=3.23.0、Storage>=2.14.0、Logging>=3.8.0、Compute>=1.19.0；仓库 X 层 `uv.lock:931-983` 则固定 BigQuery 3.35.1、Logging 3.12.1、Storage 3.3.1。两个 Python 环境不能假定相同，FastMCP 生成的完整 JSON Schema、协议版本及 Pydantic 强制转换还需离线运行快照。

### 1.2 M/B/X 分层与认证

| 层 | 范围 | 设计边界 |
|---|---|---|
| M | BigQuery 8、Storage 13、Logging 9、Compute 9 工具，全部无条件注册；允许列表只影响调用/返回，不隐藏工具（S:123–1191） | 全量工具契约为最终边界；任意 SQL 是一个执行入口，不是少数 SELECT 模板 |
| B | SQL catalog/typed rows/jobs、GCS bucket/object/version、Logging log/entry/bucket/sink/filter、Compute instance/operation/zone；服务间导出和文件字节 | 不默认复刻 billing、完整组织 IAM、真实 VM OS、SSH、Cloud Run、所有 Google 服务。任意 SQL 可触达的 ML/外部表等必须分期或明确不支持，不能漏记为不存在 |
| X | 初始化/评测的 Google SDK、gcloud fallback、工作目录文件、签名 URL HTTP；未来明确启用的 bq/REST/gRPC | 与 M 共用业务状态；X 额外的 dataset/table/bucket 删除、JSON 加载、结构化日志、范围下载和分页仍需实现或声明阶段性缺口 |

F：BQ/Logging 用 service account 的 `cloud-platform` scope 或 ADC（B:20–41，L:20–45）；Storage 始终从 JSON 文件构造 client（G:18–30），S:61 在参数缺省时填 `service-account-key.json`；Compute 另有文件存在性和默认文件/ADC fallback（C:28–47）。M 层未调用 Drive API，没有 Drive file ID。Cloud IAM principal、项目与 Google Workspace OAuth 身份可以显式关联，但不得因为同属 Google 就自动拥有 Calendar/Forms/Sheets/Drive 权限。X 层 price-comparison 还有 service account→OAuth→ADC 回退（`tasks/finalpool/price-comparison/evaluation/main.py:26-76`），需要在模拟启动边界映射为明确的同一 principal，而不复制真实密钥。

F：allowlist 支持空集合=无限制、精确匹配、末尾 `*` 前缀匹配（S:52–56、79–120）。BQ 任意查询、jobs list/cancel 不调用 dataset allowlist；Logging sink 管理不调用 log bucket allowlist。Logging 的相同配置有时匹配 log ID、有时匹配 bucket ID，不能当作可靠 Cloud IAM。D：严格兼容 profile 保留 wrapper 行为，**后端仍独立实现 IAM**，避免任意 SQL/SDK 访问绕过业务权限。

公网分类：真实模式业务 API/认证刷新需要公网；设计模式的全部业务状态、API/SDK endpoint、签名 URL 服务在本地或自控内网。安装下载、agent 模型 API、可选仿真 LLM API 分列；使用本地仿真模型时该项可离线。Storage upload/load 读取 MCP 进程可见的本地文件，download 写文件（G:173–210、248–282；B:203–212）；YAML:22 明确不设置 workspace cwd，必须提供共享 mount 和正确绝对路径，不能仅替换网络。外部对象 URL 获取若未本地化，仍是独立公网依赖。

### 1.3 当前任务与隐藏入口

F：JSON 文本扫描得到完整 8 个声明成员，下面仅表示任务/代码使用能力，**不表示曾成功运行，也不构成全部合法工具范围**。各任务 `docs/task.md:1` 说明业务目标；声明位于相应 `task_config.json:3-6`。

| 任务 | 需求涉及能力 | 初始化/评测的额外入口证据 |
|---|---|---|
| ab-testing | BQ 聚合→本地 CSV；条件创建 GCS bucket 或写日志 | `preprocess/ggcloud_upload.py:29-80` CSV load；`ggcloud_clean_dataset.py:32-69` delete/create；`ggcloud_clean_log.py:42-125` config bucket；`evaluation/main.py:133-150,192` Storage SDK/`gcloud storage buckets list`/Logging SDK |
| academic-warning | 多表 BQ→文件→CRITICAL 日志 | `preprocess/main.py:8-10,51` 加载/清理；`evaluation/main.py:54-112` Logging SDK 带时间区间轮询；注释中的 8–15 秒为此前测量描述，本次未验证，不当作分布常量 |
| flagged-transactions | BQ 按客户统计→Excel | `preprocess/ggcloud_upload.py:31-52,180-192` CSV load 与直接 query；Cloud 输出不是其独立评测唯一对象 |
| game-statistics | 当日榜单建表、历史统计插入 | `preprocess/main.py:222,398,439` delete_dataset/JSON load；`evaluation/main.py:160,209,316,388,415` 多条 SDK SQL 验证新表与历史完整性 |
| live-transactions | 多表 BQ→JSON→GCS→CRITICAL 日志 | `preprocess/main.py:49-83,136-174,191-247` 三服务初始化；`evaluation/main.py:130-133,196-235,466-470` config bucket、对象存在/下载、范围下载；`:69` SDK 日志检索 |
| machine-operating | BQ 时间范围→本地 Excel 比较→CSV→GCS | `preprocess/main.py:49-83,134-145` bucket/CSV load；`evaluation/main.py:38-99,509-513` SDK 下载、CSV 读取、字节范围预览；没有 Compute 任务使用证据 |
| price-comparison | PDF/Excel→BQ 新表/行 | `preprocess/main.py:52-126` dataset 生命周期；`evaluation/main.py:112-179` SDK count、全量查询与 table schema；含空格的列名 |
| woocommerce-new-welcome | WooCommerce 数据→BQ→邮件 | `preprocess/main.py:397-422,547-570` dataset 清理和 JSON load；`evaluation/main.py:61-91` SDK 查询与 QueryJobConfig；跨服务实体来自 WooCommerce |

以上表的相对路径均以 `tasks/finalpool/<任务>/` 为前缀。`utils/app_specific/` 中未发现 Cloud 专用业务适配器；其他 Google 服务 helper 不能代替这些散布在任务内的 SDK 路径。本次对仓库 `rg --files` 查找 dump/trajectory/tool_calls/agent JSON 与统筹扩展检查未找到可用真实调用轨迹；`test_enhanced_evaluation.py` 等是源码样例而非成功轨迹。后续需由受控账号生成脱敏的契约记录。

## 2. 工具与能力清单

### 2.1 公共接口约定

F：全部返回类型注解为 `str`。表内输出描述指 **工具函数返回文本**，不是完整 SDK JSON；FastMCP 外层 TextContent、isError/structuredContent 必须在固定依赖环境取快照，不能根据类型注解猜测精确协议字段。业务异常通常被捕获并变成 `Error ...: <exception>` 文本，allowlist 拒绝变成 `Access denied: ...`；这类业务失败不等于抛出的协议错误。schema 验证/未知工具名由 SDK 调度和校验处理，其工具错误或协议错误包装取决于具体 SDK profile，不能统一指定为 JSON-RPC error。仓库还把 content 转为模型可见 JSON（`utils/openai_agents_monkey_patch/custom_mcp_util.py:176-229`）。模型名例如 `google_cloud_bigquery_run_query`，原始 dispatch 仍用 `bigquery_run_query`（共享 F04）。未注册业务 resources/prompts；stdio 为此启动路径（S:1222）。

F（限定依赖版本）：官方 Python SDK `v1.11.0`，tag 对应 commit `ee54acbfa3d5128598c162241aa54f729659c6a5`，本次重新读取固定源码。其 [fastmcp/server.py:238、271–274](https://github.com/modelcontextprotocol/python-sdk/blob/ee54acbfa3d5128598c162241aa54f729659c6a5/src/mcp/server/fastmcp/server.py#L238) 注册 `call_tool(validate_input=False)` 后委托 ToolManager；[tool_manager.py:79–83](https://github.com/modelcontextprotocol/python-sdk/blob/ee54acbfa3d5128598c162241aa54f729659c6a5/src/mcp/server/fastmcp/tools/tool_manager.py#L79) 对未知工具名抛出 `ToolError`；[lowlevel/server.py:401–407、502–503](https://github.com/modelcontextprotocol/python-sdk/blob/ee54acbfa3d5128598c162241aa54f729659c6a5/src/mcp/server/lowlevel/server.py#L401) 将它转换为 text content 加 `CallToolResult(isError=True)`。这与该文件 [660–666](https://github.com/modelcontextprotocol/python-sdk/blob/ee54acbfa3d5128598c162241aa54f729659c6a5/src/mcp/server/lowlevel/server.py#L660) 未注册 RPC handler 的 `METHOD_NOT_FOUND` 错误路径不同。U：Cloud 仅声明 `mcp>=1.11.0`，实际部署版本未核实；上述事实是一个可核查依赖 profile，不能外推所有允许安装的 SDK 版本。

表记法：无 `=默认值` 的参数必填；`s`=string、`i`=integer、`b`=boolean。普通类型注解没有数值范围、正则或 `Literal` enum；文档列出的格式/状态选项**不是 schema enum**，业务校验多委托 SDK。表中中文是工具说明要点，完整原文 docstring/schema 推导依据是 S 对应行段。R=读、W=写、E=执行、A=管理。使用列的 BQ/GCS/Log 表示上表静态任务需求可能选择该工具，未核实逐工具轨迹；`—`=无当前任务证据。未来价值写出工具如何支持新任务。

### 2.2 BigQuery（8）

| 原始工具 / 说明 | 参数 | 输出要点 | 属性 / 状态依赖；任务线索 / 未来价值 | 证据 |
|---|---|---|---|---|
| `bigquery_run_query` 执行 SQL | `query:s, dry_run:b=False, max_results:i=1000` | 非 dry run：total/returned、bytes、毫秒、前 **5** 个 Python row dict repr；多余行计数。dry run：校验成功、估算字节/费用 | R/W/E；typed catalog、IAM、job、SQL；8 任务 BQ / 任意组合查询、DDL/DML | S:124–168；B:43–120，F |
| `bigquery_list_datasets` 列项目 datasets | 无 | count、ID/project 列表或无结果文本；allowlist 过滤 | R；catalog/ACL；BQ / 发现命名空间 | S:171–199，F |
| `bigquery_create_dataset` 新建 | `dataset_id:s, description:s="", location:s="US"` | 成功 location 文本或错误 | W/A；唯一项目内 ID、location、IAM；price-comparison 相关 / 多区域工作流 | S:202–227，F |
| `bigquery_get_dataset_info` 详情 | `dataset_id:s` | full name、location、description、created/modified ISO、过期毫秒、labels | R；dataset；BQ / 理解存储约束 | S:230–259，F |
| `bigquery_load_csv_data` 本地 CSV 入表 | `dataset_id:s, table_id:s, csv_file_path:s, skip_header:b=True, write_mode:s="WRITE_TRUNCATE"` | 文件→表成功文本，不返回 load job ID/行数 | W/E；文件、schema autodetect、三种 write disposition、job；price-comparison 相关 / 多批导入与覆盖 | S:262–289；B:155–229，F |
| `bigquery_export_table` 表→GCS | `dataset_id:s, table_id:s, destination_bucket:s, destination_path:s, file_format:s="CSV"` | `gs://...` 成功；**仅 CSV**，JSON/AVRO 即使描述列出也明确不支持 | W/E；BQ/GCS/IAM/location/格式、extract job；— / 数据交接与归档 | S:292–326；B:286–339，F |
| `bigquery_list_jobs` jobs 列表 | `max_results:i=50, state_filter:s=""` | 最多 10 项 ID/state/type；创建时间字段包装不匹配，显示 Unknown；无分页 cursor | R；job history/principal；— / 排障和取消定位 | S:329–358；B:341–382，F |
| `bigquery_cancel_job` 取消 | `job_id:s` | 成功取消文本或错误；manager 忽略 SDK cancel 返回值 | W/A；job 可见性/执行竞态；— / 中断昂贵任务 | S:361–378；B:384–403，F |

### 2.3 Cloud Storage（13）

| 原始工具 / 说明 | 参数 | 输出要点 | 属性 / 状态依赖；任务线索 / 未来价值 | 证据 |
|---|---|---|---|---|
| `storage_list_buckets` 列 buckets | 无 | 过滤后的全部 bucket 名/location/count | R；项目、bucket/ACL；GCS / 对象空间发现 | S:382–398，F |
| `storage_create_bucket` 建 bucket | `bucket_name:s, location:s="US"` | 成功文本；默认 STANDARD | W/A；全局名称约束/IAM/location；ab-testing / 资源准备 | S:401–419；G:73–104，F |
| `storage_list_objects` 列对象 | `bucket_name:s, prefix:s=""` | 总数量，最多 **20** 个 name/size；无 page token | R；当前版本/prefix/ACL；GCS / 前缀定位、大目录发现 | S:422–440；G:135–171，F |
| `storage_upload_file` 上传本地文件 | `bucket_name:s, source_file_path:s, destination_blob_name:s` | 成功路径文本 | W；真实 bytes、对象 generation、权限；live-transactions/machine-operating / 任意二进制制品 | S:443–462；G:173–210，F |
| `storage_download_file` 下载到文件 | `bucket_name:s, source_blob_name:s, destination_file_path:s` | 成功路径文本；本地创建父目录 | R/W-local；对象bytes/filesystem；GCS / 读取与转换制品 | S:465–484；G:248–282，F |
| `storage_delete_object` 删除 | `bucket_name:s, blob_name:s` | 成功或 not found 文本；NotFound 被 manager 转 False | W；版本/保留/ACL；— / 清理与版本行为 | S:487–508；G:311–335，F |
| `storage_get_bucket_info` 详情 | `bucket_name:s` | location/class/created/versioning/labels/**规则数量** | R；bucket metadata；GCS / 配置诊断 | S:511–535；G:437–454，F |
| `storage_generate_signed_url` 临时访问 | `bucket_name:s, blob_name:s, expiration_minutes:i=60, method:s="GET"` | 文本含 V4 URL、分钟数；method 说明 GET/PUT/POST/DELETE | R/委托访问；签名身份/时钟/对象HTTP；— / 跨工具交付与时效错误恢复 | S:538–558；G:401–435，F |
| `storage_copy_object` 复制 | `source_bucket:s, source_blob:s, dest_bucket:s, dest_blob:s` | 成功来源→目标文本 | W；双端ACL、generation、bytes；— / 跨 bucket 数据移动 | S:561–583；G:364–399，F |
| `storage_move_object` 移动 | 同 copy 的四个参数 | 成功文本；实际 **copy 后 delete**，非原子 rename | W；复制及删除的独立权限与失败；— / 可恢复归档 | S:586–608；G:707–743，F |
| `storage_enable_versioning` 版本开关 | `bucket_name:s, enabled:b=True` | enabled/disabled 文本 | W/A；bucket 与历史对象；— / 覆盖恢复与审计 | S:611–630；G:525–548，F |
| `storage_get_bucket_size` 大小统计 | `bucket_name:s` | 当前 list_blobs 的对象数、bytes、两位 MB/GB | R；当前可列对象实际 bytes；— / 核对导入和清理结果 | S:633–655；G:573–613，F |
| `storage_set_bucket_lifecycle` 加规则 | `bucket_name:s, age_days:i=30, action:s="Delete"` | 成功文本；追加规则，不替换；SetStorageClass 缺目标 storage class 参数 | W/A；虚拟时间/lifecycle；— / 自动过期策略 | S:658–682；G:477–523，F |

### 2.4 Cloud Logging（9）

| 原始工具 / 说明 | 参数 | 输出要点 | 属性 / 状态依赖；任务线索 / 未来价值 | 证据 |
|---|---|---|---|---|
| `logging_write_log` 写日志 | `log_name:s, message:s, severity:s="INFO"` | 成功 severity 文本；M 只能 string，调用 log_text | W；log ID、resource=global、entry/time；3 个 Log 任务 / 业务告警 | S:686–705；L:47–101，F |
| `logging_read_logs` 近期日志 | `log_filter:s="", max_entries:i=50` | count、最多 10 条 timestamp/severity/message；wrapper 消息格式有缺陷，见 §6 | R；filter AST、最近24h、索引/ACL；Log / 搜索排障 | S:708–755；L:103–185，F |
| `logging_list_logs` 日志发现 | 无 | 无 allowlist 时最多20个 log 名；配置 allowlist 时列 **global log buckets**、sink 和近7天取100条中的至多10个 log 名 | R；bucket/sink/log/时间，不是可靠“桶内日志清单”；Log / 理解路由 | S:758–837；L:244–273，F |
| `logging_delete_log` 删除日志 | `log_name:s` | 成功或错误文本 | W；log 下 entries；— / 日志生命周期与重建 | S:840–860；L:223–242，F |
| `logging_create_log_sink` 路由到后端 | `sink_name:s, destination:s, log_filter:s=""` | 成功 destination 文本；不返回 writer_identity | W/A；filter、目标资源、独立 writer IAM；— / 跨服务事件流 | S:863–883；L:487–544，F |
| `logging_list_log_sinks` 列 sinks | 无 | name/destination/filter 全部列表 | R；sink catalog；— / 诊断投递配置 | S:886–907；L:546–575，F |
| `logging_delete_log_sink` 删除 sink | `sink_name:s` | 成功或错误文本 | W/A；停止后续路由、保留历史目标对象；— / 调整路由 | S:910–927；L:577–599，F |
| `logging_export_logs_to_bigquery` 声称导出 | `dataset_id:s, table_id:s, log_filter:s="", days_back:i=1` | allowlist 通过后**固定代码参数不匹配错误**，不产生导出 | E（当前失败）；目的 dataset；— / 修复版需重定义并验证历史导出契约 | S:930–955 vs L:819–853，F |
| `logging_create_log_bucket` 建日志桶 | `bucket_id:s, location:s="global", retention_days:i=30` | 成功 bucket/retention 文本；location 参数未传递，manager 固定 global | W/A；独立于 GCS 的 bucket、retention；Log / 管理日志存储 | S:958–980；L:275–329，F |

### 2.5 Compute Engine（9）

| 原始工具 / 说明 | 参数 | 输出要点 | 属性 / 状态依赖；任务线索 / 未来价值 | 证据 |
|---|---|---|---|---|
| `compute_list_instances` 列 VM | `zone:s=""` | 所有/指定 zone 的 name/status/zone，按 allowlist 过滤 | R；instance/zone/IAM；— / 容量和故障排查 | S:984–1003；C:53–94，F |
| `compute_create_instance` 建 VM | `instance_name:s, zone:s, machine_type:s="e2-micro"` | “initiated creation”；不返回 operation ID | W/A；zone/type/quota、默认网络、Debian11镜像、10GB自动删除启动盘/NAT；— / 生命周期任务 | S:1006–1025；C:227–296，F |
| `compute_delete_instance` 删 VM | `instance_name:s, zone:s` | “initiated deletion”；非完成凭证 | W/A；instance/operation/disk；— / 清理生命周期 | S:1028–1046；C:201–225，F |
| `compute_start_instance` 启动 | `instance_name:s, zone:s` | “initiated start” | W/E；合法状态/operation；— / 恢复服务 | S:1049–1067；C:123–147，F |
| `compute_stop_instance` 停止 | `instance_name:s, zone:s` | “initiated stop” | W/E；合法状态/operation；— / 计划停机 | S:1070–1088；C:149–173，F |
| `compute_restart_instance` 重启 | `instance_name:s, zone:s` | 检查 RUNNING/STOPPING 后 reset；读取状态异常则继续尝试；错误有特殊文本 | W/E；状态/权限/operation；— / 故障恢复 | S:1091–1123；C:175–199，F |
| `compute_get_instance` 详情 | `instance_name:s, zone:s` | status/zone/type/time/IP/labels；boot disk size 和 tags 因 manager 未输出而显示 Unknown/[] | R；instance；— / 核验状态与资源配置 | S:1126–1154；C:349–381，F |
| `compute_list_zones` 可用 zones | 无 | count、最多20项；无 cursor | R；zone catalog/服务可用性；— / 区域探索 | S:1157–1168；C:330–347，F |
| `compute_wait_for_operation` 等 operation | `operation_name:s, zone:s, timeout_minutes:i=5` | completed 或 timed out；manager 对 operation.error/异常返回 False，未检查 status=DONE | R/等待；zone operation/clock；— / SDK 已知 operation 的跨入口等待 | S:1171–1191；C:298–328，F |

### 2.6 已有 manager 方法不等于额外 M 工具

F：例如 `run_query_to_dataframe`/`load_dataframe_to_table`（B:122–153、231–284）、GCS delete_bucket/batch delete/labels/directory/search（G:106–133、337–362、550–571、615–784）、Logging update/delete bucket/exclusions/metrics/search/storage export（L:331–485、601–817）没有对应 `@mcp.tool()`。它们是实现内部或 X 可选能力，不增加 39 的计数。相反任意 SQL 可执行 DDL/DML，虽没有 `create_table` 工具也不能忽略其写入语义。

## 3. 领域状态模型

以下为 D；不是现有实现。各服务保留独立状态机，共享 episode/principal/clock/blob 机制。

| 实体 / 权威持久字段 | 关系、不变量与生命周期 | 可派生/外部入口 |
|---|---|---|
| Episode / Principal / IAMBinding：episode_id、principal_id、service account/OAuth种类、project、resource role bindings、policy version | principal 与项目不是同一对象；M allowlist 是 wrapper 层附加约束；IAM 对直接 SDK/HTTP 同样生效；权限拒绝不改变资源 | 每次请求先按受信任路由确定 episode/principal，再解析 payload，不能让用户 SQL 改 episode |
| BQ Dataset：`project.dataset`、location、description、labels、created/modified、default expiration、ACL | 项目内唯一；删除带 contents 的 X 行为按范围处理；location 约束跨 dataset 查询/GCS export；重复创建报冲突 | `project:dataset` full_dataset_id 与 API resource/name 是同一实体的格式化，不用一个字符串通吃所有表示 |
| BQ Table/View/Routine：全限定 ID、schema树(type/mode/precision/scale)、typed rows 或 view SQL、metadata version、partition/cluster、expiration | schema 与 rows 一致；NUMERIC 不转 float；NULL 与缺字段/空串分离；DDL/DML 真实执行后同步 catalog；无隐式创建不存在的表（合法 CTAS/load 的创建除外） | INFORMATION_SCHEMA、get_table、COUNT、SELECT 从同一 catalog/data 派生；版本快照支持查询结果稳定和未来 time travel profile |
| BQ Job：project/location/job_id、owner、query/load/extract、配置、input版本、PENDING/RUNNING/DONE、error/cancel请求、result schema/rows、统计 | 完成和成功分开；取消是请求/竞态；load disposition 在提交时检查；结果只由执行器产生；重试相同 job ID 与新 ID 的规则分开 | M文本、jobs REST/SDK result、查询分页都读取同一 job；bytes/cost 为单独校准的统计近似，不能反推“有 rows 就成功” |
| GCS Bucket：name、所属project、location/class、ACL、versioning、lifecycle列表、retention/hold元数据、metageneration | bucket 命名在 episode 模拟世界全局唯一；与 Logging bucket 完全不同；删非空 bucket 的 X API 必须失败或显式 force逐对象删 | labels/规则数量/size 来自持久metadata/对象聚合，不能由 LLM猜测 |
| GCS ObjectVersion：bucket/name/generation、live/noncurrent/deleted、blob hash、size、content type、crc32c/md5、metadata/metageneration、created/updated、holds | 字节不可变，覆盖产生 generation；copy 产生独立目标版本；move 的 copy+delete 可部分完成；打开 versioning 后覆盖/删除不能抹掉全部历史 | MCP、SDK、范围HTTP、签名URL都访问相同bytes；prefix不是目录实体；对象名含 `/`、Unicode、空格、百分号需正确URL编码 |
| SignedAccess：签名key版本、canonical method/path/query、issued/expires、限制头及目标 | 签名是访问能力，生成 URL 不保证对象已存在；允许PUT创建的能力不能事先强制GET存在检查；过期、method/路径篡改拒绝且无写入 | `gs://bucket/object` 保持规范资源表示；可用HTTP URL经明确本地路由访问，禁止返回不可访问的假公网URL |
| LogEntry / Log：log full name、insertId、text/json/proto payload、severity数值/名称、resource/labels、timestamp/receive/index_visible_at | log ID 与 bucket ID 不能合并；text字符串即使长得像JSON仍是text；持久写入、检索可见、sink投递分别有时间；删除log处理该log entries而不删除同名bucket | Logging query AST索引；SDK结构化payload与M文本投影共享entry；排序含稳定tie-breaker，但不能伪造真实未承诺的排序 |
| LogBucket / Sink / Delivery：project/location/bucket、retention/lock/state；sink destination/filter/writerIdentity；entry→destination delivery状态 | bucket lifecycle、sink生命周期和历史投递不同；创建sink不是回填历史；目的地权限由writerIdentity检查；BQ/GCS目标资源必须真实存在或符合合法创建规则 | 配置服务REST/gRPC、日志数据面、BQ查询/GCS列表互相可观察；异步outbox避免两个后端只写成一半后声称完成 |
| Compute Zone/Instance/Operation：project/zone/name、数值ID、machine type、disk/network refs、IP/labels、状态；op ID/target/kind/status/error/start/end | 实例名在zone内唯一；zone/type/默认网络/镜像可用性参与创建；提交op后逐步PROVISIONING/STAGING/RUNNING或失败；stop到TERMINATED；reset不是stop+start脚本；删除与auto-delete disk关联 | get/list共享实例版本；SDK操作对象和wait共享op；不需要真实VM开机或SSH，因为M没有执行guest命令工具 |

所有版本、事件队列、执行输入/输出、blob和请求日志持久化。显示字符串、列举数量、bucket size、INFORMATION_SCHEMA和HTTP编码可派生，但结果的依据必须可追溯。每个 episode 可用数据库schema/独立实例隔离，GCS全局名称与固定project名仍按episode路由；不能只给名称加固定前缀而让所有episode共享真实命名空间。

跨入口路由建议：保留 M 包装层，SDK transport 使用受控 endpoint/client adapter；BQ REST、Storage JSON/media/resumable、Logging 数据面和 ConfigServiceV2、Compute 客户端都接入相同权威状态。SDK有不同凭据构造及 REST/gRPC 选择，**一个 `*_EMULATOR_HOST` 不能涵盖四服务**。BQ使用client endpoint配置；Storage emulator host/媒体URL/签名URL各核对；Logging config/data gRPC可用显式transport或独立client adapter；gcloud/bq则需要本地API或明确CLI adapter。运行初始化的宿主/控制容器/任务容器各入口均需配置，挂载文件可见性单独测；禁止静默回落真实云端。优先用薄transport层保持SDK Row/Blob/Job/exception结构，避免每份评测另造一份内存假client。

## 4. 代表性交互序列

以下 D 均可改变顺序/插入读取、由状态断言而非固定成功轨迹判定；不依赖当前任务答案。

1. **建dataset→CSV load→查询→SDK追加→查询→导出→HTTP下载**：CSV含quoted newline、空值、Unicode，追加前先get_table确认类型；断言COUNT和SUM一致、WRITE_EMPTY拒绝非空表、导出字节可解析且与已提交表版本一致。另一条正确路径可用SQL INSERT/CTAS后导出，不强制load。
2. **查询发现→稳定分页→修正NULL统计→批量MERGE**：SDK query pages或SQL显式ORDER BY+LIMIT分段；使用NULL、空组、重复key、未匹配行；断言页拼接与同一job完整结果一致，MERGE歧义输入按方言拒绝，失败不提交。M无page_token，不能发明分页工具绕过其前5行限制；可由分组SQL/导出取得完整数据。
3. **上传A→启用versioning→覆盖B→copy→move失败恢复→删除→SDK列历史**：让source delete权限缺失而dest可写，move可已复制但报错；修正权限再明确处理源/目标；断言hash、live/noncurrent generation和size，不能把move强行事务化。GET signed URL到期/改method后必须失败；PUT signed URL写后M能看见对象。
4. **create log bucket→create sink→写日志→读日志→BQ/GCS查投递→删sink→再写**：先缺目的地writer权限使投递失败，X配置授权后新条目可投递；断言旧sink删除不清除目的数据，M的text payload不自动变json。严格版本日志export工具预期参数错误；成功的路由路径使用独立sink工具，勿虚构修复后的历史回填。
5. **SDK create VM→M list/get→M wait(op)→stop→restart拒绝→start→delete**：SDK提供operation ID；M-only版本则通过get状态观察，不在返回里私加ID。注入有效zone但机器类型/配额不可用；断言失败op不变成RUNNING，stop结束才是TERMINATED，删除完成后get不存在，另zone同名实例不受影响。
6. **跨服务：WooCommerce/表格来源→BQ→GCS制品→Calendar/邮件链接**：复制业务数据时记录source ID/version/content hash；接收方只拿自己可访问链接，不共享Cloud IAM；若将GCS URL写入Drive/Calendar字段，那只是内容引用，不生成Drive file或额外权限。独立验证目标表/对象内容及下游引用，不要求工具调用顺序一致。
7. **并发与中断：两client覆盖相同对象/同表load→断网重试→重启恢复**：模拟提交后响应丢失，检查SDK幂等参数/对象条件是否存在；M未提供条件写不承诺恰好一次。重复日志/INSERT必须在状态可见；恢复后job、对象版本和日志投递不凭“最后一条success”倒推。

## 5. 候选实现与推荐

### 5.1 现成组件核实

F/U：2026-09-10 读取以下上游固定快照；“支持”是其源码/维护者清单证据，未运行验证。

| 候选 | 核实覆盖 | 明确缺口及本设计处理 |
|---|---|---|
| `goccy/bigquery-emulator` commit `cb8555bee739c794343337e8c3242b59d5d7470a` | [feature-support.md:32–74,124–182](https://github.com/goccy/bigquery-emulator/blob/cb8555bee739c794343337e8c3242b59d5d7470a/docs/feature-support.md#L32)：datasets/tables、query/load/extract/jobs与分页、CSV/JSON、GCS对接；[186–258](https://github.com/goccy/bigquery-emulator/blob/cb8555bee739c794343337e8c3242b59d5d7470a/docs/feature-support.md#L186)：GoogleSQL经googlesqlite执行，DML/DDL/scripts、Storage API等声明 | 无认证/IAM/行列权限；partition仅metadata而非分区裁剪/`_PARTITIONTIME`；部分INFORMATION_SCHEMA、time travel、跨REST session事务、external/copy/ML缺失。先对具体版本做SQL/API差分，前置IAM和job/时间层，拒绝未支持语义；不能从“可解析GoogleSQL”推出逐函数精确 |
| `fsouza/fake-gcs-server` commit `3c29d20789f6475f65d2554ad6898c4afd7124bb` | [server.go:306–343](https://github.com/fsouza/fake-gcs-server/blob/3c29d20789f6475f65d2554ad6898c4afd7124bb/fakestorage/server.go#L306)：对象media、resumable、batch、签名URL路径；[bucket.go:39–73,131–224](https://github.com/fsouza/fake-gcs-server/blob/3c29d20789f6475f65d2554ad6898c4afd7124bb/fakestorage/bucket.go#L39)：versioning与bucket创建/list分页 | [README:88–96](https://github.com/fsouza/fake-gcs-server/blob/3c29d20789f6475f65d2554ad6898c4afd7124bb/README.md#L88)明确不验证签名/expiration；bucket更新仅解码hold/versioning，不证明lifecycle/labels/location保真。IAM、签名校验、规则执行与返回metadata需独立补充并验证；不能接受“patch成功但规则丢失” |
| 普通 SQLite/PostgreSQL/DuckDB | 可作状态存储、独立小型结果核验或某些已证明等价的执行片段 | 本次未评定其特定版本的完整BigQuery兼容；不能当作GoogleSQL等价替代。SQL改写至少需AST、类型分析、三值逻辑、函数语义与结果codec，不用字符串替换或让LLM猜结果 |
| Logging/Compute 的本地通用云模拟器 | 本次未发现并核实能覆盖这两个M工具面的现成完整实现 | 优先自建有限但真实的API/state machine；“未发现”不等于市场上不存在。不能用AWS模拟器同名资源当作GoogleAPI证据 |

### 5.2 路线比较

下表为 D，相对成本为规划判断；I/S/C/T/D/P 沿用公共保真向量，不能折叠为总分。

| 路线 | I / S / C / T / D / P | 开发、运行、维护与适用性 |
|---|---|---|
| 保留固定真实MCP，替换SDK transport/backend | I最好保留说明/包装/错误；S取决于执行器；C可通过统一API较强；T需补IAM/clock；D可生成；P有wrapper同步SDK阻塞及大列表扫描 | 开发中高、运行低、上游包装维护低；**首选接口路线**，但需隔离SDK凭据/endpoint，冻结依赖；固定版本缺陷仍真实存在 |
| 有状态MCP替代实现 | I需39工具逐字段/文本契约快照；S/T可控；仅M时C不足；D/P良好 | 开发中高、运行低；配合同一API/SDK后端是备选，避免把每工具做成独立字典 |
| 本地HTTP/API +必要gRPC | I由真实MCP保留；S/T领域规则；C跨语言/SDK/CLI最强；D可生成；P可水平隔离 | 开发最高但共享收益最大；优先覆盖M与实际X请求形状、媒体/分页/异常，不复刻平台全部REST |
| SDK/client 适配 | I可能保留；S/C依赖适配覆盖完整且共享状态；T可控；D/P好 | 初期成本中，SDK升级维护较高；只patch业务方法易漏direct HTTP/CLI，适合离线试点，adapter覆盖需要manifest |
| 上述BQ/GCS模拟器 +语义补层 | I经真实MCP保留；S限定验证；C可接SDK；T原生明显不足；D/P适合规模 | 节省查询/传输开发；补IAM/版本/lifecycle成本不可省；升级按固定commit差分，不用latest |
| fixture/回放 | I局部精确；S/C只限记录过的调用；T固定；D有限；P很高 | 契约金样/错误样本用途；不能作为主环境，没有任意调用顺序与新状态能力 |
| LLM主导工具响应/状态 | I可结构校验；S尤其SQL和异步难可信；C/T需外部执行与状态机；D丰富；P慢且贵 | 原型快，验证和长期运行成本高；SQL执行结果、bytes、ACL无法靠自评证明；不推荐主路线 |
| 确定性服务 +LLM初始化内容/少量受限提案 | I/S/C/T保留代码约束；D提高语境/干扰多样性；P可提前生成并缓存 | **首选总体方案**；LLM不在大部分工具调用关键路径，成本主要是初始数据；必须外部验收内容与约束 |

首选架构：固定MCP接口层 + BQ模拟器经独立SQL差分合格的profile + GCS API/bytes存储与规则补层 + 自控Logging/Compute状态机 + X transport适配/本地API。备选：统一有状态MCP替代层仍接相同权威后端；当原包依赖/同步SDK/协议包版本难冻结时启用，需完整I契约测试。完整任意BigQuery平台不是可短期准确兑现的目标；支持范围必须可机器读取、随版本扩展。

## 6. 保真缺口与取舍

### 6.1 SQL、NULL、类型、时间和任务执行

官方规范查阅日期均为2026-09-10，服务API是滚动版本；以下是测试需求，不宣称模拟器已实现。

| 能力 | 保真目标/分期 | 误学风险和验证 |
|---|---|---|
| 标识符、catalog、DDL/DML | 首期限定常用GoogleSQL：反引号全限定ID/带空格列名、CTE、JOIN/聚合/窗口/QUALIFY、CREATE/ALTER/DROP、INSERT/UPDATE/DELETE/MERGE；INFORMATION_SCHEMA从统一catalog生成；对未支持AST明确错误 | 若只读SQL、自动忽略DDL或按关键字造rows，会丧失真实任务规划。每个语法族含成功/失败/组合测试，未在候选引擎验证的语法不入合格profile |
| NULL与集合 | SQL三值逻辑，`= NULL`不等于`IS NULL`；NOT IN含NULL、outer join无匹配、COUNT(*)/COUNT(col)、空输入聚合分开；NULL array、empty array、null元素也分开 | Python truthiness/空串当NULL、NULL统计为0会改变异常检测/筛选。独立真值表和小数据枚举核验。官方：[operators](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/operators)、[data types](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/data-types) |
| 数值与结构化类型 | INT64溢出、FLOAT64 NaN/Inf、NUMERIC/BIGNUMERIC精度、BYTES编码、BOOL、ARRAY/STRUCT/JSON与NULLABLE/REQUIRED/REPEATED schema；SQL内值、SDK Python值和M repr分层编码 | 全部转字符串/float破坏排序、比较与货币精度；日期repr也会影响agent解析。逐类型往返CSV/API/query/SDK/文本投影；精确decimal与float分别容差。高级GEOGRAPHY/RANGE等分期，不以字符串假支持 |
| 时间 | DATE/TIME/DATETIME与TIMESTAMP分开；TIMESTAMP代表绝对时刻，DATETIME不携带时区；显式时区转换、DST重复/缺失时刻、边界闭开区间、CURRENT_DATE/CURRENT_TIMESTAMP基于可控clock | 把全部本地naive时间当UTC会改变当日榜单/窗口。采用官方类型与[timestamp functions](https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/timestamp_functions)差分，固定tz数据库版本；SDK/任务进程时间必须与服务clock有明确映射 |
| CSV load/extract | autodetect、header skip、quoted delimiter/newline、空值/空串、非法行、write disposition、location、object权限与真实字节；CSV不承载嵌套重复字段 | “读CSV全转string”“失败行静默删”“导出占位文件”直接污染轨迹。官方[export table data](https://docs.cloud.google.com/bigquery/docs/exporting-data)指出CSV不能导出nested/repeated；对比导出schema/bytes再导入，不把所有CSV roundtrip当无损 |
| 执行与jobs | dry run不提交、query完成才返回；jobs记录失败/取消/重试；脚本与事务逐期覆盖；同一job分页用结果快照 | 固定成功、取消即回滚、超时即未执行均错误。真实API条件允许下测提交后超时、重复job ID、取消竞态。M query没有job ID返回且只展示5行，按原契约保留 |
| 优化/统计/高级SQL | query planner字节估算、费用、slot/性能、分区裁剪、approx函数、远程UDF/ML、外部表/Drive federation分期 | 候选模拟器接受metadata不代表执行相同；统计只能标近似，初期不生成依赖精确账单/延迟/复杂计划的训练任务。外部SQL/ML不支持时返回明确错误，不给空表或虚构预测 |

原MCP dry run将 `total_bytes_billed / 1024**4 * 5.0` 硬编码为估算（B:81–89）；这不是当前云费用报价，None值还可能导致本地异常。不得用真实“当前价格”解释该文本。`max_results=0` 在B:101条件为false，含义不是简单返回0行；负值可能立即停止取rows。精确schema coercion待固定SDK运行验证，不能悄悄改成直觉更好的校验。

### 6.2 Storage/Logging/Compute 与 wrapper 特殊行为

| 项目 | 事实/准确或近似边界 | 对训练的影响及设计处理 |
|---|---|---|
| GCS一致性 | 官方[GCS consistency](https://docs.cloud.google.com/storage/docs/consistency)区分对象读取/写入/删除/list的强一致与权限等最终一致；GCS不等于“所有云读都随机延迟” | bytes与list必须同态，权限传播可单列延迟profile；不要用统一最终一致延迟污染对象正确语义 |
| GCS版本/lifecycle | M仅开关和当前对象读取；历史generation/条件写主要X，仍是必要状态；SetStorageClass未给目标class（S:658–678/G:508–509） | 准确实现已有参数能产生的合法行为；该缺参操作真实错误待受控确认，不自动选择NEARLINE；lifecycle后台执行时刻只能近似，记录触发/生效虚拟事件 |
| move部分完成 | G:728–736先copy再delete；delete NotFound返回False未被move检查 | 不得为代码便利强行全回滚；注入复制成功删除拒绝，检查目标存在和源仍存在；兼容细节与训练推荐分开 |
| 下载相对路径 | G:270对`dirname(destination_file_path)`调用makedirs；裸文件名的空dirname可失败 | 不静默帮agent补workspace；在严格profile保留，修复profile明确；不把本地路径错误当云不存在 |
| Logging filter | 官方[Logging query language](https://docs.cloud.google.com/logging/docs/view/logging-query-language)是独立于SQL的字段/类型/存在/比较/子串/正则/逻辑表达语言；L:126–141隐含最近24h并AND用户过滤 | 必须解析表达式和正确优先级，不能字符串contains代替severity/时间/嵌套字段语义；缺字段与NULL_VALUE做反例。大范围过滤只能看到24h是wrapper约束 |
| Logging bucket与log误用 | S:697/733匹配log ID，S:771匹配bucket ID；S:800用destination子串找sink，S:780–819把全项目近期log名展示到每个allowed bucket | 列表文本不是真实路由证明；D权威路由仍按sink/filter/writerACL维护。严格profile保留投影，主训练标记缺陷，不给“同名即属于同桶”的暗规则 |
| Logging payload投影 | S:746的条件表达在json_payload为false时输出`No message`，即使text_msg存在；L:169–171还假设entry有text_payload/json_payload，SDK实际字段映射U | 不能为任务要求structured就把message:s写成log_struct；已知包装缺陷进入兼容测试，SDK对象字段还需锁版快照；后续修复须单独profile |
| 日志导出接口错配 | S:946–950传`table_id/filter_/days_back`，L:819–824接` sink_name/dataset_id/filter_string`；允许dataset通过时在调用manager前触发TypeError | **可依据源码准确复现的失败**；不得给成功/导出表；修复版必须明确是历史导出还是建sink，这两者不等价 |
| sink真实投递 | M描述例`bigquery://`/`storage://`直接原样传，L无转换；官方[sinks REST](https://docs.cloud.google.com/logging/docs/reference/v2/rest/v2/sinks)使用`bigquery.googleapis.com/projects/.../datasets/...`等destination且writerIdentity需目标权限 | 错URL应得到服务错误，不自动纠正；创建sink不保证投递成功、不默认回填；sink到GCS/BQ的delivery时序/格式分期差分 |
| log bucket location | S:958公开location，S:973未传，L:295固定global | 严格profile任意location仍作用global；修复版需变更manifest；不能把该缺陷训练成Google API普遍规律 |
| BQ jobs输出 | S:348读取creation_time，B:364写created；S:349检查error_result但B未提供；cancel忽略SDK布尔结果 | 显示Unknown/缺失不等于状态无创建时间或无错误。独立SDK oracle验证实际job，不能依据M文字判断取消/成功 |
| Compute异步 | 官方[instance lifecycle](https://docs.cloud.google.com/compute/docs/instances/instance-lifecycle)给实例状态；C:140/166/192/218/290返回op name但S mutations丢弃；wait对任何无error响应都return True | 不能改成瞬时RUNNING、也不能给M未提供的op ID。实例状态与operation状态分开；严格wrapper“completed”可能不足以证明DONE，独立API/read最终态 |
| Compute详细字段 | C:370–380没有boot_disk_size_gb/tags，S:1148–1149显示Unknown/[]；默认network/image会在真实项目缺失 | metadata权威态仍存disk/tags；投影保留版本差异。初始状态需含缺默认网络/配额不足，不总成功创建 |

**D：profile政策。** `cloud-mcp-7df9ca-strict` 保存已知包装缺陷，用于兼容回归/错误恢复研究；主训练每条轨迹标MCP与SDK版本、缺陷代码和验证范围，不能无筛选把缺陷绕过当通用云能力。`cloud-mcp-fixed-<revision>` 只能在未来修复代码与受控真实调用确认后启用，本阶段没有实施该修复。业务近似和wrapper缺陷分别统计；当前真实服务未暴露的“方便工具”不得偷偷添加。已知工具的未支持语义经原错误包装返回可识别模拟器扩展错误；未知工具名依已核实 SDK profile 保留实际工具错误/协议错误包装，至少 `v1.11.0` 的本调用链是 `CallToolResult(isError=True)`，不得改写成未知 RPC method 的 `METHOD_NOT_FOUND`。实际运行依赖与原始/模型错误双快照继续标 U；不使用伪成功或无结果掩盖缺口。

## 7. LLM 仿真可行性

### 7.1 职责与三条路线

| 能力 | 纯代码 | LLM主导 | 推荐混合职责与外部检查 |
|---|---|---|---|
| SQL/query/load/extract、typed结果 | 可真实执行、差分边界清晰，投入大 | 即使看见全部rows也难精确执行NULL、joins、decimal、并发；容易编造结果 | **代码权威执行**；LLM可离线生成业务表内容/候选schema，约束编译后才入库；不能决定query结果、自动修复agent SQL |
| GCS与Compute CRUD/state | 状态机可验证、运行便宜 | 临时状态和ID容易漂移，“应该成功”偏差严重 | 代码ID/ACL/bytes/生命周期；LLM可生成实例labels、blob文本、故障场景描述，不能伪造开机/文件hash |
| Logging与sink | filter解释器/路由需要工作，语义清晰 | 对自然语言日志真实感有价值，过滤/权限不可靠 | LLM适合初始化日志/业务背景及候选事件叙述；时间、严重性、resource references、路由及提交由代码验证和安排 |
| error/说明文本 | 原wrapper模板成本低 | 容易增加解题建议、悄悄放宽参数 | 固定模板/原SDK错误形状优先；可选LLM只在服务原本非结构化字段内生成业务内容，不能改工具schema、权限/错误类别 |

推荐**代码为主的混合**，不是每次工具都调用LLM。LLM主导若声称高保真，仍需要完整外部SQL执行器/状态机校验，核心成本不能绕过；只让同一LLM评判自己的结果不成立。

### 7.2 若试验在线LLM提案，必须使用显式状态

调用先经过确定性schema/鉴权/真实wrapper配置检查；结构化查询检索完整相关状态，包括资源不存在的索引证明、可读行/对象版本、分页覆盖、filter候选entry和目标ACL。大表交由SQL执行器，大blob只传摘要/必要片段但精确字节操作仍用blob store；摘要不替代真值。状态超上下文时分批检索，不能截断后声称查全。

LLM收到操作和最小业务上下文，提出受限change set及非结构化内容；校验器检查schema、引用、权限、typed值、生命周期、base_version和内容hash，原子提交可提交的单服务事务。跨BQ/GCS或sink投递用持久outbox/任务提交，不虚构跨云API全局原子性；move保留copy/delete两阶段。响应从已提交状态确定性渲染，LLM提案文本不得盖过最终真实结果。

版本冲突重取相关状态并最多一次修复提案（A，待成本实验），修复只针对仿真器提案格式，不能替agent修改非法参数；仍不合法则不提交并返回明确仿真失败。记录model版本、prompt版本、完整检索ID/版本、模型输入/输出、校验记录、变更集、最终响应和虚拟调度。回放提交日志/原输出可复现，不能靠temperature=0保证模型重算相同。

LLM不接收task groundtruth、评分条件、成功轨迹；资源中恶意文本按业务数据处理。禁止看到任务希望某表存在就自动建表、看到日志描述就推断不存在的entry、因权限失败给额外授权。读取只有实际状态投影，没有“合理补全”。

### 7.3 独立质量与规模成本

独立检查：同状态重复读逐字段一致；长序列后从原子日志重建状态，与API读和blob hash一致；合法/非法参数配对；权限拒绝前后hash不变；SQL随机小数据由独立参考逻辑计算；LLM生成日志的索引结果由同一业务数据的独立filter反例验证；加入不存在资源/诱导成功/答案提示红队，统计幻觉资源率、错误接受率、状态漂移、响应提交差异和答案泄露。抽取真实受控API记录与独立人工盲审；不用仿真LLM自评作为通过证据。

成本为A，非测量/报价：确定性工具路径每调用0次仿真模型；LLM主导每调用1次，失败修复最多再1次；混合初始化每episode按数据块生成若干次，运行大多0次。若在线单次输入2k–16k tokens、输出0.5k–2k，延迟规划2–12秒，则100万调用、平均8k输入/1k输出、平均1.1次尝试的模型费用为 `1.1 × (8000×P_in + 1000×P_out)`，P为该模型每百万token的实际费率；不含agent模型/缓存命中/机器费用。吞吐λ调用/秒需约 `λ×平均延迟` 个在途请求，还受token配额限制；所有数值必须实测替换。

纯代码前期SQL/API适配投入高，但边际成本为CPU/存储/IO且易并发；在线LLM可省少量内容模板开发，长期token/延迟、校验失败和漂移清洗成本增加。建议提前生成内容、按seed缓存不可变文本、批量校验、确定性快速路径；只有清楚的新内容生成调用才考虑按能力选模型，已稳定语义转为代码，不以更小模型猜SQL省成本。

可接受LLM对照试点：两组采用完全相同typed表/日志状态机，一组模板生成业务文本，一组LLM生成多样设备故障日志/对象说明和相似干扰；两组经独立约束检查后盲测未见告警归因/跨对象查询任务，比较真实环境迁移、重复率、幻觉引用、解题提示泄漏、初始化成本。另可小样本比较LLM受限“创建日志entry提案”与代码直接创建，必须同一确定性校验/提交/响应，考察开发节省是否大于验证和运行成本；SQL结果和Compute执行不交给LLM。

## 8. 合成、验证与分期

### 8.1 多样环境与可解任务

D：seed控制catalog拓扑、principal/ACL、虚拟日期、实例/operation/日志队列、数据与名称分布。配置独立改变项目/dataset/表/bucket数、空资源、表行数、嵌套深度、NULL密度、近似名称、重复客户ID、历史窗口、异构时区、日志严重性/噪声/延迟、对象体积/二进制类型、VM状态/zone/配额。业务关联由约束生成：交易关联客户、日志引用实际资源、对象摘要等于上传内容；干扰项也真实存在，不能仅给唯一符合模板名称的答案对象。

任务生成器可从状态挑可满足的约束，也可从约束构建状态；独立solvability checker验证至少一个合法工具组合，并根据M前5行/前20项、权限、不可用工具profile检查可观察性。任务目标存于评测侧，模拟器仅拿初始化场景，不拿答案。评分按最终表/对象/entry/instance状态及业务条件，不限制SELECT计算还是下载本地计算等合法路径；历史数据不得意外覆盖，额外错误写入也纳入副作用约束。

### 8.2 独立oracle与验证计划

| 验证面 | 设计用例及独立依据 | 当前证据/后续条件 |
|---|---|---|
| 契约 | 39工具名称、docstring、必填/default/类型、配置组合、成功/错误TextContent、原始与模型侧投影双快照；长文本/空content；分别验证 `tools/call` 的未知工具名与未知 RPC method，保留对应工具结果或协议错误 | 当前AST+固定源码；SDK v1.11.0 未知工具为 text+isError 的源码路径已核；实际SDK/FastMCP锁版后离线取快照，检查harness是否保留顶层错误标记；真实业务调用不在本阶段 |
| 参数边界 | missing/extra/null/错类型、0/负max、非法SQL/enum/location、坏文件路径、缺资源、无权限、冲突；拒绝后检查状态不变 | 基于源码可确定部分；SDK coercion/HTTP状态/异常文本需要版本控制与受控记录 |
| SQL与状态 | 独立typed小数据枚举 + GoogleSQL官方边界向量；事务、NULL、窗口、时间、MERGE反例；catalog/rows和SDK互查 | 同一个SQL引擎不能同时作为模拟器和唯一oracle；先精确decimal/关系代数小样，后受控真实BQ差分 |
| 对象/日志/Compute | bytes hash/独立CSV/JSON解析；日志epoch/索引窗口/路由和ACL不变量；实例与op state独立检查 | 评测读权威state snapshot/第二API，不靠success文本；失败操作检查无非法变化及允许的部分完成 |
| 组合与多入口 | §4全部序列随机插入读取、交换独立写、SDK↔M↔HTTP↔CLI交叉读写；分页结果拼接、全量与过滤结果互验 | 真实SDK版本与可用CLI单独profile；容器/宿主各入口测试endpoint、防真实网络fallback |
| 并发/恢复 | 两writer竞争generation/jobID，提交后丢响应、重启、日志投递中断；clone后分别写，reset后hash相等 | 持久WAL/outbox/operation队列；以合法执行历史检查，不能承诺跨服务线性化；重放事件证明归因 |
| 未见环境与质量 | 按实体规模/SQL族/组合图保留holdout，不仅随机换名字；新JOIN图、新时区、相似名干扰、跨服务传递 | 测试集不复用模板答案；按错误类型/语义族报覆盖，既报告通过也报告profile拒绝率 |
| LLM与成本 | §7的漂移/幻觉/成功倾向/泄露测试、长序列；对比代码/LLM/混合CPU/token/吞吐/p50/p95 | A成本经试点测量；结构错误零容忍，分布逼真由独立盲审和迁移实验确认 |

现有源码能确定注册、固定包装缺陷与X依赖，不能替代真实记录。未来差分需隔离的测试GCP项目、明确授权、最小角色矩阵、固定SDK/MCP依赖、可创建临时dataset/bucket/log sink/VM的资源配额和费用上限；本阶段**只提出条件，不执行**。只读差分仍需避免拉取业务敏感数据，以合成隔离资源为主。动态ID作双射规范化保留引用关系，时间比较相对顺序/窗口及声明精度，rows无ORDER BY按多重集合、显式ORDER BY按序；error code/category与必需字段优先，不能把实质差异当随机字段删掉。bytes/hash、数值/NULL、权限结果、持久副作用不可随意容差。

### 8.3 隔离、吞吐与可复现

每episode独立catalog/对象索引/虚拟clock/事件队列/凭据路由，readonly seed snapshot copy-on-write克隆；blob可内容寻址共享但写入新版本，ACL和引用不得跨episode。通过快照ID、生成器版本、schema profile、依赖hash、seed、请求/提交日志及调度记录重建；恢复job/result/上传session/投递outbox，reset不能仅清MCP会话。并发SDK与MCP采用resource version/CAS或数据库事务，但保留真实API没有幂等字段时的重复副作用。

瓶颈：大SQL执行CPU/内存、CSV/media IO、GCS列举聚合、Logging索引/队列、SQLite写竞争、FastMCP async函数内同步SDK阻塞、在线LLMtoken/连接数。按episode分片或进程池减少锁竞争，blob流式传输；不把M包装全量扫描偷偷改成返回前20后假计总量。性能验收独立测量同规模同语义下代码/混合的吞吐/p95、每episode存储与恢复耗时；运行profile参数与合成数据规模一起记录，降低保真换吞吐必须显式标记。

### 8.4 分期和准入门槛

| 阶段 | 能力与价值 | 准入门槛（D） |
|---|---|---|
| P0 契约/路由 | 固定39工具快照、两profile政策、身份/IAM、路径/SDK入口、权威state/clock/blob、独立oracle骨架 | 固定schema/输出差异全部解释；未支持明确失败；无真实后端fallback；episode隔离测试零串扰 |
| P1 首轮Cloud试点 | BQ catalog+SELECT/NULL/聚合/窗口+DDL/DML+CSV load；GCS创建/对象读写/copy/move/签名校验；Logging write/read/filter；BQ→GCS导出→SDK验证。选择业务结构多样的合成任务 | typed结果/bytes/权限/拒绝副作用在契约边界样本全部通过；组合随机序列与真实受控差分无未解释差异；不要求覆盖所有SQL后宣称完成 |
| P2 管理与异步扩展 | BQ jobs/cancel/scripts、GCS versions/lifecycle、Logging bucket/sink投递、Compute完整9工具状态机与operation；扩大X API/CLI | 任务状态/取消/延迟/部分完成与真实profile相符；权限矩阵、并发恢复、签名过期/变造无错误接受；所有已注册工具有明确可用或已知失败行为 |
| P3 高级语义/规模 | 扩大SQL类型/函数/INFORMATION_SCHEMA/事务/time travel/外部资源的显式profile；大环境与跨服务图；性能优化 | 各新增语义有独立oracle/真实差分；holdout组合不显著劣化；长序列无状态漂移；容量测试保留同样约束 |

Cloud首轮能证明SQL/对象/日志跨入口可迁移行为；LLM价值用§7内容生成对照单独比较，不能因代码试点通过就宣称LLM主导也可靠。整体项目可把Cloud作为SQL+二进制+异步能力的代表性后续试点，优先级不按现有8任务覆盖率决定。

## 9. 待确认与审查记录

| 项目 | 当前状态 / 所需核验 |
|---|---|
| 运行版本与完整协议schema | U：uvx实际包provenance、依赖版本、FastMCP/Pydantic coercion、TextContent/isError/structuredContent快照及未知工具错误包装；不能用仓库uv.lock代替独立uv工具环境。§2.1 核实的 SDK v1.11.0 行为不消除实际运行版本 U |
| SDK Logging entry字段 | U：L读取text_payload/json_payload与锁定Python Logging返回对象的映射需离线SDK对象测试/真实脱敏快照；已知S消息条件bug仍成立 |
| API错误/延迟分布 | U：invalid destination/SetStorageClass缺参、permission vs NotFound、cancel/Compute wait实际返回、日志索引/sink路由延迟和lifecycle生效范围；源码能判断错误路径，不能推定真实时延常数 |
| 候选模拟器 | F：固定快照及覆盖声明核实；U：实际编译、SQL差分、SDK/gRPC/CLI、并发恢复与吞吐未测。尤其fake-gcs lifecycle/签名和BQ权限不能跳过验证 |
| 高级SQL与外部源 | U/分期：合法GoogleSQL不等于本地候选引擎都可执行，未来Drive外部表/远程UDF/ML等明确单独profile、账号和公网条件 |
| 可用调用轨迹 | 未发现；本报告没有运行pass率或逐工具调用频次。受控合成账号差分仍待授权/实施阶段安排 |
| 统筹反馈 | 已采纳：严格缺陷兼容profile和修复profile分开；缺陷轨迹标注并经迁移审查后才进入训练；不把复刻bug当主目标 |
| 非原作者交叉审查 | `/root/wandb`，`gpt-6-astra / xhigh`，2026-09-10 完成39工具AST签名/default、M/B/X、SQL/GCS/Logging/Compute状态/IAM、候选缺口及LLM成本/oracle审查；未发现架构需要推翻的问题。作者仅修本报告，公共发现由统筹复核 |
| C-01 / P2：未知工具错误层级 | 原文“未知工具协议层拒绝”过度确定。作者重取官方 SDK v1.11.0（commit `ee54acbfa3d5128598c162241aa54f729659c6a5`）核实：`fastmcp/server.py:238,271-274`→`fastmcp/tools/tool_manager.py:79-83`→`lowlevel/server.py:401-407,502-503`，未知工具名为 ToolError→text+isError，而 `lowlevel/server.py:660-666` 的 METHOD_NOT_FOUND 是另一条 RPC handler 错误路径；固定链接见§2.1。已同步§2/6/8和矩阵的错误profile验证；实际运行版本/快照保留U，统筹复核已闭环 |

## 10. 能力矩阵行

```csv
object,tool_or_capability,version,operation_type,state_dependencies,proposed_method,llm_role,fidelity_gap,verification_method,priority,evidence
google-cloud,bigquery_run_query,7df9ca22115002e0cea75deec595492c520df3e1,R/W/E,catalog typed_rows IAM jobs clock,real_MCP plus verified_GoogleSQL_engine,seed_content_only,SQL coverage and statistics approximate; 5-row text projection,typed_oracle plus real_BQ_differential,P1,S:124-168; B:43-120
google-cloud,bigquery_dataset_list_create_info,7df9ca22115002e0cea75deec595492c520df3e1,R/W/A,dataset project location ACL,shared_catalog plus SDK_API,descriptions_at_initialization,SDK and raw MCP schema runtime snapshot pending,catalog_invariants plus SDK_MCP_cross_read,P1,S:171-259
google-cloud,bigquery_load_csv_data,7df9ca22115002e0cea75deec595492c520df3e1,W/E,local_file schema typed_rows load_job,CSV_parser plus query_backend,seed_business_rows,autodetect and write disposition require differential,independent_CSV_and_typed_snapshot,P1,S:262-289; B:155-229
google-cloud,bigquery_export_table,7df9ca22115002e0cea75deec595492c520df3e1,W/E,table GCS IAM location extract_job,query_backend plus shared_blob_API,none,CSV_only wrapper; nested export and location constraints,SDK_download_parse plus source_table_oracle,P1,S:292-326; B:286-339
google-cloud,bigquery_list_jobs_cancel_job,7df9ca22115002e0cea75deec595492c520df3e1,R/W/A,job owner states clock,deterministic_job_scheduler,none,wrapper missing created/error and cancel return ignored,job_state_history plus SDK_differential,P2,S:329-378; B:341-403
google-cloud,storage_bucket_list_create_info_size,7df9ca22115002e0cea75deec595492c520df3e1,R/W/A,bucket IAM location objects,local_GCS_API plus metadata_rules,seed_labels_only,emulator metadata and global name scope gaps,SDK_MCP_cross_read plus byte_aggregation,P1,S:382-419; S:511-535; S:633-655
google-cloud,storage_objects_list_upload_download_delete_copy_move,7df9ca22115002e0cea75deec595492c520df3e1,R/W,blob versions ACL local_files,local_GCS_API plus content_addressed_blob,blob_text_initialization,20-object projection; move partial commit; local path behavior,hash_range_reads plus faulted_move_history,P1,S:422-508; S:561-608; G:707-743
google-cloud,storage_generate_signed_url,7df9ca22115002e0cea75deec595492c520df3e1,R/delegation,signer method resource expiry clock,local_HTTP plus deterministic_signature_validation,none,fake_gcs_server skips signature and expiry checks,tamper_expiry_method plus HTTP_MCP_cross_read,P1,S:538-558; G:401-435
google-cloud,storage_enable_versioning_set_bucket_lifecycle,7df9ca22115002e0cea75deec595492c520df3e1,W/A,bucket versions retention clock,versioned_state plus lifecycle_scheduler,none,SetStorageClass missing class; lifecycle timing approximate,history_invariants plus SDK_generation_differential,P2,S:611-630; S:658-682; G:477-548
google-cloud,logging_write_read_list_delete,7df9ca22115002e0cea75deec595492c520df3e1,R/W,log entries payload filter IAM index_clock,deterministic_logging_API_filter_index,initial_log_content,wrapper payload and allowlist projection bugs; indexing delay,independent_filter_oracle plus SDK_cross_read,P1,S:686-860; L:47-242
google-cloud,logging_sinks_create_list_delete,7df9ca22115002e0cea75deec595492c520df3e1,R/W/A,sink filter writerIdentity GCS_BQ destination,config_API plus persistent_delivery_outbox,seed_business_context,source destination examples differ from API; no automatic backfill,writer_IAM_negative_tests plus destination_read,P2,S:863-927; L:487-599
google-cloud,logging_export_logs_to_bigquery,7df9ca22115002e0cea75deec595492c520df3e1,E_currently_fails,dataset_allowlist,strict_profile_argument_error; fixed_profile_future,none,wrapper passes unsupported arguments to manager,static_signature_check plus zero_mutation_assertion,P0,S:930-955; L:819-853
google-cloud,logging_create_log_bucket,7df9ca22115002e0cea75deec595492c520df3e1,W/A,project global_log_bucket retention,config_API_state_machine,none,location ignored by wrapper,SDK_config_cross_read plus duplicate_retention_cases,P2,S:958-980; L:275-329
google-cloud,compute_instances_list_get_create_delete_start_stop_restart,7df9ca22115002e0cea75deec595492c520df3e1,R/W/A/E,zone instance disk network quota IAM operation,deterministic_control_plane_state_machine,seed_labels_and_scenarios,operation ID dropped; missing output fields; no guest execution,instance_operation_invariants plus SDK_real_differential,P2,S:984-1154; C:53-296
google-cloud,compute_list_zones_wait_for_operation,7df9ca22115002e0cea75deec595492c520df3e1,R/wait,zone operation clock,virtual_scheduler plus SDK_API,none,20-zone projection; wrapper conflates failures with timeout,operation_history and independent_DONE_checks,P2,S:1157-1191; C:298-347
google-cloud,X_SDK_HTTP_CLI_and_shared_files,repository_ef7ab5928062defc0dc2a91a4c26ddebccb1a6a7,R/W/E/A,all_service_state auth_mapping blob mount,SDK_transport plus REST_gRPC_CLI_adapters,none,multiple_credentials_and_transports; runtime_versions_and_error_profiles_pending,SDK_MCP_HTTP_CLI_cross_read plus isolation plus versioned_error_envelopes,P0,uv.lock:931-983; live-transactions/evaluation/main.py:130-235; ab-testing/evaluation/main.py:133-150; SDK_v1.11.0_lowlevel/server.py:401-407_502-503
```
