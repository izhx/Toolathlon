# Toolathlon 端口、部署生命周期与并发隔离分析

- 分析日期：2026-09-03
- 适用范围：本仓库本地 `containerized` / `decoupled` 正式评测流程
- 分析方式：基于当前源码和配置静态核对，未启动容器或执行正式并发评测

## 一、结论

Toolathlon 当前将端口分为两类：

1. Canvas、Poste、WooCommerce 使用评测前部署的共享基础设施端口。完整正式评测开始前，需要执行一次 `global_preparation/deploy_containers.sh` 重置这些服务。
2. `30123`、`30124`、`30137` 是具体任务使用的临时端口，由任务 preprocess 或 agent 在任务执行过程中创建，不需要人工提前部署。

多代码目录可以通过独立端口段、`instance_prefix` 和 `instance_suffix` 隔离。同一代码目录目前只有一份 `ports_config.yaml` 和一套被改写的源码，不能让两个并发评测分别使用不同端口配置；完整多模型并发应使用独立 checkout/worktree，或先完成运行时端口配置改造。

## 二、端口清单

当前默认端口及本 checkout 在 `configs/ports_config.yaml` 中配置的目标端口如下：

| 默认端口 | 当前目标端口 | 用途 | 生命周期 |
|---:|---:|---|---|
| 10001 | 11001 | Canvas HTTP | 评测前部署的共享基础设施 |
| 20001 | 21001 | Canvas HTTPS 代理 | 评测前部署的宿主 Node 进程 |
| 10005 | 11005 | Poste Web | 评测前部署的共享基础设施 |
| 2525 | 3525 | Poste SMTP | 同一个 Poste 容器 |
| 1143 | 2143 | Poste IMAP | 同一个 Poste 容器 |
| 1587 | 2587 | Poste SMTP submission | 同一个 Poste 容器 |
| 10003 | 11003 | WooCommerce | 评测前部署的共享基础设施 |
| 30123 | 31123 | K8s PR Preview | 任务 preprocess 创建，agent 部署应用 |
| 30124 | 31124 | K8s MySQL port-forward | preprocess 创建数据库，agent 建立转发 |
| 30137 | 31137 | Meeting 临时 HTTP 服务 | 任务 preprocess 创建 |

目标端口只有在执行 `global_preparation/apply_port_numbers.py` 后才会写入实际部署脚本和任务文件。只编辑 `port_mappings` 不会改变当前硬编码端口。

## 三、端口硬编码位置

### 3.1 集中登记表

`configs/ports_config.yaml` 的 `files_by_port` 是替换文件登记表。当前登记规模如下：

| 端口 | 登记文件数 | 主要范围 |
|---:|---:|---|
| 1143 | 53 | 邮件任务 JSON、Python 和 Poste 部署 |
| 2525 | 3 | Poste 部署和个别任务配置 |
| 1587 | 42 | 邮件任务 JSON、Python 和 Poste 部署 |
| 10001 | 28 | Canvas 部署、客户端和任务脚本 |
| 10003 | 16 | WooCommerce 部署和任务配置 |
| 10005 | 3 | Poste 部署和用户创建脚本 |
| 20001 | 5 | Canvas 配置和 HTTPS 代理 |
| 30123 | 6 | K8s PR Preview 任务 |
| 30124 | 3 | K8s MySQL 任务 |
| 30137 | 3 | Meeting Assign 任务 |

关键入口包括：

- `global_preparation/deploy_containers.sh`：集中声明全部十个默认端口，并负责部署前端口检查。
- `deployment/canvas/scripts/setup.sh`：Canvas HTTP/HTTPS 端口。
- `deployment/poste/scripts/setup.sh`：Poste Web、SMTP、IMAP 和 submission 端口。
- `deployment/woocommerce/scripts/setup.sh`：WooCommerce HTTP 端口。
- `tasks/finalpool/**`：任务侧 URL、邮件配置、K8s 检查和临时服务端口。

### 3.2 当前替换机制

`global_preparation/apply_port_numbers.py` 调用 `PortReplacer`，对 `files_by_port` 中登记的文件执行纯文本数字替换：

```text
(?<![0-9])<default_port>(?![0-9])
```

该机制有以下边界：

- 它不会自动发现未登记的新硬编码位置；遗漏文件仍会使用默认端口。
- 它不理解字段语义；只要登记文件中出现相同的独立数字，就会被替换。
- 它直接修改 checkout 中的部署脚本、任务代码、JSON 和文档，并通过 `configs/port_changes.json` 记录恢复信息。
- 同一 checkout 只能维持一套已应用端口状态；再次 apply 会先根据 changelog 恢复，再应用新配置。

曾经登记在 `10001` 下的 `tasks/finalpool/woocommerce-product-recall/preprocess/setup_recall_data.py` 实际包含的是纽约邮编 `10001`，不是端口。当前工作区已将它移出有效替换列表，并保留注释说明。这说明端口登记表仍需在新增任务或端口时人工审查。

## 四、部署生命周期

### 4.1 完整评测前需要部署

正式完整评测前运行一次：

```bash
bash global_preparation/deploy_containers.sh true
```

脚本会停止同一 `instance_suffix` 的旧实例，然后并行启动：

| 组件 | 创建内容 | 相关硬编码端口 |
|---|---|---|
| Canvas | `canvas-docker<suffix>` 容器和宿主 HTTPS 代理 | 10001、20001 |
| Poste | `poste<suffix>` 容器 | 10005、2525、1143、1587 |
| WooCommerce | WordPress、数据库容器和网络 | 10003 |
| Kind | 基础 `cluster<suffix>1` 集群 | 不直接使用上述 `301xx` 端口 |

Canvas、Poste 和 WooCommerce 的状态会被任务修改，所以正式流程要求每次完整模型评测前重置。部署一次之后再启动该实例的任务，不需要为每个普通任务重复部署。

`deploy_containers.sh` 没有按服务选择的参数，并且 readiness probe 要求 Canvas、Poste、WooCommerce 和基础 Kind 全部就绪。只跑明确任务子集时可以人工调用单个服务的 setup 脚本，但这不属于当前完整正式流程，调用者需要自行证明任务不依赖未部署服务。

### 4.2 由任务自动创建，不需要提前部署

#### `30123`：K8s PR Preview

`k8s-pr-preview-testing` 的 preprocess 会删除旧的任务专用 Kind 集群，创建 `cluster-pr-preview<suffix>`，并配置同端口的 Kind `extraPortMappings`。随后由 agent 在集群中部署应用。用户不需要在评测前单独启动 `30123` 服务。

#### `30124`：K8s MySQL

`k8s-mysql` 的 preprocess 会创建 `cluster-mysql<suffix>`、部署 MySQL 并导入数据。任务要求 agent 建立 `kubectl port-forward`；evaluation 会检查 `30124` 转发进程及数据库连通性。该端口不是全局部署服务。

#### `30137`：Meeting Assign

`meeting-assign` 的 preprocess 会清理旧监听并运行：

```bash
python -m http.server 30137
```

该进程位于使用 host network 的任务容器中，随任务容器结束，不需要提前部署。

### 4.3 不要在评测过程中重新部署

部署脚本会：

- 停止并重建同一 suffix 的 Canvas、Poste、WooCommerce 和 Kind 资源；
- 检查所有十个端口；
- 对占用端口的非 Docker/Podman 管理进程执行 `kill -9`；
- 执行 daemon 级的 dangling volume、旧 stopped container 和 dangling image 清理。

因此评测运行期间重新执行部署脚本，可能杀掉 `30124` 的 `kubectl port-forward`、`30137` 的 Python HTTP server，或者删除同实例正在使用的基础设施。正确顺序是先完成部署，再启动评测，评测结束前不再 deploy、restore 或切换端口配置。

## 五、不同代码目录并行

每个 checkout 应视为一个完整 Toolathlon 实例，至少隔离以下内容：

| 隔离面 | 要求 |
|---|---|
| `instance_prefix` | 每个 checkout 唯一，用于任务容器名称 |
| `instance_suffix` | 每个 checkout 唯一，用于 Canvas、Poste、WooCommerce、Kind 等资源名称 |
| `port_mappings` | 十个目标端口全部不重叠，并先确认宿主未占用 |
| `dump_path` | 每个模型、attempt、代码和镜像使用独立目录 |
| 基础设施数据 | 保持在各 checkout 自己的 deployment 目录，不交叉挂载 |
| Docker 镜像 | 可以共享不可变 digest；不要在评测期间并发覆盖同一 tag |

操作流程：

```bash
# 每个 checkout 分别编辑 configs/ports_config.yaml
uv run python global_preparation/apply_port_numbers.py --dry-run
uv run python global_preparation/apply_port_numbers.py -y
uv run python global_preparation/apply_port_numbers.py --status

# 两个实例分别部署；确认全部 ready 后再启动评测
bash global_preparation/deploy_containers.sh true
bash scripts/run_parallel.sh <model> <unique-dump-path> unified <workers>
```

不要把两个并发 checkout 的整个 `configs/` 软链接到同一个目录，否则二者会共享同一份 `ports_config.yaml` 和端口改写目标。普通静态配置、端口配置和 `.mcp-auth` 的共享语义不同，不能作为一个整体处理。

## 六、同一代码目录运行不同模型

### 6.1 当前可以安全共享的内容

- `scripts/run_parallel.sh` 为每个进程生成带时间、PID 和随机数的临时模型配置文件。
- 模型 URL、API key 和模型参数可以通过各启动 shell 的环境变量独立继承。
- 两次运行使用完全不同的 `dump_path` 时，结果文件不会直接覆盖。

### 6.2 当前仍存在的冲突

- 整个 checkout 只有一份 `ports_config.yaml` 和 `port_changes.json`。
- 端口 apply 会修改同一批源码文件，不能在运行期间为另一个模型切换。
- 任务容器名使用 `instance_prefix + task + 秒级时间戳`；两个模型同秒启动同一任务可能重名。
- `task_conflict.json` 使用单个 `run_parallel.py` 进程内的 `asyncio.Lock`，不能协调两个模型进程。
- 两个模型仍会修改同一套 Canvas、Poste、WooCommerce、Kind 和任务临时端口状态。
- 两个进程若共享同一个 dump 根，还会覆盖 `stdout.log`、聚合 JSONL 和 `eval_stats.json`。

因此，只修改模型名和 dump 路径不足以安全并发完整 `finalpool`。

### 6.3 推荐方案

短期建议从同一 commit 创建两个独立 worktree，各自应用端口配置并部署：

```bash
git worktree add --detach ../Toolathlon-model-a "$(git rev-parse HEAD)"
git worktree add --detach ../Toolathlon-model-b "$(git rev-parse HEAD)"
```

如果必须保持同一个物理 checkout，需要实现一等运行实例配置：

1. 新增 `--instance-id` 和每次运行独立的 runtime config。
2. 停止全仓库端口数字替换，改为环境变量或解析后的任务配置快照。
3. 容器、网络、数据目录、日志、kubeconfig 和清理操作全部按 instance ID 隔离。
4. 容器名加入 UUID，并使用精确 label 清理。
5. 将冲突锁改为宿主文件锁或统一的跨模型调度器。

## 七、其他未纳入 `ports_config.yaml` 的端口

以下端口也可能在同机多实例时冲突，但当前不由 `apply_port_numbers.py` 管理：

| 默认端口 | 用途 | 当前行为 |
|---:|---|---|
| 8080 | Evaluation server | 启动 `eval_server.py` 时用位置参数指定 |
| 8081 | WebSocket proxy | 与 evaluation server 配套指定 |
| 8000 | 轨迹可视化服务 | `vis_traj/server.py --port` 显式指定 |
| 3000 | Google OAuth 本地回调 | 仅账号初始化阶段使用，不能并发占用 |
| 动态端口 | Decoupled MCP gateway | 未显式传入时临时选择空闲端口 |

所以 `ports_config.yaml` 的十个映射不是同机多实例的完整端口命名空间；使用 evaluation server、可视化、OAuth 初始化或显式 gateway 端口时仍需单独分配。

## 八、验证清单

部署前：

```bash
uv run python global_preparation/apply_port_numbers.py --status
docker ps --format '{{.Names}}\t{{.Ports}}'
kind get clusters
ss -ltnp
```

确认：

- 当前 checkout 的 prefix、suffix 和十个目标端口均唯一；
- 实际源码端口已经 apply，而不只是修改了 YAML；
- 没有其他实例使用相同容器、网络或 Kind 名称；
- 本次运行使用新的 dump 目录；
- 部署完成后不再执行 deploy 或 restore，直到评测结束。

