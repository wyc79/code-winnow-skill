# Performance notes

Agent D's judgment standard. Load it every run D is dispatched, alongside `core-patterns.md` and the language file matching the diff.

**Nothing in this file is ever applied.** D produces notes, they go to their own document, and no note enters the fix plan. That is not timidity about the findings — it is the honest consequence of the fact that D cannot measure. Agent A can prove a deletion safe with a grep anyone can re-run; there is no grep for "this is slow". Every note here is a hypothesis about a program nobody profiled, and a hypothesis applied without measurement is how a readable loop becomes an unreadable one for no gain.

## The gate: name the frequency, or you do not have a note

Every note states **how often the code runs, and how you established that** — the enclosing `Update()`, the request handler it sits in, the loop bound, the caller you traced.

*Test:* can you finish the sentence "this runs N times per X"? If not, stop. What you have is a preference about how the code is written, and Agent A owns that question. Hand it over or drop it; do not file it here with the frequency left vague.

This gate is the whole reason D is safe to add to a skill that opens by refusing to be a bug hunt. Without it, "performance" is a licence to comment on every line in the diff, because all code is slow if you squint. With it, the eligible set is small, and the notes that survive are the ones a reader can check by looking at one call site.

Three exclusions fall out of the gate rather than needing rules of their own:

**Startup, config load, migrations, and once-per-process code produce no notes.** They run once. The frequency argument cannot be made, so they are ineligible — however wasteful they look. A 40ms JSON parse at boot is not a finding.

**No micro-optimization.** `++i` over `i++`, a `StringBuilder` for two concatenations, hoisting a bounds check, `int` over `long`. These either fail the gate or fall below anything measurable, and proposing them is how a document stops being read. If the win is invisible without a profiler and the loop runs 20 times, it is not a note.

**No readability trade for a speculative gain.** A note that makes the code harder to follow in exchange for an unmeasured improvement is a bad trade proposed with false confidence. If the faster form is also the clearer form, say so; if it is not, the note has to be worth the cost, and at `measured: no` it usually is not.

## Establishing frequency

Two honest ways, and one that is not.

**From the enclosing entry point.** The code sits inside something whose call frequency is a property of the framework. This is the strongest form and needs no tracing.

| Ecosystem | Runs per frame / tick / request |
|---|---|
| Unity | `Update`, `FixedUpdate`, `LateUpdate`, `OnGUI`, `OnAnimatorMove`, `OnTriggerStay`, `OnCollisionStay`, `OnRenderObject` |
| UE5 | `Tick`, `TickComponent`, `TickActor`, anything bound to a tick group, `PostProcess` hooks |
| Web / service | a request handler, middleware, a serializer's per-field hook, an ORM `__getattr__` |
| UI | a render or paint method, a layout pass, a scroll or resize handler, a React render body |
| Data | a per-row callback, a `map`/`apply` body, a parser's per-token branch |
| Game / sim generally | anything called from the main loop, a physics step, an audio callback |

`OnGUI` and `OnTriggerStay` are worth naming explicitly because they are less obvious than `Update` and often worse — `OnGUI` can run several times per frame, and `OnTriggerStay` runs per overlapping collider per fixed step.

**From the loop bound.** The code is inside a loop whose iteration count you can name or bound from the diff. "Over `entities`, which the spawner caps at 400" is a frequency. "Over `items`" is not, unless you traced where `items` comes from.

**Not this: assertion.** "This is a hot path" with nothing behind it is the failure this gate exists to prevent. If the frequency came from an assumption, say so in the note's own words — `frequency: unknown, assumed hot because it is in the render module` is at least honest, and it tells the reader the note is weaker than the ones above it. Better still, drop it.

## What earns a note

Ordered roughly by how often it is real in generated code.

**Work repeated per iteration that is invariant across iterations.** A lookup, a compile, a format, an allocation, or a property resolution hoisted out of the loop changes nothing about behaviour and is usually also clearer.

**Complexity that will not hold.** A nested scan over the same collection, a linear `in`/`Contains` check inside a loop over the same data, a sort inside a loop. Name the shape (`O(n²)`) *and* the `n` you expect — the shape alone is not a frequency argument, and `O(n²)` over five elements is nothing.

**Allocation inside a hot path.** LINQ chains, closures captured per call, boxed enumerators, `params` arrays, string concatenation in a loop, a new list per frame. In a GC'd runtime this is often the real cost and it does not show up as CPU time in the obvious place.

**I/O, a query, a lock, or a syscall inside a loop.** The N+1 query is the canonical one. So is a file `stat` per item, a log write per row, and a mutex acquired per element rather than per batch.

**Quadratic string building.** `s += chunk` in a loop copies the accumulated string every iteration. Every language has the right form — `join`, `StringBuilder`, `FString::Appendf` into a reserved buffer.

**A data structure that does not match the access pattern.** A list scanned by key, a dictionary iterated by index, a queue implemented by removing from the front of an array.

**Re-computation across calls that has an obvious cache point** — but only when the cache has a clear invalidation story. If you cannot say when the cached value goes stale, the note is a fragility finding, not a performance one, and it belongs to Agent E.

## What never earns a note

- Anything failing the frequency gate, including all startup code
- Micro-optimization, as above
- A trust-boundary check. Validation at an edge is never a performance note, even when it is genuinely hot — see the "Never touch" list in `SKILL.md`. If it truly dominates a profile, that is a conversation for the user, not a note proposing its removal
- Test code. A slow test suite is a real problem and it is not this pass; test files get `tests.md` and nothing here
- Logging that is already gated, or debug-only paths compiled out of shipping builds
- Anything the scanner already flagged under `perframe-lookup`, `perframe-linq`, `expensive-lookup`, `pass-by-value` or `eager-log-format` — those are ordinary findings in the main report and the fix plan, and repeating them as notes double-counts them

## The `measured:` field

Every note carries one. Two permitted values:

- **`no`** — the default and the honest answer almost every time. The note is reasoning from a call site, not from data.
- **The benchmark or profile you actually ran**, named so someone can re-run it: `measured: pytest bench_grid.py::test_neighbours — 4.2ms → 0.3ms`. Only write this if you ran it.

This is D's analogue of Agent A's `evidence:` field, and it exists for the same reason: an instruction to verify that lives inside a long prompt competes with everything else in that prompt, and nothing downstream can tell a note whose reasoning was done from one where it was skipped. A field that must be filled makes the difference visible.

`measured: no` is not a defect in the note. It is the expected value, and it is exactly why these are notes.

## Outside the three claimed languages

`core-patterns.md` states the rule this file inherits: **verified coverage is Python, Unity C#, and Unreal C++.** Performance intuitions travel worse across languages than comment rules do, because the cost model is the thing that changes.

Concretely: a list comprehension is faster than a loop in Python and the equivalent LINQ is slower in C#; string concatenation in a loop is quadratic in most languages and optimized away by the JIT in some; a virtual call is free in one runtime and a cache miss in another; V8, PyPy and HotSpot each eliminate allocations that look expensive in source.

So outside the claimed three, note only what is language-independent — a nested scan over the same collection, an N+1 query, I/O in a loop, work invariant across iterations — and say in the note that the cost model was not verified for that language. **Do not propose an idiom swap in a language this skill does not claim.** "Use a generator instead" is sound advice in Python and may be nothing at all in Go.

## Reporting

Agent D writes its raw output to `round-NN/agent-D.md`, like every other pass. The supervisor produces `round-NN/notes.md` from it — that is the only place D's findings are ever published, never the main report and never the fix plan. The `notes.md` template is already in the round; fill it. Format, one entry per note:

```
- src/Grid.cs:22 — neighbour scan is O(n²)
  frequency:  once per FixedUpdate, 50/sec, over ~400 entities
  reasoning:  nested for over `entities` inside `entities`, neither bounded
  suggestion: spatial hash, or bail on the distance check first
  measured:   no
```

**Never use `- [ ]` and never write a `file:` line.** Those are the two tokens the fix-plan parser keys on, and a notes document that parses as a plan is a document that can be executed. The filename differs too, and both guards are deliberate.

Read `.code-winnow/perf-declined.md` before writing anything and skip any note matching an entry — path plus anchor text, line number ignored, because lines shift. Report the count of skipped notes rather than listing them; the user already answered those.

**Order notes by strength of the frequency argument, not by guessed impact.** A note whose frequency came from an enclosing `Update()` is worth more than one whose frequency came from an assumption, and guessed impact is a second unmeasured number stacked on the first.

If there are no notes, write the document anyway with an empty Notes section and say the pass ran. A missing file is indistinguishable from a pass that was skipped.
