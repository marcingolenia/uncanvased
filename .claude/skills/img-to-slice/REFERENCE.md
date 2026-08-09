# img-to-slice — per-pattern schema, scenarios, rules

Include only fields the image supports. Omit anything the board does not show.

## Per-pattern body

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
sources: [ <EventName>, ... ]         # internal events projected in (events only — never an external system)
view: { name: <ViewName>, tags: [ ... ], fields: { <field>: <type> } }
ui:  { screen: <name>, outputs: [ { name: <n>, type: <t> } ] }

# automation
trigger: { event: <EventName> }       # or { view: <ViewName> } | { timer: <desc> }
processor: <ProcessorName>
command: { name: <CommandName>, payload: { <field>: <type> } }

# translation — the ONLY way external data enters/leaves the model.
# Two variants; pick by what the board draws (see SKILL.md classification).

# --- translation, variant A: event-driven (boundary event-crossing) ---
# Board: the external system is its own swimlane labeled with the system name; the crossing arrow is the translation.
# Lane label → external.system; sticky in that lane → external.event; sticky in an internal lane → internal.event;
# arrow direction → direction (into your system = inbound, out = outbound). Freehand fallback: a boundary badge on the
# event sticky (`↔ Salesforce`, a cloud/box) → external.system, marked `# inferred`.
direction: inbound|outbound
external: { system: <name>, event: <ExternalEvent> }   # external side: keep the foreign system's language here
internal: { event: <InternalEvent>, tags: [ ... ], fields: { <field>: <type> } }

# --- translation, variant B: request-response (API fetch/translation) ---
# Board: a system agent/worker reads an internal view (To-Do list) or handles a trigger, makes an external API
# call, and records the response DIRECTLY as an internal domain event. There is NO external event sticky — the
# external system answers a call, it does not publish an event onto a bus. `sources` is the internal view/event
# driving the call (omit if none is drawn); `external_call` is the outbound request; `internal.event` is the fact recorded.
direction: outbound_request|inbound_pull   # you call out | you poll/fetch in
sources: [ <ViewName>, <EventName>, ... ]  # optional: internal source / To-Do list driving the call; omit if none drawn
external_call:
  system: <name>                           # external system being called
  action: "<HTTP verb + endpoint / RPC / API method>"   # e.g. "GET /organizations/{id}"
internal: { event: <InternalDomainEvent>, tags: [ ... ], fields: { <field>: <type> } }

# ANTI-CORRUPTION (both variants): name `internal.event` as a DOMAIN FACT in your ubiquitous language
# (`OrganizationDetailsRecorded`), NEVER after the external system or the transport
# (`OrganizationImported`, `SalesforceOrgSynced`). The Salesforce/import concern stays on the
# external side. In variant B the raw API payload translates STRAIGHT INTO `internal.event` — do NOT
# invent artificial transport events (`OrganizationQuerySent`, `OrganizationRecordReturned`) for the
# request/response round-trip. If origin matters to the domain (e.g. which source wins in a merge), record it
# as a FIELD/tag (`source`, `observedAt`) — provenance may be an attribute of a domain event, never its identity.
```

## Scenarios (only when they add information over the wiring)

`then` is **exactly one** of `event` or `exception`. A scenario is only worth emitting if it says something the slice's `command → event` wiring does **not** already imply — i.e. it has at least one of: a **given** precondition, **concrete example values**, or an **exception/branch**.

- A bare happy-path `when → then` with `given: []` and no values is a **tautology** — skip it. Never invent a `name`, `given: []`, or placeholder values to make an empty strip look real.
- If the board *draws* a scenario region but it carries no data/branch, don't fake one: add a slice-level `# todo: scenario placeholder drawn, author to complete` and emit no `scenarios:`.

```yaml
scenarios:
  - name: <what it proves — must reflect the actual precondition/branch, not "X does Y">
    given: [ { event: <EventName>, data: { ... } }, { view: <ViewName>, data: { ... } } ]
    when:  { command: <CommandName>, payload: { ... } }   # or trigger/query per pattern
    then:  { event: <EventName>, data: { ... } }
    # OR:  { exception: <ExceptionName>, message: "<...>", emits: none }
```

## Consistency rules (the validator enforces these — don't violate them)

- Every `tags` entry is one of that event/view's `fields`.
- A `state_view` projects **only internal events** — every `sources` entry is an event, never an external system, so every view field traces back to the timeline (information completeness). External data enters/leaves **only** via a `translation` slice (external event ↔ internal event); the read model then projects the resulting internal event like any other. There is no `external_view` pattern.
- Reuse the **exact same name** for an event/view every place it appears (a producer and its consumers share one name).
- Give a shared name **identical field/tag shapes** everywhere.
- `state_view` has no `command`; `automation`/`translation` have no `ui`.
- **Translation has two shapes, and the validator permits both:**
  - *Event-driven (variant A)* carries `external.event` + `internal.event` and a `direction` of `inbound`/`outbound`. It has **no** `sources` and **no** `external_call`.
  - *Request-response (variant B)* carries `external_call` (+ optional `sources`) + `internal.event` and a `direction` of `outbound_request`/`inbound_pull`. It has **no** `external.event`. Here `sources` and `external_call` on a `translation` slice are **valid**, not errors — they model the API-integration pattern (an internal To-Do view driving an outbound call). A `sources` entry, when present, is an internal view or event, same as `state_view` sources.
  - The two are mutually exclusive: a slice has *either* `external.event` (A) *or* `external_call` (B), never both.
- **Request-response translations translate raw external API payloads into domain-language internal events (`internal.event`). Do not invent artificial transport events like `QuerySent` or `RecordReturned` unless the external system literally publishes those exact events onto a message bus** (in which case it is a variant-A event-driven translation, not request-response).
- **Translation anti-corruption naming (both variants):** a `translation`'s `internal.event` is named in **domain language**, never after the external system or the transport (`OrganizationDetailsRecorded`, not `OrganizationImported`/`SalesforceOrgSynced`). Origin, when the domain cares (e.g. merge authority), is a `source`/`observedAt` **field or tag** — provenance may be an attribute of a domain event, never its identity. (Domain-language internal events are core Event Modeling; the provenance-as-attribute corollary is a consistent extension.)
