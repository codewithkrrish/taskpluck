"""Pull action items out of meeting notes.

The extractor works line by line. A line becomes an action item when it
carries at least one clear signal:

* a Markdown checkbox: ``- [ ] send the report``
* an explicit marker: ``TODO:``, ``ACTION:``, ``Follow up:``
* an owner plus a future-tense verb: ``Krrish will send the report``,
  ``Asha to review the deck by Friday``
* an ``@mention`` next to an action verb or a due date
* a plain bullet sitting under an "Action items" / "Next steps" heading

Anything else is discussion, not a task, and is left alone. The aim is
fewer, trustworthy items -- a missed item is better than a made-up one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .dates import parse_due_date

__all__ = ["ActionItem", "extract_items"]

# Verbs that turn a sentence into something somebody has to do. Deliberately
# narrow: "will be on leave" is not a task, "will send the report" is.
ACTION_VERBS = {
    "send", "share", "write", "draft", "review", "prepare", "fix", "update",
    "check", "call", "email", "schedule", "book", "deliver", "confirm",
    "deploy", "merge", "test", "file", "create", "build", "design", "ship",
    "follow up", "chase", "ping", "organise", "organize", "publish",
    "upload", "investigate", "look into", "set up", "finish", "complete",
    "submit", "present", "circulate", "finalise", "finalize", "approve",
    "sign off", "arrange", "coordinate", "message", "notify", "remind",
    "close", "open", "raise", "log", "track", "escalate", "revert",
    "clean", "migrate", "document", "record", "compile", "summarise",
    "summarize", "analyse", "analyze", "audit", "verify", "validate",
}

# Words that look like a name at the start of a line but never are one.
_NOT_A_NAME = {
    "The", "We", "I", "You", "Everyone", "Team", "All", "Please", "Note",
    "Also", "This", "That", "It", "Action", "Next", "Meeting", "Sprint",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
    "Sunday", "Today", "Tomorrow", "Yesterday", "Agenda", "Notes",
    "Discussion", "Decisions", "Attendees", "Follow", "Todo", "TODO",
}

_NAME = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)"
_VERB = (
    r"(?:send|share|write|draft|review|prepare|fix|update|check|call|email|"
    r"schedule|book|deliver|confirm|deploy|merge|test|file|create|build|"
    r"design|ship|follow\s+up|chase|ping|organise|organize|publish|upload|"
    r"investigate|look\s+into|set\s+up|finish|complete|submit|present|"
    r"circulate|finalise|finalize|approve|sign\s+off|arrange|coordinate|"
    r"message|notify|remind|close|open|raise|log|track|escalate|revert|"
    r"clean|migrate|document|record|compile|summarise|summarize|analyse|"
    r"analyze|audit|verify|validate)"
)

_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_CHECKBOX_RE = re.compile(r"^\s*[-*+]\s+\[( |x|X)\]\s+(.*)$")
_MARKER_RE = re.compile(
    r"^\s*(?:TODO|FIXME|ACTION\s+ITEM|ACTION|FOLLOW[\s-]?UP)\s*[:\-–—]\s*(.+)$",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_PLAIN_SECTION_RE = re.compile(
    r"^(action items?|next steps|to-?dos?|follow[\s-]?ups?|open items)\s*:?\s*$",
    re.IGNORECASE,
)
_MENTION_RE = re.compile(r"@([A-Za-z][\w.-]*)")
# "Krrish will send ..." / "Asha to review ..." / "Rohan should fix ..."
_OWNER_VERB_RE = re.compile(
    r"^" + _NAME + r"\s+(?:to|will|should|needs?\s+to|must|is\s+going\s+to)\s+"
    + _VERB + r"\b",
    re.IGNORECASE,
)
# Same shape as _OWNER_VERB_RE but stops before the verb, so the "Krrish to "
# part can be stripped from the task text while the verb stays.
_OWNER_PREFIX_RE = re.compile(
    r"^" + _NAME + r"\s+(?:to|will|should|needs?\s+to|must|is\s+going\s+to)\s+",
    re.IGNORECASE,
)
# "Owner: Krrish -- send the report" / "Assigned to: Asha"
_OWNER_FIELD_RE = re.compile(
    r"(?:Owner|Assigned to|Assignee|Responsible)\s*:\s*" + _NAME, re.IGNORECASE
)
# "Krrish: send the report by Friday"
_NAME_COLON_RE = re.compile(r"^" + _NAME + r"\s*:\s+(.+)$")
_VERB_WORD_RE = re.compile(_VERB, re.IGNORECASE)
_TRAILING_JUNK_RE = re.compile(r"[\s,;:\-–—]+$")


@dataclass
class ActionItem:
    """One thing somebody has to do, found in a note."""

    task: str
    owner: str | None = None
    due: date | None = None
    source: str = "<stdin>"
    line: int = 0
    raw: str = ""
    # Filled in by the CLI when --rollup week is on; not part of identity.
    week: date | None = field(default=None, compare=False)


def _clean_task(text: str, base: date) -> tuple[str, date | None]:
    """Strip a due-date phrase out of the task text and return both."""
    due, span = parse_due_date(text, base)
    if span is not None:
        text = text[: span[0]] + text[span[1]:]
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = _TRAILING_JUNK_RE.sub("", text).strip()
    # A dangling "by" / "due" / "for" left behind when the date sat at the end.
    text = re.sub(
        r"\s+(?:by|due|before|until|for|on)$", "", text, flags=re.IGNORECASE
    )
    text = re.sub(r"^please\s+", "", text, flags=re.IGNORECASE)
    return text, due


def _strip_owner_prefix(text: str, owner: str | None) -> str:
    """Drop a leading "Krrish to " / "Krrish: " from the task text.

    The owner is shown separately in the output, so keeping it in the
    task would read twice ("Krrish -- Krrish to send the report").
    """
    if owner is None:
        return text
    prefix = _OWNER_PREFIX_RE.match(text)
    if prefix and prefix.group(1).lower() == owner.lower():
        return text[prefix.end():]
    colon = _NAME_COLON_RE.match(text)
    if colon and colon.group(1).lower() == owner.lower():
        return text[colon.end(1) + 1:].lstrip()
    return text


def _strip_mention(text: str, owner: str | None) -> str:
    """Drop "@owner" from the task text when the owner came from a mention."""
    if owner is None:
        return text
    stripped = re.sub(
        r"@" + re.escape(owner) + r"\b", "", text, flags=re.IGNORECASE
    )
    return re.sub(r"\s{2,}", " ", stripped).strip()


def _owner_from_text(text: str) -> str | None:
    """Best-guess owner for a line, or None."""
    mention = _MENTION_RE.search(text)
    if mention:
        name = mention.group(1)
        return name[:1].upper() + name[1:]
    field = _OWNER_FIELD_RE.search(text)
    if field:
        return field.group(1)
    verb_owner = _OWNER_VERB_RE.match(text)
    if verb_owner:
        return verb_owner.group(1)
    colon = _NAME_COLON_RE.match(text)
    if colon and colon.group(1) not in _NOT_A_NAME:
        return colon.group(1)
    return None


def _has_action_verb(text: str) -> bool:
    return _VERB_WORD_RE.search(text) is not None


def _is_plausible_name(name: str) -> bool:
    first = name.split()[0]
    return first.lower() not in {word.lower() for word in _NOT_A_NAME}


def _line_to_item(
    line: str, source: str, lineno: int, base: date, in_action_section: bool
) -> ActionItem | None:
    stripped = line.strip()
    if not stripped or len(stripped) < 3:
        return None

    checkbox = _CHECKBOX_RE.match(line)
    if checkbox:
        if checkbox.group(1).strip():
            return None  # [x] -- already done, not an action item any more
        body = checkbox.group(2)
        owner = _owner_from_text(body)
        body = _strip_owner_prefix(body, owner)
        body = _strip_mention(body, owner)
        task, due = _clean_task(body, base)
        return ActionItem(task, owner, due, source, lineno, stripped) if task else None

    marker = _MARKER_RE.match(line)
    if marker:
        body = marker.group(1)
        owner = _owner_from_text(body)
        body = _strip_owner_prefix(body, owner)
        body = _strip_mention(body, owner)
        task, due = _clean_task(body, base)
        return ActionItem(task, owner, due, source, lineno, stripped) if task else None

    body = _BULLET_RE.sub("", line).strip()

    # "Krrish will send the report" / "Asha to review the deck"
    owner_verb = _OWNER_VERB_RE.match(body)
    if owner_verb and _is_plausible_name(owner_verb.group(1)):
        body = _strip_owner_prefix(body, owner_verb.group(1))
        task, due = _clean_task(body, base)
        return ActionItem(task, owner_verb.group(1), due, source, lineno, stripped)

    # "Owner: Krrish -- send the report"
    owner_field = _OWNER_FIELD_RE.search(body)
    if owner_field and _is_plausible_name(owner_field.group(1)):
        task, due = _clean_task(
            _OWNER_FIELD_RE.sub("", body).strip(" -–—"), base
        )
        if task:
            return ActionItem(task, owner_field.group(1), due, source, lineno, stripped)

    # "Krrish: send the report by Friday"
    colon = _NAME_COLON_RE.match(body)
    if colon and _is_plausible_name(colon.group(1)):
        rest = colon.group(1)  # the name
        remainder = colon.group(2)
        if _has_action_verb(remainder) or parse_due_date(remainder, base)[0]:
            task, due = _clean_task(remainder, base)
            if task:
                return ActionItem(task, rest, due, source, lineno, stripped)

    # "@asha please review the deck" -- needs a verb or a date, so a plain
    # thank-you mention does not become a task.
    mention = _MENTION_RE.search(body)
    if mention:
        if _has_action_verb(body) or parse_due_date(body, base)[0]:
            without_mention = _MENTION_RE.sub("", body).strip()
            task, due = _clean_task(without_mention, base)
            if task:
                owner = _owner_from_text(body)
                return ActionItem(task, owner, due, source, lineno, stripped)

    # A bare bullet under an "Action items" heading counts on its own.
    if in_action_section and _BULLET_RE.match(line):
        owner = _owner_from_text(body)
        body = _strip_owner_prefix(body, owner)
        body = _strip_mention(body, owner)
        task, due = _clean_task(body, base)
        if task:
            return ActionItem(task, owner, due, source, lineno, stripped)

    return None


def extract_items(
    text: str, source: str = "<stdin>", base: date | None = None
) -> list[ActionItem]:
    """Extract action items from ``text`` (plain text or Markdown)."""
    base = base or date.today()
    items: list[ActionItem] = []
    in_action_section = False

    for lineno, line in enumerate(text.splitlines(), start=1):
        heading = _HEADING_RE.match(line)
        if heading:
            in_action_section = bool(_PLAIN_SECTION_RE.match(heading.group(1).strip()))
            continue
        if _PLAIN_SECTION_RE.match(line.strip()):
            in_action_section = True
            continue
        # A new heading-like line that is not an action section ends it;
        # so does a blank line followed by non-bullet prose -- handled
        # implicitly, since only bullets count inside a section.
        item = _line_to_item(line, source, lineno, base, in_action_section)
        if item is not None:
            items.append(item)

    return items
