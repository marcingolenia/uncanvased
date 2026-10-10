# Updating existing slices

The board is the newer truth, but a slice file may hold work the board can't show. Slices not in the image stay untouched; never propose deleting them.

## 0. Whole board or fragment

If `slices/` is not empty, ask once (`header`: `Input`): **Fragment (Recommended)** or **Whole board**. Non-interactive runs assume fragment.

Fragment mode only adds or changes:
- Anything in the YAML but not in the image is kept, unless crossed out on the image or the user removes it.
- An element cut off by the frame is context: match it to an existing slice by name, or ask. It never becomes a new slice.
- `id` never changes. `actor`, `context` and `sequence` keep existing values unless the image shows them. New slices take them from their lane or neighbours.

Whole-board mode: what the board omits was removed (still shown in the diff).

## 1. Match

A slice matches an existing one, in this order:
1. by **id badge**: the board's corner number equals an existing `id`. This is certain: names, pattern or position may all have changed. A duplicated event carries its producer's id; it matches that slice's event and never forms a slice of its own.
2. by filename slug;
3. by same `pattern` plus same `command.name` (or `view.name` for `state_view`). This is a rename; it keeps the old file unless the user picks the new name.

Unbadged stickies are new on the board: attach them to a badged slice they are wired into, or make a new slice with the next free `id`. A badge with no matching file (deleted slice), or one badge on two separate slices, is a conflict: ask.

If a matched slice shows a different name (`CarReserved` vs `CarBooked`), ask **Rename** (then ripple) or **New** (alongside the old one). For events, warn: "If implemented, renaming stored events is a migration. Prefer New."

## 2. Ask

Fragment mode: apply the board's changes to matched slices without asking, and keep everything absent from the image silently. Ask only about renames (§1), crossed-out elements and conflicts, and about a kept scenario that references a removed or renamed name (`stale`: rewrite or drop). Report applied updates in the summary.

Whole-board mode: ask one multi-select (`header`: `Update`) listing every matched slice whose YAML differs, with a diff `preview`: "Which slices do you want updated from the board?" Ticked slices get **Update from board**; unticked ones are kept (**Keep existing**, which then counts as existing context in the gap review). A renamed slice adds **Update and rename file**; **Replace entirely** is offered only on request.

**Update from board** applies the board's changes but keeps YAML-only content: scenarios, `# added: gap review` nodes, `# gap-ignored:`, `# todo:` and `# note:` comments, and `sequence:` if the board shows none. Drop an `# added:` marker once the board shows that node. An unreadable or `# ?` board value never replaces an existing value.

## 3. Ripple

If a rename or reshape affects existing files outside this run, ask one question (`header`: `Ripple`) with per-file diffs: **Apply everywhere (Recommended)** or **Skip** (`# todo: <Name> changed in <file>` on each affected node).

## Non-interactive

Fragment mode (§0): apply the board's changes to matched slices by the **Update from board** rules (§2), keeping YAML-only content, and report each updated slice. Never ask: treat changed names as New and flag them; leave crossed-out elements, conflicts and `stale` scenarios unchanged and list them in the summary; skip ripple.
