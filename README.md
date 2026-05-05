# docmark

Convert hosted documentation sites to local Markdown — built for feeding LLMs and AI Skills.

Currently optimized for **Mintlify**-hosted docs (Anthropic, Polymarket, many web3 / crypto sites), which expose the source markdown of any page at `<url>.md`. The architecture is built around a single downloader strategy, so other doc platforms (Docusaurus, MkDocs, GitBook, ReadMe, generic HTML) can be added without rewriting the rest of the pipeline.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## Use

```powershell
docmark https://docs.polymarket.com/sitemap.xml --output ./output/polymarket
```

Or without installing:

```powershell
python -m docmark https://docs.polymarket.com/sitemap.xml --output ./output/polymarket
```

### Options

| Flag | Default | Description |
| --- | --- | --- |
| `--output`, `-o` | `output` | Directory to write markdown files into |
| `--concurrency`, `-c` | `10` | Parallel downloads |
| `--include-locales` | off | Include localized variants (`/cn/`, `/es/`, ...). Filtered out by default. |
| `--include` | none | Only crawl URLs whose path starts with this prefix |
| `--exclude` | none | Skip URLs whose path starts with this prefix (repeatable) |
| `--timeout` | `30` | Per-request timeout in seconds |

### Examples

Only API reference pages, higher concurrency:

```powershell
docmark https://docs.polymarket.com/sitemap.xml -o ./out -c 20 --include /api-reference/
```

Include Chinese variant and skip the `/builders/` section:

```powershell
docmark https://docs.polymarket.com/sitemap.xml -o ./out --include-locales --exclude /builders/
```

## How URL paths map to files

```
https://docs.polymarket.com/                           -> output/index.md
https://docs.polymarket.com/quickstart                 -> output/quickstart.md
https://docs.polymarket.com/api-reference/trade/cancel-all-orders
                                                       -> output/api-reference/trade/cancel-all-orders.md
```

## How it works

Mintlify renders HTML for users, but also serves the raw MDX source whenever a request appends `.md` to a page URL:

```
https://docs.example.com/quickstart       -> rendered HTML
https://docs.example.com/quickstart.md    -> raw markdown source
```

The crawler reads the site's `sitemap.xml`, requests `<url>.md` for every entry in parallel, and writes each response to disk preserving the URL path. No HTML parsing, no headless browser, no conversion loss — output matches what the docs author wrote.

### Detecting Mintlify

A site is likely Mintlify if any of these hold:

- `<meta name="generator" content="Mintlify">` in the HTML
- Assets served from `mintcdn.com`
- A `llms.txt` or `llms-full.txt` file exists at the site root
- Appending `.md` to a doc URL returns plain markdown (not HTML)

If `.md` requests return HTML, the site is not Mintlify and a different strategy is needed.

## Supported platforms

| Platform | Status | Strategy |
| --- | --- | --- |
| Mintlify | Implemented | Append `.md` to each page URL |
| Docusaurus | Possible | Fetch source `.md` / `.mdx` from the docs repo on GitHub |
| MkDocs | Possible | Same — fetch source from the GitHub repo |
| GitBook | Possible | GitBook API (with token), or HTML scrape |
| ReadMe | Possible | ReadMe API (with token), or HTML scrape |
| Generic / custom | Possible | HTML scrape (`markdownify` or `html2text`) |

The downloader (`src/docmark/downloader.py`) is the only piece that knows about a specific platform. Adding a new strategy means writing a small module with a `fetch(page_url, client) -> DownloadResult` function and wiring it as a `--strategy` choice in the CLI. Sitemap parsing, filters, file writing, and concurrency stay untouched.

Strategies are added on demand — when a concrete site needs them — not speculatively.

## Notes

- Sitemap-driven. URLs not listed in `sitemap.xml` are not crawled.
- Pages are saved as raw MDX. Mintlify components (`<Steps>`, `<Tabs>`, `<CardGroup>`, ...) are preserved verbatim — Claude and other LLMs read them fine.
- A best-effort fetch of `llms.txt` and `llms-full.txt` from the site root is included.

## License

MIT — see [LICENSE](LICENSE).
