# img-to-slice — gap review wizard

After the transcribed slices are written, check the slices **written in this run** (i.e. the board in the image) for gaps. Then walk the user through them **one question at a time**, so the result is a complete, canonical event model.

The transcription stays faithful to the board. A gap is only fixed when the user accepts the fix in the wizard.

## 1. Detect

Build the graph from this run's slices: UI → command → event → read model → UI / ⚙️. Existing files in `slices/` are **context only**: read them so you don't report something they already cover (e.g. `CarReturned` already exists), but never report a gap that involves only existing slices. They may be old, and reviewing them is out of scope. Then check the graph against the catalogue below. For each gap, record:
- its **kind** (from the catalogue)
- the **evidence**: the names, slices and fields involved
- a **recommended fix**, plus one alternative if a real one exists

Judge by domain meaning, not only by names. Example: `CarBooked` should update `AvailableCars`, because booking a car makes it unavailable, even though no field name says so.

### Gap catalogue (ask in this order, highest impact first)

**A. Broken information flow**
1. **Missing projection:** an event changes the state of the thing a read model shows, but it is not in that view's `sources`. Example: `CarBooked` is missing from `AvailableCars`. Fix: add the event to `sources`, and record how it changes the view as a trailing `# note:` on the `sources` line (e.g. `# note: CarBooked removes the car`).
2. **Untraceable view field:** a read model field comes from no field of any source event, which breaks information completeness. Fix: add the field to an event, or add the event that carries it.
3. **Unfed screen:** a UI output, or prefilled data on a screen, has no read model behind it. Fix: add a `state_view` slice, or name the existing view that should feed the screen.
4. **Unsourced command field:** a command payload field comes from neither a UI input, the triggering read model, nor the processor's `external_call`. Fix: add a UI input or a view field.
5. **Unsourced event field:** an event field is not derivable from the command payload. Fix: add it to the command, or mark it system-generated (`# note: system-generated`, e.g. ids or timestamps).

**B. Dangling elements**
6. **Dead-end event:** no read model consumes the event, so the information is never read. Fix: add it to an existing view, or propose a new `state_view` slice. Accept "audit only" as a valid answer.
7. **Unused read model:** neither a UI nor a ⚙️ consumes the view ("no question, no read model"). Fix: name its consumer, or drop the slice.
8. **Orphan command:** neither a UI trigger nor a processor issues the command. Fix: add the screen, or the automation slice.

**C. Missing slices**
9. **Missing reverse or lifecycle step:** an entity can enter a state but never leave it. Examples: booked but never returned or cancelled, opened but never closed. Fix: propose a new `state_change` or `automation` slice with a named command and event. Only ask this when the domain clearly implies the step.
10. **Incomplete ⚙️ chain:** an automation or translation is missing its read model or its resulting event (this was already flagged with `# warn:` during transcription). Fix: propose the missing pieces.

**D. Rule violations already flagged with `# warn:`**
11. **Event → command:** fix by inserting a to-do read model and a ⚙️, which turns the slice into an automation.
12. **Event → event:** fix by inserting the command (and its trigger) between the two events.

**E. Scenarios and smells**
13. **Untested constraint:** a slice has `constraints:` but no scenario that covers the rejection branch. Fix: propose a failure scenario. Ask only when the constraint implies a concrete rejection.
14. **Right Chair:** one read model has many unrelated sources and answers several questions. Fix: split it into named views.
15. **Bed:** one screen fires many commands. Fix: split it into screens.
16. **Naming:** an event is not in past tense, a command is not imperative, or a translation's internal event carries the foreign system's name. Fix: propose a rename and apply it everywhere the name appears.

Don't report:
- anything you can't support with evidence from the model
- pure style preferences
- gaps the user already ignored, i.e. lines that carry a `# gap-ignored: <kind>` comment

## 2. Wizard

Open with one line in chat: how many gaps were found, per section (A–E).

If there are more than 12 gaps, first ask with `AskUserQuestion` how to proceed:
- **All, one by one (Recommended)**
- **Only A–C** (completeness only)
- **Write report only**

Then ask **one `AskUserQuestion` call per gap**, in catalogue order:
- `header`: the gap kind, at most 12 characters (`Projection`, `Dead event`, `New slice`…).
- `question`: the evidence in one sentence plus the question. Example: "`CarBooked` doesn't update `AvailableCars` — a booked car would still be listed as available. Add it as a source?"
- `options` (2–4), with a `preview` showing the exact YAML change (the lines added or changed, and the file name):
  1. the recommended fix, labeled `… (Recommended)`
  2. an alternative fix, if one exists
  3. `Defer`: leave a `# todo: <gap>` comment on the affected node
  4. `Not a gap`: leave a `# gap-ignored: <kind>` comment so it isn't asked again

The user can always pick "Other" and describe their own fix. Apply it if it is unambiguous; otherwise ask a single follow-up.

Apply each answer **immediately**, before asking the next question. Later questions can depend on earlier fixes, so re-check the queue: drop gaps that are already resolved, and add any new gaps an accepted fix introduces (e.g. a new slice whose event nobody consumes).

If `AskUserQuestion` is not available (non-interactive run), skip the wizard. Instead, write `slices/GAPS.md` listing each gap with its evidence and recommended fix.

## 3. Applying fixes

- Every node a fix adds or changes gets a trailing `# added: gap review`. This keeps it distinguishable from what the board showed.
- A new slice gets its own file, named by the normal filename rule, with `# added: gap review` on the `slice:` line. Pick its `pattern` by the usual classification rules.
- All [REFERENCE.md](REFERENCE.md) consistency rules apply. A renamed or reshaped event, view or command must change **identically in every slice** that uses it.
- A fix may edit a slice file that existed before this run only if the question named that file in its preview. See also [UPDATE.md](UPDATE.md).
