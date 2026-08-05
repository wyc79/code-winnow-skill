#!/usr/bin/env python3
"""code-winnow: deterministic candidate scanner. Stdlib only.

Reports CANDIDATES, not verdicts. Every hit needs human or model judgment
before it belongs in a report - a TODO in a test fixture and a TODO blocking
a shipped feature look identical from here.

Run it from anywhere inside the repo; paths resolve against the git toplevel.
Files it cannot read are reported loudly, never skipped in silence: a scan
that read nothing must not look like a scan that found nothing.

Usage:
    python3 scan.py                      # auto-resolve scope from git
    python3 scan.py --json               # machine-readable
    python3 scan.py --scope branch --base develop
    python3 scan.py --paths a.py b.cs    # scan whole files instead
    python3 scan.py --min-severity P2    # filter noise
    python3 scan.py --since PRIOR.json   # reconcile with the last run
"""

import argparse
import ast
import datetime
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

SEVERITY_ORDER = {"P1": 0, "P2": 1, "P3": 2}

PY_EXT = {".py"}
CS_EXT = {".cs"}
CPP_EXT = {".cpp", ".h", ".hpp", ".cc", ".inl"}
PROSE_EXT = {".md", ".txt", ".rst", ".adoc"}

# The web tier. `.vue`, `.svelte` and `.astro` are in all three sets because a
# single-file component IS all three, and every web rule is anchored on syntax
# that only occurs in its own language - so running the CSS pass over a
# component file costs nothing and finds the `<style>` block.
MIXED_WEB_EXT = {".vue", ".svelte", ".astro"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"} | MIXED_WEB_EXT
HTML_EXT = {".html", ".htm"} | MIXED_WEB_EXT
CSS_EXT = {".css", ".scss", ".sass", ".less"} | MIXED_WEB_EXT

TEST_HINT = re.compile(
    r"(^|[/\\_.])(tests?|specs?|fixtures?|testing|e2e|cypress|__tests__|"
    r"unittests?)([/\\_.]|$)"
    r"|(?:^|/)conftest\.py$"
    r"|[A-Za-z0-9]+(Tests?|Spec)\.[A-Za-z]+$"
    r"|_(test|spec|unittest)\.[A-Za-z]+$"
    r"|\.(test|spec|cy|e2e)\.[A-Za-z]+$",
    re.I)

# Paths whose contents nobody hand-wrote. Scanning them produces findings no
# one can act on and buries the ones they can.
VENDOR_HINT = re.compile(
    r"(^|/)(node_modules|vendor|third_party|thirdparty|external|dist|build|"
    r"out|obj|bin|Intermediate|Binaries|DerivedDataCache|Library|Temp|"
    r"__pycache__|\.venv|venv|site-packages|migrations|generated|gen)(/|$)"
    r"|\.(min|bundle|generated|designer|g|pb)\.[A-Za-z0-9]+$"
    r"|\.(lock|snap|map)$",
    re.I,
)

# This tool's own workspace. Step 0 excludes it from git, but an untracked
# scan must not review the report it is about to write even before that lands.
WORKSPACE_HINT = re.compile(r"(^|/)\.(code-winnow|de-slop)(/|$)")

DEFAULT_MAX_BYTES = 512 * 1024
MINIFIED_AVG_LINE = 500

# Non-fatal problems worth telling the user about. Collected, then printed.
WARNINGS = []
READ_ERRORS = []

# Fatal ones: the requested scope cannot be numbered and reviewed coherently,
# so the run stops instead of guessing. Kept apart from WARNINGS because these
# decide `complete` and the exit code - an empty scope is exit 0 and means a
# clean tree, a refusal is exit 2 and means nothing was reviewed. Each entry
# is the whole message, remedy included.
REFUSALS = []

# {path: {line}} - positions in the NEW file where the diff REMOVED content.
#
# Scope keyed on added lines cannot see a deletion-only change: cut a test's
# only assertion and every surviving line is untouched, so the assertionless
# test files as pre-existing and never reports. Accumulated like WARNINGS
# rather than threaded through resolve_diff's six return points - safe because
# each scan is its own process.
REMOVED_AT = defaultdict(set)

# {path: [line]} for every file actually read this run, so anchor totals are
# counted against the same bytes the rules fired on.
FILE_LINES = {}

# Every path opened and read this run. `reconcile` needs it to distinguish a
# prior finding that is GONE from one whose file was simply not in this run's
# scope - only the first is news, and only the first is honest to report.
SCANNED_PATHS = set()


def warn(msg):
    if msg not in WARNINGS:
        WARNINGS.append(msg)


# --------------------------------------------------------------------------
# git plumbing
# --------------------------------------------------------------------------

_REPO_ROOT = None


def _git(args, cwd=None):
    # core.quotePath=false stops git c-quoting every non-ASCII path. The
    # unquoter below still exists for paths carrying quotes or control
    # characters, which git escapes regardless of that setting.
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotePath=false"] + args,
            capture_output=True, check=False,
            cwd=cwd or _REPO_ROOT,
        )
    except (FileNotFoundError, OSError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace")


def repo_root():
    """Absolute path of the git toplevel, or None outside a repo.

    Everything git prints is relative to this, not to the cwd, so every path
    the scanner opens has to be joined onto it.
    """
    global _REPO_ROOT
    if _REPO_ROOT is None:
        out = _git(["rev-parse", "--show-toplevel"], cwd=os.getcwd())
        _REPO_ROOT = out.strip() if out and out.strip() else ""
    return _REPO_ROOT or None


def abs_path(rel):
    root = repo_root()
    return os.path.join(root, rel) if root else rel


def current_branch():
    out = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    if out is None:
        return "nogit"
    return out.strip() or "detached"


def ref_exists(ref):
    return _git(["rev-parse", "--verify", "--quiet", ref + "^{commit}"]) is not None


def discover_base():
    """First base ref that exists and is not the branch we are on.

    Ordered: the remote's default branch, then the usual names, local before
    remote-tracking. A repo branched off `develop`, or a fresh clone with only
    origin/* refs, both used to fall through to "no diff found".
    """
    head = current_branch()
    out = _git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    candidates = []
    if out and out.strip():
        candidates.append(out.strip().replace("refs/remotes/", ""))
    for name in ("main", "master", "develop", "development", "trunk"):
        candidates.extend([name, "origin/" + name])
    for ref in candidates:
        if ref.split("/")[-1] == head and "/" not in ref:
            continue
        if ref_exists(ref):
            return ref
    return None


def slug(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "unknown"


_C_ESCAPES = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11,
              "\\": 92, '"': 34}


def unquote_diff_path(target):
    """Decode git's c-style path quoting.

    The escapes are octal escapes of the path's UTF-8 *bytes*, so they have to
    be rebuilt as bytes and decoded once at the end. `unicode_escape` reads
    them as latin-1 code points instead and turns every accented filename into
    mojibake that no longer names a file on disk.
    """
    target = target.strip()
    if not (len(target) > 1 and target.startswith('"') and target.endswith('"')):
        return target
    inner = target[1:-1]
    out = bytearray()
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch != "\\":
            out.extend(ch.encode("utf-8"))
            i += 1
        elif i + 1 < len(inner) and inner[i + 1] in _C_ESCAPES:
            out.append(_C_ESCAPES[inner[i + 1]])
            i += 2
        elif i + 3 < len(inner) and inner[i + 1:i + 4].isdigit():
            try:
                out.append(int(inner[i + 1:i + 4], 8))
                i += 4
            except ValueError:
                out.extend(ch.encode("utf-8"))
                i += 1
        else:
            out.extend(ch.encode("utf-8"))
            i += 1
    return out.decode("utf-8", errors="replace")


def parse_diff(raw, into=None):
    """Extract added line numbers per file from a unified diff.

    Only counts inside a hunk. The header lines (`diff --git`, `index`,
    `similarity index`, mode changes) are not file content and must not move
    the line cursor.
    """
    added = into if into is not None else defaultdict(set)
    path = None
    new_line = 0
    in_hunk = False
    # split_lines, not splitlines(): an added line carrying a form feed split
    # into two here, so the cursor advanced twice for one line and every added
    # line below it was recorded one too high.
    for line in split_lines(raw):
        if line.startswith("+++ "):
            target = unquote_diff_path(line[4:])
            path = None if target == "/dev/null" else re.sub(r"^b/", "", target)
            in_hunk = False
        elif line.startswith("--- "):
            in_hunk = False
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            new_line = int(m.group(1)) if m else 0
            in_hunk = bool(m)
        elif not in_hunk or path is None:
            continue
        elif line.startswith("+"):
            added[path].add(new_line)
            new_line += 1
        elif line.startswith("\\"):  # "\ No newline at end of file"
            continue
        elif line.startswith("-"):
            # A removed line has no number in the new file - it sat in a gap.
            # `@@ -3 +2,0 @@` means "after new line 2", so record both sides
            # of the gap and let a one-line overshoot stand: over-attributing
            # shows the finding, under-attributing hides it. See REMOVED_AT.
            REMOVED_AT[path].add(new_line)
            REMOVED_AT[path].add(new_line + 1)
            continue
        else:
            new_line += 1
    return added


def untracked_files():
    # -z: NUL-separated and never quoted, so no unquoting step can get it
    # wrong. Without it a non-ASCII new file arrived as a quoted literal and
    # every open() on it failed.
    out = _git(["ls-files", "--others", "--exclude-standard", "-z"])
    if not out:
        return []
    return [p for p in out.split("\0") if p.strip()]


def count_lines(rel):
    lines = read_lines(rel)
    return len(lines) if lines else 0


def in_scope(added):
    """Drop files with nothing in them, then add back the ones whose only
    change was a deletion.

    A deletion-only change otherwise resolves to an empty scope, and under
    `--scope auto` that is worse than a miss: the empty result falls through
    to the branch diff and reviews something else entirely.

    The value stays an empty set - no line was added, and `added_lines` should
    say so. REMOVED_AT is what carries the change. See touches_change.
    """
    out = {p: v for p, v in added.items() if v}
    for path in REMOVED_AT:
        out.setdefault(path, set())
    return out


def staged_then_edited(staged):
    """Staged files that have since been edited in the worktree.

    `git diff --name-only` is exactly the worktree-vs-index difference, so the
    intersection with the staged set is the set of files that cannot be
    numbered from the index and read from disk at the same time. Intersecting
    against `staged` - which has already been through in_scope - keeps a
    vendored or generated file from blocking a review it is not part of.
    """
    out = _git(["diff", "--name-only"])
    if not out:
        return []
    dirty = {unquote_diff_path(n) for n in out.splitlines() if n.strip()}
    return sorted(dirty & set(staged))


def post_commit_command():
    """A line to paste after committing, to review exactly what was committed.

    `--base <pre-commit HEAD>` makes the new commit the entire diff, and the
    branch scope reads the worktree, so it stays correct if editing continues.
    """
    head = (_git(["rev-parse", "--short", "HEAD"]) or "").strip()
    if not head:
        return None
    return (f"{os.path.basename(sys.executable)} {sys.argv[0]} "
            f"--scope branch --base {head}")


def refuse_staged_desync(moved):
    """Stop rather than mis-number.

    The silent form of this is the expensive one: findings below the shift are
    dropped from a `complete: true`, exit-0 report, and under `--since` the
    next run prints them as resolved - an active claim that a P1 was fixed.
    """
    listed = ", ".join(moved[:5]) + (" ..." if len(moved) > 5 else "")
    msg = (f"REFUSING: {len(moved)} file(s) are staged and have since been "
           f"edited ({listed}). `git diff --cached` numbers the staged blob, "
           "but every finding is read from the worktree, so the two describe "
           "different content and findings would be dropped in silence. "
           "Commit what you have staged and run this again, or pass "
           "--scope worktree to review the staged and unstaged work together.")
    cmd = post_commit_command()
    if cmd:
        msg += (" To review exactly what you committed, paste this after the "
                f"commit: {cmd}")
    REFUSALS.append(msg)


def warn_if_commits_are_out_of_scope(base):
    """`auto` on a dirty branch reviews the uncommitted work only. Say so.

    The default resolves to the union of uncommitted work whenever the tree is
    dirty, and only falls back to the branch diff when it is clean. So the
    normal shape of this skill's headline case - an agent wrote a feature,
    committed it, and left a few edits on top - reviews the edits and not the
    feature. Nothing was wrong with that reading of `auto`; what was wrong is
    that the commits went unmentioned, and README's own trigger list includes
    "about to open a PR", which is branch-shaped.

    Deliberately a warning and not a change of default. Silently widening
    `auto` to the whole branch would review 200 commits for someone who meant
    "my uncommitted tweaks", which is the reviewer-hostile diff this skill
    opens by refusing. The four-field integrity check in SKILL.md already
    tells the agent to read `warnings`; this is a fact for that check.
    """
    ref = base or discover_base()
    if not ref or not ref_exists(ref):
        return          # no base to compare against - discover_base warns
    out = _git(["rev-list", "--count", f"{ref}..HEAD"])
    try:
        n = int((out or "0").strip())
    except ValueError:
        return
    if n:
        warn(f"scope is uncommitted work only, but this branch is {n} "
             f"commit(s) ahead of '{ref}' - that work is NOT being reviewed. "
             f"Pass --scope branch to review the branch instead.")


def resolve_diff(scope="auto", base=None):
    """Return (label, target, {path: set(new_lines)}).

    `auto` unions everything uncommitted - staged, unstaged, and untracked -
    and only falls back to the branch diff when the working tree is clean.
    The old stop-at-first-non-empty ladder meant one staged file silently
    dropped every other edit out of scope, and untracked files - where
    generated code most often lands - were invisible in every mode.
    """
    if repo_root() is None:
        warn("not inside a git repository - use --paths to scan files directly")
        return None, None, {}

    def collect_untracked(added):
        """Fold every untracked file into `added`; return the paths taken.

        Shared by the worktree scope and the branch scope, and that sharing is
        the point. Branch scope used to skip this entirely, so a new file that
        had never been committed was invisible to `--scope branch` while
        `complete` stayed true and `warnings` stayed empty - a P1 in a
        generated test file simply absent, with every integrity field saying
        the scan was whole. Untracked files are also where generated code
        concentrates, which is the case this skill exists for.

        It is the right call for branch scope specifically because the branch
        diff already runs merge-base to WORKTREE, not to HEAD: uncommitted
        edits are in scope, so uncommitted *files* were the one inconsistent
        exclusion. SKILL.md's Step 3 review-input builder has always appended
        them for this scope, so the scanner was also the odd half of a pair
        that has to describe the same bytes.
        """
        new_files = []
        for rel in untracked_files():
            reason = skip_path(rel)
            if reason:
                # Record it. Dropping these in silence meant a branch whose
                # only new files are generated came back as an empty scope,
                # which reads exactly like a clean tree.
                if not WORKSPACE_HINT.search(rel):
                    READ_ERRORS.append({"path": rel,
                                        "error": "skipped: " + reason})
                continue
            n = count_lines(rel)
            if n:
                added[rel].update(range(1, n + 1))
                new_files.append(rel)
        return new_files

    def worktree():
        # One diff, against HEAD. Diffing the index and the worktree
        # separately produced two sets of line numbers - `--cached` numbers
        # the index blob, plain `diff` numbers the worktree blob - and both
        # were then matched against the worktree file. After `git add -p`, or
        # "stage a fix and keep editing", every finding below the shift was
        # written off as pre-existing and dropped.
        added = defaultdict(set)
        sources = []
        raw = _git(["diff", "HEAD", "--unified=0", "--diff-filter=d"])
        if raw is None:
            # no commits yet: everything tracked is in the index
            raw = _git(["diff", "--cached", "--unified=0", "--diff-filter=d"])
        if raw and raw.strip():
            parse_diff(raw, added)
        for label, args in (("staged", ["diff", "--cached", "--name-only"]),
                            ("unstaged", ["diff", "--name-only"])):
            names = _git(args)
            if names and names.strip():
                sources.append(label)
        new_files = collect_untracked(added)
        if new_files:
            sources.append(f"{len(new_files)} untracked")
        added = in_scope(added)
        return added, sources

    if scope in ("auto", "worktree", "staged", "unstaged"):
        if scope == "staged":
            raw = _git(["diff", "--cached", "--unified=0",
                        "--diff-filter=d"]) or ""
            added = in_scope(parse_diff(raw))
            if added:
                moved = staged_then_edited(added)
                if moved:
                    refuse_staged_desync(moved)
                    return None, None, {}
                return "staged changes (git diff --cached)", "staged", added
        elif scope == "unstaged":
            raw = _git(["diff", "--unified=0",
                        "--diff-filter=d"]) or ""
            added = in_scope(parse_diff(raw))
            if added:
                return "unstaged changes (git diff)", "uncommitted", added
        else:
            added, sources = worktree()
            if added:
                if scope == "auto":
                    warn_if_commits_are_out_of_scope(base)
                return ("uncommitted work (" + ", ".join(sources) + ")",
                        "worktree", added)
        if scope != "auto":
            return None, None, {}

    ref = base or discover_base()
    if ref is None:
        warn("no base branch found (tried origin/HEAD, main, master, develop, "
             "development, trunk) - pass --base <ref>")
        return None, None, {}
    if not ref_exists(ref):
        warn(f"base ref '{ref}' does not exist")
        return None, None, {}
    # Three dots on the base side - the merge base - so commits that landed on
    # the base after you branched are not counted as your changes. But diff
    # that merge base against the WORKTREE, not against HEAD: every finding is
    # read from disk, so pinning the head side to the last commit numbers a
    # blob the rules never saw, and one uncommitted insert above a finding
    # drops it from a `complete: true` report. Reviewing a branch you are
    # still working on is the normal case, so the dirty tree is the case that
    # has to work. `git merge-base` gets the base side without that pinning.
    merge_base = (_git(["merge-base", ref, "HEAD"]) or "").strip()
    if not merge_base:
        warn(f"could not diff against '{ref}' (no merge base?)")
        return None, None, {}
    raw = _git(["diff", "--unified=0", "--diff-filter=d", merge_base])
    if raw is None:
        warn(f"could not diff against '{ref}' (no merge base?)")
        return None, None, {}
    added = parse_diff(raw)
    collect_untracked(added)
    added = in_scope(added)
    if not added:
        return None, None, {}
    # The label stays exactly `branch vs <ref>` even when untracked files were
    # folded in. SKILL.md's Step 3 builder recovers the base with
    # `${SRC#branch vs }` and feeds it to `git merge-base`, so a count appended
    # here would be parsed as part of the ref name and the review input would
    # be built against nothing. The count is visible in `files` instead.
    return f"branch vs {ref}", ref, added


def report_stem(target, when=None):
    """current<branch>_target<base>_<time>, or _worktree_/_staged_/_files_
    for non-branch scopes. Timestamped so successive runs never overwrite."""
    when = when or datetime.datetime.now()
    stamp = when.strftime("%Y%m%d-%H%M")
    branch = slug(current_branch())
    if target in ("staged", "uncommitted", "worktree", "files"):
        return f"current{branch}_{target}_{stamp}"
    return f"current{branch}_target{slug(target)}_{stamp}"


def scope_identity(target):
    """A stable key for pairing rounds, which the human label is not.

    `resolve_diff` returns "uncommitted work (staged, unstaged, 3 untracked)";
    the count changes between runs, so a matcher keyed on it finds no prior
    round every time - silently, and indistinguishably from a first run.
    `meta.json` therefore carries both: `scope` for matching, `scope_label`
    for reading."""
    if target in ("staged", "uncommitted", "worktree", "files"):
        return target
    return f"branch vs {target}"


def round_number(round_dir):
    m = re.search(r"round-(\d+)$",
                  os.path.basename(os.path.normpath(round_dir)))
    return int(m.group(1)) if m else None


def prior_round(round_dir, scope_id):
    """The newest sibling round that reviewed the same scope, or None.

    Replaces a `ls -1t round-*/*.json | grep -v -- '-postfix\\|-p3'` search,
    which was a blocklist of ad-hoc filename suffixes and grew every time an
    agent invented one. Rounds written before meta.json existed are skipped
    rather than guessed at: reconciling against a mismatched baseline moves
    findings nobody touched into `resolved`, which reads as "your fixes
    worked"."""
    parent = os.path.dirname(os.path.abspath(round_dir))
    me = os.path.basename(os.path.normpath(round_dir))
    best, best_when = None, ""
    try:
        names = sorted(os.listdir(parent))
    except OSError:
        return None
    for name in names:
        if name == me or not re.fullmatch(r"round-\d+", name):
            continue
        try:
            with open(os.path.join(parent, name, "meta.json"),
                      encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        if m.get("scope") != scope_id:
            continue
        when = m.get("generated") or ""
        if when >= best_when:
            best, best_when = name, when
    return best


def _short_sha(rev):
    out = _git(["rev-parse", "--short", rev])
    return out.strip() if out and out.strip() else None


def _merge_base_sha(ref):
    out = _git(["merge-base", ref, "HEAD"])
    if not out or not out.strip():
        return None
    return _short_sha(out.strip())


def meta_document(round_dir, label, target, stem, generated, scope_flag,
                  feature=None):
    """What this round compared to what.

    The filenames inside a round no longer say what was reviewed, so this file
    and the identity block at the top of every report are the only two places
    that fact is recorded."""
    ref = None if target in ("staged", "uncommitted", "worktree", "files") \
        else target
    return {
        "round": round_number(round_dir),
        "stem": stem,
        "branch": current_branch(),
        "base": ref,
        "base_sha": _short_sha(ref) if ref else None,
        "merge_base": _merge_base_sha(ref) if ref else None,
        "scope": scope_identity(target),
        "scope_label": label,
        "scope_flag": scope_flag,
        "generated": generated.isoformat(timespec="seconds"),
        "feature": feature,
        "prior_round": prior_round(round_dir, scope_identity(target)),
    }


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def skip_path(rel, max_bytes=DEFAULT_MAX_BYTES):
    """True if this file should not be scanned, with a reason recorded."""
    if WORKSPACE_HINT.search(rel):
        return "this tool's own workspace"
    if VENDOR_HINT.search(rel):
        return "vendored or generated path"
    try:
        size = os.path.getsize(abs_path(rel))
    except OSError:
        return None  # let read_lines report the real error
    if size > max_bytes:
        return f"{size // 1024}KB exceeds --max-file-bytes"
    return None


def split_lines(text):
    """Split exactly where git splits: on \\n, nothing else.

    str.splitlines() also breaks on form feed, vertical tab, U+0085, U+2028
    and U+2029. A single form feed - the conventional page separator in Python
    and Emacs-formatted C - shifted every line number below it by one, which
    silently mismatched the diff's added-line set and dropped real findings.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [t[:-1] if t.endswith("\r") else t for t in lines]


def read_lines(rel):
    """Return the file's lines, or None after recording why not.

    Silence here is the worst possible failure: it turns "I could not open
    anything" into "0 candidates found", which reads as a clean bill of health.
    """
    full = abs_path(rel)
    try:
        with open(full, "rb") as fh:
            blob = fh.read()
    except OSError as exc:
        READ_ERRORS.append({"path": rel, "error": exc.strerror or str(exc)})
        return None
    if b"\x00" in blob[:8192]:
        READ_ERRORS.append({"path": rel, "error": "binary file"})
        return None
    # utf-8-sig, not utf-8: a leading BOM is an encoding marker that Visual
    # Studio and MSBuild write into every .cs file they touch. Reporting it as
    # an invisible character means a P1 on files nobody edited. A U+FEFF
    # anywhere else in the file is still the real thing and still reported.
    text = blob.decode("utf-8-sig", errors="replace")
    lines = split_lines(text)
    if lines and len(text) / len(lines) > MINIFIED_AVG_LINE:
        READ_ERRORS.append({"path": rel, "error": "looks minified"})
        return None
    return lines


STOPWORDS = {
    "the", "and", "for", "this", "that", "with", "from", "into", "its", "are",
    "was", "all", "not", "but", "you", "your", "has", "have", "will", "can",
}


# The archetypal restated comment in references/core-patterns.md is
# `// increment the counter` above `counter++`, and the overlap rule could not
# see it: the comment's verb is English, the code's verb is an operator, so
# {increment, counter} vs {counter} scored 0.5 against a 0.6 threshold and the
# flagship example did not fire. Lowering the threshold would have widened
# every other comparison too, against the standing position that a noisy rule
# is worse than a missing one. Naming the two unambiguous operators closes the
# archetype and touches nothing else. `=` is deliberately absent: "set" and
# "assign" appear in far too many comments that are not restatements.
CODE_VERBS = ((r"\+\+|\+=", "increment"), (r"--|-=", "decrement"))


def words(text, code=False):
    """Comment or code line -> the set of words to compare.

    `code=True` also expands the operators above to the verb a human would use
    for them, so a comment naming the action matches the line performing it.
    """
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    found = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", text)]
    if code:
        for pattern, verb in CODE_VERBS:
            if re.search(pattern, text):
                found.append(verb)
    return [w for w in found if w not in STOPWORDS]


def add(findings, path, line, sev, rule, msg, anchor="", span=None):
    """`span` is the last line the finding is *about*, when that is a block
    rather than a line - a test function, not the `def` naming it.

    Scope attribution uses it. A finding anchored at `def test_x():` is about
    the whole body, so a change inside that body is what caused it, even
    though the anchor line itself is untouched. Omit it for line-scoped rules.
    """
    f = {
        "path": path, "line": line, "severity": sev, "rule": rule,
        "message": msg, "anchor": anchor,
    }
    if span and span > line:
        f["span_end"] = span
    findings.append(f)


def touches_change(f, added, removed_at):
    """Did this change cause this finding?

    True when any line the finding covers was added, or when content was
    removed from inside that span. `added` alone answers only the first, and
    a deletion-only edit is the case that produced a silent zero.
    """
    lo = f["line"]
    hi = f.get("span_end", lo)
    return any(n in added or n in removed_at for n in range(lo, hi + 1))


ANCHOR_MAX = 120


def normalise_anchor(text):
    """SKILL.md tells the executor to apply exactly this before comparing a
    plan anchor against a candidate line. It is one function here so the two
    definitions cannot drift: if they disagree, every moved fix reports stale
    and rule 2 of the locating ladder never runs.
    """
    return re.sub(r"\s+", " ", text).strip()[:ANCHOR_MAX]


def anchor_of(lines, idx):
    """Whitespace-normalised source of the finding's line.

    The reconciliation key uses this so two instances of a constant-message
    rule in the same file stay distinguishable, and so a finding survives the
    line shifts that deleting other findings causes.
    """
    if 1 <= idx <= len(lines):
        return normalise_anchor(lines[idx - 1])
    return ""


RE_STRING = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'")
RE_LINE_COMMENT = re.compile(r"//.*$|#(?!\[).*$")


def strip_code(text):
    """Blank out string literals and line comments so brace counting and
    identifier matching do not trip over their contents."""
    return RE_LINE_COMMENT.sub("", RE_STRING.sub('""', text))


RE_PREPROCESSOR = re.compile(
    r"^\s*#\s*(include|define|undef|if|ifdef|ifndef|elif|else|endif|pragma|"
    r"error|warning|region|endregion|line|nullable|import|using)\b")
RE_SHEBANG = re.compile(r"^#!")
RE_COMMENT = re.compile(
    r"^\s*(?://+|\#+|/\*+|\*(?!/)|<!--)\s*(.+?)\s*(?:\*/|-->)?\s*$")

# `--` is a comment marker in SQL/Lua/Ada/Haskell and the pre-decrement operator
# everywhere else. Applied universally it parsed `--Index;` in C++ and
# `--remainingCharges;` in C# as restated comments, handing live code to the
# comment deleter. Gated on extension: in .sql a restated comment is still one.
RE_DASH_COMMENT = re.compile(r"^\s*--(?!-)\s*(.+?)\s*$")
DASH_COMMENT_EXT = {".sql", ".lua", ".hs", ".ads", ".adb", ".vhd", ".vhdl"}

# Comments a tool reads. They carry no prose and no "because", so every comment
# rule here votes to delete them - `//go:embed templates/*` was reported as
# restating the `var` below it. Deleting one breaks a build.
RE_DIRECTIVE = re.compile(
    r"^\s*(?:"
    r"//\s*(?:go:\w+|nolint|NOLINT|NOSONAR|CHECKSTYLE|clang-format|"
    r"IWYU\s+pragma|@ts-|@flow|eslint-|prettier-|jshint|globals?\b|"
    r"Code\s+generated\b|Deprecated:|\+build)"
    r"|/\*\s*(?:eslint|global|prettier-|#__PURE__|webpack)"
    r"|#\s*(?:noqa|type:\s*(?:ignore|[A-Z])|pylint:|mypy:|ruff:|flake8:|"
    r"fmt:\s*(?:on|off)|isort:|pragma:|shellcheck\b|hadolint\b|checkov:|"
    r"tfsec:|nosec\b|yamllint\b|doctest:|typed:\s*\w+|coding[:=]|"
    r"frozen_string_literal|syntax\s*=|yaml-language-server:)"
    r"|<!--\s*(?:markdownlint|prettier-)"
    r")", re.I)


def is_directive(text):
    """A compiler, linter, formatter or build directive wearing comment
    syntax. Never prose, never a deletion candidate."""
    return bool(RE_DIRECTIVE.match(text))


def comment_body(text, dash_comments=False):
    """The prose inside a comment, or None. Preprocessor directives and tool
    directives are not comments, however much `#include` and `# noqa` look
    like one to a regex.

    `dash_comments` opts a file into the `--` marker. It defaults to off
    because the default is what every unrecognised language gets, and the
    claimed three never use `--` as a comment - in two of them it is the
    decrement operator. Guessing "comment" there turns code into a deletion
    candidate; guessing "code" in a .sql file only costs a missed finding.
    """
    if RE_PREPROCESSOR.match(text) or RE_SHEBANG.match(text):
        return None
    if is_directive(text):
        return None
    m = RE_COMMENT.match(text)
    if not m and dash_comments:
        m = RE_DASH_COMMENT.match(text)
    if not m:
        return None
    body = m.group(1).strip()
    return body or None


# --------------------------------------------------------------------------
# universal rules
# --------------------------------------------------------------------------

# Genuinely invisible - you cannot see these in review at all.
UNICODE_INVISIBLE = {
    "\u00a0": "non-breaking space", "\u00ad": "soft hyphen",
    "\u200b": "zero-width space",
    "\u200c": "zero-width non-joiner", "\u200d": "zero-width joiner",
    "\ufeff": "byte-order mark", "\u2060": "word joiner",
    # Trojan Source (CVE-2021-42574). Two of these nine were covered, which
    # is worse than none: the advertised protection was "bidi", and the
    # isolate family below is what the published proof of concept uses.
    # U+202C is the terminator U+202E needs to be exploitable at all.
    "\u202a": "bidi embedding (LRE)", "\u202b": "bidi embedding (RLE)",
    "\u202c": "bidi terminator (PDF)",
    "\u202d": "bidi override (LRO)", "\u202e": "bidi override (RLO)",
    "\u2066": "bidi isolate (LRI)", "\u2067": "bidi isolate (RLI)",
    "\u2068": "bidi isolate (FSI)", "\u2069": "bidi isolate (PDI)",
    # Invisible characters that are legal in identifiers, so two distinct
    # symbols can render identically.
    "\u3164": "hangul filler", "\u115f": "hangul choseong filler",
    "\u2061": "function application", "\u2062": "invisible times",
    "\u2063": "invisible separator", "\u2064": "invisible plus",
}
# Visible, legitimate in prose, only a nuisance in code. P3, and not worth
# mentioning at all inside a comment or a prose file.
UNICODE_TYPOGRAPHIC = {
    "\u2014": "em dash", "\u2013": "en dash",
    "\u2018": "smart quote", "\u2019": "smart quote",
    "\u201c": "smart quote", "\u201d": "smart quote",
}

RE_TODO = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
RE_LINK_OR_ISSUE = re.compile(r"#\d+|https?://")
RE_TICKET_ID = re.compile(r"\b([A-Z]{2,})-\d+")
# Standards and encodings share the ticket shape. Treating `UTF-8` as an issue
# reference silently suppressed the orphan TODOs the rule exists to find.
NOT_TICKET_PREFIXES = {
    "UTF", "UCS", "ISO", "IEC", "SHA", "MD", "AES", "DES", "RSA", "HMAC",
    "CRC", "UUID", "GUID", "IPV", "EUC", "GB", "GBK", "BIG", "CP", "ASCII",
    "BASE", "PEP", "HTML", "CSS", "ES", "HTTP", "TLS", "SSL", "IEEE", "ANSI",
    "PKCS", "JSON", "XML", "SQL", "OAUTH", "SI", "AMD", "ARM", "X",
}
RE_DEV_HOME = re.compile(
    r"(/Users/[A-Za-z0-9._-]+|[Cc]:\\+Users\\+[A-Za-z0-9._-]+)")
RE_UNIX_HOME = re.compile(r"/home/[A-Za-z0-9._-]+")
# Two halves, deliberately. `logger?` is `logge` plus an optional `r`, so it
# never matched `log.` - the commonest spelling of the case this targets. And
# requiring the trace word inside a string literal is what keeps
# `print(x, end="")` and `blueprint_started()` out of the results.
RE_LOG_CALL = re.compile(
    r"\b(log|logger|logging|_log|Debug\.Log\w*|UE_LOG|print|console\.log|"
    r"System\.out\.print\w*)\s*[.(]", re.I)
RE_TRACE_WORD = re.compile(
    r"\b(entering|exiting|starting|finished|called|begin|end)\b", re.I)
RE_COMMENTED_CODE = re.compile(r"^\s*(//|#)\s*[\w\]\)]+.*[;{}]\s*$")
RE_TRIPLE_QUOTE = re.compile(r'"""|\'\'\'')

# ---------------------------------------------------------------------------
# secrets
#
# Structured formats only. There is deliberately no entropy heuristic here:
# hashes, UUIDs, base64 blobs, minified bundles and test fixtures all look
# random, so a "high entropy string" rule fires constantly on files that hold
# no secret at all. This skill's whole posture is that a noisy rule is worse
# than a missing one, because it trains the reader to skim - and the thing
# they skim past is the P1. Every pattern below is self-identifying: a vendor
# prefix, or a PEM header. The rule matches a *format*, never a guess.
# ---------------------------------------------------------------------------
RE_SECRET_TOKEN = re.compile(
    r"(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}"          # AWS access key id
    r"|gh[pousr]_[A-Za-z0-9]{36,}"                  # GitHub token
    r"|github_pat_[A-Za-z0-9_]{22,}"                # GitHub fine-grained PAT
    r"|glpat-[A-Za-z0-9_-]{20,}"                    # GitLab PAT
    # Slack tokens are three segments after the prefix. `xox[baprs]-` plus a
    # loose `{10,}` matched `xoxb-123456789012-` on its own - a prefix with an
    # id after it, which is not a credential and is exactly what a fixture
    # building a fake token out of pieces looks like.
    r"|xox[baprs]-[0-9]{10,}-[0-9]{10,}-[A-Za-z0-9]{20,}"  # Slack
    r"|xapp-[0-9]-[A-Z0-9]{8,}-[0-9]{10,}-[a-f0-9]{20,}"   # Slack app-level
    r"|[sr]k_live_[A-Za-z0-9]{20,}"                 # Stripe live key
    r"|sk-(?:ant|proj)-[A-Za-z0-9_-]{20,}"          # Anthropic / OpenAI
    r"|AIza[0-9A-Za-z_-]{35}"                       # Google API key
    r"|npm_[A-Za-z0-9]{36}"                         # npm
    r"|dop_v1_[a-f0-9]{64}"                         # DigitalOcean
    r"|SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}"    # SendGrid
    r"|hooks\.slack\.com/services/T[A-Za-z0-9_/-]{20,}")   # Slack webhook
# `[A-Z]+ ` covers RSA, EC, DSA, OPENSSH, PGP and the bare PKCS#8 form.
RE_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
# A UNC path names an internal host and share. Narrow on purpose: hostnames in
# general are unmatchable without false-positiving every domain in every URL,
# and the doc claim this implements is worth less than the noise that would buy.
#
# The separator counts are ranges because source code escapes them: a config
# file holds the bare form, and the Python, C#, Java or JS literal for the same
# path doubles every backslash. A pattern pinned to exactly two-then-one
# matches the config and misses every one written in actual source, which is
# the commoner place to find one. Two is still the floor, so a lone
# `\artifacts\out` relative path does not match.
#
# The lookbehind is what stops that widening from costing more than it buys.
# Allowing two backslashes as a *separator* makes an escaped Windows drive
# path - `C:\\Users\\me`, which is in every Windows codebase and which
# `local-path` already reports - structurally identical to a UNC path. A UNC
# path begins at the double backslash; a drive path has a colon or an
# identifier character in front of it. Rejecting those two is the difference.
RE_UNC_PATH = re.compile(
    r"(?<![A-Za-z0-9:_])\\{2,4}[A-Za-z][A-Za-z0-9._-]{2,}\\{1,2}[A-Za-z0-9._$-]+")
RE_SECRET_ASSIGN = re.compile(
    r"""(?ix)
    \b(pass(?:wo?rd)?|passwd|secret|api[_-]?key|apikey|auth[_-]?token
      |access[_-]?token|client[_-]?secret|private[_-]?key|credentials?
      |connection[_-]?string|bearer)
    \s* (?: := | => | [:=] ) \s*
    (['"])(?P<val>[^'"]{8,})\2
    """)
# Template syntax means the value is filled in elsewhere - it is the *absence*
# of a secret, and the shape most likely to be mistaken for one.
RE_SECRET_TEMPLATE = re.compile(
    r"\$\{|\{\{|<[A-Za-z_][A-Za-z0-9_]*>|%\(|%s|\$\(|\$[A-Z_]{2,}|@[A-Z_]{2,}@")
PLACEHOLDER_WORDS = (
    "example", "sample", "placeholder", "changeme", "change-me", "change_me",
    "redacted", "dummy", "fake", "todo", "foobar", "your", "replaceme",
    "replace-me", "replace_me", "insert", "none", "null", "nil", "undefined",
    "notreal", "hunter2", "abc123", "password", "secret", "xxxx", "test",
)


# Vendors publish well-formed keys in their own documentation - AWS's is
# `AKIAIOSFODNN7EXAMPLE` - and those get copied into config samples everywhere.
# Anchored at the END of the token, which is where a vendor puts the marker.
# A bare substring test drops a live key whose random body happens to contain
# these letters; see `looks_like_documented_example`.
DOC_EXAMPLE_SUFFIXES = ("example", "sample")


def looks_like_placeholder(val):
    """A credential-shaped literal that is obviously not a credential.

    For the *assignment* branch only, where the whole value is under suspicion
    and a filler word anywhere in it means the author wrote a stand-in.

    Three tells, and the first is the one that matters most in practice:
    `xxxxxxxx`, `--------` and `00000000` are what a redacted config looks
    like, and flagging them teaches the reader that this rule cries wolf.
    """
    if len(set(val)) <= 2:
        return True
    if RE_SECRET_TEMPLATE.search(val):
        return True
    low = val.lower()
    return any(w in low for w in PLACEHOLDER_WORDS)


def looks_like_documented_example(token):
    """A vendor's own documentation key. **Not** the full placeholder list.

    A vendor token is a fixed-length random string, so a chance substring like
    `nil`, `test` or `none` says nothing about whether it is real - and at 36
    random characters those turn up in a few percent of genuine tokens. Running
    the placeholder list over a token therefore drops live credentials, at a
    rate nobody would notice, on the one rule where a false negative is the
    worst outcome available. Match only the markers a vendor actually uses.

    That argument does not stop at the filler words, and this function used to
    stop there anyway: `example` and `sample` were matched as substrings, so a
    `gh?_` token whose 36 random characters happened to contain either word
    anywhere - a well-formed, live key - was dropped in silence, not demoted.
    (No literal here: writing one out would put a permanent P1 in this file,
    which is why the fixtures in `test_scan.py` are assembled from pieces.)

    Anchoring at the end keeps the exemption doing its actual job. A vendor
    writes the marker as a suffix (`AKIAIOSFODNN7EXAMPLE`); a random body
    carrying those letters somewhere in the middle is a token, and the whole
    point of matching a format rather than guessing at entropy is that the
    difference is knowable.
    """
    return token.lower().endswith(DOC_EXAMPLE_SUFFIXES)


def has_ticket(text):
    """A link, an issue number, or a real ticket id - but not `UTF-8`,
    `SHA-256`, `ISO-8601`, which match the same shape and mean nothing about
    ownership."""
    if RE_LINK_OR_ISSUE.search(text):
        return True
    return any(m.group(1) not in NOT_TICKET_PREFIXES
               for m in RE_TICKET_ID.finditer(text))


def docstring_lines(path, lines):
    """Line numbers inside a Python triple-quoted string.

    `comment_body` only understands single-line comment syntax, so a docstring
    - the one place in a Python file you are supposed to write prose - was
    treated as code and every em dash in it became a finding.
    """
    if os.path.splitext(path)[1].lower() not in PY_EXT:
        return set()
    inside = set()
    delim = None
    for idx, text in enumerate(lines, 1):
        pos = 0
        while True:
            m = RE_TRIPLE_QUOTE.search(text, pos)
            if not m:
                break
            if delim is None:
                delim = m.group(0)
                inside.add(idx)
            elif m.group(0) == delim:
                delim = None
                inside.add(idx)
            pos = m.end()
        if delim is not None:
            inside.add(idx)
    return inside


def check_universal(path, lines, findings):
    is_test = bool(TEST_HINT.search(path))
    is_prose = os.path.splitext(path)[1].lower() in PROSE_EXT
    dash_comments = os.path.splitext(path)[1].lower() in DASH_COMMENT_EXT
    docs = docstring_lines(path, lines)
    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        body = comment_body(text, dash_comments)
        anchor = anchor_of(lines, idx)

        for ch, name in UNICODE_INVISIBLE.items():
            if ch in text:
                # NBSP and soft hyphens are routine in prose, and in the
                # fixtures of a suite that tests invisible-character handling -
                # including this skill's own. Bidi and invisible-identifier
                # characters are an attack in prose too (the reviewer reads the
                # rendered form), so those drop one step in a test, not two.
                soft = name in ("non-breaking space", "soft hyphen")
                illustrative = is_prose or is_test
                if soft and illustrative:
                    sev = "P3"
                elif is_test:
                    sev = "P2"
                else:
                    sev = "P1"
                add(findings, path, idx, sev, "unicode-invisible",
                    f"{name} in source - invisible in review, breaks grep",
                    anchor)
                break
        if not is_prose and body is None and idx not in docs:
            for ch, name in UNICODE_TYPOGRAPHIC.items():
                if ch in text:
                    add(findings, path, idx, "P3", "unicode-typographic",
                        f"{name} in code - fine in prose, breaks grep in code",
                        anchor)
                    break

        # A developer home directory is never a deployment path, so it is a
        # P1 wherever it lands. `/home/<name>` is a container path as often as
        # a laptop one. Both are normal *data* in a path-handling test and
        # normal *examples* in documentation, so demote one step in each.
        illustrative = is_test or is_prose
        if RE_DEV_HOME.search(text):
            add(findings, path, idx, "P2" if illustrative else "P1",
                "local-path",
                "absolute path into a developer home directory", anchor)
        elif RE_UNIX_HOME.search(text):
            add(findings, path, idx, "P3" if illustrative else "P2",
                "local-path",
                "absolute /home path - a developer home or a container path, "
                "confirm which", anchor)

        # Secrets do not demote in a test or prose file. Every other rule here
        # does, because a home path in a fixture is data and an em dash in a
        # README is correct - but a well-formed vendor token is a live
        # credential wherever it sits, and a leaked key in a test fixture is
        # the *commonest* place it leaks, not a special case. The formats are
        # self-identifying, so the false-positive cost of not demoting is
        # close to zero.
        m_token = RE_SECRET_TOKEN.search(text)
        m_assign = RE_SECRET_ASSIGN.search(text)
        if RE_PRIVATE_KEY.search(text):
            add(findings, path, idx, "P1", "committed-secret",
                "private key block in source - rotate it; deleting the line "
                "does not remove it from history", anchor)
        elif m_token and not looks_like_documented_example(m_token.group(0)):
            # A *narrow* exemption, not the placeholder list - see the
            # docstring on looks_like_documented_example. Matching the format
            # is what makes this rule safe to run everywhere; exempting only
            # the vendor's published example is what keeps it from firing on
            # a copy of the docs without dropping real keys along with it.
            add(findings, path, idx, "P1", "committed-secret",
                "credential in a recognised vendor format - rotate it; "
                "deleting the line does not remove it from history", anchor)
        elif m_assign and not looks_like_placeholder(m_assign.group("val")):
            # The named-variable form is a guess about intent, not a format
            # match, so this one *does* demote where fixtures and examples
            # live. `password = "hunter2"` in a README is nearly always
            # illustration; the same line in a service is nearly always not.
            add(findings, path, idx, "P2" if illustrative else "P1",
                "committed-secret",
                f"'{m_assign.group(1)}' assigned a literal value - confirm it "
                "is not a real credential", anchor)

        if RE_UNC_PATH.search(text) and not is_prose:
            add(findings, path, idx, "P3" if is_test else "P2",
                "internal-host",
                "UNC path names an internal host and share", anchor)

        if RE_TODO.search(text) and not has_ticket(text) and not is_test:
            add(findings, path, idx, "P3", "orphan-todo",
                "placeholder with no ticket or owner", anchor)

        if RE_LOG_CALL.search(text) and any(
                RE_TRACE_WORD.search(s) for s in RE_STRING.findall(text)):
            add(findings, path, idx, "P3", "trace-logging",
                "entry/exit logging - usually debugging debris", anchor)

        if body is not None and RE_COMMENTED_CODE.match(text):
            add(findings, path, idx, "P3", "commented-code",
                "commented-out code - version control already has it", anchor)

        if body is not None and idx < len(lines):
            comment_words = set(words(body))
            code_words = set(words(lines[idx], code=True))
            if len(comment_words) >= 2:
                overlap = len(comment_words & code_words) / len(comment_words)
                if overlap >= 0.6:
                    add(findings, path, idx, "P3", "restated-comment",
                        "comment restates the line below it", anchor)


# --------------------------------------------------------------------------
# python
# --------------------------------------------------------------------------

RE_PY_LOG_FSTRING = re.compile(r"\b(log|logger|logging|_log)\.\w+\(\s*f[\"']")
RE_PY_LOGCALL = re.compile(
    r"\b(log|logger|logging|_log|LOG)\s*\.\w+\s*\(|\bprint\s*\("
    r"|\btraceback\.(print_exc|format_exc)\b")
RE_PY_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore")
RE_PY_ANY = re.compile(r":\s*Any\b|->\s*Any\b|\[str,\s*Any\]")


def check_python(path, lines, findings):
    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        anchor = anchor_of(lines, idx)
        if RE_PY_LOG_FSTRING.search(text):
            add(findings, path, idx, "P3", "eager-log-format",
                "f-string in logging call formats even when filtered out",
                anchor)
        if RE_PY_TYPE_IGNORE.search(text):
            # Name the fix: the other reading - delete the directive - passes
            # every check and fails the build under warn_unused_ignores.
            add(findings, path, idx, "P2", "type-ignore",
                "silences the checker rather than fixing the type - fix the "
                "annotation; do not delete the directive", anchor)
        if RE_PY_ANY.search(text):
            add(findings, path, idx, "P3", "any-hint",
                "Any disables checking exactly where it would help", anchor)

    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError as exc:
        warn(f"{path}: could not parse Python ({exc.msg} at line {exc.lineno})"
             " - AST rules skipped for this file")
        return

    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if line is None:
            continue
        anchor = anchor_of(lines, line)

        if isinstance(node, ast.AsyncFunctionDef):
            has_await = any(
                isinstance(n, (ast.Await, ast.AsyncFor, ast.AsyncWith))
                for n in ast.walk(node)
            )
            if not has_await:
                add(findings, path, line, "P2", "async-no-await",
                    f"'{node.name}' is async but never awaits - forces callers "
                    "async for nothing", anchor)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    add(findings, path, line, "P1", "mutable-default",
                        f"'{node.name}' has a mutable default argument - "
                        "shared across calls", anchor)
                    break

        if isinstance(node, ast.ExceptHandler):
            body = node.body
            broad = node.type is None or (
                isinstance(node.type, ast.Name)
                and node.type.id in ("Exception", "BaseException"))
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                if broad:
                    add(findings, path, line, "P1", "swallowed-exception",
                        "except/pass hides the failure entirely", anchor)
                else:
                    # `except FileNotFoundError: pass` is contextlib.suppress
                    # written out. The failure it hides is named and expected.
                    add(findings, path, line, "P2", "swallowed-exception",
                        "except/pass on a named exception - contextlib.suppress "
                        "spelled out; confirm this failure really is expected",
                        anchor)
            elif (body and isinstance(body[-1], ast.Raise)
                  and body[-1].exc is None
                  and RE_PY_LOGCALL.search(
                      " ".join(lines[body[0].lineno - 1:body[-1].lineno]))):
                # Only a duplicate traceback if something actually logged.
                # `except X: conn.rollback(); raise` is the cleanup idiom.
                add(findings, path, line, "P2", "log-and-reraise",
                    "logs then re-raises - duplicate traceback unless it adds "
                    "context", anchor)
            if node.type is None:
                add(findings, path, line, "P2", "bare-except",
                    "bare except catches KeyboardInterrupt and typos alike",
                    anchor)
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                add(findings, path, line, "P3", "broad-except",
                    "catching Exception where one failure mode is expected",
                    anchor)

    check_python_bindings(path, tree, lines, findings)
    if TEST_HINT.search(path):
        check_python_tests(path, tree, lines, findings)


def check_python_bindings(path, tree, lines, findings):
    """Fields assigned but never read; locals that are aliases or dead."""
    file_tokens = defaultdict(int)
    for token in re.findall(r"\b[A-Za-z_]\w*\b", "\n".join(lines)):
        file_tokens[token] += 1
    # Attributes reached through anything other than a plain `self.x` read -
    # getattr, __dict__, vars() - are invisible to the walk below. If the file
    # uses any of them, do not claim a field is unread.
    dynamic_access = bool(re.search(r"\b(getattr|setattr|hasattr|vars|__dict__"
                                    r"|locals|globals)\b", "\n".join(lines)))

    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        # Two passes, deliberately. Collecting `bumped` in the same pass that
        # decides whether a Load counts made the result depend on ast.walk's
        # visit order: a counter that is incremented AND read was reported as
        # "only ever updated, never read".
        bumped, stores, loads = set(), {}, set()
        for n in ast.walk(cls):
            if (isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Attribute)
                    and isinstance(n.target.value, ast.Name)
                    and n.target.value.id == "self"):
                bumped.add(n.target.attr)
                stores.setdefault(n.target.attr, n.lineno)
        for n in ast.walk(cls):
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                    and n.value.id == "self"):
                if isinstance(n.ctx, ast.Store):
                    stores.setdefault(n.attr, n.lineno)
                elif isinstance(n.ctx, ast.Load):
                    loads.add(n.attr)
        aug_only = {n.target.attr for n in ast.walk(cls)
                    if isinstance(n, ast.AugAssign)
                    and isinstance(n.target, ast.Attribute)}
        real_loads = set(loads)

        # class-body fields only when the class is not a dataclass/model/enum,
        # where every field is API by construction
        plain = not cls.decorator_list and not cls.bases
        if plain:
            for stmt in cls.body:
                target = None
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    target = stmt.target
                elif (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                      and isinstance(stmt.targets[0], ast.Name)):
                    target = stmt.targets[0]
                if target is not None:
                    stores.setdefault(target.id, stmt.lineno)
                    for n in ast.walk(cls):
                        if (isinstance(n, ast.Name) and n.id == target.id
                                and isinstance(n.ctx, ast.Load)):
                            real_loads.add(target.id)

        if dynamic_access:
            continue
        for name, line in stores.items():
            if name in real_loads or name.startswith("__"):
                continue
            private = name.startswith("_")
            # a public attribute set in __init__ is the standard way to expose
            # state; only flag it when nothing in the file touches it either
            if not private and file_tokens[name] > 1:
                continue
            detail = (f"'{name}' is only ever incremented in {cls.name}, "
                      "never read"
                      if name in aug_only
                      else f"'{name}' is assigned in {cls.name} but never read "
                           "in the class")
            add(findings, path, line, "P2" if private else "P3", "unused-field",
                detail + (" - confirm no subclass or external reader"
                          if not private else " - confirm no subclass reader"),
                anchor_of(lines, line))

    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        load_count, store_count = defaultdict(int), defaultdict(int)
        declared_elsewhere = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Name):
                if isinstance(n.ctx, ast.Load):
                    load_count[n.id] += 1
                else:
                    store_count[n.id] += 1
            elif isinstance(n, (ast.Global, ast.Nonlocal)):
                declared_elsewhere.update(n.names)
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Assign) and len(n.targets) == 1
                    and isinstance(n.targets[0], ast.Name)):
                continue
            name = n.targets[0].id
            if (name == "_" or name.startswith("_")
                    or name in declared_elsewhere or store_count[name] > 1):
                continue
            anchor = anchor_of(lines, n.lineno)
            if load_count[name] == 0:
                add(findings, path, n.lineno, "P2", "dead-local",
                    f"'{name}' is assigned in {fn.name} and never read", anchor)
            elif isinstance(n.value, ast.Name) and load_count[name] == 1:
                add(findings, path, n.lineno, "P3", "alias-variable",
                    f"'{name}' just renames '{n.value.id}' for a single use - "
                    "inline it", anchor)


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------

MOCK_ASSERT = re.compile(r"^assert_(called|any_call|has_calls|not_called)")
MOCK_FACTORY = re.compile(r"\b(Mock|MagicMock|AsyncMock|patch|mocker|monkeypatch)\b")


ASSERTING_CTX = re.compile(
    r"(raises|warns|assertRaises|assertWarns|assertLogs|assertNoLogs|"
    r"deprecated_call|ExpectedException|assertRaisesRegex)")


def _is_assert_call(node):
    """assertX(...), a bare pytest assert, or a `with` whose context manager
    is an assertion - `with pytest.raises(ValueError):` is how both pytest and
    unittest express the entire error-path contract."""
    if isinstance(node, ast.Assert):
        return True
    if isinstance(node, (ast.With, ast.AsyncWith)):
        for item in node.items:
            if ASSERTING_CTX.search(ast.dump(item.context_expr)):
                return True
        return False
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        fn = node.value.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        # leading underscores are a naming choice, not a signal; custom
        # helpers named expect_*/verify_*/check_* assert just as hard
        return bool(re.match(r"_*(assert|ASSERT|expect|verify|check|should)",
                             name))
    return False


def _assert_name(node):
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        fn = node.value.func
        return fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
    return ""


def _is_tautology(node):
    """assert True, assert 1, assert x == x, assertTrue(True)."""
    if isinstance(node, ast.Assert):
        t = node.test
        if isinstance(t, ast.Constant) and bool(t.value):
            return True
        if (isinstance(t, ast.Compare) and len(t.ops) == 1
                and isinstance(t.ops[0], (ast.Eq, ast.Is))):
            return ast.dump(t.left) == ast.dump(t.comparators[0])
        return False
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        name = _assert_name(node)
        args = node.value.args
        if name in ("assertTrue", "assertFalse") and len(args) == 1:
            return isinstance(args[0], ast.Constant)
        if name in ("assertEqual", "assertIs") and len(args) == 2:
            return ast.dump(args[0]) == ast.dump(args[1])
    return False


def _body_shape(fn):
    """AST dump with every literal blanked, so two tests that differ only in
    their constants hash the same. That is the parametrize signal."""
    class Blank(ast.NodeTransformer):
        def visit_Constant(self, node):
            return ast.copy_location(ast.Constant(value=None), node)
    clone = Blank().visit(ast.parse(ast.unparse(fn))) if hasattr(ast, "unparse") else None
    if clone is None:
        return None
    for n in ast.walk(clone):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n.name = "_"
            for a in n.args.args:
                a.arg = "_"
        if isinstance(n, ast.Name):
            n.id = "_" if n.id.startswith("expected") else n.id
    return ast.dump(clone)


def _decorator_name(dec):
    """Dotted name of a decorator, with any call stripped: `pytest.fixture`,
    `pytest.mark.skip`, `fixture`."""
    node = dec.func if isinstance(dec, ast.Call) else dec
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def check_python_tests(path, tree, lines, findings):
    """Redundancy in generated tests.

    Generated suites inflate: a test per branch that all assert the same
    thing, tests that only prove the mock was called, and asserts that cannot
    fail. Coverage numbers go up and nothing is actually verified, which is
    worse than no test - it buys false confidence and costs maintenance.
    """
    tests = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and (n.name.startswith("test_") or n.name.startswith("test"))
             and n.name != "test"]
    fixtures = {}
    used_names = defaultdict(int)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            used_names[n.id] += 1
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for dec in fn.decorator_list:
            # Match the decorator's dotted name, never its dumped source. A
            # @parametrize list whose data happens to contain the strings
            # "fixture" or "skip" is not a fixture and is not skipped.
            name = _decorator_name(dec)
            if name.split(".")[-1] == "fixture":
                fixtures[fn.name] = fn.lineno
            if name.split(".")[-1] in ("skip", "skipif", "xfail"):
                if not any(isinstance(k, ast.keyword) and k.arg == "reason"
                           for k in getattr(dec, "keywords", [])):
                    add(findings, path, fn.lineno, "P3", "skip-without-reason",
                        f"'{fn.name}' is skipped with no reason - nobody knows "
                        "when to re-enable it", anchor_of(lines, fn.lineno))

    fixture_params = set()
    for fn in tests:
        fixture_params.update(a.arg for a in fn.args.args)
    # a fixture requested by another fixture is used, and an autouse fixture
    # is requested by everything without naming anything
    for name in list(fixtures):
        for fn in ast.walk(tree):
            if (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and fn.name in fixtures and fn.name != name):
                fixture_params.update(a.arg for a in fn.args.args)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in fn.decorator_list:
            if any(isinstance(k, ast.keyword) and k.arg == "autouse"
                   for k in getattr(dec, "keywords", [])):
                fixture_params.add(fn.name)
    # conftest.py publishes fixtures to every test file beside and below it.
    # Nothing in conftest requests them, so the rule fired on all of them.
    if os.path.basename(path) != "conftest.py":
        for name, line in fixtures.items():
            if name not in fixture_params and used_names[name] <= 1:
                add(findings, path, line, "P2", "unused-fixture",
                    f"fixture '{name}' is never requested by any test in this "
                    "file", anchor_of(lines, line))

    shapes = defaultdict(list)
    for fn in tests:
        asserts = [n for n in ast.walk(fn) if _is_assert_call(n)]
        anchor = anchor_of(lines, fn.lineno)

        # span: the finding is about the whole test body, so a deletion inside
        # it counts.
        body_end = fn.end_lineno

        if not asserts:
            add(findings, path, fn.lineno, "P1", "test-without-assertion",
                f"'{fn.name}' asserts nothing - it only proves the code did "
                "not raise", anchor, span=body_end)
        else:
            if all(_is_tautology(a) for a in asserts):
                add(findings, path, fn.lineno, "P1", "tautological-test",
                    f"'{fn.name}' only makes assertions that cannot fail",
                    anchor, span=body_end)
            elif any(_is_tautology(a) for a in asserts):
                for a in asserts:
                    if _is_tautology(a):
                        add(findings, path, a.lineno, "P2", "tautological-assert",
                            "this assertion cannot fail", anchor_of(lines, a.lineno))
            # assert_called* exists only on a test double, so its presence is
            # the signal - the mock does not have to be constructed in the
            # test body, and usually it arrives from a fixture instead.
            if all(MOCK_ASSERT.match(_assert_name(a)) for a in asserts):
                add(findings, path, fn.lineno, "P1", "mock-only-test",
                    f"'{fn.name}' asserts only that a mock was called - it "
                    "tests the test double, not the code", anchor,
                    span=body_end)

        shape = _body_shape(fn)
        if shape:
            shapes[shape].append(fn)

    for group in shapes.values():
        if len(group) < 2:
            continue
        first = group[0]
        names = ", ".join(f.name for f in group[1:])
        add(findings, path, first.lineno, "P2", "duplicate-test",
            f"'{first.name}' is structurally identical to {names} - differs "
            "only in literals, so one parametrized test may cover them all; "
            "keep them separate if they pin different risks (boundaries, "
            "regressions)", anchor_of(lines, first.lineno))


# Test declarations, by family. Everything here opens a block on the same or
# the next line; the block finder below is brace- or indentation-based.
TEST_DECL = [
    # (regex, family, name group or None)
    (re.compile(r"^\s*\[(Test|TestCase|TestMethod|Fact|Theory)[\(\]]"), "attr", None),
    (re.compile(r"^\s*@(Test|ParameterizedTest|RepeatedTest)\b"), "attr", None),
    (re.compile(r"^\s*#\[(test|tokio::test|rstest|async_std::test)\b"), "attr", None),
    (re.compile(r"^\s*(TEST|TEST_F|TEST_P|TYPED_TEST)\s*\("), "inline", None),
    (re.compile(r"^\s*func\s+(Test\w+)\s*\("), "inline", 1),
    (re.compile(r"^\s*(?:public\s+|private\s+)?func\s+(test\w+)\s*\("), "inline", 1),
    (re.compile(r"^\s*(?:async\s+)?(?:it|test)(?:\.\w+)?\s*[\(`]"), "inline", None),
    (re.compile(r"^\s*(?:it|specify|example)\s+[\"'].*\s+do\b"), "ruby", None),
]
# Anything that can fail the test. Deliberately broad: a false "no assertion"
# on a real test is a P1 that wastes a reviewer's time, so err toward silence.
RE_ASSERTION = re.compile(
    r"\b(Assert\.|Assert::|Assertions\.|StringAssert|CollectionAssert|"
    r"assert\w*\s*[\(!.]|assert_\w+|EXPECT_|ASSERT_|CHECK\(|REQUIRE\(|"
    r"expect\w*\s*[\({]|\.should\b|Should\(\)|\.Should\b|shouldBe\b|"
    r"is_expected\b|"
    r"t\.(Error|Errorf|Fatal|Fatalf|Fail|FailNow)\b|"
    r"require\.\w+|verifyThat|panic!|unwrap\w*\(\)|expect_err|"
    r"should_panic|toMatchSnapshot|XCTAssert|Approvals\.)"
)
# Verifying a double is not the same as checking the result.
RE_MOCK_VERIFY = re.compile(
    r"(?<!Approvals\.)(?<!\w)(Verify|VerifyNoOtherCalls|Received|EXPECT_CALL|"
    r"AssertExpectations|toHaveBeenCalled\w*|assert_called\w*|have_received|"
    r"verify)\s*\(")
RE_SKIP_NO_REASON = re.compile(
    r"^\s*(?:@(?:Ignore|Disabled)\s*(?:\(\s*\))?\s*$"
    r"|#\[ignore\]\s*$"
    r"|\[Ignore\s*\]\s*$"
    r"|(?:it|test|describe)\.skip\b"
    r"|@Disabled\s*(?:\(\s*\))?\s*$"
    r"|#\[ignore\]"
    r"|t\.Skip(?:Now)?\(\s*\))")

RE_LITERAL = re.compile(
    r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|-?\b\d+(?:\.\d+)?\b")
RE_TAUTOLOGY = [
    # expect(true).toBe(true) / expect(1).toEqual(1)
    re.compile(r"expect\s*\(\s*([^()]+?)\s*\)\s*\.\s*(?:toBe|toEqual|"
               r"toStrictEqual|to\.equal|toBeTruthy)\s*\(\s*([^()]*?)\s*\)"),
    # assertEquals(2, 2) / assert.Equal(t, 1, 1) / EXPECT_EQ(1, 1) / assert_eq!(1, 1)
    re.compile(r"(?:assertEquals|assertEqual|assert_eq!|EXPECT_EQ|ASSERT_EQ|"
               r"Assert\.AreEqual|assert\.Equal)\s*\(\s*(?:t\s*,\s*)?"
               r"([^,()]+?)\s*,\s*([^,()]+?)\s*\)"),
]
RE_TRUE_LITERAL = re.compile(
    r"^(true|True|1|assertTrue\(true\)|XCTAssertTrue\(true\))$")


def _block_end_brace(lines, start, lookahead=3):
    """End line of the block opened at `start`.

    A brace-less test - `it('x', () => expect(y).toBe(1));` or a C#
    expression-bodied method - has no block at all. Scanning forward for the
    next `{` used to consume the FOLLOWING test's body and then skip past it,
    so an assertionless test hiding behind a one-liner was never seen. If no
    brace shows up within `lookahead` lines, treat the statement itself as
    the body.
    """
    depth, started = 0, False
    for j in range(start, len(lines)):
        c = strip_code(lines[j])
        if not started and j - start >= lookahead and "{" not in c:
            return start
        depth += c.count("{") - c.count("}")
        if "{" in c:
            started = True
        if started and depth <= 0:
            return j
        if not started and c.rstrip().endswith(";"):
            return j
    return None


def _block_end_ruby(lines, start):
    """RSpec blocks close with `end` at the opening line's indentation.

    Indentation is not syntax in Ruby, but it is universal convention in spec
    files. If the aligned `end` is not there, return None and say nothing -
    a guessed block boundary produces false P1s, which is the failure this
    whole pass is supposed to avoid.
    """
    indent = len(lines[start]) - len(lines[start].lstrip())
    for j in range(start + 1, len(lines)):
        text = lines[j]
        if not text.strip():
            continue
        if (len(text) - len(text.lstrip())) == indent and text.strip() == "end":
            return j
    return None


def _normalise_body(lines, start, end):
    """Body with comments, literals and whitespace flattened, so two tests
    that differ only in their data hash the same.

    Starts after the line carrying the body's opening brace, not after the
    declaration line. For attribute families ([Test], @Test, #[test]) the
    declaration is the attribute and the signature comes next, so slicing
    from start+1 baked each test's unique method name into its shape and the
    rule could never fire.
    """
    first = start + 1
    for j in range(start, min(end, start + 6)):
        if "{" in strip_code(lines[j]):
            first = j + 1
            break
    body = " ".join(strip_code(t) for t in lines[first:end])
    body = RE_LITERAL.sub("@", body)
    return re.sub(r"\s+", " ", body).strip()


def check_generic_tests(path, lines, findings):
    """Test redundancy for every non-Python language the diff might contain.

    Generated suites inflate the same way in all of them: a test per input
    that asserts the same thing, a test that only proves nothing threw, and a
    test that checks the mock rather than the result. Coverage climbs and
    nothing is verified, which is worse than no test - it buys false
    confidence and charges maintenance for it.
    """
    if not TEST_HINT.search(path):
        return
    n = len(lines)
    i = 0
    shapes = defaultdict(list)
    while i < n:
        code = strip_code(lines[i])
        family = None
        for rx, fam, _grp in TEST_DECL:
            if rx.match(code):
                family = fam
                break
        if family is None:
            i += 1
            continue
        end = (_block_end_ruby(lines, i) if family == "ruby"
               else _block_end_brace(lines, i))
        if end is None or end <= i:
            i += 1
            continue
        body = "\n".join(strip_code(t) for t in lines[i:end + 1])
        anchor = anchor_of(lines, i + 1)

        # An assertion that only inspects a double is not a check on the
        # result. `expect(log).toHaveBeenCalled()` reads like an assertion and
        # matches RE_ASSERTION, so compare line by line rather than asking
        # whether the body contains an assertion anywhere.
        asserting = [t for t in (strip_code(x) for x in lines[i:end + 1])
                     if RE_ASSERTION.search(t)]
        mock_lines = [t for t in asserting if RE_MOCK_VERIFY.search(t)]
        # span: the finding is about the block, not the declaration line, so
        # a deletion inside the body is attributed to this change.
        body_end = end + 1

        if not asserting:
            if RE_MOCK_VERIFY.search(body):
                add(findings, path, i + 1, "P1", "mock-only-test",
                    "test verifies mock interactions but asserts nothing about "
                    "the result - it tests the double, not the code", anchor,
                    span=body_end)
            else:
                add(findings, path, i + 1, "P1", "test-without-assertion",
                    "test body contains no assertion - it only proves the code "
                    "did not throw", anchor, span=body_end)
        elif len(mock_lines) == len(asserting):
            # Verifying an interaction is the contract for a publisher, a
            # mailer, a logger. The scanner cannot tell those from mock
            # theatre, so it hedges rather than asserting false coverage.
            add(findings, path, i + 1, "P2", "mock-only-test",
                "every assertion here checks a mock rather than a result - "
                "confirm the interaction IS the contract, otherwise assert on "
                "the outcome too", anchor, span=body_end)
        else:
            for rx in RE_TAUTOLOGY:
                m = rx.search(body)
                if m and m.group(1).strip() == m.group(2).strip():
                    add(findings, path, i + 1, "P2", "tautological-assert",
                        f"asserts {m.group(1).strip()} equals itself - cannot "
                        "fail", anchor)
                    break
            else:
                m = re.search(r"(?:assert|XCTAssertTrue|EXPECT_TRUE|ASSERT_TRUE)"
                              r"[!\s]*\(\s*(true|True|1)\s*\)", body)
                if m:
                    add(findings, path, i + 1, "P2", "tautological-assert",
                        "asserts a literal true - cannot fail", anchor)

        near = [strip_code(lines[k]) for k in range(max(0, i - 3), i)]
        near.append(code)
        near.extend(strip_code(lines[k]) for k in range(i, min(end + 1, i + 4)))
        if any(RE_SKIP_NO_REASON.search(t) for t in near):
            add(findings, path, i + 1, "P3", "skip-without-reason",
                "test is skipped with no reason - nobody knows when to "
                "re-enable it", anchor)

        shape = _normalise_body(lines, i, end)
        if shape and len(shape) > 20:
            shapes[shape].append(i + 1)
        i = end + 1

    for shape, at in shapes.items():
        if len(at) < 2:
            continue
        add(findings, path, at[0], "P2", "duplicate-test",
            f"structurally identical to the test(s) at line(s) "
            f"{', '.join(str(x) for x in at[1:])} - differs only in literals, "
            "so one table-driven or parametrized test covers them all",
            anchor_of(lines, at[0]))


# --------------------------------------------------------------------------
# c# / unity
# --------------------------------------------------------------------------

RE_CS_NULLCOND = re.compile(r"(\w+)\s*(\?\.|\?\?=|\?\?|\?\[)")
RE_CS_EMPTY_LIFECYCLE = re.compile(
    r"\b(void\s+(Awake|Start|Update|FixedUpdate|LateUpdate|OnEnable|OnDisable|"
    r"OnDestroy)\s*\(\s*\)\s*\{\s*\})"
)
RE_CS_ASYNC_VOID = re.compile(r"\basync\s+void\b")
RE_CS_DEBUG_LOG = re.compile(r"\bDebug\.(Log|LogWarning|LogError)\s*\(")
RE_CS_EXPENSIVE = re.compile(r"\b(Camera\.main|FindObjectOfType|GameObject\.Find)\b")
RE_CS_PERFRAME = re.compile(r"\b(GetComponent(InChildren|InParent)?<|Camera\.main|"
                            r"FindObjectOfType|GameObject\.Find)\b")
RE_CS_METHOD = re.compile(r"\bvoid\s+(Update|FixedUpdate|LateUpdate)\s*\(\s*\)")
# Where the scene lookup is supposed to happen. The rule's own message says
# "cache in Awake", so firing on the cached assignment contradicts itself.
RE_CS_INIT_METHOD = re.compile(r"\bvoid\s+(Awake|Start|OnEnable)\s*\(\s*\)")
# `async void` is mandatory for a .NET event handler; there is no other way to
# await inside one, and the signature is fixed by the delegate.
RE_CS_EVENT_HANDLER = re.compile(
    r"\([^)]*\b(sender|EventArgs|RoutedEventArgs|EventData)\b[^)]*\)")
RE_CS_LINQ = re.compile(r"\.(Where|Select|OrderBy|ToList|ToArray|Any|First)\s*\(")

# UnityEngine.Object subclasses, where `?.` and `??` skip the lifetime check.
UNITY_OBJECT_TYPES = {
    "GameObject", "Transform", "RectTransform", "Component", "Behaviour",
    "MonoBehaviour", "ScriptableObject", "Rigidbody", "Rigidbody2D",
    "Collider", "Collider2D", "BoxCollider", "SphereCollider", "CapsuleCollider",
    "Renderer", "MeshRenderer", "SkinnedMeshRenderer", "SpriteRenderer",
    "Animator", "Animation", "AudioSource", "AudioClip", "Camera", "Light",
    "Material", "Texture", "Texture2D", "Sprite", "Mesh", "Canvas",
    "CanvasGroup", "Image", "RawImage", "Text", "TextMesh", "TMP_Text",
    "TextMeshProUGUI", "Button", "Slider", "Toggle", "ParticleSystem",
    "NavMeshAgent", "CharacterController", "LineRenderer", "TrailRenderer",
    "Rigidbody", "Object", "UnityEngine.Object", "AudioMixer", "Shader",
}
UNITY_BUILTIN_MEMBERS = {
    "transform", "gameObject", "rigidbody", "collider", "renderer", "camera",
    "animation", "audio", "light", "particleSystem",
}
# Inherited members that are NOT UnityEngine.Object - `name ?? "x"` is fine.
UNITY_BUILTIN_VALUES = {"name", "tag", "layer", "enabled", "isActiveAndEnabled"}
# Types that are definitively not UnityEngine.Object, so `?.` on them is fine.
NON_UNITY_TYPES = {
    "string", "String", "int", "float", "double", "bool", "byte", "char",
    "long", "short", "decimal", "object", "Vector2", "Vector3", "Vector4",
    "Quaternion", "Color", "Rect", "Bounds", "List", "Dictionary", "HashSet",
    "Queue", "Stack", "IEnumerable", "IList", "IDictionary", "Array",
    "Action", "Func", "Task", "Exception", "StringBuilder", "Guid",
    "DateTime", "TimeSpan", "Nullable", "EventHandler", "Coroutine",
}
RE_CS_DECL = re.compile(
    r"\b([A-Za-z_]\w*)\s*(?:<[^<>();]*>)?\s+([A-Za-z_]\w*)\s*(?:=|;|,|\)|\{)")
RE_CS_CLASS_DECL = re.compile(r"\bclass\s+(\w+)\s*:\s*([\w\s,<>\.]+)")


def _cs_identifier_types(lines):
    """Best-effort map of identifier -> declared type name for one file."""
    types = {}
    unity_classes = set()
    for text in lines:
        m = RE_CS_CLASS_DECL.search(text)
        if m:
            bases = {b.strip().split(".")[-1] for b in m.group(2).split(",")}
            if bases & UNITY_OBJECT_TYPES:
                unity_classes.add(m.group(1))
    for text in lines:
        for m in RE_CS_DECL.finditer(strip_code(text)):
            type_name, ident = m.group(1), m.group(2)
            if type_name in ("return", "new", "case", "else", "in", "is", "as",
                             "using", "namespace", "class", "struct", "void"):
                continue
            types.setdefault(ident, type_name)
    return types, unity_classes


def _cs_method_ranges(lines, rx):
    """Approximate line ranges of matching method bodies via brace depth."""
    ranges = []
    i = 0
    while i < len(lines):
        if rx.search(strip_code(lines[i])):
            depth = 0
            started = False
            start = i + 1
            for j in range(i, len(lines)):
                code = strip_code(lines[j])
                depth += code.count("{") - code.count("}")
                if "{" in code:
                    started = True
                if started and depth <= 0:
                    ranges.append((start, j + 1))
                    i = j
                    break
        i += 1
    return ranges


def check_csharp(path, lines, findings):
    joined = "\n".join(lines)
    is_unity = "using UnityEngine" in joined
    perframe = _cs_method_ranges(lines, RE_CS_METHOD) if is_unity else []
    init_ranges = (_cs_method_ranges(lines, RE_CS_INIT_METHOD) if is_unity
                   else [])
    ident_types, unity_classes = (_cs_identifier_types(lines) if is_unity
                                  else ({}, set()))

    for m in RE_CS_EMPTY_LIFECYCLE.finditer(joined):
        line = joined[: m.start()].count("\n") + 1
        add(findings, path, line, "P2", "empty-lifecycle",
            "empty Unity lifecycle method still costs a native->managed call "
            "per frame", anchor_of(lines, line))

    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        anchor = anchor_of(lines, idx)
        code = strip_code(text)

        if is_unity:
            for m in RE_CS_NULLCOND.finditer(code):
                recv = m.group(1)
                declared = ident_types.get(recv)
                base = declared.split(".")[-1] if declared else None
                if (recv in UNITY_BUILTIN_MEMBERS
                        or base in UNITY_OBJECT_TYPES
                        or base in unity_classes):
                    add(findings, path, idx, "P1", "unity-null-conditional",
                        f"'{recv}' is a UnityEngine.Object - ?. and ?? skip the "
                        "destroyed-object check; use an explicit != null",
                        anchor)
                elif base in NON_UNITY_TYPES or recv in UNITY_BUILTIN_VALUES:
                    pass  # plain C#, the operators mean what they say
                else:
                    add(findings, path, idx, "P3", "unity-null-conditional",
                        f"?. / ?? on '{recv}', type not resolvable here - "
                        "confirm it is not a UnityEngine.Object", anchor)
                break

        if RE_CS_ASYNC_VOID.search(code) and not RE_CS_EVENT_HANDLER.search(code):
            add(findings, path, idx, "P2", "async-void",
                "async void - exceptions escape unobservable", anchor)

        if is_unity and RE_CS_DEBUG_LOG.search(code):
            add(findings, path, idx, "P3", "debug-log",
                "Debug.Log ships to builds - gate or delete", anchor)

        in_init = any(lo <= idx <= hi for lo, hi in init_ranges)
        if is_unity and RE_CS_EXPENSIVE.search(code) and not in_init:
            add(findings, path, idx, "P2", "expensive-lookup",
                "scene-wide lookup - cache it in Awake or Start", anchor)

        in_perframe = any(lo <= idx <= hi for lo, hi in perframe)
        if in_perframe and RE_CS_PERFRAME.search(code):
            add(findings, path, idx, "P2", "perframe-lookup",
                "component lookup inside a per-frame method", anchor)
        if in_perframe and RE_CS_LINQ.search(code):
            add(findings, path, idx, "P2", "perframe-linq",
                "LINQ in a per-frame method allocates every frame", anchor)


# --------------------------------------------------------------------------
# c++ / ue5
# --------------------------------------------------------------------------

RE_CPP_STD = re.compile(
    r"\bstd::(vector|map|unordered_map|set|string|shared_ptr|unique_ptr|optional)\b")
RE_CPP_IOSTREAM = re.compile(r"\b(std::cout|std::cerr|printf)\s*(<<|\()")
RE_CPP_TRY = re.compile(r"\b(try\s*\{|catch\s*\()")
RE_CPP_MEMBER_PREFIX = re.compile(r"\bm_[A-Za-z]")
RE_CPP_UOBJ_MEMBER = re.compile(
    r"^\s*(?:class\s+)?([UA][A-Z]\w+)\s*\*\s*(\w+)\s*(=\s*([^;]+))?;\s*$")
RE_CPP_TARRAY_VALUE = re.compile(r"\(\s*(?!const\b)TArray<[^>]+>\s+\w+")
RE_CPP_FSTRING_VALUE = re.compile(r"\(\s*(?!const\b)FString\s+\w+\s*[,)]")
RE_CPP_REDUNDANT_NULL = re.compile(
    r"\bif\s*\(\s*!?\s*(?:IsValid\s*\(\s*)?(\w+)\s*\)?\s*"
    r"(?:[!=]=\s*nullptr)?\s*\)")
RE_CPP_NEWOBJECT_ASSIGN = re.compile(
    r"\b(\w+)\s*=\s*(?:NewObject<|CreateDefaultSubobject<)")
RE_CPP_CLASS_OPEN = re.compile(
    r"^\s*(?:template\s*<[^>]*>\s*)?(class|struct)\s+(?:\w+_API\s+)?\w+"
    r"(?:\s*:\s*[^;{]+)?\s*(\{)?\s*$")
RE_CPP_FUNC_OPEN = re.compile(r"\)\s*(const)?\s*(noexcept)?\s*(override)?\s*\{\s*$")
# Allman brace, which is Epic's own style and the majority of UE code: the
# signature ends the line and the body's brace is on the next one.
RE_CPP_FUNC_SIG = re.compile(
    r"\)\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:final\s*)?$")
RE_CPP_CONTROL = re.compile(r"^\s*(if|else|for|while|switch|catch|do|return)\b")
NULLISH_INIT = {"nullptr", "null", "NULL", "{}", "0"}


def _has_uproperty_above(lines, idx, lookback=8):
    """True if the declaration at line `idx` carries a UPROPERTY/UFUNCTION
    macro, including the wrapped form.

    Only the single line above was checked, so Epic's own house style -

        UPROPERTY(VisibleAnywhere, BlueprintReadOnly,
                  Category = "Components")
        UStaticMeshComponent* Mesh;

    - looked like a bare member and drew a P1 saying it had no UPROPERTY.
    Walking back while the parenthesis balance stays open finds the macro
    without treating an unrelated declaration two lines up as one.
    """
    if "UPROPERTY" in lines[idx - 1]:
        return True
    depth = 0
    for j in range(idx - 2, max(-1, idx - 2 - lookback), -1):
        code = strip_code(lines[j])
        if "UPROPERTY" in code or "UFUNCTION" in code:
            return True
        depth += code.count(")") - code.count("(")
        if depth <= 0:
            return False
    return False


def _cpp_member_ranges(lines):
    """Line ranges inside a class/struct body, inline method bodies included.

    Without this, every local `UWorld* World = GetWorld();` in a .cpp was
    reported P1 as an unrooted UObject member. Locals are on the stack; the
    GC rule is about members. Subtracting inline method bodies is the caller's
    job, using `_cpp_function_ranges`.
    """
    ranges = []
    i = 0
    n = len(lines)
    while i < n:
        m = RE_CPP_CLASS_OPEN.match(strip_code(lines[i]))
        if not m:
            i += 1
            continue
        # find the opening brace (same line or the next non-empty one)
        j = i
        if not m.group(2):
            while j + 1 < n and "{" not in strip_code(lines[j]):
                j += 1
                if strip_code(lines[j]).strip().endswith(";"):
                    break
        if "{" not in strip_code(lines[j]):
            i += 1
            continue
        depth = 0
        start = j + 1
        for k in range(j, n):
            code = strip_code(lines[k])
            depth += code.count("{") - code.count("}")
            if depth <= 0 and k > j:
                ranges.append((start, k + 1))
                i = k
                break
        else:
            ranges.append((start, n))
            break
        i += 1
    return ranges


def _cpp_function_ranges(lines):
    """Line ranges inside a function body (top level or inline)."""
    ranges = []
    n = len(lines)
    k = 0
    while k < n:
        code = strip_code(lines[k])
        brace_at = None
        if RE_CPP_FUNC_OPEN.search(code):
            brace_at = k
        elif (RE_CPP_FUNC_SIG.search(code.rstrip())
              and not RE_CPP_CONTROL.match(code)
              and k + 1 < n and strip_code(lines[k + 1]).strip() == "{"):
            brace_at = k + 1
        if brace_at is not None:
            depth = 0
            for j in range(brace_at, n):
                c = strip_code(lines[j])
                depth += c.count("{") - c.count("}")
                if depth <= 0:
                    ranges.append((k + 1, j + 1))
                    k = j
                    break
            else:
                ranges.append((k + 1, n))
                break
        k += 1
    return ranges


def check_cpp(path, lines, findings):
    joined = "\n".join(lines)
    is_ue = ("UPROPERTY" in joined or "UCLASS" in joined
             or "#include \"CoreMinimal.h\"" in joined or "AActor" in joined)
    member_ranges = _cpp_member_ranges(lines) if is_ue else []
    func_ranges = _cpp_function_ranges(lines) if is_ue else []

    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        prev = lines[idx - 2] if idx >= 2 else ""
        anchor = anchor_of(lines, idx)

        if is_ue and RE_CPP_STD.search(text):
            add(findings, path, idx, "P2", "std-in-ue",
                "std container in Unreal code - TArray/TMap/FString are the "
                "house convention", anchor)

        # UE_LOG does not exist outside Unreal, so this advice is only advice
        # in a UE translation unit. Plain C++ printf is just printf.
        if is_ue and RE_CPP_IOSTREAM.search(text):
            add(findings, path, idx, "P2", "raw-output",
                "printf/iostream instead of UE_LOG", anchor)

        if is_ue and RE_CPP_TRY.search(text):
            add(findings, path, idx, "P2", "exceptions-in-ue",
                "most UE builds disable exceptions - check the module's build "
                "settings", anchor)

        if is_ue and RE_CPP_MEMBER_PREFIX.search(text):
            add(findings, path, idx, "P3", "member-prefix",
                "m_ prefix is not the Unreal naming convention", anchor)

        m = RE_CPP_UOBJ_MEMBER.match(text) if is_ue else None
        if m:
            init = (m.group(4) or "").strip()
            in_member = any(lo <= idx <= hi for lo, hi in member_ranges)
            # Inside a function body it is a stack local, and locals are not
            # GC roots to begin with. That holds for inline methods too, which
            # sit inside the class body's member range - the previous guard
            # `not (in_func and not in_member)` reduced to `True` there and
            # every local in an inline method was reported as a member.
            in_func = any(lo <= idx <= hi for lo, hi in func_ranges)
            has_prop = _has_uproperty_above(lines, idx)
            if (in_member and not in_func and not has_prop
                    and (not init or init in NULLISH_INIT)):
                add(findings, path, idx, "P1", "unrooted-uobject",
                    f"'{m.group(2)}' is a raw UObject* member without "
                    "UPROPERTY() - invisible to the GC", anchor)

        if RE_CPP_TARRAY_VALUE.search(text) or RE_CPP_FSTRING_VALUE.search(text):
            add(findings, path, idx, "P2", "pass-by-value",
                "TArray/FString taken by value - copies on every call", anchor)

        # The check has to be ON the allocated object. Matching any `if (...)`
        # after a NewObject line flagged `if (bWantsInit)` just as loudly.
        m_new = RE_CPP_NEWOBJECT_ASSIGN.search(strip_code(prev))
        m_null = RE_CPP_REDUNDANT_NULL.search(text) if m_new else None
        if m_new and m_null and m_null.group(1) == m_new.group(1):
            add(findings, path, idx, "P2", "impossible-null-check",
                f"'{m_new.group(1)}' comes from NewObject/"
                "CreateDefaultSubobject, which cannot return null - it "
                "crashes instead", anchor)


# --------------------------------------------------------------------------
# shared: unused members and alias locals for brace languages
# --------------------------------------------------------------------------

RE_MEMBER_DECL = re.compile(
    r"^\s*(?:\[[^\]]*\]\s*)*"
    r"(?:(?:public|private|protected|internal|static|readonly|const|mutable|"
    r"volatile|virtual|override|serialize|inline)\s+)*"
    r"[\w:<>,\s\*&\[\]]+?\s+(\w+)\s*(?:=[^;]*)?;\s*$")
RE_ALIAS_LOCAL = re.compile(
    r"^\s*(?:var|auto|const\s+auto|[\w:<>\*&]+)\s+(\w+)\s*=\s*"
    r"([A-Za-z_]\w*)\s*;\s*$")
RE_DECL_SKIP = re.compile(
    r"^\s*(return|using|import|package|namespace|#|//|/\*|\*|typedef|delegate|"
    r"friend|template|else|case|partial)\b")
# Access modifiers and the engine macros are the direct exposures. The rest
# are attributes binding a field to something no token count in this file can
# see: a scene file, a serializer, a DI container, the IL2CPP stripper. The
# asymmetry decides what belongs here - over-matching costs a P3 and a confirm
# note, under-matching emits P2 with no note, and P2-with-no-note is this
# scanner's delete instruction. An attribute whose reach is uncertain is
# therefore listed. Deleting a [SerializeReference] field drops every value
# already set in scenes and prefabs, silently, with a clean compile.
EXPOSED = re.compile(
    r"\b(public|protected|internal|export"
    r"|UPROPERTY|UFUNCTION"
    # Unity serialization: the value lives in a scene or prefab, not in code.
    r"|SerializeField|SerializeReference|FormerlySerializedAs|Serializable"
    # Reached by reflection: stripping, DI, editor entry points.
    r"|Preserve|RuntimeInitializeOnLoadMethod|InitializeOnLoad"
    r"|InitializeOnLoadMethod|MenuItem|ContextMenu|ContextMenuItem"
    r"|Inject|Injected"
    # Serializer contracts - the field name is the wire format.
    r"|JsonProperty|JsonPropertyName|JsonInclude|JsonRequired|JsonConverter"
    r"|DataMember|DataContract|ProtoMember|XmlElement|XmlAttribute|XmlArray"
    # Interop: the layout or the callback address is the contract.
    r"|DllImport|MonoPInvokeCallback|UnmanagedCallersOnly"
    r"|StructLayout|MarshalAs|FieldOffset"
    r")\b")

EXPOSED_LOOKBACK = 12


def _exposed_above(lines, idx, lookback=EXPOSED_LOOKBACK):
    """Is there an exposing attribute in the block decorating this line?

    Track bracket and paren balance rather than matching each line's shape,
    for the reason `_has_uproperty_above` does the same: the verdict must not
    depend on how the author wrapped their attributes. All three of these are
    one serialized field to Unity, and every one of them must keep the P3
    "confirm before removing" note:

        [SerializeField]
        [Tooltip("...")]                  stacked, one per line
        private AnimationCurve curve;

        [Tooltip("...")] [SerializeField] two groups on one line
        private float damping;

        [SerializeField,
         Range(0f, 1f)]                   wrapped attribute list
        private float speed;

    A line-shape gate accepts only the first, dropping the other two to P2
    with no note - on exactly the declarations this must never advise deleting
    unchecked. Walking upward while a bracket or paren group stays open also
    keeps an unrelated declaration two lines up from reading as decoration.
    """
    pending = 0          # unmatched closing brackets seen so far, walking up
    for j in range(idx - 1, max(0, idx - 1 - lookback), -1):
        raw = lines[j - 1].strip()
        code = strip_code(lines[j - 1])
        stripped = code.strip()

        # A comment continues the decorating block without ending it. Test the
        # RAW line: strip_code blanks `//` comments, so a `//` branch keyed on
        # the stripped text can never fire - which silently dropped the
        # confirm-before-removing note from every serialized field documented
        # with `///`, the ordinary C# way to document one.
        if raw.startswith(("//", "/*", "*")):
            continue

        if not stripped:
            if pending:
                continue
            return False

        closers = code.count("]") + code.count(")")
        openers = code.count("[") + code.count("(")

        # `closers > openers` catches a wrapped continuation like
        # `  Range(0f, 1f)]`, which starts with no bracket and would otherwise
        # end the walk immediately.
        if not (pending > 0 or stripped.startswith("[") or closers > openers):
            return False                       # a declaration, not decoration

        # Only search once we know this line is part of the block. Searching
        # unconditionally made `public class W {` one line above a private
        # field mark it exposed.
        if EXPOSED.search(code):
            return True
        pending = max(0, pending + closers - openers)
    return False


# `$"...{expr}..."` puts code inside a string literal. strip_code blanks the
# whole literal - correct for the brace counting it exists for - so the tokens
# in an interpolation hole never reached the counter, and a field referenced
# only from a format string counted as unreferenced. Read the holes here
# rather than teaching strip_code to keep them: _exposed_above balances
# brackets on stripped text, and leaving the braces in would desynchronise
# that walk. C# only - Python f-strings reach the counter through ast, and
# C++ has no interpolation.
RE_CS_INTERPOLATED = re.compile(r"(?:\$@|@\$|\$)\"(?:\\.|\"\"|[^\"\\])*\"")


def interpolation_holes(text):
    """Identifiers inside `$"..."` interpolation holes.

    `{{` and `}}` are literal braces rather than holes, so they come out
    first. Depth is tracked because a hole can hold a collection initialiser
    or a nested interpolation, and a non-greedy `{(.*?)}` would end the hole
    at the first inner brace. A format spec (`{n,6:N0}`) contributes its
    suffix as a token too - over-counting only ever suppresses a finding,
    which is the safe direction for a rule that advises deletion.
    """
    names = []
    for literal in RE_CS_INTERPOLATED.findall(text):
        body = literal.replace("{{", "").replace("}}", "")
        depth = start = 0
        for i, ch in enumerate(body):
            if ch == "{":
                if depth == 0:
                    start = i + 1
                depth += 1
            elif ch == "}" and depth:
                depth -= 1
                if depth == 0:
                    names.extend(re.findall(r"\b[A-Za-z_]\w*\b", body[start:i]))
    return names


# --------------------------------------------------------------------------
# web rules - JavaScript/TypeScript, HTML, CSS
#
# Regex level, and that is a ceiling rather than a stage: this scanner is
# stdlib Python and `ast` reads Python. So every rule below is anchored on a
# token that means one thing wherever it appears, and the structural half of
# the web pass - unused bindings, dead functions, near-duplicate components -
# is Agent A's by reading. `references/web.md` and `core-patterns.md` both say
# so; a quiet scan over a .ts diff is not coverage of those.
# --------------------------------------------------------------------------

# The statement, not the word. A `\bdebugger\b` rule hands `this.debugger.attach()`
# to a deleter at P1. So this anchors on both sides: a statement position in front
# (start of line, `;` or `{`) and a statement terminator behind. That keeps
# `{ mounted() { debugger; } }` - how it appears in a single-file component - while
# `.debugger` and `debuggerEnabled` match neither side. `if (x) debugger;` is a
# deliberate miss: the widening that caught it would also catch every property
# access.
RE_JS_DEBUGGER = re.compile(r"(?:^|[;{])\s*debugger\s*(?=[;}]|\s*$)")

# `.only` disables every other test in the file, silently, with a green run
# and a shrunken count nobody reads. Unambiguous in any file: nothing else is
# spelled `describe.only(`.
RE_JS_TEST_ONLY = re.compile(
    r"\b(?:describe|context|it|test|suite|bench)\s*\.\s*only\s*\(")

# Jasmine's spelling of the same thing, and gated on the file being a test
# file because `fit` is also an ordinary function name - fit a curve, fit a
# layout, fit a bounding box. Ungated this is a P1 on somebody's maths.
RE_JS_TEST_ONLY_JASMINE = re.compile(r"^\s*(?:fit|fdescribe|fcontext)\s*\(")

# `console.error` and `console.warn` are absent on purpose: those are how a
# library reports a real problem, and flagging them is how this rule would
# stop being read.
RE_JS_CONSOLE = re.compile(r"\bconsole\s*\.\s*(log|debug|trace|dir)\s*\(")

RE_JS_DEEP_CLONE = re.compile(
    r"JSON\s*\.\s*parse\s*\(\s*JSON\s*\.\s*stringify\s*\(")

# A role that restates the element's own semantic. Same-line only, because
# that is where an attribute on an opening tag is written and it is the only
# form a line-based scanner can attribute to the right element.
HTML_REDUNDANT_ROLE = [
    (re.compile(r"<button\b[^>]*\brole\s*=\s*[\"']button[\"']", re.I), "button"),
    (re.compile(r"<nav\b[^>]*\brole\s*=\s*[\"']navigation[\"']", re.I), "nav"),
    (re.compile(r"<main\b[^>]*\brole\s*=\s*[\"']main[\"']", re.I), "main"),
    (re.compile(r"<header\b[^>]*\brole\s*=\s*[\"']banner[\"']", re.I), "header"),
    (re.compile(r"<footer\b[^>]*\brole\s*=\s*[\"']contentinfo[\"']", re.I),
     "footer"),
    (re.compile(r"<(?:ul|ol)\b[^>]*\brole\s*=\s*[\"']list[\"']", re.I), "ul/ol"),
    (re.compile(r"<li\b[^>]*\brole\s*=\s*[\"']listitem[\"']", re.I), "li"),
    (re.compile(r"<form\b[^>]*\brole\s*=\s*[\"']form[\"']", re.I), "form"),
    (re.compile(r"<table\b[^>]*\brole\s*=\s*[\"']table[\"']", re.I), "table"),
]

# Dead since HTML5 and still emitted constantly. Attribute order is not
# assumed: each alternative matches its own attribute anywhere in the tag.
RE_HTML_OBSOLETE = re.compile(
    r"<script\b[^>]*\btype\s*=\s*[\"']text/javascript[\"']"
    r"|<script\b[^>]*\blanguage\s*=\s*[\"']javascript[\"']"
    r"|<link\b[^>]*\btype\s*=\s*[\"']text/css[\"']"
    r"|<style\b[^>]*\btype\s*=\s*[\"']text/css[\"']"
    r"|<meta\b[^>]*\bname\s*=\s*[\"']keywords[\"']", re.I)

# Prefixed properties whose unprefixed form has been universally supported for
# over a decade. This is a NAMED LIST and not a "-webkit- is legacy" rule on
# purpose: -webkit-line-clamp, -webkit-overflow-scrolling, -webkit-appearance,
# -webkit-text-size-adjust, -webkit-box-orient and -moz-osx-font-smoothing are
# still required today, and a sweeping rule would propose deleting live CSS.
RE_CSS_DEAD_PREFIX = re.compile(
    r"^\s*-(?:webkit|moz|ms|o)-"
    r"(border-radius|box-shadow|box-sizing|opacity|border-image"
    r"|transition(?:-[a-z]+)?|transform(?:-origin)?|animation(?:-[a-z]+)?)"
    r"\s*:", re.I)

RE_CSS_TRANSITION_ALL = re.compile(
    r"\btransition(?:-property)?\s*:\s*all\b", re.I)

# `@media {}` and `@supports {}` are excluded by the leading class: an empty
# at-rule is a different question from an empty rule, and one of them is a
# build artifact.
RE_CSS_EMPTY_RULE = re.compile(r"^\s*[^@{}/*\s][^{}]*\{\s*\}\s*;?\s*$")


def _css_uncommented(lines):
    """`lines` with every `/* */` span blanked, tracked across line breaks.

    Blanked rather than dropped, because `.b { color: red } /* note */` has a
    live declaration and a comment on the same line, and dropping the line
    loses the finding.

    `comment_body` cannot be reused here: it reads a leading `#` as a comment
    marker, which is true in Python and shell and false in CSS, where `#id` is
    a selector. Every `#id { … }` rule in the file would have gone silent.

    A `//` comment - legal in SCSS and LESS, not in CSS - is honoured only at
    the start of a line. Anywhere else it is far more often the `//` in a
    `url(https://…)`.

    Quoted values are tracked for one reason only: a `/*` inside a string is
    not a comment, and reading it as one opened a block that never closed and
    silenced every rule below it for the rest of the file - no error, and the
    file still counted as scanned. A string does not survive a line break in
    CSS, so quote state resets at end of line and an apostrophe in a value
    cannot latch the way the comment did.
    """
    out = []
    depth = 0
    quote = None
    for text in lines:
        if depth == 0 and quote is None and text.lstrip().startswith("//"):
            out.append("")
            continue
        buf = []
        i = 0
        while i < len(text):
            ch = text[i]
            if quote is not None:
                if ch == "\\" and i + 1 < len(text):
                    buf.append(text[i:i + 2]); i += 2
                    continue
                if ch == quote:
                    quote = None
                buf.append(ch); i += 1
            elif depth == 0 and ch in "\"'":
                quote = ch
                buf.append(ch); i += 1
            elif depth == 0 and text.startswith("/*", i):
                depth, i = 1, i + 2
                buf.append("  ")
            elif depth and text.startswith("*/", i):
                depth, i = 0, i + 2
                buf.append("  ")
            else:
                buf.append(" " if depth else ch)
                i += 1
        quote = None
        out.append("".join(buf))
    return out


def _js_uncommented(lines):
    """`lines` with JavaScript strings and comments blanked, tracked across
    line breaks.

    `strip_code` cannot do this job and must not be widened to try: it is
    shared with the C# and C++ checkers, where `#` opens a preprocessor
    directive and a backtick means nothing. In JavaScript `#` is the
    private-name sigil - `this.#count` - so treating it as a comment marker
    blanked the rest of the line and dropped every rule on it, including the
    only P1 this pass has. And a backtick opens a template literal that runs
    to the next unescaped backtick, possibly several lines down, so example
    code inside one was reported as live code.

    Template literal contents are blanked whole, `${...}` interpolations
    included. That is a deliberate false negative: an interpolation does hold
    real code, but reading it needs brace tracking through nested templates,
    and a missed finding is the safe direction for a pass whose findings
    propose deletions.
    """
    out = []
    state = None                      # None | sq | dq | tpl | block
    for text in lines:
        buf, i, n = [], 0, len(text)
        while i < n:
            ch = text[i]
            if state is None:
                if text.startswith("//", i):
                    buf.append(" " * (n - i)); i = n
                elif text.startswith("/*", i):
                    state = "block"; buf.append("  "); i += 2
                elif ch in "'\"`":
                    state = {"'": "sq", '"': "dq", "`": "tpl"}[ch]
                    buf.append(ch); i += 1
                else:
                    buf.append(ch); i += 1
            elif state == "block":
                if text.startswith("*/", i):
                    state = None; buf.append("  "); i += 2
                else:
                    buf.append(" "); i += 1
            else:
                if ch == "\\" and i + 1 < n:
                    buf.append("  "); i += 2
                elif ((ch == "'" and state == "sq")
                        or (ch == '"' and state == "dq")
                        or (ch == "`" and state == "tpl")):
                    state = None; buf.append(ch); i += 1
                else:
                    buf.append(" "); i += 1
        # Only a template literal survives a newline. Dropping sq/dq state here
        # is what stops an apostrophe in JSX text - `<p>don't</p>` - from
        # blanking every line below it, which is the latch bug this scanner
        # already shipped once in the CSS pass.
        if state in ("sq", "dq"):
            state = None
        out.append("".join(buf))
    return out


def check_js(path, lines, findings):
    is_test = bool(TEST_HINT.search(path))
    clean = _js_uncommented(lines)
    for idx in range(1, len(lines) + 1):
        anchor = anchor_of(lines, idx)
        code = clean[idx - 1]

        if RE_JS_DEBUGGER.search(code):
            # `is_test` demotes because a fixture is usually testing this.
            add(findings, path, idx, "P2" if is_test else "P1", "js-debugger",
                "debugger statement - halts execution wherever devtools are "
                "open", anchor)

        if (RE_JS_TEST_ONLY.search(code)
                or (is_test and RE_JS_TEST_ONLY_JASMINE.search(code))):
            add(findings, path, idx, "P1", "js-test-only",
                "focused test - every other test in this file is silently "
                "skipped and the suite still passes", anchor)

        if not is_test and RE_JS_CONSOLE.search(code):
            add(findings, path, idx, "P3", "js-console",
                "console.log left from a debugging pass - confirm, this is "
                "output in a CLI", anchor)

        if RE_JS_DEEP_CLONE.search(code):
            add(findings, path, idx, "P3", "js-deep-clone",
                "JSON.parse(JSON.stringify(x)) - structuredClone, and this "
                "form drops Date, Map, Set and undefined", anchor)


def _html_uncommented(lines):
    """`lines` with every `<!-- -->` span blanked, tracked across line breaks.

    Blanked rather than dropped, for the reason the CSS pass gives: live markup
    and a comment share a line constantly, and dropping the line loses the
    finding.

    No string handling, and none is wanted. HTML attribute values cannot
    contain a raw `<`, so `<!--` inside one is not expressible without an
    entity - which is the opposite of CSS, where a quoted `/*` is ordinary and
    was the whole latch. A conditional comment (`<!--[if lt IE 9]>`) is a
    comment by this rule and closes on its `-->` like any other.
    """
    out = []
    depth = 0
    for text in lines:
        buf, i, n = [], 0, len(text)
        while i < n:
            if depth == 0 and text.startswith("<!--", i):
                depth = 1; buf.append("    "); i += 4
            elif depth and text.startswith("-->", i):
                depth = 0; buf.append("   "); i += 3
            else:
                buf.append(" " if depth else text[i]); i += 1
        out.append("".join(buf))
    return out


def check_html(path, lines, findings):
    clean = _html_uncommented(lines)
    for idx in range(1, len(lines) + 1):
        text = clean[idx - 1]
        anchor = anchor_of(lines, idx)

        for pattern, element in HTML_REDUNDANT_ROLE:
            if pattern.search(text):
                add(findings, path, idx, "P3", "html-redundant-role",
                    f"role may restate what <{element}> already means - confirm, "
                    "header/footer/li/form map to their role only in the right "
                    "container", anchor)
                break

        if RE_HTML_OBSOLETE.search(text):
            add(findings, path, idx, "P3", "html-obsolete-attr",
                "attribute obsolete since HTML5", anchor)


def check_css(path, lines, findings):
    # Only a real stylesheet gets the empty-rule rule. In a .vue or .svelte
    # file the same pattern matches `methods: {}` and `function f() {}` in the
    # script block - live JavaScript, reported as an abandoned CSS rule. The
    # other two rules are anchored on syntax that means the same thing in a
    # style object as in a stylesheet, so they run everywhere.
    pure_css = os.path.splitext(path)[1].lower() not in MIXED_WEB_EXT
    clean = _css_uncommented(lines)
    for idx in range(1, len(lines) + 1):
        text = clean[idx - 1]
        anchor = anchor_of(lines, idx)

        if RE_CSS_DEAD_PREFIX.match(text):
            # P3 and never a bare delete instruction: the line above or below
            # may be the unprefixed form this one is the fallback for, and
            # only the last declaration in a rule is the live one.
            add(findings, path, idx, "P3", "css-dead-prefix",
                "vendor prefix settled for a decade - confirm nothing here "
                "relies on it as a fallback", anchor)

        if RE_CSS_TRANSITION_ALL.search(text):
            add(findings, path, idx, "P3", "css-transition-all",
                "transition: all animates properties nobody chose, including "
                "ones added later", anchor)

        if pure_css and RE_CSS_EMPTY_RULE.match(text):
            add(findings, path, idx, "P3", "css-empty-rule",
                "empty rule", anchor)


def check_bindings(path, lines, findings, exposed_note):
    """Bindings declared and never referenced (fields or locals); locals that
    only rename another binding for a single use.

    Whole-file token counting cannot see other files, other translation units,
    partial classes, or reflection. Anything exposed is therefore P3 with a
    confirm note, never a delete instruction.
    """
    stripped = [strip_code(t) for t in lines]
    counts = defaultdict(int)
    for token in re.findall(r"\b[A-Za-z_]\w*\b", "\n".join(stripped)):
        counts[token] += 1
    for text in lines:
        for name in interpolation_holes(text):
            counts[name] += 1
    is_partial = bool(re.search(r"\bpartial\s+(class|struct)\b", "\n".join(stripped)))
    is_header = os.path.splitext(path)[1].lower() in {".h", ".hpp", ".inl"}

    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        anchor = anchor_of(lines, idx)
        # test the declaration half only - an initialiser may legitimately
        # contain a call (`private List<int> items = new List<int>();`)
        decl_part = text.split("=", 1)[0]
        if RE_DECL_SKIP.match(text) or "(" in decl_part or ")" in decl_part:
            continue

        m = RE_ALIAS_LOCAL.match(text)
        if m:
            name, source = m.group(1), m.group(2)
            if counts[name] == 2 and source not in ("new", "this", "nullptr", "null"):
                add(findings, path, idx, "P3", "alias-variable",
                    f"'{name}' just renames '{source}' for a single use - "
                    "inline it", anchor)
                continue

        # A header declares; the definition and every caller live in other
        # translation units, and a partial class continues in another file.
        # "Never referenced in this file" is vacuous for every line in them,
        # so the rule reported the entire header - most loudly on exactly the
        # UPROPERTY declarations it must never advise deleting.
        if is_header or is_partial:
            continue

        m = RE_MEMBER_DECL.match(text)
        if m:
            name = m.group(1)
            if counts[name] == 1 and len(name) > 1:
                is_exposed = bool(EXPOSED.search(text)
                                  or _exposed_above(lines, idx))
                add(findings, path, idx,
                    "P3" if is_exposed else "P2", "unused-binding",
                    f"'{name}' is declared and never referenced in this file"
                    + (f" - {exposed_note}" if is_exposed else ""), anchor)
            continue


# --------------------------------------------------------------------------
# reconciliation with a previous run
# --------------------------------------------------------------------------

def finding_key(f):
    """Stable across line shifts, unique per instance.

    Line numbers move as soon as you delete anything, so they cannot be part
    of the key. The message alone is not enough either - most rules emit a
    constant string, so N instances in one file collapsed to one key and
    fixing some of them showed up as neither resolved nor live. The anchor is
    the normalised source line, which distinguishes them and survives shifts.
    """
    return (f["path"], f["rule"], f["message"], f.get("anchor", ""))


# The fields `finding_key` reads off a prior entry.
KEY_FIELDS = ("path", "rule", "message")
# `--since` echoes each matched prior entry straight into `resolved`, and the
# text printer reads these off it. `--declined` needs only the key fields: the
# entries it emits are this run's own findings, not the ones it matched against.
ECHO_FIELDS = KEY_FIELDS + ("severity", "line")


def usable_entries(entries, flag, needs):
    """Prior-report entries carrying every field we are going to read.

    Both callers used to check `path` and `rule` and then hand the entry to
    `finding_key`, which also reads `message`. So a hand-written `declined.json`
    holding `{path, rule, line}` - the obvious thing to write, and close to
    what SKILL.md's own example invites - raised `KeyError: 'message'`: exit 1,
    empty stdout, and under `--json` a traceback where the consumer was
    promised a report. These files are explicitly hand-maintained, so a partial
    entry is an expected input rather than a bug, and the only behaviour that
    leaves the run usable is to skip it and say which flag dropped what.
    """
    ok, bad = [], 0
    for e in entries:
        if isinstance(e, dict) and all(k in e for k in needs):
            ok.append(e)
        else:
            bad += 1
    if bad:
        warn(f"{flag}: ignored {bad} malformed entr{'y' if bad == 1 else 'ies'}"
             f" - each needs {', '.join(needs)}, which is what an entry is "
             "matched on; copy the finding object as the scanner emitted it")
    return ok


def load_report(path, flag):
    """A previous run's JSON, or None after warning why not."""
    try:
        with open(path, encoding="utf-8") as fh:
            prior = json.load(fh)
    except (OSError, ValueError) as exc:
        warn(f"{flag}: could not read {path} ({exc}) - ignoring it")
        return None
    # Any JSON file at all can be pointed at these flags. A list or a string
    # used to reach .get() and raise, which exited 1 with empty stdout - a
    # --json consumer saw a parse error rather than a report.
    if not isinstance(prior, dict) or not isinstance(prior.get("findings"), list):
        warn(f"{flag}: {path} is not a scanner report (no 'findings' array) - "
             "ignoring it")
        return None
    return prior


def number_occurrences(findings):
    """Stamp each finding with its 1-based index among its same-key siblings,
    counted in FILE ORDER.

    `finding_key` excludes the line number, so N instances of one rule in one
    file are indistinguishable by key alone and `--declined` had to guess.
    Sorting by line is not cosmetic: the Python rules emit through `ast.walk`
    (breadth-first), so arrival order gave occurrence 1 to the last match in
    the file - while SKILL.md tells the executor to count anchor matches top
    to bottom. File order is also the only ordering a reader can reproduce.
    """
    by_key = defaultdict(list)
    for f in findings:
        by_key[finding_key(f)].append(f)
    for group in by_key.values():
        for n, f in enumerate(sorted(group, key=lambda x: x["line"]), 1):
            f["occurrence"] = n


def number_anchor_matches(findings):
    """Stamp `anchor_index` / `anchor_total`: where this finding's line sits
    among the lines of its file that match the anchor, and how many there are.

    A different population from `occurrence`, which counts findings sharing a
    key: a diff-scoped run stamps 1 on the only flagged instance even when the
    anchor is on three lines and it is the third. The executor counts matching
    lines, so handed the flagged index it edits the first match - code nobody
    reviewed or approved. The total is what makes the ordinal safe: any change
    in it means the ordinal no longer identifies what it did, so the item is
    stale, which costs a re-run rather than a wrong-line edit.
    """
    for f in findings:
        anchor = f.get("anchor") or ""
        lines = FILE_LINES.get(f["path"])
        if not anchor or lines is None:
            continue
        # A truncated anchor is a prefix, and the executor is told to treat it
        # as one. Matching on equality here would count fewer lines than it
        # does, and every long anchor would come back stale.
        truncated = len(anchor) == ANCHOR_MAX
        matches = [n for n, text in enumerate(lines, 1)
                   if (normalise_anchor(text).startswith(anchor) if truncated
                       else normalise_anchor(text) == anchor)]
        if not matches:
            continue
        f["anchor_total"] = len(matches)
        # The finding's own line always matches: every `add()` site passes
        # `anchor_of(lines, X)` for the same X it passes as the line, against
        # this same list. A guarded fallback here would be unreachable code in
        # the one function that decides which line an approved fix edits.
        f["anchor_index"] = matches.index(f["line"]) + 1


def split_declined(findings, declined_path):
    """Move findings the user already rejected out of the live list.

    Without this a declined finding came back as `persisting` on every run.
    A punch list that keeps re-raising settled items trains the reader to
    skim, and then they skim past the P1 too.

    Per instance, not per key. `finding_key` excludes the line number so a
    decline survives line shifts, and most rules emit a constant message, so N
    occurrences in one file share a key: a set-membership test declines all N
    once the user declines any one - including occurrences written later.
    Counting alone is not enough either, since spending the budget in file
    order silences the instance at line 4 when the user declined line 9. So
    `line` picks among candidates that already matched all four key fields;
    entries with no usable `line` fall back to file order.
    """
    prior = load_report(declined_path, "--declined")
    if prior is None:
        return findings, []

    by_key = defaultdict(list)
    for i, f in enumerate(findings):
        by_key[finding_key(f)].append(i)

    taken = set()
    for d in usable_entries(prior["findings"], "--declined", KEY_FIELDS):
        pool = [i for i in by_key[finding_key(d)] if i not in taken]
        if not pool:
            continue
        occ = d.get("occurrence")
        if isinstance(occ, int):
            # Exact: same key, same position among its siblings. Survives any
            # line shift, which is the whole reason `line` is not in the key.
            exact = [i for i in pool if findings[i].get("occurrence") == occ]
            if exact:
                taken.add(exact[0])
                continue
        want = d.get("line")
        if isinstance(want, int):
            # Fallback for a declined.json written before occurrences existed.
            # A guess, and it can pick the wrong sibling once lines have moved.
            pool.sort(key=lambda i: (abs(findings[i]["line"] - want),
                                     findings[i]["line"]))
        taken.add(pool[0])

    live, declined = [], []
    for i, f in enumerate(findings):
        if i in taken:
            f["status"] = "declined"
            declined.append(f)
        else:
            live.append(f)
    return live, declined


def reconcile(findings, prior_path, scanned_paths=None):
    """Mark findings new/persisting; return (generated, resolved, out_of_scope).

    A finding present in the prior report and absent now is either fixed or no
    longer true. Either way it must not be re-reported as live - a punch list
    that keeps resurfacing settled items stops being read.

    `scanned_paths` is what keeps "absent" honest. A file that left the scope
    between runs - committed, unstaged, or simply not part of the narrower
    scope this run resolved - was never opened, so nothing was learned about
    its findings and calling them resolved is a claim we cannot support. That
    happens on the ordinary flow: winnow, commit some of it, winnow again with
    a still-dirty tree, and the committed file's live P1s came back as "no
    longer true". They go to `out_of_scope` instead, which says the true
    thing: not looked at this time. Pass None to skip the distinction.
    """
    prior = load_report(prior_path, "--since")
    if prior is None:
        return None, [], []

    prior_findings = usable_entries(prior.get("findings", []), "--since",
                                    ECHO_FIELDS)
    if (prior_findings and isinstance(prior_findings[0], dict)
            and "anchor" not in prior_findings[0]):
        warn(f"--since: {prior_path} predates anchored keys - "
             "reconciliation may be approximate")
    prior_keys = {}
    for f in prior_findings:
        prior_keys.setdefault(finding_key(f), []).append(f)
    now_counts = defaultdict(int)
    for f in findings:
        key = finding_key(f)
        now_counts[key] += 1
        f["status"] = "persisting" if key in prior_keys else "new"

    resolved, out_of_scope = [], []
    for key, group in prior_keys.items():
        gone = len(group) - now_counts.get(key, 0)
        for f in group[:max(0, gone)]:
            if scanned_paths is not None and f["path"] not in scanned_paths:
                f["status"] = "out-of-scope"
                out_of_scope.append(f)
            else:
                f["status"] = "resolved"
                resolved.append(f)
    return prior.get("generated"), resolved, out_of_scope


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def scan_file(path, findings, max_bytes=DEFAULT_MAX_BYTES):
    """Number of lines reviewed, or None if the file was never read."""
    reason = skip_path(path, max_bytes)
    if reason:
        READ_ERRORS.append({"path": path, "error": "skipped: " + reason})
        return None
    lines = read_lines(path)
    if lines is None:
        return None
    # Snapshot for number_anchor_matches: re-reading there could see different
    # bytes if the tree moved mid-scan.
    FILE_LINES[path] = lines
    # Recorded here rather than from the scope map, so it means "opened and
    # read" rather than "intended to read". `reconcile` uses it to tell a
    # finding that is gone from one whose file was never looked at.
    SCANNED_PATHS.add(path)
    ext = os.path.splitext(path)[1].lower()
    check_universal(path, lines, findings)
    if ext not in PY_EXT:
        # Python has its own AST-based pass inside check_python; every other
        # language goes through the generic one, including the ones with no
        # language rules of their own. A JS or Go test file gets the
        # redundancy pass even though nothing else here understands JS or Go.
        check_generic_tests(path, lines, findings)
    if ext in PY_EXT:
        check_python(path, lines, findings)
    elif ext in CS_EXT:
        check_csharp(path, lines, findings)
        check_bindings(path, lines, findings,
                       "Inspector/API surface, confirm before removing")
    elif ext in CPP_EXT:
        check_cpp(path, lines, findings)
        check_bindings(path, lines, findings,
                       "Blueprint/API surface, confirm before removing")
    # Separate chain, and `if` rather than `elif` for all three: a .vue or
    # .svelte file is JavaScript, HTML and CSS at once, and an elif would
    # review a third of it. `check_bindings` is deliberately not called here -
    # it counts tokens against C#/C++ declaration syntax, and there is no
    # parser in this file that can tell a JS binding from a property name.
    if ext in JS_EXT:
        check_js(path, lines, findings)
    if ext in HTML_EXT:
        check_html(path, lines, findings)
    if ext in CSS_EXT:
        check_css(path, lines, findings)
    return len(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paths", nargs="*", help="scan whole files instead of a diff")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-severity", choices=["P1", "P2", "P3"], default="P3")
    ap.add_argument("--scope", choices=["auto", "worktree", "staged",
                                        "unstaged", "branch"], default="auto",
                    help="auto: all uncommitted work (staged + unstaged + "
                         "untracked), falling back to the branch diff")
    ap.add_argument("--base", help="base ref for --scope branch")
    ap.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--whole-files", "--all-scope", dest="whole_files",
                    action="store_true",
                    help="report findings on untouched lines OF THE FILES THIS "
                         "DIFF TOUCHES, marked pre-existing. This is not a "
                         "repo-wide scan and there isn't one - to audit other "
                         "files, name them with --paths.")
    ap.add_argument("--report-name", action="store_true",
                    help="print the canonical report filename stem and exit")
    ap.add_argument("--stem", help="use this report stem verbatim, so the "
                                   "filename and the JSON agree across calls")
    ap.add_argument("--since", metavar="PRIOR.json",
                    help="reconcile against a previous run's JSON: mark findings "
                         "new/persisting and list ones no longer true")
    ap.add_argument("--declined", metavar="DECLINED.json",
                    help="a report-shaped JSON of findings the user already "
                         "rejected; matches move to 'declined' and out of the "
                         "live list instead of resurfacing every run")
    ap.add_argument("--meta", metavar="ROUND_DIR",
                    help="print this round's meta.json - what was compared to "
                         "what - and exit. Takes the round directory, because "
                         "it derives `round` from the name and scans sibling "
                         "round-*/meta.json for `prior_round`.")
    ap.add_argument("--feature", metavar="TEXT",
                    help="the user's feature phrase, recorded verbatim in "
                         "meta.json; omit when no feature was named")
    args = ap.parse_args()

    if args.report_name:
        # --json has to stay JSON on every path, including this one. Printing
        # a bare stem meant the one caller that pins the stem across calls got
        # a parse error the moment it also asked for --json.
        def emit_stem(stem):
            if args.json:
                print(json.dumps({"report_stem": stem,
                                  "warnings": WARNINGS}, indent=2))
            else:
                print(stem)

        if args.paths:
            emit_stem(report_stem("files"))
            return 0
        _, target, _added = resolve_diff(args.scope, args.base)
        if target is None:
            # Step 2 pins the stem before anything else runs, so a refusal has
            # to surface here too - with its own message and its own exit
            # code. Reported as an empty scope it reads as a clean tree at the
            # one point in the run that decides whether to continue.
            refused = bool(REFUSALS)
            msg = (" ".join(REFUSALS) if refused else
                   "No diff found - cannot name a report for an empty scope.")
            if args.json:
                print(json.dumps({"report_stem": None,
                                  "warnings": WARNINGS + [msg]}, indent=2))
                return 2 if refused else 1
            for w in WARNINGS:
                print("warning: " + w, file=sys.stderr)
            print(msg, file=sys.stderr)
            return 2 if refused else 1
        emit_stem(report_stem(target))
        return 0

    if args.meta:
        # Relative to the git toplevel, never the cwd - every other path the
        # scanner opens goes through abs_path for the same reason. Resolved
        # against a subdirectory instead, the sibling scan finds no rounds at
        # all, `prior_round` comes back null, and the report says "Previous
        # run: none" for a repo that has one. Nothing about that is visible in
        # the output.
        round_dir = args.meta if os.path.isabs(args.meta) else abs_path(args.meta)
        generated = datetime.datetime.now()
        if args.paths:
            label, target = "named files", "files"
        else:
            label, target, _added = resolve_diff(args.scope, args.base)
            if target is None:
                # Same shape as --report-name's empty-scope path: a refusal is
                # a question for the user, not a flag to retry differently.
                refused = bool(REFUSALS)
                msg = (" ".join(REFUSALS) if refused else
                       "No diff found - cannot describe an empty scope.")
                print(json.dumps({"round": round_number(round_dir),
                                  "scope": None,
                                  "warnings": WARNINGS + [msg]}, indent=2))
                return 2 if refused else 1
        flag = f"--scope {args.scope}"
        if args.base:
            flag += f" --base {args.base}"
        stem = args.stem or report_stem(target, generated)
        print(json.dumps(meta_document(round_dir, label, target, stem,
                                       generated, flag, args.feature),
                         indent=2))
        return 0

    findings = []
    # In-scope-and-true findings this report will not print, kept only so that
    # `--since` can see they are still true. Never emitted.
    filtered_preexisting = []
    in_scope_files = 0
    scanned_files = 0
    added_lines = 0
    if args.paths:
        target = "files"
        label = f"{len(args.paths)} named file(s), full contents"
        root = repo_root()
        for p in args.paths:
            rel = p
            if root and os.path.isabs(p):
                rel = os.path.relpath(p, root)
            elif root:
                rel = os.path.relpath(os.path.abspath(p), root)
            in_scope_files += 1
            n = scan_file(rel, findings, args.max_file_bytes)
            if n is not None:
                scanned_files += 1
                added_lines += n  # whole files, so every line is in scope
        for f in findings:
            f["preexisting"] = False
    else:
        label, target, added_map = resolve_diff(args.scope, args.base)
        if not added_map:
            # A refusal is not an empty scope. It has its own message, and it
            # must not be reported as a clean tree in either format.
            if REFUSALS:
                msg = " ".join(REFUSALS)
            else:
                msg = ("No diff found in scope '%s'. Pass --paths to scan "
                       "files directly, or --base <ref> to name a base branch."
                       % args.scope)
                # An empty scope that is empty *because everything in it was
                # skipped* is not a clean tree, and must not print like one.
                if READ_ERRORS:
                    msg += (f" {len(READ_ERRORS)} changed file(s) were skipped "
                            "as vendored, generated, oversized or unreadable - "
                            "see 'errors'. Nothing was reviewed.")
            # An empty scope still has to answer in the requested format.
            # Printing prose on stdout under --json made every consumer that
            # parses this - including the judgment pass - crash on a clean
            # branch instead of reading zero findings.
            if args.json:
                print(json.dumps({
                    "scope": label or f"empty ({args.scope})",
                    "generated": datetime.datetime.now().isoformat(
                        timespec="seconds"),
                    "report_stem": args.stem or report_stem(target or "worktree"),
                    "prior_report": None,
                    "files": 0, "scanned_files": 0, "added_lines": 0,
                    "findings": [], "resolved": [], "out_of_scope": [],
                    "declined": [],
                    "errors": READ_ERRORS, "warnings": WARNINGS + [msg],
                    "complete": not READ_ERRORS and not REFUSALS,
                }, indent=2))
                return 2 if (READ_ERRORS or REFUSALS) else 0
            for w in WARNINGS:
                print("warning: " + w, file=sys.stderr)
            print(msg, file=sys.stderr if REFUSALS else sys.stdout)
            for e in READ_ERRORS:
                print(f"  {e['path']}: {e['error']}", file=sys.stderr)
            return 2 if (READ_ERRORS or REFUSALS) else 0
        added_lines = sum(len(v) for v in added_map.values())
        for p in added_map:
            in_scope_files += 1
            if scan_file(p, findings, args.max_file_bytes) is not None:
                scanned_files += 1
        kept = []
        for f in findings:
            f["preexisting"] = not touches_change(
                f, added_map.get(f["path"], set()),
                REMOVED_AT.get(f["path"], set()))
            if not f["preexisting"] or args.whole_files:
                kept.append(f)
            else:
                # Held, not discarded. It is out of this report's scope but it
                # is still TRUE, and reconciliation counts truth - see the
                # `--since` call below.
                filtered_preexisting.append(f)
        findings = kept

    # Reconcile the FULL set, then filter. Reconciling the filtered set meant
    # raising --min-severity between runs reported every finding the filter
    # dropped as "no longer true" - which reads as "fixed" and tells the
    # reviewer to strike a live item off the list.
    #
    # "Full" means every filter, and the preexisting one above is the other
    # one. It runs earlier than this comment does because it is what decides
    # what a *report* contains - but it had the identical defect: a run with
    # --whole-files writes a baseline holding untouched-line findings, the next
    # ordinary run drops them here, and every one came back `resolved`. Step 4
    # of SKILL.md writes exactly that baseline as `<stem>-preexisting.json`, so
    # this was not a hypothetical ordering. Absent-because-out-of-scope and
    # absent-because-fixed are different facts and only one of them is news.
    generated = datetime.datetime.now()
    stem = args.stem or report_stem(target, generated)
    number_occurrences(findings)
    number_anchor_matches(findings)
    declined = []
    if args.declined:
        findings, declined = split_declined(findings, args.declined)
    prior_when, resolved, out_of_scope = None, [], []
    if args.since:
        # Reconcile against live AND declined. A declined finding is still
        # true - the user just does not want to hear about it - so counting
        # only the live ones reported it as "no longer true", which reads as
        # fixed. Declined and resolved are opposite claims about the same
        # line and it must never make both.
        #
        # `scanned_paths` is every file this run actually opened. A prior
        # finding in a file that is not in it was not examined, so it cannot
        # be called fixed - see `reconcile`.
        prior_when, resolved, out_of_scope = reconcile(
            findings + declined + filtered_preexisting, args.since,
            scanned_paths=set(SCANNED_PATHS))
        for f in declined:
            f["status"] = "declined"  # reconcile restamps everything it counts

    cutoff = SEVERITY_ORDER[args.min_severity]
    findings = [f for f in findings if SEVERITY_ORDER[f["severity"]] <= cutoff]
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["path"], f["line"]))
    resolved = [f for f in resolved
                if SEVERITY_ORDER.get(f.get("severity"), 0) <= cutoff]
    out_of_scope = [f for f in out_of_scope
                    if SEVERITY_ORDER.get(f.get("severity"), 0) <= cutoff]
    declined = [f for f in declined if SEVERITY_ORDER[f["severity"]] <= cutoff]

    # A read failure is a hole in the scan, not a detail. Say so in both modes.
    unreadable = [e for e in READ_ERRORS if not e["error"].startswith("skipped")]
    if unreadable:
        warn(f"{len(unreadable)} file(s) in scope could not be read - "
             "the scan is incomplete, see 'errors'")
    # Every file skipped is not a clean branch; it is a scan that reviewed
    # nothing. Left alone it prints the same 0-candidates/complete/exit-0
    # shape as a genuinely clean diff.
    reviewed_nothing = bool(in_scope_files) and not scanned_files
    if reviewed_nothing:
        warn(f"all {in_scope_files} file(s) in scope were skipped or "
             "unreadable - nothing was reviewed, see 'errors'")
    complete = not unreadable and not reviewed_nothing
    exit_code = 0 if complete else 2

    if args.json:
        print(json.dumps({
            "scope": label,
            "generated": generated.isoformat(timespec="seconds"),
            "report_stem": stem,
            "prior_report": {"path": args.since, "generated": prior_when}
                            if args.since else None,
            "files": in_scope_files,
            "scanned_files": scanned_files,
            "added_lines": added_lines,
            "findings": findings,
            "resolved": resolved,
            "out_of_scope": out_of_scope,
            "declined": declined,
            "errors": READ_ERRORS,
            "warnings": WARNINGS,
            "complete": complete,
        }, indent=2))
        return exit_code

    in_scope = [f for f in findings if not f["preexisting"]]
    preexisting = [f for f in findings if f["preexisting"]]
    for f in resolved:
        f.setdefault("preexisting", False)

    print(f"Scope: {label}")
    print(f"Generated: {generated.strftime('%Y-%m-%d %H:%M')}")
    print(f"Report stem: {stem}")
    print(f"Files: {in_scope_files} in scope, {scanned_files} reviewed; "
          f"added lines: {added_lines}")
    print(f"{len(in_scope)} candidate(s) in scope. "
          "These are candidates, not verdicts.\n")

    def dump(group):
        by_file = defaultdict(list)
        for f in group:
            by_file[f["path"]].append(f)
        for path in sorted(by_file):
            print(path)
            for f in by_file[path]:
                print(f"  {f['severity']}  {f['line']:>5}  "
                      f"{f['rule']:<24} {f['message']}")
            print()

    dump(in_scope)
    if resolved:
        print(f"--- no longer true since {prior_when or args.since} "
              f"({len(resolved)}) ---")
        print("Fixed or overtaken by events. Do not re-report as live.\n")
        dump(resolved)
    if out_of_scope:
        print(f"--- in the prior report, NOT looked at this run "
              f"({len(out_of_scope)}) ---")
        print("Their files were not in this run's scope, so nothing was "
              "learned about them. NOT fixed - unexamined.\n")
        dump(out_of_scope)
    if declined:
        print(f"--- previously declined ({len(declined)}) ---")
        print("Raised before and rejected. Noted once, not re-argued.\n")
        dump(declined)
    if preexisting:
        print(f"--- pre-existing, in files this change touches "
              f"({len(preexisting)}) ---")
        print("Incidental to the diff, not an audit. Two sentences each, "
              "top few only. Do not fix.\n")
        dump(preexisting)

    if READ_ERRORS:
        print(f"--- not scanned ({len(READ_ERRORS)}) ---", file=sys.stderr)
        for e in READ_ERRORS:
            print(f"  {e['path']}: {e['error']}", file=sys.stderr)
    for w in WARNINGS:
        print("warning: " + w, file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        os._exit(0)  # piping into head/less is not an error
