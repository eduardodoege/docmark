"""Command-line interface for docmark."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

from . import __version__
from .downloader import fetch_markdown
from .sitemap import fetch_urls
from .writer import url_to_path, write_markdown

_KNOWN_LOCALES = {
    "ar", "cn", "de", "es", "fr", "hi", "it", "ja", "ko",
    "nl", "pl", "pt", "ru", "tr", "vi", "zh", "zh-cn", "zh-tw",
}

_USER_AGENT = f"docmark/{__version__} (+https://github.com/eduardodoege/docmark)"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="docmark",
        description="Crawl a Mintlify-hosted docs site and save every page as raw markdown.",
    )
    parser.add_argument(
        "sitemap_url",
        help="URL of sitemap.xml (also accepts a sitemap-index)",
    )
    parser.add_argument(
        "--output", "-o",
        default=Path("output"),
        type=Path,
        help="Output directory (default: ./output)",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=10,
        help="Parallel downloads (default: 10)",
    )
    parser.add_argument(
        "--include-locales",
        action="store_true",
        help="Include localized variants (e.g. /cn/, /es/). Filtered out by default.",
    )
    parser.add_argument(
        "--include",
        default=None,
        help="Only crawl URLs whose path starts with this prefix.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Skip URLs whose path starts with this prefix (repeatable).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(argv)


def filter_urls(
    urls: list[str],
    *,
    include_locales: bool,
    include_prefix: str | None,
    exclude_prefixes: list[str],
) -> list[str]:
    """Apply locale + prefix filters and dedupe while preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url in seen:
            continue
        path = urlparse(url).path
        first = path.strip("/").split("/", 1)[0].lower() if path.strip("/") else ""

        if not include_locales and first in _KNOWN_LOCALES:
            continue
        if include_prefix and not path.startswith(include_prefix):
            continue
        if any(path.startswith(p) for p in exclude_prefixes):
            continue

        seen.add(url)
        out.append(url)
    return out


async def _run(args: argparse.Namespace) -> int:
    timeout = httpx.Timeout(args.timeout)
    headers = {"User-Agent": _USER_AGENT}

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
    ) as client:
        print(f"Fetching sitemap: {args.sitemap_url}")
        try:
            all_urls = await fetch_urls(args.sitemap_url, client)
        except (httpx.HTTPError, ValueError) as e:
            print(f"  ! sitemap fetch failed: {e}", file=sys.stderr)
            return 2
        print(f"  found {len(all_urls)} URLs")

        urls = filter_urls(
            all_urls,
            include_locales=args.include_locales,
            include_prefix=args.include,
            exclude_prefixes=args.exclude,
        )
        if len(urls) != len(all_urls):
            print(f"  {len(urls)} URLs after filtering")

        if not urls:
            print("Nothing to download.", file=sys.stderr)
            return 1

        sem = asyncio.Semaphore(args.concurrency)
        total = len(urls)
        ok_count = 0
        fail_count = 0
        idx = 0

        async def worker(url: str) -> None:
            nonlocal idx, ok_count, fail_count
            async with sem:
                result = await fetch_markdown(url, client)
                idx += 1
                target = url_to_path(url, args.output)
                if result.ok:
                    write_markdown(result.body, target)
                    ok_count += 1
                    print(f"  [{idx:>3}/{total}] ok    {url}")
                else:
                    fail_count += 1
                    print(
                        f"  [{idx:>3}/{total}] FAIL  {url}  -- {result.error}",
                        file=sys.stderr,
                    )

        await asyncio.gather(*(worker(u) for u in urls))

        await _save_llm_index(args.sitemap_url, args.output, client)

    print()
    print(f"Done. {ok_count} ok, {fail_count} failed.")
    print(f"Output: {args.output.resolve()}")
    return 0 if fail_count == 0 else 1


async def _save_llm_index(
    sitemap_url: str, output: Path, client: httpx.AsyncClient
) -> None:
    """Best-effort fetch of llms.txt and llms-full.txt from the site root."""
    parsed = urlparse(sitemap_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for name in ("llms.txt", "llms-full.txt"):
        try:
            resp = await client.get(f"{base}/{name}")
        except httpx.HTTPError:
            continue
        if resp.status_code == 200 and resp.text.strip():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(resp.text, encoding="utf-8")
            print(f"  saved {name} ({len(resp.text):,} bytes)")


def main() -> None:
    args = parse_args()
    sys.exit(asyncio.run(_run(args)))
