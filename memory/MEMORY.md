# Memory Index

This file is the index of everything the agent remembers. Each memory is its own `.md`
file in this folder; add one line here pointing to each, so it's easy to scan.

Memory is how the agent gets smarter over time. When the agent learns a useful fact, a
rule, or a better way to do something, it should save it here and add a pointer below.

## Shared memories (saved and shared with everyone)
<!-- Add one line per memory file, like:
- [Business terms](business-terms.md) — what our internal words mean
-->
- [Simulink parsing notes](simulink-parsing-notes.md) — how .slx/.slmx/.docx are parsed, the
  containment trick, Stateflow/SID gotchas, and the two ACC requirement docs.
- [Compliance audit notes](compliance-audit-notes.md) — ASIL/ISO 26262/ASPICE derivation rules,
  the SIL/HIL substring gotcha, and the honest ACC compliance result.

## Personal memories (kept private, not shared)
Files named `local_*.md` are personal to you and are never shared. Copy
`local_preferences.md.example` to `local_preferences.md` to set your own preferences.
