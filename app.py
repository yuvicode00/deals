"""Deal Studio — local + online server.

Pipeline: upload multi-year financial reports -> Claude extracts the figures ->
generate the full IB Excel workbook (xlsxwriter) and the populated pitch deck (HTML).

Access control (for the online/shared deployment):
  Set APP_PASSWORD to require a login (clients & partners only). If APP_PASSWORD is
  empty (e.g. running locally) the app is open and no login is shown.

Run locally:  ANTHROPIC_API_KEY=sk-... uvicorn app:app --port 8000  ->  http://localhost:8000
"""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import deque

from fastapi import FastAPI, UploadFile, File, Body, Form, Request, HTTPException
from fastapi.responses import JSONResponse, Response, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import schema
import populate_deck

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web")
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# ---- access control config ----
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
AUTH_ENABLED = bool(APP_PASSWORD)
SESSION_SECRET = os.environ.get("SESSION_SECRET") or os.urandom(24).hex()
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes")
MAX_EXTRACTS_PER_HOUR = int(os.environ.get("MAX_EXTRACTS_PER_HOUR", "60"))
# auth token is derived from the password, so changing the password logs everyone out
_AUTH_TOKEN = hmac.new(SESSION_SECRET.encode(), ("auth:" + APP_PASSWORD).encode(), hashlib.sha256).hexdigest()
OPEN_PATHS = {"/login", "/logout", "/api/health", "/favicon.ico"}

app = FastAPI(title="Deal Studio")

EXTRACT_PROMPT = (
    "You are a financial analyst. The attached file(s) are financial statements / P&L "
    "reports, possibly spanning multiple fiscal years and multiple files. Consolidate "
    "everything into ONE timeline. Return ONLY a JSON object (no prose, no markdown "
    "fences) with EXACTLY this shape. Use $ MILLIONS as decimal numbers (e.g. 12.4). "
    "Express every percentage as a decimal between 0 and 1 (0.72 = 72%). Provide the "
    "THREE most recent fiscal years in chronological order [oldest, middle, latest]. "
    "Use null for anything you cannot find. Do not invent numbers.\n"
    '{"companyName": string|null, "currencyNote": string, "years": [string,string,string], '
    '"revenue": [n,n,n], "grossMarginPct": [n,n,n], "smPct": [n,n,n], "rdPct": [n,n,n], '
    '"gaPct": [n,n,n], "daPct": [n,n,n], "taxRate": n, "projGrowth": [n,n], '
    '"segments": [{"name": string, "vals": [n,n,n]}]}'
)


def _slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", name or "Company").strip("_") or "Company"


def _authed(request: Request):
    if not AUTH_ENABLED:
        return True
    c = request.cookies.get("ds_auth", "")
    return bool(c) and hmac.compare_digest(c, _AUTH_TOKEN)


@app.middleware("http")
async def guard(request: Request, call_next):
    if AUTH_ENABLED and request.url.path not in OPEN_PATHS and not _authed(request):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return RedirectResponse("/login")
    return await call_next(request)


LOGIN_HTML = """<!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Deal Studio — כניסה</title>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;600;800&display=swap" rel="stylesheet">
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:Heebo,sans-serif;
background:radial-gradient(900px 600px at 90% -10%,rgba(79,139,255,.1),transparent),linear-gradient(180deg,#070A12,#0B1020);color:#EAEEF7}
.box{background:#0F1626;border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:34px;width:330px;text-align:center}
.dot{width:16px;height:16px;border-radius:4px;background:linear-gradient(135deg,#E4C778,#C8A24B);transform:rotate(45deg);margin:0 auto 16px;box-shadow:0 0 18px rgba(199,162,75,.6)}
h1{font-size:20px;margin:0 0 6px}p{color:#8A95AC;font-size:13px;margin:0 0 20px}
input{width:100%;background:#0B1020;border:1px solid rgba(255,255,255,.08);border-radius:10px;color:#EAEEF7;font-family:Heebo;font-size:15px;padding:12px 14px;outline:none;text-align:center}
input:focus{border-color:#C8A24B}button{width:100%;margin-top:14px;background:linear-gradient(135deg,#E4C778,#C8A24B);color:#0A0E17;border:0;border-radius:10px;font-family:Heebo;font-weight:800;font-size:15px;padding:12px;cursor:pointer}
.err{color:#F1746B;font-size:13px;margin-top:12px;min-height:16px}</style></head>
<body><form class="box" method="post" action="/login">
<div class="dot"></div><h1>Deal Studio</h1><p>גישה ללקוחות ושותפים בלבד</p>
<input type="password" name="password" placeholder="סיסמת גישה" autofocus>
<button type="submit">כניסה</button><div class="err">__ERR__</div></form></body></html>"""


@app.get("/login")
def login_page():
    return HTMLResponse(LOGIN_HTML.replace("__ERR__", ""))


@app.post("/login")
def login_submit(password: str = Form("")):
    if AUTH_ENABLED and hmac.compare_digest(password, APP_PASSWORD):
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("ds_auth", _AUTH_TOKEN, max_age=7 * 24 * 3600,
                        httponly=True, samesite="lax", secure=COOKIE_SECURE)
        return resp
    return HTMLResponse(LOGIN_HTML.replace("__ERR__", "סיסמה שגויה"), status_code=401)


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("ds_auth")
    return resp


def _block_for(upload, raw):
    ct = (upload.content_type or "").lower()
    name = (upload.filename or "").lower()
    b64 = base64.standard_b64encode(raw).decode("ascii")
    if ct == "application/pdf" or name.endswith(".pdf"):
        return {"type": "document", "source": {"type": "base64",
                "media_type": "application/pdf", "data": b64}}
    media = "image/png"
    if name.endswith((".jpg", ".jpeg")) or ct in ("image/jpeg", "image/jpg"):
        media = "image/jpeg"
    elif name.endswith(".webp") or ct == "image/webp":
        media = "image/webp"
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}}


_hits = {}
def _rate_ok(ip):
    now = time.time()
    dq = _hits.setdefault(ip, deque())
    while dq and now - dq[0] > 3600:
        dq.popleft()
    if len(dq) >= MAX_EXTRACTS_PER_HOUR:
        return False
    dq.append(now)
    return True


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL, "auth": AUTH_ENABLED,
            "has_key": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/api/extract")
async def extract(request: Request, files: list[UploadFile] = File(...)):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(400, "ANTHROPIC_API_KEY is not set on the server.")
    if not _rate_ok(request.client.host if request.client else "?"):
        raise HTTPException(429, "Rate limit reached. Please try again later.")
    try:
        from anthropic import Anthropic
    except ImportError:
        raise HTTPException(500, "The 'anthropic' package is not installed. Run: pip install -r requirements.txt")

    content = []
    for up in files:
        raw = await up.read()
        if raw:
            content.append(_block_for(up, raw))
    if not content:
        raise HTTPException(400, "No readable files were uploaded.")
    content.append({"type": "text", "text": EXTRACT_PROMPT})

    client = Anthropic()
    try:
        msg = client.messages.create(model=MODEL, max_tokens=2000,
                                     messages=[{"role": "user", "content": content}])
    except Exception as e:
        raise HTTPException(502, f"Anthropic API error: {e}")

    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    text = re.sub(r"```json|```", "", text).strip()
    try:
        extraction = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(422, f"Could not parse model output as JSON:\n{text[:1500]}")

    pitch = schema.build_pitch(extraction=extraction)
    return JSONResponse({"extraction": extraction, "pitch": pitch})


def _coerce(data):
    if not isinstance(data, dict):
        raise HTTPException(400, "Expected a pitch-data JSON object.")
    if "financials" not in data and ("revenue" in data or "companyName" in data):
        return schema.build_pitch(extraction=data)
    return schema.deep_merge(schema.DEFAULT, data)


def _build_excel(pitch, outdir):
    name = _slug(pitch.get("company", {}).get("name"))
    jpath = os.path.join(outdir, "pitch-data.json")
    xpath = os.path.join(outdir, f"{name}_MA_Analysis.xlsx")
    json.dump(pitch, open(jpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    env = dict(os.environ, PITCH_JSON=jpath, OUT_XLSX=xpath)
    r = subprocess.run([sys.executable, os.path.join(HERE, "build_workbook.py")],
                       cwd=HERE, env=env, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(xpath):
        raise HTTPException(500, f"Excel build failed:\n{r.stderr or r.stdout}")
    return name, xpath


@app.post("/api/excel")
def excel(data: dict = Body(...)):
    pitch = _coerce(data)
    with tempfile.TemporaryDirectory() as td:
        name, xpath = _build_excel(pitch, td)
        blob = open(xpath, "rb").read()
    return Response(blob,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}_MA_Analysis.xlsx"'})


@app.post("/api/deck")
def deck(data: dict = Body(...)):
    pitch = _coerce(data)
    name = _slug(pitch.get("company", {}).get("name"))
    html = populate_deck.populate(pitch)
    return Response(html, media_type="text/html",
                    headers={"Content-Disposition": f'attachment; filename="{name}_Pitch_Deck.html"'})


@app.post("/api/package")
def package(data: dict = Body(...)):
    pitch = _coerce(data)
    html = populate_deck.populate(pitch)
    with tempfile.TemporaryDirectory() as td:
        name, xpath = _build_excel(pitch, td)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("pitch-data.json", json.dumps(pitch, ensure_ascii=False, indent=2))
            z.writestr(f"{name}_Pitch_Deck.html", html)
            z.write(xpath, f"{name}_MA_Analysis.xlsx")
        blob = buf.getvalue()
    return Response(blob, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}_DealPack.zip"'})


# static frontend (mounted last so explicit routes win)
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
