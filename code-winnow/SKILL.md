---
name: code-winnow
description: 'Use when the user wants generated-code chaff removed from an uncommitted change or a branch — "winnow", "de-slop", "deslop", "clean this up before I commit", "does this look AI-written", "make this idiomatic", "cut the slop" — or is about to open a PR on agent-written code, or a large generated change just landed. Also use when asked to apply or resume an approved cleanup: "apply the fix plan", "code-winnow: apply <path>.fixplan.md". Not for general code review, bug hunts, or security audits.'
---

# Code-winnow

Generated code fails review in predictable ways. It is rarely wrong; it is bloated, over-defensive, and stylistically foreign to the repo it landed in. Linters catch the subset that is a rule violation. The rest is judgment, and that is the gap this skill fills — winnowing, in the old sense: keep the grain, blow off the chaff.

**Needs Python 3.9+ and git.** It writes reports, a fix plan and file backups under `.code-winnow/`, and git-excludes that path in Step 0. Companion skills are optional; `$WINNOW/references/portability.md` has the degraded paths.

> **Were you invoked to apply a fix plan?** If the request names a `.code-winnow/*.fixplan.md`, or asks to apply or resume an approved cleanup, go straight to **"Entering at Step 5 cold"** near the end of this file, and from there to `$WINNOW/apply-and-verify.md`. Re-run Step 0 — it is idempotent and it verifies — then skip Steps 1 through 4b entirely. **Never open `$WINNOW/review-pipeline.md` on this path**; it holds those steps and nothing else you need. The review already happened; re-running it wastes the context the plan exists to save and re-opens decisions the user already made.

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

**References live under `$WINNOW/references/`.** Each file names its readers at the top — hand an agent only what its prompt lists, since every extra file is paid five times over on a parallel run. Four are yours rather than an agent's: `core-patterns.md` and `comment-evidence.md` (read both yourself, before Step 3 — see "Before you start"), `report-format.md` (every artifact's shape) and `portability.md` (degraded paths). `$WINNOW/scripts/scan.py` is the scanner; `$WINNOW/scripts/backup.py` is Step 5a. The steps are in two files beside this one — `$WINNOW/review-pipeline.md` (Steps 1 – 4b) and `$WINNOW/apply-and-verify.md` (Steps 5 – 6) — routed after Step 0. Maintainers editing a snippet in any of the three: `DESIGN.md` holds the near-miss rationale.

## The scope rules

**Scope discipline is the whole game.** Operate only on lines the current change added or modified. A cleanup pass that wanders into untouched files produces a diff nobody can review, which is a worse outcome than the chaff you removed.

**If the user names one feature, that is the scope** — not the whole diff, even when the diff is a branch against a base. "Winnow the dash cooldown work" means the hunks that feature touched and nothing else, however much chaff is sitting three files away. Touching unrelated code inside an approved diff is the same failure as wandering outside it: the user gets back a change they did not ask for, mixed into one they cannot separate it from. Step 1 resolves the feature set and states it back before anything is reviewed.

**This is a diff review, not a repository audit.** Unless the user asks in so many words for a whole-repo pass, the job is the current change and nothing else. Pre-existing problems reach the report only as byproducts — you had the file open to review the diff, you noticed something, you mention it. Do not go looking, do not sweep for vulnerabilities, and do not let incidental findings grow past a short aside. Someone who asked you to winnow a branch and got a repo-wide defect list back did not get what they asked for, and the thing they did ask for is now buried.

**Two passes look like exceptions to that and are not.** Agent E asks how the change breaks silently, D asks what it made slow, and both work on diff lines like everyone else. **E is not a security review and does not go looking for vulnerabilities**; it asks whether *this change* removed a protection, committed a credential, or introduced a failure with no signal — those three, and nothing else in that direction. Their gates are `$WINNOW/references/fragility.md` and `performance.md`; an agent dispatched without its file produces exactly the unbounded critique this paragraph refuses.

**The rule is about what becomes a finding, not about what you may read.** Only lines the diff touched can produce one. Reading elsewhere is permitted for exactly three purposes, and none produces a finding however bad the code you pass through looks:

| Purpose | Cap | What it is |
|---|---|---|
| Learning the repo's conventions | **Three files** | *Reviewing* neighbouring code to see how this repo writes things |
| Verifying that a deletion is safe | Uncapped | Grepping for an existing helper, tracing callers, checking scenes for a serialized field |
| Sampling file headers for their shape | Uncapped, top 15 lines only | Extracting a boilerplate shape, not reading the files |

The last two are uncapped because they are lookups, not reviews — you are answering a yes/no about a specific line, not forming an opinion about someone else's file. The three-file cap binds only the first, and stretching it to cover a grep is how "verify before you delete" quietly becomes "delete without checking".

**Three rings, then.** The repo, which you may read and never report on. The diff, which produces findings. The named feature inside it, when there is one, which is the only thing eligible for a fix. When no feature is named the inner two rings are the same and nothing changes.

**Six languages are claimed, in two tiers**, and the tiers differ in what the *scanner* can do, not in how carefully the judgment is made. Full tier — Python, Unity C#, Unreal C++ — has structure-aware scanner rules. Web tier — JavaScript/TypeScript, HTML, CSS — is **regex-level only**: nothing deterministic here finds an unused binding, a dead function or a near-duplicate component in a `.ts` file, so a quiet scan over one must never be reported as coverage. The full statement is "What this skill actually claims" in `core-patterns.md`, which you read anyway. Two things bind here regardless: **when you cannot say what a line is for, keep it** — a directive list missing your ecosystem's suppression looks exactly like a complete one, right up until the deletion — and the report says which languages the diff touched and which of them were claimed.

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
| `andrej-karpathy-skills:karpathy-guidelines` | Step 5, before any edit | Stops the cleanup adding chaff of its own |
| `superpowers:dispatching-parallel-agents` | Step 3, and Step 4b rung 2 | Fans out the judgment passes; carries the fix work when context is not cleared |
| `superpowers:requesting-code-review` | Step 6 | Cold pass over the applied fixes |
| `superpowers:verification-before-completion` | Step 6 | No success claim without a run command and its output |
| `superpowers:systematic-debugging` | Step 6, on failure | Root-cause a broken test rather than patch over it |
| A simplification skill | Step 6, optional | Restructuring, which is a different job from deletion and comes after it |

**Any of these may be absent**, and the set varies by user even on Claude Code. Detection, degraded path, install route and notice format for each: `$WINNOW/references/portability.md`. Substitutes the user already chose are in `.code-winnow/substitutions.md` — read it before asking anything, and **after Step 0**, since writing it is what makes Step 0 come first.

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

## Then read the pipeline for your entry path

The steps live in two files, and which one you open depends on how you were invoked. Everything above this line binds both of them and is stated only here; neither file repeats it.

| Invoked to | Open now | Steps |
|---|---|---|
| **Review a change** | `$WINNOW/review-pipeline.md` — then `$WINNOW/apply-and-verify.md` when Step 4b hands off | 1 → 4b, then 5 → 6 |
| **Apply an approved plan** | `$WINNOW/apply-and-verify.md`. **Do not open `review-pipeline.md`** — read "Entering at Step 5 cold" below first | 5 → 6 |

**Open the file when you reach it, not before.** The review pipeline is the larger half, and a run invoked to apply a plan never needs a line of it — that is the whole reason it is a separate file rather than a section of this one.

## Entering at Step 5 cold

You were invoked with a fix plan rather than a review request — `code-winnow: apply .code-winnow/round-NN/fixplan.md`, or any phrasing that names one. The review already happened, in a session whose context is gone. Your job is to execute a list, not to form an opinion.

**First, check the `Status:` line — it must be present and must read `APPROVED`.** Anything else, including *no `Status:` line at all*, means stop: report that nobody has reviewed these findings and ask for approval before anything else. Absence is not permission. `scripts/backup.py` enforces this with a `REFUSING:` line so the gate does not depend on you remembering to read it here, but knowing why it refused saves a confused retry.

1. Read the fix plan. It is self-contained: `Status`, `Skill` (your `$WINNOW`), `Scope`, `Feature`, `Baseline` (the pre-fix JSON for Step 6), `Backup`, `Undo`, `Verify`, then the fixes and the never-touch list. Each fix carries `file:`, `line:`, `occurrence:`, `of:`, `anchor:`, `fix:` and `evidence:` — **the first five are what locate the edit**, and the rules for using them are in `$WINNOW/apply-and-verify.md` under "Locating a fix at execution time". Read that section; it is the one part of the review you do inherit, and it sits in the file you are about to open rather than in the review pipeline you are skipping. **`$ROUND` is the directory the plan sits in, and everything else derives from it** — the baseline is `$ROUND/scan.json`, the backup is `$ROUND/pre-fix`, and `$STEM` is `$ROUND/meta.json`'s `stem` field.
2. Re-run the Step 0 block. It is idempotent and it verifies with `git check-ignore` — cheap insurance against a repo where the exclusion was lost or was never valid, which in a linked worktree it silently was not. This is the one part of Steps 0–4b you *do* run.

   Then look at `.code-winnow/env.sh` before running anything that sources it. **It is from the session that wrote the plan, and it may name a different `$ROUND`** — a later review in the same repo overwrites it, and a plan copied to another machine has none at all. Every block below opens with `. .code-winnow/env.sh`, so a stale file silently redirects the backup and the reconciliation into another round's directory. If its `ROUND` does not match the directory the plan sits in, or the file is missing, set `WINNOW`, `PY`, `STEM`, `ROUND` and `BACKUP` yourself at the top of each call.

   **Derive them from the plan's location, not by copying its header values.** `$ROUND` is the plan's own directory; `BACKUP` is `$ROUND/pre-fix`; the baseline is `$ROUND/scan.json`; and `STEM` is `$ROUND/meta.json`'s `stem` field. The header's `Skill:` line is the one field to read directly, because nothing else carries `$WINNOW`. A header value is prose and arrives with whatever else is on its line; `DESIGN.md` (Step 5a) has the backup that went missing that way.
3. Step 5a — the backup, from the plan's `file:` lines. Any `REFUSING:` line means stop and say so. Then run the `Verify:` command **before editing** and fill in `Tests-before:` yourself if the plan does not already carry it. A cold session inherits no memory of what was green, and Step 6 is a comparison against that number.
4. Step 5b — the edits, located by normalised anchor, per the rules in `apply-and-verify.md`. No searching for moved anchors. **Any item that removes code and whose `evidence:` line reads `unverified` is skipped and reported, not applied** — and not researched. You have none of the context that decision was made in, which is the entire point of starting cold.
5. Step 6 — verify, reconcile against `Baseline`, report approved / applied / skipped.

**What not to do, in order of how tempting it is:**

- **Do not re-run Steps 1 through 4.** They are in `$WINNOW/review-pipeline.md`, and opening that file is the whole failure — the review will look like the obvious first move. It is not. It burns the context the plan exists to save and re-opens decisions the user already made.
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

Worked examples of each of these live in `$WINNOW/references/core-patterns.md`, which you read before Step 3 — the restated comment, the directive comment that looks like chaff and is not, and TIGHTEN-versus-DELETE on a docstring.
