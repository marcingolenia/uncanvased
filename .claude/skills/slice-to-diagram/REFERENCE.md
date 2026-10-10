# slice-to-diagram — mapping, palette, geometry, internals

The generator (`scripts/generate_diagram.py`) is the source of truth; this file
documents what it does so the layout can be reasoned about and edited.

## Swimlanes

Top to bottom: one lane per **actor** (UI mockups and ⚙️ processors only), then
**Commands / Read models**, **Events**, and one lane per **external system**.

- Actor lane = `actor:` minus any `(...)` qualifier (`System Agent (Settle rental)`
  → `System Agent`); default `System Agent` for automation / translation, `User`
  otherwise. Lanes appear in order of first use; each grows to fit its tallest
  mockup.
- External lane = `external_call.system` (automation) or `external.system`
  (translation), labelled `<system>  (external)`.

## Per-pattern mapping (YAML → board)

| pattern | Actor lane | Cmd/Read lane | Events lane | External lane | Arrows |
|---------|------------|---------------|-------------|---------------|--------|
| **state_change** | `ui` mockup (inputs → fields, `trigger.label` → button, `outputs` → list) | `command.name` (blue) | each `event.name` (orange) | — | ui → command → event |
| **state_view** | `ui` mockup (read: `outputs` as a list) | `view.name` (green) | duplicated sources, if any | — | source events ⇢ view → ui |
| **state_change** with `events:` | as above, in the first column | `command.name` | one event per column | — | command → each event |
| **automation** | ⚙️ cog + `processor` (else the actor's qualifier), ⏱ `trigger.timer` | `command.name` (blue) | `event.name` (orange) | `external_call.system` + `action` (red), if any | `trigger.view` / `trigger.event` ⇢ agent; agent → command → event; call ⇢ event |
| **translation** (2 columns) | col 2: ⚙️ cog + processor | col 1: `view.name` (green); col 2: `command.name` | col 2: `event.name` | col 1: `external.system` + `external.event` (red) | external → view; view ⇢ agent; agent → command → event |

## Slice id badges

`Board.tag(box, sid)` puts the slice's `id:` in the box's top-right corner (gray,
size 11) and groups badge, box and label so they move together. `render()` sets
`board.sid` per slice; every sticky helper (`_command`, `_event`, `_external`,
`_agent`, views, wireframes) tags with it. Exceptions: a duplicated event is
tagged with its **producer's** id; a merged screen with `<view id>·<change id>`;
ghosts get none. Badges are the round-trip key for `img-to-slice` (its
UPDATE.md §1 matches by id first).

## Screens as storyboard frames

`merge_screens()`: when a `state_view` with a `ui` is immediately followed by a
`state_change` with the same `ui.screen`, both are one frame of the storyboard —
the screen showing the read model, with the button for the next command. It is
drawn once, in the `state_change`'s column, with the state_change's inputs and
trigger and the union of both slices' `outputs`; arrows run view → screen →
command. Non-adjacent slices with the same screen stay separate frames (the
screen at a later point in time). The YAML is untouched; each slice keeps its
own `ui`.

## No backward arrows — duplicated events

`plan()` classifies every name a slice reads (`sources`, `trigger.event`,
`trigger.view`) by where its producer sits in the slice order:

- **produced further left** → a dashed arrow from the *nearest* box with that
  name at or left of the reader (original or an earlier duplicate);
- **event produced further right** → a **duplicate**: the event is re-drawn in
  the reader's own columns (`dup` palette: hatched fill, dashed stroke, label
  `<Event>\n(duplicate)`) and the arrow runs up or right from it;
- **read model produced further right** → *not* duplicated (only events are a
  shared contract); warning `read model X sits right of its reader`, no arrow;
- **produced nowhere** → a dashed gray **ghost** in the same slot, with a warning.

A `state_view` places its duplicates under its own columns with the view in the
last one; an `automation` puts them before its chain. Rendering the whole
`slices/` folder avoids ghosts.

## Ordering

`order_slices()`:

1. if **every** slice has `sequence:`, that order is used as is (an authored
   timeline);
2. otherwise Kahn topological sort — an edge from the slice that *produces* a
   name (`event`/`events`, `view.name`) to each slice that *consumes* it
   (`sources`, `trigger.*`, scenario `given:` events) — with
   `(sequence, read-model-first, filename)` priority on the ready set.
   **Cycles** (the To-Do-list loop) are broken on a real cycle member,
   read model first.

## Palette (canonical Event Modeling) — `PAL`

| key | stroke | fill | meaning |
|-----|--------|------|---------|
| command | `#1971c2` | `#a5d8ff` | blue — write |
| event | `#e8590c` | `#ffd8a8` | orange — timeline fact |
| view | `#2f9e44` | `#b2f2bb` | green — read model |
| wire | `#343a40` | `#ffffff` | white — UI wireframe |
| auto | `#5f3dc4` | `#d0bfff` | purple — processor / agent |
| external | `#c92a2a` | `#ffc9c9` | red — external system |
| ghost | `#adb5bd` | `#f1f3f5` | gray, dashed — off-board reference |
| dup | `#e8590c` | `#ffd8a8` | orange, hatched + dashed — duplicated event |

## Geometry — module constants

`COL_W=360` (per column), `BOX_W=250`, `BOX_H=100`, `START_X=40`,
`TOP_Y=70` (first actor lane), `LANE_PAD=20`, `AGENT_H=96`,
`LANE_H={cmd:200, event:200, ext:160}`. Lane y positions are computed in
`render()` and kept in `board.lane_y` (keys: actor name, `"cmd"`, `"event"`,
`("ext", system)`). Lane labels and a title live in the left gutter (`LABEL_X=-250`). Change these constants to retune spacing.

## Excalidraw output

A standard `{ "type": "excalidraw", "version": 2, "elements": [...],
"appState": {...}, "files": {} }` document. Boxes are `rectangle` + a bound `text`
element (`containerId` / `boundElements`); connectors are `arrow` elements with
`startBinding`/`endBinding` to the box ids and edge-clipped `points`, so arrows
stay attached when boxes are dragged in Excalidraw. Elements carry the required
fields (`seed`, `versionNonce`, `roundness`, `strokeStyle`, …) so the file imports
cleanly at excalidraw.com and in the VS Code extension.

## Extending

- **New pattern / element:** add a `_pattern()` renderer that returns its
  consumer box, dispatch it in `render()` and give its width in `plan()`; use
  `board.labeled(...)` with `board.lane_y[...]` for a sticky and
  `board.arrow(a, b)` to connect two box tuples `(id, x, y, w, h)`. Keep every
  arrow pointing up, down or right.
- **Recolor:** edit `PAL`. **Re-space:** edit the geometry constants.
- **Validate output:** every `containerId`, arrow binding, and `boundElements` id
  must reference an existing element id (the generator guarantees this).
