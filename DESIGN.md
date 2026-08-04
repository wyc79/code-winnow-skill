# Design notes

Why the mechanical parts of `code-winnow/SKILL.md` are written the way they are. Every
entry is a near-miss: a form that reads correctly, does something else, and fails
silently. Agents executing the skill do not need this file. Maintainers editing the
snippets do — each of these was a shipped defect, and the obvious simplification
reintroduces it.

`SKILL.md` keeps the rationale for rules an agent will argue itself out of under
pressure — scope discipline, "an unattended run never edits", the `evidence:` field,
"do not judge your own output". Those arguments are load-bearing at execution time.
Everything below is load-bearing only at edit time.

---

## Step 0 — the exclusion block

**`--git-common-dir`, not `--git-dir`.** Git reads `info/exclude` from the *common*
directory. In a linked worktree `--git-dir` returns `.git/worktrees/<name>/`, a rule
written there is silently ignored, and `git check-ignore` still says not-ignored — so
the setup this most needs to handle is the one it fails silently. Submodules are fine
either way.

**`printf '\n.code-winnow/\n'`, not `echo`.** If `info/exclude` does not end in a
newline — common, since editors append without one — `echo >>` concatenates onto the
last line: a file ending `build/` becomes `build/.code-winnow/`, which **destroys the
user's rule and excludes nothing.** Git ignores blank lines in exclude files, so the
leading `\n` is free.

**`mkdir -p ... .code-winnow`.** Nothing else creates it — the scanner writes no files
at all — and the first `> .code-winnow/...` redirect in Step 3 fails with *No such file
or directory*, taking the review input, the report, the baseline JSON, the fix plan and
the backup with it.

**Why the local exclude file rather than `.gitignore`.** `.gitignore` is tracked, so
editing it puts the file into the very diff this skill is about to review. The local
exclude file is never committed and never shows up in a diff.

**Why the verification line matters.** An unexcluded workspace means the judgment agents
are handed your own reports and backups as review input, and `git add -A` commits them —
on a run whose headline trigger is "clean this up before I commit".

## Step 1 — scope resolution

**Quote `WINNOW`.** Unquoted, bash eats every backslash: `WINNOW=C:\Users\me\skills`
becomes `C:Usersmeskills`, and a path with a space fails outright. This skill's headline
tuning is C#/Unity, so Windows paths are the common case, and every later
`"$WINNOW/scripts/scan.py"` and every reference path handed to the agents is silently
garbage.

**Test the interpreter, do not just locate it.** `command -v python3` returns the
Microsoft Store stub, which is on `PATH`, prints an install advert to stderr, and exits
49. A bare `command -v` chain "succeeds" and every scanner call then fails. Running
`"$c" -c ""` is the difference between present and working — verified on a machine where
`command -v python3` resolves the stub.

**Pin the scope flags and pass them on every later call.** Each omission silently
reviews a different thing: `--report-name` without them stamps a `_worktree_` stem onto
a `--scope branch` review, and the Step 4 baseline and the Step 6 reconciliation then
scan the wrong scope entirely while still producing a confident report. Step 2 writes
them to `env.sh` so no later block has to remember.

**Why the scanner resolves scope rather than a hand-rolled `git diff` ladder.**
Untracked files are invisible to `git diff` in every mode, and brand-new files are
exactly where generated code concentrates. A stop-at-first-non-empty ladder reviews the
staged fraction of a partially-staged branch and reports full confidence.

**Why a typo'd `--base` needs the four-field check.** `--base develp` finds no such ref,
records it in `warnings`, and returns an empty scope — which prints as a clean branch.
An empty `findings` with a non-empty `warnings` is a scan that did not happen.

**Why the feature scope is not computed up front.** Two failures, at both ends. *Hunk
ordinals mean different things to different readers* — a hunk is an artifact of how much
context the diff was rendered with. The scanner reads `git diff --unified=0`; the Step 3
agents read `-U3`. Two changes three lines apart are **one** hunk to the agents and
**two** to the scanner, and at `-U3` an unrelated typo fix two lines from a feature
change merges into the same hunk with no way to say "half of hunk 1". *And the user was
not thinking in code structure* — "the retry logic", "the parts touching the save
system" are not symbol names, and matching them by text against identifiers gets both
false hits and misses.

**Why `--paths` is not the tool for splitting a large diff.** It scans whole files,
marks every line as added, sets `preexisting: false` on everything, and stamps a
`_files_` stem that no longer reconciles against the prior run. Splitting that way
converts a diff review into the repo audit this skill exists to refuse.

**Why splits are on file boundaries.** A file handed to two agents gets two partial
views of code that has to be judged whole — a helper duplicated at the top and used at
the bottom is invisible to both — and neither agent can tell the other half exists.

**Why a feature-scoped run must not narrow `<stem>.json`.** The next run's `--since`
would compare a full baseline against a narrow one and report every out-of-feature
finding as `resolved` — a page of "no longer true" claims about findings that are all
still true. Same defect as running `--min-severity` before reconciliation, which is why
the filter lives at the report layer and touches nothing the scanner writes.

## Step 2 — the stem, the archive, and `env.sh`

**Why the stem is captured once.** Steps 3, 4 and 6 all write files named from it, and
each invocation stamps its own clock, so a run crossing a minute boundary ends up with
filenames that disagree.

**Why stderr is kept when capturing the stem.** A `REFUSING:` line arrives there and
also yields no stem, so a guard that only knows about empty scopes overwrites the one
message that explains what happened — and then advises retrying with `--base`, which
Step 1 says explicitly not to do.

**Why rotation lives in Step 2 and not Step 0.** Cold entry at Step 5 re-runs Step 0, and
rotating there would archive the fix plan the cold session was invoked to execute.

**Why `declined.json` and `perf-declined.md` survive rotation.** The archive glob matches
`current*`, the stem prefix. Neither persistent file starts with `current`, which is what
makes "declined" mean *permanently* declined rather than "declined until the next run
archives the record".

**Why `env.sh` exists at all.** Shell state does not survive between tool calls —
variables set in one call are empty in the next, and each snippet is its own call.
Without it `$STEM` and `$WINNOW` are empty three steps later and the run writes
`.code-winnow/.input.diff`, invokes `"/scripts/scan.py"`, and backs up to
`.code-winnow/.pre-fix` — each failing quietly or colliding with every other run.

**Why values are appended with `%q`.** So a path containing a space, a backslash or an
apostrophe survives being re-sourced.

**Why `snapshot()` goes in the file rather than being defined in the block.** It is
compared in later blocks and by dispatched agents, and a shell function no more survives
a tool call than a variable does. Defined only in Step 2, the check silently passes (both
sides empty) or fires unconditionally (`snapshot: command not found`).

**Why `SNAPSHOT` hashes content, `HEAD`, and untracked blobs.** *Content, not
`git status`* — status reports which files changed, not what is in them, so appending a
line to an already-untracked file leaves the stamp identical. *`HEAD`* — without it a
clean-tree branch review hashes two empty inputs and yields the empty-blob hash
`e69de29b…`, the same constant in every repo on earth, so amends and rebases go invisible
in exactly the scope where every line number moves.

**Why the empty case needs a guard.** On a clean tree with no branch diff,
`--report-name` exits non-zero with empty stdout. `$STEM` becomes the empty string,
`$BACKUP` becomes `.code-winnow/.pre-fix`, every run writes to the same filenames, and
successive runs overwrite each other.

**Why the baseline JSON is written in Step 2, not Step 4.** Step 3 hands it to every
judgment agent, so it has to exist before they are dispatched.

## Step 3 — the review input

**Diff to the worktree, not to `HEAD`.** The scanner reads every file from disk, so its
findings, line numbers and anchors describe the working tree. A commit-to-commit
`$BASE...HEAD` describes something else the moment the tree is dirty — which under
`--scope branch` is most of the time. The agents then review a diff that omits changes
the scanner scanned, while holding a JSON whose line numbers came from content the diff
never showed. Both halves are silent: the `-s` check passes because the file is large,
just wrong, and `SNAPSHOT` compares the tree against itself over time rather than `HEAD`
against the worktree. Measured on this skill's own repo, the two forms differed by 4 KB
and by whether the change under review appeared at all.

Three dots is still right on the *base* side — it is the merge base, so commits that
landed on the base after you branched do not appear as your changes. `git merge-base`
gets that without pinning the head side to the last commit. The scanner resolves
`--scope branch` the same way, for the same reason; they did not always, and a single
uncommitted insert above a finding was enough to drop it from a `complete: true` report,
then have the next `--since` run print it as resolved.

**Branch on what the scanner reports, not the flag you passed.** `--scope auto` falls
back to the branch diff on its own whenever the tree is clean, so a reviewer one commit
ahead never passes `--scope branch` and still gets a branch review. Build the input from
`git diff HEAD` in that state and it is empty — every agent receives nothing, reports
nothing to review, and the run looks clean while the scanner holds a P1.

**The `-s` check.** Whatever new way this breaks, an empty review file must never reach a
fan-out of agents that will each confidently report nothing.

**The `|| git diff --cached` fallback.** On a repo with staged files and no commit yet,
`git diff HEAD` is fatal — there is no `HEAD` — but the `{ }` group still exits 0 and the
redirect still creates an empty file. That state is a fresh repo mid-first-commit, which
is this skill's headline trigger.

**Skipping `.code-winnow/`.** The scanner hard-skips its own workspace, but this builder
is a separate path and it is the half that reaches an agent. If Step 0's exclusion ever
fails, `ls-files --others` sweeps in your own reports and the pre-fix backups of the
source you just cleaned, and presents them to the judgment agents as new-file content.

**Naming what was excluded rather than dropping it.** The scanner has a vendor filter, a
size cap and a binary check; this builder had none of them, so it `cat`-ed whatever
`ls-files --others` returned. One untracked PNG — a new sprite, a prefab, a `.meta` file,
which in a Unity or UE5 repo is the *normal* content of a change — produced a 230 KB
review input that was not valid UTF-8, and the `-s` check passed because the file was
large. An omission an agent cannot see is the same silent-coverage failure the scanner's
`errors` array exists to prevent.

**Why `git diff --name-only HEAD` rather than the scanner JSON for a cross-check.** The
JSON carries a `files` *count*, not a path list, and `findings[].path` only names files
that produced a finding — so every clean file in scope silently vanishes from such a
check.

## Step 4 — reporting and reconciliation

**The truncation trap.** `--since X.json --json > X.json` truncates the baseline before
Python opens it, so `--since` reads an empty file and reports zero resolutions. New name
out, baseline in.

**Why `$STEM.json` is excluded when searching for a prior baseline.** Step 2 writes it
before the agents are dispatched, so by Step 4 it *is* the newest JSON for this scope —
reconcile against it and every finding comes back `persisting`, `resolved` is empty, and
the report names this run as its own previous run.

**Why the scope segment must match too.** A stem carries its scope precisely so this
comparison can be made, and `ls -1t` alone does not make it. Comparing a branch baseline
against a worktree run reports differences that are only differences of scope.

**Why `out_of_scope` is a separate array from `resolved`.** The flow that produced the
false claim is the ordinary one — winnow, commit part of it, winnow again while the tree
is still dirty — and the committed file's live P1s came back as "no longer true".

**Why "absent" has to mean gone rather than merely unprinted.** A finding this report
filters out but that is still true appears as neither live nor resolved, because "out of
this report's scope" and "fixed" are different facts and only the second is news.

**Why declining needs its own file.** The finding is still true, so the scanner keeps
producing it, and without somewhere to record the answer it returns as `persisting` on
every run.

**Why the header gate routes license findings that arrive as truth findings.** The gate
was written for the convention branch, so a finding phrased as truth — "this new file
says `SPDX-License-Identifier: GPL-3.0-only`, but the repo is MIT" — would otherwise land
in "Doc fixes — approved" as an ordinary P2 with a proposed rewrite and get swept up by
"fix all". Silently relicensing a vendored file is a strictly worse version of the thing
the gate exists to prevent, arriving through the ungated door.

**Why the header gate needs a count cap as well as diff membership.** A scaffolded change
that adds 200 files makes all 200 eligible, and a one-line API sweep across 150 files
makes all 150 "modified". Diff membership limits *which* files; only a count limits *how
many*.

**Why "touched" includes lines the change took away.** Delete a generated test's only
assertion and every surviving line is untouched, so the now-assertionless test files as
pre-existing and drops out of the default run. The change created a P1 and the scan
reports nothing.

## Step 4b — the plan and the locating rules

**`file:` is authoritative, not the prose.** Put the path inside the summary sentence and
have the backup parse it back out, and you lose paths containing spaces, items with no
`:LINE`, the second file of every merged finding, and anything indented under a
sub-heading — while printing a success count derived from the same regex that just missed
them. Prose is not a data format, and a backup that under-collects silently is worse than
no backup at all.

**Why `occurrence:` and `of:` come from `anchor_index`/`anchor_total` and never from the
JSON's `occurrence`.** That field indexes findings sharing a rule and message, so a
diff-scoped run stamps 1 on the only instance the change touched even when the anchor is
on three lines and the flagged one is the third. Copying it hands the executor an ordinal
measured on a different population, and the fallback locating rule then edits the first
matching line: untouched, unreviewed, unapproved code.

**Why `of:` is required as a denominator.** An ordinal alone is satisfied by any file with
at least that many matches, so a re-run finds the *declined* twin of an already-applied
fix and edits the one line the user refused — and a newly written `catch` above the target
shifts every ordinal down by one. Two matches at plan time and one now means something was
deleted; three means something was added; either way the ordinal no longer identifies what
it identified.

**Why normalisation is required before comparing.** The anchor came from the scanner's
`normalise_anchor`, which collapses every run of whitespace to one space, strips the ends,
and truncates to 120 characters. `of:` was counted under that same normalisation, so
comparing raw lines reaches a different total and every moved item reports stale.

**Why `evidence:` is a field and not a fourth reviewing agent.** Every reference file
already said to verify before deleting, and that instruction sat inside a long agent
prompt competing with everything else in it. Nothing downstream could tell a finding whose
lookups were done from one where they were skipped, and both arrive worded with equal
confidence. Another opinion does not make a lookup happen. A required field does.

**Why `tests-delta:` exists.** This skill removes tests on purpose — merging structural
duplicates, dropping a fixture nothing requests — and those moves are legitimate. Without
the field, Step 6 cannot distinguish an approved removal from an accidental one, and the
honest reading of a smaller suite would be "restore everything", which would block
legitimate work every time the skill did one of the things it exists to do.

**Why rung 2 runs Step 5a once, in the supervisor.** The backup script copies *every* path
in the plan, not just one agent's section. Two agents running in parallel would each
snapshot the other's half mid-edit, and a header agent running last by design would
overwrite the whole restore point with fixed files. The undo command would then restore
exactly what the user wanted undone. That is deterministic, not a race.

## Step 5a — the backup

The five designed-out failure modes are documented in `code-winnow/scripts/backup.py`'s
module docstring, beside the code that implements each one. In summary: it fails closed on
a missing `Status:` line, counts plan items independently of the paths it captured, refuses
a non-empty destination, refuses a destination pasted from the plan header, refuses on any
missing file, and resolves against the git toplevel.

**Why `git stash` is not a substitute.** `--include-untracked` moves the user's work out of
the tree, which is disruptive mid-review, and it still cannot be un-popped cleanly after
further edits.

**Why the file list does not come from the scanner JSON.** Agent C's entire purpose is
producing findings on files the diff never touched, so an untouched doc has no entry in
that JSON at all — and would be edited with no copy made.

**Why a tracked file is not "safe because git can restore it".** That is the same reasoning
the step already rejects for untracked files, and it fails the same way: after three more
edits there is no clean point to return to.

**Why the test-name list matters more than the count.** Delete one test and merge two others
into a parametrized pair and the total is unchanged while a real test is gone.

## Step 6 — verification

**Why the whole suite, every time.** This skill's fixes are deletions, and a deletion's
blast radius is wherever the deleted thing was referenced from — which is precisely what
you could not see. A targeted re-run confirms the one place you already thought about.

**Why compare against a baseline rather than checking for green.** Assume the suite was
green and you will chase a failure you did not cause, eventually "fixing" unrelated code to
make it pass. Assume the failure was already there and you wave through the one your cleanup
caused, because a red suite is easy to explain away.

**Why `$SCOPE` matters most on the post-fix scan.** Omit it and the scan resolves a
different scope from the baseline it is comparing against — a `--scope branch` review
reconciled against a worktree re-scan reports every untouched finding as `resolved`, which
reads as "your fixes worked" for findings nobody touched.

**Why the deletion-safety pass reads a delta and Step 5b reads equality.** The `evidence:`
commands are *pre*-conditions: `git grep -c cachedRig -- '*.cs'` returned 3 at plan time
**because the field was still there**, and after the approved deletion it returns nothing.
Requiring the output to still match would fail every correct deletion — the only evidence
that survives a deletion unchanged is evidence that proved nothing. Step 5b runs against the
still-unmodified tree, where "the counts reproduce" is exactly the right question.

**Why the deletion-safety pass is not a fallback for a missing cold-review skill.** It was
once written that way, which had it backwards: installing the recommended reviewer bought
you *less* safety, silently. A cold reviewer reads the diff as it now stands and does not
know which lines you removed.

## The scanner

**Why there is no entropy heuristic for secrets.** Hashes, UUIDs, base64 blobs and minified
bundles all look random, so a "high-entropy string" rule fires constantly on files holding
no secret at all. A noisy rule is worse than a missing one — the reader learns to skim, and
what they skim past is the P1 three sections down.

**Why the vendor-example exemption is anchored at the end of the token.** A token is a
fixed-length random string; matching `example` or `sample` *anywhere* in the body silently
drops a live key whose body happens to contain those letters, which is a false negative on
the one rule where that is the worst outcome available.

**Why `restated-comment` maps `++`/`+=` to "increment".** The rule scores word overlap
between the comment and the line below it, at a 0.6 threshold. `// increment the counter`
above `counter++` — the archetype in `core-patterns.md` — scored 0.5: the comment's verb is
English and the code's verb is an operator, so `increment` matched nothing and only
`counter` did. Lowering the threshold to catch it would have widened every other comparison
too, against the standing position that a noisy rule is worse than a missing one. Mapping
the two unambiguous operators to their English verbs closes the archetype without touching
anything else.

**Why `unused-binding` is silent in headers and partial classes.** "Never referenced in this
file" is vacuous by construction there.

**Why `complete: false` and exit 2 when every file in scope was skipped.** A scanner that
says "0 candidates" because it could not open the files looks identical to a clean branch.

## The test harness

**Why `test_workflow.py` extracts snippets rather than copying them.** A copy agrees with
itself forever; extraction means every block in the document is an executed artifact and
stays that way as the document changes.

**Why each block runs in its own `bash` process.** The harness hosting this skill does not
preserve shell state between tool calls, and every snippet is its own call. Running them in
one shell would pass while the real sequence fails — which is how four defects shipped.

**Why `check_mutations.py` exists.** A passing test proves nothing on its own. Twelve
parametrized tests once asserted that directive comments are exempt from the comment rules,
and all twelve passed with the exemption stubbed out. The suite was green and the feature was
unverified.

**Why a stale mutation row is a failure and not a note.** A row whose `find` string no longer
appears in its target file silently stops verifying anything, which is the same defect class
the harness exists to catch. `test_mutation_rows_still_apply` in `test_scan.py` makes that a
red test in the default suite, because `check_mutations.py` itself is too slow to run there.
