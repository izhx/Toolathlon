# Notion 任务评测

一级任务列表：`configs/task_lists/finalpool/c-notion.txt`，独立组成 C-notion，包含全部 8 个 Notion 任务。这些任务已从 C-local、C-remote 清单移除，五组之间不重复。

**Notion 任务必须串行运行，不能开任务并发。** 每次只执行一个任务，等它的 preprocess、agent 和 evaluation 全部结束后，再开始下一个。运行参数必须显式设置 `workers=1`；也不能同时启动多个 C-notion 作业，包括不同模型或不同 checkout 的作业。

| 任务 | 需要 Poste | 除 Notion 外的主要依赖 |
| --- | --- | --- |
| `experiments-recordings` | 否 | W&B |
| `notion-find-job` | 是 | Poste 邮件、Google Maps、浏览器 |
| `notion-hr` | 是 | Poste 邮件、文件系统、PDF 工具 |
| `notion-movies` | 否 | 浏览器、网页抓取 |
| `notion-personal-website` | 否 | 文件系统、Word 工具 |
| `oil-price` | 否 | Yahoo Finance |
| `quantitative-financial-analysis` | 否 | Yahoo Finance、Google Sheets/Drive（Google OAuth） |
| `task-tracker` | 否 | GitHub |

其中只有 `notion-find-job`、`notion-hr` 需要本地 Poste 邮件服务。只运行其余六个任务时可跳过 Poste 部署；整份列表也不需要部署 Canvas、WooCommerce 或 Kubernetes。若与 C-local 共用实例，两组仍共享 Poste，任一组使用邮件服务时都不能重建它；分组本身不隔离邮箱状态。

`quantitative-financial-analysis` 的预处理先初始化 Google Drive/Sheets，再复制 Notion 的 `Quant Research` 页面；agent 写行情表格及 Notion 链接/评论，评分检查两边结果。它需要 Google OAuth 和 Notion 两套认证，不能因为历史记录先报 Google 凭据缺 `token` 就省略 Notion 配置。

[task debug 的 BLOCK](task-debug-progress.md#block-服务依赖标签) 使用多项服务依赖标签：本组 8 个任务均包含 Notion；`quantitative-financial-analysis` 同时标注 `Yahoo Finance;Google;Notion`，`oil-price` 标注 `Yahoo Finance;Notion`，`notion-find-job` 标注 `Google;Notion`。跑通后也保留这些标签，具体失败阶段、配置待核情况另见实跑记录和说明。网页勾选多个服务时匹配任一项，执行分组和本组串行要求仍按本文规定。

## 部署与检查

在仓库根目录执行：

```bash
# 预览，不部署
bash global_preparation/deploy_notion_containers.sh --dry-run

# 已有 Poste 时先检查；不会重建或清空邮件
bash global_preparation/deploy_notion_containers.sh --check

# 首次部署，或需要重置这套邮件环境时执行
bash global_preparation/deploy_notion_containers.sh
```

默认部署复用 `deployment/poste/scripts/setup.sh start true`：重建 `poste<instance_suffix>`，清空当前仓库的 `deployment/poste/data/`、`deployment/poste/configs/`，按原流程创建邮箱账号。它仍创建原流程的整批账号，没有另写一套两任务账号初始化逻辑。不要在其他任务使用同一 Poste 时执行重建。

如果原环境使用 `deploy_containers.sh false`，这里也传 `false`。它控制原有 Dovecot/Haraka 配置步骤：

```bash
bash global_preparation/deploy_notion_containers.sh false
```

容器运行时、实例后缀沿用现有配置；服务检查从容器实际端口映射读取端口。`ports_config.yaml` 的映射仍需通过原来的 `apply_port_numbers.py` 流程应用，单改 YAML 不会改写任务代码。

新脚本检查账号初始化统计、HTTP 响应、IMAP/SMTP 协议响应；`--check` 只检查现有服务响应。等待默认 180 秒，可用 `POSTE_READY_TIMEOUT_SECONDS` 调整。检查不发送邮件，也不验证 Notion 登录、邮箱登录或任务最终得分。失败退出非零，保留 Poste 现场供排查；不会自动重复重建。

## 运行任务列表

仍需准备普通 Notion integration 配置、源页面/评测页面、`configs/.mcp-auth` 中的 Notion OAuth 授权，以及表中各任务所需的其他服务配置。页面清理/复制与任务邮箱清理由各自 preprocess 执行。

网页入口统一使用 `https://app.notion.com`。`source_notion_page_url`、`eval_notion_page_url` 和 API 返回的浏览器页面链接仍兼容旧 `notion.so` 地址，脚本使用时会转换域名并保留路径、查询参数和片段；页面 ID 与保护规则保持一致。REST API 和官方 MCP 继续使用 `api.notion.com`、`mcp.notion.com`。

若启用 `notion_preprocess_with_playwright=True`，旧 `.so` 登录状态可能不适用于新域名，可运行 `uv run utils/app_specific/notion/notion_login_helper.py --headless` 重新生成 `configs/notion_state.json`。这与 `configs/.mcp-auth` 中的 MCP OAuth 授权分开；默认 MCP 预处理无需浏览器登录状态。

登录助手默认使用持久化浏览器目录 `configs/notion_browser_profile/chromium/`（`--browser firefox` 使用 `firefox/` 子目录），退出后保留登录状态及可缓存的 CSS、JS 等资源。资源过期或更新时仍会重新请求。可用 `--profile-dir /path/to/profiles` 指定其他根目录；同一浏览器子目录不能被多个进程同时使用，不同账号也应指定不同目录。该目录已加入 Git 忽略规则。

登录助手先检查浏览器目录中的登录状态；无效时尝试导入已有的 `configs/notion_state.json`，仍无效或文件不可读才要求重新登录。检查有效后无需邮箱或验证码，会导出最新 `notion_state.json` 并退出，供现有页面复制等脚本继续使用。检查遇到网络错误或超时会报错并保留原 JSON 文件，不把它判为登录失效。`--headless` 同样使用持久化目录；页面复制脚本仍使用 JSON 登录快照，不共享此浏览器缓存。

Notion 任务共享 OAuth 刷新状态与页面操作流程，并发可能造成刷新锁等待超时和状态竞争。按以下命令逐个运行任务：

```bash
bash scripts/run_parallel_task_list.sh \
  --task-list configs/task_lists/finalpool/c-notion.txt \
  dumps/notion-run1 \
  glm-5.2 unified 1
```

最后的 `1` 是 workers，不能省略；wrapper 默认值为 10，不适用于 Notion。可以替换模型名和 provider，但 workers 保持为 1。这个参数只限制当前进程，因此其他终端或模型作业也必须等当前 Notion 作业结束后再启动。

需要多轮时，在同一个命令中使用 `--attempts`，保持每轮任务串行、轮次之间顺序执行：

```bash
bash scripts/run_parallel_task_list.sh \
  --attempts 3 \
  --task-list configs/task_lists/finalpool/c-notion.txt \
  dumps/notion-experiment \
  glm-5.2 unified 1
```

这里不要加 `--deploy-before-attempt`：该选项仍然调用完整的 `global_preparation/deploy_containers.sh`。已有可用 Poste 时不必每轮重建；不同实验使用不同 dump 路径，并依次运行。最小部署不隔离共享邮箱、远程 Notion 页面或 OAuth 状态。

## 相对 main 的 Notion 改动与评测语义

以下结论来自 2026-09-08 的源码审查，对比 `dev/notion-url` 的 `75e5c37c` 与本地 `main` 的 `8f312c42`。比较的是两端实际文件内容（`git diff main HEAD`）；`main` 已 squash 合入之前的任务分组、部署及运行脚本改动，使用 `git diff main...HEAD` 会把这些已合入内容也列入差异。

**任务要求、groundtruth 和 PASS/FAIL 判定标准没有改变。改动主要影响登录与预处理能否成功，因此可能改变实跑结果和 NO_EVAL 比例。** 这一结论对应上述代码快照，后续代码变更需重新核对。

| 改动 | 具体变化 | 对评测语义的影响 |
| --- | --- | --- |
| 网页 URL 统一 | 新增 [urls.py](../utils/app_specific/notion/urls.py)，将支持的旧网页域名转换为 `app.notion.com`，保留路径、查询参数和片段；接入清理/复制入口、API 返回的浏览器链接等位置。REST API、官方 MCP 和 `notion.site` 公共站点地址不变。 | 页面 ID、源子页查找和目标父页面选择规则不变。 |
| 登录状态复用 | [登录助手](../utils/app_specific/notion/notion_login_helper.py) 从删除旧 JSON、重新登录，改为先检查持久化浏览器 profile，再尝试恢复已有 JSON，最后才要求重新登录。新增 profile 目录配置及 Git 忽略规则。 | 改变认证状态管理，会复用已有账号。页面复制仍读取 `notion_state.json`，不共享登录助手的浏览器缓存。 |
| 登录交互与失败处理 | 改进邮箱/验证码输入框定位、终端输入校验，以及密码、SSO、页面错误识别。无头登录跳转超时会报错并尝试保存错误截图，不再继续导出 JSON 并报告成功；检查已有会话时遇到网络错误或超时也会保留原 JSON。 | 改变登录成功/失败行为，不参与任务评分。 |
| 页面复制时序 | [复制流程](../utils/app_specific/notion/notion_page_duplicator.py) 将相关导航等待改为 `domcontentloaded`；在点击 Duplicate **之前**记录原页面 URL/ID，修复点击后快速跳转导致误记原页面的问题。 | 影响预处理成功率。复制、移动、重命名的目标规则不变，仍校验候选页面 ID 并通过 API 确认页面存在。 |
| 页面保护 | [保护模块](../utils/app_specific/notion/notion_page_protector.py) 增加新旧网页域名归一化。 | 仍保护相同的源页面和评测父页面，没有取消删除、移动、重命名保护。 |
| `oil-price` evaluator | [evaluation/main.py](../tasks/finalpool/oil-price/evaluation/main.py) 中 `_find_oil_price_page()` 返回字典的 `url` 改用新域名；这是任务评分文件中唯一的改动，另有对应 helper 导入。 | 该 `url` 字段没有参与评分；后续仍使用同一个 `duplicated_page_id` 查数据库，检查项和判定逻辑未改。 |

8 个 Notion 任务都调用公共清理/复制工具，但各任务自己的 preprocess 入口、任务描述、任务配置和 groundtruth 没有修改。另外 7 个任务的 evaluator 也没有修改。公共初始化流程仍是：清理评测父页面下的同名旧子页，复制指定源子页，移动到评测父页面、恢复任务要求的子页名，并写出 `duplicated_page_id.txt`。

使用默认 MCP 复制路径时，浏览器登录与 Playwright 等待时序的改动不会进入该复制路径；启用 `notion_preprocess_with_playwright=True` 后，这些改动才直接影响浏览器预处理。MCP 复制的页面参数、移动参数及 OAuth 刷新锁逻辑没有改变。文档、实跑记录和 CSV/HTML 展示变化不参与 evaluator 判分。

上述判断区分了判分规则和运行行为：在账号、源模板及初始化结果一致的前提下，没有发现放宽评分或改变任务目标的代码改动；登录状态复用、域名迁移和复制时序修复仍可能影响一次运行能否进入 agent/evaluation 阶段，不能据此承诺逐次运行结果完全一致。

此次审查运行了 [17 项单元测试](../tests/test_notion_urls.py) 和 [7 项本地 Chromium 测试](../tests/test_notion_login_helper.py)，全部通过。覆盖 URL/页面 ID 保持、父页面保护、MCP 复制参数、快速跳转、登录状态恢复及失败处理。复现命令如下，浏览器测试需要已安装 Playwright Chromium：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest discover \
  -s tests -p test_notion_urls.py -v

PYTHONDONTWRITEBYTECODE=1 RUN_NOTION_BROWSER_TESTS=1 \
  .venv/bin/python -B -m unittest discover \
  -s tests -p test_notion_login_helper.py -v
```

这些测试使用 mock 或本地 HTTP 页面，不连接真实 Notion。此次审查没有额外重跑真实 Notion 任务，也没有验证远程初始页面内容的一致性；以上属于源码与本地测试层面的结论。

## MCP 与 Playwright 预处理路径及对模型评测的影响

`notion_preprocess_with_playwright` 只控制评测开始前的 Notion 页面复制方式：`False` 走官方 MCP，`True` 走 Playwright。模型执行任务时的工具配置和评分规则都不随它切换。两条路径的分支入口是 [duplicate_child_page()](../utils/app_specific/notion/notion_page_duplicator.py)。以下说明基于 2026-09-08 的源码核对。

完整阶段顺序为：**清理旧页面 → 用 MCP 或 Playwright 复制模板、移动并重命名 → 写出页面 ID → 模型做任务 → evaluator 检查结果**。

| 对比项 | MCP 路径 | Playwright 路径 |
| --- | --- | --- |
| 复制方式 | 固定脚本调用官方 MCP 的 `notion-duplicate-page`。 | 固定脚本驱动浏览器点击 Duplicate。 |
| 移动方式 | 调用 `notion-move-pages`，用 `new_parent.page_id` 指定目标父页面 ID。 | 打开 Move to，搜索目标父页面标题，点击第一条匹配结果。 |
| 认证 | 使用 `configs/.mcp-auth` 中的 OAuth 授权，通过 `mcp-remote` 连接 `https://mcp.notion.com/mcp`。 | 使用 `configs/notion_state.json` 中的浏览器登录快照，创建浏览器 context；复制过程会更新该 JSON。 |
| 共同依赖 | 使用 integration key，通过 API 查找源子页、确认复制页存在、重命名；清理旧页面也走公共 API 流程。 | 相同，启用 Playwright 后仍需 integration key。 |
| 主要故障点 | OAuth 刷新、刷新锁等待、远程 MCP 调用、页面就绪等待。 | 登录失效、网页加载、元素定位、弹窗、搜索结果匹配。 |
| 交付给后续阶段的结果 | 复制出的页面及 `duplicated_page_id.txt`。 | 相同，后续使用本次复制出的页面 ID。 |

对被评测模型，直接影响如下：

- **模型使用的 Notion 工具相同。** 当前 8 个任务配置的都是 `notion`；[notion.yaml](../configs/mcp_servers/notion.yaml) 使用 `notion_integration_key_eval`，通过 `--page-id` 传入 `notion_allowed_page_ids`。任务的 [token_key_session.py 示例](../tasks/finalpool/notion-movies/token_key_session.py) 从 `duplicated_page_id.txt` 读取该值。预处理使用的 [notion_official](../configs/mcp_servers/notion_official.yaml) 是另一套服务。
- **复制操作不占被评测模型的推理轮次。** 这些操作由固定脚本调用工具或驱动浏览器完成。[TaskAgent](../utils/roles/task_agent.py) 在预处理完成后加载任务页面 ID，再连接模型工具并启动交互循环；容器预处理入口 [container_preprocess.py](../scripts/decoupled/container_preprocess.py) 也先初始化环境、加载页面配置，再交付给后续模型执行阶段。
- **任务是否提供浏览器工具由任务配置决定。** 例如 [notion-movies/task_config.json](../tasks/finalpool/notion-movies/task_config.json) 本来就包含 `playwright_with_chunk`，切换预处理方式不会增加或移除它。[该浏览器工具配置](../configs/mcp_servers/playwright_with_chunk.yaml) 使用 `--isolated`，没有加载预处理的 Notion 登录快照。
- **评分仍运行同一个 evaluator。** 开关没有切换任务要求、检查项或 PASS/FAIL 判定逻辑。

**初始化结果不同，仍会间接影响模型表现和得分。** 当前实现中，MCP 按父页面 ID 移动，Playwright 按标题搜索后点击第一条结果。存在同名父页面时，Playwright 可能选错位置；该流程等待移动对话框消失后继续重命名，没有再通过 API 核对复制页的最终父页面 ID。其后的父页面保护检查验证的是受保护页面的标题，不能代替最终归属检查。

因此，在源模板、最终父页面、复制内容和模型访问权限一致的前提下，两条路径不改变测量的任务能力；登录、复制或权限问题则可能造成预处理失败，或改变模型读取到的数据。做模型横向比较时，固定同一条预处理路径更容易控制环境差异。切换路径也不改变本文要求的 C-notion 全任务串行执行规则。

目前已从源码确认工具配置和判分规则不随开关变化；尚未做两条路径的真实远程页面内容对照，不能仅凭两边都报告预处理成功就认定初始环境完全等价。
