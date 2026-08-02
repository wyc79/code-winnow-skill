# C# / Unity

Unity slop is distinctive because generated code tends to be written as if C# were running on a server, not inside a frame budget. Several patterns below are correctness bugs, not style — Unity's object model breaks C# assumptions in ways an LLM reliably forgets.

## Unity object lifetime — the null-conditional trap

**P1, and the one to check first.**

`UnityEngine.Object` overloads `==` so a destroyed object compares equal to null. The null-conditional and null-coalescing operators do **not** use that overload — they check the managed reference, which is still alive after `Destroy()`.

```csharp
transform?.position    // does NOT detect a destroyed object
target ??= FindTarget(); // same problem
```

Generated code reaches for `?.` and `??` constantly because they are idiomatic C# everywhere else. On a `UnityEngine.Object` subclass they introduce a real bug: the branch you thought was guarded runs against a destroyed object and throws `MissingReferenceException` at some unrelated point later.

*Fix:* explicit `if (target != null)`. Flag every `?.` / `??` / `?[]` on a `MonoBehaviour`, `GameObject`, `Component`, `ScriptableObject`, or anything deriving from them. Plain C# objects are fine.

## Per-frame cost

**Empty lifecycle methods.** `void Start() { }`, `void Update() { }` left behind. Not free — Unity crosses the native/managed boundary to call every non-empty-at-compile-time `Update`, so an empty one on 500 objects is measurable. Delete them.

**`GetComponent<T>()` in `Update`.** Cache in `Awake`. Same for `GetComponentInChildren`, `FindObjectOfType` (worse — scene-wide scan), and `gameObject.tag` comparisons in hot paths (`CompareTag` allocates less).

**`Camera.main` in `Update`.** It is a tagged object lookup. Cache it.

**LINQ in per-frame code.** `Where`/`Select`/`OrderBy` allocate enumerators and closures every call, and the GC spike shows up as a frame hitch. Fine in setup, out of place in `Update`/`FixedUpdate`/`LateUpdate`.

**String concatenation or interpolation per frame**, especially inside `Debug.Log`. The string is built even when the log is filtered out.

**`Debug.Log` left in hot paths.** Wrap in `[Conditional("UNITY_EDITOR")]` or delete. Generated code logs its own progress and then leaves it in.

**Struct allocation churn.** `new Vector3(...)` in a tight loop is cheap; `new List<T>()` per frame is not. Look for collections constructed inside the loop rather than reused.

## Structure

**Property duplicating a serialized field.** `[SerializeField] private float speed;` plus `public float Speed => speed;` where nothing outside the class reads it. Added reflexively.

**`public` fields on MonoBehaviours** used only internally — `[SerializeField] private` gets the same Inspector exposure without the API surface.

**Renaming serialized fields.** **P1 / never touch.** Renaming a `[SerializeField]` field silently drops every value already set in scenes and prefabs. If a rename is genuinely warranted, it needs `[FormerlySerializedAs]` — flag it, do not do it as part of a cleanup.

**Coroutine wrapped in try/catch** where the catch only logs. Exceptions in coroutines already surface; the wrapper stops the coroutine at an arbitrary yield point instead.

**Singleton scaffolding** generated for a class with one scene instance and no cross-scene access.

**`[RequireComponent]` / `[Header]` / `[Tooltip]` spam** on fields that need none.

## Idiom drift

**`System.Random` instead of `UnityEngine.Random`**, or `Math` instead of `Mathf` — the latter is float-native and matches surrounding engine code.

**`Vector3.magnitude` for comparisons** where `sqrMagnitude` avoids a square root. Minor, but a tell that the code was written without engine context.

**`GameObject.Find` by string name.** Fragile and slow. Serialized reference or explicit wiring instead.

**`async`/`await` bolted onto Unity code** where the project uses coroutines. Consistency matters more than which is better — check the surrounding files.

## Plain C#

**`async` method with no `await`.** Returns a completed task and adds a state machine for nothing.

**`async void`** outside an event handler — exceptions escape unobservable.

**`ConfigureAwait(false)` cargo-culted** into application code (it belongs in libraries).

**Exception filters or `when` clauses** added speculatively.

**Region blocks** (`#region`) wrapping short files — folding as a substitute for structure.
