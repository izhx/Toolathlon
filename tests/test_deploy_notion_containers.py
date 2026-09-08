import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DeployNotionContainersTest(unittest.TestCase):
    """Exercise deployment boundaries with all backend operations stubbed."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        script_dir = self.root / "global_preparation"
        script_dir.mkdir()
        self.script = script_dir / "deploy_notion_containers.sh"
        shutil.copyfile(
            REPO_ROOT / "global_preparation" / self.script.name, self.script
        )
        self.fake_bin = self.root / "bin"
        self.fake_bin.mkdir()
        self.capture = self.root / "calls.txt"
        self.env = os.environ.copy()
        self.env.update(
            PATH=f"{self.fake_bin}:{self.env['PATH']}",
            CAPTURE_FILE=str(self.capture),
            POSTE_READY_TIMEOUT_SECONDS="1",
            FAKE_RUNTIME="docker",
        )
        self.stub(
            "uv",
            'cat >/dev/null\n'
            'if [[ "${FAIL_SETTINGS:-}" == 1 ]]; then exit 19; fi\n'
            'printf "%s\\nposte-inst-test\\n" "$FAKE_RUNTIME"\n',
        )
        self.stub("bash", 'exit "${SETUP_EXIT:-0}"\n')
        self.stub("jq", 'exit "${ACCOUNTS_EXIT:-0}"\n')
        for runtime in ("docker", "podman"):
            self.stub(
                runtime,
                '[[ "$1" == port && "$2" == poste-inst-test ]] || exit 99\n'
                'if [[ "$3" == "${MISSING_PORT:-}" ]]; then exit 1; fi\n'
                'case "$3" in\n'
                '  80/tcp) port=21005 ;;\n'
                '  143/tcp) port=3143 ;;\n'
                '  25/tcp) port=4525 ;;\n'
                '  587/tcp) port=3587 ;;\n'
                '  *) exit 99 ;;\n'
                'esac\n'
                'printf "0.0.0.0:%s\\n[::]:%s\\n" "$port" "$port"\n',
            )
        self.stub("curl", 'printf "%s" "${HTTP_CODE:-200}"\n')
        self.stub(
            "nc",
            'cat >/dev/null\n'
            'case "${@: -1}" in\n'
            '  3143) printf "* OK IMAP4rev1 ready\\n" ;;\n'
            '  4525|3587) printf "220 ESMTP ready\\n" ;;\n'
            '  *) exit 99 ;;\n'
            'esac\n',
        )

    def stub(self, name, body):
        path = self.fake_bin / name
        path.write_text(
            '#!/bin/bash\n'
            'printf "%s|%s|%s\\n" "${0##*/}" "$PWD" "$*" >> "$CAPTURE_FILE"\n'
            + body,
            encoding="utf-8",
        )
        path.chmod(0o755)

    def run_script(self, *args):
        return subprocess.run(
            ["/bin/bash", str(self.script), *args],
            cwd=self.root.parent,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def calls(self):
        return self.capture.read_text().splitlines() if self.capture.exists() else []

    def test_deploy_only_poste_with_configured_runtime_and_actual_ports(self):
        for runtime in ("docker", "podman"):
            with self.subTest(runtime=runtime):
                self.env["FAKE_RUNTIME"] = runtime
                self.capture.unlink(missing_ok=True)
                result = self.run_script("false")
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                self.assertEqual(
                    [call for call in calls if call.startswith("bash|")],
                    [f"bash|{self.root}|deployment/poste/scripts/setup.sh start false"],
                )
                self.assertEqual(
                    len([call for call in calls if call.startswith(f"{runtime}|")]), 4
                )
                self.assertIn("HTTP=21005 IMAP=3143 SMTP=4525 submission=3587", result.stdout)
                self.assertIn(f"nc|{self.root}|-w 3 localhost 3587", calls)
                self.assertFalse(any("prune" in call or "kill" in call for call in calls))

    def test_check_does_not_reinitialize_poste_or_accounts(self):
        result = self.run_script("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(call.startswith(("bash|", "jq|")) for call in self.calls()))

    def test_dry_run_needs_no_configuration_or_backend_access(self):
        result = self.run_script("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("setup.sh start true", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_invalid_arguments_fail_before_backend_access(self):
        for args in (("--unknown",), ("yes",), ("true", "false")):
            with self.subTest(args=args):
                self.assertEqual(self.run_script(*args).returncode, 2)
        self.env["POSTE_READY_TIMEOUT_SECONDS"] = "0"
        self.assertEqual(self.run_script().returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_configuration_failure_stops_before_deploy(self):
        self.env["FAIL_SETTINGS"] = "1"
        result = self.run_script()
        self.assertEqual(result.returncode, 19)
        self.assertFalse(any(call.startswith("bash|") for call in self.calls()))

    def test_setup_failure_is_propagated_without_retry(self):
        self.env["SETUP_EXIT"] = "17"
        result = self.run_script()
        self.assertEqual(result.returncode, 17)
        self.assertEqual(len([c for c in self.calls() if c.startswith("bash|")]), 1)
        self.assertFalse(any(c.startswith(("jq|", "docker|", "curl|")) for c in self.calls()))

    def test_partial_account_initialization_is_not_reported_as_success(self):
        self.env["ACCOUNTS_EXIT"] = "1"
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("account initialization is incomplete", result.stderr)
        self.assertFalse(any(c.startswith("docker|") for c in self.calls()))

    def test_missing_published_port_fails(self):
        self.env["MISSING_PORT"] = "143/tcp"
        result = self.run_script("--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c.startswith("curl|") for c in self.calls()))

    def test_failed_readiness_times_out_without_redeploy(self):
        self.env["HTTP_CODE"] = "503"
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("did not become ready", result.stderr)
        self.assertEqual(len([c for c in self.calls() if c.startswith("bash|")]), 1)


if __name__ == "__main__":
    unittest.main()
