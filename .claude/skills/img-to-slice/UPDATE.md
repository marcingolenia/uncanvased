# img-to-slice — updating existing slices

A board is often re-drawn because a requirement changed, then parsed again. The board is the newer truth, but an existing slice file may hold work the board can't show. Reconcile each slice before writing it.

The image may show only the changed slices. Existing slices that aren't in the image stay untouched; never propose deleting them.

## 1. Match

A transcribed slice **is** an existing slice when either:
- its filename slug matches an existing file in `slices/`, or
- it has the same `pattern` and the same `command.name` (`state_change` / `automation` / `translation`) or `view.name` (`state_view`). This is a **renamed** slice: it keeps the existing file unless the user picks the new name.

No match → write a new file. A match with identical YAML → nothing to do.

## 2. Ask (before the gap review)

For each matched slice whose YAML differs, ask one `AskUserQuestion`:
- `header`: `Update`
- `question`: the slice title, the file, and a one-line summary of what changed on the board
- `options`, each with a `preview` showing the diff (`-` / `+` lines):
  1. **Update from board (Recommended):** take the board's version, but keep everything the board can't express unless the board contradicts it:
     - `scenarios:` authored in the YAML
     - nodes marked `# added: gap review`
     - `# gap-ignored:`, `# todo:` and `# note:` comments
     - `sequence:` if the board shows none

     A kept scenario that references an event, field or view the board removed or renamed is **stale**. List it in the preview, marked `stale`, and ask a follow-up: rewrite it to the new names, or drop it.
  2. **Replace entirely:** write exactly what the board shows.
  3. **Keep existing:** leave the file untouched and skip this slice's board version.

A renamed slice gets a 4th option, **Update and rename file**, which moves the file to the new slug.

## 3. Ripple

If accepted updates rename or reshape an event, view or command, the consistency rules require every slice that uses it to change identically. Collect the affected **existing** files that are not part of this run, then ask **one** question for all of them:
- `header`: `Ripple`
- `preview`: the per-file diff
- options:
  - **Apply everywhere (Recommended)**
  - **Skip:** leave a `# todo: <Name> changed in <slice file>` comment on each affected node

Outside the gap review, this is the only case where files outside this run are edited.

## Kept slices

A slice the user chose to **keep** counts as an existing slice in the gap review: context only, never questioned.

## Non-interactive runs

If `AskUserQuestion` is not available, never overwrite. Keep every existing file and list each matched slice whose YAML differs as `differs from board, not updated` in the final summary. Skip the ripple step.
