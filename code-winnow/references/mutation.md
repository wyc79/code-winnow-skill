# Mutation proof

Whether a test *should exist* is a question about intent. Whether a test *can fail* is a question about the code, and it has an answer you can produce rather than argue: break the behaviour the test is named for, and watch what the test does.

**Who loads this:** the orchestrator, at three points — Step 3, before a test finding is reported; Step 4b, when a test rewrite or deletion goes into the plan; Step 6, when a tightened test is verified. **Not the Step 3 agents.** They read a diff and hand back findings; they do not copy trees or run suites, and five parallel agents each running a project's suite is five ways into shared state.

## Why proof rather than judgment

Two tests in one mature suite stayed green after the exact production behaviour each was *named for* was deleted. One asserted a file's absence on a code path that could never write the file under any behaviour. One rebuilt a dedup filter inside its own body and asserted on its own list comprehensions. Both had assertions, neither was mock-only, and every heuristic in `scripts/scan.py` passed them.

`tests.md` already asks the right question — *what change to the production code would make this fail?* — and the honest answer is that a reader can talk themselves into one. Mutation turns that question into a command with an output. **Proven, not argued.**

## When it runs — three situations, and nothing else

| Situation | What the mutation settles |
|---|---|
| A **test finding the judgment pass intends to report**: asserts nothing that can fail, asserts only on mocks, tautology | The finding claims the test cannot fail. That claim is checkable, and reporting it unchecked is the same unearned confidence the finding is about |
| A **proposed rewrite of a test's assertions** (Step 5 fix) | That the rewrite pins something the old assertion did not. A tightened assertion that still passes under the mutation tightened nothing |
| A **proposed test deletion** | `Never touch` makes this near-forbidden, and a mutation showing the test guards nothing is the only evidence strong enough to allow one. **Tightening is still preferred**, and a proven-empty test is an argument for tightening it first |

**Match on the defect, not the severity label.** The same false coverage arrives as P2 outside Python — `tests.md` has both reach tables. A trigger written as "P1 only" exempts the commonest form of the thing it exists to catch.

**It does not run over every test in the diff.** Mutation costs a tree copy and a suite run per finding, and a run that mutates forty tests does not finish. It is reserved for findings that are about to make a strong claim. A duplicate test, an unexplained skip, an unrequested fixture — none of those is a claim about failability, and none gets a mutation.

The scanner stamps `mutation_candidate: true` on the false-coverage findings in its `--json` output, so the candidate set is a filter over `scan.json` rather than a rule you re-derive. It is a convenience and not the trigger: a judgment-pass finding no rule produced — the dedup case below is one — is a candidate on the same terms.

## The procedure

**1. Copy the tree. Never mutate the working tree.**

Any recursive copy will do; the rule is what it excludes, not which tool makes it. `cp -a` and `rsync` are fine where they exist and neither is on a Windows runtime, so the portable form goes through the interpreter Step 1 already resolved:

```bash
# illustration only — the shape, not a block to paste
ID=mock-only_test_unique_slugs
"$PY" -c "import shutil, sys; shutil.copytree('.', sys.argv[1], symlinks=True, \
  ignore=shutil.ignore_patterns('.git', '.code-winnow'))" ".code-winnow/mutation/$ID"
```

`$ID` is a short slug you choose — the rule and the test name — unique within the run and safe as a directory name. `copytree` refuses a destination that already exists, which is the same backstop Step 2's plain `mkdir` provides: a second mutation writing into the first one's copy proves something about a tree nobody described.

- **Copy the tree as it stands, including uncommitted changes.** The review is *of* uncommitted work; a copy taken from `git archive` or a fresh clone is a different tree, and a mutation of it proves something about a commit nobody asked about.
- **Exclude `.git/` and `.code-winnow/`.** The second is what stops the copy containing a copy.
- **Never run a git write command inside the copy** — no `checkout`, `stash`, `commit`, `clean`, `reset`. The copy has no `.git/`, so those commands walk *up* to the real repository and act on the user's work. A `git worktree` is not a substitute for the copy either: it shares the object store and the index with the tree under review.
- **Delete the copy when done, pass or fail.** It is transient, it is never an artifact, and nothing in the workspace index links to it.

**2. Derive the mutation from what the test names** — its name, its docstring, and the finding. `test_unique_slugs_drops_repeats` names one behaviour; the mutation removes that behaviour and nothing else. If the test's name and its body disagree about what it covers, the name is what the suite advertises, so the name wins.

**3. Break that one behaviour with the smallest edit that removes it** — delete the guard, invert the condition, remove the write. **One mutation per finding.** Two at once cannot be attributed: a green run no longer says which behaviour went unnoticed. Record the exact edit as a diff in the report; a mutation nobody can read is a claim about a claim.

**4. Run the narrowest command that executes the finding's test in the copy** — that test, or its file. Not the suite: a whole-suite run buries the one result in noise and multiplies every risk in the safety section below. **Record the command and its output.**

**5. Read the result. There are two, and both are results.**

| The test | Verdict |
|---|---|
| **Stays green** | **Proven.** The behaviour the test is named for is gone and the test did not notice, which is what the finding said |
| **Goes red** | **The finding is wrong.** Dismiss it, and record the mutation as the reason it was dismissed. That dismissal is worth as much as a confirmation — it is a settled question with a command behind it, and it stops the next run re-arguing the same line |

A test that goes red for a reason other than its assertion — a collection error, an import that no longer resolves, a fixture that raises — is neither result. The mutation broke the harness rather than the behaviour. Narrow the edit and run it again, or mark the finding **argued** and say so.

## Closing the loop — Step 6

**When a proven-broken test is tightened, re-run the same mutation against the fixed test and show it now fails.** Same copy procedure, same edit, the new assertion. A tightening that stays green under the mutation it was written to catch has fixed nothing and reads exactly like a fix.

**A fix without that re-run is argued, not proven, and the report must say which it is.** This is the one place the label can be earned cheaply and lost silently: the mutation is already written down from Step 3, so re-running it costs a copy and a command.

## When mutation is skipped — the `argued` label

Skip it when the behaviour the test names cannot be located, when the suite cannot run in isolation, or when the copy-and-run exceeds a sensible time box — say which, and say what the box was. Then **keep the finding** and mark it **argued** rather than proven.

**Never fake the label.** A finding marked proven means the green-under-mutation output is in the report file, where the reader can check it. If that output is not there, the finding is argued, whatever you believe about it.

**Argued findings are reportable, at their own severity.** The label lets the reader weight them; it is not a demotion, and demoting an unproven finding to P3 rebuilds the immunity `comment-evidence.md` refuses one rung down. A P1 that could not be mutated is still a P1 the user needs to see today.

## Safety

- **Mutated code never leaves the copy directory.** Nothing generated by this protocol is ever applied to the user's files; the Step 5 fixes are the only edits this skill makes, and they come from an approved plan.
- **If the test command in the copy could touch shared state — the network, a global service, a real database, a shared cache, a message queue — do not run it.** Mark the finding argued and say why. The protocol proves tests; it does not exercise side effects, and a mutation that fires a real webhook has done something the user did not approve and cannot undo.
- **The copy is inside `.code-winnow/`**, which Step 0 excluded from git and the scanner hard-skips by directory prefix. That is what keeps a deliberately-broken tree out of the diff under review and out of the next scan.
- **Delete the copy when done.** A sabotaged tree left on disk under a plausible name is the one artifact of this protocol that can hurt somebody later.

## Worked example — the dedup filter

The fixture is `$WINNOW/examples/mutation/`, and it is real: `tests/test_mutation.py` runs the whole example below on every suite run, so an example that stopped working would fail this skill's own tests.

**The finding.** `examples/mutation/test_dedup.py:16` — `test_unique_slugs_drops_repeats` calls `unique_slugs`, discards the result, rebuilds the dedup filter from its own list comprehensions and asserts on those. No production behaviour can make it fail. P1, false coverage. The scanner is silent on it — there is an assertion, no mock and no tautology — so this is a judgment-pass finding with no rule behind it, which is the case the protocol exists for.

**The mutation.** Delete the guard from `unique_slugs`, which is the entire behaviour the test is named for:

<!-- winnow:mutation id=guard start -->
```diff
-        if slug in seen:
-            continue
```
<!-- winnow:mutation id=guard end -->

**The command, in the copy:**

```bash
# illustration only — run inside .code-winnow/mutation/$ID/
python3 -m pytest examples/mutation/test_dedup.py::test_unique_slugs_drops_repeats -q
```

```
.                                                                        [100%]
1 passed in 0.00s
```

**Verdict: proven.** The dedup filter is gone and the test passes. Both lines go in the report — the diff and the output — because that pair *is* the proof.

**The fix.** Tighten the assertion; do not delete the test. What the test was named for is worth pinning, and now nothing pins it:

<!-- winnow:mutation id=tighten start -->
```diff
-    unique_slugs(names)
-    slugs = [n.strip().lower() for n in names]
-    assert [s for i, s in enumerate(slugs) if s not in slugs[:i]] == ["ada", "grace"]
+    assert unique_slugs(names) == ["ada", "grace"]
```
<!-- winnow:mutation id=tighten end -->

**The same mutation, against the tightened test:**

```
>       assert unique_slugs(names) == ["ada", "grace"]
E       AssertionError: assert ['ada', 'ada', 'grace'] == ['ada', 'grace']

examples/mutation/test_dedup.py:18: AssertionError
1 failed in 0.01s
```

Red. The loop is closed, and Step 6 reports the fix as **proven** rather than applied.

The two marked blocks above are extracted by `tests/test_mutation.py` and applied to a copy of the fixture, so the example and the code it describes cannot drift apart. Editing either one without the other fails that test.
