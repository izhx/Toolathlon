"""
Notion Login Helper for MCPMark
=================================

This module provides a utility class and CLI script for logging into Notion
using Playwright. It saves the authenticated session state to a file,
which can be used for subsequent automated tasks.
"""

import argparse
import json
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

import logging

# Enable terminal line editing (including Ctrl-H/Backspace) for input().
try:
    import readline  # noqa: F401
except ImportError:
    pass

if __package__:
    from .urls import NOTION_WEB_BASE_URL, normalize_notion_url
else:
    # Also support the documented direct-script invocation.
    from urls import NOTION_WEB_BASE_URL, normalize_notion_url

# Initialize logger
logger = logging.getLogger(__name__)


class NotionLoginHelper:
    """
    Utility helper for logging into Notion using Playwright.
    """

    SUPPORTED_BROWSERS = {"chromium", "firefox"}
    CODE_INPUT_SELECTOR = (
        'input[autocomplete="one-time-code"], '
        'input[placeholder="Enter code"], input[placeholder="Paste verification code"]'
    )

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        headless: bool = True,
        state_path: Optional[str | Path] = None,
        profile_dir: Optional[str | Path] = None,
        browser: str = "firefox",
    ) -> None:
        """
        Initializes the Notion login helper.

        Args:
            url: The Notion URL to open after launching the browser.
            headless: Whether to run Playwright in headless mode.
            state_path: The path to save the authenticated session state.
            profile_dir: Root directory for persistent browser profiles.
            browser: The browser engine to use ('chromium' or 'firefox').
        """
        super().__init__()
        if browser not in self.SUPPORTED_BROWSERS:
            raise ValueError(
                f"Unsupported browser '{browser}'. Supported browsers are: {', '.join(self.SUPPORTED_BROWSERS)}"
            )

        self.url = normalize_notion_url(url or f"{NOTION_WEB_BASE_URL}/login")
        self.headless = headless
        self.browser_name = browser
        self.state_path = (
            Path(state_path or Path.cwd() / "notion_state.json").expanduser().resolve()
        )
        self.profile_dir = (
            Path(profile_dir or self.state_path.parent / "notion_browser_profile")
            .expanduser().resolve() / browser
        )
        self._browser_context: Optional[BrowserContext] = None
        self._playwright = None

    def login(self) -> BrowserContext:
        """
        Reuses the browser profile, then the exported state, before requesting login.
        """
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        browser_type = getattr(self._playwright, self.browser_name)
        logger.info("Using persistent Notion browser profile: %s", self.profile_dir)
        context = browser_type.launch_persistent_context(
            user_data_dir=str(self.profile_dir), headless=self.headless,
        )
        self._browser_context = context
        page = context.pages[0] if context.pages else context.new_page()

        valid = self._check_saved_session(page)
        if not valid and self.state_path.exists() and self._restore_saved_state(context, page):
            valid = self._check_saved_session(page)
        if valid:
            logger.info("Saved Notion login is valid; skipping login.")
            if self.url != f"{NOTION_WEB_BASE_URL}/login":
                page.goto(self.url, wait_until="domcontentloaded")
            # Keep the snapshot consumed by other scripts in sync with the profile.
            context.storage_state(path=str(self.state_path))
            logger.info("Session state exported to %s", self.state_path)
            return context

        start_url = f"{NOTION_WEB_BASE_URL}/login" if self.headless else self.url
        logger.info("No valid saved Notion login; starting a new login.")
        # The session check normally already lands on the login page. Reuse it
        # and its cached assets instead of creating a second, empty context.
        if page.url != start_url:
            logger.info("Navigating to Notion URL: %s", start_url)
            page.goto(start_url, wait_until="domcontentloaded")

        if self.headless:
            self._handle_headless_login(context)
        else:
            logger.info(
                "A browser window has been opened. Please complete the Notion login."
            )
            logger.info(
                "After you see your workspace, return to this terminal and press <ENTER>."
            )
            initial_url = page.url
            input()
            try:
                page.wait_for_url(
                    lambda u: u != initial_url, wait_until="domcontentloaded", timeout=10_000
                )
            except PlaywrightTimeoutError:
                pass  # It's okay if the URL doesn't change

        try:
            page.wait_for_load_state("domcontentloaded", timeout=5_000)
        except PlaywrightTimeoutError:
            pass

        context.storage_state(path=str(self.state_path))
        logger.info("✅ Login successful! Session state saved to %s", self.state_path)

        return context

    def _restore_saved_state(self, context: BrowserContext, page: Page) -> bool:
        """Import the existing JSON without replacing the persistent context."""
        logger.info("Restoring saved Notion login: %s", self.state_path)
        try:
            state = json.loads(self.state_path.read_text())
            # The session check has opened the current Notion origin. Restore its
            # localStorage once, then reload, so stale values cannot overwrite
            # newer login data on subsequent navigations.
            origin = page.evaluate("location.origin")
            entries = [
                entry
                for item in state.get("origins", []) if item["origin"] == origin
                for entry in item.get("localStorage", [])
            ]
            if any(not isinstance(entry["name"], str) or not isinstance(entry["value"], str)
                   for entry in entries):
                raise ValueError("Invalid localStorage snapshot")
            context.add_cookies(state.get("cookies", []))
            page.evaluate(
                "entries => { for (const {name, value} of entries) localStorage.setItem(name, value); }",
                entries,
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError, PlaywrightError) as exc:
            # Playwright validation errors may include cookie values; log only the type.
            logger.warning("Cannot restore saved login (%s); continuing to login.", type(exc).__name__)
            return False
        return True

    def _check_saved_session(self, page: Page) -> bool:
        """Check the workspace UI with saved cookies, not just cookie expiry."""
        logger.info("Checking Notion login in the browser profile...")
        try:
            response = page.goto(f"{NOTION_WEB_BASE_URL}/", wait_until="domcontentloaded", timeout=30_000)
            if response is not None and response.status >= 400:
                raise RuntimeError(
                    f"Saved login check returned HTTP {response.status}; existing state was retained."
                )
            status = page.wait_for_function(
                r"""() => {
                    const atLogin = location.pathname.replace(/\/+$/, '') === '/login';
                    if (atLogin && document.querySelector('input[type="email"]')) return 'expired';
                    if (!atLogin && document.querySelector('.notion-sidebar, .notion-sidebar-container')) {
                        return 'valid';
                    }
                    return false;
                }""",
                timeout=30_000,
            ).json_value()
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                "Could not verify saved Notion login before timeout; existing state was retained. "
                "Retry when the workspace or login page can finish loading."
            ) from exc

        return status == "valid"

    def close(self) -> None:
        """Closes the underlying browser and Playwright instance."""
        if self._browser_context:
            try:
                self._browser_context.close()
            finally:
                self._browser_context = None
        # Closing the persistent context also closes its browser and flushes its
        # profile/cache to disk.
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    @staticmethod
    def _read_login_input(prompt: str) -> str:
        while True:
            value = input(prompt)
            # Do not silently turn a mistyped address into a different address.
            if any(not char.isprintable() for char in value) or "^H" in value or "^?" in value:
                logger.warning("Input contains terminal control characters; please enter it again.")
                continue
            if value.strip():
                return value.strip()
            logger.warning("Input cannot be empty; please enter it again.")

    def _login_timeout(self, page: Page, message: str) -> RuntimeError:
        """Keep a headless failure inspectable on the machine running the script."""
        screenshot_path = self.state_path.with_suffix(".login-error.png")
        detail = f"Current page path: {urlsplit(page.url).path}."
        try:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path), timeout=5_000)
            detail += f" Login page screenshot: {screenshot_path}."
        except (OSError, PlaywrightError):
            detail += " Could not capture the login page screenshot."
        return RuntimeError(f"{message} Login failed; session state was not saved. {detail}")

    def _wait_for_code_input(self, page: Page):
        try:
            result = page.wait_for_function(
                """codeSelector => {
                    const visible = e => e && !e.closest('[aria-hidden="true"]') &&
                        e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
                    const alert = [...document.querySelectorAll('[role="alert"]')]
                        .find(e => visible(e) && e.innerText.trim());
                    if (alert) return {error: alert.innerText.trim()};
                    if ([...document.querySelectorAll(codeSelector)].some(visible)) {
                        return {step: 'code'};
                    }
                    // The initial email form also has an aria-hidden password field
                    // for autofill; it must not be mistaken for password login.
                    if ([...document.querySelectorAll('input[type="password"]')].some(visible)) {
                        return {error: 'Notion is requesting an account password. '
                            + 'Run without --headless to complete this login flow.'};
                    }
                    if ([...document.querySelectorAll('button, [role="button"]')]
                        .some(e => visible(e) && e.innerText.trim() === 'Continue with SSO')) {
                        return {error: 'Notion requires SSO. Run without --headless to complete login.'};
                    }
                    return false;
                }""",
                arg=self.CODE_INPUT_SELECTOR,
                timeout=60_000,
            ).json_value()
        except PlaywrightTimeoutError as exc:
            raise self._login_timeout(
                page, "No verification code input or login error appeared within 60 seconds after submitting email."
            ) from exc
        if result.get("error"):
            raise RuntimeError(f"Notion login stopped: {result['error']} Session state was not saved.")
        return page.locator(f":is({self.CODE_INPUT_SELECTOR}):visible").first

    def _handle_headless_login(self, context: BrowserContext) -> None:
        """
        Guides the user through the login process in headless mode.
        """
        page: Page = context.pages[0]
        login_url = f"{NOTION_WEB_BASE_URL}/login"

        email_input = page.locator('input[type="email"]:visible').first
        try:
            email_input.wait_for(state="visible", timeout=120_000)
        except PlaywrightTimeoutError as exc:
            raise self._login_timeout(page, "Timed out waiting for the email input field.") from exc

        while True:
            email = self._read_login_input("Enter your Notion email address: ")
            email_input.fill(email)
            if email_input.evaluate("element => element.validity.valid"):
                break
            logger.warning("Invalid email address; please enter it again.")

        logger.info("Submitting email; waiting for the next login step (up to 60 seconds)...")
        email_input.press("Enter")
        code_input = self._wait_for_code_input(page)
        code = self._read_login_input("Enter the verification code from your email: ")
        code_input.fill(code)
        logger.info("Submitting verification code; waiting for login redirect (up to 180 seconds)...")
        code_input.press("Enter")

        try:
            page.wait_for_url(
                lambda url: urlsplit(url).path.rstrip("/") != "/login",
                wait_until="domcontentloaded",
                timeout=180_000,
            )
        except PlaywrightTimeoutError as exc:
            raise self._login_timeout(page, "Login redirect timed out after 180 seconds.") from exc

        if self.url and self.url != login_url:
            page.goto(self.url, wait_until="domcontentloaded")

    def __enter__(self) -> "NotionLoginHelper":
        try:
            self.login()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def main():
    """Main entry point for the Notion login CLI script."""
    parser = argparse.ArgumentParser(
        description="Authenticate to Notion and generate a session state file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the login flow in headless mode (prompts for credentials).",
    )
    parser.add_argument(
        "--browser",
        default="chromium",
        choices=["chromium", "firefox"],
        help="The browser engine to use for Playwright.",
    )
    parser.add_argument(
        "--state_path",
        default="./configs/notion_state.json",
        help="The path to save the authenticated session state.",
    )
    parser.add_argument(
        "--profile-dir", "--profile_dir",
        help="Persistent profile root; defaults to notion_browser_profile beside the state file. "
             "Chromium and Firefox use separate subdirectories.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    helper = NotionLoginHelper(
        headless=args.headless, browser=args.browser, state_path=args.state_path,
        profile_dir=args.profile_dir,
    )
    with helper:
        logger.info("Login process completed.")


if __name__ == "__main__":
    main()
