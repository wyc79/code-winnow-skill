# What is in this folder

One round of a code-winnow review. Everything about this round is here.

| File | Written by | What it is |
|---|---|---|
| `meta.json` | Step 2, by `scan.py --meta` | what this round compared to what |
| `report.md` | Step 4 | the merged findings — read this first |
| `fixplan.md` | Step 4b | the approved edit list; the only thing Step 5 may act on |
| `notes.md` | Step 4 | Agent D's performance notes, merged from `agent-D.md`. **Never applied** |
| `agent-S.md` … `agent-E.md` | Steps 1 and 3 | each pass's raw output, before merging |
| `scan.json` | Step 2 | the pre-fix scanner baseline. Step 6 reconciles against it |
| `scan-postfix.json` | Step 6 | the re-scan after the edits |
| `scan-preexisting.json` | Step 4 | `--whole-files`: untouched lines of the same files |
| `scan-vs-round-NN.json` | Step 4 | reconciliation against the prior round |
| `input.diff` | Step 3 | the exact bytes every judgment agent was given |
| `tests-before.txt`, `tests-before.list` | Step 5a | the suite before the first edit |
| `tests-after.list` | Step 6 | the suite after |
| `pre-fix/` | Step 5a | a copy of every file the plan names, before editing |
| `scratch/` | any step | working files. Nothing in here is an output |

**That list is exhaustive.** Anything a run generates that is not on it goes in
`scratch/`, and any script it writes goes in `../utils/`. The rule exists
because a run once left nine intermediate files at the workspace root — a
`.findings.tsv`, a `_comments_extract.txt`, a hand-rolled `_build_input.py` —
and no rule named them, so no rule constrained where they landed.

`meta.json` is the machine-readable answer to "what was compared to what". The
same fact opens every markdown file here as a three-line identity block, because
the filenames no longer carry it.

`report.md` and the `agent-*.md` files ship no template on purpose. A skeleton
would make an agent emit every heading whether or not it had anything to put
under one, and a structurally perfect report with hollow sections is harder to
catch than one with sections missing. Their shapes are in
`references/report-format.md` and `references/agent-prompts.md`.
