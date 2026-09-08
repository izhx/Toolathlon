# Toolathlon 仓库与评测运行流程概览

> 调查范围：`/data8/zhangxin/teleai/Toolathlon`
>
> 调查时间：2026-09-04
>
> 本文基于对当前 frp-s8 工作树的静态只读检查。调查过程中没有运行仓库脚本、Python、测试、容器或评测。

## 1. 当前版本边界

调查时远端仓库状态为：

- 分支：`dev/try-run`
- HEAD：`5f5ec52a1d3c7cd5d56edaa92fdfd0cd03c666c3`
- 提交说明：`group tasks v1`
- 提交时间：2026-09-03

工作树中存在已暂存但尚未提交的修改，其中包括 `scripts/run_parallel.sh`、`scripts/run_parallel_task_list.sh`、`configs/ports_config.yaml` 和若干 `docs/` 文件。因此，本文描述的是当前 frp-s8 工作树的实际行为，不应直接视为上游稳定版本的原始行为。

## 2. 仓库在做什么

Toolathlon（The Tool Decathlon）是一个评估语言 Agent 在真实软件环境中进行通用工具使用的 benchmark。它关注的不是模型能否生成一段看似合理的答案，而是 Agent 能否通过较长的工具调用链，真正完成跨应用、跨数据源的操作任务。

仓库 README 将其定位为拥有 600+ 真实软件环境工具、面向长程任务执行的 Toolathlon-Verified 版本，见 `README.md:17-18`。

当前 `tasks/finalpool` 中实际有 108 个任务：

- 108 个任务都有独立的 `evaluation/main.py`；
- 72 个任务有 `preprocess/main.py`；
- 81 个任务有 `initial_workspace/`；
- 72 个任务有 `groundtruth_workspace/`。

任务涉及的环境包括：

- 网页、论文、搜索与金融数据；
- PDF、Excel、Word、PPT 等本地文件；
- Git、GitHub、Hugging Face、W&B；
- 邮件、Google Sheet、Google Calendar、Google Forms、Notion；
- Canvas、WooCommerce；
- Kubernetes、Docker/Podman 和本地部署服务。

当前仓库的任务风险分类将 15 个任务归为无网络依赖、30 个归为网络只读、63 个归为外部状态写入，见 `docs/finalpool-task-risk-classification.md:159-176`。因此，这不是一个完全无副作用的离线问答数据集：大量任务会使用真实凭据并修改本地或远端服务状态。

## 3. 一道任务的组成

每道任务不是一条孤立 prompt，而是一个可执行场景包。典型目录包括：

```text
tasks/finalpool/<task>/
├── docs/
│   ├── task.md
│   └── agent_system_prompt.md
├── task_config.json
├── initial_workspace/
├── preprocess/
│   └── main.py
├── evaluation/
│   └── main.py
├── groundtruth_workspace/
└── token_key_session.py
```

各部分含义如下：

- `docs/task.md`：给被测 Agent 的用户任务。
- `docs/agent_system_prompt.md`：任务级系统提示，包括工作区、完成方式等要求。
- `task_config.json`：声明该题允许连接的 MCP 服务和本地工具。
- `initial_workspace/`：Agent 开始工作前得到的初始文件。
- `preprocess/main.py`：布置本题的初始状态，例如创建测试数据、初始化服务或准备集群。
- `evaluation/main.py`：该题的专用判分器。
- `groundtruth_workspace/`：判分所需的标准答案或基准数据。
- `token_key_session.py`：可选的任务级凭据、token 或 session 覆盖。

`TaskConfig.build()` 会从这些文件构造完整任务配置，见 `utils/data_structures/task_config.py:287-313`。

任务通过 `needed_mcp_servers` 和 `needed_local_tools` 控制 Agent 可见的工具。例如，一道论文与 Excel 任务可以只开放浏览器、论文检索、PDF、Excel 和文件系统；一道 Kubernetes 任务则可以开放 K8s、Google Sheet 和文件系统。

## 4. 评测真正检查什么

最终判分不只依赖 Agent 的文本回答。每道题的 evaluator 可以检查：

- Agent 最终回复和完整工具轨迹；
- Agent 工作区中的文件及其内容；
- 邮件是否实际发送；
- WooCommerce、Canvas、Notion、GitHub 等服务是否被正确修改；
- Kubernetes 集群中的资源状态；
- Google Sheet、Calendar、Forms 等远端状态；
- 执行是否在步数、时间和状态约束内正常结束。

几个代表性例子：

- `academic-pdf-report`：Agent 检索论文第一作者、单位和 Google Scholar 页面并填写 Excel；判分器实际读取 Excel，对照 ground truth 检查每行内容。
- `woocommerce-new-product`：Agent 识别新品和折扣商品并发送邮件；判分器会查询 WooCommerce API，并通过 IMAP 检查真实已发送邮件。
- `k8s-safety-audit`：Agent 检查集群并填写 Google Sheet；判分器会读取真实 Kubernetes 状态和目标工作表。

通用 `TaskEvaluator` 只有在 Agent 执行状态为 `success` 时才运行题目自己的 evaluator。题目 evaluator 退出码为 0 时得到 `pass: true`，非 0 时得到 `pass: false`；Agent 本身未正常结束时通常得到 `pass: null`。相关逻辑见 `utils/evaluation/evaluator.py:30-73`。

## 5. `scripts/run_parallel.sh` 的入口参数

当前入口的位置参数依次为：

| 位置 | 参数 | 默认值 | 说明 |
|---:|---|---|---|
| 1 | `model_name` | `gpt-5-mini` | 被测模型名称 |
| 2 | `dump_path` | `./parallel_debug_gpt5` | 结果根目录 |
| 3 | `provider` | `unified` | 模型 Provider |
| 4 | `workers` | `10` | 最大并发任务数 |
| 5 | `image_name` | `lockon0927/toolathlon-task-image:1016beta` | 单任务容器镜像 |
| 6 | `config_file` | 空 | 空时自动生成临时配置 |
| 7 | `runner` | `containerized` | `containerized` 或 `decoupled` |
| 8 | `runmode` | `normal` | 主要供 decoupled runner 使用 |
| 9 | `agent_framework` | 空 | 可选 Agent 框架，主要供 decoupled 使用 |

此外，脚本硬编码了：

- `TASKS_FOLDER=finalpool`，但当前版本允许用同名环境变量覆盖；
- `TAG=full`；
- 单题 Agent 最大步数 `MAX_STEPS=100`；
- 单题总超时 `TIMEOUT=5400` 秒；
- 单次模型输出上限 `MAX_TOKENS=65536`。

这些参数见 `scripts/run_parallel.sh:13-32`。

`TASK_LIST` 环境变量可以指定一个文本文件，每个非空、非注释行表示一个任务名；留空时运行任务目录下的全部任务。

## 6. 顶层并行运行流程

总体调用链为：

```text
scripts/run_parallel.sh
  ├── 创建输出目录
  ├── 生成或读取评测配置
  ├── uv run run_parallel.py
  │    ├── 发现、过滤并打乱任务
  │    ├── Semaphore 控制最大并发
  │    ├── task_conflict.json 控制部分冲突任务串行
  │    └── 每道任务调用一个 single-task runner
  │          ├── run_single_containerized.sh
  │          └── run_single_decoupled.sh
  └── 聚合日志、轨迹、判分结果和统计
```

### 6.1 配置生成

`run_parallel.sh` 首先创建 dump 目录和 `scripts/temp_configs/`。如果第 6 个参数没有指向一个已有文件，就使用时间戳、PID 和随机数生成临时配置文件；已有配置则原样使用。自动生成的临时配置不会在结束后删除，见 `scripts/run_parallel.sh:34-92`。

自动配置中的主要内容包括：

- `max_turns=50`；
- `max_steps_under_single_turn_mode=100`；
- 容器内输出目录 `/workspace/dumps`；
- `direct_to_dumps=true`；
- MCP server 配置目录；
- 被测 Agent 的 model/provider；
- `parallel_tool_calls=true`；
- 最大输出 65536 tokens。

配置中虽然还有 user simulator 模型，但默认并行评测是 single-turn：Agent 直接收到一次 `task.md`，不会正常进入多轮用户模拟。

### 6.2 任务发现与断点过滤

`run_parallel.py` 只枚举 `tasks/<tasks_folder>` 下的一级子目录，并根据可选 task list 按任务 basename 过滤，见 `run_parallel.py:592-623`。

随后检查已有结果：

- 优先读取 `status.json`；
- preprocess、running 和 evaluation 已形成完成状态时跳过；
- `timeout` 或 `max_turn_exceeded` 且 preprocess 已完成时，也会被视为已完成而跳过；
- 没有有效 `status.json` 时，回退检查 `eval_res.json` 和 `traj_log.json`。

具体规则见 `run_parallel.py:430-510`。

需要重跑的任务会先将旧 leaf 目录中的结果移动到 `legacy_results/runN`；若旧目录中只有不完整的 `container.log`，则直接删除该日志，见 `run_parallel.py:246-295`。

### 6.3 并发与冲突锁

待执行任务会被随机打乱。`AsyncTaskScheduler` 使用 `asyncio.Semaphore(workers)` 限制总并发，并读取 `tasks/<folder>/task_conflict.json` 创建冲突锁，见 `run_parallel.py:120-244,678-744`。

当前 `finalpool` 只配置了四个二元冲突组：

```text
set-conf-cr-ddl              <-> student-interview
huggingface-upload           <-> dataset-license-issue
woocommerce-customer-survey  <-> woocommerce-product-recall
canvas-submit-late-work      <-> canvas-do-quiz
```

同一冲突组内的任务串行执行，并且等待冲突锁时不占 worker。但这些锁只是当前 `run_parallel.py` 进程内的 `asyncio.Lock`，不能协调另一个并行评测进程、另一个 checkout 或另一台机器。

### 6.4 单任务进程

每道任务会启动一个独立子进程组，stdout 和 stderr 写入：

```text
<dump_path>/<tasks_folder>/<task>/run.log
```

默认调用：

```text
scripts/run_single_containerized.sh
```

当 `runner=decoupled` 时调用：

```text
scripts/run_single_decoupled.sh
```

单题超过 5400 秒时，父调度器先向整个进程组发送 SIGTERM，等待 3 秒后仍未退出则发送 SIGKILL，并将 `status.json.running` 更新为 `timeout`。相关实现见 `run_parallel.py:19-106,297-340,371-412`。

## 7. 默认 containerized/phased 单题流程

`run_single_containerized.sh` 默认使用 `TOOLATHLON_CONTAINERIZED_MODE=phased`。它把一道任务拆成相互隔离的 preprocess、Agent 和 evaluation 阶段。核心实现见 `scripts/run_single_containerized.sh:580-708`。

### 7.1 创建任务容器

脚本为每道题创建单独容器，并：

- 使用 host network；
- 挂载 Docker 或 Podman socket；
- 把本题的宿主机输出目录挂载为 `/workspace/dumps`；
- 挂载 MCP OAuth 数据；
- 复制 `configs`、`scripts`、`utils`、`main.py` 和本题目录；
- 用 `sleep 7200` 保持容器存活，以便分阶段执行命令。

退出 trap 会在正常、失败或中断时清理私有 bundle/stash，并停止、删除任务容器。

### 7.2 Preprocess：布置考场

容器内执行 `scripts.decoupled.container_preprocess`：

1. 加载 eval config，并覆盖本次模型、provider 和最大步数；
2. 读取 `task_config.json`、题面和系统提示；
3. 创建 Agent workspace；
4. 复制 `initial_workspace`；
5. 执行任务自己的 `preprocess/main.py`；
6. 做 MCP 特定初始化；
7. 加载任务级 token/session；
8. 生成完整、已解析的 schema v2 task bundle。

bundle 包含题面、系统提示、所需工具、停止条件、容器路径、输出路径、固定 launch time、模型配置和可信的 resolved task config，见 `scripts/decoupled/container_preprocess.py:52-169`。

这个 bundle 随后被复制到宿主机未挂载进任务容器的私有 `/tmp` 目录，并检查任务根路径必须是 `/workspace` 下的规范绝对路径。

### 7.3 隐藏 evaluator 和 ground truth

在模型启动之前，`task_artifact_guard` 会把以下内容移出 Agent 可访问的容器：

- `preprocess/`；
- `evaluation/`；
- `groundtruth_workspace/`；
- `golden/`；
- 已知含答案的 JSON、脚本、测试、说明文件。

它先完整复制并计算哈希，再删除容器内副本。任何 stash 或恢复失败都会 fail closed，不允许在不可信状态下继续评测，见 `scripts/containerized/task_artifact_guard.py:42-97,272-349`。

### 7.4 Agent 执行阶段

可信 bundle 临时放进容器的 `/run`。`container_agent` 读取后立即 unlink，因为其中含有 evaluator 路径和任务级 token material，见 `scripts/containerized/container_agent.py:32-56`。

随后：

1. 只连接本题声明的 MCP servers；
2. 加载本题声明的本地工具；
3. 根据 model/provider 构造被测 Agent；
4. 将 `task.md` 作为 single-turn 用户请求；
5. 允许 Agent 在一次任务中进行最多 100 个模型/tool steps；
6. 保存完整 conversation history、工具调用、状态、token 和费用信息。

本地工具包括 `claim_done`、上下文管理、历史检索、超长输出处理、可选 Python 执行和 web search，见 `utils/roles/task_agent.py:45-72`。Agent 和 MCP 连接逻辑见 `utils/roles/task_agent.py:465-551`，主循环见 `utils/roles/task_agent.py:596-843`。

Agent 结果保存到 `traj_log.json`，内容包括：

- task config；
- 所有可用工具 schema；
- 完整消息和工具轨迹；
- 执行状态；
- turn/tool-call/token 统计；
- Agent 和 user simulator 成本；
- conversation history 路径。

见 `utils/roles/task_agent.py:924-968`。

### 7.5 恢复并执行可信判分

Agent 无论成功还是失败，脚本都会继续恢复可信 evaluator 和 ground truth，以便形成正式结果。恢复时会先删除 Agent 创建的同名目录、文件或 symlink，再恢复并复验哈希。

随后：

1. 删除 Agent 可能伪造的 `eval_res.json`；
2. 将未被 Agent 接触过的可信 bundle 重新放进容器；
3. 用可信 resolved config 替换 `traj_log.json` 中 Agent 可修改的 config；
4. 用宿主机观察到的 Agent 退出码修正轨迹中的运行状态；
5. 调用任务自己的 `evaluation/main.py`；
6. 写出 `eval_res.json` 和 evaluation status。

判分完成后才清理任务容器。

## 8. Decoupled 模式

当 `runner=decoupled` 时，职责拆分为：

```text
容器：preprocess
容器：启动单端口 MCP gateway，通过 SSE 暴露任务工具
宿主机：运行可替换的 Agent loop
容器：恢复可信 evaluator 并判分
```

当前支持：

- `toolathlon_default`：Toolathlon 基于 OpenAI Agents SDK 的原有框架；
- `claude_agent_sdk`：宿主机使用 Claude Agent SDK。

Host Agent 只能通过 MCP gateway 调用容器内任务工具；任务环境和 evaluator 仍由容器控制。架构说明见 `DECOUPLED_AGENT_LOOP.md:1-16,64-94`。

## 9. 输出目录与统计

一次批量运行的典型输出为：

```text
<dump_path>/
├── stdout.log
├── eval_stats.json
├── execution_report_<folder>_<model>_<tag>.json
├── eval_res_all.jsonl
├── traj_log_all.jsonl
├── container_all.log
├── run_all.log
└── <tasks_folder>/
    └── <task>/
        ├── status.json
        ├── run.log
        ├── container.log
        ├── traj_log.json
        ├── eval_res.json
        ├── conversation_history/
        ├── workspace/
        └── legacy_results/
```

关键文件含义：

- `status.json`：记录 preprocess、running、evaluation 三阶段状态；
- `run.log`：单题 runner 的完整 stdout/stderr；
- `traj_log.json`：模型与工具完整轨迹、状态、统计和成本；
- `eval_res.json`：该题最终的 `pass: true/false/null`；
- `eval_stats.json`：批量成功率、平均 turns、平均 tool calls 和各阶段状态分布；
- `execution_report_*.json`：`run_parallel.py` 对本次实际执行任务的 pass/fail/missing/invalid 分类。

顶层聚合逻辑见 `scripts/run_parallel.sh:135-161`，统计逻辑见 `scripts/generate_parallel_stats.py:32-256`。

## 10. 当前实现中需要特别注意的边界

### 10.1 顶层退出码不能代表全部任务通过

这是当前实现最容易误读的地方：

1. `run_command_async()` 在单任务脚本非零退出时只返回 `success: false`，不会抛异常，见 `run_parallel.py:73-77`。
2. `_execute_task()` 没有检查该字段，仍会将任务计为 scheduler 的 `completed/success`，然后另外读取 `eval_res.json`，见 `run_parallel.py:340-369`。
3. `run_parallel.py` 最终只打印结果、写报告，不根据失败题数退出非零。
4. `scripts/run_parallel.sh:131-133` 的 `uv run ... | tee ...` 没有启用 `pipefail`，因此 `$?` 通常取到 `tee` 的状态。

所以：

- 日志中的 `SUCCESS` 更接近“该任务进程完成了”，不等于 evaluator 通过；
- 顶层 shell exit code 为 0 也不能证明全部任务通过；
- 正式结果必须以逐题 `eval_res.json` 和顶层 `eval_stats.json` 为准。

### 10.2 单任务容器不等于所有状态完全隔离

每道题虽然有独立容器，但仍可能共享：

- host network；
- 同一个 Docker/Podman daemon；
- Canvas、Poste、WooCommerce 等本地部署服务；
- Notion、Google、GitHub、Hugging Face 等远端账号和资源。

README 明确建议在正式并行评测前重新部署所需应用，见 `README.md:247-256`。`run_parallel.sh` 本身不会部署或重置这些服务。

当前 `task_conflict.json` 的四个显式冲突组只能缓解已经登记、且处于同一个 `run_parallel.py` 进程中的冲突。执行清单另分为 A、B、C-local、C-remote、C-notion 五组；其中 C-notion 的两个邮件任务仍与 C-local 共享 Poste。多模型、多进程或多个 checkout 同时运行时，进程内锁不能协调这些跨进程访问。详见 [分组评测](finalpool-grouped-evaluation.md)。

### 10.3 重跑与聚合可能混入历史结果

重跑任务时，旧结果会被移动到 `legacy_results/runN`。但 `run_parallel.sh` 使用递归 `find` 生成：

- `container_all.log`；
- `run_all.log`；
- `eval_res_all.jsonl`；
- `traj_log_all.jsonl`。

因此这些 `*_all` 文件可能同时包含当前结果和 `legacy_results` 中的历史 attempt。相比之下，`generate_parallel_stats.py` 只 glob 当前 `<dump>/<tasks_folder>/*/status.json` 和 `eval_res.json`，不会读取 legacy 目录。

### 10.4 Decoupled 的状态细分统计存在类型问题

Phased containerized 模式将 `status.json.evaluation` 写成布尔值。Decoupled 路径默认可能写成字符串 `"pass"` 或 `"fail"`，但 `generate_parallel_stats.py` 使用 Python truthiness 判断；字符串 `"fail"` 也是真值，可能在 `status_breakdown.evaluation` 中被错计为 pass。

`average_success_rate` 仍来自 `eval_res.json` 中的布尔 `pass`，不受这个具体问题影响。

### 10.5 当前容器运行时配置

当前 checkout 中未看到 `configs/global_configs.py`。`run_single_containerized.sh` 的静态逻辑是在导入该文件失败时回退到 `podman`。本文没有实际运行脚本，因此没有验证当前主机上的 Docker/Podman 可用性。

## 11. 一句话总结

Toolathlon 是一个把“任务布置、受限工具调用、Agent 长程执行、真实环境状态和任务专属判分器”组合在一起的 Agent benchmark。`run_parallel.sh` 负责批量编排；`run_parallel.py` 负责过滤、并发和冲突锁；single-task runner 负责隔离环境；TaskAgent 负责模型与工具循环；每题 evaluator 最终根据工作区和真实服务状态给出通过或失败。
