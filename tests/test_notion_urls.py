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
                TimeoutError=TimeoutError, sync_playwright=Mock(),
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

                def navigate(url, *, wait_until):
                    if wait_until == "load":
                        raise TimeoutError("External resources prevent the load event")

                page.goto.side_effect = navigate
                with patch("builtins.input", side_effect=["test@example.com", "123456"]):
                    self.assertIs(helper.login(), context)
                expected = [call("https://app.notion.com/login", wait_until="domcontentloaded")]
                if destination:
                    expected.append(call(f"https://app.notion.com/{CHILD_ID}", wait_until="domcontentloaded"))
                self.assertEqual(page.goto.call_args_list, expected)
                page.locator.return_value.wait_for.assert_any_call(state="visible", timeout=120_000)
                context.storage_state.assert_called_once_with(path=str(helper.state_path))
                helper.close()

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
