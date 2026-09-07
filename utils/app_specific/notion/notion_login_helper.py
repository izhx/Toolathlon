"""
Notion Login Helper for MCPMark
=================================

This module provides a utility class and CLI script for logging into Notion
using Playwright. It saves the authenticated session state to a file,
which can be used for subsequent automated tasks.
"""

import argparse
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

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        headless: bool = True,
        state_path: Optional[str | Path] = None,
        browser: str = "firefox",
    ) -> None:
        """
        Initializes the Notion login helper.

        Args:
            url: The Notion URL to open after launching the browser.
            headless: Whether to run Playwright in headless mode.
            state_path: The path to save the authenticated session state.
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
        self._browser_context: Optional[BrowserContext] = None
        self._playwright = None
        self._browser = None

    def login(self) -> BrowserContext:
        """
        Reuses a valid saved session, otherwise logs in and saves a new one.
        """
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        browser_type = getattr(self._playwright, self.browser_name)
        self._browser = browser_type.launch(headless=self.headless)
        if self.state_path.exists():
            context = self._check_saved_session()
            if context is not None:
                logger.info("Saved Notion login is valid; skipping login: %s", self.state_path)
                return context

        context = self._browser.new_context()
        self._browser_context = context
        page = context.new_page()

        start_url = f"{NOTION_WEB_BASE_URL}/login" if self.headless else self.url
        logger.info("Navigating to Notion URL: %s", start_url)
        # The form can be ready while unrelated resources still delay `load`.
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

    def _check_saved_session(self) -> Optional[BrowserContext]:
        """Check the workspace UI with saved cookies, not just cookie expiry."""
        logger.info("Checking saved Notion login: %s", self.state_path)
        try:
            context = self._browser.new_context(storage_state=str(self.state_path))
        except (OSError, ValueError, PlaywrightError) as exc:
            # Playwright validation errors may include cookie values; log only the type.
            logger.warning("Cannot load saved login (%s); starting a new login.", type(exc).__name__)
            return None

        self._browser_context = context
        page = context.new_page()
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

        if status == "valid":
            if self.url != f"{NOTION_WEB_BASE_URL}/login":
                page.goto(self.url, wait_until="domcontentloaded")
            return context

        context.close()
        self._browser_context = None
        logger.info("Saved Notion login has expired; starting a new login.")
        return None

    def close(self) -> None:
        """Closes the underlying browser and Playwright instance."""
        if self._browser_context:
            try:
                self._browser_context.close()
            finally:
                self._browser_context = None
        if self._browser:
            try:
                self._browser.close()
            finally:
                self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def _handle_headless_login(self, context: BrowserContext) -> None:
        """
        Guides the user through the login process in headless mode.
        """
        page: Page = context.pages[0]
        login_url = f"{NOTION_WEB_BASE_URL}/login"

        email = input("Enter your Notion email address: ").strip()
        try:
            email_input = page.locator(
                'input[placeholder="Enter your email address..."]'
            )
            email_input.wait_for(state="visible", timeout=120_000)
            email_input.fill(email)
            email_input.press("Enter")
        except PlaywrightTimeoutError:
            raise RuntimeError("Timed out waiting for the email input field.")
        except Exception:
            page.get_by_role("button", name="Continue", exact=True).click()

        try:
            code_input = page.locator('input[placeholder="Enter code"]')
            code_input.wait_for(state="visible", timeout=120_000)
            code = input("Enter the verification code from your email: ").strip()
            code_input.fill(code)
            logger.info("Submitting verification code; waiting for login redirect (up to 180 seconds)...")
            code_input.press("Enter")
        except PlaywrightTimeoutError:
            raise RuntimeError("Timed out waiting for the verification code input.")
        except Exception:
            page.get_by_role("button", name="Continue", exact=True).click()

        try:
            page.wait_for_url(
                lambda url: urlsplit(url).path.rstrip("/") != "/login",
                wait_until="domcontentloaded",
                timeout=180_000,
            )
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                "Login redirect timed out after 180 seconds; session state was not saved. "
                f"Current page path: {urlsplit(page.url).path}. "
                "Check whether the verification code was accepted and login completed."
            ) from exc

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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    helper = NotionLoginHelper(headless=args.headless, browser=args.browser, state_path=args.state_path)
    with helper:
        logger.info("Login process completed.")


if __name__ == "__main__":
    main()
