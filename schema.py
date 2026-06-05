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


def map_extraction(ext):
    """AI extraction JSON -> partial pitch-data (financials + company name)."""
    if not isinstance(ext, dict):
        return {}
    fin, comp = {}, {}
    if ext.get("companyName"):
        comp["name"] = str(ext["companyName"])
    rev = ext.get("revenue")
    if isinstance(rev, list) and any(v not in (None, "") for v in rev):
        fin["revenue"] = [("" if v in (None, "") else v) for v in rev[:3]] + [""] * (3 - len(rev[:3]))
    for key in ("grossMarginPct", "smPct", "rdPct", "gaPct", "daPct"):
        arr = ext.get(key)
        if isinstance(arr, list) and any(v not in (None, "") for v in arr):
            fin[key] = [_disp(v) for v in arr[:3]]
    if ext.get("taxRate") not in (None, ""):
        fin["taxRate"] = _disp(ext["taxRate"])
    pg = ext.get("projGrowth")
    if isinstance(pg, list) and any(v not in (None, "") for v in pg):
        fin["projGrowth"] = [_disp(v) for v in pg[:2]]
    segs = ext.get("segments")
    if isinstance(segs, list) and any(isinstance(s, dict) and s.get("name") for s in segs):
        fin["segments"] = [{"name": str(s.get("name") or "Segment"),
                            "vals": [(("" if v in (None, "") else v))
                                     for v in (s.get("vals") or [])[:3]]}
                           for s in segs[:6] if isinstance(s, dict)]
    out = {}
    if comp:
        out["company"] = comp
    if fin:
        out["financials"] = fin
    return out


def build_pitch(extraction=None, overrides=None):
    data = copy.deepcopy(DEFAULT)
    if extraction:
        data = deep_merge(data, map_extraction(extraction))
    if overrides:
        data = deep_merge(data, overrides)
    return data
