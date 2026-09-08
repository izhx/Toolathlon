# finalpool 分组评测设计

## 目标

依据 `docs/finalpool-task-risk-classification.md`，将 `tasks/finalpool` 的 108 个任务拆成 5 个互斥且完备的 task list。运行时仍只保留一份 canonical `tasks/finalpool`，不复制任务目录，也不为任务创建软链接。

分组通过一个薄封装脚本调用现有 `scripts/run_parallel.sh`。分组运行时通过 `--task-list` 显式指定清单和独立 dump 目录，因此五组可以由五个进程同时运行；省略 `--task-list` 时运行 `tasks/finalpool` 全量任务。

C-notion 组内必须串行：显式设置 `workers=1`，每个任务完整结束后再开始下一个，也不能同时启动多个 Notion 作业。其他组可以按各自资源条件设置 workers；不能直接把其他组的并发参数用于 Notion。具体命令见 [Notion 评测](notion-evaluation.md)。

## 分组

| 分组 | 数量 | 判据 | 是否依赖 `deploy_containers.sh` |
|---|---:|---|---|
| A 无网络依赖 | 15 | 分类文档 A | 否 |
| B 网络只读 | 30 | 分类文档 B | 否 |
| C-local 本地基础设施写 | 33 | 分类文档 C，排除 Notion 任务后，`needed_mcp_servers` 至少包含 `canvas`、`emails`、`woocommerce`、`k8s` 之一 | 是 |
| C-remote 远端写 | 22 | 分类文档 C，既不使用 Notion，也不依赖上述四类本地基础设施 | 否 |
| C-notion Notion 写 | 8 | 分类文档 C，`needed_mcp_servers` 包含 `notion`；优先于本地/远端划分 | 不需要完整部署；两个邮件任务需要 Poste，可用 `deploy_notion_containers.sh` |

对应文件：

- `configs/task_lists/finalpool/a-no-network.txt`
- `configs/task_lists/finalpool/b-network-read-only.txt`
- `configs/task_lists/finalpool/c-local-infrastructure-write.txt`
- `configs/task_lists/finalpool/c-remote-write.txt`
- `configs/task_lists/finalpool/c-notion.txt`

五个文件必须满足以下不变量：

1. 每个有效行只包含一个 `tasks/finalpool` 下的任务 basename。
2. 五组之间没有重复任务。
3. 五组并集恰好覆盖 108 个任务。
4. `tasks/finalpool/task_conflict.json` 中每个 conflict group 的成员必须位于同一 task list。

当前四个显式冲突组不会跨分组：三个落在 C 本地基础设施写组，一个落在 C 远端写组。这里的冲突锁是单个 `run_parallel.py` 进程内的 `asyncio.Lock`；如果以后调整清单，不能把同一 conflict group 拆到两个并发进程。

## 薄封装脚本

入口为：

```bash
bash scripts/run_parallel_task_list.sh \
  [--attempts N] \
  [--deploy-before-attempt] \
  [--tasks-folder <name>] \
  [--task-list <task-list-file>] \
  <dump-path> \
  [model-name] \
  [provider] \
  [workers] \
  [image-name] \
  [config-file] \
  [runner] \
  [runmode] \
  [agent-framework]
```

脚本只负责：

1. 校验 dump 路径已给出、`--tasks-folder` 位于仓库 `tasks/` 下且存在，并在指定 `--task-list` 时校验清单文件。
2. 通过 `TASKS_FOLDER` 环境变量把任务目录传给 `scripts/run_parallel.sh`；默认值为 `finalpool`。
3. 指定清单时通过 `TASK_LIST` 环境变量传给 `scripts/run_parallel.sh`；省略时清除继承的 `TASK_LIST` 并运行所选任务目录中的全量任务。
4. 将 dump 路径和其余运行参数传给现有入口。
5. 在 dump 根按 task-list basename 持有非阻塞文件锁；同一分组不能重复并发启动。

默认情况下它不负责部署基础设施、不在后台创建五个进程，也不合并结果。显式传入 `--deploy-before-attempt` 时，它会在每个 attempt 前运行一次 `global_preparation/deploy_containers.sh`；部署失败会终止当前进程和剩余 attempts。该行为不会根据 task-list 文件名自动开启。

相对 task-list 路径和 dump 路径均从仓库根目录解析，因此可以从其他工作目录调用该脚本。task-list 不再接受位置参数；旧写法会直接报错并提示改用 `--task-list`，避免把清单文件误当成 dump 目录。

`--tasks-folder` 使用相对于仓库 `tasks/` 的目录名；省略时等价于 `--tasks-folder finalpool`。默认不传 `--attempts` 时，`dump-path` 是单次运行的精确输出目录，不添加模型、run 或 task-list 层：

```text
<dump-path>/
├── stdout.log
├── eval_stats.json
└── <tasks-folder>/
    └── <task>/
        ├── status.json
        ├── traj_log.json
        └── eval_res.json
```

传入 `--attempts N` 时，`dump-path` 改为实验根目录，脚本顺序执行 N 次，并将每次结果写入：

```text
全量：<dump-path>/<model-name>__run<attempt>/
分组：<dump-path>/<model-name>__run<attempt>/<task-list-basename>/
```

模型与 attempt 层使用 `<model-name>__run<attempt>`：attempt 从 1 开始且不补零，模型名中的 `/` 替换为 `_`。指定 task-list 时，task-group 位于其下一层；全量模式不再增加一层目录。锁在内部按 task-list basename 或全量任务标识隔离，因此不同分组可以共享同一个 experiment root，同一分组不能重复并发启动。

## 运行流程

同一个正式 attempt 建议使用一个共同父目录，每组一个独立子目录：

```text
results/<run-id>/
├── a-no-network/
├── b-network-read-only/
├── c-local-infrastructure-write/
├── c-remote-write/
└── c-notion/
```

如果要运行 C 本地基础设施写组，先在没有评测进程运行时部署一次：

```bash
bash global_preparation/deploy_containers.sh true
```

部署成功后再启动五组。不要在其他组运行期间重新执行部署脚本，因为它会清理并重建共享容器、网络和端口。

只运行 C-notion 时，已有可用 Poste 即可复用；首次准备邮件后端可执行 `bash global_preparation/deploy_notion_containers.sh`。完整部署已包含 Poste，运行全部五组时不用再执行最小部署。C-notion 的两个邮件任务与 C-local 共用 Poste，任一组使用期间都不能重建它；跨组邮箱操作也需要核对资源是否重叠。

示例：

```bash
bash scripts/run_parallel_task_list.sh \
  --task-list configs/task_lists/finalpool/a-no-network.txt \
  results/<run-id>/a-no-network \
  <model-name> unified 10
```

其余组替换 task-list 和 dump 子目录；C-notion 还必须将上例最后的 workers 改为 `1`，逐个执行任务。组间启动由外层终端、作业系统或进程管理器完成；五个命令不能复用同一个 dump 子目录，也不能重复启动 Notion 作业。

同一分组连续运行 3 次时，可以使用：

```bash
bash scripts/run_parallel_task_list.sh \
  --attempts 3 \
  --task-list configs/task_lists/finalpool/a-no-network.txt \
  results/<experiment-id> \
  <model-name> unified 10
```

输出为 `results/<experiment-id>/<model-name>__run1/a-no-network` 至 `<model-name>__run3/a-no-network`。其他四个分组可以共享同一个 experiment root，各自写入对应的 task-list basename 子目录。

`--attempts` 本身只编排评测，不会重置基础设施。C 本地组如果要求每次 attempt 都使用重新部署的 Canvas、Poste、WooCommerce 和 Kind，可以显式执行：

```bash
bash scripts/run_parallel_task_list.sh \
  --deploy-before-attempt \
  --attempts 3 \
  --task-list configs/task_lists/finalpool/c-local-infrastructure-write.txt \
  results/<experiment-id> \
  <model-name> unified 2
```

A、B、C-remote 和 C-notion 不应传入该参数；C-notion 的邮件后端按前述方式准备。该参数只控制当前分组进程，不会等待或协调另外四个分组。C-local 在下一轮重建 Poste 会直接中断仍在运行的 C-notion 邮件任务，因此共享实例时必须在外层协调两组，确认相关任务结束后再部署。完整脚本还会执行宿主 Docker prune 并清理固定服务和端口；要求最保守生命周期隔离时，等待全部五组结束后再部署。

不指定 task-list、直接运行全量 `finalpool` 的示例：

```bash
bash scripts/run_parallel_task_list.sh \
  --attempts 3 \
  results/<experiment-id> \
  <model-name> unified 1
```

输出位于 `results/<experiment-id>/<model-name>__run1` 至 `<model-name>__run3`，不再增加 `all-tasks` 子目录。全量任务包含 Notion，当前 runner 没有按任务组单独设置 workers 的机制，因此全量命令也使用 `workers=1`；需要其他组并行时，分别运行五份清单，并保持 C-notion 为 1。全量任务也包含 C 本地组；如果每次 attempt 都要求重置本地基础设施，还应显式传入 `--deploy-before-attempt`。

## 端口任务与五组并发关系

按 `configs/ports_config.yaml` 中当前有效的 `files_by_port` 任务路径统计，十个受管端口共直接涉及 33 个唯一任务，其中 C-local 31 个、C-notion 2 个：

| 分组 | 任务数 | 直接登记端口的任务数 | 端口关系 |
|---|---:|---:|---|
| A 无网络依赖 | 15 | 0 | 无直接宿主端口冲突 |
| B 网络只读 | 30 | 0 | 无直接宿主端口冲突 |
| C-local 本地基础设施写 | 33 | 31 | 使用 Canvas、Poste、WooCommerce 和三个任务临时端口 |
| C-remote 远端写 | 22 | 0 | 无直接宿主端口冲突，但仍可能冲突于远端账号或资源 |
| C-notion Notion 写 | 8 | 2 | `notion-find-job`、`notion-hr` 是同一 Poste 的 IMAP/SMTP 客户端 |

C 本地组中只有 `k8s-redis-helm-upgrade` 和 `k8s-safety-audit` 未直接登记固定端口。按端口分别统计时，`1143`、`1587`、`2525` 直接涉及 24、23、1 个任务，`10001`、`20001` 涉及 8、1 个任务，`10003` 涉及 9 个任务，`30123`、`30124`、`30137` 各涉及 1 个任务。同一任务可同时使用多个端口，因此这些数量不能相加；`10005` 只出现在 Poste 部署和用户初始化脚本中，没有直接登记的任务文件。

### 单模型的五组并发

同一模型按当前五份清单运行时，Canvas、Poste 和 WooCommerce 只需预先部署一套监听者。C-local 与 C-notion 会共同连接 Poste，但普通邮件任务是客户端，不会各自再次绑定服务端口；`30123`、`30124`、`30137` 仍分别只属于一个 C-local 任务。

端口不重复绑定仍不能排除共享状态竞争。C-local 内的 Canvas/WooCommerce 操作，以及 C-local 与 C-notion 间的 Poste 操作，都需要遵守各自的任务资源边界。当前 `task_conflict.json` 中的三个 C-local 冲突对和一个 C-remote Hugging Face 冲突对仍各在同一份清单内；这些进程内锁不覆盖未登记的跨组邮件状态竞争。

### 多模型同机并发

如果多个模型各自同时运行五组，它们的 C 本地进程会直接相互冲突。`task_conflict.json` 的锁是进程内 `asyncio.Lock`，不能协调不同模型进程。具体影响取决于部署方式：

- 多个模型共用已部署的一套 Canvas、Poste 和 WooCommerce 时，通常不会再次绑定服务端口，但任务的初始化、agent 操作和 evaluator 会交叉修改同一份状态，结果可能串污且不可复现。
- 每个模型都使用相同 prefix、suffix 和端口执行 `deploy_containers.sh` 时，后一次部署会停止或重建前一次评测使用的基础设施，同时端口也无法由两套监听者共用。
- `k8s-pr-preview-testing` 会处理同名 PR Preview Kind 集群和 `30123` 宿主映射，两个进程可能互删集群或因端口已占用而失败。
- `k8s-mysql` 会处理同名 MySQL Kind 集群，两个 agent 建立的 `30124` port-forward 也无法同时绑定。
- `meeting-assign` 的 preprocess 会先终止占用 `30137` 的进程，因此后启动的任务会直接杀掉前一个模型的临时 HTTP 服务。

A 和 B 组本身可以不受这十个宿主端口的影响，但多模型并发仍可能触发模型 API 或外部服务的限流。C-remote 需要隔离 Google、GitHub、Hugging Face 等远端资源；C-notion 需要隔离 Notion 页面和认证状态，以及所用的 Google/GitHub/W&B 资源和邮件账号。

因此，单模型五组并发应遵循“部署一次、启动五组、等待全部结束”。多模型并发时，应协调共用基础设施的 C-local 和 C-notion 邮件任务，并串行或隔离同一任务使用的 Notion 页面。真正并行时需为每个模型准备独立 checkout/worktree、prefix、suffix、端口、基础设施数据及远端任务资源。

## dump 与结果合并

多个 `scripts/run_parallel.sh` 进程不能共享同一个 dump 目录。虽然任务叶子目录可能互不重叠，但每个进程都会覆盖 dump 根下的 `stdout.log`、`container_all.log`、`run_all.log`、`eval_res_all.jsonl`、`traj_log_all.jsonl` 和 `eval_stats.json`。

运行结束后可以创建一个新的 merged 目录，但只合并各组的 `finalpool/<task>/` 叶子目录，并要求同名任务直接报错。不要复制各组已有的顶层汇总文件；应在 merged 目录上重新生成统计。只有模型、provider、配置、镜像、代码版本和 attempt 都一致的五组结果才能合并为一次正式评测。

## 已知边界

- A 的“无网络依赖”仅指任务工具；远程模型 API 仍然需要网络。
- `task_conflict.json` 只覆盖四个已声明的冲突组。C-local、C-remote、C-notion 仍可能共享 Google/GitHub 等远端资源，C-local 与 C-notion 还共享 Poste；跨实验的 C-notion 也可能共用 Notion 页面和认证。五组拆分本身不提供跨进程外部状态隔离。
- task-list 的执行顺序不固定，`run_parallel.py` 会在执行前随机打乱任务。
- 当前范围只实现分组清单和薄封装脚本，不实现结果合并工具。

清单结构可用以下聚焦测试验证：

```bash
python3 -m unittest discover -s tests -p 'test_finalpool_task_lists.py'
```
