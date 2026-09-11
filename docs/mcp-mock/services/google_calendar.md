# google_calendar 高保真模拟可行性与设计

> 领域作者：`google_calendar`；模型/推理强度：`gpt-6-astra / xhigh`（由统筹者的创建回执登记）。非原作者交叉审查：`/root/wandb`，2026-09-10，`gpt-6-astra / xhigh`；完整报告与固定发布包核对未发现新增实质问题，仅 CAL-01/P3 表格转义问题已由原作者修正，详见第 9 节。查阅日期：2026-09-10；仓库 HEAD：`ef7ab5928062defc0dc2a91a4c26ddebccb1a6a7`，结合当前工作树。已阅读原始需求、`shared.md`、`service-template.md`、`docs/mcp-analysis.md`；适用目录未发现 AGENTS.md。F=源码或官方资料支持；D=设计；A=规划假设；U=待确认。本阶段仅静态阅读、公开发布包内存比对与写本文；未启动 MCP、导入任务配置、读取业务凭据、初始化日历或运行 benchmark。静态交叉审查不代表运行验证通过，实际运行版本及精细后端行为的 U 保留。

## 1. 范围、版本与入口

**结论（D）：该 MCP 的 5 个工具适合采用确定性代码维护 Calendar 状态，配合可选的离线 LLM 生成业务文本。接口可按固定发布包精确复现；事件时间、PATCH、查询和跨进程状态具有明确实现路径。重复事件实例、已有参与者事件的修改权限、真实错误文本及分页截断是主要保真难点。不能把“5 个工具”解释成“5 个无约束 CRUD”。**

### 1.1 固定基线与证据索引

| 标记 | 已核实事实、来源与适用范围 |
|---|---|
| C1 | `configs/mcp_servers/google_calendar.yaml:4-13`：stdio，服务名 `google_calendar`，`npx -y @gongrzhe/server-calendar-autoauth-mcp`，cwd=`agent_workspace`，session timeout=10 秒、缓存工具列表。无版本号、只读、日历选择或工具隐藏开关。 |
| C2 | `package.json:8,11` 同时依赖 `@cocal/google-calendar-mcp:^1.3.0` 与 `@gongrzhe/server-calendar-autoauth-mcp:^1.0.2`；`package-lock.json:813-830,1688-1725` 分别锁到 1.3.0 与 1.0.2，后者 SDK=0.4.0、googleapis=133.0.0。`package-lock.json:14748-14764` 锁 Zod=3.25.76、转换器=3.24.5。**@cocal 不是 C1 调用的包，不能合并两者能力。** |
| C3 | `Dockerfile:86-94` 复制 package 与锁文件后 `npm install`；`global_preparation/install_env.sh:192-197` 也安装 npm 依赖。锁文件构成可复现分析基线，但 YAML 的裸 npx、workspace 下包解析及已有镜像/缓存可能导致偏离；未检查任务镜像，运行版本 U。 |
| S | npm 发布包 [`@gongrzhe/server-calendar-autoauth-mcp@1.0.2`](https://registry.npmjs.org/@gongrzhe/server-calendar-autoauth-mcp/-/server-calendar-autoauth-mcp-1.0.2.tgz)，以下简称 **S**，所有 `S:Lx-Ly` 指包内 `build/index.js` 行号。本地只读参考 `/tmp/toolathlon-mcp-audit-xmv3srz8/google-calendar/build/index.js` 与当日重新下载的发布包逐字节相等，SHA256=`df681a8bf56e23c7c100ce749a11ef74fd2d3bfb6e5488bb07a698146840ed13`；tarball integrity 与 C2 相同。临时路径不是后续依赖，固定 URL 与 hash 可恢复证据。 |
| S 版本差异 | 发布包 `package.json:2-3` 是 1.0.2，`S:L147-L153` 自报 serverInfo 为 `google-calendar / 1.0.0`。npm 的 repository 字段与 YAML Source 写法不同，故本文以发布包内容为准，不把可变 GitHub 主分支当成 1.0.2。此为第三方 MCP，调用官方 Google Calendar API v3。 |
| P | [`@modelcontextprotocol/sdk@0.4.0`](https://registry.npmjs.org/@modelcontextprotocol/sdk/-/sdk-0.4.0.tgz) 包内 `dist/server/index.js:32-46,60-74`、`dist/types.js:1-5`、`dist/shared/protocol.js:72-105`；当日只读核验。支持协议版本 2024-11-05、2024-10-07，初始化协商及工具能力由 SDK 处理。 |
| Z | [`zod@3.25.76`](https://registry.npmjs.org/zod/-/zod-3.25.76.tgz) `v3/types.js:2240-2263`，以及 [`zod-to-json-schema@3.24.5`](https://registry.npmjs.org/zod-to-json-schema/-/zod-to-json-schema-3.24.5.tgz) `dist/esm/parsers/object.js:3-64`、`dist/esm/Options.js:22-26`：普通 object 运行时剥离未知键；JSON Schema 转换默认 draft-07，`additionalProperties:false`。该不一致必须区分记录。 |

外部 API 语义参考均在 **2026-09-10** 查阅，版本为 **Calendar API v3 的当日官方文档**，不是 1.0.2 发布时的服务快照：[Events 资源](https://developers.google.com/workspace/calendar/api/v3/reference/events)、[list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)（页面更新 2026-07-29）、[patch](https://developers.google.com/workspace/calendar/api/v3/reference/events/patch)（2026-07-01）、[get](https://developers.google.com/workspace/calendar/api/v3/reference/events/get) 与 [delete](https://developers.google.com/workspace/calendar/api/v3/reference/events/delete)（均 2026-05-12）、[重复事件](https://developers.google.com/workspace/calendar/api/guides/recurringevents)、[错误处理](https://developers.google.com/workspace/calendar/api/guides/errors)、[资源版本](https://developers.google.com/workspace/calendar/api/guides/version-resources)。新增平台字段不自动变成该 MCP 的写能力。

### 1.2 M、B、X 三层边界

| 层 | 范围与原因 |
|---|---|
| M 已暴露 | 5 个事件工具；所有操作固定到 OAuth 用户的 `primary` 日历；写字段仅标题、说明、地点、起止 dateTime/timeZone；读取返回后端 Event 字段。`S:L95-L134,143-L145,155-L275`。 |
| B 必需 | primary 到真实日历/用户的映射、事件 ID、起止时间及时区、查询截断/排序、PATCH、删除、已有重复事件的实例展开与异常、已有事件权限和元数据。创建/更新没有 recurrence/attendees，不代表查询不会遇到这类对象。 |
| B 未暴露 | CalendarList/日历管理、ACL 管理、Freebusy 查询、全文 q 搜索、分页 token、sync token、批量 endpoint、导入/移动、创建重复规则/全天事件/参会邀请、会议创建、提醒参数与附件上传。**不能增添这些工具或参数后仍称兼容 C1。** 后端广泛能力只在影响 M 或明确 X profile 时实现。 |
| X 当前实际 | 初始化、模型和评测都使用 MCPServerManager 的 Calendar 连接；新增的进程仍访问同一凭据对应的 primary。容器脚本复制 OAuth 与凭据文件；没有在 `utils/app_specific` 或当前 finalpool 中找到直接 Calendar Python SDK/HTTP/CLI 业务调用。检索范围为相关任务及 `utils`/`tasks/finalpool` 的 Python 文本中 calendar API 路径、googleapiclient/build、events 调用；不能据此排除未来入口。 |
| X 扩展设计 | 未来需要本地 HTTP `/calendar/v3/calendars/{calendarId}/events` 及选定 Calendar SDK 适配时，与 MCP 共享同一状态内核；显式增加 profile，记录支持的方法/字段。控制面 seeding、快照、oracle 不暴露成模型工具。浏览器 Calendar 页面、CalDAV、Google 全平台并非本阶段必需。 |

### 1.3 身份、认证与公网

F：`S:L17-L50` 默认读取 `~/.calendar-mcp/gcp-oauth.keys.json` 和 `credentials.json`，可用 `CALENDAR_OAUTH_PATH`、`CALENDAR_CREDENTIALS_PATH` 改路径。cwd 中同名 OAuth key 存在时会复制到目标位置；不是纯读取的启动流程。`auth` CLI 分支启动 localhost:3000 OAuth 回调并打开浏览器，请求 `https://www.googleapis.com/auth/calendar`，成功后落盘 token（`S:L57-L94,137-L141`）。正常 server 分支未自动调用 `authenticate()`；名称中的 autoauth 不代表每次缺 token 都自动完成登录。

F：`scripts/run_single_containerized.sh:475-485`、`scripts/run_single_decoupled.sh:648-658` 把仓库 Google OAuth 与 `google_credentials.json` 复制到容器用户的 `.calendar-mcp`。`global_preparation/create_google_credentials.py:7-17,89-100` 生成多个 Google scope 的 Python 格式凭据。其 access token 字段为 `token`，Node 原生凭据常用 `access_token`；本 MCP 直接 setCredentials，是否通过 refresh_token 正常恢复需后续受控核验，本文没有读取实际凭据。**共享文件不等于 Calendar、Drive、Sheets 的资源/授权模型相同。** Calendar 事件本身不是 Drive File；只在已有附件引用 Drive 时映射 fileId/ACL。

| 公网类别 | 真实路径 | 模拟设计 |
|---|---|---|
| 业务 API | Google Calendar API v3 公网读写 | 自控后端可完全在本机/Docker/内网；没有真实业务账号要求。 |
| 认证 | Google OAuth/token 刷新需要公网；localhost 回调不算公网 | 使用 episode 测试 principal 与授权快照；不接真实 token。若保留原 MCP，需受控认证适配，不允许遗留 OAuth 自动回公网。 |
| 安装 | npm/npx、镜像/依赖下载可能需要公网 | 固定锁文件、hash 和离线制品缓存；与业务公网分别记录。 |
| 模型 | agent 模型 API 与可选仿真/生成 LLM 各自可能需要公网 | 代码路径每工具调用 0 次仿真模型调用；离线预生成可去除合成期仿真 API 依赖。 |
| 内容链接 | Event 的 htmlLink/description/attachments 可含外部 URL；这 5 个工具不负责下载链接 | 返回与状态一致的链接；若其他工具抓取，单独配置自控路由或记录公网依赖。不能把返回 URL 当成已经提供可访问页面/文件。 |

### 1.4 当前任务与轨迹证据

F：重新读取 task_config，完整成员为 `student-interview`、`set-conf-cr-ddl`，两者都还声明 emails；没有以这两个案例限制设计范围。

| 任务 | 需求与实际入口 | 对设计的约束 |
|---|---|---|
| `student-interview` | `docs/task.md:1`：从邮件筛选后在香港时间工作时段安排面试。`preprocess/main.py:227,252-258` 调 Calendar 初始化；`preprocess/setup_calendar_events.py:47-78,103-116,127-169` 查询 2020—2030 窗口、maxResults=2500，逐项删除后创建两条占用事件。`evaluation/main.py:175-206,223-270,296-317` 重连、默认 10 条查询、检查旧事件保留和安排结果。 | 进程重启不能清空状态；时区/区间、已有事件保护和邮件内容传递都重要。初始清理仅覆盖有限窗口和一次返回页，不能视作完整重置。 |
| `set-conf-cr-ddl` | `docs/task.md:1`：从邮件确定截止时间，提前三小时建日历事件。`preprocess/main.py:24-48,70-82` 与上类似清理；`evaluation/main.py:55-96` 另起 MCP 查询 AoE（-12:00）窗口，解析 `Found...` 文本中的数组并容忍 5 分钟。 | Calendar 工具没有 reminders 字段；任务的“提醒”实际通过安排事件体现，不能据此添加提醒工具。AoE 与香港时区都应由精确时间运算支持。 |

F：`utils/mcp/tool_servers.py:470-486` 的 `call_tool_with_retry` 只重试抛出的异常，不检查正常返回中的 `isError`。因此现有初始化“已创建/已删除”的日志不能替代状态验证。当前 checkout 无 `dumps`、`legacy_results` 目录；用 `rg --files` 和相关任务名、history/trajectory/eval_res 文件名扫描未取得可用工具调用轨迹。本文是源码与公开规范分析，**没有以实际轨迹验证成功或错误格式**；将来有记录时只作为部分证据。

## 2. 工具与能力清单

### 2.1 全量工具、说明及输入

下表来自 `S:L95-L183`，不是 README 推测。原始 MCP 名保留；本仓库模型工具名为 `google_calendar_<原始名>`，由 `utils/openai_agents_monkey_patch/tool_name_aliases.py:21-28,85-99` 与 `custom_mcp_util.py:123-150` 转换。属性 R=读、W=写；没有其他业务执行/管理工具。

| 工具 / 属性 | 原始工具说明 | 完整字段与必填 | 字段说明（原文）/schema 细节 | 当前使用证据与未来价值 |
|---|---|---|---|---|
| `create_event` / W | `Creates a new event in Google Calendar` | required=`summary,start,end`；summary:string；start/end:object，各 required=`dateTime`，含 dateTime:string、可选 timeZone:string；可选 description:string、location:string。 | summary=`Event title`；start.dateTime=`Start time (ISO format)`；end.dateTime=`End time (ISO format)`；timeZone=`Time zone`；description=`Event description`；location=`Event location`。无 default/format/minLength。 | student 初始化明确调用；两任务要求 agent 新增事件，但无轨迹证明实际调用。未来跨时区安排、多事件规划、冲突后重排。 |
| `get_event` / R | `Retrieves details of a specific event` | required=`eventId`；eventId:string。 | `ID of the event to retrieve`；无 default、pattern 或长度限制。 | 两任务初始化/评测未调用；未来精确定位、读后改、实例身份、读取扩展字段。 |
| `update_event` / W | `Updates an existing event` | required=`eventId`；可选 summary、description、location:string；可选 start/end:object，若提供各 required=`dateTime`，可选 timeZone:string。 | eventId=`ID of the event to update`；summary=`New event title`；start/end dateTime 分别=`New start time (ISO format)` / `New end time (ISO format)`；timeZone=`Time zone`；description=`New event description`；location=`New event location`。可仅给 eventId，未规定至少一个修改字段。 | 当前初始化/评测未调用；未来修改既有日程、清空文字、单实例调整；完整覆盖必需。 |
| `delete_event` / W | `Deletes an event from the calendar` | required=`eventId`；eventId:string。 | `ID of the event to delete`；无其他约束。 | 两任务初始化使用；未来取消单次/系列、错误 ID 恢复、删除后读。 |
| `list_events` / R | `Lists events within a specified time range` | required=`timeMin,timeMax`；二者 string；可选 maxResults:number；可选 orderBy:string enum=`startTime,updated`。 | timeMin=`Start of time range (ISO format)`；timeMax=`End of time range (ISO format)`；maxResults=`Maximum number of events to return`；orderBy=`Sort order`。number 未声明 integer/min/max；schema 无默认值。 | 两任务初始化/评测使用；未来密集日历、按更新时间定位、窗口分解、读取重复实例和全天事件。 |

F：全部 schema 是 object；根及 start/end 的 `additionalProperties:false` 来自 Z。完整 schema 的权威输入为 S 对应 schema 定义和 Z 固定转换器；没有 outputSchema、工具 annotations、readOnlyHint 或 auth 元数据声明。正式验收需从固定包列工具并比较 JSON Schema（本阶段没有启动服务）。

**两层校验不可混淆（F/D）：**

- S 的 Zod 校验检查类型、必填与 orderBy enum，不校验 ISO 日期、IANA 时区、时间先后、ID 是否存在；string 可空，optional 不等于 nullable。`maxResults:"10"` 原始 MCP 会被 Zod 拒绝；本仓库 harness 的 schema 类型修复可能先转成 number（`custom_mcp_util.py:159-177`），两条入口要分别测试。
- Zod parse 剥离额外字段，包含根的 calendarId/attendees/recurrence/id 和时间对象的 date。不能偷偷实现这些额外参数；也不能统一加 strict 后宣称与源包行为相同。合法已知字段可创建成功，但被剥离字段不会产生状态效果；内部审计记录其投影，不改写成“已支持参与者/重复事件”。纯全天 `{date:...}` 缺 dateTime 仍错误。
- `list_events` 运行时用 `maxResults || 10`、`orderBy || 'startTime'`，并固定 `singleEvents:true`（`S:L256-L265`）。所以缺 maxResults 和数值 0 都变成 10；空 orderBy 会先被 enum 拒绝。負数/小数可通过 Zod，但进入 Calendar API 的整数/范围验证；不能把工具 schema 擅自写成默认 250、integer 或 2500 截断并当成同一层的行为。

### 2.2 输出、业务分派和错误

所有成功仅一个 `content` item：`{type:"text",text:...}`，无顶层 `structuredContent`、业务 success 字段或自定义元数据。原始内容必须保留换行、英文前缀与 JSON 缩进；不能统一成 JSON 对象。

| 工具 | 后端调用 / 状态约束 | `content[0].text`（表达式模板） |
|---|---|---|
| create | `events.insert({calendarId:'primary',requestBody:validatedArgs})`；服务端生成 ID（`S:L188-L204`）。 | `Event created with ID: {response.data.id}\nTitle: {input.summary}\nStart: {input.start.dateTime}\nEnd: {input.end.dateTime}`。仅 ID 来自响应，标题/时间回显输入，不是规范化后 Event。 |
| get | `events.get`（`S:L206-L219`）；有效身份、可见事件/实例。 | `JSON.stringify(response.data,null,2)`；可包含 id/kind/etag/htmlLink/status/created/updated/start/end/creator/organizer/recurrence/attendees 等后端字段，不删成任务只用的标题与时间。 |
| update | **`events.patch`，不是 events.update/PUT**（`S:L221-L239`）；省略字段保持，已有身份与权限仍检查。 | `Event updated: {id}\nNew title: {updates.summary \|\| '(unchanged)'}\nNew start: {updates.start?.dateTime \|\| '(unchanged)'}\nNew end: {updates.end?.dateTime \|\| '(unchanged)'}`。写 summary 空串时输出可能说 unchanged，不能据这个回显判定最终状态；后端 patch 响应被丢弃。 |
| delete | `events.delete`；API 成功响应为空（`S:L241-L254`）。 | `Event deleted: {id}`。重复删除不可直接当永远成功；已删除与不存在的具体读/删行为需保持真实错误/墓碑 profile。 |
| list | `events.list`，primary、singleEvents、时间窗和默认参数；后端完整分页结构被丢弃（`S:L256-L274`）。 | `Found {response.data.items?.length \|\| 0} events:\n{JSON.stringify(response.data.items,null,2)}`。items 为 [] 时是 []；若 API 缺 items，模板会出现 `undefined`，不是擅自补成 []。是否真实出现缺 items 属 U。 |

API 的 PATCH 保留省略字段，数组更新具有整体替换语义；本版没有数组写字段，但已有数组必须在普通 patch 后保持。[官方 patch 语义](https://developers.google.com/workspace/calendar/api/v3/reference/events/patch)。get 可返回何种字段由后端版本/对象/权限决定；固定 Node SDK 不构成服务端返回字段的白名单。[官方 get](https://developers.google.com/workspace/calendar/api/v3/reference/events/get)。

F：工具处理 try/catch 统一返回 `content:[{type:"text",text:"Error: "+error.message}]` 和 `isError:true`（`S:L280-L289`）。包括 ZodError、API/认证错误以及**已进入 tools/call 的未知工具名** `Error: Unknown tool: <name>`（`S:L276-L289`）；不是所有“未知”都返回协议层错误。未注册的 JSON-RPC method（例如资源/提示请求）才走 SDK MethodNotFound；输入 envelope 不满足 CallToolRequestSchema 的错误在 handler 外，具体 RPC 表现应依 P 验证。

F：只有 tools/list、tools/call 注册，无 resources/prompts/templates、订阅、进度、任务句柄、自定义分页或动态 tool-list-change（`S:L155-L184,292-L299`；P）。tools/list 一次返回 5 个工具，无分页游标；P 初始化根据请求版本协商，公布 tools 能力。默认 `main` 先读 OAuth 文件；缺文件会 process.exit，不能把连接失败模拟成一个已连接工具的业务错误。

F：本仓库模型看到的是 content item 再次 JSON 序列化后的字符串，顶层 isError 不会单独透传；超长输出落入 workspace 文件并截断（`custom_mcp_util.py:187-227`）。因此应验证原始协议层、模型层和评测直接解析层三种包装。认证/底层错误只在 MCP 文本中出现 error.message，不能额外给模型整个 Google HTTP error JSON；后端 HTTP 适配则应保留对应 code/reason/body。

## 3. 领域状态模型

以下为 D；具体 API 字段依据前述官方 v3 Event/查询/重复事件规范，未实际实现。

| 实体 | 持久化字段/关系 | 派生与不变量 |
|---|---|---|
| Episode / Principal | episode_id、seed、profile/schema/package/tzdb 版本、虚拟时钟、principal_id、scope/凭据状态、primary_calendar_id。凭据仅测试材料，不复制真实 token。 | primary 是当前身份的别名，不能是所有 episode 共享的一个字符串资源。Calendar 与 Drive 可共享 principal 关联，scope 与资源 ACL 分开。 |
| Calendar | calendar_id、owner、默认 IANA timeZone、defaultReminders、必要 ACL/可见性配置、revision。M 不能创建/选择日历；控制面可生成多用户日历用于身份差异。 | Event 归属 `(episode,calendar_id,event_id)`；M 的 primary 查询路由到真实 ID。其他日历可作为显式 X 数据，不能从 M 凭空访问。 |
| Event 主资源 | id、iCalUID、calendar_id、summary/description/location、start/end 的 date/dateTime/timeZone、status、creator/organizer、created/updated、etag、sequence、eventType、权限字段；其余已知属性按 profile 存储。 | 服务端分配的不透明 ID 稳定可读；id 与 iCalUID 不相同，系列实例不能共用一个 event id。时间比较使用 instant，保留原时区与浮动日期语义；全天 end.date 为排他终点。标题/地点重复合法，不能按名称唯一约束。 |
| Recurrence / Exception | master event 的 RRULE/RDATE/EXDATE、实例的 recurringEventId、originalStartTime、覆盖字段、取消墓碑。 | 按查询窗口惰性展开，实例 ID 由已存身份映射稳定生成；移动实例仍保留原 originalStartTime。修改 master 或实例不能互相误用 ID；删实例不能删全系列。 |
| Attendee / Event copy | 已有参会者 email/responseStatus、organizer/creator、self、guestsCanModify、locked、可见性与与其他 principal 事件副本的关系。 | M 无新增参会者/RSVP 参数，但 get/list 能看到、update/delete 会受角色或锁定限制；保留数组及主办方身份，不能假设 primary 中全是自己主办。 |
| Attachment / Link | 已有 attachments 的 fileId/fileUrl/title/mimeType/iconLink；description 的普通 URL 与 htmlLink；跨服务引用的来源 ID/版本。 | M 不能上传附件或创建 Meet；已有引用保持。Drive 文件权限不因日历可见而自动开放。要访问附件正文时由共享 blob/Drive 适配处理，本 Calendar 内核不存一份不一致副本。 |
| Revision / operation log | 事务前后 revision、输入投影、权限决定、已提交变更、返回文本、故障计划、请求/响应 hash、提交时间、调用链入口。 | etag/updated 由提交态渲染，created 保持；sequence 不是“每个字段写入都加一”的简单替代，字段级真实变化规律待差分核验。M 无 If-Match；内部并发控制不能强迫 agent 提供不存在的版本参数。 |

查询采用区间重叠：`event.end > timeMin && event.start < timeMax`，不是只找起点落入窗口；API 时间边界为排他，list 的毫秒部分被忽略，orderBy 为起点或更新时间升序。M 自行设默认 maxResults=10，API 单页最大 2500，可能返回未满页而仍有后续；M 丢掉 pageToken 后，返回数量不是全量数。此限制必须原样保留，不能“帮忙自动翻完”。[官方 list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)。

时间模型需区分 instant、IANA 时区、全天日期、原始时间表示和渲染时区。有效起止约束、日期解析、DST 的不存在/重复本地时间以及 offset 与 timeZone 冲突响应需建立差分样例。支持任意合法时区，而非只写死香港/AoE。M 没有 freebusy 或自动避让：**普通日历允许时间重叠，模拟器不能替 agent 拒绝冲突日程或自动移到空档。** 冲突是否违反任务要求由独立 oracle 判断。

重复事件虽不能由 M 新建，其已有实例可以由 list 获取 ID，再 get/patch/delete；get master 也可能由已知 ID 调用。实例身份及 originalStartTime 必须保留。[官方重复事件与例外](https://developers.google.com/workspace/calendar/api/guides/recurringevents)。有限固定展开 fixture 只可辅助测试；不能遇到新窗口便静默“无事件”。

删除需保留足以支持再次访问、系列异常和审计的墓碑；具体 cancelled 资源的字段保留、get/再次 delete 的区别以受控记录确定。官方指出重复删除可能返回 410，不能一律当 404 或幂等成功。[官方错误处理](https://developers.google.com/workspace/calendar/api/guides/errors)。

本版工具没有长时间执行任务、通知投递状态查询或 async job polling。事务提交后成功响应应能被另一进程读取；外部邀请传播/大型群组处理可作为后续 profile 的受控异步行为，不能因为当前官方 Event 新增 async 字段就宣称本版具有相应操作工具。已有特定 eventType/locked 资源应读取保留、可写部分按约束处理；证据不足的修改不伪造成功。

## 4. 代表性交互序列

以下均为 D，按状态断言评估多种有效次序；不限当前任务。控制面初始化不能给模型暴露任务答案。

1. **普通生命周期与幂等误区**：create → get → 只改 description → list(orderBy=updated) → get → delete → get/再次 delete。断言 ID 相同、省略标题/起止保持、列表反映已提交状态、重复删除按真实错误处理。变体先 list 再 get，或创建两个同名同时间事件：两条资源必须并存，不能按内容去重。
2. **时区与恢复**：给 start 晚于 end 的事件参数 → 后端错误且状态无变更 → agent 修正 → get/list 在另一 offset 的重叠窗口读到同一 instant；加入 DST 跨夜事件与已有全天事件。断言模拟器不自动调换时间，不把 date-only 强行改成 dateTime；合法相邻不重叠区间不误入窗口。
3. **密集日历与有限检索**：在含 37 条近似标题的窗口 list 默认只见至多 10 条 → 提高 maxResults 或分解时间窗口 → get 目标 → 循环 update 多条 → 按 updated 再读。没有 M pageToken/批量工具，只能多次调用；必须显示 M 的截断现实，不虚构“下一页”参数。若同一极窄窗口超过可取上限，完整枚举任务在仅 M profile 下不一定可解，应排除或明确限制。
4. **重复实例操作**：控制面构造跨 DST 的 weekly 系列与 EXDATE → list 返回实例 → get 一条 → update 移动一次 → 再查原/新窗口 → delete 另一实例 → get master。断言原 originalStartTime 不变、其他发生次数保持、同一实例不在两个窗口重复、删除实例不消失整个系列。变体先改 master 标题再读实例，核查继承与例外。
5. **权限与参数恢复**：以受限 scope 身份 list/get 成功 → update 被拒绝；或已有 locked/非主办方不可更改字段对象写失败 → agent 选择自己有权修改的对象。断言拒绝不改变 revision、不自动授予权限、不把“不存在”自动建出来。更换身份只由显式 X/控制面操作，M 不提供 auth 切换工具。
6. **跨进程/入口**：初始化进程 create → 模型进程 list/update → 评测进程 get，重启模型 MCP 后再次读取；显式 X profile 再加入 HTTP get→M patch→SDK get。断言所有入口共享 episode、principal 映射、ID/etag/状态；未覆盖的 HTTP 方法明确 unsupported，不能落回公网。
7. **跨服务信息搬运**：emails 或 Sheets 中保存不同语言/时区/相似会议名的信息 → agent 自己确定日程参数 → create → 把返回 ID/时间写到另一个服务 → get 对照。模拟器只返回本服务状态，不能读评分规则主动把正确日程拼到描述里。若描述含 Drive URL，只是文本复制；附件下载必须另经 Drive 权限检查。
8. **并发和不确定响应**：两个客户端分别 patch 同事件的 location 与 summary → 串行化提交并保留两字段；同字段并发写则以提交顺序决定最终值。create 已提交但响应丢失 → agent 查询确认后决定重试；重试确实再 insert 时应产生第二个事件，不能凭任务意图自动去重。M 不支持 idempotency key/If-Match，不能要求模型使用虚构参数。

## 5. 候选实现与推荐

下表是 D 的可行性判断；向量 I/S/C/T/D/P 分别是接口/状态/跨入口/身份时间/数据分布/性能，不是已经测得的分数。成本为相对复杂度，不是工期承诺。

| 路线 | I/S/C/T/D/P 取舍 | 开发、运行与维护成本 |
|---|---|---|
| 保留真实 MCP，只替换 Calendar 后端 | I 高；S/C/T 取决于内核；D 由生成器；P 可高。保留 Zod、文本包装与 SDK 错误风格收益大。 | 中：原 MCP 无 endpoint env 开关（S:L143-L145），不能仅改 YAML URL。需要小型审计过的 backend/认证接缝，明确维护 patch；或固定 SDK 方法适配。不能靠真实凭据加 DNS 重定向留下刷新外网依赖。 |
| 有状态 MCP 替代实现 + 共享领域内核 | I 可精确但须维护工具/输出快照；S/T 限定范围可精确；C 取决于共享持久层；D/P 可扩展。 | 中：5 个工具有限，可直接复现源包装，免去 OAuth/SDK transport复杂度。语义成本主要在事件类型/时区/重复实例；后续源包更新需逐项差分。 |
| 本地 Calendar HTTP/API + SDK 接入 | I 通过原 MCP/SDK；S/C 强，HTTP 错误、URL、etag 条件写需额外实现；D/P 可扩展。 | 中高：先实现实际 insert/get/patch/delete/list，其他路由明确失败。SDK 配置 rootUrl/认证适配需按语言分别验证，不声称完整 Google API 兼容。 |
| 只 monkeypatch SDK/client | I 通常可保留；C 在所有调用确实经过同一补丁时成立，HTTP/CLI 容易遗漏；P 可高。 | 前期低、长期中高：适合作为确定性内核的薄适配层，不适合作为多份内存 fixture。多个进程、Node/Python 导入路径及凭据入口都需要契约测试。 |
| 现成日历服务/重复规则库 | 未确认有可直接替代 Google Calendar JSON API 的现成服务；CalDAV/ICS 兼容不是这 5 个工具的接口兼容。重复规则库可减少 B 层代码，不能提供权限/ID/错误语义。 | 库成本较低、适配中：可评估固定 `python-dateutil 2.9.0.post0` 的 rrule/rruleset/rrulestr；它处理规则集合、排除日期、窗口查询，但不提供 Calendar 实例 ID、例外复制、OAuth 或 Google PATCH 行为。不能直接当 emulator。 |
| 静态 fixture / 调用回放 | I 对已录样例精确；S/C/T 对新顺序弱；D 固定；P 高。 | 低：只用于 golden 契约、差分记录和回归种子，不能作为最终环境的动态真值。 |
| LLM 主导仿真 + 显式状态 | I 需外部校验；S/C/T 无保证，尤其 DST、排序、截断、权限；D 可改善；P/成本弱于代码。 | 粗原型低，达到可靠状态保证后仍需大部分确定性内核；每工具增加模型费用和重试。Calendar 的准确规则多，缺少稳定收益点。 |
| 混合：确定性事务 + LLM 离线内容生成 | I/S/C/T 同代码路径；D 增强；P 不增加逐工具 LLM 延迟。 | 首选数据路线：初始描述/地点/背景的批量生成和审核有成本，但可多 episode 克隆/变异并复用。LLM 不执行 Calendar 操作本身。 |

现成组件证据：当日核对 [`dateutil 2.9.0.post0 rrule.py`](https://github.com/dateutil/dateutil/blob/2.9.0.post0/src/dateutil/rrule.py) 的规则实现；[官方 rrule 文档](https://dateutil.readthedocs.io/en/stable/rrule.html) 是浮动 stable，查阅时页面版本标识与固定源码可能不同，固定 release 才是后续候选基线。其 RFC 规则支持不等于 Google 的全部时区/异常行为一致，需用 Google 记录作为外部参照。

**首选（D）**：固定 1.0.2 的工具契约，以有状态 MCP 适配层连接一个确定性 Calendar 内核；语义数据持久化到 episode 命名空间，LLM 可离线生成业务文本。此路最容易去除公网认证并保持重启一致性。**备选**：保留原 server，用经审计的 Calendar client 接缝连接同一内核/本地 HTTP；用于差分和后续多入口扩展，明确不是“零修改原包”。

替换点有源码依据：[`googleapis@133.0.0`](https://registry.npmjs.org/googleapis/-/googleapis-133.0.0.tgz) `build/src/apis/calendar/v3.js:748-779,915-923,976-985` 从每次方法 options.rootUrl 构建 API URL；S 调用没有传入该 options。全局环境变量是否能覆盖并未证明，实施时应选显式、可测试的 client 注入/方法 options 方案，并独立处理 OAuth。

## 6. 保真缺口与取舍

| 能力 | 可达到的范围与阶段 | 错误近似会训练什么 | 验证/降低影响 |
|---|---|---|---|
| 5 工具契约、文本包装、Zod/default 投影 | 源码可精确复现，P0；实际镜像工具快照 U。 | 学会不存在的工具/参数，把 title/update 回显当完整资源。 | 固定包/依赖/hash；原始与模型层双快照，空串/零值/额外键/缺字段测试。 |
| 普通定时事件 CRUD/PATCH、查询重叠/排序 | 规则可较准确复现，P0；嵌套 patch、空 patch 的 API 细节需差分。 | 更新抹掉未改字段；列表与 get 不一致；重复请求总成功且去重。 | 独立状态 oracle、变换性质、两进程交叉读和响应丢失样例。 |
| 時区、全天读取、DST | P0 应包括合法 offset/IANA 和已有全天读；稀有 DST/冲突表示作为显式差分门槛。 | 把 ISO 字符串字典序当时间，假定一天总是 24h、不同 offset 不同事件。 | pin tzdb；独立日期库/明确 UTC 预期值，跨 DST/跨月/闰年集合。 |
| 分页/截断与空结果 | MCP 丢 token 行为可精确；真实后端未满页仍有后续的分布近似。X 完整分页 P1。 | 一次 list 无结果即全环境不存在，默认取得所有事件。 | 默认10/max2500/密集同起点；M 不补 token；已确认后端分布的短页故障 profile 单独标识。 |
| 已有重复系列/实例及删除例外 | 状态规则可实现但成本较高；P0 试点用常见 DAILY/WEEKLY、COUNT/UNTIL/EXDATE，P1 扩展组合与 master/instance 各种修改。未覆盖规则不是返回空数组。 | 把每次 occurrence 当独立无父资源事件；移动改变实例身份；删除一次删除全系列。 | 独立实例集合断言、固定官方例子/授权录制差分；profile 声明范围，遇到不支持的规则返回明确模拟器扩展错误。 |
| 身份/权限/已有参与者与特殊事件 | P0 身份/scope/locked、保留参与者字段；P1 细化 organizer/guest/private 复制及特殊 eventType。精确错误原因 U。 | primary 永远全权限，日历能写即能改任何邀请，看到附件即可读 Drive。 | 权限矩阵和真实样本；权限检查先于变更，X ACL 改动后跨工具核查。 |
| etag/sequence/删除墓碑 | ID/版本稳定性可准确；精确 sequence、保留字段/删除后读取和时间粒度 U/P1。 | 每个 update 都按同一版本公式变化；已删除对象可自动恢复。 | 语义归一化比较并保留真实字段存在性；get/delete/patch 的已删组合差分。 |
| 外部邀请传播、提醒投递、Meet、附件下载、Calendar UI | 当前 M 无对应写/执行参数；已有可见元数据保留；真实传播语义昂贵，明确分期或不支持 X。 | create 事件自动发外部通知/创建视频会/下载文件，或保证任何 htmlLink 可点击。 | 不生成无依据的通知/下载成功；profile 记录 URL 可访问范围与跨服务副作用，不能仅返回伪成功。 |
| 限流/临时错误/重试 | 错误类与可控故障可实现；真实配额和响应延迟分布近似。 | 所有异常重试立即成功；create 重试不重复；永久 403 自动恢复。 | 故障时机分 commit 前/后；保留不确定提交，按错误类恢复，fault seed 与调用日志回放。 |

未知 MCP 工具名按 S 包装 `isError:true`；未注册 JSON-RPC 方法按 P MethodNotFound。已知工具遇到暂未实现的合法业务语义，返回 `Error: mock_unsupported_semantics: ...` 与 isError，并在 profile 标明是模拟器扩展，**不冒充 Google 原生错误**。额外参数在真实 Zod 已剥离的场景则保持投影行为，不能声称该额外操作成功生效。

## 7. LLM 仿真可行性

### 7.1 职责边界与选择

| 工作 | LLM 是否适合 | 外部控制 |
|---|---|---|
| 生成多语言事件说明、现实地点、邮件/会议背景、近似名称干扰项 | 适合离线生成；LLM 提供候选内容而非真实日历状态 | 校验长度、文本类型、引用存在性、敏感/答案泄露和背景一致性后写入 seed；任何相对时间由代码转换/审核。 |
| create/update 的文字字段 | API 本来保存用户传入文字，无“智能润色”能力 | 按输入投影原样存储，不能 LLM 重写、补人数、修复错误时区。 |
| get/list 的响应叙述 | 不适合，本版输出是固定模板与 JSON | 从已提交 Event 状态确定性渲染；不得创造字段、忽略干扰项或把答案排第一。 |
| 查询、排序、时区、RRULE、ID、ACL、PATCH、删除、版本、并发 | 不适合由 LLM 最终裁决 | 确定性规则/库/事务，独立状态检查；复杂不是转交模型的理由。 |
| 难穷尽的错误文本/特殊业务状态 | 可离线提出测试场景和候选解释；在线文本只能在已验证错误模板范围内选择 | 真实 error.message 记录/契约约束决定输出，不能向 agent 追加解题建议。 |

推荐是**代码主导执行，混合离线内容合成**。LLM 主导也可以作为受限实验对照，但不能只靠对话记忆维护日历。

### 7.2 若做 LLM 主导对照，如何保持状态

D：工具调用 → 确定性 schema 投影/授权 → 读取该 principal 的相关事件/索引与版本 → LLM 提出受限响应/变更集 → 独立校验器验证输入一致、时间/ID/权限/引用/状态不变量 → 乐观版本检查并原子提交 → **从已提交状态重建最终输出**。

- get 必须精确主键检索；list 必须由范围/recurrence 索引确定候选及完整性，再让模型处理实验项，不能仅挑几条“相关事件”导致负查询幻觉。大日历按索引查询+窗口惰性展开处理，业务摘要不能替代真值；候选超过上下文上限时走代码路径或显式实验失败，不能截断状态后编列表。
- 模型变更字段必须属于工具允许字段，new ID/etag/时间戳由内核分配；记录模型不知道的并发 revision。如果版本冲突，重读后重算，最多一次模型修复；再次失败不提交，记录 validator_reject 并返回明示仿真故障。不能为提高成功率静默改 agent 参数。
- 读取已有资源时禁止自动生成内容。新自然语言只在 seed 初始化/合法输入中进入状态；Calendar 工具不是文本生成服务。写入不需要的整份历史和无权资源不传模型。
- 仿真模型只看到接口契约、经权限过滤的状态及本次调用；不提供任务答案/评分目标/成功轨迹。Event description 中的指令当普通数据，不得更改模拟器规则；校验返回内容不能额外解释任务最优安排。
- 记录模型版本、提示版本、温度/采样、检索条件及状态 hash、完整提案、校验结果、重试、commit revision、最终渲染文本。复现通过已提交操作/已记录输出回放；固定 seed/temperature 不是模型输出可复现的证明。

LLM 若需独立验证完整查询结果、时间与权限，校验器已经实现这部分语义。因此其潜在收益主要是内容分布与原型探索，不能以“少写规则”作为已成立结论。

### 7.3 成本与质量对照

以下全为 A，供压测规划，**不是实测性能或当前模型价格**。令每 episode 50 次工具调用，平均每事件 JSON 0.25—1k token；list 10 条本身约 2.5—10k token，大 maxResults 不能直接塞 LLM。

| 路线 | 仿真模型次数 / 上下文 | 单调用成本和延迟假设 | 长期成本判断 |
|---|---|---|---|
| 纯代码执行 | 0；数据从状态读出 | 仿真模型成本 0；本地普通 CRUD p95 目标 <50ms、规则展开窗口 <200ms，均待压测 | 算法/事务一次投入；规模成本随状态、查询展开和响应大小增长。 |
| LLM 主导受检验 | 正常 1 次，修复率 r 时均值 1+r（上限2）；get/write 输入 2—6k，list 4—16k，输出约 0.5—3k token | `C=(1+r)*(Tin*Pin+Tout*Pout)/1e6`；模型单次 1—8 秒只是待测区间，重试增加延迟 | 50 次约 50—100 个模型调用/episode，昂贵且校验内核仍必要；大列表走代码降低覆盖，须报告 fallback 比例。 |
| 混合离线初始化 | 每 seed 1—3 次批量内容生成，运行工具0次 | 如一 seed 10k输入/20k输出 token 的假设，成本除以有效复用 episode 数；不使用线上响应缓存替代可变状态 | 批量、多模型选择、内容缓存可降成本；需监测复用造成的名称/答案模板泄漏。 |

仅举计算例：假设 Tin=6k、Tout=1k、r=0.1、Pin=1、Pout=4（价格单位/百万 token），单调用=0.011 单位，50 次=0.55；100万 episode=55万单位，**不含 agent 模型**。这些是占位价格敏感性计算，不指某个供应商现价。吞吐 T 次工具/秒、LLM 平均占用 L 秒时需要约 `T*(1+r)*L` 个并发请求；例如 T=200、L=3、r=0.1 约660，在代码方案中不存在这项模型配额瓶颈。

D：对照试点固定同一隐藏环境/任务集，比较代码、LLM提案+独立校验、离线LLM内容+代码三组：契约一致率、状态漂移/资源幻觉/错误接受率、近似参数“自动修复”率、长序列一致性、答案泄露、valid episode/s、p50/p95、token 与成本。代码 oracle 需与被试状态转移实现独立；真实记录/人工抽查提供外部基准，不能只让同一 LLM 自评。LLM生成内容组另比较任务语义多样性和跨服务背景一致性，不能只看工具成功率。

## 8. 合成、验证与分期

### 8.1 初始分布、可解任务与隔离

D：seed 配置覆盖 0/1/10/11/数百/密集大规模事件；时区、日期边界、长短文本、缺失可选字段、同名/近似名、重叠事件、可修改/不可修改副本、已有全天、重复系列、取消/移动实例、附件引用和不同更新时间。名称不使用“正确候选/干扰项”标签；发布时间/位置/邮件内容也不能以模板位置泄题。多样化内容与资源 ID 生成分开，ID 不编码任务答案。

任务生成器从真实状态产生约束，或按约束构造状态后验证可解；独立检查仅 M 的有限检索能否定位必要资源，避免把需要未暴露工具的任务误判为可解。日程安排用独立区间约束求解/检查；不强制某个事件名、创建顺序或唯一时隙，允许多种符合条件的最终状态。任务 oracle 可读取隐藏事实，但不能将其放入服务数据或仿真 LLM上下文。

单 episode 多进程通过显式 episode/session 路由到共享状态；不同 episode 用独立数据库/命名空间和测试 principal。状态键不能仅 eventId 或 primary。可采用每 episode SQLite 文件做简单隔离，扩大并发再用有事务的共享数据库按 episode 分区；数据库只是存储，不提供 Calendar 语义兼容。多进程连接启用真实事务，禁止进程启动自动 seed/清空已有 episode。

快照包含数据、ACL、虚拟时钟、ID 分配器、随机流、tzdb/profile、日志偏移与 blob 引用。克隆默认生成新的 episode 命名空间，保留内部 ID 关系；reset 从快照替换该 episode，不能以现有任务一次 list+delete 冒充 reset。异常恢复按已提交日志重放，commit 与响应丢失分别记录；不得重新执行全部 create 来“恢复”。规模瓶颈主要为 recurrence 展开、密集排序/大 JSON、历史存储与 LLM 配额；惰性窗口展开和状态索引可优化，不能通过删权限/跳校验换吞吐。

### 8.2 验证计划与验收门槛

以下为后续计划，本阶段未执行。所有允许写入的真实差分仅能在未来明确授权、专用测试账号与隔离日历条件下开展；C1 固定 primary，因此不能声称换一个 calendarId 参数即可保护真实账号。

| 类别 | 设计验证及预期断言 | 可用现成记录 / 需要受控核验 |
|---|---|---|
| 契约 | 五工具名称/说明/schema 逐字段；省略/null/空串/0/负数/小数/未知键；原始内容、错误 isError、模型重编码/截断；initialize 与 unsupported method。 | 静态发布包可建立预期；当前无 live tools/list/调用记录，需要后续隔离启动采集，不等于本阶段运行。 |
| 业务状态 | create/get/patch/list/delete 随机组合；查重叠、同名合法、写后跨排序读取、空 patch；非法输入无变更。 | 可先纯本地独立规则检查；API 时间校验、空串/嵌套 PATCH 与删除后行为需受控差分。 |
| 时间/重复/权限 | DST、all-day读取、series/instance/exception、跨 offset；scope/locked/非主办方；attachments 读取与 Drive权限分离。 | 官方例子作为部分 golden；真实归一化格式、权限制约、未知特殊事件需受控记录。 |
| 多入口与并发 | 初始化/agent/evaluator三进程、重连、M↔HTTP/SDK、不同字段和同字段竞争、创建提交后断开、snapshot clone/reset。 | 本地独立集成可验证；真实并发竞争/错误与时间特征需要后续专用账号核验。 |
| 数据分布 | 留出未见领域/语言/资源数/关系组合，扰动名称与目标排列，测试超过10条、重叠窗、长文本和多实例；不能只回归两项finalpool。 | 生成器约束检查+人工抽样；评估跨任务泛化，不把仿真中的高成功率当迁移证明。 |
| LLM 与性能 | 至少1000个seed的长序列、同态重复读、幻觉/无效接受/答案泄露对抗；10/50/200客户端并发阶梯，比较代码/LLM/混合。 | 全为待执行规划；报告有效样本数、失败率置信区间、fallback/retry比例、单位有效轨迹成本。 |

差分对齐采用调用语义与提交态关联：真实 ID 与 mock ID 建双射，验证唯一性/引用/系列归属，不比较随机字符串字面值；created/updated 用顺序与相对虚拟时间关系对齐，保留时间精度与字段存在性差异；dateTime 转 instant 比较但另外检查 offset/timeZone，不能归一化掉错误时区；etag/sequence 比较变化关系并保留未核实细节。htmlLink 验证关联的 event/principal 与可访问 profile；错误比较层级、类/原因和稳定文本，动态 request ID 单独规范化；list 已定义排序必须比较，等键 tie-break 未有规范则不锁死人为顺序。

建议门槛（D）：P0 的5工具契约/确定性不变量/隔离测试全部通过；独立oracle发现的资源幻觉、越权写、错误接受、未提交却成功和读写不一致必须为0已知未修复项。随机长序列即使零失败也报告样本数/统计上界，不宣称没有风险。P1 的 recurrence/权限/多入口必须各有实证差分，而不是用提高总通过率遮盖某类全失真；性能单独验收，不抵消保真失败。

### 8.3 实施优先级

- **P0 契约与可迁移状态试点**：全部5工具、primary身份、持久化跨进程、schema投影/错误包装、普通定时/全天读取、准确时间窗/排序/截断、PATCH/删除、基本scope/locked、常见重复实例读取/修改/删除。选择跨时区、多干扰、允许多解的改期任务，加无效参数恢复和重启后独立评测；不只复刻现有面试任务。
- **P1 扩展完整合理操作**：复杂重复规则/例外与master修改、已删读取、参与者副本/特殊事件权限、真实错误语料；按X需求加入局部HTTP/SDK、分页和etag条件写。工具名称不变，后端合法可见对象分布扩大。
- **P2 可选扩展 profile**：需要真实业务副作用时再增加通知/附件下载/Calendar UI/更广API；必须先核定入口与协议，不能凭平台能力添加M工具。原profile对不支持请求明确失败。

Calendar适合作为统一状态内核与工具契约的首轮试点候选，因为5工具边界清晰而时间/重复/跨进程约束足以检验真保真。它对“在线LLM代替复杂接口”并非最有利对象；因此另设严格限定的Calendar对照（普通CRUD+最多40条候选+独立时间/权限校验），量化LLM成本/错误与内容生成价值。更大状态和复杂规则按第7节回退统计，不能据这个小对照断言所有服务不适合LLM。

## 9. 待确认与审查记录

| 项目 | 当前状态与所需证据 |
|---|---|
| 实际镜像与npx解析 | U：已核实锁文件/发布包，未核验安装树、缓存及运行中包。后续只读读取镜像依赖manifest，再经授权隔离采集工具列表/握手。 |
| Zod/SDK运行结果 | F：固定依赖源码支持schema转换/剥离/协议行为；U：未启动固定包，需测试实际JSON Schema快照、Malformed envelope错误和缺items文本边界。 |
| 认证兼容与身份 | U：Python凭据token字段复制到Node；正确principal、refresh token/token过期形态及scope需受控验证，不读取/公布真实token。 |
| 后端精细语义 | U：空/嵌套PATCH、offset与IANA冲突、invalid maxResults服务端文案、sequence/etag时间粒度、get已删资源/实例墓碑、邀请副本权限、短页分布；需具体样例。 |
| 公共错误约定冲突 | 已处理：统筹逐行复核后更新 `shared.md` 的错误约定及 F09/F10/F11，保留该包 Unknown tool 的 isError 包装、retry helper 不检查 isError，并区分 lock 与实际运行版本。额外键投影与拒绝也不能统一，已建议公共验证明确依据实际 handler。 |
| 公共合成/验证对齐 | 已读 `synthesis-design.md`、`validation-plan.md` 初稿：共享事务/episode/回放机制与本设计一致。已提醒统筹，Calendar 真实差分需专用测试账号的 primary，不能靠次级日历 calendarId 参数隔离；公共主试点暂选 Sheets 不与本文 Calendar“候选”建议冲突。 |
| 当前轨迹缺口 | 当前检索无可用轨迹；初始化与评测源码是使用证据，不是成功运行证据。 |
| 交叉审查范围与结论 | 非原作者 `/root/wandb` 于 2026-09-10 使用 `gpt-6-astra / xhigh` 完成全文与固定包静态核对：S 文件 hash、5 工具名称/说明/schema/必填/默认/输出错误、primary/singleEvents/分页丢弃/缺 items、SDK 0.4.0 握手、官方排他时间窗/DST/recurrence、M/B/X、权限、LLM 三路线及独立 oracle 均有对应证据；未发现新增实质问题。原作者本轮已复读 `shared.md` F01–F28 与 `review-ledger.md` CAL-01。 |
| CAL-01/P3 处置 | 已修正 §2.2 update/list 输出模板的 4 处 JavaScript 逻辑或：为 Markdown 表格内的竖线逐一转义，保留渲染后的原表达式及业务含义；无接口或语义改动。自检全部表格列宽、10 节和 CSV 11 列通过，提交统筹登记闭环。 |
| 审查验证边界 | 本轮仅修文档并作静态格式检查，未重新抓取已核源码、启动 MCP 或执行业务操作。实际镜像/npx 解析、认证兼容、SDK 实际快照及精细时间/错误/墓碑/权限行为等原有 U 全部保留；交叉审查没有把这些项目变成运行通过。 |

## 10. 能力矩阵行

```csv
object,tool_or_capability,version,operation_type,state_dependencies,proposed_method,llm_role,fidelity_gap,verification_method,priority,evidence
google_calendar,create_event,@gongrzhe/server-calendar-autoauth-mcp@1.0.2,write,principal primary calendar event time ACL,deterministic MCP adapter and shared Calendar core,offline seed text only,server normalization and API error strings require differential records,contract snapshot and independent create-read invariants,P0,S:L96-L108 and L188-L204; package-lock.json:1688-1725
google_calendar,get_event,@gongrzhe/server-calendar-autoauth-mcp@1.0.2,read,event identity metadata ACL recurring instance,deterministic state renderer,no online LLM,deleted-resource and special-event fields need records,cross-process read and real API normalized differential,P0,S:L109-L111 and L206-L219
google_calendar,update_event,@gongrzhe/server-calendar-autoauth-mcp@1.0.2,write,event revision partial fields permissions,atomic PATCH semantics with source text renderer,no online LLM,empty and nested PATCH plus attendee-copy restrictions,omitted-field preservation and parallel-update histories,P0,S:L112-L125 and L221-L239; official events.patch
google_calendar,delete_event,@gongrzhe/server-calendar-autoauth-mcp@1.0.2,write,event tombstone series exception permission,transactional delete and retained tombstones,no online LLM,deleted get and repeated-delete distinctions require evidence,delete-read-list and series-instance differential,P0,S:L126-L128 and L241-L254; official API errors
google_calendar,list_events,@gongrzhe/server-calendar-autoauth-mcp@1.0.2,read,calendar range indexes timezone recurrence revision,deterministic overlap query and exact truncating wrapper,no online LLM,short pages and equal-sort-key order not fully specified,range-boundary and dense-calendar consistency,P0,S:L129-L134 and L256-L274; official events.list
google_calendar,existing recurring and all-day events,Calendar API v3 behind MCP 1.0.2,read/write,master exception originalStartTime timezone,rule library plus Calendar-specific instance state,offline background only,complex recurrence and DST behavior staged,official recurrence records and independent instance-set oracle,P1,S:L144-L145 and L264; official recurringevents
google_calendar,identity permissions and existing attendee attachments,Calendar API v3 behind MCP 1.0.2,read/write,principal scope organizer event copy Drive references,domain ACL checks and explicit cross-service identity map,offline descriptive content only,guest-copy rules and propagation need scoped profile,permission matrix and cross-service reference checks,P1,S:L17-L94 and L188-L274; official Event resource
google_calendar,initialization evaluation and future SDK HTTP,repository HEAD ef7ab592 plus MCP 1.0.2,read/write,episode shared persistent Calendar state,shared core with process routing and optional HTTP SDK adapters,none,current tasks use MCP only and broader SDK routes not validated,multi-process restart and cross-entry consistency,P0,tasks/finalpool/student-interview/preprocess/setup_calendar_events.py:47-169; evaluation/main.py:175-206; set-conf-cr-ddl/evaluation/main.py:55-96
google_calendar,protocol schema errors and authentication,SDK 0.4.0 Zod 3.25.76 converter 3.24.5,protocol/auth,version manifest credentials scope tool registration,source-compatible contract adapter and synthetic identity,none,running image and live error text unknown,initialize tools-list raw and model output snapshots,P0,package-lock.json:1707-1725 and 14748-14764; S:L95-L183 and L276-L299
google_calendar,LLM simulation comparison,design profile for MCP 1.0.2,simulation,explicit indexed state revision validated proposal,code baseline versus LLM proposal versus offline-content hybrid,controlled proposal experiment and seeded content,online LLM errors cost fallback and state truncation risk,independent oracle long-sequence leakage and cost benchmarks,P1,report sections 7 and 8
```
