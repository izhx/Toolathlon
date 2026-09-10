#!/usr/bin/env python3
"""Export explicit Markdown task data to CSV for the static HTML viewer."""

from collections import Counter
import csv
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/task-debug-progress.md"
OUTPUT = SOURCE.with_suffix(".csv")
GROUPS = {
    "A": "无网络依赖",
    "B": "网络只读",
    "C-local": "本地基础设施写",
    "C-remote": "远端写",
    "C-notion": "Notion 写",
}
STATUS_LABELS = {1: "跑通", 0: "不通", -1: "没跑"}
BLOCK_LABELS = {"yahoo": "Yahoo Finance", "google": "Google", "notion": "Notion",
                "snowflake": "Snowflake", "google-scholar": "Google Scholar"}
CSV_FIELDS = ["任务类别", "STATUS", "BLOCK", "任务", "我跑通情况",
              "lwx-env-error 描述", "task inventory 描述", "BLOCK 说明"]


def status_of(progress):
    # The user's check mark means runnable, independently of the evaluator result.
    headline = re.split(r"<br\s*/?>", progress, maxsplit=1, flags=re.I)[0]
    if "✅" in headline:
        return 1
    if not headline.strip() or "待填写" in headline:
        return -1
    return 0


def parse_blocks(cell):
    # The first line is an explicit dependency set; later lines explain evidence.
    parts = re.split(r"<br\s*/?>", cell, maxsplit=1, flags=re.I)
    labels = {label.strip() for label in parts[0].split(";")}
    if not labels <= {"0", *BLOCK_LABELS.values()} or ("0" in labels and len(labels) > 1):
        raise ValueError("BLOCK must be 0 or semicolon-separated " + ", ".join(BLOCK_LABELS.values()))
    blocks = [code for code, label in BLOCK_LABELS.items() if label in labels]
    return blocks, parts[1].strip() if len(parts) > 1 else ""


def read_rows(source=SOURCE):
    rows = []
    group = None
    seen = set()
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        heading = re.match(r"^## (A|B|C-local|C-remote|C-notion)：", line)
        if heading:
            group = heading[1]
        elif line.startswith("## "):
            group = None
        if not group or not line.startswith("| `"):
            continue
        cells = [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) != 5:
            raise ValueError(f"{source}:{number}: expected five task columns")
        task, block_cell, environment, inventory, progress = cells
        task = task.strip("`")
        if not re.fullmatch(r"[a-z0-9-]+", task) or task in seen:
            raise ValueError(f"{source}:{number}: invalid or duplicate task {task!r}")
        seen.add(task)
        status = status_of(progress)
        try:
            blocks, reason = parse_blocks(block_cell)
        except ValueError as error:
            raise ValueError(f"{source}:{number}: {task}: {error}") from error
        rows.append(dict(task=task, group=group, environment=environment,
                         inventory=inventory, progress=progress, status=status,
                         blocks=blocks, reason=reason))
    if {row["group"] for row in rows} != set(GROUPS):
        raise ValueError("Expected all five task groups in the Markdown source")
    return rows


def write_csv(rows, output=OUTPUT):
    # BOM lets spreadsheet editors recognize Chinese; csv handles commas, quotes
    # and multiline descriptions. Keep inline backticks for the HTML renderer.
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(zip(CSV_FIELDS, [
                row["group"], STATUS_LABELS[row["status"]],
                ";".join(BLOCK_LABELS[block] for block in row["blocks"]) or "0",
                row["task"],
                re.sub(r"<br\s*/?>", "\n", row["progress"], flags=re.I),
                re.sub(r"<br\s*/?>", "\n", row["environment"], flags=re.I),
                re.sub(r"<br\s*/?>", "\n", row["inventory"], flags=re.I),
                re.sub(r"<br\s*/?>", "\n", row["reason"], flags=re.I),
            ])))


def main():
    rows = read_rows()
    write_csv(rows)
    print(f"Generated {OUTPUT}: {len(rows)} tasks; "
          f"STATUS {dict(Counter(STATUS_LABELS[row['status']] for row in rows))}; "
          f"BLOCK {dict(Counter(BLOCK_LABELS[block] for row in rows for block in row['blocks']))}; "
          "HTML unchanged.")


if __name__ == "__main__":
    main()
