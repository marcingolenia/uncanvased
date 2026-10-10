# Gap review

Review only the slices written in this run (review mode: all of `slices/`). Existing `slices/` files are context: check them before reporting something as missing, never report gaps that involve only them, and never propose deleting a slice because it isn't in the image.

## Detect

Build the graph UI → command → event → read model → UI / ⚙️. For each gap record its slug, the evidence (names, slices, fields), a recommended fix and at most one alternative.

Judge by domain meaning: `CarBooked` should update `AvailableCars` even though no field says so. Raise a domain-based gap only when the board's names make it likely.

Skip gaps whose node already carries `# gap-ignored: <slug>` or `# todo: <slug>`. Skip anything without evidence, and style preferences.

## Catalogue (ask in this order)

**A. Information flow.** Can be deferred, not dismissed; only `missing-projection` offers `Not a gap`.
1. `missing-projection`: an event changes what a view shows but isn't in its `sources`. Fix: add it, with `# note: <how it changes the view>` on the `sources` line.
2. `untraceable-field`: a view field comes from no source event field. Fix: add the field to an event, or add the event.
3. `unfed-screen`: a UI output has no read model. Fix: add a `state_view` slice, or name the view.
4. `unsourced-command-field`: a payload field comes from no UI input, triggering view or `external_call`. Fix: add the input or view field.
5. `unsourced-event-field`: an event field isn't in the command payload. Fix: add it, or `# note: system-generated`.

**B. Dangling.** Check `slices/` before raising.
6. `unused-view`: no UI or ⚙️ reads the view. Fix: name its consumer.
7. `orphan-command`: no UI or processor issues the command. Fix: add the screen or automation.

An event no view reads is not a gap; list it in the summary.

**C. Missing slices**
8. `missing-reverse`: an entity enters a state it never leaves (booked, never returned). Ask only when the domain clearly implies it, as a business question ("What happens when the car is returned?"). Options: `Sketch a slice`, `Out of scope` (= not a gap), `Ask the business` (= defer).
9. `incomplete-chain`: an automation or translation lacks its read model or event. Fix: add the missing pieces.

**D. Flagged violations**
10. `event-to-command`: insert a to-do read model (its own `state_view` slice) and a ⚙️; the slice becomes an automation.
11. `event-to-event`: insert the command and its trigger between them.

**E. Specs and smells**
12. `no-spec`: a `state_change` slice has only the trivial happy path. Ask once, as one multi-select of all such slices: "Which do you want to spec now?" Follow up on ticked slices; defer the rest. Skip slices hit by `untested-constraint`.
13. `untested-constraint`: a constraint implies a rejection no scenario covers. Fix: a failure scenario.
14. `todo-spec`: a to-do list view (it triggers a ⚙️, or feeds a screen whose button records an event in its `sources`) has no scenario showing an item leaving it. Ask once, as one multi-select of all such views: "Which to-do lists should get a spec for clearing an item?" Fix per ticked view: a `state_view` scenario, given the adding event + the clearing event (same id), then the view without the item ([REFERENCE.md](REFERENCE.md) Scenarios). Recommend ticking when both events are already in `sources`.
15. `mixed-actor-screen`: one screen issues commands from different actor lanes. Fix: one screen per actor.
16. `naming`: event not past tense, command not imperative, or a translation's event named after the foreign system. Fix: rename everywhere.

**F. Story and streams.** The board must read as one story; `slice-to-diagram` draws a duplicate for every event read before it happens.
17. `out-of-story`: a slice reads an event whose producer has a higher `sequence`, other than an event recorded by its own consumer (the ⚙️ it triggers, or the command behind the button on the screen it feeds). One question per reader, listing its late events: "In the business story, does `<reader>` happen after `<event>`?" Options (no `Recommended`; this is the business's call):
    - `Move it later`: new `sequence` values after the last producer; move the reader's consumers along so a to-do view stays right before its ⚙️ and a screen's read model right before its command. Preview every changed `sequence`.
    - `Keep it here`: the view really is read earlier and later events change it (e.g. availability seen at search time). `# gap-ignored: out-of-story` on the `sources` line; the diagram keeps a duplicate.
    - `Defer`.
18. `no-stream`: events have no `context` and the board shows no labelled event lanes. Ask once: "Which streams do these events belong to?" Options, each previewing the slice → `context` mapping for every slice that records events:
    - one stream per business entity whose lifecycle the events record (`Vehicle`, `Booking`, `Rental`, `Payment`);
    - a coarser grouping by bounded context (`Fleet`, `Reservations`, `Billing`);
    - `Defer`, or `Not a gap` (one lane: `# gap-ignored: no-stream` on the first slice).

## Wizard

Start with one line: gap counts per section. Over 12 gaps: first ask **All, one by one (Recommended)** / **Only A–C and F** / **Report only**.

Then one `AskUserQuestion` per gap:
- `header`: short gap kind (≤12 chars).
- `question`: the evidence plus an open question about the business, e.g. "After `CarBooked`, should the car still appear in `AvailableCars`?" Never phrase it as a yes/no on the agent's own fix.
- `options`, each with a `preview` of the exact YAML change and file:
  1. suggested fix; mark it `(Recommended)` only when names or fields on the board prove the gap, not when it rests on domain inference
  2. alternative, if any
  3. `Defer`: `# todo: <slug>: <question for the business>` on the affected node
  4. `Not a gap`: `# gap-ignored: <slug>`. Not offered for section A (except `missing-projection`). For a missing slice, put it on the event that starts the state.

Apply "Other" answers if unambiguous; otherwise ask one follow-up. Apply each answer before the next question, and update the queue: drop gaps now resolved, add gaps the fix created.

Without `AskUserQuestion`, write the gaps to `slices/GAPS.md` instead.

## Applying fixes

- Mark each added or changed node `# added: gap review` (rewrite one-line lists one item per line first). New slices get their own file with the marker on `slice:`, the next free `id`, and a `sequence` that keeps the story in order (producer before reader).
- Follow [REFERENCE.md](REFERENCE.md) consistency rules; a changed name or shape changes in every slice that uses it.
- Edit a pre-existing file only if the question's preview named it.
