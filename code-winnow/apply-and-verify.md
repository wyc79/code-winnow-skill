# Code-winnow — apply and verify (Steps 5 – 6)

Steps 5 and 6. Two paths reach this file: a full review arriving from Step 4b of `$WINNOW/review-pipeline.md`, and a cold run invoked as `code-winnow: apply <plan>.fixplan.md`. Read `SKILL.md` first if you have not — **the scope rules and `Never touch` are stated only there and bind every edit below.**

**An approved fix plan exists, and Step 0 has run.** On the cold path, `SKILL.md`'s "Entering at Step 5 cold" states what else must be true — the `Status:` gate, the stale-`env.sh` check, and the four things not to do — before the first block here runs.

## Step 5 — Apply

**Step 5a happens exactly once per fix plan, before any edit** — the backup *and* the pre-fix test baseline, since both capture a state the first edit destroys. Who runs it depends on the rung: on rungs 1 and 3 it is the executor's first action; on rung 2 the *supervisor* runs it before dispatching, because the fix agents have never read this file. Never twice — the script refuses a non-empty backup directory precisely because a second run overwrites the originals with fixed files.

### Step 5a — Make the edits reversible, before the first one

**This is not optional and it comes before any edit, including the first one you are sure about.**

The advertised default scope is uncommitted work *including untracked files*. "Fix all" then deletes lines from files that have never been in the object store — no blob, no reflog, no `git checkout --`, no `git stash pop`. The headline trigger for this whole skill is "clean this up before I commit", so the common case is precisely the one git cannot undo.

**The list comes from the fix plan's `file:` lines, not from the scanner JSON** — Agent C reports on files the diff never touched, and those have no JSON entry to copy from.

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
"$PY" "$WINNOW/scripts/backup.py" "$BACKUP" "$ROUND/fixplan.md"
```

**Any `REFUSING:` line means stop and tell the user.** Do not edit, and do not "fix" the plan by dropping the item that would not parse. The script refuses on six things, each of which fails silently without the guard: a missing or non-`APPROVED` `Status:` line, fix items appearing after `## Never touch`, a non-empty backup directory, a destination pasted from the plan header rather than computed, any `file:` path missing from disk, and an item with no `file:` line at all. Its module docstring has what each one prevents.

**A tracked file is not "safe because git can restore it" either** — same reasoning, same failure. Then tell the user, in one line, where the copies are and how to undo:

> Backed up 7 files to `.code-winnow/round-02/pre-fix/`. To undo everything, from the repo root: `cp -a .code-winnow/round-02/pre-fix/. .` (PowerShell: `Copy-Item -Recurse -Force '.code-winnow\round-02\pre-fix\*' .`)

If the copy fails — read-only filesystem, no shell — **say so and stop.** Do not edit anyway. A cleanup that cannot be undone is not a cleanup the user agreed to, and "I could not make a backup" is a decision for them, not for you.

`git stash` is not a substitute. `DESIGN.md` (Step 5a) has why, and the rest of this step's near-miss rationale.

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

**The name list matters more than the count**, because counts can coincide — Step 6 diffs the two name sets, and a count comparison alone would call a same-count swap clean. If the runner cannot list tests, say so, fall back to counts, and note in the report that such a swap would go undetected.

**Without this, Step 6 cannot tell your deletion from a pre-existing failure**, and the two misreadings damage in opposite directions: assume green and you chase a failure you did not cause, eventually "fixing" unrelated code to make it pass; assume it was already red and you wave through the one your cleanup caused.

**Finding the command: read the repo rather than guessing** — `package.json` scripts, `Makefile`, `pyproject.toml`, `*.csproj`, `CONTRIBUTING.md`, and above all the CI workflow, which runs the command the project actually trusts. Do not substitute the ecosystem's usual invocation for the one this repo uses.

**If there is no suite, write `Tests-before: none` and say so out loud.** Then the deletion-safety pass in Step 6 is the only correctness gate the run has, which changes how carefully you should treat an `unverified` item — and the user deserves to know that before approving.

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

**The whole suite, every time.** No `-k`, no `--last-failed`, no single test file, no "just the tests near what I changed" — a deletion's blast radius is wherever the deleted thing was referenced from, which is precisely what you could not see.

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

**Report the arithmetic, not a verdict:** `412 collected before, 410 after; plan declared −3 +1; reconciled, no unexplained loss.` A reader can check that. "Tests pass" cannot be checked at all — and a green run with 400 tests where there were 412 is the coverage regression `tests.md` warns about, wearing a cleanup costume.

Then re-run the scanner with `--since` against the pre-fix JSON — **writing to a new filename**, per the Step 4 warning:

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
DECLINED=""
[ -f .code-winnow/declined.json ] && DECLINED="--declined .code-winnow/declined.json"
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM-postfix" --json \
  --since "$ROUND/scan.json" $DECLINED \
  > "$ROUND/scan-postfix.json"
```

**`$SCOPE` matters most here** — omit it and this scan resolves a different scope from the baseline it compares against, and every untouched finding comes back `resolved`. `DESIGN.md` (Step 6) has the shape of that failure.

Read the **`resolved`** array, not the raw count. Your deletions moved every line below them, so comparing line numbers between the two runs is meaningless; the reconciliation is what tells you a finding actually cleared. Anything still listed as `persisting` did not.

Then reconcile against the fix plan, which is the record of what was approved. Report three numbers plainly: **approved, applied, skipped** — with a reason for every skip, "anchor no longer present" included. An item that was approved and quietly not applied is the failure mode here, and it looks exactly like success.

Once verification passes, the backup from Step 5a has done its job. Say where it is and leave it — deleting it is the user's call, and `.code-winnow/` is already excluded from git.

### The deletion-safety pass — first in execution order, written last

**Run this on every run, before the test comparison above.** A cold reviewer reads the diff as it now stands and does not know which lines you removed — this pass is the only thing in the run that checks the removals themselves, and it is five questions.

**Agent E asked these same five questions in Step 3, and that does not make this pass redundant.** E asked them about lines A *proposed* removing; this asks them about lines that were *actually* removed — a different set, because the user edits the plan, items go stale and get skipped, and a cold Step 5 session executes without E's output in front of it. E prevents; this verifies. **Run it even on a run where E vetoed nothing.**

**Re-run every `evidence:` command behind an applied deletion and read the delta. Equality is the wrong test here** — these commands are *pre*-conditions, true because the code was still there, so a correct deletion changes their output. `DESIGN.md` (Step 6) has why Step 5b reads equality and this reads a delta.

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

