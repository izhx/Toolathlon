# run.log 流式读取的 64 KiB 单行上限缺陷

- 定位日期：2026-09-11
- 触发任务：`finalpool/vlm-history-completer`（dsv4 实跑，run `deepseek-v4-flash-0731`/260910）
- 症状：`run.log` 末尾出现 `ERROR: Separator is not found, and chunk exceed the limit`，任务被判失败，`status.json` 中 `evaluation` 为 `null`
- 结论：**既不是网络问题，也不是 `playwright_with_chunk` 分块器缺陷，而是 `run_parallel.py` 自身的日志读取缺陷**
- 修复状态：✅ 已修复并验证（见第 5、6 节）

## 1. 原始归因错在哪

`docs/task-debug-progress.md` 原先记为：

> `playwright_with_chunk` 分块器崩溃：`Separator is not found, and chunk exceed the limit`（jsdom/parse5）；两次独立运行同点复现……根因=工具链缺陷

这条归因有两处错误：

1. **组件认错了。** 报错里的 jsdom/parse5 栈来自 `@tokenizin/mcp-npx-fetch`，它依赖 `jsdom@^25`。而 `@lockon0927/playwright-mcp-with-chunk@0.1.2` 的依赖只有 playwright、ws、commander、mime 等，**完全不含 jsdom**。分块器全程没有崩。
2. **层次认错了。** `Separator is not found, and chunk exceed the limit` 这句话根本不是 Node 生态的错误，而是 CPython 标准库 `asyncio` 抛出的（`/usr/local/lib/python3.12/asyncio/streams.py:647`）。它是 harness 读日志时炸的，不是 MCP 工具本身有缺陷。

两者被混在同一段日志里，只因为容器的 stdout/stderr 是合流的。

## 2. 完整因果链

1. Agent 调用 `npx-fetch` MCP 抓网页（`fetch_fetch_markdown` 等）。

2. jsdom 解析含现代 CSS 的页面（Squarespace 那类，`--grid-gutter: calc(var(--sqs-mobile-site-gutter, 6vw) - 15.0px)`）时，其内置的老 `cssom` 解析器失败，走进 `node_modules/jsdom/lib/jsdom/living/helpers/stylesheets.js:37` 的 catch 分支：

   ```js
   const error = new Error("Could not parse CSS stylesheet");
   error.detail = sheetText;   // ← 把整张样式表原文挂进 error
   error.type = "css parsing";
   elementImpl._ownerDocument._defaultView._virtualConsole.emit("jsdomError", error);
   ```

   关键在 `error.detail = sheetText`：**整张压缩样式表被塞进 error 对象**，再由默认 virtualConsole 打到 stderr。压缩后的 CSS 没有换行。

3. MCP Python SDK 的 `stdio_client` 默认 `errlog=sys.stderr`（`mcp/client/stdio/__init__.py:97`），MCP server 的 stderr 直通父进程。

4. `scripts/run_single_containerized.sh` 在 `parent_captures_run_log=1` 模式下，把容器 exec 的 stdout/stderr 交给 `run_parallel.py`；后者又用 `stderr=subprocess.STDOUT` 合流。于是 agent 的正常输出和 jsdom 的 CSS dump 挤在同一个字节流里——日志里能直接看到粘连的证据，中间没有换行：

   ```
   Let me do fetches in batches.Error: Could not parse CSS stylesheet
   ```

5. `run_parallel.py` 的 `write_output()` 用 `await process.stdout.readline()` 读这个流。asyncio 的 `StreamReader` 默认上限 `_DEFAULT_LIMIT = 2 ** 16`（64 KiB）。当那坨无换行的 CSS 使单"行"超过 64 KiB 时，`readuntil()` 抛 `LimitOverrunError`，`readline()` 把它转成 `ValueError('Separator is not found, and chunk exceed the limit')`。

6. 该异常冒泡到 `run_parallel.py` 的 `except Exception`，写下那行 ERROR 后 `raise`，**整个任务进程被判失败**。

## 3. 为什么两次独立运行都在同一点复现

因为它是确定性的，与网络无关：同一批 URL、同一份 CSS、同一个 64 KiB 上限。

`legacy_results/run1/run.log` 和 `run.log` 都在最后一次 jsdom dump 后立刻出现该 ERROR，且两份日志都**没有** `Process ended with code:` 这一行——说明进程不是正常收尾，而是被读取异常掐断。`status.json` 两次都是：

```json
{"preprocess": "done", "running": "done", "evaluation": null}
```

即 `run_single_containerized.sh` 还没走到 Step 3.5（评测阶段）就被中断了。

## 4. Agent 其实已经完成任务

这是本缺陷最大的代价：**丢掉的是一次本该有效的实验数据**。`traj_log.json` 显示：

- `status: "success"`，90 次工具调用，39 次 LLM 请求
- 最后几条消息确认 Google Sheet 的 `'Text and Image'!K2:L21` 已写入（`updatedCells: 40`），且 agent 回读校验通过
- Architecture 与 Sources 两列 20 行数据均已填好

日志里另有两处 `get_sheet_data` 60s 超时和一次 big_vision 的 429，属真实网络噪声，但都不致命，agent 均已绕过。**任务是被日志管道杀掉的，不是被任务本身或网络杀掉的。**

## 5. 修复

`run_parallel.py`：把日志读取从"按行"改为"按块"，不再假设输出里存在换行。

```python
LOG_STREAM_CHUNK_SIZE = 65536

async def write_output():
    decoder = codecs.getincrementaldecoder('utf-8')(errors='ignore')
    while True:
        chunk = await process.stdout.read(LOG_STREAM_CHUNK_SIZE)
        if not chunk:
            break
        text = decoder.decode(chunk)
        if text:
            f.write(text)
            f.flush()
    tail = decoder.decode(b'', final=True)
    if tail:
        f.write(tail)
        f.flush()
```

两个要点：

- `StreamReader.read(n)` 不查找分隔符，因此**不受 64 KiB 上限约束**，任意长的无换行输出都能安全落盘。这比单纯调大 `limit=` 更彻底：调大上限只是把阈值推高，仍会被更大的 dump 击穿。
- 用 `codecs` 增量解码器替代逐块 `bytes.decode()`。分块边界可能切断多字节 UTF-8 序列，增量解码器会把不完整序列留到下一块，避免中文等字符被 `errors='ignore'` 吞掉。

这个修复是通用的：任何 MCP server 吐出超长单行都不会再拖垮任务，不止 jsdom 这一种触发源。

## 6. 测试与验证

新增 `tests/test_run_parallel_log_streaming.py`，6 个用例覆盖：

| 用例 | 覆盖点 |
| --- | --- |
| `test_line_far_over_stream_limit_does_not_abort_the_run` | 原始故障模式：4×64 KiB 无换行单行 |
| `test_output_with_no_trailing_newline_is_fully_captured` | 输出末尾无换行时不丢数据 |
| `test_multibyte_characters_split_across_chunks_are_not_corrupted` | 多字节字符跨块边界不损坏 |
| `test_interleaved_stderr_and_stdout_both_land_in_the_log` | stdout/stderr 合流均落盘 |
| `test_nonzero_exit_is_reported_without_raising` | 非零退出码正常上报 |
| `test_timeout_still_kills_the_process_group` | 超时仍能杀掉进程组（未回退原有行为） |

**双向验证**（关键：确认测试真的能抓住这个 bug，而不是恰好通过）：

- 在修复后的代码上：6/6 通过。
- 把 `write_output()` 临时改回 `readline()` 版本后重跑：`test_line_far_over_stream_limit_does_not_abort_the_run` 与 `test_multibyte_characters_split_across_chunks_are_not_corrupted` 失败，报出的正是生产环境那句 `Separator is not found, and chunk exceed the limit`。

此外用一个复刻脚本做端到端回放：构造 209 KiB 无换行的压缩样式表 + jsdom 风格 `Could not parse CSS stylesheet` 栈，走真实的 `run_command_async`。修复后 7 项检查全过（900 条 CSS 规则完整落盘、dump 之后的输出存活、后续阶段可达、退出码正常记录）；修复前同一脚本以生产同款错误崩溃。

回归情况：`tests/test_run_parallel_task_list.py`(16)、`tests/test_finalpool_task_lists.py`(5)、`tests/test_task_debug_csv.py`(5) 均通过，`run_parallel.py --help` 正常。

注：`configs/global_configs.py` 被 gitignore，而导入 `run_parallel` 会传递性地拉入它。新测试在该文件缺失时回退到仓库自带的 `configs/global_configs_example.py`，以便在全新 clone / CI / worktree 中也能运行。

## 7. 尚未处理的后续项

以下两项超出本次修复范围，单独记录：

1. **`except Exception` 会吃掉整个任务结果。** `run_parallel.py` 中日志管道的故障和任务本身的故障共用一个异常出口。即使本缺陷已修，其他管道级异常仍会阻止评测阶段执行。建议把这类故障降级为"记录但不中断评测"。
2. **`npx-fetch` 的 CSS dump 噪声仍在。** 给它配置静音的 virtualConsole 可从源头掐掉 dump。属治标，但能显著减小 `run.log` 体积（本例中单次 dump 就是 209 KiB 量级）。

另需修正 `docs/task-debug-progress.md` 中 `vlm-history-completer` 一行的归因（已在本次一并更新）。
