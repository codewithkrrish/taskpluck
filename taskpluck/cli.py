"""taskpluck -- pull action items out of meeting notes.

Usage:
    taskpluck notes.md                # checklist on stdout
    taskpluck standup.md retro.md     # several files at once
    cat notes.md | taskpluck           # or pipe them in
    taskpluck notes.md -o todos.md    # write the checklist to a file
    taskpluck notes.md --format json  # machine-readable output

Exit codes: 0 items found, 1 no items found, 2 input or usage error.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import date

from .dates import week_start
from .dedup import dedupe
from .errors import TaskpluckError
from .extract import extract_items
from .render import render_json, render_markdown

__version__ = "1.0.0"


def _parse_iso_date(value: str, flag: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise TaskpluckError(f"{flag}: {value!r} is not a YYYY-MM-DD date")


def _read_input(path: str) -> tuple[str, str]:
    """Return (text, display name) for a file, or stdin for '-'."""
    if path == "-":
        return sys.stdin.read(), "<stdin>"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read(), path
    except FileNotFoundError:
        raise TaskpluckError(f"no such file: {path}")
    except IsADirectoryError:
        raise TaskpluckError(f"{path} is a directory, not a notes file")
    except OSError as exc:
        raise TaskpluckError(f"cannot read {path}: {exc.strerror or exc}")


def _write_atomic(path: str, content: str) -> None:
    """Write via a temp file in the same directory, then rename."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(prefix=".taskpluck-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    except OSError:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="taskpluck",
        description="Pull action items out of meeting notes and transcripts.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="notes files to mine (default: read stdin; use - for stdin)",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="output format (default: markdown)",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="PATH",
        help="write the checklist to PATH instead of stdout",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite --output if it already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --output: show what would be written, write nothing",
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="only keep items due on or after this date (undated items pass)",
    )
    parser.add_argument(
        "--base-date",
        metavar="YYYY-MM-DD",
        help="reference date for relative dates like 'Friday' (default: today)",
    )
    parser.add_argument(
        "--rollup",
        choices=("none", "week"),
        default="none",
        help="group output by the ISO week of the due date",
    )
    parser.add_argument(
        "--owner",
        metavar="NAME",
        help="only keep items owned by NAME (case-insensitive)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    base = date.today()
    if args.base_date:
        base = _parse_iso_date(args.base_date, "--base-date")
    since = _parse_iso_date(args.since, "--since") if args.since else None

    paths = args.files or ["-"]
    if paths == ["-"] and sys.stdin.isatty():
        print(
            "taskpluck: no input -- pass a notes file or pipe notes in "
            "(taskpluck notes.md)",
            file=sys.stderr,
        )
        return 2

    items = []
    for path in paths:
        text, source = _read_input(path)
        items.extend(extract_items(text, source=source, base=base))

    items = dedupe(items)
    if since is not None:
        items = [i for i in items if i.due is None or i.due >= since]
    if args.owner:
        wanted = args.owner.lower()
        items = [i for i in items if (i.owner or "").lower() == wanted]
    if args.rollup == "week":
        for item in items:
            item.week = week_start(item.due) if item.due else None

    if not items:
        print("taskpluck: no action items found", file=sys.stderr)
        return 1

    rollup = args.rollup == "week"
    output = (
        render_json(items, rollup_week=rollup)
        if args.format == "json"
        else render_markdown(items, rollup_week=rollup)
    )

    if args.output:
        if os.path.exists(args.output) and not args.force:
            raise TaskpluckError(
                f"{args.output} already exists -- use --force to overwrite it"
            )
        if args.dry_run:
            print(f"# dry run: would write {len(items)} items to {args.output}",
                  file=sys.stderr)
            print(output, end="")
            return 0
        _write_atomic(args.output, output)
        print(
            f"taskpluck: wrote {len(items)} action items to {args.output}",
            file=sys.stderr,
        )
        return 0

    if args.dry_run:
        print("taskpluck: --dry-run needs --output; showing output instead",
              file=sys.stderr)
    print(output, end="")
    return 0


def main() -> int:
    """Entry point: turn our own errors into a human message, exit 2."""
    try:
        return run()
    except TaskpluckError as exc:
        print(f"taskpluck: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
