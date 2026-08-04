# Report, plan and workspace formats

Every artifact `SKILL.md` Steps 4, 4b and 5 write. The rules governing *what goes in*
them are in SKILL.md; this file is the shapes.

## The condensed report — shown in chat

`.code-winnow/<stem>.md` holds the full version. Omit any section that is empty rather
than printing an empty heading.

```
## Winnow report
Generated: <YYYY-MM-DD HH:MM>
Scope: <diff source> — <current branch> vs <base / worktree / staged>
Files: <files> in scope, <scanned_files> reviewed; added lines: <added_lines>
Feature: <name> — <N> of <files> files          (omit when none was named)
Passes: S scope, A chaff, B comments, C docs+headers, D performance, E silent-failure
        (say which ran; if C or D was skipped, why; if S was self-drawn rather than
        dispatched, say that too)
Scope appeals: <n> — listed below, unresolved   (omit when none)
Conflict check: <n> dismissed on comment evidence, <n> merged, <n> upgraded,
        <n> deletions vetoed by E, <n> perf notes dropped
Performance notes: <n> — .code-winnow/<stem>.notes.md (not applied)
        (or: "D skipped — no loops or hot-path entry points in this diff")
Not fixable here: <n> P1/P2 findings reported but needing a design change   (omit when none)
Previous run: <prior stem, or "none">

### P1 — Risk (behavior, security, test integrity)
- `path/file.ext:LINE` — <what> → <why> → <proposed change>

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

Full report: .code-winnow/<stem>.md — say the word to expand any item.
Fix all, or tell me which.
```

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

`.code-winnow/<stem>.fixplan.md`. The handoff contract for all three Step 4b rungs.

````markdown
# Fix plan — currentfeature-dash_targetmain_20260802-2028

Status:   APPROVED by the user on 2026-08-02
Skill:    /home/me/.claude/skills/code-winnow
Scope:    12 files in diff, 3 in feature "dash cooldown"
Feature:  "winnow the dash cooldown work" — the user's own words, confirmed to mean
          src/Dash.cs, src/DashConfig.cs, src/PlayerInput.cs
Baseline: .code-winnow/currentfeature-dash_targetmain_20260802-2028.json
Backup:   .code-winnow/currentfeature-dash_targetmain_20260802-2028.pre-fix/
Undo:     cp -a .code-winnow/currentfeature-dash_targetmain_20260802-2028.pre-fix/. .
Verify:   dotnet test
Tests-before: (filled in by Step 5a, before the first edit)

## Code fixes — approved (delete a whole item to drop it)

- [ ] P1 bare catch swallows the cooldown reset
      file:     src/Dash.cs
      line:     88
      occurrence: 1
      of:         1
      anchor:   catch (Exception) { }
      fix:      narrow to InvalidOperationException, or let it propagate
      evidence: rewrite, nothing removed

- [ ] P2 `cachedRig` declared and never read; the comment above claims it is
      reserved but names no ticket — merged finding, both lines go
      file:     src/Dash.cs
      line:     41
      occurrence: 1
      of:         1
      anchor:   private Rig cachedRig;
      fix:      delete the field and the comment above it
      evidence: git grep -c cachedRig -- '*.cs'          -> 3 (all in src/Dash.cs)
                git grep -l cachedRig -- '*.prefab' '*.unity' -> (no output)
                not [SerializeField], not public, no attribute block

## Doc fixes — approved

- [ ] P2 the tuning guide still documents `Dash.Charge()`, renamed this change
      file:     docs/tuning.md
      line:     37
      occurrence: 1
      of:         2
      anchor:   Call `Dash.Charge()` before the cooldown elapses.
      fix:      rename to `Dash.BeginCharge()`
      evidence: rewrite, nothing removed
      falsified-by: src/Dash.cs:120

## Header fixes — approved separately at the Step 4 gate

- [ ] P2 no file header; repo convention is the Epic copyright line
      file:     src/DashConfig.cs
      line:     1
      occurrence: 1
      of:         1
      anchor:   using UnityEngine;
      fix:      insert the repo header above line 1
      evidence: sampled 40 first-party .cs files (Plugins/ and ThirdParty/
                excluded); 40/40 open with the same Epic line

## Never touch

- src/Dash.cs — `[SerializeField] tuningCurve`, referenced by Dash.prefab
- Any file not named by a `file:` line above
````

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

`.code-winnow/<stem>.notes.md`. Agent D's output goes here and nowhere else.

```markdown
# Performance notes — currentfeature-dash_targetmain_20260803-1420

Scope:    12 files in diff, 3 in feature "dash cooldown"
Source:   Agent D, judgment pass. Nothing here is in the fix plan.
Status:   NOT APPLIED — hypotheses, not approved changes.
Declined: 2 previously declined, not repeated

## Notes

- src/Grid.cs:22 — neighbour scan is O(n²)
  frequency:  once per FixedUpdate, 50/sec, over ~400 entities
  reasoning:  nested for over `entities` inside `entities`, neither bounded
  suggestion: spatial hash, or bail on the distance check first
  measured:   no
```

**Never write `- [ ]` and never write a `file:` line in this document.** Those are the
two tokens `scripts/backup.py` keys on to find fix items and the paths to back up, so a
notes document carrying either would parse as a fix plan — and a plan is a thing an
executor edits files from. The differing filename is the first guard, this is the
second, and `Status: NOT APPLIED` (not the `APPROVED` the script requires) is the third.
The failure is silent and irreversible where every other guard here costs a re-run.

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

Both persistent files survive Step 2's rotation because neither name starts with
`current`, which is the prefix the archive glob matches. A rename that gave either a
stem-shaped name would silently turn every settled answer back into an open question.
