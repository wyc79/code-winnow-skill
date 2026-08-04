# Comments as evidence

The grading standard for a comment that claims the code below it is intentional.

**Who loads this:** the orchestrator, for Step 3.5 class X1 — that step arbitrates
Agent A's findings against the comments next to them, and it cannot be executed
from a pointer. Agent A does not need this file; its prompt carries the one
distinction it uses (a checkable why earns a lookup, a bare claim does not) and
its job is to tag the claim, not to grade it.

Split out of `core-patterns.md` because every judgment agent loads that file and
only one reader uses this.

Separate question from whether a comment earns its space, which is `core-patterns.md`'s Comments and Directive comments sections. There, a comment is the thing being judged. Here it is *evidence about the code below it* — the author telling you a field with no reader is read somewhere you cannot see, or a duplicate test pins a specific bug.

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

## The unverifiable claim is a question, not a pass

There is an obvious way to game the rule above, and it costs eleven characters. Append `(see #4821)` to any comment and it becomes a "checkable why"; the runtime almost certainly cannot open the tracker, so the lookup is unperformable, and if unperformable meant "leave it alone" then any line could be immunised by a generated ticket reference. In a UE5 repo `// Set in Blueprint` is the same sticker with no ticket at all.

So an unverifiable claim does not protect the code, does not silently preserve it, **and does not change its severity**. It converts the finding into a question the user answers — reported at *the severity it already carried*, tagged `author claim, unverified — confirm`, with the comment quoted and the specific lookup you could not perform named. That keeps it in front of the person who can settle it in two seconds, which neither dismissing nor deleting does.

**Reporting it at P3 was the same exploit one rung down.** If an unverifiable comment demoted every finding it touched to cosmetic, then those eleven characters would move a P1 swallowed exception to the bottom of a list this skill elsewhere tells you to *cut* when it runs past a screen. The immunity would be rebuilt out of the triage rules seconds after the severity rule closed it, and it would look like diligence. Severity describes what the code does; a claim nobody could check is not evidence about that, in either direction.

Two consequences worth stating plainly. Never propose a deletion on an unverified claim — you have no evidence. And never treat repeated unverifiable claims as a pattern of abuse; the author of a Unity project has every reason to write `// Set in the Inspector` on a field that genuinely is.

A bare claim earns no lookup, because there is nothing to look up. The comment and the code are one decision: either the claim acquires a ticket, or both lines go. Never delete the code and keep the comment, or the reverse.

## The bare-claim rule has one exception: the comment *is* the mechanism

Some code exists only to be referenced from somewhere the compiler cannot see, and the idiomatic marker for it is exactly the phrasing this file calls a bare claim:

```csharp
// Intentional. Do not remove.
private static NativeAudioCallback _callbackRef;
```

Delete that and the GC collects the marshalled delegate — an intermittent native crash, no compile error, no failing test. The same shape covers side-effect imports (`import readline`, `from . import signals`), `#[used]` statics, GC roots, `static_assert` anchors, and registration-by-construction.

**Before merging any bare claim with its declaration, ask what deleting it would break at runtime rather than at compile time.** If the binding is a callback reference, a GC root, a side-effect import, or a registration anchor, it is load-bearing regardless of how thin the comment is, and the right output is the confirm-question above — at whatever severity the finding already carried, never demoted for being unverifiable — plus a suggested rewrite of the comment to say *why*, which is the actual defect.
