# finalpool MCP 公网依赖与公网读写分析

源码核对日期：2026-09-08；公网口径修订日期：2026-09-09。仓库版本：`f7b48fe0`（另结合核对时的工作树配置）。

读取 `tasks/finalpool/*/task_config.json` 的 `needed_mcp_servers`：共 **108 个任务、33 个去重名称**，名称及任务数保留原始声明口径。其中 **32 个名称能匹配当前 MCP 配置，`web_search` 是一项声明异常**，详见后文。

## 判断口径

- **联网仅指访问公网互联网**：判断 MCP 业务初始化、工具调用是否需要访问公网。本机、Docker 容器之间及内网服务访问均不计入。因此，访问本仓库本地部署的 Canvas、邮件、WooCommerce、Kubernetes 服务标为“不需要公网”。
- **公网访问是否只读**：仅判断公网侧的业务操作是否读取内容，还是能够修改数据或提交远程执行任务。下载后写本地文件仍属于公网只读；搜索使用 HTTP POST 也不等于修改公网业务内容。访问日志、配额消耗、认证刷新与本地缓存不作为业务写入。
- **按 MCP 能力判断**：某个任务只用查询工具，不代表整个 MCP 只有只读能力；写操作最终能否成功，还取决于实际凭据和权限。没有公网访问的本地工具、服务，其“公网访问是否只读”标为“不适用”；本地读写能力在说明中保留。
- **分析范围**：表内判断 MCP 本身的公网访问。模型 API、Agent 与 MCP 网关之间的传输，以及 `npx`、`uv`、`uvx` 下载/解析依赖不计入表内；部署或工具操作间接触发的后端服务公网访问另作说明。业务工具不依赖公网，也不代表首次安装依赖包不需要公网。

## MCP 集合与分析

点击 MCP 名称可查看本仓库启动配置（`web_search` 链接指向本地工具实现）；“依据”链接指向对应实现、发布版本或官方说明。任务数按每个任务至多计一次，不能相加得到任务总数。

| MCP 名称 | 使用任务数 | 运行时是否需要公网互联网 | 公网访问是否只读 | 分析与依据 |
|---|---:|---|---|---|
| [`arxiv-latex`](../configs/mcp_servers/arxiv-latex-mcp.yaml) | 1 | 需要：公网 | 是 | 根据 arXiv ID 获取论文 LaTeX 源码并展开；没有向 arXiv 投稿或修改论文的工具。[实现][arxiv-latex-src] |
| [`arxiv_local`](../configs/mcp_servers/arxiv_local.yaml) | 5 | 搜索、下载需要公网；读取已缓存论文不需要 | 是 | `search_papers`、`download_paper` 访问 arXiv；`list_papers`、`read_paper` 操作本地存储。名称中的 `local` 不表示整个 MCP 离线。[版本][arxiv-local-src] |
| [`canvas`](../configs/mcp_servers/canvas.yaml) | 8 | 不需要（本仓库本地部署） | 不适用 | 访问本地 Canvas，示例地址为 `localhost:20001`。读取课程、创建作业、提交和更新评分等均可在本地服务完成，不需要公网。[实现][canvas-src] |
| [`emails`](../configs/mcp_servers/emails.yaml) | 24 | 不需要（本仓库本地邮件服务） | 不适用 | 通过本地 IMAP/SMTP 查收、发送、回复、删除、移动邮件及管理草稿。本表按仓库本地邮件服务判断；改接公网邮箱服务时才需要相应公网访问。[邮件配置](../configs/example_email_config.json)、[版本][emails-src] |
| [`excel`](../configs/mcp_servers/excel.yaml) | 23 | 不需要：本地文件处理 | 不适用 | 读写工作簿、单元格、公式、图表等；核对版本的工具实现没有必需的远程业务服务。[版本][excel-src] |
| [`fetch`](../configs/mcp_servers/npx-fetch.yaml) | 25 | 公网 URL 需要；本机/内网 URL 不需要 | 访问公网时是，只提供抓取工具 | `fetch_html/json/txt/markdown` 使用 HTTP GET 获取内容，未暴露任意请求方法或请求体参数。这里只判断客户端能力，不承诺任意目标站点的 GET 都无副作用。[实现][fetch-src] |
| [`filesystem`](../configs/mcp_servers/filesystem.yaml) | 86 | 不需要：本地工作目录 | 不适用 | 启动时指定任务工作目录，提供本地文件读取、写入、移动和搜索等操作。 |
| [`git`](../configs/mcp_servers/git.yaml) | 2 | 不需要：本地仓库操作 | 不适用 | 核对的 `mcp-server-git==2025.1.14` 提供状态、diff、提交、暂存、分支、checkout 等；没有暴露 clone/fetch/pull/push 工具。通过 `terminal` 执行 Git 网络命令是另一条路径。[版本][git-src] |
| [`github`](../configs/mcp_servers/github.yaml) | 7 | 需要：GitHub API | 取决于任务配置，可读写 | 配置传入 `GITHUB_READ_ONLY`。全局示例默认只读，但 finalpool 中有 5 个任务显式设置 `github_read_only="0"`，允许相应写工具；不能整体归为只读。[版本记录](../local_binary/github-mcp-version.txt)、[配置说明](#github-的只读开关) |
| [`google-cloud`](../configs/mcp_servers/google-cloud.yaml) | 8 | 需要：Google Cloud 服务 | 否，可读写/执行 | 提供 Cloud Storage、BigQuery、Logging、Compute 等操作，包括上传/删除对象、建表或执行查询、修改云资源等；资源允许列表不是只读开关。[实现][gcloud-src] |
| [`google_calendar`](../configs/mcp_servers/google_calendar.yaml) | 2 | 需要：Google Calendar API | 否，可读写 | 工具包含 `create_event`、`update_event`、`delete_event`，以及查询事件。[版本][gcalendar-src] |
| [`google_forms`](../configs/mcp_servers/google_forms.yaml) | 2 | 需要：Google Forms API | 否，可读写 | 可获取表单/回答，也调用 `forms.create`、`forms.batchUpdate` 创建或修改表单。[实现][gforms-src] |
| [`google_map`](../configs/mcp_servers/google_map.yaml) | 6 | 需要：Google Maps API | 是 | 暴露地理编码、地点检索、距离矩阵、海拔与路线查询；核对版本未暴露修改地图或发布评论工具。[版本][gmaps-src] |
| [`google_sheet`](../configs/mcp_servers/google_sheet.yaml) | 11 | 需要：Google Sheets/Drive API | 否，可读写 | 支持更新单元格、增加行列、复制/重命名工作表、创建及共享电子表格等。[版本][gsheets-src] |
| [`howtocook`](../configs/mcp_servers/howtocook.yaml) | 2 | 会尝试公网访问；失败可回退本地数据 | 是 | 启动时获取 `https://weilei.site/all_recipes.json`，失败后使用包内 `all_recipes.json`；之后查询、推荐菜谱在内存中完成。不能标为“从不联网”。[实现][howtocook-src] |
| [`huggingface`](../configs/mcp_servers/huggingface.yaml) | 5 | 需要：公网远程 MCP 服务 | 取决于远程工具配置，不能保证只读 | 通过 `mcp-remote` 连接 `https://huggingface.co/mcp`，工具集合不固定在本仓库。官方服务可配置仓库写入、Jobs、Sandboxes、Spaces 等能力；实际账号启用哪些工具需以运行时工具列表为准。[官方说明][hf-doc] |
| [`k8s`](../configs/mcp_servers/k8s.yaml) | 5 | 不需要（操作本仓库本地 Kind 集群） | 不适用（本地集群 API 操作） | 查询集群、创建/删除资源等通过本地 Kubernetes API 完成。节点拉取公网镜像、容器命令访问公网属于额外触发的公网操作，需按实际操作判断。[实现][k8s-src] |
| [`memory`](../configs/mcp_servers/memory.yaml) | 9 | 不需要：本地 JSON 存储 | 不适用 | `MEMORY_FILE_PATH` 指向任务工作目录中的 `memory/memory.json`，知识图谱实体和关系持久化在本地。 |
| [`notion`](../configs/mcp_servers/notion.yaml) | 8 | 需要：Notion API | 否，可读写 | OpenAPI 工具包括创建页面、追加/更新/删除 block、修改数据库和创建评论。页面允许列表限制范围，不将操作变成只读。[实现][notion-src] |
| [`pdf-tools`](../configs/mcp_servers/pdf-tools.yaml) | 20 | 公网 URL 下载需要；本地文件/内网 URL 不需要 | 访问公网时是，只下载 PDF | `resolve_path` 支持 URL；下载使用 HEAD/GET 并缓存到本地，随后读取、搜索、合并或提取 PDF。合并、提取会写本地文件，不会回传修改后的 PDF。[版本][pdf-src] |
| [`playwright_with_chunk`](../configs/mcp_servers/playwright_with_chunk.yaml) | 24 | 取决于页面及其资源：访问公网时需要；仅本地/内网时不需要 | 访问公网时可读写，不限只读 | 浏览器支持导航、点击、输入、文件上传等，能提交表单并改变网站状态；`--headless`、`--isolated` 和输出分块都不是只读限制。[版本][playwright-src] |
| [`pptx`](../configs/mcp_servers/pptx.yaml) | 1 | 不需要：本地演示文稿处理 | 不适用 | 核对的 2.0.6 版处理本地演示文稿和图片数据；写入超链接本身不访问链接目标。[版本][pptx-src] |
| [`rail_12306`](../configs/mcp_servers/12306.yaml) | 1 | 需要：12306 公网接口 | 是 | 按 YAML 指定的 `12306-mcp@0.3.9` 核对，工具为车站、余票、中转和列车经停查询等，没有下单、支付或退票工具。[版本][rail-src] |
| [`scholarly`](../configs/mcp_servers/scholarly_search.yaml) | 5 | 需要：arXiv / Google Scholar | 是 | 暴露 `search-arxiv` 和 `search-google-scholar` 两个检索工具，不修改远端论文或学术主页。[实现][scholarly-src] |
| [`snowflake`](../configs/mcp_servers/snowflake.yaml) | 4 | 需要：远程 Snowflake 服务 | 否，当前配置允许写 | YAML 明确传入 `--allow_write`；具备写 SQL/建表等能力，最终权限由账号角色和数据库允许范围决定。[实现][snowflake-src] |
| [`terminal`](../configs/mcp_servers/terminal.yaml) | 48 | 取决于命令：本地操作不需要；公网下载/API 调用需要 | 访问公网时可读写/执行，不限只读 | 允许列表包含 `python`、`curl`、`wget`、`git`、`kubectl`、`helm`，能够下载、上传、调用写 API 或操作远程服务，没有统一的公网只读限制。 |
| [`wandb`](../configs/mcp_servers/wandb.yaml) | 3 | 需要：W&B / Weave 等远程服务 | 否，可读写 | 安装脚本固定版本显式注册 `create_wandb_report_tool`，实现调用 `report.save()`；GraphQL 工具也接受操作字符串。当前任务主要读取实验结果，不代表 MCP 能力只读。[实现][wandb-src] |
| [`web_search`](../utils/aux_tools/web_search.py) | 1 | 声明异常；同名本地工具实现需要公网 | 本地搜索实现是只读；不存在可核对的同名 MCP | `nvidia-stock-analysis` 将其写在 `needed_mcp_servers` 中，但当前无匹配 YAML。仓库本地工具通过 Serper 搜索 API 获取结果；不能把它当作已成功连接的第 33 个 MCP。[任务配置](../tasks/finalpool/nvidia-stock-analysis/task_config.json) |
| [`woocommerce`](../configs/mcp_servers/woocommerce.yaml) | 9 | 不需要（本仓库本地商店服务） | 不适用 | 任务配置通常指向 `localhost:10003` 下的不同商店，商品、订单等查询和写入通过本地服务完成。商店处理公网图片 URL 等可能额外触发服务端公网下载。[版本][woocommerce-src] |
| [`word`](../configs/mcp_servers/word.yaml) | 2 | 不需要：本地文档处理 | 不适用 | 核对的 1.1.9 版直接读写本地 Word 文档、表格和图片；没有必需的远程业务服务。[版本][word-src] |
| [`yahoo-finance`](../configs/mcp_servers/yahoo-finance.yaml) | 10 | 需要：Yahoo Finance 等公网数据接口 | 是 | 工具读取历史行情、公司资料、新闻、财报、股东、期权、推荐数据；没有交易下单或修改账户工具。[实现][yahoo-src] |
| [`youtube`](../configs/mcp_servers/youtube.yaml) | 2 | 需要：YouTube API / 网页 | 是，按固定版本实际注册工具判断 | `server.ts` 注册的是视频/频道/播放列表查询、搜索、字幕与列表翻页，没有注册上传、评论或修改播放列表工具；仓库其他源码文件中存在相关函数不代表它们已暴露给 Agent。[实现][youtube-src] |
| [`youtube-transcript`](../configs/mcp_servers/youtube_transcript.yaml) | 3 | 需要：YouTube 网页/字幕接口 | 是 | 获取视频字幕并整理文本，不发布或修改字幕。[实现][yt-transcript-src] |

## 需要单独理解的边界

### `web_search` 是声明名，不是已配置的 MCP

[`nvidia-stock-analysis/task_config.json`](../tasks/finalpool/nvidia-stock-analysis/task_config.json) 在 `needed_mcp_servers` 中声明 `web_search`，但没有在 `needed_local_tools` 中声明它。[`MCPServerManager.connect_servers`](../utils/mcp/tool_servers.py) 遇到未配置名称只打印 `Warning: Server 'web_search' not found` 并跳过；[`TaskAgent`](../utils/roles/task_agent.py) 的本地工具映射虽包含 `web_search`，仍需由本地工具列表选择。因此，不能据该任务的 JSON 断言 Agent 获得了搜索工具。本次保留原始计数，并记录差异，没有修改任务配置。

### GitHub 的只读开关

[`configs/token_key_session_example.py`](../configs/token_key_session_example.py) 的 `github_read_only` 默认是 `"1"`，对应服务器的 [只读模式开关][github-src]。以下 5 个任务的 `token_key_session.py` 显式覆盖为 `"0"`：

- [`dataset-license-issue`](../tasks/finalpool/dataset-license-issue/token_key_session.py)
- [`email-paper-homepage`](../tasks/finalpool/email-paper-homepage/token_key_session.py)
- [`k8s-pr-preview-testing`](../tasks/finalpool/k8s-pr-preview-testing/token_key_session.py)
- [`personal-website-construct`](../tasks/finalpool/personal-website-construct/token_key_session.py)
- [`task-tracker`](../tasks/finalpool/task-tracker/token_key_session.py)

另两个声明 GitHub 的任务是 `git-repo`、`youtube-repo`，未发现同类任务级覆盖；它们是否只读仍应看实际全局配置和最终合并的任务配置，不能以示例值替代运行值。

### “任务只读”与“MCP 只读”不同

三个 W&B 任务主要读取实验数据：`wandb-best-score`、`wandb-shortest-length` 输出本地文件，`experiments-recordings` 将结果写入 Notion。尽管任务没有要求写 W&B，固定版本仍暴露创建 W&B 报告工具。因此本表将 `wandb` 标为可写；这是能力层面的判断，不是在声称任务已经进行了远端写操作。[工具注册][wandb-src]、[报告保存实现][wandb-report-src]

Hugging Face 同样需要分清调用路径：例如 [`huggingface-upload`](../tasks/finalpool/huggingface-upload/task_config.json) 同时拥有 `terminal` 和 `huggingface`，上传可通过终端里的 SDK/CLI 完成，不能仅凭任务名称推断 MCP 本身提供上传工具。远程 MCP 的具体能力还会随账号设置和服务版本变化。[官方工具说明][hf-doc]

### 可选的公网访问

`howtocook` 在启动时先尝试从公网获取菜谱，异常后才使用内置数据；`pdf-tools` 接收公网 URL 时需要公网，本地文件和内网 URL 不需要公网；`arxiv_local` 搜索和下载论文时访问 arXiv，读取本地缓存不需要公网。`fetch`、`terminal`、`playwright_with_chunk` 按实际 URL、命令、页面及资源判断是否访问公网，以及是否修改公网业务数据。

### 本地部署的四类服务

按本仓库的本地部署，`canvas`、`emails`、`woocommerce`、`k8s` 的服务 API 操作均标为 **不需要公网**，其“公网访问是否只读”标为 **不适用**。这些 MCP 能修改本地服务数据，该能力记录在说明中。

额外触发的公网访问单独判断：例如 Kubernetes 节点下载公网镜像、容器命令访问公网，或 WooCommerce 服务下载公网图片。此类操作需要公网时，应记录具体操作，不将本地服务连接本身算作公网依赖。[部署入口](../global_preparation/deploy_containers.sh)

### 统计范围和验证范围

本表仅统计任务显式声明的 `needed_mcp_servers`，不覆盖 `needed_local_tools`、任务初始化、评测脚本的全部依赖。例如 `notion_official` 没有出现在这 33 个声明名称中，但 [Notion 页面复制实现](../utils/app_specific/notion/notion_page_duplicator.py) 在相应模式下会使用它访问远程服务。

本次进行了配置与源码静态核对，没有启动 MCP、执行任务或使用业务凭据测试远程写入。第三方实现优先按 [`global_preparation/install_env.sh`](../global_preparation/install_env.sh) 的固定版本/提交、[`uv.lock`](../uv.lock) 和 [`package.json`](../package.json) 核对；npm 范围依赖使用所列版本的发布包作为参考。宿主机缺少完整的 `local_servers`、`node_modules` 安装目录，实际任务镜像里的版本未核验；Hugging Face 根据当前官方说明分析，未获取账号的实际工具列表。后续变更版本、凭据权限或远程工具设置时，应重新核对对应条目。

## 复核名称与任务数

在仓库根目录运行以下只读统计命令；它复核声明集合与计数，不自动推断网络权限：

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

files = sorted(Path('tasks/finalpool').glob('*/task_config.json'))
counts = Counter()
for path in files:
    names = json.loads(path.read_text())['needed_mcp_servers']
    assert isinstance(names, list) and all(isinstance(name, str) for name in names)
    counts.update(set(names))
print(f'tasks={len(files)}, declared_mcp_names={len(counts)}')
for name, count in sorted(counts.items()):
    print(f'{name}\t{count}')
PY
```

[arxiv-latex-src]: https://github.com/takashiishida/arxiv-latex-mcp/blob/f8bd3b3b6d3d066fe29ba356023a0b3e8215da43/arxiv-latex-mcp.py
[arxiv-local-src]: https://pypi.org/project/arxiv-mcp-server/0.2.10/
[canvas-src]: https://github.com/lockon-n/mcp-canvas-lms/blob/109770466cff5559e7c29988a153aa3563e007f7/src/client.ts
[emails-src]: https://pypi.org/project/emails-mcp/0.1.12/
[excel-src]: https://pypi.org/project/excel-mcp-server/0.1.4/
[fetch-src]: https://github.com/tokenizin-agency/mcp-npx-fetch
[git-src]: https://pypi.org/project/mcp-server-git/2025.1.14/
[github-src]: https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/cmd/github-mcp-server/main.go
[gcloud-src]: https://github.com/lockon-n/google-cloud-mcp/blob/7df9ca22115002e0cea75deec595492c520df3e1/src/server.py
[gcalendar-src]: https://www.npmjs.com/package/@gongrzhe/server-calendar-autoauth-mcp/v/1.0.2
[gforms-src]: https://github.com/matteoantoci/google-forms-mcp/blob/96f7fa1ff02b8130105ddc6d98796f3b49c1c574/src/index.ts
[gmaps-src]: https://www.npmjs.com/package/@modelcontextprotocol/server-google-maps/v/0.6.2
[gsheets-src]: https://pypi.org/project/mcp-google-sheets/0.4.1/
[howtocook-src]: https://github.com/lockon-n/HowToCook-mcp/blob/11510d36bcb55f6c84eaac3f85f2b051a1c70b5b/src/data/recipes.ts
[hf-doc]: https://huggingface.co/docs/hub/agents-mcp
[k8s-src]: https://github.com/lockon-n/mcp-server-kubernetes/blob/f6ac1263ef279dd996d13042854cb1a3bf88dd9a/src/index.ts
[notion-src]: https://github.com/lockon-n/notion-mcp-server/blob/43f117584206cee47d939207ddbe1ac02732f865/scripts/notion-openapi.json
[pdf-src]: https://pypi.org/project/pdf-tools-mcp/0.1.4/
[playwright-src]: https://www.npmjs.com/package/@lockon0927/playwright-mcp-with-chunk/v/0.1.2
[pptx-src]: https://pypi.org/project/office-powerpoint-mcp-server/2.0.6/
[rail-src]: https://www.npmjs.com/package/12306-mcp/v/0.3.9
[scholarly-src]: https://github.com/lockon-n/mcp-scholarly/blob/82a6ca268ae0d2e10664be396e1a0ea7aba23229/src/mcp_scholarly/server.py
[snowflake-src]: https://github.com/lockon-n/mcp-snowflake-server/tree/bca38f3ef5305ac53b9935bd09edbfac442b6a36
[wandb-src]: https://github.com/lockon-n/wandb-mcp-server/blob/83f6d7fe2ad2e6b6278aef4a792f35dd765fd315/src/wandb_mcp_server/server.py
[wandb-report-src]: https://github.com/lockon-n/wandb-mcp-server/blob/83f6d7fe2ad2e6b6278aef4a792f35dd765fd315/src/wandb_mcp_server/mcp_tools/create_report.py
[woocommerce-src]: https://www.npmjs.com/package/@lockon0927/woocommerce-mcp/v/1.0.6
[word-src]: https://pypi.org/project/office-word-mcp-server/1.1.9/
[yahoo-src]: https://github.com/lockon-n/yahoo-finance-mcp/blob/469103ba1464486cb7b8bd2c1f6355f42ca64a5b/server.py
[youtube-src]: https://github.com/lockon-n/youtube-mcp-server/blob/b202e00e9014bf74b9f5188b623cad16f13c01c4/src/server.ts
[yt-transcript-src]: https://github.com/jkawamoto/mcp-youtube-transcript/blob/28081729905a48bef533d864efbd867a2bfd14cd/src/mcp_youtube_transcript/__init__.py

## 按公网依赖分组的清单

以下三组按前文口径划分，互不重复，共覆盖 33 个声明名称。

### 不需要公网：10 项

按本仓库本地部署判断。

```text
canvas
emails
excel
filesystem
git
k8s
memory
pptx
woocommerce
word
```

### 公网访问只读：11 项

```text
arxiv-latex
arxiv_local
fetch
google_map
howtocook
pdf-tools
rail_12306
scholarly
yahoo-finance
youtube
youtube-transcript
```

其中 `fetch`、`pdf-tools` 仅访问公网 URL 时需要公网；`howtocook` 会尝试公网下载，失败后可回退本地数据。

### 剩余：12 项

| 名称 | 原因 |
|---|---|
| `google-cloud` | 可修改云资源、上传数据、执行任务 |
| `google_calendar` | 可创建、修改、删除事件 |
| `google_forms` | 可创建、修改表单 |
| `google_sheet` | 可修改、创建、共享表格 |
| `notion` | 可修改页面、数据库等 |
| `snowflake` | 当前配置允许写数据库 |
| `wandb` | 可创建远程报告 |
| `github` | 只读取决于配置，部分任务开启写入 |
| `huggingface` | 远程工具配置决定能力，不能保证只读 |
| `playwright_with_chunk` | 可提交表单、上传文件、修改网站数据 |
| `terminal` | 可执行公网读写命令 |
| `web_search` | 声明异常：没有同名 MCP 配置；同名本地搜索工具本身只读 |
