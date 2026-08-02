---
name: code-winnow
description: Use when the user wants generated-code chaff removed from an uncommitted change or a branch — "winnow", "code-winnow", "de-slop", "deslop", "clean this up before I commit", "does this look AI-written", "make this idiomatic", "cut the slop" — or is about to open a PR on agent-written code, or a large generated change has just landed. Also covers redundant generated tests (assertion-free, tautological, mock-only, near-duplicate) in pytest/unittest, NUnit/xUnit/MSTest, JUnit, GoogleTest, Go, Jest/Vitest/Mocha, Rust, RSpec and XCTest. Not for a general code review, a bug hunt, or a security audit — this removes chaff and does not look for defects. Tuned for C#/Unity, C++/UE5 and Python, language-agnostic elsewhere. Needs Python 3 and git; writes reports under `.code-winnow/`, appends that path to the repo's local git exclude file, and copies every file it is about to edit into a restore point first.
---

# Code-winnow

Generated code fails review in predictable ways. It is rarely wrong; it is bloated, over-defensive, and stylistically foreign to the repo it landed in. Linters catch the subset that is a rule violation. The rest is judgment, and that is the gap this skill fills — winnowing, in the old sense: keep the grain, blow off the chaff.

**Scope discipline is the whole game.** Operate only on lines the current change added or modified. A cleanup pass that wanders into untouched files produces a diff nobody can review, which is a worse outcome than the chaff you removed.

**This is a diff review, not a repository audit.** Unless the user asks in so many words for a whole-repo pass, the job is the current change and nothing else. Pre-existing problems reach the report only as byproducts — you had the file open to review the diff, you noticed something, you mention it. Do not go looking, do not sweep for vulnerabilities, and do not let incidental findings grow past a short aside. Someone who asked you to winnow a branch and got a repo-wide defect list back did not get what they asked for, and the thing they did ask for is now buried.

**The rule is about what becomes a finding, not about what you may read.** Only lines the diff touched can produce one. Reading elsewhere is permitted for exactly two purposes, both defined in Step 3: learning the repo's conventions (capped at three files) and verifying that a deletion is safe (uncapped — grepping for an existing helper, tracing callers, checking scenes for a serialized field). Neither produces findings, however bad the code you pass through looks.

**Run Step 0 first, before anything else** — including the capability check below, which writes `.code-winnow/substitutions.md`. Writing that file before the exclusion lands is the exact self-dirtying Step 0 exists to prevent.

**Then, before Step 1:** read `references/portability.md`, check which companion skills are available here, look through the installed skills for anything that fills a missing role under a different name, and — if anything is still missing — say so once, proposing the equivalents you found and letting the user choose between those, installing, running degraded, or naming their own substitute. Do not silently take the weakest path. If everything is present, say nothing.

### When nobody is there to answer

A scheduled run, a headless runtime, piped stdin, CI, or a user who has already said they are stepping away. **Three decisions come up in a run and all three have an unattended answer. Take them without asking:**

| Decision | Unattended answer |
|---|---|
| Missing companion skills (Step 0/1) | Run degraded. Put the notice at the top of the report, not in chat. |
| Diff too large to judge in one pass (Step 1) | Split it yourself, by top-level directory, largest first. Report every part; name the split you chose and any part you did not reach. |
| Apply the fixes (Step 5) | **No. Never.** Stop after Step 4, write the report, and say the run ended at the report because nobody was there to approve. |

That last row is not a default that a reading of "do not block" can override. An unattended run **never edits a file**, and the reason is Step 5a: the default scope includes untracked files, which git cannot restore. A run that stalls waiting on a question has failed; a run that silently deleted lines from files with no object-store copy has failed worse and quietly.

## Companion skills

| Skill | Used at | Purpose |
|---|---|---|
| `andrej-karpathy-skills:karpathy-guidelines` | Step 5, loaded before any edit | Governs how fixes are made. Prevents the cleanup itself from adding chaff. |
| `superpowers:dispatching-parallel-agents` | Step 3 | Fans out the judgment and comment passes. |
| `superpowers:requesting-code-review` | Step 6 | Cold pass over the applied fixes. |
| `superpowers:verification-before-completion` | Step 6 | No success claim without a run command and its output. |
| `superpowers:systematic-debugging` | Step 6, on failure | Root-cause a broken test rather than patching over it. |
| A simplification skill | Step 6, optional | Restructures genuinely complex paths. Chaff removal is deletion; simplification is restructuring. Different jobs, in that order. |

Any of these may be absent — including on Claude Code, where the set installed varies by user. `references/portability.md` has the detection, the degraded path, and the install route for each, plus the notice format for telling the user before the review starts. Substitutes the user has already chosen are recorded in `.code-winnow/substitutions.md`; read it before asking anything — **after Step 0**, since writing it is what makes Step 0 have to come first.

## Step 0 — Make the workspace invisible to git

Before writing anything — including `.code-winnow/substitutions.md` — ensure `.code-winnow/` is excluded. **Prefer the local exclude file:**

```bash
GITDIR=$(git rev-parse --git-dir)          # NOT ".git" — see below
mkdir -p "$GITDIR/info"
grep -qxF '.code-winnow/' "$GITDIR/info/exclude" 2>/dev/null \
  || echo '.code-winnow/' >> "$GITDIR/info/exclude"
```

Say in one line that you did it, and move on.

`git rev-parse --git-dir` rather than a literal `.git`, and `mkdir -p` rather than assuming the directory: **in a linked worktree or a submodule, `.git` is a file, not a directory**, and the real git-dir it points at ships without an `info/` subdirectory. Hardcoding `.git/info/exclude` fails in both, and those are exactly the setups where a reviewer is working on a branch in parallel.

Use `.gitignore` only if the user wants the exclusion shared with their team, and only after telling them it will appear in the diff. That is the reason for the default: `.gitignore` is tracked, so editing it puts the file into `git diff` — the very scope this skill is about to review. A review tool whose first act is to dirty the diff it was invoked to clean has undermined itself. The local exclude file is never committed and never shows up in a diff.

The scanner also hard-skips its own workspace directory, so a run started before this step still will not review its own reports. That is a backstop, not a reason to skip Step 0.

## Step 1 — Resolve the review scope

Let the scanner do it. `--scope auto` (the default) takes the **union of all uncommitted work**: staged, unstaged, and untracked files. If the working tree is clean it falls back to the branch diff against a discovered base.

```bash
WINNOW=<absolute path to this skill's directory>   # resolve once, use everywhere
python3 "$WINNOW/scripts/scan.py"                  # cwd: anywhere inside the repo
python3 "$WINNOW/scripts/scan.py" --scope branch --base develop
```

Three things this handles that a hand-rolled `git diff` ladder does not:

- **Untracked files are in scope.** They are invisible to `git diff` in every mode, and brand-new files are exactly where generated code concentrates. Missing them is missing the point of the review.
- **One staged file no longer eclipses the rest.** A stop-at-first-non-empty ladder reviews the staged fraction of a partially-staged branch and reports full confidence.
- **The base branch is discovered**, in order: `origin/HEAD`, then `main`, `master`, `develop`, `development`, `trunk`, local refs before remote-tracking. `--base` overrides. Branch diffs use three dots — the merge base — so commits that landed on the base after you branched do not appear as your changes.

State the source and file count before continuing — `files`, `scanned_files` and `added_lines` come straight out of the JSON. If the user pointed at specific files, honor that and say so.

**A typo'd `--base` is the failure to watch for.** `--base develp` finds no such ref, records it in `warnings`, and returns an empty scope — which prints as a clean branch. So the integrity check is four fields, not three:

```
exit code != 0        → something went wrong, read `errors`
"complete": false     → files in scope were not reviewed, the scan has holes
warnings non-empty    → READ THEM. A bad --base, an unparseable file, and a
                        --since that was ignored all live here and nowhere else
findings == []        → only means "clean" when the three above are clear
```

Never report a clean result off `findings == []` alone. An empty `findings` with a non-empty `warnings` is a scan that did not happen.

**Check the size before dispatching.** If the diff runs past a few hundred changed lines across many files, say so and offer to split it — by directory, by commit, or by language — rather than handing an agent more than it can hold. A judgment pass over a diff that overflowed its context returns confident nonsense. Unattended, split it yourself by top-level directory rather than asking.

## Step 2 — Deterministic scan

```bash
python3 "$WINNOW/scripts/scan.py"                      # auto-resolves scope
python3 "$WINNOW/scripts/scan.py" --json               # for the reviewer agent
python3 "$WINNOW/scripts/scan.py" --paths a.cs b.py
python3 "$WINNOW/scripts/scan.py" --whole-files        # untouched lines of the SAME files
python3 "$WINNOW/scripts/scan.py" --report-name        # canonical report filename stem
python3 "$WINNOW/scripts/scan.py" --stem "$STEM" --json        # pin the stem across calls
python3 "$WINNOW/scripts/scan.py" --since .code-winnow/PRIOR.json     # reconcile with last run
python3 "$WINNOW/scripts/scan.py" --declined .code-winnow/declined.json  # drop settled items
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
current<branch>_files_<YYYYMMDD-HHMM>          --paths
```

Stdlib only, no install step. Paths resolve against the git toplevel, so the cwd does not matter as long as it is inside the repo. The default pass gives in-scope findings; that is the run that matters. `--whole-files` widens to the untouched lines *of the files the diff already touches* — no further. There is no repo-wide mode; auditing anything else requires the user to name files with `--paths`, which means asking for it.

It flags regex- and AST-level candidates: fields and locals declared and never referenced, fields only ever incremented and never read, locals assigned and never used, variables that just rename another for a single use, log-and-rethrow, empty Unity lifecycle methods, `async` with no `await`, unrooted `UObject*` **members**, invisible Unicode, comments restating the line below.

In test files it additionally flags tests with no assertion, assertions that cannot fail, tests whose every assertion checks a mock, structurally identical tests that differ only in literals, fixtures nothing requests, and skips with no reason. That pass runs for pytest/unittest, NUnit/xUnit/MSTest, GoogleTest, Go, Jest/Vitest/Mocha, JUnit, Rust, RSpec, and XCTest — a JS or Go test file gets it even though nothing else here understands JS or Go. `references/tests.md` is the judgment standard.

**Read `errors`, `warnings` and `complete` before you trust a small number** — the four-field check in Step 1. Vendored, generated, oversized, minified, and binary files are skipped by design; anything else is a hole in the coverage. A scanner that says "0 candidates" because it could not open the files looks identical to a clean branch, and exit code 2 plus `"complete": false` is how you tell them apart. If *every* file in scope was skipped, `complete` is false and the exit code is 2 — that is a scan that reviewed nothing, not a clean diff.

Unused and duplicate bindings need the most judgment of anything the scanner reports. A field with no reader may be dead weight, or may be read by a subclass, a serializer, or the Inspector — the scanner marks exposed declarations at P3 with a note to confirm, and stays silent entirely in headers and partial classes, where "never referenced in this file" is vacuous by construction. Nothing about a `[SerializeField]` or `UPROPERTY` should be deleted without checking scenes and assets.

The scanner is fast and dumb on purpose. It produces **candidates, never verdicts.** A `TODO` blocking a shipped feature and a `TODO` in a test fixture look identical to a regex.

**Capture the report stem now** — Steps 3, 4 and 6 all write files named from it, and each invocation stamps its own clock, so a run that crosses a minute boundary otherwise ends up with filenames that disagree:

```bash
STEM=$(python3 "$WINNOW/scripts/scan.py" --report-name)
# currentfeature-dash_targetmain_20260802-2028
```

Pass it back with `--stem "$STEM"` on every later call.

## Step 3 — Judgment pass, by a separate agent

**Do not judge your own output.** If you wrote the code under review, you hold the design rationale that produced the chaff, and you will rationalize it. That is not a discipline problem you can solve by trying harder — it is a context problem, solved by handing the work to a reader who does not have that context.

### Build the review input first

"The diff" is not a thing that exists for the default scope — untracked files are invisible to `git diff` in every mode, and they are where generated code concentrates. Build it once, explicitly, and hand the *same bytes* to both agents so their findings can be merged:

```bash
{
  git diff HEAD                                   # staged + unstaged, one numbering
  git ls-files --others --exclude-standard -z |
    while IFS= read -r -d '' f; do
      printf '\n--- NEW FILE: %s ---\n' "$f"; cat "$f"
    done
} > .code-winnow/$STEM.input.diff
```

For `--scope branch`, that first command is `git diff <base>...HEAD` and there is no untracked half. For `--paths`, it is the named files' full contents. The scanner's JSON `findings[].path` list tells you which files are in scope if you need to cross-check.

`git diff HEAD` — not `--cached` and plain `diff` separately. Those number the index blob and the worktree blob respectively, and the agents are reading the worktree.

### Dispatch

Dispatch two agents **in parallel** (see `superpowers:dispatching-parallel-agents`). Give each only that input file, the scanner JSON, and the reference files. **No conversation history, no design rationale, no mention of who wrote the code.**

**Division of labour, so their outputs merge cleanly:** Agent B owns every comment. Agent A does not report on comments at all — if A notices one, it belongs to B. Anything else in the diff is A's.

**Agent A — chaff judgment.** Everything except comments.
> Review this diff as if a stranger wrote it. Read `references/core-patterns.md`, plus the language file(s) matching the diff: `references/csharp-unity.md` (`.cs`), `references/cpp-ue5.md` (`.cpp`/`.h`), `references/python.md` (`.py`). **If the diff touches any test file, read `references/tests.md` too** — in any language, including ones with no language file here.
> For each scanner candidate: confirm or dismiss, with a reason. Then read the diff yourself — the scanner catches maybe half of what matters, and the half it misses (speculative abstraction, mock theatre, duplicated helpers) is the expensive half.
> Comments are not yours. Another agent is reviewing every comment in this diff; skip them entirely, including scanner candidates tagged `restated-comment` or `commented-code`.
> The reference files tell you to verify before deleting — trace every caller, grep for an existing helper, check scenes and assets for a serialized field. **Do those lookups.** They are searches and reads for evidence, they are not reviews: nothing you see outside the diff becomes a finding, no matter how bad it is. The three-file cap is on *reviewing* neighbouring files for convention, not on grepping the repo to find out whether a deletion is safe. When a lookup is impossible here, say "unverified" and drop the finding to P3 rather than proposing a deletion you could not check.
> Return findings as `path:line — what → why it matters → proposed change`, tagged P1/P2/P3, plus a list of candidates you dismissed and why.

**Agent B — comment concision.** Comments, and only comments.
> For every comment in the diff, return one of: DELETE (restates the code), KEEP (carries information the code cannot — a why, a workaround, an engine quirk, a business rule), or TIGHTEN (right content, too many words) with a rewrite.
> Rewrites: one line where one line does it. No preamble, no restating the function name, no hedging. Comments earn their space by saying something the reader cannot get from the code below them.
> Never delete a comment containing a link, a ticket reference, or the word "because" — those point at information outside the file.
> A version number is not automatically protective. `// Workaround for UE 5.4 normalize bug` is a KEEP: the version is *why* the code is shaped that way. `// Updated to use the new API in v2.3` is a changelog entry and a DELETE — git already has it. The test is whether the version explains the code below it or only records when someone touched it.

**Two searches, two different rules.** Reading a neighbouring file to learn the repo's conventions is capped at three files, is read-only, and produces no findings — it is the only reason to *review* a file the diff did not touch. Grepping the repo to check whether a helper already exists, whether a caller relies on a guard, or whether a scene references a field is verification, is uncapped, and also produces no findings. Everything else in the scope rules stands.

Serial fallback if the runtime has no subagents: run A, then B, yourself, and say once in the report that the judgment pass was self-review.

## Step 4 — Report

Never edit in this step.

### Naming and dating the report

Never write `report.md`. Use `$STEM` from Step 2 so successive runs never overwrite each other and so the file says what it reviewed. Write both `.code-winnow/<stem>.md` (the human report) and `.code-winnow/<stem>.json` (the scanner output, so the next run can reconcile against it). Put the generated timestamp, the scope, and the two branch names in the document header as well — filenames get copied into chat and lose their context, and a review whose date you cannot establish is a review nobody trusts.

**Every JSON the run writes gets its own filename.** `<stem>.json` is the pre-fix baseline and is never written again — Step 6 reads it. The concrete trap:

```bash
# Step 4 — baseline, written once
python3 "$WINNOW/scripts/scan.py" --stem "$STEM" --json > ".code-winnow/$STEM.json"

# Step 6 — WRONG. The shell truncates the file before python opens it, so
# --since reads an empty file and the baseline is gone.
python3 "$WINNOW/scripts/scan.py" --since ".code-winnow/$STEM.json" --json \
  > ".code-winnow/$STEM.json"

# Step 6 — right. New name out, baseline in, baseline untouched.
python3 "$WINNOW/scripts/scan.py" --stem "$STEM-postfix" --json \
  --since ".code-winnow/$STEM.json" > ".code-winnow/$STEM-postfix.json"
```

### Reconciling with the previous run

Find the most recent `.code-winnow/*.json` for the same scope and pass it to `--since`. The scanner marks each live finding `new` or `persisting`, and returns the ones present last time and absent now in `resolved`. Matching is by file, rule, message, and the normalised source line, so several instances of the same rule in one file stay distinguishable and survive the line shifts that deleting other findings causes.

Findings present before and absent now are **no longer true** — fixed, refactored away, or overtaken by events. Report them under their own heading and never re-list them as live. A punch list that keeps resurfacing settled items stops being read, and that failure is quiet: the user does not tell you they have started skimming.

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
Previous run: <prior stem, or "none">

### P1 — Risk (behavior, security, test integrity)
- `path/file.ext:LINE` — <what> → <why> → <proposed change>

### P2 — Maintainability
### P3 — Cosmetic

### Deliberately left alone
- <looked like chaff, isn't, and why>

### Pre-existing, in files this change touches
- <one sentence: what it is> <one sentence: what it does>

### No longer true since <prior report>
- <finding> — resolved

### Previously declined
- <finding> — raised <date>, declined

Full report: .code-winnow/<stem>.md — say the word to expand any item.
Fix all, or tell me which.
```

Every count in that header comes out of the JSON: `files`, `scanned_files`, `added_lines`. When `scanned_files < files`, say which ones were skipped and why — that gap is the difference between a clean branch and a scan with holes in it. Omit any section that is empty rather than printing an empty heading.

Severity:

- **P1** — swallowed exceptions with a broad or bare `except`, validation removed from a trust boundary, tests that assert nothing or assert only on mocks, invisible Unicode (zero-width, non-breaking, bidi — *not* a leading BOM), unrooted `UObject*` members, mutable default arguments, committed developer-home paths, machine names or secrets
- **P2** — speculative abstraction, defensive checks in trusted paths, unused fields, duplicated helpers, dead scaffolding, config knobs nothing sets, structurally duplicate tests, unused fixtures, `except SpecificError: pass`, `/home/...` paths
- **P3** — comments restating code, generic naming, formatting churn on untouched lines, em dashes and smart quotes *in code* (never in comments, docstrings, prose files, or localized user-facing strings)

The "deliberately left alone" section matters more than it looks. Showing what you considered and rejected is what makes the rest credible — and it stops the next run re-flagging the same lines.

If a P3-only list runs past a screen, cut it. Twenty cosmetic nits train the user to skim, and then they skim past the P1.

### Pre-existing flaws

One section, one meaning: **problems in the files this change touches, on lines this change did not touch.** Not the rest of the repo. This is a byproduct of reading around the diff, never a reason to go looking — and nothing seen during a Step 3 verification lookup belongs here either.

Two sources feed it, and both are optional:

- What the Step 3 agents noticed while reading around the diff. This is the usual source and needs no extra command.
- `python3 "$WINNOW/scripts/scan.py" --whole-files --json` — the same scan widened to the untouched lines of those same files. **This is the only thing that populates the scanner's `preexisting` findings**, so run it if you want the deterministic half; skip it on a large diff, where it mostly adds P3 noise about code the user did not write today. Either way, say which you did.

Log every one in full to the report file. In the user-facing output, give each **at most two sentences: one for what it is, one for what it does.** Then stop. Expand only on request.

> `AudioManager.cs:88` — Coroutine started in `OnEnable` is never stopped in `OnDisable`. Toggling the object leaks a coroutine per cycle, so audio triggers stack up over a session.

Not three sentences, not a proposed patch, not a severity debate. The user asked for a review of their change; pre-existing findings are a courtesy, and a courtesy that takes over the report stops being one. If there are more than five, list the top three by severity and give a count for the rest.

If the pre-existing list is longer than the in-scope list, that is the signal to say so in one line — "this file has more going on than your change does, want a proper pass over it?" — and let the user decide. Deciding for them turns a five-minute review into an afternoon.

## Step 5 — Apply, on approval only

Wait for explicit go-ahead. If nobody is there to give one, **stop after Step 4** — see the unattended table above; an unattended run never edits.

### Step 5a — Make the edits reversible, before the first one

**This is not optional and it comes before any edit, including the first one you are sure about.**

The advertised default scope is uncommitted work *including untracked files*. "Fix all" then deletes lines from files that have never been in the object store — no blob, no reflog, no `git checkout --`, no `git stash pop`. The headline trigger for this whole skill is "clean this up before I commit", so the common case is precisely the one git cannot undo.

Copy the files first:

```bash
BACKUP=".code-winnow/$STEM.pre-fix"
python3 -c "
import json,os,shutil,sys
data=json.load(open(sys.argv[1],encoding='utf-8'))
root=os.getcwd(); dest=sys.argv[2]
for p in sorted({f['path'] for f in data['findings']}):
    d=os.path.join(dest,p); os.makedirs(os.path.dirname(d),exist_ok=True)
    shutil.copy2(os.path.join(root,p),d)
" ".code-winnow/$STEM.json" "$BACKUP"
```

Run it from the git toplevel. Then tell the user, in one line, where the copies are and how to undo:

> Backed up 7 files to `.code-winnow/currentmain_worktree_20260802-2028.pre-fix/`. To undo everything, from the repo root: `cp -a .code-winnow/currentmain_worktree_20260802-2028.pre-fix/. .` (PowerShell: `Copy-Item -Recurse -Force '.code-winnow\currentmain_worktree_20260802-2028.pre-fix\*' .`)

If the copy fails — read-only filesystem, no shell — **say so and stop.** Do not edit anyway. A cleanup that cannot be undone is not a cleanup the user agreed to, and "I could not make a backup" is a decision for them, not for you.

`git stash` is not a substitute: `--include-untracked` moves the user's work out of the tree, which is disruptive mid-review, and it still cannot be un-popped cleanly after further edits. A plain file copy inside the already-excluded workspace has none of those failure modes.

### Step 5b — The edits

**Load `andrej-karpathy-skills:karpathy-guidelines` before the first edit** — it governs how the fixes are made, and a cleanup pass that introduces its own chaff has achieved nothing. In runtimes without it, the operative parts are: make the smallest change that resolves the finding, do not rewrite what you were not asked to rewrite, state any assumption you had to make, and define what "fixed" looks like before editing.

- Deletion beats rewriting.
- One concern per edit. Do not fold a rename into a comment removal.
- Behavior stays identical. If a fix would change behavior, it is not a winnowing fix — surface it separately and leave it.
- Nothing outside the resolved scope, including formatting.

## Step 6 — Verify

Run the project's tests and report the actual output — see `superpowers:verification-before-completion`. If there is no suite, say so plainly rather than implying verification happened; an unverified cleanup that silently changed behavior is worse than the chaff.

If a test breaks, root-cause it (`superpowers:systematic-debugging`) rather than reverting blindly.

Then re-run the scanner with `--since` against the pre-fix JSON — **writing to a new filename**, per the Step 4 warning; `--since X.json > X.json` truncates the baseline before Python reads it and reports zero resolutions off an empty file:

```bash
python3 "$WINNOW/scripts/scan.py" --stem "$STEM-postfix" --json \
  --since ".code-winnow/$STEM.json" --declined .code-winnow/declined.json \
  > ".code-winnow/$STEM-postfix.json"
```

Read the **`resolved`** array, not the raw count. Your deletions moved every line below them, so comparing line numbers between the two runs is meaningless; the reconciliation is what tells you a finding actually cleared. Anything still listed as `persisting` did not.

Once verification passes, the backup from Step 5a has done its job. Say where it is and leave it — deleting it is the user's call, and `.code-winnow/` is already excluded from git.

Finally, hand off to `superpowers:requesting-code-review` for a cold pass over the applied diff, and offer a simplification skill if a path is still hard to follow after the deletions.

## Never touch

These look like chaff and are load-bearing:

- **Validation at trust boundaries** — user input, network payloads, deserialization, file parsing, plugin APIs. Redundant-looking checks at an edge are the point. "Defensive overkill" applies only to internal callers you control.
- **Comments explaining why** — workarounds, engine quirks, business rules, issue links. Delete comments that restate code; keep comments carrying information code cannot.
- **Public API surface** — exported names, serialized fields, `UPROPERTY`/`[SerializeField]`, anything Inspector- or Blueprint-facing. Renaming these is a breaking change wearing a cleanup costume.
- **Test scaffolding** — fixtures, fakes, builders, and `TODO`s in test files are normal, and a little repetition in them beats cleverness.

  This is not a blanket pass for test files, and treating it as one is how false coverage survives review. A test that asserts nothing, asserts a tautology, or asserts only that a mock was called is not scaffolding — it is a test that cannot fail, and P1 is the right severity for it. The fix is almost always to tighten the assertion, never to delete the test: removing a test is a coverage regression wearing a cleanup costume. See `references/tests.md`.
- **Anything outside the diff** — report it under Pre-existing, in two sentences, and move on.

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
