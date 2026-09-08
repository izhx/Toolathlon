import asyncio
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

from utils.app_specific.notion.urls import normalize_notion_url, notion_page_url


NOTION_DIR = Path(__file__).resolve().parents[1] / "utils/app_specific/notion"
SOURCE_ID = "11111111-2222-3333-4444-555555555555"
EVAL_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CHILD_ID = "12345678-1234-5678-9abc-def012345678"
DUPLICATE_ID = "87654321-4321-8765-cba9-876543210fed"


def load_module(name):
    spec = importlib.util.spec_from_file_location(
        f"utils.app_specific.notion._test_{name}", NOTION_DIR / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NotionUrlsTest(unittest.TestCase):
    def test_web_aliases_preserve_page_query_and_fragment(self):
        suffix = f"/workspace/Page-{CHILD_ID.replace('-', '')}?next=https%3A%2F%2Fnotion.so#block"
        for host in (
            "notion.so", "www.notion.so", "app.notion.so",
            "notion.com", "www.notion.com", "app.notion.com", "WWW.NOTION.SO",
        ):
            for scheme in ("http", "https"):
                with self.subTest(host=host, scheme=scheme):
                    self.assertEqual(
                        normalize_notion_url(f"{scheme}://{host}{suffix}"),
                        f"https://app.notion.com{suffix}",
                    )

    def test_non_web_endpoints_and_public_sites_are_unchanged(self):
        for url in (
            "https://api.notion.com/v1/pages/123",
            "https://mcp.notion.com/mcp",
            "https://team.notion.site/Page-123",
            "https://example.com/?next=https://notion.so/login",
            "https://notion.so.example.com/login",
            "mailto:updates@notion.so", "", "XX",
        ):
            with self.subTest(url=url):
                self.assertEqual(normalize_notion_url(url), url)

    def test_page_links_accept_both_id_formats(self):
        expected = "https://app.notion.com/12345678123456789abcdef012345678"
        self.assertEqual(notion_page_url(CHILD_ID), expected)
        self.assertEqual(notion_page_url(CHILD_ID.replace("-", "")), expected)


class NotionUrlConsumersTest(unittest.TestCase):
    """Exercise consumers without credentials, browsers or remote page mutations."""

    def setUp(self):
        self.config = SimpleNamespace(
            source_notion_page_url=f"https://www.notion.so/Source-{SOURCE_ID.replace('-', '')}",
            eval_notion_page_url=f"https://notion.so/Eval-{EVAL_ID.replace('-', '')}",
            notion_integration_key="test-source-key",
            notion_integration_key_eval="test-eval-key",
        )
        self.run_command = AsyncMock()
        self.modules = {
            "configs.token_key_session": SimpleNamespace(all_token_key_session=self.config),
            "configs.global_configs": SimpleNamespace(
                global_configs=SimpleNamespace(notion_preprocess_with_playwright=False)
            ),
            "notion_client": SimpleNamespace(Client=Mock()),
            "playwright.sync_api": SimpleNamespace(
                Browser=Mock, BrowserContext=Mock, Page=Mock,
                Error=RuntimeError, TimeoutError=TimeoutError, sync_playwright=Mock(),
            ),
            "utils.mcp.tool_servers": SimpleNamespace(
                MCPServerManager=Mock(), call_tool_with_retry=AsyncMock(), ToolCallError=RuntimeError,
            ),
            "utils.general.helper": SimpleNamespace(
                run_command=self.run_command, print_color=Mock(),
            ),
        }
        self.enterContext(patch.dict(sys.modules, self.modules))
        self.enterContext(patch.object(sys, "path", sys.path.copy()))
        self.protector_module = load_module("notion_page_protector")
        self.enterContext(patch.dict(sys.modules, {"notion_page_protector": self.protector_module}))

    def test_parent_protection_works_across_old_and_new_domains(self):
        for config_host in ("www.notion.so", "app.notion.com"):
            self.config.source_notion_page_url = f"https://{config_host}/Source-{SOURCE_ID.replace('-', '')}"
            protector = self.protector_module.NotionPageProtector()
            for host in ("notion.so", "www.notion.so", "notion.com", "www.notion.com", "app.notion.com"):
                for page_id in (SOURCE_ID, EVAL_ID):
                    with self.subTest(config_host=config_host, host=host, page_id=page_id):
                        url = f"https://{host}/{page_id.replace('-', '')}?v=123#block"
                        self.assertTrue(protector.is_protected_url(url))
                        self.assertFalse(protector.validate_delete_operation(page_id)[0])
                        self.assertFalse(protector.validate_rename_operation(
                            page_id, protector.get_expected_title(page_id), "Changed"
                        )[0])
            self.assertFalse(protector.is_protected_url(notion_page_url(CHILD_ID)))
            self.assertTrue(protector.validate_delete_operation(CHILD_ID)[0])

    def test_login_default_and_explicit_legacy_page_use_new_domain(self):
        helper_class = load_module("notion_login_helper").NotionLoginHelper
        self.assertEqual(helper_class().url, "https://app.notion.com/login")
        helper = helper_class(url=f"https://www.notion.so/{CHILD_ID}?v=123#block")
        self.assertEqual(helper.url, f"https://app.notion.com/{CHILD_ID}?v=123#block")

    def make_saved_login(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        state_path = Path(directory.name) / "state.json"
        state_path.write_text('{"cookies": [], "origins": []}')
        helper = load_module("notion_login_helper").NotionLoginHelper(state_path=state_path)
        self.addCleanup(helper.close)
        helper._playwright = Mock()
        browser = helper._playwright.firefox.launch.return_value
        context = browser.new_context.return_value
        page = context.new_page.return_value
        context.pages = [page]
        page.goto.return_value = None
        return helper, browser, context, page

    def test_valid_saved_login_skips_prompts_and_leaves_file_untouched(self):
        helper, browser, context, page = self.make_saved_login()
        before = (helper.state_path.read_bytes(), helper.state_path.stat().st_mtime_ns)
        page.wait_for_function.return_value.json_value.return_value = "valid"
        with patch("builtins.input", side_effect=AssertionError("Must not request credentials")) as prompt:
            self.assertIs(helper.login(), context)
        prompt.assert_not_called()
        browser.new_context.assert_called_once_with(storage_state=str(helper.state_path))
        page.goto.assert_called_once_with("https://app.notion.com/", wait_until="domcontentloaded", timeout=30_000)
        context.storage_state.assert_not_called()
        self.assertEqual((helper.state_path.read_bytes(), helper.state_path.stat().st_mtime_ns), before)

    def test_expired_or_unreadable_saved_login_starts_fresh_context(self):
        for failure in ("expired", "unreadable"):
            with self.subTest(failure=failure):
                helper, browser, saved_context, saved_page = self.make_saved_login()
                saved_page.wait_for_function.return_value.json_value.return_value = "expired"
                fresh_context = Mock()
                browser.new_context.side_effect = [
                    ValueError("invalid state file") if failure == "unreadable" else saved_context,
                    fresh_context,
                ]
                helper._handle_headless_login = Mock()
                self.assertIs(helper.login(), fresh_context)
                self.assertEqual(browser.new_context.call_args_list, [
                    call(storage_state=str(helper.state_path)), call(),
                ])
                helper._handle_headless_login.assert_called_once_with(fresh_context)
                saved_context.storage_state.assert_not_called()
                fresh_context.storage_state.assert_called_once_with(path=str(helper.state_path))
                if failure == "expired":
                    saved_context.close.assert_called_once()

    def test_saved_login_check_error_preserves_state_without_prompting(self):
        for failure in ("timeout", "server_error"):
            with self.subTest(failure=failure):
                helper, browser, context, page = self.make_saved_login()
                before = helper.state_path.read_bytes()
                if failure == "timeout":
                    page.wait_for_function.side_effect = TimeoutError("Page did not become ready")
                else:
                    page.goto.return_value = SimpleNamespace(status=502)
                with patch("builtins.input") as prompt, self.assertRaisesRegex(RuntimeError, "retained"):
                    with helper:
                        self.fail("An inconclusive session check must not report success")
                prompt.assert_not_called()
                browser.new_context.assert_called_once_with(storage_state=str(helper.state_path))
                context.storage_state.assert_not_called()
                self.assertEqual(helper.state_path.read_bytes(), before)
                context.close.assert_called_once()

    def test_login_works_when_load_never_fires_without_reloading_login_page(self):
        helper_class = load_module("notion_login_helper").NotionLoginHelper
        for destination in (None, f"https://www.notion.so/{CHILD_ID}"):
            with self.subTest(destination=destination), tempfile.TemporaryDirectory() as temp_dir:
                helper = helper_class(url=destination, state_path=Path(temp_dir) / "state.json")
                helper._playwright = Mock()
                browser = helper._playwright.firefox.launch.return_value
                context = browser.new_context.return_value
                page = context.new_page.return_value
                context.pages = [page]
                page.wait_for_function.return_value.json_value.return_value = {"step": "code"}

                def navigate(url, *, wait_until):
                    if wait_until == "load":
                        raise TimeoutError("External resources prevent the load event")

                def wait_for_redirect(predicate, *, timeout, wait_until="load"):
                    if wait_until == "load":
                        raise TimeoutError("Workspace is open but its load event never fires")
                    self.assertTrue(predicate("https://app.notion.com/home"))

                page.goto.side_effect = navigate
                page.wait_for_url.side_effect = wait_for_redirect
                with patch("builtins.input", side_effect=["test@example.com", "123456"]):
                    self.assertIs(helper.login(), context)
                expected = [call("https://app.notion.com/login", wait_until="domcontentloaded")]
                if destination:
                    expected.append(call(f"https://app.notion.com/{CHILD_ID}", wait_until="domcontentloaded"))
                self.assertEqual(page.goto.call_args_list, expected)
                page.locator.return_value.first.wait_for.assert_any_call(state="visible", timeout=120_000)
                context.storage_state.assert_called_once_with(path=str(helper.state_path))
                helper.close()

    def test_redirect_timeout_does_not_save_state_and_closes_browser(self):
        helper_class = load_module("notion_login_helper").NotionLoginHelper
        for existing_state in (False, True):
            with self.subTest(existing_state=existing_state), tempfile.TemporaryDirectory() as temp_dir:
                state_path = Path(temp_dir) / "state.json"
                old_state = '{"cookies": [], "origins": []}'
                if existing_state:
                    state_path.write_text(old_state)
                helper = helper_class(state_path=state_path)
                playwright = Mock()
                helper._playwright = playwright
                browser = playwright.firefox.launch.return_value
                context = browser.new_context.return_value
                page = context.new_page.return_value
                context.pages = [page]
                page.url = "https://app.notion.com/login?next=home#verification"
                page.wait_for_function.return_value.json_value.return_value = {"step": "code"}
                if existing_state:
                    saved_context = Mock()
                    saved_page = saved_context.new_page.return_value
                    saved_page.goto.return_value = None
                    saved_page.wait_for_function.return_value.json_value.return_value = "expired"
                    browser.new_context.side_effect = [saved_context, context]

                def wait_for_redirect(predicate, **kwargs):
                    # Query/fragment changes while still on /login are not success.
                    self.assertFalse(predicate(page.url))
                    raise TimeoutError("The verification page did not redirect")

                page.wait_for_url.side_effect = wait_for_redirect
                with patch("builtins.input", side_effect=["test@example.com", "123456"]):
                    with self.assertRaisesRegex(RuntimeError, "session state was not saved"):
                        with helper:
                            self.fail("An incomplete login must not report success")
                context.storage_state.assert_not_called()
                if existing_state:
                    self.assertEqual(state_path.read_text(), old_state)
                else:
                    self.assertFalse(state_path.exists())
                context.close.assert_called_once()
                browser.close.assert_called_once()
                playwright.stop.assert_called_once()

    def test_child_page_url_from_api_is_normalized(self):
        duplicator = load_module("notion_page_duplicator").NotionPageDuplicator("test-key")
        duplicator.notion_client.blocks.children.list.return_value = {
            "results": [{"type": "child_page", "id": CHILD_ID}]
        }
        suffix = f"/Child-{CHILD_ID.replace('-', '')}?v=123#block"
        duplicator.notion_client.pages.retrieve.return_value = {
            "url": f"https://www.notion.so{suffix}",
            "properties": {"title": {"title": [{"plain_text": "Child"}]}},
        }
        self.assertEqual(duplicator.find_child_page_by_name(SOURCE_ID, "Child"), (
            CHILD_ID, f"https://app.notion.com{suffix}",
        ))

    def test_browser_duplication_handles_fast_redirects_without_load(self):
        for retry_source, fragment_copy in ((False, False), (True, True)):
            with self.subTest(retry_source=retry_source, fragment_copy=fragment_copy):
                module = load_module("notion_page_duplicator")
                module.sync_playwright = MagicMock()
                duplicator = module.NotionPageDuplicator("test-key")
                duplicator.notion_client = Mock()
                context = module.sync_playwright.return_value.__enter__.return_value.firefox.launch.return_value.new_context.return_value
                page = context.new_page.return_value
                page.url = "about:blank"
                source_url = notion_page_url(CHILD_ID)
                source_attempts = 0

                def goto(url, *, wait_until, timeout):
                    nonlocal source_attempts
                    if wait_until == "load":
                        raise TimeoutError("Page is ready but load never fires")
                    if url == source_url:
                        source_attempts += 1
                    page.url = notion_page_url(EVAL_ID) if retry_source and source_attempts == 1 else url

                def wait_for_load_state(state, **kwargs):
                    if state == "load":
                        raise TimeoutError("External resources are still pending")

                def click(selector, **kwargs):
                    if selector == module.DUPLICATE_MENU_ITEM_SELECTOR:
                        # The URL has already changed by the time click() returns.
                        page.url = f"{source_url}#{DUPLICATE_ID.replace('-', '')}" if fragment_copy else notion_page_url(DUPLICATE_ID)

                def wait_for_url(predicate, *, timeout, wait_until="load"):
                    if wait_until == "load" or not predicate(page.url):
                        raise TimeoutError("Waiting on the wrong URL or load event")

                def retrieve(*, page_id):
                    title = duplicator.protector.PROTECTED_PAGES.get(page_id, "Child (1)")
                    return {"properties": {"title": {"title": [{"plain_text": title}]}}}

                page.goto.side_effect = goto
                page.wait_for_load_state.side_effect = wait_for_load_state
                page.click.side_effect = click
                page.wait_for_url.side_effect = wait_for_url
                duplicator.notion_client.pages.retrieve.side_effect = retrieve
                with patch.object(module.time, "sleep"), patch("builtins.print"):
                    result = duplicator.duplicate_page_with_playwright(
                        notion_page_url(SOURCE_ID), source_url, "Notion Eval Page", "Child"
                    )
                self.assertIsNotNone(result)
                self.assertEqual(duplicator.get_duplicated_page_id(), DUPLICATE_ID)
                self.assertEqual(sum(args.args[0] == module.DUPLICATE_MENU_ITEM_SELECTOR for args in page.click.call_args_list), 1)
                duplicator.notion_client.pages.update.assert_called_once_with(
                    page_id=DUPLICATE_ID,
                    properties={"title": {"title": [{"text": {"content": "Child"}}]}},
                )
                if fragment_copy:
                    self.assertIn(call(notion_page_url(DUPLICATE_ID), wait_until="domcontentloaded", timeout=60_000), page.goto.call_args_list)

    def test_modal_refresh_does_not_wait_for_load(self):
        module = load_module("notion_page_duplicator")
        duplicator = module.NotionPageDuplicator("test-key")
        page = Mock(url=f"https://www.notion.so/{CHILD_ID}")
        page.wait_for_selector.side_effect = TimeoutError("Overlay still present")

        def goto(url, *, wait_until, timeout):
            if wait_until == "load":
                raise TimeoutError("External resources are still pending")

        page.goto.side_effect = goto
        with patch.object(module.time, "sleep"), patch("builtins.print"):
            self.assertTrue(duplicator.clear_modal_overlay(page))
        page.goto.assert_called_once_with(
            f"https://app.notion.com/{CHILD_ID}", wait_until="domcontentloaded", timeout=30_000
        )

    def test_mcp_duplication_returns_new_domain_and_preserves_page_ids(self):
        module = load_module("notion_page_duplicator")
        duplicator = module.NotionPageDuplicator("test-key")
        duplicator.notion_client.pages.retrieve.return_value = {"object": "page"}
        duplicator.rename_page_via_api = Mock()
        module._acquire_notion_official_lock = AsyncMock(return_value="test-lock")
        module._release_notion_official_lock = Mock()
        module.MCPServerManager.return_value.servers = {"notion_official": MagicMock()}
        module.call_tool_with_retry.side_effect = [
            SimpleNamespace(content=[SimpleNamespace(text=json.dumps(body))])
            for body in ({"page_id": CHILD_ID}, {"result": "Success"})
        ]
        with patch("builtins.print"):
            result = asyncio.run(duplicator.duplicate_page_with_mcp(SOURCE_ID, EVAL_ID, "Child"))
        self.assertEqual(result, notion_page_url(CHILD_ID))
        self.assertEqual(duplicator.get_duplicated_page_id(), CHILD_ID)
        move_args = module.call_tool_with_retry.call_args.args[2]
        self.assertEqual(move_args, {"page_or_database_ids": [CHILD_ID], "new_parent": {"page_id": EVAL_ID}})
        module._release_notion_official_lock.assert_called_once_with("test-lock")

    def test_preprocess_converts_config_urls_before_invoking_scripts(self):
        module = load_module("notion_remove_and_duplicate")
        with patch.object(sys, "argv", [
            "preprocess", "--duplicated_page_id_file", "/tmp/unused-page-id.txt",
            "--needed_subpage_name", "Child",
        ]):
            asyncio.run(module.main())
        remove_command, duplicate_command = [args.args[0] for args in self.run_command.call_args_list]
        self.assertIn(normalize_notion_url(self.config.eval_notion_page_url), remove_command)
        self.assertIn(normalize_notion_url(self.config.source_notion_page_url), duplicate_command)
        self.assertIn(normalize_notion_url(self.config.eval_notion_page_url), duplicate_command)
        self.assertNotIn("notion.so", remove_command + duplicate_command)


if __name__ == "__main__":
    unittest.main()
