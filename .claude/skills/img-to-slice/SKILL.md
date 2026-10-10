---
name: img-to-slice
description: Convert a photo or screenshot of an Event Model board into Uncanvased YAML slice files, one file per vertical slice. Use when the user supplies an image (Miro, Excalidraw, whiteboard, paper) of an event model and wants slices, or mentions forward-pass, transcribing an event model image, or generating slice YAML from a picture, or re-parses an updated board. After transcribing, runs a question-by-question gap review wizard (missing projections, untraceable fields, missing slices, rule violations) to complete the model.
---

# Event Model image → Uncanvased slices

You convert a photo/screenshot of an **Event Model** into **Uncanvased slices**. The authored YAML is the source of truth; prose is generated later, so **you author only YAML**.

## Workflow

1. If `slices/` is not empty, first ask whether the image is the whole board or a fragment ([UPDATE.md](UPDATE.md) §0). Read the image. **Transcribe only what it shows** — do not invent fields, constraints, or scenarios.
2. Read the swimlanes (see below), then cut the timeline into vertical slices and classify each by `pattern`.
3. Attach Given-When-Then sub-diagrams and white sticky notes to their slices.
4. Write **one slice file per slice** into `slices/` (create the dir if absent). If a slice already exists there, reconcile it first, following **[UPDATE.md](UPDATE.md)**: the user picks update, replace or keep, and any knock-on changes to other existing slices are asked about once.
5. **Gap review:** check the slices from this board for gaps (e.g. `CarBooked` never updates `AvailableCars`), then walk the user through them one question at a time and apply each accepted fix. Follow **[GAPS.md](GAPS.md)**.
6. Reply with **only a brief summary**: the files written or changed (path + slice title), one per line; slices kept unchanged at the user's request; the gap tally (fixed / deferred / ignored); deferred section A gaps; and events not yet read by any view. Do **not** echo YAML back.

## Output contract

- Each file's entire content is **raw YAML** — nothing else. No fenced code block, no ` ```yaml ` wrapper, no prose.
- **Filename** = kebab-case slug of the slice title with a **`.yaml`** extension: lowercase, spaces → `-`, drop punctuation (`Add List` → `slices/add-list.yaml`). Never number filenames. The same title means the same slice (see **[UPDATE.md](UPDATE.md)**). Append `-2`, `-3`, … only when two *different* slices in this run share a title.
- **Never overwrite silently.** An existing slice file whose YAML differs is changed only through the update questions in UPDATE.md or an accepted gap-review fix.
- **Names:** event / command / view names are the sticky text in PascalCase, spaces and punctuation dropped (`Order Placed` → `OrderPlaced`, `OrdersAwaiting Packing` → `OrdersAwaitingPacking`). The same sticky text always yields the same name. Keep spelling as drawn; mark a likely typo with `# ?`.
- Unreadable type → `string`. Illegible value → keep the label and add ` # ?` on that line.
- Preserve any **badge, `*`, star, or annotation** on a box as a trailing `# note: <text>` on that node.

## Reading the board

**Building blocks (colors are hints, not proof):**

| Block | Looks like |
|---|---|
| Event | yellow/orange sticky, past tense |
| External event | **pink** sticky, or labeled `(External)`, or in an external-system lane |
| Command | blue sticky, imperative |
| Read model (view) | green sticky |
| Processor | ⚙️ cog / gear / robot icon — automated process, no human |
| UI | wireframe / mockup (fields, buttons, tables) |
| Note | white sticky — a rule, constraint or comment |
| Hotspot | **red** sticky — an open question. **Ignore it**: do not transcribe it and do not treat it as an external event |

**Swimlanes:** a lane label next to UI wireframes is the **actor** for slices whose UI sits in it (`Customer`, `Warehouse worker`). A label on an event lane is a bounded context → `context:`. A lane labeled with a foreign system name holds **external** events → `external.system`.

## Classify by `pattern`

Every arrow chain on the board is one of four shapes. The canonical chain for each:

- **state_change** — UI → **Command** → **Event**. The only way state changes.
- **state_view** — **Event(s)** → **Read Model** (→ UI, optional). No command. Every read model box on the board, including the to-do lists that feed a ⚙️, gets its own `state_view` slice.
- **automation** — internal **Read Model** (to-do list) → ⚙️ → **Command** → **Event**. No human in the loop.
- **translation** — **External Event** → **Read Model** → ⚙️ → **Command** → **internal Event**. Same as automation, but the chain starts from an external event. The read model is owned by the translation slice (it is the only place an external event may be projected).

So both ⚙️ patterns end in a command that produces an event; the difference is only whether the chain starts from an internal read model (automation) or an external event (translation). A 3rd-party API call made by the processor (e.g. "GET Salesforce Account") is an **automation** with `external_call`, not a translation — there is no external event on the board.

**Actor:** use the lane label when drawn. Otherwise infer and mark `# inferred`: `state_change` → the screen's human user (`User  # inferred`); `state_view` / `automation` / `translation` → `System Agent  # inferred`, or the service name written next to the ⚙️ (not inferred if labeled).

## Flag, don't fix

During transcription (steps 1–4), transcribe what is drawn even when it breaks a modeling rule — fixes happen only in the gap review, with the user's consent — but add a slice-level `# warn: <rule>` comment so the author sees it:

- An event arrow goes **straight into a command** (no read model + ⚙️ in between) — "don't trigger commands from events".
- An event arrow goes **straight into another event** — "no event after event".
- A command produces **more than one event** — allowed, but usually a smell.
- A ⚙️ chain is missing its read model or its resulting event.

## Per-pattern body, scenarios & rules

For the per-pattern YAML templates, how to read Given-When-Then sub-diagrams and white notes, and the consistency rules the validator enforces, see **[REFERENCE.md](REFERENCE.md)**. Consult it before writing any slice body.
