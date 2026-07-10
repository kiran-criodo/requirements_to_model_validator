# Workflow: Answer natural-language questions about the audit

## Purpose
Let an engineer ask free-text questions about traceability and compliance and get answers
**grounded in the audit results** (never guessed) — e.g. "which ASIL B requirements aren't
verified?", "which requirements aren't in the model?", "what's blocking stage 6?".

## When to use
Any conversational question about the current results: coverage, a requirement's status/ASIL,
gaps, orphan logic, verification, punch-list priorities, ASPICE/SWE status, program stage.

## Inputs
- The JSON produced by the other workflows: `output/ACC_compliance_report.json` (preferred —
  has ASIL + ISO chain) and/or `output/ACC_traceability_matrix.json`.
- If neither exists, run `workflows/traceability-audit.md` (and `compliance-audit.md`) first.

## How the agent should answer (important)
1. **Ground every answer in the data — do not answer from memory.** Get the facts from
   `tools/ask.py`, then phrase the answer. Prefer explicit flags (robust) over the free-text
   `-q` mapper:

   | The engineer asks… | Run |
   |---|---|
   | which requirements aren't in the model? | `ask.py --status Gap` |
   | which ASIL B requirements aren't verified? | `ask.py --asil "ASIL B" --unverified` |
   | which are only partially mapped? | `ask.py --status Partial` |
   | which requirements mention <X>? | `ask.py --search X` |
   | which requirements use signal <S>? | `ask.py --signal S` |
   | details for requirement 3c(i) | `ask.py --req "3c (i)"` |
   | top / P1 findings? | `ask.py --punchlist --priority P1` |
   | ASPICE / SWE status? | `ask.py --aspice` |
   | any orphan logic? | `ask.py --orphans` |
   | overall summary? | `ask.py --summary` |
   | anything (best-effort) | `ask.py -q "…the question…"` |

2. Combine filters for compound questions (e.g. `--asil "ASIL B" --status Gap`).
3. **Report honestly.** If a query returns nothing, say so plainly ("there are no AEB
   requirements in this set") rather than implying a problem or inventing an answer.
4. Cite the concrete elements (requirement IDs, model elements, SIDs) from the tool output so
   the engineer can verify.
5. If the question needs data the current audit doesn't have (e.g. a different model, or a
   requirement source that isn't loaded), say what's missing and offer to re-run the relevant
   workflow rather than guessing.

## Output
- A concise conversational answer in chat, grounded in `tools/ask.py` output. No file is
  produced unless the engineer asks for one.

## Validation (check before answering)
- The numbers you state must match what `ask.py` printed — don't round or embellish.
- If results look stale (model or requirements changed since the JSON was generated), re-run
  the audit first, then answer.
