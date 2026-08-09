---
name: img-to-slice
description: Convert a photo or screenshot of an Event Model board into Uncanvased YAML slice files, one file per vertical slice. Use when the user supplies an image (Miro, Excalidraw, whiteboard, paper) of an event model and wants slices, or mentions forward-pass, transcribing an event model image, or generating slice YAML from a picture.
---

# Event Model image → Uncanvased slices

You convert a photo/screenshot of an **Event Model** into **Uncanvased slices**. The authored YAML is the source of truth; prose is generated later, so **you author only YAML**.

## Workflow

1. Read the image. **Transcribe only what it shows** — do not invent fields, constraints, or scenarios.
2. Classify each vertical slice by `pattern` (see below).
3. Write **one slice file per slice** into `slices/` (create the dir if absent).
4. Reply with **only a brief confirmation**: the files written (path + slice title), one per line. Do **not** echo YAML back.

## Output contract

- Each file's entire content is **raw YAML** — nothing else. No fenced code block, no ` ```yaml ` wrapper, no prose. The renderer parses the file as YAML and generates prose separately later.
- **Filename** = kebab-case slug of the slice title with a **`.yaml`** extension: lowercase, spaces → `-`, drop punctuation (`Add List` → `slices/add-list.yaml`). Filenames do **not** encode order — never number them. On title collision append `-2`, `-3`, ….
- **Do not overwrite** an existing slice file whose YAML differs without flagging it — note it in your final summary rather than clobbering authored work.
- Unreadable type → `string`. Illegible value → keep the label and add ` # ?` on that line.
- Preserve any **badge, `*`, star, or annotation** on a box as a trailing `# note: <text>` on that node — never silently drop it.

## Classify by `pattern` (visual cues; colors are hints, not proof)

- **state_change** — UI/screen → **command** (blue) → **event(s)** (orange). The write side.
- **state_view** — **event(s)** (orange) → **view / read model** (green) → UI. No command. Needs `sources`. A read model projects **only internal events** — every view field must trace to an event on the timeline. If the data comes from an external system, that is a **`translation`** slice, not a source here (see REFERENCE.md).
- **automation** — no UI/human. Trigger (event | view | timer) → processor → **command**.
- **translation** — external-system boundary. No UI, no command. A translation takes **one of two forms**; pick by what the board draws:
  - **Event-driven (boundary event-crossing):** the external system is drawn as its **own swimlane labeled with the system name** (e.g. `Salesforce`) and an event sticky *crosses the boundary arrow*. **Lane label → `external.system`**, the sticky in that lane → `external.event`, the sticky landing in an internal lane → `internal.event`, and the **arrow direction across the boundary → `direction`** (into your system = `inbound`, out = `outbound`). On freehand/paper boards with no lanes, read a **boundary badge** on the event sticky (`↔ Salesforce`, a cloud/box edge) as the system and mark it `# inferred`.
  - **Request-response (API fetch/translation):** a **system agent/worker reads an internal view (a To-Do list) or handles a trigger, makes an external API call, and records the response directly as an internal domain event** — the classic Event Modeling automation-into-integration loop (e.g. a To-Do view drives a Salesforce REST query that yields `OrganizationDetailsRecorded`). There is **no external event sticky** because the external system does not publish an event onto a bus; it just answers a call. Model the internal source view (if drawn) → `sources`, the outbound call → `external_call` (`system` + `action`, e.g. the endpoint/verb/RPC), and the recorded fact → `internal.event`. Direction is `outbound_request` (you call out) or `inbound_pull` (you poll/fetch in). See REFERENCE.md for the request-response schema variant.
  - **Both forms** name the `internal.event` in **domain language** (`OrganizationDetailsRecorded`), never after the external system/transport (`OrganizationImported`) — that's the anti-corruption whole point. **Do not invent artificial transport events** (`OrganizationQuerySent`, `OrganizationRecordReturned`) to stand in for a request/response round-trip; the raw API payload translates *straight into* the internal domain event. Keep origin as a `source` field if the domain needs it (see REFERENCE.md).

## Common fields (every slice)

```yaml
slice: <human title>          # required
pattern: state_change|state_view|automation|translation   # required
actor: <role | System Agent | external service>            # required
sequence: <int>               # optional; only if the board shows an explicit order number
```

Actors are rarely drawn. If no swimlane/actor label is present, **infer a default and mark it `# inferred`** (reserve `# ?` for present-but-illegible labels):

- `state_change` with a UI → the screen's human user (e.g. `User  # inferred`).
- `state_view` / `automation` → `System Agent  # inferred`.
- `translation` → the external system on the boundary (e.g. `EmailProvider  # inferred`).

**Gear/cog/robot icon in the top swimlane** (⚙️, 🤖, a cog symbol) *in place of* a wireframe/screen is a positive signal that the slice is an **automated process, not a human-driven UI**. Treat it as such: infer `actor: System Agent` (or the **specific service name if one is labeled near the gears**, e.g. `BillingWorker`), and do **not** default the actor to a human user even for a `state_change`. This is an explicit cue, so mark it `# inferred` only when you inferred the *name*; a clearly labeled service name is not inferred. Such a slice is typically `automation` or a request-response `translation` rather than a UI `state_change`.

## Per-pattern body, scenarios & rules

For the per-pattern YAML templates, the scenario grammar (when to emit vs skip), and the consistency rules the validator enforces, see **[REFERENCE.md](REFERENCE.md)**. Consult it before writing any slice body.

Write the slice files now, then return the brief confirmation summary.
