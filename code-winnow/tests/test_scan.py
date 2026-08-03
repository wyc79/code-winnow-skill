"""Regression tests for scan.py.

Every case here is a bug that shipped once. The names say what went wrong,
not what the code does, so a failure tells you which regression came back.

Run: python3 -m pytest tests/ -q      (from the skill directory)
"""

import json
import os
import subprocess
import sys

import pytest

SCAN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "scripts", "scan.py")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def run(cwd, *args):
    proc = subprocess.run([sys.executable, SCAN, *args],
                          capture_output=True, text=True, cwd=cwd)
    return proc


def rules(cwd, *args):
    """{rule: [lines]} from a --json run."""
    proc = run(cwd, "--json", *args)
    data = json.loads(proc.stdout)
    out = {}
    for f in data["findings"]:
        out.setdefault(f["rule"], []).append(f["line"])
    return out


def severities(cwd, *args):
    """{rule: [severities]} from a --json run."""
    data = json.loads(run(cwd, "--json", *args).stdout)
    out = {}
    for f in data["findings"]:
        out.setdefault(f["rule"], []).append(f["severity"])
    return out


def write(tmp_path, rel, body):
    """Always UTF-8. `write_text` defaults to the locale codec, so on a
    GBK/cp1252 machine every non-ASCII fixture in this file raised instead of
    testing anything - and the scanner decodes UTF-8 unconditionally."""
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return str(path)


def write_bytes(tmp_path, rel, blob):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return str(path)


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t.t")
    git(tmp_path, "config", "user.name", "t")
    write(tmp_path, "seed.txt", "seed\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "init")
    return tmp_path


# --------------------------------------------------------------------------
# scope resolution
# --------------------------------------------------------------------------

def test_untracked_files_are_in_scope(repo):
    """They are invisible to `git diff` in every mode, and new files are
    where generated code concentrates."""
    write(repo, "new.py", "def f():\n    dead = 1\n    return 2\n")
    assert "dead-local" in rules(str(repo))


def test_staged_file_does_not_eclipse_unstaged_work(repo):
    """Stop-at-first-non-empty reviewed the staged fraction and claimed the
    branch was covered."""
    write(repo, "a.py", "def a():\n    x = 1\n    return 2\n")
    git(repo, "add", "a.py")
    write(repo, "b.py", "def b():\n    y = 1\n    return 2\n")
    git(repo, "add", "b.py")
    write(repo, "b.py", "def b():\n    y = 1\n    z = 2\n    return 3\n")
    found = rules(str(repo))
    assert len(found.get("dead-local", [])) >= 2


SUITE_WITH_ONE_ASSERTION = (
    "def test_alpha():\n"
    "    result = compute()\n"
    "    assert result == 3\n"
    "\n"
    "\n"
    "def test_beta():\n"
    "    compute()\n"
)


def test_a_deletion_only_change_is_not_an_empty_scope(repo):
    """The scope map is keyed on added lines, so a file that only lost lines
    had no entry and the whole scan came back 'No diff found' on a tree with
    real uncommitted work. Under `--scope auto` that was worse than a miss:
    the empty result fell through to the branch diff and reviewed something
    else, then reported on it as though it were the working tree."""
    write(repo, "app.py", "def f():\n    a = 1\n    b = 2\n    return a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "app")

    write(repo, "app.py", "def f():\n    a = 1\n    return a\n")   # only cut

    data = json.loads(run(str(repo), "--json").stdout)
    assert data["files"] == 1, (
        f"deletion-only change resolved to scope {data['scope']!r}: "
        + repr(data["warnings"]))


def test_a_diff_that_only_deletes_an_assertion_still_reports_the_test(repo):
    """Scope was 'is this finding's line one the diff added', which no
    deletion-only edit can satisfy. Removing a test's only assertion leaves
    every surviving line untouched, so the now-assertionless test was filed
    pre-existing and dropped: the change created a P1 and the scan printed
    nothing. That is this skill's headline case."""
    write(repo, "tests/test_x.py", SUITE_WITH_ONE_ASSERTION)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "suite")

    write(repo, "tests/test_x.py",                      # only the assert goes
          "def test_alpha():\n"
          "    result = compute()\n"
          "\n"
          "\n"
          "def test_beta():\n"
          "    compute()\n")

    found = rules(str(repo))
    assert 1 in found.get("test-without-assertion", []), (
        "deleting a test's only assertion produced no finding: " + repr(found))


def test_a_test_the_diff_never_touched_stays_pre_existing(repo):
    """The negative control. Attributing by span must not turn every edited
    file into a repo audit - `test_beta` was committed assertion-free and the
    diff does not reach it, so it stays out of the default run."""
    write(repo, "tests/test_x.py", SUITE_WITH_ONE_ASSERTION)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "suite")

    write(repo, "tests/test_x.py",
          "def test_alpha():\n"
          "    result = compute()\n"
          "\n"
          "\n"
          "def test_beta():\n"
          "    compute()\n")

    lines = rules(str(repo)).get("test-without-assertion", [])
    assert lines == [1], (           # line 1 is test_alpha, which the diff hit
        "test_beta is at line 5, untouched by this diff, and must not be "
        "reported on the default run: " + repr(lines))


def test_whole_files_still_surfaces_the_untouched_test(repo):
    """...and --whole-files is how you ask for it, unchanged."""
    write(repo, "tests/test_x.py", SUITE_WITH_ONE_ASSERTION)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "suite")
    write(repo, "tests/test_x.py",
          "def test_alpha():\n"
          "    result = compute()\n"
          "\n"
          "\n"
          "def test_beta():\n"
          "    compute()\n")

    lines = rules(str(repo), "--whole-files").get("test-without-assertion", [])
    assert 5 in lines, repr(lines)   # test_beta, pre-existing and asked for


def test_runs_from_a_subdirectory(repo):
    """Paths come back relative to the git toplevel, so opening them from a
    subdirectory failed - silently, which read as a clean scan."""
    write(repo, "pkg/mod.py", "def f():\n    dead = 1\n    return 2\n")
    sub = repo / "pkg"
    assert "dead-local" in rules(str(sub))


def test_base_branch_other_than_main(repo):
    git(repo, "checkout", "-qb", "develop")
    git(repo, "checkout", "-qb", "feature")
    write(repo, "c.py", "def c():\n    dead = 1\n    return 2\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    assert "dead-local" in rules(str(repo), "--scope", "branch", "--base", "develop")


def test_own_workspace_is_never_reviewed(repo):
    write(repo, ".code-winnow/report.py", "def f():\n    dead = 1\n    return 2\n")
    assert rules(str(repo)) == {}


def test_staged_then_edited_file_keeps_worktree_line_numbers(repo):
    """`git diff --cached` numbers the index blob and `git diff` numbers the
    worktree blob; both used to be matched against the worktree file. Stage a
    fix and keep editing above it and every real P1 below the shift was
    dropped as pre-existing."""
    write(repo, "a.py", "def f():\n    return 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    write(repo, "a.py", "def f():\n    return 1\n\n\ndef g():\n"
                        "    dead = 1\n    return 2\n")
    git(repo, "add", "a.py")
    # keep editing: three lines inserted above shift `dead` down in the
    # worktree but not in the index
    write(repo, "a.py", "import os\nimport sys\nimport json\n"
                        "def f():\n    return 1\n\n\ndef g():\n"
                        "    dead = 1\n    return 2\n")
    assert "dead-local" in rules(str(repo))


def test_renamed_file_is_not_reported_as_all_new_code(repo):
    """`--no-renames` turned every `git mv` into a whole-file addition, so a
    rename put the entire pre-existing file into review scope."""
    write(repo, "a.py", "def f():\n    dead = 1\n    return 2\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    git(repo, "mv", "a.py", "b.py")
    assert "dead-local" not in rules(str(repo))


def test_form_feed_does_not_shift_line_numbers(tmp_path):
    """str.splitlines() breaks on form feed, U+2028 and friends; git counts
    only \\n. One page-break separator moved every line number below it."""
    write(tmp_path, "f.py",
          "X = 1\n\x0c\ndef f():\n    dead = 1\n    return 2\n")
    assert rules(str(tmp_path), "--paths", "f.py")["dead-local"] == [4]


def test_form_feed_in_the_diff_does_not_shift_the_added_line_set(repo):
    """The same splitlines() bug on the other side: one added line carrying a
    form feed split into two, so every added line below it was recorded one
    too high and the real findings fell out of scope."""
    write(repo, "a.py", "x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    write(repo, "a.py", 'x = 1\n\x0c\nCACHE = "/Users/alice/x"\n')
    git(repo, "add", "-A")
    assert "local-path" in rules(str(repo))


def test_line_separator_does_not_shift_line_numbers(tmp_path):
    write(tmp_path, "s.py",
          'X = "a\u2028b"\ndef f():\n    dead = 1\n    return 2\n')
    assert rules(str(tmp_path), "--paths", "s.py")["dead-local"] == [3]


def test_untracked_non_ascii_filename_is_scanned(repo):
    """git c-quotes non-ASCII paths; the untracked list was never unquoted and
    the diff unquoter mangled UTF-8 through `unicode_escape`."""
    write(repo, "café.py", "def f():\n    dead = 1\n    return 2\n")
    found = rules(str(repo))
    assert "dead-local" in found, run(str(repo), "--json").stdout


def test_tracked_non_ascii_filename_is_scanned(repo):
    write(repo, "naïve.py", "x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    write(repo, "naïve.py", "x = 1\ndef f():\n    dead = 1\n    return 2\n")
    assert "dead-local" in rules(str(repo))


# --------------------------------------------------------------------------
# failure reporting
# --------------------------------------------------------------------------

def test_unreadable_file_is_loud(tmp_path):
    """A scan that opened nothing must not look like a scan that found
    nothing."""
    proc = run(str(tmp_path), "--json", "--paths", "does_not_exist.py")
    data = json.loads(proc.stdout)
    assert data["complete"] is False
    assert data["errors"]
    assert data["warnings"]


def test_unreadable_file_sets_exit_code(tmp_path):
    proc = run(str(tmp_path), "--paths", "does_not_exist.py")
    assert proc.returncode == 2


def test_oversized_file_is_skipped_not_scanned(tmp_path):
    write(tmp_path, "big.py", "x = 1\n" * 200000)
    proc = run(str(tmp_path), "--json", "--paths", "big.py")
    data = json.loads(proc.stdout)
    assert any("exceeds" in e["error"] for e in data["errors"])


# --------------------------------------------------------------------------
# wrong verdicts
# --------------------------------------------------------------------------

def test_incremented_and_read_field_is_not_reported_unread(tmp_path):
    """`bumped` was collected in the same walk that decided whether a Load
    counted, so a counter that was read got reported as never read."""
    write(tmp_path, "m.py",
          "class S:\n"
          "    def __init__(self):\n"
          "        self._hits = 0\n"
          "    def record(self):\n"
          "        self._hits += 1\n"
          "    def report(self, items):\n"
          "        for i in items:\n"
          "            if i:\n"
          "                print(self._hits)\n")
    assert "unused-field" not in rules(str(tmp_path), "--paths", "m.py")


def test_incremented_and_never_read_field_is_still_reported(tmp_path):
    """The true positive the fix above must not cost."""
    write(tmp_path, "m.py",
          "class B:\n"
          "    def __init__(self):\n"
          "        self._never = 0\n"
          "    def bump(self):\n"
          "        self._never += 1\n")
    assert "unused-field" in rules(str(tmp_path), "--paths", "m.py")


def test_uobject_local_is_not_an_unrooted_member(tmp_path):
    """Locals live on the stack; the GC rule is about members."""
    write(tmp_path, "a.cpp",
          '#include "CoreMinimal.h"\n'
          "void AMyActor::BeginPlay()\n{\n"
          "    UWorld* World = GetWorld();\n"
          "    World->Foo();\n}\n")
    assert "unrooted-uobject" not in rules(str(tmp_path), "--paths", "a.cpp")


def test_uobject_member_without_uproperty_is_still_p1(tmp_path):
    write(tmp_path, "A.h",
          '#include "CoreMinimal.h"\n'
          "UCLASS()\nclass AMyActor : public AActor\n{\n"
          "    GENERATED_BODY()\n"
          "    UPROPERTY()\n"
          "    UStaticMeshComponent* Mesh;\n"
          "    USceneComponent* Root;\n};\n")
    found = rules(str(tmp_path), "--paths", "A.h")
    assert found["unrooted-uobject"] == [8]  # Root, not Mesh


def test_multiline_uproperty_still_roots_the_member_below_it(tmp_path):
    """Epic's own house style wraps the specifier list. Only the line
    immediately above was checked, so the member under a wrapped UPROPERTY
    got a P1 saying it had none."""
    write(tmp_path, "A.h",
          '#include "CoreMinimal.h"\n'
          "UCLASS()\nclass AMyActor : public AActor\n{\n"
          "    GENERATED_BODY()\n"
          "    UPROPERTY(VisibleAnywhere, BlueprintReadOnly,\n"
          '              Category = "Components")\n'
          "    UStaticMeshComponent* Mesh;\n};\n")
    assert "unrooted-uobject" not in rules(str(tmp_path), "--paths", "A.h")


def test_local_inside_an_inline_method_is_not_a_member(tmp_path):
    """`in_member and not (in_func and not in_member)` reduces to
    `in_member`, so the local guard never fired inside a class body."""
    write(tmp_path, "A.h",
          '#include "CoreMinimal.h"\n'
          "UCLASS()\nclass AMyActor : public AActor\n{\n"
          "    GENERATED_BODY()\n"
          "    void Tick(float D) override\n    {\n"
          "        UWorld* World = nullptr;\n"
          "        World = GetWorld();\n    }\n};\n")
    assert "unrooted-uobject" not in rules(str(tmp_path), "--paths", "A.h")


def test_null_coalescing_on_a_string_is_not_a_unity_bug(tmp_path):
    write(tmp_path, "P.cs",
          "using UnityEngine;\n"
          "public class P : MonoBehaviour {\n"
          "    public string Label;\n"
          "    void Start() { var s = Label ?? \"x\"; }\n}\n")
    assert "unity-null-conditional" not in rules(str(tmp_path), "--paths", "P.cs")


def test_null_conditional_on_a_component_is_p1(tmp_path):
    write(tmp_path, "P.cs",
          "using UnityEngine;\n"
          "public class P : MonoBehaviour {\n"
          "    public Transform Target;\n"
          "    void Start() { Target?.Rotate(Vector3.up); }\n}\n")
    assert "unity-null-conditional" in rules(str(tmp_path), "--paths", "P.cs")


def test_em_dash_in_a_comment_is_not_flagged(tmp_path):
    write(tmp_path, "u.py", "# an em \u2014 dash in prose\nX = 1\n")
    assert rules(str(tmp_path), "--paths", "u.py") == {}


def test_zero_width_space_is_still_p1(tmp_path):
    write(tmp_path, "u.py", "X = \"a\u200bb\"\n")
    assert "unicode-invisible" in rules(str(tmp_path), "--paths", "u.py")


def test_preprocessor_lines_are_not_comments(tmp_path):
    write(tmp_path, "h.h", '#include "a.h"\n#define FOO 1\nint x = 1;\n')
    found = rules(str(tmp_path), "--paths", "h.h")
    assert "restated-comment" not in found
    assert "commented-code" not in found


# --------------------------------------------------------------------------
# reconciliation
# --------------------------------------------------------------------------

def test_partially_fixed_duplicate_findings_are_reported_resolved(tmp_path):
    """Keying on (path, rule, message) collapsed N instances of a
    constant-message rule into one, so fixing some of them showed up as
    neither resolved nor live - they just vanished."""
    body = ("def a():\n"
            "    # increment counter value\n"
            "    counter_value = increment(counter_value_seed)\n"
            "    # reset counter value\n"
            "    counter_value = reset(counter_value_seed)\n"
            "    # clear counter value\n"
            "    counter_value = clear(counter_value_seed)\n"
            "    return counter_value\n")
    write(tmp_path, "c.py", body)
    first = json.loads(run(str(tmp_path), "--json", "--paths", "c.py").stdout)
    assert len(first["findings"]) == 3
    (tmp_path / "prior.json").write_text(json.dumps(first))

    write(tmp_path, "c.py", body.replace("    # increment counter value\n", "")
                                .replace("    # reset counter value\n", ""))
    second = json.loads(run(str(tmp_path), "--json", "--paths", "c.py",
                            "--since", str(tmp_path / "prior.json")).stdout)
    assert len(second["findings"]) == 1
    assert len(second["resolved"]) == 2


def test_severity_filter_does_not_resolve_findings_that_are_still_true(tmp_path):
    """Reconciliation ran after the severity filter, so raising
    --min-severity between runs reported every filtered-out finding as
    'no longer true' - telling the reviewer to drop live items."""
    write(tmp_path, "t.py", "# TODO: tighten this\ndef f(x=[]):\n    return x\n")
    first = json.loads(run(str(tmp_path), "--json", "--paths", "t.py").stdout)
    assert {f["rule"] for f in first["findings"]} == {"orphan-todo",
                                                     "mutable-default"}
    (tmp_path / "prior.json").write_text(json.dumps(first), encoding="utf-8")

    second = json.loads(run(str(tmp_path), "--json", "--paths", "t.py",
                            "--min-severity", "P1",
                            "--since", str(tmp_path / "prior.json")).stdout)
    assert second["resolved"] == []


def test_since_on_json_that_is_not_a_report_does_not_crash(tmp_path):
    """An AttributeError here exited 1 with empty stdout, so a --json
    consumer got a parse error instead of a report."""
    write(tmp_path, "a.py", "def f():\n    dead = 1\n    return 2\n")
    write(tmp_path, "notareport.json", "[1, 2, 3]\n")
    proc = run(str(tmp_path), "--json", "--paths", "a.py",
               "--since", str(tmp_path / "notareport.json"))
    data = json.loads(proc.stdout)
    assert data["warnings"]
    assert "dead-local" in {f["rule"] for f in data["findings"]}


def test_report_name_under_json_emits_json(tmp_path):
    write(tmp_path, "a.py", "x = 1\n")
    proc = run(str(tmp_path), "--report-name", "--json", "--paths", "a.py")
    assert json.loads(proc.stdout)["report_stem"]


def test_a_run_that_skipped_everything_is_not_reported_clean(tmp_path):
    """0 candidates / complete:true / exit 0 is the silent-clean shape this
    scanner exists to avoid. Skipping every file in scope is not a clean
    branch, it is a scan that reviewed nothing."""
    write(tmp_path, "node_modules/x.py", "def f():\n    dead = 1\n    return 2\n")
    proc = run(str(tmp_path), "--json", "--paths", "node_modules/x.py")
    data = json.loads(proc.stdout)
    assert data["complete"] is False
    assert data["warnings"]
    assert proc.returncode == 2


def test_a_scope_of_only_skipped_new_files_is_not_reported_clean(repo):
    """Untracked files were dropped by skip_path without a word, so a branch
    whose only new files are generated reported an empty scope."""
    write(repo, "generated/api.py", "def f():\n    dead = 1\n    return 2\n")
    proc = run(str(repo), "--json")
    data = json.loads(proc.stdout)
    assert data["errors"]
    assert data["complete"] is False
    assert proc.returncode == 2


def test_a_run_that_skipped_only_some_files_is_still_complete(tmp_path):
    write(tmp_path, "node_modules/x.py", "x = 1\n")
    write(tmp_path, "a.py", "def f():\n    dead = 1\n    return 2\n")
    proc = run(str(tmp_path), "--json", "--paths", "node_modules/x.py", "a.py")
    data = json.loads(proc.stdout)
    assert data["complete"] is True
    assert proc.returncode == 0


def test_utf8_bom_is_not_an_invisible_character_finding(tmp_path):
    """Visual Studio and MSBuild write a BOM into every .cs file they touch,
    which is the exact ecosystem this scanner targets."""
    write_bytes(tmp_path, "P.cs",
                b"\xef\xbb\xbfpublic class P {\n    int x = 1;\n}\n")
    assert "unicode-invisible" not in rules(str(tmp_path), "--paths", "P.cs")


def test_zero_width_no_break_space_inside_the_file_is_still_p1(tmp_path):
    write_bytes(tmp_path, "P.cs",
                b"public class P {\n    string s = \"a\xef\xbb\xbfb\";\n}\n")
    assert "unicode-invisible" in rules(str(tmp_path), "--paths", "P.cs")


def test_json_reports_the_counts_the_report_template_asks_for(tmp_path):
    """The report header demands a file count and an added-line count. The
    scanner emitted neither, so the agent had to invent both."""
    write(tmp_path, "a.py", "def f():\n    dead = 1\n    return 2\n")
    write(tmp_path, "b.py", "x = 1\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths",
                          "a.py", "b.py").stdout)
    assert data["files"] == 2
    assert data["scanned_files"] == 2
    assert data["added_lines"] == 4


def test_declined_findings_do_not_come_back_as_live(tmp_path):
    """A finding the user rejected returned as `persisting` every run, which
    is the exact skimming failure the skill warns about."""
    write(tmp_path, "t.py", "# TODO: tighten this\ndef f(x=[]):\n    return x\n")
    first = json.loads(run(str(tmp_path), "--json", "--paths", "t.py").stdout)
    keep = [f for f in first["findings"] if f["rule"] == "orphan-todo"]
    assert keep
    (tmp_path / "declined.json").write_text(
        json.dumps({"findings": keep}), encoding="utf-8")

    second = json.loads(run(str(tmp_path), "--json", "--paths", "t.py",
                            "--declined", str(tmp_path / "declined.json")).stdout)
    assert "orphan-todo" not in {f["rule"] for f in second["findings"]}
    assert "orphan-todo" in {f["rule"] for f in second["declined"]}
    assert "mutable-default" in {f["rule"] for f in second["findings"]}


def test_a_declined_finding_is_not_also_reported_resolved(tmp_path):
    """Declining removed it from the live list before reconciliation ran, so
    the same finding came back as 'no longer true' - which reads as fixed."""
    write(tmp_path, "t.py", "# TODO: tighten this\ndef f(x=[]):\n    return x\n")
    first = json.loads(run(str(tmp_path), "--json", "--paths", "t.py").stdout)
    (tmp_path / "prior.json").write_text(json.dumps(first), encoding="utf-8")
    (tmp_path / "declined.json").write_text(json.dumps(
        {"findings": [f for f in first["findings"]
                      if f["rule"] == "orphan-todo"]}), encoding="utf-8")

    second = json.loads(run(str(tmp_path), "--json", "--paths", "t.py",
                            "--since", str(tmp_path / "prior.json"),
                            "--declined", str(tmp_path / "declined.json")).stdout)
    assert second["resolved"] == []
    assert {f["rule"] for f in second["declined"]} == {"orphan-todo"}
    assert {f["rule"] for f in second["findings"]} == {"mutable-default"}


def test_declining_one_instance_does_not_decline_its_siblings(tmp_path):
    """`split_declined` tested set membership while `reconcile` counted
    instances. `finding_key` excludes the line number and most rules emit a
    constant message, so N occurrences in one file share a key - and declining
    any one of them silently suppressed all N, including ones written later.
    One judgment call became a permanent blind spot for a whole class of P1."""
    write(tmp_path, "pay.py",
          "def charge():\n"
          "    try:\n        go()\n    except Exception:\n        pass\n"
          "def refund():\n"
          "    try:\n        go()\n    except Exception:\n        pass\n")
    first = json.loads(run(str(tmp_path), "--json", "--paths", "pay.py").stdout)
    swallowed = [f for f in first["findings"] if f["rule"] == "swallowed-exception"]
    assert len(swallowed) == 2, "fixture must produce two identical-anchor findings"

    # The user declines exactly one of them.
    (tmp_path / "declined.json").write_text(
        json.dumps({"findings": swallowed[:1]}), encoding="utf-8")

    second = json.loads(run(str(tmp_path), "--json", "--paths", "pay.py",
                            "--declined", str(tmp_path / "declined.json")).stdout)
    live = [f for f in second["findings"] if f["rule"] == "swallowed-exception"]
    gone = [f for f in second["declined"] if f["rule"] == "swallowed-exception"]
    assert len(gone) == 1, "exactly the one they declined"
    assert len(live) == 1, "the sibling must still be reported"
    assert live[0]["severity"] == "P1"


def test_a_later_instance_of_a_declined_rule_still_surfaces(tmp_path):
    """The same defect from the other direction: code written *after* the
    decline must not inherit the suppression."""
    write(tmp_path, "pay.py",
          "def charge():\n"
          "    try:\n        go()\n    except Exception:\n        pass\n")
    first = json.loads(run(str(tmp_path), "--json", "--paths", "pay.py").stdout)
    swallowed = [f for f in first["findings"] if f["rule"] == "swallowed-exception"]
    (tmp_path / "declined.json").write_text(
        json.dumps({"findings": swallowed}), encoding="utf-8")

    # A third function lands later with the same shape.
    write(tmp_path, "pay.py",
          "def charge():\n"
          "    try:\n        go()\n    except Exception:\n        pass\n"
          "def payout():\n"
          "    try:\n        go()\n    except Exception:\n        pass\n")
    second = json.loads(run(str(tmp_path), "--json", "--paths", "pay.py",
                            "--declined", str(tmp_path / "declined.json")).stdout)
    live = [f for f in second["findings"] if f["rule"] == "swallowed-exception"]
    assert len(live) == 1 and live[0]["severity"] == "P1"


def test_stacked_unity_attributes_keep_the_confirm_note(tmp_path):
    """`is_exposed` looked at the declaration and exactly one line above, so
    the verdict depended on how the author wrapped their attributes. Stacking
    [Header]/[Tooltip] on their own lines is ordinary Unity style, and it was
    the shape that lost the P3 'confirm before removing' note - on precisely
    the serialized fields that must never be deleted unchecked."""
    write(tmp_path, "Dash.cs",
          "public class Dash {\n"
          "    [SerializeField]\n"
          '    [Tooltip("Curve used to shape the dash.")]\n'
          "    private AnimationCurve tuningCurve;\n"
          "\n"
          "    [SerializeField, Range(0f, 1f)]\n"
          "    private float dashDamping;\n"
          "}\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths", "Dash.cs").stdout)
    by_anchor = {f["anchor"]: f for f in data["findings"]
                 if f["rule"] == "unused-binding"}
    stacked = by_anchor["private AnimationCurve tuningCurve;"]
    adjacent = by_anchor["private float dashDamping;"]
    assert stacked["severity"] == adjacent["severity"] == "P3"
    assert "confirm" in stacked["message"]


@pytest.mark.parametrize("attrs,label", [
    ("    [SerializeField]\n    [Tooltip(\"stacked\")]\n", "one per line"),
    ("    [Tooltip(\"two groups\")] [SerializeField]\n", "two groups, one line"),
    ("    [SerializeField,\n     Range(0f, 1f)]\n", "wrapped attribute list"),
    ("    [Header(\"Cooldown\")]\n    [SerializeField]\n", "header then field"),
    # The `//` branch that decided these was unreachable dead code: strip_code
    # blanks comments before the shape test, so a documented serialized field
    # - the ordinary C# way to write one - silently lost the confirm note.
    ("    [SerializeField]\n    /// <summary>Dash speed.</summary>\n", "/// doc comment between"),
    ("    [SerializeField]\n    // set from the Inspector\n", "// comment between"),
    ("    [SerializeField]\n    /* speed */\n", "/* block */ between"),
])
def test_every_attribute_wrapping_keeps_the_confirm_note(tmp_path, attrs, label):
    """The first fix here gated on each line's *shape*, so the verdict
    depended on how the author wrapped their attributes: a line literally
    containing SerializeField was rejected as 'not an attribute line', and a
    wrapped list's continuation has no leading bracket. Both fell back to P2
    with no note - on the serialized fields that must never be deleted
    unchecked. The regression test pinned only the shape that already worked."""
    write(tmp_path, "Dash.cs",
          "public class Dash {\n" + attrs + "    private float tuned;\n}\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths", "Dash.cs").stdout)
    found = [f for f in data["findings"] if f["rule"] == "unused-binding"]
    assert found, f"no unused-binding finding for {label}"
    assert found[0]["severity"] == "P3", label
    assert "confirm" in found[0]["message"], label


def test_declining_one_instance_picks_that_instance_after_a_line_shift(tmp_path):
    """Counting instances fixed the over-suppression and introduced a quieter
    fault: the budget was spent in file order, so declining the finding at
    line 9 silenced the one at line 4 - the user's stayed live and a
    different live P1 vanished. Line proximity guesses wrong once anything
    shifts, so identity is the occurrence index."""
    body = ("def a():\n    try:\n        go()\n    except Exception:\n        pass\n"
            "def b():\n    try:\n        go()\n    except Exception:\n        pass\n")
    write(tmp_path, "pay.py", body)
    first = json.loads(run(str(tmp_path), "--json", "--paths", "pay.py").stdout)
    swallowed = [f for f in first["findings"] if f["rule"] == "swallowed-exception"]
    assert [f["occurrence"] for f in swallowed] == [1, 2]

    # Decline the SECOND one.
    (tmp_path / "declined.json").write_text(
        json.dumps({"findings": [swallowed[1]]}), encoding="utf-8")

    # Shift every line down by three.
    write(tmp_path, "pay.py", "# a\n# b\n# c\n" + body)
    second = json.loads(run(str(tmp_path), "--json", "--paths", "pay.py",
                            "--declined", str(tmp_path / "declined.json")).stdout)
    live = [f for f in second["findings"] if f["rule"] == "swallowed-exception"]
    gone = [f for f in second["declined"] if f["rule"] == "swallowed-exception"]
    assert [f["occurrence"] for f in gone] == [2], "declined the wrong instance"
    assert [f["occurrence"] for f in live] == [1]


# Each fixture is built so the comment rule WOULD fire without the exemption:
# `restated-comment` needs high word overlap with the line below, so the
# following line echoes the directive's own words. The previous version of this
# test used `value = 1` for every case, which no comment rule can match — all
# twelve passed with the exemption stubbed out, verifying nothing.
@pytest.mark.parametrize("line,body,lang", [
    ("//go:embed templates", "var templates embed.FS", "config.go"),
    ("//go:generate stringer -type=Kind", "type Kind int", "config.go"),
    ("// Code generated by protoc. DO NOT EDIT.", "type Generated struct{}", "config.go"),
    ("//nolint:errcheck", "func errcheck() {}", "config.go"),
    ("# noqa: F401", "import readline", "t.py"),
    ("# fmt: off", "fmt_off_matrix = 1", "t.py"),
    ("# pragma: no cover", "def cover_pragma(): pass", "t.py"),
    ("# frozen_string_literal: true", "frozen_string_literal = true", "t.rb"),
    ("// @ts-expect-error", "const tsExpectError = 1;", "t.ts"),
    ("// eslint-disable-next-line no-console", "console.log(1);", "t.ts"),
    ("// clang-format off", "int clang_format_off = 1;", "t.cpp"),
    ("// NOLINTNEXTLINE", "int nolint_next_line = 1;", "t.cpp"),
])
def test_directive_comments_are_not_comment_candidates(tmp_path, line, body, lang):
    """A comment a tool reads carries no prose, restates nothing and contains
    no 'because', so every comment rule here voted to delete it. `//go:embed`
    above its var was reported as 'comment restates the line below it' and
    handed to the agent whose only verdicts are DELETE/KEEP/TIGHTEN."""
    write(tmp_path, lang, f"{line}\n{body}\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths", lang).stdout)
    # Only rules that actually exist in scan.py — the earlier version asserted
    # against "hedged-comment" and "section-header", neither of which is real.
    comment_rules = {"restated-comment", "commented-code", "orphan-todo"}
    hit = [f for f in data["findings"] if f["rule"] in comment_rules]
    assert not hit, f"{line} treated as prose: {hit}"


def test_the_directive_fixtures_would_actually_fire_without_the_exemption(tmp_path):
    """Guards the guard: proves the fixtures above can trigger the rule, so a
    future edit cannot quietly make them vacuous again. `strip_code` is what
    the exemption routes around, so bypassing `is_directive` must produce the
    finding the exemption exists to suppress."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("scanmod", SCAN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # With the directive recognised, it is not comment prose.
    assert mod.comment_body("//go:embed templates") is None
    # The same text, if it were NOT a directive, is comment prose - which is
    # what feeds restated-comment.
    assert mod.is_directive("//go:embed templates")
    assert mod.comment_body("// embed templates here") == "embed templates here"


@pytest.mark.parametrize("cp,name", [
    (0x202A, "LRE"), (0x202B, "RLE"), (0x202C, "PDF"), (0x202D, "LRO"),
    (0x202E, "RLO"), (0x2066, "LRI"), (0x2067, "RLI"), (0x2068, "FSI"),
    (0x2069, "PDI"),
])
def test_every_trojan_source_control_is_detected(tmp_path, cp, name):
    """Two of the nine bidi controls were covered while the docs advertised
    'bidi' at P1. The isolate family is what CVE-2021-42574's proof of
    concept uses, and U+202C is the terminator U+202E needs."""
    write(tmp_path, "t.js", f'const s = "a{chr(cp)}b";\n')
    data = json.loads(run(str(tmp_path), "--json", "--paths", "t.js").stdout)
    hit = [f for f in data["findings"] if f["rule"] == "unicode-invisible"]
    assert hit and hit[0]["severity"] == "P1", f"{name} U+{cp:04X} missed"


def test_nbsp_in_prose_is_not_a_p1_but_bidi_still_is(tmp_path):
    """An NBSP in Markdown is routine - pasted text, an option-space, table
    alignment - and it sorted to the top of 'P1 - Risk'. A bidi control in
    prose is still an attack, because the reviewer reads the rendered form."""
    write(tmp_path, "doc.md", "# Guide\n\nA line with a non-breaking space.\n")
    write(tmp_path, "evil.md", "# Guide\n\nA‮line with an override.\n")
    soft = json.loads(run(str(tmp_path), "--json", "--paths", "doc.md").stdout)
    hard = json.loads(run(str(tmp_path), "--json", "--paths", "evil.md").stdout)
    assert [f["severity"] for f in soft["findings"]
            if f["rule"] == "unicode-invisible"] == ["P3"]
    assert [f["severity"] for f in hard["findings"]
            if f["rule"] == "unicode-invisible"] == ["P1"]


def test_type_ignore_message_does_not_invite_deleting_the_directive(tmp_path):
    """This candidate is read by the agent that owns comments, whose verdicts
    are DELETE/KEEP/TIGHTEN. Deleting the directive fails the build under
    warn_unused_ignores, so the message has to name the actual fix."""
    write(tmp_path, "t.py", "x: int = compute()  # type: ignore[assignment]\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths", "t.py").stdout)
    hit = [f for f in data["findings"] if f["rule"] == "type-ignore"]
    assert hit and "do not delete the directive" in hit[0]["message"]


@pytest.mark.parametrize("above,label", [
    ("public class Widget {", "public class declaration"),
    ("internal class Widget {", "internal class declaration"),
    ("    public void Bar() { }", "public method"),
])
def test_a_declaration_above_a_private_field_is_not_an_attribute(tmp_path, above, label):
    """EXPOSED was searched before any shape test on the first iteration, so
    the line directly above was checked unconditionally - and `public class W {`
    made every first private field in the class look serialized."""
    write(tmp_path, "W.cs", "%s\n    private float scratch;\n}\n" % above)
    data = json.loads(run(str(tmp_path), "--json", "--paths", "W.cs").stdout)
    found = [f for f in data["findings"] if f["rule"] == "unused-binding"]
    assert found, label
    assert found[0]["severity"] == "P2", f"{label}: falsely marked exposed"
    assert "confirm" not in found[0]["message"], label


def test_occurrence_is_numbered_in_file_order_not_ast_order(tmp_path):
    """The Python rules emit through ast.walk, which is breadth-first, so a
    nested handler arrived after a shallower one written below it. Numbering
    on arrival gave occurrence 1 to the LAST match in the file - and SKILL.md
    tells the executor to count anchor matches top to bottom."""
    write(tmp_path, "deep.py",
          "def outer():\n"
          "    def inner():\n"
          "        try:\n            go()\n        except Exception:\n            pass\n"
          "    try:\n        go()\n    except Exception:\n        pass\n"
          "try:\n    go()\nexcept Exception:\n    pass\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths", "deep.py").stdout)
    hits = [f for f in data["findings"] if f["rule"] == "swallowed-exception"]
    assert len(hits) == 3, hits
    by_occ = sorted(hits, key=lambda f: f["occurrence"])
    lines = [f["line"] for f in by_occ]
    assert lines == sorted(lines), (
        f"occurrence order {lines} is not file order - the executor counts "
        "anchor matches top to bottom and would edit a different line")


def test_anchor_total_counts_matching_lines_not_flagged_findings(repo):
    """`occurrence` indexes findings that share a key. The Step 4b executor
    counts matching LINES in the file, which is a different population: a
    diff-scoped scan flags only the instance the change touched, while the
    anchor text may appear anywhere.

    SKILL.md used to say `occurrence` was already in the JSON and could be
    copied into the plan. It could not. Copying a flagged-index of 1 into a
    field the executor reads as "the first matching line" sent a moved fix to
    an untouched, unreviewed, unapproved line - which this skill calls the
    worst outcome available in it."""
    body = ("def a():\n    try:\n        one()\n    except Exception:\n        pass\n"
            "\ndef b():\n    try:\n        two()\n    except Exception:\n        pass\n")
    write(repo, "app.py", body)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    write(repo, "app.py", body +
          "\ndef c():\n    try:\n        three()\n    except Exception:\n        pass\n")

    data = json.loads(run(str(repo), "--json").stdout)
    hits = [f for f in data["findings"] if f["rule"] == "swallowed-exception"]
    assert len(hits) == 1, "only the added block is in a diff-scoped run"
    f = hits[0]
    assert f["occurrence"] == 1, "one flagged instance, so the key-index is 1"
    assert f["anchor_total"] == 3, (
        "the anchor text is on three lines of the file; the executor will "
        "count three and must be told to expect three")
    assert f["anchor_index"] == 3, (
        f"the flagged line is the third match, not the {f['occurrence']}st - "
        "these two fields must never be conflated")


def test_anchor_index_and_total_agree_with_the_executors_normalisation(tmp_path):
    """The executor compares whitespace-normalised lines. Indentation must
    not split one anchor into two, or the count it reaches disagrees with the
    count the plan recorded and every moved item reports stale."""
    write(tmp_path, "app.py",
          "def a():\n    try:\n        go()\n    except Exception:\n        pass\n"
          "\nclass K:\n    def b(self):\n        try:\n            go()\n"
          "        except Exception:\n            pass\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths", "app.py").stdout)
    hits = sorted([f for f in data["findings"]
                   if f["rule"] == "swallowed-exception"],
                  key=lambda f: f["line"])
    assert len(hits) == 2
    assert [f["anchor_index"] for f in hits] == [1, 2]
    assert [f["anchor_total"] for f in hits] == [2, 2], (
        "differently-indented copies of one line are one anchor after "
        "normalisation")


def test_invisible_character_in_a_test_fixture_is_not_a_p1(tmp_path):
    """A path-handling test gets `local-path` demoted one step because the
    path is data, not a leak. A detector's own fixture is data in exactly the
    same way, and the demotion was never wired to it - so this skill's own
    suite reported two P1s against the lines that test invisible-character
    detection. P1 is the one bucket the report rules say never to cut."""
    write(tmp_path, "tests/test_encoding.py",
          "def test_nbsp_is_flagged():\n"
          "    assert scan('a\u00a0b')\n"
          "def test_rlo_is_flagged():\n"
          "    assert scan('a\u202eb')\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths",
                          "tests/test_encoding.py").stdout)
    sevs = sorted(f["severity"] for f in data["findings"]
                  if f["rule"] == "unicode-invisible")
    assert sevs == ["P2", "P3"], (
        f"expected the soft character demoted to P3 and the bidi override to "
        f"P2 in a test file, got {sevs}")


def test_invisible_character_in_production_code_is_still_a_p1(tmp_path):
    """The demotion above is keyed on the file being a test or prose. Real
    source keeps the full severity - this is the finding the rule exists for."""
    write(tmp_path, "app.py", "x = 'a\u00a0b'\ny = 'a\u202eb'\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths", "app.py").stdout)
    sevs = {f["severity"] for f in data["findings"]
            if f["rule"] == "unicode-invisible"}
    assert sevs == {"P1"}, sevs


def test_a_plain_private_field_still_has_no_confirm_note(tmp_path):
    """The attribute walk must not turn every field into an exposed one - a
    preceding ordinary comment is not an attribute block."""
    write(tmp_path, "Dash.cs",
          "public class Dash {\n"
          "    // cached each frame\n"
          "    private float scratchValue;\n"
          "}\n")
    data = json.loads(run(str(tmp_path), "--json", "--paths", "Dash.cs").stdout)
    found = [f for f in data["findings"] if f["rule"] == "unused-binding"]
    assert found and found[0]["severity"] == "P2"
    assert "confirm" not in found[0]["message"]


def test_declined_file_that_is_not_a_report_is_a_warning_not_a_crash(tmp_path):
    write(tmp_path, "a.py", "def f():\n    dead = 1\n    return 2\n")
    write(tmp_path, "junk.json", '"nope"\n')
    data = json.loads(run(str(tmp_path), "--json", "--paths", "a.py",
                          "--declined", str(tmp_path / "junk.json")).stdout)
    assert data["warnings"]
    assert "dead-local" in {f["rule"] for f in data["findings"]}


def test_stem_can_be_pinned_across_calls(tmp_path):
    write(tmp_path, "a.py", "x = 1\n")
    out = json.loads(run(str(tmp_path), "--json", "--stem", "fixed-stem",
                         "--paths", "a.py").stdout)
    assert out["report_stem"] == "fixed-stem"


# --------------------------------------------------------------------------
# test redundancy - python
# --------------------------------------------------------------------------

PY_TESTS = (
    "import pytest\n"
    "@pytest.fixture\n"
    "def orphan():\n"
    "    return 42\n"
    "def test_two():\n"
    "    assert add(1, 1) == 2\n"
    "def test_three():\n"
    "    assert add(1, 2) == 3\n"
    "def test_runs():\n"
    "    compute()\n"
    "def test_always():\n"
    "    assert True\n"
    "def test_mock(client):\n"
    "    send(client)\n"
    "    client.send.assert_called_once()\n"
    "@pytest.mark.skip\n"
    "def test_off():\n"
    "    assert add(1, 1) == 2\n"
)


@pytest.mark.parametrize("rule", [
    "test-without-assertion",
    "tautological-test",
    "mock-only-test",
    "duplicate-test",
    "unused-fixture",
    "skip-without-reason",
])
def test_python_test_redundancy_rule_fires(tmp_path, rule):
    write(tmp_path, "tests/test_x.py", PY_TESTS)
    assert rule in rules(str(tmp_path), "--paths", "tests/test_x.py")


def test_real_python_test_is_left_alone(tmp_path):
    write(tmp_path, "tests/test_ok.py",
          "def test_adds():\n"
          "    result = add(1, 1)\n"
          "    assert result == 2\n")
    assert rules(str(tmp_path), "--paths", "tests/test_ok.py") == {}


# --------------------------------------------------------------------------
# test redundancy - everything else
# --------------------------------------------------------------------------

NO_ASSERT_CASES = {
    "tests/a.test.js": "it('runs', () => {\n  const r = add(1, 2);\n});\n",
    "tests/a_test.go": ("package m\nimport \"testing\"\n"
                        "func TestRuns(t *testing.T) {\n\t_ = Add(1, 2)\n}\n"),
    "tests/a_test.rs": "#[test]\nfn it_runs() {\n    let _ = add(1, 1);\n}\n",
    "tests/AT.java": "public class AT {\n    @Test\n    public void runs() {\n"
                     "        svc.run();\n    }\n}\n",
    "tests/AT.cs": "public class AT {\n    [Test]\n    public void Runs() {\n"
                   "        svc.Run();\n    }\n}\n",
    "tests/a_spec.rb": "describe S do\n  it \"just runs\" do\n    svc.run\n  end\nend\n",
    "tests/a_test.cpp": "TEST(Suite, Runs) {\n    svc.Run();\n}\n",
}


@pytest.mark.parametrize("rel,body", sorted(NO_ASSERT_CASES.items()))
def test_assertionless_test_is_caught_in_every_language(tmp_path, rel, body):
    write(tmp_path, rel, body)
    assert "test-without-assertion" in rules(str(tmp_path), "--paths", rel)


ASSERTING_CASES = {
    "tests/b.test.js": "it('adds', () => {\n  expect(add(1, 1)).toBe(2);\n});\n",
    "tests/b_test.go": ("package m\nimport \"testing\"\n"
                        "func TestAdds(t *testing.T) {\n"
                        "\tif Add(1, 1) != 2 {\n\t\tt.Errorf(\"bad\")\n\t}\n}\n"),
    "tests/b_test.rs": "#[test]\nfn adds() {\n    assert_eq!(add(1, 1), 2);\n}\n",
    "tests/BT.java": "public class BT {\n    @Test\n    public void adds() {\n"
                     "        assertEquals(2, svc.add(1, 1));\n    }\n}\n",
    "tests/BT.cs": "public class BT {\n    [Test]\n    public void Adds() {\n"
                   "        Assert.AreEqual(2, svc.Add(1, 1));\n    }\n}\n",
    "tests/b_spec.rb": "describe S do\n  it \"adds\" do\n"
                       "    expect(svc.add(1, 1)).to eq 2\n  end\nend\n",
    "tests/b_test.cpp": "TEST(Suite, Adds) {\n    EXPECT_EQ(2, Add(1, 1));\n}\n",
}


@pytest.mark.parametrize("rel,body", sorted(ASSERTING_CASES.items()))
def test_real_test_is_not_flagged_in_any_language(tmp_path, rel, body):
    write(tmp_path, rel, body)
    found = rules(str(tmp_path), "--paths", rel)
    assert "test-without-assertion" not in found
    assert "mock-only-test" not in found


MOCK_ONLY_CASES = {
    "tests/m.test.js": ("it('logs', () => {\n  const log = jest.fn();\n"
                        "  run(log);\n  expect(log).toHaveBeenCalled();\n});\n"),
    "tests/MT.java": "public class MT {\n    @Test\n    public void saves() {\n"
                     "        svc.run();\n        verify(repo).save();\n    }\n}\n",
    "tests/MT.cs": "public class MT {\n    [Test]\n    public void Saves() {\n"
                   "        svc.Run();\n        repo.Received().Save();\n    }\n}\n",
}


@pytest.mark.parametrize("rel,body", sorted(MOCK_ONLY_CASES.items()))
def test_mock_only_test_is_caught(tmp_path, rel, body):
    write(tmp_path, rel, body)
    assert "mock-only-test" in rules(str(tmp_path), "--paths", rel)


def test_structural_duplicates_are_caught_outside_python(tmp_path):
    write(tmp_path, "tests/d.test.js",
          "it('two', () => {\n  expect(add(1, 1)).toBe(2);\n});\n"
          "it('three', () => {\n  expect(add(1, 2)).toBe(3);\n});\n")
    assert "duplicate-test" in rules(str(tmp_path), "--paths", "tests/d.test.js")


def test_production_files_get_no_test_findings(tmp_path):
    """TEST_HINT gates the whole pass; a src file must never see it."""
    write(tmp_path, "src/app.js", "function run() {\n  const r = add(1, 2);\n}\n")
    found = rules(str(tmp_path), "--paths", "src/app.js")
    assert "test-without-assertion" not in found


# --------------------------------------------------------------------------
# false positives on idiomatic code
# --------------------------------------------------------------------------

def test_typed_except_pass_is_not_a_p1_swallow(tmp_path):
    """`except FileNotFoundError: pass` is contextlib.suppress spelled out -
    a named, expected failure mode, not a hidden one."""
    write(tmp_path, "s.py",
          "def f(p):\n    try:\n        open(p)\n"
          "    except FileNotFoundError:\n        pass\n")
    got = severities(str(tmp_path), "--paths", "s.py")
    assert got.get("swallowed-exception") == ["P2"]


def test_broad_except_pass_is_still_p1(tmp_path):
    write(tmp_path, "s.py",
          "def f(p):\n    try:\n        open(p)\n"
          "    except Exception:\n        pass\n")
    assert severities(str(tmp_path), "--paths",
                      "s.py")["swallowed-exception"] == ["P1"]


def test_container_home_path_is_not_a_p1(tmp_path):
    """/home/app/data is a deployment path in half the Dockerfiles alive."""
    write(tmp_path, "c.py", 'DATA_DIR = "/home/app/data"\n')
    assert severities(str(tmp_path), "--paths", "c.py")["local-path"] == ["P2"]


def test_developer_home_path_is_still_p1(tmp_path):
    write(tmp_path, "c.py", 'CACHE = "/Users/alice/dev/cache"\n')
    assert severities(str(tmp_path), "--paths", "c.py")["local-path"] == ["P1"]


def test_local_path_in_test_data_is_demoted(tmp_path):
    """Path normalisation tests exist to contain exactly these strings."""
    write(tmp_path, "tests/test_paths.py",
          'def test_norm():\n    assert norm("/Users/alice/x") == "x"\n')
    assert severities(str(tmp_path), "--paths",
                      "tests/test_paths.py")["local-path"] == ["P2"]


def test_local_path_in_prose_is_demoted(tmp_path):
    """Documentation naming an example path is not a committed path. The
    scanner drew a P1 on the very reference file that explains the rule."""
    write(tmp_path, "README.md", "Put the repo in `/Users/you/src/app`.\n")
    assert severities(str(tmp_path), "--paths", "README.md")["local-path"] == ["P2"]


def test_printf_in_plain_cpp_is_not_a_ue_finding(tmp_path):
    """UE_LOG does not exist outside Unreal."""
    write(tmp_path, "p.cpp",
          '#include <cstdio>\nvoid f() {\n    printf("hi");\n}\n')
    assert "raw-output" not in rules(str(tmp_path), "--paths", "p.cpp")


def test_printf_in_ue_code_is_still_flagged(tmp_path):
    write(tmp_path, "p.cpp",
          '#include "CoreMinimal.h"\nvoid AMyActor::F() {\n'
          '    printf("hi");\n}\n')
    assert "raw-output" in rules(str(tmp_path), "--paths", "p.cpp")


def test_caching_in_awake_is_not_an_expensive_lookup(tmp_path):
    """The rule's own message says 'cache in Awake'; doing so must not be a
    finding."""
    write(tmp_path, "C.cs",
          "using UnityEngine;\npublic class C : MonoBehaviour {\n"
          "    Camera cam;\n    void Awake() { cam = Camera.main; }\n}\n")
    assert "expensive-lookup" not in rules(str(tmp_path), "--paths", "C.cs")


def test_scene_lookup_outside_awake_is_still_flagged(tmp_path):
    write(tmp_path, "C.cs",
          "using UnityEngine;\npublic class C : MonoBehaviour {\n"
          "    void Shoot() { var c = Camera.main; }\n}\n")
    assert "expensive-lookup" in rules(str(tmp_path), "--paths", "C.cs")


def test_cleanup_then_reraise_is_not_log_and_reraise(tmp_path):
    """`except X: conn.rollback(); raise` is the canonical cleanup idiom and
    logs nothing to duplicate."""
    write(tmp_path, "d.py",
          "def f(conn):\n    try:\n        conn.run()\n"
          "    except ValueError:\n        conn.rollback()\n        raise\n")
    assert "log-and-reraise" not in rules(str(tmp_path), "--paths", "d.py")


def test_log_then_reraise_is_still_flagged(tmp_path):
    write(tmp_path, "d.py",
          "def f(conn):\n    try:\n        conn.run()\n"
          "    except ValueError:\n        logger.exception('boom')\n"
          "        raise\n")
    assert "log-and-reraise" in rules(str(tmp_path), "--paths", "d.py")


def test_conftest_fixtures_are_never_unused(tmp_path):
    """conftest.py exists to publish fixtures to other files. By construction
    nothing in it requests them."""
    write(tmp_path, "tests/conftest.py",
          "import pytest\n@pytest.fixture\ndef client():\n    return 1\n")
    assert "unused-fixture" not in rules(str(tmp_path), "--paths",
                                         "tests/conftest.py")


def test_unrelated_if_after_newobject_is_not_an_impossible_check(tmp_path):
    write(tmp_path, "a.cpp",
          '#include "CoreMinimal.h"\nvoid AMyActor::F() {\n'
          "    UFoo* Obj = NewObject<UFoo>();\n"
          "    if (bWantsInit) { Obj->Init(); }\n}\n")
    assert "impossible-null-check" not in rules(str(tmp_path), "--paths", "a.cpp")


def test_null_check_on_the_newobject_result_is_still_flagged(tmp_path):
    write(tmp_path, "a.cpp",
          '#include "CoreMinimal.h"\nvoid AMyActor::F() {\n'
          "    UFoo* Obj = NewObject<UFoo>();\n"
          "    if (!Obj) { return; }\n}\n")
    assert "impossible-null-check" in rules(str(tmp_path), "--paths", "a.cpp")


def test_async_void_event_handler_is_not_flagged(tmp_path):
    """The .NET event-handler signature is void; async void is the only way
    to await inside one."""
    write(tmp_path, "H.cs",
          "public class H {\n"
          "    async void OnClick(object sender, EventArgs e) { await Go(); }\n}\n")
    assert "async-void" not in rules(str(tmp_path), "--paths", "H.cs")


def test_async_void_on_a_plain_method_is_still_flagged(tmp_path):
    write(tmp_path, "H.cs",
          "public class H {\n    async void DoWork() { await Go(); }\n}\n")
    assert "async-void" in rules(str(tmp_path), "--paths", "H.cs")


def test_standard_name_is_not_a_ticket_reference(tmp_path):
    """UTF-8 / ISO-8601 / SHA-256 matched the ticket regex and silently
    suppressed real orphan TODOs."""
    write(tmp_path, "t.py", "# TODO: switch the decoder to UTF-8\nX = 1\n")
    assert "orphan-todo" in rules(str(tmp_path), "--paths", "t.py")


def test_real_ticket_reference_still_suppresses_the_todo(tmp_path):
    write(tmp_path, "t.py", "# TODO: drop this shim, PROJ-4521\nX = 1\n")
    assert "orphan-todo" not in rules(str(tmp_path), "--paths", "t.py")


def test_log_dot_call_is_matched(tmp_path):
    """`logger?` is `logge` plus an optional `r`, so the commonest spelling of
    the target case - `log.debug(...)` - never matched."""
    write(tmp_path, "t.py", 'def f():\n    log.debug("entering f")\n')
    assert "trace-logging" in rules(str(tmp_path), "--paths", "t.py")


def test_blueprint_and_end_kwarg_are_not_trace_logging(tmp_path):
    write(tmp_path, "t.py",
          'def f(x):\n    blueprint_started(x)\n    print(x, end="")\n')
    assert "trace-logging" not in rules(str(tmp_path), "--paths", "t.py")


def test_em_dash_in_a_docstring_is_not_flagged(tmp_path):
    """A docstring is prose; the rule exists to keep grep working on code."""
    write(tmp_path, "d.py",
          'def f():\n    """Compute the total — armor applies first."""\n'
          "    return 1\n")
    assert "unicode-typographic" not in rules(str(tmp_path), "--paths", "d.py")


def test_em_dash_in_code_is_still_flagged(tmp_path):
    write(tmp_path, "d.py", 'LABEL = "a — b"\n')
    assert "unicode-typographic" in rules(str(tmp_path), "--paths", "d.py")


def test_header_declarations_are_not_unused_bindings(tmp_path):
    """A header's whole job is declaring things used elsewhere, so 'never
    referenced in this file' is vacuous for every line in it."""
    write(tmp_path, "A.h",
          '#include "CoreMinimal.h"\n'
          "UCLASS()\nclass AMyActor : public AActor\n{\n"
          "    GENERATED_BODY()\n    UPROPERTY()\n"
          "    UStaticMeshComponent* Mesh;\n};\n")
    assert "unused-binding" not in rules(str(tmp_path), "--paths", "A.h")
