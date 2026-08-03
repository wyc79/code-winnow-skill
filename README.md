# code-winnow

Agent skill that strips generated-code chaff from an uncommitted change or a branch — keep the grain, blow off the slop.

Generated code is rarely wrong; it is bloated, over-defensive, and stylistically foreign to the repo it landed in. Linters catch rule violations. This skill covers the judgment gap: restated comments, unused bindings, mock-only tests, speculative abstraction, documentation the change quietly made false, and the rest of the usual AI residue.

**This is a diff review, not a repo audit.** It operates only on lines the current change added or modified. It does not hunt bugs or run a security review.

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
5. **Judge** — three parallel agents with no shared context and no design rationale: chaff, comments + docstrings, and documentation + file headers. Docstrings get their own pass, since generated diffs carry one per function whether or not there is anything to say. The third agent runs only when the diff touches docs, adds files, or changes a public surface.
6. **Reconcile** — a conflict check merges their outputs. A comment claiming intent overrides a finding only when it names a *checkable* why; a bare "reserved for future use" merges with the code into one decision instead of excusing it.
7. **Report** — human-readable + JSON under `.code-winnow/`, reconciled against prior runs and declined findings.
8. **Apply only on approval** — writes a fix plan, then applies it in a cleared context, a fix subagent, or in place. Copies every file it will edit to a restore point first (untracked files have no git undo) and refuses to edit if that copy is incomplete. Unattended runs stop at the plan, mark it `UNAPPROVED`, and never edit.
9. **Verify** — re-run the **whole** test suite and compare it against the baseline captured before the first edit, not against green: a failure absent from the baseline is yours, a pre-existing one is not yours to chase, and a green run with *fewer tests* is a regression. Then re-scan with reconciliation, run a deletion-safety pass over the removed lines only, and report approved / applied / skipped.

Every fix that removes code records an `evidence:` line — the lookups that established the deletion was safe. An item marked `unverified` is reported, not applied. That is the correctness gate: the failures that matter here (a deleted GC root, a `# noqa`, a JSDoc type, a serialized field read by a scene) break at runtime or in CI, never in a unit test.

## Languages

**Three are claimed: Python, C# / Unity, and C++ / UE5.** Each has a reference file, dedicated scanner rules, and directive and docstring tables checked against its toolchain.

Any other language gets the universal pass — comments, typography, invisible characters, generic test smells — plus ordinary judgment, under one rule that overrides the rest: **an unrecognised line is kept, not cut.** A directive list missing your ecosystem's suppression is indistinguishable from a complete one at the moment of deletion, and the shipped list does not know `// ktlint-disable` or `// swiftlint:disable`. Keeping a redundant comment in a Kotlin file costs a line; deleting a suppression costs a broken build no test catches.

Test-chaff detection is broader, because the shapes are: pytest/unittest, NUnit/xUnit/MSTest, JUnit, GoogleTest, Go, Jest/Vitest/Mocha, Rust, RSpec, and XCTest.

## Layout

```
code-winnow/
  SKILL.md                 # Agent instructions
  scripts/scan.py          # Deterministic candidate scanner
  references/              # Judgment standards (patterns, languages, tests, portability)
  tests/                   # Scanner tests, SKILL.md workflow harness, mutation check
```

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
- Anything outside the diff, or outside the named feature. The sole exception is a doc line the change made false, reported with both lines cited

## License

See the repository license file if present; otherwise treat usage as governed by your clone / fork terms.
