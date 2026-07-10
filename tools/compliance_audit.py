#!/usr/bin/env python3
"""
compliance_audit.py — ASIL / ISO 26262 / ASPICE compliance cross-check + prioritized
punch-list (tasks 5-6), layered on top of the workflow-1 traceability audit.

Reuses tools/trace_audit.py for parsing + matching, then adds:
  * ASIL classification per requirement (derived from ASIL_Classification_Standard).
  * ISO 26262-6 Part 6 traceability-chain check (Req -> Arch -> Design -> Verification
    -> Safety case) from the links and artifacts actually present.
  * ASPICE SWE.1-6 work-product status, derived from which model artifacts exist.
  * A prioritized punch-list ranked by ASIL x program stage.

Everything is derived from detectable facts — no findings are invented. Where the source
requirements carry no explicit ASIL tag (as in Requirement.docx), ASIL is marked *indicative*
(feature-level allocation per the standard's worked ACC classification).

Usage:
    python3 tools/compliance_audit.py                 # ACC example, stage auto-detected
    python3 tools/compliance_audit.py --stage 6       # override program stage (1-12)
    python3 tools/compliance_audit.py --req <docx> --model <slx> --links <slmx>
"""
from __future__ import annotations
import argparse, html, json, os, re, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trace_audit as ta  # noqa: E402

# --------------------------------------------------------------------------- #
# Program stage taxonomy (Program_Stage_Taxonomy.docx, condensed)
# --------------------------------------------------------------------------- #
PROGRAM_STAGES = {
    1: "Requirements Definition", 2: "Architecture & ASIL/QM Allocation",
    3: "Model Design (MBD)", 4: "SLDD & AUTOSAR Interface Mapping",
    5: "Model Advisor / Static Checks", 6: "Model-in-the-Loop (MIL) Test",
    7: "Code Generation", 8: "SIL / PIL", 9: "Static Code Analysis",
    10: "Hardware-in-the-Loop (HIL) Test", 11: "V&V Closure", 12: "Release / Sign-off",
}
ASIL_WEIGHT = {"QM": 0, "ASIL A": 1, "ASIL B": 2, "ASIL C": 3, "ASIL D": 4}


# --------------------------------------------------------------------------- #
# ASIL classification (per ASIL_Classification_Standard worked ACC example)
# --------------------------------------------------------------------------- #
def classify_asil(req):
    """Indicative, feature-level ASIL. ISO 26262-3 worked ACC classification puts the
    longitudinal speed/gap-control path at ASIL B (S2/E4/C2); comfort-only mode
    housekeeping with no actuation authority is Quality Managed."""
    title = req["title"].lower()
    full = (req["title"] + " " + req["text"]).lower()
    # Match the safe-state test against the TITLE only, so a parent requirement that merely
    # *lists* the modes (e.g. "...OFF Mode, STANDBY Mode & ON Mode...") isn't down-graded.
    comfort_kw = ("off mode", "standby", "default state", "set-speed", "set speed")
    safety_kw = ("gap", "following", "follow", "resume", "lead vehicle",
                 "decel", "brake", "throttle", "torque")
    if any(k in title for k in comfort_kw):
        return "QM", ("Non-actuating mode housekeeping (disengaged / standby) with no direct "
                      "actuation authority — Quality Managed.")
    if any(k in full for k in safety_kw):
        return "ASIL B", ("Longitudinal gap/speed-control path — ASIL B per ISO 26262-3 "
                          "worked ACC classification (S2/E4/C2).")
    return "ASIL B", "Part of the ASIL B ACC function (feature-level allocation)."


# --------------------------------------------------------------------------- #
# Artifact presence -> ASPICE SWE.1-6 status + program-stage auto-detect
# --------------------------------------------------------------------------- #
def scan_artifacts(model_path, links):
    """Detect which MBD work products exist next to the model."""
    d = os.path.dirname(model_path)
    def has(pred):
        try:
            for root, _dirs, files in os.walk(d):
                for f in files:
                    if pred(f, os.path.join(root, f)):
                        return True
        except OSError:
            pass
        return False
    code_gen = any(n.endswith("_ert_rtw") for n in os.listdir(d)) if os.path.isdir(d) else False
    # Match SIL/HIL only as a delimited token, so "rtwhilite.js" / "hilite_warning.png"
    # (from "highlight") don't get mistaken for HIL test results.
    def token(word):
        rx = re.compile(r"(?:^|[^a-z])" + word + r"(?:[^a-z]|$)")
        return lambda f, p: bool(rx.search(f.lower()))
    return {
        "requirements": True,                                   # the .docx we parsed
        "linkset": bool(links),                                 # .slmx present
        "sldd": has(lambda f, p: f.lower().endswith(".sldd")),
        "model_advisor": has(lambda f, p: "mareport" in f.lower()
                             or ("modeladvisor" in p.lower() and f == "report.html")),
        "code_gen": code_gen,
        "tests": has(lambda f, p: any(k in f.lower()
                     for k in ("harness", "sltest", ".mldatx", "_test", "coverage"))),
        "sil_results": has(token("sil")),
        "hil_results": has(token("hil")),
    }


def aspice_status(art):
    def s(done, partial=False):
        return "complete" if done else ("in-progress" if partial else "not-started")
    return {
        "SWE.1": ("Software Requirements Analysis", s(art["requirements"] and art["linkset"])),
        "SWE.2": ("Software Architectural Design", s(art["sldd"], art["requirements"])),
        "SWE.3": ("Detailed Design & Unit Construction", s(art["model_advisor"], True)),
        "SWE.4": ("Software Unit Verification (MIL)", s(art["tests"])),
        "SWE.5": ("Integration & Integration Test (SIL/PIL)", s(art["sil_results"], art["code_gen"])),
        "SWE.6": ("Software Qualification Test (HIL)", s(art["hil_results"])),
    }


def detect_stage(art):
    """Highest stage for which evidence exists (ignoring skipped earlier stages)."""
    if art["hil_results"]:
        return 10
    if art["code_gen"]:
        return 7
    if art["model_advisor"]:
        return 5
    if art["sldd"]:
        return 4
    return 3


# --------------------------------------------------------------------------- #
# ISO 26262-6 Part 6 traceability chain (per requirement)
# --------------------------------------------------------------------------- #
def iso_chain(res, tests_linked):
    """Which links of the bidirectional trace chain exist for this requirement."""
    traced = res["status"] in ("Matched", "Partial") and bool(res["target"])
    leaf = traced  # matched to a concrete subsystem/state = detailed-design element
    return {
        "Req ↔ Architecture": traced,
        "Architecture ↔ Design": leaf,
        "Design ↔ Verification": bool(tests_linked),
        "Verification ↔ Safety case": bool(tests_linked),
    }


# --------------------------------------------------------------------------- #
# Prioritized punch-list (ASIL x program stage)
# --------------------------------------------------------------------------- #
def build_punchlist(rows, orphans, art, stage):
    """Rank findings by ASIL weight and how late in the program the gap sits."""
    items = []
    late = stage >= 6  # verification expected from stage 6 (MIL) onward

    # 1) Missing verification linkage — the dominant finding here.
    unverified = [r for r in rows if not r["chain"]["Design ↔ Verification"]]
    by_asil = {}
    for r in unverified:
        by_asil.setdefault(r["asil"], []).append(r)
    for asil, group in sorted(by_asil.items(), key=lambda kv: -ASIL_WEIGHT.get(kv[0], 0)):
        w = ASIL_WEIGHT.get(asil, 0)
        score = w * 3 + (4 if late else 1)
        items.append({
            "score": score,
            "asil": asil,
            "title": f"No requirement-based verification for {len(group)} {asil} requirement(s)",
            "detail": ("ISO 26262-6 Design↔Verification link absent and ASPICE SWE.4 "
                       "(MIL) has no test cases. "
                       + ("Program is at Code Generation while MIL verification is empty."
                          if late else "")),
            "requirements": [g["id_display"] for g in group],
            "action": ("Create requirement-linked MIL test cases"
                       + (" (MC/DC coverage required for ASIL C/D)" if w >= 3 else "")
                       + " and re-run the trace audit."),
        })

    # 2) Orphan logic on/near the safety path.
    for o in orphans["functional"] + orphans["structural"]:
        w = 2  # unclassified orphan on an ASIL B feature
        score = w * 2 + (2 if late else 1)
        items.append({
            "score": score, "asil": "unclassified",
            "title": f"Orphan logic: {o['name']} ({o['type']})",
            "detail": ("Model element with no requirement link (SID "
                       f"{o['sid']}). On an ASIL B feature, untraced logic must be "
                       "justified or linked."),
            "requirements": [],
            "action": "Link to a requirement or document as intentionally untraced.",
        })

    # 3) ASPICE process-capability gaps (program level).
    for pid, (name, st) in aspice_status(art).items():
        if st == "not-started":
            score = (3 if pid in ("SWE.4",) else 1) + (1 if late else 0)
            items.append({
                "score": score, "asil": "process",
                "title": f"ASPICE {pid} not started — {name}",
                "detail": f"No work products found for {pid}.",
                "requirements": [],
                "action": f"Plan and execute {pid} work products for the current stage.",
            })

    items.sort(key=lambda x: -x["score"])
    # bucket into P1/P2/P3 by score tiers
    for it in items:
        it["priority"] = "P1" if it["score"] >= 8 else "P2" if it["score"] >= 4 else "P3"
    return items


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
_EXTRA_CSS = """
.asil{font-family:ui-monospace,Menlo,monospace;font-size:11px;font-weight:700;
  padding:2px 8px;border-radius:6px;white-space:nowrap;}
.asil-QM{color:var(--text-dim);background:var(--surface-2);border:1px solid var(--border);}
.asil-A{color:#2f6f8f;background:var(--good-bg);}
.asil-B{color:var(--warn);background:var(--warn-bg);}
.asil-C{color:#d9761f;background:var(--warn-bg);}
.asil-D{color:var(--bad);background:var(--bad-bg);}
.prio{font-weight:700;font-size:11.5px;padding:2px 9px;border-radius:6px;font-family:ui-monospace,monospace;}
.prio-P1{color:#fff;background:var(--bad);} .prio-P2{color:#3a2a00;background:var(--warn);}
.prio-P3{color:var(--text-dim);background:var(--surface-2);border:1px solid var(--border);}
.chain{display:flex;gap:6px;flex-wrap:wrap;}
.link{font-size:11px;padding:2px 8px;border-radius:6px;white-space:nowrap;}
.link.ok{color:var(--good);background:var(--good-bg);} .link.no{color:var(--bad);background:var(--bad-bg);}
.swe{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;}
.swecard{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:13px 15px;
  box-shadow:var(--shadow);border-top:3px solid var(--border);}
.swecard.complete{border-top-color:var(--good);} .swecard.in-progress{border-top-color:var(--warn);}
.swecard.not-started{border-top-color:var(--bad);}
.swecard .id{font-family:ui-monospace,monospace;font-weight:700;font-size:13px;}
.swecard .nm{font-size:12px;color:var(--text-dim);margin:3px 0 8px;line-height:1.35;}
.swecard .st{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;}
.swecard.complete .st{color:var(--good);} .swecard.in-progress .st{color:var(--warn);}
.swecard.not-started .st{color:var(--bad);}
.pl-detail{color:var(--text-dim);font-size:12.5px;margin-top:3px;}
.pl-action{color:var(--text);font-size:12.5px;margin-top:5px;}
.pl-action b{color:var(--accent);}
.stagebar{display:flex;gap:3px;margin-top:10px;flex-wrap:wrap;}
.stg{flex:1;min-width:20px;height:26px;border-radius:4px;background:var(--surface-2);
  border:1px solid var(--border);font-size:10px;display:flex;align-items:center;justify-content:center;
  color:var(--text-dim);font-family:ui-monospace,monospace;}
.stg.done{background:var(--good-bg);color:var(--good);border-color:var(--good);}
.stg.skip{background:var(--bad-bg);color:var(--bad);border-color:var(--bad);}
.stg.now{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:700;}
.caveat{font-size:12px;color:var(--text-dim);background:var(--surface-2);border:1px solid var(--border);
  border-radius:8px;padding:10px 13px;margin:10px 0 4px;}
"""


def render(rows, orphans, punch, aspice, art, meta):
    e = ta._e
    n = len(rows)
    asil_counts = {}
    for r in rows:
        asil_counts[r["asil"]] = asil_counts.get(r["asil"], 0) + 1
    verified = sum(1 for r in rows if r["chain"]["Design ↔ Verification"])
    p1 = sum(1 for it in punch if it["priority"] == "P1")
    stage = meta["stage"]

    # KPI tiles
    asil_b = asil_counts.get("ASIL B", 0)
    tiles = f"""
      <div class="tile stripe s-bad"><div class="lbl">Priority-1 findings</div>
        <div class="val mono">{p1}</div><div class="note">highest ASIL × stage risk</div></div>
      <div class="tile stripe s-warn"><div class="lbl">ASIL B requirements</div>
        <div class="val mono">{asil_b}</div><div class="note">of {n} · indicative allocation</div></div>
      <div class="tile stripe s-bad"><div class="lbl">Verification coverage</div>
        <div class="val mono">{verified}/{n}</div><div class="note">Design↔Verification links present</div></div>
      <div class="tile stripe s-accent"><div class="lbl">Program stage</div>
        <div class="val mono">{stage}</div><div class="note">{e(PROGRAM_STAGES[stage])}</div></div>
    """

    # Program stage bar — "done" derived from detected artifacts; any earlier stage
    # without evidence is shown as skipped.
    done = {1}
    if art["sldd"]:
        done |= {2, 4}
    if art["model_advisor"] or art["code_gen"]:
        done |= {3}
    if art["model_advisor"]:
        done |= {5}
    if art["tests"]:
        done |= {6}
    if art["code_gen"]:
        done |= {7}
    if art["sil_results"]:
        done |= {8}
    if art["hil_results"]:
        done |= {10}
    stg_cells = []
    for i in range(1, 13):
        cls = ("now" if i == stage else "done" if i in done
               else "skip" if i < stage else "")
        stg_cells.append(f'<div class="stg {cls}" title="{e(PROGRAM_STAGES[i])}">{i}</div>')
    stage_bar = '<div class="stagebar">' + "".join(stg_cells) + "</div>"

    # Punch-list
    pl = []
    for it in punch:
        reqs = (' · <span class="mono" style="font-size:11.5px">'
                + e(", ".join(it["requirements"])) + "</span>") if it["requirements"] else ""
        badge = (f'<span class="asil asil-{it["asil"].replace("ASIL ","")}">{e(it["asil"])}</span>'
                 if it["asil"].startswith("ASIL") or it["asil"] == "QM"
                 else f'<span class="chip">{e(it["asil"])}</span>')
        pl.append(f"""
        <tr>
          <td><span class="prio prio-{it['priority']}">{it['priority']}</span></td>
          <td>{badge}</td>
          <td><div style="font-weight:600">{e(it['title'])}</div>
            <div class="pl-detail">{e(it['detail'])}{reqs}</div>
            <div class="pl-action"><b>Action:</b> {e(it['action'])}</div></td>
        </tr>""")

    # ISO chain per requirement
    chain_rows = []
    for r in rows:
        links = "".join(
            f'<span class="link {"ok" if v else "no"}">{"✓" if v else "✗"} {e(k)}</span>'
            for k, v in r["chain"].items())
        chain_rows.append(f"""
        <tr>
          <td><div class="req-id mono">{e(r['id_display'])}</div>
            <div class="req-title">{e(r['title'])}</div></td>
          <td><span class="asil asil-{r['asil'].replace('ASIL ','')}">{e(r['asil'])}</span></td>
          <td><div class="chain">{links}</div></td>
        </tr>""")

    # ASPICE SWE cards
    swe = []
    for pid, (name, st) in aspice.items():
        label = {"complete": "Complete", "in-progress": "In progress", "not-started": "Not started"}[st]
        swe.append(f'<div class="swecard {st}"><div class="id">{e(pid)}</div>'
                   f'<div class="nm">{e(name)}</div><div class="st">{label}</div></div>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(meta['model'])} — Compliance & Punch-list</title>
<style>{ta._CSS}{_EXTRA_CSS}</style></head><body>
<div class="wrap">
  <header class="top">
    <div>
      <p class="eyebrow">ISO 26262 / ASPICE Compliance Cross-check</p>
      <h1>{e(meta['model'])} — Compliance & Prioritized Punch-list</h1>
      <p class="sub">{e(meta['req_doc'])} &nbsp;·&nbsp; ASIL / ISO 26262-6 Part 6 / ASPICE SWE.1–6</p>
    </div>
    <div class="meta">
      <button class="toggle" id="themeBtn">◐ Theme</button><br>
      <span>Generated <b>{e(meta['generated'])}</b></span><br>
      <span>{n} requirements · stage {stage} — {e(PROGRAM_STAGES[stage])}</span>
    </div>
  </header>

  <div class="kpis">{tiles}</div>

  <div class="caveat"><b>Program stage</b> (auto-detected from artifacts; override with
    <span class="mono">--stage N</span>). Green = evidence found, red = skipped, blue = current.
    {stage_bar}</div>

  <h2>Prioritized punch-list — ranked by ASIL × program stage</h2>
  <div class="tablecard"><div class="scroll"><table>
    <thead><tr><th>Priority</th><th>ASIL</th><th>Finding &amp; recommended action</th></tr></thead>
    <tbody>{''.join(pl)}</tbody>
  </table></div></div>

  <h2>ISO 26262-6 Part 6 — bidirectional traceability chain</h2>
  <div class="tablecard"><div class="scroll"><table>
    <thead><tr><th>Requirement</th><th>ASIL</th><th>Trace chain</th></tr></thead>
    <tbody>{''.join(chain_rows)}</tbody>
  </table></div></div>

  <h2>ASPICE SWE.1–6 — work-product status</h2>
  <div class="swe">{''.join(swe)}</div>

  <footer>
    <b>Scope:</b> tasks 5–6 — ASIL classification, ISO 26262-6 Part 6 trace-chain check,
    ASPICE SWE.1–6 status, and ASIL×stage prioritization. Built on the workflow-1
    traceability audit.<br>
    <b>ASIL note:</b> the source requirements carry no explicit ASIL tag, so ASIL here is
    <em>indicative</em> — feature-level allocation derived from the ASIL_Classification_Standard
    worked ACC example (ACC longitudinal control = ASIL B). Confirm with a formal S/E/C
    assessment.<br>
    Generated by <span class="mono">tools/compliance_audit.py</span>.
  </footer>
</div>
<script>{ta._JS}</script>
</body></html>"""


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    acc = os.path.join(here, "resources", "ACC (Adaptive Cruise Control)")
    ap = argparse.ArgumentParser(description="ASIL / ISO 26262 / ASPICE compliance audit")
    ap.add_argument("--req", default=os.path.join(acc, "Requirement.docx"))
    ap.add_argument("--model", default=os.path.join(acc, "ACC_Project.slx"))
    ap.add_argument("--links", default=os.path.join(acc, "ACC_Project.slmx"))
    ap.add_argument("--stage", type=int, default=None, help="program stage 1-12 (auto if omitted)")
    ap.add_argument("--out", default=os.path.join(here, "output", "ACC_compliance_report.html"))
    ap.add_argument("--json", default=os.path.join(here, "output", "ACC_compliance_report.json"))
    args = ap.parse_args()

    for label, path in (("requirements", args.req), ("model", args.model)):
        if not os.path.exists(path):
            sys.exit(f"ERROR: {label} file not found: {path}")

    reqs = ta.parse_requirements(args.req)
    model = ta.parse_model(args.model)
    links = ta.parse_links(args.links)
    results, orphans = ta.audit(reqs, model, links)

    art = scan_artifacts(args.model, links)
    # No .slmx link here carries a verification/test type — all are "Implement".
    tests_linked = art["tests"] and any(lk["type"].lower() in ("verify", "test") for lk in links)
    stage = args.stage if args.stage else detect_stage(art)

    rows = []
    for res, req in zip(results, reqs):
        asil, rationale = classify_asil(req)
        rows.append({**res, "asil": asil, "asil_rationale": rationale,
                     "chain": iso_chain(res, tests_linked)})

    aspice = aspice_status(art)
    punch = build_punchlist(rows, orphans, art, stage)

    meta = {
        "model": re.sub(r"\.slx$", "", os.path.basename(args.model)),
        "req_doc": os.path.basename(args.req),
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "stage": stage,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(rows, orphans, punch, aspice, art, meta))
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "artifacts": art, "aspice": aspice,
                   "requirements": rows, "punchlist": punch, "orphans": orphans},
                  f, indent=2)

    p1 = sum(1 for it in punch if it["priority"] == "P1")
    print(f"Program stage: {stage} ({PROGRAM_STAGES[stage]})")
    print(f"ASIL B requirements: {sum(1 for r in rows if r['asil']=='ASIL B')}/{len(rows)}")
    print(f"Verification linkage: {sum(1 for r in rows if r['chain']['Design ↔ Verification'])}/{len(rows)}")
    print(f"ASPICE not-started: {[k for k,(_,s) in aspice.items() if s=='not-started']}")
    print(f"Punch-list: {len(punch)} findings ({p1} P1)")
    print(f"Report -> {args.out}")
    print(f"JSON   -> {args.json}")


if __name__ == "__main__":
    main()
