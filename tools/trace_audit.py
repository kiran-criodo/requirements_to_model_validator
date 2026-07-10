#!/usr/bin/env python3
"""
trace_audit.py — Requirement-to-Model traceability audit (tasks 1-4).

Parses a requirements document (.docx), a Simulink model (.slx) and, if present,
the Simulink Requirements link set (.slmx) — all as zipped XML, no MATLAB needed —
then matches each requirement to the model element(s) that implement it and flags
gaps, orphan logic and partial signal coverage. Renders a self-contained interactive
HTML dashboard plus a JSON traceability matrix.

Usage:
    python3 tools/trace_audit.py            # runs on the bundled ACC example
    python3 tools/trace_audit.py --req <docx> --model <slx> [--links <slmx>]
                                 [--out <html>] [--json <json>]
"""
from __future__ import annotations
import argparse, html, json, os, re, sys, zipfile
from datetime import datetime, timezone

# --------------------------------------------------------------------------- #
# Generic helpers
# --------------------------------------------------------------------------- #
def _read_zip_member(path: str, member_pred) -> str:
    """Return the first zip member whose name matches member_pred(name)->bool."""
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if member_pred(n):
                return z.read(n).decode("utf-8", "ignore")
    return ""


def _strip_tags(xml: str) -> str:
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(xml)


# --------------------------------------------------------------------------- #
# Task 1 — parse requirements
# --------------------------------------------------------------------------- #
# Matches headings like "Requirement 1– Lead Vehicle:" or
# "Requirement 3c (i) – LeadVehicle_Detected_Follow (ACC ON MODE):"
_REQ_HEADING = re.compile(
    r"^Requirement\s+([0-9]+[a-z]?(?:\s*\([ivx]+\))?)\s*[–\-:]\s*(.*?)\s*:?\s*$",
    re.IGNORECASE,
)


def _norm_req_id(raw: str) -> str:
    """'3c (i)' -> '3c(i)', '1' -> '1' — a stable comparable id."""
    return re.sub(r"\s+", "", raw).lower()


def parse_requirements(docx_path: str):
    text = _strip_tags(_read_zip_member(docx_path, lambda n: n == "word/document.xml"))
    lines = [ln.rstrip() for ln in text.splitlines()]
    reqs, cur = [], None
    for ln in lines:
        m = _REQ_HEADING.match(ln.strip())
        if m:
            cur = {
                "id": _norm_req_id(m.group(1)),
                "id_display": "Requirement " + m.group(1).strip(),
                "title": m.group(2).strip(),
                "body_lines": [],
            }
            reqs.append(cur)
        elif cur is not None and ln.strip():
            cur["body_lines"].append(ln.strip())
    for r in reqs:
        r["text"] = " ".join([r["title"]] + r["body_lines"]).strip()
        del r["body_lines"]
    return reqs


# --------------------------------------------------------------------------- #
# Task 2 — parse Simulink model (.slx)
# --------------------------------------------------------------------------- #
def parse_model(slx_path: str):
    """Return dict with blocks, signals, subsystems, stateflow states, sid_index.

    Subsystem containment is recovered from the file naming scheme: the children
    of a SubSystem with SID N live in ``simulink/systems/system_N.xml`` (``system_root``
    for the top level). ``parent_of`` maps each block's SID to its owning SubSystem SID.
    """
    with zipfile.ZipFile(slx_path) as z:
        names = z.namelist()
        systems = {n: z.read(n).decode("utf-8", "ignore")
                   for n in names if re.match(r"simulink/systems/system_\w+\.xml$", n)}
        sf_xml = "".join(z.read(n).decode("utf-8", "ignore")
                         for n in names if re.match(r"simulink/stateflow/chart_\w+\.xml$", n))

    blocks, signals = [], set()
    sid_index = {}   # sid -> {name, type, kind}
    parent_of = {}   # child sid -> owning subsystem sid (None at root)
    for fname, content in systems.items():
        key = re.search(r"system_(\w+)\.xml$", fname).group(1)
        parent_sid = None if key == "root" else key
        for m in re.finditer(
            r'<Block\b[^>]*BlockType="([^"]+)"[^>]*Name="([^"]+)"[^>]*SID="([^"]+)"',
            content,
        ):
            btype = m.group(1)
            name = re.sub(r"\s+", " ", html.unescape(m.group(2))).strip()
            sid = m.group(3)
            kind = ("subsystem" if btype == "SubSystem"
                    else "signal" if btype in ("Inport", "Outport")
                    else "block")
            blocks.append({"sid": sid, "type": btype, "name": name,
                           "kind": kind, "parent": parent_sid})
            sid_index[sid] = {"name": name, "type": btype, "kind": kind}
            parent_of[sid] = parent_sid
            if btype in ("Inport", "Outport"):
                signals.add(name)

    # Stateflow states. Nested states break a naive <state>...</state> match, so
    # assign each <state SSID=..> the first labelString before the next <state> tag.
    def _first_line(raw):
        txt = html.unescape(re.sub(r"<[^>]+>", "", raw)).strip().splitlines()
        return txt[0].strip() if txt else ""

    state_pos = [(m.start(), m.group(1))
                 for m in re.finditer(r'<state\b[^>]*\bSSID="([^"]+)"', sf_xml)]
    label_pos = [(m.start(), _first_line(m.group(1)))
                 for m in re.finditer(r'<P Name="labelString">(.*?)</P>', sf_xml, re.S)]
    states = {}  # ssid -> name
    for i, (pos, ssid) in enumerate(state_pos):
        nxt = state_pos[i + 1][0] if i + 1 < len(state_pos) else len(sf_xml)
        for lp, lname in label_pos:
            if pos < lp < nxt:
                if lname and not lname.startswith("["):   # skip transition conditions
                    states[ssid] = lname
                break

    return {
        "blocks": blocks,
        "signals": signals,
        "subsystems": [b for b in blocks if b["kind"] == "subsystem"],
        "states": states,          # ssid -> name
        "sid_index": sid_index,
        "parent_of": parent_of,
    }


# --------------------------------------------------------------------------- #
# Task 2b — parse existing requirement links (.slmx)
# --------------------------------------------------------------------------- #
def parse_links(slmx_path: str):
    if not slmx_path or not os.path.exists(slmx_path):
        return []
    data = _read_zip_member(slmx_path, lambda n: n.endswith("slrequirements/data.xml"))
    links = []
    for block in re.split(r"<items ", data)[1:]:
        idm = re.search(r"<id>([^<]+)</id>", block)
        desc = re.search(r"<description>(.*?)</description>", block, re.S)
        dest = re.search(r"<artifactId>([^<]+)</artifactId>", block)
        typ = re.search(r"<typeName>([^<]+)</typeName>", block)
        if not idm:
            continue
        desc_txt = html.unescape(re.sub(r"\s+", " ", desc.group(1))).strip() if desc else ""
        hm = _REQ_HEADING.match(desc_txt)
        links.append({
            "model_id": idm.group(1).strip(),
            "req_id": _norm_req_id(hm.group(1)) if hm else None,
            "type": typ.group(1) if typ else "",
            "dest": dest.group(1) if dest else "",
            "desc": desc_txt,
        })
    return links


def resolve_target(model_id: str, model):
    """Resolve a .slmx model_id (e.g. ':36:11') to a human-readable element."""
    parts = [p for p in model_id.split(":") if p]
    if not parts:
        return "(unresolved)"
    last = parts[-1]
    states, sid_index = model["states"], model["sid_index"]
    if len(parts) > 1 and last in states:          # nested Stateflow state
        parent = sid_index.get(parts[0], {}).get("name", parts[0])
        return f"{parent} / {states[last]}"
    if last in sid_index:
        return sid_index[last]["name"]
    if last in states:
        return states[last]
    return f"SID {model_id}"


# --------------------------------------------------------------------------- #
# Task 3 & 4 — match requirements to model elements, flag gaps/orphans/partials
# --------------------------------------------------------------------------- #
def _tokens(s: str):
    return set(t for t in re.split(r"[^A-Za-z0-9]+", s.lower()) if len(t) > 2)


def audit(reqs, model, links):
    link_by_req = {}
    linked_sids = set()
    for lk in links:
        if lk["req_id"]:
            link_by_req.setdefault(lk["req_id"], lk)
        # record every sid component of a linked model id as "claimed"
        for p in lk["model_id"].split(":"):
            if p:
                linked_sids.add(p)

    model_signal_lower = {s.lower(): s for s in model["signals"]}
    name_pool = {}  # normalized element name -> ("subsystem"/"state", display)
    for b in model["subsystems"]:
        name_pool[b["name"].lower()] = ("subsystem", b["name"])
    for ssid, nm in model["states"].items():
        name_pool[nm.lower()] = ("state", nm)

    results = []
    for r in reqs:
        rtokens = _tokens(r["text"])
        # Signal-like identifiers named in the requirement (don't split on '_').
        idents = set(re.findall(r"[A-Za-z][A-Za-z0-9_]+", r["text"]))
        mentioned = sorted({model_signal_lower[i.lower()] for i in idents
                            if i.lower() in model_signal_lower})
        # Named like a signal (underscore + a capital) but absent as a signal,
        # a subsystem, or a Stateflow state -> genuinely missing from the model.
        missing_signals = sorted({
            i for i in idents
            if "_" in i and any(c.isupper() for c in i)
            and i.lower() not in model_signal_lower
            and i.lower() not in name_pool
        })

        evidence, target, confidence = None, None, None

        # (a) existing requirement link
        lk = link_by_req.get(r["id"])
        if lk:
            evidence = "Requirement link (.slmx)"
            target = resolve_target(lk["model_id"], model)
            confidence = "high"
        else:
            # (b) naming convention: a subsystem/state named after the requirement
            best = None
            for nm_lower, (kind, disp) in name_pool.items():
                overlap = _tokens(disp) & rtokens
                title_hit = _tokens(r["title"]) and _tokens(r["title"]) <= _tokens(disp)
                if title_hit or len(overlap) >= 2:
                    score = (2 if title_hit else 0) + len(overlap)
                    if not best or score > best[0]:
                        best = (score, kind, disp)
            if best:
                evidence = "Naming convention"
                target = best[2]
                confidence = "high" if best[0] >= 2 else "medium"
            else:
                # (c) semantic similarity via signal / token overlap
                if mentioned:
                    evidence = "Semantic (signal overlap)"
                    target = ", ".join(mentioned[:3])
                    confidence = "medium"

        if target:
            status = "Partial" if (missing_signals or confidence == "medium") else "Matched"
        else:
            status = "Gap"

        results.append({
            "id": r["id"], "id_display": r["id_display"], "title": r["title"],
            "text": r["text"], "status": status, "evidence": evidence,
            "target": target, "confidence": confidence,
            "mentioned_signals": mentioned, "missing_signals": missing_signals,
        })

    # ------------------------------------------------------------------ #
    # Orphan logic — containment-aware.
    # An element is "covered" if it, or any ancestor subsystem, carries a
    # requirement link. Interface ports (Inport/Outport) are excluded: they are
    # the subsystem boundary, inherently covered by the block they belong to.
    # ------------------------------------------------------------------ #
    parent_of = model["parent_of"]
    sid_index = model["sid_index"]
    linked_containers = set()   # linked SIDs that are SubSystems
    linked_states = set()       # linked Stateflow SSIDs
    for lk in links:
        parts = [p for p in lk["model_id"].split(":") if p]
        for p in parts:
            if sid_index.get(p, {}).get("type") == "SubSystem":
                linked_containers.add(p)
        if parts and parts[-1] in model["states"]:
            linked_states.add(parts[-1])

    def covered(sid):
        seen = set()
        cur = sid
        while cur is not None and cur not in seen:
            seen.add(cur)
            if cur in linked_containers:
                return True
            cur = parent_of.get(cur)
        return False

    orphans = {"functional": [], "structural": []}
    for b in model["blocks"]:
        if b["type"] in ("Inport", "Outport"):   # interface ports, not logic
            continue
        if covered(b["sid"]):
            continue
        entry = {"sid": b["sid"], "name": b["name"], "type": b["type"]}
        if b["type"] == "SubSystem":
            orphans["functional"].append(entry)
        else:
            orphans["structural"].append(entry)
    # Stateflow states with no requirement link (state's chart is inside subsystem
    # SID 36 here; a state is covered if the link targets it directly).
    for ssid, nm in model["states"].items():
        if ssid not in linked_states:
            orphans["functional"].append(
                {"sid": ssid, "name": nm, "type": "Stateflow state"})

    return results, orphans


# --------------------------------------------------------------------------- #
# Rendering — self-contained HTML dashboard
# --------------------------------------------------------------------------- #
_CSS = """
:root{
  --bg:#f4f6f8; --surface:#ffffff; --surface-2:#eef1f5; --border:#d7dce4;
  --text:#1a2030; --text-dim:#59627a; --accent:#2f6f8f;
  --good:#1f9d57; --warn:#c0801a; --bad:#cf4557; --orphan:#6d6a9c;
  --good-bg:#e7f5ec; --warn-bg:#f8efdc; --bad-bg:#fae6e9; --orphan-bg:#eceafa;
  --shadow:0 1px 2px rgba(20,30,50,.06),0 4px 16px rgba(20,30,50,.05);
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0f1319; --surface:#161b23; --surface-2:#1e2632; --border:#2a323f;
  --text:#e7ebf2; --text-dim:#96a0b2; --accent:#5aa9cf;
  --good:#37c583; --warn:#e0a844; --bad:#f0687e; --orphan:#9a92e0;
  --good-bg:#12271d; --warn-bg:#2a2314; --bad-bg:#2c1519; --orphan-bg:#1c1a2e;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 20px rgba(0,0,0,.35);
}}
:root[data-theme="light"]{
  --bg:#f4f6f8; --surface:#ffffff; --surface-2:#eef1f5; --border:#d7dce4;
  --text:#1a2030; --text-dim:#59627a; --accent:#2f6f8f;
  --good:#1f9d57; --warn:#c0801a; --bad:#cf4557; --orphan:#6d6a9c;
  --good-bg:#e7f5ec; --warn-bg:#f8efdc; --bad-bg:#fae6e9; --orphan-bg:#eceafa;
  --shadow:0 1px 2px rgba(20,30,50,.06),0 4px 16px rgba(20,30,50,.05);
}
:root[data-theme="dark"]{
  --bg:#0f1319; --surface:#161b23; --surface-2:#1e2632; --border:#2a323f;
  --text:#e7ebf2; --text-dim:#96a0b2; --accent:#5aa9cf;
  --good:#37c583; --warn:#e0a844; --bad:#f0687e; --orphan:#9a92e0;
  --good-bg:#12271d; --warn-bg:#2a2314; --bad-bg:#2c1519; --orphan-bg:#1c1a2e;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 20px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.5;-webkit-font-smoothing:antialiased;}
.mono{font-family:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  font-variant-numeric:tabular-nums;}
.wrap{max-width:1120px;margin:0 auto;padding:32px 24px 80px;}
header.top{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;
  gap:16px;border-bottom:1px solid var(--border);padding-bottom:20px;margin-bottom:28px;}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);
  font-weight:600;margin:0 0 6px;}
h1{font-size:26px;line-height:1.15;margin:0;font-weight:680;text-wrap:balance;letter-spacing:-.01em;}
.sub{color:var(--text-dim);font-size:14px;margin:8px 0 0;}
.meta{text-align:right;color:var(--text-dim);font-size:12.5px;line-height:1.7;}
.meta b{color:var(--text);font-weight:600;}

.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:26px;}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:16px 18px;box-shadow:var(--shadow);position:relative;overflow:hidden;}
.tile .lbl{font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--text-dim);font-weight:600;}
.tile .val{font-size:30px;font-weight:700;margin-top:6px;letter-spacing:-.02em;}
.tile .note{font-size:12px;color:var(--text-dim);margin-top:2px;}
.tile.stripe::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;}
.tile.s-good::before{background:var(--good)} .tile.s-warn::before{background:var(--warn)}
.tile.s-bad::before{background:var(--bad)} .tile.s-orphan::before{background:var(--orphan)}
.tile.s-accent::before{background:var(--accent)}

.bar{height:9px;border-radius:6px;background:var(--surface-2);overflow:hidden;display:flex;margin-top:12px;}
.bar span{display:block;height:100%;}
.bar .b-good{background:var(--good)} .bar .b-warn{background:var(--warn)} .bar .b-bad{background:var(--bad)}

h2{font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--text-dim);
  font-weight:700;margin:36px 0 14px;display:flex;align-items:center;gap:10px;}
h2::after{content:"";flex:1;height:1px;background:var(--border);}

.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin:-4px 0 16px;font-size:12.5px;color:var(--text-dim);}
.pill{display:inline-flex;align-items:center;gap:7px;font-weight:600;font-size:12px;
  padding:3px 10px;border-radius:999px;white-space:nowrap;}
.dot{width:8px;height:8px;border-radius:50%;flex:none;}
.p-good{color:var(--good);background:var(--good-bg)} .p-good .dot{background:var(--good)}
.p-warn{color:var(--warn);background:var(--warn-bg)} .p-warn .dot{background:var(--warn)}
.p-bad{color:var(--bad);background:var(--bad-bg)} .p-bad .dot{background:var(--bad)}
.p-orphan{color:var(--orphan);background:var(--orphan-bg)} .p-orphan .dot{background:var(--orphan)}

.tablecard{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  box-shadow:var(--shadow);overflow:hidden;}
.scroll{overflow-x:auto;}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:720px;}
thead th{text-align:left;font-size:11px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--text-dim);font-weight:700;padding:12px 14px;border-bottom:1px solid var(--border);
  background:var(--surface-2);position:sticky;top:0;}
tbody td{padding:12px 14px;border-bottom:1px solid var(--border);vertical-align:top;}
tbody tr:last-child td{border-bottom:none;}
tbody tr{position:relative;}
td.stripe{border-left:4px solid transparent;}
tr.st-Matched td.stripe{border-left-color:var(--good)}
tr.st-Partial td.stripe{border-left-color:var(--warn)}
tr.st-Gap td.stripe{border-left-color:var(--bad)}
.req-id{font-weight:600;font-size:12.5px;color:var(--text)}
.req-title{color:var(--text-dim);font-size:12.5px;margin-top:2px;}
.tgt{color:var(--text);} .ev{color:var(--text-dim);font-size:12px;}
.miss{color:var(--bad);font-size:12px;} .none{color:var(--text-dim);}

details{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  margin-bottom:8px;box-shadow:var(--shadow);overflow:hidden;}
details[open]{border-color:var(--accent);}
summary{cursor:pointer;padding:13px 16px;display:flex;align-items:center;gap:12px;
  list-style:none;font-size:14px;}
summary::-webkit-details-marker{display:none;}
summary .chev{color:var(--text-dim);transition:transform .15s;font-size:12px;}
details[open] summary .chev{transform:rotate(90deg);}
summary .grow{flex:1;font-weight:600;}
.detail-body{padding:2px 16px 16px 40px;border-top:1px solid var(--border);}
.detail-body p{margin:12px 0 6px;font-size:13.5px;color:var(--text);}
.kv{display:grid;grid-template-columns:130px 1fr;gap:6px 14px;font-size:13px;margin-top:10px;}
.kv dt{color:var(--text-dim);font-weight:600;}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:2px;}
.chip{font-size:11.5px;padding:2px 9px;border-radius:6px;background:var(--surface-2);
  border:1px solid var(--border);color:var(--text-dim);}
.orphan-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;}
.ocard{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--orphan);
  border-radius:9px;padding:11px 13px;box-shadow:var(--shadow);}
.ocard.glue{border-left-color:var(--border);opacity:.9;}
.ocard .on{font-weight:600;font-size:13px;} .ocard .ot{font-size:11.5px;color:var(--text-dim);margin-top:2px;}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--border);
  color:var(--text-dim);font-size:12px;line-height:1.7;}
.toggle{cursor:pointer;background:var(--surface-2);border:1px solid var(--border);color:var(--text);
  border-radius:8px;padding:6px 12px;font-size:12.5px;font-weight:600;font-family:inherit;}
.toggle:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
@media (max-width:560px){.meta{text-align:left}.kv{grid-template-columns:1fr}}
"""

_JS = """
(function(){
  var root=document.documentElement;
  var btn=document.getElementById('themeBtn');
  function cur(){return root.getAttribute('data-theme')||
    (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');}
  btn.addEventListener('click',function(){
    var next=cur()==='dark'?'light':'dark';
    root.setAttribute('data-theme',next);
    btn.textContent=next==='dark'?'\\u2600 Light':'\\u263e Dark';
  });
})();
"""


def _e(s):
    return html.escape(str(s if s is not None else ""))


def render_html(results, orphans, meta):
    total = len(results)
    n_match = sum(1 for r in results if r["status"] == "Matched")
    n_part = sum(1 for r in results if r["status"] == "Partial")
    n_gap = sum(1 for r in results if r["status"] == "Gap")
    covered = n_match + n_part
    cov_pct = round(100 * covered / total) if total else 0
    n_orphan_f = len(orphans["functional"])
    n_orphan_s = len(orphans["structural"])

    def pct(n):
        return (100 * n / total) if total else 0

    # KPI tiles
    tiles = f"""
      <div class="tile stripe s-accent"><div class="lbl">Requirement coverage</div>
        <div class="val mono">{cov_pct}%</div>
        <div class="note">{covered} of {total} requirements traced to the model</div>
        <div class="bar" role="img" aria-label="coverage breakdown">
          <span class="b-good" style="width:{pct(n_match):.1f}%"></span>
          <span class="b-warn" style="width:{pct(n_part):.1f}%"></span>
          <span class="b-bad" style="width:{pct(n_gap):.1f}%"></span>
        </div></div>
      <div class="tile stripe s-good"><div class="lbl">Matched</div>
        <div class="val mono">{n_match}</div><div class="note">full trace, signals present</div></div>
      <div class="tile stripe s-warn"><div class="lbl">Partial</div>
        <div class="val mono">{n_part}</div><div class="note">weak match or missing signals</div></div>
      <div class="tile stripe s-bad"><div class="lbl">Gaps</div>
        <div class="val mono">{n_gap}</div><div class="note">no model implementation</div></div>
      <div class="tile stripe s-orphan"><div class="lbl">Orphan logic</div>
        <div class="val mono">{n_orphan_f}</div><div class="note">{n_orphan_s} structural glue blocks</div></div>
    """

    # Matrix rows
    rows = []
    for r in results:
        miss = (f'<span class="miss">missing: {_e(", ".join(r["missing_signals"]))}</span>'
                if r["missing_signals"] else '<span class="none">—</span>')
        tgt = _e(r["target"]) if r["target"] else '<span class="none">no element</span>'
        ev = _e(r["evidence"]) if r["evidence"] else "—"
        conf = f' · {_e(r["confidence"])}' if r["confidence"] else ""
        rows.append(f"""
        <tr class="st-{r['status']}">
          <td class="stripe"><div class="req-id mono">{_e(r['id_display'])}</div>
            <div class="req-title">{_e(r['title'])}</div></td>
          <td>{_status_pill(r['status'])}</td>
          <td class="tgt">{tgt}</td>
          <td class="ev">{ev}{conf}</td>
          <td>{miss}</td>
        </tr>""")

    # Drill-down
    details = []
    for r in results:
        sig = ("".join(f'<span class="chip">{_e(s)}</span>' for s in r["mentioned_signals"])
               or '<span class="none">none detected</span>')
        miss = ("".join(f'<span class="chip" style="color:var(--bad)">{_e(s)}</span>'
                        for s in r["missing_signals"]) or '<span class="none">none</span>')
        details.append(f"""
        <details>
          <summary><span class="chev">▶</span>
            <span class="grow mono">{_e(r['id_display'])} — {_e(r['title'])}</span>
            {_status_pill(r['status'])}</summary>
          <div class="detail-body">
            <p>{_e(r['text'])}</p>
            <dl class="kv">
              <dt>Model element</dt><dd class="tgt">{_e(r['target']) or '—'}</dd>
              <dt>Evidence</dt><dd>{_e(r['evidence']) or '—'}{(' · ' + _e(r['confidence'])) if r['confidence'] else ''}</dd>
              <dt>Signals present</dt><dd><div class="chips">{sig}</div></dd>
              <dt>Signals missing</dt><dd><div class="chips">{miss}</div></dd>
            </dl>
          </div>
        </details>""")

    # Orphans
    ocards = []
    for o in orphans["functional"]:
        ocards.append(f'<div class="ocard"><div class="on mono">{_e(o["name"])}</div>'
                      f'<div class="ot">{_e(o["type"])} · SID {_e(o["sid"])} · no requirement traced</div></div>')
    for o in orphans["structural"]:
        ocards.append(f'<div class="ocard glue"><div class="on mono">{_e(o["name"])}</div>'
                      f'<div class="ot">{_e(o["type"])} · SID {_e(o["sid"])} · structural glue</div></div>')
    orphan_html = ("".join(ocards) if ocards
                   else '<div class="none" style="padding:8px">No orphan elements — every model block traces to a requirement.</div>')

    legend = """
      <div class="legend">
        <span class="pill p-good"><span class="dot"></span>Matched</span>
        <span class="pill p-warn"><span class="dot"></span>Partial</span>
        <span class="pill p-bad"><span class="dot"></span>Gap</span>
        <span class="pill p-orphan"><span class="dot"></span>Orphan logic</span>
      </div>"""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(meta['model'])} — Traceability Audit</title>
<style>{_CSS}</style></head><body>
<div class="wrap">
  <header class="top">
    <div>
      <p class="eyebrow">Requirement → Model Traceability</p>
      <h1>{_e(meta['model'])} — Traceability Audit</h1>
      <p class="sub">{_e(meta['req_doc'])} &nbsp;↔&nbsp; {_e(meta['model_file'])}
        {' &nbsp;·&nbsp; ' + _e(meta['links_file']) if meta.get('links_file') else ''}</p>
    </div>
    <div class="meta">
      <button class="toggle" id="themeBtn">◐ Theme</button><br>
      <span>Generated <b>{_e(meta['generated'])}</b></span><br>
      <span>{total} requirements · {meta['n_blocks']} model blocks · {meta['n_states']} states</span>
    </div>
  </header>

  <div class="kpis">{tiles}</div>

  <h2>Traceability matrix</h2>
  {legend}
  <div class="tablecard"><div class="scroll"><table>
    <thead><tr><th>Requirement</th><th>Status</th><th>Model element</th>
      <th>Evidence</th><th>Signal coverage</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div></div>

  <h2>Orphan logic — model elements with no traced requirement</h2>
  <div class="orphan-grid">{orphan_html}</div>

  <h2>Per-requirement detail</h2>
  {''.join(details)}

  <footer>
    <b>Scope:</b> tasks 1–4 (parse → match → flag). Matching uses existing requirement
    links (.slmx), naming conventions, then signal-overlap similarity.
    ASIL / ASPICE compliance cross-check and ASIL×program-stage prioritization are
    planned next steps.<br>
    Generated by <span class="mono">tools/trace_audit.py</span> — Requirements to Model Validator.
  </footer>
</div>
<script>{_JS}</script>
</body></html>"""


def _status_pill(status):
    cls = {"Matched": "p-good", "Partial": "p-warn", "Gap": "p-bad"}[status]
    return f'<span class="pill {cls}"><span class="dot"></span>{status}</span>'


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    acc = os.path.join(here, "resources", "ACC (Adaptive Cruise Control)")
    ap = argparse.ArgumentParser(description="Requirement-to-model traceability audit")
    ap.add_argument("--req", default=os.path.join(acc, "Requirement.docx"))
    ap.add_argument("--model", default=os.path.join(acc, "ACC_Project.slx"))
    ap.add_argument("--links", default=os.path.join(acc, "ACC_Project.slmx"))
    ap.add_argument("--out", default=os.path.join(here, "output", "ACC_traceability_dashboard.html"))
    ap.add_argument("--json", default=os.path.join(here, "output", "ACC_traceability_matrix.json"))
    args = ap.parse_args()

    for label, path in (("requirements", args.req), ("model", args.model)):
        if not os.path.exists(path):
            sys.exit(f"ERROR: {label} file not found: {path}")

    reqs = parse_requirements(args.req)
    model = parse_model(args.model)
    links = parse_links(args.links)
    results, orphans = audit(reqs, model, links)

    meta = {
        "model": re.sub(r"\.slx$", "", os.path.basename(args.model)),
        "model_file": os.path.basename(args.model),
        "req_doc": os.path.basename(args.req),
        "links_file": os.path.basename(args.links) if os.path.exists(args.links) else "",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_blocks": len(model["blocks"]),
        "n_states": len(model["states"]),
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render_html(results, orphans, meta))
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "requirements": results, "orphans": orphans}, f, indent=2)

    # Console summary
    n_match = sum(1 for r in results if r["status"] == "Matched")
    n_part = sum(1 for r in results if r["status"] == "Partial")
    n_gap = sum(1 for r in results if r["status"] == "Gap")
    print(f"Parsed {len(reqs)} requirements, {len(model['blocks'])} blocks, "
          f"{len(model['states'])} states, {len(links)} existing links.")
    print(f"  Matched: {n_match}   Partial: {n_part}   Gap: {n_gap}")
    print(f"  Orphan logic: {len(orphans['functional'])} functional, "
          f"{len(orphans['structural'])} structural.")
    print(f"Dashboard -> {args.out}")
    print(f"Matrix    -> {args.json}")


if __name__ == "__main__":
    main()
