# slice-to-diagram — mapping, rules, palette, geometry, internals

The generator (`scripts/generate_diagram.py`) is the source of truth; this file
documents what it does so the layout can be reasoned about and edited.

## Swimlanes

Top to bottom:

1. One lane per **actor**: UI wireframes and ⚙️ processors only. Lane = `actor:`
   minus any `(...)` qualifier (`System Agent (Settle rental)` → `System Agent`);
   default `System Agent` for automation / translation, `User` otherwise. Order of
   first use; each lane grows to fit its tallest element.
2. **Commands / Read models**: height fits the tallest sticky.
3. One **Events** lane per stream: the slice's `context:` (`EVENTS · Booking`).
   Slices without `context` share a plain `EVENTS` lane. A duplicated event
   sits in its producer's stream.
4. One lane per **external system**: `external_call.system` (automation) or
   `external.system` (translation), labelled `<system>  (external)`.
5. **Specifications**: Given / When / Then blocks (omitted with `--no-specs`
   or when no slice has scenarios).

## Per-pattern mapping (YAML → board)

| pattern | Actor lane | Cmd/Read lane | Events lane | External lane | Arrows |
|---|---|---|---|---|---|
| **state_change** | `ui` wireframe | `command` + payload | each event + fields (one column per event) | — | ui → command → event |
| **state_view** | `ui` wireframe (outputs) | `view` + fields (+ `cleared by` / `updated by`) | duplicates, if any | — | events ⇢ view → ui |
| **automation** | ⚙️ + `processor` (else the actor's qualifier), ⏱ `trigger.timer` | `command` + payload | event + fields | `external_call` system + action | view ⇢ ⚙️ → command → event; call ⇢ event |
| **translation** (2 cols) | col 2: ⚙️ | col 1: view; col 2: command | col 2: event | col 1: system + external event | external → view ⇢ ⚙️ → command → event |

Stickies show their name, then `field: type` lines (`(tag)` marks DCB tags);
`--compact` drops the lines.

## Screens as storyboard frames

`merge_screens()`: a `state_view` with a `ui` immediately followed by a
`state_change` with the same `ui.screen` is ONE frame: the screen showing the
read model, with the button for the next command. It is drawn once, in the
state_change's column (inputs + trigger + the union of both `outputs`), with
arrows view → screen → command and badge `<view id>·<change id>`. Non-adjacent
slices with the same screen stay separate frames (a later moment). The YAML is
untouched.

## Example data in wireframes

`ui_with_examples()`: an input or output shows a value instead of its type, from:
1. an explicit `example:` on the `ui` input / output;
2. else the first value for that field in the slice's scenarios: `when.payload`,
   `then.data`, or `given` view data.

Without either, inputs show the type in gray and outputs show the name only.

## No backward arrows: refs, loops, duplicates

`plan()` classifies every name a slice reads (`sources`, `trigger.event`,
`trigger.view`) by where its producer sits in the slice order:

| Producer | Drawn as |
|---|---|
| further **left** | dashed arrow from the *nearest* box with that name at or left of the reader |
| further right, and it is the view's **own consumer** (the ⚙️ triggered by this view, or the merged screen's command) | a muted line on the view: `cleared by X` (processor) / `updated by X` (screen). The To-Do loop, not a story error |
| any other event further **right** | a **duplicate** in the reader's columns (hatched, dashed, `(duplicate)`, producer's id) + stderr hint `~ story: …` |
| a **read model** further right | nothing: warning `! read model … sits right of its reader` |
| **nowhere** | a dashed gray **ghost** + warning |

A `state_view` places its duplicates under its own columns with the view in the
last one; an `automation` puts them before its chain. Each story hint means the
reader is probably told too early. Raising its `sequence:` past the producer
removes the duplicate.

## Specifications

Under each slice's main column (`anchor`: command, view, or ⚙️), one dashed
frame per scenario, stacked:

- the scenario `name`;
- `GIVEN`: one sticky per entry: event (orange), view (green), external
  (red); `data` as `key: value` lines. No entries → `(nothing happened yet)`;
- `WHEN`: the command (blue) with its payload;
- `THEN`: event(s) / view / command sticky with data, or the exception as a red
  `error` sticky (`no event emitted` when `emits: none`); `message` → white note.

Every spec sticky carries the slice's id badge; the whole frame is one group.

## Slice id badges

`Board.tag(box, sid)` puts the slice's `id:` in the box's top-right corner (gray,
size 11). `render()` sets `board.sid` per slice; every sticky is tagged.
Exceptions: a duplicate is tagged with its **producer's** id; a merged screen with
`<view id>·<change id>`; ghosts get none. Badges are the round-trip key for
`img-to-slice` (its UPDATE.md §1 matches by id first).

## Ordering

`order_slices()`:

1. if **every** slice has `sequence:`, that order is used as is (an authored
   timeline);
2. otherwise Kahn topological sort: an edge goes from the slice that *produces* a
   name to each slice that *consumes* it (`sources`, `trigger.*`, scenario `given:`
   events), with `(sequence, read-model-first, filename)` priority. Cycles (the
   To-Do loop) are broken on a real cycle member, read model first.

## Palette (`PAL`)

| key | stroke | fill | meaning |
|---|---|---|---|
| command | `#1971c2` | `#a5d8ff` | blue: write |
| event | `#e8590c` | `#ffd8a8` | orange: timeline fact |
| view | `#2f9e44` | `#b2f2bb` | green: read model |
| wire | `#343a40` | `#ffffff` | white: UI wireframe |
| auto | `#5f3dc4` | `#d0bfff` | purple: processor |
| external | `#c92a2a` | `#ffc9c9` | red: external system |
| error | `#c92a2a` | `#ffe3e3` | light red: rejected command (spec) |
| note | `#495057` | `#ffffff` | white: spec message |
| dup | `#e8590c` | `#ffd8a8` | orange, hatched + dashed: duplicated event |
| ghost | `#adb5bd` | `#f1f3f5` | gray, dashed: off-board reference |
| spec | `#ced4da` | `#f8f9fa` | dashed frame: one scenario |

## Geometry (module constants)

`COL_W=360` per column, `BOX_W=250`, `BOX_H=100` (compact sticky), `DUP_H=70`,
`START_X=40`, `TOP_Y=70`, `LANE_PAD=20`, `AGENT_H=96`, `EXT_H=120`, `CHARS=34`
(field-line width). Lane heights are measured from content in `render()` and
stored in `board.lane_y` (keys: actor name, `"cmd"`, `("event", stream)`,
`("ext", system)`, `"spec"`). Labels live in the left gutter (`LABEL_X=-250`).

## Excalidraw output

A standard `{ "type": "excalidraw", "version": 2, "elements": [...] }` document.
Stickies are a `rectangle` with a bound title `text` (`containerId` /
`boundElements`) plus unbound text for fields and badge; `Board.attach()`
records them and `dump()` groups each sticky's parts (and each wireframe, and
each scenario frame) so they move together. Arrows bind to box ids and are
edge-clipped.

## Extending

- **New pattern / element:** add a `_pattern()` renderer that returns its consumer
  box, dispatch it in `render()`, give its width and anchor in `plan()`, and
  measure any new sticky in the lane-height pass. Draw with `board.sticky(...)` at
  `board.lane_y[...] + LANE_PAD`, connect with `board.arrow(a, b)`, badge with
  `board.tag(box)`. Keep every arrow pointing up, down or right.
- **Recolor:** edit `PAL`. **Re-space:** edit the geometry constants.
- **Validate output:** every `containerId`, arrow binding and `boundElements` id
  must reference an existing element (the generator guarantees this).
