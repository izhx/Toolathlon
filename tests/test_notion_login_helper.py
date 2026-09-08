"""Browser regressions, without contacting Notion or sending login emails.

Run with RUN_NOTION_BROWSER_TESTS=1 and an installed Playwright Chromium.
"""

import json
import os
import tempfile
import threading
import time
import unittest
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


class LoginFixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requests[self.path] += 1
        if self.path in ("/fixture.css", "/fixture.js"):
            is_css = self.path.endswith(".css")
            body = b"body { color: rgb(10, 20, 30); }" if is_css else b"window.fixtureAssetReady = true;"
            self.send_response(200)
            self.send_header("Content-Type", "text/css" if is_css else "text/javascript")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/":
            self.send_response(302)
            authenticated = "fixture_session=valid" in self.headers.get("Cookie", "")
            self.send_header("Location", "/home" if authenticated else "/login")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if self.path == "/pending.png":
            self.server.release.wait(10)
            return
        if self.path == "/home":
            body = """
                <div id="workspace">Workspace</div><img src="/pending.png">
                <script>
                    if (localStorage.getItem('fixture-user') === 'valid') {
                        document.querySelector('#workspace').className = 'notion-sidebar';
                    }
                </script>
            """
        else:
            body = """
                <input id="email" type="email">
                <input type="password" aria-hidden="true" tabindex="-1">
                <div id="alert" role="alert" hidden></div>
                <input id="code" autocomplete="one-time-code" placeholder="验证码" hidden>
                <script>
                    const scenario = SCENARIO;
                    const email = document.querySelector('#email');
                    const code = document.querySelector('#code');
                    if (scenario === 'legacy') {
                        code.removeAttribute('autocomplete');
                        code.placeholder = 'Enter code';
                    }
                    email.addEventListener('keydown', e => {
                        if (e.key !== 'Enter') return;
                        sessionStorage.setItem('submittedEmail', email.value);
                        if (scenario === 'error') {
                            const alert = document.querySelector('#alert');
                            alert.textContent = 'This email address cannot be used.';
                            alert.hidden = false;
                        } else if (scenario === 'password') {
                            const password = document.createElement('input');
                            password.type = 'password';
                            document.body.append(password);
                        } else if (scenario === 'sso') {
                            const button = document.createElement('button');
                            button.textContent = 'Continue with SSO';
                            document.body.append(button);
                        } else if (scenario !== 'stalled') {
                            setTimeout(() => { code.hidden = false; }, 100);
                        }
                    });
                    code.addEventListener('keydown', e => {
                        if (e.key !== 'Enter') return;
                        document.cookie = 'fixture_session=valid; path=/; Max-Age=3600';
                        localStorage.setItem('fixture-user', 'valid');
                        location.href = '/home';
                    });
                </script>
            """.replace("SCENARIO", json.dumps(self.server.scenario))
        body = '<link rel="stylesheet" href="/fixture.css"><script src="/fixture.js"></script>' + body
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body.encode())


@unittest.skipUnless(os.environ.get("RUN_NOTION_BROWSER_TESTS") == "1", "Opt-in browser tests")
class NotionLoginBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from utils.app_specific.notion import notion_login_helper

        cls.module = notion_login_helper
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LoginFixture)
        cls.addClassCleanup(cls.server.server_close)
        thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        thread.start()
        cls.addClassCleanup(cls.server.shutdown)

    def setUp(self):
        self.server.scenario = "code"
        self.server.requests = Counter()
        self.server.release = threading.Event()
        self.addCleanup(self.server.release.set)
        self.enterContext(patch.object(
            self.module, "NOTION_WEB_BASE_URL", f"http://127.0.0.1:{self.server.server_port}"
        ))
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.state_path = Path(directory) / "notion_state.json"
        self.helper = self.module.NotionLoginHelper(state_path=self.state_path, browser="chromium")
        self.addCleanup(self.helper.close)

    def test_bad_terminal_input_and_invalid_email_are_reprompted_before_submission(self):
        answers = [
            "probe@160\b3.com", "probe@160^H3.com", "probe@160\x7f3.com",
            "not-an-email", "probe@example.test", "\x1b[1D123456", "fixture-code",
        ]
        with patch("builtins.input", side_effect=answers) as prompt:
            context = self.helper.login()
        self.assertEqual(prompt.call_count, len(answers))
        page = context.pages[0]
        self.assertEqual(page.evaluate("sessionStorage.getItem('submittedEmail')"), "probe@example.test")
        self.assertTrue(any(c["name"] == "fixture_session" for c in json.loads(self.state_path.read_text())["cookies"]))
        self.assertEqual(page.evaluate("performance.getEntriesByType('navigation')[0].loadEventEnd"), 0)

    def test_legacy_code_placeholder_still_works(self):
        self.server.scenario = "legacy"
        with patch("builtins.input", side_effect=["probe@example.test", "fixture-code"]):
            self.helper.login()
        self.assertTrue(self.state_path.exists())

    def test_profile_reuses_authentication_and_disk_cache_across_restarts(self):
        with patch("builtins.input", side_effect=["probe@example.test", "fixture-code"]):
            self.helper.login()
        self.helper.close()
        self.assertTrue(self.helper.profile_dir.is_dir())
        self.assertEqual(self.server.requests["/fixture.css"], 1)
        self.assertEqual(self.server.requests["/fixture.js"], 1)

        for snapshot in ("stale", "missing"):
            with self.subTest(snapshot=snapshot):
                if snapshot == "stale":
                    self.state_path.write_text('{"cookies": [], "origins": []}')
                else:
                    self.state_path.unlink()
                with patch("builtins.input", side_effect=AssertionError("Must reuse the profile")):
                    context = self.helper.login()
                page = context.pages[0]
                self.assertTrue(page.evaluate("window.fixtureAssetReady"))
                self.assertEqual(page.evaluate("localStorage.getItem('fixture-user')"), "valid")
                exported = json.loads(self.state_path.read_text())
                self.assertTrue(any(c["name"] == "fixture_session" for c in exported["cookies"]))
                self.assertEqual(self.server.requests["/fixture.css"], 1)
                self.assertEqual(self.server.requests["/fixture.js"], 1)
                self.helper.close()

    def test_new_profile_imports_cookie_and_local_storage_from_existing_json(self):
        self.state_path.write_text(json.dumps({
            "cookies": [{
                "name": "fixture_session", "value": "valid", "domain": "127.0.0.1", "path": "/",
                "expires": int(time.time()) + 3600, "httpOnly": True, "secure": False, "sameSite": "Lax",
            }],
            "origins": [{
                "origin": self.module.NOTION_WEB_BASE_URL,
                "localStorage": [
                    {"name": "fixture-user", "value": "valid"},
                    {"name": "fixture-setting", "value": "old"},
                ],
            }],
        }))
        with patch("builtins.input", side_effect=AssertionError("Must import the existing login")):
            context = self.helper.login()
        page = context.pages[0]
        self.assertEqual(page.evaluate("localStorage.getItem('fixture-setting')"), "old")
        # A later navigation must not reapply the old snapshot over newer values.
        page.evaluate("localStorage.setItem('fixture-setting', 'new')")
        page.reload(wait_until="domcontentloaded")
        self.assertEqual(page.evaluate("localStorage.getItem('fixture-setting')"), "new")

    def test_server_error_exits_without_code_prompt_and_preserves_saved_state(self):
        self.server.scenario = "error"
        old_state = '{"cookies": [], "origins": []}'
        self.state_path.write_text(old_state)
        with patch("builtins.input", return_value="probe@example.test") as prompt:
            with self.assertRaisesRegex(RuntimeError, "This email address cannot be used"):
                with self.helper:
                    self.fail("A rejected email must not report login success")
        self.assertEqual(prompt.call_count, 1)
        self.assertEqual(self.state_path.read_text(), old_state)

    def test_password_and_sso_are_reported_without_waiting_for_a_code(self):
        for scenario, message in (("password", "account password"), ("sso", "requires SSO")):
            with self.subTest(scenario=scenario):
                self.server.scenario = scenario
                with patch("builtins.input", return_value="probe@example.test") as prompt:
                    with self.assertRaisesRegex(RuntimeError, message):
                        with self.helper:
                            self.fail("This flow cannot be completed with an email code")
                self.assertEqual(prompt.call_count, 1)
                self.assertFalse(self.state_path.exists())

    def test_stalled_email_submission_saves_page_screenshot(self):
        self.server.scenario = "stalled"
        original_wait = self.module.Page.wait_for_function

        def short_wait(page, expression, **kwargs):
            if kwargs.get("timeout") == 60_000:
                kwargs["timeout"] = 250
            return original_wait(page, expression, **kwargs)

        with patch.object(self.module.Page, "wait_for_function", short_wait):
            with patch("builtins.input", return_value="probe@example.test") as prompt:
                with self.assertRaisesRegex(RuntimeError, "Login page screenshot"):
                    with self.helper:
                        self.fail("A stalled login must not report success")
        self.assertEqual(prompt.call_count, 1)
        self.assertFalse(self.state_path.exists())
        self.assertTrue(self.state_path.with_suffix(".login-error.png").exists())


if __name__ == "__main__":
    unittest.main()
