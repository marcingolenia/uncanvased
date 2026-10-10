# Updating existing slices

The board is the newer truth, but a slice file may hold work the board can't show. Slices not in the image stay untouched; never propose deleting them.

## 0. Whole board or fragment

If `slices/` is not empty, ask once (`header`: `Input`): **Fragment (Recommended)** or **Whole board**. Non-interactive runs assume fragment.

Fragment mode only adds or changes:
- Anything in the YAML but not in the image is kept, unless crossed out on the image or the user removes it.
- An element cut off by the frame is context: match it to an existing slice by name, or ask. It never becomes a new slice.
- `actor`, `context` and `sequence` keep existing values unless the image shows them. New slices take them from their lane or neighbours.

Whole-board mode: what the board omits was removed (still shown in the diff).

## 1. Match

A slice matches an existing one by filename slug, or by same `pattern` plus same `command.name` (or `view.name` for `state_view`). The latter is a rename; it keeps the old file unless the user picks the new name.

If a matched slice shows a different name (`CarReserved` vs `CarBooked`), ask **Rename** (then ripple) or **New** (alongside the old one). For events, warn: "If implemented, renaming stored events is a migration. Prefer New."

## 2. Ask

For each matched slice whose YAML differs, ask one question (`header`: `Update`) naming the slice, the file and the change, with a diff `preview` on each option:
1. **Update from board (Recommended):** apply the board's changes but keep YAML-only content: scenarios, `# added: gap review` nodes, `# gap-ignored:`, `# todo:` and `# note:` comments, and `sequence:` if the board shows none. Drop an `# added:` marker once the board shows that node.
   - Fragment mode: show elements missing from the image as `? not on image — kept`, then ask once: keep all (Recommended) or pick which to remove.
   - A kept scenario referencing a removed or renamed name is `stale`: ask to rewrite or drop it.
2. **Replace entirely** (whole-board mode only).
3. **Keep existing.** The slice then counts as existing context in the gap review.

A renamed slice adds **Update and rename file**.

## 3. Ripple

If a rename or reshape affects existing files outside this run, ask one question (`header`: `Ripple`) with per-file diffs: **Apply everywhere (Recommended)** or **Skip** (`# todo: <Name> changed in <file>` on each affected node).

## Non-interactive

Never overwrite. Keep existing files and report each differing slice as `differs from board, not updated`. Treat changed names as New and flag them. Skip ripple.
