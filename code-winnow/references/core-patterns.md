# Core patterns

Language-agnostic. Load this every run, then load the language-specific file.

Each entry: the tell, why it costs something, and the test for whether it is actually slop in this case.

**Two standards live next door rather than here, because this file is loaded by every judgment agent and those two are not.** `comment-evidence.md` grades a comment that claims the code below it is intentional — that is the orchestrator's Step 3.5, and an agent's whole job there is to tag the claim, not settle it. `docstrings.md` is Agent B's pass, and Agent C's for the truth branch. Both are summarized below at the depth their other readers need; neither summary is the standard.

## What this skill actually claims

**Verified coverage is six languages in two tiers, and what separates the tiers is what the scanner can parse.**

**Full tier — Python, Unity C#, Unreal C++.** A reference file each, scanner rules that read structure (Python through `ast`; C# and C++ through range-aware matching), and tables here checked against each toolchain.

**Web tier — JavaScript/TypeScript, HTML, CSS.** One reference file, `web.md`, and scanner rules that are **regex-level only**. There is no JavaScript parser here and there will not be one: the scanner is stdlib Python, and `ast` reads Python. The judgment standard in `web.md` is as thorough as the other three files; the deterministic layer beneath it is not. **In practice that means the scanner will not tell you a `.ts` binding is unused, that two components are near-duplicates, or that a function is dead** — a silent scan over a TypeScript diff did not look for those, and a report must not present it as though it did. That work is Agent A's, by reading.

Those six are the languages to trust this skill in, with that caveat attached to the last three.

Everything else gets the universal pass — comments, typography, invisible characters, generic test smells — plus these tables **on a best-effort basis**, which is a weaker claim than it appears. An incomplete directive list is indistinguishable from a complete one at the moment you are about to delete a line that is not on it, and the list below is demonstrably incomplete: `// ktlint-disable` and `// swiftlint:disable` are real suppressions in real repos, and neither the table nor the scanner's directive pattern recognises either.

**So outside those six languages, an unrecognised comment defaults to KEEP.** Not being able to say what a comment is *for*, in a language this skill does not claim, is not evidence that it is chaff — it is evidence that you are the wrong reader. Report it as a confirm-question naming the language, or say nothing at all. Keeping a redundant comment in a Kotlin file costs one line. Deleting `// ktlint-disable` because it was not in a table costs a broken build that no test catches, in a language nobody here can review the fix for.

This is a floor, not a ceiling: a clear-cut restated comment in Go is still a clear-cut restated comment. The rule bites where confidence is low, which outside the claimed languages is more often than it feels.

**Run the tests — they need the repo, and that is allowed.** "Trace every caller", "grep for the function's core operation", "check scenes and assets": these are searches for evidence, and they are the only thing standing between a confident deletion and a broken build. They do not conflict with the scope rules, which govern what becomes a *finding*, not what you may look at. Nothing you see outside the diff is reportable, however bad it is. If a lookup is impossible in this runtime, say "unverified", **keep the finding at its original severity**, move it to the report's "Author claims - confirm" section, and do not propose the deletion. Do not demote it: a P3 labelled "Cosmetic" is cut when the list runs long, so demoting on an unverifiable claim lets eleven characters of `(see #4821)` retire a real P1.

## Comments

**Restating the code.** `// increment the counter` above `counter++`. Costs a line, adds nothing, and trains readers to skip comments — which means they skip the one that mattered.
*Test:* delete it mentally. Did you lose information the code doesn't carry? If no, cut it.

**Section-header decoration.** `// ===== HELPERS =====` in a 40-line file. Structure theatre.
*Test:* does the file have enough sections that navigation is hard? Under ~200 lines, no.

**Hedged narration.** "This should handle most cases", "we may want to revisit this". Uncertainty with no owner and no ticket. Either it's a known limitation worth documenting concretely, or it's noise.

**Changelog comments.** `// Updated to use new API`, `// Added in v2.3` — that is what version control is for.
*Test:* does the version or date explain why the code below is shaped that way, or only record when someone touched it? `// Workaround for UE 5.4 normalize bug` is the first and stays. A bare "updated in v2.3" is the second and goes.

## Directive comments — never touch, in any language

**A comment that a tool reads is not prose.** It has no *why* to carry, it never contains "because", it restates nothing, and by the plain reading of every rule above it is pure noise. It is also load-bearing, and deleting it breaks the build or silently changes behaviour.

This is the largest single way this skill can do damage, because the rules that govern comments are written for prose and these are code wearing a comment's syntax.

| Directive | Deleting it |
|---|---|
| `# noqa: F401`, `# type: ignore[...]`, `# pylint: disable=` | lint or type CI fails — and under `warn_unused_ignores` an outdated one fails too, so both verdicts can break it |
| `// @ts-expect-error`, `// eslint-disable-next-line` | build fails; an *unnecessary* `@ts-expect-error` is itself an error (TS2578) |
| `//go:embed`, `//go:build`, `//go:generate` | file compiles on every platform, or the embedded FS is silently empty |
| `# frozen_string_literal: true` | silent change to string mutability |
| `// clang-format off`, `// IWYU pragma: keep`, `// NOLINT` | reformat churn, or a needed include stripped |
| `# fmt: off`, `# isort: skip`, `# pragma: no cover` | formatting or coverage gates flip |
| `<!-- prettier-ignore -->`, `# yamllint disable` | formatter rewrites content it was told not to |
| `# -*- coding: utf-8 -*-`, `#!/usr/bin/env …` | decoding or execution breaks |
| `// Deprecated:` in Go, `@deprecated` in JSDoc | machine-read; tooling stops warning consumers |
| **`// @ts-check`**, `// @ts-nocheck`, `// @flow` | **this is the pragma that makes JSDoc `{type}` load-bearing** — remove it and the file's types stop being checked, silently |
| `// <auto-generated/>` (C#), `// Code generated … DO NOT EDIT.` (Go) | analyzers, StyleCop and nullable warnings all key off these; removing one turns on hundreds of errors, and CI regeneration checks assert their presence |
| `//nolint:…`, `// NOSONAR`, `// CHECKSTYLE:OFF` | `nolintlint` also errors on an *unused* nolint, so both verdicts break CI |
| `# typed: strict` (Sorbet) | falls back to `typed: false`; type checking vanishes with **no error at all** |
| `# shellcheck disable=`, `# hadolint ignore=`, `# checkov:skip=`, `# tfsec:ignore:`, `# nosec` | the suppression's linter fails the build |
| `# syntax=docker/dockerfile:1` | must be line 1; changes the BuildKit frontend and breaks `RUN --mount` |
| `/*#__PURE__*/`, `/* webpackChunkName: "x" */` | silent bundle and tree-shaking changes, zero build error |
| `// clang-format on`, `// NOLINTEND`, `// IWYU pragma: export` | the *closing* half — delete it and the suppressed region silently extends |
| `# mypy: ignore-errors`, `# ruff: noqa` (file-level), `x = []  # type: List[int]` | file-wide suppression, or the only type annotation present |
| Block forms: `/* eslint-disable */`, `/* global */`, `/* eslint-env */` | only the `-next-line` forms look like comments; these do not |

*Test:* would any tool — compiler, linter, formatter, type checker, build system, coverage runner — behave differently if this line vanished? Then it is not a comment for the purposes of this skill. **Never DELETE, never TIGHTEN, never reflow, never move.**

**The table is a starting set, not a whitelist, and the test above outranks it.** Absence from these rows is not permission. Every ecosystem invents its own — `// ktlint-disable`, `// swiftlint:disable`, `// istanbul ignore next`, `// codecov ignore`, `# noinspection` — and new ones ship faster than any list is maintained. A comment whose shape is `<marker>:<verb>` or `<tool>-<disable|ignore|off>` is a directive until proven otherwise, whether or not it appears above.

Two adjacent traps. A directive attached to a line you are deleting goes with it — but a directive at file or block scope does not, so check what it governs before assuming it is orphaned. And a suppression whose underlying problem your change fixes is genuinely stale — that is a real finding, at P3, phrased as "this suppression looks unnecessary now, confirm", never as a silent deletion.

## Comments as evidence

Separate question from the one above. There, a comment is the thing being judged. Here it is *evidence about the code below it* — the author telling you a field with no reader is read somewhere you cannot see, or a duplicate test pins a specific bug. Authority is graded, never granted by the presence of a claim: the question is never "does a comment claim intent", it is **"does the claim name something you can go and check"**.

- **A checkable why** points at something outside itself — a ticket or URL, a named consumer or mechanism ("the serializer reads this", "set from the Inspector"), a concrete external constraint, an invariant the code depends on. It earns a *lookup*, not a pass.
- **A bare claim** asserts intent and stops — "reserved for future use", "kept for later", "intentional" with no reason. It earns no lookup, because there is nothing to look up.

**If you are a judgment agent, that is all you need**: do not dismiss your finding on a comment's say-so and do not report the comment — tag it `comment-claim: "<verbatim>"` and hand it up.

**The full standard is `comment-evidence.md`, next to this file** — the four lookup outcomes, why "no evidence" is not disproof, why an unverifiable claim keeps its severity, and the one exception where the comment *is* the mechanism. The orchestrator running Step 3.5 reads it; nobody else needs to.

## Error handling

**Log-and-rethrow.** A catch block that logs and re-raises, when a caller up the stack also logs. Produces duplicate stack traces and hides the real handler.
*Test:* does this frame add context the caller lacks? If not, delete the catch.

**Swallowed exceptions.** Catch that logs and continues, leaving the program in an undefined state. **P1** — this converts a crash into a silent corruption, which is strictly worse.

**Over-broad catches.** Catching the base exception type where one specific failure is expected. Masks bugs that should surface loudly in development.

## Defensive checks

**Null checks in trusted paths.** Guards on values that a constructor, a factory, or the type system already guarantees. Each one implies "this can be null", which is a lie the next reader has to disprove.
*Test:* trace every caller. All internal and all guaranteed non-null? Delete.
*Exception:* trust boundaries — user input, network, deserialization, plugin APIs, file parsing. Never delete these.

**Redundant existence checks.** Checking a key exists, then checking the value isn't null, then defaulting anyway. Pick one.

**Belt-and-braces validation.** The same argument validated in the caller and the callee. Keep it at the boundary; drop it in the interior.

## Speculative structure

**Interface with one implementation.** Added "for testability" or "in case we swap backends". Until the second implementation exists, it is indirection you pay for on every read.
*Test:* does a second implementation exist, or is one scheduled this quarter? If neither, inline it.

**Config knobs nothing sets.** Parameters, flags, and options where every call site uses the default.

**`**kwargs` / params-object passthrough** that no caller populates.

**Backward-compat shims for unreleased code.** Deprecation paths for an API that has never shipped.

**Premature generalization.** A function taking a strategy callback with one strategy. A generic `<T>` used at exactly one type.

## Dead weight

- Placeholder `TODO` / `FIXME` with no ticket reference and no owner (test-file TODOs are normal — leave them)
- `if __name__ == "__main__"` demo blocks, `main()` example harnesses, sample data left in production files
- Commented-out code
- Unreferenced private helpers, variables assigned and never read
- Unused imports, `using` directives and `#include`s — the section below, because "unused" is a claim there rather than an observation
- Entry/exit logging (`log.debug("entering foo")`) left from an agent's debugging pass

## Unused imports, `using` directives and `#include`s

The purest form of an agent's iteration debris: it reached for a library, changed approach, and left the line at the top of the file. Every claimed language has a tool that finds these in a second, so the detection is free. **What this skill adds is knowing when the tool is wrong** — and it is wrong in different ways in each language, which is why the ladder below is not uniform.

**"Unused" is a claim, not an observation.** An import is used when *something* consumes it, and in every language here at least one consumer is invisible to a search for the name: an import evaluated for its side effects, a `using` that decides which of two `Debug` classes a bare name resolves to, an `#include` another translation unit was relying on transitively. The name not appearing below is where this check starts, never where it ends.

| | Find it with | Propose the removal when | Severity |
|---|---|---|---|
| **Python** | `ruff check --select F401`, `pyflakes` | The tool flags it and no trap in `python.md` applies | P3 |
| **C#** | `dotnet format analyzers`, IDE0005 | Same, and it is not an alias and not reached under an inactive `#if` — `csharp-unity.md` | P3 |
| **C++** | `include-what-you-use`, `clang-tidy misc-include-cleaner` | **Only with that tool's output, or a whole-file symbol trace, named in `evidence:`** — `cpp-ue5.md` | P3 |
| **JS/TS** | ESLint `no-unused-vars`, `tsc --noUnusedLocals`, `knip` | The tool flags it and no trap in `web.md` applies. **A clean run says nothing about `import './x'`** — no binding, so no unused variable | P3 |

**Run the tool if the repo has one.** This is one of the few places in this skill where a deterministic answer is available for the asking, and eyeballing an import list with `ruff` sitting in the repo's dev dependencies is guessing on purpose. Where no tool is available, write `unverified` in `evidence:`, keep the finding at P3, and propose nothing — the same rule as every other unverifiable claim.

**C++ carries a bar the other three do not, and the reason is the signal rather than the difficulty.** Remove a `using` that C# needs and the build fails here, now, with a line number. Remove an `#include` that C++ needs and the file very often still compiles here — another header pulled the symbol in transitively, or a unity build put a neighbour's includes in the same translation unit — and the break lands on a different platform, a different compiler, or a colleague's incremental build. A stale include costs build time. A wrong removal costs someone else a red build they cannot reproduce from the diff. Those are not the same wager.

**A directive on the line settles it.** `# noqa: F401`, `// IWYU pragma: keep`, `# pylint: disable=unused-import` — these are the author saying "I know, it is deliberate", they are in the never-touch table above, and no tool output outranks them.

**Scope binds here exactly as it does everywhere.** The common case is an import the diff itself *added* and never used, and that line is in the diff. An import the diff made dead by deleting its last call site is on a line the change did not touch, so it is a courtesy note under Pre-existing — cite the diff line that removed the last use — and not a fix. Never batch: deleting eleven imports from a file whose change was two lines is formatting churn wearing a cleanup's clothes.

## Naming

**Generic names:** `data`, `result`, `temp`, `item`, `value`, `obj`, `info`, `handler`, `manager`, `processData`, `handleThing`.
*Test:* could this name apply to half the variables in the file? Then it names nothing.

**Type-suffixed names:** `userList`, `configDict`, `nameString` — the type is already in the signature.

**Verbose ceremony:** `calculateTheTotalAmountOfItems` where `total` reads better.

## Tests

**Mock theatre.** **P1.** A test that asserts a mock was called with arguments the test itself just supplied. It passes when the implementation is deleted. It is negative value: it costs maintenance and provides false confidence.
*Test:* would this test fail if the function body were replaced with `pass`? If not, it tests nothing.

**Tautological assertions.** `assertEqual(x, x)`, asserting on a constant defined two lines up.

**Test names describing mechanics not behavior.** `test_function_1` / `test_it_works`.

**Overlapping near-duplicate tests** generated in a batch, differing by one literal, where a table-driven test would say it once.

## Diff hygiene

**Formatting churn.** Reindentation, quote-style changes, import reordering on lines the change did not touch. This is the single most reviewer-hostile thing in a generated diff — it buries three real lines under two hundred cosmetic ones.
*Fix:* revert those hunks entirely.

**Invisible characters.** **P1.** Non-breaking spaces, zero-width spaces and joiners, word joiners, bidi overrides. You cannot see them in review at all, they break greps and diffs, and they occasionally break parsers. A byte-order mark at the very start of a file is not one of these — Visual Studio and MSBuild write it into every `.cs` file they touch. The scanner demotes inside a test or prose file, where these are usually fixtures: a non-breaking space or soft hyphen drops to P3, and every other invisible character in a test file to P2. **In real source they are all P1**, bidi included — that is the Trojan Source class, and a reviewer reads the rendered form.

**Typographic characters — em dashes, en dashes, smart quotes — in code.** **P3, not P1.** They are visible, and they only cost you a grep that does not match. Delete them in identifiers and in code you expect to search. **Leave them in comments, docstrings, and user-facing copy** — localized `FText`/`LocalizedString` strings are supposed to use real typography, and "fix" that and you have degraded the product to satisfy a linter. The scanner agrees: P3, and it exempts whole-line comments, Python triple-quoted regions and prose files. It does **not** exempt a comment sharing a line with code, nor string literals - so check trailing comments and localized strings yourself before accepting one.

**The same characters in a documentation file are a different question, and it is not this one.** In a README an em dash costs no grep and breaks nothing. What it does is read as machine-written, and that is the thing this skill was pointed at. So documentation prose gets its own check on its own terms: **Agent C owns it, it is measured against the repo's own docs rather than against a rule, and it stays at P3.** A repo whose documentation is already full of em dashes is not producing findings when a new doc has them — it is producing a house style, and C reports the count and moves on. The scanner is deliberately not involved: the comparison this needs is a sample of the base branch, and the scanner does not read the base branch. C's fourth direction in `agent-prompts.md` is the standard; nobody else reports on dashes in prose, and the rule above still holds everywhere that is not a `.md`, `.rst`, `.txt` or `.adoc` file.

**Absolute paths into a developer home directory** (`/Users/name/…`, `C:\Users\name\…`) committed in config or test fixtures. **P1.** A `/home/name/…` path is a P2 — half the containers alive use one as a deployment path. Either one drops a step inside a path-handling test or a documentation file, where it is data or an example rather than a leak.

**Committed credentials.** **P1.** Two halves with different confidence, and they behave differently:

- **A recognised vendor format — the scanner's half.** An AWS key id, a `ghp_`/`github_pat_`/`glpat-` token, a Slack `xox…`, a Stripe `sk_live_`, a Google `AIza…`, an npm or SendGrid token, or a `-----BEGIN … PRIVATE KEY-----` block. These are self-identifying by prefix, so the match is on a *format* rather than a guess. **P1 everywhere, including test and prose files** — the one rule here that does not demote in a fixture, because a live credential is not data and a test fixture is where keys most often leak.

  One exemption, and it is deliberately narrow: a token whose value **ends** in `example` or `sample`. Vendors publish well-formed keys in their own documentation — AWS's is `AKIAIOSFODNN7EXAMPLE` — and those get copied into config samples everywhere. It is anchored at the end because a token is a fixed-length random string: matching those letters *anywhere* in the body silently drops a live key whose body happens to contain them, which is a false negative on the one rule where that is the worst outcome available.

- **A credential-named variable assigned a literal — a judgment call, and Agent E's half.** `password = "…"`, `DB_PASSWORD = "…"`, `"db_password": "…"` in a config file. The scanner has a rule for the narrowest spelling of this, and you should know its exact reach before trusting a silent report. It matches a **fixed keyword list** — `pass` / `password` / `passwd`, `secret`, `api_key` / `apikey`, `auth_token`, `access_token`, `client_secret`, `private_key`, `credential(s)`, `connection_string`, `bearer` — on a word boundary before a bare `:`, `=`, `:=` or `=>`. Two consequences, and both are wider than "it misses prefixed names":

  - **Prefixes and quotes block it.** `DB_PASSWORD`, `db_password`, `smtp_password:`, and every `"db_password": "…"` in JSON or YAML are missed, because `_` is a word character and the quote blocks the separator.
  - **A credential named with a word outside the list is missed entirely**, prefix or not. Verified misses: `token` on its own, `api_secret`, `access_key`, `passphrase`, `pwd`.

  Those are the spellings a committed password actually has. A wider pattern is not the answer — the names are unbounded and the noise would be — so the judgment half belongs to a reader. Agent E's brief in `agent-prompts.md` carries it, at P1, never demoted in a fixture, and never fix-plan eligible.

  Either half skips anything that looks like a placeholder: template syntax (`${…}`, `{{…}}`, `<your-key>`), a value of one or two repeated characters, the usual filler words, and a value read from the environment or a secrets manager rather than written down.

**There is deliberately no entropy heuristic.** Hashes, UUIDs, base64 blobs and minified bundles all look random, so a "high-entropy string" rule fires constantly on files holding no secret at all. This skill's standing position is that a noisy rule is worse than a missing one — the reader learns to skim, and what they skim past is the P1 three sections down. Structured formats only.

**Never propose deleting a committed secret as if that fixed it.** The line is already in the object store, and in every clone and every CI cache that fetched it. The finding says *rotate it*; removing the line is cleanup after the rotation, not a substitute for it, and a report that proposes the deletion alone hands the user a false all-clear. This is why a secret is reported and never enters the fix plan.

**Internal host names.** **P2**, P3 in a test file. Narrow on purpose: only a UNC path (`\\HOST\share`), which unambiguously names an internal machine. Hostnames in general are unmatchable without flagging every domain in every URL, and the coverage is not worth that noise.

**Duplicated helper.** A utility written fresh that already exists in the repo.
*Test:* grep for the function's core operation before accepting any new helper.

## Documentation

- README sections written in the promotional register — "comprehensive", "robust", "seamlessly", "powerful"
- Doc claims about behavior the code doesn't have

## Docstrings

**Expect volume here.** Generators emit one per function whether or not there is anything to say, and they are graded on looking thorough rather than on being read. A file can gain three hundred lines of docstring and no information. This is the highest-yield place in a generated diff and the one reviewers skim hardest, because rejecting a docstring feels like rejecting diligence.

**The verdict is usually TIGHTEN, not DELETE.** Many repos require a docstring on every public symbol and enforce it — `pydocstyle`, `ruff` D-rules, Doxygen, XML-doc warnings-as-errors — so deleting one breaks the build. Delete only when the whole thing restates the signature *and* nothing requires it there.

**The full standard is `docstrings.md`, next to this file**: the redundant and convoluted shapes, what earns its place, the per-language table, and the language traps that reverse the rule — Go *requires* the restatement, a Rust `///` fence can compile as a test, C# and Java tags can be build inputs, JSDoc `{type}` in a `checkJs` project is the only type information in the file, and sometimes the docstring *is* the program. None of that is visible from the text of the comment, which is why the rule is not applicable from a summary. Agent B reads it; Agent C reads it for the truth branch.
