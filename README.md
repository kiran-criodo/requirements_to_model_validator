# Requirements to Model Validator

**An AI agent that audits a Simulink model against its requirements, plus the ISO 26262 and
ASPICE checks, continuously instead of once before a milestone review.**

On ADAS programs, requirement-to-model traceability is usually checked by hand just before
an ISO 26262 / ASPICE review, so gaps surface late. This agent gives function owners, safety
engineers and MBD leads that picture on demand. It reads the requirements document and the
Simulink model, works out which model elements implement each requirement, and reports:

- what's **traced**, **partial** or **missing** (a gap)
- **orphan logic**: model elements that no requirement asks for
- where the requirement set stands against **ASIL**, **ISO 26262-6 traceability** and
  **ASPICE SWE.1–SWE.6**, with a **punch-list ranked by ASIL × program stage**

It was first built live, on stage, for automotive engineering leaders (Skill-Lync for
Business, 7 Aug 2026), using VS Code and Claude Code on the
[Agent Builder Template](https://github.com/kiran-criodo/agent-builder-template).

> **See it without running anything:** open
> [`examples/ACC_traceability_dashboard.html`](examples/ACC_traceability_dashboard.html) and
> [`examples/ACC_compliance_dashboard.html`](examples/ACC_compliance_dashboard.html)
> (download and open in a browser). They were produced from the Adaptive Cruise Control
> model in `resources/`.

## What it can do

| # | Capability | Say something like | Workflow |
|---|------------|--------------------|----------|
| 1 | Requirement → model traceability audit | "run a traceability audit on the ACC model" | [traceability-audit](workflows/traceability-audit.md) |
| 2 | ASIL / ISO 26262 / ASPICE cross-check and prioritised punch-list | "what's blocking stage 7?", "ASPICE status" | [compliance-audit](workflows/compliance-audit.md) |
| 3 | Answer questions grounded in the audit results | "which ASIL B requirements aren't verified?" | [ask-questions](workflows/ask-questions.md) |
| 4 | Email a report to a reviewer | "email the VDD reports to the safety lead" | [send-email](workflows/send-email.md) |
| 5 | Track LLM token usage and cost | "how much has this cost?" | [token-usage](workflows/token-usage.md) |

The workflows build on each other:

```
requirements (.docx) + model (.slx) + links (.slmx)
        │
        ▼
  traceability audit ──► compliance cross-check ──► punch-list
        │                        │
        └──────► Q&A over the results ◄──────┘ ──► email to reviewer
```

## How it works

- **Deterministic core, AI on top.** Parsing and matching are plain Python, so the same
  inputs always give the same audit. The assistant chooses the workflow, runs the tools,
  checks the results and explains them. Answers to questions come from the audit data
  (`tools/ask.py`), never from memory.
- **No MATLAB needed.** `.slx`, `.slmx` and `.docx` files are zipped XML, so the agent
  parses them directly. It needs no Simulink licence, no network and no connectors.
- **Matching evidence is explicit.** Each requirement-to-element match records *how* it was
  found: an existing Requirements Toolbox link, a naming convention, or semantic
  similarity. Reviewers can see how strong each match is.
- **Honest by rule.** The agent's contract (`CLAUDE.md`) forbids inventing gaps or matches
  and requires every audit to be spot-checked before it's presented.

## Quick start

1. Set up once: Python 3.10+, then
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
   More detail in [docs/SETUP.md](docs/SETUP.md).
2. Open the folder in VS Code with the Claude extension (or run Claude Code in it).
3. Ask in plain English, e.g. *"Run the traceability and compliance audit on the ACC
   model."* Or run the tools directly:
   ```bash
   python3 tools/trace_audit.py          # defaults to the ACC example in resources/
   python3 tools/compliance_audit.py     # program stage auto-detected; or --stage 7
   python3 tools/ask.py --asil "ASIL B" --unverified
   ```
   Results go to `output/` (HTML dashboards plus JSON).

To audit your own model, pass `--req`, `--model` and `--links`. Use distinct `--out` and
`--json` paths so you don't overwrite another audit.

## What's in the repo

| Path | What's there |
|------|--------------|
| `CLAUDE.md` | The agent's operating contract: purpose, rules, scope and request routing |
| `workflows/` | Plain-English recipes for each capability |
| `tools/` | The Python tools the workflows run |
| `resources/` | Sample inputs: the ACC and VDD models with their requirements, plus the ASIL, ISO 26262/ASPICE and program-stage reference documents |
| `examples/` | Sample dashboards produced from the ACC example |
| `output/` | Generated reports (not committed) |
| `docs/` | [SETUP](docs/SETUP.md), [ARCHITECTURE](docs/ARCHITECTURE.md), [CONNECTORS](docs/CONNECTORS.md), [EMAIL_SETUP](docs/EMAIL_SETUP.md), [GIT_GUIDE](docs/GIT_GUIDE.md) |

## Sending reports by email

The email tool reads SMTP settings from a private `.env` file. Setup, including Gmail app
passwords, is in [docs/EMAIL_SETUP.md](docs/EMAIL_SETUP.md). Always try `--dry-run` first.

## Built with the Agent Builder Template

This agent started as a copy of the
[Agent Builder Template](https://github.com/kiran-criodo/agent-builder-template), which lets
anyone build an agent by describing it to an AI assistant. The original build instructions
are kept in `CREATE_AGENT_PROCESS.md` and Part A of `CLAUDE.md`.
