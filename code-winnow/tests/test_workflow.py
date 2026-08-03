"""End-to-end test of the workflow SKILL.md documents.

`test_scan.py` tests the scanner. Nothing tested the *document*, and the
document is where most of the skill lives: ~20 shell and Python snippets that
look like code, are formatted like code, and had never been executed. Reading
them is not a substitute - an unquoted `WINNOW=C:\\Users\\...` assignment, a
`command -v python3` that resolves the Microsoft Store stub, and a shell
function that cannot survive a call boundary all read perfectly.

Two properties make this a real guard rather than a copy that drifts:

**The snippets are extracted from SKILL.md, never duplicated here.** A copy
agrees with itself forever; extraction means every block in the document is an
executed artifact and stays that way as the document changes.

**Each block runs in its own `bash` process.** The harness that hosts this
skill does not preserve shell state between tool calls, and every snippet in
SKILL.md is its own call. Running them in one shell would pass while the real
sequence fails - which is exactly how four defects shipped.

What this cannot cover: Steps 3, 3.5 and 4 are agent judgment - three prompts,
the conflict arbitration, the report. This covers the mechanical spine only:
Step 0, 1, 2, the review-input builder, 5a and 6.
"""

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WINNOW = os.path.dirname(HERE)
SKILL_MD = os.path.join(WINNOW, "SKILL.md")


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def _bash_blocks():
    """[(line_no, section_heading, body)] for every ```bash block."""
    text = open(SKILL_MD, encoding="utf-8").read()
    heads = {}
    for i, line in enumerate(text.split("\n"), 1):
        m = re.match(r"^#{2,4} (.+)$", line)
        if m:
            heads[i] = m.group(1)

    def section_of(ln):
        best = ""
        for h, name in heads.items():
            if h < ln:
                best = name
        return best

    out = []
    for m in re.finditer(r"```bash\n(.*?)```", text, re.S):
        ln = text[: m.start()].count("\n") + 1
        out.append((ln, section_of(ln), m.group(1)))
    return out


# Each entry: a unique substring identifying the block, and the step it plays.
# Order is execution order. A block whose marker is not found fails loudly
# rather than silently testing nothing.
SPINE = [
    ("step0", "EXCLUSION FAILED"),
    ("step1", "# QUOTE IT"),
    ("step2", "rm -f .code-winnow/env.sh"),
    ("step3", "Ask the scanner what it actually reviewed"),
    ("step5a", "REFUSING: fix items appear after"),
    ("step6", '--since ".code-winnow/$STEM.json" $DECLINED'),
]


def _find_block(marker):
    hits = [b for b in _bash_blocks() if marker in b[2]]
    assert hits, f"no ```bash block in SKILL.md contains {marker!r}"
    assert len(hits) == 1, f"{marker!r} matches {len(hits)} blocks: {[h[0] for h in hits]}"
    return hits[0]


def bash_path():
    """Discover a bash that can actually drive git in this working tree.

    `shutil.which("bash")` on Windows finds WSL's system32\\bash.exe, which
    cannot resolve a Windows path - the same 'present on PATH' vs 'works'
    trap that made the skill's own interpreter probe pick the Microsoft Store
    stub. Probe the candidate instead of trusting the lookup.
    """
    pf = os.environ.get("PROGRAMFILES", "")
    candidates = [
        os.path.join(pf, "Git", "bin", "bash.exe") if pf else None,
        "/bin/bash", "/usr/bin/bash",
        shutil.which("bash"),
    ]
    for c in candidates:
        if not c or not (os.path.isfile(c) or shutil.which(c)):
            continue
        probe = subprocess.run(
            [c, "-c", 'cd "$(git rev-parse --show-toplevel)" && pwd'],
            cwd=WINNOW, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        if probe.returncode == 0 and probe.stdout.strip():
            return c
    return None


BASH = bash_path()
requires_bash = pytest.mark.skipif(not BASH, reason="no bash available")


def _bash_py():
    """The interpreter, as a path bash can execute."""
    p = sys.executable.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", p):          # C:/x -> /c/x for Git Bash
        p = "/" + p[0].lower() + p[2:]
    return p


def run_block(body, cwd, subs=None):
    """Run one extracted block in its OWN shell - no state carried in.

    PY is pre-set, exactly as SKILL.md's Step 1 allows ("Already know the
    path? Set PY first"). This machine has no python on PATH at all - only an
    absolute-path install - which is precisely the case that option exists for.
    """
    for a, b in (subs or {}).items():
        body = body.replace(a, b)
    body = f'PY={_bash_py()}\n' + body
    # encoding pinned: `text=True` decodes through the locale codec, so on a
    # GBK/cp1252 machine any non-ASCII byte in git's output raises instead of
    # testing anything. test_scan.py:50 learned this once already.
    proc = subprocess.run([BASH, "-c", body], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return proc


# --------------------------------------------------------------------------
# the guard that stops new snippets escaping the harness
# --------------------------------------------------------------------------

def test_every_bash_block_is_run_or_explicitly_marked_illustrative():
    """A block that is neither exercised nor labelled is how an untested
    snippet enters the document. Adding one must break this test."""
    spine_markers = [m for _, m in SPINE]
    unaccounted = []
    for ln, section, body in _bash_blocks():
        if any(m in body for m in spine_markers):
            continue
        if re.search(r"^\s*#\s*(illustration|flag reference|pattern)", body, re.I | re.M):
            continue
        unaccounted.append(f"SKILL.md:{ln} ({section}): {body.splitlines()[0][:60]}")
    assert not unaccounted, (
        "bash blocks neither run by the harness nor marked illustrative:\n  "
        + "\n  ".join(unaccounted)
        + "\n\nAdd the block to SPINE, or give it a first-line comment "
          "'# illustration only - not run by the harness'.")


# --------------------------------------------------------------------------
# the end-to-end run
# --------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path):
    """A scratch repo with real chaff in an uncommitted change."""
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, check=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "init")
    # Uncommitted work, with something the scanner will find.
    (tmp_path / "feature.py").write_text(
        "def load():\n"
        "    try:\n"
        "        go()\n"
        "    except Exception:\n"
        "        pass\n",
        encoding="utf-8")
    return tmp_path


@requires_bash
def test_step0_creates_and_excludes_the_workspace(repo):
    _, _, body = _find_block("EXCLUSION FAILED")
    p = run_block(body, str(repo))
    assert "workspace excluded" in p.stdout, p.stdout + p.stderr
    assert (repo / ".code-winnow").is_dir(), \
        "Step 0 must create .code-winnow/ - nothing else does, and the first " \
        "redirect into it fails with 'No such file or directory'"


@requires_bash
def test_step0_preserves_an_exclude_file_with_no_trailing_newline(repo):
    (repo / ".git" / "info").mkdir(parents=True, exist_ok=True)
    (repo / ".git" / "info" / "exclude").write_bytes(b"build/")   # no newline
    _, _, body = _find_block("EXCLUSION FAILED")
    run_block(body, str(repo))
    (repo / "build").mkdir(exist_ok=True)
    (repo / "build" / "o.tmp").write_text("x", encoding="utf-8")
    still = subprocess.run(["git", "check-ignore", "-q", "build/"],
                           cwd=repo, capture_output=True)
    assert still.returncode == 0, "the user's build/ rule was destroyed"


@requires_bash
def test_step1_and_step2_run_in_separate_shells_and_produce_a_stem(repo):
    """The defect this exists for: Step 2 used $PY/$WINNOW/$SCOPE that Step 1
    set in a *different* tool call, so the run aborted and reported the repo
    clean. Running these in one shell hides it completely."""
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo))
    subs = {"<absolute path to this skill's directory>": WINNOW}

    p1 = run_block(_find_block("# QUOTE IT")[2], str(repo), subs)
    assert p1.returncode == 0, f"Step 1 failed:\n{p1.stdout}\n{p1.stderr}"

    p2 = run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo), subs)
    assert "nothing to review" not in p2.stdout, (
        "Step 2 reported an empty scope on a repo with real changes - "
        "almost certainly $PY/$WINNOW did not survive from Step 1\n"
        + p2.stdout + p2.stderr)
    assert p2.returncode == 0, f"Step 2 failed:\n{p2.stdout}\n{p2.stderr}"

    env = repo / ".code-winnow" / "env.sh"
    assert env.is_file(), "Step 2 must write .code-winnow/env.sh"
    body = env.read_text(encoding="utf-8")
    for key in ("WINNOW=", "PY=", "STEM=", "BACKUP=", "SNAPSHOT="):
        assert key in body, f"env.sh is missing {key}"


@requires_bash
def test_env_sh_actually_restores_state_in_a_fresh_shell(repo):
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo))
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("# QUOTE IT")[2], str(repo), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo), subs)

    probe = run_block(
        '. .code-winnow/env.sh\n'
        '[ -n "$STEM" ] || { echo "STEM EMPTY"; exit 1; }\n'
        '[ -x "$PY" ] || command -v "$PY" >/dev/null || { echo "PY BROKEN"; exit 1; }\n'
        '"$PY" -c "print(\'interpreter ok\')"\n', str(repo))
    assert "interpreter ok" in probe.stdout, (
        "sourcing env.sh did not yield a working interpreter\n"
        + probe.stdout + probe.stderr)


@requires_bash
def test_the_snapshot_function_survives_the_call_boundary(repo):
    """SNAPSHOT is compared in later blocks and by dispatched agents. If
    snapshot() is only defined in Step 2's block it is gone by then, and the
    check silently passes (both sides empty) or fires unconditionally."""
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo))
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("# QUOTE IT")[2], str(repo), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo), subs)

    same = run_block(
        '. .code-winnow/env.sh\n'
        'type snapshot >/dev/null 2>&1 || { echo "SNAPSHOT FN MISSING"; exit 1; }\n'
        '[ "$(snapshot)" = "$SNAPSHOT" ] && echo FRESH || echo STALE\n', str(repo))
    assert "SNAPSHOT FN MISSING" not in same.stdout, \
        "snapshot() must be written into env.sh, not just defined in Step 2"
    assert "FRESH" in same.stdout, \
        f"clean tree reported stale:\n{same.stdout}{same.stderr}"

    (repo / "feature.py").write_text("def load():\n    pass\n", encoding="utf-8")
    moved = run_block(
        '. .code-winnow/env.sh\n'
        '[ "$(snapshot)" = "$SNAPSHOT" ] && echo FRESH || echo STALE\n', str(repo))
    assert "STALE" in moved.stdout, \
        "an edit to a file in scope must change the snapshot"


@requires_bash
def test_review_input_is_never_empty_when_the_scanner_found_files(repo):
    """The builder ran `git diff HEAD`, which is empty when --scope auto falls
    back to the branch diff - so all three judgment agents got zero bytes and
    reported nothing while the scanner held a P1."""
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo))
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("# QUOTE IT")[2], str(repo), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo), subs)

    p = run_block(_find_block("Ask the scanner what it actually reviewed")[2], str(repo))
    assert p.returncode == 0, f"input builder refused:\n{p.stdout}{p.stderr}"
    diffs = list((repo / ".code-winnow").glob("*.input.diff"))
    assert diffs, "no input.diff written"
    assert diffs[0].stat().st_size > 0, "review input is empty"


@requires_bash
def test_review_input_on_a_clean_tree_branch_review(tmp_path):
    """The auto->branch fallback: clean tree, one commit ahead. This is the
    shape that produced 0 bytes."""
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, check=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "init")
    git("checkout", "-qb", "feat")
    (tmp_path / "feature.py").write_text(
        "def load():\n    try:\n        go()\n    except Exception:\n        pass\n",
        encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "work")

    run_block(_find_block("EXCLUSION FAILED")[2], str(tmp_path))
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("# QUOTE IT")[2], str(tmp_path), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(tmp_path), subs)
    run_block(_find_block("Ask the scanner what it actually reviewed")[2], str(tmp_path))

    diffs = list((tmp_path / ".code-winnow").glob("*.input.diff"))
    assert diffs and diffs[0].stat().st_size > 0, (
        "clean-tree branch review produced an empty review input - the agents "
        "would report nothing while the scanner holds findings")


# --------------------------------------------------------------------------
# Step 5a's refusals
# --------------------------------------------------------------------------

def _bootstrap(path):
    """Run Steps 0-2 in separate shells and return the pinned $STEM."""
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("EXCLUSION FAILED")[2], str(path))
    run_block(_find_block("# QUOTE IT")[2], str(path), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(path), subs)
    got = run_block('. .code-winnow/env.sh; printf %s "$STEM"', str(path))
    stem = got.stdout.strip()
    assert stem, f"bootstrap yielded no STEM:\n{got.stdout}{got.stderr}"
    return stem


PLAN_BODY = """Skill:    {winnow}
Backup:   .code-winnow/{stem}.pre-fix/

## Code fixes - approved

- [ ] P1 bare except swallows the loader error
      file:       feature.py
      line:       4
      occurrence: 1 of 1
      anchor:     except Exception:
      fix:        narrow to the exception load() can actually raise
      evidence:   rewrite, nothing removed

## Never touch

- Any file not named by a `file:` line above
"""


def _write_plan(repo, stem, status_line):
    """A minimal well-formed plan; `status_line` None omits the line entirely."""
    head = f"# Fix plan - {stem}\n"
    if status_line is not None:
        head += status_line + "\n"
    p = repo / ".code-winnow" / f"{stem}.fixplan.md"
    p.write_text(head + PLAN_BODY.format(winnow=WINNOW, stem=stem),
                 encoding="utf-8")
    return p


def _run_step5a(repo):
    return run_block(_find_block("REFUSING: fix items appear after")[2], str(repo))


@requires_bash
def test_step5a_backs_up_an_approved_plan(repo):
    """The positive case, so the refusal tests below are not vacuously green
    against a script that refuses everything."""
    stem = _bootstrap(repo)
    _write_plan(repo, stem, "Status:   APPROVED by the user on 2026-08-02")
    p = _run_step5a(repo)
    out = p.stdout + p.stderr
    assert "REFUSING" not in out, out
    assert "backed up 1 file(s)" in p.stdout, out
    assert (repo / ".code-winnow" / f"{stem}.pre-fix" / "feature.py").is_file()


@requires_bash
@pytest.mark.parametrize("status, why", [
    ("Status:   UNAPPROVED - no human reviewed these findings",
     "an unattended run's own marker"),
    (None,
     "no Status line at all - a truncated write or a hand-rolled plan"),
    ("Status:   NOT APPROVED",
     "a negation that still starts with a word containing APPROVED"),
    ("Status:   pending review",
     "anything that is not approval"),
])
def test_step5a_refuses_a_plan_that_is_not_approved(repo, status, why):
    """Fail closed. The approval gate used to be one sentence in the cold-entry
    path asking the executor to stop on UNAPPROVED, which waved through every
    plan carrying no Status line - so the marked case was refused and the
    unmarked case was not, exactly backwards."""
    stem = _bootstrap(repo)
    _write_plan(repo, stem, status)
    p = _run_step5a(repo)
    out = p.stdout + p.stderr
    assert "REFUSING" in out, f"applied a plan with {why}:\n{out}"
    assert not (repo / ".code-winnow" / f"{stem}.pre-fix").exists(), \
        "refused, but still made a backup - the refusal came too late"


@requires_bash
def test_baseline_json_exists_before_step_3_needs_it(repo):
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo))
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("# QUOTE IT")[2], str(repo), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo), subs)

    # Ask the shell, don't parse the file: %q quoting is not always single-quoted.
    got = run_block('. .code-winnow/env.sh; printf %s "$STEM"', str(repo))
    stem = got.stdout.strip()
    assert stem, f"env.sh yielded no STEM:\n{got.stdout}{got.stderr}"
    baseline = repo / ".code-winnow" / f"{stem}.json"
    assert baseline.is_file(), "Step 2 must write the baseline JSON"
    data = json.loads(baseline.read_text(encoding="utf-8"))
    assert data["findings"], "baseline holds no findings for a repo with chaff"
