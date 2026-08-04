# Docstrings

The concision standard for the language's structured documentation comment, in
every language — Python `"""..."""`, C# `/// <summary>`, Doxygen `/** @brief */`,
Javadoc, JSDoc/TSDoc, Go doc comments, Rust `///`, YARD, Swift markup. The bloat
is identical across all of them; only the syntax changes.

**Who loads this:** Agent B, whose pass this is, and Agent C for the truth branch
— a docstring describing behaviour the function no longer has. Agents A, D and E
do not need it.

Split out of `core-patterns.md` because it is the largest section there and the
fewest readers use it. The universal rules, including the directive-comment table,
stay in that file.

**Expect volume here.** Generators emit a docstring per function whether or not there is anything to say, and they are graded on looking thorough rather than on being read. A file can gain three hundred lines of docstring and no information. This is the highest-yield place in a generated diff and the one reviewers skim hardest, because rejecting a docstring feels like rejecting diligence.

**The verdict is usually TIGHTEN, not DELETE.** A docstring is not a line comment. Many repos require one on every public symbol, enforced by `pydocstyle`, `ruff` D-rules, Doxygen, or XML-doc warnings-as-errors, and deleting it breaks the build or the docs site. Check before proposing a deletion: does anything else in this repo's public API go undocumented? If not, the docstring stays and gets shorter. Delete only when the whole thing restates the signature *and* nothing requires it there.

## Redundant sentences

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

## Convoluted sentences

The register, not the content. Nominalization, passive voice, and a wind-up before the verb:

| Convoluted | Direct |
|---|---|
| "This function is responsible for handling the calculation of the total" | "Returns the total" |
| "Performs the initialization of the connection pool" | "Initializes the connection pool" |
| "Utilized in order to facilitate the processing of incoming requests" | "Processes incoming requests" |
| "It should be noted that this may potentially return None" | "Returns None when the cache is cold" |

*Test:* find the verb. If the real action is trapped inside a noun ("handling the calculation of") or arrives after eight words of preamble, rewrite in the imperative or third person and cut the wind-up. Hedges — "may potentially", "it should be noted", "in some cases" — either name the case or come out.

## What earns its place

Keep, and never cut to make a docstring shorter:

- **Units and ranges** — "timeout in milliseconds", "0.0 to 1.0 inclusive"
- **Raises**, and the condition — "raises `KeyError` if the id was evicted"
- **Side effects** — writes to disk, mutates the argument, blocks, starts a thread
- **Invariants and ownership** — "caller owns the returned buffer", "not thread-safe"
- **Non-obvious defaults**, and why they are what they are
- Anything with a link or a ticket — you cannot see what is on the other end
- A "because" clause **that carries a reason** — a constraint, a decision, a consequence. Not the word on its own: "because we need to count hits" over `counter++` is restatement wearing a conjunction, and generators emit it constantly because "explain why" is the standard instruction they are given. Test it by deleting the code: if the reason still tells you something, keep it

## Every language has one — apply this to all of them

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

## Language traps that reverse the rule

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

## Reporting

Report docstring concision as **one grouped finding per file** — a count, two exemplars, and the rewrite pattern. Not one finding per docstring. Forty P3 entries for forty functions is how a report stops being read, and the P1 three sections down goes with it. **P3** for convoluted or redundant docstring prose; a docstring that is factually *wrong* is a different finding and a P2.
