"""Notion web URLs, separate from the REST API and MCP endpoints."""

from urllib.parse import urlsplit, urlunsplit


NOTION_WEB_BASE_URL = "https://app.notion.com"
_WEB_HOSTS = {
    "notion.so", "www.notion.so", "app.notion.so",
    "notion.com", "www.notion.com", "app.notion.com",
}


def normalize_notion_url(url: str) -> str:
    """Avoid web-domain redirects while preserving the page, query and fragment."""
    parts = urlsplit(url)
    if parts.scheme in {"http", "https"} and parts.netloc.lower() in _WEB_HOSTS:
        return urlunsplit(("https", "app.notion.com", parts.path, parts.query, parts.fragment))
    return url


def notion_page_url(page_id: str) -> str:
    return f"{NOTION_WEB_BASE_URL}/{page_id.replace('-', '')}"
