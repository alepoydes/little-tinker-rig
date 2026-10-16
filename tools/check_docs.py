"""Check localized page coverage and repository Markdown links without a renderer."""

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from little_tinker_rig.documentation import DEVELOPER_PAGES, heading_anchors, prose

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    languages = json.loads(
        (root / "little_tinker_rig/locale/languages.json").read_text(encoding="utf-8")
    )
    docs = root / "doc"
    pages = {
        code: {path.relative_to(docs / code) for path in (docs / code).rglob("*.md")}
        for code in languages
    }
    failures = []
    expected = set().union(*pages.values(), {Path("index.md")})
    for code, present in pages.items():
        required = expected if code == "en" else expected - DEVELOPER_PAGES
        for missing in sorted(required - present):
            failures.append(f"{code}: missing documentation page {missing}")
        if code != "en":
            for translated in sorted(present & DEVELOPER_PAGES):
                failures.append(
                    f"{code}: developer page must be English-only: {translated}"
                )
    files = [
        root / "README.md",
        *root.glob("AGENTS.md"),
        *docs.rglob("*.md"),
        *(root / "devs").glob("*.md"),
    ]
    anchor_cache = {}
    for path in files:
        text = path.read_text(encoding="utf-8")
        for line in prose(text):
            for match in re.finditer(
                r'!?\[[^\]\n]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)', line
            ):
                url = urlsplit(match[1])
                if url.scheme or url.netloc:
                    continue
                target = (
                    (path.parent / unquote(url.path)).resolve()
                    if url.path
                    else path.resolve()
                )
                if not target.exists():
                    failures.append(
                        f"{path.relative_to(root)}: missing link target {match[1]}"
                    )
                elif url.fragment and target.suffix == ".md":
                    if target not in anchor_cache:
                        anchor_cache[target] = {
                            name
                            for names in heading_anchors(
                                target.read_text(encoding="utf-8")
                            )
                            for name in names
                        }
                    if unquote(url.fragment) not in anchor_cache[target]:
                        failures.append(
                            f"{path.relative_to(root)}: missing anchor {match[1]}"
                        )
    return failures


if __name__ == "__main__":
    failures = check()
    if failures:
        raise SystemExit("\n".join(failures))
    print("Documentation pages and links: OK")
