# REQ-ACC table source + gap-analysis result

The second requirements source, `resources/UseCase_ACC_Requirements.docx`, is a tagged table
(`Req ID | Description | Type | Traced Signal`) with explicit ASIL-relevant Types. Auditing the
model against it is where the real gap story appears (unlike `Requirement.docx`, which maps 1:1).

## How it's parsed & matched
- `trace_audit.parse_requirements` auto-detects the table (header cell contains "Req ID") and
  reads id / description / Type / declared Traced Signal.
- Table-format matching keys on the **declared Traced Signal**, NOT the prose (the verbose
  descriptions incidentally share tokens with unrelated ON-mode states — matching on prose
  produced false matches like REQ-ACC-002 → a `..._Set_Speed` state).
- Tokenizer is camelCase-aware (`SetSpeed_Req_kph` → {set, speed, req, kph}) so differently
  named signals still match (SetSpeed_Req_kph ↔ Set_Speed). Semantic match needs ≥2 shared
  distinctive tokens (stopwords removed).
- Process-type requirements (e.g. Model Advisor checks) get status **Process** (no model
  element); verified in the compliance layer via ASPICE work products, not the matrix.

## ASIL for REQ-ACC (explicit, not keyword-derived)
`compliance_audit.REQACC_ASIL` encodes the ASIL standard's worked verdict: REQ-ACC-001/002 = QM
(comfort), REQ-ACC-003/004 = ASIL B. Type column drives the rest (Safety → ASIL B;
Process/Traceability → N/A). Only untagged narrative reqs fall back to keyword classification.

## Honest result (ACC model vs REQ-ACC table)
- Coverage ~14%: only REQ-ACC-001 (set-speed input) partially maps (→ `Set_Speed`, naming differs).
- Gaps: REQ-ACC-002 (QM, PID cruise), 003/004/005/006 (ASIL B — gap-maintenance, **decel limit
  004 = the safety money-shot**, brake-disengage, resume), 007 (traceability to a
  "Longitudinal Controller" subsystem that doesn't exist).
- Process: REQ-ACC-008 (Model Advisor) — satisfied via ASPICE, not a model element.
- Punch-list P1: "4 ASIL B requirements with no model implementation."

## Filenames
REQ-ACC runs use `output/REQACC_traceability_*` and `output/REQACC_compliance_report.*` so they
don't clobber the `Requirement.docx` (`ACC_*`) results. See [[compliance-audit-notes]],
[[simulink-parsing-notes]].
