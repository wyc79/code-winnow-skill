# Web — JavaScript/TypeScript, HTML, CSS

Read the section matching the file. A `.vue`, `.svelte`, `.astro` or `.html` file is usually all three at once, so read all three for those.

The web stack is where generated code is most fluent and therefore hardest to spot: it produces idiomatic-looking React, correct-looking ARIA and plausible-looking CSS, and every one of those three has a way of being wrong that reads as diligence. The traps sections matter more here than in any other language file, because the failures are overwhelmingly silent — a stripped `"use client"`, a deleted `import './styles.css'`, a reordered stylesheet. None of them fails a build.

---

# JavaScript / TypeScript

Everything here applies to `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs` and the script blocks of `.vue`/`.svelte`/`.astro`. TypeScript is not treated as a separate language: the slop is identical and only the type annotations differ.

## Never touch — things that look like debris and are load-bearing

**P1 / never touch.** Most of these leave a clean build and a green suite behind them, which is what makes them dangerous. The two that do fail a build fail it somewhere other than here — on a different `tsconfig`, in a different bundler mode — so the local green is still the wrong signal.

| Looks like | Actually is | Deleting it costs |
|---|---|---|
| `"use client"` / `"use server"` at the top of a file | A framework directive, not a stray string expression | The component silently server-renders; hooks throw at runtime, or server code ships to the browser |
| `'use strict'` | The same, for scripts | Silent semantic change — assignments to undeclared variables stop throwing |
| `import './styles.css'`, `import './polyfills'` | A side-effect import | Styling or the polyfill vanishes; nothing errors |
| `import 'reflect-metadata'`, `import 'zone.js'` | DI or change-detection bootstrap | Angular/NestJS/TypeORM decorators stop resolving, at runtime only |
| `import React from 'react'` in a `.tsx` with no `React.` in it | The **classic** JSX runtime's required import | Build breaks — or worse, works locally and breaks on a config where `jsx` is `"react"`. Check `tsconfig`'s `jsx` before calling it unused |
| `import type { X }` vs `import { X }` | Emit-affecting under `isolatedModules` / `verbatimModuleSyntax` | A runtime import of a type-only module, or a stripped import something needed |
| `data-testid`, `data-cy`, `data-qa` | Test selectors | Every e2e test that selects on it, and only when the e2e suite runs |
| An export nothing in the repo imports | Public API, or reached by string (`window[name]`, a dynamic `import()`, a route manifest) | A consumer outside this repo, or a route that 404s |
| `/*#__PURE__*/`, `/* webpackChunkName: "x" */` | Bundler pragmas | Silent bundle-size and tree-shaking changes, zero build error |
| A bare `.d.ts` ambient declaration | The only type information for an untyped dependency | Types collapse to `any`, and only under `strict` does anything say so |

**`// @ts-check`, `// @ts-expect-error`, `// eslint-disable-next-line` and the rest are in `core-patterns.md`'s directive table.** Same rule, no exceptions: a comment a tool reads is not a comment.

## Defensive overkill

**Optional chaining as punctuation.** `user?.profile?.name?.trim()` where the type says `user: User` and `profile` is required. Each `?.` is a claim that the value can be nullish, and a reader has to disprove all four. Generated code reaches for `?.` because it is never wrong.
*Test:* does the type or the call site guarantee it? Then the `?.` is documenting a fear, not a case.

**Guards on required props.** `if (!items) return null` at the top of a component whose props type says `items: Item[]`. Either the type is a lie or the guard is.

**`try/catch` around `JSON.parse` that returns `null`.** Converts a parse failure into a plausible value, and the wrong answer surfaces three frames away. This is the swallowed-exception rule in the local dialect. **P1** when the caller cannot tell the difference.

**Coercion ceremony.** `Boolean(x)` inside an `if`, `String(x)` in a template literal, `!!x` where a truthiness test already runs, `Number(x)` on something already numeric.

**`typeof window !== 'undefined'` in code that only ever runs in one environment.** Real in a universal/SSR module; noise in a browser-only file.

## Speculative structure

**Memoization by reflex.** `useMemo` around a property access, `useCallback` around a function passed to a plain DOM element, `React.memo` on a component that takes one primitive prop. Each one adds a dependency array to maintain and costs more than it saves. This is the single most common React slop pattern.
*Test:* is the memoized value expensive to compute, or is the identity depended on by a memoized child or an effect? If neither, delete it.

**A custom hook wrapping one `useState`.** `useToggle`, `useName` — indirection with no shared logic.

**A context provider with one consumer.** Props.

**A barrel `index.ts` re-exporting two modules.** Added for symmetry; costs the bundler its tree-shaking and every reader an extra hop.

**A `utils/` module holding one function**, used once, in the file next to it.

**`interface Props` + `React.FC<Props>` ceremony** in a repo whose other components are plain functions. Check the neighbours; this is a convention question, not a rule.

## Async

**`async` with no `await`.** A state machine and a promise wrapper for nothing, and every caller becomes async to match.

**`await` in a loop where `Promise.all` was meant.** Serial execution wearing concurrent syntax. Report it here only if the loop bound is small or unknown; if you can name a frequency, it is Agent D's.

**The explicit-promise antipattern.** `new Promise((resolve) => { doThing().then(resolve) })` around something that already returns a promise. Errors are lost on the way out.

**A floating promise.** A call with no `await`, no `.catch`, no `void` marker. The work fails and nothing reports it — Agent E's, not a style note.

**`.then()` chained onto `await`ed code** in the same function. Pick one; mixing them is iteration debris.

## Idiom

**`var`.** And `let` for a binding never reassigned.

**`for (let i = 0; i < xs.length; i++)`** where `for...of` reads better, or `entries()` if the index is used.

**`xs.filter(f).length > 0`** → `.some(f)`. **`xs.find(f) !== undefined`** → `.some(f)`.

**`Object.keys(o).forEach(k => … o[k] …)`** → `for (const [k, v] of Object.entries(o))`.

**`JSON.parse(JSON.stringify(x))`** as a deep clone → `structuredClone`, in any runtime from 2022 on.

**`==` is not automatically a bug.** `x == null` tests null *and* undefined in one operator and is deliberate, common, and what `eslint eqeqeq` exempts by default. Do not "fix" it to `===`.

**Deprecated string methods.** `substr` → `slice`. `escape`/`unescape` → `encodeURIComponent`.

## TypeScript

**`any` used to silence the compiler**, and `as unknown as T` double assertions — the second is a louder version of the first and always worth a finding.

**Non-null assertion by reflex.** `x!.y!.z`. Same rule as `?.`: it is a claim, and the claim is unchecked.

**Redundant annotations the initializer already provides.** `const n: number = 5`, `const s: string = "x"`.

**An `interface` with one field, used in one place.**

**`enum` where the repo uses string-literal unions**, or the reverse. Convention, not correctness — read two neighbouring files before proposing either direction.

## React specifics

**`key={index}`** on a list that can reorder, filter, or delete. Reordering reuses the wrong component state. **P2**, or **P1** if the list holds form inputs.

**State derived from props via `useEffect` + `setState`.** Compute it during render instead. The effect version renders twice and can show a stale frame.

**`useEffect` with an empty dependency array doing work that belongs in an event handler.**

**A dependency array that omits something the effect reads.** That is `react-hooks/exhaustive-deps`, which is a linter's job — mention it once and move on unless the omission is load-bearing.

---

# HTML

Applies to `.html`, `.htm`, and the template blocks of `.vue`/`.svelte`/`.astro`/`.jsx`.

## Never touch

**Templating syntax is not HTML.** `{{ … }}`, `{% … %}`, `<?php`, `<%= … %>`, `{#if}`, `@if`, `v-if`, `x-data`. Do not reformat, reindent or "clean up" a line containing any of them — you are editing a program in a language you are not reviewing.

**`id`, `for`, `aria-labelledby`, `aria-controls`, `headers`, `list`, `form`, `usemap`.** These cross-reference each other and are reached from CSS, from JS, and from anchors elsewhere in the site. An `id` with no visible consumer *in this file* is not an unused `id`.

**A class name you cannot find a use for.** CSS is global and JS selects by string. You cannot prove a class is unused from a diff, and the same rule holds in reverse in the CSS section below.

**`data-*` attributes.** Test selectors, JS hooks, analytics, framework state. They look decorative and are the only handle something else has.

**Conditional comments and tool markers.** `<!--[if lt IE 9]>`, `<!-- prettier-ignore -->`, `<!-- htmlmin:ignore -->`, Knockout's `<!-- ko -->` / `<!-- /ko -->` — that last pair is *control flow written as a comment*, and deleting half of it changes what the other half wraps.

**Whitespace between inline-block or inline elements is rendered.** Reflowing `<span>a</span> <span>b</span>` onto separate lines removes a space the layout depends on.

## Slop

**Redundant ARIA.** `role="button"` on `<button>`, `role="navigation"` on `<nav>`, `role="list"` on `<ul>`, `role="main"` on `<main>`. Generated markup adds ARIA to look accessible; a role that restates the native semantic is noise at best, and an ARIA attribute that *overrides* a native semantic is an accessibility regression. **The first rule of ARIA is not to use ARIA when a native element does the job.**
*Test:* does the attribute tell a screen reader something the element does not already say? If not, cut it.

**`aria-label` duplicating visible text.** `<button aria-label="Submit">Submit</button>` — the accessible name was already correct, and now there are two that can drift apart.

**Obsolete attributes.** `type="text/javascript"` on `<script>`, `type="text/css"` on `<link rel="stylesheet">`, `language="javascript"`, `charset` on `<script>`. All dead since HTML5, all still produced constantly.

**`<meta name="keywords">`.** No search engine has used it in over a decade.

**Wrapper soup.** `<div class="container"><div class="wrapper"><div class="inner">` where the outer two have no styling, no class in the stylesheet, and one child each.
*Test:* does anything select this element, and does it carry layout? If neither, it is a wrapper for its own sake — but check the stylesheet before deleting, per the class rule above.

**`<br>` for vertical spacing**, and `&nbsp;` runs for horizontal spacing.

**`<div onclick>` where a `<button>` belongs.** Loses keyboard access, focus, and the implicit role — and then the generated fix is `role="button" tabindex="0"`, which is three attributes reimplementing the element.

**Positive `tabindex`.** `tabindex="1"` and up rewrites the tab order of the whole page. `0` and `-1` are the only two that are ordinarily correct.

**Section-banner comments.** `<!-- ========== HEADER ========== -->` in a 60-line file.

---

# CSS

Applies to `.css`, `.scss`, `.sass`, `.less`, and the style blocks of component files.

## Never touch

**Source order is behaviour.** The cascade resolves ties by document order, so moving a rule, sorting a file, or "grouping related selectors" can change what renders — with no error and no test failure. Reordering CSS is not formatting churn. It is an edit, and this skill does not make it.

**A selector you cannot find a use for.** The markup that uses it may be in a template, a JS string, a CMS field, a Markdown file, or another repo. **You cannot prove a CSS rule is dead from a diff**, and this is the CSS version of the serialized-field rule: report it as a confirm-question if it matters, never as a deletion.

**A duplicate declaration is usually a fallback.** 

```css
color: #ffffff;          /* older browsers stop here */
color: var(--fg, #fff);  /* newer browsers take this */
```

Deleting "the duplicate" deletes the fallback. The same shape covers `display: block` before `display: flex`, and a pixel value before a `rem` one. Only the *last* declaration is the live one, so the earlier one is doing work precisely by being overridden.

**Vendor prefixes that are still required.** Not all of them are legacy: `-webkit-line-clamp`, `-webkit-overflow-scrolling`, `-webkit-appearance`, `-webkit-text-size-adjust`, `-moz-osx-font-smoothing`, `-webkit-box-orient`, and `-webkit-` gradient forms in some email contexts. Check caniuse before removing any prefix; the ones below are the ones that are safe.

**`/*! … */`** — the bang is a minifier instruction meaning *keep this comment*. It is almost always a license header.

**`/* stylelint-disable */`, `/* prettier-ignore */`, `/* autoprefixer: off */`.** Directives, per `core-patterns.md`.

**`content: ""`** on a `::before`/`::after`. Without it the pseudo-element does not render at all. It looks like an empty value and is the switch.

## Slop

**`!important` to win a specificity fight** that a better selector would have won. Real exceptions: utility classes, and overriding a third-party stylesheet you do not control — both are legitimate and common, so ask before proposing a removal.
*Test:* is there an `!important` on the losing rule too? Then someone is already fighting, and this is a design problem rather than a line to delete.

**Dead vendor prefixes.** `-webkit-border-radius`, `-moz-box-shadow`, `-ms-transform`, `-webkit-transition`, prefixed `box-sizing`, prefixed `border-radius` — settled for over a decade, and generated stylesheets still emit them. Delete these; keep the ones listed above.

**`z-index: 9999`**, and its escalating siblings. A number with no scale behind it.

**`position: relative` with no positioned descendant** and no other reason.

**`transition: all`.** Animates properties nobody intended, including ones added later, and defeats compositor optimisation. Name the properties.

**Over-qualified selectors.** `body div.container ul li a.link` where `.link` does it. Specificity that has to be beaten later with `!important`.

**Hard-coded values in a file full of custom properties.** `#3b82f6` where `var(--color-primary)` is what the rest of the stylesheet uses. This is the CSS form of convention drift, and it is the highest-value thing to look for in a generated stylesheet — read two neighbouring rules and see what the file does.

**A reset or normalize block re-declared in a component file.** `* { margin: 0; padding: 0; box-sizing: border-box; }` inside a component, where a global reset already ran.

**Empty rules.** `.foo { }` left after an iteration.

## Frameworks

**Tailwind's long class strings are not slop.** `class="flex items-center gap-2 rounded-md px-3 py-1.5"` is the convention working as designed. Do not propose extracting it to a CSS class, and do not propose `@apply` — the Tailwind maintainers advise against it, and it is a repo-wide style decision either way. What *is* reportable: a duplicated 15-class string repeated five times where the repo already has a component for it, and arbitrary values (`w-[13px]`) sitting beside a scale that has a token for it.

**CSS-in-JS and CSS Modules.** A style object rebuilt on every render is Agent D's if you can name the frequency, and otherwise nobody's. A `styles.foo` reference is a *use* of `.foo` — so a CSS Module class that looks unused may be reached from a component you did not open.

---

# Imports across the three

`core-patterns.md` holds the rule. The web-specific traps are the JS "never touch" table above — the side-effect import and the classic-runtime `React` import are the two that actually bite — plus one that belongs to no linter:

**`eslint --rule no-unused-vars` does not flag a bare side-effect import**, because `import './x'` binds nothing and there is no variable to be unused. So a clean ESLint run is not evidence about the single most dangerous removal in this stack. The tool and the trap do not overlap; you need both.
