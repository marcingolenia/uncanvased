# img-to-slice — per-pattern schema, scenarios, rules

Include only fields the image supports. Omit anything the board does not show.

## Common fields (every slice)

```yaml
slice: <human title>          # required
pattern: state_change|state_view|automation|translation   # required
actor: <role | System Agent | service name>                # required
context: <bounded context>    # optional; only if the event lane is labeled
sequence: <int>               # left-to-right position on the board, in steps of 10 (10, 20, 30…);
                              # an explicit order number on the board wins. On update, keep the
                              # existing value unless the slice moved; a new slice between two
                              # others takes a free value between them (e.g. 25). If the image is a
                              # fragment, place new slices relative to their neighbours in slices/
                              # (producer before consumer); omit sequence if there are none
```

## Per-pattern body

```yaml
# state_change — UI → Command → Event
ui:
  screen: <name>
  inputs: [ { field: <n>, type: <t>, constraints: [ ... ] } ]
  trigger: { label: "<button>", command: <CommandName> }
  outputs: [ { name: <n>, type: <t> } ]
command: { name: <CommandName>, payload: { <field>: <type> } }
event:
  name: <EventName>
  tags: [ ... ]               # DCB tag keys; MUST be a subset of fields
  # If the entity clearly has identity but no id field is drawn, add `# ? missing id/tag`
  # on the event rather than inventing an id or leaving the gap silent.
  fields: { <field>: <type> }
# events: [ { name, tags, fields }, ... ]   # instead of `event`, ONLY when the command
#                                           # visibly produces several events (+ `# warn:`)
constraints: [ "<business rule, prose>" ]   # from white sticky notes on/near the slice

# state_view — Event(s) → Read Model (→ UI)
sources: [ <EventName>, ... ]         # internal events only
view: { name: <ViewName>, tags: [ ... ], fields: { <field>: <type> } }
ui:  { screen: <name>, outputs: [ { name: <n>, type: <t> } ] }   # omit if no UI drawn

# automation — internal Read Model → ⚙️ → Command → Event
trigger: { view: <ViewName> }         # the to-do read model (preferred)
                                      # or { timer: "<desc>" } for a clock-driven cog
                                      # or { event: <EventName> } only if drawn so (+ `# warn:`)
processor: <ProcessorName>            # label next to the ⚙️; omit if unlabeled
external_call:                        # optional: 3rd-party call the processor makes, if written on the board
  system: <name>
  action: "<HTTP verb + endpoint / RPC / API method>"
command: { name: <CommandName>, payload: { <field>: <type> } }
event: { name: <EventName>, tags: [ ... ], fields: { <field>: <type> } }

# translation — External Event → Read Model → ⚙️ → Command → internal Event
external:
  system: <name>                      # external lane label / badge; `<name>  # inferred` if only "(External)"
  event: <ExternalEvent>              # the pink sticky — keep the foreign system's language
  fields: { <field>: <type> }         # optional
view: { name: <ViewName>, tags: [ ... ], fields: { <field>: <type> } }   # read model fed by the external event
processor: <ProcessorName>
command: { name: <CommandName>, payload: { <field>: <type> } }
event: { name: <InternalEvent>, tags: [ ... ], fields: { <field>: <type> } }
```

**Anti-corruption naming:** the translation's internal `event` (and its command) is named in **domain language** (`ProductRated`), never after the external system or transport (`RatingImported`, `ExternalRatingSynced`). The foreign name lives only in `external.event`. If origin matters to the domain, record it as a field (`source`, `observedAt`), never in the event name.

## Scenarios (Given-When-Then)

### Reading GWT sub-diagrams

GWT boxes are drawn **below** the slice they belong to, in rows labeled `GIVEN` / `WHEN` / `THEN`. Attach a sub-diagram to the slice whose command (or view) appears in its `WHEN` row; if ambiguous, use the slice it sits under.

- Each sticky in `GIVEN` → one `given` entry, in drawn order. Repeated stickies stay repeated (two `Item1 Added to Warehouse` → two entries).
- Text inside a sticky beyond its title (`Items: [Item1, Item1]`) → that entry's `data`.
- The `THEN` row holds an event (incl. a failure event like `Order Failed`), several events, or an exception. A **white sticky** next to it is the reason/message → `message: "<text>"`.
- Several sub-diagrams under one slice → several scenarios.

### Shape

```yaml
scenarios:
  - name: <what it proves — reflect the actual precondition/branch>
    given: [ { event: <EventName>, data: { ... } }, { view: <ViewName>, data: { ... } } ]
    when:  { command: <CommandName>, payload: { ... } }   # state_change / automation / translation
    # or:  { query: <ViewName>, key: { ... } }            # state_view
    then:  { event: <EventName>, data: { ... }, message: "<white note>" }
    # OR:  { view: <ViewName>, data: { ... } }            # state_view only: expected read-model state
    # OR:  { events: [ { event: <EventName>, data: { ... } }, ... ] }
    # OR:  { exception: <ExceptionName>, message: "<...>", emits: none }
```

Name the scenario after what the drawing shows (`Order fails when items are out of stock`); a failure that is drawn as a yellow event stays an `event`, not an `exception`.

### When to emit

A scenario is only worth emitting if it says something the slice's wiring does **not** already imply — a **given** precondition, **concrete values**, or a **failure/branch**. A bare happy-path `when → then` with `given: []` and no values is a tautology — skip it. If the board draws an empty GWT region, add a slice-level `# todo: scenario placeholder drawn, author to complete` and emit no `scenarios:`.

## White sticky notes

- On or next to a `state_change` slice → a `constraints:` entry (verbatim text).
- Inside a GWT `THEN` row → the scenario's `message`.
- Anywhere else → `# note: <text>` on the nearest node.

## Consistency rules (the validator enforces these — don't violate them)

- Every `tags` entry is one of that event/view's `fields`.
- Reuse the **exact same name** for an event/view/command every place it appears, with **identical field/tag shapes**.
- `state_view` has no `command`; `automation` and `translation` have no `ui`.
- `automation` and `translation` both require `command` and the resulting `event` — no event appears without a command.
- An **external event** appears only as a translation's `external.event`. A `state_view`'s `sources` are internal events only; the only read model that consumes an external event is the one inside a `translation` slice.
- `event` and `events` are mutually exclusive on a `state_change`; `events` needs a `# warn:`.
- Scenario `then` is exactly one of `event`, `events`, `exception`, or `view` (`view` only on a `state_view` scenario, paired with `when.query`).
