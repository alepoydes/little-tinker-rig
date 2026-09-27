"""Markdown section names shared by offline help and documentation validation."""

import re
import unicodedata


def prose(text):
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced:
            yield line


def heading_anchors(text):
    """Yield stable anchor names per ATX heading, including preceding HTML names."""
    counts, pending = {}, []
    for line in prose(text):
        pending.extend(re.findall(r"<a\s+(?:name|id)=[\'\"]([^\'\"]+)", line))
        if match := re.match(r"^#{1,6}\s+(.+?)\s*#*$", line):
            title = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", match[1])
            slug = "".join(
                c
                for c in title.lower()
                if c in " _-" or unicodedata.category(c)[0] in "LN"
            ).replace(" ", "-")
            count = counts.get(slug, 0)
            counts[slug] = count + 1
            yield [slug if count == 0 else f"{slug}-{count}", *pending]
            pending = []


def section(text, anchor):
    """Select an ATX section with its subsections; ignore headings in code fences."""
    anchors = iter(heading_anchors(text))
    lines = text.splitlines(keepends=True)
    start, level, fenced = None, 0, False
    for index, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and (match := re.match(r"^(#{1,6})\s+(.+?)\s*#*$", line)):
            names = next(anchors)
            if start is not None and len(match[1]) <= level:
                return "".join(lines[start:index])
            if anchor in names:
                start, level = index, len(match[1])
    if start is None:
        raise ValueError(f"Missing Markdown section: {anchor}")
    return "".join(lines[start:])
