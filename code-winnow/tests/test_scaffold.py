"""The shipped scaffold.

`scratch/` and `utils/` ship as real directories rather than as a rule in
prose, because an agent will not create a directory it was told about and will
use one that is already there. That is the whole mechanism by which "ad-hoc
files go in scratch/" is actually obeyed - a previous run left nine
intermediate files at the workspace root, and no rule named them, so no rule
constrained where they landed.

`report.md` and the `agent-*.md` files ship no template on purpose. A skeleton
makes an agent emit every heading whether or not it has anything to put under
one, and a structurally perfect report with hollow sections is harder to catch
than a report with sections missing.
"""

import os
import re
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WINNOW = os.path.dirname(HERE)
SCAFFOLD = os.path.join(WINNOW, "scaffold")
BACKUP_PY = os.path.join(WINNOW, "scripts", "backup.py")

ROOT_README = os.path.join(SCAFFOLD, "root", "README.md")
ROUND_README = os.path.join(SCAFFOLD, "round", "README.md")
ROUND_FIXPLAN = os.path.join(SCAFFOLD, "round", "fixplan.md")
ROUND_NOTES = os.path.join(SCAFFOLD, "round", "notes.md")


def read(p):
    return open(p, encoding="utf-8").read()


@pytest.mark.parametrize("rel", [
    "root/README.md", "root/utils/.gitkeep",
    "round/README.md", "round/fixplan.md", "round/notes.md",
    "round/scratch/.gitkeep",
])
def test_scaffold_ships_every_file(rel):
    assert os.path.isfile(os.path.join(SCAFFOLD, rel)), \
        f"scaffold/{rel} is missing; Step 0 and Step 2 copy it"


def test_root_index_links_are_relative_to_the_workspace():
    """A repo-root-relative href renders perfectly and 404s on click."""
    for href in re.findall(r"\]\(([^)]+)\)", read(ROOT_README)):
        assert not href.startswith(".code-winnow/"), (
            f"{href} is relative to the repo root; links in "
            ".code-winnow/README.md resolve against .code-winnow/")
        assert not href.startswith("/"), f"{href} is absolute"


def test_root_index_uses_one_path_placeholder():
    """Filling the paths must be a single find-and-replace of ROUND."""
    hrefs = re.findall(r"\]\(([^)]+)\)", read(ROOT_README))
    assert hrefs, "the index template has no links"
    for href in hrefs:
        assert href.startswith("{{ROUND}}/"), (
            f"{href} does not start with the placeholder")


def test_root_index_has_a_row_for_every_pass():
    text = read(ROOT_README)
    for name in ("report.md", "fixplan.md", "notes.md", "agent-S.md",
                 "agent-A.md", "agent-B.md", "agent-C.md", "agent-D.md",
                 "agent-E.md"):
        assert "{{ROUND}}/" + name in text, f"no index row for {name}"


def test_round_readme_is_static():
    """It is identical every round, so it carries no placeholder and no
    identity block - there is nothing round-specific in it to get wrong."""
    text = read(ROUND_README)
    assert "ROUND" not in text
    assert "<fill" not in text


def test_round_readme_states_the_filename_law():
    text = read(ROUND_README)
    assert "scratch/" in text and "utils/" in text
    assert "exhaustive" in text.lower(), (
        "the round README is where the enumerated-filename rule is stated")


def test_unfilled_fixplan_template_is_refused_by_backup(tmp_path):
    """The template's Status is a placeholder, not APPROVED. Copying the
    scaffold into a round must never produce a plan an executor will act on."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path,
                   check=True)
    plan = tmp_path / "fixplan.md"
    plan.write_text(read(ROUND_FIXPLAN), encoding="utf-8")
    p = subprocess.run([sys.executable, BACKUP_PY,
                        str(tmp_path / "pre-fix"), str(plan)],
                       capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode != 0
    assert "REFUSING" in (p.stdout + p.stderr)


def test_notes_template_cannot_parse_as_a_fix_plan():
    """report-format.md - `- [ ]` and `file:` are the two tokens backup.py
    keys on. A notes document carrying either would parse as a fix plan, and a
    plan is a thing an executor edits files from."""
    text = read(ROUND_NOTES)
    assert "- [ ]" not in text
    assert not re.search(r"(?m)^\s*file:", text)
    assert "NOT APPLIED" in text


@pytest.mark.parametrize("path", [ROUND_FIXPLAN, ROUND_NOTES])
def test_round_templates_carry_the_identity_block(path):
    """The filename no longer says what this reviewed, so this block does."""
    text = read(path)
    assert re.search(r"(?m)^Round:", text)
    assert re.search(r"(?m)^Compared:", text)
    assert re.search(r"(?m)^Generated:", text)


def test_every_relative_link_in_a_filled_index_resolves(tmp_path):
    """The index is the one file a reader opens. A row for a pass that never
    ran must lose its link: a dead link is indistinguishable from a live one
    until it is clicked, and by then the reader has stopped trusting the file.

    Absolute URLs are exempt. A repo-root-relative path is not, and must fail -
    `.code-winnow/round-02/report.md` renders perfectly and 404s."""
    ws = tmp_path / ".code-winnow"
    rd = ws / "round-02"
    rd.mkdir(parents=True)
    for name in ("report.md", "fixplan.md", "notes.md", "agent-A.md",
                 "agent-B.md", "agent-D.md", "agent-E.md"):
        (rd / name).write_text("x\n", encoding="utf-8")

    filled = read(ROOT_README).replace("{{ROUND}}", "round-02")
    # S and C did not run: the row stays, the link goes.
    for missing in ("agent-S.md", "agent-C.md"):
        filled = filled.replace(f"[{missing}](round-02/{missing})", missing)
    (ws / "README.md").write_text(filled, encoding="utf-8")

    dead = []
    for href in re.findall(r"\]\(([^)]+)\)", filled):
        if href.startswith(("http://", "https://", "#")):
            continue
        if not os.path.isfile(os.path.join(str(ws), href)):
            dead.append(href)
    assert not dead, f"dead links in the index: {dead}"


def test_a_filled_index_keeps_no_markers():
    """An empty cell says "not known". A surviving <fill says the agent stopped
    halfway. They are different facts and only one is acceptable."""
    filled = (read(ROOT_README)
              .replace("{{ROUND}}", "round-02")
              .replace("<fill: branch @ side vs base @ sha (scope), "
                       "YYYY-MM-DD HH:MM>", "main @ worktree, 2026-08-03 19:09")
              .replace("<fill: counts>", "")
              .replace('<fill: links, or "none">', "none"))
    assert "<fill" not in filled, (
        "the marker strings in this test have drifted from the template - the "
        "template is canonical, so update the test")
    assert "{{ROUND}}" not in filled


def test_filling_the_index_leaves_prose_about_round_alone():
    """The placeholder has to be a token that cannot occur in the prose it
    sits in, and `ROUND` is a real word.

    `sed "s|ROUND|round-06|g"` is global, so it also rewrote the template's own
    line documenting `$ROUND` as an env.sh variable, producing `$round-06`.
    That shipped in the index of a real run. The test that should have caught
    it performed the same unanchored replace, so it reproduced the defect
    instead - which is why this one asserts on the survivor, not the result."""
    filled = read(ROOT_README).replace("{{ROUND}}", "round-06")
    assert "`$ROUND`" in filled, (
        "the env.sh variable reference was rewritten by the substitution - "
        "the placeholder is not distinct from the prose around it")
    assert "$round-06" not in filled
