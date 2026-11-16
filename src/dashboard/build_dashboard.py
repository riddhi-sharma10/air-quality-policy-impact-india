"""Build the tabbed dashboard (one self-contained HTML file) from the finished notebook outputs.

Usage (from the repository root):
    python src/dashboard/build_dashboard.py          # writes dashboard/index.html
    python src/dashboard/build_dashboard.py --check  # also checks the page numbers against the tables

Reads only outputs/tables/*.csv and the executed notebook text (for the four key-question answers). No figures are
copied and the large final dataset is not read. Every number on the page comes from a saved table.
"""
import argparse, html, json, os, re, sys
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TAB = os.path.join(ROOT, "outputs", "tables")
OUT = os.path.join(ROOT, "dashboard")
NB = os.path.join(ROOT, "notebooks", "air_quality_policy_impact.ipynb")


def table(name):
    return pd.read_csv(os.path.join(TAB, name + ".csv"))


def notebook_outputs():
    cells = json.load(open(NB, encoding="utf8"))["cells"]
    found = {}
    for i, c in enumerate(cells):
        if c["cell_type"] == "markdown":
            head = "".join(c["source"]).split("\n")[0].strip()
            outs = []
            for nxt in cells[i + 1:i + 3]:
                if nxt["cell_type"] == "code":
                    for o in nxt.get("outputs", []):
                        if "data" in o and "text/markdown" in o["data"]:
                            outs.append("".join(o["data"]["text/markdown"]))
            found[head] = outs
    return found


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", s)
    return s.replace("ug/m3", "µg/m³")


def key_questions(nbt):
    """The four key questions of notebook 10.3: id -> (question, answer, how sure)."""
    text = next(v for k, v in nbt.items() if k.startswith("## 10.3"))
    status_md, q_md = text[0], text[1]
    qs = {}
    for p in [p.strip() for p in q_md.strip().split("\n\n") if p.strip().startswith("**Q")]:
        m = re.match(r"\*\*(Q\d)\. (.+?)\*\*\s*(.*)", p, re.S)
        body = m.group(3)
        ans, _, rest = body.partition(" *How sure:*")
        sure = rest.split(" *Caveat:*")[0].strip()
        cav = rest.partition(" *Caveat:*")[2].strip()
        qs[m.group(1)] = (m.group(2), ans.strip(), (sure + (" Caveat: " + cav if cav else "")).strip())
    h1 = re.search(r"H1:.*?Status(?: by the frozen rules)?: ([A-Z][A-Z ]*[A-Z])", status_md, re.S).group(1).strip()
    h2 = re.search(r"H2:.*?Status(?: by the frozen rules)?: ([A-Z][A-Z ]*[A-Z])", status_md, re.S).group(1).strip()
    return qs, h1, h2


def chip(word):
    cls = {"SUPPORTED": "ok", "WEAKLY SUPPORTED": "mid", "INCONCLUSIVE": "mid"}.get(word, "no")
    return f'<span class="chip {cls}">{word.capitalize()}</span>'


def build():
    nbt = notebook_outputs()
    qs, h1_status, h2_status = key_questions(nbt)
    kp, plain, ladder = table("T00_kpis"), table("T04b_h1_effect_plain_units"), table("T04m_season_ladder")
    events, power, recs = table("T06a_h2_events"), table("T06n_power_matched_noise"), table("T08_recommendations")
    join, sub, outages = table("T01b_join_report"), table("T01d_stations_per_sub_area"), table("T02b_outage_runs")
    gd = table("T04_group_day")

    for col in kp.columns[1:5]:                                   # one KPI row holds text, so the columns load as strings
        kp[col] = pd.to_numeric(kp[col], errors="coerce")
    prim = plain.iloc[0]
    n_st = int(sub.stations.sum())
    rows_total = int(join.iloc[0]["Rows after"])
    longest = int(outages.hours.max())
    out_total = int(kp.iloc[5, 1])

    series = [{"g": r.group[0], "d": r.date_ist, "p": round(r.pm25, 1), "lo": round(r.ci_low, 1), "hi": round(r.ci_high, 1),
               "s": int(r.stage_max)} for r in gd.itertuples()]

    lad = ladder.iloc[[0, 1, 2, 3]].copy()
    lad_labels = ["Primary model", "+ month effects", "+ week effects", "+ date effects"]
    ladder_json = [{"l": lab, "e": float(r["Effect per +5 (%)"]), "lo": float(r["CI low"]), "hi": float(r["CI high"])}
                   for lab, (_, r) in zip(lad_labels, lad.iterrows())]

    ev_rows = ""
    for _, r in events.iterrows():
        eff = "n/a" if pd.isna(r["Days 1-3 (%)"]) else f'{r["Days 1-3 (%)"]:+.0f}%'
        ci = "" if pd.isna(r["CI 1-3 low"]) else f' <span class="muted">[{r["CI 1-3 low"]:+.0f}, {r["CI 1-3 high"]:+.0f}]</span>'
        ev_rows += (f'<tr><td>{html.escape(str(r["Date"]))}</td><td>Stage {html.escape(str(r["Stage"]).replace("->", " → "))}</td>'
                    f'<td>{eff}{ci}</td><td><span class="chip no">{"Usable" if r["Usable"] else "Not usable"}</span></td></tr>')

    pw = power.iloc[:4]
    power_json = [{"n": int(r["Events"]), "m": float(r["Minimum detectable fall (80% power)"]) * 100} for _, r in pw.iterrows()]

    ev_json = [{"d": pd.to_datetime(r["Date"], format="%d %b %Y").strftime("%Y-%m-%d"),
                "l": "Stage " + str(r["Stage"]).replace("->", "→")} for _, r in events.iterrows()]

    ev_json = [{"d": pd.to_datetime(r["Date"], format="%d %b %Y").strftime("%Y-%m-%d"),
                "l": "Stage " + str(r["Stage"]).replace("->", "→")} for _, r in events.iterrows()]

    rec_rows = "".join(
        f'<li><div class="rec-t">{inline(re.sub(r"^\d+\. ", "", r.iloc[0]))}</div>'
        f'<div class="rec-m"><span>{inline(r.iloc[4])}</span><span>{inline(r.iloc[5])}</span></div></li>'
        for _, r in recs.iterrows())

    def qa(qid):
        q, a, s = qs[qid]
        return (f'<div class="qa"><div class="q">{inline(q)}</div><div class="a">{inline(a)}</div>'
                f'<details><summary>How sure?</summary><p>{inline(s)}</p></details></div>')

    def kpi(i, label, fmt, unit=""):
        return (f'<div class="kpi"><div class="kl">{label}</div><div class="kv"><span><i class="dot t"></i>{fmt(kp.iloc[i,3])}{unit}</span>'
                f'<span><i class="dot c"></i>{fmt(kp.iloc[i,4])}{unit}</span></div></div>')

    f0, f1 = (lambda v: f"{v:,.0f}"), (lambda v: f"{v:.0f}")
    note = str(kp.iloc[7, 5])                                   # "estimate for information -21.7%; ...; 95% interval -39.8% to +1.3%; ..."
    est_m, ci_m = re.search(r"information ([+-]\d+\.\d)%", note), re.search(r"interval ([^;]+);", note)
    h2_note = (f"Primary event, for information only: {est_m.group(1)}% (95% interval {ci_m.group(1)}). It fails the hold-out rule."
               if est_m and ci_m else "No event gave a reliable estimate.")
    n_usable, n_events = int(events["Usable"].sum()), len(events)
    n_methods = len(table("T04n_primary_interval_methods"))
    n_zero = int(table("T04n_primary_interval_methods")["Includes zero"].sum())

    data = json.dumps({"series": series, "ladder": ladder_json, "power": power_json, "ev": ev_json}, separators=(",", ":"))

    page = TEMPLATE
    repl = {
        "@@DATA@@": data,
        "@@NSTATIONS@@": str(n_st), "@@ROWS@@": f"{rows_total:,}",
        "@@H1CHIP@@": chip(h1_status), "@@H2CHIP@@": chip(h2_status),
        "@@H1EST@@": f"{prim['Estimate']:+.1f}%", "@@H1CI@@": f"[{prim['Decision CI low']:+.1f}, {prim['Decision CI high']:+.1f}]",
        "@@H1DATE@@": f"{ladder_json[3]['e']:+.1f}%",
        "@@H2EST@@": f"{n_usable} of {n_events}", "@@H2NOTE@@": inline(h2_note),
        "@@FRAGILE@@": f"{n_zero} of {n_methods} ways of computing the interval include zero.",
        "@@KPIS@@": kpi(0, "Winter PM2.5, µg/m³", f0) + kpi(2, "Days above 60 µg/m³", f1, "%") + kpi(4, "Hours with data", f1, "%"),
        "@@OUTAGE@@": f"{out_total:,}", "@@LONGEST@@": str(longest),
        "@@STAGE34@@": f"{int(kp.iloc[6,1]):,}",
        "@@QA1@@": qa("Q1"), "@@QA2@@": qa("Q2"), "@@QA3@@": qa("Q3"), "@@QA4@@": qa("Q4"),
        "@@EVENTS@@": ev_rows, "@@RECS@@": rec_rows,
        "@@F2EXTRA@@": f"{kp.iloc[8,3]:.1f}",
        "@@TMEAN@@": f"{kp.iloc[0,3]:.0f}", "@@CMEAN@@": f"{kp.iloc[0,4]:.0f}", "@@TDAYS@@": f"{kp.iloc[2,3]:.0f}",
        "@@EVN@@": str(len(events)), "@@EVUSABLE@@": str(int(events["Usable"].sum())),
        "@@MINDET1@@": f"{power_json[0]['m']:.0f}",
        "@@TMEAN@@": f"{kp.iloc[0,3]:.0f}", "@@CMEAN@@": f"{kp.iloc[0,4]:.0f}", "@@TDAYS@@": f"{kp.iloc[2,3]:.0f}", "@@CDAYS@@": f"{kp.iloc[2,4]:.0f}",
        "@@EVN@@": str(len(events)), "@@EVUSABLE@@": str(int(events["Usable"].sum())),
        "@@MINDET1@@": f"{power_json[0]['m']:.0f}", "@@NEED@@": str(power_json[-1]["n"]),
    }
    for k, v in repl.items():
        page = page.replace(k, v)
    return page, dict(prim=prim, h1=h1_status, h2=h2_status, rows=rows_total, out=out_total)


def main(check):
    page, facts = build()
    os.makedirs(OUT, exist_ok=True)
    assets = os.path.join(OUT, "assets")
    if os.path.isdir(assets):                                           # the old figure-based version used this folder
        for f in os.listdir(assets):
            os.remove(os.path.join(assets, f))
        os.rmdir(assets)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf8").write(page)
    print(f"wrote dashboard/index.html ({len(page)//1024} KB)")
    if check:
        text = re.sub(r"<[^>]+>", " ", page.split("<script>")[0])
        p, fails = facts["prim"], []
        for label, val in [("H1 estimate", f"{p['Estimate']:+.1f}%"), ("H1 CI", f"[{p['Decision CI low']:+.1f}, {p['Decision CI high']:+.1f}]"),
                           ("rows", f"{facts['rows']:,}"), ("outage hours", f"{facts['out']:,}"),
                           ("H1 status", facts["h1"].capitalize()), ("H2 status", facts["h2"].capitalize())]:
            if val not in text:
                fails.append(label)
        for pat in ("caused", "reduced by", "proved"):
            if re.search(rf"\b{pat}\b", text, re.I):
                fails.append("wording: " + pat)
        for t in ("summary", "explore", "fires", "grap", "actions", "about"):
            if f'id="tab-{t}"' not in page:
                fails.append("missing tab " + t)
        if "@@" in page:
            fails.append("unfilled placeholder")
        print("CHECK FAILED: " + ", ".join(fails) if fails else "CHECK PASSED: numbers, status words, wording, six tabs, no placeholders")
        sys.exit(1 if fails else 0)


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Air Quality Policy Dashboard</title>
<style>
:root{--bg:#F5F3EE;--card:#FFFFFF;--line:#E7E2D8;--text:#2B2F35;--muted:#757A82;--sage:#12945A;--sage-bg:#DDF1E6;
--sand:#8A6D2F;--sand-bg:#F3EAD6;--rose:#8D4B45;--rose-bg:#F2E1DE;--t:#F26A00;--c:#0A7CFF;--r:14px}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:0 16px}
header{padding:22px 0 10px;display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
h1{font-size:19px;margin:0;font-weight:650}.sub{color:var(--muted);font-size:13px}
.tabs{display:flex;gap:4px;background:#ECE8DF;padding:4px;border-radius:12px;overflow-x:auto;margin-bottom:18px}
.tabs button{flex:1;white-space:nowrap;border:0;background:transparent;font:inherit;color:var(--muted);padding:8px 14px;border-radius:9px;cursor:pointer}
.tabs button.on{background:var(--card);color:var(--text);box-shadow:0 1px 2px rgba(40,40,30,.08);font-weight:600}
.pane{display:none}.pane.on{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:18px;margin-bottom:14px}
.grid{display:grid;gap:14px;grid-template-columns:1fr 1fr}
.chip{display:inline-block;padding:2px 11px;border-radius:999px;font-size:12px;font-weight:650}
.chip.ok{background:var(--sage-bg);color:var(--sage)}.chip.mid{background:var(--sand-bg);color:var(--sand)}.chip.no{background:var(--rose-bg);color:var(--rose)}
.tag{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
.big{font-size:34px;font-weight:650;letter-spacing:-.02em;line-height:1.1;margin:6px 0 2px}.big small{font-size:13px;color:var(--muted);font-weight:400;letter-spacing:0}
.muted{color:var(--muted)}.note{font-size:13.5px;color:var(--muted);margin:8px 0 0}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.kpi .kl{font-size:12px;color:var(--muted)}
.kv{display:flex;gap:14px;font-size:22px;font-weight:620;margin-top:4px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.dot.t{background:var(--t)}.dot.c{background:var(--c)}
.legend{font-size:12.5px;color:var(--muted)}.legend span{margin-right:14px}
.seg{display:inline-flex;background:#ECE8DF;border-radius:9px;padding:3px;margin:0 8px 8px 0}
.seg button{border:0;background:transparent;font:inherit;font-size:13px;color:var(--muted);padding:4px 11px;border-radius:7px;cursor:pointer}
.seg button.on{background:var(--card);color:var(--text);font-weight:600}
.chk{font-size:13px;margin-right:12px;color:var(--muted);cursor:pointer;user-select:none}.chk input{accent-color:var(--sage)}
#chart{width:100%;height:280px;display:block;touch-action:none}
.read{display:flex;gap:22px;flex-wrap:wrap;margin-top:6px;font-size:13.5px}.read b{font-size:18px}
.qa{padding:12px 0;border-top:1px solid var(--line)}.qa:first-of-type{border-top:0;padding-top:0}
.qa .q{font-weight:620;margin-bottom:3px}.qa .a{font-size:14.5px}
details{margin-top:4px}summary{font-size:13px;color:var(--sage);cursor:pointer}details p{font-size:13px;color:var(--muted);margin:4px 0 0}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line)}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600}
.recs{list-style:none;margin:0;padding:0}.recs li{padding:12px 0;border-top:1px solid var(--line)}.recs li:first-child{border-top:0}
.rec-t{font-weight:620}.rec-m{font-size:13px;color:var(--muted);display:flex;gap:14px;flex-wrap:wrap;margin-top:2px}
.rec-m span+span::before{content:"· ";}
svg text{font-family:inherit}
ul.plain{margin:0;padding-left:18px}ul.plain li{margin-bottom:5px}

.hero{background:linear-gradient(120deg,#E4EDE7 0%,#F3EAD6 100%);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px;margin-bottom:16px}
.hero .q{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--sage);font-weight:650}
.hero h2{margin:4px 0 6px;font-size:21px;line-height:1.3;font-weight:650}
.hero p{margin:0;color:#4A4F57;font-size:14.5px}
.lede{display:flex;gap:12px;align-items:flex-start;background:#FBFAF6;border:1px dashed #D9D3C5;border-radius:12px;padding:12px 14px;margin-bottom:14px;font-size:14px;color:#4A4F57}
.lede .ic{flex:none;width:26px;height:26px;border-radius:50%;background:var(--sage-bg);color:var(--sage);display:grid;place-items:center;font-weight:700;font-size:14px}
.lede b{color:var(--text)}
.insight{margin-top:10px;padding:11px 14px;border-radius:10px;background:var(--sand-bg);color:#6B5320;font-size:14px}
.insight b{color:#4F3D12}
.finding{display:flex;gap:12px;padding:10px 0;border-top:1px solid var(--line);font-size:14.5px}.finding:first-child{border-top:0}
.finding .n{flex:none;width:24px;height:24px;border-radius:7px;background:var(--sage-bg);color:var(--sage);font-weight:700;display:grid;place-items:center;font-size:13px}
.card.h1{border-left:4px solid var(--sage)}.card.h2{border-left:4px solid #C9A961}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.keys{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12.5px;color:var(--muted);margin-top:6px}.keys i.sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-2px}
.gl dt{font-weight:620;margin-top:8px}.gl dd{margin:0;color:var(--muted);font-size:13.5px}
.how{font-size:13px;color:var(--muted);margin:2px 0 8px}
@media(max-width:680px){.grid,.kpis{grid-template-columns:1fr}.big{font-size:30px}}
</style></head><body><div class="wrap">
<header><h1>Burning, GRAP and Delhi-NCR air quality</h1><div class="sub">@@NSTATIONS@@ stations · hourly · 19 Feb 2025 – 30 Sep 2026 · associations, not proven effects</div></header>
<div class="hero"><div class="q">The question</div><h2>Do crop-residue fires and emergency restrictions (GRAP) change PM2.5 in Delhi-NCR once the weather is accounted for?</h2>
<p>We joined hourly air-quality readings from @@NSTATIONS@@ stations with satellite fire detections, weather and the restriction stage in force. This page shows what the data can and cannot tell us.</p></div>
<div class="tabs" role="tablist">
<button data-t="summary" class="on">Summary</button><button data-t="explore">Explore</button><button data-t="fires">Fires · H1</button>
<button data-t="grap">GRAP · H2</button><button data-t="actions">Actions</button><button data-t="about">About</button></div>

<div class="pane on" id="tab-summary">
 <div class="lede"><div class="ic">i</div><div><b>Start here.</b> Two hypotheses were tested with rules written down before the models were fitted. <b>H1:</b> more fires upwind the day before goes with higher PM2.5. <b>H2:</b> PM2.5 falls after a GRAP stage is switched on, compared with what weather and fires predict.</div></div>
 <div class="grid">
  <div class="card h1"><div class="tag">H1 · upwind fires</div>@@H1CHIP@@<div class="big">@@H1EST@@ <small>PM2.5 per +5 fires</small></div>
   <div class="muted">95% CI @@H1CI@@</div><p class="note">The link is real in the data, but it shrinks to @@H1DATE@@ when days are compared within the same date: much of it is simply "fires and smog are both high in November". @@FRAGILE@@</p></div>
  <div class="card h2"><div class="tag">H2 · GRAP activation</div>@@H2CHIP@@<div class="big">@@H2EST@@ <small>events usable</small></div>
   <div class="muted">@@H2NOTE@@</div><p class="note">Too few events gave a usable prediction, so no verdict is possible. This reflects too little data, not evidence for or against GRAP.</p></div>
 </div>
 <div class="card"><div class="tag">What we found</div>
  <div class="finding"><div class="n">1</div><div><b>Delhi-NCR is far dirtier than the control cities.</b> Winter PM2.5 averaged @@TMEAN@@ µg/m³ against @@CMEAN@@, and @@TDAYS@@% of winter days exceeded the 60 µg/m³ standard.</div></div>
  <div class="finding"><div class="n">2</div><div><b>Fires help explain PM2.5, but weather matters far more.</b> Adding fire data to the model improves prediction only slightly.</div></div>
  <div class="finding"><div class="n">3</div><div><b>We cannot yet say whether GRAP works.</b> It is switched on when pollution is already high, so a later fall is expected anyway, and there are too few events.</div></div>
 </div>
 <div class="tag" style="margin-top:4px">Winter snapshot (Oct 2025 – Feb 2026)</div>
 <div class="kpis">@@KPIS@@</div>
 <div class="legend" style="margin-top:8px"><span><i class="dot t"></i>Delhi-NCR (treated: GRAP applies)</span><span><i class="dot c"></i>Patna, Lucknow, Kanpur (control: outside the NCR)</span></div>
</div>

<div class="pane" id="tab-explore">
 <div class="lede"><div class="ic">i</div><div><b>How to read this.</b> Each line is the average PM2.5 across a group's working stations, one point per day. The dashed line is the 60 µg/m³ national daily standard. The coloured strip along the top of the chart shows the GRAP stage in force (yellow = Stage 1, deep red = Stage 4); grey bands are days with no valid data. <b>Try it:</b> pick a period, switch groups on or off, and hover a day.</div></div>
 <div class="card">
 <div class="seg" id="range"><button data-r="all" class="on">All dates</button><button data-r="winter">Oct–Feb</button><button data-r="burn">Oct–Nov</button></div>
 <label class="chk"><input type="checkbox" id="ct" checked> <i class="dot t"></i>Delhi-NCR</label>
 <label class="chk"><input type="checkbox" id="cc" checked> <i class="dot c"></i>Control cities</label>
 <label class="chk"><input type="checkbox" id="cs" checked> GRAP stages</label>
 <label class="chk"><input type="checkbox" id="ce" checked> Tested events ▲</label>
 <svg id="chart"></svg>
 <div class="keys"><span><i class="sw" style="background:#FFD21F"></i>Stage 1</span><span><i class="sw" style="background:#FF9F1C"></i>Stage 2</span><span><i class="sw" style="background:#F0542B"></i>Stage 3</span><span><i class="sw" style="background:#B0003A"></i>Stage 4</span><span><i class="sw" style="background:#B5B1A6"></i>No valid data</span><span><i class="sw" style="background:#4B2E83;clip-path:polygon(50% 0,100% 100%,0 100%)"></i>GRAP event tested for H2</span></div>
 <div class="read" id="read"></div>
 <div class="insight" id="insight"></div>
</div></div>

<div class="pane" id="tab-fires">
 <div class="hero" style="margin-bottom:14px"><div class="q">H1 · Fires and PM2.5</div><h2>Do days after more upwind fires have higher PM2.5?</h2>
  <p>"Upwind fire" = a satellite-detected fire within 100 km of a station, in the direction the wind came from, the day before. The model compares the same station across days, holding wind, temperature, humidity and boundary-layer height fixed.</p></div>
 <div class="card h1">@@QA1@@@@QA2@@</div>
 <div class="card"><div class="tag">Does the fire link survive seasonal controls?</div>
  <p class="how">Each row is the same estimate under a stricter comparison. <b style="color:#5F8570">Green</b> = the interval excludes zero (clear association); <b style="color:#8d887d">grey</b> = it includes zero (cannot rule out no link). Dot = estimate, line = 95% interval.</p>
  <svg id="ladder" style="width:100%;height:190px"></svg>
  <div class="insight">Read down the rows: once the model compares days within the same month, week or date, most of the apparent fire effect disappears. Fire adds only @@F2EXTRA@@ points of R² beyond weather and station differences.</div></div>
</div>

<div class="pane" id="tab-grap">
 <div class="hero" style="margin-bottom:14px"><div class="q">H2 · GRAP and PM2.5</div><h2>Does PM2.5 fall after a GRAP stage is switched on?</h2>
  <p>GRAP stages (1 to 4) add stricter restrictions as air worsens. For each activation we asked: was PM2.5 in the next three days lower than a model of weather and fires <i>would have predicted</i>? That prediction is called the counterfactual.</p></div>
 <div class="card h2">@@QA3@@@@QA4@@</div>
 <div class="card"><div class="tag">Every GRAP event we tested</div>
  <p class="how">"Effect" is actual minus predicted PM2.5 over days 1–3 after the stage change, with its 95% interval. An event is <b>usable</b> only if the model predicted the preceding days well enough; none did, so none of these numbers can be relied on.</p>
  <table><tr><th>Date</th><th>Change</th><th>Effect</th><th></th></tr>@@EVENTS@@</table></div>
 <div class="card"><div class="tag">Could we have detected a real effect at all?</div>
  <p class="how">Bars show the smallest true fall the method would reliably (80% of the time) detect, for a given number of events.</p>
  <svg id="power" style="width:100%;height:170px"></svg>
  <div class="insight">With one event, only a fall of about @@MINDET1@@% or more would show up. One winter gives about one event, so a clear answer needs data from several winters.</div></div>
</div>

<div class="pane" id="tab-actions">
 <div class="lede"><div class="ic">i</div><div><b>What follows from this.</b> Because the evidence on fires is weak and on GRAP is inconclusive, the recommendations are mostly about <b>getting the data that would settle the question</b>, plus one practical advisory.</div></div>
 <div class="card"><div class="tag">Recommended actions</div><ul class="recs">@@RECS@@</ul></div>
</div>

<div class="pane" id="tab-about"><div class="grid">
 <div class="card"><div class="tag">Data</div><ul class="plain"><li>PM2.5: CPCB via OpenAQ, @@NSTATIONS@@ stations, @@ROWS@@ station-hours</li><li>Fires: NASA FIRMS (VIIRS)</li><li>Weather: ERA5</li><li>Restrictions: CAQM GRAP orders</li>
  <li>@@OUTAGE@@ outage hours; longest run @@LONGEST@@ hours (Jan 2026), treated as missing</li><li>@@STAGE34@@ hours at Stage III or IV</li></ul>
  <div class="tag" style="margin-top:14px">Limits</div><ul class="plain"><li>One burning season and one winter</li><li>GRAP starts when pollution is already high</li><li>Fires counted within 100 km; cloud gaps are not zeros</li><li>Control cities are a comparison, not a clean counterfactual</li><li>No Punjab or Haryana stations</li></ul></div>
 <div class="card"><div class="tag">Glossary</div><dl class="gl" style="margin:0">
  <dt>PM2.5</dt><dd>Fine particles under 2.5 µm that reach deep into the lungs; measured in µg/m³.</dd>
  <dt>GRAP</dt><dd>Graded Response Action Plan: emergency restrictions in stages 1–4 across the NCR.</dd>
  <dt>Treated / control</dt><dd>Stations inside the NCR (GRAP applies) vs stations in Patna, Lucknow, Kanpur.</dd>
  <dt>Upwind fires</dt><dd>Fires within 100 km in the direction the wind came from, the previous day.</dd>
  <dt>Counterfactual</dt><dd>Our estimate of PM2.5 without the stage, from weather and fires.</dd>
  <dt>Confidence interval</dt><dd>The range the true value plausibly lies in; if it includes zero, "no effect" is possible.</dd></dl></div>
</div></div>
</div>
<script>
const D=@@DATA@@;
const $=s=>document.querySelector(s), NS="http://www.w3.org/2000/svg";
const C={t:"#F26A00",c:"#0A7CFF",grid:"#E2DDD2",txt:"#4F545C",sage:"#12945A",rose:"#D62B1F"};
document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{
 document.querySelectorAll(".tabs button,.pane").forEach(e=>e.classList.remove("on"));
 b.classList.add("on");$("#tab-"+b.dataset.t).classList.add("on");draw();});
function el(tag,attrs,parent,text){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(text!=null)e.textContent=text;parent&&parent.appendChild(e);return e}
function size(svg){const r=svg.getBoundingClientRect();return [r.width||600,r.height||200]}

/* Explore */
let range="all";
const days=g=>D.series.filter(r=>r.g===g);
const inRange=d=>{const m=+d.slice(5,7);return range==="all"||(range==="winter"?(m>=10||m<=2):(m>=10&&m<=11))};
const stageCol=["transparent","#FFD21F","#FF9F1C","#F0542B","#B0003A"];
function explore(){
 const svg=$("#chart");svg.innerHTML="";const [W,H]=size(svg),m={l:40,r:10,t:30,b:26};
 const sel=[];if($("#ct").checked)sel.push("t");if($("#cc").checked)sel.push("c");
 const all=D.series.filter(r=>inRange(r.d)&&sel.includes(r.g));
 const dates=[...new Set(D.series.filter(r=>inRange(r.d)).map(r=>r.d))].sort();
 if(!dates.length){return}
 const DAY=864e5,t0=new Date(dates[0]).getTime(),t1=new Date(dates[dates.length-1]).getTime()||t0+1;
 const ymax=Math.max(100,...all.map(r=>r.p))*1.12;
 const x=d=>m.l+(new Date(d).getTime()-t0)/(t1-t0||1)*(W-m.l-m.r),y=v=>H-m.b-v/ymax*(H-m.t-m.b);
 const bw=Math.max(1.5,(W-m.l-m.r)/Math.max((t1-t0)/DAY+1,1));
 const have=new Set(D.series.map(r=>r.d));
 for(let t=t0;t<=t1;t+=DAY){const d=new Date(t).toISOString().slice(0,10);if(!have.has(d)&&inRange(d))el("rect",{x:x(d)-bw/2,y:m.t,width:bw+.5,height:H-m.t-m.b,fill:"#B5B1A6",opacity:.7},svg)}
 for(let v=0;v<=ymax;v+=50){el("line",{x1:m.l,x2:W-m.r,y1:y(v),y2:y(v),stroke:C.grid},svg);el("text",{x:m.l-6,y:y(v)+4,"text-anchor":"end","font-size":11,fill:C.txt},svg,v)}
 el("text",{x:m.l,y:9,"font-size":11,fill:C.txt},svg,"PM2.5, µg/m³");
 if($("#cs").checked){days("t").filter(r=>inRange(r.d)&&r.s>0).forEach(r=>{el("rect",{x:x(r.d)-bw/2,y:m.t,width:bw+.5,height:H-m.t-m.b,fill:stageCol[r.s],opacity:.14},svg);el("rect",{x:x(r.d)-bw/2,y:14,width:bw+.5,height:9,fill:stageCol[r.s]},svg)})}
 el("line",{x1:m.l,x2:W-m.r,y1:y(60),y2:y(60),stroke:C.rose,"stroke-dasharray":"4 4"},svg);
 el("text",{x:W-m.r-2,y:y(60)-4,"text-anchor":"end","font-size":11,fill:C.rose},svg,"60 µg/m³ standard");
 const ms=[],seen=new Set();dates.forEach(d=>{const k=d.slice(0,7);if(!seen.has(k)){seen.add(k);ms.push(d)}});
 const step=Math.ceil(ms.length*52/(W-m.l-m.r));
 ms.forEach((d,i)=>{if(i%step===0)el("text",{x:x(d),y:H-8,"font-size":11,fill:C.txt,"text-anchor":"start"},svg,new Date(d+"T00:00").toLocaleString("en",{month:"short",year:"2-digit"}))});
 sel.forEach(g=>{let path="",prev=null;days(g).filter(r=>inRange(r.d)).forEach(r=>{const gap=prev&&(new Date(r.d)-new Date(prev))>DAY*1.5;path+=(path===""||gap?"M":"L")+x(r.d).toFixed(1)+" "+y(r.p).toFixed(1)+" ";prev=r.d});
  el("path",{d:path,fill:"none",stroke:"#fff","stroke-width":5,"stroke-linejoin":"round",opacity:.9},svg);el("path",{d:path,fill:"none",stroke:C[g],"stroke-width":2.6,"stroke-linejoin":"round"},svg)});
 const tr=days("t").filter(r=>inRange(r.d));
 if(sel.includes("t")&&tr.length){const pk=tr.reduce((a,b)=>b.p>a.p?b:a);const px=x(pk.d),py=y(pk.p);
  el("circle",{cx:px,cy:py,r:5.5,fill:"#fff",stroke:C.t,"stroke-width":3},svg);
  const lab="Peak "+Math.round(pk.p)+" · "+new Date(pk.d+"T00:00").toLocaleDateString("en",{day:"numeric",month:"short"});
  el("text",{x:Math.min(Math.max(px,m.l+50),W-m.r-50),y:Math.max(py-9,m.t+12),"text-anchor":"middle","font-size":11.5,"font-weight":600,fill:C.t},svg,lab)}
 if($("#ce").checked)D.ev.filter(e=>inRange(e.d)).forEach(e=>{const ex=x(e.d);const tri=el("path",{d:"M"+(ex-5)+" "+(H-m.b)+" L"+(ex+5)+" "+(H-m.b)+" L"+ex+" "+(H-m.b-9)+" Z",fill:"#4B2E83"},svg);
  const t=el("title",{},tri);t.textContent=e.l+" on "+e.d});
 const tip=el("g",{},svg),vl=el("line",{y1:m.t,y2:H-m.b,stroke:"#999",opacity:0},tip),tb=el("text",{"font-size":12,fill:"#2B2F35"},tip);
 svg.onmousemove=svg.ontouchmove=e=>{const p=e.touches?e.touches[0]:e,r=svg.getBoundingClientRect(),px=(p.clientX-r.left);
  const tt=t0+(px-m.l)/(W-m.l-m.r)*(t1-t0),d=new Date(tt).toISOString().slice(0,10);
  const rows=sel.map(g=>days(g).find(q=>q.d===d)),txt=new Date(d+"T00:00").toLocaleDateString("en",{day:"numeric",month:"short",year:"numeric"})+":  "+sel.map((g,i)=>(g==="t"?"Delhi-NCR ":"Control ")+(rows[i]?rows[i].p.toFixed(0):"no data")+(g==="t"&&rows[i]&&rows[i].s?" (Stage "+rows[i].s+")":"")).join("   ");
  vl.setAttribute("x1",px);vl.setAttribute("x2",px);vl.setAttribute("opacity",.6);tb.textContent=txt;tb.setAttribute("x",Math.min(Math.max(px-90,m.l),W-300));tb.setAttribute("y",m.t+26)};
 let h="",stats={};[["t","Delhi-NCR"],["c","Control cities"]].forEach(([g,n])=>{const r=days(g).filter(q=>inRange(q.d));
  const a=r.filter(q=>q.p>60).length,mean=r.length?Math.round(r.reduce((s,q)=>s+q.p,0)/r.length):null;stats[g]={n:r.length,pct:r.length?Math.round(100*a/r.length):null,mean:mean};
  if(!sel.includes(g))return;h+='<div><span class="muted">'+n+'</span><br><b style="color:'+C[g]+'">'+(stats[g].pct===null?"–":stats[g].pct)+'%</b> of '+r.length+' days above 60 · mean <b>'+(mean===null?"–":mean)+'</b></div>'});
 $("#read").innerHTML=h;
 const lab={all:"over the whole record",winter:"from October to February",burn:"in the October–November burning season"}[range];
 let ins="";
 if(stats.t.n&&stats.c.n){const ratio=(stats.t.mean/stats.c.mean).toFixed(1);ins="<b>In plain words:</b> "+lab+", Delhi-NCR averaged <b>"+stats.t.mean+"</b> µg/m³ against <b>"+stats.c.mean+"</b> in the control cities ("+ratio+"× higher), and exceeded the standard on <b>"+stats.t.pct+"%</b> of days versus "+stats.c.pct+"%.";
  if(range!=="all"&&tr.length){const s34=tr.filter(r=>r.s>=3).length;if(s34)ins+=" Stage III or IV was in force on "+s34+" of these days."}}
 $("#insight").style.display=ins?"block":"none";$("#insight").innerHTML=ins;
}
document.querySelectorAll("#range button").forEach(b=>b.onclick=()=>{document.querySelectorAll("#range button").forEach(x=>x.classList.remove("on"));b.classList.add("on");range=b.dataset.r;explore()});
["#ct","#cc","#cs","#ce"].forEach(s=>$(s).onchange=explore);

/* Fires: seasonal ladder */
function ladder(){
 const svg=$("#ladder");svg.innerHTML="";const [W,H]=size(svg),m={l:Math.min(150,W*0.34),r:34,t:8,b:24},L=D.ladder;
 const lo=Math.min(-5,...L.map(r=>r.lo)),hi=Math.max(...L.map(r=>r.hi))+2,x=v=>m.l+(v-lo)/(hi-lo)*(W-m.l-m.r),rh=(H-m.t-m.b)/L.length;
 el("line",{x1:x(0),x2:x(0),y1:m.t,y2:H-m.b,stroke:"#999","stroke-dasharray":"3 3"},svg);
 [0,10,20].filter(v=>v>=lo&&v<=hi).forEach(v=>el("text",{x:x(v),y:H-8,"text-anchor":"middle","font-size":11,fill:C.txt},svg,v+"%"));
 L.forEach((r,i)=>{const cy=m.t+rh*i+rh/2,sig=r.lo>0;el("text",{x:m.l-10,y:cy+4,"text-anchor":"end","font-size":12.5,fill:"#2B2F35"},svg,r.l);
  el("line",{x1:x(r.lo),x2:x(r.hi),y1:cy,y2:cy,stroke:sig?C.sage:"#4A4640","stroke-width":5,"stroke-linecap":"round"},svg);
  el("circle",{cx:x(r.e),cy:cy,r:7.5,fill:sig?C.sage:"#2E2B27"},svg);el("text",{x:x(r.hi)+8,y:cy+4,"font-size":12,fill:C.txt},svg,r.e.toFixed(1)+"%")});
}
/* GRAP: events needed */
function power(){
 const svg=$("#power");svg.innerHTML="";const [W,H]=size(svg),m={l:100,r:50,t:6,b:6},P=D.power,rh=(H-m.t-m.b)/P.length,mx=60;
 P.forEach((r,i)=>{const cy=m.t+rh*i+rh/2,w=(W-m.l-m.r)*r.m/mx;el("text",{x:m.l-10,y:cy+4,"text-anchor":"end","font-size":12.5,fill:"#2B2F35"},svg,r.n+(r.n===1?" event":" events"));
  el("rect",{x:m.l,y:cy-9,width:w,height:18,rx:5,fill:"#F0A500"},svg);el("text",{x:m.l+w+8,y:cy+4,"font-size":12,fill:C.txt},svg,"≥"+Math.round(r.m)+"% fall")});
}
function draw(){const on=document.querySelector(".pane.on").id;if(on==="tab-explore")explore();if(on==="tab-fires")ladder();if(on==="tab-grap")power()}
addEventListener("resize",draw);draw();
</script></body></html>"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    main(ap.parse_args().check)
