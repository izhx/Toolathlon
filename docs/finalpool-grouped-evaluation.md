# finalpool 分组评测设计

## 目标

依据 `docs/finalpool-task-risk-classification.md`，将 `tasks/finalpool` 的 108 个任务拆成 4 个互斥且完备的 task list。运行时仍只保留一份 canonical `tasks/finalpool`，不复制任务目录，也不为任务创建软链接。

分组通过一个薄封装脚本调用现有 `scripts/run_parallel.sh`。分组运行时通过 `--task-list` 显式指定清单和独立 dump 目录，因此四组可以由四个进程同时运行；省略 `--task-list` 时运行 `tasks/finalpool` 全量任务。

## 分组

| 分组 | 数量 | 判据 | 是否依赖 `deploy_containers.sh` |
|---|---:|---|---|
| A 无网络依赖 | 15 | 分类文档 A | 否 |
| B 网络只读 | 30 | 分类文档 B | 否 |
| C 本地基础设施写 | 35 | 分类文档 C，且 `needed_mcp_servers` 至少包含 `canvas`、`emails`、`woocommerce`、`k8s` 之一 | 是 |
| C 远端写 | 28 | 分类文档 C，但不依赖上述四类本地基础设施 | 否 |

对应文件：

- `configs/task_lists/finalpool/a-no-network.txt`
- `configs/task_lists/finalpool/b-network-read-only.txt`
- `configs/task_lists/finalpool/c-local-infrastructure-write.txt`
- `configs/task_lists/finalpool/c-remote-write.txt`

四个文件必须满足以下不变量：

1. 每个有效行只包含一个 `tasks/finalpool` 下的任务 basename。
2. 四组之间没有重复任务。
3. 四组并集恰好覆盖 108 个任务。
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

默认情况下它不负责部署基础设施、不在后台创建四个进程，也不合并结果。显式传入 `--deploy-before-attempt` 时，它会在每个 attempt 前运行一次 `global_preparation/deploy_containers.sh`；部署失败会终止当前进程和剩余 attempts。该行为不会根据 task-list 文件名自动开启。

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
└── c-remote-write/
```

如果要运行 C 本地基础设施写组，先在没有评测进程运行时部署一次：

```bash
bash global_preparation/deploy_containers.sh true
```

部署成功后再启动四组。不要在其他组运行期间重新执行部署脚本，因为它会清理并重建共享容器、网络和端口。

示例：

```bash
bash scripts/run_parallel_task_list.sh \
  --task-list configs/task_lists/finalpool/a-no-network.txt \
  results/<run-id>/a-no-network \
  <model-name> unified 10
```

其余三组替换 task-list 和 dump 子目录即可。并发启动由外层终端、作业系统或进程管理器完成；四个命令不能复用同一个 dump 子目录。

同一分组连续运行 3 次时，可以使用：

```bash
bash scripts/run_parallel_task_list.sh \
  --attempts 3 \
  --task-list configs/task_lists/finalpool/a-no-network.txt \
  results/<experiment-id> \
  <model-name> unified 10
```

输出为 `results/<experiment-id>/<model-name>__run1/a-no-network` 至 `<model-name>__run3/a-no-network`。其他三个分组可以共享同一个 experiment root，各自写入对应的 task-list basename 子目录。

`--attempts` 本身只编排评测，不会重置基础设施。C 本地组如果要求每次 attempt 都使用重新部署的 Canvas、Poste、WooCommerce 和 Kind，可以显式执行：

```bash
bash scripts/run_parallel_task_list.sh \
  --deploy-before-attempt \
  --attempts 3 \
  --task-list configs/task_lists/finalpool/c-local-infrastructure-write.txt \
  results/<experiment-id> \
  <model-name> unified 2
```

A、B 和 C 远端组不依赖 `deploy_containers.sh`，不应传入该参数。该参数只控制当前分组进程，不会等待或协调另外三个分组。当前部署脚本还会执行宿主 Docker prune 并清理固定服务和端口，因此在其他评测容器运行期间使用前，需要接受共享 Docker daemon 被修改的风险；如果要求最保守的生命周期隔离，仍由外层作业等待所有分组结束后再部署。

不指定 task-list、直接运行全量 `finalpool` 的示例：

```bash
bash scripts/run_parallel_task_list.sh \
  --attempts 3 \
  results/<experiment-id> \
  <model-name> unified 10
```

输出位于 `results/<experiment-id>/<model-name>__run1` 至 `<model-name>__run3`，不再增加 `all-tasks` 子目录。全量任务包含 C 本地组；如果每次 attempt 都要求重置本地基础设施，还应显式传入 `--deploy-before-attempt`。

## 端口任务与四组并发关系

按 `configs/ports_config.yaml` 中当前有效的 `files_by_port` 任务路径统计，十个受管端口共直接涉及 33 个唯一任务，全部位于 C 本地基础设施写组：

| 分组 | 任务数 | 直接登记端口的任务数 | 端口关系 |
|---|---:|---:|---|
| A 无网络依赖 | 15 | 0 | 无直接宿主端口冲突 |
| B 网络只读 | 30 | 0 | 无直接宿主端口冲突 |
| C 本地基础设施写 | 35 | 33 | 集中使用 Canvas、Poste、WooCommerce 和三个任务临时端口 |
| C 远端写 | 28 | 0 | 无直接宿主端口冲突，但仍可能冲突于远端账号或资源 |

C 本地组中只有 `k8s-redis-helm-upgrade` 和 `k8s-safety-audit` 未直接登记固定端口。按端口分别统计时，`1143`、`1587`、`2525` 直接涉及 24、23、1 个任务，`10001`、`20001` 涉及 8、1 个任务，`10003` 涉及 9 个任务，`30123`、`30124`、`30137` 各涉及 1 个任务。同一任务可同时使用多个端口，因此这些数量不能相加；`10005` 只出现在 Poste 部署和用户初始化脚本中，没有直接登记的任务文件。

### 单模型的四组并发

同一模型按当前四份清单各启动一个进程时，不会在组与组之间发生这十个端口的重复绑定，因为所有直接端口任务都在唯一的 C 本地进程中。Canvas、Poste 和 WooCommerce 只需预先部署一套监听者，普通任务是它们的客户端；`30123`、`30124`、`30137` 也分别只属于一个任务。

这只是“不重复 bind 同一端口”，不代表 C 本地组内没有状态竞争。多个任务仍会并发修改同一套 Canvas、Poste 或 WooCommerce 数据。当前 `task_conflict.json` 中的三个 C 本地冲突对位于同一份清单，所以同一 `run_parallel.py` 进程内的锁能使其串行；该锁不覆盖未登记的共享状态竞争。C 远端组中的 Hugging Face 冲突对也位于同一进程。

### 多模型同机并发

如果多个模型各自同时运行四组，它们的 C 本地进程会直接相互冲突。`task_conflict.json` 的锁是进程内 `asyncio.Lock`，不能协调不同模型进程。具体影响取决于部署方式：

- 多个模型共用已部署的一套 Canvas、Poste 和 WooCommerce 时，通常不会再次绑定服务端口，但任务的初始化、agent 操作和 evaluator 会交叉修改同一份状态，结果可能串污且不可复现。
- 每个模型都使用相同 prefix、suffix 和端口执行 `deploy_containers.sh` 时，后一次部署会停止或重建前一次评测使用的基础设施，同时端口也无法由两套监听者共用。
- `k8s-pr-preview-testing` 会处理同名 PR Preview Kind 集群和 `30123` 宿主映射，两个进程可能互删集群或因端口已占用而失败。
- `k8s-mysql` 会处理同名 MySQL Kind 集群，两个 agent 建立的 `30124` port-forward 也无法同时绑定。
- `meeting-assign` 的 preprocess 会先终止占用 `30137` 的进程，因此后启动的任务会直接杀掉前一个模型的临时 HTTP 服务。

A 和 B 组本身可以不受这十个宿主端口的影响，但多模型并发仍可能触发模型 API 或外部服务的限流。C 远端组不占用这些本地端口，但必须另外隔离 Notion、Google、GitHub、Hugging Face 等远端账号与资源。

因此，单模型四组并发应遵循“部署一次、启动四组、等待全部结束”。多模型并发时，至少要将 C 本地组按基础设施实例串行；如果需要 C 本地组也真正并行，应为每个模型使用独立 checkout/worktree、prefix、suffix、十个端口和基础设施数据。

## dump 与结果合并

多个 `scripts/run_parallel.sh` 进程不能共享同一个 dump 目录。虽然任务叶子目录可能互不重叠，但每个进程都会覆盖 dump 根下的 `stdout.log`、`container_all.log`、`run_all.log`、`eval_res_all.jsonl`、`traj_log_all.jsonl` 和 `eval_stats.json`。

运行结束后可以创建一个新的 merged 目录，但只合并各组的 `finalpool/<task>/` 叶子目录，并要求同名任务直接报错。不要复制各组已有的顶层汇总文件；应在 merged 目录上重新生成统计。只有模型、provider、配置、镜像、代码版本和 attempt 都一致的四组结果才能合并为一次正式评测。

## 已知边界

- A 的“无网络依赖”仅指任务工具；远程模型 API 仍然需要网络。
- `task_conflict.json` 只覆盖已显式声明的四组冲突。不同 C 组仍可能共享 Notion、Google、GitHub 等账号或远端资源；四组拆分本身不提供跨进程外部状态隔离。
- task-list 的执行顺序不固定，`run_parallel.py` 会在执行前随机打乱任务。
- 当前范围只实现分组清单和薄封装脚本，不实现结果合并工具。

清单结构可用以下聚焦测试验证：

```bash
python -m unittest tests.test_finalpool_task_lists
```
