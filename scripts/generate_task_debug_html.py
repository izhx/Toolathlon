#!/usr/bin/env python3
"""Export Markdown to docs/task-debug-progress.csv; the static HTML loads this CSV.

The existing command name is retained for compatibility. It never writes HTML.
"""

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
BLOCK_LABELS = {"yahoo": "Yahoo Finance 429", "notion": "Notion", "google": "Google"}
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


def blocks_of(task, status, progress, inventory):
    if status == 1:
        return [], ""
    if status == -1:
        # Keep historical known blockers visible without claiming a personal run.
        blocks = []
        reasons = []
        if "已知阻塞：Notion" in inventory:
            blocks.append("notion")
            reasons.append("历史已知阻塞；个人尚未实跑")
        if "已知阻塞：Google" in inventory:
            blocks.append("google")
            reasons.append("历史已知阻塞；个人尚未实跑")
        elif "Google 配置待核：" in inventory:
            blocks.append("google")
            reasons.append("Google 依赖配置待核；个人尚未实跑，未确认凭据缺失")
        return blocks, "；".join(dict.fromkeys(reasons))

    blocks = []
    if re.search(r"Yahoo Finance.*(?:429|Rate limited|Too Many Requests)", progress, re.I):
        blocks.append("yahoo")
    if "Notion" in progress or "duplicated_page_id.txt" in progress:
        blocks.append("notion")
    if re.search(r"Google|GCP|gcp-service_account|DefaultCredentialsError", progress, re.I):
        blocks.append("google")
    reason = "本次记录中的服务／凭据阻塞" if blocks else ""
    if "当前阻塞：Google Maps API 尚未配置" in progress:
        reason = "Google Maps API 尚未配置（人工标注）"

    # These preprocessing scripts call get_google_service(), whose first credential
    # lookup is cred_data['token'] in utils/app_specific/googlesheet/drive_helper.py.
    # quantitative-financial-analysis also depends on Notion, initialized after
    # Google. BLOCK records the observed failure; full dependencies are in inventory.
    google_token_tasks = {
        "gdp-cr5-analysis", "inter-final-performance-analysis", "llm-training-dataset",
        "music-analysis", "nhl-b2b-analysis", "quantitative-financial-analysis",
        "vlm-history-completer",
    }
    if task in google_token_tasks and "KeyError" in progress and "token" in progress:
        blocks.append("google")
        reason = "Google 凭据缺 token；已核对预处理代码"
    if task == "upenn-campus-route" and "Failed to get walking time" in progress:
        blocks.append("google")
        reason = "评测器调用 Google Maps 失败；具体原因待核"
    if task == "notion-personal-website" and "preprocess 卡住" in progress:
        blocks.append("notion")
        reason = "Notion 预处理卡住；具体原因待核"
    if task == "investment-decision-analysis" and "returncode 1" in progress:
        blocks.append("google")
        reason = "按 Google Sheets/Drive 预处理暂归类；本次仅有 returncode 1，待核"
    return list(dict.fromkeys(blocks)), reason


def read_rows():
    rows = []
    group = None
    seen = set()
    for number, line in enumerate(SOURCE.read_text(encoding="utf-8").splitlines(), 1):
        heading = re.match(r"^## (A|B|C-local|C-remote|C-notion)：", line)
        if heading:
            group = heading[1]
        elif line.startswith("## "):
            group = None
        if not group or not line.startswith("| `"):
            continue
        cells = [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) != 4:
            raise ValueError(f"{SOURCE}:{number}: expected four task columns")
        task, environment, inventory, progress = cells
        task = task.strip("`")
        if not re.fullmatch(r"[a-z0-9-]+", task) or task in seen:
            raise ValueError(f"{SOURCE}:{number}: invalid or duplicate task {task!r}")
        seen.add(task)
        status = status_of(progress)
        blocks, reason = blocks_of(task, status, progress, inventory)
        rows.append(dict(task=task, group=group, environment=environment,
                         inventory=inventory, progress=progress, status=status,
                         blocks=blocks, reason=reason))
    if {row["group"] for row in rows} != set(GROUPS):
        raise ValueError("Expected all five task groups in the Markdown source")
    return rows


def main():
    rows = read_rows()
    # BOM lets spreadsheet editors recognize Chinese; csv handles commas, quotes
    # and multiline descriptions. Keep inline backticks for the HTML renderer.
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(zip(CSV_FIELDS, [
                row["group"], STATUS_LABELS[row["status"]],
                ";".join(BLOCK_LABELS[block] for block in row["blocks"]) or "0",
                row["task"],
                re.sub(r"<br\s*/?>", "\n", row["progress"], flags=re.I),
                re.sub(r"<br\s*/?>", "\n", row["environment"], flags=re.I),
                re.sub(r"<br\s*/?>", "\n", row["inventory"], flags=re.I),
                row["reason"],
            ])))
    print(f"Generated {OUTPUT}: {len(rows)} tasks; "
          f"STATUS {dict(Counter(STATUS_LABELS[row['status']] for row in rows))}; "
          "HTML unchanged.")


if __name__ == "__main__":
    main()
