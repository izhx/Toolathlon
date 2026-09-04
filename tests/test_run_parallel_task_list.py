import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_parallel_task_list.sh"


class RunParallelTaskListTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.task_list = self.root / "a-no-network.txt"
        self.task_list.write_text("example-task\n", encoding="utf-8")
        self.c_local_task_list = self.root / "c-local-infrastructure-write.txt"
        self.c_local_task_list.write_text("example-task\n", encoding="utf-8")
        self.capture_file = self.root / "calls.txt"

        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        fake_bash = fake_bin / "bash"
        fake_bash.write_text(
            "#!/bin/bash\n"
            "if [ \"$1\" = \"global_preparation/deploy_containers.sh\" ]; then\n"
            "  printf 'deploy|%s\\n' \"$*\" >> \"$CAPTURE_FILE\"\n"
            "  if [ \"${FAIL_DEPLOY:-}\" = \"1\" ]; then exit 17; fi\n"
            "  exit 0\n"
            "fi\n"
            "printf 'run|%s|%s|%s\\n' \"$TASK_LIST\" \"$TASKS_FOLDER\" \"$*\" >> \"$CAPTURE_FILE\"\n",
            encoding="utf-8",
        )
        fake_bash.chmod(0o755)

        self.env = os.environ.copy()
        self.env["PATH"] = f"{fake_bin}:{self.env['PATH']}"
        self.env["CAPTURE_FILE"] = str(self.capture_file)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_wrapper(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/bash", str(SCRIPT), *arguments],
            cwd=REPO_ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def captured_calls(self) -> list[str]:
        if not self.capture_file.exists():
            return []
        return self.capture_file.read_text(encoding="utf-8").splitlines()

    def test_three_attempts_use_model_run_dump_paths(self) -> None:
        dump_root = self.root / "results"
        model_name = "anthropic/claude-sonnet-4.5"

        result = self.run_wrapper(
            "--attempts",
            "3",
            "--task-list",
            str(self.task_list),
            str(dump_root),
            model_name,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.captured_calls()
        self.assertEqual(len(calls), 3)
        for attempt, call in enumerate(calls, start=1):
            expected_dump = (
                dump_root
                / f"anthropic_claude-sonnet-4.5__run{attempt}"
                / "a-no-network"
            )
            self.assertIn(f" {expected_dump} ", call)
            self.assertTrue(
                call.startswith(f"run|{self.task_list}|finalpool|-o pipefail ")
            )

    def test_default_keeps_exact_dump_path(self) -> None:
        dump_path = self.root / "single-run"

        result = self.run_wrapper(
            "--task-list",
            str(self.task_list),
            str(dump_path),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.captured_calls()
        self.assertEqual(len(calls), 1)
        self.assertIn(f" {dump_path} ", calls[0])
        self.assertNotIn("__run1", calls[0])

    def test_deploy_before_each_attempt_runs_before_task_list(self) -> None:
        dump_root = self.root / "results"

        result = self.run_wrapper(
            "--deploy-before-attempt",
            "--attempts",
            "3",
            "--task-list",
            str(self.c_local_task_list),
            str(dump_root),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.captured_calls()
        self.assertEqual(len(calls), 6)
        for attempt in range(1, 4):
            deploy_call = calls[(attempt - 1) * 2]
            run_call = calls[(attempt - 1) * 2 + 1]
            self.assertEqual(
                deploy_call,
                "deploy|global_preparation/deploy_containers.sh",
            )
            expected_dump = (
                dump_root
                / f"glm-5.2__run{attempt}"
                / "c-local-infrastructure-write"
            )
            self.assertIn(f" {expected_dump} ", run_call)

    def test_c_local_does_not_deploy_without_explicit_option(self) -> None:
        result = self.run_wrapper(
            "--task-list",
            self.c_local_task_list,
            self.root / "single-run",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.captured_calls()
        self.assertEqual(len(calls), 1)
        self.assertTrue(
            calls[0].startswith(f"run|{self.c_local_task_list}|finalpool|")
        )

    def test_deploy_failure_stops_before_task_execution(self) -> None:
        self.env["FAIL_DEPLOY"] = "1"

        result = self.run_wrapper(
            "--deploy-before-attempt",
            "--attempts",
            "3",
            "--task-list",
            str(self.c_local_task_list),
            str(self.root / "results"),
        )

        self.assertEqual(result.returncode, 17)
        self.assertEqual(
            self.captured_calls(),
            ["deploy|global_preparation/deploy_containers.sh"],
        )

    def test_attempts_must_be_positive_integer(self) -> None:
        result = self.run_wrapper(
            "--attempts",
            "0",
            str(self.root / "results"),
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("must be a positive integer", result.stderr)
        self.assertEqual(self.captured_calls(), [])

    def test_omitted_task_list_runs_all_tasks(self) -> None:
        dump_path = self.root / "all-task-results"

        result = self.run_wrapper(str(dump_path))

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.captured_calls()
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith("run||finalpool|-o pipefail "))
        self.assertIn(f" {dump_path} ", calls[0])
        self.assertIn("Task list: all tasks (tasks/finalpool)", result.stdout)

    def test_omitted_task_list_clears_inherited_filter(self) -> None:
        self.env["TASK_LIST"] = str(self.task_list)

        result = self.run_wrapper(str(self.root / "all-task-results"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            self.captured_calls()[0].startswith("run||finalpool|-o pipefail ")
        )

    def test_all_tasks_multi_attempt_layout_has_no_group_layer(self) -> None:
        dump_root = self.root / "results"

        result = self.run_wrapper(
            "--attempts",
            "3",
            str(dump_root),
            "test/model",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.captured_calls()
        self.assertEqual(len(calls), 3)
        for attempt, call in enumerate(calls, start=1):
            expected_dump = dump_root / f"test_model__run{attempt}"
            self.assertIn(f" {expected_dump} ", call)
            self.assertNotIn(f"{expected_dump}/all-tasks", call)
            self.assertTrue(call.startswith("run||finalpool|-o pipefail "))

    def test_legacy_positional_task_list_is_rejected(self) -> None:
        result = self.run_wrapper(
            str(self.task_list),
            str(self.root / "results"),
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("use --task-list <file>", result.stderr)
        self.assertEqual(self.captured_calls(), [])

    def test_task_list_option_requires_a_value(self) -> None:
        result = self.run_wrapper("--task-list")

        self.assertEqual(result.returncode, 2)
        self.assertIn("--task-list requires a file path", result.stderr)
        self.assertEqual(self.captured_calls(), [])

    def test_named_task_list_must_exist(self) -> None:
        missing_task_list = self.root / "missing.txt"

        result = self.run_wrapper(
            "--task-list",
            str(missing_task_list),
            str(self.root / "results"),
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("task-list file does not exist", result.stderr)
        self.assertEqual(self.captured_calls(), [])

    def test_dump_path_is_still_required(self) -> None:
        result = self.run_wrapper()

        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)
        self.assertEqual(self.captured_calls(), [])

    def test_tasks_folder_is_passed_to_runner(self) -> None:
        custom_tasks_dir = tempfile.TemporaryDirectory(
            dir=REPO_ROOT / "tasks",
            prefix="test-run-parallel-task-list-",
        )
        self.addCleanup(custom_tasks_dir.cleanup)
        tasks_folder_name = Path(custom_tasks_dir.name).name

        result = self.run_wrapper(
            "--tasks-folder",
            tasks_folder_name,
            str(self.root / "results"),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            self.captured_calls()[0].startswith(
                f"run||{tasks_folder_name}|-o pipefail "
            )
        )
        self.assertIn(f"Tasks folder: tasks/{tasks_folder_name}", result.stdout)

    def test_tasks_folder_must_exist(self) -> None:
        result = self.run_wrapper(
            "--tasks-folder",
            "does-not-exist",
            str(self.root / "results"),
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("tasks folder does not exist", result.stderr)
        self.assertEqual(self.captured_calls(), [])

    def test_tasks_folder_cannot_escape_tasks_root(self) -> None:
        result = self.run_wrapper(
            "--tasks-folder",
            "..",
            str(self.root / "results"),
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("must stay under", result.stderr)
        self.assertEqual(self.captured_calls(), [])


if __name__ == "__main__":
    unittest.main()
