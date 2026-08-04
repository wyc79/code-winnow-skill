#!/usr/bin/env python3
"""Step 5a: copy every file an approved fix plan names, before the first edit.

    python3 scripts/backup.py <dest-dir> <plan>.fixplan.md

The advertised default scope is uncommitted work *including untracked files*.
"Fix all" then deletes lines from files that have never been in the object
store - no blob, no reflog, no `git checkout --`, no `git stash pop`. The
headline trigger for this skill is "clean this up before I commit", so the
common case is precisely the one git cannot undo.

The list comes from the plan's `file:` lines, not from the scanner JSON: Agent
C's whole purpose is producing findings on files the diff never touched, so an
untouched doc has no entry in that JSON at all - and would be edited with no
copy made.

Six failure modes are designed out. Every one of them was reachable, and each
fails silently in the version that lacks the guard:

1. **Fails closed on `Status:`.** A plan with no `Status:` line is what a
   truncated write, a hand-assembled plan, or one reconstructed from a report
   all produce, so absence has to refuse too. Only the unattended path marks
   itself; nothing marks the unmarked case.
2. **Counts plan items independently of the paths it captured.** A count
   derived from the capturing regex can never report its own miss.
3. **Refuses a non-empty destination.** `$STEM` is pinned for the session, so a
   second Step 5a - a follow-up "also fix 7 and 8", or a rung-2 fix agent that
   re-ran the step - copies *post-fix* files over the originals and prints the
   same success line as a healthy first run.
4. **Refuses a destination that is not the plan's sibling `pre-fix/`.** Two
   ways that goes wrong. The header is prose: `Backup: <path>  (NOT YET MADE)`
   pasted into the argument made a real directory called "  (NOT YET MADE)"
   inside the intended one, printed the usual success line, and left `Undo:`
   pointing at an empty directory. And a destination in a *different* round
   silently separates a plan from its restore point, which is only discovered
   when someone tries to undo.
5. **Refuses on any missing file** instead of printing a note and continuing.
6. **Resolves against the git toplevel.** With `os.getcwd()`, running from a
   subdirectory backs up nothing and exits 0.

Exit status is 0 on success and 1 on any refusal. Every refusal prints a line
starting `REFUSING:` and means stop and tell the user - do not edit, and do not
"fix" the plan by dropping the item that would not parse.
"""

import os
import re
import shutil
import subprocess
import sys

ITEM = re.compile(r"(?m)^\s*-\s*\[.\]\s")


def git_toplevel():
    """The repo root, so a run from a subdirectory backs up the same files."""
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         capture_output=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        sys.exit("REFUSING: not inside a git repository, so the plan's "
                 "relative `file:` paths cannot be resolved.")
    return out.stdout.strip()


def check_status(header):
    """Approval gate. Absence is not permission."""
    m = re.search(r"(?m)^\s*Status:\s*(\S.*?)\s*$", header)
    if not m:
        sys.exit("REFUSING: no `Status:` line in the plan header. A plan "
                 "nobody approved reads exactly like one nobody wrote a "
                 "status for, so this refuses both. Add `Status: APPROVED by "
                 "<who> on <date>` only if a human actually approved these "
                 "findings.")
    if not m.group(1).upper().startswith("APPROVED"):
        sys.exit(f"REFUSING: Status reads {m.group(1)!r}, not APPROVED. An "
                 "unattended run writes UNAPPROVED because nobody reviewed "
                 "the findings, and applying it would route around the Step "
                 "4b gate.")


def check_dest_shape(dest, plan_path):
    """A destination computed from the plan's location, not parsed out of its
    prose header and not pointed at another round.

    Two failures, one check. The header is prose: `Backup: <path>  (NOT YET
    MADE)` pasted into the argument once made a real directory of that name,
    printed the usual success line, and left `Undo:` pointing at an empty
    directory. And a restore point written into a different round than the plan
    being executed silently separates a plan from its originals - which is only
    discovered when someone tries to undo."""
    if re.search(r"\(|\s{2,}", dest):
        sys.exit(f"REFUSING: backup destination {dest!r} contains a "
                 "parenthetical or a run of spaces, so it was pasted from the "
                 "plan header instead of computed. Use the plan's sibling "
                 "`pre-fix/` directory.")
    want = os.path.join(os.path.dirname(plan_path), "pre-fix")
    if os.path.abspath(dest) != os.path.abspath(want):
        sys.exit(f"REFUSING: backup destination {dest!r} is not the plan's "
                 f"sibling `pre-fix/`. The plan lives in "
                 f"{os.path.dirname(plan_path)!r}, so the restore point is "
                 f"{want!r}. Compute it from the plan's path; do not copy it "
                 "out of the header.")


def plan_paths(whole):
    """Every `file:` path in the plan, in order, deduplicated."""
    # Count items on BOTH sides of the cut. Truncating first meant a section
    # appended after "## Never touch" - which is where an edit naturally lands
    # - vanished before either counter saw it, and the run printed a clean
    # "backed up 1 file(s) from 1 plan item(s)".
    plan = whole.split("\n## Never touch")[0]
    if len(ITEM.findall(whole)) != len(ITEM.findall(plan)):
        sys.exit("REFUSING: fix items appear after '## Never touch'. Move "
                 "them above it so they are backed up.")

    items = re.split(r"(?m)^\s*-\s*\[.\]\s", plan)[1:]
    if not items:
        sys.exit("REFUSING: no fix items found in the plan.")

    paths, bad = [], []
    for n, body in enumerate(items, 1):
        found = re.findall(r"(?m)^\s*file:\s*(\S.*?)\s*$", body)
        (paths.extend(found) if found else bad.append(n))
    if bad:
        sys.exit(f"REFUSING: plan item(s) {bad} have no `file:` line, so "
                 "their target cannot be backed up. Fix the plan first.")
    return list(dict.fromkeys(paths)), len(items)


def main(argv):
    if len(argv) != 2:
        sys.exit("usage: backup.py <dest-dir> <plan>.fixplan.md")
    dest, plan_path = argv

    # Absolute BEFORE the chdir: the plan path is relative to wherever the
    # caller stood, and the `file:` paths inside it are relative to the root.
    plan_path = os.path.abspath(plan_path)
    os.chdir(git_toplevel())
    if not os.path.isfile(plan_path):
        sys.exit(f"REFUSING: no fix plan at {plan_path}.")
    whole = open(plan_path, encoding="utf-8").read()

    check_status(whole.split("\n## ")[0])
    check_dest_shape(dest, plan_path)

    if os.path.isdir(dest) and os.listdir(dest):
        sys.exit(f"REFUSING: {dest} exists and is not empty. A second Step 5a "
                 "would overwrite the restore point with post-fix content. "
                 "Move it aside, or use a fresh stem.")

    uniq, n_items = plan_paths(whole)

    missing = [p for p in uniq if not os.path.isfile(p)]
    if missing:
        sys.exit("REFUSING: named in the plan but not on disk:\n  "
                 + "\n  ".join(missing))

    for p in uniq:
        d = os.path.join(dest, p)
        os.makedirs(os.path.dirname(d) or dest, exist_ok=True)
        shutil.copy2(p, d)
    print(f"backed up {len(uniq)} file(s) from {n_items} plan item(s) to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
