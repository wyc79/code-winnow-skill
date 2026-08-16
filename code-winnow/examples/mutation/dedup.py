"""The production behaviour the worked example in references/mutation.md breaks.

Deliberately small: the mutation has to be an edit a reader can check by eye,
and the point of the example is the test, not this.
"""


def unique_slugs(names):
    """Slugify `names`, dropping every repeat after the first."""
    seen = set()
    out = []
    for name in names:
        slug = name.strip().lower()
        if slug in seen:
            continue
        seen.add(slug)
        out.append(slug)
    return out
