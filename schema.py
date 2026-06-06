"""Pitch-data schema + helpers: a complete default record, a deep-merge,
and a mapper that turns the AI extraction JSON into pitch-data fields."""
import copy

DEFAULT = {
    "company": {"name": "", "tagline": "", "sector": "", "geography": "", "founded": "",
                "website": "", "model": "", "revenueModel": "", "contractLength": "",
                "grossMarginHl": "", "uvp": "", "marketPosition": "", "defensibility": ""},
    "financials": {"revenue": ["", "", ""], "grossMarginPct": ["", "", "", "", ""],
                   "smPct": ["", "", "", "", ""], "rdPct": ["", "", "", "", ""],
                   "gaPct": ["", "", "", "", ""], "daPct": ["", "", "", "", ""],
                   "projGrowth": ["", ""], "taxRate": "",
                   "segments": [{"name": "Core platform", "vals": ["", "", ""]},
                                {"name": "Expansion modules", "vals": ["", "", ""]},
                                {"name": "Services", "vals": ["", "", ""]}]},
    "unitEcon": {"recurringPct": "", "acv": "", "grossMarginPct": "", "crossSell": "",
                 "nrr": "", "logoRetention": "", "nps": "", "customers": ""},
    "products": [{"name": "", "tag": "CORE", "pct": "", "desc": ""},
                 {"name": "", "tag": "EXPANSION", "pct": "", "desc": ""},
                 {"name": "", "tag": "SERVICES", "pct": "", "desc": ""}],
    "customers": {"logos": ["", "", "", "", "", ""], "quote": "", "quoteName": "",
                  "quoteTitle": "", "quoteCompany": ""},
    "market": {"tam": "", "tamCagr": "", "sam": "", "samCagr": "", "som": "", "somCagr": "",
               "trends": ["", "", "", ""]},
    "risks": [{"name": "", "likelihood": "", "impact": "", "mitigation": ""}],
    "competition": {"axisX": "Breadth of Platform", "axisY": "Depth / Performance",
                    "players": [{"name": ""}, {"name": ""}, {"name": ""}]},
    "roadmap": [{"year": "", "title": "", "desc": ""}],
    "team": {"members": [{"name": "", "role": "", "bio": ""}], "headcount": "", "tenure": "", "attrition": ""},
    "valuation": {"wacc": "11.5", "terminalGrowth": "3.0", "netDebt": "", "shares": "",
                  "capexWcPct": "18", "fcfGrowth": ["18", "14", "10"]},
    "comps": [],
    "deal": {"ev": "", "evEbitda": "", "evRev": "", "structure": "Cash-free, debt-free",
             "stake": "100% equity", "timelineWeeks": "12",
             "buyers": [{"text": "", "fit": "High fit"}, {"text": "", "fit": "High fit"}]},
    "timeline": [
        {"name": "Preparation & marketing materials", "owner": "Advisor", "start": "0", "duration": "3"},
        {"name": "Buyer outreach & NDAs", "owner": "Advisor", "start": "2", "duration": "3"},
        {"name": "Management presentations", "owner": "Mgmt", "start": "4", "duration": "2"},
        {"name": "Data room & due diligence", "owner": "Buyer/Advisor", "start": "5", "duration": "5"},
        {"name": "Indicative offers (LOI)", "owner": "Buyer", "start": "8", "duration": "2"},
        {"name": "Confirmatory diligence", "owner": "Buyer", "start": "10", "duration": "3"},
        {"name": "SPA negotiation & signing", "owner": "Legal", "start": "12", "duration": "2"},
        {"name": "Close & completion", "owner": "All", "start": "14", "duration": "1"}],
    "contact": {"advisor": "", "firm": "", "email": "", "phone": "", "project": "Project Meridian", "date": ""},
}


def deep_merge(base, override):
    """Recursively merge override into base. Lists and scalars from override win
    (when non-empty); dicts merge key-by-key."""
    if isinstance(base, dict) and isinstance(override, dict):
        out = copy.deepcopy(base)
        for k, v in override.items():
            out[k] = deep_merge(out.get(k), v) if k in out else copy.deepcopy(v)
        return out
    if override in (None, "", [], {}):
        return copy.deepcopy(base)
    return copy.deepcopy(override)


def _disp(x):
    """Decimal (0-1) -> display percent (0-100), else passthrough."""
    try:
        f = float(x)
        return round(f * 100, 1) if 0 < f <= 1 else f
    except (TypeError, ValueError):
        return ""


def _disp_ratio(x):
    """For metrics that routinely exceed 100% (e.g. NRR ~ 0.8-1.5): treat a value
    of 3 or less as a ratio and scale to a percent; leave already-percent values."""
    try:
        f = float(x)
        return round(f * 100, 1) if 0 < f <= 3 else f
    except (TypeError, ValueError):
        return ""


def _keep(v):
    return v not in (None, "")


def map_extraction(ext):
    """AI extraction JSON -> partial pitch-data. Maps financials AND the full
    narrative set (company, market, competition, products, team, customers, comps)
    that the model drafts from the documents + web research."""
    if not isinstance(ext, dict):
        return {}
    out = {}

    # ---- company (narrative scalars) ----
    comp = {}
    for src, dst in [("companyName", "name"), ("sector", "sector"), ("tagline", "tagline"),
                     ("geography", "geography"), ("founded", "founded"), ("website", "website"),
                     ("revenueModel", "revenueModel"), ("contractLength", "contractLength"),
                     ("uvp", "uvp"), ("marketPosition", "marketPosition"),
                     ("defensibility", "defensibility")]:
        if _keep(ext.get(src)):
            comp[dst] = str(ext[src])

    # ---- financials ----
    fin = {}
    rev = ext.get("revenue")
    if isinstance(rev, list) and any(_keep(v) for v in rev):
        fin["revenue"] = [("" if not _keep(v) else v) for v in rev[:3]] + [""] * (3 - len(rev[:3]))
    for key in ("grossMarginPct", "smPct", "rdPct", "gaPct", "daPct"):
        arr = ext.get(key)
        if isinstance(arr, list) and any(_keep(v) for v in arr):
            fin[key] = [_disp(v) for v in arr[:3]]
    if _keep(ext.get("taxRate")):
        fin["taxRate"] = _disp(ext["taxRate"])
    pg = ext.get("projGrowth")
    if isinstance(pg, list) and any(_keep(v) for v in pg):
        fin["projGrowth"] = [_disp(v) for v in pg[:2]]
    segs = ext.get("segments")
    if isinstance(segs, list) and any(isinstance(s, dict) and s.get("name") for s in segs):
        fin["segments"] = [{"name": str(s.get("name") or "Segment"),
                            "vals": [("" if not _keep(v) else v) for v in (s.get("vals") or [])[:3]]}
                           for s in segs[:6] if isinstance(s, dict)]

    # ---- unit economics (percent fields as decimals -> display) ----
    ue_src = ext.get("unitEcon") or {}
    ue = {}
    if _keep(ue_src.get("nrr")):
        ue["nrr"] = _disp_ratio(ue_src["nrr"])
    for k in ("recurringPct", "grossMarginPct", "logoRetention", "crossSell"):
        if _keep(ue_src.get(k)):
            ue[k] = _disp(ue_src[k])
    for k in ("nps", "acv", "customers"):
        if _keep(ue_src.get(k)):
            ue[k] = ue_src[k]

    # ---- products ----
    products = None
    prods = ext.get("products")
    if isinstance(prods, list) and any(isinstance(p, dict) and p.get("name") for p in prods):
        products = [{"name": str(p.get("name") or ""), "tag": str(p.get("tag") or "CORE"),
                     "pct": (_disp(p["pct"]) if _keep(p.get("pct")) else ""),
                     "desc": str(p.get("desc") or "")}
                    for p in prods[:6] if isinstance(p, dict)]

    # ---- customers ----
    cu_src = ext.get("customers") or {}
    cust = {}
    if isinstance(cu_src.get("logos"), list):
        logos = [str(x) for x in cu_src["logos"] if _keep(x)]
        if logos:
            cust["logos"] = logos
    for k in ("quote", "quoteName", "quoteTitle", "quoteCompany"):
        if _keep(cu_src.get(k)):
            cust[k] = str(cu_src[k])

    # ---- market ($B sizes plain; CAGR as decimals) ----
    mk_src = ext.get("market") or {}
    mkt = {}
    for k in ("tam", "sam", "som"):
        if _keep(mk_src.get(k)):
            mkt[k] = mk_src[k]
    for k in ("tamCagr", "samCagr", "somCagr"):
        if _keep(mk_src.get(k)):
            mkt[k] = _disp(mk_src[k])
    if isinstance(mk_src.get("trends"), list):
        tr = [str(x) for x in mk_src["trends"] if _keep(x)]
        if tr:
            mkt["trends"] = tr

    # ---- competition ----
    cp_src = ext.get("competition") or {}
    comp_sec = {}
    if _keep(cp_src.get("axisX")):
        comp_sec["axisX"] = str(cp_src["axisX"])
    if _keep(cp_src.get("axisY")):
        comp_sec["axisY"] = str(cp_src["axisY"])
    pls = cp_src.get("players")
    if isinstance(pls, list) and any(isinstance(p, dict) and p.get("name") for p in pls):
        comp_sec["players"] = [dict({"name": str(p.get("name") or "")},
                                    **({"strength": p["strength"]} if _keep(p.get("strength")) else {}))
                               for p in pls[:6] if isinstance(p, dict)]

    # ---- roadmap ----
    roadmap = None
    rd = ext.get("roadmap")
    if isinstance(rd, list) and any(isinstance(r, dict) and r.get("title") for r in rd):
        roadmap = [{"year": str(r.get("year") or ""), "title": str(r.get("title") or ""),
                    "desc": str(r.get("desc") or "")} for r in rd[:8] if isinstance(r, dict)]

    # ---- team ----
    tm_src = ext.get("team") or {}
    team = {}
    if _keep(tm_src.get("headcount")):
        team["headcount"] = tm_src["headcount"]
    if _keep(tm_src.get("tenure")):
        team["tenure"] = tm_src["tenure"]
    if _keep(tm_src.get("attrition")):
        team["attrition"] = _disp(tm_src["attrition"])
    mem = tm_src.get("members")
    if isinstance(mem, list) and any(isinstance(m, dict) and m.get("name") for m in mem):
        team["members"] = [{"name": str(m.get("name") or ""), "role": str(m.get("role") or ""),
                            "bio": str(m.get("bio") or "")} for m in mem[:8] if isinstance(m, dict)]

    # ---- comps ($M) ----
    comps = None
    cmp_src = ext.get("comps")
    if isinstance(cmp_src, list) and any(isinstance(c, dict) and c.get("name") for c in cmp_src):
        comps = [{"name": str(c.get("name") or ""), "rev": c.get("rev", ""),
                  "ebitda": c.get("ebitda", ""), "ev": c.get("ev", "")}
                 for c in cmp_src[:8] if isinstance(c, dict)]

    # ---- deal multiples (AI estimate; EV/price stays advisor-provided) ----
    dl_src = ext.get("deal") or {}
    deal = {}
    for k in ("evEbitda", "evRev"):
        if _keep(dl_src.get(k)):
            deal[k] = dl_src[k]

    if comp:     out["company"] = comp
    if fin:      out["financials"] = fin
    if ue:       out["unitEcon"] = ue
    if products: out["products"] = products
    if cust:     out["customers"] = cust
    if mkt:      out["market"] = mkt
    if comp_sec: out["competition"] = comp_sec
    if roadmap:  out["roadmap"] = roadmap
    if team:     out["team"] = team
    if comps:    out["comps"] = comps
    if deal:     out["deal"] = deal
    return out


def build_pitch(extraction=None, overrides=None):
    data = copy.deepcopy(DEFAULT)
    if extraction:
        data = deep_merge(data, map_extraction(extraction))
    if overrides:
        data = deep_merge(data, overrides)
    return data
