# Workflow: Requirement → Model Traceability Audit

## Purpose
Audit how well a Simulink model implements a set of requirements: match each requirement to
the model element(s) that implement it, and flag gaps, orphan logic, and partial signal
coverage — rendered as an interactive HTML dashboard.

## When to use
Triggers like: "run a traceability audit", "check the ACC model against its requirements",
"which requirements aren't in the model?", "generate the traceability dashboard",
"is there any orphan logic in the model?".

## Inputs
- **Requirements document** (`.docx`) — the requirement set to validate against.
  Default: `resources/ACC (Adaptive Cruise Control)/Requirement.docx`.
- **Simulink model** (`.slx`). Default: `resources/ACC (Adaptive Cruise Control)/ACC_Project.slx`.
- **Requirement links** (`.slmx`, optional but recommended) — existing Requirements Toolbox
  links. Default: `resources/ACC (Adaptive Cruise Control)/ACC_Project.slmx`.
- All three are read directly as zipped XML — **no MATLAB and no network access needed.**

## Steps
1. Confirm which requirement doc / model / links to use. If the user doesn't say, use the
   ACC defaults above. If a model or requirements file is missing, ask — don't guess.
2. Run the audit tool:
   ```
   python3 tools/trace_audit.py \
     --req   "<requirements .docx>" \
     --model "<model .slx>" \
     --links "<links .slmx>"     # omit if there is no .slmx
   ```
   (With no arguments it runs on the bundled ACC example.)
3. The tool performs tasks 1–4:
   - **Parse requirements** into atomic statements (each `Requirement N…` heading).
   - **Parse the model**: subsystem tree, blocks, inport/outport signals, Stateflow states,
     and subsystem containment.
   - **Parse existing links** (`.slmx`) as the ground-truth "what's actually traced".
   - **Match** each requirement to model element(s) via: (a) existing requirement link,
     (b) naming convention, (c) signal-overlap / semantic similarity.
   - **Flag** each requirement `Matched` / `Partial` / `Gap`, detect **orphan logic**
     (elements whose subsystem chain carries no requirement link; interface ports excluded),
     and list **missing signals** named in a requirement but absent from the model.
4. Review the console summary (counts of matched / partial / gap / orphan).
5. Open the dashboard and skim it for correctness before presenting (see Validation).
6. Present the result to the user: the headline coverage %, any gaps or orphan logic, and
   the path to the dashboard. Offer to publish the dashboard as a shareable Artifact.

## Output
- `output/ACC_traceability_dashboard.html` — self-contained interactive dashboard
  (coverage KPIs, requirement × status matrix, orphan-logic panel, per-requirement drill-down).
  Theme-aware, no external dependencies; open it in any browser.
- `output/ACC_traceability_matrix.json` — the underlying matrix data, reused by later steps
  (compliance cross-check, prioritization, natural-language Q&A).
- Output filenames are derived from the model name when run on a different project.
- Note: `output/` is gitignored — the dashboard is regenerated from the tool, not committed.

## Validation (check before showing results)
- Spot-check 2–3 requirements against the dashboard's "Model element" column — the resolved
  element name should make sense (e.g. Req 3c(i) → `LeadVehicle_Detected_Follow`), not a
  random block. A wrong resolution usually means a Stateflow-parsing or SID-collision bug.
- "Missing signals" should be real signal names, not prose words or state/subsystem names.
- Orphan counts should be small and specific — if hundreds of "orphans" appear, interface
  ports or covered inner blocks are being miscounted; fix before presenting.
- Never invent gaps. If a model is well-traced, report that honestly (high coverage is a
  valid, useful result), and suggest pointing the tool at a stricter requirement set.

## Notes / limits (current build = tasks 1–4)
- ASIL / ASPICE compliance cross-check, ASIL × program-stage prioritization, and
  natural-language Q&A are **planned next steps**, not yet built.
- Containment is recovered from Simulink's `system_<SID>.xml` file-naming scheme; a state is
  treated as covered when a `.slmx` link targets it or its chart's subsystem is linked.
