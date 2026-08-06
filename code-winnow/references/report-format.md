# Report, plan and workspace formats

Every artifact `SKILL.md` Steps 4, 4b and 5 write. The rules governing *what goes in*
them are in SKILL.md; this file is the shapes.

## Who the report is written for

**A competent programmer who has never run this skill and did not write the code.** That
is the whole standard, and it is the one thing about the report that is easy to get wrong
without noticing — you finish a run holding the entire vocabulary of the skill, and every
internal term reads as ordinary English from inside.

**None of this skill's private nouns appear above the audit block.** Not the agent letters
(`A`, `B`, `C`, `D`, `E`, `S`), not `conflict check`, `X9`, `merged`, `upgraded`,
`persisting`, `anchor`, `stem`, `worktree far side`, `prior_round`. They are precise and
they are meaningless to the reader — a finding they cannot parse is a finding they skip,
and the skimming this skill works hard to prevent arrives by the back door. Say the thing
instead: "two agents reported the same line, counted once" rather than "1 merged".

**The audit block may use them, because auditing is what it is for** — but it names each
one where it appears, so a reader who drops into it is not stuck.

**This applies to the fix plan's headlines too, and only its headlines.** The plan is the
one artifact with both audiences: `backup.py` parses `Status:` and `file:` and nothing
else, so the fields stay exactly as specified and are not written for anyone to enjoy —
but the headline above them is what the user reads when deciding whether to approve the
item, and an item they cannot parse is one they approve without reading or drop without
knowing what they dropped. Nothing else in the workflow reads a headline, so there is no
cost to making it plain.

**Nothing downstream reads `report.md`.** Steps 5 and 6 run off `fixplan.md`, `scan.json`,
`scan-postfix.json`, `meta.json` and `declined.json` — all machine-shaped and none of them
governed by this section. The report is written for the person, and writing it for the
person cannot slow the machine down.

## The condensed report — shown in chat

`.code-winnow/round-NN/report.md` holds the full version, in the same order. Omit any
section that is empty rather than printing an empty heading.

**The order is the point: the answer first, the evidence next, the audit last.** The
reader's question is "what about my code" and the run's bookkeeping is not it. Opening
with nine lines of scope, pass and conflict accounting spends their attention before they
learn anything — and the P1 is below it.

```
Round:     <NN>  —  .code-winnow/round-<NN>/
Compared:  <branch> @ <side>   vs   <base> @ <sha>   (<scope>)
Generated: <YYYY-MM-DD HH:MM>

## Winnow report

<Two to four sentences, plain language. What was reviewed, in ordinary terms; how much
was found and how serious the worst of it is; what you recommend doing. Someone who
has never run this skill and has not read this code should finish this paragraph
knowing whether they need to act, and roughly on what.>

**Needs a decision from you:** <one line each, or omit the whole line when none.
These are the only things that cannot wait: the header-convention question, an
unresolved scope appeal, a credential to rotate, a finding nobody could verify.>

### P1 — Risk (behavior, security, test integrity)
- `path/file.ext:LINE` — <what it breaks or costs, in ordinary terms> → <why the line
  is like that> → <the change proposed>

### P2 — Maintainability
### P3 — Cosmetic

### Header convention
- <the conflict, as a count and one sample — see the Step 4 gate>

### Author claims — confirm  (never severity-sorted, never cut for length)
- `path/file.ext:LINE` — <finding, at its original severity> — the comment says <quote>;
  could not verify because <the lookup you could not run>

### Deliberately left alone
- <looked like chaff, isn't, and why>

### In the diff, outside "<feature>"  (not swept)
- <one sentence: what it is> <one sentence: what it does>

### Pre-existing, in files this change touches
- <one sentence: what it is> <one sentence: what it does>

### No longer true since <prior report>
- <finding> — resolved

### In the prior report, not looked at this run  (omit when none)
- <finding> — its file was not in this run's scope; unexamined, not fixed

### Previously declined
- <finding> — raised <date>, declined

### How this run was made
<Skippable if you trust the result; this is what to read if you do not. Every count
below is reported even when it is zero — an omitted number reads as though the check
was never made.>

Scope: <diff source> — <current branch> vs <base / worktree / staged>
Files: <files> in scope, <scanned_files> reviewed; added lines: <added_lines>
Feature: <name> — <N> of <files> files          (omit when none was named)
Reviews run: <name each pass in words, not letters — a code pass, a comments pass, a
        docs-and-headers pass, a performance pass, a silent-failure pass, and the
        scope pass when a feature was named. Say which ran; if the docs or
        performance pass was skipped, why; if the scope boundary was drawn by the
        orchestrator rather than a separate reviewer, say so plainly, because it is
        the one decision a reader should distrust; and if any pass ran on a smaller
        model, name it — a reader judging a thin result needs to know>
Merging the reviews: <n> findings dismissed because a comment in the code explained
        the line, <n> reported by two reviews and counted once, <n> made more serious
        after a lookup, <n> proposed deletions overruled as load-bearing, <n>
        performance notes dropped
Scope appeals: <n> — listed above, unresolved   (omit when none)
Performance notes: <n> — round-NN/notes.md (never applied)
        (or: "performance pass skipped — no loops or hot-path entry points in this diff")
Not fixable here: <n> P1/P2 findings reported but needing a design change   (omit when none)
Previous run: <prior round, or "none">

Full report: .code-winnow/round-NN/report.md — say the word to expand any item.
Fix all, or tell me which.
```

**The first three lines are mandatory on every markdown file a round writes** —
`report.md`, `fixplan.md`, `notes.md` and every `agent-*.md`. Filenames inside a round
are short and identical every round, so they say nothing about what was reviewed; this
block is where that fact lives. Copy the values out of `round-NN/meta.json` rather than
retyping them.

Every count in that header comes out of the JSON: `files`, `scanned_files`,
`added_lines`. When `scanned_files < files`, say which ones were skipped and why.

Out-of-feature findings are reported top three by severity plus a count, two sentences
each, no proposed patches:

```
### In the diff, outside "dash cooldown"  (not swept)
- `Inventory.cs:22` — Bare `except` around the reload path. Converts a failed reload
  into a silent empty inventory.
- `UIPanel.cs:9` — Field `pendingRefresh` declared and never read.
- ...and 6 more. Say the word for a full pass over these.

9 files in the diff were not reviewed — scanner only, plus whatever the agents
noticed in passing. Findings there are incidental, not a coverage claim.
```

## The header convention gate — the question, quoted in full

```
Header convention: the 9 new .cs files in this diff carry no file header. The repo's
other 214 first-party .cs files open with:  // Copyright 2019 Acme Ltd. All rights reserved.
  1. Add that header verbatim to those 9 files — its own section in the fix plan
  2. Report only, change nothing
```

Past ten files, do not offer option 1 at all — say *"N of the files this change adds
carry no header; want a header pass as its own change?"* and stop.

## The fix plan

`.code-winnow/round-NN/fixplan.md`. The handoff contract for all three Step 4b rungs.

**The shape is the template at `scaffold/round/fixplan.md`.** Step 2 already copied it
into the round, so fill that file rather than composing one from memory. What a skeleton
cannot carry lives here.

An unattended plan's header reads `Status: UNAPPROVED — no human reviewed these
findings`, and every section heading says *proposed*, not *approved*.

Anchors are written **unquoted and unfenced**. Backticks inside a value break the
moment an anchor contains a backtick, which doc fixes routinely do.

### `tests-delta:` — on any item that changes what the suite collects

```
- [ ] P2 three tests differ only in the timeout literal — parametrize them
      file:        tests/test_retry.py
      line:        12
      occurrence:  1
      of:          1
      anchor:      def test_retry_at_one_second():
      fix:         merge into @pytest.mark.parametrize with the three values
      evidence:    rewrite, coverage preserved — same three cases, one body
      tests-delta: -3 test_retry_at_one_second, test_retry_at_five_seconds,
                   test_retry_at_thirty_seconds
                   +3 test_retry_timeout[1], [5], [30]
```

Net zero there — parametrize expands at collection — which is why the field states both
sides rather than a number. A merge that quietly drops a case shows up as `-3 +2`.

## The performance notes document

`.code-winnow/round-NN/notes.md`. Agent D's output goes here and nowhere else.
**The shape is the template at `scaffold/round/notes.md`.**

**Never write `- [ ]` and never write a `file:` line in this document.** Those are the
two tokens `scripts/backup.py` keys on to find fix items and the paths to back up, so a
notes document carrying either would parse as a fix plan — and a plan is a thing an
executor edits files from. The differing filename is the first guard, this is the
second, and `Status: NOT APPLIED` (not the `APPROVED` the script requires) is the third.
The failure is silent and irreversible where every other guard here costs a re-run.

`notes.md` and `fixplan.md` are now siblings in one directory rather than separated by a
long stem, so any `round-NN/*.md` glob sweeps both. The differing filename is still the
first of the three guards; it is simply no longer the obvious one.

Write the document even when D found nothing — an empty Notes section and a line saying
the pass ran. When D was not dispatched at all, write no document and say so in the
report header instead.

## `declined.json` — persistent across runs

Scanner-report shape. Append the finding object exactly as the scanner emitted it;
`path`, `rule`, `message` and `anchor` are the key, kept verbatim. `line` is ignored in
matching, so declined items survive the line shifts other deletions cause.

```json
{ "findings": [
  { "path": "src/Foo.cs", "line": 88, "severity": "P2", "rule": "unused-binding",
    "message": "'cachedRig' is declared and never referenced in this file",
    "anchor": "private Rig cachedRig;" }
] }
```

## `perf-declined.md` — persistent across runs

D produces notes from judgment rather than a scanner rule, so `--since` and
`declined.json` cannot reach them.

```markdown
# Declined performance notes

Persistent across runs. Delete an entry to re-open the question.
Matched on path plus anchor text; the line number is ignored, because lines shift.

- src/Dash.cs | GetComponent<Rigidbody>() in Update
  declined 2026-08-03 — profiled at 0.02ms, not hot
- src/Boot.cs | config parsed twice at startup
  declined 2026-08-03 — startup only, don't care
```

Both persistent files stay at the workspace root, and that no longer rests on an
accident. It used to depend on neither name starting with `current`, the prefix the
archive glob matched; nothing globs the root now, so it is structural. That is what
makes "declined" mean *permanently* declined.
