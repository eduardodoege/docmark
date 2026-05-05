"""Parse XML sitemaps to extract page URLs.

Handles both `<urlset>` and `<sitemapindex>` roots, recursing into nested
sitemaps. Transparently decompresses `.gz` sitemaps.
"""
from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET

import httpx

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


async def fetch_urls(sitemap_url: str, client: httpx.AsyncClient) -> list[str]:
    """Return every `<loc>` URL reachable from a sitemap.

    If the sitemap is a `<sitemapindex>`, all nested sitemaps are fetched and
    merged. Output order follows sitemap order; duplicates are not removed.
    """
    raw = await _fetch_xml(sitemap_url, client)
    root = ET.fromstring(raw)
    tag = _localname(root.tag)

    if tag == "sitemapindex":
        nested = [
            loc.text.strip()
            for loc in root.findall(".//sm:sitemap/sm:loc", _NS)
            if loc.text
        ]
        urls: list[str] = []
        for nested_url in nested:
            urls.extend(await fetch_urls(nested_url, client))
        return urls

    if tag == "urlset":
        return [
            loc.text.strip()
            for loc in root.findall(".//sm:url/sm:loc", _NS)
            if loc.text
        ]

    raise ValueError(f"Unrecognized sitemap root element: <{root.tag}>")


async def _fetch_xml(url: str, client: httpx.AsyncClient) -> bytes:
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.content
    if url.lower().endswith(".gz"):
        data = gzip.decompress(data)
    return data


def _localname(tag: str) -> str:
    """Strip XML namespace from a tag name (`{ns}foo` -> `foo`)."""
    return tag.rsplit("}", 1)[-1].lower()
