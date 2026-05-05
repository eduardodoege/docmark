"""Map URLs to output file paths and write markdown to disk."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse


def url_to_path(url: str, base_dir: Path) -> Path:
    """Mirror the URL path under `base_dir`.

        https://host.com/                                   -> base_dir/index.md
        https://host.com/quickstart                         -> base_dir/quickstart.md
        https://host.com/api-reference/trade/cancel-all     ->
            base_dir/api-reference/trade/cancel-all.md
    """
    path = urlparse(url).path.strip("/")
    if not path:
        return base_dir / "index.md"
    return base_dir / f"{path}.md"


def write_markdown(content: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
