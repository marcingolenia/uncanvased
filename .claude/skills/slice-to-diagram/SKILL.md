---
name: slice-to-diagram
description: Render Uncanvased slice YAML files into a canonical Event Modeling diagram as an Excalidraw board (.excalidraw), with UI wireframe mockups (text fields, buttons, lists) and a cog+actor node for automated processes. Use when the user has slice YAML (in slices/ or named files) and wants a diagram, board, or picture back — the reverse/backward pass — or mentions Excalidraw, visualizing an event model, or turning slices into a diagram.
---

# Uncanvased slices → Event Model diagram (Excalidraw)

This is the **backward pass**: authored slice YAML → one canonical Event Modeling
board as an `.excalidraw` file. Layout is produced by a bundled deterministic
generator — **you run the script, you do not hand-author Excalidraw JSON.**

## Quick start

```bash
python3 .claude/skills/slice-to-diagram/scripts/generate_diagram.py slices/ -o board.excalidraw
```

`paths` may be a **directory** (scanned for `*.yaml`) and/or **individual slice
files**; all selected slices land on ONE combined left-to-right timeline.

```bash
# a hand-picked subset, combined into one board
python3 .../generate_diagram.py slices/request-organization-details.yaml slices/fetch-organization-details-from-salesforce.yaml -o merge-flow.excalidraw
```

## Workflow

1. Decide the selection: the whole `slices/` folder, or the specific files the
   user named. Pass exactly those to the script.
2. Run the generator. It prints the output path and the resolved slice order.
3. **Report the output path and the slice order** it printed. Tell the user the
   file opens at excalidraw.com or via the Excalidraw VS Code extension. Do
   **not** echo the JSON back.
4. If the script warns (unknown pattern, off-board reference rendered as a dashed
   "ghost" box, read model sitting right of its reader), surface that verbatim —
   don't silently drop it.

## What the board looks like (canonical Event Modeling)

Horizontal swimlanes, slices ordered left-to-right along the event timeline:

| Lane | Holds | Color |
|------|-------|-------|
| **One per actor** (`Fleet Manager`, `Customer`, `System Agent`, …) | only UI mockups (screen title, text fields, buttons, output lists) and the **⚙️ cog + processor** of an `automation` / `translation` | white / purple |
| **Commands / Read models** | commands (write) and views (read) | blue / green |
| **Events** | the event timeline spine | orange |
| **One per external system** (`Stripe`, `Salesforce`, …) | an `automation`'s `external_call`; a `translation`'s external event | red |

Actor lanes come from `actor:` in order of first appearance; a `(processor)`
qualifier is dropped, so all `System Agent (...)` processors share one lane.

**Rules of the board**
- **Arrows never point left.** A slice that reads an event produced further
  right gets its own copy of that event in its own columns, drawn hatched and
  dashed and labelled `(duplicate)`.
- **Events are the only shared contract.** Commands and read models are drawn
  once, in their own slice, and never duplicated. A read model drawn right of
  its reader is a sequencing error: the script warns and draws no arrow.
- **Every element carries its slice `id`** as a small gray badge in the
  top-right corner (UI, ⚙️, command, read model, event, external call). A merged
  screen shows both ids (`12·13`); a duplicated event shows its producer's id.
  The badge is how `img-to-slice` matches an edited board back to its slice
  files. Slices without `id:` get no badge.
- **A screen is one storyboard frame.** A `state_view` whose `ui.screen` equals
  the next `state_change`'s is drawn as ONE wireframe (read-model outputs +
  inputs + button) in the `state_change`'s column: view → screen → command.
  The same screen reappears only at a later moment in time.

Slices are written by the `img-to-slice` skill; its `REFERENCE.md` defines the YAML. A
`translation` takes two columns (view, then processor chain); a `state_change` with
several `events` takes one column per event; a slice with duplicated events gets
one extra column per duplicate (a `state_view` shares the first with its view).

Ordering: explicit `sequence:` first, then event-dependency (a producer sits left
of its consumers), then filename. The To-Do-list cycle (a view feeding an
automation that records an event feeding the same view) is broken deterministically.

## Per-pattern mapping, palette, geometry & customization

See **[REFERENCE.md](REFERENCE.md)** — how each `pattern` maps to boxes and
arrows, the exact colors/coordinates, cross-slice reference handling, and where
to edit the script to change the layout.
