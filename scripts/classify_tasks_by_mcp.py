#!/usr/bin/env python3
"""按声明的 MCP 依赖生成四份互斥任务清单。

只扫描 TASK_DIR/*/task_config.json，按任务目录名排序，每行输出一个任务名。
terminal 作为通用执行工具忽略，其余 MCP 按以下优先级分类：
1. 含白名单之外的 MCP；2. 含本地服务容器 MCP；
3. 含公网只读 MCP；4. 仅本地处理 MCP（也包括空列表或只有 terminal）。

分类不检查 needed_local_tools、预处理或评估，也不保证终端命令离线或只读。
重复运行会覆盖 TASK_DIR 中的四个同名 txt 文件，空分类也会生成空文件。
"""

import argparse
import json
from pathlib import Path


GENERAL_MCPS = {"terminal"}
LOCAL_CONTAINER_MCPS = {"canvas", "emails", "k8s", "woocommerce"}
LOCAL_FILE_MCPS = {"excel", "filesystem", "git", "memory", "pptx", "word"}
PUBLIC_READONLY_MCPS = {
    "arxiv-latex",
    "arxiv_local",
    "fetch",
    "google_map",
    "howtocook",
    "pdf-tools",
    "rail_12306",
    "scholarly",
    "youtube",
    "youtube-transcript",
}
# 严格使用约定的 20 项；yahoo-finance 等未列出的名称属于第一类。
KNOWN_MCPS = LOCAL_CONTAINER_MCPS | LOCAL_FILE_MCPS | PUBLIC_READONLY_MCPS

OUTPUT_FILES = {
    "other": "1-other-mcp.txt",
    "container": "2-local-container.txt",
    "public": "3-public-readonly.txt",
    "local": "4-local-tools.txt",
}


def classify(mcp_names: list[str]) -> str:
    """忽略通用工具后，首次命中的规则决定任务类别。"""
    names = set(mcp_names) - GENERAL_MCPS
    if names - KNOWN_MCPS:
        return "other"
    if names & LOCAL_CONTAINER_MCPS:
        return "container"
    if names & PUBLIC_READONLY_MCPS:
        return "public"
    return "local"


def collect_tasks(task_dir: Path) -> dict[str, list[str]]:
    """先读取并验证所有配置，避免配置错误时覆盖已有清单。"""
    if not task_dir.is_dir():
        raise ValueError(f"任务目录不存在或不是目录: {task_dir}")

    config_paths = sorted(task_dir.glob("*/task_config.json"))
    if not config_paths:
        raise ValueError(f"未找到任务配置: {task_dir}/*/task_config.json")

    groups: dict[str, list[str]] = {group: [] for group in OUTPUT_FILES}
    for config_path in config_paths:
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"无法读取任务配置 {config_path}: {exc}") from exc

        if not isinstance(config, dict):
            raise ValueError(f"{config_path}: 配置必须是 JSON 对象")
        names = config.get("needed_mcp_servers")
        if not isinstance(names, list) or any(
            not isinstance(name, str) or not name.strip() for name in names
        ):
            raise ValueError(
                f"{config_path}: needed_mcp_servers 必须是列表，元素必须是非空字符串"
            )
        groups[classify(names)].append(config_path.parent.name)

    return groups


def main() -> None:
    parser = argparse.ArgumentParser(
        description="按 MCP 依赖分类任务，在指定目录生成四份 txt 清单。",
        epilog=(
            "terminal 不参与分类；严格使用固定的 20 项 MCP 白名单。"
            "只扫描直接子目录的 task_config.json；重复运行会覆盖四份清单。"
        ),
    )
    parser.add_argument(
        "task_dir", type=Path, help="任务集合目录，例如 tasks/finalpool"
    )
    args = parser.parse_args()

    try:
        task_dir = args.task_dir.expanduser().resolve()
        groups = collect_tasks(task_dir)
        for group, filename in OUTPUT_FILES.items():
            output_path = task_dir / filename
            tasks = groups[group]
            output_path.write_text(
                "".join(f"{task}\n" for task in tasks), encoding="utf-8"
            )
            print(f"{output_path}: {len(tasks)} 个任务")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    print(f"合计: {sum(len(tasks) for tasks in groups.values())} 个任务")


if __name__ == "__main__":
    main()
