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
        assert href.startswith("ROUND/"), (
            f"{href} does not start with the ROUND placeholder")


def test_root_index_has_a_row_for_every_pass():
    text = read(ROOT_README)
    for name in ("report.md", "fixplan.md", "notes.md", "agent-S.md",
                 "agent-A.md", "agent-B.md", "agent-C.md", "agent-D.md",
                 "agent-E.md"):
        assert f"ROUND/{name}" in text, f"no index row for {name}"


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
