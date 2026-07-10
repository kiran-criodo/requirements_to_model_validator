# Workflow: ASIL / ISO 26262 / ASPICE Compliance Cross-check & Punch-list

## Purpose
Layer safety/process compliance on top of the traceability audit: classify each requirement
by ASIL, check the ISO 26262-6 Part 6 bidirectional traceability chain, report ASPICE SWE.1–6
work-product status, and produce a punch-list prioritized by **ASIL × program stage**.

## When to use
Triggers like: "run the compliance check", "ISO 26262 / ASPICE status", "what's our ASIL
coverage?", "give me the prioritized punch-list", "are the safety requirements verified?",
"which ASPICE work products are missing?".

## Inputs
- Same three inputs as the traceability audit (`Requirement.docx`, `ACC_Project.slx`,
  `ACC_Project.slmx`) — this workflow reuses `tools/trace_audit.py` for parsing + matching.
- The standards docs in `resources/` inform the rules (already encoded in the tool):
  `ASIL_Classification_Standard.docx`, `ISO26262_ASPICE_Compliance_Guidelines.docx`,
  `Program_Stage_Taxonomy.docx`.
- **Program stage** (1–12): auto-detected from the artifacts present, or set with `--stage N`.

## Steps
1. Confirm inputs (defaults = the ACC example). Ask if a file is missing; don't guess.
2. Run:
   ```
   python3 tools/compliance_audit.py            # stage auto-detected
   python3 tools/compliance_audit.py --stage 6  # or set the program stage explicitly
   ```
3. The tool:
   - **Classifies ASIL** per requirement (indicative, feature-level) from the ASIL standard's
     worked ACC verdict: gap/speed-control path = ASIL B; OFF/STANDBY mode housekeeping = QM.
   - **Checks the ISO 26262-6 Part 6 chain** per requirement: Req↔Architecture,
     Architecture↔Design (from the trace audit), Design↔Verification, Verification↔Safety-case
     (present only if verification/test links exist).
   - **Derives ASPICE SWE.1–6 status** from which artifacts exist next to the model
     (requirements, SLDD, Model Advisor reports, generated code, tests, SIL/HIL results).
   - **Auto-detects the program stage** from the highest-stage artifact found.
   - **Builds a prioritized punch-list** (P1/P2/P3) scored by ASIL weight × how late the gap
     sits in the program.
4. Review the console summary, then open the report and sanity-check it (see Validation).
5. Present: the headline (P1 count, ASIL distribution, verification coverage, program stage),
   the top punch-list items, and the path to the report.

## Output
- `output/ACC_compliance_report.html` — dashboard: KPI tiles, program-stage bar (done / skipped
  / current), prioritized punch-list, per-requirement ISO 26262-6 trace chain, ASPICE SWE.1–6
  status cards. Theme-aware, self-contained.
- `output/ACC_compliance_report.json` — machine-readable findings (reused by NL Q&A later).

## Validation (check before showing results)
- **Program stage must reflect real evidence.** If it jumps to HIL (10) with no HIL rig,
  suspect a substring false-positive (e.g. "hilite" ≠ "HIL") — the tool matches SIL/HIL only
  as delimited tokens; verify the detected stage matches the artifacts you can see.
- **ASIL split should be defensible**, not uniform: OFF/STANDBY-mode requirements should read
  QM, the actuation/gap-control path ASIL B. A parent requirement that merely lists modes must
  not be down-graded to QM.
- Never present ASIL as authoritative — it is **indicative** here because `Requirement.docx`
  carries no explicit ASIL tag. Say so, and point to a formal S/E/C assessment for sign-off.
- Verification findings must match reality: if the `.slmx` has only `Implement` links and no
  test artifacts exist, Design↔Verification is genuinely absent — report it, don't soften it.

## Notes / limits
- ASIL classification uses **explicit tags when the source has them** — the ASIL standard's
  worked REQ-ACC verdict (001/002 QM, 003/004 ASIL B) and the Type column
  (Process/Traceability = N/A, Safety = ASIL B). It only falls back to indicative keyword
  classification for untagged narrative requirements (`Requirement.docx`).
- The punch-list leads with **requirements that have no model implementation** (gaps),
  weighted by ASIL — so an ASIL-B safety gap (e.g. REQ-ACC-004) ranks P1 — then verification
  gaps on implemented requirements, orphan logic, and ASPICE process gaps.
- Program-stage auto-detection keys off artifact filenames next to the `.slx`; override with
  `--stage` when you know the true stage.
- Next planned step: natural-language Q&A over `output/*.json` (task 7).
