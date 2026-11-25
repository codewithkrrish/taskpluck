# taskpluck

Pull the action items out of your meeting notes — owners, due dates and all — and hand you a checklist you can actually work from.

I kept ending meetings with pages of notes and no clear list of who was doing what by when. The notes were there, the tasks were buried in them. So I wrote the small tool I wished existed: point it at a notes file, get back a tidy checklist grouped by owner, sorted by due date, with the source line attached so you can check anything that looks off.

No dependencies, no setup, no account. One command.

## What it catches

taskpluck reads plain text and Markdown and picks up the ways people actually write tasks:

- Checkboxes: `- [ ] send the Q3 report by Friday` (done ones, `- [x]`, are skipped)
- Markers: `TODO:`, `ACTION:`, `Action item:`, `Follow up:`
- Owner + verb: `Krrish will send the report`, `Asha to review the deck`, `Rohan should update the runbook`
- Mentions: `@rohan please check the staging deploy`
- `Owner: Asha — finalise the interview loop` and `Krrish: chase the invoice`
- Plain bullets under an `Action items` / `Next steps` heading

Due dates come out of the text too: `by Friday`, `Dec 2`, `5 December 2026`, `2026-12-01`, `tomorrow`, `EOD`, `next Monday`, `in 3 days`. Relative dates are worked out from today, or from `--base-date` if you want a fixed reference.

It dedupes, too — the same item written in three different notes shows up once, and the first sighting keeps its source line. Discussion lines are left alone; a missed item is better than a made-up one.

## Install

```bash
pip install git+https://github.com/codewithkrrish/taskpluck.git
```

Python 3.9 or newer. Nothing else to install — the standard library does all of it.

## Usage

```bash
taskpluck notes.md
taskpluck standup.md retro.md        # several files at once
cat notes.md | taskpluck              # or pipe them in
taskpluck notes.md -o todos.md       # write the checklist to a file
taskpluck notes.md --format json     # machine-readable output
```

### Example

`examples/standup-notes.md` in, a checklist out:

```bash
$ taskpluck --base-date 2026-11-25 examples/standup-notes.md
```

```
# Action items

## Asha

- [ ] circulate the hiring plan — due 2026-11-30 — examples/standup-notes.md:24
- [ ] review the new onboarding copy — due 2026-12-02 — examples/standup-notes.md:16

## Krrish

- [ ] send the Q3 report — due 2026-11-27 — examples/standup-notes.md:15
- [ ] chase the vendor invoice — due 2026-12-01 — examples/standup-notes.md:21

## Rohan

- [ ] update the runbook — due 2026-11-26 — examples/standup-notes.md:23
- [ ] check the staging deploy — due 2026-11-27 — examples/standup-notes.md:22
- [ ] fix the login redirect bug — due 2026-11-30 — examples/standup-notes.md:17

## Unassigned

- [ ] Book the demo room — due 2026-11-26 — examples/standup-notes.md:19
```

### Flags

| Flag | What it does |
| --- | --- |
| `--format markdown\|json` | Output format (default: markdown) |
| `-o, --output PATH` | Write the checklist to a file instead of stdout |
| `--force` | Overwrite `--output` if it already exists (refuses without this) |
| `--dry-run` | With `--output`: show what would be written, write nothing |
| `--since YYYY-MM-DD` | Only keep items due on or after this date (undated items pass) |
| `--base-date YYYY-MM-DD` | Reference date for relative dates like "Friday" (default: today) |
| `--rollup week` | Group output by the ISO week of the due date |
| `--owner NAME` | Only keep items owned by NAME (case-insensitive) |

Exit codes: `0` items found, `1` no items found, `2` bad input or bad flags. Errors are plain messages on stderr, never tracebacks.

### JSON output

```json
[
  {
    "task": "send the Q3 report",
    "owner": "Krrish",
    "due": "2026-11-27",
    "source": "notes.md",
    "line": 4
  }
]
```

With `--rollup week`, each entry also gets a `"week"` field holding the Monday of its due week.

## How it decides what counts

A line has to earn its place: a checkbox, a marker, an owner with an action verb, a mention next to a verb or a date, or a bullet under an action heading. Everything else is treated as discussion. That keeps the output short and trustworthy, and it means the tool will miss tasks written in a form it does not recognise — I would rather it missed one than invented one.

## Limitations

- It reads notes line by line, so a task split across two lines is seen as two lines, not one task.
- It only understands English dates and verbs. "Kal report bhej dena" will not parse.
- Owner detection trusts capitalised names at the start of a line; unusual names and all-lowercase notes can confuse it.
- Dates without a year roll to next year if they already passed — usually what you want for a due date, but worth knowing.
- It never edits your notes. It only reads them and writes the checklist you ask for.

## Project structure

```
taskpluck/
├── taskpluck/
│   ├── cli.py        # flags, input/output, exit codes
│   ├── dates.py      # due-date parsing ("by Friday", "Dec 2", "in 3 days")
│   ├── dedup.py      # collapse repeats across files
│   ├── errors.py     # one user-facing error type
│   ├── extract.py    # line-by-line action-item detection
│   └── render.py     # Markdown and JSON output
├── tests/            # pytest, 59 tests
├── examples/         # real notes files to try it on
├── pyproject.toml
└── README.md
```

## Tests

```bash
python -m pytest tests/
```

59 tests, covering the date parser (ISO dates, month names, weekdays, "next Monday", relative dates), the extractor (every signal above, plus the lines that must *not* become tasks), dedup, both renderers, and the CLI end to end — missing files, bad dates, `--force`/`--dry-run` behaviour, corrupt input.

## License

MIT — see [LICENSE](LICENSE).

## Author

Krrish — [github.com/codewithkrrish](https://github.com/codewithkrrish)
