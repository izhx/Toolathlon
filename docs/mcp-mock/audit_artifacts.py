#!/usr/bin/env python3
"""Read-only checks for this design bundle; --matrix emits its CSV to stdout.

These checks verify document structure/provenance consistency, not mock fidelity.
No project modules, credentials, network clients, or benchmark code are imported.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys

OBJECTS = (
    "google-cloud", "google_calendar", "google_forms", "google_sheet", "notion",
    "snowflake", "wandb", "github", "huggingface",
)
FIELDS = (
    "object", "tool_or_capability", "version", "operation_type",
    "state_dependencies", "proposed_method", "llm_role", "fidelity_gap",
    "verification_method", "priority", "evidence",
)


def check_markdown(paths: list[Path]) -> int:
    """Check local links and table shape; do not fetch external references."""
    local_links = 0
    for path in paths:
        in_code = False
        table_width = None
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith("```"):
                in_code = not in_code
                table_width = None
                continue
            if in_code:
                continue
            if line.startswith("|"):
                width = len(re.findall(r"(?<!\\)\|", line))
                if table_width is not None and width != table_width:
                    raise ValueError(f"Markdown table width differs: {path.name}:{number}")
                table_width = width
            else:
                table_width = None
            for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", line):
                target = target.strip("<>").split("#")[0]
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                target = re.sub(r":\d+$", "", target)
                if not (path.parent / target).exists():
                    raise ValueError(f"Unresolved local link: {path.name}:{number}: {target}")
                local_links += 1
        if in_code:
            raise ValueError(f"Unclosed fenced block: {path.name}")
    return local_links


def collect(root: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    rows = []
    counts = {}
    for name in OBJECTS:
        path = root / "docs/mcp-mock/services" / f"{name}.md"
        content = path.read_text()
        if re.findall(r"^## (\d+)\.", content, re.M) != [str(i) for i in range(1, 11)]:
            raise ValueError(f"Expected ten numbered sections: {path.name}")
        if not re.search(r"^## 7\. .*LLM", content, re.M):
            raise ValueError(f"Missing LLM section: {path.name}")
        blocks = list(re.finditer(r"```csv\n(.*?)```", content, re.S))
        if len(blocks) != 1:
            raise ValueError(f"Expected one matrix block: {path.name}")
        block = blocks[0]
        reader = csv.DictReader(io.StringIO(block.group(1)))
        if reader.fieldnames != list(FIELDS):
            raise ValueError(f"Wrong matrix columns: {path.name}")
        count = 0
        for row in reader:
            if None in row or any(not value or not value.strip() for value in row.values()):
                raise ValueError(f"Empty/misaligned matrix row: {path.name}:{reader.line_num}")
            if row["object"] != name:
                raise ValueError(f"Wrong matrix object: {path.name}")
            # Link to the exact source row so shorthand evidence is resolvable.
            line = content[:block.start(1)].count("\n") + reader.line_num
            row["evidence"] = f"{path.relative_to(root)}:{line}; {row['evidence']}"
            rows.append(row)
            count += 1
        if count == 0:
            raise ValueError(f"Empty capability matrix: {path.name}")
        counts[name] = count
    keys = [(row["object"], row["tool_or_capability"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate object/capability rows")
    return rows, counts


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    bundle = root / "docs/mcp-mock"
    rows, counts = collect(root)
    if sys.argv[1:] == ["--matrix"]:
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return
    if sys.argv[1:]:
        raise ValueError("Only --matrix is supported")
    required = [root / "docs/mcp-mock.md"] + [
        bundle / name for name in (
            "shared.md", "synthesis-design.md", "validation-plan.md", "capability-matrix.csv"
        )
    ]
    for path in required:
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing/empty artifact: {path}")
    with (bundle / "capability-matrix.csv").open(newline="") as stream:
        matrix = csv.DictReader(stream)
        if matrix.fieldnames != list(FIELDS) or list(matrix) != rows:
            raise ValueError("Matrix differs from service report rows; regenerate with --matrix")
    snapshot = json.loads((bundle / "source-inventory.json").read_text())
    changed = []
    for group in ("public_source_sha256", "relevant_task_config_sha256"):
        for relative, expected in snapshot[group].items():
            path = root / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                changed.append(relative)
    if changed:
        raise ValueError(f"Source changed since static inventory: {changed}")
    memberships = {name: [] for name in OBJECTS}
    for path in sorted((root / "tasks/finalpool").glob("*/task_config.json")):
        names = json.loads(path.read_text()).get("needed_mcp_servers", [])
        for name in OBJECTS:
            if name in names:
                memberships[name].append(path.parent.name)
    if memberships != snapshot["memberships"]:
        raise ValueError("Task membership differs from source inventory")
    local_links = check_markdown([root / "docs/mcp-mock.md", *sorted(bundle.rglob("*.md"))])
    print(json.dumps({
        "result": "pass",
        "scope": "documentation structure, matrix agreement, source hashes, task membership only",
        "services": len(OBJECTS),
        "capability_rows": len(rows),
        "rows_by_service": counts,
        "source_hashes_unchanged": True,
        "local_links_checked": local_links,
        "markdown_tables_consistent": True,
        "runtime_fidelity_tested": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
