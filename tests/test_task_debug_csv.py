import csv
from pathlib import Path
import tempfile
import unittest

from scripts import generate_task_debug_csv as exporter


ROOT = Path(__file__).resolve().parents[1]


class TaskDebugCSVTest(unittest.TestCase):
    def test_explicit_dependencies_survive_all_runnable_states(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "tracker.md"
            source.write_text("\n".join([
                "## A：无网络依赖",
                '| `passed` | Notion;Yahoo Finance;Google;Google<br>保留说明，含 "引号"<br>后续待核 | — | 历史 | ✅ FAIL |',
                "## B：网络只读",
                "| `failed` | Yahoo Finance;Google;Notion | — | 历史 | ❌ FAIL |",
                "## C-local：本地基础设施写",
                "| `pending` | Yahoo Finance;Google;Notion | — | 历史 | ⬜ 待填写 |",
                "## C-remote：远端写",
                "| `unlabeled` | 0 | Yahoo Finance 429 | 历史 Google 问题 | Notion 字样不自动打标签 |",
                "## C-notion：Notion 写",
                "| `notion-task` | Notion | — | 历史 | ✅ NO_EVAL |",
            ]), encoding="utf-8")
            output = Path(directory) / "tracker.csv"
            exporter.write_csv(exporter.read_rows(source), output)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                rows = {row["任务"]: row for row in csv.DictReader(stream)}

        for task, status in (("passed", "跑通"), ("failed", "不通"), ("pending", "没跑")):
            with self.subTest(task=task):
                self.assertEqual(rows[task]["STATUS"], status)
                self.assertEqual(rows[task]["BLOCK"], "Yahoo Finance;Google;Notion")
        self.assertEqual(rows["passed"]["BLOCK 说明"], '保留说明，含 "引号"\n后续待核')
        self.assertEqual(rows["unlabeled"]["BLOCK"], "0")
        self.assertEqual(rows["notion-task"]["BLOCK"], "Notion")
        self.assertEqual(rows["notion-task"]["STATUS"], "跑通")

    def test_invalid_labels_fail_with_source_location(self):
        for value in ("", "Google;", "0;Notion", "Yahoo Finance 429", "Unknown"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "tracker.md"
                source.write_text(
                    f"## A：无网络依赖\n| `invalid` | {value} | — | — | ✅ PASS |\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, r"tracker\.md:2: invalid: BLOCK"):
                    exporter.read_rows(source)

    def test_known_cross_service_and_preprocessing_dependencies(self):
        rows = {row["task"]: row for row in exporter.read_rows()}
        expected = {
            "quantitative-financial-analysis": ["yahoo", "google", "notion"],
            "investment-decision-analysis": ["yahoo", "google"],
            "oil-price": ["yahoo", "notion"],
            "notion-find-job": ["google", "notion"],
            "fillout-online-forms": ["google"],
            "ipad-edu-price": ["yahoo"],
            "shopping-helper": [],
        }
        for task, blocks in expected.items():
            with self.subTest(task=task):
                self.assertEqual(rows[task]["blocks"], blocks)
        self.assertEqual(rows["ipad-edu-price"]["status"], 1)

    def test_csv_is_current_and_export_keeps_html_unchanged(self):
        html = ROOT / "docs/task-debug-progress.html"
        before = (html.read_bytes(), html.stat().st_mtime_ns)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tracker.csv"
            exporter.write_csv(exporter.read_rows(), output)
            self.assertEqual(output.read_bytes(), exporter.OUTPUT.read_bytes())
        self.assertEqual((html.read_bytes(), html.stat().st_mtime_ns), before)

    def test_unlabeled_c_local_export_matches_tracker(self):
        expected = {
            row["task"] for row in exporter.read_rows()
            if row["group"] == "C-local" and not row["blocks"]
        }
        actual = {
            line.strip() for line in (ROOT / "configs/task_lists/finalpool/tmp-c-local.txt").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
