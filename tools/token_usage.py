#!/usr/bin/env python3
"""
token_usage.py — track LLM (Claude) token usage and cost for this agent.

The current audit tools (trace_audit, compliance_audit, ask) are deterministic and
make **no** LLM calls, so nothing is metered yet. This module is the meter: any step
that later calls the Claude API records its usage here, and the CLI reports per-run
and cumulative totals. It is also usable now for manual logging / cost estimation.

Pure Python standard library — no third-party packages.

Usage from code (wrap an Anthropic API call):
    from token_usage import UsageTracker
    tracker = UsageTracker()                      # appends to data/token_usage.jsonl
    resp = client.messages.create(model="claude-opus-4-8", ...)
    tracker.record_response(resp, label="semantic-match")   # reads resp.usage

Usage from the CLI:
    python3 tools/token_usage.py record --model claude-opus-4-8 \
        --input 1200 --output 300 --label "trace match"
    python3 tools/token_usage.py summary            # cumulative + per-model + per-day
    python3 tools/token_usage.py models             # show the pricing table

Pricing (USD per 1,000,000 tokens) is from the Claude API reference, cached
2026-06-24. Cache economics: a cache *write* costs 1.25x the input rate (5-minute
TTL) or 2x (1-hour TTL); a cache *read* costs 0.1x the input rate. Update PRICING
when Anthropic changes list prices. (Claude Sonnet 5 has an intro rate of $2/$10 per
1M through 2026-08-31; the list rate below is the conservative default.)
"""
import argparse
import datetime as _dt
import json
import os
import sys

# USD per 1,000,000 tokens: {model: (input_rate, output_rate)}
PRICING = {
    "claude-fable-5":    (10.0, 50.0),
    "claude-mythos-5":   (10.0, 50.0),
    "claude-opus-4-8":   (5.0, 25.0),
    "claude-opus-4-7":   (5.0, 25.0),
    "claude-opus-4-6":   (5.0, 25.0),
    "claude-sonnet-5":   (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5":  (1.0, 5.0),
}
_MILLION = 1_000_000
CACHE_WRITE_MULT = {"5m": 1.25, "1h": 2.0}
CACHE_READ_MULT = 0.1

DEFAULT_LOG = os.environ.get("TOKEN_USAGE_LOG", "data/token_usage.jsonl")


def compute_cost(model, input_tokens=0, output_tokens=0,
                 cache_write_tokens=0, cache_read_tokens=0, cache_ttl="5m"):
    """Cost in USD for one call. Returns None if the model isn't in PRICING."""
    if model not in PRICING:
        return None
    in_rate, out_rate = PRICING[model]
    write_mult = CACHE_WRITE_MULT.get(cache_ttl, 1.25)
    return (
        input_tokens * in_rate
        + output_tokens * out_rate
        + cache_write_tokens * in_rate * write_mult
        + cache_read_tokens * in_rate * CACHE_READ_MULT
    ) / _MILLION


class UsageTracker:
    """Append usage records to a JSONL log and compute their cost."""

    def __init__(self, log_path=DEFAULT_LOG):
        self.log_path = log_path

    def record(self, model, input_tokens=0, output_tokens=0,
               cache_write_tokens=0, cache_read_tokens=0, cache_ttl="5m",
               label=None):
        """Record one usage event; returns the written record (dict)."""
        cost = compute_cost(model, input_tokens, output_tokens,
                            cache_write_tokens, cache_read_tokens, cache_ttl)
        rec = {
            "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "model": model,
            "label": label or "",
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "cache_write_tokens": int(cache_write_tokens),
            "cache_read_tokens": int(cache_read_tokens),
            "cost_usd": round(cost, 6) if cost is not None else None,
        }
        os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        return rec

    def record_response(self, response, model=None, label=None, cache_ttl="5m"):
        """Record usage from an Anthropic SDK response object (reads ``response.usage``).

        Falls back to the response's own ``model`` field when ``model`` is omitted.
        Cache token fields are optional and default to 0 when absent."""
        usage = getattr(response, "usage", None)
        if usage is None:
            raise ValueError("response has no .usage; pass token counts to record() instead")
        model = model or getattr(response, "model", None)
        if not model:
            raise ValueError("could not determine model; pass model=...")

        def _u(name):
            return int(getattr(usage, name, 0) or 0)

        return self.record(
            model=model,
            input_tokens=_u("input_tokens"),
            output_tokens=_u("output_tokens"),
            cache_write_tokens=_u("cache_creation_input_tokens"),
            cache_read_tokens=_u("cache_read_input_tokens"),
            cache_ttl=cache_ttl,
            label=label,
        )


def _load(log_path):
    if not os.path.exists(log_path):
        return []
    out = []
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def _fmt_usd(x):
    return f"${x:,.4f}"


def _summary(records):
    total_in = total_out = total_cache_w = total_cache_r = 0
    total_cost = 0.0
    unknown_cost = 0
    per_model = {}
    per_day = {}
    for r in records:
        total_in += r.get("input_tokens", 0)
        total_out += r.get("output_tokens", 0)
        total_cache_w += r.get("cache_write_tokens", 0)
        total_cache_r += r.get("cache_read_tokens", 0)
        c = r.get("cost_usd")
        if c is None:
            unknown_cost += 1
        else:
            total_cost += c
        m = r.get("model", "?")
        pm = per_model.setdefault(m, {"calls": 0, "in": 0, "out": 0, "cost": 0.0})
        pm["calls"] += 1
        pm["in"] += r.get("input_tokens", 0)
        pm["out"] += r.get("output_tokens", 0)
        pm["cost"] += c or 0.0
        day = (r.get("ts") or "")[:10]
        pd = per_day.setdefault(day, {"calls": 0, "cost": 0.0})
        pd["calls"] += 1
        pd["cost"] += c or 0.0
    return {
        "calls": len(records),
        "input_tokens": total_in, "output_tokens": total_out,
        "cache_write_tokens": total_cache_w, "cache_read_tokens": total_cache_r,
        "cost_usd": total_cost, "unknown_cost_calls": unknown_cost,
        "per_model": per_model, "per_day": per_day,
    }


def _print_summary(s, log_path):
    print(f"Token usage — {log_path}")
    print(f"  Calls:            {s['calls']:,}")
    print(f"  Input tokens:     {s['input_tokens']:,}")
    print(f"  Output tokens:    {s['output_tokens']:,}")
    if s["cache_write_tokens"] or s["cache_read_tokens"]:
        print(f"  Cache write toks: {s['cache_write_tokens']:,}")
        print(f"  Cache read toks:  {s['cache_read_tokens']:,}")
    print(f"  Total cost:       {_fmt_usd(s['cost_usd'])}")
    if s["unknown_cost_calls"]:
        print(f"  ({s['unknown_cost_calls']} call(s) had an unpriced model — cost excluded)")
    if s["per_model"]:
        print("\n  By model:")
        for m, pm in sorted(s["per_model"].items(), key=lambda kv: -kv[1]["cost"]):
            print(f"    {m:20} {pm['calls']:>4} calls  "
                  f"in {pm['in']:>10,}  out {pm['out']:>10,}  {_fmt_usd(pm['cost'])}")
    if len(s["per_day"]) > 1:
        print("\n  By day:")
        for day in sorted(s["per_day"]):
            pd = s["per_day"][day]
            print(f"    {day}  {pd['calls']:>4} calls  {_fmt_usd(pd['cost'])}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Track LLM token usage and cost")
    ap.add_argument("--log", default=DEFAULT_LOG, help=f"JSONL log path (default {DEFAULT_LOG})")
    sub = ap.add_subparsers(dest="cmd")

    r = sub.add_parser("record", help="append one usage record")
    r.add_argument("--model", required=True)
    r.add_argument("--input", type=int, default=0, help="input (uncached) tokens")
    r.add_argument("--output", type=int, default=0)
    r.add_argument("--cache-write", type=int, default=0, help="cache creation tokens")
    r.add_argument("--cache-read", type=int, default=0)
    r.add_argument("--ttl", choices=["5m", "1h"], default="5m")
    r.add_argument("--label", default="")

    sub.add_parser("summary", help="print cumulative + per-model + per-day totals")
    sub.add_parser("models", help="print the pricing table")

    args = ap.parse_args(argv)

    if args.cmd == "models":
        print("Pricing (USD per 1,000,000 tokens):")
        print(f"  {'model':20} {'input':>8} {'output':>8}")
        for m, (i, o) in PRICING.items():
            print(f"  {m:20} {i:>8.2f} {o:>8.2f}")
        print("\n  Cache: write = 1.25x input (5m TTL) / 2x (1h); read = 0.1x input.")
        return 0

    if args.cmd == "record":
        if args.model not in PRICING:
            print(f"Warning: '{args.model}' is not in the pricing table — cost will be null.",
                  file=sys.stderr)
        tracker = UsageTracker(args.log)
        rec = tracker.record(
            model=args.model, input_tokens=args.input, output_tokens=args.output,
            cache_write_tokens=args.cache_write, cache_read_tokens=args.cache_read,
            cache_ttl=args.ttl, label=args.label,
        )
        cost = rec["cost_usd"]
        print(f"Recorded {rec['model']}: in={rec['input_tokens']:,} out={rec['output_tokens']:,}"
              + (f"  cost={_fmt_usd(cost)}" if cost is not None else "  cost=unknown")
              + f"  -> {args.log}")
        return 0

    # default: summary
    records = _load(args.log)
    if not records:
        print(f"No usage recorded yet ({args.log} is empty or missing).")
        print("Nothing to report — the current audit tools make no LLM calls.")
        return 0
    _print_summary(_summary(records), args.log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
