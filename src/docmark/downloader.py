"""Download a Mintlify page as raw markdown.

Mintlify exposes the markdown source of any doc page at `<page-url>.md`.
This module knows the URL transform and validates that the response is
markdown, not an HTML fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx


@dataclass
class DownloadResult:
    page_url: str
    md_url: str
    status: int
    body: str | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.body is not None


async def fetch_markdown(page_url: str, client: httpx.AsyncClient) -> DownloadResult:
    md_url = to_md_url(page_url)
    try:
        resp = await client.get(md_url)
    except httpx.HTTPError as e:
        return DownloadResult(page_url, md_url, 0, None, f"request failed: {e}")

    if resp.status_code != 200:
        return DownloadResult(
            page_url, md_url, resp.status_code, None, f"HTTP {resp.status_code}"
        )

    if _looks_like_html(resp):
        return DownloadResult(
            page_url,
            md_url,
            resp.status_code,
            None,
            "response is HTML (Mintlify .md endpoint not available for this page)",
        )

    return DownloadResult(page_url, md_url, resp.status_code, resp.text)


def to_md_url(page_url: str) -> str:
    """Map a page URL to its Mintlify markdown endpoint.

        https://host.com/         -> https://host.com/index.md
        https://host.com          -> https://host.com/index.md
        https://host.com/foo      -> https://host.com/foo.md
        https://host.com/foo/     -> https://host.com/foo.md
        https://host.com/foo.md   -> https://host.com/foo.md  (idempotent)
    """
    parsed = urlparse(page_url)
    path = parsed.path.rstrip("/")
    if not path:
        new_path = "/index.md"
    elif path.endswith(".md"):
        new_path = path
    else:
        new_path = f"{path}.md"
    return urlunparse(parsed._replace(path=new_path, query="", fragment=""))


def _looks_like_html(resp: httpx.Response) -> bool:
    content_type = resp.headers.get("content-type", "").lower()
    if "html" in content_type:
        return True
    head = resp.text[:200].lstrip().lower()
    return head.startswith("<!doctype html") or head.startswith("<html")
