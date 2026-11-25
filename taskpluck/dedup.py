"""Deduplication for taskpluck.

The same action item shows up in three different notes ("send the deck",
"Send the deck!", "send the deck by Friday"). They are one item. The key
is the normalised task text; the first sighting wins, but a later copy is
allowed to fill in a missing owner or due date.
"""

from __future__ import annotations

import re

from .extract import ActionItem

__all__ = ["dedupe", "normalize"]

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace."""
    return _NORMALIZE_RE.sub(" ", text.lower()).strip()


def dedupe(items: list[ActionItem]) -> list[ActionItem]:
    """Collapse repeated items, keeping the first sighting of each."""
    seen: dict[str, ActionItem] = {}
    order: list[str] = []
    for item in items:
        key = normalize(item.task)
        if not key:
            continue
        existing = seen.get(key)
        if existing is None:
            seen[key] = item
            order.append(key)
            continue
        # A later copy may know more: fill in what the first one lacked.
        if existing.owner is None and item.owner is not None:
            existing.owner = item.owner
        if existing.due is None and item.due is not None:
            existing.due = item.due
    return [seen[key] for key in order]
