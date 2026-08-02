---
name: code-winnow
description: Winnow a branch or staged diff — separate the code that earns its place from the chaff a generator left behind: comments that restate the code, defensive checks in trusted paths, log-and-rethrow wrappers, speculative abstractions, unused fields, duplicate variables, mock-only tests. Runs a deterministic scanner, hands judgment to a separate reviewer agent, reports a punch list, and applies minimal fixes on approval. Use this whenever the user says "winnow", "code-winnow", "de-slop", "deslop", "clean this up before I commit", "does this look AI-written", "review my diff", "make this idiomatic", or is about to open a PR on agent-written code. Also use it proactively after a large generated change lands and before any commit a human reviewer will read. Tuned for C#/Unity, C++/UE5, and Python, with language-agnostic rules for everything else. Runs on any agent runtime with Python 3 and git.
---

# Code-winnow

Generated code fails review in predictable ways. It is rarely wrong; it is bloated, over-defensive, and stylistically foreign to the repo it landed in. Linters catch the subset that is a rule violation. The rest is judgment, and that is the gap this skill fills — winnowing, in the old sense: keep the grain, blow off the chaff.

**Scope discipline is the whole game.** Operate only on lines the current change added or modified. A cleanup pass that wanders into untouched files produces a diff nobody can review, which is a worse outcome than the chaff you removed.

**This is a diff review, not a repository audit.** Unless the user asks in so many words for a whole-repo pass, the job is the current change and nothing else. Pre-existing problems reach the report only as byproducts — you had the file open to review the diff, you noticed something, you mention it. Do not go looking. Do not open files the diff did not touch *except* for the narrow convention check in Step 3, do not sweep for vulnerabilities, and do not let incidental findings grow past a short aside. Someone who asked you to winnow a branch and got a repo-wide defect list back did not get what they asked for, and the thing they did ask for is now buried.

**Before anything else:** read `references/portability.md`, check which companion skills are available here, look through the installed skills for anything that fills a missing role under a different name, and — if anything is still missing — say so once, proposing the equivalents you found and letting the user choose between those, installing, running degraded, or naming their own substitute. Do not silently take the weakest path. If everything is present, say nothing.

**If nobody is there to answer** — a scheduled run, a headless runtime, or a user who has already said they are stepping away — do not block on that question. Take the degraded path, start the review, and put the notice at the top of the report instead. A run that stalls for four hours waiting on a multiple-choice question has failed more completely than one that ran self-review.

## Companion skills

| Skill | Used at | Purpose |
|---|---|---|
| `andrej-karpathy-skills:karpathy-guidelines` | Step 5, loaded before any edit | Governs how fixes are made. Prevents the cleanup itself from adding chaff. |
| `superpowers:dispatching-parallel-agents` | Step 3 | Fans out the judgment and comment passes. |
| `superpowers:requesting-code-review` | Step 6 | Cold pass over the applied fixes. |
| `superpowers:verification-before-completion` | Step 6 | No success claim without a run command and its output. |
| `superpowers:systematic-debugging` | Step 6, on failure | Root-cause a broken test rather than patching over it. |
| A simplification skill | Step 6, optional | Restructures genuinely complex paths. Chaff removal is deletion; simplification is restructuring. Different jobs, in that order. |

Any of these may be absent — including on Claude Code, where the set installed varies by user. `references/portability.md` has the detection, the degraded path, and the install route for each, plus the notice format for telling the user before the review starts. Substitutes the user has already chosen are recorded in `.code-winnow/substitutions.md`; read it before asking anything.

## Step 0 — Make the workspace invisible to git

Before writing anything: ensure `.code-winnow/` is excluded. **Prefer `.git/info/exclude`** — append `.code-winnow/` there, say so in one line, and move on.

Use `.gitignore` only if the user wants the exclusion shared with their team, and only after telling them it will appear in the diff. That is the reason for the default: `.gitignore` is tracked, so editing it puts the file into `git diff` — the very scope this skill is about to review. A review tool whose first act is to dirty the diff it was invoked to clean has undermined itself. `.git/info/exclude` is local-only, never committed, and never shows up in a diff.

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

State the source and file count before continuing. If the user pointed at specific files, honor that and say so.

**Check the size before dispatching.** If the diff runs past a few hundred changed lines across many files, say so and offer to split it — by directory, by commit, or by language — rather than handing an agent more than it can hold. A judgment pass over a diff that overflowed its context returns confident nonsense.

## Step 2 — Deterministic scan

```bash
python3 "$WINNOW/scripts/scan.py"                      # auto-resolves scope
python3 "$WINNOW/scripts/scan.py" --json               # for the reviewer agent
python3 "$WINNOW/scripts/scan.py" --paths a.cs b.py
python3 "$WINNOW/scripts/scan.py" --whole-files        # untouched lines of the SAME files
python3 "$WINNOW/scripts/scan.py" --report-name        # canonical report filename stem
python3 "$WINNOW/scripts/scan.py" --stem "$STEM" --json        # pin the stem across calls
python3 "$WINNOW/scripts/scan.py" --since .code-winnow/PRIOR.json   # reconcile with last run
```

Stdlib only, no install step. Paths resolve against the git toplevel, so the cwd does not matter as long as it is inside the repo. The default pass gives in-scope findings; that is the run that matters. `--whole-files` widens to the untouched lines *of the files the diff already touches* — no further. There is no repo-wide mode; auditing anything else requires the user to name files with `--paths`, which means asking for it.

It flags regex- and AST-level candidates: fields and locals declared and never referenced, fields only ever incremented and never read, locals assigned and never used, variables that just rename another for a single use, log-and-rethrow, empty Unity lifecycle methods, `async` with no `await`, unrooted `UObject*` **members**, invisible Unicode, comments restating the line below.

In test files it additionally flags tests with no assertion, assertions that cannot fail, tests whose every assertion checks a mock, structurally identical tests that differ only in literals, fixtures nothing requests, and skips with no reason. That pass runs for pytest/unittest, NUnit/xUnit/MSTest, GoogleTest, Go, Jest/Vitest/Mocha, JUnit, Rust, RSpec, and XCTest — a JS or Go test file gets it even though nothing else here understands JS or Go. `references/tests.md` is the judgment standard.

**Read the `errors` array and the `complete` flag before you trust a small number.** Vendored, generated, oversized, minified, and binary files are skipped by design; anything else in there is a hole in the coverage. A scanner that says "0 candidates" because it could not open the files looks identical to a clean branch, and exit code 2 plus `"complete": false` is how you tell them apart.

Unused and duplicate bindings need the most judgment of anything the scanner reports. A field with no reader may be dead weight, or may be read by a subclass, a serializer, or the Inspector — the scanner marks exposed declarations, headers, and partial classes at P3 with a note to confirm, and nothing about a `[SerializeField]` or `UPROPERTY` should be deleted without checking scenes and assets.

The scanner is fast and dumb on purpose. It produces **candidates, never verdicts.** A `TODO` blocking a shipped feature and a `TODO` in a test fixture look identical to a regex.

## Step 3 — Judgment pass, by a separate agent

**Do not judge your own output.** If you wrote the code under review, you hold the design rationale that produced the chaff, and you will rationalize it. That is not a discipline problem you can solve by trying harder — it is a context problem, solved by handing the work to a reader who does not have that context.

Dispatch two agents **in parallel** (see `superpowers:dispatching-parallel-agents`). Give each only the diff, the scanner JSON, and the reference files. **No conversation history, no design rationale, no mention of who wrote the code.**

**Agent A — chaff judgment.**
> Review this diff as if a stranger wrote it. Read `references/core-patterns.md`, plus the language file(s) matching the diff: `references/csharp-unity.md` (`.cs`), `references/cpp-ue5.md` (`.cpp`/`.h`), `references/python.md` (`.py`). **If the diff touches any test file, read `references/tests.md` too** — in any language, including ones with no language file here.
> For each scanner candidate: confirm or dismiss, with a reason. Then read the diff yourself — the scanner catches maybe half of what matters, and the half it misses (speculative abstraction, mock theatre, duplicated helpers) is the expensive half.
> Before flagging anything as non-idiomatic, read up to three neighbouring files **for convention only** — you are checking what the repo already does, not reviewing those files. Nothing you see in them becomes a finding. If the repo does it everywhere, it is consistency, not chaff — report it as a repo-wide observation, not a line finding.
> Return findings as `path:line — what → why it matters → proposed change`, tagged P1/P2/P3, plus a list of candidates you dismissed and why.

**Agent B — comment concision.**
> For every comment in the diff, return one of: DELETE (restates the code), KEEP (carries information the code cannot — a why, a workaround, an engine quirk, a business rule), or TIGHTEN (right content, too many words) with a rewrite.
> Rewrites: one line where one line does it. No preamble, no restating the function name, no hedging. Comments earn their space by saying something the reader cannot get from the code below them.
> Never delete a comment containing a link, a ticket reference, a version number, or the word "because".

That neighbour-read is the **only** exception to "do not open files the diff did not touch," it is read-only, and it is capped at three files. Everything else in the scope rules stands.

Serial fallback if the runtime has no subagents: run A, then B, yourself, and say once in the report that the judgment pass was self-review.

## Step 4 — Report

Never edit in this step.

### Naming and dating the report

Never write `report.md`. Get the filename from the scanner so successive runs never overwrite each other and so the file says what it reviewed:

```bash
STEM=$(python3 "$WINNOW/scripts/scan.py" --report-name)
# current<branch>_target<base>_<YYYYMMDD-HHMM>   e.g. currentfeature-dash_targetmain_20260802-2028
# current<branch>_worktree_<YYYYMMDD-HHMM>       uncommitted work
# current<branch>_staged_<YYYYMMDD-HHMM>         explicit --scope staged
```

**Capture the stem once and pass it back with `--stem`** on every later call. Each invocation stamps its own clock, so a run that crosses a minute boundary otherwise ends up with a filename and an embedded `report_stem` that disagree.

Write both `.code-winnow/<stem>.md` (the human report) and `.code-winnow/<stem>.json` (the scanner output, so the next run can reconcile against it). Put the generated timestamp, the scope, and the two branch names in the document header as well — filenames get copied into chat and lose their context, and a review whose date you cannot establish is a review nobody trusts.

### Reconciling with the previous run

Find the most recent `.code-winnow/*.json` for the same scope and pass it to `--since`. The scanner marks each live finding `new` or `persisting`, and returns the ones present last time and absent now. Matching is by file, rule, message, and the normalised source line, so several instances of the same rule in one file stay distinguishable and survive the line shifts that deleting other findings causes.

Findings present before and absent now are **no longer true** — fixed, refactored away, or overtaken by events. Report them under their own heading and never re-list them as live. A punch list that keeps resurfacing settled items stops being read, and that failure is quiet: the user does not tell you they have started skimming.

Findings you raised before and the user explicitly declined get the same treatment — note them once as previously declined and leave them out of the live list.

Show the user the condensed version:

```
## Winnow report
Generated: <YYYY-MM-DD HH:MM>
Scope: <diff source> — <current branch> vs <base / worktree / staged>
Files: <N>, added lines: <M><, K files not scanned — see below if any>
Previous run: <prior stem, or "none">

### P1 — Risk (behavior, security, test integrity)
- `path/file.ext:LINE` — <what> → <why> → <proposed change>

### P2 — Maintainability
### P3 — Cosmetic

### Deliberately left alone
- <looked like chaff, isn't, and why>

### Pre-existing (outside this change)
- <one sentence: what it is> <one sentence: what it does>

### No longer true since <prior report>
- <finding> — resolved

Full report: .code-winnow/<stem>.md — say the word to expand any item.
Fix all, or tell me which.
```

Severity:

- **P1** — swallowed exceptions, validation removed from a trust boundary, tests that assert nothing or assert only on mocks, invisible Unicode, unrooted `UObject*` members, mutable default arguments, committed local paths or secrets
- **P2** — speculative abstraction, defensive checks in trusted paths, unused fields, duplicated helpers, dead scaffolding, config knobs nothing sets, structurally duplicate tests, unused fixtures
- **P3** — comments restating code, generic naming, formatting churn on untouched lines

The "deliberately left alone" section matters more than it looks. Showing what you considered and rejected is what makes the rest credible — and it stops the next run re-flagging the same lines.

If a P3-only list runs past a screen, cut it. Twenty cosmetic nits train the user to skim, and then they skim past the P1.

### Pre-existing flaws

Reviewing a diff means reading the files around it, and you will notice real problems in lines this change did not touch. Mention them; do not chase them. Nothing here licenses opening a file the diff did not touch.

Log every one in full to the report file. In the user-facing output, give each **at most two sentences: one for what it is, one for what it does.** Then stop. Expand only on request.

> `AudioManager.cs:88` — Coroutine started in `OnEnable` is never stopped in `OnDisable`. Toggling the object leaks a coroutine per cycle, so audio triggers stack up over a session.

Not three sentences, not a proposed patch, not a severity debate. The user asked for a review of their change; pre-existing findings are a courtesy, and a courtesy that takes over the report stops being one. If there are more than five, list the top three by severity and give a count for the rest.

If the pre-existing list is longer than the in-scope list, that is the signal to say so in one line — "this file has more going on than your change does, want a proper pass over it?" — and let the user decide. Deciding for them turns a five-minute review into an afternoon.

## Step 5 — Apply, on approval only

Wait for explicit go-ahead. **Load `andrej-karpathy-skills:karpathy-guidelines` before the first edit** — it governs how the fixes are made, and a cleanup pass that introduces its own chaff has achieved nothing. In runtimes without it, the operative parts are: make the smallest change that resolves the finding, do not rewrite what you were not asked to rewrite, state any assumption you had to make, and define what "fixed" looks like before editing.

- Deletion beats rewriting.
- One concern per edit. Do not fold a rename into a comment removal.
- Behavior stays identical. If a fix would change behavior, it is not a winnowing fix — surface it separately and leave it.
- Nothing outside the resolved scope, including formatting.

## Step 6 — Verify

Run the project's tests and report the actual output — see `superpowers:verification-before-completion`. If there is no suite, say so plainly rather than implying verification happened; an unverified cleanup that silently changed behavior is worse than the chaff.

If a test breaks, root-cause it (`superpowers:systematic-debugging`) rather than reverting blindly.

Then re-run the scanner with `--since` against the pre-fix JSON and read the **"no longer true"** section, not the raw count. Your deletions moved every line below them, so comparing line numbers between the two runs is meaningless; the reconciliation is what tells you a finding actually cleared. Anything still listed as `persisting` did not.

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
