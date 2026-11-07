"""Relative Markdown links must be clickable on GitHub.

Task-card filenames contain spaces. CommonMark rejects a destination with
unescaped spaces, so GitHub renders such a link as plain text even though
every target exists -- which is exactly what happened to 34 links.
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)\n]+)\)")
EXTERNAL = ("http://", "https://", "mailto:", "#")


def _markdown_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "DEVELOPMENT.md"]
    files.extend(sorted((ROOT / "docs").rglob("*.md")))
    return [path for path in files if path.exists()]


def test_relative_links_are_wrapped_and_resolve():
    problems: list[str] = []
    for md in _markdown_files():
        for match in LINK.finditer(md.read_text(encoding="utf-8")):
            target = match.group(1)
            if target.startswith(EXTERNAL):
                continue
            wrapped = target.startswith("<")
            path_part = target.strip("<>").split("#")[0].strip()
            if not path_part:
                continue
            where = md.relative_to(ROOT)
            if re.search(r"\s", path_part) and not wrapped:
                problems.append(f"{where}: destination has spaces, wrap it")
                continue
            resolved = (
                md.parent / urllib.parse.unquote(path_part)
            ).resolve()
            if not resolved.exists():
                problems.append(f"{where}: target does not exist -> {target}")
    assert not problems, "\n".join(problems[:10])
