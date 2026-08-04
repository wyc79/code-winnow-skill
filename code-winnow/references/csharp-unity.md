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

## Never touch — attributes that bind a field outside this file

**P1 / never touch.** Whole-file token counting cannot see a scene, a prefab, a serializer, a DI container, or the IL2CPP stripper. A field carrying any of these attributes is *referenced*, however unreferenced it looks — and every one of these failures is runtime-only or build-only, with a clean compile and a green unit suite.

| Attribute | Reached by | Deleting it costs |
|---|---|---|
| `[SerializeField]`, `[SerializeReference]` | Unity serialization | every value already set in scenes and prefabs, silently |
| `[FormerlySerializedAs]` | Unity serialization | the migration path for an already-renamed field |
| `[Preserve]` | IL2CPP stripping | the member is stripped from release builds only |
| `[RuntimeInitializeOnLoadMethod]`, `[InitializeOnLoad]`, `[InitializeOnLoadMethod]` | engine startup | the entry point never runs |
| `[MenuItem]`, `[ContextMenu]`, `[ContextMenuItem]` | editor UI | the menu entry disappears |
| `[Inject]` | Zenject / VContainer | a null dependency at runtime |
| `[JsonProperty]`, `[JsonPropertyName]`, `[JsonInclude]`, `[DataMember]`, `[ProtoMember]`, `[XmlElement]` | serializers | the wire format changes; old payloads stop round-tripping |
| `[DllImport]`, `[MonoPInvokeCallback]`, `[UnmanagedCallersOnly]` | native interop | the callback address or entry point is lost |
| `[StructLayout]`, `[MarshalAs]`, `[FieldOffset]` | marshalling | the memory layout the native side expects |

The scanner encodes this list in `EXPOSED`: a field carrying any of them is reported P3 with a confirm note, never as a delete instruction. The list is not exhaustive — an attribute you do not recognise is another ecosystem's version of the same thing, so treat an unrecognised attribute on a field as exposure and keep the field.

**Engine-invoked methods always look unreferenced.** `Awake`, `Start`, `OnEnable`, `OnDisable`, `OnDestroy`, `OnValidate`, `OnTriggerEnter`, `OnCollisionEnter`, `OnApplicationPause` and the rest are called by name from native code; nothing in the file calls them. "No caller in this file" is not evidence about them. (An *empty* lifecycle method is still deletable — see below. The point here is that a non-empty one is live.)

## Per-frame cost

**Empty lifecycle methods.** `void Start() { }`, `void Update() { }` left behind. Not free — Unity registers these by *declaration*, discovered when the script loads, and has no notion of an empty body. It crosses the native/managed boundary once per declared `Update` per frame regardless of what is inside, so an empty one on 500 objects is measurable. Delete them.

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

## Usings

The safest of the claimed languages to clean, and the reason is the signal: remove a `using` this file needs and the build fails here, now, with a line number. `dotnet format analyzers` and IDE0005 find them, so run one if the project is set up for it. Three cases where that safety does not hold, and the first is the only one that fails *silently*.

**A `using` alias is never dead.** **P1 / never touch.** `using Debug = UnityEngine.Debug;` and `using Random = UnityEngine.Random;` sit in Unity files precisely because `System.Diagnostics.Debug` and `System.Random` exist and would otherwise collide or win. Delete the alias and a bare `Debug.Log` either stops compiling or — where both namespaces are already in scope — quietly resolves to the other type. A clean compile and different behaviour is the exact failure shape this file is organised around, and it belongs beside the attribute table above rather than in a tidy-up list.

**A `using` reached only under an inactive `#if`.** `using UnityEditor;` consumed inside `#if UNITY_EDITOR`, or anything behind a define this configuration does not set, looks unreferenced in the build you are reading and is load-bearing in another. The break lands in a player build, or on the platform nobody compiled locally. Read every conditional block before calling a `using` unused, and treat a file containing `#if` as unverifiable until you have.

**A `using` a global one already supplies** — `GlobalUsings.cs`, or `ImplicitUsings` in the csproj — is genuinely redundant, and that is a real finding rather than a trap. **P3**, and say which global supplies it.

Reordered or reshuffled `using` blocks on lines the change did not touch are not a finding here at all; that is formatting churn, and Diff hygiene in `core-patterns.md` covers it.

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
