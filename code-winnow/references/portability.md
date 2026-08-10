# Running outside Claude Code

Hard dependencies: **Python 3.9+** and `git`. Everything else is a companion skill, and companion skills are checked and *reported*, not silently worked around.

3.9 is the floor because `duplicate-test` for Python files needs `ast.unparse`, which landed in 3.9. On 3.8 that rule is skipped and reports nothing — indistinguishable from a suite with no duplicates — and a dependency that degrades into a silent gap is worse than one that is simply required.

## Check first, then tell the user

**After Step 0, before Step 1** — this check reads and may write `.code-winnow/substitutions.md`, and Step 0 is what keeps that directory out of the diff under review. Check which companion skills are actually present in this runtime. Anything missing gets one compact notice — once, before the review starts, not discovered halfway through.

The reason to surface it rather than quietly degrade: the user may have the thing under a different name, may want it installed, or may not care. All three are reasonable, and only they know which. Silently taking the weakest option and mentioning it in a footnote at the end wastes the run.

Before writing the notice, do the equivalence sweep below. A skill that fills the role under a different name is the best outcome available and should be offered first.

Format the notice like this and then wait:

```
Not installed here: superpowers (parallel dispatch, code review), karpathy-guidelines.

Already installed, looks equivalent:
  - code-simplify -> the simplification role (refactors for clarity, preserves behavior)

  1. Use code-simplify for that role, install the rest — I can run the commands.
  2. Run degraded — judgment pass becomes self-review, no cold second pass. Everything else works.
  3. Point me at your own equivalents and I'll use those instead.

Say which, or "go" for option 2.
```

Keep it to that. Do not explain each missing skill in a paragraph, do not repeat the notice at each step, and do not re-ask on the next run in the same repo if the answer is already recorded (see below).

If nothing is missing, say nothing at all.

## Do not wait for an answer that is not coming

"Then wait" assumes someone is there. The run is unattended when any of these hold:

- the run was started by a schedule, a hook, a cron job, or CI
- the runtime has no way to deliver a question (headless, piped stdin, batch)
- the user has already said they are stepping away, or a previous question in this session went unanswered

Take option 2 immediately, without asking, and put the notice at the top of the report instead of in the chat, phrased as what was unavailable and what it cost. A blocked run has failed more completely than a degraded one — the degraded review still lands, and the user can re-run it with the companions installed if the gap mattered.

**This licenses proceeding without an answer. It does not license editing without an approval.** An unattended run stops after the report **and the fix plan** are written — see the unattended table in SKILL.md. The plan is a report artifact, not permission: an unattended one carries `Status: UNAPPROVED` and the cold Step 5 entry refuses it. Nothing in "do not wait" reaches an edit, because the missing answer there is not a preference between equivalent paths; it is consent to delete lines from files git cannot restore.

One carve-out, and it is narrow. `code-winnow: apply <plan>.fixplan.md` **is** Step 5 and nothing else, and it may run headlessly — against a plan a human already approved. The approval happened when the plan was written; re-demanding it in the session that merely executes would make the whole clear-and-resume path impossible. A plan marked `UNAPPROVED` is refused in exactly that situation, which is what keeps the carve-out from swallowing the rule.

## Capability matrix

| Capability | Detect by | Degraded path | Installable? |
|---|---|---|---|
| Subagents / parallel dispatch | A task-spawning tool exists | Run the passes serially yourself, in order: A, B, C, D, E. Say once that the judgment pass was self-review. Also removes rung 2 of the Step 4b ladder — see below. | No — runtime feature |
| Context clearing | The runtime offers `/clear` or an equivalent the *user* can invoke | Rung 1 of the Step 4b ladder is unavailable. Fall to rung 2, then rung 3. | No — runtime feature |
| `superpowers:*` | Listed in available skills | Their operative content is summarized inline in SKILL.md Steps 3 and 6. | Yes |
| `andrej-karpathy-skills:karpathy-guidelines` | Listed in available skills | Inline digest in SKILL.md Step 5. | Yes |
| A simplification skill | Listed in available skills | Note residual complexity as a P2 finding instead of restructuring it. | Sometimes — see below |
| Shell / file writes | Try it | Ask the user to run `scan.py` and paste the output; report inline instead of writing `.code-winnow/`. **No writes means no backup and no fix plan, which means no edits** — end at the report. | No |

## Model tiers — spend the capable model where it decides something

Some runtimes let the dispatcher choose a model per subagent. Where that exists, the
supervisor stays on the strongest model available and most of the subagents do not need
to. This is an optimisation, not a requirement: a runtime with one model runs every pass
on it and nothing here changes.

**The supervisor is never tiered down.** Step 3.5 arbitrates ten conflict classes and
grades comment evidence against a four-bucket rule where two of the buckets exist
precisely because the obvious reading is wrong. Step 6's deletion-safety pass is the only
check in the run that looks at what is *gone*. Both are judgment over other agents'
output, which is the work that most rewards a capable reader.

| Pass | Tier | Why |
|---|---|---|
| **S** — scope | **Supervisor's tier** | It decides what is *eligible* to be judged, which decides more than any verdict does. A boundary drawn one file narrow is invisible in the output: the file is simply never reviewed, by anyone, and nothing says so |
| **A** — chaff | Mid | High volume, and it applies a written standard to many lines. `core-patterns.md` carries the judgment; A applies it |
| **B** — comments and docstrings | Mid | The highest-volume pass in the skill, and the most mechanical: read a comment, decide whether it says anything the code does not |
| **C** — doc and header truth | Mid | Mostly lookup — does this doc line still match that code line |
| **D** — performance | Mid | Its gate is a frequency claim it must attach evidence to, and an unsupported note is dropped at Step 3.5 anyway |
| **E** — silent failure | **Supervisor's tier** | Its veto is the only thing between a confident deletion and a runtime break no test catches, and it must *name the mechanism* rather than object. A weaker reader fails by not objecting, which looks exactly like agreement |
| Step 4b rung 2 fix agent | Mid, or lower | It executes an approved list located by normalised anchor. The plan is the whole permission, `evidence:` is re-run before each edit, and the anchor rules refuse rather than search |

**The asymmetry is what the table encodes.** A and B failing weakly produce a thinner
report — you notice, because the findings are not there. S and E failing weakly produce a
report that looks complete and is not, and neither failure leaves a trace. Spend the
capable model where a miss is silent.

**Do not hardcode model names in a run.** Ask the runtime what it offers and pick by
tier, because published line-ups change faster than this file does. As of writing, the
Claude tiers are Opus 5 for the supervisor, Sonnet 5 for the mid rows, and Haiku 4.5 for
the fix executor; other vendors ship an equivalent three-way split under their own names.
A name that has aged out is worse than no guidance, since it fails at dispatch rather
than at review.

**This table is published as data as well as prose.** `$WINNOW/scripts/passes.py --json`
emits every pass with its tier, its trigger condition, the reference files it names and a
fully assembled prompt — for the dispatcher that can route passes across providers, which
is where per-pass tiering earns the most and where five readings from one model family
share the blind spots a panel exists to remove. It **mirrors** the rows above rather than
restating them: `tests/test_passes.py` parses this table and fails when the two disagree,
so a tier changes here and nowhere else.

**Two things in that output are defined as data rather than mirrored**, because no table
above holds them. `tiers` says what the two band names *mean* — both relative to what the
caller has enrolled, never a model or a vendor tier, since a dispatcher that reads
`supervisor` as some fixed top tier asks for a model the caller may not be able to route
to and fails at dispatch. `merge` declares Step 3.5: supervisor tier, not delegable, and
the consumer of every file the passes write. A caller that fans out the passes and finds
no declared reduce has built half the design — six agent files and nothing that reads
them. Both are additive metadata; a runtime that ignores them behaves exactly as before. The prompts themselves are never copied — they
resolve from markers in `agent-prompts.md`, and a marker that goes missing is a refusal
naming the pass, never a shorter prompt.

**Say what you did.** If any pass ran on a different tier from the supervisor, put one
line in the report header — the same reason the report already says when C or D was
skipped, or when S was self-drawn. A reader deciding how much to trust a thin Agent B
result needs to know it ran on a smaller model.

## The Step 4b ladder

Three ways to apply an approved fix plan, in order of preference. All three read the same artifact, so the choice costs nothing to defer:

| Rung | Needs | What happens |
|---|---|---|
| 1 | A user-invocable context clear | Offer it, print the resume line, stop. The user clears and pastes; a fresh session enters at "Entering at Step 5 cold". |
| 2 | Subagents | Dispatch a fix agent with **only** the fix plan and the generation-discipline skill. The main agent supervises and does not edit. |
| 3 | Neither | Apply in place. Say so once. |

**Never skip a rung silently.** Rung 1 is a user action and cannot be taken for them: offer it, and if they decline or do not answer, drop to rung 2. Do not clear anything yourself — no runtime here gives an agent that power, and a skill that claims to have cleared its own context has misreported what it did.

The ladder is a preference, not a requirement. Rung 3 applies the same fixes with the same backup and the same verification; what it loses is context headroom, which affects how well a long fix loop goes, not whether it is safe.

Do not assume any particular skill ships with any particular runtime. Claude Code installs vary per user and per project — a skill being absent tells you nothing about where you are running, so never infer the host from a missing capability. Detect, report, degrade.

## Look for an equivalent before offering to install

Every runtime ships its own skill set, and the roles this one needs are common enough that something usually fills them already under a different name. Installing a second copy of a capability the user already has is a worse outcome than using theirs.

So before proposing an install, read the available skills list and match **by role, not by name**:

| Role needed | What fills it | Look for |
|---|---|---|
| Simplification | Restructures for clarity without changing behavior | simplify, refactor, cleanup, code-quality, tidy |
| Cold review | Reviews written code from a reader's position | code-review, reviewer, critique, audit, PR review |
| Parallel dispatch | Runs independent tasks concurrently | parallel, dispatch, subagent, fan-out, orchestrat- |
| Generation discipline | Rules for how code should be written and changed | guidelines, best-practices, coding-standards, style |
| Verification | Requires evidence before a completion claim | verify, validation, test-first, definition-of-done |
| Debugging method | Root cause before fix | debug, troubleshoot, RCA |

**The deletion-safety pass in SKILL.md Step 6 is not the fallback for the cold-review row.** It runs on every run, before any cold review, and it is scoped to the lines the run removed. A cold reviewer reads the code that is there now and cannot see what is gone; the two passes answer different questions and neither substitutes for the other. Treating the checklist as a stand-in for a missing companion had it backwards — the better-equipped runtime would have got less safety.

Two rules for the matching:

**Read the candidate's own description before proposing it.** Names lie in both directions. A skill called `cleanup` may format files; a skill called `taste` may be exactly the review pass you wanted. The description is what to match against, not the slug.

**Propose, never adopt silently.** Say which skill you think fills which role and let the user confirm. You are guessing from a one-line description, and a wrong guess quietly changes what the review does — the user finds out only from the output, which is the worst moment to find out. Once confirmed, record it in `.code-winnow/substitutions.md` so the question is settled for that repo.

If a role has no candidate, say so plainly for that role rather than stretching a poor match to fill the table. "Nothing here does the cold-review pass" is useful; proposing a linter for it is not.

## Install paths

Only offer to install where the runtime actually supports it. Claude Code plugins and skills-ecosystem packages install differently:

```
/plugin marketplace add anthropics/claude-plugins-official
/plugin install <name>@claude-plugins-official

npx skills add <owner>/<repo> --skill <skill-name>
```

These commands change over time. Confirm the current one for the specific package before running it rather than pasting from here — an install command that fails halfway is worse than telling the user to install it themselves.

## User substitutes

If the user names their own equivalent ("use my `deep-review` skill instead of requesting-code-review"), take it, and record it so the next run does not ask again:

```
.code-winnow/substitutions.md

- requesting-code-review -> deep-review (user, 2026-08-02)
- karpathy-guidelines -> team CONTRIBUTING.md sections 2-4 (user, 2026-08-02)
```

Read that file at the start of the capability check and treat anything listed as satisfied. A substitute the user chose outranks the default — do not second-guess it or re-suggest the original.

## What must not depend on the host

Both scripts are stdlib-only, never import outside the standard library, and never call the network. **The scanner writes no files at all** — it prints to stdout and stderr, and every `.code-winnow/` artifact exists because a step in SKILL.md redirected it there. `scripts/backup.py` is the one deliberate exception: copying files *is* its job, it writes only into the destination it is given, and it refuses rather than writing when anything about the plan or the destination is wrong. Keep the scanner that way — it is the one part guaranteed to behave identically on Hermes, Codex, Cursor, a `python3` call in CI, or a model with no tools at all reading pasted output.

It also resolves every path against `git rev-parse --show-toplevel` rather than the cwd, so it can be invoked from anywhere in the tree. Keep that too: the failure it prevents is the silent one, where the scanner opens nothing, finds nothing, and prints a clean bill of health. Anything it cannot read goes into `errors` with `"complete": false` and exit code 2.

SKILL.md avoids Claude-Code-only syntax. Slash commands do not appear on the required path; no plugin-namespaced paths are load-bearing; every reference file is named explicitly where it is needed rather than assumed auto-loaded. The scanner is invoked through a `$WINNOW` variable holding this skill's directory, because a relative `scripts/scan.py` only resolves when the cwd is the skill folder — which is never where the repo is.

## The floor

With zero companion skills, the run is still complete: exclude the workspace → resolve scope → scan → judgment passes → conflict check → report → approval → fix plan → back up → fix → verify. The companions improve the judgment and the review. They are not load-bearing, and the review is worth running without them.

The conflict check needs nothing at all — it reconciles outputs you already have. On a serial run it matters more, not less: one agent doing every pass is likelier to produce findings that quietly contradict each other, because nothing forced the contradiction into the open.

**One class degrades further than the others on a serial run, and SKILL.md Step 3.5 says so: Agent E's veto over A's deletions.** Its value comes from A's proposal and E's objection being formed by two readers who cannot see each other's reasoning. Run serially, both come from you, minutes apart, and the objection arrives after you have already argued yourself into the deletion. The degraded path is to do E's reading of A's proposed removals as a **separate pass against `fragility.md`**, before writing either into the report — deliberately, because a parallel run gets it structurally and a serial one does not get it at all.

The backup is load-bearing, though. Without a shell or a writable filesystem you cannot make one, and then the run ends at the report — see SKILL.md Step 5a. Report the findings, say the fixes were not applied because no restore point could be written, and let the user apply them by hand.
