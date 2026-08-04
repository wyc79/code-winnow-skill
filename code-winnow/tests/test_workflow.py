"""End-to-end test of the workflow SKILL.md documents.

`test_scan.py` tests the scanner. Nothing tested the *document*, and the
document is where most of the skill lives: ~14 shell snippets that look like
code, are formatted like code, and had never been executed. Reading them is not
a substitute - an unquoted `WINNOW=C:\\Users\\...` assignment, a
`command -v python3` that resolves the Microsoft Store stub, and a shell
function that cannot survive a call boundary all read perfectly.

Step 5a used to be 70 lines of Python inlined in a heredoc here; it now lives in
`scripts/backup.py`, and SKILL.md invokes it. That is a directly-testable script
rather than a snippet an agent retypes, but the guards are the same guards, so
the tests below still drive it through the extracted bash block - the invocation
is part of the documented workflow and can break independently of the script.

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
Step 0, 1, 2, the review-input builder, Step 4's baseline reconciliation, 5a
and 6.
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
REPORT_FORMAT = os.path.join(WINNOW, "references", "report-format.md")
BACKUP_PY = os.path.join(WINNOW, "scripts", "backup.py")

# Step 0 copies the root scaffold, so its block needs $WINNOW like every other
# block does. One constant beats the same dict at fifteen call sites.
WINNOW_SUBS = {"<absolute path to this skill's directory>": WINNOW}


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
    ("step4", "PRIOR=$("),
    ("step4-index", 'sed "s|ROUND|'),
    ("step5a", "scripts/backup.py"),
    ("step6", '--since "$ROUND/scan.json" $DECLINED'),
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
        if not c or not os.path.isfile(c):
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
    # testing anything. test_scan.py's `write` helper learned this once already.
    proc = subprocess.run([BASH, "-c", body], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return proc


# --------------------------------------------------------------------------
# the guard that stops new snippets escaping the harness
# --------------------------------------------------------------------------

def test_every_bash_block_is_run_or_explicitly_marked_illustrative():
    """A block that is neither exercised nor labelled is how an untested
    snippet enters the document. Adding one must break this test."""
    unaccounted = []
    for ln, section, body in _bash_blocks():
        if any(m in body for _, m in SPINE):
            continue
        if re.search(r"^\s*#\s*(illustration|flag reference|pattern)", body, re.I | re.M):
            continue
        unaccounted.append(f"SKILL.md:{ln} ({section}): {body.splitlines()[0][:60]}")
    assert not unaccounted, (
        "bash blocks neither run by the harness nor marked illustrative:\n  "
        + "\n  ".join(unaccounted)
        + "\n\nAdd the block to SPINE (steps covered: "
        + ", ".join(name for name, _ in SPINE)
        + "), or give it a first-line comment "
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
    p = run_block(body, str(repo), WINNOW_SUBS)
    assert "workspace excluded" in p.stdout, p.stdout + p.stderr
    assert (repo / ".code-winnow").is_dir(), \
        "Step 0 must create .code-winnow/ - nothing else does, and the first " \
        "redirect into it fails with 'No such file or directory'"


@requires_bash
def test_step0_preserves_an_exclude_file_with_no_trailing_newline(repo):
    (repo / ".git" / "info").mkdir(parents=True, exist_ok=True)
    (repo / ".git" / "info" / "exclude").write_bytes(b"build/")   # no newline
    _, _, body = _find_block("EXCLUSION FAILED")
    run_block(body, str(repo), WINNOW_SUBS)
    # No `build/` directory is created: check-ignore matches on pathname and
    # does not require the path to exist, so creating it changed nothing.
    still = subprocess.run(["git", "check-ignore", "-q", "build/"],
                           cwd=repo, capture_output=True)
    assert still.returncode == 0, "the user's build/ rule was destroyed"


@requires_bash
def test_step1_and_step2_run_in_separate_shells_and_produce_a_stem(repo):
    """The defect this exists for: Step 2 used $PY/$WINNOW/$SCOPE that Step 1
    set in a *different* tool call, so the run aborted and reported the repo
    clean. Running these in one shell hides it completely."""
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
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
def test_step2_surfaces_a_refusal_instead_of_the_empty_scope_advice(repo):
    """A refusal yields no stem, so the no-stem guard used to fire and print
    over it - three causes, none of them 'the scanner refused', led by 'pass
    --base <ref>'. Step 1 says in so many words not to retry with another flag
    to get past a refusal, and the guard was recommending exactly that, at
    exit 0. The refusal has to reach the agent intact and the run has to stop.
    """
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
    subs = {"<absolute path to this skill's directory>": WINNOW,
            'SCOPE=""': 'SCOPE="--scope staged"'}
    # Stage a file, then edit it again: the one case the scanner refuses.
    (repo / "staged.py").write_text("def f():\n    d = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "staged.py"], cwd=repo, capture_output=True)
    (repo / "staged.py").write_text("def f():\n    d = 1\n# edited after\n",
                                    encoding="utf-8")

    p = run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo), subs)
    both = p.stdout + p.stderr
    assert "REFUSING:" in both, "the refusal was swallowed:\n" + both
    assert p.returncode != 0, "a refusal must stop the run, not exit 0"
    assert "pass --base <ref> to name" not in p.stdout, (
        "the no-stem guard printed its empty-scope advice over a refusal, "
        "pointing the agent at the retry Step 1 forbids:\n" + both)


@requires_bash
def test_review_input_never_contains_an_untracked_binary(repo):
    """`cat` on every untracked file put a 230 KB PNG into the review input:
    not valid UTF-8, and the `-s` guard passed because the file was large.
    New art, prefabs and .meta files are the normal content of a Unity or UE5
    change, so this is the default case, not an edge one. Excluded paths must
    still be NAMED - an omission the agent cannot see is the same silent-
    coverage failure the scanner's `errors` array exists to prevent."""
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("# QUOTE IT")[2], str(repo), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo), subs)

    art = repo / "Assets" / "Art"
    art.mkdir(parents=True)
    (art / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 900)
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "dep.js").write_text("module.exports=1\n",
                                                  encoding="utf-8")

    p = run_block(_find_block("Ask the scanner what it actually reviewed")[2],
                  str(repo))
    assert p.returncode == 0, p.stdout + p.stderr
    raw = next((repo / ".code-winnow").glob(
        "round-*/input.diff")).read_bytes()
    assert b"\x00" not in raw, "the review input carries NUL bytes"
    raw.decode("utf-8")           # must not raise
    text = raw.decode("utf-8")
    assert "icon.png" in text, "an excluded file must still be named"
    assert "not shown" in text
    assert "dep.js" in text and "vendored" in text


@requires_bash
def test_step5a_refuses_a_backup_path_pasted_from_the_plan_header(repo, tmp_path):
    """`Backup:` once ended in a `(NOT YET MADE)` marker. Copied into $BACKUP
    it made a real directory of that name nested inside the intended one, the
    script printed its usual success count, the non-empty refusal never fired
    because the intended path was still empty, and `Undo:` restored nothing.

    It asserts WHICH gate refused. backup.py now has two destination checks -
    the parenthetical one and the sibling one - and a poisoned path trips
    both, so `REFUSING:` alone stays green with the parenthetical check
    deleted. The mutation harness caught exactly that. The same lesson as
    test_step5a_refuses_the_notes_document_on_its_status_line: layered gates
    are the right design, a test that cannot say which one fired is not.

    A real $ROUND matters for the same reason. With it unset the block asks
    backup.py for `/fixplan.md`, which does not exist, and the refusal is
    "no fix plan" - a pass that proves nothing about the header at all.
    """
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    rd = repo / ".code-winnow" / "round-01"
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "fixplan.md").write_text(
        "# Fix plan\n\nStatus:   APPROVED by the user on 2026-08-03\n\n"
        "## Code fixes — approved\n\n"
        "- [ ] P1 thing\n      file:     src/a.py\n"
        "      anchor:   x = 1\n      evidence: rewrite, nothing removed\n",
        encoding="utf-8")
    body = _find_block("scripts/backup.py")[2]
    poisoned = ".code-winnow/round-01/pre-fix/  (NOT YET MADE)"
    # WINNOW too: the block invokes scripts/backup.py by path, and this test
    # deliberately runs without the env.sh that would otherwise supply it.
    p = run_block(f'WINNOW={WINNOW!r}\nROUND=.code-winnow/round-01\n'
                  f'BACKUP={poisoned!r}\n' + body, str(repo))
    both = p.stdout + p.stderr
    assert "REFUSING:" in both, both
    assert "parenthetical" in both, (
        "refused, but not on the parenthetical gate - the header-paste check "
        f"is no longer what stops this:\n{both}")
    assert not list((repo / ".code-winnow").glob("**/*NOT YET*")), \
        "a directory was created from the header's parenthetical"


@requires_bash
def test_env_sh_actually_restores_state_in_a_fresh_shell(repo):
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
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
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
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
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("# QUOTE IT")[2], str(repo), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo), subs)

    p = run_block(_find_block("Ask the scanner what it actually reviewed")[2], str(repo))
    assert p.returncode == 0, f"input builder refused:\n{p.stdout}{p.stderr}"
    diffs = list((repo / ".code-winnow").glob("round-*/input.diff"))
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

    run_block(_find_block("EXCLUSION FAILED")[2], str(tmp_path), WINNOW_SUBS)
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("# QUOTE IT")[2], str(tmp_path), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(tmp_path), subs)
    run_block(_find_block("Ask the scanner what it actually reviewed")[2], str(tmp_path))

    diffs = list((tmp_path / ".code-winnow").glob("round-*/input.diff"))
    assert diffs and diffs[0].stat().st_size > 0, (
        "clean-tree branch review produced an empty review input - the agents "
        "would report nothing while the scanner holds findings")


@requires_bash
def test_step2_creates_a_round_folder_and_moves_nothing(repo):
    """Rotation used to glob loose `current*` files out of the root at the
    start of the next run, which meant the current run's intermediates and its
    reports sat together in one flat pile for the whole life of the run. Now
    the round folder is created up front and nothing is ever moved.

    Creating it in Step 2 and not Step 0 is deliberate: cold entry at Step 5
    re-runs Step 0, and creating a round there would orphan the plan that
    session was invoked to execute."""
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
    run_block(_find_block("# QUOTE IT")[2], str(repo), WINNOW_SUBS)

    ws = repo / ".code-winnow"
    (ws / "round-01").mkdir()
    (ws / "round-01" / "report.md").write_text("round one\n", encoding="utf-8")
    (ws / "declined.json").write_text('{"findings": []}\n', encoding="utf-8")

    p = run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo),
                  WINNOW_SUBS)
    assert p.returncode == 0, f"{p.stdout}{p.stderr}"

    assert (ws / "round-02").is_dir(), "Step 2 must create the next round"
    assert (ws / "round-01" / "report.md").read_text(encoding="utf-8") \
        == "round one\n", "a completed round must never be touched again"

    # The scaffold landed.
    assert (ws / "round-02" / "README.md").is_file()
    assert (ws / "round-02" / "scratch").is_dir()
    assert (ws / "utils").is_dir()

    # ...and so did the two machine-written files.
    meta = json.loads((ws / "round-02" / "meta.json").read_text(
        encoding="utf-8"))
    assert meta["round"] == 2
    assert meta["scope"] == "worktree"
    assert meta["prior_round"] is None, \
        "round-01 has no meta.json, so it is not a baseline"
    assert (ws / "round-02" / "scan.json").is_file()

    assert (ws / "declined.json").exists(), "persistent files stay at the root"
    env = (ws / "env.sh").read_text(encoding="utf-8")
    assert "ROUND=" in env and "round-02" in env
    assert not list(ws.glob("current*")), \
        "no run artifact may be written to the workspace root"


@requires_bash
def test_step0_does_not_clobber_a_populated_index(repo):
    """Step 0 is idempotent and cold entry at Step 5 re-runs it. An
    unconditional copy would overwrite the index with a blank skeleton, and
    `cp -n` is a GNU/BSD extension - a shell that ignores the flag clobbers
    and the run carries on."""
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
    index = repo / ".code-winnow" / "README.md"
    assert index.is_file(), "Step 0 must lay down the root scaffold"

    index.write_text("# filled in by a previous run\n", encoding="utf-8")
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
    assert index.read_text(encoding="utf-8") == "# filled in by a previous run\n"


@requires_bash
def test_review_input_on_a_branch_review_includes_uncommitted_work(tmp_path):
    """The builder resolved `$BASE...HEAD`, a commit-to-commit diff, while the
    scanner reads every file from disk. On a dirty tree under a branch review
    the agents were handed a diff that omitted changes the scanner had scanned,
    and held a JSON whose line numbers came from content the diff never showed.

    Neither existing guard catches it: the `-s` check passes because the file
    is large, just wrong, and SNAPSHOT compares the tree to itself over time
    rather than HEAD to the worktree. Found by running this skill on itself.
    """
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
    # ...and now work that is NOT committed, which the scanner will read.
    (tmp_path / "feature.py").write_text(
        "def load():\n    try:\n        go()\n    except Exception:\n        pass\n"
        "\n\ndef UNCOMMITTED_MARKER():\n    unused_local = 1\n    return 2\n",
        encoding="utf-8")

    run_block(_find_block("EXCLUSION FAILED")[2], str(tmp_path), WINNOW_SUBS)
    # An explicit branch scope is the case: `auto` on a dirty tree resolves to
    # worktree and never reaches the branch path, so the mismatch only appears
    # when the reviewer names the scope - which is what reviewing a branch means.
    subs = {"<absolute path to this skill's directory>": WINNOW,
            'SCOPE=""': 'SCOPE="--scope branch --base main"'}
    run_block(_find_block("# QUOTE IT")[2], str(tmp_path), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(tmp_path), subs)
    run_block(_find_block("Ask the scanner what it actually reviewed")[2], str(tmp_path))

    diffs = list((tmp_path / ".code-winnow").glob("round-*/input.diff"))
    assert diffs, "no input.diff written"
    text = diffs[0].read_text(encoding="utf-8", errors="replace")
    assert "UNCOMMITTED_MARKER" in text, (
        "the review input omits uncommitted work the scanner scanned - the "
        "agents review one tree while the JSON describes another")


# --------------------------------------------------------------------------
# Step 5a's refusals
# --------------------------------------------------------------------------

def _bootstrap(path):
    """Run Steps 0-2 in separate shells and return this run's round
    directory name, e.g. "round-01".

    Every artifact path derives from the round now. The stem still
    identifies the run inside meta.json and the report headers; it just
    does not name files, so a test that needs a path asks for the round."""
    run_block(_find_block("EXCLUSION FAILED")[2], str(path), WINNOW_SUBS)
    run_block(_find_block("# QUOTE IT")[2], str(path), WINNOW_SUBS)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(path),
              WINNOW_SUBS)
    got = run_block('. .code-winnow/env.sh; printf %s "$ROUND"', str(path))
    round_dir = got.stdout.strip()
    assert round_dir, f"bootstrap yielded no ROUND:\n{got.stdout}{got.stderr}"
    return os.path.basename(round_dir)


PLAN_BODY = """Skill:    {winnow}
Backup:   .code-winnow/{round}/pre-fix/

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


def _write_plan(repo, round_dir, status_line):
    """A minimal well-formed plan; `status_line` None omits the line entirely."""
    head = (f"# Fix plan\n\n"
            f"Round:     {round_dir[-2:]}  -  .code-winnow/{round_dir}/\n")
    if status_line is not None:
        head += status_line + "\n"
    p = repo / ".code-winnow" / round_dir / "fixplan.md"
    p.write_text(head + PLAN_BODY.format(winnow=WINNOW, round=round_dir),
                 encoding="utf-8")
    return p


def _run_step5a(repo):
    return run_block(_find_block("scripts/backup.py")[2], str(repo))


@requires_bash
def test_step5a_backs_up_an_approved_plan(repo):
    """The positive case, so the refusal tests below are not vacuously green
    against a script that refuses everything."""
    rd = _bootstrap(repo)
    _write_plan(repo, rd, "Status:   APPROVED by the user on 2026-08-02")
    p = _run_step5a(repo)
    out = p.stdout + p.stderr
    assert "REFUSING" not in out, out
    assert "backed up 1 file(s)" in p.stdout, out
    assert (repo / ".code-winnow" / rd / "pre-fix" / "feature.py").is_file()


@requires_bash
def test_step5a_refuses_a_plan_item_with_no_file_line(repo):
    """`file:` is the whole backup list. An item without one names no target,
    so the copy silently under-collects and then prints a success count derived
    from the same regex that just missed it - and the file is edited with no
    restore point. Refusing is the only safe reading."""
    rd = _bootstrap(repo)
    (repo / ".code-winnow" / rd / "fixplan.md").write_text(
        "# Fix plan\n"
        "Status:   APPROVED by the user on 2026-08-03\n\n"
        "## Code fixes - approved\n\n"
        "- [ ] P1 bare except in feature.py line 4 swallows the loader error\n"
        "      anchor:   except Exception:\n"
        "      evidence: rewrite, nothing removed\n",
        encoding="utf-8")
    p = _run_step5a(repo)
    out = p.stdout + p.stderr
    assert "REFUSING" in out, f"backed up a plan item naming no file:\n{out}"
    assert "no `file:` line" in out, out
    assert not (repo / ".code-winnow" / rd / "pre-fix").exists()


def test_every_reference_path_named_in_the_docs_exists():
    """Extraction moved prompts, templates and the backup script out of
    SKILL.md. A pointer that survives the move but names a file that does not
    is the failure mode: the agent opens nothing, reports findings from no
    standard at all, and the run looks normal. Cheap to check, silent to miss.
    """
    docs = [SKILL_MD, os.path.join(WINNOW, "references", "agent-prompts.md")]
    missing = []
    for doc in docs:
        text = open(doc, encoding="utf-8").read()
        for rel in set(re.findall(r"\$WINNOW/((?:references|scripts)/[\w.-]+)", text)):
            if not os.path.isfile(os.path.join(WINNOW, rel)):
                missing.append(f"{os.path.basename(doc)} -> $WINNOW/{rel}")
    assert not missing, "documented paths that do not exist:\n  " + "\n  ".join(missing)


def test_the_backup_script_exists_and_skill_md_invokes_it_by_path():
    """The Step 5a block is now an invocation, not an implementation. If the
    script is gone the block fails loudly; if the block stops naming it, the
    SPINE marker below stops matching and the harness tests nothing."""
    assert os.path.isfile(BACKUP_PY), "scripts/backup.py is missing"
    _, _, body = _find_block("scripts/backup.py")
    assert '"$WINNOW/scripts/backup.py"' in body, (
        "Step 5a must invoke the script through $WINNOW - a bare relative path "
        "only resolves when the cwd is the skill folder, which it never is")


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
    rd = _bootstrap(repo)
    _write_plan(repo, rd, status)
    p = _run_step5a(repo)
    out = p.stdout + p.stderr
    assert "REFUSING" in out, f"applied a plan with {why}:\n{out}"
    assert not (repo / ".code-winnow" / rd / "pre-fix").exists(), \
        "refused, but still made a backup - the refusal came too late"


# --------------------------------------------------------------------------
# Agent D's notes document must never be executable as a fix plan
# --------------------------------------------------------------------------

NOTES_TEMPLATE = os.path.join(WINNOW, "scaffold", "round", "notes.md")


def _notes_template():
    """The performance-notes document template.

    It ships in scaffold/round/, which Step 2 copies into the round. It was
    previously a fenced block inside references/report-format.md; the template
    has to be found wherever it actually is, because a copy kept here would
    agree with itself forever while the real document drifted.
    """
    assert os.path.isfile(NOTES_TEMPLATE), (
        f"no notes template at {NOTES_TEMPLATE} - Step 2 copies it into every "
        f"round, so its absence means the round has no notes document at all")
    return open(NOTES_TEMPLATE, encoding="utf-8").read()


def test_the_notes_document_is_not_fix_plan_shaped():
    """Agent D's notes are never applied, and the only thing enforcing that at
    the mechanical level is that the document does not parse as a plan.

    Step 5a finds fix items by `- [ ]` and the paths it backs up and edits by
    `file:`. A notes document carrying either token is one an executor could act
    on. Every other failure in this skill costs a re-run; this one edits files.
    """
    tpl = _notes_template()
    assert not re.search(r"(?m)^\s*-\s*\[.\]\s", tpl), (
        "the notes template carries a `- [ ]` item marker - Step 5a's ITEM "
        "regex would parse it as an approved fix")
    assert not re.search(r"(?m)^\s*file:\s*\S", tpl), (
        "the notes template carries a `file:` line - Step 5a would back up "
        "and edit that path")


@requires_bash
def test_step5a_refuses_the_notes_document_on_its_status_line(repo):
    """Belt and braces, and it pins a different failure from the test above.

    That one pins the two tokens; this one pins the `Status:` line, by handing
    the real Step 5a script the notes template under a plan's filename.

    It asserts WHICH gate refused, not merely that something did. Asserting only
    `REFUSING` was vacuous: with Status mutated to APPROVED the script sails past
    the approval gate and refuses two checks later on "no fix items found", so
    the test stayed green while the thing it claimed to pin was gone. The
    mutation harness caught exactly that. Layered gates are the right design;
    a test that cannot say which one fired is not.
    """
    rd = _bootstrap(repo)
    (repo / ".code-winnow" / rd / "fixplan.md").write_text(
        _notes_template(), encoding="utf-8")
    p = _run_step5a(repo)
    out = p.stdout + p.stderr
    assert "REFUSING" in out, \
        f"Step 5a accepted Agent D's notes document as a fix plan:\n{out}"
    assert "Status reads" in out, (
        "refused, but not on the Status line - the notes document's "
        f"`Status: NOT APPLIED` is no longer what stops it:\n{out}")
    assert not (repo / ".code-winnow" / rd / "pre-fix").exists(), \
        "refused, but still made a backup - the refusal came too late"


@requires_bash
def test_baseline_json_exists_before_step_3_needs_it(repo):
    run_block(_find_block("EXCLUSION FAILED")[2], str(repo), WINNOW_SUBS)
    subs = {"<absolute path to this skill's directory>": WINNOW}
    run_block(_find_block("# QUOTE IT")[2], str(repo), subs)
    run_block(_find_block("rm -f .code-winnow/env.sh")[2], str(repo), subs)

    # Ask the shell, don't parse the file: %q quoting is not always single-quoted.
    got = run_block('. .code-winnow/env.sh; printf %s "$ROUND"', str(repo))
    round_dir = got.stdout.strip()
    assert round_dir, f"env.sh yielded no ROUND:\n{got.stdout}{got.stderr}"
    baseline = repo / round_dir / "scan.json"
    assert baseline.is_file(), "Step 2 must write the baseline JSON"
    data = json.loads(baseline.read_text(encoding="utf-8"))
    assert data["findings"], "baseline holds no findings for a repo with chaff"


# --------------------------------------------------------------------------
# backup.py - the destination is the plan's sibling
# --------------------------------------------------------------------------

def _plan_text():
    return (
        "# Fix plan\n\n"
        "Status:   APPROVED by the user on 2026-08-03\n"
        "Verify:   true\n\n"
        "## Code fixes - approved\n\n"
        "- [ ] P2 unused local\n"
        "      file:     feature.py\n"
        "      line:     1\n"
        "      anchor:   x = 1\n"
        "      fix:      delete it\n"
        "      evidence: rewrite, nothing removed\n"
    )


def _plan_repo(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    (tmp_path / "feature.py").write_text("x = 1\n", encoding="utf-8")
    rd = tmp_path / ".code-winnow" / "round-02"
    rd.mkdir(parents=True)
    (rd / "fixplan.md").write_text(_plan_text(), encoding="utf-8")
    return rd


def _backup(tmp_path, dest, plan):
    return subprocess.run([sys.executable, BACKUP_PY, dest, str(plan)],
                          capture_output=True, text=True, cwd=tmp_path)


def test_backup_accepts_the_plans_sibling_pre_fix(tmp_path):
    rd = _plan_repo(tmp_path)
    p = _backup(tmp_path, ".code-winnow/round-02/pre-fix", rd / "fixplan.md")
    assert p.returncode == 0, p.stdout + p.stderr
    assert (rd / "pre-fix" / "feature.py").is_file()


def test_backup_refuses_a_destination_in_another_round(tmp_path):
    """The plan and its restore point must not be able to drift apart. A
    backup written into round-01 while round-02's plan is executed leaves
    `Undo:` pointing at files that were never the originals - and that is only
    discovered when someone tries to undo."""
    rd = _plan_repo(tmp_path)
    (tmp_path / ".code-winnow" / "round-01").mkdir()
    p = _backup(tmp_path, ".code-winnow/round-01/pre-fix", rd / "fixplan.md")
    assert p.returncode != 0
    assert "REFUSING" in (p.stdout + p.stderr)


def test_backup_refuses_a_destination_at_the_workspace_root(tmp_path):
    rd = _plan_repo(tmp_path)
    p = _backup(tmp_path, ".code-winnow/pre-fix", rd / "fixplan.md")
    assert p.returncode != 0
    assert "REFUSING" in (p.stdout + p.stderr)


def test_backup_refuses_a_misspelled_sibling(tmp_path):
    rd = _plan_repo(tmp_path)
    p = _backup(tmp_path, ".code-winnow/round-02/prefix", rd / "fixplan.md")
    assert p.returncode != 0
    assert "REFUSING" in (p.stdout + p.stderr)


def test_backup_still_refuses_a_destination_pasted_from_the_header(tmp_path):
    """The original guard: `Backup: <path>  (NOT YET MADE)` pasted into the
    argument made a real directory of that name and printed the usual success
    line. It must keep firing, and with the clearer message of the two."""
    rd = _plan_repo(tmp_path)
    p = _backup(tmp_path, ".code-winnow/round-02/pre-fix  (NOT YET MADE)",
                rd / "fixplan.md")
    assert p.returncode != 0
    out = p.stdout + p.stderr
    assert "REFUSING" in out and "parenthetical" in out


# --------------------------------------------------------------------------
# Step 4's reconciliation picks its baseline from meta.json
# --------------------------------------------------------------------------

@requires_bash
def test_step4_reconciles_against_the_matching_prior_round(repo):
    r"""The baseline used to be found with
    `ls -1t round-*/*.json | grep -v -- '-postfix\|-p3\|-r2'`, a blocklist of
    ad-hoc suffixes that grew every time an agent invented one, plus a line of
    prose asking the reader to eyeball the stem's scope segment.

    Both failed the same way and quietly. A branch baseline reconciled against
    a worktree re-scan reports every untouched finding as `resolved`, which
    reads as "your fixes worked" for findings nobody touched. meta.json's
    `scope` makes the match structural."""
    ws = repo / ".code-winnow"
    ws.mkdir(exist_ok=True)
    # A newer round that reviewed something else, and an older one that did not.
    for name, scope, when in (("round-01", "worktree", "2026-01-01T00:00:00"),
                              ("round-02", "branch vs main",
                               "2026-06-01T00:00:00")):
        (ws / name).mkdir(parents=True, exist_ok=True)
        (ws / name / "meta.json").write_text(
            json.dumps({"round": int(name[-2:]), "scope": scope,
                        "generated": when}), encoding="utf-8")
        (ws / name / "scan.json").write_text(
            json.dumps({"findings": [], "resolved": [], "out_of_scope": [],
                        "declined": []}), encoding="utf-8")

    rd = _bootstrap(repo)                       # round-03, worktree scope
    meta = json.loads((ws / rd / "meta.json").read_text(encoding="utf-8"))
    assert meta["prior_round"] == "round-01", (
        "picked the more recent round rather than the matching one: "
        f"{meta['prior_round']}")

    p = run_block(_find_block("PRIOR=$(")[2], str(repo))
    assert p.returncode == 0, f"{p.stdout}{p.stderr}"
    assert (ws / rd / "scan-vs-round-01.json").is_file(), \
        f"no reconciliation output written; block said:\n{p.stdout}{p.stderr}"
    assert not (ws / rd / "scan-vs-round-02.json").exists()
    # The pre-fix baseline is never written back over.
    assert (ws / rd / "scan.json").is_file()


@requires_bash
def test_step4_index_substitutes_every_path_and_leaves_no_dead_link(repo):
    """The index is the one file a reader opens, so a dead link in it is the
    most expensive kind: it is indistinguishable from a live one until clicked,
    and by then the reader has stopped trusting the file.

    The regeneration is a full rewrite from the template, never an edit of the
    live file - that is what removes half-updated state - and `ROUND` is the
    only path placeholder, so the paths cannot be half-substituted either."""
    rd = _bootstrap(repo)
    ws = repo / ".code-winnow"
    for name in ("report.md", "fixplan.md", "notes.md", "agent-A.md",
                 "agent-B.md", "agent-E.md"):
        (ws / rd / name).write_text("x\n", encoding="utf-8")

    p = run_block(_find_block('sed "s|ROUND|')[2], str(repo))
    assert p.returncode == 0, f"{p.stdout}{p.stderr}"

    index = (ws / "README.md").read_text(encoding="utf-8")
    assert "ROUND/" not in index, "a path placeholder survived the rewrite"
    assert f"{rd}/report.md" in index

    # Every link the block itself produced must resolve. The three passes that
    # did not run still have rows; their links are dropped by hand at Step 4,
    # which is prose, so this checks only what the substitution wrote.
    dead = [h for h in re.findall(r"\]\(([^)]+)\)", index)
            if not h.startswith(("http://", "https://", "#"))
            and not (ws / h).exists()
            and os.path.basename(h) not in
            ("agent-S.md", "agent-C.md", "agent-D.md")]
    assert not dead, f"dead links in the regenerated index: {dead}"


# --------------------------------------------------------------------------
# the references follow the layout
# --------------------------------------------------------------------------

def test_report_format_points_at_the_templates_it_no_longer_holds():
    """One definition per shape. report-format.md stops carrying a second copy
    of the fixplan and notes shapes and keeps what a skeleton cannot express."""
    text = open(REPORT_FORMAT, encoding="utf-8").read()
    assert "scaffold/round/fixplan.md" in text
    assert "scaffold/round/notes.md" in text
    # The rules a template cannot carry must survive the move.
    assert "unquoted and unfenced" in text
    assert ("never severity-sorted" in text.lower()
            or "never sort" in text.lower())


def test_no_reference_file_names_a_stem_shaped_artifact_path():
    """Every <stem>.md / <stem>.json path is now round-NN/<short name>. A
    pointer that survives the move but names the old shape sends an agent to a
    path nothing writes, and the run looks normal."""
    import glob
    bad = []
    for p in glob.glob(os.path.join(WINNOW, "references", "*.md")):
        for n, line in enumerate(open(p, encoding="utf-8"), 1):
            if re.search(r"\.code-winnow/[^\s`)]*<stem>", line):
                bad.append(f"{os.path.basename(p)}:{n}: {line.strip()[:90]}")
    assert not bad, "stem-named paths still in the references:\n  " + \
        "\n  ".join(bad)


def test_report_format_requires_the_identity_block():
    text = open(REPORT_FORMAT, encoding="utf-8").read()
    assert "Compared:" in text, (
        "the filename no longer says what was reviewed, so the identity block "
        "has to be specified where the report's shape is specified")
