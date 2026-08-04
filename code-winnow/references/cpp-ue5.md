# C++ / UE5

Unreal has strong house conventions that generated code drifts away from, usually toward generic modern C++. The result compiles, works, and reads as foreign to anyone maintaining the module.

## Standard library drift

Unreal supplies its own containers, strings, and smart pointers, and the codebase expects them.

| Generated | Expected |
|---|---|
| `std::vector` | `TArray` |
| `std::map` / `unordered_map` | `TMap` |
| `std::string` | `FString` (or `FName` for identifiers, `FText` for anything user-facing) |
| `std::shared_ptr` | `TSharedPtr` (non-UObject) / `UPROPERTY()` (UObject) |
| `std::optional` | `TOptional` |
| `printf` / `std::cout` | `UE_LOG` |
| `assert` | `check()` / `checkf()` / `ensure()` |

*Test:* is the std type crossing a module boundary or touching engine API? Then it is wrong regardless of taste. Contained inside one non-engine-facing function, it is a judgment call — check neighbouring files.

**`FName` vs `FString` vs `FText`.** Generated code defaults to `FString` for everything. Identifiers compared frequently want `FName`; anything shown to a player wants `FText` for localization.

## Memory and GC

**Raw `UObject*` member without `UPROPERTY()`.** **P1.** The garbage collector doesn't see it, so the object gets collected out from under a live pointer. This is a real crash, not style.

**`TSharedPtr` wrapping a `UObject`.** Two ownership systems fighting. UObjects are GC-managed; use `UPROPERTY()`, ideally `UPROPERTY()` with `TObjectPtr`.

**`TObjectPtr` is not a substitute for `UPROPERTY()`.** It is a `UPROPERTY`-compatible wrapper adding access tracking and lazy load in editor builds — it does **not** root anything on its own. A bare `TObjectPtr<UFoo> Foo;` with no `UPROPERTY()` is exactly as invisible to the garbage collector as a raw `UFoo*`, and fails the same way: collected out from under a live pointer, at runtime, with a clean compile. The scanner only flags the raw-pointer form, so this one is yours to catch by reading.

**Null checks after allocation that cannot fail.** `NewObject<T>()` and `CreateDefaultSubobject<T>()` don't return null on failure — they crash. A guard implies a recoverable case that doesn't exist.

**`IsValid()` on a just-constructed object** in the same scope. Delete.

**`IsValid()` vs `!= nullptr`** confusion in the other direction — for a UObject that may have been marked for destruction, `IsValid()` is the correct check and `!= nullptr` is not. Do not "simplify" `IsValid()` into a null check.

## Signatures

**`TArray` by value** where `const TArray<T>&` is meant. Copies the whole array per call.

**`FString` by value** for the same reason.

**Missing `const`** on accessors and on reference parameters that are not modified.

**`UFUNCTION(BlueprintCallable)` / `UPROPERTY(EditAnywhere)` sprayed on everything.** Each one is API surface a designer can and will use, and reflection metadata has a build-time and memory cost. Exposure should be deliberate.
*Test:* does a Blueprint or the editor actually need this? If it was added "so it's available", remove it.

**Removing a `UPROPERTY` from an exposed field.** **Never touch.** Same problem as Unity serialized fields — it drops values already set in Blueprints and assets.

## Logging and asserts

**`UE_LOG` at `Log` verbosity in per-tick code.** Ships to the packaged build and floods the log.

**Custom log category defined for one file**, or logging that narrates control flow (`UE_LOG(..., TEXT("Entering DoThing"))`).

**`check()` used for recoverable conditions.** `check()` halts the program; `ensure()` reports and continues. Generated code reaches for `check()` because it reads like `assert`.

**`try`/`catch` at all.** Most UE projects build with exceptions disabled. A catch block is a strong signal the code was written without engine context.

## Includes and build

**Heavy includes in headers** where a forward declaration works. Header bloat compounds across the module and shows up as build-time regression.

**Missing `.generated.h` as the last include**, or includes added after it — the code generator requires it last.

**`#pragma once` plus include guards.** Pick one; UE uses `#pragma once`.

**Includes added but unused** after an agent's iteration loop. Real chaff, and the one import-shaped cleanup in this skill that is **reported freely and proposed only on evidence** — `include-what-you-use`, `clang-tidy misc-include-cleaner`, or a whole-file symbol trace, named in `evidence:`. Without one of those, write `fix: out of scope` and leave the line.

That asymmetry is not fussiness about C++. Remove a `using` that C# needs and the build fails here, with a line number. Remove an `#include` that C++ needs and it very often still compiles here — another header pulled the symbol in transitively, or Unreal's unity build put a neighbour's includes in the same translation unit — and the failure surfaces on a different platform, a different compiler, or a colleague's incremental build that groups the blobs differently. A stale include costs build time; a wrong removal costs someone else a red build they cannot reproduce from the diff.

Four that look unused and are not:

- **`.generated.h`** — required last, referenced by name nowhere in the file. Never touch.
- **`CoreMinimal.h`** — the module-wide convention, referenced directly by nothing.
- **A macro's home.** `UE_LOG` needs `Logging/LogMacros.h`; `check()` and `ensure()` need `Misc/AssertionMacros.h`. Grep for the macro, not for a type.
- **A template instantiation, an operator overload, or an explicit specialization** — consumed without any identifier from that header appearing on the line that consumes it.

And `// IWYU pragma: keep` is a directive, not a comment: its presence settles the question. It is in the never-touch table in `core-patterns.md`.

## Naming

Unreal's prefix convention is load-bearing — the reflection system and the style guide both depend on it:

- `U` — UObject subclasses
- `A` — Actor subclasses
- `F` — plain structs and non-UObject classes
- `E` — enums
- `I` — interfaces
- `T` — templates
- `b` — bool members (`bIsActive`, not `isActive` or `m_active`)

**`m_` prefixes** on members — not the Unreal convention.

**Snake_case anywhere.** UE is PascalCase for functions and members.

## Gameplay structure

**Tick enabled by default** on an actor that doesn't need per-frame work. `PrimaryActorTick.bCanEverTick = false` unless it does.

**Work in `Tick` that belongs on a timer or an event.** Polling a condition every frame that changes once a second.

**Component that could be a function.** Generated code creates an `UActorComponent` for logic with no state and no reuse.

**`GetWorld()` without a null check in a context where it can be null** (constructors, CDO construction) — the inverse of defensive overkill, and a common generated crash.
