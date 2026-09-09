---
name: t8n-run
description: "在 Toolathlon 仓库中审阅参数、选择或生成任务清单，通过 scripts/run_parallel.sh 后台启动实验或原地补跑，并在确认就绪后 handoff。用于启动 Toolathlon / t8n 实验、按需求跑任务子集、继续原结果目录中的未完成任务。"
---

# t8n-run

使用原生 `scripts/run_parallel.sh` 启动一次实验。默认 handoff：只检查启动是否就绪，完成交接后结束本轮，不持续监控实验，也不停止后台任务。

## 定位仓库与运行意图

- 使用用户指定的 Toolathlon checkout；未指定时检查当前工作目录。确认存在 `scripts/run_parallel.sh`、`run_parallel.py` 和 `tasks/`，所有相对路径从仓库根目录解析。
- 区分“新实验”和“原地补跑”。新实验默认 dump 为 `results/<模型名称>`，展示最终绝对路径；不要修改实际 API 模型名。目录已有任务结果时，先明确是否沿用，不清空或悄悄换目录。
- 原地补跑必须确定一个准确的旧 dump 目录，并读取 [原地补跑规则](references/in-place-rerun.md)。这不是 Agent checkpoint 恢复。
- 一次调用对筛选出的待执行任务各执行一次；不自动增加 attempts、循环重试失败任务或切换到其他启动 wrapper。
- 启动前读取当前 checkout 的 `scripts/run_parallel.sh` 参数段和实际调用，核对下游相关环境变量。下表是设计时已核对的值；脚本变化时，以当前有效行为更新审阅单。

## 任务清单

`TASK_LIST` 可以来自用户指定文件，也可以按用户需求创建临时文件。

1. 根据任务目录、题面和任务配置匹配用户需求；只澄清会改变任务集合的歧义。
2. 有效行是 `tasks/<TASKS_FOLDER>/` 下的任务 basename；忽略空行和整行 `#` 注释。核验文件可读、非空、无重复、每项均是实际任务目录。现有入口会忽略未知任务名，因此在启动前列出并解决错误。
3. 展示清单来源、完整路径、任务数和具体任务名称。不默认将空 `TASK_LIST` 当作全量运行；用户要求全量时，为当前任务目录生成显式清单。
4. 给每次启动建立独立记录目录，例如 `<dump>/.t8n-run/<UTC时间>-<唯一后缀>/`。将确认后的清单保存为其中的 `task-list.txt`，实际启动使用这份文件；临时清单随实验保留，handoff 时不删除。
5. 用清单内的实际任务判断部署与串行约束。对自定义清单同时检查当前标准分组和任务的 `needed_mcp_servers`；不只匹配清单文件名。混合清单合并所含任务的要求。

## 启动审阅单

先准备完整参数、任务清单、必要的只读检查和最终命令，再集中审阅。优先沿用本轮和此前已明确的选择，只问缺失的必要信息。用户已确认这些值并授权启动时，展示最终解析结果后继续，不重复索要确认。

以下五项始终重点展示：

| 必审项 | 规则 |
| --- | --- |
| `TASK_LIST` | 来源、实际使用的清单路径、任务数、任务名称 |
| 模型名称 | 用户指定，显式传入；不沿用脚本的默认模型 |
| dump path | 新实验默认 `results/<模型名称>`；原地补跑使用准确的旧目录；展示绝对路径和已有结果情况 |
| `TOOLATHLON_MODEL_PARAMS_FILE` | 展示实际来源、文件路径及参数内容，或明确使用默认请求参数 |
| workers | 通常 `10`；包含任一 Notion 任务时必须为 `1`，不能默默接受更大的值 |

同时列出其余有效参数供审阅：

| 参数 | 约定 / 当前默认与传入方式 |
| --- | --- |
| provider | `unified`，第三个位置参数 |
| `TASKS_FOLDER` | `finalpool`，可通过环境变量覆盖 |
| `TAG` | 脚本内 `full` |
| `MAX_STEPS` | 脚本内 `100` |
| `TIMEOUT` | 脚本内 `5400` 秒，含单任务预处理、Agent、后处理 |
| `MAX_TOKENS` | 脚本内 `65536`，只用于生成默认 eval config |
| Docker image | 第五个位置参数，默认 `lockon0927/toolathlon-task-image:1016beta` |
| eval config | 第六个位置参数；默认由脚本生成临时 JSON |
| runner | 第七个位置参数，默认 `containerized` |
| runmode | 第八个位置参数，默认 `normal`，仅用于 `decoupled` |
| agent framework | 第九个位置参数，默认空，仅用于 `decoupled` |
| `TOOLATHLON_CONTAINERIZED_MODE` | 下游默认 `phased`；显示已继承的覆盖值 |
| 模型连接 | 有效 `TOOLATHLON_OPENAI_BASE_URL`、API key 是否配置及来源；不展示 key 明文 |
| 运行安排 | 新实验 / 原地补跑、handoff、部署状态与本次是否执行部署 |

自动生成 eval config 时，还展示 `max_turns=50`、`tool_choice=auto`、`parallel_tool_calls=true`、`max_inner_turns=2000`；用户指定配置时显示其实际值。

- 脚本自身的默认 dump 是 `./parallel_debug_gpt5`。skill 必须显式传入已确认的结果目录。
- `MAX_STEPS`、`TIMEOUT`、`MAX_TOKENS`、`TAG` 目前是脚本内直接赋值，外层 export 同名变量不能覆盖。用户要求更改时先确定当前入口能实际表达的方式，不能给出无效命令或为了启动擅改脚本。
- 用户指定的 eval config 必须存在且是合法配置；脚本会在指定文件不存在时生成默认内容，skill 不依赖这个静默回退。已有配置中的模型、provider、max steps 会被命令行改写，`agent.generation.max_tokens` 不会被脚本的 `65536` 改写。
- 外层 dump 是宿主机路径。默认 containerized 配置保持 `global_task_config.dump_path=/workspace/dumps`、`direct_to_dumps=true`，不要替换成宿主机结果路径。

核心命令形状如下。使用真实、已确认的值，保留需要的可选参数位置；运行目录是仓库根目录：

```bash
TASK_LIST="$task_list_snapshot" \
TOOLATHLON_MODEL_PARAMS_FILE="$model_params_snapshot" \
bash scripts/run_parallel.sh "$model_name" "$dump_path" unified "$workers"
```

两个 snapshot 变量须先解析为真实文件；默认请求参数的处理见下节。当前入口内部存在未加引号的参数展开及 shell 字符串拼接，外层加引号不能修复全部问题；参数中的路径、模型名等须能被此入口安全表达，遇到空白或 shell 元字符时报告具体限制，不冒险拼接执行。

## 模型参数与环境

- `TOOLATHLON_MODEL_PARAMS_FILE` 是模型请求参数 JSON，和第六个位置参数的 eval config 不同。
- `scripts/run_single_containerized.sh` 会在模型 URL、key、参数文件环境变量为空时从仓库 `.env` 补值。确认实际来源，将已确认的连接配置放入后台进程环境，避免任务启动时重新拾取不同配置；不得将 key 写入审阅单、启动命令文件或交接记录。读取 `.env` 时避免回显敏感内容。
- 指定参数文件时先验证可读、JSON 顶层为对象，再将文件内容原样复制为本次记录目录的 `model-params.json`，显式传入该快照的绝对路径；不能只记录原文件路径或创建符号链接。下游把它复制到容器 `/workspace/model_params.json`。
- 非空参数对象使用“必要请求字段 + 用户参数”分支，不自动补全 eval config 中的采样默认值。展示 token 上限、thinking / reasoning、temperature 等实际提供的值；缺失值标为未显式发送，不能声称仍使用 `65536`。若 JSON 覆盖 `model` 等核心字段，应把有效覆盖列入审阅。
- 文件不存在或解析失败可能回退默认请求参数，因此不能带着这类问题启动。
- 用户明确选择默认请求参数时，创建内容为 `{}` 的本次 `model-params.json` 并显式传入，标注为默认模式。这会进入默认请求参数分支，同时避免 `.env` 回填旧参数文件；不修改用户的 `.env`。
- 检查实际运行时 Docker / Podman 是否可访问、`uv` 是否可用、目标镜像可用性及必需的本地配置文件。启动任务容器或 MCP 预检不属于纯只读检查，服务连通也不证明远端任务权限全部可用。

## 启动配置快照

每次启动（含原地补跑）在 `<dump>/.t8n-run/<UTC时间>-<唯一后缀>/` 保存以下文件；每次使用新目录，不覆盖之前的记录。这是执行 skill 时必须完成的步骤，直接运行 `scripts/run_parallel.sh` 不会自动生成这些记录。

| 文件 | 保存内容 |
| --- | --- |
| `launch.json` | 启动时间、仓库绝对路径 / commit / dirty 状态、运行安排与部署结论；审阅单中的有效参数：模型、provider、dump、workers、`TASKS_FOLDER`、`TAG`、`MAX_STEPS`、`TIMEOUT`、`MAX_TOKENS`、镜像、runner、runmode、agent framework、`TOOLATHLON_CONTAINERIZED_MODE`；任务清单来源 / 快照路径 / 数量、模型参数来源 / 原路径 / 快照路径 / 默认或自定义模式、eval config 来源 / 原路径 / 快照路径及命令行覆盖；模型 base URL、API key 是否配置及来源，不保存 key 值。区分脚本 `MAX_TOKENS` 与实际请求中的 token 参数。 |
| `task-list.txt` | 本次确认的任务清单，实际启动使用这份文件。 |
| `model-params.json` | 实际模型请求参数文件的完整副本；默认模式为 `{}`。实际启动使用这份文件。 |
| `eval-config.json` | 用户指定 eval config 时，在启动前复制并通过第六个位置参数传入；由脚本自动生成时，从启动日志定位真实文件，生成后立即复制，handoff 前确认已保存。另在 `launch.json` 记录模型、provider、max steps 等有效覆盖，不把原始配置快照误称为最终生效配置。 |
| `launch-command.txt` | 最终命令及非敏感环境覆盖，使用快照绝对路径，不含 API key。 |
| `launch.log` | 本次后台启动的完整 stdout / stderr。 |

先写入并核对启动前可确定的参数与快照，再创建后台进程；随后将 PID / 会话名、自动生成的 eval config 路径和就绪证据补入本次 `launch.json`。不把整个 `.env` 或认证配置目录复制进启动记录。

## 部署与并发

- **C-local / 自定义本地依赖清单**：启动前确认所需服务已部署且可用。完整 C-local 通常执行 `bash global_preparation/deploy_containers.sh`；已有成功部署证据仍要核对当前服务状态。自定义子集可按实际依赖核对对应服务。
- **C-notion / 含 Notion 的清单**：整个作业 `workers=1`，并检查没有其他 Notion 作业同时运行，包括其他模型或 checkout。单个进程 workers 为 1 不能约束其他进程。
- 当前 `c-notion.txt` 中 `notion-find-job`、`notion-hr` 需要 Poste。完整部署已经包含 Poste，已有可用服务可复用。需要单独准备时使用 `bash global_preparation/deploy_notion_containers.sh`；检查已有服务使用其 `--check`。其余 Notion 任务不因组名自动要求完整基础设施部署。
- Poste 检查不验证 Notion 授权或邮箱登录。另行核对所选任务需要的 Notion integration、OAuth 状态以及其他服务配置；细节读取当前 `docs/notion-evaluation.md`。
- 审阅单明确“已部署并复用 / 本次执行部署 / 尚未就绪”。未获授权时不能根据清单名称自动部署；用户已授权本次具体部署则继续，无需再次确认。
- 完整部署会清理共享容器、网络、卷、镜像和端口；Notion 最小部署也会重建 Poste 并清空邮件数据。先核对没有正在使用这些资源的实验，不在它们运行时重建；不能用反复部署作为自动修复手段。部署脚本的 `true/false` 控制邮件服务配置，不是跳过 K8s 的开关。
- C-local 与 C-notion 可能共用 Poste，分组不隔离邮箱。多个 C-local 作业共享服务时也要协调；`task_conflict.json` 的锁仅在一个 `run_parallel.py` 进程内有效。
- 一个 dump 目录同时只能有一个写入作业。直接入口没有目录互斥锁，启动和原地补跑前核对真实进程与容器，不能把留下的 PID 文件当作进程仍存活的证明。没有冲突时才启动；不自动停止未知归属的作业。

## 后台启动与 handoff

1. 按“启动配置快照”保存本次 `launch.json`、任务清单、模型参数、eval config 和最终命令；自动生成的 eval config 在生成后补存。原地补跑还保存本次将跳过和将执行的任务列表，并按参考文档备份会被覆盖的根层日志 / 统计文件。
2. 若原地补跑的待执行任务为零，报告“没有需要补跑的任务”，不启动后台进程，也不宣称已 handoff。
3. 用持久会话或独立后台进程运行原生命令。例如使用 Python `subprocess.Popen` 的参数数组，设置 `cwd=repo_root`、`env=已确认环境`、`stdin=DEVNULL`、`stdout=打开的启动日志`、`stderr=STDOUT`、`start_new_session=True`。后台命令仍然是 `bash scripts/run_parallel.sh ...`。不要只依赖当前工具调用的临时 session 存活。
4. 完整启动日志写入本次记录目录的 `launch.log`，不要与脚本自己用 `tee` 写的 `<dump>/stdout.log` 共用文件。记录 PID、启动时间与可核对的命令；使用持久会话时记录会话名。禁止把 key 拼进命令行。生成的临时 eval config 路径可从启动日志定位，保存其快照和有效覆盖信息。
5. 在有限窗口内检查启动，通常最多 10 分钟；按所选任务的已知预处理耗时可调整并说明。检查间隔不超过 60 秒，期间给出简短进展。核对真实调度进程、预期的筛选数量、已开始执行的任务及其容器 / 日志。
6. 就绪证据至少包括：后台调度进程仍存活；实际待执行任务数符合预览；至少一个待执行任务已完成预处理、进入 Agent，且日志出现真实模型响应或工具调用。只有 PID、容器创建消息或 `STARTING` 不足以证明模型已经跑起来。检查已启动任务是否出现共同的配置 / 认证 / 容器启动错误；如有则报告，不能只挑一个成功片段宣布整批正常。
7. 就绪后更新启动记录并交接：模型、清单与任务数、实际执行 / 跳过数量、workers、dump 目录、PID / 会话名、`launch.json` / `model-params.json` / 日志路径和实际就绪证据。结束本轮，不再定期轮询，不等待整个实验完成，不追加重跑，不发送 INT / TERM 或停止容器。
8. 若短任务已全部结束，按真实结果报告“已结束”，不伪造仍运行的 PID。若检查窗口到期仍未就绪，报告“已启动但尚未验证就绪”、当前阶段、日志及存活情况；保留后台现场，不自动重启或延长为持续监控。若已经退出，报告启动失败和可定位的错误。用户后来明确要求检查时，再做一次实时观察。

脚本的 `tee` 管道未默认启用 `pipefail`，调度器部分失败路径也可能打印 `SUCCESS`；就绪或任务完成的结论不能只看 shell 退出码或这行日志。以当前进程、任务状态和实际产物为证据。
