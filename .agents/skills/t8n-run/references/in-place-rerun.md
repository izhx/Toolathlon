# 原地补跑：复用当前入口

用户要求继续旧实验、原地补跑，或目标 dump 已有任务结果时读取本文件。规则对应设计时已检查的 `run_parallel.py`；执行前核对当前 checkout 的 `filter_tasks_with_existing_results`、`_archive_previous_results` 和下游 runner。不要另造一套以评分通过率决定跳过的规则。

## 预览与启动

1. 确定准确的旧 dump、TASKS_FOLDER 和本次任务集合。原始任务清单优先从该实验启动记录恢复，也可按用户要求生成子集清单；不要用“已有结果目录的任务”代替原任务全集，否则会漏掉从未开始的任务。
2. 核对真实进程，确保旧调度器、单任务 runner 和写入该目录的任务容器已经退出。残留 `running` 状态并不证明旧进程已停止。直接 `run_parallel.sh` 不加目录锁。
3. 对照原实验的模型、provider、参数文件 / eval config、镜像和代码。当前筛选函数不会核验这些身份信息。缺少历史记录时说明无法证明一致；存在变化时在审阅中说明，不把旧结果当成本次配置的全部新结果。
4. 用当前原生筛选函数的实际语义生成“将跳过 / 将执行”预览。可在确认模块导入没有副作用后调用原函数；若导入会加载无关依赖或执行全局代码，读取函数，或在隔离临时进程中仅提取所需函数进行只读预览。不能为预览直接运行主启动脚本，因为它会创建 / 覆盖文件并开始执行任务。
5. 沿用已确认的旧 dump，再运行一次 `scripts/run_parallel.sh`。无需 `--resume`，只补跑本次清单中未被原生规则跳过的任务；每个待执行任务执行一次，之后按 SKILL.md 做 handoff。

## 原生筛选顺序

先按 TASK_LIST 过滤，再读取 `<dump>/<TASKS_FOLDER>/<task>/status.json`。

| 可读取的状态 | 动作 |
| --- | --- |
| `preprocess=done`，`running=done`，`evaluation` 非 null | 跳过，包含布尔 `false` 和评分失败 |
| `preprocess=done`，`running=timeout` | 跳过 |
| `preprocess=done`，`running=max_turn_exceeded` | 跳过 |
| 其余状态，包括预处理失败、未完成、Agent fail / running、evaluation 为 null | 执行 |

可正常使用的 `status.json` 优先于其他结果文件。上述跳过分支不检查 `eval_res.json` 是否存在、内容是否有效，也不校验轨迹完整性。审阅时可指出异常，但不要擅自改变脚本的判定。

当 `status.json` 不存在或读取处理异常时，回退按以下顺序判断：

1. `run.log` 包含字面文本 `raise MaxTurnsExceeded(`：跳过。
2. `eval_res.json` 存在，且 `traj_log.json` 可以解析、其中 `status == "success"`：跳过。这里仅检查 eval 文件存在，不读取其 pass 或验证其 JSON。
3. 其余情况执行。

脚本显示的 “successful completion” 和跳过原因不完全覆盖这些分支，不能仅解析日志中的概括性文字来决定预览。

## 归档与重新执行

原生 `_archive_previous_results` 在每个待执行任务启动前处理其目录：

- 将除 `legacy_results` 外的内容移到 `legacy_results/runN/`，N 为从 1 起第一个未占用编号。
- 日志、状态、结果、工作目录和 checkpoint 都可能被移动；已有历史目录保留。
- 如果旧内容只有 `container.log`，直接删除该日志，不建立历史目录。
- 移动失败目前只记录警告，不保证整批归档原子完成；启动检查若发现这类错误，应报告具体现场。

```text
<dump>/finalpool/task-a/
├── legacy_results/
│   ├── run1/                 # 更早一次
│   └── run2/                 # 本次启动前归档的内容
├── status.json              # 本次执行产生
├── run.log
└── ...
```

待执行任务从新的任务容器和预处理开始，再运行 Agent 和 evaluation。现有并行入口没有开启 `allow_resume`，不是从旧 checkpoint 恢复，也不是仅重新评分。原地补跑本身不执行基础设施部署，部署是否需要执行仍按本次审阅决定。

## 强制重跑与统计边界

- “将失败任务写进临时清单”不会绕过完成状态过滤：评分 false、预处理完成后的 timeout / max_turn_exceeded 仍会被跳过。
- 当前入口没有 `--force` / `--rerun` 开关。若用户明确要求强制重跑这些任务，先说明哪些会被跳过和现有能力边界；不能将一次无任务执行的启动报告为已完成强制重跑。另行确定具体实现，不自动删除或篡改状态文件，也不把补跑变成 retry-until-pass。
- `<dump>/stdout.log` 启动时覆盖；其他根层聚合和 `eval_stats.json` 在后处理时重写。启动前将已有根层日志 / 统计备份放在 dump **外**的独立归档目录，记录路径，避免递归汇总再次收入备份；不搬动任务结果来代替原生归档。
- shell 的递归 `find` 汇总会包含 `legacy_results` 中的历史结果，不能把 `eval_res_all.jsonl` 的条数当成本次任务数。
- `generate_parallel_stats.py` 读取当前任务层的状态 / 结果，不递归历史，但其统计范围不按本次 TASK_LIST 过滤。同一旧 dump 用临时子集补跑后，`eval_stats.json` 可能包含该目录中其他已有任务；清单路径记录不等于统计已限定在清单范围。
- 原地补跑检查结果时使用当前任务叶子文件，结合本次“执行 / 跳过”清单区分新旧结果。
