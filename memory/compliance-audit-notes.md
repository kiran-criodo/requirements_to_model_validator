# Compliance audit (ASIL / ISO 26262 / ASPICE) — derivation rules & gotchas

How `tools/compliance_audit.py` derives its findings, and traps to avoid. Everything is
derived from detectable facts — never invent ASIL levels, test coverage, or stages.

## ASIL classification (indicative, feature-level)
Source `Requirement.docx` has **no explicit ASIL tags**, so ASIL is derived and must be
labelled *indicative*. Rules from `ASIL_Classification_Standard.docx` worked ACC example
(ACC longitudinal control = ASIL B; comfort-only = QM):
- Match comfort/safe-state keywords (`off mode`, `standby`, `default state`, `set-speed`)
  against the requirement **title only** — otherwise a parent req that merely *lists* the modes
  ("OFF Mode, STANDBY Mode & ON Mode") gets wrongly down-graded to QM.
- Do **not** put `acceleration_mode` in the safety keyword set — every state sets that output,
  so it doesn't discriminate control vs. safe-state.
- Expected ACC result: 10 ASIL B, 2 QM (only Req 3a OFF and 3b STANDBY are QM).
- If the source has explicit ASIL/Type tags (e.g. a REQ-ACC table), use those instead of deriving.

## Program-stage / SIL-HIL detection gotcha
Detect SIL/HIL results by matching the token as a **delimited word**, not a substring:
`(?:^|[^a-z])hil(?:[^a-z]|$)`. A plain `"hil" in name` false-matches `rtwhilite.js` and
`hilite_warning.png` (from "highlight") in the generated-code folder and wrongly reports the
program at stage 10 (HIL). Correct ACC stage = **7 (Code Generation)**.

## Honest ACC compliance result
- Stage 7; artifacts present: requirements, SLDD, Model Advisor reports, generated code.
  **No test artifacts** → SWE.4 (MIL) and SWE.6 (HIL) not started; SWE.5 in-progress.
- ISO 26262-6 chain: Req↔Architecture ✓ and Architecture↔Design ✓ (from the trace audit), but
  Design↔Verification ✗ and Verification↔Safety-case ✗ for **all** requirements — the `.slmx`
  has only `Implement` links, no verification/test links.
- Headline finding (P1): no requirement-based verification for the 10 ASIL B requirements,
  while the program has already reached Code Generation (stage 6 MIL skipped).

## Reuse
`compliance_audit.py` imports `trace_audit.py` (parse_requirements / parse_model / parse_links /
audit) — keep that dependency stable. See also [[simulink-parsing-notes]].
