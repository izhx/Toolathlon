#!/usr/bin/env python3
"""Manage the notion_official OAuth grant: check whether it works, and import one
completed on another machine.

Why this exists
---------------
The Notion preprocess step duplicates pages through the ``notion_official`` MCP
server, which authenticates with an OAuth grant that ``mcp-remote`` keeps on
disk. Two things about that storage have each broken every Notion task at least
once, and neither surfaces as a readable error -- tasks just hang until the
outer preprocess timeout, because the MCP call path has no timeout of its own
and preprocess output is buffered until the process exits.

1. The config directory is named after mcp-remote's own version:

     <= 0.3.1  ->  .mcp-auth/mcp-remote-<version>/   (this repo pins 0.1.16,
                   so .mcp-auth/mcp-remote-0.1.16/)
     >= 0.3.2  ->  .mcp-auth/mcp-remote-v1/          (fixed name, no longer
                   tied to the package version)

   Authorizing on a machine with a current mcp-remote drops the grant in
   ``mcp-remote-v1/``, while task containers run the version pinned in
   ``configs/mcp_servers/notion_official.yaml`` and read
   ``mcp-remote-0.1.16/``. The grant is fine, it is just in a directory nothing
   reads -- so mcp-remote starts a fresh browser authorization that can never
   complete in a headless container.

2. A grant on the wrong Notion workspace connects and refreshes perfectly well,
   then 404s on every page the tasks need. Authentication is not the same
   question as access.

The credential filename is ``md5(<server url>)``, identical on every machine, so
a directory copied from another host needs no renaming.

Commands
--------
    # is the grant on disk usable? (safe, read-only)
    uv run python global_preparation/notion_official_auth.py verify

    # import a grant from a mcp-remote-v1 dir, then verify it
    uv run python global_preparation/notion_official_auth.py fix --from /path/to/mcp-remote-v1

    # import only, no verification
    uv run python global_preparation/notion_official_auth.py import --from /path/to/mcp-remote-v1

    # show what an import would do, without writing
    uv run python global_preparation/notion_official_auth.py import --dry-run

``--from`` defaults to this repo's own ``.mcp-auth/mcp-remote-v1``, which is
where authorizing on this machine with a current mcp-remote lands.

Exits non-zero if a verification check fails or an import cannot proceed.
"""
import argparse
import datetime
import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

AUTH_DIR = REPO_ROOT / "configs" / ".mcp-auth"
YAML_PATH = REPO_ROOT / "configs" / "mcp_servers" / "notion_official.yaml"

# Files that make up a usable grant. Both are required: tokens.json's
# refresh_token is bound to the client_id that issued it, and that client_id
# lives in client_info.json. Copying only tokens.json leaves the refresh_token
# in a directory whose client_id differs, and Notion rejects the refresh.
NEEDED = ("client_info.json", "tokens.json")
# Leftovers from an in-flight browser flow. Carrying these over would make
# mcp-remote believe it still has a pending authorization to finish.
STALE = ("code_verifier.txt", "lock.json")

# The release where mcp-remote switched to the fixed `mcp-remote-v1` name.
FIXED_DIR_SINCE = (0, 3, 2)

# same default as scripts/run_single_containerized.sh
TASK_IMAGE = "lockon0927/toolathlon-task-image:1016beta"
CALL_TIMEOUT_SECONDS = 60


# --------------------------------------------------------------------------
# shared: what the yaml says the containers will do
# --------------------------------------------------------------------------

def read_yaml_config():
    """Server URL, pinned mcp-remote version, npx args and config dir, read from
    the yaml so this script keeps working if any of them is changed there."""
    cfg = yaml.safe_load(YAML_PATH.read_text())
    args = cfg["params"]["args"]
    spec = args[0]                      # e.g. "mcp-remote@0.1.16" or "mcp-remote"
    url = next(a for a in args if a.startswith("http"))
    version = spec.split("@", 1)[1] if "@" in spec else None
    config_dir = (cfg["params"].get("env") or {}).get(
        "MCP_REMOTE_CONFIG_DIR", "./configs/.mcp-auth")
    return url, version, args, config_dir


def version_tuple(v):
    out = []
    for part in v.split("."):
        digits = "".join(c for c in part if c.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def target_dir_for(version):
    """Which .mcp-auth subdir the pinned mcp-remote will read."""
    if version is None:
        return None, ("configs/mcp_servers/notion_official.yaml does not pin an "
                      "mcp-remote version, so the config dir npx lands in can change "
                      "between runs. Pin it (e.g. mcp-remote@0.1.16) first.")
    if version_tuple(version) >= FIXED_DIR_SINCE:
        return AUTH_DIR / "mcp-remote-v1", None
    return AUTH_DIR / ("mcp-remote-%s" % version), None


def describe_grant(directory, server_hash, label):
    """Print what a grant directory holds. Never prints token material."""
    tokens_path = directory / ("%s_tokens.json" % server_hash)
    client_path = directory / ("%s_client_info.json" % server_hash)
    if not tokens_path.exists() or not client_path.exists():
        return None
    tokens = json.loads(tokens_path.read_text())
    client = json.loads(client_path.read_text())
    expires = datetime.datetime.fromtimestamp(tokens["expires_at"] / 1000)
    hours_left = (expires - datetime.datetime.now()).total_seconds() / 3600
    print("%s:" % label)
    print("  client_id       : %s" % client.get("client_id"))
    print("  access_token    : <len=%d>" % len(tokens.get("access_token", "")))
    print("  refresh_token   : %s" % ("present" if tokens.get("refresh_token") else "MISSING"))
    print("  access expires  : %s (%.1f h from now)"
          % (expires.isoformat(sep=" ", timespec="minutes"), hours_left))
    if not tokens.get("refresh_token"):
        print("  WARNING: without a refresh_token the grant dies when the access token expires")
    if hours_left < 0:
        print("  NOTE: the access token is already expired; mcp-remote will try to refresh it")
    return tokens


# --------------------------------------------------------------------------
# import
# --------------------------------------------------------------------------

def do_import(src_arg, dry_run):
    url, version, _args, _config_dir = read_yaml_config()
    dst_dir, err = target_dir_for(version)
    if err:
        print(err, file=sys.stderr)
        return 1

    server_hash = hashlib.md5(url.encode()).hexdigest()
    src = Path(src_arg) if src_arg else AUTH_DIR / "mcp-remote-v1"

    print("server url    : %s" % url)
    print("pinned version: mcp-remote@%s" % version)
    print("url hash      : %s" % server_hash)
    print("source        : %s" % src)
    print("target        : %s" % dst_dir)
    print()

    if not src.is_dir():
        print("source directory does not exist: %s" % src, file=sys.stderr)
        return 1
    if src.resolve() == dst_dir.resolve():
        print("source and target are the same directory; nothing to import", file=sys.stderr)
        return 1

    missing = [n for n in NEEDED if not (src / ("%s_%s" % (server_hash, n))).exists()]
    if missing:
        print("source is missing: %s" % ", ".join(missing))
        print("source contains  : %s" % sorted(p.name for p in src.iterdir()))
        print("The OAuth flow was not completed (tokens.json only appears once the "
              "browser redirect lands). Re-authorize, then import.", file=sys.stderr)
        return 1

    describe_grant(src, server_hash, "source grant")
    print()

    if dry_run:
        print("--dry-run: nothing written")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = AUTH_DIR / (".bak-import-%s" % stamp)
    backup.mkdir(parents=True)
    if dst_dir.is_dir():
        shutil.copytree(dst_dir, backup / dst_dir.name)
        print("backed up target -> %s" % (backup / dst_dir.name))
    else:
        dst_dir.mkdir(parents=True)
        print("target did not exist; created it")

    for name in STALE:
        p = dst_dir / ("%s_%s" % (server_hash, name))
        if p.exists():
            shutil.move(str(p), str(backup / ("removed_%s" % name)))
            print("removed in-flight state: %s" % name)

    for name in NEEDED:
        dest = dst_dir / ("%s_%s" % (server_hash, name))
        shutil.copy2(src / ("%s_%s" % (server_hash, name)), dest)
        os.chmod(dest, 0o600)
        print("copied: %s" % name)

    print()
    print("target now contains:")
    for p in sorted(dst_dir.iterdir()):
        print("  %-52s %d bytes" % (p.name, p.stat().st_size))
    print()
    print("backup: %s" % backup)
    return 0


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

class StdioMCP:
    """Minimal MCP stdio client: send a request, read until the matching id."""

    def __init__(self, cmd):
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1)
        self.responses = queue.Queue()
        self.stderr_lines = []
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self):
        for line in self.proc.stdout:
            line = line.strip()
            if line.startswith("{"):
                try:
                    self.responses.put(json.loads(line))
                except ValueError:
                    pass

    def _read_stderr(self):
        for line in self.proc.stderr:
            self.stderr_lines.append(line.rstrip())

    def notify(self, method, params=None):
        self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def request(self, req_id, method, params=None, timeout=CALL_TIMEOUT_SECONDS):
        self._write({"jsonrpc": "2.0", "id": req_id, "method": method,
                     "params": params or {}})
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = self.responses.get(timeout=2)
            except queue.Empty:
                if self.proc.poll() is not None:
                    return {"error": "proxy exited rc=%s" % self.proc.returncode}
                continue
            if msg.get("id") == req_id:
                return msg
        return {"error": "timed out after %ss waiting for id=%s" % (timeout, req_id)}

    def _write(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.terminate()


def tool_text(response):
    try:
        return response["result"]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return json.dumps(response, ensure_ascii=False)


def page_id(url):
    """Trailing 32-hex id of a Notion page URL."""
    from utils.app_specific.notion.urls import normalize_notion_url
    tail = normalize_notion_url(url).rstrip("/").split("/")[-1]
    return tail.split("?")[0].split("-")[-1]


def do_verify():
    """Run the pinned mcp-remote inside the task image, with configs/.mcp-auth
    bind-mounted the way run_single_containerized.sh mounts it, so what this
    reports is what a real task run will see.

    Five checks, because there are five distinct ways this has broken:
      1. the proxy connects at all
      2. notion-duplicate-page is in the tool list (the tool the duplicator calls)
      3./4. the grant can see the source and eval pages this deployment needs --
         a grant on the wrong workspace passes every other check
      5. it does not fall back to asking for a browser authorization, which in a
         headless container means waiting forever
    """
    from configs.token_key_session import all_token_key_session

    url, version, args, config_dir = read_yaml_config()
    dst_dir, err = target_dir_for(version)
    if err:
        print(err, file=sys.stderr)
        return 1
    server_hash = hashlib.md5(url.encode()).hexdigest()
    auth_dir = AUTH_DIR.resolve()

    source_id = page_id(all_token_key_session.source_notion_page_url)
    eval_id = page_id(all_token_key_session.eval_notion_page_url)

    print("mcp-remote args : %s" % " ".join(args))
    print("config dir      : %s  (host %s)" % (config_dir, auth_dir))
    print("grant dir       : %s" % dst_dir)
    print("task image      : %s" % TASK_IMAGE)
    print("pages this deployment needs:")
    print("  source : %s" % source_id)
    print("  eval   : %s" % eval_id)
    print()

    if dst_dir.is_dir():
        describe_grant(dst_dir, server_hash, "grant on disk")
    else:
        print("grant dir does not exist: %s" % dst_dir)
    print()

    cmd = ["docker", "run", "--rm", "-i",
           "-v", "%s:/workspace/configs/.mcp-auth" % auth_dir,
           "-e", "MCP_REMOTE_CONFIG_DIR=%s" % config_dir,
           "-w", "/workspace", "--entrypoint", "npx", TASK_IMAGE] + args

    checks = {}
    client = StdioMCP(cmd)
    try:
        resp = client.request(1, "initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "notion-official-verify", "version": "0"}})
        checks["connects"] = "result" in resp
        if not checks["connects"]:
            print("initialize failed: %s" % json.dumps(resp, ensure_ascii=False)[:300])
        client.notify("notifications/initialized")

        resp = client.request(2, "tools/list")
        tools = [t["name"] for t in (resp.get("result") or {}).get("tools", [])]
        checks["notion-duplicate-page available"] = "notion-duplicate-page" in tools

        for label, pid in (("eval page visible", eval_id),
                           ("source page visible", source_id)):
            resp = client.request(3, "tools/call",
                                  {"name": "notion-fetch", "arguments": {"id": pid}})
            text = tool_text(resp)
            visible = "object_not_found" not in text and "Could not find" not in text
            checks[label] = visible
            if not visible:
                print("%s -> %s" % (label, text[:200]))
    finally:
        client.close()

    asked_for_browser = any("Please authorize this client" in line
                            for line in client.stderr_lines)
    checks["no browser authorization needed"] = not asked_for_browser

    print()
    print("=== results ===")
    for name, passed in checks.items():
        print("  %-34s %s" % (name, "OK" if passed else "FAIL"))
    print()

    if all(checks.values()):
        print("notion_official is ready; Notion tasks can run")
        return 0

    print("notion_official is NOT ready")
    if asked_for_browser:
        print("  -> it is still asking for a browser authorization, so tokens.json is")
        print("     absent or its refresh was rejected. Re-authorize, then:")
        print("       uv run python global_preparation/notion_official_auth.py fix \\")
        print("         --from /path/to/mcp-remote-v1")
    elif not checks.get("eval page visible", True) or not checks.get("source page visible", True):
        print("  -> it authenticates fine but cannot see the configured pages, so the")
        print("     grant is on the wrong Notion workspace (or its page selection")
        print("     excludes them). Re-authorize with the account that owns the pages")
        print("     above and grant access to the Source/Eval page trees.")
    return 1


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command")

    sub.add_parser("verify", help="check whether the grant on disk is usable (read-only)")

    p_imp = sub.add_parser("import", help="import a grant from another mcp-remote config dir")
    p_imp.add_argument("--from", dest="src", default=None,
                       help="source directory (default: this repo's .mcp-auth/mcp-remote-v1)")
    p_imp.add_argument("--dry-run", action="store_true",
                       help="report what would happen without writing")

    p_fix = sub.add_parser("fix", help="import, then verify")
    p_fix.add_argument("--from", dest="src", default=None,
                       help="source directory (default: this repo's .mcp-auth/mcp-remote-v1)")

    args = ap.parse_args()

    if args.command == "verify":
        return do_verify()
    if args.command == "import":
        return do_import(args.src, args.dry_run)
    if args.command == "fix":
        rc = do_import(args.src, dry_run=False)
        if rc != 0:
            return rc
        print()
        print("=" * 60)
        print("verifying the imported grant")
        print("=" * 60)
        print()
        return do_verify()

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
