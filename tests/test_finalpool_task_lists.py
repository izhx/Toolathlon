import csv
import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FINALPOOL_ROOT = REPO_ROOT / "tasks" / "finalpool"
CLASSIFICATION_DOC = REPO_ROOT / "docs" / "finalpool-task-risk-classification.md"
TASK_LIST_ROOT = REPO_ROOT / "configs" / "task_lists" / "finalpool"

TASK_LISTS = {
    "a": TASK_LIST_ROOT / "a-no-network.txt",
    "b": TASK_LIST_ROOT / "b-network-read-only.txt",
    "c-local": TASK_LIST_ROOT / "c-local-infrastructure-write.txt",
    "c-remote": TASK_LIST_ROOT / "c-remote-write.txt",
    "c-notion": TASK_LIST_ROOT / "c-notion.txt",
}
LOCAL_INFRASTRUCTURE_SERVERS = {"canvas", "emails", "woocommerce", "k8s"}


def read_task_list(path: Path) -> list[str]:
    tasks = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            tasks.append(line)
    return tasks


def read_classification_section(document: str, start: str, end: str) -> set[str]:
    section = document.split(start, 1)[1].split(end, 1)[0]
    return {
        match.group(1)
        for line in section.splitlines()
        if (match := re.match(r"^\| ([a-z0-9-]+) \|", line))
    }


class FinalpoolTaskListsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.groups = {name: read_task_list(path) for name, path in TASK_LISTS.items()}
        document = CLASSIFICATION_DOC.read_text(encoding="utf-8")
        cls.classified = {
            "a": read_classification_section(document, "## A.", "## B."),
            "b": read_classification_section(document, "## B.", "## C."),
            "c": read_classification_section(document, "## C.", "## D."),
        }

    def test_lists_are_disjoint_and_cover_finalpool(self) -> None:
        seen: dict[str, str] = {}
        for group_name, tasks in self.groups.items():
            self.assertEqual(len(tasks), len(set(tasks)), f"duplicates in {group_name}")
            for task in tasks:
                self.assertNotIn(task, seen, f"{task} appears in two task lists")
                seen[task] = group_name

        finalpool_tasks = {
            path.name for path in FINALPOOL_ROOT.iterdir() if path.is_dir()
        }
        self.assertEqual(set(seen), finalpool_tasks)
        self.assertEqual(len(seen), 108)

    def test_lists_match_risk_classification_and_notion_first_split(self) -> None:
        self.assertEqual(set(self.groups["a"]), self.classified["a"])
        self.assertEqual(set(self.groups["b"]), self.classified["b"])

        expected_local = set()
        expected_notion = set()
        for task in self.classified["c"]:
            config = json.loads(
                (FINALPOOL_ROOT / task / "task_config.json").read_text(encoding="utf-8")
            )
            if "notion" in config.get("needed_mcp_servers", []):
                expected_notion.add(task)
            elif LOCAL_INFRASTRUCTURE_SERVERS.intersection(
                config.get("needed_mcp_servers", [])
            ):
                expected_local.add(task)

        self.assertEqual(set(self.groups["c-local"]), expected_local)
        self.assertEqual(set(self.groups["c-notion"]), expected_notion)
        self.assertEqual(
            set(self.groups["c-remote"]),
            self.classified["c"] - expected_local - expected_notion,
        )

    def test_five_group_sizes(self) -> None:
        self.assertEqual(
            {name: len(tasks) for name, tasks in self.groups.items()},
            {"a": 15, "b": 30, "c-local": 33, "c-remote": 22, "c-notion": 8},
        )

    def test_tracker_csv_matches_current_task_groups(self) -> None:
        with (REPO_ROOT / "docs/task-debug-progress.csv").open(
            encoding="utf-8-sig", newline=""
        ) as source:
            rows = list(csv.DictReader(source))
        expected = {
            task: name.lower() for name, tasks in self.groups.items() for task in tasks
        }
        self.assertEqual(len(rows), len(expected))
        self.assertEqual(
            {row["任务"]: row["任务类别"].lower() for row in rows}, expected
        )

    def test_declared_conflicts_do_not_cross_task_lists(self) -> None:
        task_to_group = {
            task: group_name
            for group_name, tasks in self.groups.items()
            for task in tasks
        }
        conflict_config = json.loads(
            (FINALPOOL_ROOT / "task_conflict.json").read_text(encoding="utf-8")
        )
        for conflict_group in conflict_config["conflict_groups"]:
            assigned_groups = {task_to_group[task] for task in conflict_group}
            self.assertEqual(
                len(assigned_groups),
                1,
                f"conflict group crosses task lists: {conflict_group}",
            )


if __name__ == "__main__":
    unittest.main()
