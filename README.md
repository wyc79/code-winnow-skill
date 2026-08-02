# code-winnow

Agent skill that strips generated-code chaff from an uncommitted change or a branch — keep the grain, blow off the slop.

Generated code is rarely wrong; it is bloated, over-defensive, and stylistically foreign to the repo it landed in. Linters catch rule violations. This skill covers the judgment gap: restated comments, unused bindings, mock-only tests, speculative abstraction, and the rest of the usual AI residue.

**This is a diff review, not a repo audit.** It operates only on lines the current change added or modified. It does not hunt bugs or run a security review.

## When to use

- "Winnow this", "de-slop", "clean this up before I commit"
- "Does this look AI-written?", "make this idiomatic", "cut the slop"
- About to open a PR on agent-written code
- A large generated change just landed

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
npx skills add <owner>/code-winnow-skill
```

Then invoke it by name (`code-winnow`, `winnow`, `de-slop`) or by asking the agent to clean up generated / AI-looking changes before commit.

## Requirements

- **Python 3.8+** (stdlib only — no pip install for the scanner)
- **git**
- Optional companion skills improve the run (parallel judgment, cold review, edit discipline). Missing ones degrade gracefully; see [`code-winnow/references/portability.md`](code-winnow/references/portability.md).

## How it works

1. **Exclude workspace** — `.code-winnow/` goes in the local git exclude so reports never dirty the diff under review.
2. **Scan** — `scripts/scan.py` resolves scope (staged ∪ unstaged ∪ untracked, or branch vs base) and emits regex/AST **candidates**, not verdicts.
3. **Judge** — separate agents confirm or dismiss candidates and review comments, using language-specific references.
4. **Report** — human-readable + JSON under `.code-winnow/`, reconciled against prior runs and declined findings.
5. **Apply only on approval** — copies touched files to a restore point first (untracked files have no git undo). Unattended runs stop at the report and never edit.
6. **Verify** — re-scan with reconciliation, run the project tests when a suite exists.

Tuned for **C# / Unity**, **C++ / UE5**, and **Python**; language-agnostic elsewhere. Test-chaff detection also covers pytest/unittest, NUnit/xUnit/MSTest, JUnit, GoogleTest, Go, Jest/Vitest/Mocha, Rust, RSpec, and XCTest.

## Layout

```
code-winnow/
  SKILL.md                 # Agent instructions
  scripts/scan.py          # Deterministic candidate scanner
  references/              # Judgment standards (patterns, languages, tests, portability)
  tests/                   # Scanner tests
```

## Scanner (standalone)

From anywhere inside a git repo:

```bash
python3 path/to/code-winnow/scripts/scan.py
python3 path/to/code-winnow/scripts/scan.py --json
python3 path/to/code-winnow/scripts/scan.py --scope branch --base main
python3 path/to/code-winnow/scripts/scan.py --paths a.py b.cs
```

Run `python3 scripts/scan.py --help` for the full flag set. Reports and backups land in `.code-winnow/` at the repo root (git-excluded by the skill's Step 0).

## What it never touches

- Validation at trust boundaries (user input, network, deserialization, plugins)
- Comments that explain *why* (workarounds, engine quirks, ticket links)
- Public / serialized API surface (`UPROPERTY`, `[SerializeField]`, exports)
- Test scaffolding — unless the "test" asserts nothing, asserts a tautology, or only checks mocks (those are P1)

## License

See the repository license file if present; otherwise treat usage as governed by your clone / fork terms.
