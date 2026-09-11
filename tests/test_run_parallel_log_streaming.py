"""Regression tests for run_parallel.run_command_async log streaming.

Background: a task run used to die with

    ERROR: Separator is not found, and chunk exceed the limit

whenever a subprocess wrote a single line longer than asyncio's 64 KiB
StreamReader limit.  This happens in practice: the npx-fetch MCP server's jsdom
dependency attaches an entire minified CSS stylesheet to its "Could not parse
CSS stylesheet" error and prints it to stderr, which the runner merges into
stdout.  The reader must therefore never assume that newlines exist.
"""

import asyncio
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# configs/global_configs.py is gitignored, and importing run_parallel pulls it in
# transitively via utils.general.helper.  These tests only exercise subprocess log
# streaming, so fall back to the checked-in example config when the real one is
# absent (fresh clone, CI, worktree).
if importlib.util.find_spec("configs.global_configs") is None:
    _example = importlib.import_module("configs.global_configs_example")
    _stub = types.ModuleType("configs.global_configs")
    _stub.global_configs = _example.global_configs
    sys.modules["configs.global_configs"] = _stub

from run_parallel import LOG_STREAM_CHUNK_SIZE, run_command_async  # noqa: E402


def python_emitting(snippet: str) -> str:
    """Build a shell command running `snippet` under the current interpreter."""
    return f"{sys.executable} -c {snippet!r}"


class RunCommandAsyncLogStreamingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temp_dir.name) / "run.log"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_command(self, command: str, timeout_seconds: int = 60) -> dict:
        return asyncio.run(
            run_command_async(
                command,
                str(self.log_file),
                timeout_seconds=timeout_seconds,
            )
        )

    def log_text(self) -> str:
        return self.log_file.read_text(encoding="utf-8")

    def test_line_far_over_stream_limit_does_not_abort_the_run(self) -> None:
        """The original vlm-history-completer failure mode."""
        # 4x the 64 KiB limit, no newline until the very end.
        payload_size = LOG_STREAM_CHUNK_SIZE * 4
        command = python_emitting(
            "import sys;"
            f"sys.stdout.write('X' * {payload_size});"
            "sys.stdout.write('\\nTRAILER\\n')"
        )

        result = self.run_command(command)

        self.assertTrue(result["success"], result)
        self.assertEqual(result["returncode"], 0)
        log = self.log_text()
        self.assertNotIn("Separator is not found", log)
        self.assertIn("X" * payload_size, log)
        self.assertIn("TRAILER", log)
        self.assertIn("Process ended with code: 0", log)

    def test_output_with_no_trailing_newline_is_fully_captured(self) -> None:
        command = python_emitting(
            "import sys; sys.stdout.write('no trailing newline here')"
        )

        result = self.run_command(command)

        self.assertTrue(result["success"], result)
        self.assertIn("no trailing newline here", self.log_text())

    def test_multibyte_characters_split_across_chunks_are_not_corrupted(self) -> None:
        # Pad with single-byte characters so that the 3-byte character lands on a
        # chunk boundary, then assert it survived reassembly.
        pad = LOG_STREAM_CHUNK_SIZE - 1
        command = python_emitting(
            "import sys;"
            f"sys.stdout.write('a' * {pad});"
            "sys.stdout.write('中文');"
            "sys.stdout.write('\\nEND\\n')"
        )

        result = self.run_command(command)

        self.assertTrue(result["success"], result)
        log = self.log_text()
        self.assertIn("中文", log)
        self.assertNotIn("�", log)
        self.assertIn("END", log)

    def test_interleaved_stderr_and_stdout_both_land_in_the_log(self) -> None:
        command = python_emitting(
            "import sys;"
            "sys.stdout.write('from-stdout\\n'); sys.stdout.flush();"
            "sys.stderr.write('from-stderr\\n'); sys.stderr.flush()"
        )

        result = self.run_command(command)

        self.assertTrue(result["success"], result)
        log = self.log_text()
        self.assertIn("from-stdout", log)
        self.assertIn("from-stderr", log)

    def test_nonzero_exit_is_reported_without_raising(self) -> None:
        command = python_emitting("import sys; sys.exit(3)")

        result = self.run_command(command)

        self.assertFalse(result["success"])
        self.assertEqual(result["returncode"], 3)
        self.assertIn("Process ended with code: 3", self.log_text())

    def test_timeout_still_kills_the_process_group(self) -> None:
        command = python_emitting("import time; time.sleep(30)")

        with self.assertRaises(TimeoutError):
            self.run_command(command, timeout_seconds=1)

        self.assertIn("TIMEOUT after 1 seconds", self.log_text())


if __name__ == "__main__":
    unittest.main()
