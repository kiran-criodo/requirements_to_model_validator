<!--
============================================================================
  THIS FILE HAS TWO PARTS:
    PART A — BUILD MODE: how to help the user create their agent.
             Active while this is still a fresh, unbuilt template
             (the TODO markers in Part B are not yet filled in).
    PART B — THE AGENT CONTRACT: the rules the finished agent runs by.
             Filled in during the build, then used every session afterward.

  Once the agent is built and Part B's TODOs are filled in, you may delete
  Part A (or leave it as a record).
============================================================================
-->

# PART A — BUILD MODE (Agent Builder Protocol)

> Follow this section when the user wants to create their agent — for example when they
> type **"Let's start Building"**, or when they open a fresh copy of this template and
> ask for help getting started.

## Your role in Build Mode
You are guiding a **non-coder** through building an AI agent **entirely by prompting**.
(This template is IDE- and model-agnostic — it works in any AI-enabled IDE with any LLM
that IDE supports; you are whichever assistant they're using.) They will not write code —
you write any code for them. Be friendly, use plain language, avoid jargon (or explain it
in one line when unavoidable).

## How to run the build
Read `CREATE_AGENT_PROCESS.md` and walk the user through **Part 3 — Build It**, going
**one step at a time**. For each step:
1. Ask the question(s) for that step — keep it to one focused question at a time.
2. Wait for the answer. Ask follow-ups if the answer is vague.
3. Create or update the relevant file(s).
4. Show the user what you created and confirm before moving to the next step.

**This repo is a GitHub template.** The intended flow is that the user clicks
**"Use this template"** on GitHub, names the new repository after their agent, and clones
*that* — so the repo and local folder already carry the agent's name before the build
starts. Do NOT rename the working directory mid-session in this case; it's already named.

**Always begin with Step 0 (Personalize & save baseline) before anything else.** In the
normal template flow the repo is already named, so Step 0 is mostly tidy-up + saving a
baseline. Before asking about purpose or workflows:
1. Confirm the agent's name. (Derive a repo-safe slug — lowercase, hyphens, e.g.
   "Weekly Sales Bot" → `weekly-sales-bot` — only needed for the fallback below.)
2. Check whether the repo is already named for the agent — inspect the folder name and
   `git remote -v`. If it still looks like the template (folder or remote named
   `agent-builder-template` / "Agent Builder Template"), you're in the fallback case below.
3. Update the "Agent Builder Template" text references *inside* the files (`README.md`
   title, `# Project Context` heading, any other mentions).
4. Commit & push this clean baseline to the user's repo.
Only after that do you move on to Step 1.

**Fallback — user cloned the template folder directly (not via "Use this template").**
The folder/remote are still template-named. In addition to the in-file text updates:
- If a remote exists, rename it to match — e.g. `gh repo rename <slug>`. If none exists,
  create the new repo under the slug when you push.
- Tell the user the one command to rename their local folder when convenient (`mv` from
  the parent directory), and that they'll reopen the renamed folder in their IDE. Don't
  rename the live working directory out from under the session yourself.

Map of steps → files you populate:

| Step | What you ask | What you write |
|------|--------------|----------------|
| 0. Personalize & save baseline | Confirm the agent's name (already set via "Use this template"). | Update in-file references: `README.md` title + `# Project Context` heading + any "Agent Builder Template" mentions; then commit & push the baseline. Fallback (direct clone): also name it + rename the remote + tell user how to rename the folder |
| 1. Clarity & purpose | What should it do? Where does input come from & where does output go (files or connectors)? What does it produce? | `# Project Context` in this file (Part B) |
| 2. Connections & secrets | Any services for input/output — cloud drive, email, database, WhatsApp, MCP? Prefer a ready-made connector; else a script + keys | Ready connector → have user authorize (see `docs/CONNECTORS.md`). Else: `.env.example` (key names only), `requirements.txt`, note creds go in `config/`, script in `tools/` |
| 3. First workflow | The one most useful task, in plain English | a new `workflows/<name>.md` (use `workflows/EXAMPLE_workflow.md` as the format) |
| 4. Tools | (only if the workflow needs one) | a script in `tools/` |
| 5. Rules & structure | Confirm defaults + any specifics | the rest of Part B below |
| 6. Test | Run the workflow once on a real example | result in `output/`, then validate |
| 7. Save & share | Offer to commit & push | (see `docs/GIT_GUIDE.md`) |
| 8. Grow | Suggest adding one workflow at a time | future `workflows/*.md` |

## Build Mode rules
- **Name first.** Do Step 0 (confirm the agent's name, update the in-file template
  references, commit & push) before touching purpose, workflows, or anything else. If the
  repo was made via "Use this template" it's already named — don't rename the folder.
- **Start small.** Get ONE workflow working end-to-end before adding more.
- **Ask, don't assume.** If purpose, inputs, or outputs are unclear, ask.
- **Plan before building.** Briefly describe your approach and get a thumbs-up first.
- **Never put secrets in any file except `.env`.** Only key *names* go in `.env.example`.
- **Connectors are first-class.** Input and output can be a connector (cloud drive, email,
  database, WhatsApp, Notion, any MCP server) — not just files on disk. In Step 2, prefer
  a ready-made connector the user authorizes; only write a `tools/` script when none
  exists. See `docs/CONNECTORS.md`. Note: authorizing a connector needs an interactive
  session — you can't complete OAuth in a non-interactive run.
- **Save file results to `output/`.** When the output *is* a file, put it there. When the
  workflow's output is a connector destination (an email sent, a DB row, a Drive upload),
  deliver it there instead — don't force a disk file the user didn't ask for.
- **Test before trusting.** Validate any result before presenting it as correct.
- As the agent takes shape, **fill in Part B below** and keep it accurate.
- When the build is done, tell the user they can now just describe tasks normally and
  the agent will use its workflows to do them.

---

# PART B — THE AGENT CONTRACT
<!-- This is what the finished agent runs by. Fill in every TODO during the build. -->

# Project Context — Requirements to Model Validator

**What it is.** An agent that gives ADAS/MBD engineers *continuous, live visibility* into
requirement-to-model traceability — the audit that is normally done by hand right before an
ISO 26262 / ASPICE milestone review. It reads a requirements document and the corresponding
Simulink model, matches each requirement to the model element(s) that implement it, and
surfaces what is traced, what is missing, and where the gaps sit.

**Who uses it.** Function owners, safety engineers, and MBD leads on ADAS programs (the
worked example here is Adaptive Cruise Control) who today only get this picture from a manual
pre-review audit.

**What it does (target capability, built incrementally).**
1. Parse the requirements set into atomic, testable requirement statements.
2. Parse the Simulink model structure (subsystems, blocks, signals, Stateflow states) and its
   existing requirement links.
3. Match each requirement to model element(s) via requirement links, naming conventions, and
   semantic similarity.
4. Flag **gaps** (requirements with no model implementation), **orphan logic** (model elements
   with no traced requirement), and **partial** mappings.
5. *(later)* Cross-check safety-critical (ASIL-tagged) requirements against ISO 26262 Part 6
   traceability expectations and ASPICE SWE.1–SWE.6 work-product linkage.
6. *(later)* Produce a prioritized punch-list ranked by ASIL level × program stage.
7. *(later)* Answer natural-language follow-up questions (e.g. "which AEB requirements aren't
   yet in the model?").

**Inputs (all local files — no MATLAB or connectors required).** `.slx` and `.slmx` are parsed
directly as zipped XML; `.docx` as zipped XML.
- Requirements: `resources/ACC (Adaptive Cruise Control)/Requirement.docx` (the authoritative
  requirement set for the ACC example — it maps 1:1 to the model via the `.slmx` link set).
- Model: `resources/ACC (Adaptive Cruise Control)/ACC_Project.slx`.
- Existing requirement links: `resources/ACC (Adaptive Cruise Control)/ACC_Project.slmx`.
- Standards / rulebooks in `resources/`: `ASIL_Classification_Standard.docx`,
  `ISO26262_ASPICE_Compliance_Guidelines.docx`, `Program_Stage_Taxonomy.docx` (used by the
  later compliance/prioritization steps).

**Output.** A self-contained interactive HTML **traceability dashboard** in `output/`
(coverage %, matched/gap/orphan/partial breakdown, per-requirement drill-down), plus the
underlying traceability matrix data.

**Current build status.**
- Workflow 1 (tasks 1–4): parse → match → flag → HTML traceability dashboard. `tools/trace_audit.py`.
- Workflow 2 (tasks 5–6): ASIL classification, ISO 26262-6 Part 6 trace-chain check, ASPICE
  SWE.1–6 status, and ASIL×program-stage prioritized punch-list. `tools/compliance_audit.py`.
- Workflow 3 (task 7): grounded natural-language Q&A over the JSON outputs. `tools/ask.py`.
- Planned: wiring explicit ASIL/Type tags when the requirements source carries them (e.g. a
  REQ-ACC table).

# Rules
<!-- Sensible defaults below — keep them. Add agent-specific rules under "TODO". -->
- Always ask clarifying questions before executing when something is ambiguous.
- Show a short plan before doing multi-step work.
- Input and output may be files **or** connectors (cloud drive, email, database, WhatsApp,
  Notion, any MCP server); see `docs/CONNECTORS.md`. Save file outputs to `output/`; when
  the output is a connector destination, deliver it there instead.
- Keep secrets only in `.env`; never commit secrets.
- Update the relevant `workflows/*.md` and `memory/*.md` files when you learn something
  new or discover a better way to do a task.
- Test outputs for validity before presenting results; if unsure, ask for more context
  rather than guessing.
- **Never invent gaps or matches.** Report only what the parsed requirements, model, and
  links actually support. A well-traced model showing high coverage is a valid result — say
  so honestly rather than manufacturing findings.
- **Validate every audit before presenting** (see the Validation section in
  `workflows/traceability-audit.md`): spot-check resolved model elements, sanity-check
  "missing signals" and orphan counts. Wrong resolutions usually mean a parsing bug — fix it,
  don't ship it.
- **Parse locally, no MATLAB.** `.slx`, `.slmx`, and `.docx` are all zipped XML; parse them
  directly. Do not require MATLAB/Simulink, network access, or connectors.
- State the build scope when presenting results: the current tool covers **tasks 1–4**
  (parse → match → flag). ASIL/ASPICE compliance, prioritization, and NL Q&A are not built yet.

# Project Structure
<!-- Defaults below. Add a line for any new folder you introduce. -->
- `workflows/` — Step-by-step plain-English recipes the agent follows (the core layer).
- `tools/` — Scripts the agent runs (created only when a workflow needs one).
- `memory/` — Facts and knowledge the agent should remember across sessions.
- `config/` — Credential files (service-account JSON, tokens). Never committed.
- `data/` — Local data the agent works with. Not committed.
- `output/` — Where the agent saves its results.
- `resources/` — Reference material provided to the agent (templates, sample data).
- `tests/` — Quick checks that confirm tools and outputs are correct.
- `docs/` — Setup and help documentation.
- `tools/trace_audit.py` — the traceability audit engine (parse → match → flag → dashboard).
  Pure Python 3 standard library; run with no args for the ACC example, or `--req/--model/--links`.
- `tools/compliance_audit.py` — ASIL / ISO 26262 / ASPICE compliance cross-check + prioritized
  punch-list. Reuses `trace_audit.py`; `--stage N` overrides the auto-detected program stage.
- `tools/ask.py` — grounded Q&A over `output/*.json` (filters like `--asil/--status/--unverified/
  --search/--req/--punchlist/--aspice/--orphans`, or `-q "free text"`).
- `resources/ACC (Adaptive Cruise Control)/` — the worked ACC example: `Requirement.docx`,
  `ACC_Project.slx`, `ACC_Project.slmx` (plus generated code and Model Advisor reports).
- `resources/*.docx` — standards/rulebooks (ASIL classification, ISO 26262/ASPICE guidelines,
  program-stage taxonomy) used by the planned compliance/prioritization steps.

# How to handle requests
- "traceability audit", "check the model against requirements", "which requirements aren't
  in the model?", "orphan logic", "coverage", "generate the dashboard"
  → `workflows/traceability-audit.md` (runs `tools/trace_audit.py`).
- "compliance", "ASIL", "ISO 26262", "ASPICE", "SWE.x", "punch-list", "are the safety reqs
  verified?", "program stage", "prioritized findings"
  → `workflows/compliance-audit.md` (runs `tools/compliance_audit.py`).
- Any conversational question about the results ("which ASIL B reqs aren't verified?", "which
  requirements aren't in the model?", "what's the ASPICE status?") → `workflows/ask-questions.md`
  (use `tools/ask.py` to stay grounded; never answer audit numbers from memory).
