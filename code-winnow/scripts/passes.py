#!/usr/bin/env python3
"""code-winnow: the judgment-pass contract, as JSON. Stdlib only.

Assembles a dispatch-ready prompt for each judgment pass from the single
source that holds them - `references/agent-prompts.md` - and publishes the
dispatch metadata beside it, so a caller routing passes across providers does
not have to parse prose.

Nothing here is required. `review-pipeline.md` Step 3 still says to read
`agent-prompts.md` and copy each prompt, and that path works in a runtime with
no shell at all. This script is for the caller that has one.

What it exists to prevent: a prompt assembled by hand that is missing a shared
block, or that still contains `$WINNOW`, `<the round directory>` or Agent S's
worked example. Every one of those produces an agent that reads no standard
and returns findings anyway - findings from no standard at all, which look
exactly like findings from this one. So a slot this script cannot fill is a
refusal, never a shorter prompt.

Usage:
    python3 passes.py --json --raw
    python3 passes.py --json --round .code-winnow/round-07 \\
        --identity-block-file .code-winnow/round-07/identity.txt --no-feature
    python3 passes.py --json --pass A --round .code-winnow/round-07 \\
        --identity-block "$IDENTITY" --feature "the dash cooldown work" \\
        --scope-list .code-winnow/round-07/scratch/scope.txt

Exit codes: 0 fine, 2 refused (a `REFUSING:` line on stderr says which pass
and which slot).
"""

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.dirname(HERE)

MARKER = re.compile(
    r"<!--\s*winnow:(?P<kind>prompt|shared)\s+id=(?P<id>[A-Za-z0-9_-]+)\s+"
    r"(?P<edge>start|end)\s*-->"
)
HEADING = re.compile(
    r"^##\s+Agent\s+(?P<id>[A-Za-z0-9_-]+)\s*[—–-]\s*(?P<name>.+?)\s*$",
    re.M,
)
REFERENCE = re.compile(r"\$WINNOW/references/([A-Za-z0-9_.\-]+\.md)")


class Refusal(Exception):
    """Something the caller has to decide. Never worked around here."""


def read(path, what):
    try:
        with io.open(path, encoding="utf-8", newline="") as fh:
            return fh.read().replace("\r\n", "\n")
    except (IOError, OSError) as exc:
        raise Refusal("cannot read %s (%s): %s" % (what, path, exc))


# --------------------------------------------------------------------------
# the marked document
# --------------------------------------------------------------------------

def unquote(body):
    """A marked span as prompt text.

    A block marker wraps a blockquote and the `> ` prefix comes off. An inline
    marker wraps a span of ordinary prose, which is hard-wrapped in the source
    and is one sentence in a prompt.
    """
    body = body.strip("\n")
    lines = body.split("\n")
    if lines and all(line.startswith(">") for line in lines):
        return "\n".join(
            line[2:] if line.startswith("> ") else line[1:] for line in lines
        )
    return " ".join(line.strip() for line in lines)


def parse_blocks(text):
    """{(kind, id): body}, plus where each block's start marker sat.

    Every structural problem here is a refusal naming the id. A marker pair
    that silently resolved to nothing would emit a prompt that is merely
    short, and short is the one failure mode nobody notices.
    """
    blocks = {}
    starts = {}
    open_key = None
    open_at = 0
    for match in MARKER.finditer(text):
        key = (match.group("kind"), match.group("id"))
        label = "%s:%s" % key
        if match.group("edge") == "start":
            if open_key is not None:
                raise Refusal(
                    "%s starts while %s:%s is still open - winnow markers may "
                    "not nest or interleave" % ((label,) + open_key))
            if key in blocks:
                raise Refusal("%s has more than one start marker" % label)
            open_key, open_at = key, match.end()
            starts[key] = match.start()
        else:
            if open_key != key:
                raise Refusal(
                    "%s has an end marker with no matching start%s"
                    % (label, "" if open_key is None
                       else " (%s:%s is the one that is open)" % open_key))
            blocks[key] = unquote(text[open_at:match.start()])
            open_key = None
    if open_key is not None:
        raise Refusal("%s:%s is never closed" % open_key)
    return blocks, starts


def parse_headings(text, starts):
    """{id: (name, dispatch note)} for every `## Agent X — name` section.

    The dispatch note is everything between the heading and the pass's own
    prompt marker, so it needs no marker of its own and cannot drift from the
    prompt it introduces.
    """
    out = {}
    for match in HEADING.finditer(text):
        pid = match.group("id")
        start = starts.get(("prompt", pid))
        if start is None or start < match.end():
            continue
        out[pid] = (match.group("name"), text[match.end():start].strip())
    return out


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------

def check_locator(name, slot, blocks):
    kind, bid = slot["in"].split(":", 1)
    body = blocks.get((kind, bid))
    if body is None:
        raise Refusal(
            "slot %s is declared in %s, which has no marked block"
            % (name, slot["in"]))
    seen = body.count(slot["find"])
    if seen != slot["count"]:
        raise Refusal(
            "slot %s is stale: %r appears %d time(s) in %s, expected %d. It "
            "locates nothing, so the placeholder would ship as instruction"
            % (name, slot["find"], seen, slot["in"], slot["count"]))


def fill(body, name, slot, values, pid, raw):
    if raw:
        return body
    value = values.get(name)
    if value is None:
        raise Refusal(
            "pass %s: slot %s is unfilled - supply it with %s, or pass --raw "
            "for the uninstantiated contract"
            % (pid, name, slot.get("from", "the matching flag")))
    return body.replace(slot["find"], value)


def assemble(entry, contract, blocks, values, raw, feature_named, scope_list):
    """The pass's own block, then the shared blocks it declares, in order."""
    pid = entry["id"]
    slots = contract["slots"]
    used = []

    def resolve(kind, bid, slot_names):
        body = blocks[(kind, bid)]
        for name in slot_names:
            body = fill(body, name, slots[name], values, pid, raw)
            used.append(name)
        return body

    if ("prompt", pid) not in blocks:
        raise Refusal(
            "pass %s is declared in passes.json but agent-prompts.md has no "
            "<!-- winnow:prompt id=%s start --> marker" % (pid, pid))
    parts = [resolve("prompt", pid, entry.get("slots", []))]

    for bid in entry["shared"]:
        block = contract["shared_blocks"].get(bid)
        if block is None:
            raise Refusal("pass %s declares unknown shared block %r" % (pid, bid))
        if block.get("requires") == "feature" and not raw and not feature_named:
            continue
        if block["source"] == "input":
            if raw:
                continue
            if scope_list is None:
                raise Refusal(
                    "pass %s: shared block %s has no content - supply it with "
                    "%s. A, B, C, D and E receive the confirmed scope as a "
                    "rule, not a hint"
                    % (pid, bid, block.get("from", "the matching flag")))
            parts.append(scope_list)
            continue
        if ("shared", bid) not in blocks:
            raise Refusal(
                "pass %s declares shared block %s, which agent-prompts.md "
                "does not mark" % (pid, bid))
        parts.append(resolve("shared", bid, block.get("slots", [])))

    return "\n\n".join(parts), used


# --------------------------------------------------------------------------

def dispatch_state(entry, raw, feature_named):
    if raw:
        return None
    if entry["runs"] == "always":
        return "yes"
    if entry.get("conditional_on") == "feature":
        return "yes" if feature_named else "no"
    return "conditional"


def build(args):
    root = os.path.abspath(args.winnow_root or DEFAULT_ROOT)
    contract = json.loads(read(os.path.join(root, "passes.json"), "passes.json"))
    prompts_md = os.path.join(root, *contract["source"].split("/"))
    text = read(prompts_md, "the prompt source")

    blocks, starts = parse_blocks(text)
    headings = parse_headings(text, starts)

    declared = [e["id"] for e in contract["passes"]]
    marked = [i for k, i in blocks if k == "prompt"]
    unmarked = sorted(i for i in declared if i not in marked)
    unclaimed = sorted(i for i in marked if i not in declared)
    if unmarked or unclaimed:
        # Both directions in one message. A rename shows up as one of each,
        # and reporting only the first sends the reader to the wrong file.
        parts = []
        if unmarked:
            parts.append("passes.json declares %s with no "
                         "<!-- winnow:prompt id=... --> marker"
                         % ", ".join(unmarked))
        if unclaimed:
            parts.append("agent-prompts.md marks %s, which passes.json does "
                         "not declare" % ", ".join(unclaimed))
        raise Refusal("; ".join(parts) + ". A pass on one side and not the "
                      "other is a prompt nothing dispatches, or a dispatch "
                      "with no prompt")

    for name, slot in contract["slots"].items():
        check_locator(name, slot, blocks)

    feature_named = bool(args.feature)
    scope_list = None
    if args.scope_list:
        scope_list = read(args.scope_list, "the confirmed scope list").strip()

    out = []
    for entry in contract["passes"]:
        pid = entry["id"]
        if args.only and pid != args.only:
            continue
        if pid not in headings:
            raise Refusal(
                "pass %s has no `## Agent %s - ...` heading in agent-prompts.md"
                % (pid, pid))
        name, condition = headings[pid]
        state = dispatch_state(entry, args.raw, feature_named)
        # `pass_id` is the one slot whose value is per-pass rather than
        # per-run, which is why the map is rebuilt here.
        values = {
            "round_dir": args.round,
            "identity_block": args.identity_block,
            "feature_phrase": args.feature,
            "pass_id": pid,
        }

        if state == "no":
            prompt, used, refs = None, [], []
        else:
            prompt, used = assemble(entry, contract, blocks, values, args.raw,
                                    feature_named, scope_list)
            refs = [os.path.join(root, "references", n)
                    for n in sorted(set(REFERENCE.findall(prompt)))]
            missing = [p for p in refs if not os.path.isfile(p)]
            if missing:
                raise Refusal(
                    "pass %s names reference file(s) that do not exist: %s. "
                    "Those files are where the judgment lives; an agent that "
                    "cannot open them still returns findings"
                    % (pid, ", ".join(os.path.basename(p) for p in missing)))
            if not args.raw:
                prompt = prompt.replace("$WINNOW", root)

        out.append({
            "id": pid,
            "name": name,
            "step": entry["step"],
            "runs": entry["runs"],
            "conditional_on": entry.get("conditional_on"),
            "condition": condition,
            "tier": entry["tier"],
            "dispatch": state,
            "writes": "agent-%s.md" % pid,
            "shared": entry["shared"],
            "reference_files": refs,
            "slots": [
                {"name": n, "from": contract["slots"][n].get("from"),
                 "filled": not args.raw}
                for n in used
            ],
            "prompt": prompt,
        })

    if args.only and not out:
        raise Refusal("no pass with id %r" % args.only)

    return {
        "version": contract["version"],
        "provides": contract["provides"],
        "winnow_root": root,
        "raw": bool(args.raw),
        "feature": args.feature,
        # Passed through, not restated. A dispatcher mapping `tier` onto its
        # own vocabulary needs the band semantics in the same document as the
        # bands, or it reads `supervisor` as a vendor tier name - which is
        # wrong on any deployment whose ceiling sits lower. `merge` is here
        # for the same reason: six writes with no declared consumer look like
        # six independent results rather than one fan-out awaiting its reduce.
        "tiers": contract["tiers"],
        "merge": contract["merge"],
        "passes": out,
    }


def summary(data):
    """The dispatch table, for a human deciding what to route where.

    Deliberately not the prompts. Eight thousand characters of Agent A scrolled
    past is how you stop reading the two lines that say which passes are going
    to a weaker model.
    """
    rows = ["%-3s %-5s %-11s %-12s %-11s %s" % (
        "id", "step", "tier", "dispatch", "writes", "refs")]
    for entry in data["passes"]:
        rows.append("%-3s %-5s %-11s %-12s %-11s %d" % (
            entry["id"], entry["step"], entry["tier"],
            entry["dispatch"] if entry["dispatch"] is not None else "-",
            entry["writes"], len(entry["reference_files"])))
    idle = [e["id"] for e in data["passes"] if e["dispatch"] == "no"]
    cond = [e["id"] for e in data["passes"] if e["dispatch"] == "conditional"]
    if idle:
        rows.append("")
        rows.append("not dispatched: %s (no feature was named)" % ", ".join(idle))
    if cond:
        rows.append("")
        # ASCII, like everything else this prints. A summary line is human
        # output, but it still goes through the locale codec on the way out.
        rows.append("conditional: %s - their trigger is a property of the diff, "
                    "which this script\n  does not read. The condition is in "
                    "each pass's `condition` field; decide it\n  yourself before "
                    "dispatching." % ", ".join(cond))
    rows.append("")
    rows.append("--json for the prompts and the full contract.")
    return "\n".join(rows) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true",
                    help="the full contract, prompts included. Without it you "
                         "get the dispatch table only")
    ap.add_argument("--raw", action="store_true",
                    help="the uninstantiated contract: slots left in place, "
                         "no inputs required")
    ap.add_argument("--winnow-root", metavar="PATH",
                    help="this skill's directory; $WINNOW expands to it. "
                         "Defaults to the one this script lives in")
    ap.add_argument("--pass", dest="only", metavar="ID",
                    help="emit one pass. The whole contract is still validated")
    ap.add_argument("--round", metavar="DIR",
                    help="the round directory every pass writes into")
    ap.add_argument("--identity-block", metavar="TEXT",
                    help="the three-line identity block, already rendered")
    ap.add_argument("--identity-block-file", metavar="PATH",
                    help="read --identity-block from a file")
    ap.add_argument("--feature", metavar="TEXT",
                    help="the user's own words for the named feature")
    ap.add_argument("--no-feature", action="store_true",
                    help="no feature was named; the diff is the scope")
    ap.add_argument("--scope-list", metavar="PATH",
                    help="the confirmed file and region list, as text")
    args = ap.parse_args()

    try:
        if args.identity_block_file:
            if args.identity_block:
                raise Refusal("--identity-block and --identity-block-file "
                              "are two ways to say the same thing; pick one")
            args.identity_block = read(
                args.identity_block_file, "the identity block").strip("\n")
        if not args.raw:
            if bool(args.feature) == bool(args.no_feature):
                raise Refusal(
                    "say whether a feature was named: --feature \"<their "
                    "words>\" or --no-feature. Guessing is the one thing not "
                    "to do here - a boundary drawn one file narrow leaves "
                    "that file reviewed by nobody, and nothing in the output "
                    "says so")
        data = build(args)
    except Refusal as exc:
        sys.stderr.write("REFUSING: %s\n" % exc)
        return 2

    if args.json:
        # ASCII on purpose, as `scan.py` is. The prompts are full of em dashes,
        # and `> out.json` on a cp1252 or GBK console writes them through the
        # locale codec - mojibake at best, an OSError mid-document at worst,
        # and either way the consumer sees a truncated file rather than a
        # failure.
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
    else:
        sys.stdout.write(summary(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
