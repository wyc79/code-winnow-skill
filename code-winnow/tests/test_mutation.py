"""The mutation protocol, run end to end on the fixture its worked example names.

`references/mutation.md` documents a procedure whose whole claim is that it
produces a result instead of an argument. A worked example nobody executes is an
argument about a procedure that exists to replace arguments - so this runs it.
The two marked diff blocks in that document are extracted, applied to a copy of
`examples/mutation/`, and both halves are required: the finding's test stays
green under the mutation (the proof), and the tightened test goes red under the
same mutation (the loop closed).

It is the drift guard as well. The blocks have to match the fixture byte for
byte, and the command has to be the one the document prints, so a document that
stopped describing the code it names fails here rather than in someone's run.

Nothing is mutated in place: every edit goes to a copy under pytest's tmp_path,
exactly as the protocol requires of the tree it is proving.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WINNOW = os.path.dirname(HERE)
DOC = os.path.join(WINNOW, "references", "mutation.md")
SCAN = os.path.join(WINNOW, "scripts", "scan.py")
EXAMPLE = os.path.join(WINNOW, "examples", "mutation")
PROD = os.path.join(EXAMPLE, "dedup.py")
TEST = os.path.join(EXAMPLE, "test_dedup.py")


# --------------------------------------------------------------------------
# extraction - the document is the source, never a copy of it
# --------------------------------------------------------------------------

def _doc():
    return open(DOC, encoding="utf-8").read()


def _diff_block(marker_id):
    """(removed, added) for one `<!-- winnow:mutation id=X -->` diff block.

    Removed lines are what must already be in the fixture; added lines are what
    replaces them. Returning both from one block is what stops the two halves
    of an edit drifting apart in the document.
    """
    pat = (r"<!-- winnow:mutation id=" + re.escape(marker_id) +
           r" start -->\s*```diff\n(.*?)```\s*<!-- winnow:mutation id="
           + re.escape(marker_id) + r" end -->")
    m = re.search(pat, _doc(), re.S)
    assert m, (f"mutation.md has no marked diff block id={marker_id!r}; the "
               "worked example is what this whole file runs")
    removed, added = [], []
    for line in m.group(1).splitlines():
        assert line[:1] in "-+", f"id={marker_id}: {line!r} is neither side of a diff"
        (removed if line.startswith("-") else added).append(line[1:])
    return "\n".join(removed) + "\n" if removed else "", \
           "\n".join(added) + "\n" if added else ""


def _command():
    """The worked example's own pytest command, run with this interpreter.

    Extracted rather than retyped: a harness running a different command from
    the one the document prints is a harness that proves the document works
    when it does not.
    """
    m = re.search(r"(?m)^python3 -m pytest (.+)$", _doc())
    assert m, "the worked example no longer carries a runnable pytest command"
    return [sys.executable, "-m", "pytest", *shlex.split(m.group(1))]


# --------------------------------------------------------------------------
# the copy - never the tree this is run from
# --------------------------------------------------------------------------

def _copy(tmp_path):
    """A throwaway copy of the fixture, at the path the document's command
    names. `tmp_path` plays the copy root - `.code-winnow/mutation/<id>/` in a
    real run - so the command runs against the same relative path either way."""
    dst = tmp_path / "examples" / "mutation"
    shutil.copytree(EXAMPLE, dst,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dst


def _edit(path, find, replace):
    body = open(path, encoding="utf-8").read()
    assert find in body, (
        f"{os.path.basename(path)} does not contain the text mutation.md says "
        f"it does:\n{find!r}\nThe document and the fixture have drifted.")
    open(path, "w", encoding="utf-8").write(body.replace(find, replace, 1))


def _run(cwd):
    return subprocess.run(_command(), cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------
# the protocol
# --------------------------------------------------------------------------

def test_the_document_and_the_fixture_describe_the_same_code(tmp_path):
    """Both marked blocks quote the fixture, and the fixture passes as it
    stands. A worked example whose test is already red proves nothing about a
    mutation, because there is no green to lose."""
    guard, _ = _diff_block("guard")
    weak, tight = _diff_block("tighten")
    assert guard in open(PROD, encoding="utf-8").read(), \
        "the mutation edit is not in examples/mutation/dedup.py"
    assert weak in open(TEST, encoding="utf-8").read(), \
        "the assertion the fix replaces is not in examples/mutation/test_dedup.py"
    assert tight.strip(), "the tighten block proposes no replacement"

    _copy(tmp_path)
    p = _run(tmp_path)
    assert p.returncode == 0, f"the fixture is red before any mutation:\n{p.stdout}"


def test_the_named_test_stays_green_under_the_mutation(tmp_path):
    """The proof. `test_unique_slugs_drops_repeats` is named for the dedup
    filter; deleting the filter entirely leaves it passing, which is what the
    P1 says and what no heuristic in this skill can establish."""
    guard, _ = _diff_block("guard")
    work = _copy(tmp_path)
    _edit(work / "dedup.py", guard, "")

    p = _run(tmp_path)
    assert p.returncode == 0, (
        "the test went red under the mutation, so the finding is WRONG and the "
        f"worked example is no longer an example of proof:\n{p.stdout}")
    assert "1 passed" in p.stdout, p.stdout


def test_the_tightened_assertion_passes_on_correct_code(tmp_path):
    """A tightening that fails on correct code is not a fix, and it would make
    the red run below meaningless - the pair is only evidence if this end of it
    is green."""
    weak, tight = _diff_block("tighten")
    work = _copy(tmp_path)
    _edit(work / "test_dedup.py", weak, tight)

    p = _run(tmp_path)
    assert p.returncode == 0, f"the tightened test fails on unmutated code:\n{p.stdout}"


def test_the_tightened_assertion_fails_under_the_same_mutation(tmp_path):
    """Step 6's closing of the loop. The same mutation, the fixed test, and it
    must now fail - otherwise the tightening pinned nothing and reads exactly
    like a fix."""
    guard, _ = _diff_block("guard")
    weak, tight = _diff_block("tighten")
    work = _copy(tmp_path)
    _edit(work / "test_dedup.py", weak, tight)
    _edit(work / "dedup.py", guard, "")

    p = _run(tmp_path)
    assert p.returncode != 0, (
        "the tightened test still passes with the dedup filter deleted; the "
        f"fix is argued, not proven:\n{p.stdout}")
    assert "AssertionError" in p.stdout, (
        "it failed for some reason other than its assertion - the mutation "
        f"broke the harness, not the behaviour:\n{p.stdout}")


def test_the_scanner_heuristics_are_silent_on_the_fixture():
    """Why the protocol exists at all, pinned as a fact rather than a claim.

    The fixture test has an assertion, no mock and no tautology any rule can
    see, so `scan.py` passes it - which is the shape of both tests in the run
    that motivated this. If a future rule does catch it, this fails, and the
    honest response is to say so in mutation.md rather than to keep telling
    readers the heuristics miss it.
    """
    proc = subprocess.run(
        [sys.executable, SCAN, "--json", "--paths",
         os.path.relpath(TEST, WINNOW), os.path.relpath(PROD, WINNOW)],
        cwd=WINNOW, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    data = json.loads(proc.stdout)
    assert data["findings"] == [], (
        "the scanner now flags the worked example; mutation.md says it does "
        f"not: {[(f['rule'], f['line']) for f in data['findings']]}")


@pytest.mark.parametrize("wanted", ["proven", "argued"])
def test_the_document_names_both_labels(wanted):
    """The label is the protocol's whole output. A document carrying only the
    good one turns "could not be mutated" into silence, which is the failure
    the argued label exists to prevent."""
    assert wanted in _doc(), f"mutation.md never says {wanted!r}"
