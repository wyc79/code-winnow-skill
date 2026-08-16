# Code-winnow — the review pipeline (Steps 1 – 4b)

Steps 1 through 4b. `SKILL.md` dispatched you here; read it first if you have not. **The scope rules, the unattended table, `Never touch` and the companion-skill list are there, they are stated only there, and they bind every step below.**

**Two things must already be true:** `$WINNOW` is resolved, and Step 0 has run — the `.code-winnow/` exclusion is in place and verified. If either is not, go back to `SKILL.md`.

This file ends at the fix plan. `$WINNOW/apply-and-verify.md` takes over at Step 5, and a run invoked as `code-winnow: apply <plan>.fixplan.md` reads that file *instead of* this one.

## Step 1 — Resolve the review scope

Let the scanner do it. `--scope auto` (the default) takes the **union of all uncommitted work**: staged, unstaged, and untracked files. If the working tree is clean it falls back to the branch diff against a discovered base.

**On a branch with commits *and* a dirty tree, `auto` reviews the uncommitted work only** — the fallback to the branch diff happens when the tree is clean, not otherwise. The scanner puts the gap in `warnings` (`this branch is N commit(s) ahead of 'main' - that work is NOT being reviewed`). **When you see that warning, ask** — "your branch has 3 commits I am not reviewing; want the whole branch (`--scope branch`) or just the uncommitted work?" It is one question and the two answers review different code.

**On the base branch itself, that fallback is correctly empty** — `main` diffed against `main` is nothing, so a clean tree on `main` yields no stem and no scope. That is not a broken setup and not a clean bill of health; it means you have to say what to compare against. Pass `--base <ref>`, or name the commit the work started from. This is the first thing to check when a run reports nothing, because it looks exactly like a clean tree from every field in the output.

```bash
cd "$(git rev-parse --show-toplevel)"
WINNOW="<absolute path to this skill's directory>"   # QUOTE IT — see below
SCOPE=""                                             # or: --scope branch --base develop

# Pick an interpreter that RUNS, not merely one that is on PATH.
# Already know the path? Set PY first and the probe is skipped.
for c in python3 python py; do
  [ -n "$PY" ] && break
  command -v "$c" >/dev/null 2>&1 && "$c" -c "" >/dev/null 2>&1 \
    && PY=$(command -v "$c")
done
[ -n "$PY" ] || { echo "no working Python on PATH — set PY to its absolute path:"
                  echo "  PY=/c/Users/me/miniconda3/python.exe"; exit 1; }

"$PY" "$WINNOW/scripts/scan.py" $SCOPE
```

Three things there are not stylistic. **Quote `WINNOW`** — unquoted, bash eats every backslash and a Windows path becomes garbage. **Test the interpreter, do not just locate it** — `command -v python3` finds the Microsoft Store stub, which exits 49. **Pin `$SCOPE` and pass it on every later scanner call** — each omission silently reviews a different thing. Step 2 writes all three to a file so no later block has to remember them.

**Do not replace this with a hand-rolled `git diff` ladder.** The scanner puts untracked files in scope — invisible to `git diff` in every mode, and exactly where generated code concentrates — stops one staged file eclipsing the rest, and discovers the base branch. Branch scope diffs the **merge base against the worktree**, which is the same content Step 3 builds the review input from. `DESIGN.md` (Step 1) has the ladder each of those replaces.

State the source and file count before continuing — `files`, `scanned_files` and `added_lines` come straight out of the JSON. If the user pointed at specific files, honor that and say so.

### If the user named a feature

They can ask for a branch review and still mean one slice of it: "winnow the dash cooldown work", "just the retry logic", "only the parts touching the save system". Take that literally.

**Do not try to compute the scope. Pass the user's words to the agents and let them judge it.** Resolving the phrase to a hunk or line set up front and filtering mechanically fails at both ends — hunk ordinals mean different things to the scanner and the agents, and the user was not thinking in code structure when they asked. Deciding what belongs to a feature is a judgment about intent, and judgment is what the agents are for. So carry the request, do not compile it.

**Dispatch Agent S first** — its prompt is in `$WINNOW/references/agent-prompts.md`. It gets the input diff and the user's phrase verbatim, and nothing else: no scanner JSON, no conversation history, no design rationale. **Do not produce the reading yourself.**

**Scope is a bigger power than judgment, and it is the one you should least be trusted with** — in this skill's headline case you generated the code an hour ago, and a boundary drawn one file narrow leaves that file reviewed by nobody with nothing in the output to show it. Settling it once also keeps A and B paired for Step 3.5. `DESIGN.md` (Step 1) has both failures in full.

**Then confirm it with the user before dispatching anyone else:**

```
You asked for the dash cooldown work. Scope pass says:
  Dash.cs, DashConfig.cs, PlayerInput.cs        in
  SaveSystem.cs — dash state is serialised here unsure
  the other 8 files                             out — will report only
Confirm or correct before I start.
```

Every `unsure` is a question, asked now. `unsure` must never be silently resolved into either pile — that bucket is precisely where a guess would have been wrong without anyone finding out, and asking costs one line.

**A, B, C, D and E then receive the confirmed scope as a rule, not a hint** — the file and region list, plus the user's phrase for context. They do not re-derive it. They may **appeal** the boundary, and appeals go to the user with the report, never applied silently. That keeps the one thing a reviewing agent genuinely knows better — it has read the code — without letting every agent redraw the line.

Ask, because you are guessing from a phrase. A reading that is silently one file wide reviews code the user did not ask about; one that is silently one file narrow misses the thing they did. Neither is visible in the output. Unattended: Agent S still runs, but nothing confirms it, so take its `in` set only when it returned no `unsure` at all — otherwise **widen to the whole diff and say so**.

When no feature is named, none of this happens: no Agent S, no tags, no appeals, and the diff is the scope.

The fix plan records the feature as the user's phrase plus the files that survived, so a cold executor inherits the constraint in the form it was actually decided.

Three things the feature set governs, and three it does not:

| Governs | Does not govern |
|---|---|
| What A, B, C, D and E review at all | What the scanner scans — **always the whole diff** |
| Which findings are live in the report, and which notes D writes | What `$ROUND/scan.json` contains — always the full scan |
| Which findings reach the fix plan | What you may read for verification |

**That first "does not" is load-bearing.** A narrowed `$ROUND/scan.json` would make the next run's `--since` report every out-of-feature finding as `resolved` — a page of "no longer true" claims about findings that are all still true. The filter lives at the report layer and touches nothing the scanner writes.

Findings outside the feature are a byproduct, handled exactly like pre-existing ones — see Step 4.

### The four-field integrity check

A typo'd `--base` finds no such ref, records it in `warnings`, and returns an empty scope — which prints as a clean branch. So the check is four fields, not three:

```
exit code != 0        → something went wrong, read `errors`
"complete": false     → files in scope were not reviewed, the scan has holes
warnings non-empty    → READ THEM. A bad --base, an unparseable file, and a
                        --since that was ignored all live here and nowhere else
findings == []        → only means "clean" when the three above are clear
```

Never report a clean result off `findings == []` alone. An empty `findings` with a non-empty `warnings` is a scan that did not happen.

**A warning starting `REFUSING:` is not a failure to work around — it is a question for the user.** The scanner stops when the requested scope cannot be numbered and read coherently at the same time. Today that is one case: under `--scope staged`, a file that is staged *and has since been edited*. `git diff --cached` numbers the staged blob while every finding is read from the worktree, so continuing would drop findings in silence and later report them as fixed.

Do not retry with a different flag to get past it, and do not report the run as clean. Surface it and let the user choose:

- **Commit what is staged, then re-run.** The refusal carries a paste-ready line (`--scope branch --base <pre-commit sha>`) that reviews exactly what the commit contains.
- **Review the staged and unstaged work together** with `--scope worktree`, if separating them was not the point.

Name the blocking files — the message lists them — so the choice is concrete. Unattended, stop at the refusal and report it; do not pick a scope on the user's behalf, because the two answers review different code.

**Two warnings are benign and must not be read as a failed scan.** A missing `--since` or `--declined` file warns `could not read … - ignoring it`; on a first run, or in any repo with no `declined.json` yet, that is the normal state. Guard them instead of passing them unconditionally:

```bash
# illustration only — the guard pattern; env.sh does not exist until Step 2
DECLINED=""
[ -f .code-winnow/declined.json ] && DECLINED="--declined .code-winnow/declined.json"
"$PY" "$WINNOW/scripts/scan.py" $SCOPE $DECLINED --json
```

Everything else in `warnings` is real.

**Binary files, and files that *look* minified, set `complete: false`.** They are unreadable, not skipped — only vendored and oversized paths carry the `skipped:` prefix that exempts them. Note the asymmetry: a file *named* `app.min.js` matches the vendored-path pattern and is exempt, while an unminified-looking name whose content has very long lines is unreadable and holes the scan. Check `errors` for what was actually unreadable: a binary asset in the diff is expected and means nothing, while a source file that failed to decode means the review missed code.

**Check the size before dispatching.** If the diff runs past a few hundred changed lines across many files, say so and offer to split it — by directory, by commit, or by language — rather than handing an agent more than it can hold. A judgment pass over a diff that overflowed its context returns confident nonsense. Unattended, split it yourself by top-level directory rather than asking.

**Split the dispatch, never the scope.** `--paths` looks like the tool for this and is not: it converts a diff review into the repo audit this skill exists to refuse. Instead run the same scope once, then hand each agent a subset of the **files** and give each subset its own section in one report. Split on file boundaries, never inside a file.

## Step 2 — Deterministic scan

Run the scanner with `$SCOPE` pinned. **Full flag reference: `"$PY" "$WINNOW/scripts/scan.py" --help`** — it is the authority, and re-stating it here is how the two drift apart. Stdlib only, no install step; paths resolve against the git toplevel, so any cwd inside the repo works.

**Pin the stem once** via `--report-name`, then pass `--stem "$STEM"` on every later call. **The stem embeds the scope** (`_worktree_`, `_staged_`, `_target<base>_`, `_files_`), and that is load-bearing rather than cosmetic: Step 4 reconciles against the most recent scanner JSON *for the same scope*, and a branch baseline compared against a worktree run reports differences that are only differences of scope.

**The workspace layout is in the repo's `README.md`, and `round-NN/README.md` ships in the scaffold.** Three rules from it bind here:

- **The root holds no run artifacts.** Everything a round produces is written into that round's directory and is never moved between rounds; rotation is `mkdir`, prior rounds stay reachable by `--since`, and nothing is deleted. **Rotation happens here, in Step 2 — not in Step 0**, because cold entry re-runs Step 0 and must not archive the plan it was invoked to execute.
- **Anything not on the round README's list goes in `round-NN/scratch/`**, and any script a run writes goes in `.code-winnow/utils/`. Both ship in the scaffold, so they already exist when an agent needs one. A run once left nine intermediate files at the workspace root because no rule named them.
- **Filenames inside a round say nothing about what was reviewed** — they are short and identical every round. The scope lives in `meta.json` and in the identity block atop every markdown file. Never reconstruct it from a filename.

`--whole-files` widens to the untouched lines *of the files the diff already touches* — no further. There is no repo-wide mode.

It flags regex- and AST-level candidates: fields and locals declared and never referenced, fields only ever incremented and never read, locals assigned and never used, variables that just rename another for a single use, log-and-rethrow, empty Unity lifecycle methods, `async` with no `await`, unrooted `UObject*` **members**, invisible Unicode, comments restating the line below, and committed credentials in a recognised vendor format.

**On the web tier it also flags** a `debugger` statement, a focused test (`describe.only`, `fdescribe` — P1, because every other test in the file is silently skipped and the run still passes), `console.log` left in source, `JSON.parse(JSON.stringify(…))`, an ARIA role restating its own element, HTML attributes obsolete since HTML5, vendor prefixes settled for a decade, `transition: all`, and empty CSS rules. **These are the whole of the web-tier rule set** and they are regex-level — `check_universal` and the generic test pass run on a web file too, as the paragraphs below describe. A `.vue`/`.svelte`/`.astro`/`.html`/`.htm` file gets all three languages' rules, because it is all three — with one exception: the empty-rule check runs only in a real stylesheet, since `function noop() {}` in an inline script matches that pattern exactly. `.jsx`/`.tsx` are JavaScript only, so JSX markup is not scanned by the HTML rules. Two rules are narrower than their names suggest and a report should not round them up: `fdescribe`/`fit` are only flagged inside a file that looks like a test file (`fit` is also how you fit a curve), while `describe.only` is flagged anywhere; and the vendor-prefix rule is a **named list of settled properties**, not a `-webkit-` sweep, so `-webkit-line-clamp` and its five siblings are correctly silent rather than missed.

**Two classes are deliberately not scanner rules, and a run that assumes otherwise reports them as absent.** *Unused imports, `using` directives and `#include`s* belong to Agent A: every claimed language already has a linter that finds them, so a scanner rule would duplicate the tool while this skill's value is knowing the handful of cases where the tool is wrong — a side-effect import, a `using` alias, a transitively-needed header. *Em and en dashes in documentation prose* belong to Agent C: the judgment is whether the diff's docs read differently from the repo's, and that comparison needs a sample of the base branch, which the scanner does not read. Both are in `core-patterns.md`; neither will ever appear in `scan.json`.

**`committed-secret` is the one rule whose findings never enter the fix plan** — and the same holds for Agent E's credential findings, which are the judgment half of the same concern — at any severity and however clearly they are worded. Deleting the line does not un-leak the credential; it is already in the object store, in every clone, and in every CI cache that fetched it. The fix is to rotate, which is not a behaviour-preserving edit and not this skill's business. Report it, say "rotate it", and propose no patch. A cleanup that quietly deleted the line would hand the user an all-clear they have not earned, which is worse than not detecting it.

In test files it additionally flags tests with no assertion, assertions that cannot fail, tests whose every assertion checks a mock, structurally identical tests that differ only in literals, and skips with no reason. That pass runs for pytest/unittest, NUnit/xUnit/MSTest, GoogleTest, Go, Jest/Vitest/Mocha, JUnit, Rust, RSpec, and XCTest — a JS or Go test file gets it even though nothing else here understands JS or Go. `$WINNOW/references/tests.md` is the judgment standard.

**The first three of those carry `mutation_candidate: true` in the JSON.** They are the false-coverage family — the findings whose claim is that the test cannot fail — and Step 3 proves that claim rather than arguing it, per `$WINNOW/references/mutation.md`. The stamp is a filter over `scan.json`, nothing more: the scanner does not run mutations, and the field is keyed on the rule rather than the severity because the same defect is P2 outside Python.

**Three of the scanner's test rules are narrower than that list suggests, and a report written from the list alone will claim coverage that did not happen:**

| Rule | Actual reach |
|---|---|
| `unused-fixture` | **pytest only.** It is emitted from the Python checker and nowhere else. An unrequested `[SetUp]`, `beforeEach` or `TEST_F` fixture is invisible to the scanner in every other language — judgment-pass work, not scanner work |
| `mock-only-test` | **Python: P1 when the test asserts and *every* assertion is an `assert_called*` call on a double.** A Python test with no assertions at all is `test-without-assertion`, not this rule. **Outside Python: P1 when the body verifies a mock and asserts nothing else; P2 when it does assert and every assertion checks a double.** That P2 is hedged on purpose, because verifying an interaction is legitimate when the interaction *is* the contract |
| `tautological-*` | **P1 only in Python, and only when every assertion in the test is tautological.** A mixed Python test, and every non-Python tautology, is P2 |

So when the scanner reports nothing in these categories, that is not the same claim in every language, and the report should not say it is.

(`duplicate-test` for Python needs `ast.unparse`, which is why this skill requires Python 3.9 rather than 3.8 — on 3.8 that rule finds nothing and says nothing.)

**Read `errors`, `warnings` and `complete` before you trust a small number** — the four-field check in Step 1. Vendored, generated and oversized paths are skipped by design and do not hole the scan; binary and minified-by-content files are *unreadable* and do. If *every* file in scope was skipped, `complete` is false and the exit code is 2 — that is a scan that reviewed nothing, not a clean diff.

Unused and duplicate bindings need the most judgment of anything the scanner reports. A field with no reader may be dead weight, or may be read by a subclass, a serializer, or the Inspector — the scanner marks exposed declarations at P3 with a note to confirm, and its unused-binding rule stays silent in headers and partial classes, where "never referenced in this file" is vacuous by construction. Nothing about a `[SerializeField]` or `UPROPERTY` should be deleted without checking scenes and assets.

The scanner is fast and dumb on purpose. It produces **candidates, never verdicts.** A `TODO` blocking a shipped feature and a `TODO` in a test fixture look identical to a regex.

**Capture the report stem now** — Steps 3, 4 and 6 all write files named from it, and each invocation stamps its own clock:

```bash
cd "$(git rev-parse --show-toplevel)"
rm -f .code-winnow/env.sh            # a stale one from a prior run must not survive

# Repeat Step 1's three values. This block cannot source env.sh — it is the
# block that writes it — and shell state does not cross a tool call.
WINNOW="<absolute path to this skill's directory>"
SCOPE=""
for c in python3 python py; do
  [ -n "$PY" ] && break
  command -v "$c" >/dev/null 2>&1 && "$c" -c "" >/dev/null 2>&1 \
    && PY=$(command -v "$c")
done
[ -n "$PY" ] || { echo "no working Python on PATH — set PY to its absolute path:"
                  echo "  PY=/c/Users/me/miniconda3/python.exe"; exit 1; }

# Keep stderr. A REFUSAL arrives there and also yields no stem, so a guard
# that only knows about empty scopes overwrites the one message that explains
# what happened — and then tells you to retry with --base, which Step 1 says
# explicitly not to do.
ERRF=$(mktemp)
STEM=$("$PY" "$WINNOW/scripts/scan.py" $SCOPE --report-name 2>"$ERRF") || STEM=""
if [ -z "$STEM" ]; then
  cat "$ERRF" >&2
  if grep -q '^REFUSING:' "$ERRF"; then
    rm -f "$ERRF"
    echo "" >&2
    echo "That is a refusal, not an empty scope. It is a question for the" >&2
    echo "user — see Step 1. Do NOT retry with a different --scope or --base" >&2
    echo "to get past it: the available answers review different code, and" >&2
    echo "picking one silently is the failure the refusal exists to prevent." >&2
    exit 1
  fi
  rm -f "$ERRF"
  echo "no stem. Three causes, in the order they actually happen:"
  echo "  1. the tree is clean AND you are on the base branch, so auto's"
  echo "     branch fallback has nothing to diff — pass --base <ref> to name"
  echo "     what to compare against. \`git branch --show-current\` tells you."
  echo "  2. the scope really is empty — nothing to review."
  echo "  3. \$PY or \$WINNOW is wrong."
  echo "Check 1 first; it looks identical to a clean tree and is not."
  exit 0
fi
rm -f "$ERRF"

# This run gets a new round folder, and nothing is moved. A completed round is
# already whole in its own directory, and the root never held this run's
# artifacts to begin with. Creating it HERE and not in Step 0 is deliberate:
# cold entry at Step 5 re-runs Step 0, and creating a round there would orphan
# the fix plan the cold session was invoked to execute.
#
# The HIGHEST existing round number, never the count. With round-01 and
# round-03 present a count yields 03, `mkdir -p` succeeds on the directory that
# is already there, `cp -a` overwrites its fixplan.md and notes.md with the
# blank template, and the whole thing exits 0 with no output. Deleting one
# round folder is enough to destroy an approved plan in another. `sort -n`
# after discarding non-numeric suffixes, so legacy `round-01-scope-probe`
# names neither count nor collide.
LAST=$(ls -d .code-winnow/round-* 2>/dev/null | sed 's|.*/round-||' \
       | grep -E '^[0-9]+$' | sort -n | tail -1)
N=$(printf '%02d' $(( 10#${LAST:-0} + 1 )))
ROUND=".code-winnow/round-$N"

# Plain `mkdir`, not `mkdir -p`: it must FAIL if the directory exists. That is
# the backstop for any numbering mistake, and it is the difference between a
# loud stop and a silently blanked plan.
mkdir "$ROUND" || { echo "REFUSING: $ROUND already exists — numbering is wrong,"
                    echo "and continuing would overwrite that round. Stop here."
                    exit 1; }
cp -a "$WINNOW/scaffold/round/." "$ROUND/"
echo "this run is round-$N"

# One definition point for every later block. Written fresh each run.
# The function goes IN the file: it is needed in later shells, and a shell
# function no more survives a tool call than a variable does.
cat > .code-winnow/env.sh <<'FUNC'
snapshot() {
  { git rev-parse HEAD 2>/dev/null || echo "no-head"
    git diff HEAD 2>/dev/null || git diff --cached
    git ls-files --others --exclude-standard -z \
      | while IFS= read -r -d '' f; do
          case "$f" in .code-winnow/*) continue ;; esac
          printf '%s\n' "$f"; git hash-object "$f"
        done
  } | git hash-object --stdin
}
FUNC

# Values appended with %q so a path containing a space, a backslash or an
# apostrophe survives being re-sourced.
{ printf 'WINNOW=%q\n' "$WINNOW"
  printf 'PY=%q\n'     "$PY"
  printf 'SCOPE=%q\n'  "$SCOPE"
  printf 'STEM=%q\n'   "$STEM"
  printf 'ROUND=%q\n'  "$ROUND"
  printf 'BACKUP=%q\n' "$ROUND/pre-fix"
} >> .code-winnow/env.sh

. .code-winnow/env.sh
printf 'SNAPSHOT=%q\n' "$(snapshot)" >> .code-winnow/env.sh

. .code-winnow/env.sh
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM" --meta "$ROUND" \
  > "$ROUND/meta.json"
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM" --json \
  > "$ROUND/scan.json"
echo "stem $STEM, round $N"
```

**Every later block opens by reloading it**, because shell state does not survive between tool calls:

```bash
# illustration only — the preamble every later block opens with
cd "$(git rev-parse --show-toplevel)"
. .code-winnow/env.sh || { echo "no env.sh — restart at Step 2"; exit 1; }
[ -n "$STEM" ] || { echo "env.sh is incomplete — restart at Step 2"; exit 1; }
```

**`SNAPSHOT` is the staleness stamp.** It hashes `HEAD`, the tracked diff, and every untracked file's blob — so an edit to a file in scope changes it, and so does a commit, an amend or a rebase. Recompute and compare it whenever the tree may have moved:

```bash
# illustration only — run after sourcing env.sh
[ "$(snapshot)" = "$SNAPSHOT" ] || echo "STALE: the tree changed since the scan"
```

The whole review rests on line numbers that were true when the scanner ran. If a file changes afterwards — the user keeps working, a formatter runs, a rebase lands — the agents review a diff that no longer matches disk, every finding's line is off, and at Step 5 every anchor fails to match and the whole plan reports "stale" with no explanation of why. The stamp turns that into one sentence at the moment it happens.

Our own writes under `.code-winnow/` are excluded from the hash, so the run does not invalidate itself.

**The baseline JSON is written here, not in Step 4.** Step 3 hands it to every judgment agent, so it has to exist before they are dispatched. Step 4 reads it, and reconciles against the *previous* run's JSON, never this one's.

## Step 3 — Judgment pass, by a separate agent

**Do not judge your own output.** If you wrote the code under review, you hold the design rationale that produced the chaff, and you will rationalize it. That is not a discipline problem you can solve by trying harder — it is a context problem, solved by handing the work to a reader who does not have that context.

### Build the review input first

"The diff" is not a thing that exists for the default scope — untracked files are invisible to `git diff` in every mode, and they are where generated code concentrates. Build it once, explicitly, and hand the *same bytes* to every agent so their findings can be merged and the conflict check can pair them:

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh

# Ask the scanner what it actually reviewed, rather than assuming.
SRC=$("$PY" "$WINNOW/scripts/scan.py" $SCOPE --json \
      | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["scope"])')
case "$SRC" in
  # Merge base, NOT `$BASE...HEAD`. Three dots is the right BASE side and the
  # wrong HEAD side: it pins the comparison to the last commit, while the
  # scanner reads every file from disk. Diff from the merge base to the
  # WORKTREE and both describe the same bytes.
  branch*) BASE=${SRC#branch vs }; RANGE=$(git merge-base "$BASE" HEAD) ;;
  *)       RANGE="" ;;
esac

# Emit every untracked file the agents should actually read, and NAME the ones
# they should not. `cat` on an untracked binary is the failure this exists for:
# one new PNG turns the review input into 230 KB of undecodable bytes, the -s
# check passes because the file is large, and five agents are handed it.
emit_untracked() {
  git ls-files --others --exclude-standard -z |
    while IFS= read -r -d '' f; do
      case "$f" in
        .code-winnow/*) continue ;;
        */node_modules/*|node_modules/*|*/__pycache__/*|*/vendor/*|vendor/*) \
          printf '\n--- NEW FILE (vendored, not shown): %s ---\n' "$f"; continue ;;
        *.min.js|*.min.css|*.map|*.lock) \
          printf '\n--- NEW FILE (generated, not shown): %s ---\n' "$f"; continue ;;
      esac
      # -I is "treat binary as non-matching", so this is true only for text.
      if ! LC_ALL=C grep -qI . "$f" 2>/dev/null; then
        printf '\n--- NEW FILE (binary or empty, not shown): %s ---\n' "$f"
        continue
      fi
      if [ "$(wc -c < "$f")" -gt 524288 ]; then
        printf '\n--- NEW FILE (over 512 KiB, not shown): %s ---\n' "$f"
        continue
      fi
      printf '\n--- NEW FILE: %s ---\n' "$f"; cat "$f"
    done
}

{
  if [ -n "$RANGE" ]; then
    git diff "$RANGE"                                # base..worktree
  else
    git diff HEAD 2>/dev/null || git diff --cached   # unborn HEAD: no commit yet
  fi
  emit_untracked
} > "$ROUND/input.diff"

[ -s "$ROUND/input.diff" ] || {
  echo "review input is empty but the scanner found files — do NOT dispatch"; exit 1; }
```

Five guards in that block, all against the same silent-empty failure, and `DESIGN.md` has what each one prevents: diffing to the **worktree** rather than `HEAD`, branching on **what the scanner reports** rather than the flag you passed, the `-s` check, the `|| git diff --cached` fallback for an unborn `HEAD`, and naming excluded files rather than dropping them.

For `--paths`, the input is the named files' full contents instead.

To cross-check which files are in scope, use `git diff --name-only HEAD` and `git ls-files --others --exclude-standard`. **Not the scanner JSON** — it carries a `files` *count*, not a path list.

### Dispatch

Dispatch the agents **in parallel** (see `superpowers:dispatching-parallel-agents`). Give each only that input file, the baseline scanner JSON from Step 2, and the reference files. **No conversation history, no design rationale, no mention of who wrote the code.**

**The prompts are in `$WINNOW/references/agent-prompts.md`.** Read it before dispatching and copy each prompt from there. It also holds the two blocks every Step 3 prompt carries verbatim — the staleness precondition and, when a feature was named, the scope rule. **Expand `$WINNOW` to its real value in every prompt**: a subagent's cwd is the repo, it has no `$WINNOW`, and an agent that cannot open the reference files still returns findings — they are just findings from no standard at all.

**Subagents may run on a cheaper model than yours; you may not.** Tier down the volume passes (A, B) if the runtime lets you choose, and **keep S and E at your own tier** — both are where a weaker reader fails invisibly. The table and the reasoning are in `$WINNOW/references/portability.md`. If the runtime offers no choice, ignore this.

**`$WINNOW/scripts/passes.py` will assemble these prompts for you, and it is optional.** It reads the same marked blocks out of `agent-prompts.md`, attaches the shared blocks each pass takes, expands `$WINNOW` and the round directory, and prints one JSON object per pass carrying its tier, its trigger condition, the reference files it names and the assembled prompt — so a dispatcher choosing a model per pass has the table above as data rather than prose. **It refuses rather than guesses**: a slot it cannot fill, a reference file that is not there, or a declared pass with no marker is a `REFUSING:` line and exit 2, never a prompt that is quietly one block short. Copying the prompts by hand is still what this step describes and nothing below depends on the script — a runtime with no shell reads `agent-prompts.md` and loses nothing.

```bash
# illustration only — not run by the harness
# The identity block is the three lines every markdown file in this round opens
# with. You render it from meta.json anyway; pass the same string here.
"$PY" "$WINNOW/scripts/passes.py" --json --round "$ROUND" \
  --identity-block-file "$ROUND/scratch/identity.txt" --no-feature

# When Step 1 resolved a feature, both halves are required — the user's own
# words, and the file and region list they confirmed.
"$PY" "$WINNOW/scripts/passes.py" --json --round "$ROUND" \
  --identity-block-file "$ROUND/scratch/identity.txt" \
  --feature "winnow the dash cooldown work" \
  --scope-list "$ROUND/scratch/scope.txt"
```

**`--feature` or `--no-feature` is not optional, and that is the point.** The script will not guess which run this is, because the two produce different prompts: without a feature the scope blocks are absent, and with one Agent S's prompt carries the user's phrase instead of the worked example the document uses to show its shape. An extraction that kept that example would dispatch a scope pass against a feature nobody asked for, and S would return a confident boundary for it.

**Division of labour, so their outputs merge cleanly — one agent, one question.** **Agent S** ran already: it drew the feature boundary in Step 1 and is finished before any of these start.

| | Owns | The question it answers | Runs |
|---|---|---|---|
| **A** | Code. Not comments, not documentation files | Does this line earn its place? | Always |
| **B** | Every comment and docstring | Does this comment earn its space? | Always |
| **C** | Documentation files, file headers, doc-versus-code truth, and the typography of prose the diff wrote | Is this still true, and does it match the repo? | Conditional |
| **D** | Runtime cost of code the diff added | Does this do more work than it needs to, at a frequency that matters? | Conditional |
| **E** | Silent failure and fragility, including protections the diff removed | How does this break, and why does the suite stay green? | Whenever A does |

If A notices a comment, it belongs to B. If B notices that a docstring is factually wrong, that is C's. If D notices dead code, that is A's. If A notices that a deletion it is proposing would break something invisible to the compiler, that is E's, and E outranks it. The overlaps are real and Step 3.5 resolves them; do not have the agents negotiate.

**A, B and E are the ones that always run**, so a diff with no docs and no hot path still gets code, comments and silent-failure coverage. C and D are conditional because their trigger is a property of the diff — the trigger conditions are at the head of each prompt in `agent-prompts.md`. There is no equivalent exemption for E: a one-line change is enough to add a swallowed exception.

**Serial fallback**, if the runtime has no subagents: run A, B, C, D, E yourself in that order, and say once in the report that the judgment pass was self-review. Two things degrade further and the report must carry both:

- **E's veto.** Run serially, A's proposed deletion and E's objection come from one reader minutes apart, so the objection lands after you have talked yourself into the deletion. Do E's pass over A's proposed removals **as a separate reading against `fragility.md`**, before either is written into the report.
- **Agent S.** Its whole value is that a reader with no design rationale drew the boundary, which self-drawing destroys. Draw it, confirm with the user as usual, and **record in the report that the scope was self-drawn** — that line tells a later reader which decision to distrust.

`$WINNOW/references/portability.md` has the full degraded path.

### Test findings are proven before they are reported

**A test finding says the test cannot fail, and that is checkable.** Three things go through `$WINNOW/references/mutation.md` before they reach the report: a test finding you intend to report (asserts nothing that can fail, asserts only on mocks, tautology), a proposed rewrite of a test's assertions, and a proposed test deletion. Copy the tree into `.code-winnow/mutation/<id>/`, break the one behaviour the test is *named* for, run that test in the copy. **Green under the mutation proves the finding; red disproves it** — dismiss it, and record the mutation as the reason, because a settled question with a command behind it stops the next run re-arguing the line. **You run this, not the agents**: they read a diff and never execute anything. **Every test finding in the report then carries `proven` or `argued`**, where argued is the honest label for one that could not be mutated — the reference has the three reasons that is allowed, and the rule that the label is never faked. It is not run over every test in the diff; it is for findings about to make a strong claim.

## Step 3.5 — Conflict check

The split that keeps the agents' outputs mergeable also blinds A to what the author said, so without this step the report contradicts itself — proposing a deletion on one page and quoting the comment defending it on another. `DESIGN.md` (Step 3.5) has the reasoning.

**Run this yourself**, once all agents return, before writing anything. It is reconciliation of two outputs, not judgment of code, so the "do not judge your own output" rule of Step 3 does not apply here.

**If Agent A returned no `comment-claim:` tags at all, this step has nothing to work on — and that is usually a bug, not a clean diff.** A's instruction to keep a finding it would rather dismiss and hand it up for arbitration is one line inside a long prompt, written as two negatives, and it asks A to do the unnatural thing. The natural thing — see `// Reserved for future use`, quietly drop its own finding — produces an empty conflict check and a report that looks fine. Before concluding there were no conflicts, grep the diff yourself for the bare-claim vocabulary (`reserved`, `intentional`, `do not remove`, `for future`, `kept for`) and check that A either tagged those lines or had no finding near them. If A swallowed them, re-dispatch A with the tagging rule restated at the top of its prompt rather than reconstructing its judgment here.

**One constraint that does apply, and it is the important one: you may not overturn a finding using design rationale you hold from earlier in this session.** That rationale is exactly what Step 3 exists to keep out, and it will arrive dressed as "I know why that parameter is there". Only three things count as evidence: the diff, the comment text, and a lookup in the repo.

### What pairs with what

A comment is adjacent to a finding when it is on the same line as the finding's `anchor`, in the contiguous comment block immediately above it, or the docstring of the declaration the anchor sits in. Nothing further away pairs — a comment three functions up is not evidence about this line.

### The ten classes

| | Situation | Resolution |
|---|---|---|
| **X1** | A comment claims intent that contradicts one of A's findings | Graded — below |
| **X2** | A deletes a declaration; B says TIGHTEN or KEEP on its comment | The deletion subsumes B's verdict. The comment goes with the code, as **one** finding. Prevents an orphaned comment describing a field that no longer exists, and a rewrite nobody will read |
| **X3** | B says DELETE the comment; A says delete the code | Not a conflict — they agree. Emit **one** merged finding, not two entries for one edit |
| **X4** | An intent comment sits on a test finding | Graded, plus the floor below |
| **X5** | C says a docstring is false; B says TIGHTEN or KEEP | **Truth beats concision.** C wins, and B's rewrite must carry the corrected fact. If B said DELETE, that already resolves it — one finding |
| **X6** | A deletes a symbol; C reports a doc that documents it | **One** merged finding naming both locations: delete the code, update the doc. Two edits, one decision |
| **X7** | B says DELETE or TIGHTEN a file header that C identifies as the repo's convention | **KEEP it verbatim.** Headers are boilerplate on purpose; concision does not apply to them, and a header that matches 200 other files is doing its job precisely by being identical |
| **X8** | A proposes deleting a line D wrote a note about | **The deletion wins.** Drop the note and count it. If A proposes a *rewrite* rather than a deletion, keep the note and mark it `re-check after applying` |
| **X9** | A proposes deleting a line E identifies as load-bearing | **E wins** — below |
| **X10** | A and E flag the same line for the same underlying reason | **One** merged finding at the higher severity, carrying E's `breaks:` and `no test:` fields. Two entries for one edit is the same defect as X3 |

X5, X6 and X7 do not arise when C was not dispatched. When it was not, B's one-line notes about comments or docstrings it suspected were false still reach the report — as P3 "unverified doc claim", never dropped. A suspicion nobody checked is worth less than a verified finding and more than silence.

X8 does not arise when D was not dispatched. X9 and X10 always can, since E runs whenever A does.

Findings outside the confirmed scope never enter this step. Scope appeals are not conflicts either: they go to the user with the report, not through these rules.

### X1 — grading the claim

The rule is `$WINNOW/references/comment-evidence.md`, and the short version is that authority is earned, never granted by the presence of a claim.

**A checkable why** — a ticket, a named consumer or mechanism, a concrete external constraint — **earns a lookup, not a pass.** Four outcomes, and the file has the reasoning behind each:

| Outcome | Handling |
|---|---|
| **Confirmed** — you found what the comment names | Dismiss A's finding → "Deliberately left alone", comment quoted as the reason |
| **Disproved** — positive evidence of the *opposite* | Finding stands, **up one severity** (P1 stays P1), message says the comment is false |
| **No evidence either way** — the grep returned nothing | **Not disproof. Never file it as Disproved.** Original severity, mark `unverified`, propose nothing |
| **Unperformable** — no network, no tooling to read the asset | Same as no-evidence |

**Only positive disproof earns the upgrade**, because absence of evidence is the *normal* result for truthful comments — the consumers worth commenting about are the ones grep cannot see.

**An unverified claim keeps its severity**, goes to "Author claims — confirm", never enters the fix plan, and is never proposed for deletion. **Do not demote it to P3** for being unverifiable: that reads as caution and rebuilds the same immunity one rung down, where eleven characters of `(see #4821)` sink a P1 into the cosmetic list the report rules tell you to cut when it runs long.

**A bare claim** — "reserved for future implementation", "kept for later", "intentional" with no reason — earns no lookup, because there is nothing to look up, and it does not protect the code. Merge the comment and the code into **one** finding at A's severity:

> `Combat.cs:41` — `enableAdvancedMode` is never read, and the comment above it asserts it is reserved without saying for what. → Add a ticket reference, or remove both lines.

**Never propose deleting the code and keeping the comment, or the reverse.** Those two lines are one decision.

### X4 — the floor

**A comment can justify a test's existence. It can never justify its false coverage.** `// intentional duplicate, pins #412` dismisses `duplicate-test`. Nothing in a comment dismisses an "asserts nothing" or "mock-only" finding — a note saying the test is intentional does not make an unfailable test able to fail. Keep it, quote the comment, and say what assertion would fix it.

**Match on the defect, not the severity label.** Those findings arrive as P1 *or* P2 depending on language and shape — a Jest test whose only assertion is `toHaveBeenCalled()` is P2, not P1. A floor written as "nothing dismisses a P1" would let the commonest form of the defect through on a technicality. `$WINNOW/references/tests.md` has both tables, and the carve-out that matters in the other direction: a test with no assertion that fails by crashing — an import smoke test, a does-not-crash regression — is not false coverage and is dismissible with one line naming it.

### X9 — E vetoes the deletion

**When E names a mechanism that makes a line load-bearing, A's finding is dismissed.** It moves to "Deliberately left alone" with E's reason quoted, and it does not reach the fix plan. The mechanisms are the ones in the Step 6 deletion-safety list and in `$WINNOW/references/fragility.md`: a GC root or callback reference, a directive comment, a type carrier, a trust-boundary check, a registration anchor, a side-effect import, a serialized field an asset reads.

**E must name the mechanism, not merely object.** "This looks load-bearing" is not a veto — it is the style opinion E's own gate excludes. If E cannot say what breaks and why no test catches it, A's finding stands on A's evidence, and the disagreement is reported as a confirm-question at A's severity rather than silently resolved either way.

**One direction only: E can save a line, never condemn one on A's behalf.** If E thinks something *should* be deleted and A did not flag it, that is an ordinary E finding held to E's own gate — not a veto and not a merge.

Step 6's deletion-safety pass asks these same questions after the edits land, and it is **not** made redundant by X9: `DESIGN.md` (Step 3.5) has why both stay.

### Output

A merged finding list, and one line for the report:

```
Conflict check: 3 dismissed on comment evidence, 2 merged, 1 upgraded (comment
contradicted by lookup), 2 deletions vetoed by E, 1 perf note dropped (line deleted).
```

Report every count, including the zeroes that matter. "0 deletions vetoed by E" on a diff where A proposed twelve deletions is a fact about the run; an omitted count reads as though the check was not made.

Unattended runs execute this step normally — it needs no user input.

## Step 4 — Report

Never edit in this step.

**Every shape this step writes is in `$WINNOW/references/report-format.md`** — the condensed report, the header-gate question, the fix plan, the performance notes document, `declined.json` and `perf-declined.md`. Read it before writing. What follows is what goes *in* them.

**Write for a competent programmer who has never run this skill and did not write the code** — and note that by this point you are the worst-placed person to judge whether you have, because you are holding every term this document uses and from inside they all read as ordinary English. That is how a report ends up precise, complete and unreadable by the person who asked for it. `report-format.md` carries the standard operatively: the words that may not appear, and the order — **answer first, findings next, the run's bookkeeping last**. Every count is still reported, zeroes included; it just goes at the end.

### Naming and dating the report

Write `$ROUND/report.md`. `$ROUND/scan.json` already exists from Step 2.

**The filename no longer says what was reviewed, so the file has to.** Every markdown file a round writes — `report.md`, `fixplan.md`, `notes.md` and every `agent-*.md` — opens with the identity block:

```
Round:     02  —  .code-winnow/round-02/
Compared:  feat-golden-eval @ worktree   vs   main @ 69a5604   (branch scope)
Generated: 2026-08-03 19:09
```

Copy those values out of `$ROUND/meta.json`; do not retype them from memory. This is the block that makes a report readable when its path has been pasted into chat without its context — the job the stem used to do badly.

**Every JSON the run writes gets its own filename.** `$ROUND/scan.json` is the pre-fix baseline, written once in Step 2 and never again — Step 6 reads it. `--since X.json --json > X.json` truncates the baseline before Python opens it, so `--since` reads an empty file and the baseline is gone. New name out, baseline in:

```bash
# illustration only — the shape Step 6 uses
"$PY" "$WINNOW/scripts/scan.py" $SCOPE --stem "$STEM-postfix" --json \
  --since "$ROUND/scan.json" > "$ROUND/scan-postfix.json"
```

### Reconciling with the previous run

**`scan.py` already chose it.** `$ROUND/meta.json` carries `prior_round` — the newest round whose `scope` matches this one's, or `null`. Read the field; do not search the directory:

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
PRIOR=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["prior_round"] or "")' \
        "$ROUND/meta.json")

# `if`, not `[ -n "$PRIOR" ] && …`. As the last command of the block that
# short-circuits to exit 1 on the no-prior path — which is the FIRST RUN of
# every repo, and which this document calls normal three paragraphs down. A
# step that exits non-zero on its own documented happy path teaches whoever
# runs it to ignore the exit code.
if [ -n "$PRIOR" ]; then
  "$PY" "$WINNOW/scripts/scan.py" $SCOPE \
    --stem "$STEM-vs-$PRIOR" --json --since ".code-winnow/$PRIOR/scan.json" \
    > "$ROUND/scan-vs-$PRIOR.json"
  echo "reconciled against $PRIOR"
else
  echo "no prior round of this scope — the report says 'Previous run: none'"
fi
```

This used to be `ls -1t .code-winnow/round-*/*.json | grep -v -- '-postfix\|-p3\|-r2'` plus a line of prose telling you to eyeball the stem's scope segment. Both failed the same way: the exclusion list was a blocklist of ad-hoc suffixes that grew every time an agent invented one, and the scope check was advisory. **A branch baseline reconciled against a worktree re-scan reports every untouched finding as `resolved`**, which reads as "your fixes worked" for findings nobody touched.

Rounds written before `meta.json` existed carry no scope and are never chosen, so the first run after this change says "Previous run: none". A wrong baseline is worse than no baseline.

Never write back over `$ROUND/scan.json`, which Step 6 still needs as the pre-fix baseline. The scanner marks each live finding `new` or `persisting`, and returns the ones present last time and absent now in `resolved`. Matching is by file, rule, message, and the normalised source line.

Findings present before and absent now are **no longer true** — fixed, refactored away, or overtaken by events. Report them under their own heading and never re-list them as live. A punch list that keeps resurfacing settled items stops being read, and that failure is quiet: the user does not tell you they have started skimming.

**A finding whose file this run never opened is `out_of_scope`, not `resolved`.** The scanner records every path it actually read, so a prior finding in a file that left the scope lands in its own array and its own report section, saying the true thing: not examined. Never fold it into the resolved list.

**"Absent" means gone, not merely unprinted**, and the scanner enforces the distinction so a mismatched baseline cannot manufacture resolutions. A finding this report filters out but that is still true is counted during reconciliation and then dropped from the output: it appears as neither live nor resolved. Declined findings are handled the same way and for the same reason.

### Findings the user declined

Declining is not the same as resolving: the finding is still true, so the scanner keeps producing it, and without somewhere to record the answer it returns as `persisting` on every run — the same skimming failure by a different route.

Keep one file, `.code-winnow/declined.json`, in scanner-report shape (see `report-format.md`). When the user rejects a finding, append the finding object exactly as the scanner emitted it — `path`, `rule`, `message` and `anchor` are the key, all four verbatim. Pass it on every later run with `--declined .code-winnow/declined.json`. Matches move to the `declined` array and out of `findings`. The file is a normal file — the user can delete a line from it to re-open a question. `line` is ignored in matching, so declined items survive line shifts.

### Severity

**Use the severity the owning agent or the scanner assigned.** The taxonomy is not re-derived here: `core-patterns.md` has the invisible-character demotion ladder and the vendor-format rule that does *not* demote in a fixture, `fragility.md` has E's brief and the rule that out-of-scope findings keep their severity, and `tests.md` has both false-coverage tables. You read `core-patterns.md` yourself before Step 3.

**Do not demote** because a finding is unfixable here, unverifiable in this runtime, or inconvenient for report length. Three things bind on top of that:

- **Credentials stay P1** — the scanner's vendor-format rows and E's judged ones alike — are never demoted in a test or prose file, and never enter the fix plan. Rotate, do not delete.
- **"Validation removed from a trust boundary" is a P1 that only E detects.** No scanner rule finds it; E is what makes that line true rather than aspirational.
- **E should essentially never produce a P3.** A cosmetic E finding failed its own gate and belongs to A.

### Findings that cannot be fixed here

E produces findings whose fix is a design decision — a save migration, a cache invalidation strategy, a locking scheme, a schema backfill. Step 5b binds every fix to preserving behaviour, so these are reported and left. **Every committed-credential finding is in this category too** — the scanner's `committed-secret` rows and E's read of a named credential alike — for a different reason: the repair is to rotate the credential, and deleting the line only hides it from the working tree while it stays in history.

**They stay at their own severity and stay in the P1 or P2 list.** Do not demote them for being unfixable, do not move them to a separate section, and do not move them into the performance notes. A P1 that this pass cannot repair is still a P1 the user needs to see today, and every mechanism for tidying it away ends with it below the fold. Mark the item `fix: out of scope — <why>`, count them in the header's `Not fixable here:` line, and leave them where the severity puts them.

The fix plan omits them, so "fix all" cannot sweep them up. That is the only place the distinction has any mechanical effect, and it is enough.

### What to cut and what never to cut

The "deliberately left alone" section matters more than it looks. Showing what you considered and rejected is what makes the rest credible — and it stops the next run re-flagging the same lines.

If a P3-only list runs past a screen, cut it. Twenty cosmetic nits train the user to skim, and then they skim past the P1.

**Never cut "Author claims — confirm", and never sort it by severity.** Those items keep the severity they had before the comment was considered, and each one is a question only the user can answer in two seconds. Folding them into P3 is what makes the nine-character attack work: append `(see #4821)` to a comment above `except Exception: pass`, the lookup is unperformable in most runtimes, and a demoted item lands under "Cosmetic" and gets trimmed for length. A silent-data-loss P1 disappears for twenty-two characters of generated comment.

### The performance notes document

**D is dispatched like every other pass and writes its raw output to `$ROUND/agent-D.md`.** You then produce `$ROUND/notes.md` from it, exactly as you produce `report.md` from A, B, C and E. The shape and its three guards are in `report-format.md`.

**`notes.md` is the only place D's findings are ever published**: not a section of the report, and **nothing in it enters the fix plan or is ever applied.** That is what "nowhere else" means — it constrains where the notes *go*, not whether D's raw output exists. Read the other way it made `agent-D.md` a file the skill forbids and the index template links, so the index carried a permanently dead link.

**Write the document even when D found nothing** — an empty Notes section and a line saying the pass ran. A missing file is indistinguishable from a pass that was skipped, and those are different facts. When D was not dispatched at all, write no document and say so in the report header instead.

D produces notes from judgment rather than from a scanner rule, so `--since` and `declined.json` cannot reach them. Keep `.code-winnow/perf-declined.md` and hand it to D on every later run; D skips matches and reports the count. **Matching is by path plus anchor, never by line number** — a note declined at line 22 is the same note when an unrelated edit moves it to line 40.

### Findings outside the named feature

Only when Step 1 resolved a feature. Same discipline as pre-existing flaws, for the same reason: it is a courtesy, and a courtesy that takes over the report stops being one.

This is what the scanner found outside the confirmed scope, plus anything A, B, C, D or E happened to notice at its edges. **Nobody swept for it.** Report it as a courtesy: top three by severity, a count for the rest, two sentences each, no proposed patches, no severity debate.

These never enter the fix plan and are not eligible for Step 5. Fixing one takes a second, explicit approval — and the honest way to get it is to offer a proper pass, not to slip them into a cleanup the user scoped to something else.

**Agent S's `unsure` files are not in this section**, and neither are scope appeals. Both were questions put to the user; filing either here reads as "reviewed and set aside", which is the one thing they are not.

**Say what the out-of-feature files did not get**, because a partial pass reads as a complete one. The agents judged what they happened to see there; nothing systematic ran. A mock-only test in a file nobody opened is absent from the report entirely, and the header's `3 of 12 files` otherwise reads like coverage of twelve.

One consequence worth knowing rather than fixing: these are never presented as decisions, so they can never be declined, so they persist in every later run. If one keeps returning and the user does not want it, the answer is to judge it properly in a scoped run.

### The header convention gate

**Any finding that touches a copyright, license, or SPDX line goes through this gate** — whichever branch of Agent C produced it, and whether it was framed as a convention conflict or as a stale-doc correction. Do not fold it into "fix all". A license line is never an ordinary doc finding.

If Agent C found a header conflict, **ask before proposing any header edit**, using the question shape in `report-format.md`. **Quote the header you are proposing, in full.** The user is being asked to assert a company name and a year onto files; they cannot answer that from the word "the repo's header". A 2019 notice on a file created this year is wrong in a way only they can see.

**Cap it at ten files.** Past that, do not offer the fix option at all — say *"N of the files this change adds carry no header; want a header pass as its own change?"* and stop. Diff membership limits *which* files; only a count limits *how many*.

Two reasons this is a gate and not a finding like any other. Header edits are bulk and mechanical, so "fix all" would sweep them in unread — and bulk mechanical edits are the thing this skill calls the most reviewer-hostile content in a generated diff. And a header carries a license claim: adding a copyright line to a file is an assertion about ownership, which is not a call this skill gets to make.

Severities are in Agent C's brief: missing is P3, wrong is P2, CI-enforced is P1. The gate applies to all three — severity decides how loudly it is reported, never whether it needs asking.

**Only files the diff added or modified are ever eligible.** If the repo's own headers are inconsistent, that is a pre-existing condition — one sentence in the report, and no further. Unattended: report only, never unify.

### Pre-existing flaws

One section, one meaning: **problems in the files this change touches, on lines this change did not touch.** Not the rest of the repo. This is a byproduct of reading around the diff, never a reason to go looking — and nothing seen during a Step 3 verification lookup belongs here either.

**"Touched" includes lines the change took away, and that is not a technicality.** A finding about a *block* — a test function, not the `def` naming it — belongs to this change when anything inside that block was added **or deleted**. Judging by the anchor line alone is blind in the one direction this skill exists to look: delete a generated test's only assertion and every surviving line is untouched, so the now-assertionless test files as pre-existing and drops out of the default run. The change created a P1 and the scan reports nothing.

Two sources feed it, and both are optional:

- What the Step 3 agents noticed while reading around the diff. This is the usual source and needs no extra command.
- `"$PY" "$WINNOW/scripts/scan.py" $SCOPE --whole-files --stem "$STEM-preexisting" --json > "$ROUND/scan-preexisting.json"` — the same scan widened to the untouched lines of those same files. **This is the only thing that populates the scanner's `preexisting` findings**, so run it if you want the deterministic half; skip it on a large diff, where it mostly adds P3 noise. Either way, say which you did.

Log every one in full to the report file. In the user-facing output, give each **at most two sentences: one for what it is, one for what it does.** Then stop. Expand only on request.

> `AudioManager.cs:88` — Coroutine started in `OnEnable` is never stopped in `OnDisable`. Toggling the object leaks a coroutine per cycle, so audio triggers stack up over a session.

Not three sentences, not a proposed patch, not a severity debate. If there are more than five, list the top three by severity and give a count for the rest.

If the pre-existing list is longer than the in-scope list, say so in one line — "this file has more going on than your change does, want a proper pass over it?" — and let the user decide. Deciding for them turns a five-minute review into an afternoon.

### Regenerate the index — the last action of Step 4

`.code-winnow/README.md` is the one file a reader opens. Rewrite it **in full** from the template; never edit the live file, so there is no half-updated state and no marker to preserve.

```bash
cd "$(git rev-parse --show-toplevel)"; . .code-winnow/env.sh
sed "s|{{ROUND}}|$(basename "$ROUND")|g" "$WINNOW/scaffold/root/README.md" \
  > .code-winnow/README.md
```

**The placeholder is `{{ROUND}}` and not `ROUND` because the substitution is global and `ROUND` is a real word.** The template's own prose documents `$ROUND` as an `env.sh` variable, and an unanchored `s|ROUND|round-06|g` rewrote it to `$round-06` — in the index of a real run. A placeholder has to be a token that cannot occur in the prose around it.

That handles every path in one substitution. Fill the rest by hand, from what you already hold:

- The `Current round:` line, out of `$ROUND/meta.json` — branch, side, base, sha, scope, timestamp.
- The **This round** column, from the counts the conflict check just produced — `14 live, 3 P1`, `9 items, APPROVED`, `4 notes`. Leave a cell blank rather than guessing.
- **Previous rounds**, one link per `round-NN/` directory, oldest first.

**Replace every placeholder, including by nothing.** A blank cell says the count is not known; a leftover placeholder says you stopped halfway. They are different facts and the tests fail on the second.

**A pass that did not run keeps its row and loses its link** — the bare filename as plain text, and `not dispatched` in the last column. Deleting the row would make a skipped pass indistinguishable from a pass this skill does not have, and a link to a file nobody wrote is a dead link in the first place a reader looks.

**Links resolve against `.code-winnow/`, not the repo root.** `round-02/report.md`, never `.code-winnow/round-02/report.md` — the second renders perfectly and 404s on click.

## Step 4b — Record the approved set, and choose how to apply it

**Wait for explicit go-ahead.** This is the gate. If nobody is there to give one, write the fix plan and **stop there**. See the unattended table; an unattended run never edits.

**An unattended plan is marked, and the mark is load-bearing.** Its header line reads `Status: UNAPPROVED — no human reviewed these findings`, and every section heading says *proposed*, not *approved*. Without that, an unattended run writes a file listing every finding under "approved", and the resume path — which exists to execute a settled list without re-opening it — turns a scheduled scan into a one-paste auto-apply of deletions nobody read. That routes straight around the gate this document builds two sections earlier, using the mechanism it built one section later. "Entering at Step 5 cold" refuses any plan carrying that line, and `scripts/backup.py` refuses it again.

### The fix plan

Once the user has approved a subset, write `$ROUND/fixplan.md` — **the shape is in `$WINNOW/references/report-format.md`**. It holds what the fix pass needs and nothing else, and it is the handoff contract for all three rungs below.

**`file:` is authoritative, not the prose.** Every item carries at least one `file:` line, and `line:` / `occurrence:` / `of:` / `anchor:` are the fields it pairs with; a merged X6 finding lists each group in order. The headline is for the reader. Prose is not a data format: `scripts/backup.py` parses `file:` lines and nothing else.

**`line:` is what the locating rule actually uses** — "Locating a fix at execution time", in `$WINNOW/apply-and-verify.md` — so an item without it cannot be applied.

**`occurrence:` and `of:` count matching lines of the file, and both come from the scanner as `anchor_index` and `anchor_total`.** Copy `line` and those two straight out of the JSON. Together they distinguish the third `catch (Exception) { }` in a file from the first. **The JSON's `occurrence` field is not one of them** — it indexes findings that share a rule and message, a different population; copying it hands the executor an ordinal measured on the wrong thing and rule 2 below then edits untouched, unreviewed, unapproved code.

Anchors are written **unquoted and unfenced**. Backticks inside a value break the moment an anchor contains a backtick, which doc fixes routinely do.

The user edits the plan directly — delete an item to drop it. Write it whether or not a clear happens: it is also the on-disk record of what was approved, and Step 6 reconciles against it.

### `evidence:` — the deletion-safety field

**Every item carries one, and on anything that removes code it is the load-bearing field.** Three permitted values:

- **The commands you ran and what they returned** — literally, so Step 6 can run them again. `git grep -c cachedRig -- '*.cs'` → `2`. Not a summary of a lookup: the lookup, re-executable. "Traced it" is not evidence; neither, quite, is "grepped repo-wide, 3 hits, all in this file", because a fabricated count is textually identical to a real one and the plan is written by the same agent that proposed the deletion. A command someone else can re-run is the only form of this that survives an agent having a bad day.
- **`rewrite, nothing removed`** — for a tightened comment, a corrected doc line, an inserted header. Nothing is being taken away, so there is nothing to prove safe.
- **`unverified — <the lookup you could not perform>`** — and then the item must not propose a deletion.

**An `unverified` deletion is a rule violation upstream, and the executor refuses it.** `comment-evidence.md` already says an unverifiable claim becomes a confirm-question — at its own severity — and never a proposed deletion, so such an item should not have reached the plan. If one does, skip it, and report it as *"approved but unverified — not applied"* rather than applying it or silently dropping it. Rewrites with `unverified` are fine; only removal needs proof.

This is the whole correctness gate, and it is deliberately not a fourth reviewing agent. Another opinion does not make a lookup happen. A required field does.

### `tests-delta:` — on any item that changes what the suite collects

This skill removes tests on purpose: merging structural duplicates, dropping a fixture nothing requests. Those are approved changes, and they move the pass count legitimately. **So an item that changes collection declares exactly how, by name** — both sides, not a net number, so a merge that quietly drops a case shows up as `-3 +2`. The field's shape is in `report-format.md`.

Without it, Step 6 has no way to distinguish an approved removal from an accidental one, and the honest reading of a smaller suite would be "restore everything" — which would block legitimate work every time the skill did one of the things it exists to do.

### `mutation:` — on any item that rewrites or deletes a test

Same argument as `evidence:`, and the same answer: proof is a required field, not another opinion. The item carries the mutation edit, the command, and the label — `proven` or `argued` — so the user approving a change to their tests can see whether anything was actually demonstrated. `$WINNOW/references/mutation.md` is the procedure and `report-format.md` has the field's shape.

**A deletion may be proposed only on `proven`.** On `argued`, propose the tightening instead, or propose nothing: an unproven deletion of a test is the one edit in this skill most likely to be waved through unread, and the plan is where it stops being waved through.

### Then choose a rung

By Step 5 you are carrying the diff, the scanner JSON, every agent's output, the conflict check, the report, the performance notes, and the approval conversation. The fix loop — edit, test, reconcile, sometimes debug — is the part of the run that most needs headroom and least needs that history.

**Rung 1 — clear and resume. Offer this first.**

```
Fix plan written to .code-winnow/round-NN/fixplan.md.

To apply it with a clean context: /clear, then paste

    code-winnow: apply .code-winnow/round-NN/fixplan.md
```

Say plainly what it buys, and do not oversell it: a long edit-and-test loop then runs against a small stable prefix instead of the whole review. Clearing does not carry the previous cache forward; the win is headroom and a clean prefix for the turns that follow.

**Rung 2 — fix subagents.** If the user would rather not clear, or the runtime has no equivalent, dispatch the work to a subagent with no conversation history. You stay supervisor: you merged the findings, you verify, you reconcile, **you do not edit.**

**Its prompt must carry four things, because it has never read this file** and every rule below lives only here:

1. The fix plan, and `andrej-karpathy-skills:karpathy-guidelines`.
2. **The anchor-location rules** — "Locating a fix at execution time" in `$WINNOW/apply-and-verify.md` — copied into the prompt in full, not cited: the agent has read neither file. Normalise, match at `line:`, else *only if the file holds exactly `of:` matches* take the `occurrence:`-th counting top to bottom, else report stale. Never "the one remaining match", and never the ordinal without the total check. Without this the agent locates by line number or searches, and the search is what edits code the user struck from the plan.
3. **The `evidence: unverified` rule** — skip those items, report them, do not perform the missing lookup and proceed.
4. **"Step 5a is already done; do not run it."** Otherwise it re-runs the backup and copies half-edited files over the restore point.

**On this rung you run Step 5a yourself, once, before dispatching anything — both halves, the backup and the `Tests-before` baseline — and you tell each fix agent that both are already done and that it must not run 5a.** The backup script copies *every* path in the plan, not just one agent's section, so two agents each running it would snapshot the other's half mid-edit. That is deterministic, not a race, and the non-empty-directory refusal built into `backup.py` is what catches it if this instruction is ever missed.

Code fixes and doc fixes can go to two agents in parallel — different files, no shared state. **Check the `file:` sets are actually disjoint first**; if any path appears in both sections, run them in sequence. Header fixes always go last and alone: they touch line 1 of files the other agents are editing.

**Rung 3 — in place.** No subagents and no clear available. Apply the plan yourself, and say so once in the report.

## Handing off — this file ends here

The rung decides what happens next, and only one of the three continues in this session:

- **Rung 1 — you are done.** Print the clear-and-resume message above and stop. The next session enters cold through `SKILL.md`, reads `$WINNOW/apply-and-verify.md`, and never opens this file. Do not read ahead into Steps 5 and 6 "to be ready": that spends the context the rung exists to free, in the session that is about to end.
- **Rungs 2 and 3 — open `$WINNOW/apply-and-verify.md` now** and continue at Step 5. Everything above stays true; nothing in it is repeated there.

**Whichever rung, nothing further in this file applies.** Steps 1 – 4b are finished, and the fix plan is now the contract — not the report, not the agents' outputs, and not the conflict check.

