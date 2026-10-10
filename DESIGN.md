# Event Modeling: Uncanvased — Design & Kickoff

> A plain-text, version-controlled way to do Event Modeling that lives next to your code
> and drives autonomous AI development — no proprietary whiteboard required.

This is the single get-started document: the idea, the locked decisions, the full
specification with worked examples, and a build plan.

---

## 1. The idea

Event Modeling is normally done on a heavy visual canvas (Miro, Excalidraw, a wall of
sticky notes). **Uncanvased** replaces that canvas with a **plain-text Markdown/YAML
specification in Git**, sitting alongside the code it describes. From there:

- **Forward pass** — a photo/screenshot of *any* Event Model (paper, Miro, whiteboard) goes
  through a Vision LLM and becomes structured Uncanvased slices.
- **AI execution loop (bring-your-own)** — a coding agent (Ralph loop, Claude Code, Cursor)
  reads the slices, writes the business logic and Given-When-Then tests, and commits passing code.
- **Reverse pass** — the toolkit renders the slices back into an editable `.excalidraw`
  board so you can inspect the model visually.

The toolkit is **language-agnostic about the code it helps you write**, and itself
implemented in **F# / .NET**. It is intended for event-sourced systems, specifically ones
using **UmaDB + Dynamic Consistency Boundaries** (dcb.events) — though nothing in the spec
is coupled to a particular store.

### Bi-directional lifecycle

```
                         FORWARD PASS
   Visual diagram / photo ──(Vision LLM)──▶  Uncanvased slices  (source of truth in Git)
                                                     │
                                                     │  (bring-your-own AI loop)
                              REVERSE PASS           ▼
   Excalidraw board  ◀──(deterministic render;      Tested & working codebase
                          Vision only for foreign
                          images)
```

---

## 2. What the toolkit owns (and does not)

**Owns:** the spec standard, a deterministic validator, the forward pass (image→spec), and
the reverse renderer (spec→Excalidraw).

**Does not own:** the AI execution loop. It **never generates or checks tests**. The
bring-your-own loop writes both production code and tests.

---

## 3. Locked decisions

| # | Area | Decision |
|---|------|----------|
| 1 | Scope | This repo **is** the toolkit (spec + validator + forward prompts + reverse renderer). Language-agnostic. Loop is bring-your-own. |
| 2 | Parse contract | **YAML block is the authored source of truth**; prose is a generated view, never parsed. LLM drift handled by validator + repair, not by hoping the model obeys. |
| 3 | Scenarios | Given-When-Then are **fully-typed YAML**; authors read the prose-rendered version. |
| 4 | Tests | The loop writes tests **and** code. Toolkit does not emit or check tests. |
| 5 | Reverse board | Uniform "drop any image → spec", **but** generated boards embed ground-truth YAML → deterministic re-sync. **Vision is fallback only** for foreign images. |
| 6 | Data model | **Derived catalog** (lint scans slices). Hard-error on conflicting field shapes for a shared name; warn on single-occurrence names. Optional `model.yaml` escape hatch. |
| 7 | Patterns | **Discriminated union** on `pattern`: `state_change / state_view / automation / translation`, each with own required/forbidden fields. |
| 8 | Ordering | **Causal topological sort** over the catalog; `sequence:` only breaks ties; cycles are an error; filenames don't determine order. |
| 9 | File on disk | **One `.md` per slice**: YAML block on top, generated prose below. Validator fails on prose drift. |
| 10 | Validator | **Pure & deterministic** (no LLM/network); precise line-level errors. Repair is the calling agent's job. |
| 11 | Language | **F# / .NET**, shipped as a `dotnet tool` (NuGet). DUs are the natural encoding of the pattern schema. |
| 12 | LLM provider | **Pluggable** `ILlmProvider`, **Claude default**, swappable. Deterministic parts need no API key. |
| 13 | DCB / UmaDB | Persistence-agnostic; **tags are first-class on events** (catalog + validator). Consistency boundary stays **prose** for now (loop infers the append-condition). |

---

## 4. Repository layout

```
event_modelling_uncanvased/
├── src/
│   ├── Uncanvased.Core/        # slice DU, YAML load/save, derived catalog
│   ├── Uncanvased.Validate/    # deterministic validator + prose-drift check
│   ├── Uncanvased.Render/      # deterministic Excalidraw skeleton + wireframe cache
│   ├── Uncanvased.Llm/         # ILlmProvider + Claude adapter (vision, wireframes)
│   └── Uncanvased.Cli/         # `uncanvased` dotnet tool entrypoint
├── prompts/                    # forward-pass + wireframe prompt templates
├── examples/todo/              # reference specs (slices below)
│   ├── slice_01_register_user.md
│   ├── slice_02_add_todo_item.md
│   ├── ...
│   └── model.yaml              # optional catalog override (usually absent)
├── DESIGN.md                   # this file
└── README.md
```

---

## 5. Specification (Uncanvased v1.0)

### 5.1 Slice file anatomy

Each slice is one committed `.md` file. The **fenced `yaml uncanvased` block is authored and
is the only thing tooling parses**. Everything below the `<!-- generated -->` marker is
produced by the renderer and checked for drift by the validator.

````markdown
```yaml uncanvased
slice: Add ToDo Item
pattern: state_change
actor: Registered User
# ... pattern-specific body ...
```

<!-- generated: do not edit below; run `uncanvased render` -->
# Slice 02: Add ToDo Item
...prose rendered from the YAML above...
````

### 5.2 Common fields (every pattern)

```yaml
slice: <human title>                  # required
pattern: state_change|state_view|automation|translation   # required, selects the schema
actor: <role | system agent | external service>           # required
sequence: <int>                       # optional; only breaks ties between independent slices
```

### 5.3 Events, tags, and the derived catalog

Domain events are declared where they are **produced**. Each event names its **tag keys**
(DCB identifiers), which must correspond to fields that supply the tag values.

```yaml
event:
  name: ToDoItemAdded
  tags: [user, item]        # DCB tag keys
  fields:
    itemId: string          # supplies tag `item`
    userId: string          # supplies tag `user`
    title: string
    status: enum[ACTIVE, COMPLETED]
```

There is **no hand-written catalog**. `uncanvased validate` scans all slices and derives one:

- **Hard error** — the same event/view name declared with **conflicting field or tag shapes**.
- **Warning** — a name that appears **exactly once** (typo smell, e.g. `ToDoItemAdd`).
- Optional `model.yaml` may declare canonical names to silence warnings / harden unknowns.

### 5.4 The four patterns

**`state_change`** — `UI → Command → Event(s)`. The write side.

```yaml
pattern: state_change
ui:
  screen: TodoListScreen
  inputs:
    - { field: title, type: string, constraints: [required, "1-100 chars"] }
  trigger: { label: "[+ Add Item]", command: AddToDoItem }
  outputs:
    - { name: "List Item Title", type: string }
    - { name: "Status Badge", type: "enum[ACTIVE, COMPLETED]" }
    - { name: "Item Counter", type: string }        # "Active Items: X / 3"
command:
  name: AddToDoItem
  payload:
    userId: string
    title: string
event:
  name: ToDoItemAdded
  tags: [user, item]
  fields: { itemId: string, userId: string, title: string, status: enum[ACTIVE, COMPLETED] }
constraints:
  - "A user cannot have more than 3 active items."      # DCB boundary (prose)
  - "Title must not be empty or blank."
scenarios: [ ... ]   # see 5.5
```

**`state_view`** — `Event(s) → View → UI`. The read side. **No command.** Requires `sources`.

A `state_view` projects **only internal events** — every field on the screen must trace back to an event on the timeline (**information completeness**, the property the whole method exists to guarantee). Data from an external system therefore never appears as a `sources` entry; it enters via a **`translation`** slice (below) that records it as an internal event, which the read model then projects like any other. No `external_view` pattern is introduced — external reads must not drift from canonical Event Modeling.

```yaml
pattern: state_view
sources: [ToDoItemAdded, ToDoItemCompleted, ToDoItemRemoved]   # internal events projected in (events only)
view:
  name: UserItemCountView
  tags: [user]
  fields: { userId: string, activeCount: int }
ui:
  screen: TodoListScreen
  outputs:
    - { name: "Item Counter", type: string }
scenarios: [ ... ]
```

**`automation`** — `Read Model (to-do list) → ⚙️ processor → Command → Event`. **Forbids `ui`.** No human actor. The processor reads a to-do read model (owned by its own `state_view` slice) rather than reacting to an event directly ("don't trigger commands from events"). A 3rd-party API call the processor makes is recorded as `external_call`; the call result still enters the model only through the command → event.

```yaml
pattern: automation
trigger: { view: DueItemsView }        # view (preferred) | timer; event only if drawn so (warn)
processor: SendReminderGear
external_call: { system: EmailProvider, action: "POST /send" }   # optional
command:
  name: SendReminder
  payload: { userId: string, itemId: string }
event:
  name: ReminderSent
  tags: [user, item]
  fields: { userId: string, itemId: string }
scenarios: [ ... ]
```

**`translation`** — `External Event → Read Model → ⚙️ processor → Command → internal Event`. The canonical anti-corruption boundary: an automation whose chain starts from an external event instead of an internal read model. **Forbids `ui`.** Requires `command` and `event` — like everywhere else, state changes only through a command. The translation's read model is the **only** read model allowed to consume an external event.

**Board notation.** The external event is a **pink/red** sticky, labeled `(External)`, or placed in a swimlane labeled with the foreign system's name. The forward pass maps: lane label / badge → `external.system`, the external sticky → `external.event`, the green box it feeds → `view`, the ⚙️ → `processor`, then `command` and the internal `event`. The internal command/event are named in domain language; the foreign name stays on `external.event`.

```yaml
pattern: translation
external:
  system: EmailProvider
  event: EmailBounced
view:
  name: BouncedEmailsToProcess
  tags: [user]
  fields: { userId: string, reason: string }
processor: BounceHandler
command:
  name: InvalidateUserEmail
  payload: { userId: string, reason: string }
event:
  name: UserEmailInvalidated
  tags: [user]
  fields: { userId: string, reason: string }
scenarios: [ ... ]
```

### 5.5 Scenarios (typed Given-When-Then)

Scenarios are typed YAML. `then` is **either** an emitted event **or** an exception.

```yaml
scenarios:
  - name: Successfully add item when under limit
    given:
      - event: UserRegistered
        data: { userId: usr_123 }
      - view: UserItemCountView
        data: { userId: usr_123, activeCount: 2 }
    when:
      command: AddToDoItem
      payload: { userId: usr_123, title: "Buy groceries" }
    then:
      event: ToDoItemAdded
      data: { itemId: item_999, userId: usr_123, title: "Buy groceries", status: ACTIVE }

  - name: Reject item when limit of 3 is reached
    given:
      - view: UserItemCountView
        data: { userId: usr_123, activeCount: 3 }
    when:
      command: AddToDoItem
      payload: { userId: usr_123, title: "Clean garage" }
    then:
      exception: MaxItemsExceededException
      message: "Cannot add item. Maximum limit of 3 items reached."
      emits: none
```

### 5.6 Ordering & wiring

- Timeline position = **topological sort** over catalog edges (an event's producer precedes
  its consumers). `sequence:` breaks ties among causally-independent slices.
- Cross-slice **arrows are inferred** from shared catalog nodes — not declared separately.
- A **dependency cycle is a validator error**.

---

## 6. Worked example — a Todo app

### `examples/todo/slice_02_add_todo_item.md`

````markdown
```yaml uncanvased
slice: Add ToDo Item
pattern: state_change
actor: Registered User
sequence: 20

ui:
  screen: TodoListScreen
  inputs:
    - { field: title, type: string, constraints: [required, "1-100 chars"] }
  trigger: { label: "[+ Add Item]", command: AddToDoItem }
  outputs:
    - { name: "List Item Title", type: string }
    - { name: "Status Badge", type: "enum[ACTIVE, COMPLETED]" }
    - { name: "Item Counter", type: string }

command:
  name: AddToDoItem
  payload: { userId: string, title: string }

event:
  name: ToDoItemAdded
  tags: [user, item]
  fields: { itemId: string, userId: string, title: string, status: enum[ACTIVE, COMPLETED] }

constraints:
  - "A user cannot have more than 3 active items on their ToDo list."
  - "Item title must not be empty or blank spaces."

scenarios:
  - name: Successfully add item when under limit
    given:
      - event: UserRegistered
        data: { userId: usr_123 }
      - view: UserItemCountView
        data: { userId: usr_123, activeCount: 2 }
    when:
      command: AddToDoItem
      payload: { userId: usr_123, title: "Buy groceries" }
    then:
      event: ToDoItemAdded
      data: { itemId: item_999, userId: usr_123, title: "Buy groceries", status: ACTIVE }

  - name: Reject item when limit of 3 is reached
    given:
      - view: UserItemCountView
        data: { userId: usr_123, activeCount: 3 }
    when:
      command: AddToDoItem
      payload: { userId: usr_123, title: "Clean garage" }
    then:
      exception: MaxItemsExceededException
      message: "Cannot add item. Maximum limit of 3 items reached."
      emits: none
```

<!-- generated: do not edit below; run `uncanvased render` -->
# Slice 02: Add ToDo Item

**Pattern:** State Change · **Actor:** Registered User

## Screen — `TodoListScreen`
- Input `title`: string (required, 1-100 chars)
- Action: **[+ Add Item]** ➔ `AddToDoItem`
- Outputs: List Item Title, Status Badge (ACTIVE|COMPLETED), Item Counter

## Business Constraints
- A user cannot have more than 3 active items on their ToDo list.
- Item title must not be empty or blank spaces.

## Scenarios
### 1. Successfully add item when under limit
- **GIVEN** `UserRegistered` { userId: usr_123 }; `UserItemCountView` { activeCount: 2 }
- **WHEN** `AddToDoItem` { title: "Buy groceries" }
- **THEN** `ToDoItemAdded` { itemId: item_999, status: ACTIVE }

### 2. Reject item when limit of 3 is reached
- **GIVEN** `UserItemCountView` { activeCount: 3 }
- **WHEN** `AddToDoItem` { title: "Clean garage" }
- **THEN** ✗ `MaxItemsExceededException` — "Cannot add item. Maximum limit of 3 items reached." (no events)
````

### Companion slices (YAML bodies only)

`slice_03_item_count_view.md` — **state_view**:

```yaml uncanvased
slice: User Item Count
pattern: state_view
actor: System Agent
sources: [ToDoItemAdded, ToDoItemCompleted, ToDoItemRemoved]
view:
  name: UserItemCountView
  tags: [user]
  fields: { userId: string, activeCount: int }
ui:
  screen: TodoListScreen
  outputs:
    - { name: "Item Counter", type: string }
scenarios:
  - name: Count reflects added minus completed
    given:
      - event: ToDoItemAdded     { data: { userId: usr_123, itemId: item_1 } }
      - event: ToDoItemAdded     { data: { userId: usr_123, itemId: item_2 } }
      - event: ToDoItemCompleted { data: { userId: usr_123, itemId: item_1 } }
    when:
      query: UserItemCountView
      key: { userId: usr_123 }
    then:
      view: UserItemCountView
      data: { userId: usr_123, activeCount: 1 }
```

`slice_04_send_reminder.md` — **automation**:

```yaml uncanvased
slice: Send Due Reminder
pattern: automation
actor: System Agent
trigger: { view: DueItemsView }
processor: SendReminderGear
command:
  name: SendReminder
  payload: { userId: string, itemId: string }
event:
  name: ReminderSent
  tags: [user, item]
  fields: { userId: string, itemId: string }
scenarios:
  - name: Due item triggers a reminder
    given:
      - view: DueItemsView
        data: { userId: usr_123, itemId: item_2 }
    when:
      command: SendReminder
      payload: { userId: usr_123, itemId: item_2 }
    then:
      event: ReminderSent
      data: { userId: usr_123, itemId: item_2 }
```

---

## 7. F# schema sketch (starting point)

```fsharp
type FieldShape = Map<string, string>          // fieldName -> type expr

type EventDef =
    { Name: string; Tags: string list; Fields: FieldShape }

type Scenario =
    { Name: string
      Given: GivenItem list
      When:  Trigger
      Then:  Outcome }                          // Emitted of EventData | Rejected of Exn

type Slice =
    | StateChange of StateChangeSlice
    | StateView   of StateViewSlice
    | Automation  of AutomationSlice
    | Translation of TranslationSlice
// The DU makes "Automation forbids ui" and "StateView requires sources"
// unrepresentable-when-wrong: each case only carries its legal fields.
```

---

## 8. Validator rules (deterministic, no LLM)

1. YAML parses into the correct pattern case; required fields present, forbidden fields absent.
2. Every referenced event/view/screen resolves in the derived catalog.
3. No conflicting field/tag shapes for a shared name (**error**); single-occurrence names (**warn**).
4. Each event's `tags` are a subset of its `fields`.
5. Scenario `then` is exactly one of `event`, `events` or `exception`.
6. No dependency cycles in the causal graph.
7. Committed prose matches freshly-rendered prose (**drift error**).
8. **TODO** — a `state_view` `sources` entry must resolve to an **internal event** in the catalog, never an external one (**error**, "external data must cross via a `translation` slice"). External events appear only as a translation's `external.event`. Enforces information completeness.
9. **TODO** — `automation` and `translation` require both `command` and `event` (no event without a command).

---

## 9. Reverse renderer notes

- **Deterministic skeleton:** swimlanes (UI / command / event / view), left-to-right
  timeline via toposort, Event Modeling colors (blue command, orange event, green view),
  inferred wiring arrows.
- **Wireframe contents:** LLM-generated Excalidraw JSON per screen, **cached by a hash of
  the UI contract** → unchanged screen = zero calls, fully offline.
- **Ground-truth embed:** the canonical YAML is stamped into the `.excalidraw` so re-sync of
  your own board is deterministic; Vision is used only for foreign images.
- **TODO — external-system swimlane primitive:** one lane per distinct `external.system`, labeled
  with the system name, holding the `external.event` as a pink sticky. From there the translation
  renders like an automation: external event → view → ⚙️ → command → internal event.

---

## 10. Build plan

**Milestone A — deterministic core (no LLM, this is the trustworthy foundation)**
1. Model `Slice` as an F# DU with typed scenarios; the compiler enforces per-pattern shape.
2. YAML load/save (YamlDotNet) ↔ the DU; extract the `yaml uncanvased` block from a `.md`.
3. Derived catalog: scan slices, detect shape conflicts (error) and single-occurrence names (warn).
4. `uncanvased validate`: schema + referential integrity + tag-subset + cycle detection, precise line-level errors.
5. Prose generator + drift check wired into `validate`.

**Milestone B — reverse render (deterministic first)**
6. Toposort + swimlane/timeline layout → `.excalidraw` JSON (System.Text.Json), colors, arrows.
7. Embed ground-truth YAML into the board.
8. Wireframe layer via `ILlmProvider`, cached by UI-contract hash.
9. Ingest: deterministic diff when embedded YAML present; else Vision fallback.

**Milestone C — forward pass & packaging**
10. `ILlmProvider` + Claude adapter; forward-pass prompt (image → YAML) → straight into the validator, errors fed back for repair.
11. `uncanvased` CLI (`validate`, `render`, `forward`, `ingest`) as a `dotnet tool`; publish to NuGet.
12. Port this Todo example into `examples/todo/`; rewrite `README.md` from this design.

**Suggested first week:** Milestone A end-to-end on the Todo example. Once `validate` is
green and prose renders, you have a usable spec + safety net — everything after that is additive.

---

## 11. Open items (refinements, not blockers)

- Exact field-type grammar (`enum[...]`, nullable, nested objects) — extend as examples demand.
- Whether to promote the DCB **consistency boundary** from prose to a structured `boundary`
  block (query + append-condition). Deferred; additive if loop-inference proves flaky.
- Slice **granularity guidance** for authors ("how big is a slice?") — docs, not tooling.

---

# Part II — V2: Parallel Execution & Control Plane

V1 gives you the spec, validator, and renderer, and leaves the AI loop bring-your-own. **V2
adds an orchestration layer** that runs many bring-your-own loops **in parallel, safely, and
observably** — one isolated worktree + container per slice, with a live web dashboard. It
does **not** change any v1 decision: the container still runs *your* agent against *your*
spec; V2 only wraps execution in isolation and gives it a control plane.

## 12. The idea

Autonomous coding agents run arbitrary CLI (`rm -rf`, package installs, shell scripts) and
need a real runtime with a database to verify Given-When-Then scenarios. Running several of
them on your host at once invites blast-radius accidents, port collisions, polluted global
deps, and merge chaos. V2 isolates each slice's build into its own **Git worktree** mounted
into its own **Docker container**, orchestrated by a single-binary **Uncanvased UI server**.

```
                          UNCANVASED UI SERVER
                          (http://localhost:4000)
                                    │
                 ┌──────────────────┴──────────────────┐
                 ▼                                     ▼
      Git Worktree: Slice 01                Git Worktree: Slice 02
      (mounts code volume)                  (mounts code volume)
                 │                                     │
                 ▼                                     ▼
      Docker Container #1                   Docker Container #2
      ┌───────────────────────┐            ┌───────────────────────┐
      │ Isolated runtime      │            │ Isolated runtime      │
      │ Independent DB/ports  │            │ Independent DB/ports  │
      │ Safe command exec     │            │ Safe command exec     │
      └───────────────────────┘            └───────────────────────┘
```

## 13. Why (the four guarantees)

- **Blast-radius control** — a container guarantees the agent can't touch host files or
  poison global dependencies. Worst case, you throw the container away.
- **Deterministic test environments** — every slice runs against a clean, pinned base image
  (.NET, Node, Go, Python) with its own isolated database container (PostgreSQL,
  EventStoreDB, or **UmaDB**) via `docker-compose`.
- **Zero port collisions** — ports map at the container level, so two parallel loops can both
  bind internal `8080`; Docker maps them to different host ports (`8081`, `8082`).
- **Clean worktree mounting** — mount the worktree into the container
  (`-v ./worktrees/slice-01:/workspace`). The agent edits files inside the container; Git in
  the worktree tracks those changes natively on the host filesystem, ready to review.

## 14. Execution flow

1. **Spec created** — user drops `slice_01.md` into `specs/` (validated by the v1 core first).
2. **Worktree spun up** — server creates branch `feat/slice-01` at `.uncanvased/worktrees/slice-01`.
3. **Container spawns** — server runs a container mounting that specific worktree:

   ```bash
   docker run --rm \
     -v $(pwd)/.uncanvased/worktrees/slice-01:/workspace \
     -w /workspace \
     -e SLICE_SPEC_PATH=specs/slice_01.md \
     uncanvased/agent-runner:latest
   ```

4. **Loop runs** — the agent inside the container writes code, runs tests, and verifies the
   slice's Given-When-Then scenarios.
5. **UI stream** — WebSockets stream the container's stdout/stderr straight to the dashboard.
6. **Completion & cleanup** — tests pass ➔ container stops ➔ user reviews the Git diff in the
   UI ➔ merges to `main` ➔ worktree is removed.

## 15. Full Uncanvased stack (v1 core + v2 orchestration)

| Layer | Technology / implementation | Role |
|-------|------------------------------|------|
| Spec & core validation | F# / .NET CLI (`dotnet tool install -g uncanvased`) | Strict DU pattern enforcement, topological DAG sort, YAML validation |
| Reverse renderer | F# / .NET renderer + LLM wireframe cache | Converts specs to visual `.excalidraw` boards (deterministic skeleton, cached wireframes) |
| Control-plane UI | Single-binary web server (WebSockets) | Live slice list, progress visualization, agent log streaming |
| Workspace isolation | Git worktrees | Prevents merge conflicts and context pollution during parallel slice builds |
| Execution sandbox | Docker containers | Safe, isolated environment for the bring-your-own loop to build and test |

## 16. Relationship to v1 & new open questions

- **No v1 decision changes.** The container's `agent-runner` still hosts *your* loop; the
  `uncanvased` CLI runs inside it for `validate`/`render`. The dashboard is additive.
- **Runner image is BYO-friendly.** `uncanvased/agent-runner` should be a thin base
  (CLI + git) that a project extends with its language toolchain and its chosen agent.
- **Open — agent & keys:** how the loop and its `ILlmProvider` key are injected into the
  container (env vs. mounted secret), and how to avoid leaking keys into logs streamed over WS.
- **Open — DCB test DB:** ship a reference `docker-compose` with UmaDB (or EventStoreDB) so
  slice tests run against a real DCB store; decide per-slice vs. shared-ephemeral DB.
- **Open — concurrency & merge:** max parallel containers, and merge policy when two slices
  touch the same files (queue, rebase, or human-serialize at review).
- **Open — server language:** the single-binary web server can also be .NET (reuse the core)
  or a separate stack; default to .NET to keep one toolchain.
```
