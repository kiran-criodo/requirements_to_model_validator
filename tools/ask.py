#!/usr/bin/env python3
"""
ask.py — grounded natural-language Q&A over the traceability + compliance results (task 7).

Answers questions like "which ASIL B requirements aren't verified?" or "which requirements
mention resume?" straight from the JSON the audits produce — so every answer is grounded in
real data, never guessed. Two ways to use it:

  * Explicit filters (robust, what the agent maps a question to):
        python3 tools/ask.py --asil "ASIL B" --unverified
        python3 tools/ask.py --status Gap
        python3 tools/ask.py --search resume
        python3 tools/ask.py --punchlist --priority P1
        python3 tools/ask.py --req 3c
        python3 tools/ask.py --orphans        --aspice        --summary

  * A free-text question (best-effort intent mapping for standalone use):
        python3 tools/ask.py -q "which ASIL B requirements aren't verified?"

Reads output/ACC_compliance_report.json (preferred) or output/ACC_traceability_matrix.json.
"""
from __future__ import annotations
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "output")
VERIFY_KEY = "Design ↔ Verification"


# --------------------------------------------------------------------------- #
# Load data
# --------------------------------------------------------------------------- #
def load(compliance=None, traceability=None):
    comp_path = compliance or os.path.join(OUT, "ACC_compliance_report.json")
    trace_path = traceability or os.path.join(OUT, "ACC_traceability_matrix.json")
    data = {"compliance": None, "traceability": None, "source": None}
    if os.path.exists(comp_path):
        data["compliance"] = json.load(open(comp_path, encoding="utf-8"))
        data["source"] = comp_path
    if os.path.exists(trace_path):
        data["traceability"] = json.load(open(trace_path, encoding="utf-8"))
        data["source"] = data["source"] or trace_path
    if not data["compliance"] and not data["traceability"]:
        sys.exit("No audit results found. Run tools/trace_audit.py (and tools/compliance_audit.py) first.")
    return data


def reqs(data):
    d = data["compliance"] or data["traceability"]
    return d["requirements"]


def has_compliance(data):
    return data["compliance"] is not None


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
def verified(r):
    return bool(r.get("chain", {}).get(VERIFY_KEY))


def filter_reqs(rs, status=None, asil=None, evidence=None, verif=None,
                signal=None, search=None):
    out = rs
    if status:
        out = [r for r in out if r["status"].lower() == status.lower()]
    if asil:
        a = asil.lower().replace("asil", "").strip()
        out = [r for r in out if r.get("asil", "").lower().replace("asil", "").strip() == a]
    if evidence:
        out = [r for r in out if (r.get("evidence") or "").lower().find(evidence.lower()) >= 0]
    if verif is True:
        out = [r for r in out if verified(r)]
    elif verif is False:
        out = [r for r in out if not verified(r)]
    if signal:
        s = signal.lower()
        out = [r for r in out if any(s == x.lower() for x in r.get("mentioned_signals", []))
               or any(s == x.lower() for x in r.get("missing_signals", []))]
    if search:
        q = search.lower()
        out = [r for r in out if q in (r["title"] + " " + r["text"]).lower()]
    return out


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def fmt_req(r, comp):
    bits = [r["status"]]
    if comp and r.get("asil"):
        bits.append(r["asil"])
        bits.append("verified" if verified(r) else "unverified")
    tgt = f" → {r['target']}" if r.get("target") else ""
    return f"  • {r['id_display']} — {r['title']}  [{', '.join(bits)}]{tgt}"


def print_reqs(rs, comp, header):
    print(header)
    if not rs:
        print("  (none)")
        return
    for r in rs:
        print(fmt_req(r, comp))


def print_summary(data):
    rs = reqs(data)
    n = len(rs)
    matched = sum(1 for r in rs if r["status"] == "Matched")
    partial = sum(1 for r in rs if r["status"] == "Partial")
    gap = sum(1 for r in rs if r["status"] == "Gap")
    print(f"Requirements: {n}   Matched: {matched}   Partial: {partial}   Gap: {gap}")
    if has_compliance(data):
        c = data["compliance"]
        ver = sum(1 for r in rs if verified(r))
        from collections import Counter
        asil = dict(Counter(r.get("asil", "?") for r in rs))
        p1 = sum(1 for it in c["punchlist"] if it["priority"] == "P1")
        print(f"ASIL: {asil}")
        print(f"Verification linkage: {ver}/{n}")
        print(f"Program stage: {c['meta']['stage']}   Punch-list: {len(c['punchlist'])} "
              f"({p1} P1)")
        orph = c["orphans"]
    else:
        orph = data["traceability"]["orphans"]
    print(f"Orphan logic: {len(orph['functional'])} functional, {len(orph['structural'])} structural")


def print_punchlist(data, priority=None):
    if not has_compliance(data):
        sys.exit("No compliance results — run tools/compliance_audit.py first.")
    items = data["compliance"]["punchlist"]
    if priority:
        items = [it for it in items if it["priority"].lower() == priority.lower()]
    print(f"Punch-list ({len(items)} item(s){', ' + priority if priority else ''}):")
    for it in items:
        reqs_s = ("  [" + ", ".join(it["requirements"]) + "]") if it["requirements"] else ""
        print(f"  {it['priority']} · {it['asil']} · {it['title']}{reqs_s}")
        print(f"        action: {it['action']}")


def print_orphans(data):
    orph = (data["compliance"] or data["traceability"])["orphans"]
    print("Orphan logic (model elements with no traced requirement):")
    for kind in ("functional", "structural"):
        for o in orph[kind]:
            print(f"  • {o['name']} ({o['type']}, SID {o['sid']}) — {kind}")
    if not orph["functional"] and not orph["structural"]:
        print("  (none)")


def print_aspice(data):
    if not has_compliance(data):
        sys.exit("No compliance results — run tools/compliance_audit.py first.")
    print("ASPICE SWE.1–6 work-product status:")
    for pid, (name, st) in data["compliance"]["aspice"].items():
        print(f"  {pid}  {st:12} {name}")


def print_req_detail(data, req_id):
    comp = has_compliance(data)
    q = req_id.lower().replace("requirement", "").replace(" ", "")
    matches = [r for r in reqs(data)
               if r["id"] == q or r["id_display"].lower().replace(" ", "").endswith(q)]
    if not matches:
        print(f"No requirement matching '{req_id}'.")
        return
    for r in matches:
        print(f"{r['id_display']} — {r['title']}")
        print(f"  status:   {r['status']}   evidence: {r.get('evidence')} ({r.get('confidence')})")
        print(f"  element:  {r.get('target')}")
        if comp and r.get("asil"):
            print(f"  ASIL:     {r['asil']} — {r.get('asil_rationale','')}")
            print("  ISO 26262-6 chain: " + ", ".join(
                f"{k} {'✓' if v else '✗'}" for k, v in r["chain"].items()))
        if r.get("missing_signals"):
            print(f"  missing signals: {', '.join(r['missing_signals'])}")


# --------------------------------------------------------------------------- #
# Free-text intent mapping (best-effort; the agent normally sets flags directly)
# --------------------------------------------------------------------------- #
def answer_question(data, question):
    q = question.lower()
    comp = has_compliance(data)

    # dispatch to non-requirement views first
    if any(k in q for k in ("aspice", "swe.", "work product")):
        return print_aspice(data)
    if "orphan" in q:
        return print_orphans(data)
    if "stage" in q and "program" in q or q.strip() in ("stage?", "what stage"):
        if comp:
            print(f"Program stage: {data['compliance']['meta']['stage']}")
        return
    if any(k in q for k in ("punch", "priority", "p1", "top finding", "highest")):
        pr = "P1" if ("p1" in q or "highest" in q or "priority 1" in q) else \
             "P2" if "p2" in q else "P3" if "p3" in q else None
        return print_punchlist(data, pr)
    if any(k in q for k in ("summary", "overview", "overall", "how are we")):
        return print_summary(data)

    # requirement filters (AND-combined)
    status = ("Gap" if any(k in q for k in ("gap", "not in the model", "not implemented",
                                            "missing from the model", "aren't in the model",
                                            "not yet in the model"))
              else "Partial" if "partial" in q
              else "Matched" if ("matched" in q or "fully traced" in q) else None)
    asil = ("ASIL D" if "asil d" in q else "ASIL C" if "asil c" in q
            else "ASIL B" if ("asil b" in q or "asil-b" in q) else
            "ASIL A" if "asil a" in q else "QM" if re.search(r"\bqm\b", q) else None)
    verif = (False if any(k in q for k in ("unverified", "not verified", "no verification",
                                           "aren't verified", "without test", "no test",
                                           "not tested", "lack verification"))
             else True if "verified" in q or "have tests" in q else None)
    evidence = ("link" if "link" in q else "naming" if "naming" in q
                else "semantic" if "semantic" in q else None)

    # a quoted phrase or a signal-like / capitalized token becomes a search term
    search = None
    mq = re.search(r'"([^"]+)"|\bmention[s]?\s+(\w+)|\babout\s+(\w+)', question)
    if mq:
        search = next(g for g in mq.groups() if g)
    elif not any([status, asil, verif is not None, evidence]):
        toks = re.findall(r"\b([A-Z][A-Za-z0-9_]{2,})\b", question)
        stop = {"Which", "What", "Requirement", "Requirements", "Model", "ASIL", "The", "Are"}
        toks = [t for t in toks if t not in stop]
        if toks:
            search = toks[0]

    rs = filter_reqs(reqs(data), status=status, asil=asil, evidence=evidence,
                     verif=verif, search=search)
    desc = []
    if asil: desc.append(asil)
    if status: desc.append(status)
    if verif is False: desc.append("unverified")
    if verif is True: desc.append("verified")
    if evidence: desc.append(f"{evidence}-matched")
    if search: desc.append(f'mentioning "{search}"')
    label = " ".join(desc) if desc else "matching"
    print_reqs(rs, comp, f"{len(rs)} requirement(s) {label}:")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Grounded Q&A over the audit results")
    ap.add_argument("-q", "--question", help="free-text question (best-effort mapping)")
    ap.add_argument("--status", choices=["Matched", "Partial", "Gap"])
    ap.add_argument("--asil", help='e.g. "ASIL B" or QM')
    ap.add_argument("--evidence", help="link | naming | semantic")
    ap.add_argument("--verified", action="store_true")
    ap.add_argument("--unverified", action="store_true")
    ap.add_argument("--signal", help="requirements naming this signal")
    ap.add_argument("--search", help="substring in requirement title/text")
    ap.add_argument("--req", help="detail for one requirement id, e.g. 3c or '3c (i)'")
    ap.add_argument("--orphans", action="store_true")
    ap.add_argument("--punchlist", action="store_true")
    ap.add_argument("--priority", choices=["P1", "P2", "P3"])
    ap.add_argument("--aspice", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--compliance-json"); ap.add_argument("--traceability-json")
    args = ap.parse_args()

    data = load(args.__dict__.get("compliance_json"), args.__dict__.get("traceability_json"))

    if args.question:
        return answer_question(data, args.question)
    if args.req:
        return print_req_detail(data, args.req)
    if args.orphans:
        return print_orphans(data)
    if args.aspice:
        return print_aspice(data)
    if args.punchlist or args.priority:
        return print_punchlist(data, args.priority)
    if args.summary:
        return print_summary(data)
    if any([args.status, args.asil, args.evidence, args.verified, args.unverified,
            args.signal, args.search]):
        verif = True if args.verified else False if args.unverified else None
        rs = filter_reqs(reqs(data), status=args.status, asil=args.asil,
                         evidence=args.evidence, verif=verif, signal=args.signal,
                         search=args.search)
        return print_reqs(rs, has_compliance(data), f"{len(rs)} requirement(s):")
    # default
    print_summary(data)


if __name__ == "__main__":
    main()
