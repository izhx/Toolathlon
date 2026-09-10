#!/usr/bin/env python3
"""Calculate pass=true / selected tasks from current task results, read-only.

Examples:
    python3 scripts/calculate_pass_rate.py results/my-run
    python3 scripts/calculate_pass_rate.py results/my-run --task-list tasks.txt
    python3 scripts/calculate_pass_rate.py results/my-run/finalpool --tasks-folder .
"""

import argparse
import json
import sys
from pathlib import Path


def select_tasks(tasks_dir: Path, task_list: Path | None) -> list[str]:
    if task_list is None:
        return sorted(
            path.name for path in tasks_dir.iterdir()
            if path.is_dir() and not path.name.startswith(".")
            and path.name != "legacy_results"
        )

    names = []
    seen = set()
    for line_number, line in enumerate(
        task_list.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if name.startswith(".") or "/" in name or "\\" in name or name == "legacy_results":
            raise ValueError(f"{task_list}:{line_number}: expected a task basename: {name!r}")
        if name not in seen:
            names.append(name)
            seen.add(name)
    if not names:
        raise ValueError(f"Task list is empty: {task_list}")
    return names


def calculate_pass_rate(
    run_dir: Path, task_list: Path | None = None, tasks_folder: str = "finalpool"
) -> dict:
    folder = Path(tasks_folder)
    if folder.is_absolute() or ".." in folder.parts:
        raise ValueError("--tasks-folder must be relative to the run directory")
    tasks_dir = (run_dir / folder).resolve()
    if not tasks_dir.is_dir():
        raise ValueError(f"Task directory does not exist: {tasks_dir}")

    task_names = select_tasks(tasks_dir, task_list)
    groups = {name: [] for name in ("passed", "failed", "no_eval", "missing", "invalid")}
    errors = {}
    for name in task_names:
        task_dir = tasks_dir / name
        if not task_dir.is_dir():
            groups["missing"].append(name)
            continue

        # Read only the current leaf, never archived attempts or aggregate files.
        try:
            data = json.loads((task_dir / "eval_res.json").read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "pass" not in data:
                raise ValueError("expected a JSON object with a 'pass' field")
            passed = data["pass"]
            if passed is True:
                category = "passed"
            elif passed is False:
                category = "failed"
            elif passed is None:
                category = "no_eval"
            else:
                raise ValueError("'pass' must be true, false, or null")
        except FileNotFoundError:
            category = "no_eval"
        except (OSError, ValueError, UnicodeError) as exc:
            category = "invalid"
            errors[name] = str(exc)
        groups[category].append(name)

    total = len(task_names)
    return {
        "tasks_dir": str(tasks_dir),
        "total_tasks": total,
        "pass_rate": len(groups["passed"]) / total if total else None,
        **groups,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="Run result directory")
    parser.add_argument(
        "--task-list", type=Path,
        help="One task basename per line; ignore blank lines, # comments, and duplicates. "
             "All listed tasks count in the denominator, including missing tasks. "
             "If omitted, use all task directories; TASK_LIST is not inherited.",
    )
    parser.add_argument(
        "--tasks-folder", default="finalpool",
        help="Task subdirectory (default: finalpool); use . if run_dir directly contains tasks",
    )
    args = parser.parse_args()
    try:
        stats = calculate_pass_rate(args.run_dir, args.task_list, args.tasks_folder)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))

    print(f"Task directory: {stats['tasks_dir']}")
    print(f"Task list: {args.task_list or '(all task directories)'}")
    print(f"Total tasks: {stats['total_tasks']}")
    for category, label in (
        ("passed", "Passed"), ("failed", "Failed"),
        ("no_eval", "No evaluation (missing file or pass=null)"),
        ("missing", "Missing task directories"), ("invalid", "Invalid results"),
    ):
        print(f"{label}: {len(stats[category])}")
        for name in stats[category]:
            print(f"  - {name}")
    if stats["pass_rate"] is None:
        print("Pass rate: N/A (no tasks)")
    else:
        print(f"Pass rate: {len(stats['passed'])}/{stats['total_tasks']} = {stats['pass_rate']:.2%}")
    for name, error in stats["errors"].items():
        print(f"Warning: {name}/eval_res.json: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
