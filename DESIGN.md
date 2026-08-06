# Design notes

Why the mechanical parts of the workflow are written the way they are. Every entry is a
near-miss: a form that reads correctly, does something else, and fails silently. Agents
executing the skill do not need this file. Maintainers editing the snippets do — each of
these was a shipped defect, and the obvious simplification reintroduces it.

The workflow is three documents — `code-winnow/SKILL.md` (the spine and Step 0),
`review-pipeline.md` (Steps 1 – 4b) and `apply-and-verify.md` (Steps 5 – 6) — split by
entry path so that a run invoked to apply an approved plan does not read the review it
is skipping. Where an entry below says "SKILL.md" about a step, the step now lives in
whichever of the two files owns it; `test_workflow.py` asserts that mapping, so it
cannot drift silently.

Those documents keep the rationale for rules an agent will argue itself out of under
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

## Step 2 — the stem, the round, and `env.sh`

**Why the stem is captured once.** It is stamped into `meta.json`, into every scanner
JSON's `report_stem`, and into the report headers, and each invocation stamps its own
clock — so a run crossing a minute boundary ends up with records that disagree about
when it happened. It no longer *names* files; see below.

**Why filenames inside a round are short and fixed.** A stem on every filename put a
46-character prefix on nine lines of `ls` and made the listing unreadable, and it turned
"which JSON is the prior baseline" into string parsing —
`ls -1t round-*/*.json | grep -v -- '-postfix\|-p3\|-r2'`, a blocklist of ad-hoc
suffixes that grew every time an agent invented one. Identity moved to `meta.json` and
to a three-line block at the top of every markdown file, and the matcher compares a
field instead of a substring.

**Why `scope` and `scope_label` are two fields in `meta.json`.** `resolve_diff` returns
a human label — `uncommitted work (staged, unstaged, 3 untracked)`. The count is part
of the string and changes between runs, so a prior-round matcher keyed on it finds
nothing, every run, and every report says "Previous run: none" — indistinguishable from
a genuine first run. `scope` is the stable identity (`worktree`, `branch vs main`) and
is the only field the matcher reads.

**Why a round with no `meta.json` is skipped rather than guessed at.** Rounds written
before this layout carry no scope, and the only way to infer one is to parse a legacy
filename — the thing this design removes. Reconciling against a mismatched baseline
moves findings nobody touched into `resolved`, which reads as "your fixes worked". No
baseline is the safer failure.

### Why the root has no aliases

The obvious design is a symlink per report at the workspace root, pointing into the
current round. Measured in Git Bash on Windows:

| Command | Result |
|---|---|
| `ln -s round-01/agent-A.md agent-A.md` | a regular 20-byte **copy**, silently, exit 0 |
| `ln -s round-01 latest` | a **copied directory**, silently |
| `MSYS=winsymlinks:nativestrict ln -s …` | a real symlink, only with Developer Mode on |
| `ln round-01/agent-A.md agent-A3.md` | a hard link, no env var, no privileges |

A default `ln -s` that silently copies is the worst outcome available for a "most
recent" alias: correct on round 1, stale on round 2, and nothing in the output says so.

Hard links avoid that and were still rejected. A root `fixplan.md` re-points on every
rotation, so a user who copies the resume line, starts round 03, then pastes it, applies
round-03's plan believing it is round-02's. Naming the round in the resume line cannot
do that. The root therefore holds one regenerated index and no aliases at all.

**Why the index is rewritten in full rather than edited.** A surgical update needs a
marker to find, and a half-updated index is worse than a stale one — it is stale in a
way that looks current. `{{ROUND}}` is the only path placeholder, so the paths cannot be
half-substituted either.

**Why the placeholder is `{{ROUND}}` and not `ROUND`.** The substitution is global and
`ROUND` is an ordinary English word, so `s|ROUND|round-06|g` also rewrote the template's
own line documenting `$ROUND` as an `env.sh` variable, into `$round-06`. That shipped in
the index of a real run. A placeholder has to be a token that cannot occur in the prose
around it — and the test that should have caught this performed the *same* unanchored
replace, so it reproduced the defect rather than detecting it. The replacement test
asserts on the survivor (`$ROUND` is still there) rather than on the result.

**Why the reconciliation block uses `if` and not `&&`.** `[ -n "$PRIOR" ] && …` was the
block's last command, so the no-prior path short-circuited and the block exited 1 — on
the first run of every repo, which this document calls normal. A step that fails on its
own documented happy path teaches whoever runs it to stop reading exit codes, and the
four-field integrity check rests entirely on exit codes being meaningful.

**Why `agent-D.md` exists.** Step 4 said D's output goes to `notes.md` "and nowhere
else", while the index template shipped a live link to `agent-D.md` — so following the
document made that link permanently dead. "Nowhere else" constrains where D's *findings*
are published: not the report, not the fix plan. It was never about D's raw output, which
is written and merged exactly like A's, B's, C's and E's.

**Why `cp -n` is not used for the root scaffold.** Step 0 is idempotent and cold entry
at Step 5 re-runs it, so an unconditional copy overwrites a populated index with a blank
skeleton. `cp -n` looks like the fix and is a GNU/BSD extension: a shell that ignores
the flag clobbers, and the run carries on. Per-file `[ -f … ] ||` tests are portable and
visible.

**Why the scaffold copy sits after `git check-ignore` and not beside it.** Writing the
scaffold into a workspace that is not yet excluded is the exact self-dirtying Step 0
exists to prevent, so the check gained an `exit 1`.

**Why `scratch/` and `utils/` ship as directories.** An agent will not create a
directory it was told about in prose; it will use one that is already there. A run left
nine intermediate files at the workspace root — a `.findings.tsv`, a
`_comments_extract.txt`, a hand-rolled `_build_input.py` — because no rule named them,
so no rule constrained where they landed.

**Why `report.md` and the agent reports have no template.** Templates invert this
skill's failure mode. An agent that skips `report-format.md` today writes a report with
sections missing, which is visibly wrong; handed a skeleton, the same agent emits every
heading anyway, producing a structurally perfect document with hollow sections. That is
harder to catch than a missing one, and it collides with the standing rule to omit an
empty section rather than print an empty heading. The templates that do ship — the two
READMEs, `fixplan.md`, `notes.md` — are the ones something downstream validates.

**Why stderr is kept when capturing the stem.** A `REFUSING:` line arrives there and
also yields no stem, so a guard that only knows about empty scopes overwrites the one
message that explains what happened — and then advises retrying with `--base`, which
Step 1 says explicitly not to do.

**Why the round is created in Step 2 and not Step 0.** Cold entry at Step 5 re-runs
Step 0, and creating a round there would orphan the fix plan the cold session was
invoked to execute.

**Why the round number is the highest existing one and not the count, and why `mkdir`
has no `-p`.** With `round-01` and `round-03` present, a count yields `03`; `mkdir -p`
then succeeds on the directory that is already there, `cp -a` overwrites its
`fixplan.md` and `notes.md` with the blank template, and the run exits 0 with no output.
Deleting a single round folder is enough to destroy an approved plan in another one.
Counting was harmless while filenames carried the stem — a collision wrote different
names into the same directory — so fixed short names turned a benign count into a
destructive one. That is a protection the layout change *removed*, not one it inherited.
`sort -n` runs after non-numeric suffixes are discarded, so a legacy
`round-01-scope-probe` neither counts nor collides; `10#` forces base ten, because
`$(( 08 + 1 ))` is an invalid-octal error in bash and would abort the ninth round of any
repo. The bare `mkdir` is the backstop: it fails loudly if the number is ever wrong
again. Found by running the skill on its own branch.

**Why a test asserts the workflow documents contain no lone carriage return.** A `\r` written through
a shell one-liner became a literal `0x0D` inside the PowerShell undo command, which
rendered as `'.code-winnowound-02\pre-fix\*'` — the only Windows recovery route in the
document, handed to the user immediately after their files were edited. It passed every
guard: the scanner's invisible-character set excludes CR deliberately, and the test
harness only extracts ```bash blocks, so a prose line is neither executed nor scanned.
The tell was that Python warned about `\c` and `\p` in the same string and said nothing
about `\r` — **the invalid escapes were the harmless ones, and the valid escape was the
bug.** Write text containing backslashes from a script file, not from `python -c`.

**Why `declined.json` and `perf-declined.md` survive.** They used to survive because the
archive glob matched `current*` and neither name started with it — an accident that a
rename would have quietly undone, turning every settled answer back into an open
question. Nothing globs the root now and nothing is ever moved out of it, so the
property is structural.

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

## Step 3.5 — conflict arbitration

**Why the step exists at all.** The split that keeps the agents' outputs mergeable also
blinds A to the thing that most often decides its verdicts: what the author said. A field
with no reader is dead weight — unless the line above it says the serializer reads it.
Without the merge the report contradicts itself, proposing a deletion on one page and
quoting the comment defending it on another.

**Why X9 is worth having when Step 6 asks the same five questions.** X9 asks them before
the fix plan is written, so the bad deletion is never approved: the user never sees it
offered, never says yes, and nothing has to be reverted. Step 6's deletion-safety pass
asks them after the edits land, and its remedy is restoring a file from the backup.

**Why both passes stay, and neither is redundant.** The fix plan is a *user-edited subset*
of what E reviewed — the user deletes items, items go stale and get skipped, and a cold
Step 5 session executes the plan without E's output in front of it. Step 6 checks what was
actually removed, which is not knowable at Step 3.5.

**Why E's veto runs one direction only.** E saving a line rests on E naming a mechanism
that breaks. E condemning a line A did not flag rests on nothing but E's opinion, and E's
own gate excludes style opinions — so it is an ordinary E finding, held to E's gate, not a
veto and not a merge.

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

**Why a cold session computes the backup path instead of reading it from the plan header.**
The header is prose written for a human, and a value copied out of it arrives with whatever
else is on that line. `Backup:` once carried a trailing `(NOT YET MADE)` marker, and the
backup silently went to a directory of that name — so the restore point existed, under a
name nothing would ever look for. `backup.py` now refuses a destination containing a
parenthetical, but that is the backstop; the durable fix is that every path derives from
`$ROUND`, the directory the plan itself sits in.

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

**Why the fourth part reads `new` rather than running its own scan.** `--since` already
stamps every live finding `new` or `persisting` against the pre-fix baseline, so the answer
to "what did the cleanup add" is computed by the reconciliation scan and was being thrown
away — Step 6 read `resolved` and `persisting` and never `new`. The check costs one array
read. A second scanner invocation would cost a full pass and produce the same array.

**Why a `new` finding cannot be line churn.** `finding_key` is
`(path, rule, message, anchor)` with the normalised source line as the anchor and no line
number anywhere in it — that is exactly why it was written that way, because deletions move
every line below them. So `new` cannot mean "the same finding, further up the file"; it
means a `(path, rule, message, anchor)` combination that did not exist before the edits.
Without that property the check would be unusable: every deletion would produce a page of
phantom `new` entries and the count would be ignored within one run.

**Why it is a scanner read and not a fourth judgment agent.** "Do not judge your own
output" applies to judgment, so the answer was to take the judgment out rather than to add
a reviewer. Detection is the scanner's stamp. Bucketing was the part that smuggled judgment
back in — the first draft said "on a line this fix pass wrote", which asks the agent that
made the edits to recall whether a finding is its own doing, with the exculpating bucket
free to choose and nothing in the output revealing a wrong choice. Comparing against
`$ROUND/pre-fix/` answers it from disk instead: the backup predates the first edit, so the
bucket is a diff. What is left that is genuinely judgment — chaff no rule can see — goes to
the cold reviewer that already runs, which is a fresh context by construction. A fourth
agent would re-review the whole applied diff to find what one array lookup finds for free.

**Why the cold-review handoff carries an explicit instruction.** It used to ask for "a cold
read of the applied diff", and a reviewer given a diff reviews it on its merits — it has no
way to know the diff is the *output of a cleanup pass*, so it never asks whether the
cleanup added anything. The one question this handoff exists for was the one thing not in
the prompt.

**Why a repair loop stops after two attempts.** A `new` finding that survives its own repair
is not chaff any more, it is a design problem in the fix — and Step 5b binds every edit to
preserving behaviour. Looping would either exceed that bound or oscillate, and both are
worse than reporting the pair and letting the user decide.

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

## The web tier

**Why one `web.md` and not three files.** A `.vue`, `.svelte`, `.astro` or `.html` file is JavaScript,
HTML and CSS at once, so a diff that touches one needs all three standards anyway. Three
files would mean three reads for the common case and a dispatch rule to decide between
them, to save nothing — every extra reference file is paid five times over on a parallel
run, and this split would have added reads rather than removed them.

**Why `.html` is in `MIXED_WEB_EXT` and not in an HTML-only set.** It was HTML-only at
first, and a review showed what that produced: a page with an inline
`<script>debugger;</script>` scanned to `findings=0, errors=[]` — a clean bill rather than
a skip — while the same bytes in a `.vue` produced findings across all three languages.
Membership is also what makes `check_css`'s `pure_css` gate withhold the empty-rule rule
from these files, which it must, because `function noop() {}` in an inline script matches
that pattern exactly. The widening came *after* the three passes had matching lexical
awareness, deliberately: extending coverage onto a lexer that read template literals as
code would have multiplied the defect rather than fixed it.

**Why the three web extension sets overlap, and why the dispatch is `if` and not `elif`.**
`MIXED_WEB_EXT` is in all three sets, and the three calls in `scan_file` are sequential
`if`s. Written as an `elif` chain — which is how the Python/C#/C++ block above it is
written, so it is the obvious thing to copy — a `.vue` file gets `check_js` and nothing
else, and the HTML and CSS two thirds of the file report clean. `web-dispatch-not-exclusive`
in `check_mutations.py` pins it. Running all three costs nothing because every web rule is
anchored on syntax that occurs in only one of the three languages.

**Why `check_bindings` is not called for web files.** It counts identifier tokens against
C#/C++ declaration syntax. There is no parser here that can tell a JS binding from a
property name, a destructure, or a JSX attribute, and a token-counting unused-binding rule
over JavaScript produces confident nonsense.

**Why the web scanner rules stop where they do.** The scanner is stdlib Python and `ast`
reads Python, so there is no route to a JS parse tree — which is the difference between the
two tiers and is stated in `core-patterns.md`, `SKILL.md` and the root `README.md` rather
than left to be inferred. A silent scan over a `.ts` diff has not looked for unused
bindings, dead functions or near-duplicate components, and the failure mode is that the
report reads as though it had.

**Why three of the web rules are narrower than the obvious pattern.** Each has a mutation
row, because in all three cases the obvious pattern is one token wider than the rule and
the extra width is live code:

- `\bdebugger\b` flags `this.debugger.attach()` at P1. The shipped rule anchors on a
  statement position in front and a terminator behind. Note that the mutation row rests on
  that one form alone: `debuggerEnabled` is in the same fixture as the other near-miss, and
  it matches neither pattern, because there is no word boundary between `r` and `E`.
- Matching `role="button"` without the element flags `<div role="button">`, which is ARIA
  doing its job and the only thing naming that element to a screen reader.
- A "`-webkit-` is legacy" sweep flags `-webkit-line-clamp`, `-webkit-overflow-scrolling`,
  `-webkit-appearance`, `-webkit-text-size-adjust`, `-webkit-box-orient` and
  `-moz-osx-font-smoothing`, none of which are safely replaceable by their unprefixed form
  across the browsers this rule has to stay quiet on. The rule is a named list of settled
  properties, and it has to stay one.

**Why `console.error` and `console.warn` are absent from `js-console`.** Those are how a
library reports a real problem. A rule that fires on them fires on correct code in every
file that handles an error, and the standing position is that a noisy rule is worse than a
missing one.

## Imports, and dashes in documentation

**Why unused imports are not a scanner rule.** Every claimed language already has a linter
that finds them — `ruff F401`, IDE0005, ESLint `no-unused-vars`, IWYU — so a scanner rule
would duplicate a tool the repo probably already runs. This skill opens by saying linters
catch the subset that is a rule violation and the rest is judgment; the judgment here is
knowing the handful of cases where the linter is *wrong*, which is what the language files
now carry. A rule that agreed with `ruff` would add noise and no coverage.

**Why C++ `#include` removals need tool evidence and the other languages do not.** The
signal, not the difficulty. A wrong `using` removal in C# fails the build here, now, with a
line number. A wrong `#include` removal very often still compiles here — another header
supplied the symbol transitively, or a unity build grouped a neighbour's includes into the
same translation unit — and fails on a platform, compiler or incremental build the author
cannot see from the diff. A stale include costs build time; a wrong removal costs someone
else a red build they cannot reproduce.

**Why an import the diff made dead is a courtesy note and not a fix.** It sits on a line the
change did not touch, so reporting it as a fix would need a third documented exception to
the scope rule, and "two exceptions, and only two" is a line worth keeping. It goes in
Pre-existing with the diff line that removed the last use cited, which tells the user
everything without widening the rule.

**Why dashes in documentation are Agent C's and not a scanner rule.** The question is not
"is there an em dash" — that is trivially matchable — but "does this document read
differently from the rest of the repo's documentation". Answering it needs a sample of the
base branch, which the scanner does not read. A scanner rule could only fire unconditionally,
and in a repo whose docs already use em dashes (this one does) that is a page of findings
about house style.

**Why the existing `unicode-typographic` rule still exempts prose files.** It is a different
rule answering a different question. That one is about a grep that does not match, which in
prose is not a cost. The new check is about authorship, which in code is not a cost. Same
characters, opposite files, and merging them would have produced a rule that is wrong in
both places.

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
