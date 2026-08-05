#!/usr/bin/env python3
"""Mutation check: does each test actually fail when its fix is removed?

A passing test proves nothing on its own. Twelve parametrized tests here once
asserted that directive comments are exempt from the comment rules, and all
twelve passed with the exemption stubbed out - the fixture could not trigger
those rules either way. They also asserted against two rule names that do not
exist in the scanner. The suite was green and the feature was unverified.

This script breaks each fix in turn and requires the matching tests to fail.
A mutation that leaves the suite green means the tests are not pinning it.

    python3 tests/check_mutations.py           # all mutations
    python3 tests/check_mutations.py declined  # substring filter

Slow (one pytest run per mutation), so it is not part of the default suite.
Run it whenever you add a regression test, and before believing one.

**It never edits the tree it is run from.** Everything is copied to a temp
directory first and broken there, so an interrupted run cannot leave a
sabotaged scanner on disk, and the repo stays safe to edit while it runs.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
WINNOW = os.path.dirname(HERE)
SCAN = os.path.join(WINNOW, "scripts", "scan.py")
BACKUP = os.path.join(WINNOW, "scripts", "backup.py")
SKILL = os.path.join(WINNOW, "SKILL.md")
REPORT_FORMAT = os.path.join(WINNOW, "references", "report-format.md")
TEST_SCAN = os.path.join(WINNOW, "tests", "test_scan.py")
NOTES_TPL = os.path.join(WINNOW, "scaffold", "round", "notes.md")


# (name, target_file, find, replace_with, pytest -k expression that MUST fail)
#
# SKILL.md is a mutation target too. Its embedded scripts are executable
# artifacts that test_workflow.py extracts and runs, so a guard written into
# one of them can go vacuous exactly like a guard in scan.py can. The same
# holds for the templates in references/report-format.md: the notes document's
# shape is what stops an executor treating Agent D's hypotheses as a fix plan.
MUTATIONS = [
    ("directive-exemption", SCAN,
     "    if is_directive(text):\n        return None\n",
     "    if False:\n        return None\n",
     "directive"),

    # meta.json's `scope` is a stable identity, never resolve_diff's human
    # label - which carries an untracked count that changes between runs. A
    # matcher keyed on the label finds no prior round, every run, and every
    # report says "Previous run: none" indistinguishably from a first run.
    ("meta-scope-identity", SCAN,
     '    if target in ("staged", "uncommitted", "worktree", "files"):\n'
     '        return target\n'
     '    return f"branch vs {target}"',
     '    return "worktree"',
     "meta_scope_is_stable or meta_branch_scope"),

    # Pairing rounds by recency alone reconciles a worktree run against a
    # branch baseline, which reports every untouched finding as `resolved`.
    ("meta-prior-round-scope", SCAN,
     '        if m.get("scope") != scope_id:\n            continue\n',
     '        if False:\n            continue\n',
     "meta_prior_round_matches_scope"),

    # A restore point in a different round than the plan being executed leaves
    # `Undo:` pointing at files that were never the originals, and nothing says
    # so until someone tries to undo.
    ("backup-dest-sibling", BACKUP,
     "    if os.path.abspath(dest) != os.path.abspath(want):\n",
     "    if False:\n",
     "backup_refuses_a_destination_in_another_round"),

    # Numbering in arrival order instead of file order: ast.walk is
    # breadth-first, so a nested handler is numbered before a shallower one
    # written below it, and the executor counts anchors top-to-bottom.
    ("occurrence-file-ordering", SCAN,
     'for n, f in enumerate(sorted(group, key=lambda x: x["line"]), 1):',
     'for n, f in enumerate(group, 1):',
     "occurrence or declin"),

    ("declined-instance-matching", SCAN,
     "        occ = d.get(\"occurrence\")\n",
     "        occ = None\n",
     "declin"),

    ("exposed-attribute-walk", SCAN,
     "        if EXPOSED.search(code):\n            return True\n",
     "        if False:\n            return True\n",
     "attribute or confirm_note or exposed"),

    ("trojan-source-bidi", SCAN,
     '    "\\u2066": "bidi isolate (LRI)",',
     '    "\\u0000_disabled_LRI": "bidi isolate (LRI)",',
     "trojan or bidi or unicode"),

    ("prose-nbsp-demotion", SCAN,
     '                if soft and illustrative:',
     '                if False:',
     "nbsp or prose or invisible_character"),

    # A file that only lost lines has no entry in a map keyed on additions,
    # so the scan reports "No diff found" on a tree with real work.
    ("deletion-only-scope", SCAN,
     "    out = {p: v for p, v in added.items() if v}\n"
     "    for path in REMOVED_AT:\n"
     "        out.setdefault(path, set())\n"
     "    return out",
     "    return {p: v for p, v in added.items() if v}",
     "deletion_only"),

    # Attribute by anchor line instead of by span: a deletion inside a test
    # body leaves every surviving line untouched, so the now-assertionless
    # test is filed pre-existing and silently dropped.
    ("deletion-span-attribution", SCAN,
     "    return any(n in added or n in removed_at for n in range(lo, hi + 1))",
     "    return lo in added",
     "never_touched"),

    # Revert the approval gate to the fail-OPEN form it shipped with: refuse
    # only what explicitly says UNAPPROVED. A plan with no Status line then
    # applies - the shape a truncated write or a hand-rolled plan produces -
    # routing straight around the Step 4b gate.
    ("status-fail-closed", BACKUP,
     '    if not m:\n        sys.exit("REFUSING: no `Status:` line',
     '    if False:\n        sys.exit("REFUSING: no `Status:` line',
     "step5a"),

    # Agent D's notes are never applied, and nothing mechanical enforces that
    # except the notes document failing to parse as a fix plan. Three ways it
    # could start parsing, one row each - the tokens Step 5a finds items and
    # paths by, and the Status line that gates the whole script.
    ("notes-doc-no-file-line", NOTES_TPL,
     "  frequency:  <fill: how often it runs, and over how much>",
     "  file:       src/Grid.cs\n"
     "  frequency:  <fill: how often it runs, and over how much>",
     "notes"),

    ("notes-doc-no-item-marker", NOTES_TPL,
     "- <fill: path:line",
     "- [ ] <fill: path:line",
     "notes"),

    ("notes-doc-status-not-approved", NOTES_TPL,
     "Status:   NOT APPLIED",
     "Status:   APPROVED",
     "notes"),

    # A secrets rule earns its place only if it stays quiet. Break the
    # placeholder guard and every redacted config line becomes a P1 - which is
    # how a reader learns to skim the severity that must never be skimmed.
    ("secret-placeholder-guard", SCAN,
     "    if len(set(val)) <= 2:\n        return True\n",
     "    if False:\n        return True\n",
     "placeholder"),

    ("secret-placeholder-words", SCAN,
     "    return any(w in low for w in PLACEHOLDER_WORDS)",
     "    return False",
     "placeholder"),

    # The inverse failure: a live vendor token demoted in a test file, where
    # keys most often leak. Every other universal rule demotes there, so this
    # exemption is one edit away from being "tidied up" into consistency.
    ("secret-no-test-demotion", SCAN,
     '            add(findings, path, idx, "P1", "committed-secret",\n'
     '                "credential in a recognised vendor format - rotate it; "',
     '            add(findings, path, idx, "P2" if illustrative else "P1",\n'
     '                "committed-secret",\n'
     '                "credential in a recognised vendor format - rotate it; "',
     "vendor_token"),

    # The exemption for tokens must stay narrower than the one for assigned
    # literals. Widening it to the filler-word list looks like consistency and
    # silently drops any real token that happens to contain `nil` or `test` -
    # a false negative, on the rule where that is the worst outcome available.
    ("secret-token-exemption-width", SCAN,
     "elif m_token and not looks_like_documented_example(m_token.group(0)):",
     "elif m_token and not looks_like_placeholder(m_token.group(0)):",
     "filler_word"),

    # Same argument, one rung finer, and the rung the shipped code was on: the
    # narrowed list was still applied as a *substring*, so a well-formed token
    # whose random body contained `sample` anywhere was dropped in silence.
    # Anchoring at the end is the whole fix, and a suffix test is exactly what
    # a careless "simplification" would widen back to `in`.
    ("secret-token-exemption-anchoring", SCAN,
     "    return token.lower().endswith(DOC_EXAMPLE_SUFFIXES)",
     "    low = token.lower()\n"
     "    return any(w in low for w in DOC_EXAMPLE_SUFFIXES)",
     "filler_word"),

    # The other direction. Deleting the exemption outright makes every copy of
    # AWS's published `...EXAMPLE` key a P1, which is the false positive the
    # exemption exists for - so the narrowing has to be pinned from both sides.
    ("secret-doc-example-exemption", SCAN,
     "    return token.lower().endswith(DOC_EXAMPLE_SUFFIXES)",
     "    return False",
     "vendor_doc_marker or documentation_example"),

    # Reconciliation must see every finding that is still TRUE, not every
    # finding this report happens to print. Dropping the held-back preexisting
    # set reports untouched-line findings as "no longer true" the first time
    # anyone reconciles against a --whole-files baseline - which SKILL.md Step
    # 4 writes by name.
    ("since-counts-preexisting", SCAN,
     "            findings + declined + filtered_preexisting, args.since,",
     "            findings + declined, args.since,",
     "whole_files_baseline or genuinely_fixed"),

    # `finding_key` reads three fields; the guards used to check two. These
    # files are hand-maintained by instruction, so the third being absent is an
    # expected input - and it exited 1 with empty stdout under --json.
    ("prior-entry-key-fields", SCAN,
     'KEY_FIELDS = ("path", "rule", "message")',
     'KEY_FIELDS = ("path", "rule")',
     "partial_prior"),

    # Pinning the UNC separators to exactly two-then-one matches a config file
    # and misses every escaped source literal, which is the commoner form.
    ("unc-escaped-separators", SCAN,
     r'r"(?<![A-Za-z0-9:_])\\{2,4}[A-Za-z][A-Za-z0-9._-]{2,}\\{1,2}'
     r'[A-Za-z0-9._$-]+")',
     r'r"(?<![A-Za-z0-9:_])\\\\[A-Za-z][A-Za-z0-9._-]{2,}\\'
     r'[A-Za-z0-9._$-]+")',
     "escaped_source_literal"),

    # The other half of the same trade. Widening the separators without the
    # lookbehind makes `C:\\Users\\me` a "host reference" - a false positive
    # in every Windows codebase, and a strictly worse outcome than the miss
    # the widening was there to fix.
    ("unc-drive-path-lookbehind", SCAN,
     r'r"(?<![A-Za-z0-9:_])\\{2,4}',
     r'r"\\{2,4}',
     "drive_path"),

    # A prior finding whose file was never opened is not evidence of a fix.
    ("since-out-of-scope-split", SCAN,
     "            if scanned_paths is not None and f[\"path\"] not in scanned_paths:",
     "            if False:",
     "left_scope or scanned_file_is_still"),

    # `auto` on a dirty branch reviews the uncommitted work only. Deliberate -
    # but going silent about the commits it skipped is what made it a hole.
    ("auto-out-of-scope-commits-warning", SCAN,
     "                    warn_if_commits_are_out_of_scope(base)",
     "                    pass",
     "dirty_branch_warns or clean_tree_branch_review_does_not"),

    # A refusal produces no stem, so the empty-scope guard fires on top of it
    # and its advice ("pass --base <ref>") is the retry Step 1 forbids.
    ("step2-refusal-passthrough", SKILL,
     """  if grep -q '^REFUSING:' "$ERRF"; then""",
     """  if false; then""",
     "refusal"),

    # Without the text test the builder cats untracked binaries into the file
    # five judgment agents are handed, and `-s` passes because it is large.
    ("step3-binary-exclusion", SKILL,
     '      if ! LC_ALL=C grep -qI . "$f" 2>/dev/null; then',
     '      if false; then',
     "untracked_binary"),

    # A backup path pasted out of the plan header instead of computed.
    ("step5a-backup-path-shape", BACKUP,
     '    if re.search(r"\\(|\\s{2,}", dest):',
     '    if False:',
     "pasted_from_the_plan"),

    # The plan's `file:` lines are the whole backup list. Parse the path out of
    # the headline sentence instead and you lose paths with spaces, items with
    # no `:LINE`, and the second file of every merged finding - while printing
    # a success count derived from the same regex that just missed them.
    ("step5a-file-line-required", BACKUP,
     '        (paths.extend(found) if found else bad.append(n))',
     '        paths.extend(found)',
     "step5a"),

    # A test file is a mutation target too. The secrets fixtures are assembled
    # from pieces so that scanning test_scan.py does not trip the rule it
    # tests; writing one as a literal is the obvious, readable thing a
    # contributor would do, and it silently puts a permanent P1 in this repo.
    # The key is spliced here for the same reason it is spliced there.
    ("secret-fixture-assembled", TEST_SCAN,
     'AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLQ"',
     'AWS_KEY = "AKIA' + 'IOSFODNN7EXAMPLQ"',
     "no_fixture_in_this_file"),

    # The next three rows are all the same shape of mistake: the obvious
    # pattern is one token wider than the rule, and the extra width is live
    # code. Each row widens it back and requires the quiet-side test to catch
    # it, because a narrowing with no test is a narrowing the next reader
    # simplifies away.

    # `\bdebugger\b` reads like the whole rule and flags `this.debugger.attach()`
    # at P1. That one form is what this row rests on: `debuggerEnabled` in the
    # same fixture matches neither pattern, so it guards nothing here.
    ("js-debugger-anchoring", SCAN,
     r'RE_JS_DEBUGGER = re.compile(r"(?:^|[;{])\s*debugger\s*(?=[;}]|\s*$)")',
     r'RE_JS_DEBUGGER = re.compile(r"\bdebugger\b")',
     "debugger_is_quiet_on_an_identifier"),

    # Matching the attribute without the element flags `<div role="button">`,
    # which is ARIA doing its job and the only thing naming that element.
    ("html-role-element-gating", SCAN,
     r'r"<button\b[^>]*\brole',
     r'r"(?:)[^>]*\brole',
     "redundant_role_is_quiet_on_a_div"),

    # A "-webkit- is legacy" sweep proposes deleting -webkit-line-clamp and
    # friends, and the page silently loses line clamping and momentum scroll.
    ("css-prefix-named-list", SCAN,
     r'r"(border-radius|box-shadow|box-sizing|opacity|border-image"',
     r'r"([a-z-]+|border-image"',
     "dead_prefix_is_quiet_on_prefixes_still_required"),

    # `elif` here reviews a third of a single-file component and reports the
    # other two thirds as clean.
    ("web-dispatch-not-exclusive", SCAN,
     "    if ext in HTML_EXT:\n        check_html(path, lines, findings)",
     "    elif ext in HTML_EXT:\n        check_html(path, lines, findings)",
     "single_file_component"),

    # Ungated, Jasmine's `fit(` is a P1 on every `fit(chart, bounds)` in a
    # layout module.
    ("web-jasmine-test-gating", SCAN,
     "or (is_test and RE_JS_TEST_ONLY_JASMINE.search(code))",
     "or RE_JS_TEST_ONLY_JASMINE.search(code)",
     "jasmine_is_quiet_outside_a_test_file"),

    # The empty-rule pattern matches `methods: {}` and `function f() {}`
    # exactly. Ungated by extension it reports live JavaScript in a .vue
    # script block as an abandoned CSS rule.
    ("web-empty-rule-scope", SCAN,
     "        if pure_css and RE_CSS_EMPTY_RULE.match(text):",
     "        if RE_CSS_EMPTY_RULE.match(text):",
     "empty_rule_is_quiet_in_a_single_file_component"),

    # Without the blanking pass, a commented-out block of old CSS is a page of
    # findings - and it is the block most likely to contain dead prefixes,
    # because that is why it was commented out.
    ("web-comment-blanking", SCAN,
     "    clean = _css_uncommented(lines)",
     "    clean = lines",
     "css_rules_are_quiet_inside_a_block_comment"),

    # check_js used `strip_code`, which is a Python/C#/C++ lexer: it does not
    # know a backtick opens a string, and it reads JS's private-name `#` as a
    # comment marker. Reverting to it reports findings against strings and
    # drops every rule on any line holding a private field.
    ("web-js-lexer", SCAN,
     "    clean = _js_uncommented(lines)\n"
     "    for idx in range(1, len(lines) + 1):\n"
     "        anchor = anchor_of(lines, idx)\n"
     "        code = clean[idx - 1]",
     "    for idx in range(1, len(lines) + 1):\n"
     "        anchor = anchor_of(lines, idx)\n"
     "        code = strip_code(lines[idx - 1])",
     "template_literal or private_field"),
]


def run(argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


# Everything this script breaks, it breaks inside a throwaway copy.
#
# `scaffold` is here because tests/ reads it. A directory the tests depend on
# but the mirror does not carry fails every one of those tests inside the
# mirror while passing in the real tree, and the harness reports it as a red
# baseline rather than as the missing copy it is.
COPY_DIRS = ("scripts", "tests", "references", "scaffold")
COPY_FILES = ("SKILL.md",)


def mirror(dst):
    """Copy the skill into `dst`, so a mutation never reaches the real tree.

    This used to edit `scripts/scan.py` in place and put it back in a
    `finally`. That is correct only while nothing goes wrong: Ctrl-C between
    the two writes, a crashed interpreter, or a machine losing power all leave
    a deliberately-broken scanner on disk with no warning - and the failure is
    invisible, because a mutated scanner still runs and still prints findings.
    It also means the tree is unsafe to touch for the several minutes this
    takes, so an edit made in parallel is silently reverted by the restore.
    Both were observed. A copy removes the whole class.
    """
    ignore = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
    for name in COPY_DIRS:
        src = os.path.join(WINNOW, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, name), ignore=ignore)
    for name in COPY_FILES:
        src = os.path.join(WINNOW, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst, name))


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    work = tempfile.mkdtemp(prefix="code-winnow-mutations-")
    try:
        return _run_all(only, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _run_all(only, work):
    mirror(work)
    # MUTATIONS names paths in the real tree; every write goes to the mirror.
    def mirrored(target):
        return os.path.join(work, os.path.relpath(target, WINNOW))

    pristine = {t: open(mirrored(t), encoding="utf-8").read()
                for t in {m[1] for m in MUTATIONS}}

    base = run([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=work)
    if base.returncode != 0:
        print("BASELINE SUITE IS RED - fix that first")
        print(base.stdout[-2000:])
        return 1
    print(f"baseline: {base.stdout.strip().splitlines()[-1]}\n")

    failures = []
    for name, target, find, repl, kexpr in MUTATIONS:
        if only and only not in name:
            continue
        original = pristine[target]
        if find not in original:
            print(f"  !! {name:28} MUTATION NO LONGER APPLIES "
                  f"({os.path.basename(target)} changed; update this script)")
            failures.append(name)
            continue
        path = mirrored(target)
        try:
            open(path, "w", encoding="utf-8").write(original.replace(find, repl, 1))
            got = run([sys.executable, "-m", "pytest", "tests/", "-q", "-k", kexpr],
                      cwd=work)
        finally:
            open(path, "w", encoding="utf-8").write(original)

        tail = got.stdout.strip().splitlines()[-1] if got.stdout.strip() else "(no output)"
        nfail = len(re.findall(r"^FAILED ", got.stdout, re.M))
        # `nfail == 0` is the case a return-code check alone waves through:
        # pytest exits 5 for "no tests collected", which is non-zero, so a `-k`
        # expression that has gone stale after a rename reported "ok, 0 test(s)
        # caught it" and the script exited 0. The staleness guard above checks
        # the `find` string; nothing checked the `-k` until this line.
        if got.returncode == 0 or nfail == 0:
            why = ("tests still pass with the fix removed" if got.returncode == 0
                   else "-k matched no tests - this row is stale, not passing")
            print(f"  VACUOUS  {name:28} {why}")
            print(f"           -k {kexpr!r} -> {tail}")
            failures.append(name)
        else:
            print(f"  ok       {name:28} {nfail} test(s) caught it")

    print()
    if failures:
        print(f"{len(failures)} mutation(s) unaccounted for - a surviving "
              "mutation means those tests verify nothing; one that no longer "
              "applies means this script is stale:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("every mutation was caught")
    return 0


if __name__ == "__main__":
    sys.exit(main())
