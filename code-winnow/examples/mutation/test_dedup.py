"""A test named for the dedup filter that never asks the filter anything.

It calls `unique_slugs`, discards the result, rebuilds the filter out of its own
list comprehensions, and asserts on those. It has an assertion, no mock and no
tautology any regex or AST rule can see - so every heuristic in scripts/scan.py
passes it, which is the whole reason references/mutation.md exists. Only the
mutation catches it.

Kept broken on purpose. Do not fix it: the tightened form is the second half of
the worked example, and tests/test_mutation.py applies it to a copy.
"""

from dedup import unique_slugs


def test_unique_slugs_drops_repeats():
    names = ["Ada", "ada", "Grace"]
    unique_slugs(names)
    slugs = [n.strip().lower() for n in names]
    assert [s for i, s in enumerate(slugs) if s not in slugs[:i]] == ["ada", "grace"]
