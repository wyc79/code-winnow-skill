"""The machine-readable judgment-pass contract.

`references/agent-prompts.md` is the single source of every prompt body. This
file guards the machinery that publishes it: the boundary markers in that
document, the structural metadata in `passes.json`, and `scripts/passes.py`,
which assembles the two into a dispatch-ready prompt.

Two properties make this a real guard rather than a copy that drifts, and both
follow the convention `test_workflow.py` already sets:

**Prompt text is never duplicated here.** Every expectation about a prompt body
is computed from `agent-prompts.md` at test time. A copy agrees with itself
forever.

**The locators are checked for staleness.** `passes.json` addresses spans of
prompt text by `find` string. A `find` that no longer matches stops locating
anything while every other test stays green - the same defect class
`check_mutations.py` exists to catch, so it gets the same treatment here.
"""

import io
import json
import os
import re
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
WINNOW = os.path.dirname(HERE)
PROMPTS_MD = os.path.join(WINNOW, "references", "agent-prompts.md")
PORTABILITY_MD = os.path.join(WINNOW, "references", "portability.md")
ROUND_README = os.path.join(WINNOW, "scaffold", "round", "README.md")
PASSES_JSON = os.path.join(WINNOW, "passes.json")
PASSES_PY = os.path.join(WINNOW, "scripts", "passes.py")

IDENTITY = (
    "Round:     07  —  .code-winnow/round-07/\n"
    "Compared:  feat-dash @ worktree   vs   main @ 69a5604   (branch scope)\n"
    "Generated: 2026-08-09 23:47"
)

# The six passes, in the order the pipeline dispatches them: S at Step 1, then
# A B C D E in parallel at Step 3.
PASS_IDS = ["S", "A", "B", "C", "D", "E"]

# The blocks every prompt carries in addition to its own. Three are blockquotes
# with their own headings; `scope-hunks` is the sentence in the file's intro
# that travels with the confirmed file list when a feature was named.
SHARED_IDS = ["writes", "staleness", "scope-rule", "scope-hunks"]

# `scope-list` is the one shared block with no marker: its content is the
# confirmed file and region list, which only the run knows.
INPUT_BLOCK_IDS = ["scope-list"]

# `scope-hunks` is also the one block marked inline, around a span of ordinary
# prose rather than around a blockquote. The two forms carry different
# obligations, so the tests below pin which ids they expect to find in each
# rather than iterating whatever turns up.
INLINE_IDS = ["scope-hunks"]

MARKER = re.compile(
    r"<!--\s*winnow:(?P<kind>prompt|shared)\s+id=(?P<id>[A-Za-z0-9-]+)\s+"
    r"(?P<edge>start|end)\s*-->"
)


def read(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def marker_sites():
    """Every marker with the line it sits on, sorted into its two forms.

    A marker with a line to itself brackets a blockquote; one embedded in a
    line of prose brackets a span inside that line.

    The `>` in the strip is what sorts a marker someone wrote *inside* the
    blockquote it brackets. That is a block marker in the wrong place and it has
    to arrive as one: classified inline it would be held to the inline rule,
    which is about the span's own quote marks, and a marker sitting behind a
    `> ` is nowhere near them while still cutting a line off the emitted prompt.
    """
    lines = read(PROMPTS_MD).replace("\r\n", "\n").split("\n")
    block, inline = [], []
    for num, line in enumerate(lines):
        alone = MARKER.sub("", line).strip(" \t>") == ""
        for match in MARKER.finditer(line):
            site = (match.group("kind"), match.group("id"),
                    match.group("edge"), num, match)
            (block if alone else inline).append(site)
    return lines, block, inline


def markers():
    """Every marker in agent-prompts.md, as (kind, id, edge, offset)."""
    return [
        (m.group("kind"), m.group("id"), m.group("edge"), m.start())
        for m in MARKER.finditer(read(PROMPTS_MD))
    ]


def test_every_pass_prompt_is_marked():
    found = {(k, i, e) for k, i, e, _ in markers()}
    missing = [
        f"winnow:prompt id={pid} {edge}"
        for pid in PASS_IDS
        for edge in ("start", "end")
        if ("prompt", pid, edge) not in found
    ]
    assert not missing, (
        "agent-prompts.md is missing prompt markers: " + ", ".join(missing)
    )


def test_every_shared_block_is_marked():
    found = {(k, i, e) for k, i, e, _ in markers()}
    missing = [
        f"winnow:shared id={sid} {edge}"
        for sid in SHARED_IDS
        for edge in ("start", "end")
        if ("shared", sid, edge) not in found
    ]
    assert not missing, (
        "agent-prompts.md is missing shared-block markers: " + ", ".join(missing)
    )


def test_no_marker_names_an_unknown_id():
    """A marker with no entry in the known sets is as broken as a missing one.

    AC-3's other direction: a typo'd id produces a block nothing resolves, and
    the emitted prompt is silently short rather than absent.
    """
    known = {("prompt", p) for p in PASS_IDS} | {("shared", s) for s in SHARED_IDS}
    strays = sorted({(k, i) for k, i, _, _ in markers()} - known)
    assert not strays, f"agent-prompts.md has markers for unknown ids: {strays}"


def test_every_marker_pairs_and_nests_correctly():
    """start before end, exactly once each, never interleaved."""
    seen = {}
    open_now = None
    for kind, mid, edge, off in markers():
        key = (kind, mid)
        if edge == "start":
            assert open_now is None, (
                f"{kind}:{mid} starts while {open_now} is still open — "
                "markers may not interleave"
            )
            assert key not in seen, f"{kind}:{mid} has more than one start marker"
            seen[key] = off
            open_now = key
        else:
            assert open_now == key, f"{kind}:{mid} ends without a matching start"
            open_now = None
    assert open_now is None, f"{open_now} is never closed"
    assert len(seen) == len(PASS_IDS) + len(SHARED_IDS)


# AC-6 — markers are punctuation for machines; they change no prose
#
# This was briefed as a diff: strip the markers out of the working tree, compare
# against the last commit, and prove the change that introduced them reworded
# nothing. That comparison is asymmetric — one side stripped, the other not — so
# it holds only while the marker change is *uncommitted*. Committing the markers
# put them on both sides of it, and it went red in every clean checkout: the one
# state it passed in was a dirty worktree, which is not a state a repository can
# be cloned into.
#
# The claim it existed to make was checked once, directly, and holds: stripping
# the markers out of ca9eb4e's agent-prompts.md reproduces the file as 6e157dc
# left it — the last commit to touch it — byte for byte. Markers went in and no
# prose moved.
#
# What replaces it are the two standing obligations that claim rests on, as
# properties of the file rather than of the working tree, so a clean checkout
# can still check them.


def test_block_markers_bracket_exactly_their_blockquote():
    """AC-6, first obligation: a marked block is one whole blockquote.

    Every prompt and shared block here is a blockquote, and its markers sit on
    lines of their own immediately outside it.

    A marker that drifts *into* the quote silently drops the prompt's first or
    last line. One that drifts *out* is worse than it sounds: the body stops
    being a blockquote throughout, so `unquote` falls to its inline branch and
    collapses the whole block into a single run with the `> ` prefixes left in.
    Both still assemble and both still read like an instruction. Short is the
    failure `passes.py`'s own docstring calls the one nobody notices.
    """
    lines, block, _ = marker_sites()
    assert {(k, i) for k, i, _, _, _ in block} == (
        {("prompt", p) for p in PASS_IDS}
        | {("shared", s) for s in SHARED_IDS if s not in INLINE_IDS}
    ), (
        "the blocks marked around a blockquote are no longer the ones expected "
        "— this test iterates what it finds, so a marking that leaves this form "
        "would leave it passing over nothing"
    )

    def quoted(index):
        return 0 <= index < len(lines) and lines[index].startswith(">")

    wrong = []
    for kind, mid, edge, num, _ in block:
        inner, outer = (num + 1, num - 1) if edge == "start" else (num - 1, num + 1)
        if lines[num].lstrip().startswith(">"):
            wrong.append(
                f"line {num + 1}: {kind}:{mid} {edge} is written inside the "
                "blockquote it brackets rather than outside it"
            )
        elif not quoted(inner):
            wrong.append(
                f"line {num + 1}: {kind}:{mid} {edge} does not touch the "
                "blockquote it brackets"
            )
        elif quoted(outer):
            wrong.append(
                f"line {num + 1}: {kind}:{mid} {edge} has quoted text on its "
                "outer side, so the pair brackets part of a blockquote rather "
                "than all of it — the emitted prompt is missing a line"
            )
    assert not wrong, "agent-prompts.md marker drift:\n" + "\n".join(wrong)


def test_inline_markers_bracket_exactly_their_quoted_span():
    """AC-6, second obligation: an inline marker sits on the span's own quotes.

    `scope-hunks` is marked inside a sentence, around the `*"..."*` phrase the
    intro tells the reader to pass on verbatim, so the quote marks are the
    boundary and checking them pins the span to that phrase.

    A weaker check — that the marker does not land mid-word — passes on any
    boundary between two words, and the emitted rule is truncated all the same.
    Take the last clause off this one and five parallel agents are told they may
    read anything, with nothing left saying what to report.
    """
    lines, _, inline = marker_sites()
    assert {(k, i) for k, i, _, _, _ in inline} == {
        ("shared", s) for s in INLINE_IDS
    }, (
        "the blocks marked inline are no longer the ones expected — this test "
        "iterates what it finds, so a marking that leaves this form would leave "
        "it passing over nothing"
    )

    wrong = []
    for kind, mid, edge, num, match in inline:
        line = lines[num]
        if edge == "start":
            ok = line[:match.start()].endswith('*"')
        else:
            ok = line[match.end():].startswith('"*')
        if not ok:
            wrong.append(
                f"line {num + 1}: {kind}:{mid} {edge} is not against the quote "
                "mark of the span it brackets"
            )
    assert not wrong, "agent-prompts.md inline marker drift:\n" + "\n".join(wrong)


# --------------------------------------------------------------------------
# passes.json — the structural half


def contract():
    return json.loads(read(PASSES_JSON))


def test_passes_json_declares_every_pass_in_dispatch_order():
    ids = [p["id"] for p in contract()["passes"]]
    assert ids == PASS_IDS, (
        "passes.json must declare all six passes in dispatch order — S at "
        "Step 1, then A B C D E in parallel at Step 3"
    )


def test_passes_json_carries_no_prompt_text():
    """The single-source constraint, enforced rather than trusted.

    Prompt bodies live in agent-prompts.md alone. A locator (`find`) is
    exempt: it is short, it must match exactly, and the script fails loudly
    when it does not — so it cannot drift undetected the way a copy can.
    """
    raw = contract()
    locators = set()
    for slot in raw["slots"].values():
        if "find" in slot:
            locators.add(slot["find"])
    blob = json.dumps({k: v for k, v in raw.items() if k != "slots"})
    prose = [
        line[2:].strip()
        for line in read(PROMPTS_MD).replace("\r\n", "\n").split("\n")
        if line.startswith("> ") and len(line) > 40
    ]
    leaked = [s for s in prose if s in blob and s not in locators]
    assert not leaked, f"passes.json contains prompt prose: {leaked[:3]}"


@pytest.mark.parametrize("pid", PASS_IDS)
def test_every_pass_declares_known_shared_blocks(pid):
    entry = next(p for p in contract()["passes"] if p["id"] == pid)
    known = set(SHARED_IDS) | set(INPUT_BLOCK_IDS)
    unknown = [s for s in entry["shared"] if s not in known]
    assert not unknown, f"pass {pid} declares unknown shared blocks: {unknown}"


def test_agent_S_takes_only_the_writes_block():
    """S runs at Step 1, before the rules the other blocks state.

    The staleness precondition is 'verbatim, in every Step 3 prompt' and S is
    not one; the scope rule is a boundary S is the one drawing.
    """
    entry = next(p for p in contract()["passes"] if p["id"] == "S")
    assert entry["shared"] == ["writes"]


@pytest.mark.parametrize("pid", ["A", "B", "C", "D", "E"])
def test_step3_passes_take_every_shared_block(pid):
    entry = next(p for p in contract()["passes"] if p["id"] == pid)
    assert entry["shared"] == [
        "writes", "staleness", "scope-rule", "scope-list", "scope-hunks",
    ], f"pass {pid} is a Step 3 prompt and carries all of them"


def extract(kind, bid):
    """The text between a marker pair, computed independently of passes.py.

    Deliberately a second implementation. If the expectation came from the
    thing under test, AC-2 would assert that the script agrees with itself.
    """
    text = read(PROMPTS_MD).replace("\r\n", "\n")
    start = re.search(r"<!--\s*winnow:%s\s+id=%s\s+start\s*-->" % (kind, bid), text)
    end = re.search(r"<!--\s*winnow:%s\s+id=%s\s+end\s*-->" % (kind, bid), text)
    assert start and end, f"no marker pair for {kind}:{bid}"
    body = text[start.end():end.start()].strip("\n")
    lines = body.split("\n")
    if all(ln.startswith(">") for ln in lines):
        return "\n".join(
            ln[2:] if ln.startswith("> ") else ln[1:] for ln in lines
        )
    return " ".join(ln.strip() for ln in lines)      # an inline span


def test_every_declared_slot_is_defined():
    raw = contract()
    defined = set(raw["slots"])
    used = set()
    for block in raw["shared_blocks"].values():
        used.update(block.get("slots", []))
    for entry in raw["passes"]:
        used.update(entry.get("slots", []))
    assert not used - defined, f"undefined slots referenced: {sorted(used - defined)}"
    assert not defined - used, f"slots defined and never used: {sorted(defined - used)}"


def test_every_slot_locator_still_matches_its_block():
    """The staleness guard the whole find-string design rests on.

    A `find` that no longer matches stops locating anything while every other
    test stays green - and the emitted prompt keeps a placeholder that reads
    like real instruction. `check_mutations.py` treats a stale locator as a
    red test for exactly this reason; so does this.
    """
    for name, slot in contract()["slots"].items():
        kind, bid = slot["in"].split(":", 1)
        body = extract("shared" if kind == "shared" else "prompt", bid)
        seen = body.count(slot["find"])
        assert seen == slot["count"], (
            f"slot {name}: expected {slot['count']} occurrence(s) of "
            f"{slot['find']!r} in {slot['in']}, found {seen} — the locator is "
            "stale and locates nothing"
        )


# --------------------------------------------------------------------------
# tiers — parsed from portability.md, never copied

TIER_ROW = re.compile(
    r"^\|\s*\*\*(?P<id>[A-Z])\*\*\s*—[^|]*\|\s*(?P<tier>[^|]+?)\s*\|", re.M
)


def portability_tiers():
    out = {}
    for m in TIER_ROW.finditer(read(PORTABILITY_MD).replace("\r\n", "\n")):
        tier = m.group("tier").replace("*", "").strip().lower()
        out[m.group("id")] = "supervisor" if "supervisor" in tier else tier
    return out


def test_the_tier_table_is_actually_being_read():
    """Guard the parser, not just the values.

    A regex that matches nothing makes every tier comparison below vacuous,
    and a vacuous cross-check reads exactly like a passing one.
    """
    assert sorted(portability_tiers()) == sorted(PASS_IDS), (
        "the model-tier table in portability.md did not parse into six passes; "
        f"got {portability_tiers()}"
    )


@pytest.mark.parametrize("pid", PASS_IDS)
def test_tier_matches_portability_table(pid):
    entry = next(p for p in contract()["passes"] if p["id"] == pid)
    assert entry["tier"] == portability_tiers()[pid], (
        f"pass {pid}: passes.json publishes tier {entry['tier']!r} while "
        "portability.md's table says otherwise. The table is the standard; a "
        "contract that disagrees with it routes the pass to the wrong model "
        "and nothing in the output says so"
    )


def test_S_and_E_are_the_passes_held_at_supervisor_tier():
    """The asymmetry the table exists to encode.

    A and B failing weakly produce a thinner report and you notice. S and E
    failing weakly produce a report that looks complete and is not.
    """
    tiers = {p["id"]: p["tier"] for p in contract()["passes"]}
    assert {k for k, v in tiers.items() if v == "supervisor"} == {"S", "E"}
    assert {k for k, v in tiers.items() if v == "mid"} == {"A", "B", "C", "D"}


def bands():
    return {k: v for k, v in contract()["tiers"].items() if k != "_comment"}


def test_every_tier_a_pass_uses_is_defined():
    """A band with no definition is a dispatcher's guess.

    The `tier` string is the whole routing instruction. An undefined one
    still routes - to whatever the reader assumed it meant - and nothing in
    the output says the assumption was made.
    """
    assert {p["tier"] for p in contract()["passes"]} == set(bands())


# The failure this encodes: `supervisor` is not a vendor's top tier. It is
# whatever the caller's strongest enrolled model happens to be, which on a
# deployment that holds its ceiling below the top is a different model
# entirely. A band pinned to an absolute name asks for something the caller
# cannot route to, and that fails at dispatch rather than at review.
ABSOLUTE = re.compile(
    r"\b(t[123]|opus|sonnet|haiku|gpt|gemini|claude|llama|mistral)\b", re.I)


@pytest.mark.parametrize("band", ["supervisor", "mid"])
def test_tier_bands_are_relative_never_absolute(band):
    spec = bands()[band]
    assert spec["relative_to"] in ("ceiling", "below-ceiling")
    leaked = [k for k, v in spec.items()
              if isinstance(v, str) and ABSOLUTE.search(v)]
    assert not leaked, (
        f"the {band!r} band names an absolute model or tier in {leaked}. The "
        "bands are relative to what the caller has enrolled; a pinned name "
        "ages out of the line-up and is already wrong wherever the ceiling "
        "sits lower than it"
    )


def test_the_supervisor_band_is_the_ceiling_and_says_so_in_prose_too():
    """Mirror check, in the direction the prose owns.

    `passes.json` claims the supervisor band is never tiered down. That claim
    is portability.md's to make; if the doctrine is ever softened there, the
    contract must not keep asserting it on its own authority.
    """
    assert bands()["supervisor"]["relative_to"] == "ceiling"
    assert "supervisor is never tiered down" in read(PORTABILITY_MD).lower()


def test_merge_is_held_at_supervisor_tier_and_is_not_delegable():
    """Step 3.5 is the one pass that cannot be fanned out.

    A dispatcher that reads six passes and no merge builds the map and skips
    the reduce - six agent files with no consumer, which looks like six
    results rather than one unfinished fan-out.
    """
    merge = contract()["merge"]
    assert merge["tier"] == "supervisor"
    assert merge["delegable"] is False


def test_merge_runs_after_every_pass_it_reduces():
    merge = contract()["merge"]
    assert merge["step"] > max(p["step"] for p in contract()["passes"])


# --------------------------------------------------------------------------
# scripts/passes.py


def run(*args, **kw):
    return subprocess.run(
        [sys.executable, PASSES_PY, *args],
        capture_output=True, text=True, cwd=kw.get("cwd", WINNOW),
    )


def emit(*args):
    proc = run("--json", *args)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def full(*args):
    """A fully instantiated run: every slot filled."""
    return emit("--round", ".code-winnow/round-07",
                "--identity-block", IDENTITY, *args)


def test_emits_every_pass():
    """AC-1, first half."""
    assert [p["id"] for p in full("--no-feature")["passes"]] == PASS_IDS


def test_raw_needs_no_inputs():
    assert [p["id"] for p in emit("--raw")["passes"]] == PASS_IDS


@pytest.mark.parametrize("key", [
    "id", "name", "step", "runs", "condition", "tier",
    "reference_files", "writes", "shared", "slots", "dispatch", "prompt",
])
def test_every_pass_carries_every_field(key):
    for entry in full("--no-feature")["passes"]:
        assert key in entry, f"pass {entry.get('id')} is missing {key!r}"


def test_emit_carries_the_manifest_blocks():
    """What a dispatcher gets without opening passes.json itself.

    `--json` is the interface for a caller that has a shell; a block living
    only in the file that caller never reads does not exist for it. Passed
    through rather than restated, so there is one definition of a band.
    """
    out, raw = emit("--raw"), contract()
    for key in ("provides", "tiers", "merge"):
        assert out.get(key) == raw[key], f"{key!r} did not survive emit"


def test_a_single_pass_emit_still_declares_the_merge():
    """Routing one pass is the case that most easily loses the reduce.

    `--pass A` is what a dispatcher calls per agent. If `merge` were emitted
    only alongside the full set, the per-pass caller would fan out six agents
    and never learn that anything consumes them.
    """
    out = full("--no-feature", "--pass", "A")
    assert [p["id"] for p in out["passes"]] == ["A"]
    assert out["merge"]["tier"] == "supervisor"
    assert out["tiers"]["mid"]["relative_to"] == "below-ceiling"


def test_name_comes_from_the_heading():
    names = {p["id"]: p["name"] for p in emit("--raw")["passes"]}
    assert names["A"] == "chaff judgment"
    assert names["E"] == "silent failure and fragility"


def test_writes_matches_the_round_scaffold():
    """The scaffold README lists `agent-S.md … agent-E.md` as a round's output.

    If the contract named a different file, an agent would write somewhere the
    round README does not list - and that list is documented as exhaustive.
    """
    readme = read(ROUND_README)
    assert "`agent-S.md` … `agent-E.md`" in readme
    for entry in emit("--raw")["passes"]:
        assert entry["writes"] == "agent-%s.md" % entry["id"]


def test_no_unexpanded_winnow_anywhere():
    """AC-1, second half.

    An agent that cannot open the reference files still returns findings -
    they are just findings from no standard at all.
    """
    blob = json.dumps(full("--no-feature"))
    assert "$WINNOW" not in blob


def test_no_placeholder_survives_a_filled_run():
    """The failure AC-1 as briefed would have missed.

    `$WINNOW` is not the only thing that resolves to nothing. A round
    directory, a pass id and an identity block do too, and each of them reads
    like real instruction when it is left in.
    """
    for entry in full("--no-feature")["passes"]:
        if entry["prompt"] is None:
            continue
        for stale in ("<the round directory>", "<X>", "<NN>", "<branch>",
                      "<YYYY-MM-DD HH:MM>"):
            assert stale not in entry["prompt"], (
                f"pass {entry['id']} kept the placeholder {stale!r}"
            )


def test_every_reference_file_exists():
    """AC-4."""
    seen = 0
    for entry in full("--no-feature")["passes"]:
        for path in entry["reference_files"]:
            assert os.path.isfile(path), f"{entry['id']} references {path}"
            seen += 1
    assert seen, "no pass listed a reference file — the extractor read nothing"


def test_reference_files_are_absolute_and_rooted_at_winnow_root():
    entry = next(p for p in emit("--raw", "--pass", "A")["passes"])
    assert entry["reference_files"]
    for path in entry["reference_files"]:
        assert os.path.isabs(path)
        assert os.path.normpath(path).startswith(os.path.normpath(WINNOW))


def test_agent_A_lists_the_reference_files_its_prompt_names():
    entry = next(p for p in emit("--raw", "--pass", "A")["passes"])
    named = {os.path.basename(p) for p in entry["reference_files"]}
    assert named == {
        "core-patterns.md", "csharp-unity.md", "cpp-ue5.md",
        "python.md", "web.md", "tests.md",
    }


# --------------------------------------------------------------------------
# AC-2 — the assembled prompt is the marked text, not a paraphrase of it


@pytest.mark.parametrize("pid", PASS_IDS)
def test_raw_prompt_is_its_marked_block_plus_declared_shared_blocks(pid):
    """AC-2, verified rather than eyeballed.

    Both sides are computed from agent-prompts.md, but by two different
    readers: `extract` here, and the script's own parser there.
    """
    entry = next(p for p in emit("--raw")["passes"] if p["id"] == pid)
    declared = next(p for p in contract()["passes"] if p["id"] == pid)["shared"]
    parts = [extract("prompt", pid)]
    for bid in declared:
        if contract()["shared_blocks"][bid]["source"] == "marker":
            parts.append(extract("shared", bid))
    assert entry["prompt"] == "\n\n".join(parts)


def test_shared_block_text_is_present_verbatim_in_a_step3_prompt():
    """'verbatim, in every Step 3 prompt' is the file's own word for it."""
    entry = next(p for p in emit("--raw")["passes"] if p["id"] == "B")
    assert extract("shared", "staleness") in entry["prompt"]
    assert extract("shared", "writes") in entry["prompt"]


def test_agent_S_gets_no_staleness_or_scope_block():
    """S runs at Step 1 and is the pass that draws the scope."""
    entry = next(p for p in emit("--raw")["passes"] if p["id"] == "S")
    assert extract("shared", "staleness") not in entry["prompt"]
    assert extract("shared", "scope-rule") not in entry["prompt"]


# --------------------------------------------------------------------------
# AC-3 — a broken contract is an error naming the pass, never a short prompt


def sabotage(path, find, repl, *args):
    """Run the script against a temporarily broken file."""
    orig = io.open(path, encoding="utf-8", newline="").read()
    assert find in orig, f"stale sabotage locator: {find!r}"
    try:
        io.open(path, "w", encoding="utf-8", newline="").write(
            orig.replace(find, repl, 1))
        return run("--json", *args)
    finally:
        io.open(path, "w", encoding="utf-8", newline="").write(orig)


def test_a_removed_marker_is_an_error_naming_the_pass():
    proc = sabotage(PROMPTS_MD, "<!-- winnow:prompt id=C start -->", "", "--raw")
    assert proc.returncode == 2
    assert "C" in proc.stderr and "REFUSING" in proc.stderr


def test_an_entry_with_no_marker_is_an_error_naming_the_pass():
    proc = sabotage(PASSES_JSON, '"id": "E"', '"id": "Z"', "--raw")
    assert proc.returncode == 2
    assert "Z" in proc.stderr and "REFUSING" in proc.stderr


def test_a_marker_with_no_entry_is_an_error_naming_the_pass():
    proc = sabotage(PROMPTS_MD, "winnow:prompt id=D start",
                    "winnow:prompt id=Q start", "--raw")
    assert proc.returncode == 2
    assert "Q" in proc.stderr and "REFUSING" in proc.stderr


def test_a_stale_slot_locator_is_an_error_naming_the_slot():
    proc = sabotage(PASSES_JSON, '"find": "<the round directory>"',
                    '"find": "<the round folder>"', "--raw")
    assert proc.returncode == 2
    assert "round_dir" in proc.stderr and "REFUSING" in proc.stderr


def test_a_missing_reference_file_is_an_error_naming_the_pass(tmp_path):
    """A half-installed skill must not produce a slightly thinner prompt.

    The reference files are where all the judgment lives; an agent that cannot
    open them still returns findings.
    """
    os.makedirs(str(tmp_path / "references"))
    for rel in ("passes.json", "references/agent-prompts.md"):
        io.open(str(tmp_path / rel), "w", encoding="utf-8", newline="").write(
            read(os.path.join(WINNOW, rel.replace("/", os.sep))))
    proc = run("--json", "--raw", "--winnow-root", str(tmp_path))
    assert proc.returncode == 2
    assert "REFUSING" in proc.stderr
    assert "core-patterns.md" in proc.stderr


# --------------------------------------------------------------------------
# slots — fail closed


def test_unfilled_slot_refuses_and_names_pass_and_slot():
    proc = run("--json", "--no-feature")            # no --round, no identity
    assert proc.returncode == 2
    assert "REFUSING" in proc.stderr
    assert "round_dir" in proc.stderr


def test_agent_S_never_carries_the_worked_example():
    """The worst placeholder in the file, and the quietest.

    Extracted verbatim, S's worked example dispatches a scope pass against a
    feature nobody asked for, and S returns a confident boundary for it. There
    are only two honest outcomes: the real phrase, or no prompt at all.
    """
    dispatched = emit("--pass", "S", "--round", ".code-winnow/round-07",
                      "--identity-block", IDENTITY,
                      "--feature", "the retry logic")["passes"][0]
    assert "dash cooldown" not in dispatched["prompt"]

    idle = next(p for p in full("--no-feature")["passes"] if p["id"] == "S")
    assert idle["prompt"] is None


def test_feature_replaces_the_worked_example():
    data = emit("--pass", "S", "--round", ".code-winnow/round-07",
                "--identity-block", IDENTITY, "--feature", "the retry logic")
    prompt = data["passes"][0]["prompt"]
    assert "the retry logic" in prompt
    assert "dash cooldown" not in prompt
    assert "cooldown work" not in prompt


def test_naming_a_feature_without_the_confirmed_list_refuses():
    """A, B, C, D and E receive the confirmed scope as a rule, not a hint."""
    proc = run("--json", "--pass", "A", "--round", ".code-winnow/round-07",
               "--identity-block", IDENTITY, "--feature", "the retry logic")
    assert proc.returncode == 2
    assert "scope-list" in proc.stderr


def test_feature_run_carries_the_scope_blocks(tmp_path):
    listing = tmp_path / "scope.txt"
    listing.write_text("Retry.cs\nRetryConfig.cs — lines 10-40\n", encoding="utf-8")
    data = emit("--pass", "A", "--round", ".code-winnow/round-07",
                "--identity-block", IDENTITY, "--feature", "the retry logic",
                "--scope-list", str(listing))
    prompt = data["passes"][0]["prompt"]
    assert extract("shared", "scope-rule") in prompt
    assert extract("shared", "scope-hunks") in prompt
    assert "RetryConfig.cs — lines 10-40" in prompt


def test_no_feature_omits_the_scope_blocks():
    prompt = next(p for p in full("--no-feature")["passes"]
                  if p["id"] == "A")["prompt"]
    assert extract("shared", "scope-rule") not in prompt
    assert extract("shared", "scope-hunks") not in prompt


def test_choosing_neither_feature_flag_refuses():
    """Guessing whether a feature was named is the one thing not to do.

    A boundary drawn one file narrow leaves that file reviewed by nobody, and
    nothing in the output says so.
    """
    proc = run("--json", "--round", ".code-winnow/round-07",
               "--identity-block", IDENTITY)
    assert proc.returncode == 2
    assert "--feature" in proc.stderr and "--no-feature" in proc.stderr


def test_S_is_not_dispatched_when_no_feature_was_named():
    entry = next(p for p in full("--no-feature")["passes"] if p["id"] == "S")
    assert entry["dispatch"] == "no"
    assert entry["prompt"] is None


@pytest.mark.parametrize("pid,expected", [
    ("A", "yes"), ("B", "yes"), ("E", "yes"), ("C", "conditional"),
    ("D", "conditional"),
])
def test_dispatch_reports_conditional_passes_honestly(pid, expected):
    """C and D turn on a property of the diff, which this script cannot read.

    Claiming 'yes' for them would publish a decision nobody made.
    """
    entry = next(p for p in full("--no-feature")["passes"] if p["id"] == pid)
    assert entry["dispatch"] == expected


# --------------------------------------------------------------------------
# runs and condition


def test_condition_comes_from_the_dispatch_note():
    conds = {p["id"]: p["condition"] for p in emit("--raw")["passes"]}
    assert conds["A"].startswith("Everything except comments and doc files")
    assert conds["C"].startswith("Dispatch **only** when the diff touches")
    assert "no trigger condition" in conds["E"]


@pytest.mark.parametrize("pid,runs", [
    ("S", "conditional"), ("A", "always"), ("B", "always"),
    ("C", "conditional"), ("D", "conditional"), ("E", "always"),
])
def test_runs_agrees_with_the_dispatch_note(pid, runs):
    entry = next(p for p in emit("--raw")["passes"] if p["id"] == pid)
    assert entry["runs"] == runs
    note = entry["condition"].lower().replace("*", "")   # `**only** when`
    if runs == "conditional":
        assert "only when" in note
    else:
        assert "only when" not in note


# --------------------------------------------------------------------------
# AC-7 — stdlib only, 3.9


def test_passes_py_imports_only_the_standard_library():
    """`portability.md`: both scripts are stdlib-only and never call the
    network. A third one joining them inherits the same rule."""
    import ast
    tree = ast.parse(read(PASSES_PY))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    allowed = {"argparse", "io", "json", "os", "re", "sys"}
    assert roots <= allowed, f"non-stdlib or unexpected imports: {roots - allowed}"


def test_passes_py_parses_as_python_3_9():
    """The floor portability.md sets, and the reason it sets one: a dependency
    that degrades into a silent gap is worse than one that is simply required.

    `feature_version` is the real check — grepping for `match ` finds every
    variable named `match`, which is how a syntax guard passes while proving
    nothing.
    """
    import ast
    ast.parse(read(PASSES_PY), feature_version=(3, 9))


def test_without_json_it_prints_a_readable_summary():
    """`--json` has to mean something, or it is the no-op flag this skill
    exists to cut. Default output is the dispatch table, one line per pass."""
    proc = run("--raw")
    assert proc.returncode == 0, proc.stderr
    assert not proc.stdout.lstrip().startswith("{")
    for pid in PASS_IDS:
        assert re.search(r"^%s\s" % pid, proc.stdout, re.M), \
            f"pass {pid} is missing from the summary"
    assert "supervisor" in proc.stdout and "mid" in proc.stdout


def test_the_summary_says_which_passes_are_not_dispatched():
    proc = run("--round", ".code-winnow/round-07",
               "--identity-block", IDENTITY, "--no-feature")
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in proc.stdout.split("\n") if ln.startswith("S ")]
    assert lines, f"no line for pass S in:\n{proc.stdout}"
    assert "no" in lines[0].split(), lines[0]


def test_output_survives_any_stdout_codec():
    """`> out.json` must produce the same bytes everywhere.

    The prompts are full of em dashes. Written through a locale codec on a
    cp1252 or GBK console they arrive as mojibake or as an OSError mid-write,
    and either way the consumer sees a truncated document rather than a
    failure. `scan.py` emits pure ASCII for this reason; so does this.

    portability.md: the scripts are "the one part guaranteed to behave
    identically on Hermes, Codex, Cursor, a python3 call in CI".
    """
    # The filled run, not --raw: under --raw every `dispatch` is null, so the
    # summary's conditional and not-dispatched lines never print and an ASCII
    # assertion over it proves nothing.
    filled = ["--round", ".code-winnow/round-07",
              "--identity-block", IDENTITY, "--no-feature"]
    for argv in (["--json"] + filled, filled, ["--json", "--raw"], ["--raw"]):
        proc = subprocess.run(
            [sys.executable, PASSES_PY] + argv,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=WINNOW,
        )
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        proc.stdout.decode("ascii")        # raises if anything non-ASCII got out
    plain = subprocess.run(
        [sys.executable, PASSES_PY] + filled,
        stdout=subprocess.PIPE, cwd=WINNOW).stdout
    assert b"conditional: C, D" in plain, "the line under test did not print"

    proc = subprocess.run(
        [sys.executable, PASSES_PY, "--json", "--raw"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=WINNOW,
    )
    body = proc.stdout.decode("ascii")
    assert "\\u2014" in body, (
        "the em dashes should be escaped, not absent — this test would "
        "otherwise pass on an empty document"
    )
    assert json.loads(body)["passes"]


def test_refusals_survive_any_stderr_codec():
    """A refusal that cannot be printed is the worst outcome available.

    The message is the entire value of failing loudly; losing it to the
    locale codec turns a named refusal back into a silent one.
    """
    refusals = [
        ["--json"],                                       # neither feature flag
        ["--json", "--no-feature"],                       # unfilled round_dir
        ["--json", "--round", "r", "--identity-block", "i",
         "--feature", "x"],                               # no scope list
        ["--json", "--pass", "nope", "--raw"],            # unknown pass
    ]
    for argv in refusals:
        proc = subprocess.run(
            [sys.executable, PASSES_PY] + argv,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=WINNOW,
        )
        assert proc.returncode == 2, (argv, proc.stderr)
        assert proc.stderr.startswith(b"REFUSING:"), (argv, proc.stderr)
        proc.stderr.decode("ascii")


def test_no_network_calls():
    src = read(PASSES_PY)
    for bad in ("urllib", "http", "socket", "requests"):
        assert bad not in src, f"{bad} has no business in this script"
