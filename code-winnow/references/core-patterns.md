# Core patterns

Language-agnostic. Load this every run, then load the language-specific file.

Each entry: the tell, why it costs something, and the test for whether it is actually slop in this case.

## What this skill actually claims

**Verified coverage is three languages: Python, Unity C#, and Unreal C++.** Each has a reference file next to this one, dedicated scanner rules, and tables here that were checked against its toolchain. Those are the languages to trust this skill in.

Everything else gets the universal pass — comments, typography, invisible characters, generic test smells — plus these tables **on a best-effort basis**, which is a weaker claim than it appears. An incomplete directive list is indistinguishable from a complete one at the moment you are about to delete a line that is not on it, and the list below is demonstrably incomplete: `// ktlint-disable` and `// swiftlint:disable` are real suppressions in real repos, and neither the table nor the scanner's directive pattern recognises either.

**So outside those three languages, an unrecognised comment defaults to KEEP.** Not being able to say what a comment is *for*, in a language this skill does not claim, is not evidence that it is chaff — it is evidence that you are the wrong reader. Report it as a confirm-question naming the language, or say nothing at all. Keeping a redundant comment in a Kotlin file costs one line. Deleting `// ktlint-disable` because it was not in a table costs a broken build that no test catches, in a language nobody here can review the fix for.

This is a floor, not a ceiling: a clear-cut restated comment in Go is still a clear-cut restated comment. The rule bites where confidence is low, which outside the three claimed languages is more often than it feels.

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

Separate question from the one above. There, a comment is the thing being judged. Here it is *evidence about the code below it* — the author telling you a field with no reader is read somewhere you cannot see, or a duplicate test pins a specific bug.

This matters because the obvious rule is wrong. "If a comment says the code is intentional, do not flag it" hands every generated line an opt-out, written by the same generator. `// Reserved for future implementation` above a field nothing sets is not a defense of speculative structure — it *is* speculative structure, with a second line of it stacked on top.

So authority is graded. The question is never "does a comment claim intent", it is **"does the claim name something you can go and check".**

**A checkable why** — the comment points at something outside itself:

- a ticket, issue, or PR reference, or a URL
- a named consumer or mechanism: "the serializer reads this", "set from the Inspector", "Blueprint calls this", "mirrors the prod constructor"
- a concrete external constraint: "UE 5.4 returns a zero vector on near-zero input"
- an invariant the code below depends on

**A bare claim** — asserts intent and stops:

- "reserved for future use", "reserved for future implementation"
- "kept for later", "will be used", "placeholder"
- "intentional", "do not remove" — with no reason given

*Test:* could a reader who distrusts the comment go and verify it? A checkable why gives them somewhere to go. A bare claim asks for faith.

**Then go and check it.** A checkable why earns a lookup, not a pass. Grep for the serializer, search the scenes for the field, open the ticket if it is reachable. **Four outcomes, and the difference between the middle two is where this rule goes wrong:**

- **Confirmed** — you found the thing. The comment protects the code. Dismiss the finding and quote the comment as the reason.
- **Disproved** — you found positive evidence of the opposite: the named ticket exists and says something else, the named consumer exists and does not reference this. The finding stands, goes *up* a severity (P3→P2→P1; a P1 stays P1), and says the comment is false. A comment asserting something untrue is worse than no comment, because it stops every future reader from touching the line for a reason that does not exist.
- **No evidence either way** — the grep returned nothing. **This is not disproof, and it must never be treated as disproof.** Keep the finding at its original severity, mark it `unverified`, and propose nothing.
- **Unperformable** — no network for the ticket, no tooling for the asset. Same handling as no-evidence.

**Absence of evidence is the normal result for truthful comments.** The consumers that are hard to grep are exactly the ones worth commenting about: Blueprints and scenes in binary assets, reflection, dependency injection, `getattr`, serializers, SQL views, wire protocols, `dlopen`. Reading "grep found nothing" as "the author lied" produces a confident P1 accusing a correct comment of being false, proposes the deletion, and the build stays green while the game breaks at runtime. Only positive disproof earns the upgrade.

### The unverifiable claim is a question, not a pass

There is an obvious way to game the rule above, and it costs eleven characters. Append `(see #4821)` to any comment and it becomes a "checkable why"; the runtime almost certainly cannot open the tracker, so the lookup is unperformable, and if unperformable meant "leave it alone" then any line could be immunised by a generated ticket reference. In a UE5 repo `// Set in Blueprint` is the same sticker with no ticket at all.

So an unverifiable claim does not protect the code, does not silently preserve it, **and does not change its severity**. It converts the finding into a question the user answers — reported at *the severity it already carried*, tagged `author claim, unverified — confirm`, with the comment quoted and the specific lookup you could not perform named. That keeps it in front of the person who can settle it in two seconds, which neither dismissing nor deleting does.

**Reporting it at P3 was the same exploit one rung down.** If an unverifiable comment demoted every finding it touched to cosmetic, then those eleven characters would move a P1 swallowed exception to the bottom of a list this skill elsewhere tells you to *cut* when it runs past a screen. The immunity would be rebuilt out of the triage rules seconds after the severity rule closed it, and it would look like diligence. Severity describes what the code does; a claim nobody could check is not evidence about that, in either direction.

Two consequences worth stating plainly. Never propose a deletion on an unverified claim — you have no evidence. And never treat repeated unverifiable claims as a pattern of abuse; the author of a Unity project has every reason to write `// Set in the Inspector` on a field that genuinely is.

A bare claim earns no lookup, because there is nothing to look up. The comment and the code are one decision: either the claim acquires a ticket, or both lines go. Never delete the code and keep the comment, or the reverse.

### The bare-claim rule has one exception: the comment *is* the mechanism

Some code exists only to be referenced from somewhere the compiler cannot see, and the idiomatic marker for it is exactly the phrasing this file calls a bare claim:

```csharp
// Intentional. Do not remove.
private static NativeAudioCallback _callbackRef;
```

Delete that and the GC collects the marshalled delegate — an intermittent native crash, no compile error, no failing test. The same shape covers side-effect imports (`import readline`, `from . import signals`), `#[used]` statics, GC roots, `static_assert` anchors, and registration-by-construction.

**Before merging any bare claim with its declaration, ask what deleting it would break at runtime rather than at compile time.** If the binding is a callback reference, a GC root, a side-effect import, or a registration anchor, it is load-bearing regardless of how thin the comment is, and the right output is the confirm-question above — at whatever severity the finding already carried, never demoted for being unverifiable — plus a suggested rewrite of the comment to say *why*, which is the actual defect.

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
- Unused imports, unreferenced private helpers, variables assigned and never read
- Entry/exit logging (`log.debug("entering foo")`) left from an agent's debugging pass

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

**Typographic characters — em dashes, en dashes, smart quotes — in code.** **P3, not P1.** They are visible, and they only cost you a grep that does not match. Delete them in identifiers and in code you expect to search. **Leave them in comments, docstrings, prose files, and user-facing copy** — localized `FText`/`LocalizedString` strings are supposed to use real typography, and "fix" that and you have degraded the product to satisfy a linter. The scanner agrees: P3, and it exempts whole-line comments, Python triple-quoted regions and prose files. It does **not** exempt a comment sharing a line with code, nor string literals - so check trailing comments and localized strings yourself before accepting one.

**Absolute paths into a developer home directory** (`/Users/name/…`, `C:\Users\name\…`) committed in config or test fixtures. **P1.** A `/home/name/…` path is a P2 — half the containers alive use one as a deployment path. Either one drops a step inside a path-handling test or a documentation file, where it is data or an example rather than a leak.

**Committed credentials.** **P1.** Two halves with different confidence, and they behave differently:

- **A recognised vendor format — the scanner's half.** An AWS key id, a `ghp_`/`github_pat_`/`glpat-` token, a Slack `xox…`, a Stripe `sk_live_`, a Google `AIza…`, an npm or SendGrid token, or a `-----BEGIN … PRIVATE KEY-----` block. These are self-identifying by prefix, so the match is on a *format* rather than a guess. **P1 everywhere, including test and prose files** — the one rule here that does not demote in a fixture, because a live credential is not data and a test fixture is where keys most often leak.

  One exemption, and it is deliberately narrow: a token whose value **ends** in `example` or `sample`. Vendors publish well-formed keys in their own documentation — AWS's is `AKIAIOSFODNN7EXAMPLE` — and those get copied into config samples everywhere. It is anchored at the end because a token is a fixed-length random string: matching those letters *anywhere* in the body silently drops a live key whose body happens to contain them, which is a false negative on the one rule where that is the worst outcome available.

- **A credential-named variable assigned a literal — a judgment call, and Agent E's half.** `password = "…"`, `DB_PASSWORD = "…"`, `"db_password": "…"` in a config file. The scanner has a rule for the narrowest spelling of this, and you should know its reach before trusting a silent report: it is anchored on a word boundary and a bare `[:=]`, so it catches `password = "…"` and **misses every prefixed name** (`DB_PASSWORD`, `db_password`, `smtp_password`) and every quoted JSON or YAML key. Those are the spellings a committed password actually has. A wider pattern is not the answer — the names are unbounded and the noise would be — so the judgment half belongs to a reader. Agent E's brief in SKILL.md Step 3 carries it, at P1, never demoted in a fixture, and never fix-plan eligible.

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

**Expect volume here.** Generators emit a docstring per function whether or not there is anything to say, and they are graded on looking thorough rather than on being read. A file can gain three hundred lines of docstring and no information. This is the highest-yield place in a generated diff and the one reviewers skim hardest, because rejecting a docstring feels like rejecting diligence.

**The verdict is usually TIGHTEN, not DELETE.** A docstring is not a line comment. Many repos require one on every public symbol, enforced by `pydocstyle`, `ruff` D-rules, Doxygen, or XML-doc warnings-as-errors, and deleting it breaks the build or the docs site. Check before proposing a deletion: does anything else in this repo's public API go undocumented? If not, the docstring stays and gets shorter. Delete only when the whole thing restates the signature *and* nothing requires it there.

### Redundant sentences

The generated shape is four restatements of one fact:

```python
def get_user(user_id: int) -> User | None:
    """Get the user by id.

    This function retrieves the user associated with the given user id.
    It takes a user id and returns the corresponding user object.

    Args:
        user_id (int): The user id.

    Returns:
        User | None: The user object, or None.
    """
```

The summary line is the only line carrying anything, and it barely does. The paragraph restates the summary. `Args` restates the parameter name and repeats the type already in the signature. `Returns` repeats the return annotation.

*Test, sentence by sentence:* cover the signature and read only this sentence. Does it tell you something the signature does not? `user_id (int): The user id` fails. `user_id: must be a positive database id, not a session id` passes.

*Test for the whole block:* would a reader who already read the signature learn anything? If not, one summary line is the entire correct docstring — and if that line only restates the function name, there is no correct docstring and the question becomes whether the repo requires one.

### Convoluted sentences

The register, not the content. Nominalization, passive voice, and a wind-up before the verb:

| Convoluted | Direct |
|---|---|
| "This function is responsible for handling the calculation of the total" | "Returns the total" |
| "Performs the initialization of the connection pool" | "Initializes the connection pool" |
| "Utilized in order to facilitate the processing of incoming requests" | "Processes incoming requests" |
| "It should be noted that this may potentially return None" | "Returns None when the cache is cold" |

*Test:* find the verb. If the real action is trapped inside a noun ("handling the calculation of") or arrives after eight words of preamble, rewrite in the imperative or third person and cut the wind-up. Hedges — "may potentially", "it should be noted", "in some cases" — either name the case or come out.

### What earns its place

Keep, and never cut to make a docstring shorter:

- **Units and ranges** — "timeout in milliseconds", "0.0 to 1.0 inclusive"
- **Raises**, and the condition — "raises `KeyError` if the id was evicted"
- **Side effects** — writes to disk, mutates the argument, blocks, starts a thread
- **Invariants and ownership** — "caller owns the returned buffer", "not thread-safe"
- **Non-obvious defaults**, and why they are what they are
- Anything with a link or a ticket — you cannot see what is on the other end
- A "because" clause **that carries a reason** — a constraint, a decision, a consequence. Not the word on its own: "because we need to count hits" over `counter++` is restatement wearing a conjunction, and generators emit it constantly because "explain why" is the standard instruction they are given. Test it by deleting the code: if the reason still tells you something, keep it

### Every language has one — apply this to all of them

"Docstring" here means the language's structured documentation comment, wherever it appears. The generator emits these in every language and the bloat is identical; only the syntax changes.

| Language | Form | Redundant-restatement tell |
|---|---|---|
| Python | `"""..."""` | `Args:` repeating names and annotated types; `Returns:` repeating the return annotation |
| C# | `/// <summary>`, `<param>`, `<returns>` | `<param name="userId">The user id.</param>` |
| C++ / UE5 | `/** @brief @param @return */` | `@param Count The count.` |
| Java | Javadoc `/** @param @return @throws */` | `@return the result` |
| JS (JSDoc) | `/** @param {type} */` | `@param {string} name - The name.` — **but see below** |
| TS (TSDoc) | `/** @param name - ... */`, no `{type}` | A `{type}` brace at all; the signature has it |
| Go | `// Name does ...` above the declaration | A second sentence restating the first |
| Rust | `///`, `//!` | `/// Returns the value.` above `fn value()` |
| Ruby (YARD) | `# @param id [Integer]` | `# @param id [Integer] the id` |
| Ruby (RDoc) | plain prose, `:call-seq:` | A paragraph restating the method name |
| Swift | `///` markup, `- Parameter:` | `- Parameter name: The name.` |

**The first three rows are the claimed ones**; the rest are here because the bloat is real in every language, not because this file has been checked against their toolchains. Outside Python, C# and C++, propose a rewrite only when you can **name the convention and the tool that enforces it** — or confirm nothing enforces one. If you cannot, report the count and the pattern and let the user decide.

That is not excess caution, and the section immediately below is the argument for it: in Go the restatement is *mandatory*, in Rust the docstring may be a compiled test, in Java and C# it may be a build input. Every one of those inverts the rule in the table, and none of them is visible in the text of the comment. A rule that reverses depending on the toolchain is not one to apply from a table alone.

### Language traps that reverse the rule

These are the ones that turn a tidy-up into a broken build, and none of them are visible from the text of the comment.

**Go doc comments are supposed to restate the name.** `// ParseConfig parses the config file.` looks like the textbook restatement and is the required convention — `revive`'s `exported` rule and `staticcheck` ST1020 both check it. (`golint` is often cited here and was archived in 2021; and both live rules are off in golangci-lint's default set, so the repo may not enforce it.) Convention holds regardless of tooling: in Go, cut the *second* sentence that repeats the first, never the first. Watch the blank line too — a TIGHTEN that leaves one between the comment and the declaration detaches the doc comment entirely.

**Rust doc comments can run as tests.** A fenced code block inside `///` is compiled and executed by `cargo test` — **for library targets**. Doctests do not run in `bin` targets, and are disabled by `doctest = false` or by an `ignore` or `text` fence annotation. **`no_run` does not disable them**: the block is still compiled, only execution is skipped, so editing one can still break the build. `compile_fail` inverts the rule entirely — that block is *required* to fail compilation, and "fixing" the example is what breaks it. Treat any fenced block in a Rust doc comment as test code by default: the rules in `tests.md` apply, not these.

Two more in the same family. A `# `-prefixed line inside a Rust doc fence is **hidden from the rendered docs but still compiled** — it looks exactly like commented-out code and deleting it breaks the doctest. And `#![doc = include_str!("../README.md")]` makes the README's fenced blocks into doctests, which is worth knowing because Agent C is the one agent allowed to edit untouched docs.

The same executes-as-tests trap exists in Python under `--doctest-modules` and in any docstring containing `>>>`, where `# doctest: +SKIP` is load-bearing: delete it and the example runs and fails.

**Rust also has the compile-check trap.** `#![deny(missing_docs)]` or `#![warn(missing_docs)]` with `-D warnings` makes a `///` on any `pub` item a build input. Deleting one fails the build, exactly as in C# and Java below.

**Doc comments that compile-check.** C# `<param>` under CS1573/CS1591 with `GenerateDocumentationFile` and warnings-as-errors, and Java `@param` under `-Xdoclint`, are build inputs. Removing one entry from a documented method's parameter list fails the build. Verify the project's warning settings before proposing a deletion, or leave it and say why.

**UE5 `/** */` above `UPROPERTY` or `UFUNCTION` is user-facing.** UnrealHeaderTool turns it into the `ToolTip` metadata a designer reads in the Details panel. That is shipped product text, not developer commentary — treat it like a localized string, tighten it only for the reader who will actually see it, and never delete it as ceremony.

**Sometimes the docstring *is* the program.** `argparse.ArgumentParser(description=__doc__)`, `click` and `typer` help text, `docopt` — where the module docstring is the CLI grammar and editing it changes what the program accepts. Tightening any of these rewrites user-facing output or breaks parsing. Before touching a module-level docstring, grep for `__doc__`. This skill's own scanner is an instance: `scan.py` passes `description=__doc__` to argparse, so "cut the restated summary" would delete its `--help` body.

**A C# `<inheritdoc/>` is not an empty docstring.** Deleting it removes the member's documentation entirely and can trip CS1591. Same shape: TSDoc `@internal` under `stripInternal` — remove it and an internal symbol is published into the emitted `.d.ts`.

**In JSDoc, `{type}` is the type system — not a restatement of one.** The table above lists `@param {string} name` as the redundancy tell, and in TypeScript it is. In a `// @ts-check` file, a `checkJs: true` project, or anything using Closure Compiler, there is no signature to restate it *from*: the brace annotation is the only type information in the file. Cutting it as "redundant" deletes the types, and under `strict` it fails the build. Check for a `jsconfig.json`, `checkJs`, or a `// @ts-check` pragma before touching a brace annotation in a `.js` file. `@typedef`, `@template`, `@type` and `@satisfies` are pure declarations and are never redundant.

### Reporting

Report docstring concision as **one grouped finding per file** — a count, two exemplars, and the rewrite pattern. Not one finding per docstring. Forty P3 entries for forty functions is how a report stops being read, and the P1 three sections down goes with it. **P3** for convoluted or redundant docstring prose; a docstring that is factually *wrong* is a different finding and a P2.
