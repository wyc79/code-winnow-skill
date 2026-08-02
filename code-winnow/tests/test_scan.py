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
