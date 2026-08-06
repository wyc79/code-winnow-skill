# code-winnow

Agent skill that strips generated-code chaff from an uncommitted change or a branch — keep the grain, blow off the slop.

Generated code is rarely wrong; it is bloated, over-defensive, and stylistically foreign to the repo it landed in. Linters catch rule violations. This skill covers the judgment gap: restated comments, unused bindings, mock-only tests, speculative abstraction, documentation the change quietly made false, and the rest of the usual AI residue.

It also asks two questions about the change that a green test suite cannot answer: **how does this break silently**, and **what did it make slow**. Both are gated hard — the fragility pass reports only what the diff did and only where no test could catch it, and the performance pass reports nothing it cannot attach a call frequency to.

**This is a diff review, not a repo audit.** It operates only on lines the current change added or modified. It does not hunt bugs and it is **not a security review** — use a dedicated tool for that. Two security-shaped things it does report: a protection *this change removed*, quoted from the diff's own `-` side, and a committed credential. The credential pass is split by what each half is good at — the scanner matches self-identifying vendor formats (`AKIA…`, `ghp_…`, `sk_live_…`, PEM blocks), and the silent-failure agent reads the added lines for a named credential assigned a literal, which is the half no pattern reaches: `DB_PASSWORD`, `db_password`, `"db_password":` in a config file. Neither is ever auto-fixed — you cannot un-leak a key by deleting the line.

## When to use

- "Winnow this", "de-slop", "clean this up before I commit"
- "Does this look AI-written?", "make this idiomatic", "cut the slop"
- About to open a PR on agent-written code
- A large generated change just landed
- Only one feature in a branch — "winnow the dash cooldown work" scopes the review to that feature's hunks and nothing else

**Not for:** general code review, bug hunts, or security audits.

## Install

Copy or symlink the `code-winnow/` directory into your agent skills path:

| Runtime | Typical path |
|---|---|
| Claude Code | `~/.claude/skills/code-winnow/` |
| Cursor | `~/.cursor/skills/code-winnow/` or `.cursor/skills/code-winnow/` (project) |
| Cross-runtime | `~/.agents/skills/code-winnow/` |

Or install from this repo with your preferred skills CLI, e.g.:

```bash
npx skills add wyc79/code-winnow-skill
```

Then invoke it by name (`code-winnow`, `winnow`, `de-slop`) or by asking the agent to clean up generated / AI-looking changes before commit.

## Requirements

- **Python 3.9+** (stdlib only — no pip install for the scanner). 3.9 is the floor because duplicate-test detection for Python uses `ast.unparse`; on 3.8 that rule silently finds nothing, which looks exactly like a clean suite.
- **git**
- Optional companion skills improve the run (parallel judgment, cold review, edit discipline). Missing ones degrade gracefully; see [`code-winnow/references/portability.md`](code-winnow/references/portability.md).

## How it works

1. **Exclude workspace** — `.code-winnow/` goes in the local git exclude so reports never dirty the diff under review.
2. **Check capabilities** — detect which companion skills exist here, look for equivalents already installed under other names, and say once what is missing before the review starts rather than degrading silently.
3. **Scan** — `scripts/scan.py` resolves scope (staged ∪ unstaged ∪ untracked, or branch vs base) and emits regex/AST **candidates**, not verdicts.
4. **Scope, if a feature was named** — a separate agent draws the boundary from your own words before any review starts, and you confirm it. Deciding what is *eligible* to be judged matters more than any verdict, and the agent that wrote the code should not be the one drawing that line.
5. **Judge** — five parallel agents with no shared context and no design rationale: chaff, comments + docstrings, documentation + file headers, performance, and silent failure. Docstrings get their own pass, since generated diffs carry one per function whether or not there is anything to say. Docs and performance are conditional — they run only when the diff gives them something to look at.
6. **Reconcile** — a conflict check merges their outputs across ten classes. A comment claiming intent overrides a finding only when it names a *checkable* why; a bare "reserved for future use" merges with the code into one decision instead of excusing it. And the fragility pass can **veto a deletion**: when it names the mechanism that makes a line load-bearing, the proposed removal never reaches the fix plan.
7. **Report** — human-readable + JSON under `.code-winnow/round-NN/`, reconciled against the most recent prior round *of the same scope* and against declined findings. Performance notes go to a separate document and are never applied. The root index is regenerated so one clickable file points at everything the round produced.
8. **Apply only on approval** — writes a fix plan, then applies it in a cleared context, a fix subagent, or in place. Copies every file it will edit to a restore point first (untracked files have no git undo) and refuses to edit if that copy is incomplete. Unattended runs stop at the plan, mark it `UNAPPROVED`, and never edit.
9. **Verify** — re-run the **whole** test suite and compare it against the baseline captured before the first edit, not against green: a failure absent from the baseline is yours, a pre-existing one is not yours to chase, and a green run with *fewer tests* is a regression. Then re-scan with reconciliation, run a deletion-safety pass over the removed lines only, and report approved / applied / skipped.

Every fix that removes code records an `evidence:` line — the lookups that established the deletion was safe. An item marked `unverified` is reported, not applied. That is the correctness gate: the failures that matter here (a deleted GC root, a `# noqa`, a JSDoc type, a serialized field read by a scene) break at runtime or in CI, never in a unit test.

## Languages

**Six are claimed, in two tiers.**

**Full tier — Python, C# / Unity, C++ / UE5.** A reference file each, structure-aware scanner rules, and directive and docstring tables checked against each toolchain.

**Web tier — JavaScript/TypeScript, HTML, CSS**, sharing `web.md`. The judgment standard is as thorough; the scanner rules under it are **regex-level only**, because a stdlib-Python scanner has no JavaScript parser. So nothing deterministic here finds an unused binding, a dead function or a near-duplicate component in a `.ts` file — that half is the judgment pass's, and a quiet scan over a TypeScript diff must not be read as coverage of it.

Any other language gets the universal pass — comments, typography, invisible characters, generic test smells — plus ordinary judgment, under one rule that overrides the rest: **an unrecognised line is kept, not cut.** A directive list missing your ecosystem's suppression is indistinguishable from a complete one at the moment of deletion, and the shipped list does not know `// ktlint-disable` or `// swiftlint:disable`. Keeping a redundant comment in a Kotlin file costs a line; deleting a suppression costs a broken build no test catches.

Test-chaff detection is broader, because the shapes are: pytest/unittest, NUnit/xUnit/MSTest, JUnit, GoogleTest, Go, Jest/Vitest/Mocha, Rust, RSpec, and XCTest.

## Layout

```
code-winnow/
  SKILL.md                 # The spine every run reads: scope rules, Never touch,
                           #   Step 0, and the routing table to the two files below
  review-pipeline.md       # Steps 1 – 4b — review, conflict check, report, fix plan.
                           #   A run invoked to apply a plan never opens this file.
  apply-and-verify.md      # Steps 5 – 6 — backup, edits, deletion-safety, reconcile.
                           #   Both entry paths end here.
  scripts/scan.py          # Deterministic candidate scanner
  scripts/backup.py        # Step 5a: the restore point, and six refusals
  references/
    core-patterns.md       # Universal judgment standard — read every run
    comment-evidence.md    # The X1 grading rule — orchestrator only
    docstrings.md          # Docstring concision — Agent B, and C for truth
    agent-prompts.md       # The six dispatch prompts (S, A, B, C, D, E)
    report-format.md       # Report, fix plan, notes and declined-file shapes
    fragility.md           # Agent E's gate
    performance.md         # Agent D's gate
    tests.md               # Test-chaff judgment standard
    portability.md         # Companion-skill detection and degraded paths
    python.md, csharp-unity.md, cpp-ue5.md    # The full-tier claimed languages
    web.md                 # JS/TS, HTML and CSS — one file, because a .vue is all three
  scaffold/                # Copied into the workspace: root at Step 0, round at Step 2
    root/README.md         #   the index template — ROUND is its only path placeholder
    round/README.md        #   what is in a round folder, and the filename rule
    round/fixplan.md       #   the plan template; its Status is a placeholder, so an
                           #   unfilled copy is refused by backup.py
    round/notes.md         #   Agent D's template
  tests/                   # Scanner tests, SKILL.md workflow harness, mutation check
DESIGN.md                  # Why the mechanical parts are written as they are.
                           #   Not shipped to agents; read it before editing a snippet.
```

### The workspace it writes

```
.code-winnow/
  README.md          the index — one clickable file, regenerated each round
  env.sh  declined.json  perf-declined.md  substitutions.md
  utils/             helper scripts a run wrote, shared across rounds
  round-01/
  round-02/          meta.json, report.md, fixplan.md, notes.md, agent-S..E.md,
                     scan*.json, input.diff, tests-*, pre-fix/, scratch/
```

**Every round is self-contained and nothing is ever moved between them** — rotation is
`mkdir`. Filenames inside a round are short and identical every round, so what the round
compared to what lives in `meta.json` and in a three-line block at the top of every
markdown file, never in a filename. Anything a run generates that the round README does
not list goes in `scratch/`.

There are no symlinks or aliases at the root, deliberately: `ln -s` on Git Bash silently
produces a *copy*, and a hard-linked `fixplan.md` re-points every rotation, so a resume
line copied yesterday would apply today's plan. `DESIGN.md` has the measurements.

The workflow is the three documents at the top of that tree, and the split is by **entry
path**, not by step. `SKILL.md` holds what binds every run — the scope rules, the
unattended answers, `Never touch`, Step 0 — and routes to one of two files. A full review
reads `review-pipeline.md` and then `apply-and-verify.md`; a run invoked as
`code-winnow: apply <plan>.fixplan.md` reads `apply-and-verify.md` and never opens the
review pipeline at all. That second path is the reason for the boundary: it already
skips Steps 1 – 4b, and a single file made it read them first to be told to.

The prompts, templates and the backup script live beside those three so an orchestrator
that only needs to *dispatch* a prompt does not have to read it, and so the backup is a
testable script rather than a heredoc an agent retypes. Every one of those files is
still under test: `test_workflow.py` extracts and runs the shell blocks from all three
documents, checks that each step is defined in exactly one of them, and checks that the
routers still name the files they route to; `check_mutations.py` mutates the script, the
templates and the documents alike.

## Scanner (standalone)

From anywhere inside a git repo:

```bash
python3 path/to/code-winnow/scripts/scan.py
python3 path/to/code-winnow/scripts/scan.py --json
python3 path/to/code-winnow/scripts/scan.py --scope branch --base main
python3 path/to/code-winnow/scripts/scan.py --paths a.py b.cs
```

Run `python3 scripts/scan.py --help` for the full flag set. The scanner itself **writes no files** — it prints to stdout. Reports, fix plans and backups land in `.code-winnow/` at the repo root because the skill's steps redirect them there; Step 0 creates that directory and git-excludes it.

## What it never touches

- Validation at trust boundaries (user input, network, deserialization, plugins)
- Comments that explain *why* (workarounds, engine quirks, ticket links)
- Public / serialized API surface (`UPROPERTY`, `[SerializeField]`, exports)
- Test scaffolding — unless the "test" asserts nothing, asserts a tautology, or only checks mocks. Those are false coverage and get fixed, not deleted (P1 or P2 depending on language and shape)
- File headers matching the repo's convention. Unifying divergent headers needs an explicit yes, and never touches files outside the diff
- Any line the fragility pass names as load-bearing — a GC root, a directive comment, a type carrier, a registration anchor, a side-effect import. That veto beats a proposed deletion and the removal never reaches the fix plan
- Anything outside the diff, or outside the named feature. The sole exception is a doc line the change made false, reported with both lines cited

## License

See the repository license file if present; otherwise treat usage as governed by your clone / fork terms.
