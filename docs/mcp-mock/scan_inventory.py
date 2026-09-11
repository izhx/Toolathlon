#!/usr/bin/env python3
"""Read-only public-source inventory; never imports project configuration.

Usage: python docs/mcp-mock/scan_inventory.py [repository_root]
Writes JSON to stdout only. Does not read credential files or task token files.
This is an analysis aid, not a mock implementation or a runtime capability probe.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

OBJECTS = (
    "google-cloud", "google_calendar", "google_forms", "google_sheet", "notion",
    "snowflake", "wandb", "github", "huggingface",
)
PUBLIC_FILES = (
    "utils/mcp/tool_servers.py", "utils/roles/task_agent.py",
    "utils/openai_agents_monkey_patch/custom_mcp_util.py",
    "utils/openai_agents_monkey_patch/tool_name_aliases.py",
    "utils/data_structures/task_config.py", "global_preparation/install_env.sh",
    "package.json", "package-lock.json", "pyproject.toml", "uv.lock",
    "local_binary/github-mcp-version.txt",
)


def main() -> None:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
    tasks = sorted((root / "tasks/finalpool").glob("*/task_config.json"))
    memberships: dict[str, list[str]] = {name: [] for name in OBJECTS}
    task_hashes = {}
    for path in tasks:
        raw = path.read_bytes()
        declaration = json.loads(raw).get("needed_mcp_servers", [])
        if not isinstance(declaration, list) or any(not isinstance(x, str) for x in declaration):
            raise ValueError(f"Invalid declaration: {path.relative_to(root)}")
        for name in OBJECTS:
            if name in declaration:
                memberships[name].append(path.parent.name)
                task_hashes[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
    files = list(PUBLIC_FILES) + [f"configs/mcp_servers/{name}.yaml" for name in OBJECTS]
    files += ["configs/mcp_servers/notion_official.yaml"]
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    result = {
        "kind": "static-public-source-inventory",
        "runtime_tools_verified": False,
        "repository_commit": revision,
        "task_count": len(tasks),
        "memberships": memberships,
        "public_source_sha256": hashes,
        "relevant_task_config_sha256": task_hashes,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
