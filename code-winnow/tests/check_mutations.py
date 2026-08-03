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
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WINNOW = os.path.dirname(HERE)
SCAN = os.path.join(WINNOW, "scripts", "scan.py")
SKILL = os.path.join(WINNOW, "SKILL.md")


# (name, target_file, find, replace_with, pytest -k expression that MUST fail)
#
# SKILL.md is a mutation target too. Its embedded scripts are executable
# artifacts that test_workflow.py extracts and runs, so a guard written into
# one of them can go vacuous exactly like a guard in scan.py can.
MUTATIONS = [
    ("directive-exemption", SCAN,
     "    if is_directive(text):\n        return None\n",
     "    if False:\n        return None\n",
     "directive"),

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
    ("status-fail-closed", SKILL,
     r'''m = re.search(r"(?m)^\s*Status:\s*(\S.*?)\s*$", header)
if not m:
    sys.exit("REFUSING: no `Status:` line in the plan header. A plan nobody "
             "approved reads exactly like one nobody wrote a status for, so "
             "this refuses both. Add `Status: APPROVED by <who> on <date>` "
             "only if a human actually approved these findings.")
if not m.group(1).upper().startswith("APPROVED"):
    sys.exit(f"REFUSING: Status reads {m.group(1)!r}, not APPROVED. An "
             "unattended run writes UNAPPROVED because nobody reviewed the "
             "findings, and applying it would route around the Step 4b gate.")''',
     r'''if "UNAPPROVED" in header:
    sys.exit("REFUSING: UNAPPROVED")''',
     "step5a"),

    # Agent D's notes are never applied, and nothing mechanical enforces that
    # except the notes document failing to parse as a fix plan. Three ways it
    # could start parsing, one row each - the tokens Step 5a finds items and
    # paths by, and the Status line that gates the whole script.
    ("notes-doc-no-file-line", SKILL,
     "  frequency:  once per FixedUpdate",
     "  file:       src/Grid.cs\n  frequency:  once per FixedUpdate",
     "notes"),

    ("notes-doc-no-item-marker", SKILL,
     "- src/Grid.cs:22",
     "- [ ] src/Grid.cs:22",
     "notes"),

    ("notes-doc-status-not-approved", SKILL,
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
]


def run(argv, cwd=None):
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    pristine = {t: open(t, encoding="utf-8").read()
                for t in {m[1] for m in MUTATIONS}}

    base = run([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=WINNOW)
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
        try:
            open(target, "w", encoding="utf-8").write(original.replace(find, repl, 1))
            got = run([sys.executable, "-m", "pytest", "tests/", "-q", "-k", kexpr],
                      cwd=WINNOW)
        finally:
            open(target, "w", encoding="utf-8").write(original)

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
