# Simulink / requirements parsing notes (ACC example)

Non-obvious facts learned while building `tools/trace_audit.py`. These save re-discovery and
prevent regressions.

## File formats (all zipped XML — parse directly, no MATLAB)
- **`.slx`** is a ZIP. Model structure lives in `simulink/systems/system_<N>.xml`; Stateflow
  in `simulink/stateflow/chart_<N>.xml`.
- **`.slmx`** (Requirements Toolbox link set) is a ZIP; the links are in
  `slrequirements/data.xml` as `<items>` with `<id>` (model element id like `:36:11`),
  `<description>` (the requirement text), and `<dest><artifactId>` (points into the req doc).
- **`.docx`** is a ZIP; text is in `word/document.xml`.

## Subsystem containment (key trick)
The children of a SubSystem with SID `N` live in the file **`system_N.xml`** (`system_root.xml`
for the top level). So the filename number == the owning SubSystem's SID. This is how
`parent_of` (containment) is recovered without a real parser.
- Hierarchy: root → `Adaptive_Cruise_Control` (SID 79) → `Requirement1_Lead_Vehicle` (1),
  `Requirement2_Drive_Vehicle` (4), `Requirement3_ACC_Algorithm` (7) → `ACC_MODE_ALGORITHM`
  (36, holds the Stateflow chart).

## Stateflow parsing gotcha
States nest, so a naive `<state ...>...</state>` regex mis-associates labels (only 8 of 9
states parsed, and one went missing). Fix: collect every `<state SSID=..>` position and assign
each the **first `<P Name="labelString">` before the next `<state>` tag**. Skip labels
starting with `[` — those are transition conditions, not state names.

## SID vs SSID collision
`.slmx` ids like `:36:11` mean "SSID 11 inside subsystem SID 36". A Stateflow **SSID** can
equal an unrelated block **SID** (e.g. 11 is also a block elsewhere). When resolving a nested
id, check the Stateflow state map **before** the block-SID index, or it resolves to the wrong
element (this caused Req 3c(i) to mis-resolve to `RadarInput_DriveVehicle`).

## Signal-name detection
Don't tokenize on `_` when detecting signal names — `Set_Speed` must stay whole to match the
model signal `Set_Speed`. Use `[A-Za-z][A-Za-z0-9_]+` and compare full identifiers. A
"missing signal" must not match any signal, subsystem, or Stateflow state name (state names
like `LeadVehicle_Detected_Follow` were false-positived as missing signals).

## Two requirement documents exist (don't confuse them)
- `resources/ACC (Adaptive Cruise Control)/Requirement.docx` — narrative Req 1/2/3/3a-c that
  maps **1:1 to the model** via `.slmx`. This is the authoritative set the audit runs on.
- `resources/UseCase_ACC_Requirements.docx` — a cleaner `REQ-ACC-001..008` table with ASIL
  **types** and traced-signal names that **do not** match the model's signal names. Useful
  later for the ASIL/compliance step and for demonstrating real gaps.

## Known honest result for the ACC example
12/12 requirements Matched; orphan logic = the top container `Adaptive_Cruise_Control` (SID 79,
no direct link) and a `Unit Delay` feedback block (SID 103). This is the correct, expected
output — the reference model is well-traced.
