# google_forms 高保真模拟可行性与设计

> 领域作者：`/root/google_forms`；非原作者交叉审查：`/root/github`，审查与原作者修订日期均为 2026-09-10，具体处置见 §9。领域分析、审查和本轮修订均使用 `gpt-6-astra / xhigh`，由统筹确认。查阅日期：2026-09-10。仓库 HEAD：`ef7ab5928062defc0dc2a91a4c26ddebccb1a6a7`，同时核对当前工作树。已读原始需求、`shared.md`、`service-template.md`、`docs/mcp-analysis.md`；祖先目录及相关目录未找到适用 AGENTS.md。本文只做源码/公开资料分析与设计，没有导入配置、运行 MCP、初始化业务、执行 benchmark 或真实服务写入。
>
> F = 已核实事实；D = 尚未实现的设计；A = 规划假设；U = 待确认。M/B/X、I/S/C/T/D/P 采用 [共享定义](../shared.md)。主结论：**五工具接口与基础表单状态适合代码实现，内容生成适合离线 LLM；Forms、Drive、响应提交必须共享状态。浏览器页面、版本化发布默认值和高级题目行为是主要缺口。**

## 1. 范围、版本与入口

### 1.1 固定版本与证据边界

F：仓库使用第三方 `matteoantoci/google-forms-mcp`，不是 Google 官方 MCP；其后端是官方 Forms API v1。配置通过 Node/stdio 启动，传入三个 OAuth 环境变量；工具列表缓存，客户端超时 20 秒，没有只读、工具过滤或 endpoint 开关。见 `configs/mcp_servers/google_forms.yaml:1-16`。安装脚本固定提交 `96f7fa1ff02b8130105ddc6d98796f3b49c1c574`，随后执行 `npm install`、build、`npm audit fix`，所以固定仓库提交不等于已核实镜像依赖树；见 `global_preparation/install_env.sh:238-245`。

本次参考目录为 `/tmp/toolathlon-mcp-audit-xmv3srz8/google-forms`，manifest 下载来源为该提交的 [GitHub archive](https://codeload.github.com/matteoantoci/google-forms-mcp/tar.gz/96f7fa1ff02b8130105ddc6d98796f3b49c1c574)。已只读下载固定 raw 文件逐字节比较，以下三项全部一致；没有执行源码：

| 文件 | SHA-256 | 版本事实 |
|---|---|---|
| `src/index.ts` | `c93d0e360041daf42987173d45d8eb5f06a5ed8bba5ed576601e36abcd631a9e` | 服务自报 `google-forms-mcp / 0.1.0`；注册完整五工具 |
| `package.json` | `bc3c0c4741cbcd4ceb43a0123d2231add3c6cd860437e6b1672dd949242b1ffe` | 包版本 `0.1.0`；依赖含范围约束 |
| `package-lock.json` | `41b490e0565c7f1999923f61b127c87645874280e6c0ee5875e0df6f4212d9b4` | MCP SDK `1.6.1`；googleapis `126.0.1`；google-auth-library `9.15.1` |

下文 `G:<行号>` 均指固定提交的 [src/index.ts](https://github.com/matteoantoci/google-forms-mcp/blob/96f7fa1ff02b8130105ddc6d98796f3b49c1c574/src/index.ts)，对应本地参考文件同一行号。锁文件证据为 [package-lock.json:25-45、868-917](https://github.com/matteoantoci/google-forms-mcp/blob/96f7fa1ff02b8130105ddc6d98796f3b49c1c574/package-lock.json#L868)。本机没有 `local_servers/google-forms-mcp` 可供核实；实际容器构建产物、握手协议版本、依赖更新和租户行为仍为 U。固定 SDK 类型定义也不能锁住远程 API 的新增响应字段。

### 1.2 M/B/X 边界

| 层 | 确认或设计范围 | 不应混淆的边界 |
|---|---|---|
| M（F） | `create_form`、`add_text_question`、`add_multiple_choice_question`、`get_form`、`get_form_responses`，完整清单见第 2 节 | 没有改题/删题/删表单、列出或搜索表单、发布、权限管理、提交回答、回答分页参数；不能新增这些 MCP 工具假称兼容 |
| B（F/D） | 表单、排序 Item/Question、回答及题目 ID、Drive 文件身份、ACL、发布与接收回答状态、版本和可见时间；读取既有表单会看到超过两种可创建题型的内容 | “M 只能新增短文本和 RADIO”不意味着 `get_form` 只需返回这两种题型 |
| X（F） | Python `googleapiclient` Forms/Drive；OAuth 文件读取与刷新；浏览器填写；HTML GET 和短链接 HEAD | 替换 MCP 进程不会自动替换这些路径；CLI/Apps Script 未发现当前任务调用，不自动实现完整平台 |
| X（D，扩展 profile） | Forms 六种 batchUpdate 子请求、响应 get/list/filter/page；Drive 文件查询/改名/权限/删除；发布 API；本地表单页面与提交 | 用于合理的新组合与状态维护；只在明确提供该 SDK/HTTP/浏览器入口时可调用，不能让五工具 MCP 获得隐形能力 |

F：当前全部显式声明 `google_forms` 的 finalpool 成员只有 `woocommerce-customer-survey`、`woocommerce-product-recall`（各自 `task_config.json:2-7`）。另有不声明此 MCP 的 `fillout-online-forms`，通过浏览器和初始化/评测依赖 Forms；它不是第三个 M 声明任务。

| 任务/公共路径 | 初始化与 agent 入口 | 评测/其他入口及共享要求 |
|---|---|---|
| `woocommerce-customer-survey` | 清理匹配名称的 Forms；agent 使用五工具构造问卷、发送邮件并保存 Drive URL | `evaluation/main.py:252-305` 经 Drive `files.get(fields=id,name,mimeType,createdTime,modifiedTime,owners,webViewLink)` 再 Forms get；`407-488` 另一路 Forms get；`491-528` 公网页面 HTML fallback；`docs/task.md:1-3` 明确 Drive 链接交付 |
| `woocommerce-product-recall` | 可选清理表单；agent 按模板创建题目并发送链接 | `evaluation/check_remote_recall.py:214-269` 读取本地 form_id/URL，短链用 `requests.head(...allow_redirects=True)`；`452-543` 用带认证的 Forms get 验证 ID 和模板，不再用 HTML 可达性代替存在性 |
| `fillout-online-forms` | `preprocess/main.py:18-31,33-259,269-289` 通过 Forms create 和一次 11 项 batchUpdate 建表，题型含文本、RADIO、CHECKBOX、date；agent 通过 `playwright_with_chunk` 填写（`task_config.json:2-6`、`docs/task.md:1`） | `evaluation/main.py:23-48,60-105,127-131` 从文件建 OAuth client，可能刷新并回写 token；Forms get 建 questionId→题名映射，responses.list 取回答；注释提到提交后可见性延迟，但没有本次运行测量 |
| 公共清理 | `utils/app_specific/google_form/ops.py:24-45` 读 OAuth JSON 并 build Drive v3；`48-72` 按 `name contains`、MIME 查询并翻页 | `95-116` 对每个结果执行 `files.delete`；这是实际删除入口，不是 Forms MCP 工具；缺失 pattern 时扫描全部 Forms，episode 隔离必须约束其可见命名空间 |

U：在仓库可见文件、上述三任务及常见 `dump/trajectory/messages/agent log` 文件名范围未找到可核实的完整 Forms 调用轨迹；没有打开业务凭据或以 groundtruth 充当调用证据。题目/输出约束是任务需求，不能据此断言每个 M 工具都在历史运行中调用过。本次精确工具清单来自固定注册源码。

### 1.3 认证、公网与时间版本

F：M 从 `GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN` 建 OAuth2 client，缺任一项启动即报错；client 只预置 refresh token，Forms API client 在构造时绑定（G:14-54）。X 多数读取 `configs/google_credentials.json` 六字段，公共 helper 可触发 refresh（`utils/app_specific/google_oauth/ops.py:6-14`）。本次只读代码，不读取凭据值。是否同一 principal 必须由 episode 身份映射明确保证；recall 评测注释“same OAuth account”不是账号相等的运行证明。

F：表单体读取、写入、回答读取所需 scope 不同；`forms.body.readonly` 不等于 `forms.responses.readonly`，有效 scope 也不自动赋予对象 ACL。分别见官方 [forms.get](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/get)、[forms.create](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/create)、[responses.list](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms.responses/list)。上游辅助授权脚本请求 `.../auth/forms` 与 `.../auth/drive`（固定 `src/get-refresh-token.ts:28-32`）；它不在 YAML 启动路径，不据其字符串推定本次实际授权成功。

F/U：官方 [迁移公告](https://developers.google.com/workspace/forms/api/guides/api-changes-to-google-forms)（页面更新 2026-07-22，查阅 2026-09-10）说明，2026-06-30 后 API 新建表单默认未发布；旧 [create 参考页](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/create)（页面更新 2025-04-08）仍描述省略 `unpublished` 为已发布。D：后端 profile 记录 API 行为日期和创建政策，以新公告设计当前默认值，保留有证据的历史 profile；真实租户 rollout 待受控验证。**创建成功、编辑者可读、已发布、接受回答、回答者有权限是不同状态。** recall 注释（`check_remote_recall.py:459-465`）的“private to creator”不能替代这些维度；不能为了让旧任务可解而悄悄发布。

真实业务与 OAuth refresh 需要公网 Google；安装 npm 需要下载网络；agent 模型 API 另计。D：本地模拟业务后端、页面、token 仿真均可无需公网，镜像预置依赖；远程仿真 LLM 或下载外部图片单列公网需求。只将 `forms.googleapis.com` 改地址仍会遗漏 Drive、OAuth 和 `docs.google.com/forms.gle`。

## 2. 工具与能力清单

### 2.1 全量 M 契约

F：五工具始终静态可见，无权限相关隐藏列表。表中说明为忠实中文概述，原始英文描述及字段描述的逐字契约见对应 G 行；未来契约快照应保留原文本，不替换成此报告概述。输入均为 `type:object`，没有 `additionalProperties:false`、长度限制、format、enum 或 schema `default`；以下 `required` 列是 schema 必填，布尔默认值仅写在说明及实现中。不能把“说明默认 false”误录成 JSON Schema 默认关键字。

| 原始工具名 / 模型侧名后缀 | 说明；属性；对象与状态依赖 | 输入与实际校验 | 成功 `content[0].text` 内 JSON；特殊行为 | 证据、现有使用与未来价值 |
|---|---|---|---|---|
| `create_form` / `google_forms_create_form` | 创建新表单；W；principal、Drive 文件、Form | 必填 `title:string`；可选 `description:string`；只检查 JS `!args.title`；空串失败，空白串不被 wrapper 去空白 | `{formId,title,description,responderUri}`；description 回显 `args.description \|\| ''`；URI 自行拼为 `https://docs.google.com/forms/d/{formId}/viewform`，不采用 API 的 responderUri | G:69-86,203-247；两声明任务有创建需求，实际轨迹 U；任意问卷/登记/调查创建 |
| `add_text_question` / `google_forms_add_text_question` | 添加文本题；W，内部先 R；Form/Item/Question/ACL | 必填 `formId:string,questionTitle:string`；可选 `required:boolean`，有效默认 false；只检查两个必填值 truthiness | `{success:true,message,questionTitle,required}`；message 表示文本题添加成功；先 `forms.get`，结果不使用，再 `batchUpdate(createItem)`；`textQuestion:{}`；固定插入 index 0；不回传 itemId/questionId/revision | G:87-108,249-311；两任务可用路径；既有复杂表单增加登记字段、ID 回读 |
| `add_multiple_choice_question` / `google_forms_add_multiple_choice_question` | 添加选择题；W；Form/Item/Question/选项 | 必填 `formId:string,questionTitle:string,options:array<string>`；可选 `required:boolean=false`；wrapper 仅额外检查 Array.isArray，没有检查非空/元素类型/重复值 | `{success:true,message,questionTitle,options,required}`；message 表示选择题添加成功；`choiceQuestion.type='RADIO'`、options 映射 `{value}`，index 0；没有 CHECKBOX/多选参数，不先 GET | G:109-137,313-379；两任务可用路径；任意单选调查，错误后修正选项 |
| `get_form` / `google_forms_get_form` | 读取完整表单；R；Form 与 principal 的可见状态 | 必填 `formId:string`；只检查 truthiness；不接收 URL 解析、fields、revision 参数 | 完整 `response.data`，典型 `formId,info,settings,items,revisionId,responderUri,linkedSheetId,publishSettings` 按 API 条件出现；不删掉复杂题型/输出字段 | G:138-151,381-406；两任务的读回核验有价值，X 有确切同类调用；未来表单审计、题型推理、版本比较 |
| `get_form_responses` / `google_forms_get_form_responses` | 读取回答列表；R；Response、题目 ID、回答读取权限 | 必填 `formId:string`；只检查 truthiness；没有 filter/pageSize/pageToken | 完整 `response.data`，通常 `{responses:[...],nextPageToken?}`；**只执行一次 list，不翻页**；空列表字段是否省略遵循真实 JSON 记录 | G:152-165,408-433；两声明任务未证实要求此工具；fillout 评测走同类 X 入口；未来反馈统计、增量核验与分页局限识别 |

F：成功都返回一个 `TextContent`，其中 text 是 `JSON.stringify(...,null,2)`；不是顶层 JSON 对象、不是 `structuredContent`，没有显式 MIME、annotations、resource link 或 tool outputSchema。工具增题输出是确认信息，不能因为不回传题目 ID 就省略持久化 ID。服务只声明 tools capability；没有注册 resources、resource templates、prompts、sampling 或业务 notifications。stdio 和关闭路径见 G:28-39,435-443。

F：所有工具执行异常，包括未知工具抛出的 `McpError(MethodNotFound)`，都会被外层 catch 改成 `{content:[{type:'text',text:'Error: '+error.message}],isError:true}`（G:169-200）。缺参在方法内抛 InvalidParams；后端失败再包 InternalError，消息增加 `Failed to ...` 前缀；McpError.message 的完整前缀格式须以锁定 SDK 实际构造结果核验。**未知工具在此版本也被包成工具错误，不是透传 JSON-RPC MethodNotFound**；这是通用 unknown-tool 建议必须尊重的服务例外。stdio/启动失败则没有成功连接的工具调用结果。

F：wrapper 不完整执行其声明 schema：`options=[]` 在 JS 层通过；非 string 元素和错误类型的 `required` 也可能进入后端，`args.required || false` 不是类型校验。D：分别保存“声明 schema”“wrapper 校验”“后端约束”“harness 参数恢复”；合法输入契约精确复刻，非法输入不能全部改成统一的提前 schema error。真实后端对空选项、重复选项、空标题的具体拒绝码/消息为 U，需参数反例差分。无依据地接受或修正非法输入同样不允许。

F：harness 将服务名和工具名拼接并标准化为上述模型工具名（`utils/openai_agents_monkey_patch/tool_name_aliases.py:21-28,85-99`）；模型看到的是 `content[0].model_dump_json()` 字符串，顶层 `isError` 不单独串行化（`custom_mcp_util.py:176-195`）。因此原始 MCP envelope 和最终模型文本需双层验证；保留普通文本错误，不能只保存 `isError` 而令模型误判成功。

### 2.2 B/X 契约及真实包装缺陷

| 能力 | 后端/额外入口契约与边界 | 设计要求 |
|---|---|---|
| 创建与 description | M 将非空 description 放进 forms.create 的 `info`；官方 create 只允许 title/documentTitle，明确不允许 description 等其他字段 | 保留 M 参数和请求行为；description 能否导致当前服务拒绝、具体错误须差分，不能暗中改成 create→updateFormInfo，也不能把回显 description 当已持久化证据。来源：G:208-235、[create](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/create) |
| 读取丰富结构 | M 读取没有字段过滤，可能得到 section、grid、媒体、paragraph、date/time、scale/rating、quiz、文件题等 | 先覆盖它们的读取表示、ID 与引用；高级创建/浏览器交互可分期，但不可将未知 kind 丢掉或改写成 textQuestion。官方 [Form 模型](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms) |
| 批量修改 | X 的 `POST /v1/forms/{id}:batchUpdate` 含 requests，六种子请求为 updateFormInfo/updateSettings/createItem/moveItem/deleteItem/updateItem；可有 includeFormInResponse 和 writeControl；返回 replies 与请求位置对应 | 支持路径级 updateMask 与按执行顺序解释索引，区分文档标题和表单标题；updateItem 中 item/question ID 若提供且包含于 mask，则采用传入值；ID 为空且包含于 mask，则生成新 ID；未纳入 mask 的 ID 不因其他字段更新而重设。requiredRevisionId 过期返回 400；targetRevisionId 是合并语义。批量失败原子性、create 末尾索引边界及改 ID 后历史回答表现列为 U，不从 Sheets 推断。官方 [batchUpdate / UpdateItemRequest](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/batchUpdate#UpdateItemRequest)，2026-09-10 复核；此例外只在 B/X，不新增 M 工具 |
| 响应分页 | HTTP list 支持 `pageSize,pageToken,filter`；省略 pageSize 时最多 5000；filter 仅支持 UTC RFC3339 的 timestamp 大于/大于等于；list 中每个 FormResponse 不返回 formId | X 可翻页；M 仅返回第一页与真实 token，不能用额外参数偷偷扩展。分页 token 绑定 form/filter/episode，精确排序及并发翻页边界待记录确认。官方 [responses.list](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms.responses/list) |
| 回答模型 | 回答以 questionId 为键，textAnswers.answers 为 value 字符串数组；CHECKBOX 多值、日期/时间的文本格式、文件答案和 quiz 分数均有专门表示 | 不以题名作主键，不把数值型题答案变成 JSON number；缺答、空串和不存在字段分开。官方 [FormResponse](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms.responses) |
| Drive 与发布 | Forms 在 Drive 中；删除与访问保护经 Drive。发布状态与 published-view responder ACL 分离；X 可用 setPublishSettings 及 Drive permissions，当前 M 均未暴露 | 一份文件身份；reader 的 published view 仅代表回答入口，不能给予编辑/全部回答读取权限。官方 [发布和回答者管理](https://developers.google.com/workspace/forms/api/guides/publish-form)、[setPublishSettings](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/setPublishSettings) |
| 浏览器/HTTP 提交 | 当前 fillout 的 agent 用浏览器；官方 REST responses 资源只有 get/list，没有提交方法。源码扫描未发现固定 `formResponse`/`entry.*` 提交协议实现 | 本地页面的提交必须改变 Response 状态，并提供真实必填/选项/发布/权限约束；Google 未公开的页面 DOM、提交字段和 Cookie 行为是 U，不能宣称实现任意 `POST /v1/forms/{id}/responses` 就兼容 Google。浏览器可用 profile 与原站网络协议 profile 分开 |

## 3. 领域状态模型

D：共享基础设施只负责事务、命名空间、时钟与 blob；Forms 领域负责题型、题目顺序、答案校验和发布语义。一个 episode 内由 Forms/Drive/浏览器/SDK 使用同一权威状态，不靠工具历史文本恢复。

| 持久实体 | 核心字段、关系与不变量 | 可派生内容/注意事项 |
|---|---|---|
| Principal / Grant | episode_id、principal_id、OAuth client、scope 集合、账号类型、过期/撤销状态；明确区分 editor、reader、responder 和 response-reader 能力 | 按调用主体、scope、文件 ACL、published view 联合决策；不同入口令牌可映射同 principal，但不能默认同厂商账号相同 |
| DriveFile | file_id 与 form_id 一一映射；MIME `application/vnd.google-apps.form`、name、parents、owner、ACL、created/modified 时间、trashed/deleted；共享 Drive 文件域 | documentTitle 从 Drive name 映射，Form info.title 独立；URL 是映射结果而非资源存在证明；Drive `files.delete` 是永久删除，不冒充移入回收站。见官方 [files.delete](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/delete) |
| Form | form_id、info.title/description、settings、ordered item IDs、content_revision、publishSettings/legacy profile、接受回答状态、canonical responder URL/公开 ID、可选 linkedSheetId | 记录 principal 可见的 opaque revision token；token 过期策略、权限/发布更改不强行等同题目 revision；运行日志保存时间政策版本 |
| Item / Question | 内部记录键与对外 itemId/questionId 分开；常规读写保持 ID，X updateItem 可按 mask 合法重设；保留每版 ID、变更事件及前后版本映射；题型 union、required、标题/说明、选项/跳转、位置；group 中多 Question，非题目 Item 无伪造 questionId | 名称可重复，顺序通过列表持久化；M 增题总置首；X 改 ID 后 M get 读取新版本，不将合法 ID 变化判为漂移；ID 不在 mask 时不得自行重分配；Quiz、媒体、文件题的数据表示纳入读路径 |
| Response / Answer | form_id、responseId、first_submit_time、last_submit_time、respondentEmail 可缺、questionId→typed answer、可选 grades/totalScore、提交时题目版本及当时 ID、可见时间 | API JSON 从状态渲染；内部保留原始回答与版本，不把旧 questionId 自动重绑到新 ID，也不要求所有历史答案都引用当前版本题目；改 ID 后对外历史表示为 U；同名人多次提交是不同 response，不套用 finalpool“同名最后一次”评分规则 |
| ResponderSession | page/form/public ID、principal/匿名、已填字段、分支路径、编辑回答凭据的受控模拟标识、提交 nonce、浏览器 locale | 草稿不计入 API responses；重复提交/编辑需区分，nonce 不自动制造真实 API 没有的幂等保证；表单关闭、未发布、ACL 撤销均影响后续合法提交 |
| Media / Upload | blob_id、hash、MIME、大小、文件名、Drive file/folder ID、source URL、ACL；表单媒体与回答附件分开 | get_form/read response 可引用合法 blob；M 没有下载/上传文件工具。官方目前不允许 API 创建 fileUploadQuestion，不应开放虚假成功；预置该题可读，实际浏览器上传分期 |
| Event / Snapshot | committed operation、受影响版本、visibility_at、关联 sheet 投递事件、故障阶段、快照/模型版本 | API 的排序/分页索引是派生索引；恢复时从已提交事务与 outbox 重建，不能重复生成已提交回答 |

D：回答时间用虚拟 UTC instant，日期题值另用题型规定的本地文本，不把生日当成带时区时间戳。Forms 写请求与浏览器提交的事件时间分开；可配置回答索引短暂不可见窗口，范围由后续差分校准。读限流、昂贵回答读取限流、写限流分桶；官方 [配额文档](https://developers.google.com/workspace/forms/api/limits) 区分这些类别并建议 429 后退避，不把当前配额常数固化成所有账号规则。M 文本题增加一次额外 GET，其读失败与配额消耗必须可观察。

D：Forms 与 Drive 删除以一次业务事务使所有入口不可再正常读取；内部审计可保留 tombstone，不能向 agent 暴露已删正文。题目删除或 updateItem 改 ID 后的历史回答形态、表单删除后已关联 Sheet 是否保留历史数据、附件保留策略为 U；先保存原始历史以待正确渲染，不自行改写旧回答或级联删除跨服务资源。linkedSheetId 可先只读复现；若 episode 允许真实“提交→Sheet 新行”，需与 Sheets 作者共同规定投递、列映射和可见延迟，不能伪造两份互不相连的数据。

D：外部 URL 展示可保持真实 URL 形状，通过 episode 网络路由到本地服务；域名、短链、`/d/{formId}` 与 `/d/e/{publicId}` 明确映射。若采用显式 local-origin URL，须列为接口偏差，不能声称保留原样兼容。M create 的拼接 URL 和 get 返回的 canonical responderUri 可以不同，不能强行统一抹去包装行为。

## 4. 代表性交互序列

以下均为 D，超出现有模板固定调用顺序；X 步骤只在声明该入口的 profile 中使用。

1. **置首与稳定 ID**：M create → add_text(A) → add_choice(B) → get → add_text(A 同名) → get。断言顺序 `[A新,B,A旧]`、三个 itemId/questionId 各异，旧回答仍指向旧题；重名不覆盖，success 文本不代替状态核验。
2. **跨入口修改与错误恢复**：X 创建含 RADIO/CHECKBOX/date/grid 的表单 → M get → X batch 更新说明/移动题目 → M get → 带旧 requiredRevisionId 更新失败 → 重读 revision 后合法更新。断言失败不改变观察到的合法状态、M 不降格复杂题型；另以含一个非法子请求的批次验证整批或部分提交的真实策略后锁定 profile。
3. **权限与发布**：主体 A 建表，B 能回答但不能编辑；未发布时 B 提交失败 → A 经 X 发布并授予 published-view reader → B 合法提交 → A 经 M responses 读取 → 撤销回答权限。断言仅发布不赋编辑权，仅拿 URL不授回答权，关闭接收后不能新增 response。
4. **多页响应与时间过滤**：预置超过一页回答及同秒不同 responseId → M responses 看到第一页/token → X list 正确翻页，改 filter 却沿用 token 应失败 → 合法重发过滤请求。断言跨页无凭空记录，边界 `>`/`>=` 不混淆；M 不因调用次数增加而自动切换下一页。
5. **跨工具删除与搜索**：Drive X 用 MIME/name/parents 查询并翻页 → M 按返回 fileId get → Drive 改名 → M get 与 Drive get 对比 → Drive 删除 → M get/responses 与浏览器访问失败。断言文件名改变不必改变可见表单标题；查询与 ACL 一致，删除不影响另一个 episode 同名表单。
6. **回答纠正与题目演化**：浏览器漏必填字段失败 → 更正后提交 → X 变更题名、插入新可选题 → 浏览器新增或使用合法编辑入口修订回答 → M get/responses。断言草稿不入库、createTime 不随编辑重置、lastSubmittedTime 正确变化，历史答案不按最新题名重新猜测；真实编辑/删题历史行为待差分后启用。
7. **跨服务工作流**：M 创建并构建采购调研 → 邮件服务传递 canonical URL → 浏览器提交 → M 读取 → Sheets 写入明确分析汇总；或选择已启用 linkedSheet 投递 profile。断言邮件引用指向同一表单，分析由已提交回答计算，汇总不是模拟器提供的任务答案。
8. **并发与不确定提交**：两个 worker 同时 M add_* → 两次均提交则两题都保留，排序与提交历史一致；注入“已提交但响应丢失”→ agent 重试可能新增重复题。断言不能以参数相同偷偷去重；错误恢复应通过读取当前状态。对不同 form/episode 允许并行，对同 form 操作有可核验序列。
9. **合法 ID 变更与历史边界**：X 建题并提交旧回答 → 仅更新题名且 mask 不含 ID → M get 确认 ID 保留 → X updateItem 在 mask 中提供合法非空新 ID → M get 确认采用新值 → X 在 mask 中置空 ID → M get 确认由服务生成新值。分别覆盖 itemId 与 questionId。独立 checker 依据调用 mask 和各版表单验证 ID 转移，另以真实 X responses 记录核对旧 questionId 的历史表现；不能按题名迁移旧答案，也不能先假定 API 会保留、删除或重写它。最后提交的新回答应能关联当前题目版本；存在旧回答的 ID 变更组合需完成受控差分后启用。

## 5. 候选实现与推荐

D：首选 **Forms 领域规则引擎 + 持久状态 + 固定五工具的有状态 MCP facade + 本地 Forms/Drive HTTP/SDK 与响应页面入口**；M 的名称、schema、调用顺序与 text/error 包装从固定版本做契约对照，规则引擎供所有入口共用。LLM 只作离线内容生成或受限候选实验。备选是保留真实 MCP server，注入本地 backend/client；该路径更利于包装保真，须先解决认证、不可配置 endpoint 与 X 入口路由。

下表是设计比较，非性能实测；I 接口、S 状态、C 一致性、T 身份时间、D 数据分布、P 性能分别判断。

| 路线 | I / S / C / T / D / P 可达边界 | 开发、运行与维护代价 |
|---|---|---|
| 保留真实 MCP，替换后端 | I 最易贴近固定 wrapper；S/C/T 仍由本地后端决定；D 可丰富；P 受 stdio/JS 层少量固定开销 | 五工具无需重写；但 G:41-54 无 endpoint 参数，不能仅设环境变量声称离线。后续需显式 client/transport 注入补丁，或受控代理+本地证书+OAuth 路由；还要接 Python/浏览器。固定并审计适配层，不能修改题目业务逻辑 |
| 有状态 MCP facade + 规则核心（首选） | I 可通过完整固定快照精确；S/C/T 在明示 profile 内可精确；D 由 seed/内容库补足；P 容易分片 | 五工具表面很小，需复现包装缺陷而非顺手修复；后端和 X 开发占主体。维护时分别 diff upstream wrapper 与 API 行为政策 |
| 本地 Forms/Drive HTTP | I 支持真实 HTTP 请求/响应及 Google 风格错误；S/C 统一；T 可建模但 OAuth/TLS 细节分期；D/P 可控 | 实现 Forms create/get/batch/list、Drive q/fields/page 与 auth adapter；SDK discovery 必须固定在本地，不能仅替换数据 URL。浏览器页面另做，不能直接用 JSON 页面冒充 |
| Python/Node SDK client 适配 | I 对被拦截 SDK 路径可准确，任意 HTTP/浏览器不自动覆盖；S/C 若共核心可一致 | 低于完整 OAuth/网络仿真成本；需准确保留 `.execute()`、`response.data`、HttpError/gaxios error、refresh 行为；不同 SDK 方法遗漏易形成漏网公网路径 |
| Formbricks 自托管复用 | 原生是其 Survey/Response 模型，非 Google Forms I；基础问卷内容可复用；S/C/T 需要桥接；D 丰富；P 多一层成本 | 官方证实有 Docker 自托管，以及 `/api/v1/management/surveys`（API key）、`/api/v1/client/{environmentId}/responses`（surveyId/data/finished）。没有证据支持 Google forms ID/Drive ACL/revision/batchUpdate 或 Google DOM 兼容；不能直接替代。当前在线 v1 文档，未固定部署镜像，不推荐首轮引入 |
| WireMock scenarios / 静态 fixture / 回放 | I 对已有 HTTP 样本准确；S 只对预定义有限状态有效；任意组合 C/T 不足；D 有限；P 好 | 官方 scenarios 提供命名状态机和 reset；适合错误包装、OAuth失败、故障注入、固定记录回归，不承担任意表单/回答状态和答案生成 |
| LLM 主导 + 显式状态校验 | I 仍需 deterministic renderer；S/C/T 受 validator 覆盖限制；D 强；P 低且有模型配额风险 | 初样例快，长期约束/排错并不比代码小；每调用成本增加，精确 Forms 操作缺少需要模型判断的服务语义 |
| 混合 | 代码决定所有业务变更和读取；LLM 初始化业务文本；I/S/C/T 同规则核心；D 可提高；P 大部分调用无模型开销 | 一次内容生成可被多次合法采样/变体使用；需要内容/约束/泄题审查。作为首选内容层，不让 LLM 发明 API 行为 |

候选核验：查阅 2026-09-10，Formbricks 官方 [Docker 自托管](https://formbricks.com/docs/self-hosting/setup/docker)、[Create Survey v1](https://formbricks.com/docs/api-reference/management-api--survey/create-survey)、[Create Response v1](https://formbricks.com/docs/api-reference/client-api--response/create-response)；WireMock 官方 [Stateful Behaviour](https://wiremock.org/docs/stateful-behaviour/)。这些材料证实各自实际接口，并不证实任何 Google 兼容层。状态存储可用现有事务数据库/SQLite 分 episode 文件，但数据库只是存储，不自带 Forms 语义；本文不宣称任何现成产品完成兼容。

## 6. 保真缺口与取舍

| 能力/差异 | 目标级别与边界 | 若简化会训练出什么错误规律 | 验证/处理 |
|---|---|---|---|
| 五工具 schema、包装、固定 index 0 | I 可依据源码准确；SDK 构造错误文本细节 U | 按调用顺序尾插、把增题 success 当新增 ID、误用未暴露参数 | 固定 schema 双快照；显式列置首序列；禁止 facade 增加工具 |
| M create description、拼接 URL | 请求构造可精确；服务当前拒绝行为/链接重定向 U | 以为 create 能可靠写 description、以为任意拼接链接都可提交 | 记录 wrapper 与 API 差异；未来受控 create 参数矩阵；读取状态验证 |
| ID 可追溯性、合法重设与引用 | 常规读写及 updateItem 的 mask 规则可准确设计；改 ID 后历史回答 U | 题名可作唯一标识、所有 ID 变化都非法、旧答案自动转到新 ID | 独立检查未含 ID/非空 ID/空 ID 三类 mask；按版本核引用；历史回答单独差分 |
| 高级题型与媒体 | M 读取表示优先精确；高级写/UI、文件上传与 grading 分期 | get 永远只有两种题型；文件题答案是普通文本；错误精确计算 | rich seeded Forms/Responses；每种 union 分支契约与独立 oracle；不支持写必须显式失败 |
| 发布、身份、scope | 当前公告+版本政策；租户/legacy/组织策略 U | 创建就公开、能填等于能读全部答案、只换 scope 字符串就获权限 | 三维权限矩阵和 API date profile；授权真实账号分别采样；不能因 finalpool 可解而免权限 |
| 分页/filter/Drive 查询 | X 的语法与索引可实现；未明确排序/并发页一致性 U | 多次 M 调用自动翻页、空返回代表确无资源、任意字符串搜索成功 | 查询 AST 与结果投影独立；重复页、非法 token、q 转义、fields omission；保留首屏局限 |
| 批量原子性/并发合并 | 代码保证已声明策略；真实批量失败与 targetRevisionId 合并分期/U | 无效子请求被部分接受或静默忽略、所有冲突都返回 409 | 先差分确定批量事务语义；targetRevisionId 未实现时显式拒绝，不能等同 CAS |
| 浏览器 DOM 与提交流程 | 页面功能近似；高保真 Google DOM/网络需受控记录 | 学到模拟器专属 DOM、伪造 submit endpoint、登录/上传永远略过 | DOM/无障碍树与请求快照差分；分别报告业务成功率与真实页面迁移差异 |
| 429/可见延迟/不确定提交 | 配置可复現，延迟分布近似；真实分布 U | 重试不会重复写、提交必定立即可见、无限查询不耗配额 | 区分 commit 前后故障；可见时钟/outbox；记录观察时间与提交时间 |
| linkedSheet、附件生命周期 | 字段与引用读取优先；跨服务自动投递/保留策略分期 | Form/Sheet 两份数据可不一致、删 Form 一定删 Sheet | 明示 linked/unlinked profile；跨服务合约；不虚构同步/级联行为 |

D：如果已知 M 调用落入尚未实现的语义，沿该工具真实 `isError + text` 外壳返回清晰的不支持错误，注明模拟器扩展错误的身份；不要返回空成功结果。当前 M 完整五工具不能以“本任务不用”删减；未暴露 B 功能可以保持只读/预置或分期，但不能为已支持组合提供矛盾状态。

## 7. LLM 仿真可行性

### 7.1 职责与路线选择

D：**推荐代码主导业务、LLM 离线丰富数据的混合方案。** Forms 的五个 M 操作都属于精确结构读写，没有类似自然语言搜索排序的服务内推断；LLM 生成的工具解释不是 Google API 的真实功能。

| 工作 | LLM 适用性与可决定内容 | 必须由外部组件决定 |
|---|---|---|
| 多样初始问卷、说明、选项、历史反馈 | 适合；生成跨行业/语言/语气、合理不一致反馈、近似名称和噪声文本 | schema、题型合法组合、唯一/稳定 ID、选项/答案对应、时间/ACL、是否可解 |
| 已有 get_form / responses | 不适合主导；最多做离线内容风格生成后落库，运行时读真值 | 完整资源查询、字段投影、分页、缺失/无权、答案值与分数；不得实时补全缺失答案 |
| create/add/batch/delete/ACL | LLM 主导仅作为对照提案器；可尝试从调用生成受限变更集 | 参数/权限/题型/引用/版本/索引/原子性验证，ID 分配与状态提交；不允许猜测不存在的 form |
| 浏览器对话/错误内容 | 服务确实提供的固定帮助可用模板；离线本地化候选可由 LLM 提出 | 页面状态与验证错误必须对应实际字段，不能提示 agent 任务答案或暗中修正输入 |
| Quiz 精确打分、统计、日期与选项 | 不适合作为运行时权威 | 确定性计算及独立规则；主观题评分如未来有明确服务支持再另设人工/模型近似 profile |

LLM 主导路线也必须显式保存全部状态。D：先以 `(episode,principal,formId)` 检索完整相关 Form/ACL/题目索引和请求所需 Response 页，负查询也执行真实索引查询；大表单以结构化工具分页获取，blob 只读引用，摘要不作为真值。给提案模型输入调用及必要状态，不给任务答案、评分目标或成功轨迹。自然语言业务数据按不可信数据隔离，不能更改仿真规则。

D：提案输出限制为 `{expectedVersion,operations,claimedResponse}`，规则层校验调用明确提供的 ID，并按缺省或 updateItem 的空 ID/mask 规则生成 ID；模型不能自行重分配既有 ID。外部校验 schema/权限/题型 union/引用/顺序/时间和必填值，在一个事务中提交。响应从提交态由固定 renderer 生成并与 claimedResponse 比较，模型不能独立决定最终读结果。版本冲突重读；校验失败最多一次修复，仍失败则不提交并返回明示仿真器内部失败，不伪装真实服务错误。日志区分“Google 风格业务拒绝”和“模型提案校验失败”，后者不能不加标注进入训练。

D：读取不能凭需求补资源，写入不能自动改错误 options/发布/ACL、不能补 agent 漏填字段；模型内容只可来自初始化或明确合法业务创建。并发提交由数据库隔离，写后跨入口读依据同一 committed state；中断恢复重放已提交事务，不再次调用 LLM。记录模型和提示版本、相关输入状态 hash、模型原始输出、校验结果、最终变更和提交序号；固定温度不等于可复现，以记录回放及状态 hash 为标准。

### 7.2 成本、延迟与质量对照

A（规划，非测量或厂商报价）：代码路径每工具调用 0 次仿真模型调用；混合内容层每 episode 1–3 次批量生成（输入约 2k–8k token，输出约 2k–10k），后续 30–100 次工具访问摊薄；LLM 主导每工具 1 次提案，校验修复率记为 `r`，均值 `1+r` 次，规划 `r=0.05–0.2`，初始每次输入 2k–12k、输出 0.3k–2k token。大表单/回答会超过此范围，必须实测检索后 token 分布，不能默认装入上下文。

设输入/输出模型费率为 `p_in/p_out`（每百万 token），则百万工具调用的额外模型成本约为 `(1+r) × (T_in×p_in + T_out×p_out)`，另加状态检索、校验和失败重试成本。示例仅作算术：`T_in=6000,T_out=800,r=0.1` 时，费用为 `6600×p_in+880×p_out`，不填当前价格。混合路径按每 episode 生成费除以该 episode 有效轨迹调用数；重用内容应按不同 seed/关系扰动，不能让同名模板泄露答案。

A：若每次模型调用 1–10 秒，LLM 主导额外均值约 `(1+r)×1–10 秒` 加检索/提交，最差重试会接近或超出当前 20 秒 MCP timeout；代码本地路径预期更低但须用 p50/p95/p99 和长响应实测。目标吞吐 `Q` 次工具/秒的模型并发近似 `Q×(1+r)×模型平均耗时`，再看 token rate 限制。确定性读取快速路径、预生成文本、缓存不可变内容 hash、稳定规则迁移到代码可降成本；不同模型只影响内容生成候选，不降低规则校验。

D：对照试点用相同 hidden seeds 和未见顺序，比较 A 纯代码+模板，B 代码+LLM 离线内容，C LLM 变更提案+同一外部校验器。评测器由另一套状态查询/不变量检查实现，不由同一个仿真 LLM 自评。必报：重复读不一致率、跨入口差异率、长序列 state drift、非法操作接受率、资源/字段幻觉、静默修复率、成功偏置、答案泄露、拒绝正确调用率、有效轨迹/总成本与延迟分位。预计 C 在此服务难以抵偿精确规则成本，是可证伪判断；B 的价值主要在数据多样性和真实业务风格，应通过盲审和真实迁移对照衡量。

## 8. 合成、验证与分期

### 8.1 可解任务与规模设计

D：seed 控制形式结构与关系，LLM 内容记录作为额外固定输入。变化表单 0/1/多份、同名/近名、题目长度/语言/顺序、空选项反例、optional/required、复杂题型、历史 revision、空/部分/多页回答、匿名/实名、共享权限和发布历史。姓名不唯一，反馈可重复，文件名不携带“正确答案”；任务约束从环境的合法目标采样，也可反向生成满足约束的状态，生成后用独立可解性检查确认至少一个可用入口序列。

D：任务生成器选择业务目标，模拟器只执行服务语义，评测器检查最终状态和权限下可观测结果；三者不共享答案生成逻辑。评分可要求“题目集合/顺序满足约束”“所有合法回答在截止时刻提交”“指定主体无越权”，允许多种添加顺序和先读后写路径。若仅提供 M 且当前新建默认未发布，不能生成要求创建后对外填写且无发布路径的任务；可以预置已发布目标或在任务接口中明确加入 X 发布权限。

D：每 episode 独立 tenant/schema 或数据库文件，principal/file/publicId/pageToken/浏览器 session 均绑定 episode；资源对外 ID 保持不透明，不把 namespace 泄露成解题线索。按 form 分区串行提交，跨 form/episode 并行；快照包含时钟、随机状态、ACL、blob manifest、事件队列与模型生成内容。克隆只读初态后写入隔离 overlay；重置切换快照，恢复按已提交日志推进，不能复用别的 episode token 或 nonce。吞吐重点测大表单 JSON 序列化、5000 响应页、Drive 查询索引、页面并发与 outbox，不只测空 form get。

### 8.2 验证设计与后续门槛

| 检查 | 独立 oracle / 方法 | 已有证据能做什么；未来条件 |
|---|---|---|
| 契约 | 静态提取完整五工具 schema/description，核对模型 alias；原始 MCP 和 harness text 双快照 | 当前可依据固定源码设计；真实 SDK 运行快照尚未采集，后续使用无业务写入的本地 client stub |
| 参数与错误 | 缺参、null、空字符串/数组、错误类型、额外字段、未知工具、401/403/404/429/5xx | wrapper 路径来自源码；Google 错误消息/状态对应关系需合法受控账号和记录，禁止猜测统一成功/统一 404 |
| 状态机与组合 | 第 4 节全序列；独立遍历实体关系和提交日志；随机交换可交换操作 | 不用 facade success 判断；覆盖未见题目类型/顺序、重名、删除、跨入口 |
| SDK/HTTP/浏览器一致性 | SDK 创建→M get→页面提交→X responses→Drive 删除；网络记录全部 endpoint | 不运行现有清理/初始化；未来独立测试项目/账号及隔离路由，屏蔽未声明真实外联 |
| 批量/时间/并发 | 无效子项位置排列、revision 过期、响应可见窗口、commit 后丢包、并发历史合法性 | 批量原子性/索引边界/targetRevisionId 要受控差分；不得借别的 Google API 结论代填 |
| updateItem ID 与历史回答 | 独立读取请求 mask 和每版 Form，分别验证 ID 未纳入/传入非空/置空生成；再比较更新前后 Response 原始 questionId 及提交版本 | 新 ID 转移按官方定义核验；旧回答保留/省略/改写等对外行为未确认，需受控差分，不以同一 ID 映射器同时执行和评分 |
| 数据/LLM | 多 seed 分层覆盖；冻结模型记录；独立规则+盲审+答案泄露探针 | 同模型自评分不能验收；B/C 与 A 对照按有效轨迹成本比较 |
| 复现/隔离 | 同日志回放状态 hash、克隆/reset、崩溃点恢复、跨 episode ID/token 请求 | 目标：零跨 episode 泄漏、零已提交状态丢失；性能数字后续测量 |

D：真实服务差分只在后续另获授权的测试账号/项目中进行。本阶段不执行。动态 form/item/question/response ID 用一一对应映射比较引用图，不能简单删除所有 ID 字段；updateItem 合法重设时，按版本和变更事件建立映射，不强制整段轨迹只有一套不变 ID。旧回答映射与当前题目映射分别验证，不利用新 ID 映射掩盖历史差异。时间比较相对关系与格式/精度，revision 按 opaque identity/冲突行为比较；数组顺序在有语义时严格比较，未保证的排序先记录再建立 comparator。错误文本保留稳定前缀、状态码和字段定位，动态 request IDs 单独归一化。浏览器页面比较无障碍树/操作结果/网络约束，不把像素相似当业务一致性。

D：建议分期按迁移价值推进：

- **P0 契约与完整 M 核心**：五工具、JS 包装差异、全部可读 Form/Response schema 家族、稳定 ID/顺序、scope/ACL/发布状态、Drive file 映射、跨入口基础 get/create/batch/list/delete、可控时间错误；先确认 description 与发布默认值。首轮试点至少含新增置首→跨入口读→无权失败→合法恢复→Response 读→删除核验。
- **P1 广义组合与响应入口**：Forms 六种 batch 子请求、FieldMask/CAS，明确包含 updateItem 按 mask 保留/采用/重新生成 itemId 与 questionId；Drive q/fields/分页/改名与 published ACL、response filter/page；浏览器基础文本/RADIO/CHECKBOX/date 提交、发布/关闭状态、重复提交故障、同名干扰。ID 重设本身纳入契约，含旧回答的组合须先确认历史语义，未确认的组合明示分期限制；题目类型/操作顺序覆盖不能止于现有三任务。
- **P2 高代价语义**：targetRevisionId 合并、高级分支/grid/媒体/文件上传、真实 Google DOM 提交兼容、题目演化后的历史回答、linkedSheet 自动投递。未支持分支须可识别拒绝并在 profile 明示；P0 rich-read 不等于这些写/UI 已兼容。

D：每期验收分别报告 I/S/C/T/D/P。P0/P1 必须完整覆盖其公开 schema、通过全部确定性不变量和负例、组合/跨入口读取无矛盾、无静默成功；支持的真实差分样本无未解释语义差异。扩大并发前完成 reset/恢复/跨 episode 隔离；扩大数据分布前完成未见结构和跨主体任务测试；启用 LLM 提案前要求无资源幻觉与非法接受，失败样本明确隔离。这里的零错误指测试样本，不代表总体零风险。具体样本量、并发梯度和证据等级按 [validation-plan.md](../validation-plan.md) 的 A0–A4、V01–V12、G0–G5；内容生成与 episode 机制按 [synthesis-design.md](../synthesis-design.md)。目标不以 finalpool PASS 数量替代以上门槛。

## 9. 待确认与审查记录

| 编号 | 问题/证据边界 | 后续核验与处理 |
|---|---|---|
| U01 | 运行镜像实际依赖可能受 npm audit fix 影响；本次只核固定源码/锁文件 | 保存镜像 manifest、构建产物 hash、MCP handshake/tools/list，重新跑契约 diff |
| U02 | create(description) 与官方允许字段冲突；wrapper 输出回显不证明 description 持久化 | 后续受控错误/空串/缺省对照；保留原 wrapper，不提前修补业务行为 |
| U03 | 新旧官方文档发布默认值冲突，租户/legacy 行为未测；recall 注释过度概括私有性 | 按 2026-07-22 迁移公告配置当前政策，单独记录历史版本；API/浏览器/ACL 联合差分 |
| U04 | 批量失败事务边界、create/move 索引、空/重复选项、targetRevisionId、response 排序/删题历史 | 需要参数和并发差分；未确定行为不能用 LLM猜测或套用 Sheets 规则 |
| U05 | Google 浏览器 DOM、短链/公开 ID、表单提交与编辑/文件上传协议 | 受控浏览器录制网络和可访问树；声明功能页面近似与原协议兼容的不同 profile |
| U06 | linkedSheet 与附件删除/历史保留、响应可见延迟分布 | 与 Sheets/Drive 共享域复核，未来真实事件采样；无记录时保持显式分期 |
| U07 | 未找到本次可用完整 Forms 调用轨迹；MCP tools/list 未运行核验 | 固定注册代码已覆盖五工具，运行元数据仍不能声称已验证 |
| U08 | updateItem 合法更换 questionId 后，已有回答对外保留/省略/重写的具体规则尚未核实 | 内部保存原始回答与提交版本；对 ID 转移及旧回答分别设计独立差分，未完成前不得自动重绑答案或宣称完整历史兼容 |
| R01 | 作者发现 shared unknown tool 通则与 G:182-198 不一致 | 统筹已复核并在 shared F09 修正公共错误标准；本报告已回读确认此服务保留 catch 后的工具错误 |
| R02 | 作者发现 Forms 发布政策时序冲突及 published-view ACL 共享需求 | 统筹已复核 migration/create 日期差，在 shared F13/U 合并；本报告已回读公共合成/验证设计，保持 dated profile 与 ACL 分层 |
| R03 | 非原作者 `/root/github` 于 2026-09-10 完成只读交叉审查，使用 `gpt-6-astra / xhigh` | 审查确认五工具、默认/错误、Drive/SDK/browser-X、LLM 校验/成本/回放与独立 oracle 有证据；提出 F-01/F-02，由原作者本轮修订，统筹负责 review-ledger 闭环；其余已列 U 保留 |
| F-01（P3） | 审查发现原第 61 行 JS 双竖线在 Markdown 表格中未转义，渲染拆列 | 已转义该表达式并保留 JS 或运算语义；自检全部 Markdown 表格列宽、10 节和 11 列 CSV，未改工具契约 |
| F-02（P2） | 审查发现原第 81/96/214 行将稳定 ID 泛化，遗漏 [UpdateItemRequest](https://developers.google.com/workspace/forms/api/reference/rest/v1/forms/batchUpdate#UpdateItemRequest) 的 mask 内传入/空 ID 规则；统筹和作者均于 2026-09-10 重读官方证据 | 已同步 §2/3/4/6/7/8 及 CSV：仅 B/X updateItem 可合法重设 ID，不新增 M 工具；增加版本映射与独立 ID/旧回答验证。历史回答行为仍为 U08，不凭空规定迁移结果 |

本文引用的 Google 文档均为官方 Forms API v1 / Drive API v3 在线资料，查阅 2026-09-10；固定 MCP 源码版本另列于 1.1。官方页面错误示例/版本冲突已明确记录，当前生产状态、未执行的差分、性能与成本不是确认事实。

## 10. 能力矩阵行

```csv
object,tool_or_capability,version,operation_type,state_dependencies,proposed_method,llm_role,fidelity_gap,verification_method,priority,evidence
google_forms,create_form,96f7fa1ff02b8130105ddc6d98796f3b49c1c574,W,Principal;DriveFile;Form;publish policy,stateful MCP facade and Forms core,offline content only,description backend rejection and canonical URL U,wrapper snapshot;create-get differential,P0,G:69-86;203-247;official forms.create
google_forms,add_text_question,96f7fa1ff02b8130105ddc6d98796f3b49c1c574,R+W,Form;ordered Item;Question;ACL,code preserving GET then index-0 insertion,none,SDK error strings U,order and stable-ID assertions;negative parameters,P0,G:87-108;249-311
google_forms,add_multiple_choice_question,96f7fa1ff02b8130105ddc6d98796f3b49c1c574,W,Form;RADIO options;Question;ACL,code preserving index-0 insertion,offline option text only,empty and duplicate option rejection U,schema snapshot;option counterexamples;readback,P0,G:109-137;313-379
google_forms,get_form,96f7fa1ff02b8130105ddc6d98796f3b49c1c574,R,Form;rich Item union;revision;Drive links,deterministic state rendering,none,rich write and UI coverage staged,all read-schema branches;MCP-SDK-Drive parity,P0,G:138-151;381-406;official Form resource
google_forms,get_form_responses,96f7fa1ff02b8130105ddc6d98796f3b49c1c574,R,Response;questionId;visibility;response ACL,deterministic first-page rendering,offline historical text only,no MCP paging parameters;order U,repeat reads;question references;page boundary,P0,G:152-165;408-433;official responses.list
google_forms,MCP envelope and visibility,0.1.0 source with SDK lock 1.6.1,protocol,fixed five-tool schema;stdio;error wrapping,contract-locked facade,none,unknown tool is caught tool error;runtime SDK U,raw MCP and harness output snapshots,P0,G:28-39;169-200;435-443;custom_mcp_util.py:176-195
google_forms,Forms batchUpdate X,Forms API v1,R+W,Item order;FieldMask;versioned itemId and questionId;revision;settings,shared HTTP and SDK adapter with mask-aware ID handling,proposal-only experiment,atomicity U;targetRevisionId merge staged;historical answers after ID reset U,invalid mixed batch;CAS;ID mask cases;independent historical-response comparison,P1,fillout-online-forms/preprocess/main.py:33-259;official batchUpdate#UpdateItemRequest
google_forms,Drive identity metadata query delete X,Drive API v3,R+W,DriveFile;Form ID;owner;ACL;page state,shared Drive service and Forms transactions,none,q scope and deletion history boundaries,Drive list-get-delete versus MCP reads,P0,utils/app_specific/google_form/ops.py:45-102;customer-survey/evaluation/main.py:252-305
google_forms,publish and responder permissions X,Forms v1 and Drive v3 policy 2026-07-22,manage,legacy profile;published;accepting;published-view ACL,dated code policy and permission checks,none,older create reference disagrees;tenant rollout U,principal matrix;unpublished and closed submission,P1,official api-changes-to-google-forms;publish-form
google_forms,HTTP browser response submission X,Google Forms browser protocol U,W,ResponderSession;Question;Response;publish;ACL,local functional page with shared core,offline content only,DOM and undocumented submission protocol staged,browser-to-API round trip;invalid answers;network capture,P1,fillout-online-forms/task_config.json:2-6;evaluation/main.py:60-105
google_forms,response filtering paging X,Forms API v1,R,Response index;timestamp;page token;visibility,deterministic HTTP query engine,none,sort and concurrent page semantics U,page union;filter boundary;token binding,P1,official forms.responses.list
google_forms,rich media quiz upload and linkedSheet,Forms API v1 readable state,R+W staged,Blob;Drive folder;grading;Sheet mapping;history,rich-read core and staged execution adapters,offline dataset content,API cannot create upload questions;UI and linked events staged,typed read snapshots;blob hashes;cross-service event checks,P2,official Form and FormResponse resources
google_forms,LLM simulation experiment,design 2026-09-10,simulation,explicit state;version;validated patch;replay,compare code versus offline-LLM hybrid versus proposal model,seed content or externally validated proposals,drift hallucination success bias latency,independent invariants;hidden seeds;cost per valid trace,P1,service report sections 7-8
```
