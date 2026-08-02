# Running outside Claude Code

Hard dependencies: Python 3.8+ and `git`. Everything else is a companion skill, and companion skills are checked and *reported*, not silently worked around.

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

**This licenses proceeding without an answer. It does not license editing without an approval.** An unattended run stops after the report is written — see the unattended table in SKILL.md. Nothing in "do not wait" reaches Step 5, because the missing answer there is not a preference between equivalent paths; it is consent to delete lines from files git cannot restore.

## Capability matrix

| Capability | Detect by | Degraded path | Installable? |
|---|---|---|---|
| Subagents / parallel dispatch | A task-spawning tool exists | Run the passes serially yourself. Say once that the judgment pass was self-review. | No — runtime feature |
| `superpowers:*` | Listed in available skills | Their operative content is summarized inline in SKILL.md Steps 3 and 6. | Yes |
| `andrej-karpathy-skills:karpathy-guidelines` | Listed in available skills | Inline digest in SKILL.md Step 5. | Yes |
| A simplification skill | Listed in available skills | Note residual complexity as a P2 finding instead of restructuring it. | Sometimes — see below |
| Shell / file writes | Try it | Ask the user to run `scan.py` and paste the output; report inline instead of writing `.code-winnow/`. **No writes means no backup, which means no edits** — end at the report. | No |

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

The scanner is stdlib-only, never imports outside the standard library, never calls the network, and never writes outside `.code-winnow/`. Keep it that way — it is the one part guaranteed to behave identically on Hermes, Codex, Cursor, a `python3` call in CI, or a model with no tools at all reading pasted output.

It also resolves every path against `git rev-parse --show-toplevel` rather than the cwd, so it can be invoked from anywhere in the tree. Keep that too: the failure it prevents is the silent one, where the scanner opens nothing, finds nothing, and prints a clean bill of health. Anything it cannot read goes into `errors` with `"complete": false` and exit code 2.

SKILL.md avoids Claude-Code-only syntax. Slash commands do not appear on the required path; no plugin-namespaced paths are load-bearing; every reference file is named explicitly where it is needed rather than assumed auto-loaded. The scanner is invoked through a `$WINNOW` variable holding this skill's directory, because a relative `scripts/scan.py` only resolves when the cwd is the skill folder — which is never where the repo is.

## The floor

With zero companion skills, the run is still complete: exclude the workspace → resolve scope → scan → judgment pass → report → approval → back up → fix → verify. The companions improve the judgment and the review. They are not load-bearing, and the review is worth running without them.

The backup is load-bearing, though. Without a shell or a writable filesystem you cannot make one, and then the run ends at the report — see SKILL.md Step 5a. Report the findings, say the fixes were not applied because no restore point could be written, and let the user apply them by hand.
