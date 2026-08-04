# Fix plan

Round:     <fill: NN>  —  .code-winnow/round-<fill: NN>/
Compared:  <fill: branch @ side>   vs   <fill: base @ sha>   (<fill: scope>)
Generated: <fill: YYYY-MM-DD HH:MM>

Status:   <fill: APPROVED by WHO on DATE — or UNAPPROVED, no human reviewed these findings>
Skill:    <fill: the absolute path of the code-winnow skill directory>
Scope:    <fill: N files in diff, M in feature "...">
Feature:  <fill: the user's own words, and the files they were confirmed to mean — or "none named">
Baseline: <fill: .code-winnow/round-NN/scan.json>
Backup:   <fill: .code-winnow/round-NN/pre-fix/>
Undo:     <fill: cp -a .code-winnow/round-NN/pre-fix/. .>
Verify:   <fill: the project's test command>
Tests-before: (filled in by Step 5a, before the first edit)

## Code fixes — approved (delete a whole item to drop it)

- [ ] <fill: P1|P2|P3 — one line, what and why>
      file:       <fill: path/from/repo/root.ext>
      line:       <fill: N>
      occurrence: <fill: anchor_index from the scanner JSON>
      of:         <fill: anchor_total from the scanner JSON>
      anchor:     <fill: the source line, unquoted and unfenced>
      fix:        <fill: the smallest change that resolves it>
      evidence:   <fill: the commands you ran and what they returned — or
                  "rewrite, nothing removed" — or "unverified — THE LOOKUP YOU
                  COULD NOT PERFORM", which forbids a deletion>

## Doc fixes — approved

## Header fixes — approved separately at the Step 4 gate

## Never touch

- <fill: what is load-bearing here, and the mechanism that makes it so>
- Any file not named by a `file:` line above
