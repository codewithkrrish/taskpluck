"""Tests for dedup and rendering (taskpluck.dedup, taskpluck.render)."""

import json
from datetime import date

from taskpluck.dedup import dedupe, normalize
from taskpluck.extract import ActionItem
from taskpluck.render import render_json, render_markdown


def item(task, owner=None, due=None, source="notes.md", line=1):
    return ActionItem(task=task, owner=owner, due=due, source=source, line=line)


def test_normalize():
    assert normalize("Send the Q3 report!") == "send the q3 report"
    assert normalize("  send   the   report ") == "send the report"


def test_dedupe_collapses_repeats():
    items = dedupe([
        item("Send the Q3 report", owner="Krrish", source="a.md", line=3),
        item("send the q3 report!", source="b.md", line=7),
        item("Send the Q3 report by Friday", due=date(2026, 11, 27)),
    ])
    assert len(items) == 2
    assert items[0].owner == "Krrish"  # first sighting wins
    assert items[0].source == "a.md"


def test_dedupe_fills_missing_owner_and_due():
    items = dedupe([
        item("Review the deck"),
        item("review the deck", owner="Asha", due=date(2026, 12, 2)),
    ])
    assert len(items) == 1
    assert items[0].owner == "Asha"
    assert items[0].due == date(2026, 12, 2)


def test_dedupe_keeps_order():
    items = dedupe([item("B task"), item("A task"), item("b task")])
    assert [i.task for i in items] == ["B task", "A task"]


def test_markdown_groups_by_owner():
    out = render_markdown([
        item("Send the report", owner="Krrish", due=date(2026, 11, 27),
             source="notes.md", line=4),
        item("Book the room", source="notes.md", line=9),
    ])
    assert out.startswith("# Action items\n")
    assert "## Krrish" in out
    assert "## Unassigned" in out
    assert "- [ ] Send the report — due 2026-11-27 — notes.md:4" in out
    assert "- [ ] Book the room — notes.md:9" in out
    # Named owners come before Unassigned.
    assert out.index("## Krrish") < out.index("## Unassigned")


def test_markdown_sorts_by_due_date():
    out = render_markdown([
        item("Later task", due=date(2026, 12, 5)),
        item("Sooner task", due=date(2026, 11, 27)),
        item("Undated task"),
    ])
    assert out.index("Sooner task") < out.index("Later task") < out.index("Undated task")


def test_markdown_empty():
    assert "No action items found." in render_markdown([])


def test_markdown_rollup_groups_by_week():
    out = render_markdown([
        item("Friday task", due=date(2026, 11, 27)),
        item("Next week task", due=date(2026, 12, 2)),
        item("Undated task"),
    ], rollup_week=True)
    assert "## Week of 2026-11-23" in out
    assert "## Week of 2026-11-30" in out
    assert "## No due date" in out


def test_json_shape():
    out = json.loads(render_json([
        item("Send the report", owner="Krrish", due=date(2026, 11, 27),
             source="notes.md", line=4),
    ]))
    assert out == [{
        "task": "Send the report",
        "owner": "Krrish",
        "due": "2026-11-27",
        "source": "notes.md",
        "line": 4,
    }]


def test_json_rollup_adds_week():
    out = json.loads(render_json(
        [item("Send the report", due=date(2026, 11, 27))], rollup_week=True
    ))
    assert out[0]["week"] == "2026-11-23"


def test_json_empty_is_empty_list():
    assert json.loads(render_json([])) == []
