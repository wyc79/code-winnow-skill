# Tests

Load this whenever the diff touches a test file, in any language.

Test code gets a pass in review that production code does not, and generators exploit it. A suite can double in size, raise coverage, and verify nothing new. That is worse than no test: it buys false confidence and charges maintenance rent forever. The rule for the rest of this skill — delete what does not earn its place — applies here exactly as it does everywhere else. What changes is the test for whether something earns it.

**The question for every test: what change to the production code would make this fail?** If you cannot name one, the test is decoration. If the answer is the same for two tests, one of them is redundant.

## The redundancy families

**No assertion at all.** The test calls the code and ends. It passes as long as nothing throws — which is a real, if weak, smoke test, and it is worth exactly that much. Generated suites produce them in bulk because "call every public method" is an easy shape to emit.
*Test:* if the function returned a completely wrong value, would this test notice? If not, either assert on the result or say in one line that it is a smoke test.

**Assertions that cannot fail.** `assert True`, `assertEqual(2, 2)`, `expect(true).toBe(true)`, `assert_eq!(1, 1)`. Usually a placeholder someone meant to fill in.
*Test:* does any operand depend on the code under test? If neither does, the line is a no-op.

**Mock theatre.** Every assertion checks the double: `assert_called_once`, `toHaveBeenCalled`, `verify(repo).save()`, `Received().Save()`. The test proves the code called what you told it to call, which you already knew from reading the code — it re-asserts the implementation, so it fails on every refactor and passes through every behavior bug.
*Test:* is there at least one assertion about a returned value, a stored state, or an emitted effect? Verifying an interaction is legitimate when the interaction *is* the contract (a message was published, a payment was charged). It is not a substitute for checking the result.

**Structural duplicates.** Three tests with identical bodies differing only in literals. One parametrized or table-driven test covers them, and adding the fourth case then costs one line instead of eight.
*Test:* blank the literals. Are the bodies the same? Then merge: `@pytest.mark.parametrize`, `[TestCase]`, `it.each`, a Go table, `#[rstest]`.
*Counter-test:* if the cases differ in *why* they exist rather than in their data — a boundary, an error path, a regression with a ticket — keep them separate and name them for the reason. Merging those loses the documentation.

**Tests of the framework.** Asserting that a dataclass stores what you passed it, that an enum has the members you just declared, that a getter returns the field. The language already guarantees it.

**Over-mocked units.** Every collaborator is a double, so the test exercises the wiring diagram and nothing else. Often the sign a real object would have been cheaper.

**Setup nobody uses.** A fixture no test requests, a builder used once, a `beforeEach` populating state the assertions never touch. Same rule as unused fields in production code.

**Skips with no reason.** `@pytest.mark.skip`, `@Ignore`, `it.skip`, `t.Skip()`, `#[ignore]` with no explanation. Nobody knows what has to be true to re-enable it, so nobody ever does. P3, but it is the kind that accumulates.

## What is not redundant

Do not cut these to make the numbers look better:

- **The unglamorous duplicate.** Two tests that look alike but pin different regressions. If the name or a comment carries a ticket, it is documentation of a bug that happened.
- **Boundary cases that share a shape.** `0`, `1`, `-1`, `MAX` read as four copies of one test. They are four different risks.
- **Fixtures, fakes, and builders.** Test scaffolding is meant to be a little repetitive and a little verbose. Readability at 3am beats elegance.
- **`TODO`s in test files.** Normal, and the scanner does not flag them.
- **Assertions that look weak but pin a contract** — that a call does *not* raise, that a list stays ordered, that a deprecated path still works.

## What a comment can and cannot excuse

Test files attract intent comments — "intentional duplicate", "kept deliberately", "this fixture is test-only". Grade them exactly as `comment-evidence.md` says: a checkable why protects, a bare claim does not. But test findings have one extra rule on top, and it does not bend.

**A comment can justify a test's existence. It can never justify its false coverage.**

| Comment | Finding | Outcome |
|---|---|---|
| `// intentional duplicate — pins the #412 regression` | `duplicate-test` | Dismissed. This is the counter-test from Structural duplicates, stated by the author |
| `// deliberately test-only, mirrors the prod builder` | `unused-fixture` | Dismissed |
| `// this test is intentional` | **asserts nothing / mock-only** (P1, or P2 in the non-Python forms above) | **Not dismissed.** Keep it, quote the comment, and say what assertion would fix it. Never let the P2 label read as "already downgraded, therefore settled" |

The asymmetry is the point. Whether a test *should exist* is a question about intent, and the author is the authority on their own intent. Whether a test *can fail* is a question about the code, and no comment changes the answer. A test that asserts nothing asserts nothing whether or not someone wrote "intentional" above it.

**The floor applies to tests that cannot fail — not to tests that fail by crashing.** Two shapes are routinely mistaken for assertion-free and are nothing of the kind:

```python
def test_legacy_plugin_imports():
    import myapp.plugins.legacy   # noqa: F401
```

```cpp
TEST(WidgetTest, TickAfterDestroyDoesNotCrash) { Widget w; w.Destroy(); w.Tick(); }
```

Neither has an assertion and both fail loudly — on ImportError, on panic, on segfault. Not asserting *is* the contract: the test says "this does not blow up", which is a real regression pin and often the only way to express one. Demanding "what assertion would fix it" has no answer, because nothing is broken.

So: the finding is dismissible, and the right output is one line naming it a smoke or crash-regression test. The same carve-out applies to interaction assertions where the interaction *is* the contract — a message published, a payment charged — per Mock theatre above. Where the SKILL.md severity list and this file appear to disagree, **this file is the standard**; SKILL.md's list is a summary and summaries lose the exceptions.

What the floor still catches, absolutely: a test that runs to completion no matter what the production code does. `assert True`, a mock asserting on arguments the test itself supplied, a call whose result is discarded where a wrong result would be silently fine. Those cannot fail, and no comment makes them able to.

This is the single most likely place for the whole skill to be talked out of its job, because "the author said it was on purpose" reads as a complete answer and is not one. False coverage is what lets a real bug ship, and a comment above it does not make the bug less shipped.

## Language notes

| Family | Test shape | Assertion vocabulary | Mock verbs |
|---|---|---|---|
| pytest / unittest | `def test_*`, `class Test*` | `assert`, `assertEqual`, `pytest.raises` | `assert_called*`, `mock.assert_*` |
| NUnit / xUnit / MSTest | `[Test]`, `[Fact]`, `[Theory]` | `Assert.*`, `Should()` | `Verify(`, `Received()` |
| GoogleTest | `TEST`, `TEST_F`, `TEST_P` | `EXPECT_*`, `ASSERT_*` | `EXPECT_CALL` |
| Go | `func TestXxx(t *testing.T)` | `t.Error*`, `t.Fatal*`, `require.*`, `assert.*` | `AssertExpectations`, gomock |
| Jest / Vitest / Mocha | `it(...)`, `test(...)`, `describe(...)` | `expect(...)`, `assert.*`, `.should` | `toHaveBeenCalled*`, `jest.fn`, sinon |
| JUnit | `@Test`, `@ParameterizedTest` | `assertEquals`, `assertThat` | `verify(`, Mockito |
| Rust | `#[test]`, `#[tokio::test]`, `#[rstest]` | `assert!`, `assert_eq!`, `should_panic` | mockall `expect_*` |
| RSpec | `it "..." do` | `expect(...).to`, `assert_*` | `have_received` |
| XCTest | `func testXxx()` | `XCTAssert*` | — |

The scanner covers the mechanical parts of most of these — no assertion, tautology, mock-only, structural duplicates, unexplained skips. It cannot tell a meaningful duplicate from a lazy one, and it has no idea whether an interaction assertion is the contract. That is the judgment pass's job, and this file is the standard for it.

**Three of its rules do not reach every family in that table, and the gaps are silent.** A scanner that finds nothing because the rule never ran looks exactly like a clean suite:

| Rule | Where it actually runs |
|---|---|
| `unused-fixture` | **pytest only.** "Setup nobody uses" in NUnit, JUnit, Jest, GoogleTest or RSpec is yours to find — the scanner will never raise it |
| `mock-only-test` | P1 when the test has no assertions at all; **P2 outside Python** when it asserts and every assertion checks a double |
| `tautological-*` | **P1 only in Python, and only when every assertion is tautological.** Mixed Python tests and all non-Python tautologies are P2 |

The severity split matters for the floor below: when it says a P1 cannot be dismissed, the finding in front of you may well be the P2 form of the same defect. **The floor is about the defect, not the label** — a test whose every assertion checks a double is false coverage at P1 or P2, and a comment does not excuse either.

## Reporting

Test findings follow the same severity scale as everything else:

- **P1** — a test that cannot fail, asserts nothing, or asserts only about a double. These are not weak tests, they are false coverage, and false coverage is what lets a real bug ship. **The scanner files two of these at P2 outside Python** — see the reach table above. The floor is about the defect, not the label.
- **P2** — structural duplicates, unused fixtures, over-mocking.
- **P3** — unexplained skips, naming, ceremony.

Never propose deleting a test outright when tightening it would do. "This asserts nothing — assert on the return value" is a fix. "Delete this test" is a coverage regression wearing a cleanup costume, and it is the one edit in this whole skill most likely to be waved through unread.

**Any fix that changes what the suite collects must name the tests it removes and the tests it adds**, in the plan, before approval — SKILL.md calls this the `tests-delta:` field. Merging three duplicates into a parametrized case is legitimate and expected; it is also indistinguishable from quietly dropping two of them unless the cases are listed on both sides. Verification then reconciles the collected names against that declaration instead of guessing whether a smaller suite was intentional. State the cases, not a count: `-3 +3` with the names is checkable, "merged the duplicates" is not.
