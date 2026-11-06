# Workflow: Track LLM token usage and cost

## Purpose
Meter Claude API token usage and dollar cost for the agent — per call, per model, per day,
and cumulatively. This is infrastructure: it's ready for any step that calls an LLM, and can
also be used now for manual logging or cost estimation.

## Important scope note
The agent's current tools (`trace_audit.py`, `compliance_audit.py`, `ask.py`, `send_email.py`)
are **deterministic and make no LLM calls** — so there is nothing to meter yet. `token_usage.py`
starts recording the moment an LLM-backed step is added (or you log a call manually). Always
state this honestly: an empty usage report means "no LLM calls happened", not "tracking is broken".

## When to use
- "how many tokens / how much has this cost?", "token usage", "LLM cost", "usage report"
  → `python3 tools/token_usage.py summary`
- After (or inside) any future step that calls the Claude API → record the usage (see below).

## How to record usage

**From code (the intended path once a step calls the API).** Read the token counts straight
off the Anthropic response's `usage` object:

```python
from token_usage import UsageTracker          # tools/ is importable
tracker = UsageTracker()                        # appends to data/token_usage.jsonl
resp = client.messages.create(model="claude-opus-4-8", ...)
tracker.record_response(resp, label="semantic-requirement-match")
```

`record_response` reads `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, and
`cache_read_input_tokens` and prices them (cache writes at 1.25x input / reads at 0.1x input).

**From the CLI (manual logging / estimates):**
```
python3 tools/token_usage.py record --model claude-opus-4-8 --input 1200 --output 300 \
    --label "trace match"
```

## How to report
```
python3 tools/token_usage.py summary     # cumulative + per-model + per-day, with total $ cost
python3 tools/token_usage.py models      # the pricing table used for costing
```

## Inputs / outputs
- Log file: `data/token_usage.jsonl` (one JSON record per call). `data/` is gitignored, so the
  ledger stays local and is not committed. Override with `--log PATH` or `TOKEN_USAGE_LOG`.

## Validation
- Prices are USD per 1,000,000 tokens, from the Claude API reference (Opus 4.8 $5/$25, Sonnet 5
  $3/$15, Haiku 4.5 $1/$5, Fable 5 $10/$50). If Anthropic changes list prices, update `PRICING`
  in `tools/token_usage.py` — don't silently report stale costs.
- An unpriced model records `cost_usd: null` and is excluded from the cost total (the summary
  says how many such calls there were). Add the model to `PRICING` to fix.
- Report usage numbers from `token_usage.py summary` — never estimate token counts from memory.
