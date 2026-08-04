# code-winnow workspace

Current round: **ROUND** — <fill: branch @ side vs base @ sha (scope), YYYY-MM-DD HH:MM>

|   | Report | What it answers | This round |
|---|---|---|---|
| — | [report.md](ROUND/report.md) | merged findings, severities, what to fix | <fill: counts> |
| — | [fixplan.md](ROUND/fixplan.md) | the approved edit list | <fill: counts> |
| — | [notes.md](ROUND/notes.md) | performance notes — never applied | <fill: counts> |
| S | [agent-S.md](ROUND/agent-S.md) | where is the feature boundary? | <fill: counts> |
| A | [agent-A.md](ROUND/agent-A.md) | does this code line earn its place? | <fill: counts> |
| B | [agent-B.md](ROUND/agent-B.md) | does this comment earn its space? | <fill: counts> |
| C | [agent-C.md](ROUND/agent-C.md) | is the doc still true, and does the header match? | <fill: counts> |
| D | [agent-D.md](ROUND/agent-D.md) | what did this change make slow? | <fill: counts> |
| E | [agent-E.md](ROUND/agent-E.md) | how does this break silently? | <fill: counts> |

To apply the plan: `code-winnow: apply .code-winnow/ROUND/fixplan.md`

Previous rounds: <fill: links, or "none">

## How this workspace works

This file is rewritten in full from the skill's template at the end of every
round — never edited in place, so there is no half-updated state and no marker
to preserve.

**Links are relative to this file's directory.** `ROUND/report.md`, never
`.code-winnow/ROUND/report.md`; the second renders perfectly and 404s on click.

**A pass that did not run keeps its row and loses its link** — the bare
filename as plain text, and `not dispatched` in the last column. Deleting the
row would make a skipped pass indistinguishable from a pass this skill does not
have.

**The middle column is template text and is always correct.** The right-hand
column is filled at Step 4 from counts the supervisor already holds. It may end
up blank when a count is genuinely unavailable; a surviving `<fill` marker is a
different thing and the tests fail on it. Blank says "not known"; the marker
says the agent stopped halfway.

Everything about a round lives in that round's own folder, and nothing is ever
moved between them. The files here are:

| | |
|---|---|
| `README.md` | this index |
| `env.sh` | the run in progress: `$WINNOW`, `$PY`, `$SCOPE`, `$STEM`, `$ROUND`, `$BACKUP`, `$SNAPSHOT` |
| `declined.json` | findings the user rejected. Persistent — delete a line to re-open the question |
| `perf-declined.md` | Agent D notes the user dismissed. Persistent |
| `substitutions.md` | companion-skill substitutes already chosen for this repo |
| `utils/` | helper scripts a run wrote, shared across rounds |
| `round-NN/` | one round each — open its `README.md` for what is inside |
