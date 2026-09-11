# google_sheet 高保真模拟可行性与设计

> 领域作者：`/root/google_sheet`；本次由统筹显式创建，模型 `gpt-6-astra / xhigh`。非原作者 `/root/snowflake` 于 2026-09-10 完成只读交叉审查，审查模型同为 `gpt-6-astra / xhigh`；未发现实质修订问题，原作者已接受并登记 SH-01（见第 9 节及[审查记录](../review-ledger.md)）。查阅日期：2026-09-10；仓库 HEAD `ef7ab5928062defc0dc2a91a4c26ddebccb1a6a7`，结论同时核对当前工作树。已读原始需求、`shared.md`、`service-template.md`、`docs/mcp-analysis.md`、Forms 报告及公共合成/验证设计；未找到适用 AGENTS.md。本阶段只读源码和公开资料、编写报告，没有导入配置、启动 MCP、初始化业务、执行 benchmark 或真实服务写入。
>
> F=已核实事实，D=设计，A=规划假设，U=待确认；M/B/X 和 I/S/C/T/D/P 采用[共享定义](../shared.md)。结论：**15 个工具的契约与基础网格/Drive 状态适合代码实现，LLM 主要用于预生成业务数据；公式、格式、依赖版本造成的输出变化与多步骤部分成功是主要难点。Sheets + 必要 Drive 适合首轮试点，但不能把返回的 `folder` 或“工具未抛异常”当成独立成功证据。**

## 1. 范围、版本与入口

### 1.1 固定来源与运行边界

F：配置引用第三方 `xing5/mcp-google-sheets`，通过 `uvx mcp-google-sheets`/stdio 启动；注入 `CREDENTIALS_PATH`、`TOKEN_PATH`、`DRIVE_FOLDER_ID`，工具列表缓存，客户端超时 60 秒，没有只读、工具过滤或 API endpoint 参数。安装脚本固定 `mcp-google-sheets@0.4.1`，但 YAML 没写版本，实际 uvx 环境/镜像尚未核验。证据：`configs/mcp_servers/google_sheet.yaml:1-16`、`global_preparation/install_env.sh:199-207`。

固定发布源为 [PyPI 0.4.1](https://pypi.org/project/mcp-google-sheets/0.4.1/) 及 manifest 指定的[内容寻址 sdist](https://files.pythonhosted.org/packages/16/1f/9ea49480bffe470560f0d155f34f86a3fb5dafec79b4bcb6eeed70c076a8/mcp_google_sheets-0.4.1.tar.gz)。本次只读重新下载，核对包内 `PKG-INFO` 的 `Name/Version` 和三个源码文件字节，未执行包：

| 内容 | SHA-256 / 核对结果 |
|---|---|
| 发布归档 | `60b06da85d6a25a6d1413f2a704aab6a91a8a6fdac8c57206258758e311ec279` |
| `src/mcp_google_sheets/server.py` | `ee57b8d7e4459e16c682531fd5162ab78021a8894c99a11e745ff1e54d992908`，与本地参考一致 |
| `src/mcp_google_sheets/__init__.py` | `28d6756c3f5919fc99c25bfdd5479e7a06bfd65b110cbb367d840380d6c176d7`，一致 |
| `pyproject.toml` | `e85d0382117304590c10daeed6f8f9aeccdee069a375b06befc4d4f9ac218d6b`，一致 |

以下 **S:行号** 指 `/tmp/toolathlon-mcp-audit-xmv3srz8/mcp-google-sheets/src/mcp_google_sheets/server.py`，可由上述固定归档恢复同一文件及行号。包只要求 `mcp>=1.5.0`、`google-api-python-client>=2.117.0`、`google-auth>=2.28.1`、`google-auth-oauthlib>=1.2.0`（包内 `pyproject.toml:1-12`、`PKG-INFO`）；没有冻结这些依赖。不能把 0.4.1 当成完整协议锁定版本。

F/U：本机 `.venv` 元数据为 MCP SDK 1.9.0、Pydantic 2.11.3、gspread 6.2.1、google-api-python-client 2.171.0，各自 `*.dist-info/METADATA:1-3` 已文本核对；这不是 uv tool 隔离环境或任务镜像版本。下文 **K:** 指本机 `.venv/lib/python3.12/site-packages/mcp/`；关键序列化还核对了官方固定 [Python SDK v1.9.0 server.py](https://github.com/modelcontextprotocol/python-sdk/blob/v1.9.0/src/mcp/server/fastmcp/server.py#L872) 和 [v1.5.0 server.py](https://github.com/modelcontextprotocol/python-sdk/blob/v1.5.0/src/mcp/server/fastmcp/server.py)。二者都递归展开列表，JSON 缩进则不同；部署的握手版本、schema、输出仍需未来快照。外部源码和官方 API 文档均查阅于 2026-09-10；在线 API 文档属于该日期的 B 层资料，不扩大本版 M 层工具集合。

### 1.2 M/B/X 边界和认证

| 层 | 覆盖与必要边界 |
|---|---|
| M，F | 15 个静态工具和一个 `spreadsheet://{spreadsheet_id}/info` 资源模板；全部见第 2 节。没有直接 delete、values.append、clear、任意 batchUpdate、格式写入、SQL、搜索参数或分页工具。 |
| B，F/D | Sheets v4 工作簿/工作表/网格、值解释/计算/显示、插入维度/复制/改名；Drive v3 文件、父目录、权限、查询与排序。工具能读完整 grid metadata、写公式并复制既有复杂表，因此不能只存字符串二维数组。 |
| X，F | 初始化和评测直接使用 googleapiclient、gspread、Drive；本地 URL/ID 文件；部分任务跨 Notion、WooCommerce、邮件、本地 Excel。SDK 自身的数据补齐/类型转换也须保留。 |
| 不自动扩大，D | Google Sheets 网页协同编辑、Apps Script、Connected Sheets、完整 Office 编辑器、Drive 全平台不因同厂商而全部纳入；但其产生的既有 metadata 若经 M 可读，需要保留表示或明确 profile 限制。 |

F：S:27-32、43-112 请求 Sheets 和完整 Drive scope。认证顺序是 base64 service-account 配置 → 存在的 service-account 文件 → OAuth token/刷新或本地浏览器授权 → ADC；不是只有 YAML 显示的 OAuth。`CREDENTIALS_CONFIG` 的解码错误没有内层恢复；OAuth 刷新可能访问公网，交互授权会写 token；默认 service-account 路径也是候选。服务器使用 `build('sheets','v4')` 与 `build('drive','v3')`，没有 endpoint 注入。认证失败在 lifespan 阶段，不应生成伪造工具成功。没有读取实际凭据，本次无法确认 principal、scope 或 ACL 的有效授权。

F：`DRIVE_FOLDER_ID` 只影响 `list_spreadsheets` 查询与 `create_spreadsheet` 的后续移动；任意 ID 的读写和分享不先检查其父目录（S:125-272、712-770、820-930）。它**不是文件访问允许列表或 episode 隔离边界**。权限要由身份、scope、Drive ACL、保护范围共同判断；Sheets/Forms/Calendar 的 token 即使来自同一路径，也不能自动认定同主体。X 的 `utils/app_specific/google_oauth/ops.py:6-14` 也可能刷新 token。

公网分类：真实业务调用和 OAuth 刷新访问 Google 公网；uv/PyPI 安装下载另计；agent 模型与仿真模型 API 另计。D：预置依赖与本地业务/认证替代可使业务链无需公网；内网访问不算公网。未来 `IMPORTRANGE`、`IMPORTXML`、`GOOGLEFINANCE` 等外部依赖须分别声明允许范围、来源版本与出口，不能悄悄回落真实账户。

### 1.3 当前任务与全部额外入口

F：JSON 静态扫描当前 108 个 `tasks/finalpool/*/task_config.json`，恰有以下 11 个声明 `google_sheet`。表中使用是任务要求或源码路径，**不是已执行轨迹统计**。每行的 `preprocess/main.py` 除投资任务外均调用公共 Drive 文件复制链；初始化公共契约见下表后说明。

| 任务完整成员 | 需求线索与初始化 | 评测真实入口及证据 |
|---|---|---|
| `gdp-cr5-analysis` | 读源表、建结果工作簿/工作表；`docs/task.md:1`；`preprocess/main.py:29-41` | Drive 按父目录/名称/MIME/非回收站过滤，Sheets values.get `sheet!A:Z`；`evaluation/main.py:43-62` |
| `inter-final-performance-analysis` | 填三工作表，保存链接；`docs/task.md:1`；`preprocess/main.py:47-68` | Drive 查询/URL，gspread open_by_key/worksheet/get_all_records；`evaluation/check_content.py:75-90,132-184`；“只读链接”需求不等于已检验 ACL |
| `investment-decision-analysis` | 三个独立工作簿；`docs/task.md:1`；初始化只创建/清空目录，`preprocess/main.py:29-43` | Drive files.list，Sheets values.get 无工作表前缀 `A:Z`；`evaluation/main.py:57-100`；导入 gspread 不表示实际用它读数据 |
| `k8s-safety-audit` | 读旧周、写 Week3；`docs/task.md:1`；`preprocess/main.py:30-43` | Drive files.list、Sheets values.get，再结合 kubectl；`evaluation/check_google_sheet.py:48-74` |
| `llm-training-dataset` | 更新 `ptdata` 并按数据规模排序；`docs/task.md:1`；`preprocess/main.py:28-41` | Drive 查询后 values.get 引号包裹整张工作表名；`evaluation/main.py:138-165` |
| `music-analysis` | 从 Google Sheet 读取，产出本地多 sheet xlsx；`docs/task.md:1-4`；`preprocess/main.py:28-41` | 评测用 pandas.read_excel 比较本地 xlsx，**不读远程 Sheets**；`evaluation/main.py:19-48,99-120` |
| `nhl-b2b-analysis` | 读赛程、建结果工作簿；`docs/task.md:1`；`preprocess/main.py:28-41` | 公共 Drive 查询与 gspread 首张表 get_all_values；`evaluation/main.py:29-36`、`utils/app_specific/googlesheet/drive_helper.py:107-150` |
| `quantitative-financial-analysis` | 建表并把 URL 放入 Notion；`docs/task.md:1`；`preprocess/main.py:29-42` | Notion HTTP 读链接，gspread open_by_key/worksheet/get_all_records；`evaluation/check_content.py:18-46,57-130`；folder_id 参数只打印，不实际验证父目录 |
| `update-material-inventory` | 读 BOM、扣原料、反向更新 WooCommerce；`docs/task.md:1`；`preprocess/main.py:29-46,256-277` | 评测调用 `GoogleSheetsClient`，Drive get/list 支持 shared-drive flags 后 values.get；`evaluation/check_sheets.py:14-17,58-75`、`preprocess/sheets_setup.py:31-82` |
| `vlm-history-completer` | 读原表、补两列；`docs/task.md:1-2`；`preprocess/main.py:28-41` | Drive 按名称找，不存在则退到目录第一张表；gspread 指定 tab/get_all_values；`evaluation/main.py:109-171` |
| `woocommerce-stock-alert` | 更新采购表并邮件告警；`docs/task.md:1`；`preprocess/main.py:311-328` | 从 `files/sheet_id.txt` 取 ID，values.get `stock_sheet!A:H`；`evaluation/evaluate_updated_stock_alert.py:132-157` |

F：公共初始化读取 OAuth JSON 后 build 两 API；`find_folder_by_name`、`create_folder`、`clear_folder`、`copy_sheet_to_folder` 分别使用 Drive files.list/create/delete/get/copy/update、permissions.create，复制的是**整个工作簿文件**，随后给 `anyone/writer` 权限；不是 M 的单 tab `copy_sheet`。见 `utils/app_specific/googlesheet/drive_helper.py:10-91`。clear/list 都只调用一次 list，没有翻页。任务 token 文件按磁盘 `folder_id.txt` 读取动态目录，如 `tasks/finalpool/gdp-cr5-analysis/token_key_session.py:6-12`；模拟初始化不能继续指向真实模板 ID，也不能通过清理固定远程目录实现 episode reset。

F：gspread 6.2.1 在 `gspread/urls.py:9-34` 硬编码 Sheets、Drive、docs URL，`http_client.py:104-141,223-321` 用 AuthorizedSession 和真实 REST。`Worksheet.get_all_values` 默认 `pad_values=True`（`worksheet.py:474-494`），`get` 会补齐内部矩形（950-968）；`get_all_records` 还会表头校验和 numericise（497-610）；`update(raw=True)` 默认 RAW（1108-1117、1234-1237）。这些是 client 行为，不能在 HTTP 服务中照搬为所有入口的统一响应。固定上游：[gspread v6.2.1 worksheet.py](https://github.com/burnash/gspread/blob/v6.2.1/gspread/worksheet.py#L474)、[urls.py](https://github.com/burnash/gspread/blob/v6.2.1/gspread/urls.py#L9)。

U：在仓库可见路径和常见 `trajectory/messages/eval_res/launch/tool log` 文件名、以上任务源码范围，没有发现可用的完整 Sheets dump；外部结果目录不在本次证据内。当前没有 A1 真实记录或业务运行验证；任何具体工具的历史调用次数均未知。`terminal`/`python_execute` 存在意味着未来能走额外 SDK/HTTP，不能只替换 MCP 后声称任务已离线。

## 2. 工具与能力清单

### 2.1 全量工具、输入与 handler 返回

F：以下 15 个 `@mcp.tool()` 均无注册条件。模型侧名为 `google_sheet_` 加原工具名（`utils/openai_agents_monkey_patch/tool_name_aliases.py:21-28,85-99`）。说明列是中文概述；完整英文 docstring（含 Args/Returns）位于对应 S 行，未来 tools/list 快照须原样保留，不能拿报告概述替换工具说明。

F：输入 schema 为 object，由签名经 FastMCP/Pydantic 生成；`ctx:Context=None` 是内部注入，不暴露为工具参数。表中无默认值的参数全部 required；`str/int/bool` 对应 string/integer/boolean；`Optional[T]=None` 表示可省略或 null、默认 null；无 `minLength/minimum/maximum/format` 等显式约束。`Dict[str,str]` 仅约束映射值为 string，**不声明内部固定 key 必填或 enum**。`Any` 单元格不限制 JSON 类型，但后端并不接受任意 JSON 对象。SDK 的预解析/类型转换与 backend 拒绝须分层记录，不能擅自强制严格或放宽。证据：S 各签名；K:`server/fastmcp/tools/base.py:55-81`、`utilities/func_metadata.py:45-98,137-167`。

下表“返回”是 Python handler 返回值；**原始 content 包装另见 2.2**。R=读、W=写、A=权限管理、E=计算随写触发。

| 原始工具名 | 说明、属性、对象/状态 | required；optional/default 与额外校验 | handler 返回、API 映射、证据 | 现有需求线索；未来价值 |
|---|---|---|---|---|
| `get_sheet_data` | 取 tab/range 完整 grid；R；工作簿、ACL、类型/格式 | `spreadsheet_id:str,sheet:str`；`range:Optional[str]=None`；range 空串按无 range | 原样 `Spreadsheet` 字典，`spreadsheets.get(ranges=[sheet!range 或 sheet],includeGridData=True)`；S:125-157 | 11 任务可用读取路径、非调用证明；格式/公式审计 |
| `get_sheet_formulas` | 取公式视图；R；相同网格 | `spreadsheet_id,sheet`；`range=None` | `values.get(valueRenderOption='FORMULA').values` 或 `[]`，返回声明 `List[List[Any]]`；包含非公式原值，不过滤成仅公式单元格；S:159-192 | 实际 M 使用 U；依赖分析和公式纠错 |
| `update_cells` | 更新范围；W/E；网格/保护/依赖 | `spreadsheet_id,sheet,range:str,data:List[List[Any]]`；无矩形或数值范围预校验 | values.update，固定 `USER_ENTERED`，原样 UpdateValuesResponse：`spreadsheetId,updatedRange,updatedRows,updatedColumns,updatedCells` 等按 API；S:194-230 | 填表/库存/结果写入；通用表格操作 |
| `batch_update_cells` | 同 tab 多范围更新；W/E | `spreadsheet_id,sheet,ranges:Dict[str,List[List[Any]]]`；空映射、重叠范围不预检 | 映射迭代顺序生成 ValueRange 列表，values.batchUpdate 固定 `USER_ENTERED`；原样 `spreadsheetId,totalUpdatedRows/Columns/Cells/Sheets,responses[]`；S:233-272 | 写入需求可选路径；稀疏修订与批量性能 |
| `add_rows` | 在指定位置插行；W；grid/格式/公式引用 | `spreadsheet_id,sheet,count:int`；`start_row:Optional[int]=None`；0 基；默认在开头，非 append；无正数校验 | 先 metadata 按 title 找 sheetId；未找到返回普通 `{"error":...}`；否则 batchUpdate insertDimension ROWS，end=start+count、inheritFromBefore=start>0；S:275-330 | 实际调用 U；结构变更/错误边界 |
| `add_columns` | 插列；W；相同结构依赖 | `spreadsheet_id,sheet,count`；`start_column=None`；0 基、默认开头 | 同上，dimension COLUMNS；S:333-388 | 补列需求可用；结构引用迁移 |
| `list_sheets` | 按 API 返回顺序列 tab 名；R | `spreadsheet_id:str` | metadata→`List[str]`，不含 sheetId/index；S:391-410 | 多 tab 任务；发现与定位 |
| `copy_sheet` | 将一个 tab 复制到另一工作簿并改名；W；源读权、目标写权、网格及引用 | `src_spreadsheet,src_sheet,dst_spreadsheet,dst_sheet:str`；无默认 | 未找到源 tab 返回 `{"error":...}`；copyTo 后必要时另一次 rename，返回 `{"copy":SheetProperties,"rename":BatchUpdateSpreadsheetResponse}` 或仅 copy；S:413-484 | 历史调用 U；复用模板、跨工作簿资料迁移 |
| `rename_sheet` | tab 改名；W；稳定 sheetId/名字索引/公式引用 | **`spreadsheet:str`**、`sheet:str,new_name:str`；不是 spreadsheet_id | 先 metadata 查 title，未找到返回普通 error；batchUpdate updateSheetProperties(fields='title') 原样返回；S:487-538 | 建结果 tab 可用；命名修正与稳定引用 |
| `get_multiple_sheet_data` | 多工作簿/范围逐项取值；R | `queries:List[Dict[str,str]]`；内部 spreadsheet_id/sheet/range truthy 才读；缺 key或空串追加项目 error | 每 query 独立 values.get（默认格式化值），返回原 query 加 `data:二维数组` 或 `error:str`；保留额外字典键；不是一个原子 batchGet；S:541-586 | 多表对照需求；部分失败恢复 |
| `get_multiple_spreadsheet_summary` | 读取多工作簿 title、tab、表头/前数行；R；**没有语言总结** | `spreadsheet_ids:List[str]`；`rows_to_fetch:int=5`；实际 `max(1,rows_to_fetch)`，不以负数报错 | 每工作簿 `{spreadsheet_id,title,sheets,error}`；每 tab `{title,sheet_id,headers,first_rows,error}`；metadata fields 投影后逐 tab values.get `sheet!A1:{max_row}`，嵌套捕错；S:589-675 | 实际调用 U；多工作簿探索，超长表预览 |
| `create_spreadsheet` | 建工作簿、尝试移目录；W；Drive file/owner/parent | `title:str`；无空白/唯一性预校验 | Sheets create(fields='spreadsheetId,properties,sheets')→Drive get parents/update；返回 `{spreadsheetId,title,sheets:[名称],folder}`；目录移动失败仍返回目标 folder，S:712-771 | GDP/投资/NHL/金融明确创建需求；任意新工作簿 |
| `create_sheet` | 已有工作簿建 tab；W；title唯一/index/grid | `spreadsheet_id,title:str` | batchUpdate addSheet，提取 `{sheetId,title,index,spreadsheetId}`，index 可为 None；S:774-817 | 新 tab/结构任务；多 sheet 分析 |
| `list_spreadsheets` | 列配置目录的工作簿；R；Drive 文件索引/可见权 | 无 agent 输入 | 一次 files.list，q=MIME+可选 parent、spaces='drive'、orderBy='modifiedTime desc'、fields='files(id,name)'；返回 `[{id,title}]`；S:820-851 | 当前任务定位源/结果；目录发现 |
| `share_spreadsheet` | 对多人逐个授权；A/W；Drive ACL/主体/通知 | `spreadsheet_id:str,recipients:List[Dict[str,str]]`；`send_notification:bool=True`；内部缺 role 默认为 writer；缺 email、role 非 reader/commenter/writer 为逐项失败；无 email format校验 | permissions.create(type=user,fields='id')；`{successes:[{email_address,role,permissionId}],failures:[{email_address,error}]}`；后端错误尝试取 `content.error.message`；S:854-930 | 历史使用 U；协作分发/部分授权失败，不能因现有任务少用而删掉 |

F：`list_spreadsheets` 的描述说“all”“My Drive”，实际未传 pageToken/pageSize，fields 中也不请求 nextPageToken；没有 `trashed=false`、没有 `'root' in parents`，更没有 owner 限制。因此不能实现为“所有未删除的根目录文件”。Drive 官方说明 list 默认包含 trashed，并支持分页及多类语料范围；本版 M 只投影第一页，X 可完整翻页。[Drive files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list)（v3，查阅 2026-09-10）。

### 2.2 content、错误、资源与协议

F（明确依赖 profile）：本机 SDK 1.9.0 `K:server/fastmcp/server.py:272-279,872-891` 将 dict 转为一个 JSON text，将 list/tuple **递归展开为多个 content item**，str 是原 text，None 变零项。由此：`list_sheets` 是多个名称 text；`list_spreadsheets`、multiple 查询/summary 是每个 dict 一条 JSON text；`get_sheet_formulas` 的二维列表会展开至标量 text，行边界丢失；空数组可能成为空 content。不要把 Python 返回注解当 wire schema。1.5.0 同样展开但 JSON 紧凑化，1.9.0 用两空格缩进；更高版本行为 U。该版本不会自动产生这里未声明的 outputSchema/structuredContent；工具未设置 readOnlyHint/destructiveHint 等 annotations，也没有图片/音频返回路径。

F：`K:server/fastmcp/tools/base.py:84-100` 把校验/执行异常包成 ToolError；`tools/tool_manager.py:60-64` 对未知工具抛 ToolError；`server/lowlevel/server.py:410-421` 最终返回 text + `isError:true`。这条结论仅适用已核对 SDK profile，不能强制所有错误为 JSON-RPC error。原始工具结果经本仓库 `custom_mcp_util.py:176-229` 再串行化 content，顶层 isError 不单独写给模型；需双层 golden。

| 错误路径 | 本版 handler 行为与提交边界 | 设计要求 |
|---|---|---|
| 类型/缺必填、未知工具、未捕获 API 错误 | FastMCP 工具错误路径；典型 includeGridData/get/update/batch/create 的 API 失败会向上抛；S 对应工具、K 同上 | 保留经过 SDK 包装的 text/isError，HttpError 的状态/内容前缀须未来样例确认 |
| add_rows/add_columns/rename 缺 tab；copy 缺源 tab | 直接返回 `{"error":...}`，SDK 视为正常返回/isError=false；S:304-305,362-363,442-443,514-515 | 不能提升成统一异常，oracle 必须解析业务结果及检查状态 |
| multiple 查询/summary | 每 query、每工作簿或每 tab 捕错，其他项继续；S:565-586,615-675 | 返回中可以同时有数据和 error，不清除已有成功读取 |
| share | 按 recipient 循环提交，各自成功/失败；S:880-930 | 有部分 ACL 已改变；不能全部回滚，也不能全部成功 |
| create 后移动失败 | 创建已经提交，移动捕错只 stdout warning；仍回显配置目标 folder；S:734-770 | 兼容 profile 保留返回缺陷，状态保留真实父目录；该缺陷轨迹单独标注，修复 profile另版本 |
| copyTo 后 rename 失败 | copyTo 已提交，新 tab 保留，后续异常传出；S:445-484 | 不原子回滚；重试可再复制，不能按调用内容偷偷去重 |

F/U：资源模板 `spreadsheet://{spreadsheet_id}/info` 注册函数 `get_spreadsheet_info`，预期读取 metadata 后返回 JSON 字符串 `{title,sheets:[{title,sheetId,gridProperties}]}`（S:678-709）；无额外资源实例、prompt、订阅或业务 notification 注册。SDK 1.9.0 默认资源 MIME `text/plain`（K:`server/fastmcp/resources/base.py:29-32`），template list 未补 MIME（`server.py:295-304`）。但实现调用 `mcp.get_lifespan_context()`，该方法在核对的 SDK 1.5.0/1.9.0 不存在；在这些 profile 下预计读取失败，不能宣称可成功读取。资源异常经 read_resource 路径，不等于工具 isError 路径（K:`resources/types.py:54-69`、`server.py:306-318`、`lowlevel/server.py:285-341`），具体 JSON-RPC code/message 和实际镜像需受控核验。

F/U：server 未显式传 MCP version，FastMCP 设置依 SDK；入口包 `__init__.py:4-6` 对同步 `server.main()` 使用 asyncio.run，而 S:932-934 内 mcp.run 自己运行 transport。初始化和建表中的 `print` 未指定 stderr（S:59-101,741-764,837-839），stdio 文本污染及退出行为需要无业务启动契约样例确认；当前不能推定影响已发生，也不能静默修正为已验证成功。上述兼容缺陷不应成为默认训练任务的取巧条件。

### 2.3 B/X 值、公式、A1 与批量语义

| 能力 | 已有依据和明确边界 | 需要实现/验证的关键语义 |
|---|---|---|
| RAW / USER_ENTERED | M 两个值写工具恒 USER_ENTERED；RAW 仅 X API/SDK 可选。官方 [ValueInputOption](https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueInputOption) | RAW 字符串不解析，USER_ENTERED 按 Sheets 输入规则解释数字/日期/公式；不可给 M 添加 raw 参数，也不可把 `=...` 永远当文字。按 locale、现有格式和输入类型做差分。 |
| 值与空白 | API ValueRange 支持 bool/string/double；null 是跳过写，空串是写空；默认 ROWS；输出裁剪尾部空行列。官方 [ValueRange](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values) | 未传、null、空串、0、false、稀疏洞不同；不把未覆盖区域清空，不固定补满请求尺寸。X 的 COLUMNS 与 gspread补齐在入口层处理。 |
| 三种读取 | `get_sheet_data` 获取 GridData；FORMULA 获取输入公式/其他值；普通 values.get 默认格式化值。官方 [CellData](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/cells)、[ValueRenderOption](https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueRenderOption) | 持久化输入、计算 effectiveValue、显示 formattedValue 和 numberFormat；formulaValue 与 errorValue 不混成普通字符串。GridData 的 startRow/startColumn、rowData.values 及省略默认字段需保留；includeGridData 不是任意矩形自动补零。 |
| A1 和身份 | API 支持有限/开放端/整行/整列、带引号 tab、同名 named range；sheetId稳定，位置不稳定。官方 [概念/A1](https://developers.google.com/workspace/sheets/api/guides/concepts) | M 直接拼接 `sheet!range`，不自动加引号；带空格/特殊字符、A1形似名字、引号转义需差分。metadata查 tab 的工具按精确原名比较，不能一律剥引号。summary 固定生成 `title!A1:N`，其合法边界待实测，不擅自改成 A1:ZN。 |
| 结构变动 | M insertDimension 0基、endIndex开区间、inheritFromBefore由位置决定；create/rename/copy见 S | 行列插入要移动内容、格式和相关引用；tab改名保留 sheetId并调整公式；复制建立新sheetId，内部/外部引用变化须差分，不能仅复制 value JSON。 |
| 批量写 | Sheets values.batchUpdate 是多 ValueRange；spreadsheets.batchUpdate 是有序 Request 列表，两者不是同一API。官方 [values.batchUpdate](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/batchUpdate)、[batchUpdate](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate) | 单次API请求原子应用，任一非法子请求不产生部分写；按请求顺序返回 responses/replies及空reply。M ranges字典只有一个tab且无法表达重复同key；重叠不同range的具体终态/计数需真实反例确认，不能假设可以任意重排。 |
| 时间与配额 | 日期/时间是数值+格式，见 [DateTimeRenderOption](https://developers.google.com/workspace/sheets/api/reference/rest/v4/DateTimeRenderOption)。官方[限额](https://developers.google.com/workspace/sheets/api/limits)声明单API原子、超时、分钟配额 | 冻结 locale/timeZone、日期解析、TODAY/NOW/随机重算政策；模拟429/超时/提交后丢响应分开。指南的2MB是建议payload而非硬上限，不能将其当必拒绝阈值；真实项目配额是 profile 数据。 |

上述官方资料为 Sheets v4、查阅 2026-09-10。M 多工具各自发出多个 API 请求时，不享有跨 API 原子性；不能将官方“单请求原子”外推到 create+move、copy+rename、share循环或多个 summary 读取。

## 3. 领域状态模型

D：权威业务状态按 `(episode,principal,spreadsheetId)` 路由；Sheets 与 Drive 使用相同文件 ID。PostgreSQL/SQLite 只存状态与事务，不替代公式解释器。状态从事件日志重建，LLM 对话不是数据库。

| 持久实体 | 字段、关系、不变量 | 派生/入口约束 |
|---|---|---|
| Principal / OAuthGrant | episode主体、账号类别、scope、有效期/撤销、组织策略；测试认证令牌映射身份 | 不把 token 值或 gcloud/ADC 默认身份作为共享答案；scope和ACL分别校验 |
| DriveFile / Folder | fileId、MIME、name、parent、owner、created/modifiedTime、trashed、permissions版本；工作簿fileId=spreadsheetId | `name`与Spreadsheet title同一对象的两视图；同名文件合法，目录查询、直接ID读取与隐藏资源一致；父目录移动不改ID |
| Spreadsheet | spreadsheetId、properties(title,locale,timeZone,autoRecalc/defaultFormat等)、有序sheetId集合、namedRanges、资源版本 | URL可由稳定ID派生；API省略字段不能靠默认空对象全面填充；工作簿版本为内部并发控制，不擅自增加 M 响应字段 |
| Sheet | 工作簿内稳定非负sheetId、title、index、sheetType、gridProperties(row/columnCount、冻结/隐藏)、merges、保护、格式规则 | tab标题唯一；索引连续且可变；插行列改变坐标和维度，rename不分配新ID；删最后tab限制在X相应profile中明确 |
| Cell / GridChunk | 0基坐标、userEnteredValue联合类型、userEnteredFormat、note/runs/validation；稀疏网格分块 | effectiveValue/有效格式/显示值由输入+依赖+locale+时钟计算，可缓存但带依赖版本；空格不是空单元格 |
| FormulaGraph | 公式AST、原始输入、绝对/相对/命名/跨tab引用、依赖版本、重算状态、错误类型 | 不把LLM输出当计算值；变更依赖后失效；循环/缺引用/除零/数组覆盖需按支持profile处理 |
| Permission / Notification | fileId、permissionId、type、role、email/domain、继承来源、能力；模拟通知outbox | M只建user reader/commenter/writer；X初始化anyone writer也必须可表达；共享权限立即影响各入口，通知只记录/投递本地outbox |
| Operation / Snapshot | API提交序号、调用ID、read/write集合、故障阶段、回复、快照hash、虚拟时钟、日志 | 非幂等create/insert/copy的新调用可以再次生效；回放旧响应不是把未来相同参数请求去重 |
| CrossServiceRef / Blob | Forms linkedSheetId、Notion/邮件里的URL、外部公式来源ID/版本、必要图片/附件字节hash | 链接与拷贝区分；Forms响应同步到关联表需事件和映射，不能凭linkedSheetId猜测已写入；未暴露二进制工具不发明上传能力 |

D：M↔googleapiclient↔gspread↔直接 REST 共用业务引擎；SDK内格式化/补齐只在client发生。Google API替代至少路由 Sheets `/v4/spreadsheets`、values路径、`:batchUpdate`、sheets `:copyTo`，Drive `/drive/v3/files`、`/drive/v3/files/{fileId}/copy`和`/drive/v3/files/{fileId}/permissions`；Drive复制是POST `/copy`，不是Sheets风格冒号方法。证据：[Drive files.copy](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/copy)。这些只是必要子集，路径/verb/fields/query以真实discovery为准。稳定 `https://docs.google.com/spreadsheets/d/{id}/edit#gid={sheetId}` 形状可作为引用保留；浏览器实际打开需要显式本地页面/代理profile，返回一个看似Google URL不等于页面兼容。

D：共享Drive层与 Forms 报告一致，持有file ID、父目录和ACL；Sheets负责网格/公式，Forms负责问题/响应，不能统一成泛CRUD。Forms linkedSheetId读取并不等于当前Sheets MCP能创建关联或自动收集响应；以后支持同步必须有单独事件语义和跨域oracle。

## 4. 代表性交互序列

D：以下为未来生成/验证样例，初态与调用顺序可变，不绑定现有任务答案。

| 序列 | 可验证状态断言 |
|---|---|
| 创建工作簿→Drive查父目录→create_sheet→写值/公式→三种读取→rename→X删除文件→旧ID读 | fileId与spreadsheetId一致；公式计算正确；rename不改sheetId；删除后不能从任一入口继续读取活资源。目录移动注入失败时，create返回folder与Drive实际parent可能不同，必须识别。 |
| X生成多页Drive目录→M列表→X跟pageToken定位晚页→M直接ID读取→批量更新→逐范围读取 | X跨页不重不漏；M仍只第一页，反复调用不会自动前进；直接ID能读权限允许的晚页文件。批量所有结果与单读一致，modifiedTime排序变化可解释。 |
| X RAW写 `=1+2` 与 M USER_ENTERED写同串→formula/grid/value三入口→改依赖值→再次读取 | 第一格仍字符串，第二格为formula与计算值；展示格式和原始输入可追溯；不能让M或SDK差异消失。 |
| 源tab跨行公式→add_rows/add_columns不同位置→rename→copy_sheet到另簿→再改源 | 坐标/绝对与相对引用按规则调整；复制是独立网格；复制目标命名冲突时已有副本保留；源后续写不直接改复制值，除非有明确外部引用。 |
| 读权限主体更新失败→有分享权主体share(reader/非法role/缺email/writer)→两主体交叉读写 | 逐项成功/失败和ACL实际一致；reader能读不能写；writer可写；无权限拒绝不能自动提高权限。固定folder不阻止合法的目录外ID读取。 |
| batch有效范围+非法范围→确认无写→agent修正→成功→与两个独立update比较 | 单API非法批次无部分写；独立两次update允许前次已提交；响应计数/顺序真实，重叠range与null跳过有专门oracle。 |
| 多工作簿summary含空tab/无权文件/特殊标题→get_multiple_sheet_data混合成功/失败→单项定位 | summary是读取投影，不能编造说明或数据；error局部保留；先summary/先单读都指向相同状态，多个请求不承诺同一事务快照。 |
| 表格URL写到Notion或采购邮件→另一主体按URL从SDK读取→权限撤销/文件移目录→重读 | 引用指向相同ID；移动不破坏ID；撤权后的读取不泄漏；URL文本本身不授予权限。涉及撤销使用X已支持权限API，M没有撤销工具。 |

## 5. 候选实现与推荐

### 5.1 路线比较

D：I接口、S状态、C一致性、T身份时间、D分布、P规模分别判断，不用一个“兼容分”。下列“可精确”均指通过差分后可在声明profile内达到，不代表已实现。

| 路线 | I/S/C/T/D/P 与成本取舍 | 结论 |
|---|---|---|
| 保留固定MCP，替换Sheets/Drive后端 | I最接近已冻结依赖；S/T仍需领域引擎；HTTP统一可使C较强；D靠生成器；P受同步SDK/JSON影响。认证、build/discovery、硬编码URL路由成本明显 | **首选集成路线**：固定MCP+共享本地API核心，启动注入由后续实施单独设计；不能只改一个环境变量就宣称完成 |
| 有状态MCP替代实现 | I需复刻签名/docstring/奇异错误/content，容易比原版“更好用”而失真；S/T同等开发；只有M时C不完整；P低调用开销 | 备选M适配器，必须与X共用同一后端和契约golden，不以独立JSON store替代整条链 |
| 本地HTTP/API兼容服务 | 路径、HTTP错误、fields、分页更可验证；S复杂但可复用多SDK；C/T有统一落点；D独立；P适合跨episode并行 | 首选权威服务核心；先实现支撑全部M和必要X的API面，其余明确profile不支持 |
| SDK/client适配 | 复用gspread补齐/数值化，减少对外HTTP模拟；但每语言/CLI另接线，遗漏任一路径会分叉 | 可作为受控harness内的连接方式，适配transport/endpoint、不重写任务答案或评测逻辑；不覆盖任意终端HTTP |
| 现成表格引擎/办公服务 | 计算和xlsx导入可复用，但不含Sheets v4、Drive ACL、Google特有公式/格式。I/C/T不能靠产品名解决 | 仅作组件；见5.2；不宣称可直接替代Google Sheets |
| 静态fixture/回放 | 有记录时I精确，S只在原序列、C/T不能自然组合；P高、开发低 | 契约golden/初态/故障样本辅助，不作自由交互后端 |
| LLM主导 | I可受schema约束但列表/数值易错；S/C/T需要几乎完整校验器；D文本多样；P和长期费用差 | 可做受限对照，不推荐生产在线读写/计算；无状态对话方案直接排除 |
| 代码状态/计算 + LLM预生成 | I/S/C/T由代码；D增加行业/语言/噪声；P无每工具模型延迟，生成费按episode摊销 | **推荐总体方案**；内容不能在查询时按agent需求新造 |

F/D：原server的build没有endpoint参数；本机google-api-python-client支持 `client_options.api_endpoint`（`googleapiclient/discovery.py:315-323,569-585`），但本server未使用，不等于已有配置开关。后续保留MCP可选择受控service factory/transport注入或本地discovery；gspread硬编码URL也必须一起路由。DNS/TLS全局重定向风险与难度更大，不作为默认设计。认证用可检查的模拟grant，网关明确拒绝未支持出口，避免凭据刷新意外连接真实Google。

### 5.2 现成公式引擎的已核实边界

F：HyperFormula 3.4.0 的官方tag已解析到固定提交 `af2d59dc61ec1434498c7233d06e77370e7235b8`；`package.json` 确认3.4.0、GPL-3.0-only，官网另有商业授权路线。它是headless计算组件，有依赖图、表内/跨tab引用及大量函数；不是Sheets/Drive API服务。以下均以该固定源码和2026-09-10资料为准：

| 已核实组件 | 可复用内容 | 不可推定兼容的部分 |
|---|---|---|
| HyperFormula 3.4.0 | 单实例多worksheet、依赖重算、常用算术/统计/逻辑/日期函数；采用差分通过的函数及配置白名单 | 每实例仅一个workbook；异步、动态数组等缺口；FILTER/SEQUENCE输出尺寸受静态推导约束，SUBTOTAL不忽略嵌套小计。不能把Google动态范围/跨工作簿/外部函数直接接上。固定[known-limitations.md:9-38](https://github.com/handsontable/hyperformula/blob/af2d59dc61ec1434498c7233d06e77370e7235b8/docs/guide/known-limitations.md#L9) |
| HyperFormula的Google兼容配置 | TRUE/FALSE命名表达式、array模式、日期/数值与separator可配置 | en-US千分位与参数分隔符无法同时采用相同逗号；locale/date/TEXT需额外适配；“Google兼容”不是完整计算等价。固定[compatibility-with-google-sheets.md:17-94](https://github.com/handsontable/hyperformula/blob/af2d59dc61ec1434498c7233d06e77370e7235b8/docs/guide/compatibility-with-google-sheets.md#L17) |
| LibreOffice Calc（本轮仅核官网当前说明，未冻结可执行版本，U） | 可评估真实本地公式计算与Office文件导入导出 | 官方明确Excel导入/导出存在公式、格式等转换差异，更不能推出Sheets语义等价；UNO/进程启动、隔离、格式转换的额外成本未测量。[官方转换限制](https://help.libreoffice.org/latest/en-US/text/shared/guide/ms_import_export_limitations.html) |
| openpyxl 3.1.3文档 | xlsx读写、公式文本及缓存值作为导入辅助 | 文档明确不计算公式；不能作为effectiveValue oracle或Sheets计算后端。[Simple Formulae](https://openpyxl.readthedocs.io/en/3.1.3/simple_formulae.html) |

D：首选评估HyperFormula加Google输入/渲染/引用适配；若某函数不兼容，优先补确定性实现/缩小显式profile，不交LLM猜数字。许可选择计入选型成本，不从商业文档推定当前项目已获授权。本轮没有安装、执行或压测上述引擎；函数“存在”不证明参数边界等价。完整公式能力长期分期，并保留公式族、locale、错误/循环/数组行为的覆盖矩阵。

## 6. 保真缺口与取舍

| 能力 | 可达层级与取舍 | 会训练出的错误规律 | 验证/降低影响 |
|---|---|---|---|
| 15工具名称、签名、handler请求映射 | I依据固定源码可准确；SDK生成的完整schema/content须冻结依赖后核验 | rename使用错误参数名；把二维formula结果当固定JSON数组；未知工具层级错误 | 原始tools/list与model-view双快照，SDK1.5/1.9不能混用 |
| 基础网格/ID/CRUD/Drive | S/C限定范围可精确 | 写后另入口无数据；目录=ACL；假folder成功；重命名换ID | 多入口读、独立parent/ACL checker、部分失败历史 |
| A1/类型/值/空白/基本格式 | 可依据规范实现，但locale/省略字段/错误文本需差分 | null当清空；所有数值字符串；加行=末尾追加；输入范围自动修正 | 类型边界、原始grid与ValueRange分别比较、特殊标题/稀疏表 |
| 常用公式与依赖图 | 小集代码可精确；引擎兼容仅经验证的组合 | formulaValue、effectiveValue、formattedValue互相矛盾；改源不重算 | 独立小算例+受控Sheets差分；输入/引用/错误/格式一起比 |
| 高级公式/外部数据/迭代计算/动态数组 | 高代价，分期；不假成功或假`#NAME?`冒充Google不支持 | Google合法函数被训练成无效；凭空产生实时金融数据；数组覆盖静默丢值 | 模拟器不支持错误明确标记扩展，失败轨迹隔离；补全函数前不生成依赖其成功的任务 |
| 格式/保护/合并/验证/条件格式/pivot | 读取与复制需保留；基础有效格式/保护优先，复杂动态计算分期 | 只要值对就算全表正确；修改受保护格成功；复制后metadata消失 | rich初态、保护反例、复制前后比较；不能用过期缓存假装有效格式 |
| list/分页/排序 | M首页限制可准确；X语法/分页需实现；并发页水位细节U | 一次list必穷尽；重复请求下一页；所有list都自动排除回收站 | 大于页边界、同modifiedTime、trashed、目录外直接ID；不统一改写q |
| 批量/多步提交/重试 | 单API原子可实现；跨调用不原子；重叠值计数细节U | 重试create没有副作用；share自动全成或全撤；失败就保证无变化 | 请求内外分开故障注入、状态/计数oracle、重复操作集合 |
| 身份/时间/并发 | 基础ACL/作用域/虚拟时间可精确；组织/共享盘/可见延迟U或分期 | 链接=权限；权限写天然支持并发合并；真实分钟配额不存在 | 多身份矩阵；官方permissions.create指出同文件并发权限操作不支持，仅最后更新应用，不能宣称串行化即完全复刻；[官方来源](https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions/create) |
| resource/stdio/实际运行镜像 | 已发现源码兼容疑点；部署结果U | 所有列出的资源一定能读；stdout日志可当协议消息 | 先冻结依赖做无业务契约检验，兼容/修复profile分开 |
| 数据分布与性能 | D/P不能从契约推断 | 只记模板、永远小表/无权限错/同序列 | 多seed/稀疏密集/长文本/含公式干扰；吞吐必须在通过语义门槛后测 |

## 7. LLM 仿真可行性

### 7.1 职责与一致性

D：推荐**代码业务引擎 + LLM离线生成内容**。LLM适合组织背景、产品描述、研究条目、多语表头、合理噪声/重复内容等初始化提案；数值、日期、外键、答案与计算约束经代码校验。M没有“智能总结”或生成文本工具；summary只取表头/前行，read只读已有内容，share只写agent指定ACL。在线LLM不得额外写分析结论、补业务缺失资源或替agent构造公式。

| 路线 | LLM能决定 | 硬性外部校验/不能委托 | 开发与长期成本 |
|---|---|---|---|
| 主要代码 | 可不用LLM；模板/受约束生成器产生初态 | schema、ID、ACL、A1、计算、引用调整、排序/分页、事务/错误均代码 | 首期语义成本较高，单调用成本低；长期扩展需差分库 |
| LLM主导受限仿真 | 仅对鉴权后的相关状态提出允许的cell/metadata patch或查询投影 | 检查每单元格来源、完整写集、权限、公式执行、read-set版本；响应从提交态生成 | 可减少部分dispatcher代码，几乎省不了正确性引擎；长表token/验证费用高，不推荐生产 |
| 混合 | 预生成业务内容和候选分布；高频读写走确定性路径 | 所有在线状态转换/读结果由规则和执行组件；预生成内容提交一次成为事实 | 综合推荐；付一次生成成本摊到多交互，避免每次调用引入延迟 |

D：如做在线对照，链路为调用+完整必要状态→LLM提案→外部校验→按真实API边界提交→render已提交态。相关状态用A1/文件索引查询得到：读范围取ACL/网格/格式及依赖闭包，插入/改名取所有受影响引用，copy取源对象与目标名字/ACL，list查询必须先获得候选全集/索引水位。禁止让LLM用摘要猜未命中对象；大表分块和索引检索，超过支持计算/上下文预算明确失败，不丢范围。

D：LLM输出只包含 `{read_versions,proposed_operations,field_sources}`，不发明ID/计算结果。规则校验原始参数，不帮agent纠正非法range/role；公式执行器提供值，不信任proposal数值。对合法提案按每个真实API事务提交；copy/rename与share各子操作边界保留。版本冲突重取状态；内部修复最多一次（A），仍失败返回明示模拟器失败、无新增提交；不得伪装Google业务错误。最终响应由代码从提交结果构造，防止proposal与实际状态不一致。

D：模拟器不接收任务答案/评分目标/成功轨迹；sheet文本作为业务数据而非指令。负查询也需确实查索引；读取不生成资源；非法参数不“理解意图”后修复。记录模型供应商/版本、prompt版本、相关状态及hash、模型原输出、validator结果、提交和响应；回放只复用已记录提案/提交，不再次采样。read-cache键包括episode/principal/ACL/locale/profile/依赖版本和虚拟时间，不能跨主体或跨clock窗口复用。

### 7.2 成本、规模与对照

A（规划而非实测/报价）：纯代码每工具0次仿真模型；混合每episode预生成1–3次，输入2k–8k、输出2k–10k token，之后50–200个工具调用摊销。LLM主导每工具1次提案，平均修复率r=0.05–0.2时为1+r次；范围小的调用输入4k–16k、输出0.5k–3k，复制/大表可能远超该区间。大range直接返回真实数据的token不是可以通过LLM“总结”缩掉的成本。

A：百万调用的额外模型费用为 `(1+r)×(Tin×pin+Tout×pout)`，pin/pout为每百万token价格。示例 `Tin=8000,Tout=1000,r=0.1` 得 `8800×pin+1100×pout`，不代入当前厂商价格。混合在线占比f时乘f，另加初始化；有效轨迹成本还除以独立验收有效率，加存储/CPU/公式/验证/废弃重跑。不能仅比较模型账单或工具完成率。

A：模型单次延迟假设1–10s，则在线额外平均延迟约(1+r)倍，加状态读取/校验；长调用可能碰当前60s客户端超时。若目标Q=100 tool/s、r=0.1、均值3s，全在线需约330个模型在途，输入速率约880k token/s；这些是容量算式，不是已观测性能。预生成、确定性读/公式、版本缓存、离线批处理可降本；只批处理独立episode/不改变因果顺序的操作。

D：三组盲测用相同profile和held-out初态：A代码+模板，B代码+LLM预生成，C受限在线提案+硬validator。A/B比较文本/任务多样性与最终真实迁移；C比较开发工时、错误接受/拒绝正确调用、长序列漂移、幻觉/静默修复、修复率、token/p95/每有效轨迹费用。结构/数值由独立oracle判，不用同一LLM自评。预计C难在该域获得净收益，这是需要数据证伪的设计判断。公共主试点可以验证内容预生成价值；公共[验证计划第5节](../validation-plan.md)已将在线LLM补充试点选为W&B原生文档问答（由其领域报告核验契约），不将本版summary改造成生成式功能。Sheets的C组仅是可选状态提案压力对照，不是首轮必须部署的路线。

## 8. 合成、验证与分期

### 8.1 多样初态、任务与隔离

D：seed分别控制资源数量、表结构、内容、ACL、历史、故障/虚拟时钟；变化0/1/多工作簿、多tab、重名文件/近名tab、多语言特殊名、不同locale/timeZone、短长文本、稀疏表/空尾、bool/数值/文本数字/日期、公式链/循环/错误/隐藏行/保护/格式、目录外共享文件/回收站/大于分页边界。先生成满足不变量的事件序列，再物化初态；LLM内容经校验后记录bytes/hash，seed本身不保证重采样相同。

D：任务可从状态目标生成，也可由约束反向建环境；目标例为“给符合业务条件的记录更新、其余不变”“建立指定角色的可访问副本”“修复依赖引用而保留格式”。独立可解性checker验证权限、支持函数和可用入口存在至少一条合法路径；不要求固定工具顺序。M没有分页/删除/RAW时，不能给仅M环境安排必须用这些能力才能完成的任务；可预置目标在首屏、给ID或显式启用X，但不能暗藏额外工具或泄露答案。

D：episode从会话/模拟凭据决定，不接受agent参数切换；同资源的M/X/API共享状态，跨episode文件ID/权限/缓存/对象blob访问关系隔离。网格稀疏分块，公式依赖图按工作簿缓存，copy-on-write快照保存ACL/locale/时钟/公式版本/事件队列；只分享不可变字节，不共享写入状态。reset创建新generation并使旧会话失效；恢复按API提交收据重建，不重放业务create。每工作簿短事务、跨workbook copy保留两段边界；大规模跨episode并行，公式执行加资源预算，禁止用全局真实Drive清理复位。

### 8.2 独立验证设计

| 验证族 | 必测样例和独立证据 |
|---|---|
| 契约/协议 | 冻结MCP+SDK+Pydantic后完整tools/resource-template快照；15工具签名/docstring/默认/ctx排除；dict/list/二维list/None/空content；isError及harness模型视图；未知工具、resource失败；真实镜像U先补证据 |
| 参数边界 | 空ID/空标题、缺字段/类型/null、count≤0、0基/末端插入、非法A1/引号、ragged值/嵌套对象、非法email/role、负rows_to_fetch、未知query字典键；分别按schema/wrapper/backend判断 |
| 业务状态 | 创建/父目录/改名稳定ID、删除/复制/修改独立性、null跳过/空串清空、保护/格式继承、单API batch原子与跨API部分成功、重试非幂等 |
| 公式 | 人工审定小网格的手算值/类型/错误、Google规范样例、未来真实Sheets差分；同单元格RAW/USER_ENTERED和三读取视图；绝对/相对/跨tab引用、rename/insert、locale/date、循环/数组溢出；不以同一公式引擎生成期望 |
| 多入口/跨服务 | M写→googleapiclient/gspread读；SDK RAW写→M读；Drive复制→M列tab；ACL变动跨主体；Notion/邮件URL→相同文件；gspread补齐/numericise属于client，HTTP保持ValueRange语义 |
| 搜索/时间/并发 | X完整分页和M首屏限制；q/name/parent/trashed/fields；modifiedTime排序/同刻tie；并发值写和权限竞争；提交后响应丢失、copy后rename失败、create后move失败 |
| 隔离/复现 | 同名同形ID的不同episode、缓存ACL变更、快照/重置/旧游标/故障恢复；输入/状态/输出hash可重建；无双提交/跨episode污染 |
| 生成/LLM质量 | held-out调用图和业务域、长序列、名字重排反事实、近重复/权限干扰；无资源/字段幻觉、无答案泄漏、无成功偏置、无文本指令越权；独立检查+人审文本分布 |
| 规模/成本 | 在相同保真门槛后测1→10→100episode，p50/p95/p99、公式依赖变更成本、大响应序列化、DB/blob、模型token/修复率/每有效轨迹总成本；不给未测吞吐承诺 |

D：独立oracle只读状态导出/Drive ACL/实际值与审计事件，由不同逻辑实现；禁止导入同一handler或只信`success/folder`。mutation testing注入“写无效但成功、错父目录、null清空、读写分叉、列表补全、公式值过期、越权、复制无新ID”，要求oracle全部检出。ID比较建立保持引用的双射，不删除ID字段；时间比较保留排序/时区/精度；列表只在真实无顺序保证时无序比较；浮点容差依据函数和格式，精确计数/布尔/字符串不放宽。

F/U：现在只有静态源码/官方资料，尚无可用真实dump。未来现成记录可验证已发生的schema/content/API映射及部分错误，但单条响应不能证明前置态或未用能力。受控真实差分需要专用Drive目录、两到多个测试主体、冻结MCP及依赖/locale/配额、授权的创建/改写/分享/删除清单、有限通知对象和脱敏记录；本阶段仅设计这些条件，没有执行真实写入或发送通知。

### 8.3 首轮试点和扩大范围

D：认可公共 **Sheets + 必要Drive** 主试点，作如下精确化：

1. **P0契约冻结**：确认实际uvx依赖/镜像、15工具和资源模板、原始与模型输出；资源缺陷/列表展开/stdio疑点单独立profile，不默认修复。
2. **P0核心语义试点**：基础创建/列举/网格读写/稀疏批量/工作表增改/插行列/复制/分享；必要Drive文件/目录/ACL；googleapiclient与gspread交叉读写。首轮包含算术、SUM/AVERAGE/IF和同簿跨tab引用的小公式集及RAW/USER_ENTERED差异，不只写字符串。复杂公式明确尚未支持，不能把本阶段profile称为全Sheets兼容。
3. **P1覆盖扩大**：补完整已注册工具的合理参数组合、高级format/保护/合并/验证、更多公式及引用、shared-drive/分页/并发差分、读取丰富metadata；全量任意Sheets batchUpdate不是M工具，按X需求及迁移价值逐类加入，不能误算成已暴露M能力。
4. **P2长尾**：复杂数组/命名范围/外部公式/Forms关联同步、Office导入导出、需要时的浏览器profile。每新增能力先函数/错误/状态差分再放入合成任务，长期边界仍按M合理行为保真需求拓展。

D：建议至少30个未见seed，每个变化结构/权限/内容三轴；关键负例/状态机会≥3000且样本内硬错误0；100–1000步长序列，1→10→100episode隔离恢复；原始schema/输出未解释差异0、多入口状态分叉0、独立oracle能检出上述mutation，之后才扩大公式与吞吐。沿用公共验证计划的统计限定：样本零错不证明总体零错，独立近似下95%错误率上界约3/n，相关长序列按环境聚类。试点只比较LLM预生成内容时，不据此宣称在线LLM仿真已获益。

## 9. 待确认与审查记录

| 编号 | 缺失证据/冲突 | 所需核验与当前处理 |
|---|---|---|
| U1 | 实际uvx/容器的mcp、Pydantic、google client版本及握手 | 未来无业务镜像清单+tools/resources快照；已冻结0.4.1包字节，未冒充部署锁文件 |
| U2 | SDK列表展开、resource不存在方法、stdout与入口退出影响 | 已核1.5.0/1.9.0源码；待隔离无业务契约运行，分别登记兼容/修复profile |
| U3 | 复杂A1（尤其summary的A1:N）、引号、空标题、ragged/null、重叠batch计数 | 后端真实反例/差分；保持wrapper原始参数拼接，不擅自修正 |
| U4 | 拷贝跨簿公式/格式/命名范围、插入引用调整、高级公式重算 | 受控小图差分；引擎函数存在不等于等价，未测函数不得进入成功任务依赖 |
| U5 | 组织策略/shared-drive/继承ACL、索引延迟、并发权限和配额 | 专用身份矩阵与时钟/竞争样例；DRIVE_FOLDER_ID不当ACL；阶段profile说明近似 |
| U6 | 可用完整真实调用轨迹 | 本仓库扫描未找到；从未声明A1/A2/benchmark验证 |
| C1 | 公共架构统一原子提交可能抹掉多API部分成功 | 已反馈统筹：S:445-484、734-770、880-930；本报告按API事务边界设计，create folder回显缺陷独立验收 |
| C2 | 公共试点若将公式全部后移，易只验证字符串CRUD | 已反馈首轮纳入小型本地公式/三视图/RAW对照；完整公式仍分期，LLM主要评估预生成 |
| C3 | Forms/Sheets共享Drive与linkedSheetId | 已对读Forms报告：身份/ACL共享，Form发布/响应与Sheet计算各自独立；关联同步须额外实现与验证 |
| SH-01 | 非原作者 `/root/snowflake` 于 2026-09-10 完成只读交叉审查，模型 `gpt-6-astra / xhigh`，未发现实质修订问题 | 原作者同日接受结论，仅更新首页和本节；U1–U6 完整保留，正文推荐无需修订；统筹维护的[review-ledger SH-01](../review-ledger.md)记录审查来源，最终闭环由统筹确认 |

SH-01 核证范围与接受依据：

- **版本、全量接口与入口**：重核固定 0.4.1 server hash、15 个工具的签名/handler/API 映射与捕错、1 个资源模板、安装/config、全部 11 个声明任务和 Drive-X 链；MCP SDK 1.9.0 的二维列表展开、普通 error dict 与 ToolError 分层、资源缺 `get_lifespan_context` 均与第 1–2 节证据一致。
- **状态与组件边界**：确认 create→move、copy→rename、share 逐人提交的部分成功语义，以及 HyperFormula 固定提交的 known-limitations/Google 兼容差异、Drive 同文件权限并发限制；第 3–6 节没有将这些行为压成统一原子 CRUD。
- **LLM、合成与验证**：三条路线的职责、状态检索/外部校验、成本与回放分析完整；独立公式/ACL oracle、未见调用组合和 Sheets+Drive 主试点相互一致。原作者已对读最新 shared.md；新增 W&B wrapper/SDK 进程隔离约束不改变 Sheets 推荐。

此次接受的是文档与源码证据审查结论，不能据此宣称模拟器已实现、已通过真实服务差分或达到运行高保真；实际镜像、账号策略、公式边界和运行轨迹仍按 U1–U6 待确认。

本次已完成的检查仅为源码/发布包hash/清单与文档结构核对；上文所有运行实验、兼容profile和实现路线均未实施。

## 10. 能力矩阵行

```csv
object,tool_or_capability,version,operation_type,state_dependencies,proposed_method,llm_role,fidelity_gap,verification_method,priority,evidence
google_sheet,get_sheet_data,mcp-google-sheets 0.4.1,R,Spreadsheet Sheet Cell ACL Format,shared Sheets HTTP core plus fixed MCP,offline seed content,full GridData omission and computed metadata need differential,grid and ValueRange cross-entry golden,P0,S:125-157; CellData v4 2026-09-10
google_sheet,get_sheet_formulas,mcp-google-sheets 0.4.1,R,formula input and cell value,formula state plus SDK-specific serialization,none,SDK1.5 and1.9 recursively flatten lists; deployed SDK unknown,raw MCP and harness snapshot plus formula oracle,P0,S:159-192; K:fastmcp/server.py:872-891
google_sheet,update_cells and batch_update_cells,mcp-google-sheets 0.4.1,W/E,typed grid locale ACL formula dependencies,deterministic USER_ENTERED and atomic values API,none,locale parsing and overlapping range counts need differential,RAW versus USER_ENTERED and null empty negative cases,P0,S:194-272; Sheets ValueInputOption
google_sheet,add_rows and add_columns,mcp-google-sheets 0.4.1,W,grid dimensions format and references,deterministic insertDimension,none,reference and inherited format edge cases,index boundary and shift invariants,P0,S:275-388
google_sheet,list_sheets and rename_sheet,mcp-google-sheets 0.4.1,R/W,stable sheetId title index and formulas,deterministic metadata operations,none,rename argument is spreadsheet; missing tab is ordinary error dict,stable ID and name collision differential,P0,S:391-410;487-538
google_sheet,copy_sheet,mcp-google-sheets 0.4.1,W,source grid target ACL titles and formula graph,copyTo then separate rename transaction,none,copy survives rename failure; cross-workbook formula semantics,partial failure and independent source target writes,P0,S:413-484
google_sheet,get_multiple_sheet_data,mcp-google-sheets 0.4.1,R,multiple files ranges ACL,independent values reads with per-item errors,none,not atomic batchGet; extra query keys preserved,mixed success errors and cross-tool views,P0,S:541-586
google_sheet,get_multiple_spreadsheet_summary,mcp-google-sheets 0.4.1,R,metadata and first rows per tab,deterministic projection and nested errors,none,rows clamp to1; A1:N and titles need real samples,headers first_rows and repeated reads,P0,S:589-675
google_sheet,create_spreadsheet and create_sheet,mcp-google-sheets 0.4.1,W,Drive file parent owner and sheets,shared state with API-specific commits,none,folder move failure still reports configured folder,independent Drive parents and created IDs oracle,P0,S:712-817
google_sheet,list_spreadsheets,mcp-google-sheets 0.4.1,R,Drive query ACL modifiedTime,Drive query projection first-page compatibility,none,no pagination token no trashed filter no root restriction,M first page versus X pagination and trashed cases,P0,S:820-851; Drive files.list v3
google_sheet,share_spreadsheet,mcp-google-sheets 0.4.1,A/W,Drive permissions principals notification outbox,per-recipient permission commits,none,partial success and same-file concurrency behavior,ACL oracle and reader writer tests,P0,S:854-930; Drive permissions.create v3
google_sheet,spreadsheet info resource template,mcp-google-sheets 0.4.1,R,spreadsheet metadata and FastMCP context,versioned resource compatibility profile,none,get_lifespan_context absent in verified SDK1.5 and1.9,resource list MIME and error protocol snapshot,P0,S:678-709; K:fastmcp/server.py:295-318
google_sheet,Drive and SDK HTTP initialization evaluation,Sheets v4 Drive v3 gspread6.2.1,X R/W/A,file IDs parents ACL and grid,common HTTP state plus client transport adapters,none,gspread padding numericise and RAW defaults differ from M,preprocess-equivalent state plans and cross-entry oracle,P0,utils/app_specific/googlesheet/drive_helper.py:10-150; gspread worksheet.py:474-610
google_sheet,local formulas and formatted values,Sheets v4 dated 2026-09-10,E,formula graph locale timeZone number formats,validated HyperFormula3.4.0 subset plus Google adapters,offline business data only,engine is not full Google compatibility,independent hand-calculated cases and controlled Sheets differential,P0,HyperFormula af2d59dc61ec1434498c7233d06e77370e7235b8; Sheets CellData
google_sheet,advanced formulas formats protected ranges and shared drives,Sheets v4 Drive v3 dated 2026-09-10,E/W/A,arrays external references format rules permissions,staged deterministic engines and state rules,none,dynamic arrays external functions and tenant policy gaps,per-family semantic profile and holdout differential,P1-P2,S:149-157; Sheets CellData; HyperFormula known-limitations.md
google_sheet,multi-episode synthesis and replay,design only,management,namespace snapshots clock event log and blobs,isolated shared service and versioned logs,offline seeded content proposals,distribution latency and throughput unmeasured,mutation isolation recovery and effective-trajectory cost,P0,sections3-8; shared.md; validation-plan.md
```
