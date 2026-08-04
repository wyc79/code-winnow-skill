# Performance notes

Round:     <fill: NN>  —  .code-winnow/round-<fill: NN>/
Compared:  <fill: branch @ side>   vs   <fill: base @ sha>   (<fill: scope>)
Generated: <fill: YYYY-MM-DD HH:MM>

Scope:    <fill: N files in diff, M in feature "...">
Source:   Agent D, judgment pass. Nothing here is in the fix plan.
Status:   NOT APPLIED — hypotheses, not approved changes.
Declined: <fill: N previously declined, not repeated>

## Notes

- <fill: path:line — what does more work than it needs to>
  frequency:  <fill: how often it runs, and over how much>
  reasoning:  <fill: what in the code makes it costly>
  suggestion: <fill: the cheaper shape>
  measured:   <fill: no — or the measurement>

<!-- Write this document even when D found nothing: an empty Notes section and
     a line saying the pass ran. A missing file is indistinguishable from a
     pass that was skipped, and those are different facts. When D was not
     dispatched at all, write no document and say so in the report header.

     Never write a checklist item marker and never write a `file:` line here.
     Those are the two tokens scripts/backup.py keys on to find fix items and
     the paths to back up, so a notes document carrying either would parse as a
     fix plan - and a plan is a thing an executor edits files from. The
     differing filename is the first guard, this is the second, and
     `Status: NOT APPLIED` is the third. -->
