# Slice schema, scenarios, rules

Include only what the image shows.

## Common fields

```yaml
slice: <title>                # required
id: <int>                     # required; stable slice id, see below
pattern: state_change|state_view|automation|translation   # required
actor: <role | System Agent | service name>                # required; state_view: only if a UI reads it
context: <event stream>       # event lane label (`Booking`); else set in the gap review (`no-stream`)
sequence: <int>               # see below
```

`id`: the slice's permanent identity, drawn as a corner badge on every element of the slice. Assigned once: a badge on the board wins; otherwise the next free number (highest `id` in `slices/` + 1), handed out left to right. Never renumber, never reuse an id, even after a slice is deleted. Renaming or moving a slice keeps its `id`.

`context`: the stream the slice's events belong to: one swimlane per business entity or bounded context whose lifecycle they record (`Vehicle`, `Booking`, `Payment`). Name streams in business language, not after technical components.

`sequence`: the slice's place in the story, left to right in steps of 10. A slice comes after every event it reads, except events recorded by its own consumer (the ⚙️ it triggers, or the button on the screen it feeds); the `out-of-story` gap checks this. Start from the board position; a drawn order number wins (an order number, not an id badge). On update keep the existing value (in fragment mode always, unless a number is drawn). A new slice takes a free value between its neighbours (e.g. 25), producer before consumer; omit if it has none.

## Per-pattern body

```yaml
# UI → Command → Event
pattern: state_change
ui:
  screen: <name>
  inputs: [ { field: <n>, type: <t>, constraints: [ ... ], example: <value> } ]   # example: only if a value is drawn
  trigger: { label: "<button>", command: <CommandName> }
  outputs: [ { name: <n>, type: <t>, example: <value> } ]
command: { name: <CommandName>, payload: { <field>: <type> } }
event:
  name: <EventName>
  tags: [ ... ]               # DCB tag keys, a subset of fields; identity but no id drawn → `# ? missing id/tag`
  fields: { <field>: <type> }
# events: [ { name, tags, fields }, ... ]   # instead of `event`, only if drawn so (+ `# warn:`)
constraints: [ "<rule>" ]     # white notes on/near the slice
```

```yaml
# Event(s) → Read Model (→ UI)
pattern: state_view
sources: [ <EventName>, ... ] # internal events only
view: { name: <ViewName>, tags: [ ... ], fields: { <field>: <type> } }
ui: { screen: <name>, outputs: [ { name: <n>, type: <t> } ] }   # only if drawn
```

```yaml
# Read Model → ⚙️ → Command → Event
pattern: automation
trigger: { view: <ViewName> } # or { timer: "<desc>" }; { event: <EventName> } only if drawn so (+ `# warn:`)
processor: <ProcessorName>    # ⚙️ label, if any
external_call: { system: <name>, action: "<verb + endpoint / method>" }   # only if written on the board
command: { name: <CommandName>, payload: { <field>: <type> } }
event: { name: <EventName>, tags: [ ... ], fields: { <field>: <type> } }
```

```yaml
# External Event → Read Model → ⚙️ → Command → internal Event
pattern: translation
external:
  system: <name>              # lane label or badge; `<name>  # inferred` if only "(External)"
  event: <ExternalEvent>      # foreign system's language
  fields: { <field>: <type> }
view: { name: <ViewName>, tags: [ ... ], fields: { <field>: <type> } }
processor: <ProcessorName>
command: { name: <CommandName>, payload: { <field>: <type> } }
event: { name: <InternalEvent>, tags: [ ... ], fields: { <field>: <type> } }
```

**Anti-corruption:** name a translation's command and event in domain language (`ProductRated`), never after the source (`RatingImported`). The foreign name lives only in `external.event`; record origin as a field if it matters.

## Scenarios

GWT sub-diagrams sit below their slice in `GIVEN` / `WHEN` / `THEN` rows. On a board drawn by `slice-to-diagram`, each scenario is a dashed frame under its slice: the frame title is `name`, stickies carry the slice's id badge and `key: value` data lines, `(nothing happened yet)` means `given: []`, a red sticky in `THEN` is the `exception` (`no event emitted` → `emits: none`), and a white note under it is `message`. Attach each to the slice whose command is in `WHEN`, or, with no `WHEN` row, whose view or command is in `THEN`; if unclear, the slice above it.
- Each `GIVEN` sticky → one `given` entry, in order; repeats stay repeated.
- Extra text in a sticky (`Items: [Item1, Item1]`) → its `data`.
- A white note beside `THEN` → `message`.
- Several sub-diagrams → several scenarios.

```yaml
scenarios:
  - name: <what it proves, e.g. "Order fails when items are out of stock">
    given: [ { event: <EventName>, data: { ... } }, { view: <ViewName>, data: { ... } } ]
    when:  { command: <CommandName>, payload: { ... } }   # state_change only; state_view / automation / translation have no `when`
    then:  { event: <EventName>, data: { ... }, message: "<white note>" }
    # or:  { events: [ { event: <EventName>, data: { ... } }, ... ] }
    # or:  { exception: <ExceptionName>, message: "<...>", emits: none }
    # or:  { view: <ViewName>, data: { ... } }            # state_view: Given events → Then view
    # or:  { command: <CommandName>, payload: { ... } }   # automation / translation: Given to-do view → Then command
```

State view: `given` holds the source events; `then.view` is the resulting state. A to-do list (a view that triggers a ⚙️ or feeds a screen whose button clears an item) earns a spec showing an item leaving the list:

```yaml
scenarios:
  - name: Authorized deposit leaves the list
    given:
      - { event: BookingPlaced, data: { bookingId: "B-1", quotedTotal: 250.00 } }
      - { event: DepositAuthorized, data: { bookingId: "B-1", amount: 250.00 } }
    then: { view: DepositsToAuthorize, data: { items: [] } }
``` Automation / translation: `given` holds the trigger (`view`, or `external: { event, data }` for a translation) and any prior events; `then.command` is what the processor issues.

A failure drawn as a yellow event stays an `event`. Emit a scenario only if it adds a precondition, concrete values or a failure; skip a bare happy path. An empty GWT region drawn → `# todo: scenario placeholder drawn, author to complete`, no `scenarios:`.

## White notes

- Near a `state_change` slice → `constraints:` entry, verbatim.
- In a `THEN` row → scenario `message`.
- Elsewhere → `# note: <text>` on the nearest node.

## Consistency rules (validator-enforced)

- `tags` ⊆ that event's or view's `fields`.
- One name per event / view / command everywhere, with identical fields and tags.
- `state_view` has no `command`; `automation` and `translation` have no `ui` and require `command` + `event`.
- External events appear only in `external.event`; `sources` are internal events.
- `event` xor `events`; `events` needs a `# warn:`.
- `ui.trigger.command` equals `command.name`.
- Every name in a scenario (`given`, `when`, `then`) is an event, view or command defined in some slice; `when.command` is this slice's own command, `then.view` its own view, `then.command` its own command.
- `when` only in `state_change`, where it is required.
- `then` is exactly one of `event`, `events`, `exception`, `view`, `command` (`view` only in `state_view`; `command` only in `automation` / `translation`).
