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


def write(tmp_path, rel, body):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
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
