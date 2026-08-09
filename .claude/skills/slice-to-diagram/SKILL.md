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
   "ghost" box), surface that verbatim — don't silently drop it.

## What the board looks like (canonical Event Modeling)

Four horizontal lanes, slices ordered left-to-right along the event timeline:

| Lane | Holds | Color |
|------|-------|-------|
| **Wireframes** | UI mockup (screen title, text fields, buttons, output lists) — or a **⚙️ cog + actor** for `automation` / request-response `translation` | white / purple |
| **Commands / Read models** | commands (write) and views (read) | blue / green |
| **Events** | the event timeline spine | orange |
| **External systems** | external systems & API calls from `translation` slices | red |

Ordering: explicit `sequence:` first, then event-dependency (a producer sits left
of its consumers), then filename. The To-Do-list cycle (a view feeding an
automation that records an event feeding the same view) is broken deterministically.

## Per-pattern mapping, palette, geometry & customization

See **[REFERENCE.md](REFERENCE.md)** — how each `pattern` maps to boxes and
arrows, the exact colors/coordinates, cross-slice reference handling, and where
to edit the script to change the layout.
