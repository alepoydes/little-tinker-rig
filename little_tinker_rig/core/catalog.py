"""Catalog families share discovery while retaining exact Python templates."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .block_metadata import LEVELS

if TYPE_CHECKING:
    from .snippets import Snippet


@dataclass(frozen=True)
class Family:
    primary: "Snippet"
    members: "tuple[Snippet, ...]"

    @property
    def identity(self):
        return self.primary.identity

    @property
    def category(self):
        return self.primary.category or self.identity.rsplit("/", 1)[0]

    def choices(self, level="all", allowed=None, eligible=None):
        """Filter exact variants before selecting a card, including legacy lesson IDs."""
        return tuple(
            snippet
            for snippet in self.members
            if (snippet.catalog_visible or allowed is not None)
            and (allowed is None or snippet.identity in allowed)
            and (eligible is None or snippet.identity in eligible)
            and (level == "all" or LEVELS.index(snippet.level) <= LEVELS.index(level))
        )


def families(snippets):
    """Validate and group current templates without changing recognition or source."""
    current = {s.identity: s for s in snippets if not s.historical}
    groups = {}
    for snippet in current.values():
        identity = snippet.catalog_id
        primary = current.get(identity)
        if primary is None or primary.family:
            raise ValueError(
                f"{snippet.identity}: family needs a current primary block: {identity}"
            )
        if (
            snippet.expression != primary.expression
            or snippet.context != primary.context
        ):
            raise ValueError(
                f"{snippet.identity}: family variants need the same insertion kind and context"
            )
        if (
            snippet.category
            and primary.category
            and snippet.category != primary.category
        ):
            raise ValueError(
                f"{snippet.identity}: family variants need the same category"
            )
        if snippet.family and snippet.group and snippet.group != primary.group:
            raise ValueError(
                f"{snippet.identity}: family variants inherit the primary group"
            )
        groups.setdefault(identity, []).append(snippet)
    return tuple(
        Family(
            current[identity],
            tuple(
                sorted(
                    members,
                    key=lambda s: (s.identity != identity, LEVELS.index(s.level)),
                )
            ),
        )
        for identity, members in groups.items()
    )
