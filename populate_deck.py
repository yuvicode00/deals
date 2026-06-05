"""Populate the tokenized pitch deck from a pitch-data dict.
Faithful Python port of the browser tokenMap() so server and client agree."""
import os, re

_TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deck_template.html")


def _num(v, d):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _money(v):
    f = _num(v, None)
    if f is None:
        return "$X.XM"
    return f"${int(f)}M" if f == int(f) else f"${f:.1f}M"


def _P(v, fb):
    if v is None:
        return fb
    s = str(v).strip()
    return fb if s == "" else s


def _gi(arr, i, dfl):
    if isinstance(arr, list) and i < len(arr) and arr[i] not in (None, ""):
        return _num(arr[i], dfl)
    return dfl


def token_map(d):
    f = d.get("financials", {})
    ue = d.get("unitEcon", {})
    co = d.get("company", {})
    mk = d.get("market", {})
    dl = d.get("deal", {})
    ct = d.get("contact", {})
    tm = d.get("team", {})
    revsrc = f.get("revenue", []) or []
    rev = [_num((revsrc[i] if i < len(revsrc) else 0), 0) for i in range(3)]
    maxR = max(rev + [1])
    cagr = round((pow(rev[2] / rev[0], 0.5) - 1) * 100) if rev[0] > 0 else "XX"

    gm = _gi(f.get("grossMarginPct"), 2, 72)
    sm = _gi(f.get("smPct"), 2, 26)
    rd = _gi(f.get("rdPct"), 2, 14)
    ga = _gi(f.get("gaPct"), 2, 10)
    e = gm - sm - rd - ga
    ebitda_margin = round(e) if e > 0 else 24
    ebitda_ltm = round(rev[2] * (e if e > 0 else 24) / 100 * 10) / 10

    gm_hl = co.get("grossMarginHl") or ue.get("grossMarginPct")
    acv_v = ue.get("acv")
    m = {
        "company_name": _P(co.get("name"), "[COMPANY NAME]"),
        "tagline": _P(co.get("tagline"), "[One-line positioning statement.]"),
        "sector": _P(co.get("sector"), "[Industry]"),
        "geography": _P(co.get("geography"), "[Geography]"),
        "rev_ltm": _money(rev[2]) if rev[2] else "$X.XM",
        "rev_first": _money(rev[0]) if rev[0] else "$X.XM",
        "rev_ltm_num": rev[2] or "27.9",
        "rev0": rev[0] or "0", "rev1": rev[1] or "0", "rev2": rev[2] or "0",
        "rev0c": _money(rev[0]) if rev[0] else "$0",
        "rev1c": _money(rev[1]) if rev[1] else "$0",
        "rev2c": _money(rev[2]) if rev[2] else "$0",
        "h0": round(rev[0] / maxR * 100) or 40,
        "h1": round(rev[1] / maxR * 100) or 60,
        "h2": round(rev[2] / maxR * 100) or 100,
        "growth_yoy": ("+" + str(round((rev[2] / rev[1] - 1) * 100)) + "%") if rev[1] > 0 else "+XX%",
        "cagr_pct": f"{cagr}%", "cagr_num": cagr or 50,
        "gross_margin": _P(gm_hl, "XX") + "%",
        "gross_margin_num": _num(gm_hl, 72),
        "ebitda_margin_num": ebitda_margin,
        "ebitda_ltm_num": ebitda_ltm,
        "customers_num": _num(ue.get("customers"), 1240),
        "nrr_num": _num(ue.get("nrr"), 118),
        "recurring_pct": _P(ue.get("recurringPct"), "XX") + "%",
        "nrr_pct": _P(ue.get("nrr"), "XXX") + "%",
        "logo_ret_num": _num(ue.get("logoRetention"), 94),
        "nps_num": _num(ue.get("nps"), 62),
        "revenue_model": _P(co.get("revenueModel"), "Recurring · Subscription"),
        "contract_length": _P(co.get("contractLength"), "[12–36 mo]"),
        "uvp": _P(co.get("uvp"), "[The only solution that delivers X, Y and Z in one platform.]"),
        "market_position": _P(co.get("marketPosition"), "[Top 3 player; #1 in segment.]"),
        "defensibility": _P(co.get("defensibility"), "[Proprietary data, switching costs and network effects.]"),
        "tam": _P(mk.get("tam"), "XX"), "tam_cagr": _P(mk.get("tamCagr"), "XX") + "%",
        "sam": _P(mk.get("sam"), "X.X"), "som": _P(mk.get("som"), "XXX"),
        "deal_price": _money(dl.get("ev")) if dl.get("ev") else "$XX.XM",
        "deal_evebitda": _P(dl.get("evEbitda"), "XX.X") + "x",
        "deal_evrev": _P(dl.get("evRev"), "X.X") + "x",
        "deal_structure": _P(dl.get("structure"), "[Cash-free, debt-free]"),
        "deal_stake": _P(dl.get("stake"), "[100% equity]"),
        "deal_weeks": "[~" + _P(dl.get("timelineWeeks"), "12") + " weeks]",
        "advisor": _P(ct.get("advisor"), "[Advisor]"), "firm": _P(ct.get("firm"), "[Firm]"),
        "email": _P(ct.get("email"), "[name@firm.com]"), "phone": _P(ct.get("phone"), "[+xxx]"),
        "date": _P(ct.get("date"), "[Month, Year]"), "project": _P(ct.get("project"), "Project Meridian"),
        "headcount": _P(tm.get("headcount"), "XX"), "tenure": _P(tm.get("tenure"), "X"),
        "attrition": _P(tm.get("attrition"), "XX") + "%",
        "acv": ("$" + f"{float(acv_v):,.0f}") if (acv_v not in (None, "") and _num(acv_v, None) is not None) else "$XX,XXX",
        "crosssell": _P(ue.get("crossSell"), "XX") + "%",
    }
    prods = d.get("products", []) or []
    tags = ["CORE", "EXPANSION", "SERVICES"]
    for i in range(3):
        p = prods[i] if i < len(prods) else {}
        m[f"prod{i}_name"] = _P(p.get("name"), f"[Product {i+1}]")
        m[f"prod{i}_tag"] = _P(p.get("tag"), tags[i] if i < 3 else "LINE")
        m[f"prod{i}_pct"] = _P(p.get("pct"), "XX")
        m[f"prod{i}_desc"] = _P(p.get("desc"), "[Offering description.]")
    members = (tm.get("members") or [])
    for i in range(4):
        t = members[i] if i < len(members) else {}
        m[f"team{i}_name"] = _P(t.get("name"), "[Name]")
        m[f"team{i}_role"] = _P(t.get("role"), "[Role]")
        m[f"team{i}_bio"] = _P(t.get("bio"), "[Short bio.]")
    road = d.get("roadmap", []) or []
    for i in range(5):
        r = road[i] if i < len(road) else {}
        m[f"road{i}_yr"] = _P(r.get("year"), f"FY[+{i}]")
        m[f"road{i}_title"] = _P(r.get("title"), "[Milestone]")
        m[f"road{i}_desc"] = _P(r.get("desc"), "[Description.]")
    comp = d.get("competition", {}) or {}
    m["comp_x"] = _P(comp.get("axisX"), "Breadth of Platform")
    m["comp_y"] = _P(comp.get("axisY"), "Depth / Performance")
    players = comp.get("players", []) or []
    for i in range(3):
        c = players[i] if i < len(players) else {}
        m[f"comp{i}_name"] = _P(c.get("name"), "[Competitor " + chr(65 + i) + "]")
    cust = d.get("customers", {}) or {}
    logos = cust.get("logos", []) or []
    for i in range(6):
        m[f"logo{i}"] = _P(logos[i] if i < len(logos) else None, "[LOGO]")
    m["quote"] = _P(cust.get("quote"), "[A short, specific testimonial about measurable results.]")
    m["quote_name"] = _P(cust.get("quoteName"), "[Customer Name]")
    m["quote_title"] = _P(cust.get("quoteTitle"), "[Title]")
    m["quote_company"] = _P(cust.get("quoteCompany"), "[Company]")
    buyers = dl.get("buyers", []) or []
    for i in range(2):
        b = buyers[i] if i < len(buyers) else {}
        m[f"buyer{i}_text"] = _P(b.get("text"), "[Ideal buyer profile.]")
        m[f"buyer{i}_fit"] = _P(b.get("fit"), "High fit")
    return m


def populate(data, template_path=_TPL):
    tpl = open(template_path, encoding="utf-8").read()
    m = token_map(data)
    return re.sub(r"\{\{(\w+)\}\}", lambda g: str(m.get(g.group(1), g.group(0))), tpl)


if __name__ == "__main__":
    import json, sys
    data = json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 else {}
    out = populate(data)
    left = sorted(set(re.findall(r"\{\{(\w+)\}\}", out)))
    sys.stderr.write(f"unresolved tokens: {left}\n")
    sys.stdout.write(out)
