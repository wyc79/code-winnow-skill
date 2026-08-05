---
name: code-winnow
description: 'Use when the user wants generated-code chaff removed from an uncommitted change or a branch — "winnow", "de-slop", "deslop", "clean this up before I commit", "does this look AI-written", "make this idiomatic", "cut the slop" — or is about to open a PR on agent-written code, or a large generated change just landed. Also use when asked to apply or resume an approved cleanup: "apply the fix plan", "code-winnow: apply <path>.fixplan.md". Not for general code review, bug hunts, or security audits.'
---

# Code-winnow

Generated code fails review in predictable ways. It is rarely wrong; it is bloated, over-defensive, and stylistically foreign to the repo it landed in. Linters catch the subset that is a rule violation. The rest is judgment, and that is the gap this skill fills — winnowing, in the old sense: keep the grain, blow off the chaff.

**Needs Python 3.9+ and git.** It writes reports, a fix plan and file backups under `.code-winnow/`, and git-excludes that path in Step 0. Companion skills are optional; `$WINNOW/references/portability.md` has the degraded paths.

> **Were you invoked to apply a fix plan?** If the request names a `.code-winnow/*.fixplan.md`, or asks to apply or resume an approved cleanup, go straight to **"Entering at Step 5 cold"** near the end of this file. Re-run Step 0 — it is idempotent and it verifies — then skip Steps 1 through 4b entirely. The review already happened; re-running it wastes the context the plan exists to save and re-opens decisions the user already made.

## Steps at a glance

| Step | What it does | Writes |
|---|---|---|
| **0** | Git-excludes `.code-winnow/`, **verifies**, lays down the root scaffold | `.git/info/exclude`, `README.md`, `utils/` |
| — | Read `core-patterns.md` and `comment-evidence.md`; check companion skills | `substitutions.md` |
| **1** | Resolve the review scope; if a feature was named, dispatch **Agent S** and confirm the boundary with the user | — |
| **2** | Deterministic scan; pin the stem; **create this run's round** | `env.sh`, `round-NN/{meta.json,scan.json}` |
| **3** | Build the review input, then dispatch **A B C D E** in parallel | `round-NN/input.diff` |
| **3.5** | Conflict check — merge their outputs across ten classes, yourself | — |
| **4** | Write the report and the performance notes, then regenerate the index. **Never edits** | `round-NN/{report.md,notes.md}`, `README.md` |
| **4b** | Wait for approval; write the fix plan; choose a rung | `round-NN/fixplan.md` |
| **5a** | Back up every file the plan names; record the test baseline | `round-NN/{pre-fix/,tests-before.*}` |
| **5b** | Apply the approved items, located by normalised anchor | the user's files |
| **6** | Deletion-safety pass → test comparison → re-scan and reconcile | `round-NN/{scan-postfix.json,tests-after.list}` |

Everything a run writes is inside `.code-winnow/round-NN/`, under a fixed short name. The root holds the index, the persistent files and `utils/`, and nothing is ever moved between rounds. `round-NN/README.md` lists the folder's contents; `round-NN/meta.json` records what the round compared to what.

Reference files, all under `$WINNOW/references/`: `core-patterns.md` (universal judgment standard, **read it yourself**), `comment-evidence.md` (the X1 grading rule — **also yours**, and nobody else's), `docstrings.md` (Agent B's, and C's), `agent-prompts.md` (the six dispatch prompts), `report-format.md` (every artifact's shape), `fragility.md`, `performance.md`, `tests.md`, `portability.md`, and one per claimed language — `python.md`, `csharp-unity.md`, `cpp-ue5.md`, and `web.md` for JavaScript/TypeScript, HTML and CSS together, because a `.vue` or `.svelte` file is all three. Each file names its own readers at the top; hand an agent what its prompt asks for and nothing else, since every extra file is paid five times over on a parallel run. `$WINNOW/scripts/scan.py` is the scanner; `$WINNOW/scripts/backup.py` is Step 5a. Maintainers editing the snippets in this file should read `DESIGN.md` in the repo root, which holds the near-miss rationale for every mechanical choice below.

## The scope rules

**Scope discipline is the whole game.** Operate only on lines the current change added or modified. A cleanup pass that wanders into untouched files produces a diff nobody can review, which is a worse outcome than the chaff you removed.

**If the user names one feature, that is the scope** — not the whole diff, even when the diff is a branch against a base. "Winnow the dash cooldown work" means the hunks that feature touched and nothing else, however much chaff is sitting three files away. Touching unrelated code inside an approved diff is the same failure as wandering outside it: the user gets back a change they did not ask for, mixed into one they cannot separate it from. Step 1 resolves the feature set and states it back before anything is reviewed.

**This is a diff review, not a repository audit.** Unless the user asks in so many words for a whole-repo pass, the job is the current change and nothing else. Pre-existing problems reach the report only as byproducts — you had the file open to review the diff, you noticed something, you mention it. Do not go looking, do not sweep for vulnerabilities, and do not let incidental findings grow past a short aside. Someone who asked you to winnow a branch and got a repo-wide defect list back did not get what they asked for, and the thing they did ask for is now buried.

**Two passes look like exceptions to that and are not.** Agent E asks how the change breaks silently, and Agent D asks what it made slow. Both are bounded by gates as hard as the scope rule itself — E reports only what the diff did and only when no test could catch it, D reports only what it can attach a frequency to — and both work on diff lines like everyone else. E is not a security review and does not go looking for vulnerabilities; it asks whether *this change* removed a protection, committed a credential, or introduced a failure with no signal. Those three, and nothing else in that direction. `$WINNOW/references/fragility.md` and `$WINNOW/references/performance.md` hold the gates, and an agent that cannot open them will produce exactly the unbounded critique this paragraph refuses.

**The rule is about what becomes a finding, not about what you may read.** Only lines the diff touched can produce one. Reading elsewhere is permitted for exactly three purposes, and none produces a finding however bad the code you pass through looks:

| Purpose | Cap | What it is |
|---|---|---|
| Learning the repo's conventions | **Three files** | *Reviewing* neighbouring code to see how this repo writes things |
| Verifying that a deletion is safe | Uncapped | Grepping for an existing helper, tracing callers, checking scenes for a serialized field |
| Sampling file headers for their shape | Uncapped, top 15 lines only | Extracting a boilerplate shape, not reading the files |

The last two are uncapped because they are lookups, not reviews — you are answering a yes/no about a specific line, not forming an opinion about someone else's file. The three-file cap binds only the first, and stretching it to cover a grep is how "verify before you delete" quietly becomes "delete without checking".

**Three rings, then.** The repo, which you may read and never report on. The diff, which produces findings. The named feature inside it, when there is one, which is the only thing eligible for a fix. When no feature is named the inner two rings are the same and nothing changes.

**Six languages are claimed, in two tiers.** The full tier is Python, Unity C# and Unreal C++: a reference file each, structure-aware scanner rules, and tables checked against their toolchains. The web tier is JavaScript/TypeScript, HTML and CSS, sharing `web.md`, with **regex-level scanner rules only** — there is no JavaScript parser in a stdlib-Python scanner, so nothing deterministic here finds an unused binding, a dead function or a near-duplicate component in a `.ts` file. The judgment standard is as thorough for those three as for the other three; the layer under it is thinner, and the report has to say so rather than let a quiet scan read as coverage. Any other language gets the universal pass and ordinary judgment, under one rule that overrides the rest — **when you cannot say what a line is for, keep it.** A directive list that is missing your ecosystem's suppression looks exactly like a list that is complete, right up until the deletion. `references/core-patterns.md` states this as "What this skill actually claims"; say in the report which languages the diff touched and which of them were the claimed ones.

**Two documented exceptions, and only two.**

1. **Pre-existing flaws in the files the diff touches**, on lines it did not touch — capped at two sentences each, reported as a courtesy, never swept for. Step 4 defines it.
2. **A documentation file the diff never touched**, when a specific line of the diff makes a specific line of that doc false. That is not a pre-existing flaw — it did not exist before this change, the change created it, and it is the author's business. Agent C owns it; the bounds are narrow and capped: cite both lines, or say nothing.

Both are courtesies with hard limits, not licence to widen. Everything else outside the diff you may read and must not report.

## Before you start

**Resolve `$WINNOW` before anything else.** It is the absolute path of this skill's directory — the one containing this file, `scripts/` and `references/`. Every scanner call and every reference path below is written against it, because a bare `references/…` or `scripts/scan.py` only resolves when the cwd is the skill folder, which is never where the repo is.

**Then read `$WINNOW/references/core-patterns.md` and `$WINNOW/references/comment-evidence.md` yourself, before Step 3.** Not only the agents — *you*. Two steps are yours alone and neither can be executed from a pointer: Step 3.5 arbitrates comment evidence against the grading rule in `comment-evidence.md`, and Step 6's deletion-safety pass checks removals against `core-patterns.md`'s directive-comment table. On a parallel run you dispatch the judgment agents and would otherwise never open either, then make both judgments against a filename.

`comment-evidence.md` is yours and only yours — the agents tag claims, you grade them — which is why it is a separate file rather than a section every agent would carry the cost of.

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

Any of these may be absent — including on Claude Code, where the set installed varies by user. `$WINNOW/references/portability.md` has the detection, the degraded path, and the install route for each, plus the notice format. Substitutes the user has already chosen are recorded in `.code-winnow/substitutions.md`; read it before asking anything — **after Step 0**, since writing it is what makes Step 0 have to come first.

## Step 0 — Make the workspace invisible to git

Before writing anything — including `.code-winnow/substitutions.md` — ensure `.code-winnow/` is excluded. **Prefer the local exclude file:**

```bash
cd "$(git rev-parse --show-toplevel)"
WINNOW="<absolute path to this skill's directory>"   # quoted — see Step 1
EXDIR="$(git rev-parse --git-common-dir)/info"       # --git-common-dir, NOT --git-dir
mkdir -p "$EXDIR" .code-winnow
grep -qxF '.code-winnow/' "$EXDIR/exclude" 2>/dev/null \
  || printf '\n.code-winnow/\n' >> "$EXDIR/exclude"

if git check-ignore -q .code-winnow/; then
  echo "workspace excluded"
else
  echo "EXCLUSION FAILED — stop here, write nothing"
  exit 1
fi

# The root scaffold, copied only now that the exclusion has been verified —
# writing it into an unexcluded workspace is the exact self-dirtying this step
# exists to prevent. Per-file existence tests, never `cp -n`: that flag is a
# GNU/BSD extension, and a shell that ignores it overwrites a populated index
# with a blank skeleton and carries on. This step is idempotent and cold entry
# at Step 5 re-runs it, so clobbering here is not hypothetical.
mkdir -p .code-winnow/utils
[ -f .code-winnow/README.md ] \
  || cp "$WINNOW/scaffold/root/README.md" .code-winnow/README.md
```

**Verify, do not assume.** If the failure line prints, stop and tell the user. The `exit 1` is what stops the scaffold copy below it from running anyway.

Five things in that block are load-bearing and each has a near-miss that looks right: `--git-common-dir` rather than `--git-dir`, `printf` rather than `echo`, the `mkdir -p`, the `[ -f … ] ||` guard rather than `cp -n`, and the copy sitting *after* the check rather than beside it. Do not simplify any of them — `DESIGN.md` has what each one prevents.

Use `.gitignore` only if the user wants the exclusion shared with their team, and only after telling them it will appear in the diff.

The scanner also hard-skips its own workspace directory, so a run started before this step still will not review its own reports. That is a backstop, not a reason to skip Step 0.

## Step 1 — Resolve the review scope

Let the scanner do it. `--scope auto` (the default) takes the **union of all uncommitted work**: staged, unstaged, and untracked files. If the working tree is clean it falls back to the branch diff against a discovered base.

**On a branch with commits *and* a dirty tree, `auto` reviews the uncommitted work only** — the fallback to the branch diff happens when the tree is clean, not otherwise. The scanner puts the gap in `warnings` (`this branch is N commit(s) ahead of 'main' - that work is NOT being reviewed`). **When you see that warning, ask** — "your branch has 3 commits I am not reviewing; want the whole branch (`--scope branch`) or just the uncommitted work?" It is one question and the two answers review different code.

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

Three things there are not stylistic. **Quote `WINNOW`** — unquoted, bash eats every backslash and a Windows path becomes garbage. **Test the interpreter, do not just locate it** — `command -v python3` finds the Microsoft Store stub, which exits 49. **Pin `$SCOPE` and pass it on every later scanner call** — each omission silently reviews a different thing. Step 2 writes all three to a file so no later block has to remember them.

Three things this handles that a hand-rolled `git diff` ladder does not:

- **Untracked files are in scope.** They are invisible to `git diff` in every mode, and brand-new files are exactly where generated code concentrates.
- **One staged file no longer eclipses the rest.**
- **The base branch is discovered**, in order: `origin/HEAD`, then `main`, `master`, `develop`, `development`, `trunk` — each tried as a local ref then as its remote-tracking form. `--base` overrides. Branch scope diffs the **merge base against the worktree**: the merge base on the near side, so commits that landed on the base after you branched do not appear as your changes, and the worktree on the far side, so uncommitted work on the branch is in scope. That is the same content the review input is built from — see Step 3.

State the source and file count before continuing — `files`, `scanned_files` and `added_lines` come straight out of the JSON. If the user pointed at specific files, honor that and say so.

### If the user named a feature

They can ask for a branch review and still mean one slice of it: "winnow the dash cooldown work", "just the retry logic", "only the parts touching the save system". Take that literally.

**Do not try to compute the scope. Pass the user's words to the agents and let them judge it.** Resolving the phrase to a hunk or line set up front and filtering mechanically fails at both ends — hunk ordinals mean different things to the scanner and the agents, and the user was not thinking in code structure when they asked. Deciding what belongs to a feature is a judgment about intent, and judgment is what the agents are for. So carry the request, do not compile it.

**Dispatch Agent S first** — its prompt is in `$WINNOW/references/agent-prompts.md`. It gets the input diff and the user's phrase verbatim, and nothing else: no scanner JSON, no conversation history, no design rationale. **Do not produce the reading yourself.**

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

**A, B, C, D and E then receive the confirmed scope as a rule, not a hint** — the file and region list, plus the user's phrase for context. They do not re-derive it. They may **appeal** the boundary, and appeals go to the user with the report, never applied silently. That keeps the one thing a reviewing agent genuinely knows better — it has read the code — without letting every agent redraw the line.

Ask, because you are guessing from a phrase. A reading that is silently one file wide reviews code the user did not ask about; one that is silently one file narrow misses the thing they did. Neither is visible in the output. Unattended: Agent S still runs, but nothing confirms it, so take its `in` set only when it returned no `unsure` at all — otherwise **widen to the whole diff and say so**.

When no feature is named, none of this happens: no Agent S, no tags, no appeals, and the diff is the scope.

The fix plan records the feature as the user's phrase plus the files that survived, so a cold executor inherits the constraint in the form it was actually decided.

Three things the feature set governs, and three it does not:

| Governs | Does not govern |
|---|---|
| What A, B, C, D and E review at all | What the scanner scans — **always the whole diff** |
| Which findings are live in the report, and which notes D writes | What `<stem>.json` contains — always the full scan |
| Which findings reach the fix plan | What you may read for verification |

**That first "does not" is load-bearing.** A narrowed `<stem>.json` would make the next run's `--since` report every out-of-feature finding as `resolved` — a page of "no longer true" claims about findings that are all still true. The filter lives at the report layer and touches nothing the scanner writes.

Findings outside the feature are a byproduct, handled exactly like pre-existing ones — see Step 4.

### The four-field integrity check

A typo'd `--base` finds no such ref, records it in `warnings`, and returns an empty scope — which prints as a clean branch. So the check is four fields, not three:

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

**Two warnings are benign and must not be read as a failed scan.** A missing `--since` or `--declined` file warns `could not read … - ignoring it`; on a first run, or in any repo with no `declined.json` yet, that is the normal state. Guard them instead of passing them unconditionally:

```bash
# illustration only — the guard pattern; env.sh does not exist until Step 2
DECLINED=""
[ -f .code-winnow/declined.json ] && DECLINED="--declined .code-winnow/declined.json"
"$PY" "$WINNOW/scripts/scan.py" $SCOPE $DECLINED --json
```

Everything else in `warnings` is real.

**Binary files, and files that *look* minified, set `complete: false`.** They are unreadable, not skipped — only vendored and oversized paths carry the `skipped:` prefix that exempts them. Note the asymmetry: a file *named* `app.min.js` matches the vendored-path pattern and is exempt, while an unminified-looking name whose content has very long lines is unreadable and holes the scan. Check `errors` for what was actually unreadable: a binary asset in the diff is expected and means nothing, while a source file that failed to decode means the review missed code.

**Check the size before dispatching.** If the diff runs past a few hundred changed lines across many files, say so and offer to split it — by directory, by commit, or by language — rather than handing an agent more than it can hold. A judgment pass over a diff that overflowed its context returns confident nonsense. Unattended, split it yourself by top-level directory rather than asking.

**Split the dispatch, never the scope.** `--paths` looks like the tool for this and is not: it converts a diff review into the repo audit this skill exists to refuse. Instead run the same scope once, then hand each agent a subset of the **files** and give each subset its own section in one report. Split on file boundaries, never inside a file.

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
  README.md            the index — regenerated at the end of every round
  env.sh               this run's state
  declined.json        persistent across runs
  perf-declined.md     persistent across runs — Agent D's notes the user dismissed
  substitutions.md     persistent across runs — companion-skill substitutes
  utils/               helper scripts a run wrote, shared across rounds
  round-01/
  round-02/
    README.md          what is in a round folder
    meta.json          what this round compared to what
    report.md  fixplan.md  notes.md
    agent-S.md  agent-A.md  agent-B.md  agent-C.md  agent-D.md  agent-E.md
    scan.json          the pre-fix baseline, written once in Step 2
    scan-postfix.json  scan-preexisting.json  scan-vs-round-01.json
    input.diff
    tests-before.txt  tests-before.list  tests-after.list
    pre-fix/           Step 5a backup
    scratch/           everything else this run produced
```

**The root holds no run artifacts at all.** Every file a round produces lives in that round's directory from the moment it is written, and nothing is ever moved between rounds. Rotation is `mkdir`. Prior rounds stay readable and stay reachable by `--since`; nothing is deleted.

**The per-round file list above is exhaustive.** Anything a run generates that is not on it goes in `round-NN/scratch/`, and any script it writes goes in `.code-winnow/utils/`. Both directories ship in the scaffold and therefore already exist when an agent needs one — which is the difference between a rule that is obeyed and a rule that is merely read. A previous run left nine intermediate files at the workspace root because no rule named them, so no rule constrained where they landed.

**Filenames inside a round say nothing about what was reviewed**, which is the point — they are short and identical every round. The scope lives in `meta.json` and in the three-line identity block at the top of every markdown file. Never reconstruct it from a filename.

**The persistent files stay at the root, and that no longer depends on an accident.** It used to rest on none of their names starting with `current`, the prefix the archive glob matched; now nothing globs the root, so it is structural. That is what makes "declined" mean *permanently* declined.

Stdlib only, no install step. Paths resolve against the git toplevel, so the cwd does not matter as long as it is inside the repo. The default pass gives in-scope findings; that is the run that matters. `--whole-files` widens to the untouched lines *of the files the diff already touches* — no further. There is no repo-wide mode.

It flags regex- and AST-level candidates: fields and locals declared and never referenced, fields only ever incremented and never read, locals assigned and never used, variables that just rename another for a single use, log-and-rethrow, empty Unity lifecycle methods, `async` with no `await`, unrooted `UObject*` **members**, invisible Unicode, comments restating the line below, and committed credentials in a recognised vendor format.

**On the web tier it also flags** a `debugger` statement, a focused test (`describe.only`, `fdescribe` — P1, because every other test in the file is silently skipped and the run still passes), `console.log` left in source, `JSON.parse(JSON.stringify(…))`, an ARIA role restating its own element, HTML attributes obsolete since HTML5, vendor prefixes settled for a decade, `transition: all`, and empty CSS rules. **These are the whole of the web-tier rule set** and they are regex-level — `check_universal` and the generic test pass run on a web file too, as the paragraphs below describe. A `.vue`/`.svelte`/`.astro` file gets all three languages' rules, because it is all three — with one exception: the empty-rule check runs only in a real stylesheet, since `methods: {}` in a script block matches it exactly. Two rules are narrower than their names suggest and a report should not round them up: `fdescribe`/`fit` are only flagged inside a file that looks like a test file (`fit` is also how you fit a curve), while `describe.only` is flagged anywhere; and the vendor-prefix rule is a **named list of settled properties**, not a `-webkit-` sweep, so `-webkit-line-clamp` and its five siblings are correctly silent rather than missed.

**Two classes are deliberately not scanner rules, and a run that assumes otherwise reports them as absent.** *Unused imports, `using` directives and `#include`s* belong to Agent A: every claimed language already has a linter that finds them, so a scanner rule would duplicate the tool while this skill's value is knowing the handful of cases where the tool is wrong — a side-effect import, a `using` alias, a transitively-needed header. *Em and en dashes in documentation prose* belong to Agent C: the judgment is whether the diff's docs read differently from the repo's, and that comparison needs a sample of the base branch, which the scanner does not read. Both are in `core-patterns.md`; neither will ever appear in `scan.json`.

**`committed-secret` is the one rule whose findings never enter the fix plan** — and the same holds for Agent E's credential findings, which are the judgment half of the same concern — at any severity and however clearly they are worded. Deleting the line does not un-leak the credential; it is already in the object store, in every clone, and in every CI cache that fetched it. The fix is to rotate, which is not a behaviour-preserving edit and not this skill's business. Report it, say "rotate it", and propose no patch. A cleanup that quietly deleted the line would hand the user an all-clear they have not earned, which is worse than not detecting it.

In test files it additionally flags tests with no assertion, assertions that cannot fail, tests whose every assertion checks a mock, structurally identical tests that differ only in literals, and skips with no reason. That pass runs for pytest/unittest, NUnit/xUnit/MSTest, GoogleTest, Go, Jest/Vitest/Mocha, JUnit, Rust, RSpec, and XCTest — a JS or Go test file gets it even though nothing else here understands JS or Go. `$WINNOW/references/tests.md` is the judgment standard.

**Three of the scanner's test rules are narrower than that list suggests, and a report written from the list alone will claim coverage that did not happen:**

| Rule | Actual reach |
|---|---|
| `unused-fixture` | **pytest only.** It is emitted from the Python checker and nowhere else. An unrequested `[SetUp]`, `beforeEach` or `TEST_F` fixture is invisible to the scanner in every other language — judgment-pass work, not scanner work |
| `mock-only-test` | **Python: P1 when the test asserts and *every* assertion is an `assert_called*` call on a double.** A Python test with no assertions at all is `test-without-assertion`, not this rule. **Outside Python: P1 when the body verifies a mock and asserts nothing else; P2 when it does assert and every assertion checks a double.** That P2 is hedged on purpose, because verifying an interaction is legitimate when the interaction *is* the contract |
| `tautological-*` | **P1 only in Python, and only when every assertion in the test is tautological.** A mixed Python test, and every non-Python tautology, is P2 |

So when the scanner reports nothing in these categories, that is not the same claim in every language, and the report should not say it is.

(`duplicate-test` for Python needs `ast.unparse`, which is why this skill requires Python 3.9 rather than 3.8 — on 3.8 that rule finds nothing and says nothing.)

**Read `errors`, `warnings` and `complete` before you trust a small number** — the four-field check in Step 1. Vendored, generated and oversized paths are skipped by design and do not hole the scan; binary and minified-by-content files are *unreadable* and do. If *every* file in scope was skipped, `complete` is false and the exit code is 2 — that is a scan that reviewed nothing, not a clean diff.

Unused and duplicate bindings need the most judgment of anything the scanner reports. A field with no reader may be dead weight, or may be read by a subclass, a serializer, or the Inspector — the scanner marks exposed declarations at P3 with a note to confirm, and its unused-binding rule stays silent in headers and partial classes, where "never referenced in this file" is vacuous by construction. Nothing about a `[SerializeField]` or `UPROPERTY` should be deleted without checking scenes and assets.

The scanner is fast and dumb on purpose. It produces **candidates, never verdicts.** A `TODO` blocking a shipped feature and a `TODO` in a test fixture look identical to a regex.

**Capture the report stem now** — Steps 3, 4 and 6 all write files named from it, and each invocation stamps its own clock:

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

# This run gets a new round folder, and nothing is moved. A completed round is
# already whole in its own directory, and the root never held this run's
# artifacts to begin with. Creating it HERE and not in Step 0 is deliberate:
# cold entry at Step 5 re-runs Step 0, and creating a round there would orphan
# the fix plan the cold session was invoked to execute.
#
# The HIGHEST existing round number, never the count. With round-01 and
# round-03 present a count yields 03, `mkdir -p` succeeds on the directory that
# is already there, `cp -a` overwrites its fixplan.md and notes.md with the
# blank template, and the whole thing exits 0 with no output. Deleting one
# round folder is enough to destroy an approved plan in another. `sort -n`
# after discarding non-numeric suffixes, so legacy `round-01-scope-probe`
# names neither count nor collide.
LAST=$(ls -d .code-winnow/round-* 2>/dev/null | sed 's|.*/round-||' \
       | grep -E '^[0-9]+$' | sort -n | tail -1)
N=$(printf '%02d' $(( 10#${LAST:-0} + 1 )))
ROUND=".code-winnow/round-$N"

# Plain `mkdir`, not `mkdir -p`: it must FAIL if the directory exists. That is
# the backstop for any numbering mistake, and it is the difference between a
# loud stop and a silently blanked plan.
mkdir "$ROUND" || { echo "REFUSING: $ROUND already exists — numbering is wrong,"
                    echo "and continuing would overwrite that round. Stop here."
                    exit 1; }
cp -a "$WINNOW/scaffold/round/." "$ROUND/"
echo "this run is round-$N"

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
  printf 'ROUND=%q\n'  "$ROUND"
  printf 'BACKUP=%q\n' "$ROUND/pre-fix"
} >> .code-winnow/env.sh

. .code-winnow/env.sh
printf 'SNAPSHOT=%q\n' "$(snapshot)" >> .code-winnow/env.sh

. .code-winnow/env.sh
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM" --meta "$ROUND" \
  > "$ROUND/meta.json"
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM" --json \
  > "$ROUND/scan.json"
echo "stem $STEM, round $N"
```

**Every later block opens by reloading it**, because shell state does not survive between tool calls:

```bash
# illustration only — the preamble every later block opens with
cd "$(git rev-parse --show-toplevel)"
. .code-winnow/env.sh || { echo "no env.sh — restart at Step 2"; exit 1; }
[ -n "$STEM" ] || { echo "env.sh is incomplete — restart at Step 2"; exit 1; }
```

**`SNAPSHOT` is the staleness stamp.** It hashes `HEAD`, the tracked diff, and every untracked file's blob — so an edit to a file in scope changes it, and so does a commit, an amend or a rebase. Recompute and compare it whenever the tree may have moved:

```bash
# illustration only — run after sourcing env.sh
[ "$(snapshot)" = "$SNAPSHOT" ] || echo "STALE: the tree changed since the scan"
```

The whole review rests on line numbers that were true when the scanner ran. If a file changes afterwards — the user keeps working, a formatter runs, a rebase lands — the agents review a diff that no longer matches disk, every finding's line is off, and at Step 5 every anchor fails to match and the whole plan reports "stale" with no explanation of why. The stamp turns that into one sentence at the moment it happens.

Our own writes under `.code-winnow/` are excluded from the hash, so the run does not invalidate itself.

**The baseline JSON is written here, not in Step 4.** Step 3 hands it to every judgment agent, so it has to exist before they are dispatched. Step 4 reads it, and reconciles against the *previous* run's JSON, never this one's.

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
} > "$ROUND/input.diff"

[ -s "$ROUND/input.diff" ] || {
  echo "review input is empty but the scanner found files — do NOT dispatch"; exit 1; }
```

Five guards in that block, all against the same silent-empty failure, and `DESIGN.md` has what each one prevents: diffing to the **worktree** rather than `HEAD`, branching on **what the scanner reports** rather than the flag you passed, the `-s` check, the `|| git diff --cached` fallback for an unborn `HEAD`, and naming excluded files rather than dropping them.

For `--paths`, the input is the named files' full contents instead.

To cross-check which files are in scope, use `git diff --name-only HEAD` and `git ls-files --others --exclude-standard`. **Not the scanner JSON** — it carries a `files` *count*, not a path list.

### Dispatch

Dispatch the agents **in parallel** (see `superpowers:dispatching-parallel-agents`). Give each only that input file, the baseline scanner JSON from Step 2, and the reference files. **No conversation history, no design rationale, no mention of who wrote the code.**

**The prompts are in `$WINNOW/references/agent-prompts.md`.** Read it before dispatching and copy each prompt from there. It also holds the two blocks every Step 3 prompt carries verbatim — the staleness precondition and, when a feature was named, the scope rule. **Expand `$WINNOW` to its real value in every prompt**: a subagent's cwd is the repo, it has no `$WINNOW`, and an agent that cannot open the reference files still returns findings — they are just findings from no standard at all.

**Subagents may run on a cheaper model than yours; you may not.** If the runtime lets you pick a model per agent, the volume passes are the ones to tier down — A and B read a written standard and apply it to many lines, which is what a mid-tier model is good at. **Keep S and E at your own tier**, and stay there yourself. `$WINNOW/references/portability.md` has the table and the reasoning; the short version is that S decides what is *eligible* to be reviewed and E's veto is the only thing standing between a confident deletion and a silent runtime break, so both are the passes where a weaker reader fails invisibly. If the runtime offers no choice, this paragraph costs nothing — ignore it.

**Division of labour, so their outputs merge cleanly — one agent, one question.** **Agent S** ran already: it drew the feature boundary in Step 1 and is finished before any of these start.

| | Owns | The question it answers | Runs |
|---|---|---|---|
| **A** | Code. Not comments, not documentation files | Does this line earn its place? | Always |
| **B** | Every comment and docstring | Does this comment earn its space? | Always |
| **C** | Documentation files, file headers, doc-versus-code truth, and the typography of prose the diff wrote | Is this still true, and does it match the repo? | Conditional |
| **D** | Runtime cost of code the diff added | Does this do more work than it needs to, at a frequency that matters? | Conditional |
| **E** | Silent failure and fragility, including protections the diff removed | How does this break, and why does the suite stay green? | Whenever A does |

If A notices a comment, it belongs to B. If B notices that a docstring is factually wrong, that is C's. If D notices dead code, that is A's. If A notices that a deletion it is proposing would break something invisible to the compiler, that is E's, and E outranks it. The overlaps are real and Step 3.5 resolves them; do not have the agents negotiate.

**A, B and E are the ones that always run**, so a diff with no docs and no hot path still gets code, comments and silent-failure coverage. C and D are conditional because their trigger is a property of the diff — the trigger conditions are at the head of each prompt in `agent-prompts.md`. There is no equivalent exemption for E: a one-line change is enough to add a swallowed exception.

**Two searches, two different rules.** Reading a neighbouring file to learn the repo's conventions is capped at three files, is read-only, and produces no findings. Grepping the repo to check whether a helper already exists, whether a caller relies on a guard, whether a scene references a field, or which doc describes a changed function is verification, is uncapped, and produces no findings of its own.

Serial fallback if the runtime has no subagents: run A, then B, then C, then D, then E yourself, and say once in the report that the judgment pass was self-review.

**On a serial run, E's veto is the thing most likely to be lost, and it is the one worth protecting.** Running the passes yourself means A's proposed deletions and E's objections to them are formed by the same reader, in one context, minutes apart — so the objection arrives after you have already talked yourself into the deletion. Do E's pass over A's proposed removals **as a separate reading**, against `fragility.md`, before writing either into the report.

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
| **X8** | A proposes deleting a line D wrote a note about | **The deletion wins.** Drop the note and count it. If A proposes a *rewrite* rather than a deletion, keep the note and mark it `re-check after applying` |
| **X9** | A proposes deleting a line E identifies as load-bearing | **E wins** — below |
| **X10** | A and E flag the same line for the same underlying reason | **One** merged finding at the higher severity, carrying E's `breaks:` and `no test:` fields. Two entries for one edit is the same defect as X3 |

X5, X6 and X7 do not arise when C was not dispatched. When it was not, B's one-line notes about comments or docstrings it suspected were false still reach the report — as P3 "unverified doc claim", never dropped. A suspicion nobody checked is worth less than a verified finding and more than silence.

X8 does not arise when D was not dispatched. X9 and X10 always can, since E runs whenever A does.

Findings outside the confirmed scope never enter this step. Scope appeals are not conflicts either: they go to the user with the report, not through these rules.

### X1 — grading the claim

The rule is `$WINNOW/references/comment-evidence.md`, and the short version is that authority is earned, never granted by the presence of a claim.

**A checkable why** — a ticket, a named consumer or mechanism, a concrete external constraint — **earns a lookup, not a pass.** Do the lookup:

- **Confirmed** — you found the thing the comment names. Dismiss A's finding; it moves to "Deliberately left alone" with the comment quoted as the reason.
- **Disproved** — you found positive evidence of the *opposite*: the named ticket exists and says something else, the named consumer exists and does not reference this. The finding stands, goes **up one severity** (P3→P2→P1; a P1 stays P1), and its message says the comment is false. A comment asserting something untrue is worse than no comment, because it stops every future reader from touching the line for a reason that does not exist.
- **No evidence either way** — the grep returned nothing. **This is not disproof, and must never be filed as Disproved.** Keep the finding at its original severity, mark it `unverified`, propose nothing.
- **Unperformable** — no network for the ticket, no tooling to read the asset. Same handling as no-evidence.

**The middle two are where this goes wrong, which is why there are four buckets and not three.** With only Confirmed / Contradicted / Impossible, an agent whose grep came back empty has no bucket for its actual situation, and the nearest label is "Contradicted" — which upgrades severity and writes "the comment is false" into the report. **Absence of evidence is the normal result for truthful comments**, because the consumers worth commenting about are the ones grep cannot see: Blueprints and scenes in binary assets, reflection, dependency injection, serializers, SQL views, wire protocols. Only positive disproof earns the upgrade.

An unverified claim is **not** silently preserved either: it becomes a question for the user, reported in its own "Author claims — confirm" section **at the severity A gave it**. It never enters the fix plan and it is never proposed for deletion.

Do not demote it to P3 for being unverifiable. That reads as caution and is the same immunity one rung down — eleven characters of `(see #4821)` would move a P1 to the bottom of a cosmetic list the report rules tell you to cut when it runs long.

**A bare claim** — "reserved for future implementation", "kept for later", "intentional" with no reason — does not protect the code, and earns no lookup, because there is nothing to look up. Merge the comment and the code into **one** finding at A's severity:

> `Combat.cs:41` — `enableAdvancedMode` is never read, and the comment above it asserts it is reserved without saying for what. → Add a ticket reference, or remove both lines.

This is the case the obvious rule gets wrong. `// Reserved for future implementation` is not a defense against speculative structure — it *is* speculative structure, with a second line of it stacked on top. A rule that let a comment immunise the code beneath it would let generated code immunise itself with a generated comment, and the skill would stop working on precisely the case it exists for.

Never propose deleting the code and keeping the comment, or the reverse. Those two lines are one decision.

### X4 — the floor

**A comment can justify a test's existence. It can never justify its false coverage.** `// intentional duplicate, pins #412` dismisses `duplicate-test`. Nothing in a comment dismisses an "asserts nothing" or "mock-only" finding — a note saying the test is intentional does not make an unfailable test able to fail. Keep it, quote the comment, and say what assertion would fix it.

**Match on the defect, not the severity label.** Those findings arrive as P1 *or* P2 depending on language and shape — a Jest test whose only assertion is `toHaveBeenCalled()` is P2, not P1. A floor written as "nothing dismisses a P1" would let the commonest form of the defect through on a technicality. `$WINNOW/references/tests.md` has both tables, and the carve-out that matters in the other direction: a test with no assertion that fails by crashing — an import smoke test, a does-not-crash regression — is not false coverage and is dismissible with one line naming it.

### X9 — E vetoes the deletion

**When E names a mechanism that makes a line load-bearing, A's finding is dismissed.** It moves to "Deliberately left alone" with E's reason quoted, and it does not reach the fix plan. The mechanisms are the ones in the Step 6 deletion-safety list and in `$WINNOW/references/fragility.md`: a GC root or callback reference, a directive comment, a type carrier, a trust-boundary check, a registration anchor, a side-effect import, a serialized field an asset reads.

**This is the payoff of running E at all.** Step 6's deletion-safety pass asks these same questions *after* the edits land, and its remedy is to restore the file from the backup. X9 asks them before the fix plan is written, so the bad deletion is never approved — the user never sees it offered, never says yes to it, and nothing has to be reverted.

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

**Every shape this step writes is in `$WINNOW/references/report-format.md`** — the condensed report, the header-gate question, the fix plan, the performance notes document, `declined.json` and `perf-declined.md`. Read it before writing. What follows is what goes *in* them.

### Naming and dating the report

Write `$ROUND/report.md`. `$ROUND/scan.json` already exists from Step 2.

**The filename no longer says what was reviewed, so the file has to.** Every markdown file a round writes — `report.md`, `fixplan.md`, `notes.md` and every `agent-*.md` — opens with the identity block:

```
Round:     02  —  .code-winnow/round-02/
Compared:  feat-golden-eval @ worktree   vs   main @ 69a5604   (branch scope)
Generated: 2026-08-03 19:09
```

Copy those values out of `$ROUND/meta.json`; do not retype them from memory. This is the block that makes a report readable when its path has been pasted into chat without its context — the job the stem used to do badly.

**Every JSON the run writes gets its own filename.** `<stem>.json` is the pre-fix baseline, written once in Step 2 and never again — Step 6 reads it. `--since X.json --json > X.json` truncates the baseline before Python opens it, so `--since` reads an empty file and the baseline is gone. New name out, baseline in:

```bash
# illustration only — the shape Step 6 uses
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM-postfix" --json \
  --since "$ROUND/scan.json" > "$ROUND/scan-postfix.json"
```

### Reconciling with the previous run

**`scan.py` already chose it.** `$ROUND/meta.json` carries `prior_round` — the newest round whose `scope` matches this one's, or `null`. Read the field; do not search the directory:

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
PRIOR=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["prior_round"] or "")' \
        "$ROUND/meta.json")

# `if`, not `[ -n "$PRIOR" ] && …`. As the last command of the block that
# short-circuits to exit 1 on the no-prior path — which is the FIRST RUN of
# every repo, and which this document calls normal three paragraphs down. A
# step that exits non-zero on its own documented happy path teaches whoever
# runs it to ignore the exit code.
if [ -n "$PRIOR" ]; then
  "$PY" "$WINNOW/scripts/scan.py" $SCOPE \
    --stem "$STEM-vs-$PRIOR" --json --since ".code-winnow/$PRIOR/scan.json" \
    > "$ROUND/scan-vs-$PRIOR.json"
  echo "reconciled against $PRIOR"
else
  echo "no prior round of this scope — the report says 'Previous run: none'"
fi
```

This used to be `ls -1t .code-winnow/round-*/*.json | grep -v -- '-postfix\|-p3\|-r2'` plus a line of prose telling you to eyeball the stem's scope segment. Both failed the same way: the exclusion list was a blocklist of ad-hoc suffixes that grew every time an agent invented one, and the scope check was advisory. **A branch baseline reconciled against a worktree re-scan reports every untouched finding as `resolved`**, which reads as "your fixes worked" for findings nobody touched.

Rounds written before `meta.json` existed carry no scope and are never chosen, so the first run after this change says "Previous run: none". A wrong baseline is worse than no baseline.

Never write back over `$ROUND/scan.json`, which Step 6 still needs as the pre-fix baseline. The scanner marks each live finding `new` or `persisting`, and returns the ones present last time and absent now in `resolved`. Matching is by file, rule, message, and the normalised source line.

Findings present before and absent now are **no longer true** — fixed, refactored away, or overtaken by events. Report them under their own heading and never re-list them as live. A punch list that keeps resurfacing settled items stops being read, and that failure is quiet: the user does not tell you they have started skimming.

**A finding whose file this run never opened is `out_of_scope`, not `resolved`.** The scanner records every path it actually read, so a prior finding in a file that left the scope lands in its own array and its own report section, saying the true thing: not examined. Never fold it into the resolved list.

**"Absent" means gone, not merely unprinted**, and the scanner enforces the distinction so a mismatched baseline cannot manufacture resolutions. A finding this report filters out but that is still true is counted during reconciliation and then dropped from the output: it appears as neither live nor resolved. Declined findings are handled the same way and for the same reason.

### Findings the user declined

Declining is not the same as resolving: the finding is still true, so the scanner keeps producing it, and without somewhere to record the answer it returns as `persisting` on every run — the same skimming failure by a different route.

Keep one file, `.code-winnow/declined.json`, in scanner-report shape (see `report-format.md`). When the user rejects a finding, append the finding object exactly as the scanner emitted it — `path`, `rule`, `message` and `anchor` are the key, all four verbatim. Pass it on every later run with `--declined .code-winnow/declined.json`. Matches move to the `declined` array and out of `findings`. The file is a normal file — the user can delete a line from it to re-open a question. `line` is ignored in matching, so declined items survive line shifts.

### Severity

- **P1** — swallowed exceptions with a broad or bare `except`, validation removed from a trust boundary, tests that assert nothing or assert only on mocks, invisible Unicode in real source (zero-width, non-breaking, bidi — *not* a leading BOM; **inside a test file** the scanner demotes these to P2, and a non-breaking space or soft hyphen to P3 in a test *or* prose file — everything else in a prose file stays P1), unrooted `UObject*` members, mutable default arguments, committed developer-home paths, committed credentials in a recognised vendor format (**not** demoted in a test or prose file, and never fix-plan eligible — rotate, do not delete). **From E:** silent corruption or data loss, a persisted surface changed with no migration, any failure with no observable signal, **and a credential E read and judged real** — also never demoted and never fix-plan eligible
- **P2** — speculative abstraction, defensive checks in trusted paths, unused fields, duplicated helpers, dead scaffolding, config knobs nothing sets, structurally duplicate tests, unused fixtures, `except SpecificError: pass`, `/home/...` paths, UNC paths naming an internal host, a credential-named variable assigned a literal in a test or prose file — that last one is the *scanner* guessing from a name, which is why it demotes in a fixture, and it is not in tension with E's P1 above: E demotes nothing because E has read the value and judged it, where the scanner has only matched a shape. **From E:** fragility that surfaces loudly but that nothing tests, a newly-added suppression, a constant duplicated where it will desync
- **P3** — comments restating code, generic naming, formatting churn on untouched lines, em dashes and smart quotes *in code* (the scanner exempts **whole-line** comments, Python triple-quoted regions and prose files; it does **not** exempt a trailing comment on a code line, nor string literals, so leave typography alone in localized and user-facing strings yourself). **E should essentially never land here** — a cosmetic E finding failed its own gate and belongs to A

**"Validation removed from a trust boundary" was already a P1 before Agent E existed**, and nothing enforced it — no scanner rule detects it and no agent was asked to look. E is what makes that line true rather than aspirational.

### Findings that cannot be fixed here

E produces findings whose fix is a design decision — a save migration, a cache invalidation strategy, a locking scheme, a schema backfill. Step 5b binds every fix to preserving behaviour, so these are reported and left. **Every committed-credential finding is in this category too** — the scanner's `committed-secret` rows and E's read of a named credential alike — for a different reason: the repair is to rotate the credential, and deleting the line only hides it from the working tree while it stays in history.

**They stay at their own severity and stay in the P1 or P2 list.** Do not demote them for being unfixable, do not move them to a separate section, and do not move them into the performance notes. A P1 that this pass cannot repair is still a P1 the user needs to see today, and every mechanism for tidying it away ends with it below the fold. Mark the item `fix: out of scope — <why>`, count them in the header's `Not fixable here:` line, and leave them where the severity puts them.

The fix plan omits them, so "fix all" cannot sweep them up. That is the only place the distinction has any mechanical effect, and it is enough.

### What to cut and what never to cut

The "deliberately left alone" section matters more than it looks. Showing what you considered and rejected is what makes the rest credible — and it stops the next run re-flagging the same lines.

If a P3-only list runs past a screen, cut it. Twenty cosmetic nits train the user to skim, and then they skim past the P1.

**Never cut "Author claims — confirm", and never sort it by severity.** Those items keep the severity they had before the comment was considered, and each one is a question only the user can answer in two seconds. Folding them into P3 is what makes the nine-character attack work: append `(see #4821)` to a comment above `except Exception: pass`, the lookup is unperformable in most runtimes, and a demoted item lands under "Cosmetic" and gets trimmed for length. A silent-data-loss P1 disappears for twenty-two characters of generated comment.

### The performance notes document

**D is dispatched like every other pass and writes its raw output to `$ROUND/agent-D.md`.** You then produce `$ROUND/notes.md` from it, exactly as you produce `report.md` from A, B, C and E. The shape and its three guards are in `report-format.md`.

**`notes.md` is the only place D's findings are ever published**: not a section of the report, and **nothing in it enters the fix plan or is ever applied.** That is what "nowhere else" means — it constrains where the notes *go*, not whether D's raw output exists. Read the other way it made `agent-D.md` a file the skill forbids and the index template links, so the index carried a permanently dead link.

**Write the document even when D found nothing** — an empty Notes section and a line saying the pass ran. A missing file is indistinguishable from a pass that was skipped, and those are different facts. When D was not dispatched at all, write no document and say so in the report header instead.

D produces notes from judgment rather than from a scanner rule, so `--since` and `declined.json` cannot reach them. Keep `.code-winnow/perf-declined.md` and hand it to D on every later run; D skips matches and reports the count. **Matching is by path plus anchor, never by line number** — a note declined at line 22 is the same note when an unrelated edit moves it to line 40.

### Findings outside the named feature

Only when Step 1 resolved a feature. Same discipline as pre-existing flaws, for the same reason: it is a courtesy, and a courtesy that takes over the report stops being one.

This is what the scanner found outside the confirmed scope, plus anything A, B, C, D or E happened to notice at its edges. **Nobody swept for it.** Report it as a courtesy: top three by severity, a count for the rest, two sentences each, no proposed patches, no severity debate.

These never enter the fix plan and are not eligible for Step 5. Fixing one takes a second, explicit approval — and the honest way to get it is to offer a proper pass, not to slip them into a cleanup the user scoped to something else.

**Agent S's `unsure` files are not in this section**, and neither are scope appeals. Both were questions put to the user; filing either here reads as "reviewed and set aside", which is the one thing they are not.

**Say what the out-of-feature files did not get**, because a partial pass reads as a complete one. The agents judged what they happened to see there; nothing systematic ran. A mock-only test in a file nobody opened is absent from the report entirely, and the header's `3 of 12 files` otherwise reads like coverage of twelve.

One consequence worth knowing rather than fixing: these are never presented as decisions, so they can never be declined, so they persist in every later run. If one keeps returning and the user does not want it, the answer is to judge it properly in a scoped run.

### The header convention gate

**Any finding that touches a copyright, license, or SPDX line goes through this gate** — whichever branch of Agent C produced it, and whether it was framed as a convention conflict or as a stale-doc correction. Do not fold it into "fix all". A license line is never an ordinary doc finding.

If Agent C found a header conflict, **ask before proposing any header edit**, using the question shape in `report-format.md`. **Quote the header you are proposing, in full.** The user is being asked to assert a company name and a year onto files; they cannot answer that from the word "the repo's header". A 2019 notice on a file created this year is wrong in a way only they can see.

**Cap it at ten files.** Past that, do not offer the fix option at all — say *"N of the files this change adds carry no header; want a header pass as its own change?"* and stop. Diff membership limits *which* files; only a count limits *how many*.

Two reasons this is a gate and not a finding like any other. Header edits are bulk and mechanical, so "fix all" would sweep them in unread — and bulk mechanical edits are the thing this skill calls the most reviewer-hostile content in a generated diff. And a header carries a license claim: adding a copyright line to a file is an assertion about ownership, which is not a call this skill gets to make.

Severities are in Agent C's brief: missing is P3, wrong is P2, CI-enforced is P1. The gate applies to all three — severity decides how loudly it is reported, never whether it needs asking.

**Only files the diff added or modified are ever eligible.** If the repo's own headers are inconsistent, that is a pre-existing condition — one sentence in the report, and no further. Unattended: report only, never unify.

### Pre-existing flaws

One section, one meaning: **problems in the files this change touches, on lines this change did not touch.** Not the rest of the repo. This is a byproduct of reading around the diff, never a reason to go looking — and nothing seen during a Step 3 verification lookup belongs here either.

**"Touched" includes lines the change took away, and that is not a technicality.** A finding about a *block* — a test function, not the `def` naming it — belongs to this change when anything inside that block was added **or deleted**. Judging by the anchor line alone is blind in the one direction this skill exists to look: delete a generated test's only assertion and every surviving line is untouched, so the now-assertionless test files as pre-existing and drops out of the default run. The change created a P1 and the scan reports nothing.

Two sources feed it, and both are optional:

- What the Step 3 agents noticed while reading around the diff. This is the usual source and needs no extra command.
- `"$PY" "$WINNOW/scripts/scan.py" $SCOPE --whole-files --stem "$STEM-preexisting" --json > "$ROUND/scan-preexisting.json"` — the same scan widened to the untouched lines of those same files. **This is the only thing that populates the scanner's `preexisting` findings**, so run it if you want the deterministic half; skip it on a large diff, where it mostly adds P3 noise. Either way, say which you did.

Log every one in full to the report file. In the user-facing output, give each **at most two sentences: one for what it is, one for what it does.** Then stop. Expand only on request.

> `AudioManager.cs:88` — Coroutine started in `OnEnable` is never stopped in `OnDisable`. Toggling the object leaks a coroutine per cycle, so audio triggers stack up over a session.

Not three sentences, not a proposed patch, not a severity debate. If there are more than five, list the top three by severity and give a count for the rest.

If the pre-existing list is longer than the in-scope list, say so in one line — "this file has more going on than your change does, want a proper pass over it?" — and let the user decide. Deciding for them turns a five-minute review into an afternoon.

### Regenerate the index — the last action of Step 4

`.code-winnow/README.md` is the one file a reader opens. Rewrite it **in full** from the template; never edit the live file, so there is no half-updated state and no marker to preserve.

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
sed "s|{{ROUND}}|$(basename "$ROUND")|g" "$WINNOW/scaffold/root/README.md" \
  > .code-winnow/README.md
```

**The placeholder is `{{ROUND}}` and not `ROUND` because the substitution is global and `ROUND` is a real word.** The template's own prose documents `$ROUND` as an `env.sh` variable, and an unanchored `s|ROUND|round-06|g` rewrote it to `$round-06` — in the index of a real run. A placeholder has to be a token that cannot occur in the prose around it.

That handles every path in one substitution. Fill the rest by hand, from what you already hold:

- The `Current round:` line, out of `$ROUND/meta.json` — branch, side, base, sha, scope, timestamp.
- The **This round** column, from the counts the conflict check just produced — `14 live, 3 P1`, `9 items, APPROVED`, `4 notes`. Leave a cell blank rather than guessing.
- **Previous rounds**, one link per `round-NN/` directory, oldest first.

**Replace every placeholder, including by nothing.** A blank cell says the count is not known; a leftover placeholder says you stopped halfway. They are different facts and the tests fail on the second.

**A pass that did not run keeps its row and loses its link** — the bare filename as plain text, and `not dispatched` in the last column. Deleting the row would make a skipped pass indistinguishable from a pass this skill does not have, and a link to a file nobody wrote is a dead link in the first place a reader looks.

**Links resolve against `.code-winnow/`, not the repo root.** `round-02/report.md`, never `.code-winnow/round-02/report.md` — the second renders perfectly and 404s on click.

## Step 4b — Record the approved set, and choose how to apply it

**Wait for explicit go-ahead.** This is the gate. If nobody is there to give one, write the fix plan and **stop there**. See the unattended table; an unattended run never edits.

**An unattended plan is marked, and the mark is load-bearing.** Its header line reads `Status: UNAPPROVED — no human reviewed these findings`, and every section heading says *proposed*, not *approved*. Without that, an unattended run writes a file listing every finding under "approved", and the resume path — which exists to execute a settled list without re-opening it — turns a scheduled scan into a one-paste auto-apply of deletions nobody read. That routes straight around the gate this document builds two sections earlier, using the mechanism it built one section later. "Entering at Step 5 cold" refuses any plan carrying that line, and `scripts/backup.py` refuses it again.

### The fix plan

Once the user has approved a subset, write `$ROUND/fixplan.md` — **the shape is in `$WINNOW/references/report-format.md`**. It holds what the fix pass needs and nothing else, and it is the handoff contract for all three rungs below.

**`file:` is authoritative, not the prose.** Every item carries at least one `file:` line, and `line:` / `occurrence:` / `of:` / `anchor:` are the fields it pairs with; a merged X6 finding lists each group in order. The headline is for the reader. Prose is not a data format: `scripts/backup.py` parses `file:` lines and nothing else.

**`line:` is what the locating rule below actually uses**, so an item without it cannot be applied.

**`occurrence:` and `of:` count matching lines of the file, and both come from the scanner as `anchor_index` and `anchor_total`.** Copy `line` and those two straight out of the JSON. Together they distinguish the third `catch (Exception) { }` in a file from the first. **The JSON's `occurrence` field is not one of them** — it indexes findings that share a rule and message, a different population; copying it hands the executor an ordinal measured on the wrong thing and rule 2 below then edits untouched, unreviewed, unapproved code.

Anchors are written **unquoted and unfenced**. Backticks inside a value break the moment an anchor contains a backtick, which doc fixes routinely do.

The user edits the plan directly — delete an item to drop it. Write it whether or not a clear happens: it is also the on-disk record of what was approved, and Step 6 reconciles against it.

### `evidence:` — the deletion-safety field

**Every item carries one, and on anything that removes code it is the load-bearing field.** Three permitted values:

- **The commands you ran and what they returned** — literally, so Step 6 can run them again. `git grep -c cachedRig -- '*.cs'` → `2`. Not a summary of a lookup: the lookup, re-executable. "Traced it" is not evidence; neither, quite, is "grepped repo-wide, 3 hits, all in this file", because a fabricated count is textually identical to a real one and the plan is written by the same agent that proposed the deletion. A command someone else can re-run is the only form of this that survives an agent having a bad day.
- **`rewrite, nothing removed`** — for a tightened comment, a corrected doc line, an inserted header. Nothing is being taken away, so there is nothing to prove safe.
- **`unverified — <the lookup you could not perform>`** — and then the item must not propose a deletion.

**An `unverified` deletion is a rule violation upstream, and the executor refuses it.** `comment-evidence.md` already says an unverifiable claim becomes a confirm-question — at its own severity — and never a proposed deletion, so such an item should not have reached the plan. If one does, skip it, and report it as *"approved but unverified — not applied"* rather than applying it or silently dropping it. Rewrites with `unverified` are fine; only removal needs proof.

This is the whole correctness gate, and it is deliberately not a fourth reviewing agent. Another opinion does not make a lookup happen. A required field does.

### `tests-delta:` — on any item that changes what the suite collects

This skill removes tests on purpose: merging structural duplicates, dropping a fixture nothing requests. Those are approved changes, and they move the pass count legitimately. **So an item that changes collection declares exactly how, by name** — both sides, not a net number, so a merge that quietly drops a case shows up as `-3 +2`. The field's shape is in `report-format.md`.

Without it, Step 6 has no way to distinguish an approved removal from an accidental one, and the honest reading of a smaller suite would be "restore everything" — which would block legitimate work every time the skill did one of the things it exists to do.

### Locating a fix at execution time

Files change between approval and execution, so the executor locates by **anchor text, not line number**.

**Normalise before comparing.** The anchor came from the scanner's `normalise_anchor`, which collapses every run of whitespace to one space, strips the ends, and truncates to 120 characters. So the plan's `private Rig cachedRig;` never equals the file's `        private Rig cachedRig;`. Apply the same normalisation to each candidate line before comparing, and treat a 120-character anchor as a prefix match. **`of:` was counted under that same normalisation**, so comparing raw lines reaches a different total and every moved item reports stale.

**Never search for a moved anchor.** Match only where the plan says, normalised:

1. Normalised anchor matches at `line:` → edit there.
2. It does not, but the file still contains **exactly `of:` matches** for the anchor → edit the `occurrence:`-th of them, counting **top to bottom**, and say the line moved.
3. Anything else — including a match count that is not `of:` — → **report the item stale and skip it.** Never search for "the one remaining match".

**`of:` is the denominator, and the ordinal is unsafe without it.** An ordinal alone is satisfied by any file with at least that many matches, so a re-run finds the *declined* twin of an already-applied fix and edits the one line the user refused. Report stale — that costs a re-run, against a wrong-line edit that costs a deletion nobody approved.

**Counting is top to bottom, over matching lines, and the scanner agrees.** Do not count findings, do not count occurrences of a *symbol* — count lines whose normalised text matches the anchor.

A fix applied to the wrong line is the worst outcome available in this whole skill, and it is silent. Skipping a genuinely-moved fix costs the user one re-run; the alternative costs them a deletion they declined.

**If several items report stale at once, stop and check `SNAPSHOT` before applying any of them.** One stale anchor is a moved line; all of them stale means the tree changed since the review, and the right response is to re-run it rather than to apply the survivors.

### Then choose a rung

By Step 5 you are carrying the diff, the scanner JSON, every agent's output, the conflict check, the report, the performance notes, and the approval conversation. The fix loop — edit, test, reconcile, sometimes debug — is the part of the run that most needs headroom and least needs that history.

**Rung 1 — clear and resume. Offer this first.**

```
Fix plan written to .code-winnow/round-NN/fixplan.md.

To apply it with a clean context: /clear, then paste

    code-winnow: apply .code-winnow/round-NN/fixplan.md
```

Say plainly what it buys, and do not oversell it: a long edit-and-test loop then runs against a small stable prefix instead of the whole review. Clearing does not carry the previous cache forward; the win is headroom and a clean prefix for the turns that follow.

**Rung 2 — fix subagents.** If the user would rather not clear, or the runtime has no equivalent, dispatch the work to a subagent with no conversation history. You stay supervisor: you merged the findings, you verify, you reconcile, **you do not edit.**

**Its prompt must carry four things, because it has never read this file** and every rule below lives only here:

1. The fix plan, and `andrej-karpathy-skills:karpathy-guidelines`.
2. **The anchor-location rules** above, in full — normalise, match at `line:`, else *only if the file holds exactly `of:` matches* take the `occurrence:`-th counting top to bottom, else report stale. Never "the one remaining match", and never the ordinal without the total check. Without this the agent locates by line number or searches, and the search is what edits code the user struck from the plan.
3. **The `evidence: unverified` rule** — skip those items, report them, do not perform the missing lookup and proceed.
4. **"Step 5a is already done; do not run it."** Otherwise it re-runs the backup and copies half-edited files over the restore point.

**On this rung you run Step 5a yourself, once, before dispatching anything — both halves, the backup and the `Tests-before` baseline — and you tell each fix agent that both are already done and that it must not run 5a.** The backup script copies *every* path in the plan, not just one agent's section, so two agents each running it would snapshot the other's half mid-edit. That is deterministic, not a race, and the non-empty-directory refusal built into `backup.py` is what catches it if this instruction is ever missed.

Code fixes and doc fixes can go to two agents in parallel — different files, no shared state. **Check the `file:` sets are actually disjoint first**; if any path appears in both sections, run them in sequence. Header fixes always go last and alone: they touch line 1 of files the other agents are editing.

**Rung 3 — in place.** No subagents and no clear available. Apply the plan yourself, and say so once in the report.

## Step 5 — Apply

**Step 5a happens exactly once per fix plan, before any edit** — the backup *and* the pre-fix test baseline, since both capture a state the first edit destroys. Who runs it depends on the rung: on rungs 1 and 3 it is the executor's first action; on rung 2 the *supervisor* runs it before dispatching, because the fix agents have never read this file. Never twice — the script refuses a non-empty backup directory precisely because a second run overwrites the originals with fixed files.

### Step 5a — Make the edits reversible, before the first one

**This is not optional and it comes before any edit, including the first one you are sure about.**

The advertised default scope is uncommitted work *including untracked files*. "Fix all" then deletes lines from files that have never been in the object store — no blob, no reflog, no `git checkout --`, no `git stash pop`. The headline trigger for this whole skill is "clean this up before I commit", so the common case is precisely the one git cannot undo.

**The list comes from the fix plan's `file:` lines, not from the scanner JSON.** Agent C's entire purpose is producing findings on files the diff never touched, so an untouched doc has no entry in that JSON at all — and would be edited with no copy made.

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
"$PY" "$WINNOW/scripts/backup.py" "$BACKUP" "$ROUND/fixplan.md"
```

**Any `REFUSING:` line means stop and tell the user.** Do not edit, and do not "fix" the plan by dropping the item that would not parse. The script refuses on six things, each of which fails silently without the guard: a missing or non-`APPROVED` `Status:` line, fix items appearing after `## Never touch`, a non-empty backup directory, a destination pasted from the plan header rather than computed, any `file:` path missing from disk, and an item with no `file:` line at all. Its module docstring has what each one prevents.

Nor should you reason that a tracked file is safe because git can restore it. That is the same reasoning this step already rejects for untracked files, and it fails the same way: after three more edits there is no clean point to return to.

Then tell the user, in one line, where the copies are and how to undo:

> Backed up 7 files to `.code-winnow/round-02/pre-fix/`. To undo everything, from the repo root: `cp -a .code-winnow/round-02/pre-fix/. .` (PowerShell: `Copy-Item -Recurse -Force '.code-winnow\round-02\pre-fix\*' .`)

If the copy fails — read-only filesystem, no shell — **say so and stop.** Do not edit anyway. A cleanup that cannot be undone is not a cleanup the user agreed to, and "I could not make a backup" is a decision for them, not for you.

`git stash` is not a substitute: `--include-untracked` moves the user's work out of the tree, which is disruptive mid-review, and it still cannot be un-popped cleanly after further edits.

### Step 5a, second half — record what the tests looked like before

**Run the suite now, before the first edit, and save both the result and the list of test names.** Same command Step 6 will use, whole suite, no filters:

```bash
# illustration only — substitute the project's real commands
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
<the project's test command> 2>&1 | tee "$ROUND/tests-before.txt"
<the runner's list command>   > "$ROUND/tests-before.list"
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

**Without this, Step 6 cannot tell your deletion from a pre-existing failure**, and both misreadings are damaging in opposite directions. Assume the suite was green and you will chase a failure you did not cause, eventually "fixing" unrelated code to make it pass. Assume the failure was already there and you wave through the one your cleanup caused, because a red suite is easy to explain away.

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
- **Re-run each `evidence:` command now, before touching anything, and require the same output.** This is the one moment equality is the right test: the tree is still exactly what the plan was written against, so the recorded counts must reproduce. A count that has **grown** means something started referencing the target between approval and execution — skip that item and say so. A count that has **shrunk** means the plan was written against a tree that no longer exists; treat it as stale. Items whose evidence is `rewrite, nothing removed` have no command and skip this check.
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
<the runner's list command> > "$ROUND/tests-after.list"
diff "$ROUND/tests-before.list" "$ROUND/tests-after.list"
```

- Missing tests that a `tests-delta:` line declared → **expected.** Report them as "3 tests merged into 1 parametrized case, coverage preserved".
- Missing tests that **no** `tests-delta:` line declared → **a regression, even with everything green.** A deleted test, a broken collection, a file that no longer imports — all three surface as a smaller suite and as success in every summary line. Restore from the backup.
- Tests present before *and* after but with a changed identifier → an approved rename, or a merge that quietly dropped a case. The name diff is the only thing that catches this.

**Report the arithmetic, not a verdict:** `412 collected before, 410 after; plan declared −3 +1; reconciled, no unexplained loss.` A reader can check that. "Tests pass" cannot be checked at all.

This is the skill's own rule turned on itself. `$WINNOW/references/tests.md` calls removing a test "a coverage regression wearing a cleanup costume" — and a green run with 400 tests where there were 412 is exactly that.

Then re-run the scanner with `--since` against the pre-fix JSON — **writing to a new filename**, per the Step 4 warning:

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
DECLINED=""
[ -f .code-winnow/declined.json ] && DECLINED="--declined .code-winnow/declined.json"
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM-postfix" --json \
  --since "$ROUND/scan.json" $DECLINED \
  > "$ROUND/scan-postfix.json"
```

`$SCOPE` matters most here. Omit it and this scan resolves a different scope from the baseline it is comparing against — a `--scope branch` review reconciled against a worktree re-scan reports every untouched finding as `resolved`, which reads as "your fixes worked" for findings nobody touched.

Read the **`resolved`** array, not the raw count. Your deletions moved every line below them, so comparing line numbers between the two runs is meaningless; the reconciliation is what tells you a finding actually cleared. Anything still listed as `persisting` did not.

Then reconcile against the fix plan, which is the record of what was approved. Report three numbers plainly: **approved, applied, skipped** — with a reason for every skip, "anchor no longer present" included. An item that was approved and quietly not applied is the failure mode here, and it looks exactly like success.

Once verification passes, the backup from Step 5a has done its job. Say where it is and leave it — deleting it is the user's call, and `.code-winnow/` is already excluded from git.

### The deletion-safety pass — first in execution order, written last

**Run this on every run, before the test comparison above.** A cold reviewer reads the diff as it now stands and does not know which lines you removed — this pass is the only thing in the run that checks the removals themselves, and it is five questions.

**Agent E asked these same five questions in Step 3, and that does not make this pass redundant.** E asked them about lines A *proposed* removing, and its veto (X9) stopped the worst ones from reaching the plan. This asks them about lines that were *actually* removed — a different set, because the user edits the plan, items go stale and get skipped, and a cold Step 5 session executes without E's output in front of it. E prevents; this verifies. Run it even on a run where E vetoed nothing.

**Re-run every `evidence:` command behind an applied deletion and read the delta. Equality is the wrong test here.** These commands are *pre*-conditions: `git grep -c cachedRig -- '*.cs'` returned 3 at plan time **because the field was still there**, and after the approved deletion it returns nothing. Requiring the output to "still match" fails every correct deletion.

Three readings, per item:

| Output now | What it means |
|---|---|
| Dropped, and nothing remains outside the files the plan names | **Expected.** The references were where the evidence said they were |
| Unchanged | **The edit did not land.** Reconcile the item as not-applied; do not record it as verified |
| Dropped, but hits remain in a file the plan does **not** name | **Those are live references to what you just removed.** The plan-time lookup was wrong, or the tree moved under it. Restore that file |

Hits remaining *inside* a file the plan names are ambiguous — a usage the fix should also have removed, or an unrelated substring — and the `Verify:` command settles it, because a dangling reference does not survive a build. Say which reading each item got.

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

You were invoked with a fix plan rather than a review request — `code-winnow: apply .code-winnow/round-NN/fixplan.md`, or any phrasing that names one. The review already happened, in a session whose context is gone. Your job is to execute a list, not to form an opinion.

**First, check the `Status:` line — it must be present and must read `APPROVED`.** Anything else, including *no `Status:` line at all*, means stop: report that nobody has reviewed these findings and ask for approval before anything else. Absence is not permission. `scripts/backup.py` enforces this with a `REFUSING:` line so the gate does not depend on you remembering to read it here, but knowing why it refused saves a confused retry.

1. Read the fix plan. It is self-contained: `Status`, `Skill` (your `$WINNOW`), `Scope`, `Feature`, `Baseline` (the pre-fix JSON for Step 6), `Backup`, `Undo`, `Verify`, then the fixes and the never-touch list. Each fix carries `file:`, `line:`, `occurrence:`, `of:`, `anchor:`, `fix:` and `evidence:` — **the first five are what locate the edit**, and the rules for using them are in Step 4b under "Locating a fix at execution time". Read that section; it is the one part of the review you do inherit. **`$ROUND` is the directory the plan sits in, and everything else derives from it** — the baseline is `$ROUND/scan.json`, the backup is `$ROUND/pre-fix`, and `$STEM` is `$ROUND/meta.json`'s `stem` field.
2. Re-run the Step 0 block. It is idempotent and it verifies with `git check-ignore` — cheap insurance against a repo where the exclusion was lost or was never valid, which in a linked worktree it silently was not. This is the one part of Steps 0–4b you *do* run.

   Then look at `.code-winnow/env.sh` before running anything that sources it. **It is from the session that wrote the plan, and it may name a different `$ROUND`** — a later review in the same repo overwrites it, and a plan copied to another machine has none at all. Every block below opens with `. .code-winnow/env.sh`, so a stale file silently redirects the backup and the reconciliation into another round's directory. If its `ROUND` does not match the directory the plan sits in, or the file is missing, set `WINNOW`, `PY`, `STEM`, `ROUND` and `BACKUP` yourself at the top of each call.

   **Derive them from the plan's location, not by copying its header values.** `$ROUND` is the plan's own directory; `BACKUP` is `$ROUND/pre-fix`; the baseline is `$ROUND/scan.json`; and `STEM` is `$ROUND/meta.json`'s `stem` field. The header's `Skill:` line is the one field to read directly, because nothing else carries `$WINNOW`.

   The plan header is prose written for a human, and a value copied out of it arrives with whatever else is on that line — `Backup:` once carried a trailing `(NOT YET MADE)` marker, and the backup silently went to a directory of that name. `backup.py` now refuses a destination with a parenthetical in it, but the durable fix is to compute the path rather than parse it.
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
