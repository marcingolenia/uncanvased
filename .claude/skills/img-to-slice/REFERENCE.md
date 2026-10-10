# Slice schema, scenarios, rules

Include only what the image shows.

## Common fields

```yaml
slice: <title>                # required
pattern: state_change|state_view|automation|translation   # required
actor: <role | System Agent | service name>                # required
context: <bounded context>    # only if the event lane is labeled
sequence: <int>               # see below
```

`sequence`: left-to-right board position in steps of 10; a drawn order number wins. On update keep the existing value (in fragment mode always, unless a number is drawn). A new slice takes a free value between its neighbours (e.g. 25), producer before consumer; omit if it has none.

## Per-pattern body

```yaml
# UI → Command → Event
pattern: state_change
ui:
  screen: <name>
  inputs: [ { field: <n>, type: <t>, constraints: [ ... ] } ]
  trigger: { label: "<button>", command: <CommandName> }
  outputs: [ { name: <n>, type: <t> } ]
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

GWT sub-diagrams sit below their slice in `GIVEN` / `WHEN` / `THEN` rows. Attach each to the slice whose command or view is in `WHEN`; if unclear, the slice above it.
- Each `GIVEN` sticky → one `given` entry, in order; repeats stay repeated.
- Extra text in a sticky (`Items: [Item1, Item1]`) → its `data`.
- A white note beside `THEN` → `message`.
- Several sub-diagrams → several scenarios.

```yaml
scenarios:
  - name: <what it proves, e.g. "Order fails when items are out of stock">
    given: [ { event: <EventName>, data: { ... } }, { view: <ViewName>, data: { ... } } ]
    when:  { command: <CommandName>, payload: { ... } }   # or { query: <ViewName>, key: { ... } } for state_view
                                                          # or { processor: <ProcessorName> } for automation / translation
    then:  { event: <EventName>, data: { ... }, message: "<white note>" }
    # or:  { events: [ { event: <EventName>, data: { ... } }, ... ] }
    # or:  { exception: <ExceptionName>, message: "<...>", emits: none }
    # or:  { view: <ViewName>, data: { ... } }            # state_view only
    # or:  { command: <CommandName>, payload: { ... } }   # automation / translation only
```

Automation / translation: `given` holds the trigger (`view`, or `external: { event, data }` for a translation) and any prior events; `then.command` is what the processor issues.

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
- `then` is exactly one of `event`, `events`, `exception`, `view`, `command` (`view` only with `when.query`; `command` only with `when.processor`).
