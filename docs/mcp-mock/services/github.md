# GitHub 高保真模拟可行性与设计

作者：GitHub 领域 agent，创建参数 `gpt-6-astra / xhigh`；实际会话配置由统筹协作记录核实。查阅日期：2026-09-10。非原作者 `/root/snowflake` 已以 `gpt-6-astra / xhigh` 完成全文及固定源码交叉审查；作者于同日完成 G-01–G-03 修订，处置见 §9，统筹最终确认见 [review-ledger](../review-ledger.md)。F=源码事实，D=设计，A=规划假设，U=待确认。已阅读原始需求、shared、统一模板、总体报告及 synthesis/validation 相关约定；仓库与祖先未发现适用 AGENTS.md。本阶段只读扫描、下载公开固定源码、写本文；没有导入业务配置、运行 MCP/benchmark、真实服务写入或实现 mock。

## 1. 范围、版本与入口

**D：首选固定 MCP + GitHub REST/GraphQL 兼容服务 + 真实 Git 对象库；身份、issue/PR、搜索、通知和执行状态由确定性组件管理。LLM 适合预生成代码/issue/讨论内容，以及分期支持的 Copilot 原生生成行为，不能生成“已经执行成功”的结果。** 基础 Git/issue/PR 在限定 profile 内有望达到高状态保真；全量搜索、Actions、安全分析、Copilot 及权限政策长尾需分期。以下不是运行验证结论。

**F：版本与来源。** `configs/mcp_servers/github.yaml:1-19` 启动本地 `github-mcp-server stdio`，并传 PAT、`GITHUB_ALLOWED_REPOS`、`GITHUB_READ_ONLY`，缓存工具列表、超时 50 秒。`local_binary/github-mcp-version.txt:1-5` 指向 fork `lockon-n/github-mcp-server` 的 `ef07feb90b95893767c106067868735d9f550ba6`，不是官方主仓当前版本。2026-09-10 已从 [固定提交完整源码归档](https://codeload.github.com/lockon-n/github-mcp-server/tar.gz/ef07feb90b95893767c106067868735d9f550ba6) 读取全目录；本次归档 SHA-256 `63df13eb3c5af3445536269cdb5bc8dff7d9eece97a729b88080bd18c2ff2fc8`。下文 **S/** 均指该提交根目录，可通过 [固定源码树](https://github.com/lockon-n/github-mcp-server/tree/ef07feb90b95893767c106067868735d9f550ba6) 定位；临时下载位置不作为持久依赖。旧 `/tmp` 中只有 main/tools 片段，不作为完整能力证据。

`S/go.mod:6-11,42` 固定 `go-github/v74 v74.0.0`、`mcp-go v0.36.0`、Viper `v1.20.1`、`githubv4` 提交 `48295856cce7`。binary 的实际构建参数、运行镜像、最终环境及在线后端政策仍 U；版本文本不证明 binary 字节确实来自该提交。

| 层 | 范围、入口与证据 | 共享状态/边界 |
|---|---|---|
| M | 默认注册 91 个业务工具，另有可选 dynamic 3 工具、5 个 resource templates、2 个 prompts；`S/pkg/github/tools.go:19-222` | 按 §2 的配置条件注册；不以 7 任务子集截断 |
| B | REST repository/contents/Git database、GraphQL node/connection/mutation、raw bytes；Actions/log/artifact、安全告警及生成代理所需后端 | Git SHA 图、issue/PR/review、ACL 和异步状态需真实关联；平台其余 billing/packages/webhooks 管理不是自动全实现范围 |
| X / REST | `utils/app_specific/github/api.py:16,37-156` GET user/repo/commits/issue/comments，POST user/repos/issues，PATCH repo，DELETE repo；`repo_ops.py:10-70` 读默认分支后 PUT contents；`helper_funcs.py:24-58,61-81,84-159,161-259,289-379` contents/base64、ref rollback、递归删除、compare、fork/rename/create | 不受 MCP 只读/允许列表约束；重定向这些硬编码 `api.github.com` 入口必须共享 M 状态 |
| X / Git | `utils/app_specific/github/git_ops.py:20-40` 用系统 Git HTTPS `clone --mirror` / `push --mirror`；`utils/general/helper.py:564-583` 调 fork/独立复制脚本；本地 git MCP 为另一服务 | Git refs/objects 与 REST/GraphQL 必须同图；本地工作树/index 保留本地状态，push/fetch 才同步 |
| X / SDK、CLI、浏览器 | 本次扫描 `utils/app_specific/github` 和相关 finalpool Python/sh 未见 PyGithub 或 `gh` 调用；Python 客户端实为 requests。当前任务 GitHub URL 多是仓库/README/网页内容，不证明实际 GitHub 浏览器自动化。未来 terminal 可走 `gh api/pr/repo`、Git、HTTP/浏览器 | `gh` 同时依赖 REST/GraphQL 和 Git；不能用 shell 输出 fixture 替代它。Web UI 如进入 profile 需另有 GitHub 页面契约，Gitea 页面不能冒充 GitHub UI |

认证区分 PAT 主体、组织 membership/team、repo ACL、细粒度 token scope、bot/App 身份。wrapper 允许列表不是后端 ACL。业务后端本地/自控时可无公网；agent/仿真模型 API、Go/CLI/镜像安装、Actions 下载依赖、文档/外部 URL、LFS/发布资产分别记录，不能把本机/Docker/内网记为公网。

当前声明 GitHub 的完整任务如下；“使用”是任务/初始化/评测静态证据，不是观察到某工具调用。

| 任务 | 静态使用案例与额外入口 | 证据 |
|---|---|---|
| dataset-license-issue | GitHub issue/comment/README 与 HF 数据集联动；初始化 delete/create/mirror Git/改 README/创建 issue，评测读提交与 issue/comments | `task_config.json`；该任务 `preprocess/main.py:56-127`、`evaluation/main.py:7-11,74-100` |
| email-paper-homepage | 邮件驱动主页/论文 repo 内容修改；独立镜像复制；评测 contents/branch SHA/compare | `task_config.json`；`preprocess/main.py:164-235`、`evaluation/main.py:7,48-120` |
| git-repo | 仓库资料读取，最终本地文件/PDF 检查 | `task_config.json`、`docs/task.md`、`evaluation/main.py:8-9`、`evaluation/check_local.py` |
| personal-website-construct | 建仓/改主页文件；初始化删目标 repo，评测直接 REST 读文件 | `task_config.json`、`preprocess/main.py:1-25`、`evaluation/main.py:1-4`、`evaluation/check_remote.py:6` |
| sync-todo-to-readme | 本地 git 与 GitHub README 同步；初始化 mirror clone/create/push 并写本地认证文件；评测 REST 读远端 README | `task_config.json`、`preprocess/main.py:31-68`、`evaluation/main.py:8-12,35-42` |
| task-tracker | GitHub 仓库任务→Notion；初始化 mirror clone/create/push，评测 branches/contents | `task_config.json`、`preprocess/main.py:24-64`、`evaluation/main.py:260-331` |
| youtube-repo | 视频技术→搜索原始 GitHub 仓库→本地 Markdown | `task_config.json`、`docs/task.md:1`、`evaluation/main.py` |

以上任务路径均以 `tasks/finalpool/<task>/` 为前缀。四个声明任务的 token 文件明确 `github_read_only="0"`：dataset-license-issue:11、email-paper-homepage:7、personal-website-construct:6、task-tracker:15；另有 **声明外** `k8s-pr-preview-testing/token_key_session.py:34` 的旧覆盖。后者 preprocess 只 import `fork_repo` 而未调用（`preprocess/main.py:11,25-49`），eval import GitHub helpers 后只取 token，HTTP 实际请求为本地健康页（`evaluation/main.py:9,130,235`）；扫描 `scripts/k8s_pr_preview_testing.sh` 未见 GitHub/Git 操作。因此旧配置不构成当前 GitHub 业务依赖证据。`sync-todo-to-readme` 在当前 7 成员中，不能用旧 `docs/mcp-analysis.md:62-70` 名单替换。本次检索常见 dump/output 目录未取得可用 Toolathlon GitHub 轨迹；响应和任务使用均未获运行轨迹验证。

## 2. 工具与能力清单

### 2.1 配置决定的暴露边界

**F：** `S/cmd/github-mcp-server/main.go:43-70,83-110` 默认 `toolsets=all`、`dynamic-toolsets=false`、`read-only=false`、内容窗口 5000。可通过 `--toolsets`/`GITHUB_TOOLSETS`、`--dynamic-toolsets`/`GITHUB_DYNAMIC_TOOLSETS` 配置；本仓 YAML 没传这两项，不代表继承进程环境一定为空。toolsets 有 repos、issues、users、orgs、pull_requests、code_security、secret_protection、dependabot、notifications、discussions、actions、security_advisories、context、gists，以及无工具的 experiments。all 下普通工具 **91=56 read+35 write**，dynamic 模式另加 3 个发现/启用工具，合计能力清单 94。

**F：只读键存在源码冲突。** main 读取 `viper.GetBool("read-only")`，仅 `SetEnvPrefix("github")/AutomaticEnv()`，没有 env key replacer；[Viper v1.20.1 `viper.go:413-418,437-444,1206-1212`](https://github.com/spf13/viper/blob/v1.20.1/viper.go#L413) 只拼接并大写，故查询的是 `GITHUB_READ-ONLY`，不是 YAML 的 `GITHUB_READ_ONLY`。CLI `--read-only` 可传入 true，之后 `S/pkg/toolsets/toolsets.go:65-93,175-181` 的写工具过滤成立；**不能据本仓示例值 1 宣称运行只读**。这是固定源码推导，binary/任务进程实际效果待受控契约验证。本阶段不修代码、不启动 server。

**F：允许列表范围。** `S/pkg/github/repo_permission.go:58-95` 空列表不限制；非空时先查并缓存当前用户，仅 `owner == currentUser` 的个人仓库按 exact `owner/repo` 或 shorthand `repo` 检查，其他用户/组织仓库直接通过此 wrapper（仍受 GitHub ACL）。`"null"` 是普通列表项，不是特殊关闭值。`create_repository` 在任何非空列表下返回 tool error，并不隐藏工具（`create_repo_wrapper.go:11-23`）。普通 wrapper 先必取 owner/repo 再调 handler（`permission_wrappers.go:13-36`）；fork只检查源owner/repo，rename只检查旧名，没有对目标owner/name重新做该列表检查（`:77-87`），所以不能把create_repository禁用理解为所有建仓路径都禁用。搜索、GraphQL `list_issues`、assign_copilot_to_issue、discussions、全局/组织 advisory、Gist、部分通知、resource templates 未套仓库 wrapper，见 `tools.go:25-51,53-73,123-188`；不能称为完整仓库隔离。

**F：dynamic** 去掉初始 all，保留显式 toolset，初始可仅有 3 dynamic 工具；无自动保留 context。`enable_toolset` 改 server 全局列表，仅 `AddTools`，不会补注册该组的 resources/prompts（`S/internal/ghmcp/server.go:113-156`、`dynamic_tools.go:22-59`）。它的 readOnlyHint=true 指不写 GitHub，实际上会修改工具可见集合；工具缓存/notifications/list_changed 与 harness 缓存的相容性需单独验证。只读模式不移除 repos resources 或 issues prompts。

### 2.2 完整逐工具核对表

每行链接是固定提交中定义该工具的函数起点：**完整英文 description、annotations、输入 schema 和实际 handler** 都在该处，可逐项审计；表内说明使用短标题，交付时不可用短标题替换原 description。`!` 为 advertised required，`?` 为 optional；`s/n/b/a/o` 分别为 string/number/boolean/array/object；`P`=page/perPage、`C`=perPage/after。大多数工具是数字 schema 而非 integer，实际 parser 见 §2.3。`O`=owner!/repo! 两个 string。R/W 来自注册分组，Actions dispatch/rerun、Copilot 两项另属执行 E，dynamic 属配置管理 A。输出及业务状态按下方能力族说明。

#### context（3 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `get_me` | R / Get my user profile | `无` | [context_tools.go:37](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/context_tools.go#L37) |
| `get_teams` | R / Get teams | `user?s` | [context_tools.go:106](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/context_tools.go#L106) |
| `get_team_members` | R / Get team members | `org!s; team_slug!s` | [context_tools.go:193](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/context_tools.go#L193) |

#### repos（18 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `search_repositories` | R / Search repositories | `query!s; minimal_output?b=true; P` | [search.go:17](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/search.go#L17) |
| `get_commit` | R / Get commit details | `O; sha!s; include_diff?b=true; P` | [repositories.go:120](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L120) |
| `search_code` | R / Search code | `query!s; sort?s; order?s{asc/desc}; P` | [search.go:133](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/search.go#L133) |
| `list_commits` | R / List commits | `O; sha?s; author?s; P` | [repositories.go:207](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L207) |
| `list_branches` | R / List branches | `O; P` | [repositories.go:303](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L303) |
| `create_or_update_file` | W / Create or update file | `O; path!s; content!s; message!s; branch!s; sha?s` | [repositories.go:380](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L380) |
| `create_repository` | W / Create repository | `name!s; description?s; organization?s; private?b; autoInit?b` | [repositories.go:493](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L493) |
| `get_file_contents` | R / Get file or directory contents | `O; path?s=/; ref?s; sha?s` | [repositories.go:583](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L583) |
| `fork_repository` | W / Fork repository | `O; organization?s; name?s` | [repositories.go:799](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L799) |
| `rename_repository` | W / Rename repository | `O; new_name!s` | [repositories.go:889](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L889) |
| `delete_file` | W / Delete file | `O; path!s; message!s; branch!s` | [repositories.go:964](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L964) |
| `create_branch` | W / Create branch | `O; branch!s; from_branch?s` | [repositories.go:1135](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L1135) |
| `push_files` | W / Push files to repository | `O; branch!s; files!a; message!s` | [repositories.go:1236](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L1236) |
| `list_tags` | R / List tags | `O; P` | [repositories.go:1408](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L1408) |
| `get_tag` | R / Get tag details | `O; tag!s` | [repositories.go:1477](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L1477) |
| `list_releases` | R / List releases | `O; P` | [repositories.go:1564](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L1564) |
| `get_latest_release` | R / Get latest release | `O` | [repositories.go:1629](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L1629) |
| `get_release_by_tag` | R / Get a release by tag name | `O; tag!s` | [repositories.go:1683](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/repositories.go#L1683) |

#### issues（13 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `get_issue` | R / Get issue details | `O; issue_number!n` | [issues.go:148](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L148) |
| `list_issue_types` | R / List available issue types | `owner!s` | [issues.go:210](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L210) |
| `add_issue_comment` | W / Add comment to issue | `O; issue_number!n; body!s` | [issues.go:257](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L257) |
| `add_sub_issue` | W / Add sub-issue | `O; issue_number!n; sub_issue_id!n; replace_parent?b` | [issues.go:331](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L331) |
| `list_sub_issues` | R / List sub-issues | `O; issue_number!n; page?n; per_page?n` | [issues.go:419](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L419) |
| `remove_sub_issue` | W / Remove sub-issue | `O; issue_number!n; sub_issue_id!n` | [issues.go:513](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L513) |
| `reprioritize_sub_issue` | W / Reprioritize sub-issue | `O; issue_number!n; sub_issue_id!n; after_id?n; before_id?n` | [issues.go:592](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L592) |
| `search_issues` | R / Search issues | `query!s; owner?s; repo?s; sort?s{comments/reactions/reactions-+1/reactions--1/reactions-smile/reactions-thinking_face/reactions-heart/reactions-tada/interactions/created/updated}; order?s{asc/desc}; P` | [issues.go:705](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L705) |
| `create_issue` | W / Open new issue | `O; title!s; body?s; assignees?a; labels?a; milestone?n; type?s` | [issues.go:750](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L750) |
| `list_issues` | R / List issues | `O; state?s{OPEN/CLOSED}; labels?a; orderBy?s{CREATED_AT/UPDATED_AT/COMMENTS}; direction?s{ASC/DESC}; since?s; C` | [issues.go:890](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L890) |
| `update_issue` | W / Edit issue | `O; issue_number!n; title?s; body?s; state?s{open/closed}; labels?a; assignees?a; milestone?n; type?s` | [issues.go:1102](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L1102) |
| `get_issue_comments` | R / Get issue comments | `O; issue_number!n; P` | [issues.go:1265](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L1265) |
| `assign_copilot_to_issue` | W/E / Assign Copilot to issue | `O; issueNumber!n` | [issues.go:1368](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/issues.go#L1368) |

#### users（1 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `search_users` | R / Search users | `query!s; sort?s{followers/repositories/joined}; order?s{asc/desc}; P` | [search.go:301](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/search.go#L301) |

#### orgs（1 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `search_orgs` | R / Search organizations | `query!s; sort?s{followers/repositories/joined}; order?s{asc/desc}; P` | [search.go:325](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/search.go#L325) |

#### pull_requests（18 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `get_pull_request` | R / Get pull request details | `O; pullNumber!n` | [pullrequests.go:21](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L21) |
| `create_pull_request` | W / Open new pull request | `O; title!s; body?s; head!s; base!s; draft?b; maintainer_can_modify?b` | [pullrequests.go:87](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L87) |
| `update_pull_request` | W / Edit pull request | `O; pullNumber!n; title?s; body?s; state?s{open/closed}; draft?b; base?s; maintainer_can_modify?b; reviewers?a` | [pullrequests.go:211](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L211) |
| `list_pull_requests` | R / List pull requests | `O; state?s{open/closed/all}; head?s; base?s; sort?s{created/updated/popularity/long-running}; direction?s{asc/desc}; P` | [pullrequests.go:487](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L487) |
| `merge_pull_request` | W / Merge pull request | `O; pullNumber!n; commit_title?s; commit_message?s; merge_method?s{merge/squash/rebase}` | [pullrequests.go:599](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L599) |
| `search_pull_requests` | R / Search pull requests | `query!s; owner?s; repo?s; sort?s{comments/reactions/reactions-+1/reactions--1/reactions-smile/reactions-thinking_face/reactions-heart/reactions-tada/interactions/created/updated}; order?s{asc/desc}; P` | [pullrequests.go:692](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L692) |
| `get_pull_request_files` | R / Get pull request files | `O; pullNumber!n; P` | [pullrequests.go:737](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L737) |
| `get_pull_request_status` | R / Get pull request status checks | `O; pullNumber!n` | [pullrequests.go:812](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L812) |
| `update_pull_request_branch` | W / Update pull request branch | `O; pullNumber!n; expectedHeadSha?s` | [pullrequests.go:897](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L897) |
| `get_pull_request_comments` | R / Get pull request comments | `O; pullNumber!n` | [pullrequests.go:979](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L979) |
| `get_pull_request_reviews` | R / Get pull request reviews | `O; pullNumber!n` | [pullrequests.go:1051](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L1051) |
| `create_and_submit_pull_request_review` | W / Create and submit a pull request review without comments | `O; pullNumber!n; body!s; event!s{APPROVE/REQUEST_CHANGES/COMMENT}; commitID?s` | [pullrequests.go:1116](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L1116) |
| `create_pending_pull_request_review` | W / Create pending pull request review | `O; pullNumber!n; commitID?s` | [pullrequests.go:1219](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L1219) |
| `add_comment_to_pending_review` | W / Add review comment to the requester's latest pending pull request review | `O; pullNumber!n; path!s; body!s; subjectType!s{FILE/LINE}; line?n; side?s{LEFT/RIGHT}; startLine?n; startSide?s{LEFT/RIGHT}` | [pullrequests.go:1311](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L1311) |
| `submit_pending_pull_request_review` | W / Submit the requester's latest pending pull request review | `O; pullNumber!n; event!s{APPROVE/REQUEST_CHANGES/COMMENT}; body?s` | [pullrequests.go:1477](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L1477) |
| `delete_pending_pull_request_review` | W / Delete the requester's latest pending pull request review | `O; pullNumber!n` | [pullrequests.go:1611](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L1611) |
| `get_pull_request_diff` | R / Get pull request diff | `O; pullNumber!n` | [pullrequests.go:1730](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L1730) |
| `request_copilot_review` | W/E / Request Copilot review | `O; pullNumber!n` | [pullrequests.go:1798](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/pullrequests.go#L1798) |

#### actions（14 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `list_workflows` | R / List workflows | `O; P` | [actions.go:26](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L26) |
| `list_workflow_runs` | R / List workflow runs | `O; workflow_id!s; actor?s; branch?s; event?s{branch_protection_rule/check_run/check_suite/create/delete/deployment/deployment_status/discussion/discussion_comment/fork/gollum/issue_comment/issues/label/merge_group/milestone/page_build/public/pull_request/pull_request_review/pull_request_review_comment/pull_request_target/push/registry_package/release/repository_dispatch/schedule/status/watch/workflow_call/workflow_dispatch/workflow_run}; status?s{queued/in_progress/completed/requested/waiting}; P` | [actions.go:86](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L86) |
| `run_workflow` | W/E / Run workflow | `O; workflow_id!s; ref!s; inputs?o` | [actions.go:225](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L225) |
| `get_workflow_run` | R / Get workflow run | `O; run_id!n` | [actions.go:324](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L324) |
| `get_workflow_run_logs` | R / Get workflow run logs | `O; run_id!n` | [actions.go:380](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L380) |
| `list_workflow_jobs` | R / List workflow jobs | `O; run_id!n; filter?s{latest/all}; P` | [actions.go:446](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L446) |
| `get_job_logs` | R / Get job logs | `O; job_id?n; run_id?n; failed_only?b; return_content?b; tail_lines?n=500` | [actions.go:534](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L534) |
| `rerun_workflow_run` | W/E / Rerun workflow run | `O; run_id!n` | [actions.go:782](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L782) |
| `rerun_failed_jobs` | W/E / Rerun failed jobs | `O; run_id!n` | [actions.go:845](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L845) |
| `cancel_workflow_run` | W / Cancel workflow run | `O; run_id!n` | [actions.go:908](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L908) |
| `list_workflow_run_artifacts` | R / List workflow artifacts | `O; run_id!n; P` | [actions.go:973](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L973) |
| `download_workflow_run_artifact` | R / Download workflow artifact | `O; artifact_id!n` | [actions.go:1042](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L1042) |
| `delete_workflow_run_logs` | W / Delete workflow logs | `O; run_id!n` | [actions.go:1107](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L1107) |
| `get_workflow_run_usage` | R / Get workflow usage | `O; run_id!n` | [actions.go:1171](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/actions.go#L1171) |

#### code_security（2 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `get_code_scanning_alert` | R / Get code scanning alert | `O; alertNumber!n` | [code_scanning.go:17](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/code_scanning.go#L17) |
| `list_code_scanning_alerts` | R / List code scanning alerts | `O; state?s=open{open/closed/dismissed/fixed}; ref?s; severity?s{critical/high/medium/low/warning/note/error}; tool_name?s` | [code_scanning.go:83](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/code_scanning.go#L83) |

#### secret_protection（2 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `get_secret_scanning_alert` | R / Get secret scanning alert | `O; alertNumber!n` | [secret_scanning.go:17](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/secret_scanning.go#L17) |
| `list_secret_scanning_alerts` | R / List secret scanning alerts | `O; state?s{open/resolved}; secret_type?s; resolution?s{false_positive/wont_fix/revoked/pattern_edited/pattern_deleted/used_in_tests}` | [secret_scanning.go:84](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/secret_scanning.go#L84) |

#### dependabot（2 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `get_dependabot_alert` | R / Get dependabot alert | `O; alertNumber!n` | [dependabot.go:17](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/dependabot.go#L17) |
| `list_dependabot_alerts` | R / List dependabot alerts | `O; state?s=open{open/fixed/dismissed/auto_dismissed}; severity?s{low/medium/high/critical}` | [dependabot.go:84](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/dependabot.go#L84) |

#### security_advisories（4 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `list_global_security_advisories` | R / List global security advisories | `ghsaId?s; type?s=reviewed{reviewed/malware/unreviewed}; cveId?s; ecosystem?s{actions/composer/erlang/go/maven/npm/nuget/other/pip/pub/rubygems/rust}; severity?s{unknown/low/medium/high/critical}; cwes?a; isWithdrawn?b; affects?s; published?s; updated?s; modified?s` | [security_advisories.go:16](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/security_advisories.go#L16) |
| `list_repository_security_advisories` | R / List repository security advisories | `O; direction?s{asc/desc}; sort?s{created/updated/published}; state?s{triage/draft/published/closed}` | [security_advisories.go:185](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/security_advisories.go#L185) |
| `get_global_security_advisory` | R / Get a global security advisory | `ghsaId!s` | [security_advisories.go:274](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/security_advisories.go#L274) |
| `list_org_repository_security_advisories` | R / List org repository security advisories | `org!s; direction?s{asc/desc}; sort?s{created/updated/published}; state?s{triage/draft/published/closed}` | [security_advisories.go:319](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/security_advisories.go#L319) |

#### notifications（6 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `list_notifications` | R / List notifications | `filter?s{default/include_read_notifications/only_participating}; since?s; before?s; owner?s; repo?s; P` | [notifications.go:26](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/notifications.go#L26) |
| `dismiss_notification` | W / Dismiss notification | `threadID!s; state?s{read/done}` | [notifications.go:149](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/notifications.go#L149) |
| `mark_all_notifications_read` | W / Mark all notifications as read | `lastReadAt?s; owner?s; repo?s` | [notifications.go:216](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/notifications.go#L216) |
| `get_notification_details` | R / Get notification details | `notificationID!s` | [notifications.go:295](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/notifications.go#L295) |
| `manage_notification_subscription` | W / Manage notification subscription | `notificationID!s; action!s{ignore/watch/delete}` | [notifications.go:353](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/notifications.go#L353) |
| `manage_repository_notification_subscription` | W / Manage repository notification subscription | `O; action!s{ignore/watch/delete}` | [notifications.go:438](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/notifications.go#L438) |

#### discussions（4 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `list_discussions` | R / List discussions | `owner!s; repo?s; category?s; orderBy?s{CREATED_AT/UPDATED_AT}; direction?s{ASC/DESC}; C` | [discussions.go:120](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/discussions.go#L120) |
| `get_discussion` | R / Get discussion | `O; discussionNumber!n` | [discussions.go:259](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/discussions.go#L259) |
| `get_discussion_comments` | R / Get discussion comments | `O; discussionNumber!n; C` | [discussions.go:336](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/discussions.go#L336) |
| `list_discussion_categories` | R / List discussion categories | `owner!s; repo?s` | [discussions.go:444](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/discussions.go#L444) |

#### gists（3 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `list_gists` | R / List Gists | `username?s; since?s; P` | [gists.go:17](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/gists.go#L17) |
| `create_gist` | W / Create Gist | `description?s; filename!s; content!s; public?b=false` | [gists.go:93](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/gists.go#L93) |
| `update_gist` | W / Update Gist | `gist_id!s; description?s; filename!s; content!s` | [gists.go:182](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/gists.go#L182) |

#### dynamic（3 项）

| 原始工具名 | 属性 / 说明短标题 | advertised 输入（类型/必填/默认/枚举） | 固定源码定义 |
|---|---|---|---|
| `enable_toolset` | R/A / Enable a toolset | `toolset!s` | [dynamic_tools.go:22](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/dynamic_tools.go#L22) |
| `list_available_toolsets` | R/A / List available toolsets | `无` | [dynamic_tools.go:62](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/dynamic_tools.go#L62) |
| `get_toolset_tools` | R/A / List all tools in a toolset | `toolset!s` | [dynamic_tools.go:96](https://github.com/lockon-n/github-mcp-server/blob/ef07feb90b95893767c106067868735d9f550ba6/pkg/github/dynamic_tools.go#L96) |


### 2.3 必填、默认、枚举和输出契约

公共参数 parser 为 `S/pkg/github/server.go:35-188,192-295`：RequiredParam 拒绝缺字段、错误类型和零值；RequiredInt 从 float64 转 int，不能自行把它加强为“所有小数都拒绝”。OptionalInt 也先转 int，WithDefault 版本在结果为 0 时使用默认值。专用 `OptionalStringArrayParam` 接受 null 转空、`[]string` 或逐项检查 JSON 解码后的 `[]any`；通用 `OptionalParam[T]` 只做直接类型断言，不能把前者行为推广到所有数组参数，`cwes` 的冲突见下文。只有部分 typed handlers 用 typed 解码。P schema min page=1、perPage=1..100，handler 默认 page=1/perPage=30；C 默认 perPage=30/after 空。schema bounds 与 handler/后端拒绝需分别取样，不能假设广告 schema 自动执行全部校验。

| 能力族 / 完整状态依赖 | 默认、约束及易混淆输入 | 返回 content/元数据、错误与既有/未来价值 |
|---|---|---|
| repos 与 Git 文件 | `create_or_update_file` 的 M 输入 content 是文件正文字符串；handler 取 `[]byte(content)`，SDK JSON 序列化时才为 REST 编成 base64，更新带 blob sha。push_files content 同样是普通文本，files 子对象只含必填 path/content，schema additionalProperties=false，写树 mode 固定 100644；create_branch 未传 from_branch 时查真实 default_branch；delete_file 自行读取树并建提交，不要求用户 sha。create_repository private/autoInit 缺省经 bool 零值为 false | 多数 text 中 JSON：Repository、Ref、ContentsResponse、Commit、tag/release 对象/列表。fork 遇 AcceptedError 返回普通文本“进行中”。get_commit include_diff 默认 true；list_commits 转 MinimalCommit。当前多任务使用，未来版本迁移/修复/发布链基础。编码证据见下文 G-01；其他证据 `repositories.go:120-205,380-582,799-963,964-1406` |
| get_file_contents / raw | path schema optional default `/`，handler 却 RequiredParam(path)；sha 优先于 ref 解析。目录要尾 `/`，返回最小 directory entry 数组；文件先 Contents 取 SHA/size，再 raw 取内容；>5MiB 只元数据，encoding=none/content空；text/json/xml/javascript 为 text，其余 base64 | text JSON 含 type/encoding/size/name/path/content/sha/url/git_url/html_url/download_url；目录有 type/name/path/sha/html_url 等最小字段。SHA/ref 路径存在不一致见 §6；不应统一改成 raw text 或 image content。`repositories.go:583-797,1812-1876`；`minimal_types.go` |
| 搜索 / 用户组织 | query 必填，search_users/orgs 在没有 type: 限定时追加相应类型；search_issues/search_pull_requests 有 owner/repo 可选和各自 is: 限定。仓库 minimal_output 默认 true；sort/order 支持值以每行源码为准（user/org 为 followers/repositories/joined，order asc/desc） | JSON text 搜索 envelope 保留 total_count/incomplete_results/items，最小投影不等于全量 REST 响应。搜索索引、ACL、匹配与直接读共享状态；不能直接把 Git grep 当完整 GitHub 搜索。现有检索任务，未来跨 repo triage。`search.go:17-346`、`search_utils.go`、`issues.go:705-748`、`pullrequests.go:692-735` |
| issues / sub-issues | list_issues 用 GraphQL，state OPEN/CLOSED，orderBy CREATED_AT/UPDATED_AT/COMMENTS，direction ASC/DESC；handler 默认两种state均查询、CREATED_AT/DESC。update_issue state 小写 open/closed，数组不是自然语言；sub_issue_id 是全局 issue ID，不是 issue_number；replace_parent 控制父子，reprioritize 的 before_id/after_id 在 OptionalInt 转换后必须**恰好一个非零**；两个都省略/转为零或两个都非零均为 tool error（G-03） | JSON text issue/comment/子项及 connection 信息；同 repo issue/PR 编号与全局/node ID 必须映射。`list_issue_types` schema 只 owner，但 wrapper 必取未声明 repo，按广告参数会 tool error，应建缺陷回归而非假成功。当前 license/tracker，未来依赖拆分/排序/归档。`issues.go:148-704,750-1325`、`issues_prs_wrappers.go:41-45` |
| PR / reviews | head/base 指向现存 refs，可跨 fork；draft 与 maintainer_can_modify 可选。merge_method=merge/squash/rebase；update_branch expectedHeadSha 为并发前提；review event APPROVE/REQUEST_CHANGES/COMMENT；subjectType FILE/LINE，side/startSide LEFT/RIGHT，位置必须属于该 diff；每 principal 每 PR 的 pending review 关联真实节点 | get/list/status/files/comments/reviews 为 JSON text；diff 是普通 diff text。创建/提交/删除 review 多为成功短文本，不回传新 review ID；add_comment 通过 viewer 查询最近 pending review，源码注释里的 pullRequestReviewID **未暴露**。update_pull_request 的 REST edit、GraphQL draft 切换、request reviewers 分步，可能部分成功。未来协作审核/冲突恢复价值高。`pullrequests.go:211-485,1116-1728` |
| Actions / 执行 | workflow_id 字符串接受数字 ID 或文件名；dispatch ref 必填、inputs object 的值需适合 workflow 输入；run/job/artifact 各自 ID。job logs 模式：failed_only=true 必须 run_id，否则 job_id；tail_lines=500，最多内容窗口行数，return_content=false | 列表为 workflows/runs/jobs/artifacts 等 API JSON envelope；dispatch/rerun/cancel/delete-logs 返回含 HTTP status/status_code 的说明 JSON；queued 不等于 completed。run logs/artifact 下载工具给临时 ZIP URL，并不直接给 bytes；job logs 可给 logs_url 或 logs_content/original_length，failed_only 可在总结果内逐 job error（不全失败）。`actions.go:26-1223`；未来 CI 调试/重试/产物链，不是当前任务最小集 |
| code/secret/Dependabot/advisory | code state open/closed/dismissed/fixed，默认 schema open，severity 见源码；Dependabot state open/fixed/dismissed/auto_dismissed、severity low..critical；secret state open/resolved，resolution 枚举、secret_type 过滤；global advisory type reviewed/malware/unreviewed（schema default reviewed）、ecosystem/CVE/GHSA/CWE/time filters；其中 cwes 虽声明 array，标准 JSON 调用提供数组/空数组/null 都无法通过 `OptionalParam[[]string]`，省略才返回该参数零值（G-02） | JSON text 原始告警/公告对象或列表；cwes 类型失败返回 text+isError，不能伪造成功筛选。未暴露 alert update、security scan 执行或公告写入，不能从后端有此 API 自动加工具。已存在告警须关联代码 revision/location、依赖/版本，LLM 不凭请求编造扫描结果。当前7任务未见证据，未来安全排查与修复后验证；源码各表行 |
| notifications | filter=default/include_read_notifications/only_participating；时间字符串解析；owner/repo 必须配对才用 repo 通知；dismiss state=read/done；订阅 action ignore/watch/delete | JSON text notification/thread/subscription；部分写返回短文本。subject URL 可解析到同一 issue/PR/commit，unread/last_read_at 与主体绑定；不能把 mark-all 变成删通知。当前7任务未见，未来工作队列与审批。`notifications.go:19-525` |
| discussions / context / Gist | discussions/categories 允许省 repo 查组织；list_discussions 指定 orderBy 时还需 direction；category 为 ID；get_teams user 缺省当前身份；get_team_members 首100，无工具分页；gist create public 默认 false，单次 create/update 只有 filename/content 一文件 | discussion/comments connection JSON text，context 最小用户、org/team、member login 列表，gists GitHub对象 JSON text；组织/category/answer/replies 与 ACL 真实关联；Gist owner/版本/files 独立于 repository allowlist。当前未见，未来团队寻址、知识检索、片段分享。`discussions.go:120-530`、`context_tools.go:37-251`、`gists.go:17-266` |
| Copilot / 生成执行 | assign_copilot_to_issue 使用 issueNumber，不是 issue_number；查 suggestedActors 中 copilot-swe-agent、issue node/现有 assignees 后 GraphQL replaceActorsForAssignable；annotation idempotent=true。request_copilot_review 请求 bot reviewer；账号能力不足会失败 | assignment 成功短文本仅证明分配，不能断言 PR 已产生；review 请求成功可为空 text。真实代码生成/验证属于后端异步能力；需要实现时单独执行器及生成代理，不能将此类工具当普通 label mutation。`issues.go:1368-1530`、`pullrequests.go:1798-1863` |
| dynamic / M 管理 | list 无参数；get/enable 的 toolset 为当前 toolsets 枚举；重复 enable 返回 already enabled | JSON text 列 toolsets（enabled 为字符串状态）、tool 数组或成功短文本；无业务状态写。list change 的原始协议与模型工具缓存需同时验证。`dynamic_tools.go:22-124` |

**F：G-01 编码层次。** `repositories.go:399-401,428,441-448,465` 将 M 字符串正文直接转 bytes；[go-github v74.0.0 `RepositoryContentFileOptions`](https://github.com/google/go-github/blob/v74.0.0/github/repos_contents.go#L54) 的 Content 是未编码 `[]byte`。固定源码 `repositories_test.go:1095-1108` 也将 M 正文和预期 REST base64 分列。本轮只读该测试，没有执行。设计必须保留 `M 正文→REST base64→Git/raw 原始 bytes`：M 传 `Hello` 时落文件为 `Hello`；M 传 `SGVsbG8=` 时落文件应为这 8 个字面字符，不能预先解码成 `Hello`。直接 X REST 调用的 content 才遵循 REST 的 base64 契约。

**F：G-02 与 G-03 参数分层。** `security_advisories.go:94-96` 的 cwes 使用通用类型断言；[mcp-go v0.36.0 `CallToolParams/GetArguments`](https://github.com/mark3labs/mcp-go/blob/v0.36.0/mcp/tools.go#L54) 保留 `Arguments any` / `map[string]any`，标准 JSON 数组解码为 `[]any`，不能断言成 `[]string`，null 也不匹配。此为固定调用链的静态推导；内部测试直接构造 Go `[]string` 不能证明原始 JSON 调用成功。`issues.go:640-655` 则先把两个定位 number 转 int，再检查零值互斥；例如 after_id=0.5 且 before_id 省略会落入两者为零的错误，after_id=1.5 且 before_id=0 会向后端传 after_id=1（后端仍可因 ID/权限等拒绝）。不能将广告 number 改成 integer 并称严格兼容。两项均需原始 JSON-RPC 负例；修复参数转换只能进入另行版本化的修复 profile。

**F：错误分层。** 参数、permission wrapper 与 `pkg/errors/error.go:110-124` 返回 `CallToolResult` 的 text+isError=true；其他 handlers 直接返回 Go error（如部分网络、GraphQL、marshal 失败）。[mcp-go v0.36.0 `server/server.go:1030-1067`](https://github.com/mark3labs/mcp-go/blob/v0.36.0/server/server.go#L1030) 将未知工具变为 JSON-RPC INVALID_PARAMS，将 handler error 变 INTERNAL_ERROR，不应统一改成 isError。普通成功 JSON 是 text content，不是 structuredContent；短文本/空 text、部分结果内的 error、下载 URL、资源的 MIME/URI 单独保留。Toolathlon 将 content 投影给模型，可能丢顶层 isError（`utils/openai_agents_monkey_patch/custom_mcp_util.py:176-229`）；须同时保存原始结果和模型可见结果。

### 2.4 Resources、prompts 与协议

**F：** `S/pkg/github/repository_resource.go:23-64` 注册五种模板：`repo://{owner}/{repo}/contents{/path*}`、`repo://{owner}/{repo}/refs/heads/{branch}/contents{/path*}`、`repo://{owner}/{repo}/sha/{sha}/contents{/path*}`、`repo://{owner}/{repo}/refs/tags/{tag}/contents{/path*}`、`repo://{owner}/{repo}/refs/pull/{prNumber}/head/contents{/path*}`。参数来自 URI；PR 模板先取 head SHA；目录/空 path 返回 error；text 或 application MIME 返回 TextResourceContents，其他 MIME 用 base64 BlobResourceContents；`.md` 强制 text/markdown，含原 URI 与 MIME（:68-190）。与 get_file_contents 的 application MIME 判定不完全相同，不能强行统一。未套 repoChecker；未见静态 resources、Git 文件变化触发订阅推送的业务实现，虽 server 宣告 resource subscription/listChanged（`server.go:15-29`），真实订阅行为 U，不能凭 capability flag 承诺通知齐全。

两 prompts 为 `AssignCodingAgent`（必填 repo=`owner/repo`，`issues.go:1556-1593`）及 `IssueToFixWorkflow`（必填 owner/repo/title/description；可选 labels/assignees 逗号串，`workflow_prompts.go:13-75`），返回固定 user/assistant text message 列表。它们提供工作流文本，本身不创建资源、不执行工具；这是服务原本提供的帮助，不能扩写任务答案。stdio JSON-RPC initialize/tools/resources/prompts/logging 的行为随 mcp-go 固定版本验证；原始工具名经 harness 变 `github_<tool>`，不能在 dispatch 改名。

## 3. 领域状态模型

以下均 D；GitHub 的 Git 对象 API 及 tree mode/type/SHA 关系以 [官方 Git database 文档](https://docs.github.com/en/rest/git) 和 [tree API](https://docs.github.com/en/rest/git/trees) 为规范参照（查阅 2026-09-10），实施时冻结后端日期/profile。

| 持久化实体 | 字段、关联和不变量 | 派生/多入口映射 |
|---|---|---|
| Principal / Credential / Org / Team | login、numeric ID、GraphQL node ID、主体类型、membership/role、repo grant、scope/expiry、bot availability；模拟 credential 与 episode 绑定 | REST user、GraphQL viewer、Git HTTP/SSH、raw/download、gh 同一主体；wrapper currentUser cache另建会话状态，不能代替 ACL |
| Repository / Alias / ForkNetwork | numeric/node ID、owner/name/default_branch、visibility、archive/disabled、has_issues、merge policies、rename aliases、parent/source；同 episode owner/name 唯一 | rename 不改变对象 ID；fork 与独立 mirror clone 不同（Git 图相同不代表 fork关系相同）；URL 从路由 manifest派生 |
| Blob / Tree / Commit / Tag / Ref | 用真实 Git 产生 bytes/hash、tree mode/path/type、parents、author/committer/time/message、signed/verification 元数据与 ref tip；不可变对象，ref CAS 更新 | REST contents/Git database、raw、M resources、Git clone/fetch/push同对象图；文件存在性由 tree决定，不另维护互相矛盾的“文件表” |
| WorkingCopy / LFS / Asset | 本地 index/worktree属于工作空间；LFS pointer 保存 oid sha256/size，真实大文件是独立 blob；release assets和Actions ZIP各自ACL/expiry | 本版无LFS工具；Git/raw/CLI profile若接收LFS必须分清 pointer与materialized bytes，未支持明确拒绝，不把指针文本当完整模型/数据；大文件未检出当前任务直接使用 |
| Issue / PR / Label / Milestone / IssueType / SubIssue | issue 与 PR 共用 repo 内 number空间，但 numeric ID/node ID各自有类型；PR扩展base/head repo/ref/sha、mergeable/merged/merge_commit；子项唯一父/无环/有序；内容/状态/assignees/labels历史 | REST issues和pulls的重叠投影，GraphQL类型、搜索节点、notification subject均映射同身份；仓库移除/无权限使关联查询按契约不可达 |
| Comment / Review / ReviewComment / Discussion | author/body/edited/deleted/timestamps，review pending/submitted/dismissed、event、commit、diff line/side/path；每主体pending review约束；discussion category/answer/reply结构 | diff位置与固定commit绑定，过时comment不静默迁到新行；评论编辑与回复引用保持关系；M未暴露的创建能力可用于合法初始数据或明确X层 |
| Notification / Subscription | 主体、repo、subject类型ID、reason/unread/last_read_at、thread与repo订阅/ignore | 独立业务事件推进 unread；GET不默认自动标读；mark-all以时间界限和范围处理 |
| Workflow / Run / Attempt / Job / Artifact / Check | workflow文件revision、event/ref/headSHA/inputs、trigger actor、queued/in_progress/completed及conclusion、attempt、job/step依赖、logs、billable/usage、artifact bytes/digest/expiry | 支持工作流真实执行生成状态与产物；rerun保留历史attempt；cancel与完结有合法竞态，delete logs不删除运行；通知/PR status同一事件投影 |
| Alert / Advisory / Dependency / CopilotTask | GHSA/CVE/CWE、ecosystem/package/version range、severity、state/location/commit、repo可见性；Copilot执行任务关联issue/PR/review/commit/job | 安全告警初态必须可追溯到已定义分析或已知记录；非实际scan不能声称“已检查全部代码”；Copilot提交来自真实生成和执行记录 |

搜索索引、计数、diff/mergeability、URL、connection cursor均可派生，但索引水位/构建版本要快照。精确 Git 数据不能由LLM维护。普通 patch、issue create等按API真实提交边界事务；`push_files`为读ref→建tree→建commit→非force更新ref，最后冲突时孤立Git对象可存在，但分支仍旧；`update_pull_request`多API不可全回滚。跨服务HF数据集链接/Notion页面/邮件引用存来源ID、revision、内容hash，复制与活引用分开，各自授权。

本地路由同时覆盖 API、GraphQL、raw、uploads、Git smart HTTP/SSH、临时artifact/download、网页 URL。固定 host hook 使用 `S/internal/ghmcp/server.go:354-405` 的 GHES `/api/v3`、`/api/graphql`、`/raw`，通过 URL.Hostname 丢弃端口，不能直接声称 `--gh-host http://localhost:8000` 可用；应选受控主机名+80/443网关，或日后显式版本化 transport 改造。本阶段不实施。硬编码 github.com 的 X 入口需可审计的 transport/URL适配；不能仅改M endpoint。

## 4. 代表性交互序列

以下 D，超出现有任务固定流程；oracle 不按调用顺序打分。

1. 创建repo→建branch→M create_or_update_file写正文→M push_files写多文件→Git fetch读同commit→X REST以合法sha和base64修改一文件→M resource按旧commit读旧内容→按branch读新内容→delete_file→旧commit仍可读。独立比较M正文、REST解码后bytes、Git/raw内容与hash/parents/tree/ref，加入字面`SGVsbG8=`避免误解码；其他文件不变，不把删除当前路径等同抹去历史。
2. 搜索相似repo→分多页定位→按owner/repo列issues→建父/子issue→先重排再替换父（另一路先替换再重排）→search/direct-read/notification比对。断言number≠global ID、树无环、分页不重不漏，缺权限不自动造对象。
3. 两客户端读同branch→分别push_files→一方成功、另一方ref冲突→重取tip并显式合并→创建PR→pending review→加多行comment→submit→另一入口读取。断言失败不覆盖新tip，review位置属于真实diff，pending/submitted生命周期正确。
4. PR含冲突或未满足检查→merge失败→修文件/更新分支→重新运行workflow→检查完成→merge（merge/squash/rebase分别回归）→Git验证父链、base分支和issue/PR状态。断言queued不能被当pass，合并方式改变历史而非只改merged布尔。
5. 读取组织/teams→权限受限repo direct-read失败→用户切到被授权repo成功→相同名字的不同episode repo读写隔离；wrapper个人allowlist与组织放行另设反例。断言服务ACL仍执行、不会因为wrapper放行而越权。
6. dispatch→分页list runs定位自己的headSHA/inputs→get_job_logs失败模式→下载artifact URL并校验bytes→rerun_failed_jobs→删除logs→旧URL过期/读logs失败，artifact按独立有效期行为。断言attempt历史、取消竞态和每job error均保留。
7. HF dataset/model card携GitHub issue链接→查repo license/commit→合法评论写回issue→把有版本的文件摘要复制至Notion→各入口复查。断言跨服务URL/ID存在、来源hash可追溯、无默认跨服务授权。
8. dynamic从空业务toolset开始→get_toolset_tools→enable repos→list_tools与缓存比较→试resources/prompts→启用issues再取prompt；对照初始显式启用issues/repos。断言dynamic只增加工具的固定实现差异被发现，不臆造资源注册。
9. 合法含缺陷的profile：缺path的get_file_contents、list_issue_types仅owner、sha/ref冲突、cwes省略与显式JSON数组/null、reprioritize双定位/零/小数分别走相应失败、转换或不一致回归；oracle指出偏差。这些轨迹独立标签，不作为鼓励错误行为的主训练数据。

## 5. 候选实现与推荐

I/S/C/T/D/P按共享定义。下表是D的可达到范围和相对成本；未测性能，不给伪精确兼容评分。

| 路线 | I / S / C / T / D / P | 开发、运行、维护与适用边界 |
|---|---|---|
| 保留固定 MCP，替换HTTP后端（首选） | I近源码精确；S/C取决于Git+领域内核；T需另建；D可生成；P有stdio/API开销但无逐调用LLM | 接口维护较少，REST/GraphQL/raw适配开发高；可复用真实Git。保留版本缺陷；host丢port与X硬编码路由必须解决 |
| 有状态MCP facade + 共用API（备选） | I需完整94/资源/prompt与错误快照；S/C/T可精确支持；D/P可控 | 更容易本地隔离、修复兼容问题，但重复wrapper逻辑、维护成本更高；必须按版本标兼容/修复profile |
| 只实现本地HTTP/API | 对MCP契约仍需原server/facade；对X价值高 | API内核是共同必要组件，单独API不是完整M替代；不需实现GitHub所有REST路径但必须覆盖每个已支持工具的真实下游调用 |
| SDK/client适配 | M Go client transport + X requests/Git/gh可共享状态；I靠上层 | 集中endpoint/credential映射可用；逐函数monkeypatch易漏REST/GraphQL/raw/重定向且隐藏真实HTTP错误；不能当唯一底座 |
| Gitea v1.24.6 + GitHub兼容层 | Git对象/部分repo/issue/PR可复用；M I/API S/C不直接兼容；T和UI不同；D可seed；P需测 | 官方Swagger见下；需要大量翻译和补实体，尤其GraphQL/Git写接口/Actions/安全/Copilot；自控Git托管候选，不是可直接换URL的GitHub模拟器 |
| git-http-backend / Git plumbing + 自研metadata | Git S高、跨入口同图容易；issue/PR/ACL/API皆需自建 | 比Gitea更小的语义冲突，但repo/用户权限与HTTP facade工作更多；首选中最小可控Git执行底座 |
| 静态fixture/HTTP replay | I黄金样例可精确；S/C仅限已录顺序，T/D贫乏；P高 | 适合只读契约回归与故障样例，不适合随机写入/并发和未来任务；不可按答案选择下一条返回 |
| LLM主导+外部状态校验 | I需确定性渲染；S/C/T若完全校验，优势主要剩内容；D高潜力；P贵且波动 | 快速样例成本低，长期每调用费用高；执行/搜索/版本校验仍需代码，无法省掉核心内核 |
| 混合（建议） | I/S/C/T走代码+Git；D由LLM合法生成；P大多数调用快速路径 | 一次初态生成摊销；Copilot限定执行profile在线生成；保留模型调用/patch/验证日志，维护双系统但按能力限制复杂度 |

**F：现成底座已核实际接口。** [Gitea v1.24.6 官方 Swagger 源](https://github.com/go-gitea/gitea/blob/v1.24.6/templates/swagger/v1_json.tmpl) 的 basePath 为 `/api/v1`；存在repo/contents、issues/pulls/reviews、Git blobs/trees/refs读取、Actions workflows/dispatches/jobs logs/artifacts等路由。该规范Git blobs/trees/commits/refs未提供GitHub对应的POST建对象/PATCH更新ref接口，故原MCP `push_files/delete_file`不能靠路径前缀替换；需直接Git执行或专门兼容API。该规范无GitHub GraphQL `/graphql`/node mutations、Copilot、安全扫描/Dependabot/advisory等同名路由；不能推断所有平台功能绝对不存在，但足以否定本版无适配直连。GitHub内容写PUT、Gitea区分POST创建/PUT更新及字段/错误同样要翻译。官方 [Actions差异说明](https://docs.gitea.com/next/usage/actions/comparison) 也明确与GitHub有差异，且`uses: actions/...`可触发公网下载；next文档仅作风险参照，不能代替v1.24.6行为快照。查阅均2026-09-10。

不推荐为了已有任务只保留repo/contents而遗漏另外工具族。P0可先交付窄profile，但所有已核实工具继续保留“分期/不支持”矩阵；未支持功能返回原包装内显式模拟器不支持错误，不编造已执行。

## 6. 保真缺口与取舍

| 能力 / 分级 | 具体偏差与取舍 | 错误学习风险与验证 |
|---|---|---|
| I契约、Git读写/基础issue/PR：可依据固定源码准确 | 用原server保description/schema/错误；Git生成真hash/parents；状态内核统一各入口 | 只造40位sha会使Git fetch/compare失败；独立git fsck/cat-file/diff/rev-list验图，含空repo/二进制/大目录/旧revision |
| 文件写编码：各入口精确（G-01） | M create_or_update_file收正文，SDK编码成REST base64，后端解码得到Git bytes；M facade不得提前decode，X REST保留自身编码要求 | base64样式正文被误解码会改变文件/hash；使用Hello、字面SGVsbG8=、Unicode/换行跨M/REST/Git/raw逐层比对 |
| 固定wrapper缺陷：准确兼容但隔离 | readonly env绑定冲突、owner-only list_issue_types被wrapper要求repo、path optional却handler必填；广告schema和实际handler各自保留 | 修复profile改版本，兼容缺陷轨迹不进主能力训练；必须对省字段、显式字段、CLI/环境配置逐项差分 |
| 参数转换：strict与fixed分开（G-02/G-03） | cwes广告array与通用[]string断言冲突，JSON数组/null失败；reprioritize广告number先截为int，再要求恰一非零定位 | 用原始JSON-RPC验证省略/数组/null及双给/零/小数；不得凭Go typed测试宣称wire成功，不自动修数组parser或强化schema |
| get_file_contents sha/ref：已发现源码偏差 | `repositories.go:635-648` rawOpts先解析sha/ref，而Contents元数据仍用原ref；:685-717 raw用rawOpts。两revision同路径不同bytes时可能SHA/size来自ref、content来自sha，甚至先因错误ref失败 | 后端各endpoint必须忠实各自请求，不为凑响应偷偷改内容；独立检查response sha与blob bytes、保存偏差profile；不要学“SHA与内容无关” |
| 搜索与分页：限定语义准确、排序近似 | 支持经差分的GitHub query qualifiers/boolean/日期/语言等；全文相关性/索引延迟无法靠简单LIKE重现；工具无翻页参数处保截断，如team members first100、failed job helper只取首页 | 总是命中目标/强行全量翻页会降低真实搜索迁移；holdout查询/噪声数量/索引水位/不完整结果/截断专测，不宣称完整搜索语法 |
| PR合并/审核/branch policy：基础精确、长尾分期 | 真实merge/squash/rebase和冲突；权限/required checks/review dismissal/保护分支规则按profile实现；REST+GraphQL多步部分失败保留 | 只翻merged布尔、所有检查立即完成会训练错误流程；Git历史、check/review状态与merge授权独立核验 |
| Actions与安全执行：高成本分期 | 可先支持读取合法预置历史、异步dispatch/cancel/retry状态及限定真实工作流执行；任意runner环境/marketplace action/安全扫描全覆盖不承诺 | 禁止LLM造日志、测试通过或扫描无漏洞；未知workflow明确不支持，execution profile用实际exit code/artifact hash，读取历史注明来源不是本轮执行 |
| Copilot：真实M已暴露、服务结果分期/U | bot assignment/review request可精确状态机；代码解决能力/生成分布与账号plan相关，需真正受控生成+执行 | assignment成功≠PR成功。若仅模拟可用性缺失按真实错误返回，若宣称bot可用须实现生命周期，不能永远queued掩盖无执行 |
| 文件/LFS/URL/UI：部分精确、额外入口分期 | 常规Git/raw资源精确；LFS pointer/object/下载签名及GitHub页面在X profile分别实现；M >5MiB/目录/MIME投影保留 | 不可访问URL、LFS假bytes、Gitea界面冒充GitHub会破坏跨入口任务；多入口内容hash/授权/到期、浏览器页面契约单独验收 |
| 权限、限流、时间：核心精确、政策U | 后端ACL独立于wrapper，case/canonical repo、rename alias、撤销token、404隐藏、scope、primary/secondary limits按冻结profile | “只有allowlist就是安全”“重试永远成功”“read都会立即搜到”均有害；真实只读记录校准错误/headers/索引延迟，未来受控写入再验 |

不在本版M的repo删除、任意GraphQL工具、上传release asset、创建discussion、管理branch protection、LFS管理不能擅自增加工具；X初始化已用的删除/启用issues/Git mirror则必须有相应模拟入口。GitHub Actions/生成器可以执行代码是本版M支撑语义，不能因7任务未用而省略最终设计。

## 7. LLM 仿真可行性

**D：推荐混合但在线主路径为代码。** LLM预生成业务repo/README/issue/comment/discussion/合理commit message、安全告警背景等内容，经构建器落库；它不能将普通API“存用户给的body”改成替用户写答案。安全告警实际字段由已定义分析/规则/记录提供，LLM只作可验证的说明文本。Copilot代码/评论属于原生允许的生成行为，适合限定在线LLM，但生成代码还须执行器和独立测试验证；不能因为GitHub工具难实现而把Git操作/GraphQL筛选交给LLM猜。

| 路线 | LLM可决定 / 外部必须决定 | 保真、开发和长期成本 |
|---|---|---|
| 代码主导 | LLM无在线职责，可不用LLM初态 | 写Git/ACL/状态规则成本高、契约可复用；每工具0仿真模型调用，长期稳定、易测；自然语言分布需额外生成器 |
| LLM主导 | 检索到相关状态后提出字段投影/变更/解释；不得改agent参数、增不存在资源、造执行结果 | 降低部分内容规则开发，仍需完整schema/ACL/ID/事务/查询/Git校验；读也校验等价查询后往往重复做工，单调用与长序列成本高；只作为对照 |
| 混合 | 离线多样内容；可用Copilot任务内受控代码/评论生成；其余确定性快速路径 | 内容成本按episode摊销，线上f低；开发保留代码内核+生成器/validator双系统，但减少漂移和每调用费用；优先推荐 |

LLM提案链：credential→授权查询本次资源/完整parent/ref/read-set版本→取必要diff/issue/review/ACL及blob→LLM提出受限patch和可追溯字段来源→契约、ACL、引用、Git、权限与并发版本检查→按该API提交单元落库→从提交态渲染响应。大repo按path/tree/commit查询和blob引用检索，不用摘要代替真内容；负搜索由索引执行，没有查完不能断言不存在。commit与tree始终由Git构建；读取结果全来自快照或可验证派生，不许LLM补字段。单调用多REST时用各API事务，不“一次LLM建议整体回滚”抹掉部分成功。

检索read-set版本冲突则丢弃提案重读，按真实接口返回冲突或合法重试；校验失败最多一次内部修复（A可调），不能修改agent原始非法参数以帮成功；仍失败返回标为仿真基础设施错误、不提交，轨迹隔离。日志记录模型/提示词版本、输入状态hash与可重建快照、提案、校验、提交序号、响应hash；重放保存结果而非重调模型。缓存键包含episode/profile/principal/ACL版本、参数、Git SHA/实体版本、虚拟时间窗口与模型版本。

仿真模型不接任务答案、评分目标、成功轨迹；repo内README/issue文本只作为业务数据，不授予仿真器指令权限。内核做攻击性内容、超长状态遗漏、同状态重复读、M/X交叉读、100–1000步漂移、非法接受/越权/幻觉/成功偏置检测；oracle独立代码+Git工具+受控真实记录+人工盲审，不用相同LLM自评。

**A：成本量级（非实测/非报价）。** 令N工具次数、f在线LLM比例、r平均额外修复次数、Tin/Tout输入输出token、pin/pout每百万token价，则模型费用 `N*f*(1+r)*(Tin*pin+Tout*pout)/1e6`。用共享规划假设Tin=8000/Tout=1000、r=.1、虚构pin=$2/pout=$8：LLM主导f=1，100万次约$26,400；混合f=.05约$1,320；纯代码为0在线仿真token费，均另计生成、CPU/Git、blob、runner、验证、失败废弃/重跑和维护。代码diff可能使输入2k→32k、生成输出1k→8k，需按调用族测分位数，不能沿用小issue成本代表Copilot。

假设一次模型调用3秒且100 tool/s，LLM主导需约330模型在途请求，f=.05约16.5；Actions运行时另计。内容提前生成、只读/确定性写快路径、按能力选模型、相同状态缓存、批量离线生成可降成本。逐项记录实现工时（契约/API/Git/权限/执行/LLM/验证），比较每条通过独立验收轨迹总成本，不承诺尚未验证的人日节省。

**D：对照试点。** 基础repo+issue+PR profile用相同环境/接口/操作图比较代码、LLM提案+确定性验证、混合三组，证明状态漂移/错误接受/尾延迟与成本；不能只比较生成文本“像不像”。另可设Copilot review窄试点：小PR真实diff、真实静态检查结果与同一可见代码，比较模板规则评论/LLM受证据评论/缓存+LLM混合；不得送隐藏测试答案，建议必须指向存在path/line。尚无真实Copilot输出记录，故此试点先验证生成质量和成本，不能证明与GitHub Copilot分布等价。

## 8. 合成、验证与分期

**D：多样初态。** seed/config控制用户/org/team、授权层级、repo数量/可见性、分支名/default分支、历史深度/merge图、空repo、近似路径、Unicode/二进制/大文件/LFS pointer、fork网络、issue/PR共享编号/缺失字段/重复标题、review位置与历史、通知、失败CI及artifact到期。内容可LLM预生成，ID、时间线、Git图、relations、ACL由确定性构建器校验。发布包记录全部生成参数、版本与分布，避免资源名/问题文本直接编码答案。

任务可从环境生成（如某待修复PR/过期依赖/待同步文档）或按任务约束构建环境；验证存在合法主体/工具profile/可达资源/允许操作路径。oracle只验目标状态和允许副作用，接受不同合法顺序、不同正确代码实现与提交数量；任务生成器与环境/API及评分器分开，隐藏groundtruth。

| 验证组 | 设计验证/独立证据 | 阶段与边界 |
|---|---|---|
| 契约 V01–03 | 91业务+3dynamic逐工具声明/实际handler、全部枚举/默认/错误、5resources/2prompts；all/子集/dynamic/CLI readonly/环境readonly/allowlist组合；原始JSON-RPC与harness投影双快照 | 可用固定源码和现有60份工具snapshot作部分对照，snapshot不完整；无业务写条件下未来受控tools/list可补，当前未运行 |
| 状态/组合 V04–05 | §4操作图随机拓扑、缺字段/错类型/zero/fraction/越界、空数组/重复/非法ref/path/旧sha；git fsck、独立tree/diff/parent检查；issue/PR编号/子项无环/ACL/review状态不变量 | 不复制服务handler作唯一oracle；mutation测试故意引入假成功/错sha/遗漏权限，确认能抓住 |
| 跨入口/身份 V06–07 | M写→Git/REST/raw/GraphQL/resource读，Git push→M读，gh路径按manifest核对；rename、revoked token、组织/个人allowlist、下载URL到期 | 当前真实REST/Git调用源码可定路径，行为差分需未来专用账号、授权资源；不在此阶段写真实服务 |
| 隔离/恢复 V08–09 | 相同可见repo名跨episode、两个客户端更新ref、reset后旧URL/cursor/job/LLM提案拒绝、崩溃发生在建tree/建commit/更新ref前后、fork/Action中途 | bare repo/blob基线只读+每episode refs/metadata overlay，锁粒度repo/ref，event队列带generation；日志重建hash一致，避免重放非幂等create |
| 分布/新结构 V10 | 30+未见seed、未见语言/业务域/调用图、长链100–1000步、搜索噪声/同名资源/权限差异、动作顺序holdout | finalpool七任务为部分回归，不作为能力分母；报告hard fail率和模板泄题指标 |
| LLM/性能 V11–12 | 资源/执行结果幻觉、错误接受、帮助偏置、注入、漂移、响应/提交不一致；三路线同profile后测tool/s、p95/p99、token/修复/执行成本和有效轨迹成本 | 先通过相同保真门槛再比吞吐；计划1→10→100→1000 episode梯度，不代表已测 |

交叉审查补充的必测契约（D，尚未执行）：

| 问题 | 输入/独立观察 | 严格固定版本的预期与负例 |
|---|---|---|
| G-01 正文与编码 | M content依次为`Hello`、`SGVsbG8=`、Unicode/换行；观察实际REST body，再用Git cat-file/raw独立读bytes | Hello对应REST `SGVsbG8=`，落Git仍为Hello；M字面SGVsbG8=落Git必须原样8 bytes，禁止预decode；对应blob SHA由独立Git产生 |
| G-02 cwes wire类型 | 原始JSON中省略cwes，以及`["CWE-79"]`、`[]`、`null`；专用OptionalStringArrayParam路径另作对照 | 在其余前提成立时省略仅继续后续参数/API处理；后三者在cwes处text+isError且不发公告列表请求。不能用内部map里的Go []string替代wire用例；fixed profile另验显式数组筛选 |
| G-03 排序定位 | 两者省略、两者0、两者非零；一个0另一个合法非零；after_id=0.5/1.5且另一参数省略或0 | 前三类均tool error且子项顺序不变；单一非零才继续后端。0.5截为0后报缺定位，1.5截为1后继续真实ID/权限检查；原始schema仍为number，不能伪称所有小数在schema拒绝 |

后续差分采用冻结版本/账号plan/权限的专用GitHub org和可回收repo；真实写入/Actions触发需后续明确授权及封闭runner/依赖/配额，本阶段仅列条件。ID保持一致双射及引用关系；Git若相同bytes/author/committer/time则比较真实SHA，否则比较映射后的父图/树/bytes，不简单删sha；时间比较字段语义/精度，搜索比较支持qualifier/集合与分页边界，相关性近似单列，异步比较合法状态偏序及终态。下载URL比较目标bytes/ACL/expiry。readonly/allowlist源码缺陷由契约profile明确记录，不能以oracle接受错误来提高“通过率”。

P0：先冻结完整契约和配置，打通真实Git+REST/GraphQL核心身份/repo/file/issue/PR/review与必须X入口、错误/冲突/部分失败、独立oracle和episode隔离。P1：搜索扩展、subissues/team/discussion/Gist/notification、release/历史安全告警读取、资源/提示完整交互与数据分布。P2：经差分Actions真实执行与更全branch policy/安全分析、LFS/大资产、Copilot生成执行及GitHub UI profile。P1/P2已暴露工具始终列为未完成，不能在P0宣称全91兼容。扩容前按共享G0–G5门槛：契约覆盖、关键不变量/非法接受/越权/假成功硬错误零样本、至少3000独立检查机会、组合holdout、隔离与回放、再比较成本；零样本不代表总体零风险。

## 9. 待确认与审查记录

| 状态 | 问题 / 所需证据 | 当前处理 |
|---|---|---|
| U | binary真实构建/运行依赖、tools/resources/prompts列表及环境继承；readonly变量在实际binary是否存在同缺陷 | 源码和Viper固定依赖证明绑定冲突；不把示例read-only当运行事实，后续受控无业务调用捕获契约 |
| U | resource订阅、dynamic list_changed与Toolathlon缓存、列表分页运行行为 | 已分开server capability与业务实现，未来用协议client验证不触真实业务 |
| F/D | allowlist仅个人+部分工具覆盖，create限制与list_issue_types隐藏repo要求 | §2明确并交统筹；backend ACL独立；兼容/修复profile不混用 |
| F/D | get_file_contents path required和sha/ref元数据错配、multiAPI部分成功 | §2/6记录；独立Git oracle必须拒绝不一致；不修改现有server |
| U | 账号plan下Copilot可用性、Actions/安全后端策略、复杂搜索排序与限流真实记录 | 按日期/plan/profile冻结；不能从源码注册推断账号服务可用 |
| U | 现有真实调用轨迹、未声明任务中实际GitHub UI/gh/LFS行为 | 已扫相关任务/公共helper和常见dump位置，未取得可用轨迹；区分URL文本/unused import与业务调用 |
| 非原作者审查已完成 | `/root/snowflake`，`gpt-6-astra / xhigh`，2026-09-10；全文及固定源码复核94工具、schema/默认/错误、wrapper、多入口、候选与执行/LLM/成本/oracle | 发现下列三项P2，作者在同一模型/effort会话中修订完毕；未修改共享文档或任何服务源码，统筹最终确认见review-ledger |
| G-01 / P2 / 作者已修订 | 将M正文误写成base64；`repositories.go:399-401,428,441-448,465`、go-github v74 `repos_contents.go:54-59`、固定`repositories_test.go:1095-1108` | §2/4/6/8和CSV已明确M正文→REST base64→Git/raw bytes，增加字面SGVsbG8=负例；静态证据已核，实际binary跨入口差分仍U |
| G-02 / P2 / 作者已修订 | 泛化数组null处理，遗漏cwes typed断言；`security_advisories.go:94-96`、`server.go:106-119,162-188`、mcp-go v0.36 `mcp/tools.go:54-72` | §2/4/6/8和CSV已区分专用数组parser与cwes的JSON数组/null失败、省略路径、strict/fixed profile；实际wire错误快照仍U，未将修复写成已实现 |
| G-03 / P2 / 作者已修订 | reprioritize误写“至少一定位”；`issues.go:640-655`、`server.go:126-131`证明先转int再要求恰一非零 | §2/4/6/8和CSV已加入双给/省略/0/小数转换反例；保留number schema，后端ID/权限和实际binary差分仍U |

## 10. 能力矩阵行

```csv
object,tool_or_capability,version,operation_type,state_dependencies,proposed_method,llm_role,fidelity_gap,verification_method,priority,evidence
github,toolsets_dynamic_readonly_allowlist,ef07feb90b95893767c106067868735d9f550ba6,read+manage,session toolset principal repo policy,fixed MCP and independent backend ACL,none,readonly env binding and partial personal allowlist,configuration and protocol differential,P0,S/cmd/github-mcp-server/main.go:65-110;S/pkg/github/repo_permission.go:58-95
github,repos_files_git_18_tools,ef07feb90b95893767c106067868735d9f550ba6,read+write,repo blob tree commit ref default_branch,real Git plus REST and raw facade,offline content,M text to REST base64 boundary; sha-ref mismatch and output projection,M literal-base64-text to REST and Git raw bytes oracle,P0,S/pkg/github/tools.go:23-52;S/pkg/github/repositories.go:399-465;S/pkg/github/repositories_test.go:1095-1108
github,issues_subissues_12_tools_without_copilot,ef07feb90b95893767c106067868735d9f550ba6,read+write,issue number nodeID labels parent order ACL,deterministic issue graph and REST GraphQL,offline issue content,list_issue_types undeclared repo; reprioritize exactly one nonzero after int conversion,state invariants plus raw JSON zero fraction and dual-position cases,P0,S/pkg/github/tools.go:53-73;S/pkg/github/issues_prs_wrappers.go:41-45;S/pkg/github/issues.go:640-655;S/pkg/github/server.go:126-131
github,pull_requests_reviews_17_tools_without_copilot,ef07feb90b95893767c106067868735d9f550ba6,read+write,base head graph diff review checks ACL,Git merge engine plus REST GraphQL state,offline comments,partial multiAPI update and branch policy long tail,Git ancestry review state and controlled differential,P0,S/pkg/github/tools.go:82-106;S/pkg/github/pullrequests.go:21-1796
github,copilot_assignment_and_review_2_tools,ef07feb90b95893767c106067868735d9f550ba6,write+execute,bot availability issue PR refs job lifecycle,assignment state plus bounded generation executor,online native code or review generation,account policy and output distribution unknown,actual execution plus independent review evidence,P2,S/pkg/github/issues.go:1368-1530;S/pkg/github/pullrequests.go:1798-1863
github,actions_14_tools,ef07feb90b95893767c106067868735d9f550ba6,read+write+execute,workflow revision runs attempts jobs logs artifacts,deterministic lifecycle plus real bounded runner,offline scenario content,arbitrary workflows runners and marketplace gaps,job exit bytes hashes lifecycle differential,P2,S/pkg/github/tools.go:143-161;S/pkg/github/actions.go:26-1223
github,security_alerts_and_advisories_10_tools,ef07feb90b95893767c106067868735d9f550ba6,read,repo commit location dependency advisory ACL,typed indexed alert state,offline grounded explanatory content,cwes advertised array fails raw JSON typed assertion; scan and backend policy gaps,cwes omitted array empty null wire negatives plus alert revision filter oracle,P1,S/pkg/github/tools.go:107-121;163-169;S/pkg/github/security_advisories.go:94-96;S/pkg/github/server.go:106-119
github,notifications_6_tools,ef07feb90b95893767c106067868735d9f550ba6,read+write,principal subject unread thread subscription,deterministic event projections,offline subject content,partial wrapper scope and timestamp policies,subject resolution and state transition checks,P1,S/pkg/github/tools.go:123-133;S/pkg/github/notifications.go:26-525
github,discussions_4_tools,ef07feb90b95893767c106067868735d9f550ba6,read,repo org category discussion reply ACL,GraphQL connections over shared state,offline discussion generation,search ordering and organization visibility,direct and paginated GraphQL oracle,P1,S/pkg/github/tools.go:135-141;S/pkg/github/discussions.go:120-530
github,context_users_orgs_5_tools,ef07feb90b95893767c106067868735d9f550ba6,read,principal org team membership search index,REST GraphQL identity projections,offline profile content,member first100 and backend search ranking,identity mapping ACL and truncation checks,P0,S/pkg/github/tools.go:74-81;174-179;S/pkg/github/context_tools.go:37-251
github,gists_3_tools,ef07feb90b95893767c106067868735d9f550ba6,read+write,gist owner files revision visibility,deterministic gist store and API,offline snippet content,single-file write interface and ACL,write list and permission differential,P1,S/pkg/github/tools.go:181-188;S/pkg/github/gists.go:17-266
github,resources_5_and_prompts_2,ef07feb90b95893767c106067868735d9f550ba6,read+protocol,repo ref raw MIME prompt params,fixed templates and resource handlers,none,resource allowlist gap and subscriptions unknown,URI MIME bytes prompt and dynamic registration snapshots,P1,S/pkg/github/repository_resource.go:23-190;S/pkg/github/workflow_prompts.go:13-75;S/pkg/github/issues.go:1556-1593
github,X_REST_Git_gh_browser_LFS,repository current plus explicit future profiles,read+write+execute,shared Git and metadata principal blob routes,HTTP transport and real Git with scoped CLI UI adapters,none,hardcoded endpoints and future gh UI LFS unverified,cross-entry hashes identity and unsupported errors,P0,utils/app_specific/github/api.py:16-156;git_ops.py:20-40;helper_funcs.py:24-379
```
