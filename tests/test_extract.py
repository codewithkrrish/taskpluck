"""Tests for the extractor (taskpluck.extract)."""

from datetime import date

from taskpluck.extract import extract_items

BASE = date(2026, 11, 25)  # a Wednesday


def first(text: str, base: date = BASE):
    items = extract_items(text, base=base)
    assert len(items) == 1, f"expected 1 item, got {items}"
    return items[0]


def test_checkbox():
    item = first("- [ ] send the Q3 report by Friday")
    assert item.task == "send the Q3 report"
    assert item.due == date(2026, 11, 27)
    assert item.owner is None


def test_done_checkbox_is_ignored():
    assert extract_items("- [x] send the report") == []
    assert extract_items("- [X] send the report") == []


def test_markers():
    assert first("TODO: fix the login bug").task == "fix the login bug"
    assert first("ACTION: review the deck").task == "review the deck"
    assert first("Action item: book the demo room").task == "book the demo room"
    assert first("Follow up: chase the vendor").task == "chase the vendor"


def test_owner_will_pattern():
    item = first("Krrish will send the report by Friday")
    assert item.owner == "Krrish"
    assert item.task == "send the report"
    assert item.due == date(2026, 11, 27)


def test_owner_to_pattern():
    item = first("Asha to review the onboarding copy by Dec 2")
    assert item.owner == "Asha"
    assert item.task == "review the onboarding copy"
    assert item.due == date(2026, 12, 2)


def test_owner_should_pattern():
    item = first("Rohan should update the runbook tomorrow")
    assert item.owner == "Rohan"
    assert item.task == "update the runbook"
    assert item.due == date(2026, 11, 26)


def test_name_colon_pattern():
    item = first("Krrish: send the report by Friday")
    assert item.owner == "Krrish"
    assert item.task == "send the report"


def test_owner_field():
    item = first("Owner: Asha — finalise the interview loop by 5 Dec")
    assert item.owner == "Asha"
    assert item.task == "finalise the interview loop"
    assert item.due == date(2026, 12, 5)


def test_mention_with_verb():
    item = first("@asha please review the deck by Friday")
    assert item.owner == "Asha"
    assert item.task == "review the deck"
    assert item.due == date(2026, 11, 27)


def test_mention_inside_marker_line():
    item = first("ACTION: @rohan please check the staging deploy in 2 days")
    assert item.owner == "Rohan"
    assert item.task == "check the staging deploy"
    assert item.due == date(2026, 11, 27)


def test_mention_inside_checkbox():
    item = first("- [ ] @asha review the onboarding copy by Dec 2")
    assert item.owner == "Asha"
    assert item.task == "review the onboarding copy"
    assert item.due == date(2026, 12, 2)


def test_mention_without_verb_is_not_a_task():
    assert extract_items("Thanks @asha for the notes") == []
    assert extract_items("@rohan great work on the demo") == []


def test_discussion_lines_are_not_tasks():
    notes = """The deploy went out on time.
We spent the morning talking about onboarding.
Nobody could agree on whether it is the copy or the form.
"""
    assert extract_items(notes) == []


def test_non_action_sentence_start_is_not_an_owner():
    # "The team will send ..." -- "The" is not a person.
    assert extract_items("The team will send an update soon") == []
    assert extract_items("We will review the plan tomorrow") == []


def test_action_section_bullets_count():
    items = extract_items(
        "## Action items\n- Book the demo room\n- Order lunch\n",
        base=BASE,
    )
    assert [i.task for i in items] == ["Book the demo room", "Order lunch"]


def test_plain_section_heading_counts():
    items = extract_items("Next steps:\n- Ship the fix\n", base=BASE)
    assert [i.task for i in items] == ["Ship the fix"]


def test_bullet_outside_action_section_needs_a_signal():
    # A plain bullet with no marker, owner, or verb is just a note.
    assert extract_items("- The homepage is faster now\n") == []


def test_empty_and_blank_input():
    assert extract_items("") == []
    assert extract_items("\n\n   \n") == []


def test_line_numbers_and_source():
    items = extract_items("Intro line\n- [ ] do the thing\n", source="notes.md")
    assert items[0].line == 2
    assert items[0].source == "notes.md"


def test_due_date_stripped_from_task_text():
    item = first("- [ ] Book the demo room for Thursday")
    assert item.task == "Book the demo room"
    assert item.due == date(2026, 11, 26)


def test_checkbox_with_owner_prefix_stripped():
    item = first("- [ ] Krrish to send the Q3 report by Friday")
    assert item.owner == "Krrish"
    assert item.task == "send the Q3 report"
