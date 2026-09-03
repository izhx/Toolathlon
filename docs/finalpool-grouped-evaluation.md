# finalpool 分组评测设计

## 目标

依据 `docs/finalpool-task-risk-classification.md`，将 `tasks/finalpool` 的 108 个任务拆成 4 个互斥且完备的 task list。运行时仍只保留一份 canonical `tasks/finalpool`，不复制任务目录，也不为任务创建软链接。

分组通过一个薄封装脚本调用现有 `scripts/run_parallel.sh`。每次调用显式指定 task-list 文件和独立 dump 目录，因此四组可以由四个进程同时运行。

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
  <task-list-file> \
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

1. 校验 task-list 文件存在且 dump 路径已给出。
2. 将 task-list 文件通过 `TASK_LIST` 环境变量传给 `scripts/run_parallel.sh`。
3. 将 dump 路径和其余运行参数传给现有入口。
4. 在 dump 根持有一个非阻塞文件锁；另一个通过该脚本启动的进程如果复用同一 dump，会立即失败。

它不负责部署基础设施、不在后台创建四个进程，也不合并结果。这样部署、运行和结果整理三个生命周期保持分离。

相对 task-list 路径和 dump 路径均从仓库根目录解析，因此可以从其他工作目录调用该脚本。

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
  configs/task_lists/finalpool/a-no-network.txt \
  results/<run-id>/a-no-network \
  <model-name> unified 10
```

其余三组替换 task-list 和 dump 子目录即可。并发启动由外层终端、作业系统或进程管理器完成；四个命令不能复用同一个 dump 子目录。

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
