# finalpool 五组并发风险分析

- 分析日期：2026-09-03；分组更新：2026-09-07（主机资源和运行条件仍为原检查快照，本次未重新验证）
- 适用范围：当前 checkout 中的五个 `finalpool` task list，以及 `containerized` / `decoupled` 并行评测流程
- 分析方式：源码审计、任务配置核对、聚焦测试和只读主机检查；未启动正式任务、基础设施或真实 OAuth/API 并发验证

## 一、结论

五组在任务清单和 dump 目录层面可以并行，但当前环境还不能直接开始正式评测，也不建议按默认参数一次启动 `5 × 10 = 50` 个 workers（C-notion 只有 8 个任务，实际同时活跃任务上限为 48）。

| 判断项 | 结论 |
|---|---|
| 五组任务是否重复 | 否；共享服务的状态和生命周期仍需协调 |
| 已声明冲突是否跨组 | 否，可以由现有进程内锁处理 |
| dump 是否会覆盖 | 使用当前 `--attempts` 布局时不会 |
| 本地基础设施是否完全隔离 | 否，仅做到任务命名空间隔离，不是实例隔离 |
| 外部账号是否隔离 | 否，共享 Notion、Google、GitHub、Hugging Face 等账号 |
| 当前机器是否已具备运行条件 | 否 |
| 是否建议五组各使用 10 workers | 不建议 |
| 是否支持各组运行三次 | 支持；C-local 可要求 attempt 前完整部署；C-notion 复用 Poste，重建前必须协调相关任务 |

总体建议：

- 探索性运行：补齐环境后，可以从低并发开始并行。
- 正式、可比较的三次评测：如果 C-local 要求 attempt 前重建，必须先确认共享 Poste 的 C-notion 邮件任务结束；要求同步的 108-task 轮次或完整部署隔离时，使用五组屏障。
- 当前 checkout 立即开跑：单组也会因为运行环境缺失而失败。

## 二、任务清单和调度锁

五组当前数量如下：

| 分组 | 数量 |
|---|---:|
| `a-no-network` | 15 |
| `b-network-read-only` | 30 |
| `c-local-infrastructure-write` | 33 |
| `c-remote-write` | 22 |
| `c-notion` | 8 |
| 合计 | 108 |

聚焦检查结果：

- 五组交集为空；
- 五组并集恰好覆盖 108 个 `tasks/finalpool` 任务目录；
- 没有缺失或额外任务；
- 三个显式冲突组位于 `c-local`，一个位于 `c-remote`；
- `tests.test_finalpool_task_lists` 和 `tests.test_run_parallel_task_list` 共 21 个测试通过。

当前 `tasks/finalpool/task_conflict.json` 中有四个冲突组：

1. `set-conf-cr-ddl` / `student-interview`
2. `huggingface-upload` / `dataset-license-issue`
3. `woocommerce-customer-survey` / `woocommerce-product-recall`
4. `canvas-submit-late-work` / `canvas-do-quiz`

这些冲突对没有被拆到两个 task list，所以同一组内的 `run_parallel.py` 可以对它们加锁。

但是，`run_parallel.py` 为每个 `AsyncTaskScheduler` 创建自己的 `asyncio.Lock`。该锁只对当前 Python 进程有效，不能协调：

- 另一个 task-list 进程；
- 另一次实验；
- 另一个 checkout/worktree；
- 绕过该调度器直接启动的任务。

五组当前能保留声明锁语义，是因为已声明冲突对全部位于同一组，不代表所有共享后端冲突都已登记。

## 三、dump 路径与结果隔离

当前 `scripts/run_parallel_task_list.sh --attempts 3` 使用模型加 attempt 层，并在其下按 task-group 隔离结果：

```text
results/<experiment-id>/
├── <model>__run1/
│   ├── a-no-network/
│   ├── b-network-read-only/
│   ├── c-local-infrastructure-write/
│   ├── c-remote-write/
│   └── c-notion/
├── <model>__run2/
│   └── ...
└── <model>__run3/
    └── ...
```

上图是显式传入 `--task-list` 的五组运行布局。省略 `--task-list` 运行全量任务时，不增加 task-group 层，直接写入 `results/<experiment-id>/<model>__run<attempt>/`。

该布局具有以下性质：

- attempt 之间不覆盖；
- group 之间不覆盖；
- 模型名中的 `/` 会替换为 `_`；
- 五个不同 group 可以共享同一个 experiment root；
- 同一实验根下，同一 group 被重复启动时会被 group 文件锁拒绝。

如果不使用 `--attempts`，每个 group 必须显式使用独立 dump 子目录。不能让多个 `scripts/run_parallel.sh` 进程共享同一个精确 dump 目录，因为每个进程都会覆盖以下文件：

- `stdout.log`
- `container_all.log`
- `run_all.log`
- `eval_res_all.jsonl`
- `traj_log_all.jsonl`
- `eval_stats.json`

五组结束后，各自的 `eval_stats.json` 只代表该组，不能直接视为一次 108-task 总分。正式汇总时应只合并 `finalpool/<task>/` 叶子目录，并重新生成统计。

## 四、共享资源竞态审计

### 4.1 已排除：`canvas-art-manager` / `canvas-homework-grader-python` 邮箱冲突

`c-local` 中的 8 个 Canvas 任务和 22 个邮件任务不会自动全部串行；`c-notion` 另有 2 个邮件任务，也连接同一 Poste。

初步检查时曾怀疑以下两个任务会同时修改 `teresat@mcp.com`：

- `canvas-art-manager` 先清空 `mcpcanvasadmin3@mcp.com`；
- 随后随机选择 100–150 封干扰邮件，与目标邮件一起导入；
- 它的 300 封候选干扰邮件全部发往 `teresat@mcp.com`；
- `canvas-homework-grader-python` 恰好会清空并重建 `teresat@mcp.com` 的 INBOX。

继续沿实际导入链路核对后，可以排除这个冲突：

- `canvas-art-manager/token_key_session.py` 指向该任务自己的 `email_config.json`，其中登录账号是 `mcpcanvasadmin3@mcp.com`；
- `canvas-homework-grader-python/email_config.json` 登录的是 `teresat@mcp.com`；
- `configs/mcp_servers/emails.yaml` 使用任务的 `emails_config_file` 启动 `emails-mcp`；
- `emails-mcp` 的 `import_emails` 使用当前已认证的 IMAP 连接执行 `APPEND`，把邮件加入该账号的目标文件夹；备份数据中的 `to_addr` 只会还原为邮件的 `To:` 头，不负责选择目标邮箱。

因此，`canvas-art-manager` 中写着 `to_addr=teresat@mcp.com` 的干扰邮件实际会被追加到 `mcpcanvasadmin3@mcp.com` 的 INBOX，不会写入 Teresa 的邮箱。两个任务并发时分别清理和重建不同账号，不需要增加以下冲突组：

```json
["canvas-art-manager", "canvas-homework-grader-python"]
```

该数据仍有语义不整洁的问题：`canvas-art-manager` 的干扰邮件收件人头与实际邮箱账号不一致。若后续希望提高任务数据可读性，可以单独修正 `fake_emails.json`，但这不是并发正确性问题。

其他 Canvas 任务当前大多使用不同课程名或课程后缀。部分任务会操作相同的 Canvas 用户，但主要是在不同课程中注册用户，暂未发现同等级的直接课程覆盖。

即使课程名不同，8 个任务仍共享同一个 Canvas 服务和数据库，因此高并发下仍可能出现 API 超时、数据库压力和最终一致性延迟。

### 4.2 C-notion 组内串行瓶颈与跨实验共享认证

**执行规则：C-notion 固定使用 `workers=1`，一个任务的 preprocess、agent、evaluation 全部结束后再开始下一个；不同模型或 checkout 的 Notion 作业也不能重叠运行。** 刷新锁不能代替整任务串行。命令见 [Notion 评测](notion-evaluation.md)。下文的并发等待分析说明违反该规则时的风险。

任务的 `needed_mcp_servers` 中写的是 `notion`，但相关 preprocess 会间接调用 `notion_official`：

- 全部 8 个 Notion 任务已归入独立一级清单 `configs/task_lists/finalpool/c-notion.txt`；
- C-local 和 C-remote 不再包含 Notion 任务。

任务容器会把宿主机的 `configs/.mcp-auth` 读写挂载到 `/workspace/configs/.mcp-auth`。Notion OAuth refresh token 会轮换，因此多个容器同时刷新同一认证状态可能导致旧 token 失效。

当前 `utils/app_specific/notion/notion_page_duplicator.py` 已使用：

```text
configs/.mcp-auth/notion_official_refresh.lock
```

配合 `flock` 串行化 Notion MCP 生命周期。这能避免 refresh token 写入竞态，但也会带来吞吐问题：

- 8 个 Notion preprocess 不能真正同时 duplicate；
- 等待该文件锁的任务已经占用了 task container 和 scheduler worker；
- 锁等待上限为 600 秒；
- 持锁任务的 page-ready 等待本身最多可达 600 秒，之后还有 move retry。

如果随机调度首先选中多个 Notion 任务，`c-notion` 的多个 worker 可能同时处于等待锁状态，严重时等待者会超时。

当前 8 个 Notion 子页面名称不同，暂未发现它们互相删除同一个页面。主要风险是共享认证状态、吞吐和等待超时。同一轮 Notion 调用现集中在 C-notion 进程内，但多个实验或 checkout 仍可能共享认证目录；分组不能代替刷新锁和远端页面隔离。

### 4.3 Google Sheets

当前共有 11 个 Google Sheets 任务：

- `c-local`：3 个；
- `c-remote`：7 个；
- `c-notion`：1 个（`quantitative-financial-analysis`）。

当前配置的 11 个文件夹名不同，因此同一轮五组运行中暂未发现直接删除同一个任务文件夹的情况。

但 `utils/app_specific/googlesheet/drive_helper.py` 的行为存在以下边界：

1. 通过全局文件夹名查找；
2. 如果存在多个同名文件夹，直接使用 API 返回的第一个；
3. preprocess 会删除该文件夹中的全部文件；
4. 复制进去的 Sheet 会授予 `anyone/writer` 权限。

因此仍存在以下风险：

- 历史遗留的同名文件夹导致选择错误；
- 同一个任务被另一场实验同时运行时互相清空文件；
- 所有任务共享 Google Drive/Sheets 账号和 API quota。

### 4.4 Google Cloud、GitHub、Hugging Face

当前配置审计没有发现五组内使用相同的 BigQuery dataset、GitHub repo 或主要 Hugging Face 目标：

- 8 个 Google Cloud 任务使用不同 BigQuery dataset；
- GitHub 写任务使用不同目标 repo；
- 两个真正会删除/重建 Hugging Face dataset 的任务已位于同一 conflict group；
- 4 个 Snowflake 任务使用不同数据库。

但这些任务仍共享同一个账号、token 或 project，因此存在：

- API rate limit；
- GitHub secondary rate limit；
- Google Cloud job/quota 限制；
- 同一任务被另一场实验同时运行时的删除/重建竞态；
- 远端最终一致性导致 evaluator 过早读取。

## 五、各组共享服务情况

| 服务 | 涉及分组 |
|---|---|
| Notion | `c-notion: 8` |
| Google Sheets | `c-local: 3`，`c-remote: 7`，`c-notion: 1` |
| Google Cloud | `c-local: 1`，`c-remote: 7` |
| GitHub | `B: 2`，`c-local: 1`，`c-remote: 3`，`c-notion: 1` |
| Hugging Face | `c-remote: 5` |
| Google Map | `B: 5`，`c-notion: 1` |
| W&B | `B: 2`，`c-notion: 1` |
| Emails/Poste | `c-local: 22`，`c-notion: 2` |

本地有状态服务主要集中在 `c-local`：

- Canvas：8 个任务；
- Emails/Poste：22 个 C-local 任务，另有 2 个 C-notion 任务共用；
- WooCommerce：9 个任务；
- K8s：5 个任务；
- Snowflake：4 个任务。

A、B、C-remote 不直接使用这些本地后端；C-local 内仍有共享状态访问，C-local 与 C-notion 之间也共享 Poste。不能用进程内 task_conflict 锁推断跨组邮箱状态已隔离。

## 六、主机资源风险

当前主机计算资源：

- CPU：64 核；
- 内存：约 1 TiB，检查时可用约 967 GiB。

计算资源不是当前最明显的瓶颈，但以下资源存在风险。

### 6.1 inotify

当前值：

```text
fs.inotify.max_user_watches=65536
fs.inotify.max_user_instances=128
fs.inotify.max_queued_events=16384
```

检查时已有约 14 个 inotify instance 被使用。仓库安装脚本建议：

```text
fs.inotify.max_user_watches=1048576
fs.inotify.max_user_instances=16384
fs.inotify.max_queued_events=16384
```

Kind、Node MCP server、Playwright 和文件监控程序都会消耗 inotify instance。五组各配置 10 workers 时，最多 48 个活跃任务容器比较容易遇到 `ENOSPC` 或文件监控初始化失败。

### 6.2 磁盘

当前 `/data8`：

```text
总容量约 7.3T
已使用约 6.4T
剩余约 471G
使用率 94%
```

Docker 当前有约 396.8 GiB 镜像被标记为可回收。虽然 471 GiB 对单轮运行可能仍然足够，但三轮任务输出、Kind 节点、容器可写层、镜像拉取和日志会继续增长。

不应只按剩余绝对容量判断；94% 使用率意味着运行期间更容易触发数据库、Docker 或日志写入失败。

### 6.3 模型 API 并发

五组各配置 10 workers，总配额为 50；C-notion 只有 8 个任务，最多约 48 个 agent 同时运行。`scripts/run_parallel.sh` 生成的配置还允许 `parallel_tool_calls=true`。

即使 CPU 和内存足够，也可能先遇到：

- 模型 API RPM/TPM 限制；
- HTTP 429；
- 长请求排队；
- 任务 5400 秒 timeout；
- 外部 MCP 服务同时限流。

建议初始 workers：

```text
A        4
B        4
C-local  2
C-remote 1
C-notion 1
总并发  12
```

修正 inotify 并完成小规模并发试跑后，可逐步增加其他组的 workers；C-notion 始终保持为 1。总并发 16–20 只是原容量建议，不是源码中的硬限制。

## 七、容器隔离风险

### 7.1 Host network

每个任务容器都使用 `--network host`。所有容器共享宿主机网络命名空间，因此：

- 临时服务端口必须全局唯一；
- 一个任务可以访问另一个任务的服务端口；
- 错误的清理命令可能停止兄弟任务的进程。

当前任务端口 `30123`、`30124`、`30137` 用途不同，没有发现五组内的直接重复，但它们仍处于同一个宿主端口空间。

### 7.2 Docker socket

Docker 模式下，每个任务容器还会挂载：

```text
/var/run/docker.sock:/var/run/docker.sock
```

因此任务容器可以访问同一个 Docker daemon。Docker socket 权限接近宿主机 root，容器之间并不是安全隔离关系。

Terminal MCP 虽未直接允许 `docker` 命令，但允许 `curl`、Python 和 shell operator，不能把命令 allowlist 当成 Docker socket 的可靠安全边界。

### 7.3 容器名称

任务容器名使用：

```text
<instance-prefix>toolathlon-<task-name>-<second-resolution-timestamp>
```

当前五组任务名互不重复，所以五组内部通常不会发生容器重名。但如果另一场实验在同一秒启动相同任务，并且复用了相同 `instance_prefix`，仍可能发生名称冲突。

### 7.4 Decoupled gateway 端口

Decoupled runner 在没有显式端口时：

1. 临时绑定 `127.0.0.1:0` 获取空闲端口；
2. 关闭 socket；
3. 稍后才启动 gateway。

步骤 2 和步骤 3 之间存在 TOCTOU 竞态。高并发时其他进程可能抢占该端口。

如果没有必须使用 host-side agent loop，五组并行时优先使用 `containerized`。

## 八、部署生命周期

`global_preparation/deploy_containers.sh` 不是无副作用的健康检查。它会：

- prune dangling volume/container/image；
- 停止并删除 Canvas、Poste、WooCommerce；
- 删除固定网络和 Kind 资源；
- 检查十个端口；
- 对非容器运行时管理的端口占用进程执行 `kill -9`；
- 重新部署并等待全部服务 ready。

因此不能在评测运行期间重新执行完整部署脚本。只运行 C-notion 时可用 `deploy_notion_containers.sh` 准备 Poste；该脚本同样会重建邮件服务，必须等待 C-local/C-notion 中使用同一 Poste 的任务结束。

正确顺序是：

```text
部署并等待全部 ready
        ↓
启动五个评测进程
        ↓
等待五组全部结束
        ↓
检查结果
        ↓
才允许下一次 deploy
```

在评测过程中 deploy 可能停止共享服务、杀掉 K8s port-forward 或任务临时 HTTP server。

## 九、三次正式评测的编排

如果五个进程分别执行：

```bash
--attempts 3
```

每个 group 内部会顺序运行三次，但五个 group 之间没有 attempt 屏障。例如：

```text
A attempt-1 完成后立即进入 A attempt-2
C-local 此时可能仍在执行 attempt-1
```

这种方式能保存三份结果。A、B、C-remote 的 attempt 可以独立推进，但 C-local 若在下一轮完整重建，会同时重置 C-notion 依赖的 Poste；共享实例时必须先协调邮件任务结束。等待本身不会重置外部 SaaS。

C 本地组如果要求每次 attempt 都重新部署 Canvas、Poste、WooCommerce 和 Kind，应显式使用：

```bash
bash scripts/run_parallel_task_list.sh \
  --deploy-before-attempt \
  --attempts 3 \
  --task-list configs/task_lists/finalpool/c-local-infrastructure-write.txt \
  results/<experiment-id> \
  <model-name> unified 2
```

该参数会在每个 attempt 前执行 `global_preparation/deploy_containers.sh`，部署失败则停止剩余 attempts。A、B、C-remote 和 C-notion 不应传入该参数；C-notion 的 Poste 需在运行前单独准备或复用完整部署的实例。

要求 attempt-N 是同步的完整 108-task 轮次，或希望完整部署期间没有其他评测运行时，可使用五组屏障；即使不要求全局同步，重建前也必须协调共享 Poste 的 C-notion 邮件任务：

```text
for attempt in 01 02 03:
    1. 在没有评测任务运行时执行 deploy_containers.sh，为 C 本地组重置基础设施
    2. 等待 Canvas、Poste、WooCommerce、Kind 全部 ready
    3. 并行启动五个单-attempt task list
    4. 等待五个进程全部结束
    5. 校验本轮 108 个任务叶子结果
    6. 确认本轮完全结束后，才进入下一轮
```

对应目录仍建议使用：

```text
results/<experiment-id>/<model>__run1/<group>/
results/<experiment-id>/<model>__run2/<group>/
results/<experiment-id>/<model>__run3/<group>/
```

当前部署脚本还会执行宿主 Docker prune，并清理固定容器和端口。`--deploy-before-attempt` 不会等待其他四个分组，且会直接停止 C-notion 使用的 Poste。该参数不提供跨组协调；共享实例时先等待相关邮件任务结束，要求完整生命周期隔离时使用上述五组屏障。

适用判断：

- C-local 要求 attempt 间重置：在外层协调共享 Poste 的任务后使用完整部署；不能让独立进程在 C-notion 邮件任务运行时自行重建。
- A、B、C-remote：直接使用 `--attempts 3`，不运行本地部署脚本。
- C-notion：先准备或检查 Poste，随后可使用 `--attempts 3`；正常重跑不必每轮重建，页面和任务邮箱由 preprocess 准备。
- 五组必须构成时间同步的完整轮次，或要求 deploy 时宿主上没有其他评测容器：使用外层 attempt 屏障。
- 只做重复采样、不要求 C 本地组重置：五组都可以直接使用 `--attempts 3`。

## 十、当前 checkout 的运行阻断项

只读环境检查结果：

- Docker `28.2.2` 可用；
- 当前没有运行中的容器；
- 默认任务镜像 `lockon0927/toolathlon-task-image:1016beta` 不存在；
- `podman` 不存在；
- host 上 `kind`、`kubectl` 不在 PATH；
- `configs/global_configs.py` 不存在；
- `configs/token_key_session.py` 不存在；
- `configs/google_credentials.json` 不存在；
- `configs/gcp-oauth.keys.json` 不存在；
- `configs/.mcp-auth` 不存在；
- `configs/port_changes.json` 不存在。

存在两个直接影响：

1. `global_configs.py` 缺失时，单任务 runner 会静默回退到 `podman`，但本机没有 podman。
2. 正常模式会无条件复制 Google credential 文件；即使 A 组任务不使用 Google，也可能因文件不存在而退出。

此外，`configs/ports_config.yaml` 当前配置了 `11001/11003/...` 目标端口，但实际部署源码仍包含 `10001/10003/...` 默认端口，且没有 `port_changes.json`。这说明目标端口配置尚未从当前 checkout 被实际 apply。

因此当前状态下不是只有五组并发存在风险，而是单组也无法完成正常启动。

## 十一、结果可靠性边界

`scripts/run_parallel_task_list.sh` 通过 `bash -o pipefail` 调用 `scripts/run_parallel.sh`，可以捕获 shell pipeline 中的 Python 非零退出。

但是，`run_parallel.py` 会把单任务 timeout/exception 转换成结果对象，并通过 `asyncio.gather(..., return_exceptions=True)` 继续执行。主函数打印失败任务后通常正常结束。

所以：

```text
group 进程退出码为 0
```

不等价于：

```text
该组所有任务都成功执行并产生有效分数
```

每轮至少检查：

```text
<dump>/<group>/finalpool/<task>/status.json
<dump>/<group>/finalpool/<task>/traj_log.json
<dump>/<group>/finalpool/<task>/eval_res.json
<dump>/<group>/eval_stats.json
```

还应确认：

- 108 个任务全部存在；
- `eval_res.json` 可解析且含有 `pass`；
- 没有 `not_executed` 或无意中的旧结果跳过；
- 五组使用相同模型、provider、配置、镜像、代码版本和 attempt；
- 聚合时没有把 `legacy_results` 中的历史文件重复计入。

## 十二、正式开跑前建议清单

1. 补齐 `global_configs.py`、`token_key_session.py`、Google credentials 和 `.mcp-auth`。
2. 明确设置 `podman_or_docker=docker`。
3. 拉取或指定实际存在的 task image，正式运行时最好记录 image digest。
4. 执行端口配置的 dry-run、apply 和 status，确认源码端口已经修改。
5. 调整 inotify 参数至仓库建议值。
6. 确认当前没有其他实验共享同一套远端测试资源。
7. C-local 要求 attempt 间重置时，先协调 C-notion 邮件任务和共享 Poste 生命周期；其他四组不传 `--deploy-before-attempt`。
8. 先以总 workers 约 12 做并发试跑，再逐步放大。
9. 监控 HTTP 429、Notion lock timeout、Docker/Kind 错误、inotify 和磁盘增长。
10. 下一次完整 deploy 前至少确认共享 Poste 的 C-notion 邮件任务结束；全局同步轮次或最保守部署隔离时等待五组全部结束。
11. 以 108 个任务叶子产物为完成标准，不只检查顶层退出码。

## 十三、最终判断

当前五组的拆分和 dump 设计已经具备并行执行的基础，已声明的四个冲突组也没有被错误拆分。

但它们仍是同一个运行实例中的五个调度进程，共享：

- 宿主网络；
- Docker daemon；
- Canvas、Poste、WooCommerce 等本地服务；
- Notion、Google、GitHub、Hugging Face 等远端账号；
- 模型 API 配额。

因此不能把当前设计描述成“五个完全隔离、可以无条件并发的实验”。更准确的结论是：

> 补齐运行环境、确认共享账号和资源的边界、降低总 workers，并协调 C-local/C-notion 共用 Poste 的生命周期后，五组可以在同一个 Toolathlon 实例中条件并行。全局 attempt 屏障用于同步轮次或完整部署隔离；默认五组各 10 workers 的配置仍需经过实际容量验证。
