# img-to-slice — updating existing slices

A board is often re-drawn because a requirement changed, then parsed again. The board is the newer truth, but an existing slice file may hold work the board can't show. Reconcile each slice before writing it.

Existing slices that aren't in the image stay untouched; never propose deleting them.

## 0. Whole board or fragment?

If `slices/` is not empty, ask once, before transcribing (`header`: `Input`):
- **Fragment (Recommended)**: the image shows only some slices, possibly cropped
- **Whole board**: the image shows every slice in full

Non-interactive runs assume **fragment**. Fragment mode only adds or changes; it never removes by omission.

**In fragment mode:**
- **Not drawn ≠ removed.** Anything in the existing YAML but not in the image (a source, a field, an input) is kept. It is removed only if the image visibly crosses it out, or the user picks `remove` for it in the update question.
- **Cut-off elements are context.** An element whose chain leaves the frame (e.g. an event at the edge whose command is off-picture) never becomes a new slice. Match it to an existing slice by name. If nothing matches, ask the user what it is.
- **Unshown metadata is kept.** `actor`, `context` and `sequence` keep their existing values unless the image shows them (a lane label, an order number). A new slice gets `actor` / `context` from its lane if drawn, otherwise from its neighbouring slices, and `sequence` by the fragment rule in [REFERENCE.md](REFERENCE.md).

**In whole-board mode,** the board's version of a slice is complete: what is missing was removed. The removal still shows in the update question's diff.

## 1. Match

A transcribed slice **is** an existing slice when either:
- its filename slug matches an existing file in `slices/`, or
- it has the same `pattern` and the same `command.name` (`state_change` / `automation` / `translation`) or `view.name` (`state_view`). This is a **renamed** slice: it keeps the existing file unless the user picks the new name.

No match → write a new file. A match with identical YAML → nothing to do.

**Changed names.** If a matched slice shows a different event, command or view name than the file (e.g. `CarReserved` where the file says `CarBooked`), ask. Never guess:
- **Rename** `CarBooked` → `CarReserved`, then ripple (§3)
- **New**: a different element alongside the old one

For an event, the question warns: "If this slice is already implemented, the events are stored, so a rename is a migration and a contract change. Prefer **New**: add the new event and keep the old one for history."

## 2. Ask (before the gap review)

For each matched slice whose YAML differs, ask one `AskUserQuestion`:
- `header`: `Update`
- `question`: the slice title, the file, and a one-line summary of what changed on the board
- `options`, each with a `preview` showing the diff (`-` / `+` lines):
  1. **Update from board (Recommended):** apply the board's changes, but keep everything the board can't express unless the board contradicts it:
     - `scenarios:` authored in the YAML
     - nodes marked `# added: gap review`. If the board now shows such a node, drop its marker: the board has caught up
     - `# gap-ignored:`, `# todo:` and `# note:` comments
     - `sequence:` if the board shows none

     In fragment mode, list each existing element missing from the image in the preview as `? not on image — kept`. If there are any, ask one follow-up: keep all (Recommended), or pick which to remove.

     A kept scenario that references an event, field or view the board removed or renamed is **stale**. List it in the preview, marked `stale`, and ask a follow-up: rewrite it to the new names, or drop it.
  2. **Replace entirely:** write exactly what the board shows. Not offered in fragment mode.
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

If `AskUserQuestion` is not available, assume fragment mode and never overwrite. Keep every existing file and list each matched slice whose YAML differs as `differs from board, not updated` in the final summary. Treat a changed name as **New** and flag it in the summary. Skip the ripple step.
