# Python

Python slop is mostly ceremony: type-hint theatre, defensive scaffolding, and abstraction added because it looks professional.

## Type hints and docstrings

**`Any` as a type hint.** `Dict[str, Any]`, `-> Any`, `**kwargs: Any`. Documents nothing and disables the checker at exactly the point it would help. If the shape is known, write it (`TypedDict`, `dataclass`, `Protocol`).

**Hints restating the obvious while omitting the hard part.** `def f(x: int, cfg: dict) -> dict:` — `int` was never in doubt; the two `dict`s are the whole question.

**Docstring restating the signature.**
```python
def get_user(user_id: int) -> User:
    """Get a user.

    Args:
        user_id: The user id.
    Returns:
        The user.
    """
```
Four lines conveying nothing the signature didn't. Delete, or replace with the part that isn't obvious — what happens when the user doesn't exist.

**Full Google/NumPy-style docstrings on private helpers.** Ceremony scaled to the wrong audience.

**`Optional[X]` where nothing returns None**, or a missing `Optional` where something does. Check the returns.

## Error handling

**Log-and-reraise.**
```python
try:
    do_thing()
except Exception as e:
    logger.error(f"Error doing thing: {e}")
    raise
```
Duplicates the traceback and drops the type. Delete the wrapper unless it adds context the caller genuinely lacks.

**Bare `except:` or `except Exception:`** around a call with one realistic failure mode. Catches `KeyboardInterrupt` and typos alike.

**`except ... : pass`.** **P1.** Silent failure.

**Exception messages that restate the exception class.** `raise ValueError("Invalid value")`.

## Defensive scaffolding

**Null guards on values that cannot be None** — already checked by the caller, or guaranteed by a dataclass default.

**`.get(key, default)` where the key is always present**, dict built two lines up.

**`isinstance` checks in internal functions** the type checker already covers.

**`if not items: return []`** before a loop that handles empty naturally.

## Speculative structure

**ABC with one concrete subclass.** Written for testability; monkeypatching or a Protocol costs less.

**Factory function returning one type.**

**Config dataclass with fields nothing reads.**

**`**kwargs` passthrough** where no caller passes extras — hides the real signature from every reader and every tool.

**`@staticmethod`-only class** used as a namespace. That is what modules are.

## Async

**`async def` with no `await` in the body.** Adds coroutine overhead and forces every caller to be async for nothing.

**`asyncio.run` inside a library function** — takes over the caller's event loop.

**Blocking I/O inside `async def`** (`requests`, `time.sleep`, sync file reads). Stalls the loop and defeats the point.

**`await` in a loop** where `asyncio.gather` was intended — serial execution wearing async syntax.

## Dead weight

- Unused imports (an agent's iteration debris)
- `if __name__ == "__main__":` demo block in a library module
- `print()` left from debugging; entry/exit `logger.debug` narration
- Commented-out alternative implementations
- `pass` after a docstring-only body
- `# type: ignore` added to silence an error rather than fix it — flag with the underlying error

## Idiom

**Manual index loops.** `for i in range(len(xs)): xs[i]` → iterate directly, or `enumerate` if the index is used.

**Manual accumulation** where a comprehension reads better — and the reverse: a nested triple comprehension that should be a loop. Both directions are slop; the comprehension is not automatically better.

**String concatenation in a loop** instead of `"".join`.

**`os.path` string juggling** in a codebase that uses `pathlib`.

**Mutable default argument.** `def f(items=[])`. **P1** — a real bug, and generated code still produces it.

**f-strings in logging calls.** `logger.info(f"...")` formats eagerly even when the level is filtered; `logger.info("...%s", x)` doesn't.

## Tests

**Mock theatre.** **P1.** `mock.assert_called_with(x)` where the test supplied `x` and the assertion would pass against an empty implementation.

**Patching the function under test.**

**`assert True` / `assert result is not None`** as the only assertion.

**Fixtures with no teardown** holding real resources.
