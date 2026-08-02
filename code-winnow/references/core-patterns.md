# Core patterns

Language-agnostic. Load this every run, then load the language-specific file.

Each entry: the tell, why it costs something, and the test for whether it is actually slop in this case.

## Comments

**Restating the code.** `// increment the counter` above `counter++`. Costs a line, adds nothing, and trains readers to skip comments — which means they skip the one that mattered.
*Test:* delete it mentally. Did you lose information the code doesn't carry? If no, cut it.

**Section-header decoration.** `// ===== HELPERS =====` in a 40-line file. Structure theatre.
*Test:* does the file have enough sections that navigation is hard? Under ~200 lines, no.

**Hedged narration.** "This should handle most cases", "we may want to revisit this". Uncertainty with no owner and no ticket. Either it's a known limitation worth documenting concretely, or it's noise.

**Changelog comments.** `// Updated to use new API` — that is what version control is for.

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

**Unicode hazards.** **P1.** Em dashes, smart quotes, non-breaking spaces, and zero-width characters in source, string literals, or identifiers. They break greps, diffs, and occasionally parsers, and they are invisible in review.

**Absolute local paths, machine names, or credentials** committed in config or test fixtures. **P1.**

**Duplicated helper.** A utility written fresh that already exists in the repo.
*Test:* grep for the function's core operation before accepting any new helper.

## Documentation

- Docstrings restating the signature (`"""Gets the name. Args: name. Returns: the name."""`)
- README sections written in the promotional register — "comprehensive", "robust", "seamlessly", "powerful"
- Doc claims about behavior the code doesn't have
