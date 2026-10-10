# img-to-slice — gap review wizard

After the transcribed slices are written, check the slices **written in this run** (i.e. the board in the image) for gaps. Then walk the user through them **one question at a time**, so the result is a complete, canonical event model.

The transcription stays faithful to the board. A gap is only fixed when the user accepts the fix in the wizard.

**The image may be a fragment** (e.g. one redrawn slice), not the whole board. Something missing from the image is not missing from the model: look for it in `slices/` first. Never propose deleting a slice or file because it isn't in the image.

## 1. Detect

Build the graph from this run's slices: UI → command → event → read model → UI / ⚙️. Existing files in `slices/` are **context only**: read them so you don't report something they already cover (e.g. `CarReturned` already exists), but never report a gap that involves only existing slices. They may be old, and reviewing them is out of scope. Then check the graph against the catalogue below. For each gap, record:
- its **kind** (from the catalogue)
- the **evidence**: the names, slices and fields involved
- a **recommended fix**, plus one alternative if a real one exists

Judge by domain meaning, not only by names. Example: `CarBooked` should update `AvailableCars`, because booking a car makes it unavailable, even though no field name says so. But don't pad the queue: raise a domain-based gap only when the board's own names make it likely. When in doubt, ask, and let `Not a gap` be the cheap way out.

### Gap catalogue (ask in this order, highest impact first)

Each kind has a fixed slug (in brackets), used in `# gap-ignored:` and `# todo:` comments so re-runs can match them.

**A. Broken information flow** — information completeness, the property the method exists to guarantee. These can be deferred but not dismissed: no `Not a gap` option, except for `[missing-projection]`, which rests on domain judgment.
1. **Missing projection** `[missing-projection]`: an event changes the state of the thing a read model shows, but it is not in that view's `sources`. Example: `CarBooked` is missing from `AvailableCars`. Fix: add the event to `sources`, and record how it changes the view as a trailing `# note:` on the `sources` line (e.g. `# note: CarBooked removes the car`).
2. **Untraceable view field** `[untraceable-field]`: a read model field comes from no field of any source event. Fix: add the field to an event, or add the event that carries it.
3. **Unfed screen** `[unfed-screen]`: a UI output, or prefilled data on a screen, has no read model behind it. Fix: add a `state_view` slice, or name the existing view that should feed the screen.
4. **Unsourced command field** `[unsourced-command-field]`: a command payload field comes from neither a UI input, the triggering read model, nor the processor's `external_call`. Fix: add a UI input or a view field.
5. **Unsourced event field** `[unsourced-event-field]`: an event field is not derivable from the command payload. Fix: add it to the command, or mark it system-generated (`# note: system-generated`, e.g. ids or timestamps).

**B. Dangling elements**
6. **Unused read model** `[unused-view]`: neither a UI nor a ⚙️ consumes the view, in this run or in `slices/` ("no question, no read model"). Fix: name its consumer, or `Defer`.
7. **Orphan command** `[orphan-command]`: neither a UI trigger nor a processor issues the command, in this run or in `slices/`. Fix: add the screen, or the automation slice.

An event no read model reads yet is **not** a gap: facts are kept for questions asked later. List such events once in the final summary as "not yet read by any view".

**C. Missing slices**
8. **Missing reverse or lifecycle step** `[missing-reverse]`: an entity can enter a state but never leave it, and nothing in `slices/` covers it. Examples: booked but never returned or cancelled. Only ask this when the domain clearly implies the step. Ask it as a question for the business, e.g. "What happens when the car is returned?", with these options:
   - `Sketch a slice`: only then build a new `state_change` or `automation` slice
   - `Out of scope`: treated as `Not a gap`
   - `Ask the business`: treated as `Defer`
9. **Incomplete ⚙️ chain** `[incomplete-chain]`: an automation or translation is missing its read model or its resulting event (this was already flagged with `# warn:` during transcription). Fix: propose the missing pieces.

**D. Rule violations already flagged with `# warn:`**
10. **Event → command** `[event-to-command]`: fix by inserting a to-do read model and a ⚙️, which turns the slice into an automation. The to-do read model also gets its own new `state_view` slice, with the triggering event as its source.
11. **Event → event** `[event-to-event]`: fix by inserting the command (and its trigger) between the two events.

**E. Specs and smells**
12. **No spec** `[no-spec]`: a `state_change` slice has no scenario beyond the trivial happy path. Ask "What must be true first, or what makes this fail?" Recommended option: `Defer`. Skip it when `[untested-constraint]` already applies to the slice.
13. **Untested constraint** `[untested-constraint]`: a slice has `constraints:` but no scenario that covers the rejection branch. Fix: propose a failure scenario. Ask only when the constraint implies a concrete rejection.
14. **Mixed-actor screen** `[mixed-actor-screen]`: one screen issues commands that belong to different actor lanes. A screen with several buttons for one actor is fine. Fix: split it into one screen per actor.
15. **Naming** `[naming]`: an event is not in past tense, a command is not imperative, or a translation's internal event carries the foreign system's name. Fix: propose a rename and apply it everywhere the name appears.

Don't report:
- anything you can't support with evidence from the model
- pure style preferences
- gaps the user already ignored, i.e. lines that carry a `# gap-ignored: <slug>` comment
- gaps already deferred, i.e. lines that carry a `# todo: <slug>` comment (list them in the summary instead)

## 2. Wizard

Open with one line in chat: how many gaps were found, per section (A–E).

If there are more than 12 gaps, first ask with `AskUserQuestion` how to proceed:
- **All, one by one (Recommended)**
- **Only A–C** (completeness only)
- **Write report only**

Then ask **one `AskUserQuestion` call per gap**, in catalogue order:
- `header`: the gap kind, at most 12 characters (`Projection`, `Unused view`, `New slice`…).
- `question`: the evidence in one sentence plus the question. Example: "`CarBooked` doesn't update `AvailableCars` — a booked car would still be listed as available. Add it as a source?"
- `options` (2–4), with a `preview` showing the exact YAML change (the lines added or changed, and the file name):
  1. the recommended fix, labeled `… (Recommended)`
  2. an alternative fix, if one exists
  3. `Defer`: leave a `# todo: <slug>: <gap>` comment on the affected node (same placement rule as below)
  4. `Not a gap` (not offered for section A, except `[missing-projection]`): leave a `# gap-ignored: <slug>` comment so it isn't asked again. For a gap with no node yet (e.g. `[missing-reverse]`), put it on the event that starts the state: `CarBooked  # gap-ignored: missing-reverse`

The user can always pick "Other" and describe their own fix. Apply it if it is unambiguous; otherwise ask a single follow-up.

Apply each answer **immediately**, before asking the next question. Later questions can depend on earlier fixes, so re-check the queue: drop gaps that are already resolved, and add any new gaps an accepted fix introduces (e.g. a new slice whose screen has no read model).

Deferred section A gaps are listed in every final summary until resolved.

If `AskUserQuestion` is not available (non-interactive run), skip the wizard. Instead, write `slices/GAPS.md` listing each gap with its evidence and recommended fix.

## 3. Applying fixes

- Every node a fix adds or changes gets a trailing `# added: gap review`. This keeps it distinguishable from what the board showed. To mark a single item in a one-line list (e.g. `sources: [A, B]`), rewrite that list one item per line first.
- A new slice gets its own file, named by the normal filename rule, with `# added: gap review` on the `slice:` line. Pick its `pattern` by the usual classification rules.
- All [REFERENCE.md](REFERENCE.md) consistency rules apply. A renamed or reshaped event, view or command must change **identically in every slice** that uses it.
- A fix may edit a slice file that existed before this run only if the question named that file in its preview. See also [UPDATE.md](UPDATE.md).
