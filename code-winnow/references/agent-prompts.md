# Agent prompts

The dispatch text for the six judgment agents. `SKILL.md` Step 1 dispatches **S**;
Step 3 dispatches **A**, **B**, **C**, **D** and **E**.

**Expand `$WINNOW` to its real value before dispatching.** A subagent's cwd is the
repo, not the skill directory, and it has no `$WINNOW` — an unexpanded variable or a
relative `references/core-patterns.md` both resolve to nothing, and those files are
where all the judgment lives. An agent that cannot open them still returns findings;
they are just findings from no standard at all.

**Every Step 3 prompt also carries the staleness precondition below, verbatim**, and —
when Step 1 resolved a feature — the confirmed file and region list plus *"Findings
only from these hunks. You may read anything; report nothing else."*

## Where each agent writes — in every prompt

> Write your output to `<the round directory>/agent-<X>.md`, and open it with these
> three lines, filled from `<the round directory>/meta.json`:
>
> ```
> Round:     <NN>  —  .code-winnow/round-<NN>/
> Compared:  <branch> @ <side>   vs   <base> @ <sha>   (<scope>)
> Generated: <YYYY-MM-DD HH:MM>
> ```

Expand the round directory to its real value, exactly as with `$WINNOW` — a subagent
has no `$ROUND` either. Files inside a round are short and identical every round, so
nothing in `agent-B.md` says what it reviewed; that block is the only thing that does,
and it is what makes the file readable when its path is pasted somewhere on its own.

Anything an agent generates that is not its own report goes in
`<the round directory>/scratch/`, and any script it writes goes in
`.code-winnow/utils/`. Both directories already exist. A run once left nine
intermediate files at the workspace root because no rule named them.

## The staleness precondition — verbatim, in every Step 3 prompt

> Before you report anything, confirm your input is still current. You were given a
> diff and a scanner JSON describing the working tree at a moment in time. Whenever you
> open a file to verify something, check that the lines around your finding actually
> match what the diff says is there. **If a file on disk disagrees with the diff you
> were given, stop and report `STALE INPUT` with the path** — do not report findings
> against it, do not re-derive the diff yourself, and do not silently adjust the line
> numbers. Someone edited the tree while this review was running, and every line number
> you hold is now a guess.

Each agent has to check for itself. The orchestrator's `SNAPSHOT` comparison catches a
change before dispatch and after return, but not one landing *during* — and the
parallel window is exactly when the user is most likely to still be working.

## The scope rule — in every Step 3 prompt when a feature was named

> Scope was settled before you started and the user confirmed it. Work only inside it.
> If you find something that plainly belongs to this feature and is outside the list, or
> plainly does not belong and is inside it, **say so as an appeal** — name the location
> and the reason, and keep reviewing under the list as given. Do not act on your own
> scope opinion; a boundary that moves per agent stops being a boundary.

## The required fields

`anchor:` / `occurrence:` / `of:` / `evidence:` appear on every finding that is
proposed for action, from A, B, C and E alike. `occurrence` and `of` count **lines of
the file**, not findings. For a scanner candidate they are in the JSON as
**`anchor_index` and `anchor_total`** — copy those two. Do **not** copy the JSON's
`occurrence` field; it indexes findings sharing a rule and message, which is a
different population.

---

## Agent S — scope

Dispatched only when a feature was named, and **before** A, B, C, D and E. It gets the
input diff and the user's phrase verbatim. Nothing else: no scanner JSON, no
conversation history, no design rationale.

> The user asked for a review of one thing only, in their words: *"winnow the dash
> cooldown work"*.
> Here is the full diff. Decide, for each file and for any region within a file that
> plainly differs from the rest of it, whether it is part of what they asked for.
> Return `in | out | unsure`, each with one line of reason. Use `unsure` freely — it is
> a question the user will answer, not a failure. Do not review the code, do not report
> chaff, do not propose changes. You are drawing a boundary, nothing else.

## Agent A — chaff judgment

Everything except comments and doc files. Runs always.

> Review this diff as if a stranger wrote it. Read `$WINNOW/references/core-patterns.md`,
> plus the language file(s) matching the diff: `$WINNOW/references/csharp-unity.md`
> (`.cs`), `$WINNOW/references/cpp-ue5.md` (`.cpp`/`.h`), `$WINNOW/references/python.md`
> (`.py`). **If the diff touches any test file, read `$WINNOW/references/tests.md` too**
> — in any language, including ones with no language file here.
> **Those three languages are what this skill claims.** A file in any other language
> gets the universal rules and your ordinary judgment, and one extra rule that overrides
> the rest: **when you cannot say what a line is for, keep it.** Read "What this skill
> actually claims" in `core-patterns.md`. Not recognising something in a language nobody
> here reviewed is not evidence it is chaff.
> For each scanner candidate: confirm or dismiss, with a reason. Then read the diff
> yourself — the scanner catches maybe half of what matters, and the half it misses
> (speculative abstraction, mock theatre, duplicated helpers) is the expensive half.
> **Comments are not yours to report on** — another agent owns every one of them,
> including scanner candidates tagged `restated-comment` or `commented-code`. **But read
> them.** When a comment next to one of your findings claims the code is intentional —
> reserved, deliberate, needed by something you cannot see — do *not* dismiss your
> finding on that basis and do *not* report the comment. Keep the finding and tag it
> `comment-claim: "<the comment, verbatim>"`. A later step arbitrates, and you do not
> need its rules — only the distinction it grades on. **A checkable why** points at
> something outside itself: a ticket or URL, a named consumer or mechanism ("the
> serializer reads this", "set from the Inspector"), a concrete external constraint. **A
> bare claim** asserts intent and stops: "reserved for future use", "kept for later",
> "intentional" with no reason. Tag either one; never resolve either one yourself.
> The reference files tell you to verify before deleting — trace every caller, grep for
> an existing helper, check scenes and assets for a serialized field. **Do those
> lookups.** They are searches and reads for evidence, they are not reviews: nothing you
> see outside the diff becomes a finding, no matter how bad it is. The three-file cap is
> on *reviewing* neighbouring files for convention, not on grepping the repo to find out
> whether a deletion is safe. When a lookup is impossible here, say "unverified", keep
> the finding at its original severity, and propose nothing. Do not demote it — a later
> step routes unverified claims to their own section, and demoting them instead is what
> lets a generated ticket reference retire a real P1.
> **Return format, and every field is required** — the fix plan is built from these
> verbatim, and a field you leave out is one the supervisor has to invent from a file it
> has not read:
> ```
> path:line — what → why it matters → proposed change      [P1|P2|P3]
> anchor:     <the finding's source line, copied exactly as it appears>
> occurrence: <N>   (which matching line this is, counting top to bottom)
> of:         <M>   (how many lines of the whole file match that anchor)
> evidence:   <what you looked up and what you found — or the word `unverified`>
> ```
> **`occurrence` and `of` count lines of the file, not findings.** For a scanner
> candidate they are in the JSON as **`anchor_index` and `anchor_total`** — copy those
> two. Do **not** copy the JSON's `occurrence` field into `occurrence:`; it is the index
> among findings sharing a rule and message, which is a different population. A
> diff-scoped scan flags only the instance the change touched, so its `occurrence` is 1
> even when the anchor text is on three lines and the flagged one is the third — and an
> executor told "the first match" then edits an untouched line nobody reviewed.
> **For anything you found yourself, establish both** — open the file, copy the line,
> normalise runs of whitespace, and count every line that matches. That count is not
> bookkeeping: at execution time it is the only thing standing between a fix and the
> wrong line, because the executor refuses any item whose total has changed. If you
> cannot establish it, say so and drop the item rather than guessing a number.
> Also return the candidates you dismissed, and why.

## Agent B — comment and docstring concision

Comments and docstrings, and only those. Runs always.

> For every comment in the diff, return one of: DELETE (restates the code), KEEP
> (carries information the code cannot — a why, a workaround, an engine quirk, a
> business rule), or TIGHTEN (right content, too many words) with a rewrite.
> Rewrites: one line where one line does it. No preamble, no restating the function
> name, no hedging. Comments earn their space by saying something the reader cannot get
> from the code below them.
> Never delete a comment containing a link or a ticket reference — those point at
> information outside the file, and you cannot see what is on the other end.
> **"because" is a signal, not a shield.** It usually introduces a reason the code cannot
> state, and when it does, keep the comment. But it is one word, and "explain why in
> comments" is the standard instruction given to code generators, so it arrives attached
> to restatement constantly: `// increment the counter because we need to count hits` is
> still a restatement, and the clause after "because" says nothing the line below does
> not. Read what follows it. A reason that survives deleting the code — a constraint, a
> decision, a consequence — is a KEEP. A reason that is just the code again in prose is
> not.
> A version number is not automatically protective. `// Workaround for UE 5.4 normalize
> bug` is a KEEP: the version is *why* the code is shaped that way. `// Updated to use
> the new API in v2.3` is a changelog entry and a DELETE — git already has it. The test
> is whether the version explains the code below it or only records when someone touched
> it.
> **Docstrings need their own pass, and it is the highest-yield thing you will do.** Read
> `$WINNOW/references/docstrings.md` before starting it — the whole file, which is the
> standard for this half of your job.
> Generated diffs carry a docstring per function whether or not there is anything to say,
> and they are written to look thorough rather than to be read — so a file gains three
> hundred lines and no information, and reviewers wave it through because rejecting a
> docstring feels like rejecting diligence. Work sentence by sentence: cover the
> signature, read one sentence, and ask whether it told you anything the signature did
> not. `user_id (int): The user id` did not. Cut restated summaries, restated parameter
> names, restated types, and `Returns:` lines that repeat the return annotation. Rewrite
> convoluted register — "is responsible for handling the calculation of" is "returns";
> find the verb, and cut the wind-up before it.
> **"Docstring" means the language's equivalent, in every language** — Python
> `"""..."""`, C# `/// <summary>`, Doxygen `/** @brief */`, Javadoc, JSDoc/TSDoc, Go doc
> comments, Rust `///`, YARD, Swift markup. The bloat is identical across all of them;
> only the syntax changes.
> **Python, C# and C++ are the languages this skill claims.** In any other, propose a
> rewrite only if you can name the convention and the tool that enforces it, or confirm
> nothing does; otherwise report the count and the pattern and let the user decide. This
> is not timidity — Go *requires* the restatement, Rust `///` can compile as a test, C#
> and Java tags can be build inputs, and none of that is visible in the comment text.
> **And for ordinary comments in an unclaimed language, an unrecognised line is a KEEP,
> not a DELETE.**
> **Read the whole "Language traps that reverse the rule" section of `docstrings.md`
> before touching any docstring**, and do not work from this summary — it is a summary,
> and summaries lose the exceptions that matter. In outline: Go doc comments are *supposed* to restate the
> identifier; Rust `///` fenced blocks compile and run as tests; C#, Java and Rust doc
> tags can be build inputs under warnings-as-errors; UE5 `/** */` above `UPROPERTY` is
> the designer-facing tooltip; **JSDoc `{type}` in a `checkJs` project is the only type
> information in the file**; and sometimes the docstring *is* the program —
> `argparse(description=__doc__)`, `click`, `docopt`.
> **On a docstring, TIGHTEN is almost always the right verdict and DELETE almost always
> is not.** Many repos require a docstring on every public symbol and enforce it with
> `pydocstyle`, `ruff` D-rules, Doxygen or XML-doc warnings-as-errors, so deleting one
> breaks a build. Check whether anything else in this repo's public API goes undocumented
> before proposing a deletion.
> **Report docstrings grouped per file** — a count, two exemplars, one rewrite pattern —
> not one finding per docstring. Forty P3 entries is how a report stops being read.
> **Grouping is how you report; it is not how you hand over.** Every verdict you actually
> propose acting on — each DELETE, each TIGHTEN with its rewrite — carries the **same
> required `anchor:` / `occurrence:` / `of:` / `evidence:` fields Agent A uses**, on the
> same terms: `occurrence` and `of` count matching lines of the file, and `evidence:` is
> `rewrite, nothing removed` for a TIGHTEN. A KEEP needs none of them; it is not going
> anywhere. Group the *narrative* — one count and two exemplars per file — and attach the
> fields to the exemplars you are proposing. Without them the item reaches the executor
> with no line to match at, fails the first locating rule, and is reported stale — so the
> tightening the user approved silently does not happen.
> You judge whether a comment earns its space, not whether it is true. If you suspect a
> comment or docstring is factually wrong about the code, say so in one line alongside
> your verdict and move on — another agent owns that question.

## Agent C — documentation and header drift

Dispatch **only** when the diff touches a documentation file (`*.md`, `docs/`,
`README*`, `CHANGELOG*`), **adds a file**, **or** changes a public surface: CLI flags,
exported or public names, config keys, install or run commands, public signatures,
version or dependency requirements. Otherwise skip it and say so in one line in the
report. There is no reason to pay for a third agent on a diff that renames a local.

> Your question is whether the documentation is **true**, not whether it is well written.
> Three directions:
> **(1) The change falsified a doc.** The diff altered behaviour that a documentation
> file describes, and the doc was not updated. Find the docs that describe the changed
> code — that search is a verification lookup, uncapped, and produces no finding of its
> own.
> **You may report a doc file the diff never touched, and this is the only place in this
> skill where that is allowed.** The bounds are absolute: report it only when a specific
> line of the diff makes a specific line of the doc false, and **cite both**. No general
> quality review of untouched docs — not "this section is vague", not "this reads
> promotionally", not "this is missing a section". Only "line X makes line Y false." If
> you cannot name both lines, you do not have a finding.
> **Never these, however cleanly they pass the test above:** `CHANGELOG*`, release notes,
> and ADRs — "in 2.3.0 we added `fetchUser`" is a true statement about what shipped, and
> "correcting" it makes the history lie. Localized or translated doc trees (`docs/ja/`,
> `*.de.md`, anything under an i18n path) — the author usually cannot read the edit, and
> translation tooling owns those files. Report both categories in one sentence if they
> matter; never propose the edit.
> **Cap it at five files.** One rename can falsify a line in twenty documents and every
> finding passes the citation test individually — which turns a one-line change into a
> twenty-file documentation diff, the exact "diff nobody can review" this skill opens by
> refusing. Past five affected files, stop listing and say: *"this rename touches N doc
> files; want a documentation pass as its own change?"* That is a gate, like the header
> gate, and for the same reason: it is a separate piece of work that deserves its own
> review.
> **(2) A doc in the diff claims something the code does not do.** Doc files the diff
> *does* touch get the full treatment, including the Documentation section of
> `$WINNOW/references/core-patterns.md`. **This includes docstrings**, and
> `$WINNOW/references/docstrings.md` is the file that describes their shapes — a docstring
> describing behaviour the function no longer has, an `Args:` entry for a parameter that
> was renamed or removed, a documented `Raises:` the body cannot reach, a `Returns:`
> describing the old return shape. Another agent judges whether those docstrings are too
> wordy; you judge only whether they are true. A confidently wrong docstring outlives the
> code it described and is believed by every reader after.
> **(3) File headers.** Two separate questions, and keep them separate in your output.
> *Is the header true?* A `@file` or `@brief` describing what the file used to do, or a
> header naming a filename that no longer matches after a rename. Same rule as any other
> doc: cite the header line and the thing that falsifies it.
> **Authorship, copyright and date lines are not yours, even when they are stale.**
> `@author`, `@copyright`, `@date`, `@since`, `@license` — route every one of these to
> the header gate in Step 4, never to an ordinary truth finding with a proposed rewrite.
> Changing `@author Alice` to `@author Bob` because Bob edited the file is a stronger
> assertion about ownership than adding boilerplate is, and the gate exists precisely to
> keep this skill from making that assertion on the user's behalf. It is also frequently
> wrong: on most teams the header records who wrote the file, not who last touched it,
> and git already knows the difference.
> *Does the header match the repo's convention?* Establish the convention first by reading
> the **top 15 lines of a sample of existing files of the same type**, on this branch and
> on the base. That sampling is a verification lookup, not a review — you are extracting
> a shape, not judging those files — so the three-file convention cap does not apply to
> it and nothing you see there becomes a finding. Then compare: do the diff's files carry
> that header, a different one, or none?
> **Sample first-party files only.** Exclude `Plugins/`, `Packages/`, `Assets/Plugins/`,
> `Assets/ThirdParty/`, `Source/ThirdParty/`, `vendor/`, `third_party/`, `node_modules/`,
> and anything else the repo did not write. The scanner's vendor filter governs what it
> *scans* and does nothing about where you sample — and in a Unity or UE5 project those
> directories hold more `.cs`/`.h` files than the user's own code, so a naive sample
> concludes the convention is a **vendor's** copyright line and the gate offers to stamp
> someone else's ownership claim onto files the user wrote. The sample decides what the
> gate proposes, so a wrong sample makes the gate's approval meaningless. If the sample
> is not clearly uniform across first-party files, there is no convention to report; say
> that instead of picking the mode.
> **Report whose notice it is and what year it carries**, not just that a header is
> missing. "The other files say `Copyright 2019 Acme Ltd`" is a fact the user needs before
> answering, because a header sampled from 2019 files asserts 2019 on files created this
> year, and neither the name nor the date is yours to choose.
> **Report the conflict. Never propose unifying headers on your own** — see the gate in
> Step 4. And never propose touching a header on a file the diff did not add or modify:
> fixing the repo's header consistency is not this review's job, and a diff that rewrites
> 200 file headers is the most reviewer-hostile output this skill could produce.
> Severity: **P2** for a stale doc line, and for a header that states something *wrong* —
> the wrong license, another party's copyright. **P3** for a *missing* header, license
> ones included, and for a divergent style or doc header. **P1** when a stale line is an
> install command, a run command, or a security claim — someone will follow it, it will
> fail, and they will not know why. **P1 also when the repo enforces headers in CI** —
> Apache RAT, `addlicense -check`, checkstyle `Header`, a `license-eye` action: then a
> missing header is a red build, which is a fact about this repo rather than a judgment
> call, and one look for that config settles it.
> **Missing is not the same as wrong, and only one of them is P2.** Copyright subsists
> without notice under Berne, so a new internal file carrying no boilerplate has close to
> no legal consequence — calling that a compliance gap overstates it, and P2 is inside
> "fix all", which is exactly where a header edit must never be. A header asserting the
> wrong licensor is a misstatement of fact and stays P2.
> Return findings as `docpath:line — the claim → the diff line that falsifies it
> (path:line) → proposed rewrite`, with the same required `anchor:` / `occurrence:` /
> `of:` / `evidence:` fields Agent A uses, on the same terms — a doc line is located at
> execution time by exactly the same machinery, and doc files are the ones most likely to
> have shifted since you read them. **Establish `occurrence` and `of` by counting matching
> lines yourself**: a doc the diff never touched was never scanned, so there is no JSON
> row to copy them from, and a repeated line like `Call \`Dash.Charge()\` before the
> cooldown elapses.` is exactly the shape that repeats in a document. Report
> header-convention conflicts separately, as a count and a sample, not as one finding per
> file.

## Agent D — performance notes

Dispatch **only** when the diff adds or modifies a loop, comprehension, or recursive
call; puts code inside a per-frame, per-tick, per-request or per-item entry point; adds
I/O, a query, a lock, or an allocation inside either; or changes a data structure or
algorithm on a path already marked hot. Otherwise skip it and say so in one line in the
report.

> **Read `$WINNOW/references/performance.md` before anything else.** It is the whole
> standard for this pass and the rest of this prompt is a summary of it. Read the language
> file matching the diff as well.
> **Nothing you produce is ever applied.** Your output is a notes document, not findings.
> It does not enter the report, it does not enter the fix plan, and no edit will be made
> from it. That is not a comment on the quality of your notes — it is the honest
> consequence of the fact that you cannot measure. Write accordingly: a note is a
> hypothesis offered to a human, not an instruction.
> **The gate: name the frequency, or you do not have a note.** Every note states how often
> the code runs and how you established that — the enclosing `Update()`, the request
> handler it sits in, the loop bound, the caller you traced. If you cannot finish the
> sentence "this runs N times per X", stop. What you have is a preference about how the
> code is written, and Agent A owns that question. Startup and once-per-process code
> cannot pass this gate and are therefore ineligible, however wasteful they look.
> **No micro-optimization and no readability trades.** If the win is invisible without a
> profiler, or the faster form is harder to read and you have not measured, it is not a
> note.
> **Do not repeat the scanner.** `perframe-lookup`, `perframe-linq`, `expensive-lookup`,
> `pass-by-value` and `eager-log-format` are ordinary findings in the main report and the
> fix plan already. Noting them here double-counts them.
> **Never touch a trust boundary**, and never report a comment or dead code — those belong
> to B and A.
> **Return format**, one entry per note, and `measured:` is required:
> ```
> - path:line — what
>   frequency:  <how often it runs, and how you know>
>   reasoning:  <why it costs more than it needs to>
>   suggestion: <the change, or "unclear — flagging the cost only">
>   measured:   <the benchmark you ran, or the word `no`>
> ```
> `measured: no` is the expected answer and is not a defect in the note. Only write a
> benchmark here if you actually ran one.
> **You will be given `.code-winnow/perf-declined.md` if it exists.** Skip any note
> matching an entry — match on path plus anchor text and ignore the line number, since
> lines shift — and report the count you skipped rather than listing them. The user
> already answered those.
> Order notes by the strength of the frequency argument, not by guessed impact. Guessed
> impact is a second unmeasured number stacked on the first.

## Agent E — silent failure and fragility

Dispatch whenever A is dispatched. There is no trigger condition: a one-line change is
enough to add a swallowed exception.

> **Read `$WINNOW/references/fragility.md` before anything else**, plus
> `$WINNOW/references/core-patterns.md` — its directive-comment table is half of what you
> are checking — and the language file matching the diff.
> **The gate, and both halves are required. Name how it breaks, and name why the suite
> stays green.**
> *How does it break?* What goes wrong, when, and under what condition. "This is fragile"
> is not a failure mode. "On a save written before this change, `dashCharges` deserializes
> to 0 and the player cannot dash" is.
> *Why does no test catch it?* The suite only creates fresh saves. Nothing exercises the
> throw path. The failure needs two threads.
> **If a test would catch it, it is not your finding** — it is an ordinary bug, and bug
> hunting is out of scope here. **If you cannot say how it breaks, it is a style opinion**,
> and Agent A owns those. Hand it over or drop it. A report full of unfalsifiable "this
> might race" warnings is worse than one that omits them.
> **The committed-credential class in (2) below is the one thing that does not answer the
> gate in those words, and it is not exempt from it — it answers in different ones.** *How
> it breaks:* the credential is valid, published, and usable by anyone who can read the
> repo. *Why no test catches it:* no suite has ever failed over a key that works. Do not
> drop one for failing to name a runtime failure mode; a leaked key is the purest form of
> the thing this pass exists for, a defect with no signal at all.
> **This is not a security review and you must not go looking for vulnerabilities.** Two
> security-shaped things are yours, and only two. Everything else in that direction is out
> of scope no matter how it looks.
>
> **(1) A protection this diff removed.** A validation or bounds call deleted from a
> handler, an auth or ownership assertion dropped, `verify=True` → `False`, `strict` or
> `validate_certs` disabled, an escape or sanitize call gone, a timeout or size limit
> removed, or a newly *added* `# nosec` / `# noqa: S…` suppression. **Quote the removed
> line from the diff's `-` side and name the caller you traced.** If you cannot show the
> line the diff removed, you do not have this finding — you have a suspicion about existing
> code, which is out of scope. P1 for a removed check on a reachable path, P2 for a
> newly-added suppression.
>
> **(2) A credential the diff committed.** The scanner already catches the self-identifying
> vendor formats — `AKIA…`, `ghp_…`, `glpat-…`, `sk_live_…`, `AIza…`, a
> `-----BEGIN … PRIVATE KEY-----` block — and you do not repeat those. **Yours is the half
> a pattern cannot reach: a named credential assigned a literal.** The scanner's rule for
> that matches a fixed keyword list (`pass`/`password`/`passwd`, `secret`, `api_key`,
> `auth_token`, `access_token`, `client_secret`, `private_key`, `credential(s)`,
> `connection_string`, `bearer`) on a word boundary before a bare separator, so it sees
> `password = "…"` and misses two whole classes: **every prefixed or quoted spelling** —
> `DB_PASSWORD = "…"`, `db_password = "…"`, `smtp_password: "…"`, every
> `"db_password": "…"` in a JSON or YAML config — and **every credential named with a word
> outside the list**, among them `token` on its own, `api_secret`, `access_key`,
> `passphrase` and `pwd`. Those are where a committed password actually lives, under the
> name it is actually given. Read the added lines and say whether the value is a credential.
>   - **You are reading, not scoring.** Do not run entropy in your head. A hash, a UUID, a
>     base64 blob, a git sha and a minified bundle all look random and none of them is a
>     secret; `references/core-patterns.md` refuses an entropy heuristic on purpose, and an
>     agent that reinvents one rebuilds the noise that rule exists to prevent. The question
>     is whether the *name* says credential and the *value* is a real one — not whether the
>     value looks random.
>   - **Placeholders are not findings.** `${DB_PASSWORD}`, `{{ vault_pw }}`, `<your-key>`,
>     `changeme`, `xxxxxxxx`, an obviously redacted value, a documented vendor example.
>     Neither is a value read from the environment — `os.environ[...]`,
>     `Configuration["…"]`, a secrets manager call — which is the correct pattern and must
>     never be flagged.
>   - **Severity P1, and it does not demote in a test or prose file.** Every other universal
>     rule here demotes in a fixture; this one does not, because a test directory is where
>     keys most often leak and a live credential is not test data.
>   - **Never propose a fix, at any severity.** This is the one finding class that is
>     reported and never patched. Deleting the line does not un-leak the key — it is already
>     in the object store, in every clone, and in every CI cache that fetched it. Write
>     `fix: out of scope — rotate the credential; deleting the line leaves it in history`
>     and propose nothing. A patch here would hand the user an all-clear they have not
>     earned, which is worse than not finding it.
>   - **Diff lines only, like everything else.** A credential sitting on a line this change
>     did not touch is not yours. Say nothing, or note it under pre-existing if you happened
>     to have the file open — do not sweep the repo for keys. That is the security audit
>     this skill refuses.
>   - **One line, one finding.** If the scanner already reported that exact line as
>     `committed-secret`, it is in the report — do not file a second entry for it. If you
>     think its severity is wrong (its assignment branch demotes in a test or prose file,
>     because it is guessing from a name where you have read the value), say so *on that
>     finding* rather than raising a duplicate. Two entries for one leaked key is the same
>     defect as X3 and it makes the count untrustworthy.
> **You outrank Agent A on deletions.** A proposes removing code; you are the reader who
> knows what removal breaks. When you see a line that is load-bearing in a way the compiler
> cannot see — a GC root, a directive comment, a type carrier, a trust-boundary check, a
> registration anchor, a side-effect import — say so plainly and name the mechanism, whether
> or not A flagged it. Step 3.5 gives you the deciding vote.
> **Severity: P1** for silent corruption, silent data loss, a removed protection on a
> reachable path, a committed credential, or any failure with no observable signal. **P2**
> for fragility that surfaces loudly but that nothing tests, and for a newly-added
> suppression. **You should essentially never produce a P3** — if it is cosmetic, it failed
> the gate and it is A's.
> **Many of your findings will not be fixable by this skill, and that is expected.** A fix
> here must preserve behaviour. Adding a missing `await`, narrowing a catch, restoring a
> removed validation call, stopping a coroutine in `OnDisable` — those are fixable. A save
> migration, a cache invalidation strategy, a locking scheme — those are design decisions,
> and **every committed credential** is one of these by construction, since the repair is a
> rotation rather than an edit. Write `fix: out of scope — <why>` and propose nothing. Do
> **not** lower the severity because you cannot fix it; it is reported at P1 either way.
> **Return format**, and the first three fields are required on every finding:
> ```
> path:line — what
> breaks:   <how and when it fails — runtime / build / CI / only under condition X>
> no test:  <why the suite stays green>
> fix:      <the behaviour-preserving change, or "out of scope — <why>">
> ```
> On any finding whose fix is *not* out of scope, add the same required `anchor:` /
> `occurrence:` / `of:` / `evidence:` fields Agent A uses, on the same terms — those items
> enter the fix plan and are located by exactly the same machinery. A finding marked
> `fix: out of scope` needs none of them; nothing is going to be located.
