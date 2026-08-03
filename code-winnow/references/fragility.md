# Silent failure and fragility

Agent E's judgment standard. Load it every run, alongside `core-patterns.md` and the language file matching the diff. E runs whenever A runs — unlike C and D, no diff shape is exempt, because a one-line change is enough to add a swallowed exception.

## Why this pass exists

This skill already knows what silent breakage looks like. It is the most consistent theme in the whole document, and Step 6 states it plainly: *every item in the deletion-safety pass fails at runtime, at build time, or in CI config — not in a unit test — which is exactly why they survive a green suite.* The directive table in `core-patterns.md` is a catalogue of the same thing: "type checking vanishes with **no error at all**", "silent bundle changes, zero build error", "silent change to string mutability".

**But all of it is applied in one direction only.** Those five deletion-safety questions — was it referenced from somewhere the compiler cannot see, was it a directive, did it carry type information, was it validation at a trust boundary, did a test lose its only failure mode — are asked exclusively about lines *this skill's own fix* removed. Nobody has ever asked them about what the diff under review did.

That is the hole E fills, and it is why E is not a bug hunt bolted onto a skill that refuses bug hunts. It is the same five questions, pointed at the change instead of at the cleanup.

## The gate: name how it breaks, and why the suite stays green

Every finding answers both halves. Neither alone is enough.

*Test one — how does it break?* Name the failure: what goes wrong, when, and under what condition. "This is fragile" is not a failure mode. "On a save file written before this change, `dashCharges` deserializes to 0 and the player cannot dash" is.

*Test two — why does the suite stay green?* Name the reason no existing test catches it. The suite only creates fresh saves. Nothing exercises the throw path. The failure needs two threads. The break is in generated code the tests do not import.

**If a test would catch it, it is not an E finding.** It is an ordinary bug, and bug hunting is out of scope — the suite, CI, or a code review will get it. E's entire value is the class of defect that a green run cannot see, and widening past that turns this into the general code review the skill opens by refusing.

**If you cannot say how it breaks, it is a style opinion.** Agent A owns those. Hand it over or drop it. "This design is confusing", "this could be refactored", "this might have a race" with no named mechanism — none of these are findings here, and filing them is how E stops being trusted.

Both halves, every time. The gate is short on purpose: it has to survive being read at the end of a long prompt.

**One class answers the gate in different words and is not exempt from it: a committed credential.** *How it breaks:* the key is valid, published, and usable by anyone who can read the repo. *Why no test catches it:* no suite has ever failed over a key that works. Read literally, "name the runtime failure" would drop the purest example of a defect with no signal, so it is written out here rather than left to be inferred. See "Committed credentials" below.

## The catalogue

Not exhaustive — the gate above outranks any list, and a shape absent from here that passes both tests is still a finding. These are the ones that recur in generated diffs.

### Failure that leaves no signal

**Swallowed exceptions.** A catch that logs and continues, leaving the program in an undefined state. Already **P1** in `core-patterns.md`; E's addition is to check whether the diff *introduced* one, and what state the program is in afterwards. Converting a crash into silent corruption is strictly worse than the crash.

**`async void` / fire-and-forget.** In C#, an exception thrown from `async void` cannot be caught by the caller and takes down the process or vanishes, depending on the sync context. The same shape is an unawaited `Task`, a floating promise, a `go func()` with no error channel, a `threading.Thread` whose target raises. The work silently stops and nothing reports it.

**A default that masks the failure.** `dict.get(k, 0)`, `TryGetValue` ignoring the bool, `?? 0`, `catch { return null; }`. Each converts "absent" into a plausible value, and the wrong answer propagates further from its cause than the exception would have.

**Retry or fallback with no ceiling and no log.** The system degrades and nothing says so.

### State that can desync

**A constant duplicated rather than referenced.** The same magic number, format string, key name, or version literal written in two places. Nothing breaks now; it breaks the first time someone changes one. Name both locations.

**A cache with no invalidation path.** The most common form in generated code: a memo, a lazily-built dictionary, or a cached component reference, added with no answer to "when does this go stale?". If there is a clear invalidation point the code is fine and any concern is Agent D's; if there is not, it is E's.

**Two representations of one fact** — a count field beside the collection it counts, a flag mirroring a state enum, a serialized copy of something also computed. They will diverge.

**Order dependence that is not expressed.** Code that works because `Awake` runs before `Start`, because one registration happens before another, because a dict preserved insertion order, because module import order put the patch first. Unity's `Awake`/`Start`/`OnEnable` ordering across objects is not guaranteed without a script execution order; UE5's `BeginPlay` has the same property.

### Breaks somewhere the compiler cannot see

This is the deletion-safety list, pointed at the diff.

**A serialized or persisted surface changed without a migration.** A new `[SerializeField]` or `UPROPERTY` with no default for existing scenes and prefabs; a renamed field that orphans saved data; a changed enum ordinal where the ordinal was persisted; a database column added with no backfill; a wire-format field whose meaning changed while its name did not. Old data loads as zero, null, or the wrong case, and every test that writes its own fixture passes.

**A reference that only reflection, DI, or an asset holds.** Renaming a class that a scene references by name, a handler resolved by string, an ORM mapping keyed on the attribute name, a Blueprint calling a `UFUNCTION`. The compiler is happy.

**A directive comment added or removed.** See the table in `core-patterns.md`. E's angle is the *addition*: a newly-added `# noqa`, `# type: ignore`, `// NOLINT`, `@SuppressWarnings`, or `# nosec` in the diff is a suppression of something, and the something is usually the finding.

**Type information carried in a comment.** A JSDoc `{type}` removed in a `checkJs` project, a `// @ts-check` pragma dropped, a `<param>` deleted under CS1573. `core-patterns.md` has the full set; E checks whether the diff did it.

### Resources and lifecycle

**Acquired on one path, released on another.** A subscription in `OnEnable` with no matching `OnDisable`, a coroutine started and never stopped, a file or socket opened outside a `with`/`using`, an event handler added per call. These leak per cycle and only show up after a long session — never in a test.

**A lifecycle hook that assumes it runs once** but is called on every enable, every level load, or every hot reload.

### Concurrency, only when you can name the interleaving

**A shared mutable touched from two places** where you can name both and say why they overlap. Check-then-act on shared state, a lazy init with no lock, a collection mutated while iterated under a condition.

**Name the interleaving or drop it.** "This might race" is the single easiest thing to say and the hardest to act on, and a report full of unfalsifiable race warnings is worse than one that omits them.

## Removed protections

A protection this change took away is an E finding, and it is the strongest kind because the evidence is in the diff itself.

Not *"is this code vulnerable"* — that is out of scope and you must not go looking. Only: did the diff **delete or weaken a check that was there**?

- A validation or bounds call removed from a handler
- An auth, permission, or ownership assertion dropped
- `verify=True` → `False`, `validate_certs` disabled, `strict` turned off, TLS or hostname checking relaxed
- An escape, sanitize, or encode call gone
- A timeout or size limit removed
- A newly added security suppression: `# nosec`, `# noqa: S…`, `@SuppressWarnings("security")`

**Quote the removed line from the diff's `-` side and name the caller you traced.** If you cannot show the line the diff removed, you do not have this finding — you have a suspicion about existing code, which is out of scope. That is the same gate Agent C works under, for the same reason.

**P1** for a removed check on a reachable path. **P2** for a newly-added suppression, which is a signal rather than proof.

This is the mirror of a rule already in `SKILL.md`. "Never touch validation at a trust boundary" stops the *cleanup* from deleting one; this stops the *diff under review* from having deleted one silently. Two halves of one concern, and neither covers the other.

## Committed credentials

The second security-shaped thing that is yours, and the last one. Everything else in that direction stays out of scope.

**The scanner already owns the half a pattern can do.** Self-identifying vendor formats — `AKIA…`, `ghp_…`, `github_pat_…`, `glpat-…`, `xox…`, `sk_live_…`, `sk-ant-…`, `AIza…`, `npm_…`, a `-----BEGIN … PRIVATE KEY-----` block. Do not repeat those; they are already in the report as `committed-secret`.

**Yours is the half it cannot reach: a named credential assigned a literal.** The scanner's rule for that is anchored on a word boundary and a bare `[:=]`, which means it sees `password = "…"` and misses every real-world spelling around it:

```
password     = "…"     scanner sees it
DB_PASSWORD  = "…"     missed - no word boundary before PASSWORD
db_password  = "…"     missed - same
smtp_password: "…"     missed - same
"db_password": "…"     missed - the quote blocks the separator
```

That last one is `appsettings.json`, `config.yml`, `.env.example` gone wrong — the commonest place a committed password actually lives, under the commonest name it is actually given. Widening the pattern is not the fix: credential names are unbounded, and a pattern loose enough to catch them all is loose enough to fire on every `*_key` and `*_token` in the repo. This is a reading job.

**Four rules, and the first is the one that keeps this pass trustworthy:**

**You are reading, not scoring.** Do not run entropy in your head. A hash, a UUID, a git sha, a base64 blob and a minified bundle all look random and none of them is a secret. `core-patterns.md` refuses an entropy heuristic on purpose — a noisy secrets rule teaches the reader to skim, and what they skim past is the P1 three sections down. The question is whether the *name* says credential and the *value* is a real one, never whether the value looks random.

**Placeholders and indirection are not findings.** `${DB_PASSWORD}`, `{{ vault_pw }}`, `<your-api-key>`, `changeme`, `xxxxxxxx`, an obviously redacted value, a vendor's published example. Nor is a value read rather than written — `os.environ[…]`, `Configuration["…"]`, a secrets-manager call. That is the correct pattern, and flagging it is how a security pass loses its audience in one run.

**P1, and it does not demote in a test or prose file.** Every other universal rule demotes in a fixture, because a home path in a fixture is data. A live credential is not data, and a test directory is where keys most often leak.

**Never propose a fix.** This is the one finding class that is reported and never patched, at any severity and however clearly worded. Deleting the line does not un-leak the key — it is already in the object store, in every clone, and in every CI cache that fetched it. Write:

```
fix:      out of scope - rotate the credential; deleting the line leaves it in history
```

A patch here would hand the user an all-clear they have not earned, which is a worse outcome than not detecting it at all.

**Diff lines only, like everything else in this file.** A credential on a line this change did not touch is not yours — note it under pre-existing if you had the file open anyway, and do not go looking. Sweeping a repo for keys is the security audit this skill opens by refusing, and it is a job for a tool with a rotation workflow behind it.

## E vetoes A's deletions

Agent A proposes removing code. E is the reader who knows what removal breaks. When A proposes deleting a line E identifies as load-bearing — a GC root, a directive, a type carrier, a trust-boundary check, a registration anchor, a side-effect import — **E wins**, and Step 3.5 dismisses A's finding into "Deliberately left alone" with E's reason.

That is the real structural payoff of this agent. Step 6's deletion-safety pass catches the same mistakes *after* the edits land and reverts them. E catches them before the fix plan is written, so the bad deletion is never approved in the first place.

Both passes stay. They are the same questions at two different moments, and the fix plan is a user-edited subset of what E reviewed, so neither makes the other redundant.

## Severity

- **P1** — silent corruption, silent data loss, a removed protection on a reachable path, a committed credential, or any failure with no observable signal at all
- **P2** — fragility that surfaces loudly when it breaks (a crash, a log, a visible error) but that nothing tests; a newly-added suppression; a desync that needs a future edit to trigger
- **P3** — E should essentially never produce one. If a finding is cosmetic, it failed the gate, and it is Agent A's

## When the fix is out of scope

Many E findings cannot be fixed by this skill, and that is expected rather than a gap.

`SKILL.md` Step 5b already binds every fix: *behavior stays identical; if a fix would change behavior, it is not a winnowing fix — surface it separately and leave it.* E inherits that rule with no new machinery:

- **Fix-plan eligible** when the change preserves behaviour and is local — add the missing `await`, narrow a catch to the expected type, replace a duplicated constant with a reference to the original, restore a removed validation call, stop a coroutine in `OnDisable`.
- **Reported and left** when the fix is a design decision — a save migration, a cache invalidation strategy, a locking scheme, a schema backfill. Write `fix: out of scope — <why>` and propose nothing. **Every committed credential is in this bucket by construction**, for a different reason than the rest: the repair is a rotation, which is not a behaviour-preserving edit and not this skill's to make.

An out-of-scope finding still goes in the main report at its own severity. It is not demoted for being unfixable here, and it is not moved to a side document — burying a P1 because this pass cannot repair it is the failure mode this whole arrangement exists to avoid.

## Required fields

Every finding:

```
breaks:   <how and when it fails — runtime / build / CI / only under condition X>
no test:  <why the suite stays green>
fix:      <the behaviour-preserving change, or "out of scope — <why>">
```

Plus the standard `anchor:` / `occurrence:` / `of:` / `evidence:` fields **only on fix-plan-eligible findings**, on exactly the terms Agent A uses. A finding marked `fix: out of scope` needs none of them — the same logic as Agent B's KEEP verdicts, which need no anchor because nothing is going to be located.

## Outside the three claimed languages

`core-patterns.md`'s rule holds and bites harder here than anywhere. The lifecycle guarantees, the GC behaviour, the async model and the serialization rules are exactly what changes between ecosystems, and every entry above depends on one of them.

Report the language-independent shapes — a duplicated constant, a swallowed exception, a removed validation call, a resource acquired and not released, a persisted surface changed with no migration — and say the ecosystem's guarantees were not verified. **Do not assert a lifecycle or memory-model claim about a runtime this skill does not claim.** "This will be garbage collected" is a fact in one language and a guess in another, and a confident wrong claim about a runtime nobody here reviews is worse than silence.
