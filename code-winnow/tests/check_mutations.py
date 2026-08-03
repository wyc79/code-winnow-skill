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
    python3 tests/check_mutations.pydeclined   # substring filter

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
        if got.returncode == 0:
            print(f"  VACUOUS  {name:28} tests still pass with the fix removed")
            print(f"           -k {kexpr!r} -> {tail}")
            failures.append(name)
        else:
            nfail = len(re.findall(r"^FAILED ", got.stdout, re.M))
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
