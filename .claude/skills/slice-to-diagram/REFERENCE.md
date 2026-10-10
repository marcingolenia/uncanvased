# slice-to-diagram — mapping, palette, geometry, internals

The generator (`scripts/generate_diagram.py`) is the source of truth; this file
documents what it does so the layout can be reasoned about and edited.

## Per-pattern mapping (YAML → board)

| pattern | Wireframe lane | Cmd/Read lane | Events lane | External lane | Arrows |
|---------|----------------|---------------|-------------|---------------|--------|
| **state_change** | `ui` mockup (inputs → fields, `trigger.label` → button, `outputs` → list) | `command.name` (blue) | each `event.name` (orange) | — | ui → command → event |
| **state_view** | `ui` mockup (read: `outputs` as a list) | `view.name` (green) | — | — | source events → view → ui |
| **state_change** with `events:` | as above, in the first column | `command.name` | one event per column | — | command → each event |
| **automation** | ⚙️ cog + `actor` (+ `processor`, ⏱ `trigger.timer`) | `command.name` (blue) | `event.name` (orange) | `external_call.system` + `action` (red), if any | `trigger.view` / `trigger.event` ⇢ agent (dashed); agent → command → event; call → event |
| **translation** (2 columns) | col 2: ⚙️ cog + `actor` (+ `processor`) | col 1: `view.name` (green); col 2: `command.name` | col 2: `event.name` | col 1: `external.system` + `external.event` (red) | external → view; view ⇢ agent; agent → command → event |

The cog+actor node is how automated processes appear where a human UI would sit —
matching the gear-icon rule in the `img-to-slice` classification.

## Ordering

`order_slices()` sorts by, in priority order:

1. explicit `sequence:` (lower first);
2. **event dependency** — an edge is added from the slice that *produces* a name
   (`event`/`events`, `view.name`) to any slice that *consumes*
   it (`sources`, `trigger.event`, `trigger.view`); producers sort before consumers;
3. filename.

Implemented as Kahn topological sort with a `(sequence, filename)` priority on the
ready set. **Cycles** — e.g. the canonical To-Do-list loop where a `state_view`
feeds an `automation` whose `event` feeds that same view —
are expected; they're broken deterministically by lowest `(indeg, sequence, filename)`.
Give slices an explicit `sequence:` when you want a specific left-to-right order.

## Cross-slice references & ghosts

Produced names are registered the first time they're drawn. A consumer's
dependency arrow (dashed) is drawn from the registered producer box. If a consumed
name has **no producer among the selected files** (e.g. you rendered a subset), it
is drawn as a dashed **ghost** box in the first free lane of the consumer's column
(events, external, commands; else stacked below the board), so
nothing is silently dropped. Rendering the whole `slices/` folder avoids ghosts.

## Palette (canonical Event Modeling) — `PAL`

| key | stroke | fill | meaning |
|-----|--------|------|---------|
| command | `#1971c2` | `#a5d8ff` | blue — write |
| event | `#e8590c` | `#ffd8a8` | orange — timeline fact |
| view | `#2f9e44` | `#b2f2bb` | green — read model |
| wire | `#343a40` | `#ffffff` | white — UI wireframe |
| auto | `#5f3dc4` | `#d0bfff` | purple — processor / agent |
| external | `#c92a2a` | `#ffc9c9` | red — external system |
| ghost | `#adb5bd` | `#f1f3f5` | gray — off-board reference |

## Geometry — module constants

`COL_W=360` (per-slice column), `BOX_W=250`, `BOX_H=100`, `START_X=40`,
`LANE_Y={wire:70, cmd:500, event:760, ext:1010}`. Lane labels and a title live in
the left gutter (`LABEL_X=-250`). Change these constants to retune spacing.

## Excalidraw output

A standard `{ "type": "excalidraw", "version": 2, "elements": [...],
"appState": {...}, "files": {} }` document. Boxes are `rectangle` + a bound `text`
element (`containerId` / `boundElements`); connectors are `arrow` elements with
`startBinding`/`endBinding` to the box ids and edge-clipped `points`, so arrows
stay attached when boxes are dragged in Excalidraw. Elements carry the required
fields (`seed`, `versionNonce`, `roundness`, `strokeStyle`, …) so the file imports
cleanly at excalidraw.com and in the VS Code extension.

## Extending

- **New pattern / element:** add a `_pattern()` renderer, dispatch it in
  `render()` and give its width in `span()`; call `board.place(col, lane)` for
  each box so ghosts avoid it; use `board.labeled(...)` for a sticky and `board.arrow(a, b)` to
  connect two box tuples `(id, x, y, w, h)`.
- **Recolor:** edit `PAL`. **Re-space:** edit the geometry constants.
- **Validate output:** every `containerId`, arrow binding, and `boundElements` id
  must reference an existing element id (the generator guarantees this).
