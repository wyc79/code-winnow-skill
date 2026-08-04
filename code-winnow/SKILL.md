---
name: code-winnow
description: 'Use when the user wants generated-code chaff removed from an uncommitted change or a branch — "winnow", "de-slop", "deslop", "clean this up before I commit", "does this look AI-written", "make this idiomatic", "cut the slop" — or is about to open a PR on agent-written code, or a large generated change just landed. Also use when asked to apply or resume an approved cleanup: "apply the fix plan", "code-winnow: apply <path>.fixplan.md". Covers code, comments, docstrings, generated tests, file headers, and docs the change made false. Also flags changes that will break silently — where no test can catch it — plus committed credentials, and writes separate, never-applied performance notes. Not for general code review, bug hunts, or security audits.'
---

# Code-winnow

Generated code fails review in predictable ways. It is rarely wrong; it is bloated, over-defensive, and stylistically foreign to the repo it landed in. Linters catch the subset that is a rule violation. The rest is judgment, and that is the gap this skill fills — winnowing, in the old sense: keep the grain, blow off the chaff.

**Needs Python 3.9+ and git.** It writes reports, a fix plan and file backups under `.code-winnow/`, and git-excludes that path in Step 0. Companion skills are optional; `$WINNOW/references/portability.md` has the degraded paths.

> **Were you invoked to apply a fix plan?** If the request names a `.code-winnow/*.fixplan.md`, or asks to apply or resume an approved cleanup, go straight to **"Entering at Step 5 cold"** near the end of this file. Re-run Step 0 — it is idempotent and it verifies — then skip Steps 1 through 4b entirely. The review already happened; re-running it wastes the context the plan exists to save and re-opens decisions the user already made.

**Scope discipline is the whole game.** Operate only on lines the current change added or modified. A cleanup pass that wanders into untouched files produces a diff nobody can review, which is a worse outcome than the chaff you removed.

**If the user names one feature, that is the scope** — not the whole diff, even when the diff is a branch against a base. "Winnow the dash cooldown work" means the hunks that feature touched and nothing else, however much chaff is sitting three files away. Touching unrelated code inside an approved diff is the same failure as wandering outside it: the user gets back a change they did not ask for, mixed into one they cannot separate it from. Step 1 resolves the feature set and states it back before anything is reviewed.

**This is a diff review, not a repository audit.** Unless the user asks in so many words for a whole-repo pass, the job is the current change and nothing else. Pre-existing problems reach the report only as byproducts — you had the file open to review the diff, you noticed something, you mention it. Do not go looking, do not sweep for vulnerabilities, and do not let incidental findings grow past a short aside. Someone who asked you to winnow a branch and got a repo-wide defect list back did not get what they asked for, and the thing they did ask for is now buried.

**Two passes look like exceptions to that and are not.** Agent E asks how the change breaks silently, and Agent D asks what it made slow. Both are bounded by gates as hard as the scope rule itself — E reports only what the diff did and only when no test could catch it, D reports only what it can attach a frequency to — and both work on diff lines like everyone else. E is not a security review and does not go looking for vulnerabilities; it asks whether *this change* removed a protection, committed a credential, or introduced a failure with no signal. Those three, and nothing else in that direction. `$WINNOW/references/fragility.md` and `$WINNOW/references/performance.md` hold the gates, and an agent that cannot open them will produce exactly the unbounded critique this paragraph refuses.

**The rule is about what becomes a finding, not about what you may read.** Only lines the diff touched can produce one. Reading elsewhere is permitted for exactly three purposes, all defined in Step 3, and none produces a finding however bad the code you pass through looks:

| Purpose | Cap | What it is |
|---|---|---|
| Learning the repo's conventions | **Three files** | *Reviewing* neighbouring code to see how this repo writes things |
| Verifying that a deletion is safe | Uncapped | Grepping for an existing helper, tracing callers, checking scenes for a serialized field |
| Sampling file headers for their shape | Uncapped, top 15 lines only | Extracting a boilerplate shape, not reading the files |

The last two are uncapped because they are lookups, not reviews — you are answering a yes/no about a specific line, not forming an opinion about someone else's file. The three-file cap binds only the first, and stretching it to cover a grep is how "verify before you delete" quietly becomes "delete without checking".

**Three rings, then.** The repo, which you may read and never report on. The diff, which produces findings. The named feature inside it, when there is one, which is the only thing eligible for a fix. When no feature is named the inner two rings are the same and nothing changes.

**Three languages are claimed: Python, Unity C#, and Unreal C++.** They have a reference file each, dedicated scanner rules, and tables checked against their toolchains. Any other language gets the universal pass and ordinary judgment, under one rule that overrides the rest — **when you cannot say what a line is for, keep it.** A directive list that is missing your ecosystem's suppression looks exactly like a list that is complete, right up until the deletion. `references/core-patterns.md` states this as "What this skill actually claims"; say in the report which languages the diff touched and which of them were the claimed ones.

**Two documented exceptions, and only two.**

1. **Pre-existing flaws in the files the diff touches**, on lines it did not touch — capped at two sentences each, reported as a courtesy, never swept for. Step 4 defines it.
2. **A documentation file the diff never touched**, when a specific line of the diff makes a specific line of that doc false. That is not a pre-existing flaw — it did not exist before this change, the change created it, and it is the author's business. Agent C in Step 3 owns it; the bounds are narrow and capped: cite both lines, or say nothing.

Both are courtesies with hard limits, not licence to widen. Everything else outside the diff you may read and must not report.

**Resolve `$WINNOW` before anything else.** It is the absolute path of this skill's directory — the one containing this file, `scripts/` and `references/`. Every scanner call and every reference path below is written against it, because a bare `references/…` or `scripts/scan.py` only resolves when the cwd is the skill folder, which is never where the repo is.

**Then read `$WINNOW/references/core-patterns.md` yourself, before Step 3.** Not only the agents — *you*. Two steps are yours alone and neither can be executed from a pointer: Step 3.5 arbitrates comment evidence against the grading rule in that file, and Step 6's deletion-safety pass checks removals against its directive-comment table. On a parallel run you dispatch the judgment agents and would otherwise never open it, then make both judgments against a filename.

**Run Step 0 next, before anything else that writes** — including the capability check below, which writes `.code-winnow/substitutions.md`. Writing that file before the exclusion lands is the exact self-dirtying Step 0 exists to prevent.

**Then, before Step 1:** read `$WINNOW/references/portability.md`, check which companion skills are available here, look through the installed skills for anything that fills a missing role under a different name, and — if anything is still missing — say so once, proposing the equivalents you found and letting the user choose between those, installing, running degraded, or naming their own substitute. Do not silently take the weakest path. If everything is present, say nothing.

### When nobody is there to answer

A scheduled run, a headless runtime, piped stdin, CI, or a user who has already said they are stepping away. **Five decisions come up in a run and all five have an unattended answer. Take them without asking:**

| Decision | Unattended answer |
|---|---|
| Missing companion skills (Step 0/1) | Run degraded. Put the notice at the top of the report, not in chat. |
| Diff too large to judge in one pass (Step 1) | Split it yourself, by top-level directory, largest first. Report every part; name the split you chose and any part you did not reach. |
| A named feature you cannot resolve (Step 1) | **Widen.** Review the whole diff and say in the report that the feature could not be resolved and what you reviewed instead. |
| Unify file headers (Step 4) | **No.** Report the conflict, change nothing. A header carries a license claim, and asserting one on the user's behalf is not a call to take in their absence. |
| Apply the fixes (Step 5) | **No. Never.** Stop after Step 4b, write the report and the fix plan marked `Status: UNAPPROVED`, and say the run ended there because nobody was there to approve. |

**The last row is not a default that a reading of "do not block" can override.** An unattended run **never edits a file**, because the default scope includes untracked files that git cannot restore. A run that stalls waiting on a question has failed; a run that silently deleted lines from files with no object-store copy has failed worse and quietly.

**One carve-out, and only this one:** a run invoked as `code-winnow: apply <plan>.fixplan.md` *is* Step 5, and it may run unattended — against a plan a human already approved. Demanding approval again in the session that merely executes would make the clear-and-resume path impossible. A plan marked `UNAPPROVED` is refused there, which is what stops the carve-out from swallowing the row above it.

The feature row goes wide rather than guessing narrow because the two failures are not symmetrical: reviewing more than was asked costs the reader a scroll, while reviewing the wrong three files and reporting full confidence is silent.

## Companion skills

| Skill | Used at | Purpose |
|---|---|---|
| `andrej-karpathy-skills:karpathy-guidelines` | Step 5, loaded before any edit | Governs how fixes are made. Prevents the cleanup itself from adding chaff. |
| `superpowers:dispatching-parallel-agents` | Step 3, and Step 4b rung 2 | Fans out the judgment, comment and documentation passes; also carries the fix work when the context is not cleared. |
| `superpowers:requesting-code-review` | Step 6 | Cold pass over the applied fixes. |
| `superpowers:verification-before-completion` | Step 6 | No success claim without a run command and its output. |
| `superpowers:systematic-debugging` | Step 6, on failure | Root-cause a broken test rather than patching over it. |
| A simplification skill | Step 6, optional | Restructures genuinely complex paths. Chaff removal is deletion; simplification is restructuring. Different jobs, in that order. |

Any of these may be absent — including on Claude Code, where the set installed varies by user. `$WINNOW/references/portability.md` has the detection, the degraded path, and the install route for each, plus the notice format for telling the user before the review starts. Substitutes the user has already chosen are recorded in `.code-winnow/substitutions.md`; read it before asking anything — **after Step 0**, since writing it is what makes Step 0 have to come first.

## Step 0 — Make the workspace invisible to git

Before writing anything — including `.code-winnow/substitutions.md` — ensure `.code-winnow/` is excluded. **Prefer the local exclude file:**

```bash
cd "$(git rev-parse --show-toplevel)"
EXDIR="$(git rev-parse --git-common-dir)/info"   # --git-common-dir, NOT --git-dir
mkdir -p "$EXDIR" .code-winnow
grep -qxF '.code-winnow/' "$EXDIR/exclude" 2>/dev/null \
  || printf '\n.code-winnow/\n' >> "$EXDIR/exclude"

git check-ignore -q .code-winnow/ \
  && echo "workspace excluded" \
  || echo "EXCLUSION FAILED — stop here, write nothing"
```

**Verify, do not assume.** If that last line prints the failure, stop and tell the user. Every later step writes into `.code-winnow/`, and an unexcluded workspace means the judgment agents are handed your own reports and backups as review input, and `git add -A` commits them — on a run whose headline trigger is "clean this up before I commit".

Three things in that block are load-bearing, and each has a near-miss that looks right:

**`--git-common-dir`, not `--git-dir`.** Git reads `info/exclude` from the *common* directory. In a linked worktree `--git-dir` returns `.git/worktrees/<name>/`, a rule written there is silently ignored, and `git check-ignore` still says not-ignored — so the setup this most needs to handle is the one it fails silently. (Submodules are fine either way.)

**`printf '\n.code-winnow/\n'`, not `echo`.** If `info/exclude` does not end in a newline — common, since editors append without one — `echo >>` concatenates onto the last line: a file ending `build/` becomes `build/.code-winnow/`, which **destroys the user's rule and excludes nothing.** Git ignores blank lines in exclude files, so the leading `\n` is free.

**`mkdir -p ... .code-winnow`.** Nothing else creates it — the scanner writes no files at all — and the first `> .code-winnow/...` redirect in Step 3 fails with *No such file or directory*, taking the review input, the report, the baseline JSON, the fix plan and the backup with it.

Use `.gitignore` only if the user wants the exclusion shared with their team, and only after telling them it will appear in the diff. That is the reason for the default: `.gitignore` is tracked, so editing it puts the file into the very diff this skill is about to review. The local exclude file is never committed and never shows up in a diff.

The scanner also hard-skips its own workspace directory, so a run started before this step still will not review its own reports. That is a backstop, not a reason to skip Step 0.

## Step 1 — Resolve the review scope

Let the scanner do it. `--scope auto` (the default) takes the **union of all uncommitted work**: staged, unstaged, and untracked files. If the working tree is clean it falls back to the branch diff against a discovered base.

**On a branch with commits *and* a dirty tree, `auto` reviews the uncommitted work only** — the fallback to the branch diff happens when the tree is clean, not otherwise. That is the intended reading, and it is also the shape of this skill's headline case: an agent wrote a feature, committed it, and left a few edits on top. The scanner now puts the gap in `warnings` (`this branch is N commit(s) ahead of 'main' - that work is NOT being reviewed`), so the four-field check below catches it. **When you see that warning, ask** — "your branch has 3 commits I am not reviewing; want the whole branch (`--scope branch`) or just the uncommitted work?" It is one question and the two answers review different code.

**On the base branch itself, that fallback is correctly empty** — `main` diffed against `main` is nothing, so a clean tree on `main` yields no stem and no scope. That is not a broken setup and not a clean bill of health; it means you have to say what to compare against. Pass `--base <ref>`, or name the commit the work started from. This is the first thing to check when a run reports nothing, because it looks exactly like a clean tree from every field in the output.

```bash
cd "$(git rev-parse --show-toplevel)"
WINNOW="<absolute path to this skill's directory>"   # QUOTE IT — see below
SCOPE=""                                             # or: --scope branch --base develop

# Pick an interpreter that RUNS, not merely one that is on PATH.
# Already know the path? Set PY first and the probe is skipped.
for c in python3 python py; do
  [ -n "$PY" ] && break
  command -v "$c" >/dev/null 2>&1 && "$c" -c "" >/dev/null 2>&1 \
    && PY=$(command -v "$c")
done
[ -n "$PY" ] || { echo "no working Python on PATH — set PY to its absolute path:"
                  echo "  PY=/c/Users/me/miniconda3/python.exe"; exit 1; }

"$PY" "$WINNOW/scripts/scan.py" $SCOPE
```

**Quote `WINNOW`.** Unquoted, bash eats every backslash: `WINNOW=C:\Users\me\skills` becomes `C:Usersmeskills`, and a path with a space fails outright. This skill's headline tuning is C#/Unity, so Windows paths are the common case, and every later `"$WINNOW/scripts/scan.py"` and every reference path handed to the agents is silently garbage.

**Test the interpreter, do not just locate it.** `command -v python3` returns the Microsoft Store stub, which is on `PATH`, prints an install advert to stderr, and exits 49. So a bare `command -v` chain "succeeds" and every scanner call then fails. Running `"$c" -c ""` is the difference between present and working — verified on a machine where `command -v python3` resolves the stub.

**Pin the scope flags too, and pass them on every later call.** Every command in this document that invokes the scanner needs them, and each one that omits them silently reviews a different thing: `--report-name` without them stamps a `_worktree_` stem onto a `--scope branch` review, and the Step 4 baseline and the Step 6 reconciliation then scan the wrong scope entirely while still producing a confident report. Step 2 writes all of these to a file so no later block has to remember them.

Three things this handles that a hand-rolled `git diff` ladder does not:

- **Untracked files are in scope.** They are invisible to `git diff` in every mode, and brand-new files are exactly where generated code concentrates. Missing them is missing the point of the review.
- **One staged file no longer eclipses the rest.** A stop-at-first-non-empty ladder reviews the staged fraction of a partially-staged branch and reports full confidence.
- **The base branch is discovered**, in order: `origin/HEAD`, then `main`, `master`, `develop`, `development`, `trunk` — each tried as a local ref then as its remote-tracking form, `main` before `origin/main` before `master`. `--base` overrides. Branch scope diffs the **merge base against the worktree**: the merge base on the near side, so commits that landed on the base after you branched do not appear as your changes, and the worktree on the far side, so uncommitted work on the branch is in scope. That is the same content the review input is built from — see Step 3.

State the source and file count before continuing — `files`, `scanned_files` and `added_lines` come straight out of the JSON. If the user pointed at specific files, honor that and say so.

### If the user named a feature

They can ask for a branch review and still mean one slice of it: "winnow the dash cooldown work", "just the retry logic", "only the parts touching the save system". Take that literally.

**Do not try to compute the scope. Pass the user's words to the agents and let them judge it.**

The tempting move is to resolve the phrase to a hunk or line set up front and filter mechanically. Do not. It fails at both ends:

**Hunk ordinals mean different things to different readers.** A hunk is an artifact of how much context the diff was rendered with. The scanner reads `git diff --unified=0`; the Step 3 agents read `git diff HEAD`, which is `-U3`. Two changes three lines apart are **one** hunk to the agents and **two** to the scanner, so "hunk 2" names different regions to the two readers of the same diff. At `-U3` an unrelated typo fix two lines from a feature change also merges into the same hunk, and there is no way to say "half of hunk 1".

**And the user was not thinking in code structure when they asked.** "The retry logic", "the parts touching the save system", "the dash cooldown work" — none of these are symbol names, and matching them by text against identifiers gets both false hits and misses. Deciding what belongs to a feature is a judgment about intent, and judgment is what the agents are for. A brittle rule that silently returns the wrong set is worse than a judgment call that is stated out loud.

So carry the request, do not compile it:

**1. Restate your understanding before dispatching**, in the user's own terms, and let them correct it:

```
You asked for the dash cooldown work. Reading the diff, that looks like:
  Dash.cs, DashConfig.cs, PlayerInput.cs        — clearly in
  SaveSystem.cs — dash state is serialised here — not sure, tell me
  the other 8 files                             — unrelated, will report only
Confirm or correct before I start.
```

**Do not produce that reading yourself. Dispatch Agent S first.**

**Agent S — scope.** Dispatched only when a feature was named, and **before** A, B, C, D and E. It gets the input diff and the user's phrase verbatim. Nothing else: no scanner JSON, no conversation history, no design rationale.

> The user asked for a review of one thing only, in their words: *"winnow the dash cooldown work"*.
> Here is the full diff. Decide, for each file and for any region within a file that plainly differs from the rest of it, whether it is part of what they asked for.
> Return `in | out | unsure`, each with one line of reason. Use `unsure` freely — it is a question the user will answer, not a failure. Do not review the code, do not report chaff, do not propose changes. You are drawing a boundary, nothing else.

Two reasons this is its own agent rather than your reading of the diff.

**Scope is a bigger power than judgment, and it is the one you should least be trusted with.** Step 3 already says not to judge your own output. Deciding what is *eligible* to be judged decides more than any verdict does — and in this skill's headline case you generated the code an hour ago. An agent that knows the helper it bodged into `Utils.cs` is not *really* dash cooldown work leaves it out, states back something entirely reasonable, gets a yes, and that file is never reviewed by anyone. Nothing in the output shows it happened.

**One boundary, settled once.** The alternative — every agent judging scope as it goes — desynchronises them. Step 3.5 pairs A's finding with B's verdict on the comment above it; if A calls that line in-scope and B calls it out, the pair never meets, A's finding goes live alone, and the merged finding those two rules exist to produce silently does not happen.

**Then confirm it with the user before dispatching anyone else:**

```
You asked for the dash cooldown work. Scope pass says:
  Dash.cs, DashConfig.cs, PlayerInput.cs        in
  SaveSystem.cs — dash state is serialised here unsure
  the other 8 files                             out — will report only
Confirm or correct before I start.
```

Every `unsure` is a question, asked now. `unsure` must never be silently resolved into either pile — that bucket is precisely where a guess would have been wrong without anyone finding out, and asking costs one line.

**A, B, C, D and E then receive the confirmed scope as a rule, not a hint** — the file and region list, plus the user's phrase for context. They do not re-derive it. One thing they may do:

> Scope was settled before you started and the user confirmed it. Work only inside it.
> If you find something that plainly belongs to this feature and is outside the list, or plainly does not belong and is inside it, **say so as an appeal** — name the location and the reason, and keep reviewing under the list as given. Do not act on your own scope opinion; a boundary that moves per agent stops being a boundary.

Appeals go to the user with the report, never applied silently. That keeps the one thing a reviewing agent genuinely knows better — it has read the code — without letting every agent redraw the line.

Ask, because you are guessing from a phrase. A reading that is silently one file wide reviews code the user did not ask about; one that is silently one file narrow misses the thing they did. Neither is visible in the output. Unattended: Agent S still runs, but nothing confirms it, so take its `in` set only when it returned no `unsure` at all — otherwise **widen to the whole diff and say so**, per the unattended table. An unreviewed boundary drawn by one agent and approved by nobody is the failure this whole section exists to prevent.

When no feature is named, none of this happens: no Agent S, no tags, no appeals, and the diff is the scope.

The fix plan records the feature as the user's phrase plus the files that survived, so a cold executor inherits the constraint in the form it was actually decided.

Three things the feature set governs, and three it does not:

| Governs | Does not govern |
|---|---|
| What A, B, C, D and E review at all | What the scanner scans — **always the whole diff** |
| Which findings are live in the report, and which notes D writes | What `<stem>.json` contains — always the full scan |
| Which findings reach the fix plan | What you may read for verification |

**That first "does not" is load-bearing.** If a feature-scoped run wrote a narrowed `<stem>.json`, the next run's `--since` would compare a full baseline against a narrow one and report every out-of-feature finding as `resolved` — a page of "no longer true" claims about findings that are all still true. That is the same defect as running `--min-severity` before reconciliation, and it is the reason the filter lives at the report layer and touches nothing the scanner writes.

Findings outside the feature are a byproduct, handled exactly like pre-existing ones — see Step 4.

**A typo'd `--base` is the failure to watch for.** `--base develp` finds no such ref, records it in `warnings`, and returns an empty scope — which prints as a clean branch. So the integrity check is four fields, not three:

```
exit code != 0        → something went wrong, read `errors`
"complete": false     → files in scope were not reviewed, the scan has holes
warnings non-empty    → READ THEM. A bad --base, an unparseable file, and a
                        --since that was ignored all live here and nowhere else
findings == []        → only means "clean" when the three above are clear
```

Never report a clean result off `findings == []` alone. An empty `findings` with a non-empty `warnings` is a scan that did not happen.

**A warning starting `REFUSING:` is not a failure to work around — it is a question for the user.** The scanner stops when the requested scope cannot be numbered and read coherently at the same time. Today that is one case: under `--scope staged`, a file that is staged *and has since been edited*. `git diff --cached` numbers the staged blob while every finding is read from the worktree, so continuing would drop findings in silence and later report them as fixed.

Do not retry with a different flag to get past it, and do not report the run as clean. Surface it and let the user choose:

- **Commit what is staged, then re-run.** The refusal carries a paste-ready line (`--scope branch --base <pre-commit sha>`) that reviews exactly what the commit contains.
- **Review the staged and unstaged work together** with `--scope worktree`, if separating them was not the point.

Name the blocking files — the message lists them — so the choice is concrete. Unattended, stop at the refusal and report it; do not pick a scope on the user's behalf, because the two answers review different code.

**Two warnings are benign and must not be read as a failed scan.** A missing `--since` or `--declined` file warns `could not read … - ignoring it`; on a first run, or in any repo with no `declined.json` yet, that is the normal state and not a hole in the coverage. Guard them instead of passing them unconditionally:

```bash
# illustration only — the guard pattern; env.sh does not exist until Step 2
DECLINED=""
[ -f .code-winnow/declined.json ] && DECLINED="--declined .code-winnow/declined.json"
"$PY" "$WINNOW/scripts/scan.py" $SCOPE $DECLINED --json
```

Everything else in `warnings` is real.

**Binary files, and files that *look* minified, set `complete: false`.** They are unreadable, not skipped — only vendored and oversized paths carry the `skipped:` prefix that exempts them. Note the asymmetry: a file *named* `app.min.js` matches the vendored-path pattern and is exempt, while an unminified-looking name whose content has very long lines is unreadable and holes the scan. Check `errors` for what was actually unreadable before reporting the scan as holed: a binary asset in the diff is expected and means nothing, while a source file that failed to decode means the review missed code.

**Check the size before dispatching.** If the diff runs past a few hundred changed lines across many files, say so and offer to split it — by directory, by commit, or by language — rather than handing an agent more than it can hold. A judgment pass over a diff that overflowed its context returns confident nonsense. Unattended, split it yourself by top-level directory rather than asking.

**Split the dispatch, never the scope.** `--paths` looks like the tool for this and is not: it scans whole files, marks every line as added, sets `preexisting: false` on everything, and stamps a `_files_` stem that no longer reconciles against the prior run. Splitting that way converts a diff review into the repo audit this skill exists to refuse. Instead run the same scope once, then hand each agent a subset of the **files** and give each subset its own section in one report.

Split on file boundaries, not inside a file. A file handed to two agents gets two partial views of code that has to be judged whole — a helper duplicated at the top and used at the bottom is invisible to both — and neither agent can tell that the other half exists.

## Step 2 — Deterministic scan

```bash
# Flag reference. Real invocations carry $SCOPE and come after `. .code-winnow/env.sh`.
"$PY" "$WINNOW/scripts/scan.py"                      # auto-resolves scope
"$PY" "$WINNOW/scripts/scan.py" --json               # for the reviewer agent
"$PY" "$WINNOW/scripts/scan.py" --paths a.cs b.py
"$PY" "$WINNOW/scripts/scan.py" --whole-files        # untouched lines of the SAME files
"$PY" "$WINNOW/scripts/scan.py" --report-name        # canonical report filename stem
"$PY" "$WINNOW/scripts/scan.py" --stem "$STEM" --json        # pin the stem across calls
"$PY" "$WINNOW/scripts/scan.py" --since .code-winnow/PRIOR.json     # reconcile with last run
"$PY" "$WINNOW/scripts/scan.py" --declined .code-winnow/declined.json  # drop settled items
```

Every flag:

| Flag | What it does |
|---|---|
| `--scope auto\|worktree\|staged\|unstaged\|branch` | Default `auto`: staged ∪ unstaged ∪ untracked, falling back to the branch diff. |
| `--base REF` | Base ref for `--scope branch`. A ref that does not exist lands in `warnings`, not `errors`. |
| `--paths A B` | Scan these whole files instead of a diff. |
| `--whole-files` | Also report untouched lines *of the files the diff touches*. This is what fills the report's Pre-existing section. |
| `--min-severity P1\|P2\|P3` | Default `P3` (everything). Reconciliation runs before this filter, so raising it between runs does not fake resolutions. |
| `--max-file-bytes N` | Default 512 KiB. Larger files land in `errors` as skipped, not silently. |
| `--json` | Machine-readable on every path, including empty scopes and `--report-name`. |
| `--report-name` | Print the canonical stem and exit. |
| `--stem S` | Use this stem verbatim so filename and embedded `report_stem` agree. |
| `--since PRIOR.json` | Mark findings `new`/`persisting`, list ones no longer true. |
| `--declined FILE.json` | Report-shaped JSON of findings the user rejected; matches move to `declined` instead of resurfacing. |

Stem shapes:

```
current<branch>_target<base>_<YYYYMMDD-HHMM>   branch diff
current<branch>_worktree_<YYYYMMDD-HHMM>       uncommitted work (the default)
current<branch>_staged_<YYYYMMDD-HHMM>         --scope staged
current<branch>_uncommitted_<YYYYMMDD-HHMM>    --scope unstaged
current<branch>_files_<YYYYMMDD-HHMM>          --paths
```

Five shapes, and the scope is in the name deliberately: Step 4's reconciliation looks for the most recent scanner JSON **for the same scope**, and comparing a branch baseline against a worktree run reports differences that are only differences of scope.

### How the workspace is laid out

```
.code-winnow/
  env.sh                     this run's state
  declined.json              persistent across runs
  perf-declined.md           persistent across runs — Agent D's notes the user dismissed
  <stem>.md                  this run's report
  <stem>.notes.md            this run's performance notes (Agent D) — never applied
  <stem>.fixplan.md          this run's plan
  <stem>.json, .input.diff, .pre-fix/, .tests-*.list
  round-01/ … round-NN/      every previous run, archived by Step 2
```

**The root only ever holds the run in progress.** Step 2 moves the previous run's dated artifacts into the next `round-NN/` before writing anything, so "which report is current" is answered by looking at the root rather than by comparing timestamps in a flat pile of forty files. Prior rounds stay readable and stay reachable by `--since`; nothing is deleted.

**The two persistent files survive that rotation for free, and the reason is worth knowing before anyone edits the glob.** The archive step matches `current*`, which is the stem prefix — so `<stem>.md` and `<stem>.notes.md` are swept into the round folder, while `declined.json` and `perf-declined.md` are not, because neither starts with `current`. That is what makes "declined" mean *permanently* declined rather than "declined until the next run archives the record". A rename that gave either file a stem-shaped name would silently turn every settled answer back into an open question.

Stdlib only, no install step. Paths resolve against the git toplevel, so the cwd does not matter as long as it is inside the repo. The default pass gives in-scope findings; that is the run that matters. `--whole-files` widens to the untouched lines *of the files the diff already touches* — no further. There is no repo-wide mode; auditing anything else requires the user to name files with `--paths`, which means asking for it.

It flags regex- and AST-level candidates: fields and locals declared and never referenced, fields only ever incremented and never read, locals assigned and never used, variables that just rename another for a single use, log-and-rethrow, empty Unity lifecycle methods, `async` with no `await`, unrooted `UObject*` **members**, invisible Unicode, comments restating the line below, and committed credentials in a recognised vendor format.

**`committed-secret` is the one rule whose findings never enter the fix plan** — and the same holds for Agent E's credential findings, which are the judgment half of the same concern — at any severity and however clearly they are worded. Deleting the line does not un-leak the credential — it is already in the object store, in every clone, and in every CI cache that fetched it. The fix is to rotate, which is not a behaviour-preserving edit and not this skill's business. Report it, say "rotate it", and propose no patch. A cleanup that quietly deleted the line would hand the user an all-clear they have not earned, which is worse than not detecting it.

In test files it additionally flags tests with no assertion, assertions that cannot fail, tests whose every assertion checks a mock, structurally identical tests that differ only in literals, and skips with no reason. That pass runs for pytest/unittest, NUnit/xUnit/MSTest, GoogleTest, Go, Jest/Vitest/Mocha, JUnit, Rust, RSpec, and XCTest — a JS or Go test file gets it even though nothing else here understands JS or Go. `$WINNOW/references/tests.md` is the judgment standard.

**Three of the scanner's test rules are narrower than that list suggests, and a report written from the list alone will claim coverage that did not happen:**

| Rule | Actual reach |
|---|---|
| `unused-fixture` | **pytest only.** It is emitted from the Python checker and nowhere else. An unrequested `[SetUp]`, `beforeEach` or `TEST_F` fixture is invisible to the scanner in every other language — judgment-pass work, not scanner work |
| `mock-only-test` | **P1 with no assertions at all; P2 outside Python when the test does assert and every assertion checks a double.** The P2 case is hedged on purpose, because verifying an interaction is legitimate when the interaction *is* the contract |
| `tautological-*` | **P1 only in Python, and only when every assertion in the test is tautological.** A mixed Python test, and every non-Python tautology, is P2 |

So when the scanner reports nothing in these categories, that is not the same claim in every language, and the report should not say it is.

(`duplicate-test` for Python needs `ast.unparse`, which is why this skill requires Python 3.9 rather than 3.8 — on 3.8 that rule finds nothing and says nothing.)

**Read `errors`, `warnings` and `complete` before you trust a small number** — the four-field check in Step 1. Vendored, generated and oversized paths are skipped by design and do not hole the scan; binary and minified-by-content files are *unreadable* and do. Read `errors` to tell them apart - a PNG in the diff is expected and means nothing, a source file that failed to decode means the review missed code. A scanner that says "0 candidates" because it could not open the files looks identical to a clean branch, and exit code 2 plus `"complete": false` is how you tell them apart. If *every* file in scope was skipped, `complete` is false and the exit code is 2 — that is a scan that reviewed nothing, not a clean diff.

Unused and duplicate bindings need the most judgment of anything the scanner reports. A field with no reader may be dead weight, or may be read by a subclass, a serializer, or the Inspector — the scanner marks exposed declarations at P3 with a note to confirm, and its unused-binding rule stays silent in headers and partial classes, where "never referenced in this file" is vacuous by construction (other rules still apply there). Nothing about a `[SerializeField]` or `UPROPERTY` should be deleted without checking scenes and assets.

The scanner is fast and dumb on purpose. It produces **candidates, never verdicts.** A `TODO` blocking a shipped feature and a `TODO` in a test fixture look identical to a regex.

**Capture the report stem now** — Steps 3, 4 and 6 all write files named from it, and each invocation stamps its own clock, so a run that crosses a minute boundary otherwise ends up with filenames that disagree:

```bash
cd "$(git rev-parse --show-toplevel)"
rm -f .code-winnow/env.sh            # a stale one from a prior run must not survive

# Repeat Step 1's three values. This block cannot source env.sh — it is the
# block that writes it — and shell state does not cross a tool call.
WINNOW="<absolute path to this skill's directory>"
SCOPE=""
for c in python3 python py; do
  [ -n "$PY" ] && break
  command -v "$c" >/dev/null 2>&1 && "$c" -c "" >/dev/null 2>&1 \
    && PY=$(command -v "$c")
done
[ -n "$PY" ] || { echo "no working Python on PATH — set PY to its absolute path:"
                  echo "  PY=/c/Users/me/miniconda3/python.exe"; exit 1; }

# Keep stderr. A REFUSAL arrives there and also yields no stem, so a guard
# that only knows about empty scopes overwrites the one message that explains
# what happened — and then tells you to retry with --base, which Step 1 says
# explicitly not to do.
ERRF=$(mktemp)
STEM=$("$PY" "$WINNOW/scripts/scan.py" $SCOPE --report-name 2>"$ERRF") || STEM=""
if [ -z "$STEM" ]; then
  cat "$ERRF" >&2
  if grep -q '^REFUSING:' "$ERRF"; then
    rm -f "$ERRF"
    echo "" >&2
    echo "That is a refusal, not an empty scope. It is a question for the" >&2
    echo "user — see Step 1. Do NOT retry with a different --scope or --base" >&2
    echo "to get past it: the available answers review different code, and" >&2
    echo "picking one silently is the failure the refusal exists to prevent." >&2
    exit 1
  fi
  rm -f "$ERRF"
  echo "no stem. Three causes, in the order they actually happen:"
  echo "  1. the tree is clean AND you are on the base branch, so auto's"
  echo "     branch fallback has nothing to diff — pass --base <ref> to name"
  echo "     what to compare against. \`git branch --show-current\` tells you."
  echo "  2. the scope really is empty — nothing to review."
  echo "  3. \$PY or \$WINNOW is wrong."
  echo "Check 1 first; it looks identical to a clean tree and is not."
  exit 0
fi
rm -f "$ERRF"

# Archive the previous run before this one writes anything. Every dated
# artifact whose stem is not $STEM moves into the next round-NN/ folder, so the
# workspace root only ever holds the run in progress plus env.sh and
# declined.json. Rotating HERE and not in Step 0 is deliberate: cold entry at
# Step 5 re-runs Step 0, and rotating there would archive the fix plan the
# cold session was invoked to execute.
PREV=$(find .code-winnow -maxdepth 1 -type f -name 'current*' ! -name "$STEM*" \
       -o -maxdepth 1 -type d -name '*.pre-fix' ! -name "$STEM*" 2>/dev/null)
if [ -n "$PREV" ]; then
  N=$(printf '%02d' $(( $(ls -d .code-winnow/round-* 2>/dev/null | wc -l) + 1 )))
  mkdir -p ".code-winnow/round-$N"
  printf '%s\n' "$PREV" | while IFS= read -r p; do
    [ -n "$p" ] && mv "$p" ".code-winnow/round-$N/"
  done
  echo "archived the previous run to .code-winnow/round-$N/"
fi

# One definition point for every later block. Written fresh each run.
# The function goes IN the file: it is needed in later shells, and a shell
# function no more survives a tool call than a variable does.
cat > .code-winnow/env.sh <<'FUNC'
snapshot() {
  { git rev-parse HEAD 2>/dev/null || echo "no-head"
    git diff HEAD 2>/dev/null || git diff --cached
    git ls-files --others --exclude-standard -z \
      | while IFS= read -r -d '' f; do
          case "$f" in .code-winnow/*) continue ;; esac
          printf '%s\n' "$f"; git hash-object "$f"
        done
  } | git hash-object --stdin
}
FUNC

# Values appended with %q so a path containing a space, a backslash or an
# apostrophe survives being re-sourced.
{ printf 'WINNOW=%q\n' "$WINNOW"
  printf 'PY=%q\n'     "$PY"
  printf 'SCOPE=%q\n'  "$SCOPE"
  printf 'STEM=%q\n'   "$STEM"
  printf 'BACKUP=%q\n' ".code-winnow/$STEM.pre-fix"
} >> .code-winnow/env.sh

. .code-winnow/env.sh
printf 'SNAPSHOT=%q\n' "$(snapshot)" >> .code-winnow/env.sh

. .code-winnow/env.sh
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM" --json \
  > ".code-winnow/$STEM.json"
echo "stem $STEM"
```

**Every later block opens by reloading it**, because shell state does not survive between tool calls — variables set in one call are empty in the next, and each snippet here is its own call:

```bash
# illustration only — the preamble every later block opens with
cd "$(git rev-parse --show-toplevel)"
. .code-winnow/env.sh || { echo "no env.sh — restart at Step 2"; exit 1; }
[ -n "$STEM" ] || { echo "env.sh is incomplete — restart at Step 2"; exit 1; }
```

Without that, `$STEM` and `$WINNOW` are empty three steps later and the run writes `.code-winnow/.input.diff`, invokes `"/scripts/scan.py"`, and backs up to `.code-winnow/.pre-fix` — each failing quietly or writing to a filename that collides with every other run.

**`SNAPSHOT` is the staleness stamp.** It hashes `HEAD`, the tracked diff, and every untracked file's blob — so an edit to a file in scope changes it, and so does a commit, an amend or a rebase.

All three ingredients are load-bearing:

- **Content, not `git status`.** Status reports which files changed, not what is in them, so appending a line to an already-untracked file leaves the stamp identical.
- **`HEAD`.** Without it a clean-tree branch review hashes two empty inputs and yields the empty-blob hash `e69de29b…` — the same constant in every repo on earth — so amends and rebases go invisible in exactly the scope where every line number moves.
- **In `env.sh`, as a function.** It is compared in later blocks and by dispatched agents, and a shell function no more survives a tool call than a variable does. Defined only here, the check silently passes (both sides empty) or fires unconditionally (`snapshot: command not found`).

Recompute and compare it whenever the tree may have moved:

```bash
# illustration only — run after sourcing env.sh
[ "$(snapshot)" = "$SNAPSHOT" ] || echo "STALE: the tree changed since the scan"
```

The whole review rests on line numbers that were true when the scanner ran. If a file changes afterwards — the user keeps working, a formatter runs, a rebase lands — the agents review a diff that no longer matches disk, every finding's line is off, and at Step 5 every anchor fails to match and the whole plan reports "stale" with no explanation of why. The stamp turns that into one sentence at the moment it happens.

Our own writes under `.code-winnow/` are excluded from the hash, so the run does not invalidate itself.

**Guard the empty case.** On a clean tree with no branch diff, `--report-name` exits non-zero with empty stdout and nothing checks it. `$STEM` becomes the empty string, `$BACKUP` becomes `.code-winnow/.pre-fix`, every run writes to the same filenames, and successive runs overwrite each other — the exact failure the stem exists to prevent. Distinguish it from an interpreter failure: if `$PY` is unset, that is Step 1's problem, not an empty scope.

**The baseline JSON is written here, not in Step 4.** Step 3 hands it to every judgment agent, so it has to exist before they are dispatched; writing it two steps later left them with a path to a file that was not there yet. Step 4 no longer writes it — it reads it, and reconciles against the *previous* run's JSON, never this one's.

## Step 3 — Judgment pass, by a separate agent

**Do not judge your own output.** If you wrote the code under review, you hold the design rationale that produced the chaff, and you will rationalize it. That is not a discipline problem you can solve by trying harder — it is a context problem, solved by handing the work to a reader who does not have that context.

### Build the review input first

"The diff" is not a thing that exists for the default scope — untracked files are invisible to `git diff` in every mode, and they are where generated code concentrates. Build it once, explicitly, and hand the *same bytes* to every agent so their findings can be merged and the conflict check can pair them:

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh

# Ask the scanner what it actually reviewed, rather than assuming.
SRC=$("$PY" "$WINNOW/scripts/scan.py" $SCOPE --json \
      | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["scope"])')
case "$SRC" in
  # Merge base, NOT `$BASE...HEAD`. Three dots is the right BASE side and the
  # wrong HEAD side: it pins the comparison to the last commit, while the
  # scanner reads every file from disk. Diff from the merge base to the
  # WORKTREE and both describe the same bytes.
  branch*) BASE=${SRC#branch vs }; RANGE=$(git merge-base "$BASE" HEAD) ;;
  *)       RANGE="" ;;
esac

# Emit every untracked file the agents should actually read, and NAME the ones
# they should not. `cat` on an untracked binary is the failure this exists for:
# one new PNG turns the review input into 230 KB of undecodable bytes, the -s
# check passes because the file is large, and five agents are handed it.
emit_untracked() {
  git ls-files --others --exclude-standard -z |
    while IFS= read -r -d '' f; do
      case "$f" in
        .code-winnow/*) continue ;;
        */node_modules/*|node_modules/*|*/__pycache__/*|*/vendor/*|vendor/*) \
          printf '\n--- NEW FILE (vendored, not shown): %s ---\n' "$f"; continue ;;
        *.min.js|*.min.css|*.map|*.lock) \
          printf '\n--- NEW FILE (generated, not shown): %s ---\n' "$f"; continue ;;
      esac
      # -I is "treat binary as non-matching", so this is true only for text.
      if ! LC_ALL=C grep -qI . "$f" 2>/dev/null; then
        printf '\n--- NEW FILE (binary or empty, not shown): %s ---\n' "$f"
        continue
      fi
      if [ "$(wc -c < "$f")" -gt 524288 ]; then
        printf '\n--- NEW FILE (over 512 KiB, not shown): %s ---\n' "$f"
        continue
      fi
      printf '\n--- NEW FILE: %s ---\n' "$f"; cat "$f"
    done
}

{
  if [ -n "$RANGE" ]; then
    git diff "$RANGE"                                # base..worktree
  else
    git diff HEAD 2>/dev/null || git diff --cached   # unborn HEAD: no commit yet
  fi
  emit_untracked
} > ".code-winnow/$STEM.input.diff"

[ -s ".code-winnow/$STEM.input.diff" ] || {
  echo "review input is empty but the scanner found files — do NOT dispatch"; exit 1; }
```

**Diff to the worktree, not to `HEAD`, and this is the guard the `-s` check cannot give you.** The scanner reads every file from disk, so its findings, line numbers and anchors describe the working tree. A commit-to-commit `$BASE...HEAD` describes something else the moment the tree is dirty — which under `--scope branch` is most of the time, since that is what reviewing a branch you are still working on looks like. The agents then review a diff that omits changes the scanner scanned, while holding a JSON whose line numbers came from content the diff never showed. Both halves are silent: the `-s` check passes because the file is large, just wrong, and `SNAPSHOT` compares the tree against itself over time rather than `HEAD` against the worktree. Measured on this skill's own repo, the two forms differed by 4 KB and by whether the change under review appeared at all.

Three dots is still right on the *base* side — it is the merge base, so commits that landed on the base after you branched do not appear as your changes. `git merge-base` gets that without pinning the head side to the last commit.

The scanner resolves `--scope branch` the same way, for the same reason, so the two halves describe one tree. They did not always: the scanner pinned its head side to `HEAD` while the review input read the worktree, and a single uncommitted insert above a finding was enough to drop it from a `complete: true` report — then have the next `--since` run print it as resolved.

For `--paths`, the input is the named files' full contents instead.

`git diff HEAD` — not `--cached` and plain `diff` separately. Those number the index blob and the worktree blob respectively, and the agents are reading the worktree.

**Branch on what the scanner reports, not on the flag you passed.** `--scope auto` falls back to the branch diff on its own whenever the tree is clean, so a reviewer one commit ahead never passes `--scope branch` and still gets a branch review. Build the input from `git diff HEAD` in that state and it is empty — every agent receives nothing, reports nothing to review, and the run looks clean while the scanner holds a P1. The scanner's `scope` string is the one place the fallback decision is recorded.

Three further guards in that block, all against the same silent-empty failure:

**The `-s` check refuses to dispatch on an empty input.** Whatever new way this breaks, an empty review file must never reach a fan-out of agents that will each confidently report nothing.

**The `|| git diff --cached` fallback.** On a repo with staged files and no commit yet, `git diff HEAD` is fatal — there is no `HEAD` to diff against — but the `{ }` group still exits 0 and the redirect still creates an empty file. That state is a fresh repo mid-first-commit, and "clean this up before I commit" is this skill's headline trigger.

**Skipping `.code-winnow/`.** The scanner hard-skips its own workspace, but this builder is a separate path and it is the half that reaches an agent. If Step 0's exclusion ever fails, `ls-files --others` sweeps in your own reports and the pre-fix backups of the source you just cleaned, and presents them to the judgment agents as new-file content.

**Naming what it did not include, rather than dropping it.** The scanner has a vendor filter, a size cap and a binary check; this builder is a separate path and had none of them, so it `cat`-ed whatever `ls-files --others` returned. One untracked PNG — a new sprite, a prefab, a `.meta` file, which in a Unity or UE5 repo is the *normal* content of a change — produced a 230 KB review input that was not valid UTF-8, and the `-s` check passed because the file was large. Every excluded path still gets a `NEW FILE (…, not shown)` line, because an omission an agent cannot see is the same silent-coverage failure the scanner's `errors` array exists to prevent. If an agent needs one of those files it can open it; what it must not do is read a report that never mentioned it.

To cross-check which files are in scope, use `git diff --name-only HEAD` and `git ls-files --others --exclude-standard`. **Not the scanner JSON** — it carries a `files` *count*, not a path list, and `findings[].path` only names files that produced a finding, so every clean file in scope silently vanishes from such a check.

### Dispatch

Dispatch the agents **in parallel** (see `superpowers:dispatching-parallel-agents`). Give each only that input file, the baseline scanner JSON from Step 2, and the reference files. **No conversation history, no design rationale, no mention of who wrote the code.**

**Give every prompt absolute paths.** The reference files are written below as `$WINNOW/references/...`, and you must expand `$WINNOW` to its real value before dispatching. A subagent's cwd is the repo, not the skill directory, and it has no `$WINNOW` — an unexpanded variable or a relative `references/core-patterns.md` both resolve to nothing, and those files are where all the judgment lives. An agent that cannot open them still returns findings; they are just findings from no standard at all.

**Give every prompt the staleness precondition, verbatim.** These agents read files while they work, and the review can run for minutes:

> Before you report anything, confirm your input is still current. You were given a diff and a scanner JSON describing the working tree at a moment in time. Whenever you open a file to verify something, check that the lines around your finding actually match what the diff says is there. **If a file on disk disagrees with the diff you were given, stop and report `STALE INPUT` with the path** — do not report findings against it, do not re-derive the diff yourself, and do not silently adjust the line numbers. Someone edited the tree while this review was running, and every line number you hold is now a guess.

Each agent has to check for itself. The orchestrator's `SNAPSHOT` comparison catches a change before dispatch and after return, but not one landing *during* — and the parallel window is exactly when the user is most likely to still be working. An agent that quietly renumbers around a moved line produces findings whose anchors all fail at Step 5, reported there as "stale" with no trace of the cause.

**Division of labour, so their outputs merge cleanly — one agent, one question.** **Agent S** ran already: it drew the feature boundary in Step 1 and is finished before any of these start. These work inside the boundary the user confirmed and do not redraw it; they may appeal it, and an appeal goes to the user, not into their findings.

| | Owns | The question it answers | Runs |
|---|---|---|---|
| **A** | Code. Not comments, not documentation files | Does this line earn its place? | Always |
| **B** | Every comment and docstring | Does this comment earn its space? | Always |
| **C** | Documentation files, file headers, and doc-versus-code truth | Is this still true, and does it match the repo? | Conditional |
| **D** | Runtime cost of code the diff added | Does this do more work than it needs to, at a frequency that matters? | Conditional |
| **E** | Silent failure and fragility, including protections the diff removed | How does this break, and why does the suite stay green? | Whenever A does |

If A notices a comment, it belongs to B. If B notices that a docstring is factually wrong, that is C's. If D notices dead code, that is A's. If A notices that a deletion it is proposing would break something invisible to the compiler, that is E's, and E outranks it. The overlaps are real and Step 3.5 resolves them; do not have the agents negotiate.

**A, B and E are the ones that always run**, so a diff with no docs and no hot path still gets code, comments and silent-failure coverage. C and D are conditional because their trigger is a property of the diff — no doc surface, nothing for C; no loop and no hot path, nothing for D. There is no equivalent exemption for E: a one-line change is enough to add a swallowed exception.

**If a feature was named in Step 1, say so in every prompt** and list the file and hunk set. Add: *"Findings only from these hunks. You may read anything; report nothing else."*

**Agent A — chaff judgment.** Everything except comments and doc files.
> Review this diff as if a stranger wrote it. Read `$WINNOW/references/core-patterns.md`, plus the language file(s) matching the diff: `$WINNOW/references/csharp-unity.md` (`.cs`), `$WINNOW/references/cpp-ue5.md` (`.cpp`/`.h`), `$WINNOW/references/python.md` (`.py`). **If the diff touches any test file, read `$WINNOW/references/tests.md` too** — in any language, including ones with no language file here.
> **Those three languages are what this skill claims.** A file in any other language gets the universal rules and your ordinary judgment, and one extra rule that overrides the rest: **when you cannot say what a line is for, keep it.** Read "What this skill actually claims" in `core-patterns.md`. Not recognising something in a language nobody here reviewed is not evidence it is chaff.
> For each scanner candidate: confirm or dismiss, with a reason. Then read the diff yourself — the scanner catches maybe half of what matters, and the half it misses (speculative abstraction, mock theatre, duplicated helpers) is the expensive half.
> **Comments are not yours to report on** — another agent owns every one of them, including scanner candidates tagged `restated-comment` or `commented-code`. **But read them.** When a comment next to one of your findings claims the code is intentional — reserved, deliberate, needed by something you cannot see — do *not* dismiss your finding on that basis and do *not* report the comment. Keep the finding and tag it `comment-claim: "<the comment, verbatim>"`. A later step arbitrates. See "Comments as evidence" in `$WINNOW/references/core-patterns.md` for what separates a claim you can check from one you cannot.
> The reference files tell you to verify before deleting — trace every caller, grep for an existing helper, check scenes and assets for a serialized field. **Do those lookups.** They are searches and reads for evidence, they are not reviews: nothing you see outside the diff becomes a finding, no matter how bad it is. The three-file cap is on *reviewing* neighbouring files for convention, not on grepping the repo to find out whether a deletion is safe. When a lookup is impossible here, say "unverified", keep the finding at its original severity, and propose nothing. Do not demote it - a later step routes unverified claims to their own section, and demoting them instead is what lets a generated ticket reference retire a real P1.
> **Return format, and every field is required** — the fix plan is built from these verbatim, and a field you leave out is one the supervisor has to invent from a file it has not read:
> ```
> path:line — what → why it matters → proposed change      [P1|P2|P3]
> anchor:     <the finding's source line, copied exactly as it appears>
> occurrence: <N>   (which matching line this is, counting top to bottom)
> of:         <M>   (how many lines of the whole file match that anchor)
> evidence:   <what you looked up and what you found — or the word `unverified`>
> ```
> **`occurrence` and `of` count lines of the file, not findings.** For a scanner candidate they are in the JSON as **`anchor_index` and `anchor_total`** — copy those two. Do **not** copy the JSON's `occurrence` field into `occurrence:`; it is the index among findings sharing a rule and message, which is a different population. A diff-scoped scan flags only the instance the change touched, so its `occurrence` is 1 even when the anchor text is on three lines and the flagged one is the third — and an executor told "the first match" then edits an untouched line nobody reviewed.
> **For anything you found yourself, establish both** — open the file, copy the line, normalise runs of whitespace, and count every line that matches. That count is not bookkeeping: at execution time it is the only thing standing between a fix and the wrong line, because the executor refuses any item whose total has changed. If you cannot establish it, say so and drop the item rather than guessing a number.
> Also return the candidates you dismissed, and why.

**Agent B — comment and docstring concision.** Comments and docstrings, and only those.
> For every comment in the diff, return one of: DELETE (restates the code), KEEP (carries information the code cannot — a why, a workaround, an engine quirk, a business rule), or TIGHTEN (right content, too many words) with a rewrite.
> Rewrites: one line where one line does it. No preamble, no restating the function name, no hedging. Comments earn their space by saying something the reader cannot get from the code below them.
> Never delete a comment containing a link or a ticket reference — those point at information outside the file, and you cannot see what is on the other end.
> **"because" is a signal, not a shield.** It usually introduces a reason the code cannot state, and when it does, keep the comment. But it is one word, and "explain why in comments" is the standard instruction given to code generators, so it arrives attached to restatement constantly: `// increment the counter because we need to count hits` is still a restatement, and the clause after "because" says nothing the line below does not. Read what follows it. A reason that survives deleting the code — a constraint, a decision, a consequence — is a KEEP. A reason that is just the code again in prose is not.
> A version number is not automatically protective. `// Workaround for UE 5.4 normalize bug` is a KEEP: the version is *why* the code is shaped that way. `// Updated to use the new API in v2.3` is a changelog entry and a DELETE — git already has it. The test is whether the version explains the code below it or only records when someone touched it.
> **Docstrings need their own pass, and it is the highest-yield thing you will do.** Read the Docstrings section of `$WINNOW/references/core-patterns.md` before starting it. Generated diffs carry a docstring per function whether or not there is anything to say, and they are written to look thorough rather than to be read — so a file gains three hundred lines and no information, and reviewers wave it through because rejecting a docstring feels like rejecting diligence. Work sentence by sentence: cover the signature, read one sentence, and ask whether it told you anything the signature did not. `user_id (int): The user id` did not. Cut restated summaries, restated parameter names, restated types, and `Returns:` lines that repeat the return annotation. Rewrite convoluted register — "is responsible for handling the calculation of" is "returns"; find the verb, and cut the wind-up before it.
> **"Docstring" means the language's equivalent, in every language** — Python `"""..."""`, C# `/// <summary>`, Doxygen `/** @brief */`, Javadoc, JSDoc/TSDoc, Go doc comments, Rust `///`, YARD, Swift markup. The bloat is identical across all of them; only the syntax changes.
> **Python, C# and C++ are the languages this skill claims.** In any other, propose a rewrite only if you can name the convention and the tool that enforces it, or confirm nothing does; otherwise report the count and the pattern and let the user decide. This is not timidity — Go *requires* the restatement, Rust `///` can compile as a test, C# and Java tags can be build inputs, and none of that is visible in the comment text. **And for ordinary comments in an unclaimed language, an unrecognised line is a KEEP, not a DELETE.**
> **Read the whole "Language traps that reverse the rule" section before touching any docstring**, and do not work from this summary — it is a summary, and summaries lose the exceptions that matter. In outline: Go doc comments are *supposed* to restate the identifier; Rust `///` fenced blocks compile and run as tests; C#, Java and Rust doc tags can be build inputs under warnings-as-errors; UE5 `/** */` above `UPROPERTY` is the designer-facing tooltip; **JSDoc `{type}` in a `checkJs` project is the only type information in the file**; and sometimes the docstring *is* the program — `argparse(description=__doc__)`, `click`, `docopt`.
> **On a docstring, TIGHTEN is almost always the right verdict and DELETE almost always is not.** Many repos require a docstring on every public symbol and enforce it with `pydocstyle`, `ruff` D-rules, Doxygen or XML-doc warnings-as-errors, so deleting one breaks a build. Check whether anything else in this repo's public API goes undocumented before proposing a deletion.
> **Report docstrings grouped per file** — a count, two exemplars, one rewrite pattern — not one finding per docstring. Forty P3 entries is how a report stops being read.
> **Grouping is how you report; it is not how you hand over.** Every verdict you actually propose acting on — each DELETE, each TIGHTEN with its rewrite — carries the **same required `anchor:` / `occurrence:` / `of:` / `evidence:` fields Agent A uses**, on the same terms: `occurrence` and `of` count matching lines of the file, and `evidence:` is `rewrite, nothing removed` for a TIGHTEN. A KEEP needs none of them; it is not going anywhere. Group the *narrative* — one count and two exemplars per file — and attach the fields to the exemplars you are proposing. Without them the item reaches the executor with no line to match at, fails the first locating rule, and is reported stale — so the tightening the user approved silently does not happen.
> You judge whether a comment earns its space, not whether it is true. If you suspect a comment or docstring is factually wrong about the code, say so in one line alongside your verdict and move on — another agent owns that question.

**Agent C — documentation and header drift.** Dispatch **only** when the diff touches a documentation file (`*.md`, `docs/`, `README*`, `CHANGELOG*`), **adds a file**, **or** changes a public surface: CLI flags, exported or public names, config keys, install or run commands, public signatures, version or dependency requirements. Otherwise skip it and say so in one line in the report. There is no reason to pay for a third agent on a diff that renames a local.
> Your question is whether the documentation is **true**, not whether it is well written. Three directions:
> **(1) The change falsified a doc.** The diff altered behaviour that a documentation file describes, and the doc was not updated. Find the docs that describe the changed code — that search is a verification lookup, uncapped, and produces no finding of its own.
> **You may report a doc file the diff never touched, and this is the only place in this skill where that is allowed.** The bounds are absolute: report it only when a specific line of the diff makes a specific line of the doc false, and **cite both**. No general quality review of untouched docs — not "this section is vague", not "this reads promotionally", not "this is missing a section". Only "line X makes line Y false." If you cannot name both lines, you do not have a finding.
> **Never these, however cleanly they pass the test above:** `CHANGELOG*`, release notes, and ADRs — "in 2.3.0 we added `fetchUser`" is a true statement about what shipped, and "correcting" it makes the history lie. Localized or translated doc trees (`docs/ja/`, `*.de.md`, anything under an i18n path) — the author usually cannot read the edit, and translation tooling owns those files. Report both categories in one sentence if they matter; never propose the edit.
> **Cap it at five files.** One rename can falsify a line in twenty documents and every finding passes the citation test individually — which turns a one-line change into a twenty-file documentation diff, the exact "diff nobody can review" this skill opens by refusing. Past five affected files, stop listing and say: *"this rename touches N doc files; want a documentation pass as its own change?"* That is a gate, like the header gate, and for the same reason: it is a separate piece of work that deserves its own review.
> **(2) A doc in the diff claims something the code does not do.** Doc files the diff *does* touch get the full treatment, including the Documentation section of `$WINNOW/references/core-patterns.md`. **This includes docstrings** — a docstring describing behaviour the function no longer has, an `Args:` entry for a parameter that was renamed or removed, a documented `Raises:` the body cannot reach, a `Returns:` describing the old return shape. Another agent judges whether those docstrings are too wordy; you judge only whether they are true. A confidently wrong docstring outlives the code it described and is believed by every reader after.
> **(3) File headers.** Two separate questions, and keep them separate in your output.
> *Is the header true?* A `@file` or `@brief` describing what the file used to do, or a header naming a filename that no longer matches after a rename. Same rule as any other doc: cite the header line and the thing that falsifies it.
> **Authorship, copyright and date lines are not yours, even when they are stale.** `@author`, `@copyright`, `@date`, `@since`, `@license` — route every one of these to the header gate in Step 4, never to an ordinary truth finding with a proposed rewrite. Changing `@author Alice` to `@author Bob` because Bob edited the file is a stronger assertion about ownership than adding boilerplate is, and the gate exists precisely to keep this skill from making that assertion on the user's behalf. It is also frequently wrong: on most teams the header records who wrote the file, not who last touched it, and git already knows the difference.
> *Does the header match the repo's convention?* Establish the convention first by reading the **top 15 lines of a sample of existing files of the same type**, on this branch and on the base. That sampling is a verification lookup, not a review — you are extracting a shape, not judging those files — so the three-file convention cap does not apply to it and nothing you see there becomes a finding. Then compare: do the diff's files carry that header, a different one, or none?
> **Sample first-party files only.** Exclude `Plugins/`, `Packages/`, `Assets/Plugins/`, `Assets/ThirdParty/`, `Source/ThirdParty/`, `vendor/`, `third_party/`, `node_modules/`, and anything else the repo did not write. The scanner's vendor filter governs what it *scans* and does nothing about where you sample — and in a Unity or UE5 project those directories hold more `.cs`/`.h` files than the user's own code, so a naive sample concludes the convention is a **vendor's** copyright line and the gate offers to stamp someone else's ownership claim onto files the user wrote. The sample decides what the gate proposes, so a wrong sample makes the gate's approval meaningless. If the sample is not clearly uniform across first-party files, there is no convention to report; say that instead of picking the mode.
> **Report whose notice it is and what year it carries**, not just that a header is missing. "The other files say `Copyright 2019 Acme Ltd`" is a fact the user needs before answering, because a header sampled from 2019 files asserts 2019 on files created this year, and neither the name nor the date is yours to choose.
> **Report the conflict. Never propose unifying headers on your own** — see the gate in Step 4. And never propose touching a header on a file the diff did not add or modify: fixing the repo's header consistency is not this review's job, and a diff that rewrites 200 file headers is the most reviewer-hostile output this skill could produce.
> Severity: **P2** for a stale doc line, and for a header that states something *wrong* — the wrong license, another party's copyright. **P3** for a *missing* header, license ones included, and for a divergent style or doc header. **P1** when a stale line is an install command, a run command, or a security claim — someone will follow it, it will fail, and they will not know why. **P1 also when the repo enforces headers in CI** — Apache RAT, `addlicense -check`, checkstyle `Header`, a `license-eye` action: then a missing header is a red build, which is a fact about this repo rather than a judgment call, and one look for that config settles it.
> **Missing is not the same as wrong, and only one of them is P2.** Copyright subsists without notice under Berne, so a new internal file carrying no boilerplate has close to no legal consequence — calling that a compliance gap overstates it, and P2 is inside "fix all", which is exactly where a header edit must never be. A header asserting the wrong licensor is a misstatement of fact and stays P2.
> Return findings as `docpath:line — the claim → the diff line that falsifies it (path:line) → proposed rewrite`, with the same required `anchor:` / `occurrence:` / `of:` / `evidence:` fields Agent A uses, on the same terms — a doc line is located at execution time by exactly the same machinery, and doc files are the ones most likely to have shifted since you read them. **Establish `occurrence` and `of` by counting matching lines yourself**: a doc the diff never touched was never scanned, so there is no JSON row to copy them from, and a repeated line like `Call \`Dash.Charge()\` before the cooldown elapses.` is exactly the shape that repeats in a document. Report header-convention conflicts separately, as a count and a sample, not as one finding per file.

**Agent D — performance notes.** Dispatch **only** when the diff adds or modifies a loop, comprehension, or recursive call; puts code inside a per-frame, per-tick, per-request or per-item entry point; adds I/O, a query, a lock, or an allocation inside either; or changes a data structure or algorithm on a path already marked hot. Otherwise skip it and say so in one line in the report. There is no reason to pay for an agent on a diff that renames a local.
> **Read `$WINNOW/references/performance.md` before anything else.** It is the whole standard for this pass and the rest of this prompt is a summary of it. Read the language file matching the diff as well.
> **Nothing you produce is ever applied.** Your output is a notes document, not findings. It does not enter the report, it does not enter the fix plan, and no edit will be made from it. That is not a comment on the quality of your notes — it is the honest consequence of the fact that you cannot measure. Write accordingly: a note is a hypothesis offered to a human, not an instruction.
> **The gate: name the frequency, or you do not have a note.** Every note states how often the code runs and how you established that — the enclosing `Update()`, the request handler it sits in, the loop bound, the caller you traced. If you cannot finish the sentence "this runs N times per X", stop. What you have is a preference about how the code is written, and Agent A owns that question. Startup and once-per-process code cannot pass this gate and are therefore ineligible, however wasteful they look.
> **No micro-optimization and no readability trades.** If the win is invisible without a profiler, or the faster form is harder to read and you have not measured, it is not a note.
> **Do not repeat the scanner.** `perframe-lookup`, `perframe-linq`, `expensive-lookup`, `pass-by-value` and `eager-log-format` are ordinary findings in the main report and the fix plan already. Noting them here double-counts them.
> **Never touch a trust boundary**, and never report a comment or dead code — those belong to B and A.
> **Return format**, one entry per note, and `measured:` is required:
> ```
> - path:line — what
>   frequency:  <how often it runs, and how you know>
>   reasoning:  <why it costs more than it needs to>
>   suggestion: <the change, or "unclear — flagging the cost only">
>   measured:   <the benchmark you ran, or the word `no`>
> ```
> `measured: no` is the expected answer and is not a defect in the note. Only write a benchmark here if you actually ran one.
> **You will be given `.code-winnow/perf-declined.md` if it exists.** Skip any note matching an entry — match on path plus anchor text and ignore the line number, since lines shift — and report the count you skipped rather than listing them. The user already answered those.
> Order notes by the strength of the frequency argument, not by guessed impact. Guessed impact is a second unmeasured number stacked on the first.

**Agent E — silent failure and fragility.** Dispatch whenever A is dispatched. There is no trigger condition: a one-line change is enough to add a swallowed exception.
> **Read `$WINNOW/references/fragility.md` before anything else**, plus `$WINNOW/references/core-patterns.md` — its directive-comment table is half of what you are checking — and the language file matching the diff.
> **The gate, and both halves are required. Name how it breaks, and name why the suite stays green.**
> *How does it break?* What goes wrong, when, and under what condition. "This is fragile" is not a failure mode. "On a save written before this change, `dashCharges` deserializes to 0 and the player cannot dash" is.
> *Why does no test catch it?* The suite only creates fresh saves. Nothing exercises the throw path. The failure needs two threads.
> **If a test would catch it, it is not your finding** — it is an ordinary bug, and bug hunting is out of scope here. **If you cannot say how it breaks, it is a style opinion**, and Agent A owns those. Hand it over or drop it. A report full of unfalsifiable "this might race" warnings is worse than one that omits them.
> **The committed-credential class in (2) below is the one thing that does not answer the gate in those words, and it is not exempt from it — it answers in different ones.** *How it breaks:* the credential is valid, published, and usable by anyone who can read the repo. *Why no test catches it:* no suite has ever failed over a key that works. Do not drop one for failing to name a runtime failure mode; a leaked key is the purest form of the thing this pass exists for, a defect with no signal at all.
> **This is not a security review and you must not go looking for vulnerabilities.** Two security-shaped things are yours, and only two. Everything else in that direction is out of scope no matter how it looks.
>
> **(1) A protection this diff removed.** A validation or bounds call deleted from a handler, an auth or ownership assertion dropped, `verify=True` → `False`, `strict` or `validate_certs` disabled, an escape or sanitize call gone, a timeout or size limit removed, or a newly *added* `# nosec` / `# noqa: S…` suppression. **Quote the removed line from the diff's `-` side and name the caller you traced.** If you cannot show the line the diff removed, you do not have this finding — you have a suspicion about existing code, which is out of scope. P1 for a removed check on a reachable path, P2 for a newly-added suppression.
>
> **(2) A credential the diff committed.** The scanner already catches the self-identifying vendor formats — `AKIA…`, `ghp_…`, `glpat-…`, `sk_live_…`, `AIza…`, a `-----BEGIN … PRIVATE KEY-----` block — and you do not repeat those. **Yours is the half a pattern cannot reach: a named credential assigned a literal.** The scanner's rule for that is anchored on a word boundary and a bare `=`, so it sees `password = "…"` and misses `DB_PASSWORD = "…"`, `db_password = "…"`, `smtp_password: "…"` and every `"db_password": "…"` in a JSON or YAML config — which is where a committed password actually lives, under the name it is actually given. Read the added lines and say whether the value is a credential.
>   - **You are reading, not scoring.** Do not run entropy in your head. A hash, a UUID, a base64 blob, a git sha and a minified bundle all look random and none of them is a secret; `references/core-patterns.md` refuses an entropy heuristic on purpose, and an agent that reinvents one rebuilds the noise that rule exists to prevent. The question is whether the *name* says credential and the *value* is a real one — not whether the value looks random.
>   - **Placeholders are not findings.** `${DB_PASSWORD}`, `{{ vault_pw }}`, `<your-key>`, `changeme`, `xxxxxxxx`, an obviously redacted value, a documented vendor example. Neither is a value read from the environment — `os.environ[...]`, `Configuration["…"]`, a secrets manager call — which is the correct pattern and must never be flagged.
>   - **Severity P1, and it does not demote in a test or prose file.** Every other universal rule here demotes in a fixture; this one does not, because a test directory is where keys most often leak and a live credential is not test data.
>   - **Never propose a fix, at any severity.** This is the one finding class that is reported and never patched. Deleting the line does not un-leak the key — it is already in the object store, in every clone, and in every CI cache that fetched it. Write `fix: out of scope — rotate the credential; deleting the line leaves it in history` and propose nothing. A patch here would hand the user an all-clear they have not earned, which is worse than not finding it.
>   - **Diff lines only, like everything else.** A credential sitting on a line this change did not touch is not yours. Say nothing, or note it under pre-existing if you happened to have the file open — do not sweep the repo for keys. That is the security audit this skill refuses.
>   - **One line, one finding.** If the scanner already reported that exact line as `committed-secret`, it is in the report — do not file a second entry for it. If you think its severity is wrong (its assignment branch demotes in a test or prose file, because it is guessing from a name where you have read the value), say so *on that finding* rather than raising a duplicate. Two entries for one leaked key is the same defect as X3 and it makes the count untrustworthy.
> **You outrank Agent A on deletions.** A proposes removing code; you are the reader who knows what removal breaks. When you see a line that is load-bearing in a way the compiler cannot see — a GC root, a directive comment, a type carrier, a trust-boundary check, a registration anchor, a side-effect import — say so plainly and name the mechanism, whether or not A flagged it. Step 3.5 gives you the deciding vote.
> **Severity: P1** for silent corruption, silent data loss, a removed protection on a reachable path, a committed credential, or any failure with no observable signal. **P2** for fragility that surfaces loudly but that nothing tests, and for a newly-added suppression. **You should essentially never produce a P3** — if it is cosmetic, it failed the gate and it is A's.
> **Many of your findings will not be fixable by this skill, and that is expected.** A fix here must preserve behaviour. Adding a missing `await`, narrowing a catch, restoring a removed validation call, stopping a coroutine in `OnDisable` — those are fixable. A save migration, a cache invalidation strategy, a locking scheme — those are design decisions, and **every committed credential** is one of these by construction, since the repair is a rotation rather than an edit. Write `fix: out of scope — <why>` and propose nothing. Do **not** lower the severity because you cannot fix it; it is reported at P1 either way.
> **Return format**, and the first three fields are required on every finding:
> ```
> path:line — what
> breaks:   <how and when it fails — runtime / build / CI / only under condition X>
> no test:  <why the suite stays green>
> fix:      <the behaviour-preserving change, or "out of scope — <why>">
> ```
> On any finding whose fix is *not* out of scope, add the same required `anchor:` / `occurrence:` / `of:` / `evidence:` fields Agent A uses, on the same terms — those items enter the fix plan and are located by exactly the same machinery. A finding marked `fix: out of scope` needs none of them; nothing is going to be located.

**Two searches, two different rules.** Reading a neighbouring file to learn the repo's conventions is capped at three files, is read-only, and produces no findings — it is the only reason to *review* a file the diff did not touch. Grepping the repo to check whether a helper already exists, whether a caller relies on a guard, whether a scene references a field, or which doc describes a changed function is verification, is uncapped, and produces no findings of its own. Everything else in the scope rules stands.

Serial fallback if the runtime has no subagents: run A, then B, then C, then D, then E yourself, and say once in the report that the judgment pass was self-review.

**On a serial run, E's veto is the thing most likely to be lost, and it is the one worth protecting.** Running the passes yourself means A's proposed deletions and E's objections to them are formed by the same reader, in one context, minutes apart — so the objection arrives after you have already talked yourself into the deletion. Do E's pass over A's proposed removals **as a separate reading**, against `fragility.md`, before writing either into the report. The parallel run gets this for free by construction; a serial run has to spend the effort deliberately.

**Agent S has no serial fallback worth the name, and the report must say so.** Its whole value is that a reader with no design rationale drew the boundary; doing it yourself restores exactly the conflict it exists to remove. Draw it, confirm it with the user as usual, and record in the report that the scope was self-drawn — that line is what tells a later reader which decision to distrust if something turns out to have been left out.

## Step 3.5 — Conflict check

The split that keeps the agents' outputs mergeable also blinds A to the one thing that most often decides its verdicts: what the author said. A field with no reader is dead weight — unless the line above it says the serializer reads it. Without this step the report contradicts itself, proposing a deletion on one page and quoting the comment defending it on another.

**Run this yourself**, once all agents return, before writing anything. It is reconciliation of two outputs, not judgment of code, so the "do not judge your own output" rule of Step 3 does not apply here.

**If Agent A returned no `comment-claim:` tags at all, this step has nothing to work on — and that is usually a bug, not a clean diff.** A's instruction to keep a finding it would rather dismiss and hand it up for arbitration is one line inside a long prompt, written as two negatives, and it asks A to do the unnatural thing. The natural thing — see `// Reserved for future use`, quietly drop its own finding — produces an empty conflict check and a report that looks fine. Before concluding there were no conflicts, grep the diff yourself for the bare-claim vocabulary (`reserved`, `intentional`, `do not remove`, `for future`, `kept for`) and check that A either tagged those lines or had no finding near them. If A swallowed them, re-dispatch A with the tagging rule restated at the top of its prompt rather than reconstructing its judgment here.

**One constraint that does apply, and it is the important one: you may not overturn a finding using design rationale you hold from earlier in this session.** That rationale is exactly what Step 3 exists to keep out, and it will arrive dressed as "I know why that parameter is there". Only three things count as evidence: the diff, the comment text, and a lookup in the repo.

### What pairs with what

A comment is adjacent to a finding when it is on the same line as the finding's `anchor`, in the contiguous comment block immediately above it, or the docstring of the declaration the anchor sits in. Nothing further away pairs — a comment three functions up is not evidence about this line.

### The ten classes

| | Situation | Resolution |
|---|---|---|
| **X1** | A comment claims intent that contradicts one of A's findings | Graded — below |
| **X2** | A deletes a declaration; B says TIGHTEN or KEEP on its comment | The deletion subsumes B's verdict. The comment goes with the code, as **one** finding. Prevents an orphaned comment describing a field that no longer exists, and a rewrite nobody will read |
| **X3** | B says DELETE the comment; A says delete the code | Not a conflict — they agree. Emit **one** merged finding, not two entries for one edit |
| **X4** | An intent comment sits on a test finding | Graded, plus the floor below |
| **X5** | C says a docstring is false; B says TIGHTEN or KEEP | **Truth beats concision.** C wins, and B's rewrite must carry the corrected fact. If B said DELETE, that already resolves it — one finding |
| **X6** | A deletes a symbol; C reports a doc that documents it | **One** merged finding naming both locations: delete the code, update the doc. Two edits, one decision |
| **X7** | B says DELETE or TIGHTEN a file header that C identifies as the repo's convention | **KEEP it verbatim.** Headers are boilerplate on purpose; concision does not apply to them, and a header that matches 200 other files is doing its job precisely by being identical |
| **X8** | A proposes deleting a line D wrote a note about | **The deletion wins.** Drop the note and count it. A note about a line that is going away is noise, and kept alongside, the report and the notes document contradict each other. If A proposes a *rewrite* rather than a deletion, keep the note and mark it `re-check after applying` |
| **X9** | A proposes deleting a line E identifies as load-bearing | **E wins** — below |
| **X10** | A and E flag the same line for the same underlying reason | **One** merged finding at the higher severity, carrying E's `breaks:` and `no test:` fields. Two entries for one edit is the same defect as X3 |

X5, X6 and X7 do not arise when C was not dispatched. When it was not, B's one-line notes about comments or docstrings it suspected were false still reach the report — as P3 "unverified doc claim", never dropped. A suspicion nobody checked is worth less than a verified finding and more than silence.

X8 does not arise when D was not dispatched. X9 and X10 always can, since E runs whenever A does.

Findings outside the confirmed scope never enter this step — arbitrating something nobody is going to act on spends judgment on a byproduct. Scope appeals are not conflicts either: they go to the user with the report, not through these rules.

### X1 — grading the claim

The rule is in `$WINNOW/references/core-patterns.md` under "Comments as evidence", and the short version is that authority is earned, never granted by the presence of a claim.

**A checkable why** — a ticket, a named consumer or mechanism, a concrete external constraint — **earns a lookup, not a pass.** Do the lookup:

- **Confirmed** — you found the thing the comment names. Dismiss A's finding; it moves to "Deliberately left alone" with the comment quoted as the reason.
- **Disproved** — you found positive evidence of the *opposite*: the named ticket exists and says something else, the named consumer exists and does not reference this. The finding stands, goes **up one severity** (P3→P2→P1; a P1 stays P1), and its message says the comment is false. A comment asserting something untrue is worse than no comment, because it stops every future reader from touching the line for a reason that does not exist.
- **No evidence either way** — the grep returned nothing. **This is not disproof, and must never be filed as Disproved.** Keep the finding at its original severity, mark it `unverified`, propose nothing.
- **Unperformable** — no network for the ticket, no tooling to read the asset. Same handling as no-evidence.

**The middle two are where this goes wrong, which is why there are four buckets and not three.** With only Confirmed / Contradicted / Impossible, an agent whose grep came back empty has no bucket for its actual situation, and the nearest label is "Contradicted" — which upgrades severity and writes "the comment is false" into the report. **Absence of evidence is the normal result for truthful comments**, because the consumers worth commenting about are the ones grep cannot see: Blueprints and scenes in binary assets, reflection, dependency injection, serializers, SQL views, wire protocols. Only positive disproof earns the upgrade.

An unverified claim is **not** silently preserved either: it becomes a question for the user, reported in its own "Author claims — confirm" section **at the severity A gave it**. It never enters the fix plan and it is never proposed for deletion.

Do not demote it to P3 for being unverifiable. That reads as caution and is the same immunity one rung down — eleven characters of `(see #4821)` would move a P1 to the bottom of a cosmetic list the report rules tell you to cut when it runs long. `$WINNOW/references/core-patterns.md` has the long version.

**A bare claim** — "reserved for future implementation", "kept for later", "intentional" with no reason — does not protect the code, and earns no lookup, because there is nothing to look up. Merge the comment and the code into **one** finding at A's severity:

> `Combat.cs:41` — `enableAdvancedMode` is never read, and the comment above it asserts it is reserved without saying for what. → Add a ticket reference, or remove both lines.

This is the case the obvious rule gets wrong. `// Reserved for future implementation` is not a defense against speculative structure — it *is* speculative structure, with a second line of it stacked on top. A rule that let a comment immunise the code beneath it would let generated code immunise itself with a generated comment, and the skill would stop working on precisely the case it exists for.

Never propose deleting the code and keeping the comment, or the reverse. Those two lines are one decision.

### X4 — the floor

**A comment can justify a test's existence. It can never justify its false coverage.** `// intentional duplicate, pins #412` dismisses `duplicate-test`. Nothing in a comment dismisses an "asserts nothing" or "mock-only" finding — a note saying the test is intentional does not make an unfailable test able to fail. Keep it, quote the comment, and say what assertion would fix it.

**Match on the defect, not the severity label.** Those findings arrive as P1 *or* P2 depending on language and shape — a Jest test whose only assertion is `toHaveBeenCalled()` is P2, not P1. A floor written as "nothing dismisses a P1" would let the commonest form of the defect through on a technicality. `$WINNOW/references/tests.md` has both tables, and the carve-out that matters in the other direction: a test with no assertion that fails by crashing — an import smoke test, a does-not-crash regression — is not false coverage and is dismissible with one line naming it.

### X9 — E vetoes the deletion

**When E names a mechanism that makes a line load-bearing, A's finding is dismissed.** It moves to "Deliberately left alone" with E's reason quoted, and it does not reach the fix plan. The mechanisms are the ones in the Step 6 deletion-safety list and in `$WINNOW/references/fragility.md`: a GC root or callback reference, a directive comment, a type carrier, a trust-boundary check, a registration anchor, a side-effect import, a serialized field an asset reads.

**This is the payoff of running E at all, and it is worth being explicit about why.** Step 6's deletion-safety pass asks these same questions *after* the edits land, and its remedy is to restore the file from the backup. X9 asks them before the fix plan is written, so the bad deletion is never approved — the user never sees it offered, never says yes to it, and nothing has to be reverted.

**Both passes stay, and neither is redundant.** The fix plan is a user-edited subset of what E reviewed: the user can delete items, and a cold Step 5 session executes a plan without E's output in front of it. Step 6 is the check that runs against what was *actually removed*, which is not knowable here.

**E must name the mechanism, not merely object.** "This looks load-bearing" is not a veto — it is the style opinion E's own gate excludes. If E cannot say what breaks and why no test catches it, A's finding stands on A's evidence, and the disagreement is reported as a confirm-question at A's severity rather than silently resolved either way.

**One direction only: E can save a line, never condemn one on A's behalf.** If E thinks something *should* be deleted and A did not flag it, that is not a veto and not a merge — it is an ordinary E finding, and it needs E's own gate satisfied like any other.

### Output

A merged finding list, and one line for the report:

```
Conflict check: 3 dismissed on comment evidence, 2 merged, 1 upgraded (comment
contradicted by lookup), 2 deletions vetoed by E, 1 perf note dropped (line deleted).
```

Report every count, including the zeroes that matter. "0 deletions vetoed by E" on a diff where A proposed twelve deletions is a fact about the run; an omitted count reads as though the check was not made.

Unattended runs execute this step normally — it needs no user input.

## Step 4 — Report

Never edit in this step.

### Naming and dating the report

Never write `report.md`. Use `$STEM` from Step 2 so successive runs never overwrite each other and so the file says what it reviewed. Write `.code-winnow/<stem>.md`, the human report; `.code-winnow/<stem>.json` already exists from Step 2. Put the generated timestamp, the scope, and the two branch names in the document header as well — filenames get copied into chat and lose their context, and a review whose date you cannot establish is a review nobody trusts.

**Every JSON the run writes gets its own filename.** `<stem>.json` is the pre-fix baseline, written once in Step 2 and never again — Step 6 reads it. The concrete trap:

```bash
# illustration only — the truncation trap, not a step to run
# Step 2 — baseline, written once, never overwritten
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM" --json > ".code-winnow/$STEM.json"

# Step 6 — WRONG. The shell truncates the file before python opens it, so
# --since reads an empty file and the baseline is gone.
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --since ".code-winnow/$STEM.json" --json \
  > ".code-winnow/$STEM.json"

# Step 6 — right. New name out, baseline in, baseline untouched.
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM-postfix" --json \
  --since ".code-winnow/$STEM.json" > ".code-winnow/$STEM-postfix.json"
```

### Reconciling with the previous run

Find the most recent scanner JSON for the same scope and pass it to `--since`. **Look in the round folders, not just the root** — Step 2 archived the previous run there, so the root holds only this run:

```bash
# illustration only — the search, not a step to run
ls -1t .code-winnow/round-*/*.json 2>/dev/null | grep -v -- '-postfix\|-p3\|-r2' | head -1
```

Exclude `$STEM.json`, which this run wrote minutes ago, and the derived `-postfix`, `-vs-` and `-preexisting` outputs, which are reconciliation results or widened scans rather than baselines. **Check the stem's scope segment matches too** — `_worktree_` against `_worktree_`, `_target<base>_` against the same base. A stem carries its scope precisely so this comparison can be made, and `ls -1t` alone does not make it.

That exclusion is not pedantry. Step 2 writes the baseline before the agents are dispatched, so by Step 4 it *is* the newest JSON for this scope — reconcile against it and every finding comes back `persisting`, `resolved` is empty, and the report names this run as its own previous run. Write the reconciled output to `.code-winnow/$STEM-vs-<prior stem>.json`; never back over `$STEM.json`, which Step 6 still needs as the pre-fix baseline. If no earlier run exists, say "Previous run: none" and skip `--since` entirely. The scanner marks each live finding `new` or `persisting`, and returns the ones present last time and absent now in `resolved`. Matching is by file, rule, message, and the normalised source line, so several instances of the same rule in one file stay distinguishable and survive the line shifts that deleting other findings causes.

Findings present before and absent now are **no longer true** — fixed, refactored away, or overtaken by events. Report them under their own heading and never re-list them as live. A punch list that keeps resurfacing settled items stops being read, and that failure is quiet: the user does not tell you they have started skimming.

**A finding whose file this run never opened is `out_of_scope`, not `resolved`.** The scanner records every path it actually read, so a prior finding in a file that left the scope — committed since the last run, or simply outside a narrower one — lands in its own array and its own report section, saying the true thing: not examined. The flow that produced the false claim is the ordinary one — winnow, commit part of it, winnow again while the tree is still dirty, and the committed file's live P1s came back as "no longer true". Report that section as unexamined and never fold it into the resolved list; if the user wants those answered, the scope has to include them.

**"Absent" means gone, not merely unprinted**, and the scanner enforces the distinction so a mismatched baseline cannot manufacture resolutions. A finding this report filters out but that is still true — a pre-existing one on an untouched line, on a run without `--whole-files` — is counted during reconciliation and then dropped from the output: it appears as neither live nor resolved, because "out of this report's scope" and "fixed" are different facts and only the second is news. Declined findings are handled the same way and for the same reason.

### Findings the user declined

Declining is not the same as resolving: the finding is still true, so the scanner keeps producing it, and without somewhere to record the answer it returns as `persisting` on every run — the same skimming failure by a different route.

Keep one file, `.code-winnow/declined.json`, in scanner-report shape. When the user rejects a finding, append the finding object exactly as the scanner emitted it (`path`, `rule`, `message`, `anchor` are the key — keep all four verbatim):

```json
{ "findings": [
  { "path": "src/Foo.cs", "line": 88, "severity": "P2", "rule": "unused-binding",
    "message": "'cachedRig' is declared and never referenced in this file",
    "anchor": "private Rig cachedRig;" }
] }
```

Pass it on every later run with `--declined .code-winnow/declined.json`. Matches move to the `declined` array and out of `findings`, so they never re-enter the live list. The file is a normal file — the user can delete a line from it to re-open a question. `line` is ignored in matching, so declined items survive the line shifts that other deletions cause.

Show the user the condensed version:

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
- <the conflict, as a count and one sample — see the gate below>

### Author claims — confirm  (never severity-sorted, never cut for length)
- `path/file.ext:LINE` — <finding, at its original severity> — the comment says <quote>; could not verify because <the lookup you could not run>

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

Every count in that header comes out of the JSON: `files`, `scanned_files`, `added_lines`. When `scanned_files < files`, say which ones were skipped and why — that gap is the difference between a clean branch and a scan with holes in it. Omit any section that is empty rather than printing an empty heading.

Severity:

- **P1** — swallowed exceptions with a broad or bare `except`, validation removed from a trust boundary, tests that assert nothing or assert only on mocks, invisible Unicode in real source (zero-width, non-breaking, bidi — *not* a leading BOM; **inside a test file** the scanner demotes these to P2, and a non-breaking space or soft hyphen to P3 in a test *or* prose file — everything else in a prose file stays P1), unrooted `UObject*` members, mutable default arguments, committed developer-home paths, committed credentials in a recognised vendor format (**not** demoted in a test or prose file, and never fix-plan eligible — rotate, do not delete). **From E:** silent corruption or data loss, a persisted surface changed with no migration, any failure with no observable signal, **and a credential E read and judged real** — also never demoted and never fix-plan eligible
- **P2** — speculative abstraction, defensive checks in trusted paths, unused fields, duplicated helpers, dead scaffolding, config knobs nothing sets, structurally duplicate tests, unused fixtures, `except SpecificError: pass`, `/home/...` paths, UNC paths naming an internal host, a credential-named variable assigned a literal in a test or prose file — that last one is the *scanner* guessing from a name, which is why it demotes in a fixture, and it is not in tension with E's P1 above: E demotes nothing because E has read the value and judged it, where the scanner has only matched a shape. **From E:** fragility that surfaces loudly but that nothing tests, a newly-added suppression, a constant duplicated where it will desync
- **P3** — comments restating code, generic naming, formatting churn on untouched lines, em dashes and smart quotes *in code* (the scanner exempts **whole-line** comments, Python triple-quoted regions and prose files; it does **not** exempt a trailing comment on a code line, nor string literals, so leave typography alone in localized and user-facing strings yourself). **E should essentially never land here** — a cosmetic E finding failed its own gate and belongs to A

**"Validation removed from a trust boundary" was already a P1 before Agent E existed**, and nothing enforced it — no scanner rule detects it and no agent was asked to look. E is what makes that line true rather than aspirational, which is worth knowing if you are wondering what a fragility pass buys over the severity table that was already there.

### Findings that cannot be fixed here

E produces findings whose fix is a design decision — a save migration, a cache invalidation strategy, a locking scheme, a schema backfill. Step 5b binds every fix to preserving behaviour, so these are reported and left. **Every committed-credential finding is in this category too** — the scanner's `committed-secret` rows and E's read of a named credential alike — for a different reason: the repair is to rotate the credential, and deleting the line only hides it from the working tree while it stays in history.

**They stay at their own severity and stay in the P1 or P2 list.** Do not demote them for being unfixable, do not move them to a separate section, and do not move them into the performance notes. A P1 that this pass cannot repair is still a P1 the user needs to see today, and every mechanism for tidying it away — demotion, a side heading, a separate document — ends with it below the fold. Mark the item `fix: out of scope — <why>`, count them in the header's `Not fixable here:` line, and leave them where the severity puts them.

The fix plan omits them, so "fix all" cannot sweep them up. That is the only place the distinction has any mechanical effect, and it is enough.

The "deliberately left alone" section matters more than it looks. Showing what you considered and rejected is what makes the rest credible — and it stops the next run re-flagging the same lines.

If a P3-only list runs past a screen, cut it. Twenty cosmetic nits train the user to skim, and then they skim past the P1.

**Never cut "Author claims — confirm", and never sort it by severity.** Those items keep the severity they had before the comment was considered, and each one is a question only the user can answer in two seconds. Folding them into P3 is what makes the nine-character attack work: append `(see #4821)` to a comment above `except Exception: pass`, the lookup is unperformable in most runtimes, and a demoted item lands under "Cosmetic" and gets trimmed for length. A silent-data-loss P1 disappears for twenty-two characters of generated comment.

### The performance notes document

Agent D's output goes to `.code-winnow/$STEM.notes.md` and nowhere else. It is not a section of the report, and **nothing in it enters the fix plan or is ever applied.**

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

**Never write `- [ ]` and never write a `file:` line in this document.** Those are the two tokens Step 5a's parser keys on to find fix items and the paths to back up. A notes document that used them would parse as a fix plan — and a plan is a thing an executor edits files from. The differing filename is the first guard and this is the second, because the failure is silent and irreversible where every other guard here costs a re-run.

For the same reason the document carries `Status: NOT APPLIED`, which is not the `Status: APPROVED` the plan parser requires. Three independent things would have to go wrong together.

**Write the document even when D found nothing** — an empty Notes section and a line saying the pass ran. A missing file is indistinguishable from a pass that was skipped, and those are different facts. When D was not dispatched at all, write no document and say so in the report header instead.

### Performance notes the user declined

Same problem as declined findings, same shape of answer. D produces notes from judgment rather than from a scanner rule, so `--since` and `declined.json` cannot reach them: without somewhere to record a rejection, the same five notes come back verbatim on every run until the code changes.

Keep `.code-winnow/perf-declined.md`. When the user dismisses a note, append it with the reason:

```markdown
# Declined performance notes

Persistent across runs. Delete an entry to re-open the question.
Matched on path plus anchor text; the line number is ignored, because lines shift.

- src/Dash.cs | GetComponent<Rigidbody>() in Update
  declined 2026-08-03 — profiled at 0.02ms, not hot
- src/Boot.cs | config parsed twice at startup
  declined 2026-08-03 — startup only, don't care
```

Hand it to D on every later run. D skips matches and reports the count rather than listing them.

**Matching is by path plus anchor, never by line number** — the same rule `declined.json` follows and for the same reason. A note declined at line 22 is the same note when an unrelated edit moves it to line 40, and matching on the line would resurrect it.

This file is persistent: it lives beside `declined.json` and is not archived into a round folder, because its name does not start with the stem prefix the rotation matches. See the layout block in Step 2 — that property is load-bearing and easy to break with a rename.

### Findings outside the named feature

Only when Step 1 resolved a feature. Same discipline as pre-existing flaws, for the same reason: it is a courtesy, and a courtesy that takes over the report stops being one.

This is what the scanner found outside the confirmed scope, plus anything A, B, C, D or E happened to notice at its edges. **Nobody swept for it** — no agent reviewed those files, and the scanner had already run over the whole diff anyway. Report it as a courtesy: top three by severity, a count for the rest, two sentences each, no proposed patches, no severity debate.

```
### In the diff, outside "dash cooldown"  (not swept)
- `Inventory.cs:22` — Bare `except` around the reload path. Converts a failed reload into a silent empty inventory.
- `UIPanel.cs:9` — Field `pendingRefresh` declared and never read.
- ...and 6 more. Say the word for a full pass over these.
```

These never enter the fix plan and are not eligible for Step 5. Fixing one takes a second, explicit approval — and the honest way to get it is to offer a proper pass, not to slip them into a cleanup the user scoped to something else.

**Agent S's `unsure` files are not in this section**, and neither are scope appeals. Both were questions put to the user; filing either here reads as "reviewed and set aside", which is the one thing they are not. If the user answered an `unsure` with "out", it lands here like any other out-of-scope file — but only after they said so.

**Say what the out-of-feature files did not get**, because a partial pass reads as a complete one. The agents judged what they happened to see there; nothing systematic ran. A mock-only test in a file nobody opened is absent from the report entirely, and the header's `3 of 12 files` otherwise reads like coverage of twelve:

```
9 files in the diff were not reviewed — scanner only, plus whatever the agents
noticed in passing. Findings there are incidental, not a coverage claim.
```

One consequence worth knowing rather than fixing: these are never presented as decisions, so they can never be declined, so they persist in every later run. If one keeps returning and the user does not want it, the answer is to judge it properly in a scoped run — not to decline something that was never offered.

### The header convention gate

**Any finding that touches a copyright, license, or SPDX line goes through this gate** — whichever branch of Agent C produced it, and whether it was framed as a convention conflict or as a stale-doc correction. Do not fold it into "fix all".

That routing matters more than it looks. The gate was written for the convention branch, so a finding phrased as *truth* — "this new file says `SPDX-License-Identifier: GPL-3.0-only`, but the repo is MIT" — would otherwise land in "Doc fixes — approved" as an ordinary P2 with a proposed rewrite, and get swept up by "fix all". Silently relicensing a vendored file is a strictly worse version of the thing the gate exists to prevent, arriving through the ungated door. A license line is never an ordinary doc finding.

If Agent C found a header conflict, **ask before proposing any header edit.**

```
Header convention: the 9 new .cs files in this diff carry no file header. The repo's
other 214 first-party .cs files open with:  // Copyright 2019 Acme Ltd. All rights reserved.
  1. Add that header verbatim to those 9 files — its own section in the fix plan
  2. Report only, change nothing
```

**Quote the header you are proposing, in full.** The user is being asked to assert a company name and a year onto files; they cannot answer that from the word "the repo's header". A 2019 notice on a file created this year is wrong in a way only they can see.

**Cap it at ten files.** Past that, do not offer option 1 at all — say *"N of the files this change adds carry no header; want a header pass as its own change?"* and stop. Both bounds on eligibility are keyed to diff membership, which sounds narrow and is not: a scaffolded change that adds 200 files makes all 200 eligible, a one-line API sweep across 150 files makes all 150 "modified", and the user answers `1` once and gets the 200-file diff this skill opens by refusing. Diff membership limits *which* files; only a count limits *how many*.

Two reasons this is a gate and not a finding like any other. Header edits are bulk and mechanical, so "fix all" would sweep them in unread — and bulk mechanical edits are the thing this skill calls the most reviewer-hostile content in a generated diff. And a header carries a license claim: adding a copyright line to a file is an assertion about ownership, which is not a call this skill gets to make.

Severities for header findings are in Agent C's brief above: missing is P3, wrong is P2, CI-enforced is P1. The gate applies to all three — severity decides how loudly it is reported, never whether it needs asking.

**Only files the diff added or modified are ever eligible.** If the repo's own headers are inconsistent, that is a pre-existing condition — one sentence in the report, and no further. Unattended: report only, never unify.

### Pre-existing flaws

One section, one meaning: **problems in the files this change touches, on lines this change did not touch.** Not the rest of the repo. This is a byproduct of reading around the diff, never a reason to go looking — and nothing seen during a Step 3 verification lookup belongs here either.

**"Touched" includes lines the change took away, and that is not a technicality.** A finding about a *block* — a test function, not the `def` naming it — belongs to this change when anything inside that block was added **or deleted**. Judging by the anchor line alone is blind in the one direction this skill exists to look: delete a generated test's only assertion and every surviving line is untouched, so the now-assertionless test files as pre-existing and drops out of the default run. The change created a P1 and the scan reports nothing.

Two sources feed it, and both are optional:

- What the Step 3 agents noticed while reading around the diff. This is the usual source and needs no extra command.
- `"$PY" "$WINNOW/scripts/scan.py" $SCOPE --whole-files --stem "$STEM-preexisting" --json > ".code-winnow/$STEM-preexisting.json"` — the same scan widened to the untouched lines of those same files. **This is the only thing that populates the scanner's `preexisting` findings**, so run it if you want the deterministic half; skip it on a large diff, where it mostly adds P3 noise about code the user did not write today. Either way, say which you did.

Log every one in full to the report file. In the user-facing output, give each **at most two sentences: one for what it is, one for what it does.** Then stop. Expand only on request.

> `AudioManager.cs:88` — Coroutine started in `OnEnable` is never stopped in `OnDisable`. Toggling the object leaks a coroutine per cycle, so audio triggers stack up over a session.

Not three sentences, not a proposed patch, not a severity debate. The user asked for a review of their change; pre-existing findings are a courtesy, and a courtesy that takes over the report stops being one. If there are more than five, list the top three by severity and give a count for the rest.

If the pre-existing list is longer than the in-scope list, that is the signal to say so in one line — "this file has more going on than your change does, want a proper pass over it?" — and let the user decide. Deciding for them turns a five-minute review into an afternoon.

## Step 4b — Record the approved set, and choose how to apply it

**Wait for explicit go-ahead.** This is the gate. If nobody is there to give one, write the fix plan below and **stop there**. See the unattended table; an unattended run never edits.

**An unattended plan is marked, and the mark is load-bearing.** Its header line reads `Status: UNAPPROVED — no human reviewed these findings`, and every section heading says *proposed*, not *approved*. Without that, an unattended run writes a file listing every finding under "approved", and the resume path — which exists to execute a settled list without re-opening it — turns a scheduled scan into a one-paste auto-apply of deletions nobody read. That routes straight around the gate this same document builds two sections earlier, using the mechanism it built one section later. "Entering at Step 5 cold" refuses any plan carrying that line.

### The fix plan

Once the user has approved a subset, write `.code-winnow/$STEM.fixplan.md`. It holds what the fix pass needs and nothing else, and it is the handoff contract for all three rungs below — one artifact, one standard, whoever ends up executing.

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

**`file:` is authoritative, not the prose.** Every item carries at least one `file:` line, and `line:` / `occurrence:` / `of:` / `anchor:` are the fields it pairs with; a merged X6 finding lists each group in order. The headline is for the reader.

**`line:` is what the locating rule below actually uses**, so an item without it cannot be applied — "anchor matches at the recorded location" needs a recorded location, and without one every item fails rule 1, falls to rule 2, and reports stale.

**`occurrence:` and `of:` count matching lines of the file, and both come from the scanner as `anchor_index` and `anchor_total`.** Copy `line` and those two straight out of the JSON. Together they distinguish the third `catch (Exception) { }` in a file from the first, which no other field can. **The JSON's `occurrence` field is not one of them** — it indexes findings that share a rule and message, so a diff-scoped run stamps 1 on the only instance the change touched even when the anchor is on three lines and the flagged one is the third. Copying it into `occurrence:` hands the executor an ordinal measured on a different population, and rule 2 below then edits the first matching line: untouched, unreviewed, unapproved code.

That is not decoration. Put the path inside the summary sentence and have the backup parse it back out, and you lose paths containing spaces, items with no `:LINE`, the second file of every merged finding, and anything indented under a sub-heading — while printing a success count derived from the same regex that just missed them. Prose is not a data format, and a backup that under-collects silently is worse than no backup at all.

Anchors are written **unquoted and unfenced**. Backticks inside a value break the moment an anchor contains a backtick, which doc fixes routinely do.

The user edits the plan directly — delete an item to drop it. Write it whether or not a clear happens: it is also the on-disk record of what was approved, and Step 6 reconciles against it.

### `evidence:` — the deletion-safety field

**Every item carries one, and on anything that removes code it is the load-bearing field.** Three permitted values:

- **The commands you ran and what they returned** — literally, so Step 6 can run them again. `git grep -c cachedRig -- '*.cs'` → `2`. Not a summary of a lookup: the lookup, re-executable. "Traced it" is not evidence; neither, quite, is "grepped repo-wide, 3 hits, all in this file", because a fabricated count is textually identical to a real one and the plan is written by the same agent that proposed the deletion. A command someone else can re-run is the only form of this that survives an agent having a bad day.
- **`rewrite, nothing removed`** — for a tightened comment, a corrected doc line, an inserted header. Nothing is being taken away, so there is nothing to prove safe.
- **`unverified — <the lookup you could not perform>`** — and then the item must not propose a deletion. See below.

### `tests-delta:` — on any item that changes what the suite collects

This skill removes tests on purpose: merging structural duplicates, dropping a fixture nothing requests. Those are approved changes, and they move the pass count legitimately. **So an item that changes collection declares exactly how, by name:**

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

Net zero there — parametrize expands at collection — which is exactly why the field states both sides rather than a number. A merge that quietly drops a case shows up as `-3 +2`, and the whole point is that this is visible in the plan *before* anyone approves it.

Without the field, Step 6 has no way to distinguish an approved removal from an accidental one, and the honest reading of a smaller suite would be "restore everything" — which would block legitimate work every time the skill did one of the things it exists to do.

This field exists because the instruction it enforces was already in the skill and was unenforceable. Every reference file says to verify before deleting — trace the callers, grep for the helper, check the scenes — and that instruction sits inside a long agent prompt, competing with everything else in it. Nothing downstream could tell a finding whose lookups were done from one where they were skipped, and both arrive worded with equal confidence. A field that has to be filled in makes the difference visible; a paragraph asking nicely does not.

**An `unverified` deletion is a rule violation upstream, and the executor refuses it.** `$WINNOW/references/core-patterns.md` already says an unverifiable claim becomes a confirm-question — at its own severity — and never a proposed deletion, so such an item should not have reached the plan. If one does, skip it, and report it as *"approved but unverified — not applied"* rather than applying it or silently dropping it. Rewrites with `unverified` are fine; only removal needs proof.

This is the whole correctness gate, and it is deliberately not a fourth reviewing agent. Another opinion does not make a lookup happen. A required field does.

### Locating a fix at execution time

Files change between approval and execution, so the executor locates by **anchor text, not line number**. Two things the naive comparison gets wrong:

**Normalise before comparing.** The anchor came from the scanner's `normalise_anchor`, which collapses every run of whitespace to one space, strips the ends, and truncates to 120 characters. So the plan's `private Rig cachedRig;` never equals the file's `        private Rig cachedRig;`. Apply the same normalisation to each candidate line before comparing, and treat a 120-character anchor as a prefix match. **`of:` was counted under that same normalisation**, so comparing raw lines reaches a different total and every moved item reports stale.

**Never search for a moved anchor.** Match only where the plan says, normalised:

1. Normalised anchor matches at `line:` → edit there.
2. It does not, but the file still contains **exactly `of:` matches** for the anchor → edit the `occurrence:`-th of them, counting **top to bottom**, and say the line moved.
3. Anything else — including a match count that is not `of:` — → **report the item stale and skip it.** Never search for "the one remaining match".

**`of:` is the denominator, and the ordinal is unsafe without it.** An ordinal alone is satisfied by any file with at least that many matches, so a re-run finds the *declined* twin of an already-applied fix and edits the one line the user refused — and a newly written `catch` above the target shifts every ordinal down by one. Recording the total closes both: two matches at plan time and one now means something was deleted, three means something was added, and either way the ordinal no longer identifies what it identified. Report stale — that costs a re-run, against a wrong-line edit that costs a deletion nobody approved.

**Counting is top to bottom, over matching lines, and the scanner agrees.** `anchor_index` and `anchor_total` are computed by walking the file in order under the same normalisation, which is also the only ordering a human reading the file can reproduce. Do not count findings, do not count occurrences of a *symbol* — count lines whose normalised text matches the anchor.

A fix applied to the wrong line is the worst outcome available in this whole skill, and it is silent. Skipping a genuinely-moved fix costs the user one re-run; the alternative costs them a deletion they declined.

**If several items report stale at once, stop and check `SNAPSHOT` before applying any of them.** One stale anchor is a moved line; all of them stale means the tree changed since the review, and the right response is to re-run it rather than to apply the survivors.

### Then choose a rung

By Step 5 you are carrying the diff, the scanner JSON, every agent's output, the conflict check, the report, the performance notes, and the approval conversation. The fix loop — edit, test, reconcile, sometimes debug — is the part of the run that most needs headroom and least needs that history.

**Rung 1 — clear and resume. Offer this first.**

```
Fix plan written to .code-winnow/<stem>.fixplan.md.

To apply it with a clean context: /clear, then paste

    code-winnow: apply .code-winnow/<stem>.fixplan.md
```

Say plainly what it buys, and do not oversell it: a long edit-and-test loop then runs against a small stable prefix instead of the whole review. Clearing does not carry the previous cache forward; the win is headroom and a clean prefix for the turns that follow.

**Rung 2 — fix subagents.** If the user would rather not clear, or the runtime has no equivalent, dispatch the work to a subagent with no conversation history. You stay supervisor: you merged the findings, you verify, you reconcile, **you do not edit.**

**Its prompt must carry four things, because it has never read this file** and every rule below lives only here:

1. The fix plan, and `andrej-karpathy-skills:karpathy-guidelines`.
2. **The anchor-location rules** from Step 4b, in full — normalise, match at `line:`, else *only if the file holds exactly `of:` matches* take the `occurrence:`-th counting top to bottom, else report stale. Never "the one remaining match", and never the ordinal without the total check. Without this the agent locates by line number or searches, and the search is what edits code the user struck from the plan.
3. **The `evidence: unverified` rule** — skip those items, report them, do not perform the missing lookup and proceed.
4. **"Step 5a is already done; do not run it."** Otherwise it re-runs the backup and copies half-edited files over the restore point.

**On this rung you run Step 5a yourself, once, before dispatching anything — both halves, the backup and the `Tests-before` baseline — and you tell each fix agent that both are already done and that it must not run 5a.**

Both halves of that matter. A fix agent given only the plan has never read this file, so it cannot run a step it was never told about — and if it did, the backup script copies *every* path in the plan, not just its own section. Two agents running in parallel would each snapshot the other's half mid-edit, and a header agent running last by design would overwrite the whole restore point with fixed files. The undo command would then restore exactly what the user wanted undone. That is deterministic, not a race, and the refusal now built into Step 5a is what catches it if this instruction is ever missed.

Code fixes and doc fixes can go to two agents in parallel — different files, no shared state, now that neither is copying files. **Check the `file:` sets are actually disjoint first**; if any path appears in both sections, run them in sequence. Header fixes always go last and alone: they touch line 1 of files the other agents are editing.

**Rung 3 — in place.** No subagents and no clear available. Apply the plan yourself, and say so once in the report.

## Step 5 — Apply

**Step 5a happens exactly once per fix plan, before any edit** — the backup *and* the pre-fix test baseline, since both capture a state the first edit destroys. Who runs it depends on the rung: on rungs 1 and 3 it is the executor's first action; on rung 2 the *supervisor* runs it before dispatching, because the fix agents have never read this file. Never twice — the script refuses a non-empty backup directory precisely because a second run overwrites the originals with fixed files.

### Step 5a — Make the edits reversible, before the first one

**This is not optional and it comes before any edit, including the first one you are sure about.**

The advertised default scope is uncommitted work *including untracked files*. "Fix all" then deletes lines from files that have never been in the object store — no blob, no reflog, no `git checkout --`, no `git stash pop`. The headline trigger for this whole skill is "clean this up before I commit", so the common case is precisely the one git cannot undo.

**The list comes from the fix plan's `file:` lines, not from the scanner JSON.** It copies every file the plan names — Code, Doc and Header fixes alike — and **refuses to proceed** rather than under-collecting:

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
"$PY" - "$BACKUP" ".code-winnow/$STEM.fixplan.md" <<'PY'
import os, re, shutil, sys
dest, plan_path = sys.argv[1], sys.argv[2]
whole = open(plan_path, encoding="utf-8").read()

# Fail closed on approval. The cold-entry path asks the agent to read the
# `Status:` line and stop if it says UNAPPROVED - which waves through a plan
# carrying no Status line at all, the exact shape a truncated write or a
# hand-rolled plan produces. Only the unattended path marks itself; nothing
# marks the absent case, so absence has to be a refusal too.
header = whole.split("\n## ")[0]
m = re.search(r"(?m)^\s*Status:\s*(\S.*?)\s*$", header)
if not m:
    sys.exit("REFUSING: no `Status:` line in the plan header. A plan nobody "
             "approved reads exactly like one nobody wrote a status for, so "
             "this refuses both. Add `Status: APPROVED by <who> on <date>` "
             "only if a human actually approved these findings.")
if not m.group(1).upper().startswith("APPROVED"):
    sys.exit(f"REFUSING: Status reads {m.group(1)!r}, not APPROVED. An "
             "unattended run writes UNAPPROVED because nobody reviewed the "
             "findings, and applying it would route around the Step 4b gate.")

plan = whole.split("\n## Never touch")[0]

# Count items on BOTH sides of the cut. Truncating first meant a section
# appended after "## Never touch" - which is where an edit naturally lands -
# vanished before either counter saw it, and the run printed a clean
# "backed up 1 file(s) from 1 plan item(s)".
ITEM = re.compile(r"(?m)^\s*-\s*\[.\]\s")
if len(ITEM.findall(whole)) != len(ITEM.findall(plan)):
    sys.exit("REFUSING: fix items appear after '## Never touch'. Move them "
             "above it so they are backed up.")

# A destination copied out of the plan header rather than computed. The
# header is prose: `Backup: <path>  (NOT YET MADE)` pasted into $BACKUP made
# a real directory called "  (NOT YET MADE)" inside the intended one, printed
# the usual success line, and left `Undo:` pointing at an empty directory.
if re.search(r"\(|\s{2,}", dest):
    sys.exit(f"REFUSING: backup destination {dest!r} contains a parenthetical "
             "or a run of spaces, so it was pasted from the plan header "
             "instead of computed. Use .code-winnow/<stem>.pre-fix, where "
             "<stem> is the plan's filename minus `.fixplan.md`.")

if os.path.isdir(dest) and os.listdir(dest):
    sys.exit(f"REFUSING: {dest} exists and is not empty. A second Step 5a "
             "would overwrite the restore point with post-fix content. Move "
             "it aside, or use a fresh stem.")

items = re.split(r"(?m)^\s*-\s*\[.\]\s", plan)[1:]
if not items:
    sys.exit(f"REFUSING: no fix items found in {plan_path}.")

paths, bad = [], []
for n, body in enumerate(items, 1):
    found = re.findall(r"(?m)^\s*file:\s*(\S.*?)\s*$", body)
    (paths.extend(found) if found else bad.append(n))
if bad:
    sys.exit(f"REFUSING: plan item(s) {bad} have no `file:` line, so their "
             "target cannot be backed up. Fix the plan first.")

uniq = list(dict.fromkeys(paths))
missing = [p for p in uniq if not os.path.isfile(p)]
if missing:
    sys.exit("REFUSING: named in the plan but not on disk:\n  "
             + "\n  ".join(missing))

for p in uniq:
    d = os.path.join(dest, p)
    os.makedirs(os.path.dirname(d) or dest, exist_ok=True)
    shutil.copy2(p, d)
print(f"backed up {len(uniq)} file(s) from {len(items)} plan item(s) to {dest}")
PY
```

**Any `REFUSING:` line means stop and tell the user.** Do not edit, and do not "fix" the plan by dropping the item that would not parse.

Five failure modes are designed out:

- **It fails closed on `Status:`.** A plan with **no** `Status:` line is what a truncated write, a hand-assembled plan, or one reconstructed from a report all produce — so absence has to refuse too. Only the unattended path marks itself; nothing marks the unmarked case. Step 5a is the right place because it is the one step every rung runs, cold entry included, before the first edit.
- **It counts plan items independently of the paths it captured.** A count derived from the capturing regex can never report its own miss.
- **It refuses a non-empty backup directory.** `$STEM` is pinned for the session, so a second Step 5a — a follow-up "also fix 7 and 8", or a re-run — would copy *post-fix* files over the originals and print the same success line as a healthy first run.
- **It refuses on any missing file** instead of printing a note and continuing.
- **It resolves against the git toplevel.** With `os.getcwd()`, running from a subdirectory backs up nothing and exits 0.

**Do not go back to `{f['path'] for f in data['findings']}`.** Agent C's entire purpose is producing findings on files the diff never touched, so an untouched doc has no entry in the scanner JSON at all — and it would be edited with no copy made.

Nor should you reason that a tracked file is safe because git can restore it. That is the same reasoning this step already rejects for untracked files, and it fails the same way: after three more edits there is no clean point to return to.

Then tell the user, in one line, where the copies are and how to undo:

> Backed up 7 files to `.code-winnow/currentmain_worktree_20260802-2028.pre-fix/`. To undo everything, from the repo root: `cp -a .code-winnow/currentmain_worktree_20260802-2028.pre-fix/. .` (PowerShell: `Copy-Item -Recurse -Force '.code-winnow\currentmain_worktree_20260802-2028.pre-fix\*' .`)

If the copy fails — read-only filesystem, no shell — **say so and stop.** Do not edit anyway. A cleanup that cannot be undone is not a cleanup the user agreed to, and "I could not make a backup" is a decision for them, not for you.

`git stash` is not a substitute: `--include-untracked` moves the user's work out of the tree, which is disruptive mid-review, and it still cannot be un-popped cleanly after further edits. A plain file copy inside the already-excluded workspace has none of those failure modes.

### Step 5a, second half — record what the tests looked like before

**Run the suite now, before the first edit, and save both the result and the list of test names.** Same command Step 6 will use, whole suite, no filters:

```bash
# illustration only — substitute the project's real commands
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
<the project's test command> 2>&1 | tee ".code-winnow/$STEM.tests-before.txt"
<the runner's list command>   > ".code-winnow/$STEM.tests-before.list"
```

| Runner | Listing the collected tests |
|---|---|
| pytest | `python3 -m pytest --collect-only -q` |
| .NET | `dotnet test --list-tests` |
| Go | `go test ./... -list '.*'` |
| Rust | `cargo test -- --list` |
| Jest / Vitest | `npx jest --listTests`, `npx vitest list` |
| JUnit / Gradle | `gradle test --dry-run` |
| ctest | `ctest -N` |

Then write into the fix plan's header: the command, the result, and the collected count — `Tests-before: 412 collected, 409 passed, 3 failed (test_legacy_auth, test_flaky_upload, test_win_paths)`.

**The name list matters more than the count**, because counts can coincide. Delete one test and merge two others into a parametrized pair and the total is unchanged while a real test is gone. Step 6 diffs the two name sets; a count comparison alone would call that clean.

If the runner cannot list tests, say so and fall back to counts — noting in the report that a same-count swap would not be detected.

**Without this, Step 6 cannot tell your deletion from a pre-existing failure**, and both misreadings are damaging in opposite directions. Assume the suite was green and you will chase a failure you did not cause, eventually "fixing" unrelated code to make it pass. Assume the failure was already there and you wave through the one your cleanup caused, because a red suite is easy to explain away. A baseline turns Step 6 from a judgment call into a comparison.

Finding the command: read the repo rather than guessing — `package.json` scripts, `Makefile`, `pyproject.toml`, `*.csproj`, `CONTRIBUTING.md`, and above all the CI workflow, which runs the command the project actually trusts.

| Ecosystem | Usual command |
|---|---|
| Python | `python3 -m pytest -q` |
| .NET / Unity | `dotnet test` (Unity: EditMode/PlayMode via the Test Runner or `-runTests`) |
| JS / TS | `npm test`, `yarn test`, `pnpm test` |
| Go | `go test ./...` |
| Rust | `cargo test` |
| C++ | `ctest`, or the project's harness |
| Java | `mvn test`, `gradle test` |
| Ruby | `bundle exec rspec` |
| Swift | `swift test` |

**If there is no suite, write `Tests-before: none` and say so out loud.** Then the deletion-safety pass in Step 6 is the only correctness gate the run has, which changes how carefully you should treat an `unverified` item — and the user deserves to know that before approving.

### Step 5b — The edits

**Load `andrej-karpathy-skills:karpathy-guidelines` before the first edit** — it governs how the fixes are made, and a cleanup pass that introduces its own chaff has achieved nothing. In runtimes without it, the operative parts are: make the smallest change that resolves the finding, do not rewrite what you were not asked to rewrite, state any assumption you had to make, and define what "fixed" looks like before editing.

- **Check `evidence:` before applying any item that removes code.** If it reads `unverified`, skip the item and report it as approved-but-unverified. Do not perform the missing lookup yourself and proceed — you are executing a decision, not re-making it, and on rungs 1 and 2 you have none of the context that decision was made in.
- **Re-run each `evidence:` command now, before touching anything, and require the same output.** This is the one moment equality is the right test: the tree is still exactly what the plan was written against, so the recorded counts must reproduce. A count that has **grown** means something started referencing the target between approval and execution — skip that item and say so. A count that has **shrunk** means the plan was written against a tree that no longer exists; treat it as stale, the same as a missing anchor. Items whose evidence is `rewrite, nothing removed` have no command and skip this check. Approval was given against a state of the world, and this is the only step that confirms the world is still in it.
- Deletion beats rewriting.
- One concern per edit. Do not fold a rename into a comment removal.
- Behavior stays identical. If a fix would change behavior, it is not a winnowing fix — surface it separately and leave it.
- Nothing outside the resolved scope, including formatting.
- **Nothing outside the named feature**, if there was one, and **no file the fix plan does not name.** The plan is the whole permission. Noticing something adjacent and fixing it while you are in the file is the failure this rule exists for — the user approved a list, not a direction.
- Header edits only where the Step 4 gate approved them, and only on files the diff already touched.

## Step 6 — Verify

**Three parts, in this order: the deletion-safety pass, then the test comparison, then the re-scan and reconciliation.** The safety pass is written last in this file because it needs the vocabulary the other two establish, but it is the one to run first — it is the only check in the whole run that looks at what is *gone*, and the two below it can only see what is there.

**Re-run the whole suite** — the same command Step 5a recorded, and paste the actual output. See `superpowers:verification-before-completion`: no success claim without a command and its result.

**The whole suite, every time.** No `-k`, no `--last-failed`, no single test file, no "just the tests near what I changed". This skill's fixes are deletions, and a deletion's blast radius is wherever the deleted thing was referenced from — which is precisely what you could not see. A targeted re-run confirms the one place you already thought about.

**Then compare against `Tests-before`, do not check for green:**

| Reading | What it means |
|---|---|
| Same failures as before, no new ones | **Pass.** Report the pre-existing failures as pre-existing; do not chase them, and do not "fix" unrelated code to clear them |
| A failure that is not in the baseline | **Your fixes did it.** Root-cause with `superpowers:systematic-debugging`, or restore that file from the Step 5a backup. Never edit the test to make it pass |
| Everything green, but the collected set changed | Check it against the plan — below |
| Baseline was `none` | Say so. The deletion-safety pass below is then the only gate this run has |

**Diff the collected test names, and reconcile the difference against the plan.** Every removal must be one the plan declared in a `tests-delta:` line:

```bash
# illustration only — substitute the project's real commands
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
<the runner's list command> > ".code-winnow/$STEM.tests-after.list"
diff ".code-winnow/$STEM.tests-before.list" ".code-winnow/$STEM.tests-after.list"
```

- Missing tests that a `tests-delta:` line declared → **expected.** Report them as "3 tests merged into 1 parametrized case, coverage preserved".
- Missing tests that **no** `tests-delta:` line declared → **a regression, even with everything green.** A deleted test, a broken collection, a file that no longer imports — all three surface as a smaller suite and as success in every summary line. Restore from the backup.
- Tests present before *and* after but with a changed identifier → an approved rename, or a merge that quietly dropped a case. The name diff is the only thing that catches this; counts can coincide exactly while a real test vanishes.

**Report the arithmetic, not a verdict:** `412 collected before, 410 after; plan declared −3 +1; reconciled, no unexplained loss.` A reader can check that. "Tests pass" cannot be checked at all.

This is the skill's own rule turned on itself. `$WINNOW/references/tests.md` calls removing a test "a coverage regression wearing a cleanup costume" — and a green run with 400 tests where there were 412 is exactly that, wearing the costume well enough that every summary line calls it success.

Then re-run the scanner with `--since` against the pre-fix JSON — **writing to a new filename**, per the Step 4 warning; `--since X.json > X.json` truncates the baseline before Python reads it and reports zero resolutions off an empty file:

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
DECLINED=""
[ -f .code-winnow/declined.json ] && DECLINED="--declined .code-winnow/declined.json"
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM-postfix" --json \
  --since ".code-winnow/$STEM.json" $DECLINED \
  > ".code-winnow/$STEM-postfix.json"
```

`$SCOPE` matters most here. Omit it and this scan resolves a different scope from the baseline it is comparing against — a `--scope branch` review reconciled against a worktree re-scan reports every untouched finding as `resolved`, which reads as "your fixes worked" for findings nobody touched.

Read the **`resolved`** array, not the raw count. Your deletions moved every line below them, so comparing line numbers between the two runs is meaningless; the reconciliation is what tells you a finding actually cleared. Anything still listed as `persisting` did not.

Then reconcile against the fix plan, which is the record of what was approved. Report three numbers plainly: **approved, applied, skipped** — with a reason for every skip, "anchor no longer present" included. An item that was approved and quietly not applied is the failure mode here, and it looks exactly like success.

Once verification passes, the backup from Step 5a has done its job. Say where it is and leave it — deleting it is the user's call, and `.code-winnow/` is already excluded from git.

### The deletion-safety pass — first in execution order, written last

**Run this on every run, before the test comparison above.** It was once written as a fallback for runtimes lacking `superpowers:requesting-code-review`, which had it exactly backwards: installing the recommended reviewer bought you *less* safety, silently. A cold reviewer reads the diff as it now stands and does not know which lines you removed — this pass is the only thing in the run that checks the removals themselves, and it is five questions.

**Agent E asked these same five questions in Step 3, and that does not make this pass redundant.** E asked them about lines A *proposed* removing, and its veto (X9) stopped the worst ones from reaching the plan. This asks them about lines that were *actually* removed — which is a different set, because the user edits the plan, items go stale and get skipped, and a cold Step 5 session executes without E's output in front of it. E prevents; this verifies. Run it even on a run where E vetoed nothing.

**Re-run every `evidence:` command behind an applied deletion and read the delta. Equality is the wrong test here.** These commands are *pre*-conditions: `git grep -c cachedRig -- '*.cs'` returned 3 at plan time **because the field was still there**, and after the approved deletion it returns nothing. Requiring the output to "still match" fails every correct deletion — the only evidence that survives a deletion unchanged is evidence that proved nothing.

Three readings, per item:

| Output now | What it means |
|---|---|
| Dropped, and nothing remains outside the files the plan names | **Expected.** The references were where the evidence said they were |
| Unchanged | **The edit did not land.** Reconcile the item as not-applied; do not record it as verified |
| Dropped, but hits remain in a file the plan does **not** name | **Those are live references to what you just removed.** The plan-time lookup was wrong, or the tree moved under it. Restore that file |

Hits remaining *inside* a file the plan names are ambiguous — a usage the fix should also have removed, or an unrelated substring — and the `Verify:` command settles it, because a dangling reference does not survive a build. Say which reading each item got.

The equality check does belong somewhere, and it is in Step 5b: run against the still-unmodified tree, where "the counts reproduce" is exactly the right question and a changed count means the world moved between approval and execution.

Then keep to the shape below. **Scope: the lines this run removed. Not the repo, not the diff, not the files they sit in.** This is a check on your own edits, which is why it does not turn the skill into the bug hunt it says it is not.

Tests are the usual gate and they do not cover this. Every item below fails at runtime, at build time, or in CI config — not in a unit test — which is exactly why they survive a green suite.

Walk each deleted line and ask:

- **Was it referenced from somewhere the compiler cannot see?** A GC root or callback reference, a side-effect import, a registration-by-construction, reflection or `getattr`, dependency injection, a serialized field read by a scene or prefab, a Blueprint, an ORM mapping, a wire-format field. The tell is that nothing references it *in source* — which is also the tell for real dead code, so the `evidence:` line is what separates them.
- **Was it a directive rather than prose?** `# noqa`, `# type: ignore`, `//go:build`, `// @ts-expect-error`, `# frozen_string_literal`, `// NOLINT`. See the Directive comments section of `$WINNOW/references/core-patterns.md`. Deleting one breaks a build or silently changes behaviour, and no test catches it.
- **Did it carry type information?** A JSDoc `{type}` in a `checkJs` project, a docstring under `pydocstyle`/`ruff` D-rules, a `<param>` under CS1573, a `///` under `missing_docs`. These are build inputs wearing comment syntax.
- **Was it validation at a trust boundary?** Re-read the caller. "Redundant" is a claim about every caller, including the one added next month.
- **Did a test lose its only failure mode?** A crash-regression test whose body you tightened, a smoke test now asserting something narrower than "it does not throw".

Anything you cannot clear: restore **just that file** from the Step 5a backup — `cp -a "$BACKUP/<path>" "<path>"`, not the whole tree, which would revert every approved fix — say why in the report, and leave it. **Restoring one line you were unsure about costs nothing. Shipping one silent runtime break costs the user their trust in the whole tool**, and they will not know which of your deletions did it.

Only once this pass is clean, hand off to `superpowers:requesting-code-review` for a cold read of the applied diff, and offer a simplification skill if a path is still hard to follow after the deletions. That pass is additive: it reviews the code that is there now, this one reviews what is gone.

## Entering at Step 5 cold

You were invoked with a fix plan rather than a review request — `code-winnow: apply .code-winnow/<stem>.fixplan.md`, or any phrasing that names one. The review already happened, in a session whose context is gone. Your job is to execute a list, not to form an opinion.

**First, check the `Status:` line — it must be present and must read `APPROVED`.** Anything else, including *no `Status:` line at all*, means stop: report that nobody has reviewed these findings and ask for approval before anything else. Absence is not permission. Step 5a enforces this with a `REFUSING:` line so the gate does not depend on you remembering to read it here, but knowing why it refused saves a confused retry.

1. Read the fix plan. It is self-contained: `Status`, `Skill` (your `$WINNOW`), `Scope`, `Feature`, `Baseline` (the pre-fix JSON for Step 6), `Backup`, `Undo`, `Verify`, then the fixes and the never-touch list. Each fix carries `file:`, `line:`, `occurrence:`, `of:`, `anchor:`, `fix:` and `evidence:` — **all five of the first are what locate the edit**, and the rules for using them are in Step 4b under "Locating a fix at execution time". Read that section; it is the one part of the review you do inherit. **`$STEM` is the plan's filename minus `.fixplan.md`.**
2. Re-run the Step 0 block. It is idempotent and it verifies with `git check-ignore` — cheap insurance against a repo where the exclusion was lost or was never valid, which in a linked worktree it silently was not. This is the one part of Steps 0–4b you *do* run.

   Then look at `.code-winnow/env.sh` before running anything that sources it. **It is from the session that wrote the plan, and it may name a different `$STEM`** — a later review in the same repo overwrites it, and a plan copied to another machine has none at all. Every block below opens with `. .code-winnow/env.sh`, so a stale file silently redirects the backup and the reconciliation to another run's filenames. If its `STEM` does not match the plan's own name, or the file is missing, set `WINNOW`, `PY`, `STEM` and `BACKUP` yourself at the top of each call. **Derive them from the plan's filename, not by copying its header values:** `STEM` is the filename minus `.fixplan.md`, and `BACKUP` is `.code-winnow/$STEM.pre-fix`. The header's `Skill:` line is the one field to read directly, because nothing else carries `$WINNOW`.

The plan header is prose written for a human, and a value copied out of it arrives with whatever else is on that line. `Backup:` once carried a trailing `(NOT YET MADE)` marker; pasted into `$BACKUP` it produced a real directory named <code>&nbsp;&nbsp;(NOT YET MADE)</code> nested inside the intended one, the backup script printed its usual success line, the non-empty-directory refusal never fired because the intended path was still empty, and the plan's own `Undo:` command then restored nothing. Step 5a now refuses a destination with a parenthetical in it, but the durable fix is to compute the path rather than parse it.
3. Step 5a — the backup, from the plan's `file:` lines. Any `REFUSING:` line means stop and say so. Then run the `Verify:` command **before editing** and fill in `Tests-before:` yourself if the plan does not already carry it. A cold session inherits no memory of what was green, and Step 6 is a comparison against that number.
4. Step 5b — the edits, located by normalised anchor, per the rules in Step 4b. No searching for moved anchors. **Any item that removes code and whose `evidence:` line reads `unverified` is skipped and reported, not applied** — and not researched. You have none of the context that decision was made in, which is the entire point of starting cold.
5. Step 6 — verify, reconcile against `Baseline`, report approved / applied / skipped.

**What not to do, in order of how tempting it is:**

- **Do not re-run Steps 1 through 4.** You will land at the top of this file and the whole review will look like the obvious first move. It is not. It burns the context the plan exists to save and re-opens decisions the user already made.
- **Do not re-review the code.** You have no scanner output and no judgment agents, so anything you notice is a fresh unreviewed opinion arriving after the approval gate.
- **Do not add findings.** If a fix looks wrong to you, say so and skip it. Say it in the report; do not act on it.
- **Do not touch a file the plan does not name**, however obvious the adjacent problem.

A struck-through or deleted line in the plan means the user dropped that fix. Honour it silently — do not ask why, and do not re-propose it.

If the plan is missing, unreadable, or names a backup directory that already contains files, stop and say so rather than guessing. A half-applied plan re-applied from the top is how a clean revert becomes impossible.

## Never touch

These look like chaff and are load-bearing:

- **Validation at trust boundaries** — user input, network payloads, deserialization, file parsing, plugin APIs. Redundant-looking checks at an edge are the point. "Defensive overkill" applies only to internal callers you control.
- **Comments explaining why** — workarounds, engine quirks, business rules, issue links. Delete comments that restate code; keep comments carrying information code cannot.
- **Public API surface** — exported names, serialized fields, `UPROPERTY`/`[SerializeField]`, anything Inspector- or Blueprint-facing. Renaming these is a breaking change wearing a cleanup costume.
- **Test scaffolding** — fixtures, fakes, builders, and `TODO`s in test files are normal, and a little repetition in them beats cleverness.

  This is not a blanket pass for test files, and treating it as one is how false coverage survives review. A test that asserts nothing, asserts a tautology, or asserts only that a mock was called is not scaffolding — it is a test that cannot fail, and P1 is the right severity for it. The fix is almost always to tighten the assertion, never to delete the test: removing a test is a coverage regression wearing a cleanup costume. See `$WINNOW/references/tests.md`.
- **File headers matching the repo's convention** — a copyright or license block identical across two hundred files is doing its job by being identical. Concision does not apply to boilerplate that exists to be uniform. Headers are only ever edited through the Step 4 gate, only on files the diff already touched, and never to make the repo consistent with itself.
- **Anything a line E calls load-bearing** — a GC root, a directive comment, a type carrier, a trust-boundary check, a registration anchor, a side-effect import. E's veto in Step 3.5 outranks A's deletion, and the finding moves to "Deliberately left alone" with the mechanism named.
- **Anything outside the diff** — report it under Pre-existing, in two sentences, and move on. The one exception is a documentation line the change made false, which Agent C reports with both lines cited.
- **Anything outside the named feature**, when the user named one — the boundary Agent S drew and the user confirmed. It goes in the outside-the-feature section as a byproduct and is not eligible for a fix. An `unsure` file, or an agent's appeal to move the line, is a question for the user — never something you settle yourself.

## Worked examples

**Restated comment**

```python
# Get the user by id
def get_user(user_id: int) -> User:
```
P3. Delete. Costs a line, buys nothing.

**Looks like chaff, is not**

```cpp
// Cannot use FVector::Normalize here — UE 5.4 returns zero vector on
// near-zero input, which breaks the dash at low stick deflection.
```
Keep, and list under "deliberately left alone". Exactly the comment a future reader needs.

**Same line, opposite calls**

```csharp
if (config == null) throw new ArgumentNullException(nameof(config));
```
Private method called once from three lines up: P2, delete. Public entry point on a plugin API: leave it. The caller decides, not the syntax.

**Comment concision (Agent B, TIGHTEN)**

Before: `// This method is responsible for handling the calculation of the total damage, taking into account the armor value of the target as well as any active buffs.`
After: `// Armor applies before buffs — order matters, see #412.`
