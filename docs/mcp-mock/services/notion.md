# notion 高保真模拟可行性与设计

> 领域作者：`/root/notion`，创建时显式指定 `gpt-6-astra / xhigh`；非原作者审查者：`/root/github`，同为 `gpt-6-astra / xhigh`，2026-09-10 完成只读交叉审查，未发现实质修订问题，作者已登记接受，详见 §9 与 [N-01 审查台账](../review-ledger.md)。查阅日期：2026-09-10。仓库 HEAD：`ef7ab5928062defc0dc2a91a4c26ddebccb1a6a7`。已读原始需求、[共享约定](../shared.md)、统一模板、`docs/mcp-analysis.md`、合成设计与验证计划；适用 AGENTS.md 未发现。本文 F 为源码/官方资料事实，D 为设计，A 为规划假设，U 为待确认。仅文档与静态扫描；没有导入配置、连接账号、启动 MCP、业务初始化、真实写入、清理或 benchmark。

## 1. 范围、版本与入口

**结论（D）：首选保留固定 Notion MCP fork，以其现有 `BASE_URL` 接入本地 HTTP 状态服务；SDK、直接 HTTP 与必要浏览器入口共享同一领域状态。** 页面/块/数据库/评论的可检查状态适合代码主导，LLM 主要用于提前生成业务内容。普通 MCP 契约可精确冻结，但固定 schema 本身存在缺陷；完整 Notion UI、数据库公式/rollup、动态官方 MCP 与云端时间行为需要分期或补证据。不能把模拟 19 个 RPC 响应当成完整替代。

### 1.1 固定证据基线

| 层 | F/U 事实、版本与范围 | 证据 |
|---|---|---|
| M 普通 `notion` | `npx -y @notionhq/notion-mcp-server --page-id <allowed IDs>`，stdio，100 秒会话超时，缓存工具列表；Integration Bearer，`Notion-Version: 2022-06-28` | `configs/mcp_servers/notion.yaml:5-18` |
| 安装基线 | `package.json` 固定 `lockon-n/notion-mcp-server#43f117584206cee47d939207ddbe1ac02732f865`；该 fork 包版本为 `1.9.0`，提交比版本号更精确。上游为 makenotion，当前执行基线是第三方修改 fork | `package.json:24`；固定源 `package.json:9` |
| 可核对固定源码 | 本次只读源码位于 `/tmp/toolathlon-mcp-audit-xmv3srz8/notion`。下文 `S:` 均指该提交相对路径，可由[固定源码根](https://github.com/lockon-n/notion-mcp-server/tree/43f117584206cee47d939207ddbe1ac02732f865)重取，不能依赖临时目录永久存在 | [OpenAPI](https://github.com/lockon-n/notion-mcp-server/blob/43f117584206cee47d939207ddbe1ac02732f865/scripts/notion-openapi.json)、[parser](https://github.com/lockon-n/notion-mcp-server/blob/43f117584206cee47d939207ddbe1ac02732f865/src/openapi-mcp-server/openapi/parser.ts)、[proxy](https://github.com/lockon-n/notion-mcp-server/blob/43f117584206cee47d939207ddbe1ac02732f865/src/openapi-mcp-server/mcp/proxy.ts) |
| X 远程 `notion_official` | stdio `mcp-remote https://mcp.notion.com/mcp`，OAuth 状态目录 `./configs/.mcp-auth`。本次没有远程 tools/list 快照；**其完整工具集合、schema、资源/prompt、版本和实际权限均 U** | `configs/mcp_servers/notion_official.yaml:5-14` |
| X Python SDK | `notion-client==2.5.0` 锁基线；仓库依赖范围为 `>=2.5.0`。本机安装源码默认 API 头也是 2022-06-28，支持 `base_url`，但调用点只传 auth。不是 Notion 官方发布的 JS SDK | `pyproject.toml:86`；`uv.lock:2048-2056`；本机 `.venv/lib/python3.12/site-packages/notion_client/client.py:31-54,76-95`；[2.5.0 发布包](https://files.pythonhosted.org/packages/b6/8c/b2f11904e1ef7a33338d3890fc50d30ffa2d0fca51b01b0a827d909b615a/notion_client-2.5.0.tar.gz) |
| B API 与当前云服务 | 固定头不等于冻结后端时间。2025-09-03 将数据库容器与 data source 分开；旧头仍服务单数据源数据库，但多数据源可能使旧数据库操作失败、搜索遗漏。当前新参考页还包含 2026-03-11 行为，不能回填为旧 fork 已暴露能力 | [2025-09-03 迁移指南](https://developers.notion.com/guides/get-started/upgrade-guide-2025-09-03)、[FAQ](https://developers.notion.com/guides/get-started/upgrade-faqs-2025-09-03)、[版本说明](https://developers.notion.com/reference/versioning)，均查阅 2026-09-10 |

启动命令未内嵌提交，任务镜像解析结果未核验；本报告只确认安装基线，不声称已核实运行镜像。普通 MCP 后端默认是公网 `api.notion.com`；官方 MCP 是公网 `mcp.notion.com`；浏览器为公网 `app.notion.com`。附件外部 URL、依赖下载、agent 模型与仿真模型公网分别统计。`BASE_URL` 指向本地只能去除普通 MCP 的业务公网，不能自动覆盖其他入口。

为保持表格可读，后文短引用 `S:parser.ts`、`S:proxy.ts`、`S:page-access-control.ts`、`S:client/http-client.ts`、`S:notion-openapi.json` 分别展开为固定源码的 `src/openapi-mcp-server/openapi/parser.ts`、`src/openapi-mcp-server/mcp/proxy.ts`、`src/openapi-mcp-server/auth/page-access-control.ts`、`src/openapi-mcp-server/client/http-client.ts`、`scripts/notion-openapi.json`。仓库内短文件名 `notion_page_duplicator.py` 等指 `utils/app_specific/notion/`，任务路径另按表下注释展开。

### 1.2 仓库真实调用路径与当前案例

F：扫描 `tasks/finalpool/*/task_config.json` 的 JSON，声明 `notion` 的完整 8 项为下表。声明与初始化/评测源码证明路径需求，**没有可用工具轨迹证明某一 agent 实际调用过某工具**。本轮公共扫描未发现可直接分析的 dump，本领域另查任务/工具源而未获取远程日志。

| 当前任务 | Notion 与跨服务行为线索 | 初始化/评测证据 |
|---|---|---|
| `experiments-recordings` | W&B 实验记录→Notion 数据库；评测直接 HTTP 查询数据库并对比实验行 | `preprocess/main.py:39`；`evaluation/main.py:194-218,258-299` |
| `notion-find-job` | 招聘网站/地图/邮件→Job Tracker 数据库；按页面标题及父页面定位，查询/块读取有分页 | `preprocess/main.py:29`；`evaluation/check_remote.py:7-47,49-99,415-468` |
| `notion-hr` | 本地文件/PDF/邮件→Candidates 数据库；评测调用 `utils/app_specific/notion/ops.py` | `preprocess/main.py:31`；`evaluation/main.py:232-272` |
| `notion-movies` | 浏览器/抓取→电影页面和数据库；评测直接 search、blocks、pages、database query | `preprocess/main.py:28`；`evaluation/check_remote.py:25-75,135-167,338-412` |
| `notion-personal-website` | Word/文件→页面长文本；评测读 Page/Block 并提取章节 | `preprocess/main.py:26`；`evaluation/check_remote.py:18,313-329` |
| `oil-price` | Yahoo Finance/文件→页面及分析数据库；直接 HTTP 读取/分页查询，返回浏览器 URL | `preprocess/main.py:28`；`evaluation/main.py:15-34,143-168,975-999` |
| `quantitative-financial-analysis` | Google Sheet URL 和评论写入 Notion；评测直连 comments/blocks 并继续读取 Sheet | `preprocess/main.py:57`；`evaluation/check_content.py:19-47,144-170` |
| `task-tracker` | GitHub/Notion 任务同步；评测用 Python SDK 取 child_database、分页 query，与本地表格比较 | `preprocess/main.py:80-98`；`evaluation/main.py:127-198` |

表内任务相对路径均在 `tasks/finalpool/<任务>/`。任务成员依据各 `task_config.json` 的 `needed_mcp_servers`；不能将上述调用需求解释为固定 schema 均可成功表达。

必须共享状态的额外入口（F→D）：

1. **初始化**：`notion_remove_and_duplicate.py:22-45` 先删除目标父页下同名子页，再复制源页。删除器实际 GET 分页块并 `DELETE /v1/blocks/{page_id}`（`notion_remove_page.py:26-53,55-98`），提示语中的“永久删除”不能代替 API 的归档/回收站语义。
2. **SDK**：复制器 `Client(auth=...)`，列源页子块、读取 Page、改标题（`notion_page_duplicator.py:127,157-180,203-225`）；评测也构造独立 SDK client。替换 MCP 进程不会拦截它们。源页查询只读一页，不能为适配这种限制让模拟端偷偷返回全部数据。
3. **远程 duplicate/move**：代码请求 `notion-duplicate-page({page_id})`，读取文本 JSON 的 `page_id`；用 SDK 轮询可读性；再调用 `notion-move-pages({page_or_database_ids:[id],new_parent:{page_id}})` 并期待 `result` 以 `Success` 开头（`notion_page_duplicator.py:535-637`）。这只证明**调用者期待**两种契约，不是远程完整快照或成功运行证据。两者作为 X 适配需求，不能混入普通 19 工具清单。
4. **Playwright**：开关 `notion_preprocess_with_playwright` 选择复制路径（`notion_page_duplicator.py:107,679-683`）；浏览器使用 storage state，点 Duplicate/Move to，并取目标标题首个匹配（同文件 `277-343,471-499`），远程 MCP 则按父 ID 移动。状态一致也不能保证 UI 标题选择等价。当前 Notion 评测主体是 SDK/HTTP，未发现独立 Notion UI 评分器；浏览器仍承担初始化，部分任务还向 agent 开放通用 Playwright。
5. **URL/保护**：`urls.py:6-22` 将浏览器别名规范到 `https://app.notion.com`，保留 path/query/fragment，不改 `api.notion.com`、`mcp.notion.com`、`notion.site`。`NotionPageProtector` 只约束显式经过它的操作（`notion_page_protector.py:72-86,92-145,153-205`）；复制器改名/移动有调用，直接 `requests`、任意浏览器或普通 MCP 不受这个 Python 类全局拦截。它与 fork 的 `--page-id` 限制、后端 ACL 是三种边界。
6. **认证持久化**：`.mcp-auth` 是宿主读写 bind（`scripts/run_single_containerized.sh:317-327`）；复制器 flock 序列化官方 MCP 生命周期（`notion_page_duplicator.py:60-98,543-545,638-639`）。这不提供 episode 数据隔离。现有真实 Notion 工作流继续遵循串行约束；本文模拟后端的并发设计不授权真实任务并发。

## 2. 工具与能力清单

### 2.1 原始工具契约与完整 19 项

F：以下从固定 `S:scripts/notion-openapi.json` 的全部操作和 converter 推导。原始工具名为 `API-<operationId>`，最终描述是 `Notion | <表中英文>`（`S:src/openapi-mcp-server/openapi/parser.ts:171-196,519-523`），没有把长 API 文档塞入顶层说明。模型在本仓库看到 `notion_API_<operationId 中横线改下划线>`，dispatch 仍用原名；例如 `notion_API_post_database_query`。命名转换见 `utils/openai_agents_monkey_patch/tool_name_aliases.py:21-28,85-99`。

表中 `!` 为 required，未标记为可选；`s/i/b/o/a` 分别是 string/integer/boolean/object/array；`=100` 指 schema 注解默认值，不是已经验证省略参数时 wrapper 会注入。所有工具 input 根为 object，路径/查询与 JSON body 属性展平至同一层；`$defs` 为空。嵌套完整 schema 以固定源指定区间为准，缺陷在 2.2 明示。输出栏是 HTTP 业务对象/列表形状，**19 项均没有公开 MCP outputSchema**。L(T) 指 `{object:'list',results:T[],has_more,next_cursor,...}`；分页 property item 还有类型专属字段，不能都变成简单数组。

| 原始工具名 | 精确说明后缀 | 输入与关键限制 | 业务输出；属性 | 已有路径/未来价值；状态依赖 | 固定 spec 行 |
|---|---|---|---|---|---|
| `API-get-user` | Retrieve a user | `user_id!:s(uuid)` | User；读 | 当前工具调用 U；身份识别/提及/people；用户与可见字段 | 36-78 |
| `API-get-users` | List all users | `start_cursor:s,page_size:i=100` | L(User)；读 | 当前 U；协作成员选择/消歧；workspace 成员与权限 | 85-121 |
| `API-get-self` | Retrieve your token's bot user | 无参数 | bot User/owner；读 | 当前 U；凭据身份诊断；integration principal | 130-214 |
| `API-post-database-query` | Query a database | `database_id!:s,filter_properties:a[s],filter:o,sorts:a[{property!,direction!∈ascending/descending}],start_cursor:s,page_size:i=100,archived:b,in_trash:b` | L(Page，wiki 情形可含 Database)；读 | 多任务评测对应路径；复杂条件检索/批改定位；属性类型/ACL/索引 | 221-844 |
| `API-post-search` | Search by title | `query:s,sort:{direction:s,timestamp:s},filter:{value:s,property:s},start_cursor:s,page_size:i=100`；说明限制 sort timestamp 为 last_edited_time、filter object 为 page/database，但这些未编码 enum | L(Page/Database)；读 | 页面/数据库发现；名称消歧，不能全文内容检索；ACL/标题索引 | 850-908 |
| `API-get-block-children` | Retrieve block children | `block_id!:s,start_cursor:s,page_size:i=100` | L(Block)；读 | 初始化及多评测；树遍历/长内容分页；有序子列表 | 914-945 |
| `API-patch-block-children` | Append block children | `block_id!:s,children!:a[object],after:s`；子项只列 paragraph、bulleted_list_item；`type` enum 同二者，rich_text 子型仅 text，嵌套对象关闭 extra keys | L(新 Block)；写 | 内容编辑用例；增量/指定位置插入；父可写、顺序、附件/文本 | 951-1109 |
| `API-retrieve-a-block` | Retrieve a block | `block_id!:s` | Block；读 | 树遍历/定位写入对象；type、parent、has_children | 1115-1128 |
| `API-update-a-block` | Update a block | `block_id!:s,type:o,archived:b=true`；`type` object 不是正常块类型键，见 2.2 | Block；写 | 编辑/恢复案例；类型不可随便切换、原内容 | 1134-1168 |
| `API-delete-a-block` | Delete a block | `block_id!:s` | 归档/回收站 Block；写 | 初始化删除同名子页；归档后恢复/引用行为；树与软删除 | 1174-1189 |
| `API-retrieve-a-page` | Retrieve a page | `page_id!:s,filter_properties:s`，后者与 database query 的数组类型不同 | Page；读 | SDK/HTTP 多入口读取；不能代替取整棵 Block 树；属性/parent/ACL | 1195-1216 |
| `API-patch-page` | Update page properties | `page_id!:s,properties:o,in_trash:b=false,archived:b,icon:o,cover:o`；properties 如传则必须 title 数组，仅可含 title/type；icon 只 emoji，cover 只 external.url | Page；写 | 更新页面/数据库行需求；属性类型与只读派生字段；schema 窄化见 2.2 | 1222-1358 |
| `API-post-page` | Create a page | `parent!:{page_id!:s(uuid)},properties!:{title!:a,type?:'title'},children:a[s],icon:s(format json),cover:s(format json)` | Page；写 | 创建文档/记录的迁移价值高，但当前描述不能完整表达数据库行；父与属性 schema | 1364-1451 |
| `API-create-a-database` | Create a database | `parent!:{type!:'page_id',page_id!:uuid},properties!:o,title:a[rich text]`；每个属性定义 oneOf 只有 title 类型，可带 description | Database；写 | 新项目/结构设计；唯一 title 类型、属性 ID、页父 | 1457-1581 |
| `API-update-a-database` | Update a database | `database_id!:s,title:a,description:a,properties:o`；properties 仅显式列 name:s，其 extra keys 默认宽松 | Database；写 | schema 演进/改名/后续查询；属性 ID 稳定与值迁移 | 1587-1712 |
| `API-retrieve-a-database` | Retrieve a database | `database_id!:s` | Database/schema；读 | 评测及未来类型发现；不是数据库行列表 | 1718-1746 |
| `API-retrieve-a-page-property` | Retrieve a page property item | `page_id!:s,property_id!:s,page_size:i,start_cursor:s`；说明默认 100，schema 无 default | PropertyItem 或分页 PropertyItem 列表；读 | 当前 U；完整读取大型 relation/rich_text/rollup；编码后的属性 ID | 1752-1812 |
| `API-retrieve-a-comment` | Retrieve comments | `block_id!:s,start_cursor:s,page_size:i`，说明最大 100；schema 无 default | L(Comment)，原 description 限 unresolved；读 | financial-analysis 评测；批注讨论/审核；discussion 与 ACL | 1818-1861 |
| `API-create-a-comment` | Create comment | `parent!:{page_id!:s},rich_text!:a[{text!:{content!:s}}]`；无显式 discussion_id | Comment；写 | financial-analysis 评论写入需求；未来审阅工作流；用户/父页/评论能力 | 1867-1933 |

当前路径标记只代表对应领域/HTTP/SDK 使用，不假称 tool name 有运行覆盖。未来能力价值不是依据 finalpool 调用频次排序。数据库的复杂属性、所有可读 block 类型与分页必须进入长期 B 层；不能因为 wrapper 只在 append schema 列两种块，就把已有 heading、table、to_do、嵌套页、附件读成 paragraph。

### 2.2 schema、输出与错误中影响 agent 的差异

F：converter 复制 `type/format/description/enum/default/required/additionalProperties/items/oneOf/anyOf/allOf`，**未传播 `minimum/maximum/minLength/maxLength/minItems/maxItems`**；body 根 `additionalProperties` 也不随展平复制到 input 根（`S:parser.ts:96-163,370-431`）。所以“文档最大 100”不等于 tools/list 中有 `maximum:100`。内部构造的错误说明随后被 summary 覆盖（同文件 `184-189,433-446`）。需要分别存原 OpenAPI、生成 schema、harness 最终 schema；不能自行补强后仍宣称字节级兼容。

F：固定 schema 存在实质矛盾：page create 的 children 是 string[]，icon/cover 是 JSON 格式字符串，properties 却只接受 title 数组；append 仅两种 block；update block 使用 `type:object` 而非 paragraph 等键；query filter 的 `or/and` 写在 schema 的 properties 之外，converter 因而只产宽 object。业务数据库行的真实 `properties:{字段:{类型:值}}` 与这些声明并不等价。wrapper 没有显式按工具 schema 校验每次 arguments，而是将参数送往 HTTP；harness 还有字符串参数修复（`utils/openai_agents_monkey_patch/custom_mcp_util.py:159-177`），**不能由此断言所有不符合 schema 的参数必被拒绝，或全部可绕过而成功**。这需要后续不联网契约执行和受控后端差分。D：设置 `fork-43f1175-contract` 与明确升级后的 `revised-contract` 两个 profile；后者必须换版本清单和标签，禁止无声修正、固定正确答案或偷偷替 agent 改合法参数。

F：`S:proxy.ts:41,74-90` 只宣告 `tools:{}`，工具列表一页返回全部 19 项，仅 name/description/inputSchema；没有 resources、prompts、订阅或输出 schema 注册，没有 readOnly/destructive annotations。converter 虽算 `returnSchema`，proxy 丢弃它。OpenAPI 多数 response 为空或仅示例，只有少数用户响应有 schema；`retrieve-a-page-property` 例文甚至含非有效 JSON 示意，不能复制为黄金响应。普通 profile 的资源/prompt 能力为未暴露，远程官方 profile 则 U。fork 同时有 stdio 和有认证的 Streamable HTTP/session 实现（`S:scripts/start-server.ts:21-23,92-106,154-243`），本仓库只启用 stdio；不要把 HTTP token 当成 Notion integration token。

| 错误层 | 已核实表示与调用行为 | 设计与验证 |
|---|---|---|
| HTTP 成功 | 一项 `{type:'text',text:JSON.stringify(response.data)}`；状态码/header 不进入模型文本；无 structuredContent/isError | 保留文本 JSON，不替换成顶层业务 object；分页/User/Page 等具体字段需补输出黄金记录 |
| HTTP 业务错误 | HttpClientError 保存 HTTP status/body/headers；proxy 文本为 `{status:'error',...data}`，若真实 body 已有数值 status，会覆盖字符串；**没有 `isError:true`** | 验证 code/message/status/request_id（若真实有）与 SDK/HTTP 对应；不能统一改成其他服务错误包装 |
| fork 页限制拒绝 | 一项文本 JSON，含 `status:'error',error:'Access denied',message,details`，同样无 isError | 与后端 403/404 区分；请求可能在远程 HTTP 操作前被拒绝 |
| unknown tool / 非 HTTP 异常 | 找不到 operation 在 try 外 `throw Error('Method ... not found')`；其他异常重抛 | 需 MCP SDK 版本下的原始 JSON-RPC 录制；源码不足以确定最终错误 code；不得编造普通 Notion error body |
| 后端非法参数/权限/限流 | 当前官方列 400 validation_error/missing_version、401 unauthorized、403 restricted_resource、404 object_not_found、409 conflict_error、429 rate_limited、5xx 等；404 也可表示未分享 | 按 API/backend profile 固定响应和权限条件；精确措辞 U，不用 success/空列表掩盖错误 |

前四行证据：`S:src/openapi-mcp-server/client/http-client.ts:104-165,173-189`、`S:proxy.ts:94-155`。后端错误依据[官方状态码](https://developers.notion.com/reference/status-codes)（当前文档，查阅 2026-09-10），不是 2022 年历史错误快照。harness 将 content 项再次 JSON 序列化且超长落盘（`custom_mcp_util.py:176-229`）；原始 MCP、模型看到的双层文本和落盘完整内容都要检查。

F：初始化公用 `call_tool_with_retry` 只捕获异常重试，收到正常 CallToolResult 会直接返回（`utils/mcp/tool_servers.py:453-486`）。因此普通 Notion 的文本业务错误不会靠这一层自动恢复；“调用未抛异常”不能计为成功。HTTP Retry-After header 在 proxy 包装时也未转交给模型，后端 body 若包含重试信息则仍可见。

### 2.3 身份与 `--page-id` 的真实边界

F：工具可见性不随页 allowlist 减少，限制发生在调用时。`S:auth/page-access-control.ts:112-145,150-188,191-375` 尝试按 page/database/block 解析父链并缓存允许/拒绝；`clearCache()` 仅定义，未见调用。目标抽取仅覆盖 pages、blocks、database query、page create（同文件 `381-408`）。**search/users、database retrieve/update/create、comments 未抽到目标，proxy 放行**（`S:proxy.ts:169-179`）。这不代表后端 ACL 也放行，更不保证 allowlist 外资源都不可见；模拟需保留两层判断。关系/mention 指向的其他资源也需后端能力验证，不能只校验主 page_id。

D：未移动资源时可复现当前 fork 缓存；跨 X 移动/权限变化后缓存 stale 是独立兼容反例。修复 profile 用带 ancestor/ACL version 的缓存，不把修复归给旧版本。用于大规模隔离的 episode ACL 必须在更下层强制生效；fork 的不完整页面过滤不得被当作多租户隔离。`--page-url` URL 解析只匹配末尾 UUID，query/fragment 情况与 Python URL helper 不同（`S:page-access-control.ts:74-99`）；主配置使用 page-id，但未来配置组合应覆盖。

## 3. 领域状态模型

D：本地服务维护 Notion 专属资源图，不把 Page、Block 和 Database 三者压成一张无类型 JSON 表。核心实体可存关系表加受约束 JSON，blob 独立存储；所有键包含 episode/generation，真实暴露的 ID 保持 Notion 形状。

| 实体 | 持久化字段/关系及主要不变量 | 派生、历史与入口 |
|---|---|---|
| Workspace / Principal / Integration | workspace ID、person/bot、owner、成员可见性、read/insert/update content、read/insert comments、用户信息能力；资源分享/grant | MCP integration、SDK evaluation key 与 OAuth user 分开映射，不能默认同权；用户的 email/avatar 缺省按能力 |
| Page | UUID、parent 类型及 ID、typed properties、icon/cover、归档/回收站状态、created/edited 时间与用户 | Page retrieve 不包含完整正文；正文从 page ID 的 block children 读取；URL 与 ID 有可逆映射，改名不换 ID |
| Block 与有序边 | UUID、block type/type payload、parent、sibling order、rich_text、has_children、软删除/来源链接 | 页/child_page/child_database 的 ID 与对应实体衔接；有序树无环，链接/mention 是引用而非父边；删除/恢复不得随机重建 ID |
| Database（旧头视图） | UUID、父页、title/description、is_inline、属性 schema、property ID/name/type、options、schema revision | 行是 Page；重命名字段保持属性 ID，query 与 Page properties 按同一 schema；新 multi-source 内部可显式标记，旧头按证据返回失败而非混合两个表 |
| PropertyValue / Relation | title/rich_text、number、select/multi_select/status、date、people、checkbox、URL/email/phone、files、relation；保留 null 与空集差别 | relation 双向联动按 schema；公式/rollup/created/edited 类型为服务派生且不可任意写；属性 ID 不必 UUID，可 URL 编码，不能用显示名充当永久 ID |
| Comment / Discussion | comment ID、parent block/page、discussion ID、creator/times、rich_text、resolved 状态（读取可见性所需） | 当前普通 MCP 仅创建页评论和读 unresolved；没有编辑/删除/resolve 工具，不伪造它们；discussion reply 等 B/X profile 另核验 |
| File / Media | external URL 或托管文件引用、mime、filename、字节 hash/size、签名 URL 有效期、资源 ACL | bytes 一致性由 blob 保证；URL 元数据与下载结果不能各造一份。旧 M 无上传工具；UI 初始化可带托管文件，SDK 2.5.0 虽有 file_uploads 端点但当前调用未使用，不能据此宣布 M 暴露上传 |
| Index / Visibility event / Quota | 标题与属性索引、索引水位、虚拟时间、operation receipt、workspace/connection 配额 | direct retrieve 与 search 索引可暂不一致，但必须追溯真实已存在资源；写提交版本与索引可见版本分开 |

F→D：富文本保留 text/mention/equation 的类型、annotations、link/href、plain_text 和目标引用；plain_text 是投影，不能替换原 rich_text。旧 M 可读复杂内容的范围大于可创建 schema。外部附件与托管签名 URL 是不同生命周期；当前[File 对象文档](https://developers.notion.com/reference/file-object)区分 external/file/file_upload（查阅 2026-09-10），最后一种不能加入固定 M 工具清单。期满 URL 应失败/刷新，但引用对象本身不消失；外部 URL 不会自动成为 Notion 托管字节。

D：内部记录 commit revision/event log 支持快照和恢复；**不把内部版本号、历史查询或 ETag 前置条件暴露成固定 MCP 原本没有的功能**。同一字段并发写、不同字段合并、归档祖先影响孩子、relation 对删除引用的表现都先用真实受控记录确定，不预设所有 PATCH 原子合并或乐观锁冲突。可接受先限定顺序执行的 profile，同时保留完整并发缺口。

F→D：旧 database query 支持 typed filter 和多重排序，返回可能少于 page_size，wiki database 可含数据库，默认不含 archived（[旧版 query 参考](https://developers.notion.com/reference/post-database-query)，明确标 up to 2022-06-28，查阅 2026-09-10）。不将它实现成字符串全文检索/任意 SQL。排序 tie、null、日期仅日期与带时区时间的边界需独立样例；relation/rollup 和公式不是把 JSON 字段直接相加。查询表达式用专用 AST/typed evaluator，持久化层 SQL 只作执行手段。

F→D：search 按标题、索引不是完整 workspace 枚举，索引有延迟（[搜索限制](https://developers.notion.com/reference/search-optimizations-and-limitations)，查阅 2026-09-10）。确定性 profile 可选择记录化的可见事件和延迟分布，但不得为了可复现发明固定“第三次搜索必出现”；分页 cursor 绑定主体、查询/profile/episode 及可见水位。后端分页稳定性与索引更新的真实承诺 U，静态状态下必须不重不漏，动态状态下按录制契约比较。

F→D：当前[请求限制](https://developers.notion.com/reference/request-limits)（查阅 2026-09-10）已是按套餐的连接预算加 workspace 配额，且存在 529 与 Retry-After；不能硬编码旧“总是 3 req/s”。尺寸约束包括单段 text.content 2000 字符、请求 1000 block 元素/500KB 等；追加 block 的每次 100 个、两层嵌套与旧 `after` 字段对照[追加接口当前文档](https://developers.notion.com/reference/patch-block-children)及固定 spec。限制值需进入有日期的 backend profile，字符/字节边界分开测试；当前接口新增 position 不能倒灌旧 schema。配额与索引事件持久化用于恢复，网络真实等待可映射虚拟时间，不牺牲错误发生条件。

## 4. 代表性交互序列

以下为 D，不按某条现成轨迹编码。每个序列在不同 seed、顺序和入口执行；具体调用必须符合该 profile，旧 schema 无法表达的操作留作 X/revised profile，不能假装普通 MCP 全支持。

| 序列 | 关键步骤与变化 | 独立状态断言 |
|---|---|---|
| 文档生命周期 | 创建页→追加两批文本→直接读与分页遍历→改名→归档→恢复；交换两次独立字段操作顺序 | ID 稳定；正文与元数据分别可读；拼接内容/顺序准确；不把 delete 当硬删；无关兄弟未变 |
| 分页后批改 | 在 0/1/99/100/101/多页数据库中 query filter/sort→按 property item 读取完整关系→逐行 PATCH→重新 query；改变 page_size 与按不同合法顺序写 | 静态 query 无漏/重；新集合与已提交属性吻合；PATCH 未指定字段不被清空；跨页操作不是服务未承诺的总事务 |
| 身份和错误恢复 | bot 无页面分享→404；有分享无 update 能力→403；切换到预先存在的有权 principal→成功；字段/父类型错误后 agent 自行修参 | 失败无变更、无资源幻觉；错误权限层正确；模拟器不自动分享、不主动提示私有目标 ID |
| 同一资源跨入口 | SDK 创建/改标题→MCP retrieve/search；MCP append→HTTP children；HTTP 归档→SDK query；旧 fork allowlist 缓存前后对照 | 都映射同一 page/block ID 与版本；模型/初始化/评测凭据能看到不同投影；缓存误差有明确 profile 标签 |
| 层级移动与复制 | X 复制带数据库/嵌套页/附件的页→SDK 轮询→按 ID 移到新父→浏览器按同名父标题选择另一候选的对照 | copy 是新 ID 图且原图未变，move 保留资源 ID；内部/外部 relation 和 synced 引用按待确认复制规则；不能以“Success”代替终态 |
| 评论与外部资源 | Sheet 生成可访问 URL→Notion 写链接与评论→GET comments→不同 principal 读链接并下载/读 Sheet；替换为受限 URL | Notion 存 URL 不意味着共享了 Sheet；Sheet ACL 独立；comment body 与 parent/creator准确，无自动撰写内容 |
| 搜索与时间 | 新页直接读成功→搜索暂未出现→推进虚拟时间→重新分页；期间改名、撤销分享、注入429 | 已存在与可检索分开；结果可追溯同一版本；撤销权限不靠 stale index 泄漏；限流重试不产生重复非幂等创建 |
| 长内容和附件 | 多语言 rich_text/mention/公式文本与合法长树→跨多次追加；2001 字符段被拒→由 agent 分段；托管附件 URL 到期再 retrieve | 拒绝操作无静默截断；全文 hash/annotations 不漂移；相同 attachment hash，URL 可变；下载失败与空文件区分 |

需要真实页面复制语义、归档引用、UI 重名顺序的序列暂为 U 依赖测试；没有远程动态快照时先在命名明确的 X 设计 profile 评审，不能纳入“固定官方 MCP 已兼容”指标。

## 5. 候选实现与推荐

各维度 I/S/C/T/D/P 采用共享标准，下面是可达到的目标而非实测。成本使用相对量级，未做工时或吞吐测量。

| 方案 | I 接口 | S/C 语义与一致性 | T/D/P | 开发/长期成本与取舍 |
|---|---|---|---|---|
| **保留固定 MCP + 本地 Notion HTTP 后端（首选）** | name/schema/说明/错误包装由原代码保留 | 自写 typed 资源图；SDK/HTTP 可共用，API 语义仍要实现 | ACL/虚拟时间可检查；LLM 预生成内容；每调用无必需模型开销 | 中高开发、低在线成本；源已有 BASE_URL，减少 wrapper 漂移；不能覆盖官方远程与 UI 本身 |
| 有状态 MCP 替代实现 | 可由固定清单生成，但包装/缓存需重写 | 不补 HTTP 则 X 层断裂 | 易多租户扩展；状态规则不能省 | 作为轻量离线工具训练备选；必须同时提供 HTTP adapter 才可声明仓库级替代 |
| SDK/client adapter | 保留 SDK 用户侧类型和异常较容易 | 共享同一后端，不能逐函数各放 fixture | 需区分 SDK 默认重试/headers | 适合额外路由，不宜独立作为全部模拟器；绕过真实序列化会漏 HTTP 错误/分页 |
| 浏览器本地 UI/API adapter | 页面结构与网络可接同状态 | 能支持复制/移动，但 DOM、选择器、交互时间远比 API 难 | 数据多样会扩大 UI 分支；浏览器成本高 | 分期提供明确 UI profile；只做初始化语义 adapter 的 profile 不声明 Playwright 可直接跑通 |
| Baserow 等现成本地表格服务 | **不是 Notion API** | 可复用行/列持久化，缺 Page/Block/rich_text/Notion relation/ACL/返回类型 | 有自己的 UI/权限/分页语义 | 适配面可能大于定制存储；不是首选 |
| PostgreSQL/SQLite + blob | 仅存储，无 MCP/API 兼容性 | 事务/索引有用，Notion typed query/树/版本规则自写 | episode 隔离/快照适用 | 作为首选底座，不能声称数据库引擎替代 Notion 服务 |
| fixture/回放 | 已录字段可精确 | 跨顺序写后读、没录的合法组合不足 | 廉价；数据和状态分布窄 | 仅契约/差分黄金记录、初始化 seed 基础，不能当主要交互模型 |
| LLM 主导在线仿真 | schema可约束但详细输出易漂移 | 显式状态+独立 validator 仍必需；大树与查询完整性难 | 长上下文/多并发高延迟成本 | 可做限定实验，不作为默认；开发快的收益会被验证器和长期调用成本抵消 |
| **代码在线 + LLM 初始化/有限提案（推荐组合）** | 沿用精确契约 | 提案经 typed validator、ACL、read-set version校验，再从提交态渲染 | 多样文本有效；确定性快速路径稳定 | 文本复用摊销成本；初期与纯代码同保真门槛比较收益 |

F：替换点是 `S:scripts/start-server.ts:14-16` 读取 BASE_URL，`S:src/init-server.ts:30-33` 替换 OpenAPI server URL，`S:client/http-client.ts:36-49` 用该地址。SDK 2.5.0 同样支持 base_url（上文版本证据），但 `utils/app_specific` 和任务评测多处硬编码 HTTPS URL。D：后续实现可注入独立 adapter/endpoint 设置或限定环境代理路由；仅设置 MCP env 不足。本阶段不改这些调用点。所有路由须保留请求方法、query重复参数、URL编码、响应status/body/header与真实异常类型。

F：核对的 Baserow 官方[数据库 API](https://baserow.io/user-docs/database-api)与[后端 API](https://baserow.io/docs/apis/rest-api)（当前文档，版本未固定，查阅 2026-09-10）暴露 `/api/database/rows/table/{table_id}/`、自有 table/field IDs、Token auth、表权限与分页；不提供 Notion `/v1/pages`/Block API 的兼容承诺。该候选仅是部分结构化数据底座，无需为了产品相似额外引入同步系统。未找到并核实能完整代替固定 fork+SDK+UI 的现成 Notion 模拟器；这是一项检索证据限制，不是证明不存在此产品。

## 6. 保真缺口与取舍

| 能力 | 目标等级/阶段 | 若简化会学到的错误规律 | 降低偏差与验证 |
|---|---|---|---|
| 19 工具名称/说明/input/包装 | I 可按源码精确；输出业务 schema 部分 U | 不同参数名/类型、错误始终 isError 或 JSON object | 固定三层 schema 快照与原始协议黄金记录；先保持旧缺陷标签，再独立修订 profile |
| 普通 Page/Block/Comment 基本转移 | S/C 限定类型可准确实现 | “创建=随便返回 ID”“正文跟随 retrieve page 全给”“评论自带推荐答案” | 独立 ID/树/字节/属性审计，mutate错误响应与终态做反例 |
| Page/Database property 语义与查询 | 高价值且必须优先，复杂部分分期 | 混淆 null/空值，字符串数值排序，只有title一种属性，任意过滤条件都接受 | typed query AST、手算小例与真实 differential；保持旧 wire schema窄化和B支持范围不同 |
| 公式/rollup/关系深层组合 | S 分期，表达式全集与服务限制 U | LLM 把统计“算得像”，跨页关系更新不影响派生结果 | 开始只发布已核实函数/类型集合；依赖图增量计算；不支持明确报模拟扩展错误，不返0/空串冒充结果 |
| 完整 block 类型/嵌套结构 | 读取须广；复杂写入口分期 | 把所有块降成 plain text，丢 checkboxes/table/mention | typed payload与lossless存储；未支持渲染不改原状态；長树 hash 和 round trip |
| 归档/回收站/恢复/引用 | 核心优先；引用/祖先继承细节 U | delete 后永久失联或恢复成新 ID，引用自动删除 | 原对象与墓碑分离，受控差分决定恢复/查询可见性；不从删除脚本提示语推语义 |
| 认证能力/分享/页面根限制 | T 两层可建模；fork覆盖缺陷可复现 | token全权、page-id=全局防护、同名=同一页 | 多principal权限矩阵、allowlist漏路由样例、跨入口缓存失效；episode隔离独立强制 |
| 分页/搜索/索引 | 静态集合准确；动态排序/索引延迟近似 | 第一页就是全集、search立即完整、cursor可跨查询复用 | 0/100/101边界、变page_size和顺序；索引事件记录；不能迎合现有评测漏分页 |
| 托管/外部附件 | bytes/metadata/ACL可准确；签名URL时效近似 | URL存在=下载成功，外部链接自动共享/永久可用 | blob hash、过期时钟、跨服务ACL、下载错误矩阵；无原始 bytes 时不可伪造附件内容 |
| 官方远程 MCP | U，先冻结账号工具快照 | 把代码期待的两个名当全部工具，拿旧OpenAPI替新官方服务 | 记录完整 tools/list所有页/schema/hash/权限/日期；再设计所有已暴露能力 |
| Playwright完整UI | 成本高，后期独立profile | 标题查找总命中目标、复制即完成、DOM永不变化 | 独立浏览器契约/截图/选择器和状态比对；未实现UI不得宣传全仓库无需修改运行 |
| 历史版本/并发/重复写/限流 | 内部历史可精确；服务冲突策略U，时间近似 | 所有重试幂等、所有 PATCH有版本冲突、429固定等一秒 | 按真实接口注入故障，原响应收据回放与新调用重试区分；云政策另dated profile |

D：可迁移优先级不是“先让8题过”，而是完成 typed 数据库属性+页块关系+分页/查询+权限/错误+HTTP共态，之后扩展复杂属性和多入口。只实现纯文本 CRUD 虽易快，却会系统性削弱跨工具状态推理能力。

## 7. LLM 仿真可行性

### 7.1 职责与路线

D：**推荐代码主导在线语义，混合初始数据生成；不推荐把每次读取/编辑交给 LLM 自由模拟。** Notion 的价值在真实且多样的业务内容，但读取、写入、排序、权限和引用主要是可检验事实。

| 能力 | LLM 可做 | 必须由确定性组件/外部证据决定 |
|---|---|---|
| 初态内容 | 生成多语言会议记录、项目文档、招聘/CRM/研究材料、合理干扰段落、模板组合 | ID/parent/typed values/ACL/时间/附件bytes/关系约束；不得编码答案与预期调用顺序 |
| 合法创建/修改 | 在实验组提出对现有参数的受限状态patch，辅助处理已核实支持的复杂结构投影 | 不得润色或补全 agent 未要求写入的正文；必需字段缺失不能代填；原输入文本保持字节/规范约定一致 |
| 读取/查询/排序/分页 | 可试验受限JSON投影提案，但必须逐字段证明源于状态，通常无经济性 | 完整候选集、比较/过滤/排序、cursor、属性派生，负查询证据；不允许“看起来可能存在”的页 |
| 自然语言响应 | 仅仿真原接口本来提供的自由内容；普通19工具主要返回资源 JSON，几乎没有需要在线创作的服务行为 | HTTP code/message模板与已提交内容；不额外提示如何完成任务 |
| 公式/rollup/身份/文件/并发 | 可做离线规则研究或测试数据提案 | 真实执行/typed evaluator、ACL、hash、原子事务、合法状态图；不能因为难实现转给模型猜答案 |

纯代码开发要实现领域规则和内容生成模板；LLM 主导减少初期分支编码，但为保证完整查询、图结构、事务正确，仍需近似同规模的验证器。混合收益最明确在内容/分布多样化，而非让模型重复输出大段已有 JSON。

### 7.2 有限在线 LLM 的一致性设计

D：`工具请求 + 已鉴权read-set → 检索相关状态 → LLM给出结构化patch/输出提案 → schema与业务校验 → 带版本的原子提交 → 由提交态渲染响应`。

检索粒度为 page/block 子树切片、database schema+匹配候选索引、comment discussion、ancestor ACL、文件引用；调用只读100个子项时不传整个workspace，合法全树要求多次确定性遍历。查询无结果必须由完整查询执行器证明，不能因摘要没出现就断言不存在。长文档保留 blob/chunk 引用和内容hash，LLM摘要只能帮助路由，不能成为被返回或覆盖的权威内容。结构元数据和真正涉及写入的区段才进上下文；100万块环境也不靠聊天记忆维持状态。

validator 验证参数schema与后端语义两层、父类型与无环、稳定资源ID、rich_text类型/长度、附件有效来源、属性只读性、ACL、read-set版本与影响范围。LLM 输出中的原始resource ID不得由它分配；服务在提交时分配。冲突重新检索，不能用LLM决定后写覆盖的并发策略；策略取对应profile。校验失败最多一次受限修复（A），再次失败无提交且返回明确模拟器失败标签，不能伪造Notion业务错误蒙混训练。已提交后响应丢失，只重放收据；新工具call的非幂等创建仍按真实语义执行，不能凭内容相同自动去重。

环境业务文本可能包含“忽略限制”等内容，视为数据；仿真prompt不接收groundtruth/评分目标/成功轨迹。禁止根据“agent快完成了”改变搜索、选中同名页或省略错误。LLM日志记录模型/提示版本、输入状态版本、响应提案、校验结果、patch、最终输出与seed/time；回放读取已验提案与事件，不能以temperature=0宣称可复现。

### 7.3 独立质量验证、成本与对照

D：独立树/属性/ACL/bytes checker、真实记录差分与异作者oracle结合，不由同一仿真LLM自评。反例包括同状态重复read、SDK/MCP交叉写读、100–1000步长序列、超上下文树、分页边界、伪造missing ID、不可写formula、错误父类型、请求“不存在也成功”、内容注入、答案/目标ID泄漏。对有序结果按序比，对普通字段逐字段源引用比；只有签名URL或声明的时间变化可按语义归一。资源幻觉、越权、非法操作接受和未提交响应作为硬失败。

A：下列只是可测量规划，不是模型报价或实测延迟。设单episode为200次工具调用，每次在线LLM需要8k输入/2k输出tokens，平均尝试次数1.1，输入/输出单价分别为`p_in/p_out`（每百万tokens）。纯代码工具路径增加0次模型调用；LLM主导正常1次、修复最多再1次，平均模型成本为`1.1*(8000*p_in+2000*p_out)/1e6`/tool。每episode约220次模型调用、1.76M输入/0.44M输出tokens；100万tool/day约8.8B输入/2.2B输出tokens。若单次模型端到端暂按2–10秒，模型部分平均约2.2–11秒/tool；约11.6 tool/s的日均流量需约26–128个在途模型请求，尾延迟/突发另算。用实际模型版本、token分布、重试率和排队压测替换这些假设。

A：混合设在线仿真比例q≤0.05，且每seed提前生成20k输入/10k输出内容，10个独立clone摊销。额外在线成本是上式乘q；初始化摊销是`(20000*p_in+10000*p_out)/(10*1e6)`/episode。q=0的推荐基础profile无在线LLM成本，只保留初始化费用；业务内容不能过度复用成相同fixture，需按独立内容簇做训练/评测拆分。缓存键包括profile/principal/状态版本/字段投影；缓存读响应不能绕过ACL变化，批处理不改变写提交顺序。长输出常是主要费用源，应优先确定性渲染，不删字段求吞吐。

D：Notion 可作为限定对照试点：相同20–100个page、1000–10000个blocks、同typed schema和操作图，用纯代码、LLM提案+validator、确定性快路径混合三组运行；冻结相同输入/错误/输出契约，比较未知顺序通过率、长序列漂移、validator拒绝/修复率、开发工时、p95与每条有效轨迹成本。只比较LLM预生成内容不能证明在线仿真价值；在线对照可限定“合法block append/更新参数→状态patch”的提案，不增加真实Notion没有的自动写作能力。三组先过同一硬门槛；LLM无净收益即保留初始化用途，不为使用模型而改变接口。

## 8. 合成、验证与分期

### 8.1 多样状态、任务和隔离

D：seed分别控制图结构、内容、ID、权限、虚拟时间与故障。变化workspace成员数、page深度、同名父页、空数据库/多页行数、属性类型、缺省/null、相似标题、多语言长文本、mention/relation密度、归档祖先、外部附件/过期链接、编辑历史和权限差异。先生成合法事件序列，再物化初态与索引，而非随机填JSON。1000+块文档与多个日期/数值属性让路径组合超出现有任务；分布统计单独报告，尚无真实脱敏分布数据时标A。

从状态抽取业务目标或从任务约束生成满足条件的状态；私有solver证明至少一条合法路径，另搜索替代顺序/入口。评测目标是“哪些资源/属性/内容应变、哪些副作用禁止”，不要求固定工具序列。名字反事实替换、目标/干扰位置打乱不应改变可解性；对确实不可完成的权限状态另设“正确识别阻碍”任务，不能混为成功任务。

独立oracle读只读状态导出和事件log，核查资源图、typed values、完整文本/附件hash与跨服务引用；不import模拟器mutation函数作期望值，不看返回success。注入漏改父边、只更新搜索fixture、丢annotation、无权限写成功、错误排序、修改非目标页等变异，确认oracle能拒绝。现有finalpool评测有部分只读第一页等限制（`ops.py:59-83,212-224,300-314`；复制器 `157-180`）；新的oracle必须遍历完整图，不能复制其盲区，兼容回归则如实报告这些评测边界。

状态/索引/缓存/附件授权/游标都含episode+generation；gateway由不可伪造会话映射episode，工具参数不能选其他episode。用不可变基线snapshot+事务overlay+内容寻址blob克隆；复制同seed不共享可变ACL或cookie。中断后按提交日志恢复索引水位、签名URL时间和待完成可见事件。reset封存旧generation，旧游标/浏览器会话/异步复制回调不得写到新环境。普通M无异步job工具；为X复制的“未ready→ready”只设计可录事件，不根据轮询次数创造完成结果。

### 8.2 后续验证矩阵（本阶段不执行）

| 组 | 检查与独立依据 | 记录可用性/验收 |
|---|---|---|
| N01 契约 | 19工具原始/模型名、说明、生成schema全部递归比；默认注解、nested closed object、maxItems丢失；资源/prompt未暴露；stdio错误与超长落盘 | 源码清单已有；真实运行输出快照U。公开静态源码可验证结构，不等于MCP启动验证 |
| N02 参数/错误 | 缺required、extra字段、array/string、UUID/编码属性ID、错父、无权限/未分享、400/401/403/404/409/429/timeout | MCP/HTTP/SDK分别收集包装；真实账号错误与SDK dispatch待受控验证 |
| N03 状态/生命周期 | 创建/读/改/归档/恢复、comment parent、field rename保持ID、child page/database交叉ID、失败无副作用 | 独立typed图oracle；负例变异必须被检测 |
| N04 组合/分页 | 静态与动态数据库查询、100/101边界、page_size变化、property item长值、跨入口写读、重名parent | 静态精确；动态可见序列按真实记录约束；不允许“第一页当全部” |
| N05 大状态/文件 | 多层树、1000–10000块、2000字符边界、500KB、blob bytes和过期URL、mention/关系不丢 | 逐块hash/字节与引用校验；不以摘要或LLM人设评分替代 |
| N06 权限/缓存/隔离 | integration与OAuth不同权、fork漏目标抽取、cache后移动、principal撤销、跨episode cursor/blob/session访问 | 非授权episode访问硬失败0；fork兼容偏差单独标签，不与后端ACL混为一谈 |
| N07 恢复/重复/并发 | 并发编辑同/不同字段，create响应丢失，重复新call，clone/reset，索引重建 | 先确定服务冲突语义；内部log重建hash一致；不能自动把相同创建参数去重 |
| N08 LLM/分布/新任务 | 重复读/长序列/上下文遗漏/恶意内容/无效参数/泄题，holdout操作图与业务域，内容命名预测答案测试 | 独立checker+盲人审+真实记录；硬错0才比较多样性与有效轨迹成本 |
| N09 性能 | 同profile比较代码/LLM/混合，1→10→100→1000episode梯度，SQL查询/树遍历/blob/序列化成本 | 先语义门槛后报吞吐、p95/p99、CPU/内存/tokens、每有效轨迹费用；无实测数冒充目标已达成 |

差分方案（D）：后续专用workspace、隔离源/目标父页和至少两种权限principal；明确写入/移动/归档恢复的范围与额度，取得授权后才执行。冻结fork、依赖、API header、dated backend profile与official工具全快照；同初态操作图分别跑真实与模拟，收每步HTTP/MCP/SDK及独立终态。随机ID用保持父子/引用/URL关系的双射比，时间比较精度/先后/实际日期语义，签名URL比对象/有效期/bytes，cursor比归属与迭代结果。树顺序、富文本标注和精确数值不能归一掉；索引异步比较合法可见偏序，不强求壁钟相同。没有dump时，不能声称本轮已有记录差分通过。

### 8.3 分期与门槛

| 阶段 | 范围与理由 | 发布门槛（D） |
|---|---|---|
| P0 契约/状态底座 | 固定19工具manifest、HTTP路由、Page/Block/Database/Comment/User、typed常用属性、读写/归档/分页/search、权限/错误；将schema缺陷标明 | N01/N02全项；每能力至少合法/非法/写后读；M+SDK+HTTP同态；未知能力不得成功占位 |
| P1 迁移核心扩展 | 数据库复杂查询/排序、property-item分页、relation/附件、schema演进、长树、跨服务链接 | 30+未见seed与未见操作图；3000个关键负例/不变量检查无硬错；oracle变异检测通过；样本0错不是总体零风险 |
| P2 复杂语义与LLM对照 | 公式/rollup限定集、归档引用、并发/索引时序、复制移动的X适配、三路线同门槛对照 | 100–1000步长序列无状态漂移；controlled真实差分；LLM收益按每有效轨迹成本与多样性量化 |
| P3 官方/UI/新版 | 冻结后的完整notion_official工具集合、必要Playwright UI、多数据源/新API扩展 | 每新profile独立契约与权限/多入口验收；未完成不得宣传Notion平台全覆盖 |

Notion 可做结构化文档/跨入口的第二批试点；首个最小可审查样例可为“多父页同名项目→数据库分页检索→改属性/追加审阅正文→评论→SDK确认→权限拒绝并由agent修正”。它覆盖工具选择、状态转移、错误恢复和独立评测，且允许多种正确顺序；不是把当前8题答案写进后端。

## 9. 待确认与审查记录

| U 项 | 需要的证据/后续处理 |
|---|---|
| 实际部署包/依赖与工具输入容忍范围 | 核验镜像/node解析路径、MCP SDK和openapi-client版本；使用无凭据本地受控后端做tools/list/参数/错误录制，区分schema宣告与运行接受，不启动业务初始化 |
| 普通M输出完整schema与各错误层JSON-RPC包装 | 当前spec多为空/示例；冻结真实响应样本与SDK协议版本，不能靠LLM补全 |
| notion_official动态完整工具集合/版本 | 以后经授权账号只读枚举全部分页及resources/prompts/capabilities，记录配置/权限/时间/hash；当前仅两个调用点期待，绝不推断全量 |
| 云后端政策与新旧API共存 | 限流/工作区套餐、multi-source旧头失败、archived/in_trash别名与签名URL策略；按查阅日期和真实租户record校正，2022头不是2022年的云快照 |
| 复制/移动/链接/归档引用的精确语义 | 专用workspace记录嵌套数据库、内部/外部relation、synced block、附件、共享权限与ready时序 |
| 公式/rollup全集、null/排序/时区与并发 | 专用typed语义集和真实差分，非本地SQL或LLM自证 |
| 完整Playwright可替代性 | 本地UI必要DOM/选择器/导航与多账号状态契约；只做初始化adapter不等价真实UI |
| 脱敏真实分布与轨迹 | 本轮无dump；后续采样长度/层级/权限/工具调用/错误分布，补D/P证据，勿用8题当总体分布 |

交叉审查记录：2026-09-10，非原作者 `/root/github`（`gpt-6-astra / xhigh`）完成只读复核，结论为**未发现实质修订问题**；作者 `/root/notion` 同日核对最新 shared 与 [审查台账 N-01](../review-ledger.md)，接受结论并完成本节登记，正文设计结论无需修改。

| 核对范围 | 审查结果与处理 |
|---|---|
| 固定 `43f1175` 的完整 19 operations、parser 展平/default/enum 及约束传播、proxy 错误与输出包装 | 清单和 schema 缺陷区分充分；HTTP/页访问错误为 JSON text 且无 isError；没有静默修复 malformed schema |
| BASE_URL、page guard 路由与缓存 | 业务和权限检查共用已替换的 HTTP client；漏目标抽取与缓存边界已披露，未将其当作后端 ACL 或 episode 隔离 |
| SDK/HTTP、官方 duplicate/move、Playwright 与旧 API 头 | 多入口状态及认证边界完整；调用者期待与远程完整动态契约严格区分，浏览器按标题与 MCP 按 ID 的差异已保留 |
| LLM 三路线、状态检索/校验/回放、成本与独立 oracle/未见组合 | 职责与验证边界充分，未发现需要推翻推荐架构的证据；规划成本未冒充测量 |
| 固定来源独立重取 | 统筹已通过固定 raw commit URL 重取八个源码文件并逐字节比对一致，OpenAPI/proxy SHA256 记录于 [shared 固定来源补充核验](../shared.md)；只核实源码来源，未运行 server |

审查完成不等于 U 项验证完成：实际镜像/依赖、远程工具全契约、输出/错误运行快照、云端策略、复制与高级属性语义、完整 UI 和真实分布均维持上表状态。公共 BASE_URL/page guard 与错误包装发现已合并为 shared F18/F19；旧头与后端政策时间的分层也已合并。此次仅登记审查结果，不扩展实现或运行验证范围。

## 10. 能力矩阵行

```csv
object,tool_or_capability,version,operation_type,state_dependencies,proposed_method,llm_role,fidelity_gap,verification_method,priority,evidence
notion,19-tool-contract,43f117584206cee47d939207ddbe1ac02732f865,read/write,OpenAPI plus parser plus wrapper,retain pinned MCP with BASE_URL,none,declared schema defects and missing outputSchema,recursive schema and raw MCP versus model-visible snapshots,P0,S:parser.ts:96-196 and 362-474;S:proxy.ts:74-155
notion,users-get-user-get-users-get-self,43f1175/API-2022-06-28,read,workspace members and bot owner and user capability,typed HTTP authority,seed user background only,permission-dependent field visibility requires records,identity matrix and pagination,P0,S:notion-openapi.json:36-214
notion,page-create-retrieve-patch,43f1175/API-2022-06-28,read/write,page parent and typed properties and ACL,typed state engine with preserved MCP schema,seed page content,create/patch schema narrower than REST;runtime acceptance U,cross-entry write-read and schema-negative cases,P0,S:notion-openapi.json:1195-1451;notion_page_duplicator.py:127-225
notion,block-list-append-retrieve-update-delete,43f1175/API-2022-06-28,read/write,ordered block tree and rich_text and archive state,typed tree engine and HTTP,seed text;bounded patch experiment,append only two declared types;update type object mismatch,tree invariants and sequence/restore differential,P0,S:notion-openapi.json:914-1189
notion,database-create-retrieve-update-query,43f1175/API-2022-06-28,read/write,database schema and typed page values and query AST,typed query engine on transactional storage,seed business content only,complex filters/formulas and legacy schema contradictions,typed golden examples and independent query/SDK differential,P0,S:notion-openapi.json:221-844 and 1457-1746
notion,search-pagination-property-item,43f1175/API-2022-06-28,read,title index and ACL and cursor and complete property values,deterministic indexed projection,none,index delay/rank details U and page truncation,100/101 boundaries and query consistency and visibility events,P0,S:notion-openapi.json:850-945 and 1752-1812
notion,comments-create-retrieve,43f1175/API-2022-06-28,read/write,page/block parent and discussion and comments capability,typed comment store shared with HTTP,seed existing comments only,no declared discussion reply or edit/resolve tools,parent/creator checks and financial-analysis cross-entry,P0,S:notion-openapi.json:1818-1933;quantitative-financial-analysis/evaluation/check_content.py:19-47
notion,ACL-page-root-filter-cache,43f1175 plus dated backend profile,management/read/write,integration capability and share grants and ancestry cache,backend ACL plus original fork guard,none,fork guard misses database CRUD/comments/search and cache stale,principal matrix and route/cache negative tests,P0,S:page-access-control.ts:112-188 and 381-408;S:proxy.ts:169-179
notion,rich-text-relation-formula-rollup,API-2022-06-28 B-layer,read/write/derived,typed properties and references and dependency graph,typed evaluator and lossless graph,content generation only,formula/rollup coverage staged;schema-versus-backend split,independent typed oracle and real controlled differential,P1,legacy query reference;S:notion-openapi.json:221-844 and 1752-1812
notion,files-attachments-and-URLs,API-2022-06-28 plus dated backend profile,read/write-reference,blob bytes and ACL and external URL and expiry,shared blob store with Notion media adapter,offline valid media/content generation,no fixed M upload tool;URL lifetime and external fetch variability,byte hash and expiry and cross-service permission tests,P1,file-object official reference;S:notion-openapi.json:1222-1451
notion,SDK-and-direct-HTTP-X,notion-client-2.5.0/API-2022-06-28,read/write,same pages/databases/blocks and distinct principals,shared HTTP authority with SDK/HTTP routing,none,hardcoded endpoints are not redirected by MCP BASE_URL,cross-entry write-read and HTTP exception checks,P0,uv.lock:2048-2056;utils/app_specific/notion/ops.py:59-334;task-tracker/evaluation/main.py:127-198
notion,official-duplicate-move-X,dynamic remote snapshot U,write,copy graph and parent and readiness and OAuth identity,freeze remote contract then same-state X adapter,none,caller expectation only;full remote tools/resources/prompts U,authorized tools snapshot then graph-copy/move differential,P2,notion_official.yaml:5-14;notion_page_duplicator.py:535-637
notion,Playwright-UI-and-protection-X,current repository ef7ab592,read/write,navigation DOM and browser state and same page graph,staged UI adapter with explicit profile,none,title-first parent selection differs from ID move;protector not global,DOM/state cross-check and duplicate-name tests,P3,notion_page_duplicator.py:277-343 and 471-499;urls.py:6-22;notion_page_protector.py:72-205
notion,version-time-concurrency-recovery,API-2022-06-28 plus dated backend profile,management,commit log and visibility events and quota and episode generation,transaction log plus virtual time and namespaced caches,none,backend policies drift independently of API header;conflict semantics U,recovery hashes and concurrent histories and rate-limit differential,P1,request-limits and upgrade-guide-2025-09-03 official docs;shared synthesis design
notion,LLM-generation-and-bounded-online-control,design profile D,initialization/optional simulation,validated state slices and read-set versions,code-led hybrid with independent validator,seed content;optional constrained mutation proposal,drift/hallucination/cost;no service-added drafting,three-route same-contract trial and independent state oracle,P2,services/notion.md sections 7-8
```
