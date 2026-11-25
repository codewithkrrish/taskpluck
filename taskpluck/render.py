"""Render extracted action items as Markdown or JSON.

Sorting is stable and obvious: due date first (undated items last), then
owner, then the task text. Markdown groups by owner; ``--rollup week``
groups by the ISO week of the due date instead.
"""

from __future__ import annotations

import json

from .dates import week_start
from .extract import ActionItem

__all__ = ["render_json", "render_markdown", "sort_items"]


def sort_items(items: list[ActionItem]) -> list[ActionItem]:
    """Due date, then owner, then task -- undated and unassigned last."""
    return sorted(
        items,
        key=lambda item: (
            item.due is None,
            item.due,
            item.owner is None,
            (item.owner or "").lower(),
            item.task.lower(),
        ),
    )


def _format_item(item: ActionItem) -> str:
    parts = [f"- [ ] {item.task}"]
    if item.due is not None:
        parts.append(f"due {item.due.isoformat()}")
    parts.append(f"{item.source}:{item.line}")
    return " — ".join(parts)


def render_markdown(items: list[ActionItem], rollup_week: bool = False) -> str:
    """A checklist a human can paste straight into their notes."""
    lines = ["# Action items", ""]
    ordered = sort_items(items)
    if not ordered:
        lines.append("No action items found.")
        return "\n".join(lines) + "\n"

    if rollup_week:
        weeks: dict[str, list[ActionItem]] = {}
        for item in ordered:
            label = (
                f"Week of {week_start(item.due).isoformat()}"
                if item.due is not None
                else "No due date"
            )
            weeks.setdefault(label, []).append(item)
        for label, group in weeks.items():
            lines.append(f"## {label}")
            lines.append("")
            lines.extend(_owner_groups(group))
    else:
        lines.extend(_owner_groups(ordered))

    return "\n".join(lines) + "\n"


def _owner_groups(items: list[ActionItem]) -> list[str]:
    owners: dict[str, list[ActionItem]] = {}
    for item in items:
        owners.setdefault(item.owner or "Unassigned", []).append(item)
    # Named owners first (alphabetical), Unassigned last.
    names = sorted(name for name in owners if name != "Unassigned")
    if "Unassigned" in owners:
        names.append("Unassigned")
    lines: list[str] = []
    for name in names:
        lines.append(f"## {name}")
        lines.append("")
        lines.extend(_format_item(item) for item in owners[name])
        lines.append("")
    return lines


def render_json(items: list[ActionItem], rollup_week: bool = False) -> str:
    """One object per item; machine-readable, stable key order."""
    ordered = sort_items(items)
    payload = []
    for item in ordered:
        entry = {
            "task": item.task,
            "owner": item.owner,
            "due": item.due.isoformat() if item.due else None,
            "source": item.source,
            "line": item.line,
        }
        if rollup_week:
            entry["week"] = (
                week_start(item.due).isoformat() if item.due else None
            )
        payload.append(entry)
    return json.dumps(payload, indent=2) + "\n"
