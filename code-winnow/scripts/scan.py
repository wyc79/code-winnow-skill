#!/usr/bin/env python3
"""code-winnow: deterministic candidate scanner. Stdlib only.

Reports CANDIDATES, not verdicts. Every hit needs human or model judgment
before it belongs in a report - a TODO in a test fixture and a TODO blocking
a shipped feature look identical from here.

Run it from anywhere inside the repo; paths resolve against the git toplevel.
Files it cannot read are reported loudly, never skipped in silence: a scan
that read nothing must not look like a scan that found nothing.

Usage:
    python3 scan.py                      # auto-resolve scope from git
    python3 scan.py --json               # machine-readable
    python3 scan.py --scope branch --base develop
    python3 scan.py --paths a.py b.cs    # scan whole files instead
    python3 scan.py --min-severity P2    # filter noise
    python3 scan.py --since PRIOR.json   # reconcile with the last run
"""

import argparse
import ast
import datetime
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

SEVERITY_ORDER = {"P1": 0, "P2": 1, "P3": 2}

PY_EXT = {".py"}
CS_EXT = {".cs"}
CPP_EXT = {".cpp", ".h", ".hpp", ".cc", ".inl"}
PROSE_EXT = {".md", ".txt", ".rst", ".adoc"}

TEST_HINT = re.compile(
    r"(^|[/\\_.])(tests?|specs?|fixtures?|testing|e2e|cypress|__tests__|"
    r"unittests?)([/\\_.]|$)"
    r"|(?:^|/)conftest\.py$"
    r"|[A-Za-z0-9]+(Tests?|Spec)\.[A-Za-z]+$"
    r"|_(test|spec|unittest)\.[A-Za-z]+$"
    r"|\.(test|spec|cy|e2e)\.[A-Za-z]+$",
    re.I)

# Paths whose contents nobody hand-wrote. Scanning them produces findings no
# one can act on and buries the ones they can.
VENDOR_HINT = re.compile(
    r"(^|/)(node_modules|vendor|third_party|thirdparty|external|dist|build|"
    r"out|obj|bin|Intermediate|Binaries|DerivedDataCache|Library|Temp|"
    r"__pycache__|\.venv|venv|site-packages|migrations|generated|gen)(/|$)"
    r"|\.(min|bundle|generated|designer|g|pb)\.[A-Za-z0-9]+$"
    r"|\.(lock|snap|map)$",
    re.I,
)

# This tool's own workspace. Step 0 excludes it from git, but an untracked
# scan must not review the report it is about to write even before that lands.
WORKSPACE_HINT = re.compile(r"(^|/)\.(code-winnow|de-slop)(/|$)")

DEFAULT_MAX_BYTES = 512 * 1024
MINIFIED_AVG_LINE = 500

# Non-fatal problems worth telling the user about. Collected, then printed.
WARNINGS = []
READ_ERRORS = []


def warn(msg):
    if msg not in WARNINGS:
        WARNINGS.append(msg)


# --------------------------------------------------------------------------
# git plumbing
# --------------------------------------------------------------------------

_REPO_ROOT = None


def _git(args, cwd=None):
    try:
        out = subprocess.run(
            ["git"] + args, capture_output=True, text=True, check=False,
            cwd=cwd or _REPO_ROOT,
        )
    except (FileNotFoundError, OSError):
        return None
    return out.stdout if out.returncode == 0 else None


def repo_root():
    """Absolute path of the git toplevel, or None outside a repo.

    Everything git prints is relative to this, not to the cwd, so every path
    the scanner opens has to be joined onto it.
    """
    global _REPO_ROOT
    if _REPO_ROOT is None:
        out = _git(["rev-parse", "--show-toplevel"], cwd=os.getcwd())
        _REPO_ROOT = out.strip() if out and out.strip() else ""
    return _REPO_ROOT or None


def abs_path(rel):
    root = repo_root()
    return os.path.join(root, rel) if root else rel


def current_branch():
    out = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    if out is None:
        return "nogit"
    return out.strip() or "detached"


def ref_exists(ref):
    return _git(["rev-parse", "--verify", "--quiet", ref + "^{commit}"]) is not None


def discover_base():
    """First base ref that exists and is not the branch we are on.

    Ordered: the remote's default branch, then the usual names, local before
    remote-tracking. A repo branched off `develop`, or a fresh clone with only
    origin/* refs, both used to fall through to "no diff found".
    """
    head = current_branch()
    out = _git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    candidates = []
    if out and out.strip():
        candidates.append(out.strip().replace("refs/remotes/", ""))
    for name in ("main", "master", "develop", "development", "trunk"):
        candidates.extend([name, "origin/" + name])
    for ref in candidates:
        if ref.split("/")[-1] == head and "/" not in ref:
            continue
        if ref_exists(ref):
            return ref
    return None


def slug(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "unknown"


def unquote_diff_path(target):
    """git quotes paths containing spaces or non-ASCII in c-style quotes."""
    target = target.strip()
    if target.startswith('"') and target.endswith('"') and len(target) > 1:
        try:
            return target[1:-1].encode().decode("unicode_escape")
        except (UnicodeDecodeError, ValueError):
            return target[1:-1]
    return target


def parse_diff(raw, into=None):
    """Extract added line numbers per file from a unified diff.

    Only counts inside a hunk. The header lines (`diff --git`, `index`,
    `similarity index`, mode changes) are not file content and must not move
    the line cursor.
    """
    added = into if into is not None else defaultdict(set)
    path = None
    new_line = 0
    in_hunk = False
    for line in raw.splitlines():
        if line.startswith("+++ "):
            target = unquote_diff_path(line[4:])
            path = None if target == "/dev/null" else re.sub(r"^b/", "", target)
            in_hunk = False
        elif line.startswith("--- "):
            in_hunk = False
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            new_line = int(m.group(1)) if m else 0
            in_hunk = bool(m)
        elif not in_hunk or path is None:
            continue
        elif line.startswith("+"):
            added[path].add(new_line)
            new_line += 1
        elif line.startswith("\\"):  # "\ No newline at end of file"
            continue
        elif line.startswith("-"):
            continue
        else:
            new_line += 1
    return added


def untracked_files():
    out = _git(["ls-files", "--others", "--exclude-standard"])
    if not out:
        return []
    return [p for p in out.splitlines() if p.strip()]


def count_lines(rel):
    lines = read_lines(rel)
    return len(lines) if lines else 0


def resolve_diff(scope="auto", base=None):
    """Return (label, target, {path: set(new_lines)}).

    `auto` unions everything uncommitted - staged, unstaged, and untracked -
    and only falls back to the branch diff when the working tree is clean.
    The old stop-at-first-non-empty ladder meant one staged file silently
    dropped every other edit out of scope, and untracked files - where
    generated code most often lands - were invisible in every mode.
    """
    if repo_root() is None:
        warn("not inside a git repository - use --paths to scan files directly")
        return None, None, {}

    def worktree():
        added = defaultdict(set)
        sources = []
        for label, args in (("staged", ["diff", "--cached", "--unified=0"]),
                            ("unstaged", ["diff", "--unified=0"])):
            raw = _git(args + ["--no-renames", "--diff-filter=d"])
            if raw and raw.strip():
                before = len(added)
                parse_diff(raw, added)
                if len(added) >= before:
                    sources.append(label)
        new_files = []
        for rel in untracked_files():
            if skip_path(rel):
                continue
            n = count_lines(rel)
            if n:
                added[rel].update(range(1, n + 1))
                new_files.append(rel)
        if new_files:
            sources.append(f"{len(new_files)} untracked")
        added = {p: v for p, v in added.items() if v}
        return added, sources

    if scope in ("auto", "worktree", "staged", "unstaged"):
        if scope == "staged":
            raw = _git(["diff", "--cached", "--unified=0", "--no-renames",
                        "--diff-filter=d"]) or ""
            added = {p: v for p, v in parse_diff(raw).items() if v}
            if added:
                return "staged changes (git diff --cached)", "staged", added
        elif scope == "unstaged":
            raw = _git(["diff", "--unified=0", "--no-renames",
                        "--diff-filter=d"]) or ""
            added = {p: v for p, v in parse_diff(raw).items() if v}
            if added:
                return "unstaged changes (git diff)", "uncommitted", added
        else:
            added, sources = worktree()
            if added:
                return ("uncommitted work (" + ", ".join(sources) + ")",
                        "worktree", added)
        if scope != "auto":
            return None, None, {}

    ref = base or discover_base()
    if ref is None:
        warn("no base branch found (tried origin/HEAD, main, master, develop, "
             "trunk) - pass --base <ref>")
        return None, None, {}
    if not ref_exists(ref):
        warn(f"base ref '{ref}' does not exist")
        return None, None, {}
    raw = _git(["diff", "--unified=0", "--no-renames", "--diff-filter=d",
                f"{ref}...HEAD"])
    if raw is None:
        warn(f"could not diff against '{ref}' (no merge base?)")
        return None, None, {}
    added = {p: v for p, v in parse_diff(raw).items() if v}
    if not added:
        return None, None, {}
    return f"branch vs {ref}", ref, added


def report_stem(target, when=None):
    """current<branch>_target<base>_<time>, or _worktree_/_staged_/_files_
    for non-branch scopes. Timestamped so successive runs never overwrite."""
    when = when or datetime.datetime.now()
    stamp = when.strftime("%Y%m%d-%H%M")
    branch = slug(current_branch())
    if target in ("staged", "uncommitted", "worktree", "files"):
        return f"current{branch}_{target}_{stamp}"
    return f"current{branch}_target{slug(target)}_{stamp}"


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def skip_path(rel, max_bytes=DEFAULT_MAX_BYTES):
    """True if this file should not be scanned, with a reason recorded."""
    if WORKSPACE_HINT.search(rel):
        return "this tool's own workspace"
    if VENDOR_HINT.search(rel):
        return "vendored or generated path"
    try:
        size = os.path.getsize(abs_path(rel))
    except OSError:
        return None  # let read_lines report the real error
    if size > max_bytes:
        return f"{size // 1024}KB exceeds --max-file-bytes"
    return None


def read_lines(rel):
    """Return the file's lines, or None after recording why not.

    Silence here is the worst possible failure: it turns "I could not open
    anything" into "0 candidates found", which reads as a clean bill of health.
    """
    full = abs_path(rel)
    try:
        with open(full, "rb") as fh:
            blob = fh.read()
    except OSError as exc:
        READ_ERRORS.append({"path": rel, "error": exc.strerror or str(exc)})
        return None
    if b"\x00" in blob[:8192]:
        READ_ERRORS.append({"path": rel, "error": "binary file"})
        return None
    text = blob.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if lines and len(text) / len(lines) > MINIFIED_AVG_LINE:
        READ_ERRORS.append({"path": rel, "error": "looks minified"})
        return None
    return lines


STOPWORDS = {
    "the", "and", "for", "this", "that", "with", "from", "into", "its", "are",
    "was", "all", "not", "but", "you", "your", "has", "have", "will", "can",
}


def words(text):
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    found = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", text)]
    return [w for w in found if w not in STOPWORDS]


def add(findings, path, line, sev, rule, msg, anchor=""):
    findings.append({
        "path": path, "line": line, "severity": sev, "rule": rule,
        "message": msg, "anchor": anchor,
    })


def anchor_of(lines, idx):
    """Whitespace-normalised source of the finding's line.

    The reconciliation key uses this so two instances of a constant-message
    rule in the same file stay distinguishable, and so a finding survives the
    line shifts that deleting other findings causes.
    """
    if 1 <= idx <= len(lines):
        return re.sub(r"\s+", " ", lines[idx - 1]).strip()[:120]
    return ""


RE_STRING = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'")
RE_LINE_COMMENT = re.compile(r"//.*$|#(?!\[).*$")


def strip_code(text):
    """Blank out string literals and line comments so brace counting and
    identifier matching do not trip over their contents."""
    return RE_LINE_COMMENT.sub("", RE_STRING.sub('""', text))


RE_PREPROCESSOR = re.compile(
    r"^\s*#\s*(include|define|undef|if|ifdef|ifndef|elif|else|endif|pragma|"
    r"error|warning|region|endregion|line|nullable|import|using)\b")
RE_SHEBANG = re.compile(r"^#!")
RE_COMMENT = re.compile(
    r"^\s*(?://+|\#+|/\*+|\*(?!/)|<!--|--(?!-))\s*(.+?)\s*(?:\*/|-->)?\s*$")


def comment_body(text):
    """The prose inside a comment, or None. Preprocessor directives are not
    comments, however much `#include` looks like one to a regex."""
    if RE_PREPROCESSOR.match(text) or RE_SHEBANG.match(text):
        return None
    m = RE_COMMENT.match(text)
    if not m:
        return None
    body = m.group(1).strip()
    return body or None


# --------------------------------------------------------------------------
# universal rules
# --------------------------------------------------------------------------

# Genuinely invisible - you cannot see these in review at all.
UNICODE_INVISIBLE = {
    "\u00a0": "non-breaking space", "\u200b": "zero-width space",
    "\u200c": "zero-width non-joiner", "\u200d": "zero-width joiner",
    "\ufeff": "byte-order mark", "\u2060": "word joiner",
    "\u202a": "bidi override", "\u202e": "bidi override",
}
# Visible, legitimate in prose, only a nuisance in code. P3, and not worth
# mentioning at all inside a comment or a prose file.
UNICODE_TYPOGRAPHIC = {
    "\u2014": "em dash", "\u2013": "en dash",
    "\u2018": "smart quote", "\u2019": "smart quote",
    "\u201c": "smart quote", "\u201d": "smart quote",
}

RE_TODO = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
RE_TICKET = re.compile(r"([A-Z]{2,}-\d+|#\d+|https?://)")
RE_LOCAL_PATH = re.compile(
    r"(/Users/[A-Za-z0-9._-]+|/home/[A-Za-z0-9._-]+|[Cc]:\\Users\\)")
RE_TRACE_LOG = re.compile(
    r"(logger?|logging|Debug\.Log|UE_LOG|print|console\.log)\b.{0,60}?"
    r"\b(entering|exiting|starting|finished|called|begin|end)\b",
    re.I,
)
RE_COMMENTED_CODE = re.compile(r"^\s*(//|#)\s*[\w\]\)]+.*[;{}]\s*$")


def check_universal(path, lines, findings):
    is_test = bool(TEST_HINT.search(path))
    is_prose = os.path.splitext(path)[1].lower() in PROSE_EXT
    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        body = comment_body(text)
        anchor = anchor_of(lines, idx)

        for ch, name in UNICODE_INVISIBLE.items():
            if ch in text:
                add(findings, path, idx, "P1", "unicode-invisible",
                    f"{name} in source - invisible in review, breaks grep",
                    anchor)
                break
        if not is_prose and body is None:
            for ch, name in UNICODE_TYPOGRAPHIC.items():
                if ch in text:
                    add(findings, path, idx, "P3", "unicode-typographic",
                        f"{name} in code - fine in prose, breaks grep in code",
                        anchor)
                    break

        if RE_LOCAL_PATH.search(text):
            add(findings, path, idx, "P1", "local-path",
                "absolute local path committed", anchor)

        if RE_TODO.search(text) and not RE_TICKET.search(text) and not is_test:
            add(findings, path, idx, "P3", "orphan-todo",
                "placeholder with no ticket or owner", anchor)

        if RE_TRACE_LOG.search(text):
            add(findings, path, idx, "P3", "trace-logging",
                "entry/exit logging - usually debugging debris", anchor)

        if body is not None and RE_COMMENTED_CODE.match(text):
            add(findings, path, idx, "P3", "commented-code",
                "commented-out code - version control already has it", anchor)

        if body is not None and idx < len(lines):
            comment_words = set(words(body))
            code_words = set(words(lines[idx]))
            if len(comment_words) >= 2:
                overlap = len(comment_words & code_words) / len(comment_words)
                if overlap >= 0.6:
                    add(findings, path, idx, "P3", "restated-comment",
                        "comment restates the line below it", anchor)


# --------------------------------------------------------------------------
# python
# --------------------------------------------------------------------------

RE_PY_LOG_FSTRING = re.compile(r"\b(logger?|logging)\.\w+\(\s*f[\"']")
RE_PY_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore")
RE_PY_ANY = re.compile(r":\s*Any\b|->\s*Any\b|\[str,\s*Any\]")


def check_python(path, lines, findings):
    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        anchor = anchor_of(lines, idx)
        if RE_PY_LOG_FSTRING.search(text):
            add(findings, path, idx, "P3", "eager-log-format",
                "f-string in logging call formats even when filtered out",
                anchor)
        if RE_PY_TYPE_IGNORE.search(text):
            add(findings, path, idx, "P2", "type-ignore",
                "silences the checker rather than fixing the type", anchor)
        if RE_PY_ANY.search(text):
            add(findings, path, idx, "P3", "any-hint",
                "Any disables checking exactly where it would help", anchor)

    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError as exc:
        warn(f"{path}: could not parse Python ({exc.msg} at line {exc.lineno})"
             " - AST rules skipped for this file")
        return

    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if line is None:
            continue
        anchor = anchor_of(lines, line)

        if isinstance(node, ast.AsyncFunctionDef):
            has_await = any(
                isinstance(n, (ast.Await, ast.AsyncFor, ast.AsyncWith))
                for n in ast.walk(node)
            )
            if not has_await:
                add(findings, path, line, "P2", "async-no-await",
                    f"'{node.name}' is async but never awaits - forces callers "
                    "async for nothing", anchor)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    add(findings, path, line, "P1", "mutable-default",
                        f"'{node.name}' has a mutable default argument - "
                        "shared across calls", anchor)
                    break

        if isinstance(node, ast.ExceptHandler):
            body = node.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                add(findings, path, line, "P1", "swallowed-exception",
                    "except/pass hides the failure entirely", anchor)
            elif body and isinstance(body[-1], ast.Raise) and body[-1].exc is None:
                add(findings, path, line, "P2", "log-and-reraise",
                    "logs then re-raises - duplicate traceback unless it adds "
                    "context", anchor)
            if node.type is None:
                add(findings, path, line, "P2", "bare-except",
                    "bare except catches KeyboardInterrupt and typos alike",
                    anchor)
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                add(findings, path, line, "P3", "broad-except",
                    "catching Exception where one failure mode is expected",
                    anchor)

    check_python_bindings(path, tree, lines, findings)
    if TEST_HINT.search(path):
        check_python_tests(path, tree, lines, findings)


def check_python_bindings(path, tree, lines, findings):
    """Fields assigned but never read; locals that are aliases or dead."""
    file_tokens = defaultdict(int)
    for token in re.findall(r"\b[A-Za-z_]\w*\b", "\n".join(lines)):
        file_tokens[token] += 1
    # Attributes reached through anything other than a plain `self.x` read -
    # getattr, __dict__, vars() - are invisible to the walk below. If the file
    # uses any of them, do not claim a field is unread.
    dynamic_access = bool(re.search(r"\b(getattr|setattr|hasattr|vars|__dict__"
                                    r"|locals|globals)\b", "\n".join(lines)))

    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        # Two passes, deliberately. Collecting `bumped` in the same pass that
        # decides whether a Load counts made the result depend on ast.walk's
        # visit order: a counter that is incremented AND read was reported as
        # "only ever updated, never read".
        bumped, stores, loads = set(), {}, set()
        for n in ast.walk(cls):
            if (isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Attribute)
                    and isinstance(n.target.value, ast.Name)
                    and n.target.value.id == "self"):
                bumped.add(n.target.attr)
                stores.setdefault(n.target.attr, n.lineno)
        for n in ast.walk(cls):
            if (isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                    and n.value.id == "self"):
                if isinstance(n.ctx, ast.Store):
                    stores.setdefault(n.attr, n.lineno)
                elif isinstance(n.ctx, ast.Load):
                    loads.add(n.attr)
        aug_only = {n.target.attr for n in ast.walk(cls)
                    if isinstance(n, ast.AugAssign)
                    and isinstance(n.target, ast.Attribute)}
        real_loads = set(loads)

        # class-body fields only when the class is not a dataclass/model/enum,
        # where every field is API by construction
        plain = not cls.decorator_list and not cls.bases
        if plain:
            for stmt in cls.body:
                target = None
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    target = stmt.target
                elif (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                      and isinstance(stmt.targets[0], ast.Name)):
                    target = stmt.targets[0]
                if target is not None:
                    stores.setdefault(target.id, stmt.lineno)
                    for n in ast.walk(cls):
                        if (isinstance(n, ast.Name) and n.id == target.id
                                and isinstance(n.ctx, ast.Load)):
                            real_loads.add(target.id)

        if dynamic_access:
            continue
        for name, line in stores.items():
            if name in real_loads or name.startswith("__"):
                continue
            private = name.startswith("_")
            # a public attribute set in __init__ is the standard way to expose
            # state; only flag it when nothing in the file touches it either
            if not private and file_tokens[name] > 1:
                continue
            detail = (f"'{name}' is only ever incremented in {cls.name}, "
                      "never read"
                      if name in aug_only
                      else f"'{name}' is assigned in {cls.name} but never read "
                           "in the class")
            add(findings, path, line, "P2" if private else "P3", "unused-field",
                detail + (" - confirm no subclass or external reader"
                          if not private else " - confirm no subclass reader"),
                anchor_of(lines, line))

    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        load_count, store_count = defaultdict(int), defaultdict(int)
        declared_elsewhere = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Name):
                if isinstance(n.ctx, ast.Load):
                    load_count[n.id] += 1
                else:
                    store_count[n.id] += 1
            elif isinstance(n, (ast.Global, ast.Nonlocal)):
                declared_elsewhere.update(n.names)
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Assign) and len(n.targets) == 1
                    and isinstance(n.targets[0], ast.Name)):
                continue
            name = n.targets[0].id
            if (name == "_" or name.startswith("_")
                    or name in declared_elsewhere or store_count[name] > 1):
                continue
            anchor = anchor_of(lines, n.lineno)
            if load_count[name] == 0:
                add(findings, path, n.lineno, "P2", "dead-local",
                    f"'{name}' is assigned in {fn.name} and never read", anchor)
            elif isinstance(n.value, ast.Name) and load_count[name] == 1:
                add(findings, path, n.lineno, "P3", "alias-variable",
                    f"'{name}' just renames '{n.value.id}' for a single use - "
                    "inline it", anchor)


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------

MOCK_ASSERT = re.compile(r"^assert_(called|any_call|has_calls|not_called)")
MOCK_FACTORY = re.compile(r"\b(Mock|MagicMock|AsyncMock|patch|mocker|monkeypatch)\b")


ASSERTING_CTX = re.compile(
    r"(raises|warns|assertRaises|assertWarns|assertLogs|assertNoLogs|"
    r"deprecated_call|ExpectedException|assertRaisesRegex)")


def _is_assert_call(node):
    """assertX(...), a bare pytest assert, or a `with` whose context manager
    is an assertion - `with pytest.raises(ValueError):` is how both pytest and
    unittest express the entire error-path contract."""
    if isinstance(node, ast.Assert):
        return True
    if isinstance(node, (ast.With, ast.AsyncWith)):
        for item in node.items:
            if ASSERTING_CTX.search(ast.dump(item.context_expr)):
                return True
        return False
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        fn = node.value.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        # leading underscores are a naming choice, not a signal; custom
        # helpers named expect_*/verify_*/check_* assert just as hard
        return bool(re.match(r"_*(assert|ASSERT|expect|verify|check|should)",
                             name))
    return False


def _assert_name(node):
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        fn = node.value.func
        return fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
    return ""


def _is_tautology(node):
    """assert True, assert 1, assert x == x, assertTrue(True)."""
    if isinstance(node, ast.Assert):
        t = node.test
        if isinstance(t, ast.Constant) and bool(t.value):
            return True
        if (isinstance(t, ast.Compare) and len(t.ops) == 1
                and isinstance(t.ops[0], (ast.Eq, ast.Is))):
            return ast.dump(t.left) == ast.dump(t.comparators[0])
        return False
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        name = _assert_name(node)
        args = node.value.args
        if name in ("assertTrue", "assertFalse") and len(args) == 1:
            return isinstance(args[0], ast.Constant)
        if name in ("assertEqual", "assertIs") and len(args) == 2:
            return ast.dump(args[0]) == ast.dump(args[1])
    return False


def _body_shape(fn):
    """AST dump with every literal blanked, so two tests that differ only in
    their constants hash the same. That is the parametrize signal."""
    class Blank(ast.NodeTransformer):
        def visit_Constant(self, node):
            return ast.copy_location(ast.Constant(value=None), node)
    clone = Blank().visit(ast.parse(ast.unparse(fn))) if hasattr(ast, "unparse") else None
    if clone is None:
        return None
    for n in ast.walk(clone):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n.name = "_"
            for a in n.args.args:
                a.arg = "_"
        if isinstance(n, ast.Name):
            n.id = "_" if n.id.startswith("expected") else n.id
    return ast.dump(clone)


def _decorator_name(dec):
    """Dotted name of a decorator, with any call stripped: `pytest.fixture`,
    `pytest.mark.skip`, `fixture`."""
    node = dec.func if isinstance(dec, ast.Call) else dec
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def check_python_tests(path, tree, lines, findings):
    """Redundancy in generated tests.

    Generated suites inflate: a test per branch that all assert the same
    thing, tests that only prove the mock was called, and asserts that cannot
    fail. Coverage numbers go up and nothing is actually verified, which is
    worse than no test - it buys false confidence and costs maintenance.
    """
    tests = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and (n.name.startswith("test_") or n.name.startswith("test"))
             and n.name != "test"]
    fixtures = {}
    used_names = defaultdict(int)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            used_names[n.id] += 1
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for dec in fn.decorator_list:
            # Match the decorator's dotted name, never its dumped source. A
            # @parametrize list whose data happens to contain the strings
            # "fixture" or "skip" is not a fixture and is not skipped.
            name = _decorator_name(dec)
            if name.split(".")[-1] == "fixture":
                fixtures[fn.name] = fn.lineno
            if name.split(".")[-1] in ("skip", "skipif", "xfail"):
                if not any(isinstance(k, ast.keyword) and k.arg == "reason"
                           for k in getattr(dec, "keywords", [])):
                    add(findings, path, fn.lineno, "P3", "skip-without-reason",
                        f"'{fn.name}' is skipped with no reason - nobody knows "
                        "when to re-enable it", anchor_of(lines, fn.lineno))

    fixture_params = set()
    for fn in tests:
        fixture_params.update(a.arg for a in fn.args.args)
    # a fixture requested by another fixture is used, and an autouse fixture
    # is requested by everything without naming anything
    for name in list(fixtures):
        for fn in ast.walk(tree):
            if (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and fn.name in fixtures and fn.name != name):
                fixture_params.update(a.arg for a in fn.args.args)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in fn.decorator_list:
            if any(isinstance(k, ast.keyword) and k.arg == "autouse"
                   for k in getattr(dec, "keywords", [])):
                fixture_params.add(fn.name)
    for name, line in fixtures.items():
        if name not in fixture_params and used_names[name] <= 1:
            add(findings, path, line, "P2", "unused-fixture",
                f"fixture '{name}' is never requested by any test",
                anchor_of(lines, line))

    shapes = defaultdict(list)
    for fn in tests:
        asserts = [n for n in ast.walk(fn) if _is_assert_call(n)]
        anchor = anchor_of(lines, fn.lineno)

        if not asserts:
            add(findings, path, fn.lineno, "P1", "test-without-assertion",
                f"'{fn.name}' asserts nothing - it only proves the code did "
                "not raise", anchor)
        else:
            if all(_is_tautology(a) for a in asserts):
                add(findings, path, fn.lineno, "P1", "tautological-test",
                    f"'{fn.name}' only makes assertions that cannot fail",
                    anchor)
            elif any(_is_tautology(a) for a in asserts):
                for a in asserts:
                    if _is_tautology(a):
                        add(findings, path, a.lineno, "P2", "tautological-assert",
                            "this assertion cannot fail", anchor_of(lines, a.lineno))
            # assert_called* exists only on a test double, so its presence is
            # the signal - the mock does not have to be constructed in the
            # test body, and usually it arrives from a fixture instead.
            if all(MOCK_ASSERT.match(_assert_name(a)) for a in asserts):
                add(findings, path, fn.lineno, "P1", "mock-only-test",
                    f"'{fn.name}' asserts only that a mock was called - it "
                    "tests the test double, not the code", anchor)

        shape = _body_shape(fn)
        if shape:
            shapes[shape].append(fn)

    for group in shapes.values():
        if len(group) < 2:
            continue
        first = group[0]
        names = ", ".join(f.name for f in group[1:])
        add(findings, path, first.lineno, "P2", "duplicate-test",
            f"'{first.name}' is structurally identical to {names} - differs "
            "only in literals, so one parametrized test may cover them all; "
            "keep them separate if they pin different risks (boundaries, "
            "regressions)", anchor_of(lines, first.lineno))


# Test declarations, by family. Everything here opens a block on the same or
# the next line; the block finder below is brace- or indentation-based.
TEST_DECL = [
    # (regex, family, name group or None)
    (re.compile(r"^\s*\[(Test|TestCase|TestMethod|Fact|Theory)[\(\]]"), "attr", None),
    (re.compile(r"^\s*@(Test|ParameterizedTest|RepeatedTest)\b"), "attr", None),
    (re.compile(r"^\s*#\[(test|tokio::test|rstest|async_std::test)\b"), "attr", None),
    (re.compile(r"^\s*(TEST|TEST_F|TEST_P|TYPED_TEST)\s*\("), "inline", None),
    (re.compile(r"^\s*func\s+(Test\w+)\s*\("), "inline", 1),
    (re.compile(r"^\s*(?:public\s+|private\s+)?func\s+(test\w+)\s*\("), "inline", 1),
    (re.compile(r"^\s*(?:async\s+)?(?:it|test)(?:\.\w+)?\s*[\(`]"), "inline", None),
    (re.compile(r"^\s*(?:it|specify|example)\s+[\"'].*\s+do\b"), "ruby", None),
]
# Anything that can fail the test. Deliberately broad: a false "no assertion"
# on a real test is a P1 that wastes a reviewer's time, so err toward silence.
RE_ASSERTION = re.compile(
    r"\b(Assert\.|Assert::|Assertions\.|StringAssert|CollectionAssert|"
    r"assert\w*\s*[\(!.]|assert_\w+|EXPECT_|ASSERT_|CHECK\(|REQUIRE\(|"
    r"expect\w*\s*[\({]|\.should\b|Should\(\)|\.Should\b|shouldBe\b|"
    r"is_expected\b|"
    r"t\.(Error|Errorf|Fatal|Fatalf|Fail|FailNow)\b|"
    r"require\.\w+|verifyThat|panic!|unwrap\w*\(\)|expect_err|"
    r"should_panic|toMatchSnapshot|XCTAssert|Approvals\.)"
)
# Verifying a double is not the same as checking the result.
RE_MOCK_VERIFY = re.compile(
    r"(?<!Approvals\.)(?<!\w)(Verify|VerifyNoOtherCalls|Received|EXPECT_CALL|"
    r"AssertExpectations|toHaveBeenCalled\w*|assert_called\w*|have_received|"
    r"verify)\s*\(")
RE_SKIP_NO_REASON = re.compile(
    r"^\s*(?:@(?:Ignore|Disabled)\s*(?:\(\s*\))?\s*$"
    r"|#\[ignore\]\s*$"
    r"|\[Ignore\s*\]\s*$"
    r"|(?:it|test|describe)\.skip\b"
    r"|@Disabled\s*(?:\(\s*\))?\s*$"
    r"|#\[ignore\]"
    r"|t\.Skip(?:Now)?\(\s*\))")

RE_LITERAL = re.compile(
    r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|-?\b\d+(?:\.\d+)?\b")
RE_TAUTOLOGY = [
    # expect(true).toBe(true) / expect(1).toEqual(1)
    re.compile(r"expect\s*\(\s*([^()]+?)\s*\)\s*\.\s*(?:toBe|toEqual|"
               r"toStrictEqual|to\.equal|toBeTruthy)\s*\(\s*([^()]*?)\s*\)"),
    # assertEquals(2, 2) / assert.Equal(t, 1, 1) / EXPECT_EQ(1, 1) / assert_eq!(1, 1)
    re.compile(r"(?:assertEquals|assertEqual|assert_eq!|EXPECT_EQ|ASSERT_EQ|"
               r"Assert\.AreEqual|assert\.Equal)\s*\(\s*(?:t\s*,\s*)?"
               r"([^,()]+?)\s*,\s*([^,()]+?)\s*\)"),
]
RE_TRUE_LITERAL = re.compile(
    r"^(true|True|1|assertTrue\(true\)|XCTAssertTrue\(true\))$")


def _block_end_brace(lines, start, lookahead=3):
    """End line of the block opened at `start`.

    A brace-less test - `it('x', () => expect(y).toBe(1));` or a C#
    expression-bodied method - has no block at all. Scanning forward for the
    next `{` used to consume the FOLLOWING test's body and then skip past it,
    so an assertionless test hiding behind a one-liner was never seen. If no
    brace shows up within `lookahead` lines, treat the statement itself as
    the body.
    """
    depth, started = 0, False
    for j in range(start, len(lines)):
        c = strip_code(lines[j])
        if not started and j - start >= lookahead and "{" not in c:
            return start
        depth += c.count("{") - c.count("}")
        if "{" in c:
            started = True
        if started and depth <= 0:
            return j
        if not started and c.rstrip().endswith(";"):
            return j
    return None


def _block_end_ruby(lines, start):
    """RSpec blocks close with `end` at the opening line's indentation.

    Indentation is not syntax in Ruby, but it is universal convention in spec
    files. If the aligned `end` is not there, return None and say nothing -
    a guessed block boundary produces false P1s, which is the failure this
    whole pass is supposed to avoid.
    """
    indent = len(lines[start]) - len(lines[start].lstrip())
    for j in range(start + 1, len(lines)):
        text = lines[j]
        if not text.strip():
            continue
        if (len(text) - len(text.lstrip())) == indent and text.strip() == "end":
            return j
    return None


def _normalise_body(lines, start, end):
    """Body with comments, literals and whitespace flattened, so two tests
    that differ only in their data hash the same.

    Starts after the line carrying the body's opening brace, not after the
    declaration line. For attribute families ([Test], @Test, #[test]) the
    declaration is the attribute and the signature comes next, so slicing
    from start+1 baked each test's unique method name into its shape and the
    rule could never fire.
    """
    first = start + 1
    for j in range(start, min(end, start + 6)):
        if "{" in strip_code(lines[j]):
            first = j + 1
            break
    body = " ".join(strip_code(t) for t in lines[first:end])
    body = RE_LITERAL.sub("@", body)
    return re.sub(r"\s+", " ", body).strip()


def check_generic_tests(path, lines, findings):
    """Test redundancy for every non-Python language the diff might contain.

    Generated suites inflate the same way in all of them: a test per input
    that asserts the same thing, a test that only proves nothing threw, and a
    test that checks the mock rather than the result. Coverage climbs and
    nothing is verified, which is worse than no test - it buys false
    confidence and charges maintenance for it.
    """
    if not TEST_HINT.search(path):
        return
    n = len(lines)
    i = 0
    shapes = defaultdict(list)
    while i < n:
        code = strip_code(lines[i])
        family = None
        for rx, fam, _grp in TEST_DECL:
            if rx.match(code):
                family = fam
                break
        if family is None:
            i += 1
            continue
        end = (_block_end_ruby(lines, i) if family == "ruby"
               else _block_end_brace(lines, i))
        if end is None or end <= i:
            i += 1
            continue
        body = "\n".join(strip_code(t) for t in lines[i:end + 1])
        anchor = anchor_of(lines, i + 1)

        # An assertion that only inspects a double is not a check on the
        # result. `expect(log).toHaveBeenCalled()` reads like an assertion and
        # matches RE_ASSERTION, so compare line by line rather than asking
        # whether the body contains an assertion anywhere.
        asserting = [t for t in (strip_code(x) for x in lines[i:end + 1])
                     if RE_ASSERTION.search(t)]
        mock_lines = [t for t in asserting if RE_MOCK_VERIFY.search(t)]
        if not asserting:
            if RE_MOCK_VERIFY.search(body):
                add(findings, path, i + 1, "P1", "mock-only-test",
                    "test verifies mock interactions but asserts nothing about "
                    "the result - it tests the double, not the code", anchor)
            else:
                add(findings, path, i + 1, "P1", "test-without-assertion",
                    "test body contains no assertion - it only proves the code "
                    "did not throw", anchor)
        elif len(mock_lines) == len(asserting):
            # Verifying an interaction is the contract for a publisher, a
            # mailer, a logger. The scanner cannot tell those from mock
            # theatre, so it hedges rather than asserting false coverage.
            add(findings, path, i + 1, "P2", "mock-only-test",
                "every assertion here checks a mock rather than a result - "
                "confirm the interaction IS the contract, otherwise assert on "
                "the outcome too", anchor)
        else:
            for rx in RE_TAUTOLOGY:
                m = rx.search(body)
                if m and m.group(1).strip() == m.group(2).strip():
                    add(findings, path, i + 1, "P2", "tautological-assert",
                        f"asserts {m.group(1).strip()} equals itself - cannot "
                        "fail", anchor)
                    break
            else:
                m = re.search(r"(?:assert|XCTAssertTrue|EXPECT_TRUE|ASSERT_TRUE)"
                              r"[!\s]*\(\s*(true|True|1)\s*\)", body)
                if m:
                    add(findings, path, i + 1, "P2", "tautological-assert",
                        "asserts a literal true - cannot fail", anchor)

        near = [strip_code(lines[k]) for k in range(max(0, i - 3), i)]
        near.append(code)
        near.extend(strip_code(lines[k]) for k in range(i, min(end + 1, i + 4)))
        if any(RE_SKIP_NO_REASON.search(t) for t in near):
            add(findings, path, i + 1, "P3", "skip-without-reason",
                "test is skipped with no reason - nobody knows when to "
                "re-enable it", anchor)

        shape = _normalise_body(lines, i, end)
        if shape and len(shape) > 20:
            shapes[shape].append(i + 1)
        i = end + 1

    for shape, at in shapes.items():
        if len(at) < 2:
            continue
        add(findings, path, at[0], "P2", "duplicate-test",
            f"structurally identical to the test(s) at line(s) "
            f"{', '.join(str(x) for x in at[1:])} - differs only in literals, "
            "so one table-driven or parametrized test covers them all",
            anchor_of(lines, at[0]))


# --------------------------------------------------------------------------
# c# / unity
# --------------------------------------------------------------------------

RE_CS_NULLCOND = re.compile(r"(\w+)\s*(\?\.|\?\?=|\?\?|\?\[)")
RE_CS_EMPTY_LIFECYCLE = re.compile(
    r"\b(void\s+(Awake|Start|Update|FixedUpdate|LateUpdate|OnEnable|OnDisable|"
    r"OnDestroy)\s*\(\s*\)\s*\{\s*\})"
)
RE_CS_ASYNC_VOID = re.compile(r"\basync\s+void\b")
RE_CS_DEBUG_LOG = re.compile(r"\bDebug\.(Log|LogWarning|LogError)\s*\(")
RE_CS_EXPENSIVE = re.compile(r"\b(Camera\.main|FindObjectOfType|GameObject\.Find)\b")
RE_CS_PERFRAME = re.compile(r"\b(GetComponent(InChildren|InParent)?<|Camera\.main|"
                            r"FindObjectOfType|GameObject\.Find)\b")
RE_CS_METHOD = re.compile(r"\bvoid\s+(Update|FixedUpdate|LateUpdate)\s*\(\s*\)")
RE_CS_LINQ = re.compile(r"\.(Where|Select|OrderBy|ToList|ToArray|Any|First)\s*\(")

# UnityEngine.Object subclasses, where `?.` and `??` skip the lifetime check.
UNITY_OBJECT_TYPES = {
    "GameObject", "Transform", "RectTransform", "Component", "Behaviour",
    "MonoBehaviour", "ScriptableObject", "Rigidbody", "Rigidbody2D",
    "Collider", "Collider2D", "BoxCollider", "SphereCollider", "CapsuleCollider",
    "Renderer", "MeshRenderer", "SkinnedMeshRenderer", "SpriteRenderer",
    "Animator", "Animation", "AudioSource", "AudioClip", "Camera", "Light",
    "Material", "Texture", "Texture2D", "Sprite", "Mesh", "Canvas",
    "CanvasGroup", "Image", "RawImage", "Text", "TextMesh", "TMP_Text",
    "TextMeshProUGUI", "Button", "Slider", "Toggle", "ParticleSystem",
    "NavMeshAgent", "CharacterController", "LineRenderer", "TrailRenderer",
    "Rigidbody", "Object", "UnityEngine.Object", "AudioMixer", "Shader",
}
UNITY_BUILTIN_MEMBERS = {
    "transform", "gameObject", "rigidbody", "collider", "renderer", "camera",
    "animation", "audio", "light", "particleSystem",
}
# Inherited members that are NOT UnityEngine.Object - `name ?? "x"` is fine.
UNITY_BUILTIN_VALUES = {"name", "tag", "layer", "enabled", "isActiveAndEnabled"}
# Types that are definitively not UnityEngine.Object, so `?.` on them is fine.
NON_UNITY_TYPES = {
    "string", "String", "int", "float", "double", "bool", "byte", "char",
    "long", "short", "decimal", "object", "Vector2", "Vector3", "Vector4",
    "Quaternion", "Color", "Rect", "Bounds", "List", "Dictionary", "HashSet",
    "Queue", "Stack", "IEnumerable", "IList", "IDictionary", "Array",
    "Action", "Func", "Task", "Exception", "StringBuilder", "Guid",
    "DateTime", "TimeSpan", "Nullable", "EventHandler", "Coroutine",
}
RE_CS_DECL = re.compile(
    r"\b([A-Za-z_]\w*)\s*(?:<[^<>();]*>)?\s+([A-Za-z_]\w*)\s*(?:=|;|,|\)|\{)")
RE_CS_CLASS_DECL = re.compile(r"\bclass\s+(\w+)\s*:\s*([\w\s,<>\.]+)")


def _cs_identifier_types(lines):
    """Best-effort map of identifier -> declared type name for one file."""
    types = {}
    unity_classes = set()
    for text in lines:
        m = RE_CS_CLASS_DECL.search(text)
        if m:
            bases = {b.strip().split(".")[-1] for b in m.group(2).split(",")}
            if bases & UNITY_OBJECT_TYPES:
                unity_classes.add(m.group(1))
    for text in lines:
        for m in RE_CS_DECL.finditer(strip_code(text)):
            type_name, ident = m.group(1), m.group(2)
            if type_name in ("return", "new", "case", "else", "in", "is", "as",
                             "using", "namespace", "class", "struct", "void"):
                continue
            types.setdefault(ident, type_name)
    return types, unity_classes


def _cs_perframe_ranges(lines):
    """Approximate line ranges of Update-family method bodies via brace depth."""
    ranges = []
    i = 0
    while i < len(lines):
        if RE_CS_METHOD.search(strip_code(lines[i])):
            depth = 0
            started = False
            start = i + 1
            for j in range(i, len(lines)):
                code = strip_code(lines[j])
                depth += code.count("{") - code.count("}")
                if "{" in code:
                    started = True
                if started and depth <= 0:
                    ranges.append((start, j + 1))
                    i = j
                    break
        i += 1
    return ranges


def check_csharp(path, lines, findings):
    joined = "\n".join(lines)
    is_unity = "using UnityEngine" in joined
    perframe = _cs_perframe_ranges(lines) if is_unity else []
    ident_types, unity_classes = (_cs_identifier_types(lines) if is_unity
                                  else ({}, set()))

    for m in RE_CS_EMPTY_LIFECYCLE.finditer(joined):
        line = joined[: m.start()].count("\n") + 1
        add(findings, path, line, "P2", "empty-lifecycle",
            "empty Unity lifecycle method still costs a native->managed call "
            "per frame", anchor_of(lines, line))

    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        anchor = anchor_of(lines, idx)
        code = strip_code(text)

        if is_unity:
            for m in RE_CS_NULLCOND.finditer(code):
                recv = m.group(1)
                declared = ident_types.get(recv)
                base = declared.split(".")[-1] if declared else None
                if (recv in UNITY_BUILTIN_MEMBERS
                        or base in UNITY_OBJECT_TYPES
                        or base in unity_classes):
                    add(findings, path, idx, "P1", "unity-null-conditional",
                        f"'{recv}' is a UnityEngine.Object - ?. and ?? skip the "
                        "destroyed-object check; use an explicit != null",
                        anchor)
                elif base in NON_UNITY_TYPES or recv in UNITY_BUILTIN_VALUES:
                    pass  # plain C#, the operators mean what they say
                else:
                    add(findings, path, idx, "P3", "unity-null-conditional",
                        f"?. / ?? on '{recv}', type not resolvable here - "
                        "confirm it is not a UnityEngine.Object", anchor)
                break

        if RE_CS_ASYNC_VOID.search(code):
            add(findings, path, idx, "P2", "async-void",
                "async void - exceptions escape unobservable", anchor)

        if is_unity and RE_CS_DEBUG_LOG.search(code):
            add(findings, path, idx, "P3", "debug-log",
                "Debug.Log ships to builds - gate or delete", anchor)

        if is_unity and RE_CS_EXPENSIVE.search(code):
            add(findings, path, idx, "P2", "expensive-lookup",
                "scene-wide lookup - cache in Awake", anchor)

        in_perframe = any(lo <= idx <= hi for lo, hi in perframe)
        if in_perframe and RE_CS_PERFRAME.search(code):
            add(findings, path, idx, "P2", "perframe-lookup",
                "component lookup inside a per-frame method", anchor)
        if in_perframe and RE_CS_LINQ.search(code):
            add(findings, path, idx, "P2", "perframe-linq",
                "LINQ in a per-frame method allocates every frame", anchor)


# --------------------------------------------------------------------------
# c++ / ue5
# --------------------------------------------------------------------------

RE_CPP_STD = re.compile(
    r"\bstd::(vector|map|unordered_map|set|string|shared_ptr|unique_ptr|optional)\b")
RE_CPP_IOSTREAM = re.compile(r"\b(std::cout|std::cerr|printf)\s*(<<|\()")
RE_CPP_TRY = re.compile(r"\b(try\s*\{|catch\s*\()")
RE_CPP_MEMBER_PREFIX = re.compile(r"\bm_[A-Za-z]")
RE_CPP_UOBJ_MEMBER = re.compile(
    r"^\s*(?:class\s+)?([UA][A-Z]\w+)\s*\*\s*(\w+)\s*(=\s*([^;]+))?;\s*$")
RE_CPP_TARRAY_VALUE = re.compile(r"\(\s*(?!const\b)TArray<[^>]+>\s+\w+")
RE_CPP_FSTRING_VALUE = re.compile(r"\(\s*(?!const\b)FString\s+\w+\s*[,)]")
RE_CPP_REDUNDANT_NULL = re.compile(
    r"\bif\s*\(\s*!?\s*(IsValid\s*\(\s*)?\w+\s*\)?\s*(!=\s*nullptr)?\s*\)")
RE_CPP_NEWOBJECT = re.compile(r"\b(NewObject<|CreateDefaultSubobject<)")
RE_CPP_CLASS_OPEN = re.compile(
    r"^\s*(?:template\s*<[^>]*>\s*)?(class|struct)\s+(?:\w+_API\s+)?\w+"
    r"(?:\s*:\s*[^;{]+)?\s*(\{)?\s*$")
RE_CPP_FUNC_OPEN = re.compile(r"\)\s*(const)?\s*(noexcept)?\s*(override)?\s*\{\s*$")
NULLISH_INIT = {"nullptr", "null", "NULL", "{}", "0"}


def _cpp_member_ranges(lines):
    """Line ranges that are inside a class/struct body but not inside a
    function body.

    Without this, every local `UWorld* World = GetWorld();` in a .cpp was
    reported P1 as an unrooted UObject member. Locals are on the stack; the
    GC rule is about members.
    """
    ranges = []
    i = 0
    n = len(lines)
    while i < n:
        m = RE_CPP_CLASS_OPEN.match(strip_code(lines[i]))
        if not m:
            i += 1
            continue
        # find the opening brace (same line or the next non-empty one)
        j = i
        if not m.group(2):
            while j + 1 < n and "{" not in strip_code(lines[j]):
                j += 1
                if strip_code(lines[j]).strip().endswith(";"):
                    break
        if "{" not in strip_code(lines[j]):
            i += 1
            continue
        depth = 0
        start = j + 1
        func_depth = None
        for k in range(j, n):
            code = strip_code(lines[k])
            opens, closes = code.count("{"), code.count("}")
            if func_depth is None and RE_CPP_FUNC_OPEN.search(code) and depth >= 1:
                func_depth = depth  # inline method body begins here
            before = depth
            depth += opens - closes
            if func_depth is not None and depth <= func_depth:
                func_depth = None
            elif func_depth is None and before >= 1 and depth >= 1:
                pass
            if depth <= 0 and k > j:
                ranges.append((start, k + 1))
                i = k
                break
        else:
            ranges.append((start, n))
            break
        i += 1
    return ranges


def _cpp_function_ranges(lines):
    """Line ranges inside a function body (top level or inline)."""
    ranges = []
    n = len(lines)
    k = 0
    while k < n:
        code = strip_code(lines[k])
        if RE_CPP_FUNC_OPEN.search(code):
            depth = 0
            for j in range(k, n):
                c = strip_code(lines[j])
                depth += c.count("{") - c.count("}")
                if depth <= 0 and j > k:
                    ranges.append((k + 1, j + 1))
                    k = j
                    break
            else:
                ranges.append((k + 1, n))
                break
        k += 1
    return ranges


def check_cpp(path, lines, findings):
    joined = "\n".join(lines)
    is_ue = ("UPROPERTY" in joined or "UCLASS" in joined
             or "#include \"CoreMinimal.h\"" in joined or "AActor" in joined)
    member_ranges = _cpp_member_ranges(lines) if is_ue else []
    func_ranges = _cpp_function_ranges(lines) if is_ue else []

    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        prev = lines[idx - 2] if idx >= 2 else ""
        anchor = anchor_of(lines, idx)

        if is_ue and RE_CPP_STD.search(text):
            add(findings, path, idx, "P2", "std-in-ue",
                "std container in Unreal code - TArray/TMap/FString are the "
                "house convention", anchor)

        if RE_CPP_IOSTREAM.search(text):
            add(findings, path, idx, "P2", "raw-output",
                "printf/iostream instead of UE_LOG", anchor)

        if is_ue and RE_CPP_TRY.search(text):
            add(findings, path, idx, "P2", "exceptions-in-ue",
                "most UE builds disable exceptions - check the module's build "
                "settings", anchor)

        if is_ue and RE_CPP_MEMBER_PREFIX.search(text):
            add(findings, path, idx, "P3", "member-prefix",
                "m_ prefix is not the Unreal naming convention", anchor)

        m = RE_CPP_UOBJ_MEMBER.match(text) if is_ue else None
        if m:
            init = (m.group(4) or "").strip()
            in_member = any(lo <= idx <= hi for lo, hi in member_ranges)
            in_func = any(lo <= idx <= hi for lo, hi in func_ranges)
            has_prop = "UPROPERTY" in prev or "UPROPERTY" in text
            # a declaration with a real initialiser inside a function body is a
            # local, and locals are not GC roots to begin with
            is_local = in_func and not in_member
            if (in_member and not is_local and not has_prop
                    and (not init or init in NULLISH_INIT)):
                add(findings, path, idx, "P1", "unrooted-uobject",
                    f"'{m.group(2)}' is a raw UObject* member without "
                    "UPROPERTY() - invisible to the GC", anchor)

        if RE_CPP_TARRAY_VALUE.search(text) or RE_CPP_FSTRING_VALUE.search(text):
            add(findings, path, idx, "P2", "pass-by-value",
                "TArray/FString taken by value - copies on every call", anchor)

        if RE_CPP_NEWOBJECT.search(prev) and RE_CPP_REDUNDANT_NULL.search(text):
            add(findings, path, idx, "P2", "impossible-null-check",
                "NewObject/CreateDefaultSubobject cannot return null - it "
                "crashes instead", anchor)


# --------------------------------------------------------------------------
# shared: unused members and alias locals for brace languages
# --------------------------------------------------------------------------

RE_MEMBER_DECL = re.compile(
    r"^\s*(?:\[[^\]]*\]\s*)*"
    r"(?:(?:public|private|protected|internal|static|readonly|const|mutable|"
    r"volatile|virtual|override|serialize|inline)\s+)*"
    r"[\w:<>,\s\*&\[\]]+?\s+(\w+)\s*(?:=[^;]*)?;\s*$")
RE_ALIAS_LOCAL = re.compile(
    r"^\s*(?:var|auto|const\s+auto|[\w:<>\*&]+)\s+(\w+)\s*=\s*"
    r"([A-Za-z_]\w*)\s*;\s*$")
RE_DECL_SKIP = re.compile(
    r"^\s*(return|using|import|package|namespace|#|//|/\*|\*|typedef|delegate|"
    r"friend|template|else|case|partial)\b")
EXPOSED = re.compile(r"\b(public|protected|internal|UPROPERTY|UFUNCTION|"
                     r"SerializeField|Serializable|export)\b")


def check_bindings(path, lines, findings, exposed_note):
    """Bindings declared and never referenced (fields or locals); locals that
    only rename another binding for a single use.

    Whole-file token counting cannot see other files, other translation units,
    partial classes, or reflection. Anything exposed is therefore P3 with a
    confirm note, never a delete instruction.
    """
    stripped = [strip_code(t) for t in lines]
    counts = defaultdict(int)
    for token in re.findall(r"\b[A-Za-z_]\w*\b", "\n".join(stripped)):
        counts[token] += 1
    is_partial = bool(re.search(r"\bpartial\s+(class|struct)\b", "\n".join(stripped)))
    is_header = os.path.splitext(path)[1].lower() in {".h", ".hpp", ".inl"}

    for idx in range(1, len(lines) + 1):
        text = lines[idx - 1]
        anchor = anchor_of(lines, idx)
        # test the declaration half only - an initialiser may legitimately
        # contain a call (`private List<int> items = new List<int>();`)
        decl_part = text.split("=", 1)[0]
        if RE_DECL_SKIP.match(text) or "(" in decl_part or ")" in decl_part:
            continue

        m = RE_ALIAS_LOCAL.match(text)
        if m:
            name, source = m.group(1), m.group(2)
            if counts[name] == 2 and source not in ("new", "this", "nullptr", "null"):
                add(findings, path, idx, "P3", "alias-variable",
                    f"'{name}' just renames '{source}' for a single use - "
                    "inline it", anchor)
                continue

        m = RE_MEMBER_DECL.match(text)
        if m:
            name = m.group(1)
            if counts[name] == 1 and len(name) > 1:
                prev = lines[idx - 2] if idx >= 2 else ""
                is_exposed = bool(EXPOSED.search(text) or EXPOSED.search(prev))
                # a header declares; the definition and every caller live
                # elsewhere, so "unreferenced in this file" means nothing
                if is_header or is_partial:
                    is_exposed = True
                add(findings, path, idx,
                    "P3" if is_exposed else "P2", "unused-binding",
                    f"'{name}' is declared and never referenced in this file"
                    + (f" - {exposed_note}" if is_exposed else ""), anchor)
            continue


# --------------------------------------------------------------------------
# reconciliation with a previous run
# --------------------------------------------------------------------------

def finding_key(f):
    """Stable across line shifts, unique per instance.

    Line numbers move as soon as you delete anything, so they cannot be part
    of the key. The message alone is not enough either - most rules emit a
    constant string, so N instances in one file collapsed to one key and
    fixing some of them showed up as neither resolved nor live. The anchor is
    the normalised source line, which distinguishes them and survives shifts.
    """
    return (f["path"], f["rule"], f["message"], f.get("anchor", ""))


def reconcile(findings, prior_path):
    """Mark findings new/persisting and return the ones that are gone.

    A finding present in the prior report and absent now is either fixed or no
    longer true. Either way it must not be re-reported as live - a punch list
    that keeps resurfacing settled items stops being read.
    """
    try:
        with open(prior_path, encoding="utf-8") as fh:
            prior = json.load(fh)
    except (OSError, ValueError) as exc:
        warn(f"--since: could not read {prior_path} ({exc}) - "
             "reporting every finding as new")
        return None, []

    prior_findings = prior.get("findings", [])
    if prior_findings and "anchor" not in prior_findings[0]:
        warn(f"--since: {prior_path} predates anchored keys - "
             "reconciliation may be approximate")
    prior_keys = {}
    for f in prior_findings:
        prior_keys.setdefault(finding_key(f), []).append(f)
    now_counts = defaultdict(int)
    for f in findings:
        key = finding_key(f)
        now_counts[key] += 1
        f["status"] = "persisting" if key in prior_keys else "new"

    resolved = []
    for key, group in prior_keys.items():
        gone = len(group) - now_counts.get(key, 0)
        for f in group[:max(0, gone)]:
            f["status"] = "resolved"
            resolved.append(f)
    return prior.get("generated"), resolved


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def scan_file(path, findings, max_bytes=DEFAULT_MAX_BYTES):
    reason = skip_path(path, max_bytes)
    if reason:
        READ_ERRORS.append({"path": path, "error": "skipped: " + reason})
        return
    lines = read_lines(path)
    if lines is None:
        return
    ext = os.path.splitext(path)[1].lower()
    check_universal(path, lines, findings)
    if ext not in PY_EXT:
        # Python has its own AST-based pass inside check_python; every other
        # language goes through the generic one, including the ones with no
        # language rules of their own. A JS or Go test file gets the
        # redundancy pass even though nothing else here understands JS or Go.
        check_generic_tests(path, lines, findings)
    if ext in PY_EXT:
        check_python(path, lines, findings)
    elif ext in CS_EXT:
        check_csharp(path, lines, findings)
        check_bindings(path, lines, findings,
                       "Inspector/API surface, confirm before removing")
    elif ext in CPP_EXT:
        check_cpp(path, lines, findings)
        check_bindings(path, lines, findings,
                       "Blueprint/API surface, confirm before removing")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paths", nargs="*", help="scan whole files instead of a diff")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-severity", choices=["P1", "P2", "P3"], default="P3")
    ap.add_argument("--scope", choices=["auto", "worktree", "staged",
                                        "unstaged", "branch"], default="auto",
                    help="auto: all uncommitted work (staged + unstaged + "
                         "untracked), falling back to the branch diff")
    ap.add_argument("--base", help="base ref for --scope branch")
    ap.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--whole-files", "--all-scope", dest="whole_files",
                    action="store_true",
                    help="report findings on untouched lines OF THE FILES THIS "
                         "DIFF TOUCHES, marked pre-existing. This is not a "
                         "repo-wide scan and there isn't one - to audit other "
                         "files, name them with --paths.")
    ap.add_argument("--report-name", action="store_true",
                    help="print the canonical report filename stem and exit")
    ap.add_argument("--stem", help="use this report stem verbatim, so the "
                                   "filename and the JSON agree across calls")
    ap.add_argument("--since", metavar="PRIOR.json",
                    help="reconcile against a previous run's JSON: mark findings "
                         "new/persisting and list ones no longer true")
    args = ap.parse_args()

    if args.report_name:
        if args.paths:
            print(report_stem("files"))
            return 0
        _, target, _added = resolve_diff(args.scope, args.base)
        if target is None:
            for w in WARNINGS:
                print("warning: " + w, file=sys.stderr)
            print("No diff found - cannot name a report for an empty scope.",
                  file=sys.stderr)
            return 1
        print(report_stem(target))
        return 0

    findings = []
    if args.paths:
        target = "files"
        label = f"{len(args.paths)} named file(s), full contents"
        root = repo_root()
        for p in args.paths:
            rel = p
            if root and os.path.isabs(p):
                rel = os.path.relpath(p, root)
            elif root:
                rel = os.path.relpath(os.path.abspath(p), root)
            scan_file(rel, findings, args.max_file_bytes)
        for f in findings:
            f["preexisting"] = False
    else:
        label, target, added_map = resolve_diff(args.scope, args.base)
        if not added_map:
            msg = ("No diff found in scope '%s'. Pass --paths to scan files "
                   "directly, or --base <ref> to name a base branch."
                   % args.scope)
            # An empty scope still has to answer in the requested format.
            # Printing prose on stdout under --json made every consumer that
            # parses this - including the judgment pass - crash on a clean
            # branch instead of reading zero findings.
            if args.json:
                print(json.dumps({
                    "scope": label or f"empty ({args.scope})",
                    "generated": datetime.datetime.now().isoformat(
                        timespec="seconds"),
                    "report_stem": args.stem or report_stem(target or "worktree"),
                    "prior_report": None,
                    "findings": [], "resolved": [],
                    "errors": READ_ERRORS, "warnings": WARNINGS + [msg],
                    "complete": True,
                }, indent=2))
                return 0
            for w in WARNINGS:
                print("warning: " + w, file=sys.stderr)
            print(msg)
            return 0
        for p in added_map:
            scan_file(p, findings, args.max_file_bytes)
        kept = []
        for f in findings:
            f["preexisting"] = f["line"] not in added_map.get(f["path"], set())
            if not f["preexisting"] or args.whole_files:
                kept.append(f)
        findings = kept

    cutoff = SEVERITY_ORDER[args.min_severity]
    findings = [f for f in findings if SEVERITY_ORDER[f["severity"]] <= cutoff]
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["path"], f["line"]))

    generated = datetime.datetime.now()
    stem = args.stem or report_stem(target, generated)
    prior_when, resolved = None, []
    if args.since:
        prior_when, resolved = reconcile(findings, args.since)

    # A read failure is a hole in the scan, not a detail. Say so in both modes.
    unreadable = [e for e in READ_ERRORS if not e["error"].startswith("skipped")]
    if unreadable:
        warn(f"{len(unreadable)} file(s) in scope could not be read - "
             "the scan is incomplete, see 'errors'")

    if args.json:
        print(json.dumps({
            "scope": label,
            "generated": generated.isoformat(timespec="seconds"),
            "report_stem": stem,
            "prior_report": {"path": args.since, "generated": prior_when}
                            if args.since else None,
            "findings": findings,
            "resolved": resolved,
            "errors": READ_ERRORS,
            "warnings": WARNINGS,
            "complete": not unreadable,
        }, indent=2))
        return 2 if unreadable else 0

    in_scope = [f for f in findings if not f["preexisting"]]
    preexisting = [f for f in findings if f["preexisting"]]
    for f in resolved:
        f.setdefault("preexisting", False)

    print(f"Scope: {label}")
    print(f"Generated: {generated.strftime('%Y-%m-%d %H:%M')}")
    print(f"Report stem: {stem}")
    print(f"{len(in_scope)} candidate(s) in scope. "
          "These are candidates, not verdicts.\n")

    def dump(group):
        by_file = defaultdict(list)
        for f in group:
            by_file[f["path"]].append(f)
        for path in sorted(by_file):
            print(path)
            for f in by_file[path]:
                print(f"  {f['severity']}  {f['line']:>5}  "
                      f"{f['rule']:<24} {f['message']}")
            print()

    dump(in_scope)
    if resolved:
        print(f"--- no longer true since {prior_when or args.since} "
              f"({len(resolved)}) ---")
        print("Fixed or overtaken by events. Do not re-report as live.\n")
        dump(resolved)
    if preexisting:
        print(f"--- pre-existing, in files this change touches "
              f"({len(preexisting)}) ---")
        print("Incidental to the diff, not an audit. Two sentences each, "
              "top few only. Do not fix.\n")
        dump(preexisting)

    if READ_ERRORS:
        print(f"--- not scanned ({len(READ_ERRORS)}) ---", file=sys.stderr)
        for e in READ_ERRORS:
            print(f"  {e['path']}: {e['error']}", file=sys.stderr)
    for w in WARNINGS:
        print("warning: " + w, file=sys.stderr)
    return 2 if unreadable else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        os._exit(0)  # piping into head/less is not an error
