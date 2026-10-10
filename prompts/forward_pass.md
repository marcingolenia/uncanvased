# Forward-pass prompt — Event Model image → Uncanvased YAML

You convert a photo/screenshot of an **Event Model** (Miro, Excalidraw, whiteboard, paper)
into **Uncanvased slices**. The authored YAML is the source of truth; prose is generated later,
so **you author only YAML**.

## Output contract — write one file per slice
- Write **one slice file per vertical slice** into the `slices/` directory (create it if absent). Each file is a Markdown file whose entire content is a single fenced ` ```yaml uncanvased ` block — nothing else. The renderer appends the generated prose below it later; do not write prose yourself.
- **Filename** is a kebab-case slug derived from the slice title: lowercase, spaces → `-`, drop punctuation (e.g. `Add List` → `slices/add-list.md`, `Todo Lists` → `slices/todo-lists.md`). Filenames do **not** encode order — timeline order is derived downstream, so never number them or renumber on insert. If two titles collide, append `-2`, `-3`, ….
- **Do not overwrite** an existing slice file whose YAML differs without flagging it: if a target filename already exists, note it in your final summary rather than silently clobbering authored work.
- After writing, reply with **only a brief confirmation** — the list of files written (path + slice title), one per line. Do **not** echo the YAML back in the response.
- Transcribe only what the image shows. **Do not invent** fields, constraints, or scenarios. When a type is unreadable, use `string`. When a value is illegible, keep the label and add ` # ?` on that line.
- Preserve any **badge, `*`, star, or annotation** on a box as a trailing `# note: <text>` on that node — never silently drop it (a starred read model, a flagged event, etc. usually carries intent).

## Classify each slice by `pattern` (visual cues)
- **state_change** — a UI/screen → **command** (blue) → **event(s)** (orange). The write side.
- **state_view** — **event(s)** (orange) → **view / read model** (green) → UI. No command. Needs `sources`.
- **automation** — no UI/human. A trigger (event | view | timer) → processor → **command**.
- **translation** — an external-system boundary. External event ↔ internal event. No UI, no command.

Colors are hints, not proof — classify by the boxes and arrows present.

## Common fields (every slice)
```yaml
slice: <human title>          # required
pattern: state_change|state_view|automation|translation   # required
actor: <role | System Agent | external service>            # required
sequence: <int>               # left-to-right position on the board, steps of 10; an explicit order number wins
```

Actors are rarely drawn. If no swimlane/actor label is present, **infer a default and mark it** rather than guessing per slice:
- `state_change` with a UI → the screen's human user (e.g. `User  # inferred`).
- `state_view` / `automation` → `System Agent  # inferred`.
- `translation` → the external system on the boundary (e.g. `EmailProvider  # inferred`).
Use `# inferred` (a confident default) — reserve `# ?` for labels that are present but illegible.

## Per-pattern body (include only fields the image supports)
```yaml
# state_change
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
constraints: [ "<business rule / DCB boundary, prose>" ]

# state_view
sources: [ <EventName>, ... ]         # events projected in
view: { name: <ViewName>, tags: [ ... ], fields: { <field>: <type> } }
ui:  { screen: <name>, outputs: [ { name: <n>, type: <t> } ] }

# automation
trigger: { event: <EventName> }       # or { view: <ViewName> } | { timer: <desc> }
processor: <ProcessorName>
command: { name: <CommandName>, payload: { <field>: <type> } }

# translation
direction: inbound|outbound
external: { system: <name>, event: <ExternalEvent> }
internal: { event: <InternalEvent>, tags: [ ... ], fields: { <field>: <type> } }
```

## Scenarios (only when they add information over the wiring)
`then` is **exactly one** of `event`, `events`, `exception`, or `view` (`view` only on a `state_view` scenario). A scenario is only worth emitting if it
says something the slice's `command → event` wiring does **not** already imply — i.e. it has at
least one of: a **given** precondition, **concrete example values**, or an **exception/branch**.
- A bare happy-path `when → then` with `given: []` and no values is a **tautology** — skip it.
  Never invent a `name`, `given: []`, or placeholder values to make an empty strip look real.
- If the board *draws* a scenario region but it carries no data/branch, don't fake one: add a
  slice-level `# todo: scenario placeholder drawn, author to complete` and emit no `scenarios:`.
```yaml
scenarios:
  - name: <what it proves — must reflect the actual precondition/branch, not "X does Y">
    given: [ { event: <EventName>, data: { ... } }, { view: <ViewName>, data: { ... } } ]
    when:  { command: <CommandName>, payload: { ... } }   # or trigger/query per pattern
    then:  { event: <EventName>, data: { ... } }
    # OR:  { exception: <ExceptionName>, message: "<...>", emits: none }
    # OR:  { view: <ViewName>, data: { ... } }   # state_view only (when: { query, key })
```

## Consistency rules (the validator enforces these — don't violate them)
- Every `tags` entry is one of that event/view's `fields`.
- Reuse the **exact same name** for an event/view every place it appears (a producer and its consumers share one name).
- Give a shared name **identical field/tag shapes** everywhere.
- `state_view` has no `command`; `automation`/`translation` have no `ui`.

Write the slice files now, then return the brief confirmation summary.
