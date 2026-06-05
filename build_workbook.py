#!/usr/bin/env python3
"""
build_workbook.py
=================
Generates a 7-sheet, IB-grade M&A research workbook for [COMPANY NAME].

Conventions (Goldman Sachs model standard):
  - BLUE font  = hardcoded inputs / assumptions a user may change for scenarios
  - BLACK font = formulas & calculations
All derived numbers are LIVE Excel formulas (recalculated by LibreOffice afterwards),
never hardcoded Python results, so the model stays dynamic.

Sheets:
  1. Executive Dashboard   - KPI cards, sparklines, 3-light status, conditional formats
  2. Financial Model       - P&L + revenue-by-segment, 3yr actual + 2yr proj, assumptions
  3. Valuation Summary     - DCF, comps multiples, value-bridge WATERFALL chart
  4. Comparable Companies  - 7 peers, trading multiples, subject row color-coded
  5. Market & Industry     - TAM/CAGR, trends, risk register (icon set)
  6. Sensitivity Analysis  - two 2-variable tables w/ heat-map color scales
  7. Transaction Timeline  - Gantt (stacked-bar chart) + phase table
"""
import xlsxwriter
import json, os, re as _re

# ============================================================
# pitch-data.json — optional single source of truth (from the
# intake app). When present, its values drive the blue INPUT
# cells; every formula stays intact. Missing fields fall back
# to the built-in illustrative defaults.
# ============================================================
PITCH = {}
for _p in [os.environ.get("PITCH_JSON", ""),
           "/home/claude/acquisition-pitch/intake/pitch-data.json",
           "/mnt/user-data/outputs/pitch-data.json",
           os.path.join(os.path.dirname(os.path.abspath(__file__)), "pitch-data.json"),
           "pitch-data.json"]:
    if _p and os.path.exists(_p):
        try:
            PITCH = json.load(open(_p, encoding="utf-8"))
            print(f"[pitch-data] loaded inputs from {_p}")
            break
        except Exception as _e:
            print(f"[pitch-data] could not parse {_p}: {_e}")
if not PITCH:
    print("[pitch-data] none found — using built-in placeholder defaults")

def pget(path, d=None):
    cur = PITCH
    for k in str(path).split("."):
        if isinstance(cur, list):
            try: cur = cur[int(k)]
            except (ValueError, IndexError): return d
        elif isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return d
        if cur is None or cur == "":
            return d
    return d if cur in (None, "") else cur

def fnum(path, d):           # number from path
    try: return float(pget(path))
    except (TypeError, ValueError): return d
def fpct(path, d):           # decimal from path (accepts 72 or 0.72)
    try:
        f = float(pget(path)); return f/100.0 if f > 1.0 else f
    except (TypeError, ValueError): return d
def fstr(path, d):
    v = pget(path); return str(v) if v not in (None, "") else d
def fnv(v, d):               # number from raw value
    try: return float(v)
    except (TypeError, ValueError): return d
def fpv(v, d):               # decimal from raw value
    try:
        f = float(v); return f/100.0 if f > 1.0 else f
    except (TypeError, ValueError): return d
def p5(path, defs):          # 5-year % assumption row as decimals
    return [fpct(f"{path}.{i}", defs[i]) for i in range(5)]

COMPANY = fstr("company.name", "[COMPANY NAME]")
_slug = _re.sub(r'[^A-Za-z0-9]+', '_', COMPANY).strip('_') or "Company"
OUT = os.environ.get("OUT_XLSX") or os.path.join(os.getcwd(), f"{_slug}_MA_Analysis.xlsx")

wb = xlsxwriter.Workbook(OUT, {"nan_inf_to_errors": True})

# ----------------------------------------------------------------------------
# PALETTE  (navy / gold to match the pitch deck)
# ----------------------------------------------------------------------------
NAVY   = "#0B1020"   # deep title band
NAVY2  = "#16203A"   # section subheaders
NAVY3  = "#1F2C4D"   # alt / hover
GOLD   = "#C8A24B"
GOLD_L = "#E4C778"
BLUE   = "#4F8BFF"
PAPER  = "#FFFFFF"
GREY_L = "#F4F6FB"   # zebra
INK    = "#1A2233"
MUT    = "#6B7689"
POS    = "#1E7F4F"
NEG    = "#C0392B"
INPUT_BLUE = "#0000FF"   # IB input-cell convention

CCY      = '$#,##0.0;($#,##0.0);"-"'         # $ millions, 1 dp
CCY0     = '$#,##0;($#,##0);"-"'              # $ whole
PCT      = '0.0%;(0.0%);"-"'
PCT0     = '0%;(0%);"-"'
MULT     = '0.0"x"'
NUM      = '#,##0;(#,##0);"-"'
NUM1     = '#,##0.0'

def F(**kw):
    return wb.add_format(kw)

# core formats -----------------------------------------------------------------
fmt = {
 "title":   F(font_name="Arial", font_size=18, bold=True, font_color=GOLD,  bg_color=NAVY, valign="vcenter", indent=1),
 "subtitle":F(font_name="Arial", font_size=10, font_color="#C4CCDC",        bg_color=NAVY, valign="vcenter", indent=1),
 "band_r":  F(bg_color=NAVY),
 "sect":    F(font_name="Arial", font_size=11, bold=True, font_color=GOLD_L, bg_color=NAVY2, valign="vcenter", indent=1, border=1, border_color=NAVY3),
 "colhdr":  F(font_name="Arial", font_size=9.5, bold=True, font_color="#FFFFFF", bg_color=NAVY2, align="center", valign="vcenter", border=1, border_color=NAVY3, text_wrap=True),
 "colhdr_l":F(font_name="Arial", font_size=9.5, bold=True, font_color="#FFFFFF", bg_color=NAVY2, align="left", valign="vcenter", border=1, border_color=NAVY3, indent=1),
 "rowlbl":  F(font_name="Arial", font_size=10, font_color=INK, align="left", indent=1, border=1, border_color="#D6DCE8"),
 "rowlbl_b":F(font_name="Arial", font_size=10, bold=True, font_color=INK, align="left", indent=1, border=1, border_color="#D6DCE8"),
 "note":    F(font_name="Arial", font_size=8.5, italic=True, font_color=MUT),
 "src":     F(font_name="Arial", font_size=8.5, italic=True, font_color=MUT, align="left", indent=1),
}

def cell(num, *, inp=False, bold=False, total=False, pct=False, mult=False, ccy=True, whole=False, center=False):
    """Build a value format with IB color convention."""
    o = dict(font_name="Arial", font_size=10, border=1, border_color="#D6DCE8")
    o["font_color"] = INPUT_BLUE if inp else INK
    if bold:  o["bold"] = True
    if total: o.update(top=2, bottom=6, bg_color="#EEF1F8", bold=True, border_color=NAVY3)
    if center:o["align"] = "center"
    if pct:   o["num_format"] = PCT
    elif mult:o["num_format"] = MULT
    elif whole:o["num_format"] = CCY0 if ccy else NUM
    else:     o["num_format"] = CCY if ccy else NUM1
    return wb.add_format(o)

# common cell-format cache
IN_C  = cell(0, inp=True)            # blue currency input
IN_P  = cell(0, inp=True, pct=True)  # blue percent input
IN_N  = cell(0, inp=True, ccy=False) # blue number input
CA_C  = cell(0)                      # black currency calc
CA_P  = cell(0, pct=True)
CA_M  = cell(0, mult=True)
CA_N  = cell(0, ccy=False)
TOT_C = cell(0, total=True)
TOT_P = cell(0, total=True, pct=True)

def setup(ws, title, n_last_col="J"):
    """Stamp the navy title band, footer, gridline + page setup on a sheet."""
    ws.hide_gridlines(2)
    ws.set_paper(9)               # A4
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.set_margins(0.4, 0.4, 0.6, 0.6)
    ws.repeat_rows(0, 2)
    ws.set_footer(
        f'&L&"Arial"&8&KC0392BSTRICTLY PRIVATE & CONFIDENTIAL'
        f'&C&"Arial"&8&K6B7689{COMPANY} — Project Meridian'
        f'&R&"Arial"&8&K6B7689Page &P of &N')
    last = n_last_col
    ws.merge_range(f"A1:{last}1", COMPANY, fmt["title"])
    ws.merge_range(f"A2:{last}2", title, fmt["subtitle"])
    ws.set_row(0, 30); ws.set_row(1, 18); ws.set_row(2, 6)
    ws.merge_range(f"A3:{last}3", "", fmt["band_r"])

# =============================================================================
# 1. EXECUTIVE DASHBOARD
# =============================================================================
d = wb.add_worksheet("1. Exec Dashboard")
setup(d, "Executive Dashboard  ·  Investment Snapshot", "L")
d.set_column("A:A", 2)
d.set_column("B:L", 11.5)

kpi_lbl = F(font_name="Arial", font_size=9, bold=True, font_color=MUT, bg_color="#FFFFFF",
            align="left", top=2, left=2, right=2, top_color=GOLD, left_color="#E1E6F0", right_color="#E1E6F0", indent=1, valign="vcenter")
kpi_val = F(font_name="Arial", font_size=22, bold=True, font_color=NAVY, bg_color="#FFFFFF",
            align="left", left=2, right=2, left_color="#E1E6F0", right_color="#E1E6F0", indent=1, valign="vcenter")
kpi_sub = F(font_name="Arial", font_size=9, font_color=POS, bg_color="#FFFFFF",
            align="left", bottom=2, left=2, right=2, bottom_color="#E1E6F0", left_color="#E1E6F0", right_color="#E1E6F0", indent=1, valign="vcenter")

# KPI cards (each 3 rows x 3 cols)  ------------------------------------------
cards = [
    ("REVENUE (LTM)", '=\'2. Financial Model\'!E8', CCY, "+50% 3-yr CAGR", POS),
    ("EBITDA (LTM)",  '=\'2. Financial Model\'!E16', CCY, "24% margin", POS),
    ("ENTERPRISE VALUE", '=\'3. Valuation Summary\'!C26', CCY, "Mid-point estimate", MUT),
    ("NET REVENUE RETENTION", 1.18, PCT0, "Expansion > churn", POS),
]
r = 5
positions = [("B","D"),("E","G"),("H","J"),("K","L")]
# 4 cards across columns
col_starts = ["B","E","H","K"]
for i,(lbl,val,nf,sub,subcol) in enumerate(cards):
    c0 = col_starts[i]
    c1 = chr(ord(c0)+2) if i < 3 else "L"
    d.merge_range(f"{c0}{r}:{c1}{r}", lbl, kpi_lbl)
    vfmt = F(font_name="Arial", font_size=22, bold=True, font_color=NAVY, bg_color="#FFFFFF",
             align="left", left=2, right=2, left_color="#E1E6F0", right_color="#E1E6F0", indent=1, valign="vcenter", num_format=nf)
    if isinstance(val,str):
        d.merge_range(f"{c0}{r+1}:{c1}{r+1}", "", vfmt)
        d.write_formula(f"{c0}{r+1}", val, vfmt)
    else:
        d.merge_range(f"{c0}{r+1}:{c1}{r+1}", val, vfmt)
    sfmt = F(font_name="Arial", font_size=9, font_color=subcol, bg_color="#FFFFFF",
             align="left", bottom=2, left=2, right=2, bottom_color="#E1E6F0", left_color="#E1E6F0", right_color="#E1E6F0", indent=1, valign="vcenter")
    d.merge_range(f"{c0}{r+2}:{c1}{r+2}", sub, sfmt)
d.set_row(r-1, 6); d.set_row(r, 16); d.set_row(r+1, 30); d.set_row(r+2, 16)

# Revenue trend + sparkline block -------------------------------------------
r2 = 10
d.merge_range(f"B{r2}:L{r2}", "Revenue Trajectory ($M) — FY[-2] → FY[+2]", fmt["sect"])
yrs = ["FY[-2]","FY[-1]","FY[0]","FY[+1]E","FY[+2]E"]
d.write_row(f"B{r2+1}", [""]+yrs, fmt["colhdr"])
d.write(f"B{r2+2}", "Revenue", fmt["rowlbl_b"])
# pull from Financial Model row 8 (C..G) onto THIS row so the sparkline below reads it
for j,col in enumerate(["C","D","E","F","G"]):
    d.write_formula(f"{col}{r2+2}", f"='2. Financial Model'!{col}8", cell(0, bold=(j==2)))
d.write(f"B{r2+3}", "Spark", fmt["rowlbl"])
d.add_sparkline(f"C{r2+3}", {  # one sparkline spanning the row visual
    "range": f"'1. Exec Dashboard'!C{r2+2}:G{r2+2}",
    "type": "column", "markers": False, "series_color": GOLD, "high_point": True, "high_color": NAVY})
d.merge_range(f"D{r2+3}:G{r2+3}",
              "▲ Column sparkline reads the row above — replace inputs and it redraws.", fmt["note"])

# Scorecard with 3-light traffic system -------------------------------------
r3 = 15
d.merge_range(f"B{r3}:L{r3}", "Investment Scorecard  ·  Traffic-Light Status", fmt["sect"])
d.write_row(f"B{r3+1}", ["Metric","Actual","Target","vs Target","Status"], fmt["colhdr"])
d.merge_range(f"G{r3+1}:L{r3+1}", "Commentary", fmt["colhdr_l"])
score = [
    ("Revenue growth (YoY)", 0.49, 0.30, "[Outperforming plan]"),
    ("Gross margin",         0.72, 0.65, "[Software-grade economics]"),
    ("EBITDA margin",        0.24, 0.20, "[Profitable and scaling]"),
    ("Net revenue retention",1.18, 1.10, "[Healthy expansion]"),
    ("Customer diversification (1−top-10)", 0.78, 0.70, "[Well spread across logos]"),
    ("Cash runway",          0.95, 0.80, "[Self-funding]"),
]
rr = r3+2
for k,(m,act,tgt,note) in enumerate(score):
    d.write(f"B{rr}", m, fmt["rowlbl"])
    d.write_number(f"C{rr}", act, cell(0, inp=True, pct=True))
    d.write_number(f"D{rr}", tgt, cell(0, inp=True, pct=True))
    d.write_formula(f"E{rr}", f"=C{rr}-D{rr}", cell(0, pct=True))     # delta
    d.write_formula(f"F{rr}", f"=C{rr}/D{rr}-1", cell(0, pct=True, center=True))  # ratio drives icon
    d.merge_range(f"G{rr}:L{rr}", note, fmt["rowlbl"])
    rr += 1
# 3-traffic-light icon set on the ratio column F
d.conditional_format(f"F{r3+2}:F{rr-1}", {
    "type": "icon_set", "icon_style": "3_traffic_lights", "icons_only": False,
    "icons": [{"criteria": ">=", "type": "number", "value": 0.05},
              {"criteria": ">=", "type": "number", "value": -0.05}]})
# data bars on the delta column E for quick scan
d.conditional_format(f"E{r3+2}:E{rr-1}", {"type":"data_bar","bar_color":GOLD})

d.merge_range(f"B{rr+1}:L{rr+1}",
    "Source: Company management accounts (illustrative placeholders). Replace with audited figures in the data room.", fmt["src"])

# =============================================================================
# 2. FINANCIAL MODEL
# =============================================================================
m = wb.add_worksheet("2. Financial Model")
setup(m, "Financial Model  ·  P&L, Segments & Projections ($M)", "G")
m.set_column("A:A", 1.5)
m.set_column("B:B", 30)
m.set_column("C:G", 12.5)

m.write_row("C5", ["FY[-2]A","FY[-1]A","FY[0]A","FY[+1]E","FY[+2]E"], fmt["colhdr"])
m.write("B5", "($ in millions)", fmt["colhdr_l"])

# --- Assumptions block (blue inputs) ---
m.merge_range("B7:G7", "Income Statement  ·  P&L ($M)", fmt["sect"])
# growth & margin assumption rows live below the P&L for reference; define here
# We'll put assumptions at rows 25+ and reference them.

# --- P&L ---
# Revenue: actuals are inputs (C..E), projections are formulas using growth assumption
m.write("B8", "Total revenue", fmt["rowlbl_b"])
for col,val in zip("CDE",[fnum("financials.revenue.0",12.4),fnum("financials.revenue.1",18.7),fnum("financials.revenue.2",27.9)]):
    m.write_number(f"{col}8", val, cell(0, inp=True, bold=True))
m.write_formula("F8", "=E8*(1+F26)", cell(0, bold=True))   # F26 = proj growth yr1
m.write_formula("G8", "=F8*(1+G26)", cell(0, bold=True))

m.write("B9", "  Growth %", fmt["rowlbl"])
m.write("C9", "", CA_P)
for col,prev in zip("DEFG","CDEF"):
    m.write_formula(f"{col}9", f"={col}8/{prev}8-1", CA_P)

m.write("B10", "COGS", fmt["rowlbl"])
for col in "CDEFG":
    m.write_formula(f"{col}10", f"=-{col}8*(1-{col}24)", CA_C)  # 24 = gross margin

m.write("B11", "Gross profit", fmt["rowlbl_b"])
for col in "CDEFG":
    m.write_formula(f"{col}11", f"={col}8+{col}10", cell(0, bold=True))
m.write("B12", "  Gross margin %", fmt["rowlbl"])
for col in "CDEFG":
    m.write_formula(f"{col}12", f"={col}11/{col}8", CA_P)

m.write("B13", "Sales & marketing", fmt["rowlbl"])
m.write("B14", "R&D", fmt["rowlbl"])
m.write("B15", "G&A", fmt["rowlbl"])
for r_,assume in [(13,27),(14,28),(15,29)]:
    for col in "CDEFG":
        m.write_formula(f"{col}{r_}", f"=-{col}8*{col}{assume}", CA_C)

m.write("B16", "EBITDA", fmt["rowlbl_b"])
for col in "CDEFG":
    m.write_formula(f"{col}16", f"={col}11+{col}13+{col}14+{col}15", cell(0, bold=True, total=False))
m.write("B17", "  EBITDA margin %", fmt["rowlbl"])
for col in "CDEFG":
    m.write_formula(f"{col}17", f"={col}16/{col}8", CA_P)

m.write("B18", "D&A", fmt["rowlbl"])
for col in "CDEFG":
    m.write_formula(f"{col}18", f"=-{col}8*{col}30", CA_C)
m.write("B19", "EBIT", fmt["rowlbl_b"])
for col in "CDEFG":
    m.write_formula(f"{col}19", f"={col}16+{col}18", cell(0, bold=True))
m.write("B20", "Taxes @ rate", fmt["rowlbl"])
for col in "CDEFG":
    m.write_formula(f"{col}20", f"=-MAX({col}19,0)*$C$31", CA_C)
m.write("B21", "Net operating profit (NOPAT)", fmt["rowlbl_b"])
for col in "CDEFG":
    m.write_formula(f"{col}21", f"={col}19+{col}20", cell(0, total=True))

# --- Assumptions detail (rows 24-31) ---
m.write("B23", "Assumptions  (blue = input, change for scenarios)", fmt["sect"])
m.merge_range("B23:G23", "Assumptions  (blue = input, change for scenarios)", fmt["sect"])
arows = [
    (24, "Gross margin %",         p5("financials.grossMarginPct",[0.68,0.70,0.72,0.73,0.74]), PCT),
    (26, "Revenue growth % (proj)",[None,None,None, fpct("financials.projGrowth.0",0.40), fpct("financials.projGrowth.1",0.32)], PCT),
    (27, "S&M % of revenue",       p5("financials.smPct",[0.30,0.28,0.26,0.25,0.24]), PCT),
    (28, "R&D % of revenue",       p5("financials.rdPct",[0.16,0.15,0.14,0.14,0.13]), PCT),
    (29, "G&A % of revenue",       p5("financials.gaPct",[0.12,0.11,0.10,0.10,0.09]), PCT),
    (30, "D&A % of revenue",       p5("financials.daPct",[0.03,0.03,0.03,0.03,0.03]), PCT),
]
for r_,lbl,vals,nf in arows:
    m.write(f"B{r_}", "  "+lbl, fmt["rowlbl"])
    for col,v in zip("CDEFG", vals):
        if v is None:
            m.write(f"{col}{r_}", "", cell(0, inp=True, pct=True))
        else:
            m.write_number(f"{col}{r_}", v, cell(0, inp=True, pct=True))
m.write("B25", "  (Growth % above is derived for actuals)", fmt["note"])
m.write("B31", "  Tax rate (single)", fmt["rowlbl"])
m.write_number("C31", fpct("financials.taxRate",0.23), cell(0, inp=True, pct=True))
m.merge_range("D31:G31", "← applied to all projection years", fmt["note"])

# --- Revenue by segment ---
m.merge_range("B33:G33", "Revenue by Segment ($M)", fmt["sect"])
m.write_row("C34", ["FY[-2]A","FY[-1]A","FY[0]A","FY[+1]E","FY[+2]E"], fmt["colhdr"])
m.write("B34", "Segment", fmt["colhdr_l"])
seg = []
_segj = pget("financials.segments")
if isinstance(_segj, list) and any(isinstance(_s, dict) and _s.get("name") for _s in _segj):
    for _s in _segj[:6]:
        vs = _s.get("vals") or []
        seg.append((str(_s.get("name") or "Segment"), [fnv((vs[i] if i < len(vs) else None), 0.0) for i in range(3)]))
else:
    seg = [("Core platform",[7.0,10.5,16.2]), ("Expansion modules",[3.2,5.4,8.1]), ("Services",[2.2,2.8,3.6])]
sr = 35
for name,vals in seg:
    m.write(f"B{sr}", name, fmt["rowlbl"])
    for col,v in zip("CDE", vals):
        m.write_number(f"{col}{sr}", v, cell(0, inp=True))
    # projections grow with total revenue growth assumption
    m.write_formula(f"F{sr}", f"=E{sr}*(1+$F$26)", CA_C)
    m.write_formula(f"G{sr}", f"=F{sr}*(1+$G$26)", CA_C)
    sr += 1
m.write(f"B{sr}", "Total", fmt["rowlbl_b"])
for col in "CDEFG":
    m.write_formula(f"{col}{sr}", f"=SUM({col}35:{col}{sr-1})", cell(0, total=True))
m.write(f"B{sr+1}", "  Check vs P&L revenue", fmt["note"])
for col in "CDEFG":
    m.write_formula(f"{col}{sr+1}", f"={col}{sr}-{col}8", cell(0, ccy=True))  # should be ~0

# --- Combo chart: revenue (columns) + EBITDA margin (line) ---
combo_col = wb.add_chart({"type": "column"})
combo_col.add_series({
    "name": "Revenue ($M)",
    "categories": "='2. Financial Model'!$C$5:$G$5",
    "values": "='2. Financial Model'!$C$8:$G$8",
    "fill": {"color": GOLD}, "border": {"none": True},
    "data_labels": {"value": True, "num_format": '$#,##0.0', "font": {"name":"Arial","size":8,"color":NAVY}}})
line = wb.add_chart({"type": "line"})
line.add_series({
    "name": "EBITDA margin %",
    "categories": "='2. Financial Model'!$C$5:$G$5",
    "values": "='2. Financial Model'!$C$17:$G$17",
    "line": {"color": BLUE, "width": 2.25},
    "marker": {"type": "circle", "size": 6, "fill": {"color": BLUE}},
    "y2_axis": True})
combo_col.combine(line)
combo_col.set_title({"name": "Revenue & EBITDA Margin", "name_font": {"name":"Arial","size":11,"color":NAVY}})
combo_col.set_x_axis({"num_font":{"name":"Arial","size":9}})
combo_col.set_y_axis({"name":"$M","major_gridlines":{"visible":True,"line":{"color":"#E8ECF4"}},"num_font":{"name":"Arial","size":9}})
combo_col.set_y2_axis({"name":"Margin %","num_format":"0%","num_font":{"name":"Arial","size":9}})
combo_col.set_legend({"position":"bottom","font":{"name":"Arial","size":9}})
combo_col.set_chartarea({"border":{"none":True}})
combo_col.set_size({"width": 760, "height": 300})
m.insert_chart("B43", combo_col)

# =============================================================================
# 3. VALUATION SUMMARY
# =============================================================================
v = wb.add_worksheet("3. Valuation Summary")
setup(v, "Valuation Summary  ·  DCF, Comparable Multiples & Value Bridge", "H")
v.set_column("A:A", 1.5)
v.set_column("B:B", 30)
v.set_column("C:H", 13)

# --- DCF assumptions ---
v.merge_range("B5:H5", "Discounted Cash Flow  (blue = input)", fmt["sect"])
v.write("B6", "WACC", fmt["rowlbl"]);            v.write_number("C6", fpct("valuation.wacc",0.115), cell(0, inp=True, pct=True))
v.write("B7", "Terminal growth (g)", fmt["rowlbl"]); v.write_number("C7", fpct("valuation.terminalGrowth",0.030), cell(0, inp=True, pct=True))
v.write("B8", "Net debt", fmt["rowlbl"]);        v.write_number("C8", fnum("valuation.netDebt",2.5), cell(0, inp=True))
v.write("D6", "Tax rate", fmt["rowlbl"]);        v.write_number("E6", fpct("financials.taxRate",0.23), cell(0, inp=True, pct=True))
v.write("D7", "Shares (m)", fmt["rowlbl"]);      v.write_number("E7", fnum("valuation.shares",10.0), cell(0, inp=True, ccy=False))

# --- FCF projection (5 yrs) ---
v.write_row("D10", ["Yr 1","Yr 2","Yr 3","Yr 4","Yr 5"], fmt["colhdr"])
v.write("B10", "Free cash flow build ($M)", fmt["colhdr_l"])
v.write("B11", "EBITDA", fmt["rowlbl"])
# pull FY+1, FY+2 EBITDA from model then grow remaining at fading rate
v.write_formula("D11", "='2. Financial Model'!F16", CA_C)
v.write_formula("E11", "='2. Financial Model'!G16", CA_C)
v.write("B14", "  FCF growth (yr3-5)", fmt["rowlbl"]); 
_fcg = {"F":fpct("valuation.fcfGrowth.0",0.18), "G":fpct("valuation.fcfGrowth.1",0.14), "H":fpct("valuation.fcfGrowth.2",0.10)}
for col in ["F","G","H"]:
    v.write_number(f"{col}14", _fcg[col], cell(0, inp=True, pct=True))
v.write_formula("F11", "=E11*(1+F14)", CA_C)
v.write_formula("G11", "=F11*(1+G14)", CA_C)
v.write_formula("H11", "=G11*(1+H14)", CA_C)
v.write("B12", "less: capex & WC (% EBITDA)", fmt["rowlbl"])
v.write_number("C12", fpct("valuation.capexWcPct",0.18), cell(0, inp=True, pct=True))
for col in "DEFGH":
    v.write_formula(f"{col}13", f"={col}11*(1-$C$12)*(1-$E$6)", CA_C)  # unlevered FCF after tax
v.write("B13", "Unlevered FCF", fmt["rowlbl_b"])
v.write("B15", "Discount factor", fmt["rowlbl"])
for i,col in enumerate("DEFGH", start=1):
    v.write_formula(f"{col}15", f"=1/(1+$C$6)^{i}", cell(0, ccy=False, ))
v.write("B16", "PV of FCF", fmt["rowlbl_b"])
for col in "DEFGH":
    v.write_formula(f"{col}16", f"={col}13*{col}15", cell(0, bold=True))

# --- Terminal value + EV ---
v.merge_range("B18:H18", "Enterprise & Equity Value", fmt["sect"])
v.write("B19", "Sum PV of FCF", fmt["rowlbl"]);     v.write_formula("C19", "=SUM(D16:H16)", CA_C)
v.write("B20", "Terminal value (Gordon)", fmt["rowlbl"]); v.write_formula("C20", "=H13*(1+C7)/(C6-C7)", CA_C)
v.write("B21", "PV of terminal value", fmt["rowlbl"]);    v.write_formula("C21", "=C20*H15", CA_C)
v.write("B22", "  TV as % of EV", fmt["note"]);     v.write_formula("C22", "=C21/(C19+C21)", CA_P)
v.write("B23", "Enterprise value (DCF)", fmt["rowlbl_b"]); v.write_formula("C23", "=C19+C21", cell(0, total=True))
v.write("B24", "less: net debt", fmt["rowlbl"]);    v.write_formula("C24", "=-C8", CA_C)
v.write("B25", "Equity value (DCF)", fmt["rowlbl_b"]); v.write_formula("C25", "=C23+C24", cell(0, total=True))
v.write("B26", "EV — selected (mid)", fmt["rowlbl_b"]); v.write_formula("C26", "=AVERAGE(C23,G31)", cell(0, total=True))
v.write("B27", "Implied EV/EBITDA", fmt["rowlbl"]); v.write_formula("C27", "=C23/'2. Financial Model'!E16", CA_M)
v.write("B28", "Implied equity / share", fmt["rowlbl"]); v.write_formula("C28", "=C25/E7", cell(0))

# --- Comps-implied valuation (mini) ---
v.merge_range("E19:H19", "Comparable-multiple cross-check", fmt["colhdr_l"])
v.write_row("F20", ["Metric","Multiple","Implied EV"], fmt["colhdr"])
v.write("E20", "Method", fmt["colhdr_l"])
v.write("E21", "EV / EBITDA", fmt["rowlbl"])
v.write_formula("F21", "='2. Financial Model'!E16", CA_C)
v.write_formula("G21", "='4. Comparable Companies'!I13", CA_M)  # median EV/EBITDA (col I)
v.write_formula("H21", "=F21*G21", CA_C)
v.write("E22", "EV / Revenue", fmt["rowlbl"])
v.write_formula("F22", "='2. Financial Model'!E8", CA_C)
v.write_formula("G22", "='4. Comparable Companies'!H13", CA_M)  # median EV/Rev (col H)
v.write_formula("H22", "=F22*G22", CA_C)
v.write("E31", "Comps mid EV", fmt["rowlbl_b"])
v.write_formula("G31", "=AVERAGE(H21:H22)", cell(0, total=True))

# --- Value-bridge WATERFALL (stacked-column technique) ---
# Bridge: PV FCF -> +PV Terminal -> EV -> -Net debt -> Equity value
v.merge_range("B30:D30", "Value Bridge ($M)", fmt["sect"])
wf_labels = ["PV of FCF","PV terminal","Enterprise\nvalue","less Net\ndebt","Equity\nvalue"]
v.write_row("C33", wf_labels, fmt["colhdr"])
v.write("B33", "Waterfall data", fmt["colhdr_l"])
# rows: base(invisible) / down / up , columns C..G
v.write("B34", "Base (hidden)", fmt["rowlbl"])
v.write("B35", "Increase", fmt["rowlbl"])
v.write("B36", "Decrease", fmt["rowlbl"])
v.write("B37", "Total", fmt["rowlbl"])
# C: PV FCF (total), D: PV terminal (increase on top of C), E: EV (total), F: net debt (decrease), G: equity (total)
# Base row
v.write_formula("C34", "=0", cell(0, ccy=True, ))
v.write_formula("D34", "=C19", cell(0))                      # sits on top of PV FCF
v.write_formula("E34", "=0", cell(0))
v.write_formula("F34", "=C25", cell(0))                      # equity value level (top of decrease)
v.write_formula("G34", "=0", cell(0))
# Increase row
v.write_formula("C35", "=C19", cell(0))
v.write_formula("D35", "=C21", cell(0))
v.write_formula("E35", "=0", cell(0))
v.write_formula("F35", "=0", cell(0))
v.write_formula("G35", "=0", cell(0))
# Decrease row
v.write_formula("C36", "=0", cell(0))
v.write_formula("D36", "=0", cell(0))
v.write_formula("E36", "=0", cell(0))
v.write_formula("F36", "=C8", cell(0))                       # net debt magnitude
v.write_formula("G36", "=0", cell(0))
# Total row (EV and Equity shown as totals)
v.write_formula("C37", "=0", cell(0))
v.write_formula("D37", "=0", cell(0))
v.write_formula("E37", "=C23", cell(0))                      # EV total bar
v.write_formula("F37", "=0", cell(0))
v.write_formula("G37", "=C25", cell(0))                      # Equity total bar
# need E34 base for EV total = 0 (already), F34 base for equity total handled via decrease stack

wf = wb.add_chart({"type": "column", "subtype": "stacked"})
cats = "='3. Valuation Summary'!$C$33:$G$33"
wf.add_series({"name":"base","categories":cats,"values":"='3. Valuation Summary'!$C$34:$G$34",
               "fill":{"none":True},"border":{"none":True}})
wf.add_series({"name":"Increase","categories":cats,"values":"='3. Valuation Summary'!$C$35:$G$35",
               "fill":{"color":GOLD},"border":{"none":True}})
wf.add_series({"name":"Decrease","categories":cats,"values":"='3. Valuation Summary'!$C$36:$G$36",
               "fill":{"color":NEG},"border":{"none":True}})
wf.add_series({"name":"Total","categories":cats,"values":"='3. Valuation Summary'!$C$37:$G$37",
               "fill":{"color":NAVY},"border":{"none":True},
               "data_labels":{"value":True,"num_format":'$#,##0.0;;',"font":{"name":"Arial","size":8,"color":NAVY}}})
wf.set_title({"name":"Value Bridge: DCF Enterprise → Equity Value","name_font":{"name":"Arial","size":11,"color":NAVY}})
wf.set_x_axis({"num_font":{"name":"Arial","size":8.5}})
wf.set_y_axis({"name":"$M","major_gridlines":{"visible":True,"line":{"color":"#E8ECF4"}},"num_font":{"name":"Arial","size":9}})
wf.set_legend({"none":True})
wf.set_chartarea({"border":{"none":True}})
wf.set_size({"width":620,"height":300})
v.insert_chart("E33", wf)

# =============================================================================
# 4. COMPARABLE COMPANIES
# =============================================================================
c = wb.add_worksheet("4. Comparable Companies")
setup(c, "Comparable Company Analysis  ·  Trading Multiples", "I")
c.set_column("A:A", 1.5)
c.set_column("B:B", 24)
c.set_column("C:I", 12.5)

c.write_row("C5", ["Revenue\n($M)","EBITDA\n($M)","EBITDA\nmargin","Rev growth\n(YoY)","EV ($M)","EV /\nRevenue","EV /\nEBITDA"], fmt["colhdr"])
c.write("B5", "Company", fmt["colhdr_l"])
# peers: name, rev, ebitda, growth, EV  (margin, multiples are formulas)
_compj = pget("comps")
_crows = []
if isinstance(_compj, list):
    for _c in _compj:
        if isinstance(_c, dict) and _c.get("name") and _c.get("ev") not in (None, "") and _c.get("ebitda") not in (None, ""):
            try:
                _crows.append((str(_c.get("name")), float(_c.get("rev") or 0), float(_c.get("ebitda")),
                               fpv(_c.get("growth"), 0.25), float(_c.get("ev"))))
            except (TypeError, ValueError):
                pass
if len(_crows) >= 3:
    peers = _crows
else:
    peers = [
        ("[Peer Alpha Inc.]",  142.0, 31.2, 0.22, 500.0),
        ("[Peer Beta Corp.]",   88.5, 15.9, 0.31, 240.0),
        ("[Peer Gamma Ltd.]",  205.0, 49.2, 0.18, 835.0),
        ("[Peer Delta SaaS]",   54.0, 10.3, 0.44, 195.0),
        ("[Peer Epsilon AG]",  120.0, 24.0, 0.27, 360.0),
        ("[Peer Zeta Group]",  176.0, 33.4, 0.20, 470.0),
        ("[Peer Eta Co.]",      67.0, 12.7, 0.36, 230.0),
    ]
row = 6
first = row
for name,rev,eb,grw,ev in peers:
    c.write(f"B{row}", name, fmt["rowlbl"])
    c.write_number(f"C{row}", rev, cell(0, inp=True))
    c.write_number(f"D{row}", eb,  cell(0, inp=True))
    c.write_formula(f"E{row}", f"=D{row}/C{row}", CA_P)
    c.write_number(f"F{row}", grw, cell(0, inp=True, pct=True))
    c.write_number(f"G{row}", ev,  cell(0, inp=True))
    c.write_formula(f"H{row}", f"=G{row}/C{row}", CA_M)   # EV/Rev
    c.write_formula(f"I{row}", f"=G{row}/D{row}", CA_M)   # EV/EBITDA
    row += 1
last = row-1
# stats
def stat_row(lbl, fn, rr):
    c.write(f"B{rr}", lbl, fmt["rowlbl_b"])
    c.write_formula(f"C{rr}", f"={fn}(C{first}:C{last})", cell(0, total=True))
    c.write_formula(f"D{rr}", f"={fn}(D{first}:D{last})", cell(0, total=True))
    c.write_formula(f"E{rr}", f"={fn}(E{first}:E{last})", cell(0, total=True, pct=True))
    c.write_formula(f"F{rr}", f"={fn}(F{first}:F{last})", cell(0, total=True, pct=True))
    c.write_formula(f"G{rr}", f"={fn}(G{first}:G{last})", cell(0, total=True, mult=True))
    c.write_formula(f"H{rr}", f"={fn}(H{first}:H{last})", cell(0, total=True, mult=True))
    c.write_formula(f"I{rr}", f"={fn}(I{first}:I{last})", cell(0, total=True, mult=True))
stat_row("Mean",   "AVERAGE", 13)   # NOTE row 13 referenced by Valuation sheet (median below)
# fix: put median on 13 (referenced), mean on 14
c.write("B13", "Median", fmt["rowlbl_b"])
for col in "CDEFGHI":
    nf = (PCT if col in "EF" else (MULT if col in "GHI" else CCY))
    o = dict(font_name="Arial",font_size=10,top=2,bottom=6,bg_color="#EEF1F8",bold=True,border_color=NAVY3,num_format=nf,font_color=INK)
    c.write_formula(f"{col}13", f"=MEDIAN({col}{first}:{col}{last})", wb.add_format(o))
c.write("B14", "Mean", fmt["rowlbl_b"])
for col in "CDEFGHI":
    nf = (PCT if col in "EF" else (MULT if col in "GHI" else CCY))
    c.write_formula(f"{col}14", f"=AVERAGE({col}{first}:{col}{last})", cell(0, pct=(col in "EF"), mult=(col in "GHI"), ccy=(col in "CDG")))
c.write("B15", "Min", fmt["rowlbl"])
c.write("B16", "Max", fmt["rowlbl"])
for fn,rr in [("MIN",15),("MAX",16)]:
    for col in "GHI":
        c.write_formula(f"{col}{rr}", f"={fn}({col}{first}:{col}{last})", cell(0, mult=True))

# subject company row (color-coded)
c.write("B18", "Subject Company", fmt["sect"]); c.merge_range("B18:I18", "Subject Company  vs  Peer Set", fmt["sect"])
c.write("B19", COMPANY, fmt["rowlbl_b"])
subj_fill = F(font_name="Arial",font_size=10,bg_color="#FBF3DD",border=1,border_color=GOLD,font_color=NAVY,bold=True,num_format=CCY)
subj_pct  = F(font_name="Arial",font_size=10,bg_color="#FBF3DD",border=1,border_color=GOLD,font_color=NAVY,bold=True,num_format=PCT)
subj_m    = F(font_name="Arial",font_size=10,bg_color="#FBF3DD",border=1,border_color=GOLD,font_color=NAVY,bold=True,num_format=MULT)
c.write_formula("C19", "='2. Financial Model'!E8",  subj_fill)
c.write_formula("D19", "='2. Financial Model'!E16", subj_fill)
c.write_formula("E19", "=D19/C19", subj_pct)
c.write_formula("F19", "='2. Financial Model'!E9",  subj_pct)
c.write_formula("G19", "='3. Valuation Summary'!C26", subj_fill)
c.write_formula("H19", "=G19/C19", subj_m)
c.write_formula("I19", "=G19/D19", subj_m)
c.write("B20", "Premium / (discount) to peer median (EV/EBITDA)", fmt["rowlbl"])
c.merge_range("B20:F20", "Premium / (discount) to peer median (EV/EBITDA)", fmt["rowlbl"])
c.write_formula("G20", "=I19/I13-1", cell(0, pct=True, bold=True))

# color-code multiples columns vs peer set (green=cheap, red=rich)
c.conditional_format(f"H{first}:H{last}", {"type":"3_color_scale",
    "min_color":"#1E7F4F","mid_color":"#FFF2CC","max_color":"#C0392B"})
c.conditional_format(f"I{first}:I{last}", {"type":"3_color_scale",
    "min_color":"#1E7F4F","mid_color":"#FFF2CC","max_color":"#C0392B"})
c.merge_range("B22:I22", "Green = lower multiple (cheaper) · Red = higher. Source: public filings / market data (illustrative).", fmt["src"])

# =============================================================================
# 5. MARKET & INDUSTRY RESEARCH
# =============================================================================
k = wb.add_worksheet("5. Market & Industry")
setup(k, "Market & Industry Research  ·  Analyst Brief", "H")
k.set_column("A:A", 1.5); k.set_column("B:B", 30); k.set_column("C:H", 13)

k.merge_range("B5:H5", "Market Sizing & Growth", fmt["sect"])
k.write_row("C6", ["FY[0]","FY[+1]","FY[+2]","FY[+3]","FY[+4]","CAGR"], fmt["colhdr"])
k.write("B6", "($B unless noted)", fmt["colhdr_l"])
mkt = [("Total addressable market (TAM)", fnum("market.tam",42.0), fpct("market.tamCagr",0.14)),
       ("Serviceable market (SAM)",        fnum("market.sam",9.5),  fpct("market.samCagr",0.16)),
       ("Obtainable / target (SOM)",       fnum("market.som",0.42), fpct("market.somCagr",0.28))]
mr = 7
for name,base,cagr in mkt:
    k.write(f"B{mr}", name, fmt["rowlbl_b"] if mr==7 else fmt["rowlbl"])
    k.write_number(f"C{mr}", base, cell(0, inp=True))
    k.write_number(f"H{mr}", cagr, cell(0, inp=True, pct=True))   # cagr input drives projection
    for col,prev in zip("DEFG","CDEF"):
        k.write_formula(f"{col}{mr}", f"={prev}{mr}*(1+$H{mr})", CA_C)
    mr += 1

# market growth column chart
mc = wb.add_chart({"type":"column"})
for i,(name,_,_) in enumerate(mkt):
    mc.add_series({"name":f"='5. Market & Industry'!$B${7+i}",
                   "categories":"='5. Market & Industry'!$C$6:$G$6",
                   "values":f"='5. Market & Industry'!$C${7+i}:$G${7+i}",
                   "fill":{"color":[BLUE,GOLD,NAVY][i]},"border":{"none":True}})
mc.set_title({"name":"Market Expansion ($B)","name_font":{"name":"Arial","size":11,"color":NAVY}})
mc.set_legend({"position":"bottom","font":{"name":"Arial","size":9}})
mc.set_y_axis({"major_gridlines":{"visible":True,"line":{"color":"#E8ECF4"}},"num_font":{"name":"Arial","size":9}})
mc.set_x_axis({"num_font":{"name":"Arial","size":9}})
mc.set_chartarea({"border":{"none":True}})
mc.set_size({"width":440,"height":250})
k.insert_chart("B12", mc)

# key trends
k.merge_range("F11:H11", "Key Demand Drivers", fmt["sect"])
_tr = pget("market.trends")
if isinstance(_tr, list) and any(str(x).strip() for x in _tr):
    trends = [str(x) for x in _tr if str(x).strip()][:6]
else:
    trends = ["[Structural shift toward digital adoption in the category]",
              "[Regulatory / compliance tailwinds increasing spend]",
              "[Incumbent tech debt creating displacement opportunity]",
              "[Rising buyer willingness to consolidate vendors]"]
for i,t in enumerate(trends):
    k.merge_range(f"F{12+i}:H{12+i}", "•  "+t, fmt["rowlbl"])

# risk register w/ icon set
k.merge_range("B25:H25", "Risk Register  ·  Severity", fmt["sect"])
k.write_row("C26", ["Likelihood","Impact","Score","Sev."], fmt["colhdr"])
k.write("B26", "Risk factor", fmt["colhdr_l"])
k.merge_range("G26:H26", "Mitigation", fmt["colhdr_l"])
_rk = pget("risks")
_rrows = []
if isinstance(_rk, list):
    for r in _rk:
        if isinstance(r, dict) and r.get("name"):
            _rrows.append((str(r.get("name")), fpv(r.get("likelihood"),0.3), fpv(r.get("impact"),0.6), str(r.get("mitigation") or "")))
if _rrows:
    risks = _rrows
else:
    risks = [("[Customer concentration]",0.3,0.6,"[Diversify logos; multi-year contracts]"),
         ("[Competitive pricing pressure]",0.5,0.5,"[Deepen product moat; ROI selling]"),
         ("[Key-person dependency]",0.4,0.8,"[Retention packages; documentation]"),
         ("[Macro / budget cycles]",0.5,0.4,"[Land-and-expand; usage-based pricing]"),
         ("[Regulatory change]",0.2,0.6,"[Compliance roadmap; advisory board]")]
rr = 27
for name,lk,im,mit in risks:
    k.write(f"B{rr}", name, fmt["rowlbl"])
    k.write_number(f"C{rr}", lk, cell(0, inp=True, pct=True))
    k.write_number(f"D{rr}", im, cell(0, inp=True, pct=True))
    k.write_formula(f"E{rr}", f"=C{rr}*D{rr}", cell(0, pct=True))
    k.write_formula(f"F{rr}", f"=E{rr}", cell(0, pct=True, center=True))
    k.merge_range(f"G{rr}:H{rr}", mit, fmt["rowlbl"])
    rr += 1
k.conditional_format(f"F27:F{rr-1}", {"type":"icon_set","icon_style":"3_traffic_lights",
    "reverse_icons":True,  # high score = red
    "icons":[{"criteria":">=","type":"number","value":0.30},
             {"criteria":">=","type":"number","value":0.15}]})
k.conditional_format(f"E27:E{rr-1}", {"type":"data_bar","bar_color":NEG})
k.merge_range(f"B{rr+1}:H{rr+1}", "Score = Likelihood × Impact. Source: management & analyst assessment (illustrative).", fmt["src"])

# =============================================================================
# 6. SENSITIVITY ANALYSIS
# =============================================================================
s = wb.add_worksheet("6. Sensitivity Analysis")
setup(s, "Sensitivity Analysis  ·  Valuation Range ($M)", "I")
s.set_column("A:A", 1.5); s.set_column("B:B", 18); s.set_column("C:I", 11.5)

# Table 1: EV sensitivity to WACC (rows) x terminal growth (cols)
s.merge_range("B5:I5", "Table 1 — Enterprise Value: WACC  ×  Terminal Growth", fmt["sect"])
s.write("B6", "Base EV ($M):", fmt["rowlbl_b"])
s.write_formula("C6", "='3. Valuation Summary'!C23", cell(0, total=True))
s.write("B7", "WACC ↓ / g →", fmt["colhdr_l"])
g_vals = [0.020,0.025,0.030,0.035,0.040]
w_vals = [0.095,0.105,0.115,0.125,0.135]
# column headers (terminal growth g) in C7:G7
for j,g in enumerate(g_vals):
    s.write_number(6, 2+j, g, F(font_name="Arial",font_size=9.5,bold=True,bg_color=NAVY2,font_color="#FFFFFF",align="center",num_format=PCT,border=1,border_color=NAVY3))
# rows C8:G12
base_fcf = "'3. Valuation Summary'!$C$19"     # PV of FCF (approx const)
tv_fcf   = "'3. Valuation Summary'!$H$13"     # last yr unlevered FCF
for i,w in enumerate(w_vals):
    rrow = 8+i
    s.write_number(f"B{rrow}", w, F(font_name="Arial",font_size=9.5,bold=True,bg_color=NAVY2,font_color="#FFFFFF",align="center",num_format=PCT,border=1,border_color=NAVY3))
    for j,g in enumerate(g_vals):
        col = chr(ord("C")+j)
        # EV ≈ PV FCF (held) + [last FCF*(1+g)/(w-g)] / (1+w)^5
        s.write_formula(f"{col}{rrow}",
            f"={base_fcf}+({tv_fcf}*(1+{col}$7))/(($B{rrow}-{col}$7))/(1+$B{rrow})^5",
            cell(0))
s.conditional_format("C8:G12", {"type":"3_color_scale",
    "min_color":"#C0392B","mid_color":"#FFF2CC","max_color":"#1E7F4F"})

# Table 2: Equity value to Revenue CAGR (rows) x EBITDA margin (cols)
s.merge_range("B15:I15", "Table 2 — Implied EV: Revenue CAGR  ×  Exit EV/EBITDA", fmt["sect"])
s.write("B16", "CAGR ↓ / Mult →", fmt["colhdr_l"])
mult_vals = [12.0,14.0,16.0,18.0,20.0]
cagr_vals = [0.25,0.30,0.35,0.40,0.45]
for j,mu in enumerate(mult_vals):
    s.write_number(15, 2+j, mu, F(font_name="Arial",font_size=9.5,bold=True,bg_color=NAVY2,font_color="#FFFFFF",align="center",num_format=MULT,border=1,border_color=NAVY3))
ebit_base = "'2. Financial Model'!$E$16"   # current EBITDA
mgn       = "'2. Financial Model'!$E$17"   # ebitda margin
for i,cg in enumerate(cagr_vals):
    rrow = 17+i
    s.write_number(f"B{rrow}", cg, F(font_name="Arial",font_size=9.5,bold=True,bg_color=NAVY2,font_color="#FFFFFF",align="center",num_format=PCT,border=1,border_color=NAVY3))
    for j,mu in enumerate(mult_vals):
        col = chr(ord("C")+j)
        # implied EV = EBITDA grown 3yrs at CAGR (margin held) * exit multiple
        s.write_formula(f"{col}{rrow}",
            f"={ebit_base}*(1+$B{rrow})^3*{col}$16",
            cell(0))
s.conditional_format("C17:G21", {"type":"3_color_scale",
    "min_color":"#C0392B","mid_color":"#FFF2CC","max_color":"#1E7F4F"})
s.merge_range("B23:I23", "Heat-map: red = lower value, green = higher. Blue cells (axes) are inputs — edit to re-scope the range.", fmt["src"])

# =============================================================================
# 7. TRANSACTION TIMELINE
# =============================================================================
t = wb.add_worksheet("7. Transaction Timeline")
setup(t, "Transaction Timeline  ·  Indicative Process (Weeks)", "I")
t.set_column("A:A", 1.5); t.set_column("B:B", 26); t.set_column("C:E", 11); t.set_column("F:I", 11)

t.merge_range("B5:I5", "Process Phases", fmt["sect"])
t.write_row("C6", ["Owner","Start (wk)","Duration (wk)","End (wk)"], fmt["colhdr"])
t.write("B6", "Workstream", fmt["colhdr_l"])
_tl = pget("timeline")
_prows = []
if isinstance(_tl, list):
    for p in _tl:
        if isinstance(p, dict) and p.get("name"):
            _prows.append((str(p.get("name")), "["+str(p.get("owner") or "Owner")+"]", fnv(p.get("start"),0), fnv(p.get("duration"),1)))
if _prows:
    phases = _prows
else:
    phases = [
        ("Preparation & marketing materials", "[Advisor]",    0, 3),
        ("Buyer outreach & NDAs",             "[Advisor]",    2, 3),
        ("Management presentations",          "[Mgmt]",       4, 2),
        ("Data room & due diligence",         "[Buyer/Advisor]",5, 5),
        ("Indicative offers (LOI)",           "[Buyer]",      8, 2),
        ("Confirmatory diligence",            "[Buyer]",     10, 3),
        ("SPA negotiation & signing",         "[Legal]",     12, 2),
        ("Close & completion",                "[All]",       14, 1),
    ]
pr = 7
first_p = pr
for name,owner,start,dur in phases:
    t.write(f"B{pr}", name, fmt["rowlbl"])
    t.write(f"C{pr}", owner, fmt["rowlbl"])
    t.write_number(f"D{pr}", start, cell(0, inp=True, ccy=False, center=True))
    t.write_number(f"E{pr}", dur,   cell(0, inp=True, ccy=False, center=True))
    t.write_formula(f"F{pr}", f"=D{pr}+E{pr}", cell(0, ccy=False, center=True))
    pr += 1
last_p = pr-1
t.write(f"B{pr}", "Total elapsed (weeks)", fmt["rowlbl_b"])
t.write_formula(f"F{pr}", f"=MAX(F{first_p}:F{last_p})", cell(0, total=True, ccy=False))

# Gantt = horizontal stacked bar: invisible "start" + visible "duration"
gantt = wb.add_chart({"type":"bar","subtype":"stacked"})
catref = f"='7. Transaction Timeline'!$B${first_p}:$B${last_p}"
gantt.add_series({"name":"start","categories":catref,
                  "values":f"='7. Transaction Timeline'!$D${first_p}:$D${last_p}",
                  "fill":{"none":True},"border":{"none":True}})
gantt.add_series({"name":"Duration (weeks)","categories":catref,
                  "values":f"='7. Transaction Timeline'!$E${first_p}:$E${last_p}",
                  "fill":{"color":GOLD},"border":{"color":GOLD_L},
                  "data_labels":{"value":True,"font":{"name":"Arial","size":8,"color":NAVY}}})
gantt.set_title({"name":"Indicative Deal Timeline (~14–16 weeks)","name_font":{"name":"Arial","size":11,"color":NAVY}})
gantt.set_x_axis({"name":"Week","min":0,"major_gridlines":{"visible":True,"line":{"color":"#E8ECF4"}},"num_font":{"name":"Arial","size":9}})
gantt.set_y_axis({"reverse":True,"num_font":{"name":"Arial","size":9}})
gantt.set_legend({"none":True})
gantt.set_chartarea({"border":{"none":True}})
gantt.set_size({"width":760,"height":300})
t.insert_chart(f"B{pr+2}", gantt)

# ----------------------------------------------------------------------------
wb.close()
print("workbook written:", OUT)
