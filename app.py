“””
WheelsOS — Options Radar (Streamlit)
Converted from wheelsOS.html React app.

Data source: Anthropic Claude API with web_search tool
→ fetches live Yahoo Finance quotes server-side (no Finnhub needed)
Deploy: GitHub → streamlit.io/cloud → share URL → open in Safari
“””

import streamlit as st
import requests
import json
import math
import re
from datetime import date, datetime, timedelta
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────

# PAGE CONFIG  (must be first Streamlit call)

# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
page_title=“Options Radar”,
page_icon=“📡”,
layout=“centered”,
initial_sidebar_state=“collapsed”,
)

# ──────────────────────────────────────────────────────────────────────────────

# CSS — dark terminal theme matching wheelsOS

# ──────────────────────────────────────────────────────────────────────────────

st.markdown(”””

<style>
/* ── Global ── */
html, body, [data-testid="stAppViewContainer"] {
    background: #050a14 !important;
    color: #e2e8f0;
    font-family: 'DM Mono', 'Courier New', monospace;
}
[data-testid="stAppViewContainer"] > .main { background: #050a14; }
[data-testid="stHeader"] { background: transparent; }
.block-container {
    padding-top: 0.5rem;
    padding-bottom: 3rem;
    max-width: 820px;
}
/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

/* ── App header ── */
.or-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 0 10px;
    border-bottom: 1px solid rgba(16,185,129,0.2);
    margin-bottom: 14px;
}
.or-title {
    font-size: 18px;
    font-weight: 700;
    color: #10b981;
    letter-spacing: 0.14em;
}
.or-sub {
    font-size: 10px;
    color: #475569;
    letter-spacing: 0.08em;
    margin-top: 3px;
}

/* ── Status pills ── */
.pill-green { display:inline-block; background:rgba(16,185,129,0.15);
    border:1px solid rgba(16,185,129,0.4); color:#10b981;
    padding:2px 10px; border-radius:20px; font-size:11px; font-weight:700; }
.pill-red { display:inline-block; background:rgba(239,68,68,0.15);
    border:1px solid rgba(239,68,68,0.4); color:#f87171;
    padding:2px 10px; border-radius:20px; font-size:11px; font-weight:700; }
.pill-amber { display:inline-block; background:rgba(245,158,11,0.15);
    border:1px solid rgba(245,158,11,0.4); color:#fbbf24;
    padding:2px 10px; border-radius:20px; font-size:11px; font-weight:700; }

/* ── Alert bars ── */
.alert-red {
    background: rgba(239,68,68,0.10); border: 1px solid rgba(239,68,68,0.30);
    border-radius: 8px; padding: 10px 14px; color: #f87171;
    font-size: 12px; margin-bottom: 10px; font-weight: 600;
}
.alert-amber {
    background: rgba(245,158,11,0.10); border: 1px solid rgba(245,158,11,0.30);
    border-radius: 8px; padding: 10px 14px; color: #fbbf24;
    font-size: 12px; margin-bottom: 10px; font-weight: 600;
}
.alert-green {
    background: rgba(16,185,129,0.07); border: 1px solid rgba(16,185,129,0.20);
    border-radius: 8px; padding: 8px 14px; color: #10b981;
    font-size: 11px; margin-bottom: 10px;
}

/* ── Cards ── */
.or-card {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px; padding: 16px; margin-bottom: 12px;
}
.or-card-active-call {
    background: rgba(245,158,11,0.06);
    border: 1px solid rgba(245,158,11,0.30);
    border-radius: 10px; padding: 16px; margin-bottom: 12px;
    box-shadow: 0 0 20px rgba(245,158,11,0.07);
}
.or-card-active-put {
    background: rgba(16,185,129,0.06);
    border: 1px solid rgba(16,185,129,0.30);
    border-radius: 10px; padding: 16px; margin-bottom: 12px;
    box-shadow: 0 0 20px rgba(16,185,129,0.07);
}

/* ── Stat boxes inside cards ── */
.stat-box {
    background: rgba(255,255,255,0.03);
    border-radius: 6px; padding: 9px 10px; text-align: center;
}
.stat-lbl { font-size: 9px; color: #64748b; letter-spacing: 0.10em;
             text-transform: uppercase; margin-bottom: 3px; }
.stat-val { font-size: 14px; font-weight: 600; }

/* ── Trade setup box ── */
.setup-box-call {
    background: rgba(245,158,11,0.08);
    border: 1px solid rgba(245,158,11,0.20);
    border-radius: 7px; padding: 11px 13px; margin-bottom: 10px;
    display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 12px;
}
.setup-box-put {
    background: rgba(16,185,129,0.08);
    border: 1px solid rgba(16,185,129,0.20);
    border-radius: 7px; padding: 11px 13px; margin-bottom: 10px;
    display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 12px;
}

/* ── Progress bar ── */
.pbar-track {
    height: 4px; background: rgba(255,255,255,0.06);
    border-radius: 2px; overflow: hidden;
}

/* ── Signal badges ── */
.sig-call { background:rgba(245,158,11,0.15); color:#f59e0b;
    border:1px solid rgba(245,158,11,0.35); padding:2px 9px;
    border-radius:4px; font-size:10px; font-weight:700; }
.sig-put  { background:rgba(16,185,129,0.15); color:#10b981;
    border:1px solid rgba(16,185,129,0.35); padding:2px 9px;
    border-radius:4px; font-size:10px; font-weight:700; }
.sig-wait { background:rgba(71,85,105,0.2); color:#475569;
    border:1px solid rgba(71,85,105,0.25); padding:2px 9px;
    border-radius:4px; font-size:10px; font-weight:700; }
.sig-stop { background:rgba(107,114,128,0.15); color:#6b7280;
    border:1px solid rgba(107,114,128,0.25); padding:2px 9px;
    border-radius:4px; font-size:10px; font-weight:700; }

/* ── Streamlit widget overrides for dark theme ── */
.stButton > button {
    background: rgba(16,185,129,0.12) !important;
    border: 1px solid rgba(16,185,129,0.35) !important;
    color: #10b981 !important;
    border-radius: 7px !important;
    font-family: 'DM Mono','Courier New',monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.08em !important;
    font-weight: 700 !important;
}
.stButton > button:hover {
    background: rgba(16,185,129,0.20) !important;
    border-color: rgba(16,185,129,0.55) !important;
}
.stButton[data-testid="baseButton-primary"] > button,
button[kind="primary"] {
    background: linear-gradient(135deg,rgba(16,185,129,0.25),rgba(6,182,212,0.18)) !important;
    color: #10b981 !important;
}
.stTextInput input, .stTextArea textarea {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(16,185,129,0.25) !important;
    color: #e2e8f0 !important;
    border-radius: 7px !important;
    font-family: 'DM Mono','Courier New',monospace !important;
}
.stTextInput input:focus { border-color: rgba(16,185,129,0.6) !important; }
[data-baseweb="tab-list"] {
    background: rgba(5,10,20,0.97) !important;
    border-bottom: 1px solid rgba(16,185,129,0.12) !important;
}
[data-baseweb="tab"] {
    color: #475569 !important;
    font-family: 'DM Mono','Courier New',monospace !important;
    font-size: 10px !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
}
[aria-selected="true"][data-baseweb="tab"] {
    color: #10b981 !important;
    border-bottom: 2px solid #10b981 !important;
}
.stExpander { border: 1px solid rgba(255,255,255,0.07) !important;
               border-radius: 9px !important; background: rgba(255,255,255,0.025) !important; }
.stExpander summary { color: #94a3b8 !important; font-size: 12px !important; }
[data-testid="stMetricValue"] { color: #e2e8f0 !important; font-size: 20px !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 10px !important; }
[data-testid="stMetricDelta"] { font-size: 11px !important; }
</style>

“””, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────

# CONSTANTS

# ──────────────────────────────────────────────────────────────────────────────

VIX_LIMIT      = 25
MOVE_THRESHOLD = 5
DEFAULT_TICKERS = [“TSLL”, “SOXL”, “TQQQ”]

HIGH_RISK_EVENTS = [
{“date”: “2026-04-09”, “event”: “CPI Report”,                “type”: “CPI”},
{“date”: “2026-04-29”, “event”: “FOMC Meeting”,               “type”: “FED”},
{“date”: “2026-04-30”, “event”: “Fed Interest Rate Decision”, “type”: “RATE”},
{“date”: “2026-05-07”, “event”: “CPI Report”,                “type”: “CPI”},
{“date”: “2026-06-09”, “event”: “FOMC Meeting”,               “type”: “FED”},
{“date”: “2026-06-10”, “event”: “Fed Interest Rate Decision”, “type”: “RATE”},
{“date”: “2026-07-09”, “event”: “CPI Report”,                “type”: “CPI”},
{“date”: “2026-07-28”, “event”: “FOMC Meeting”,               “type”: “FED”},
{“date”: “2026-07-29”, “event”: “Fed Interest Rate Decision”, “type”: “RATE”},
{“date”: “2026-09-15”, “event”: “FOMC Meeting”,               “type”: “FED”},
{“date”: “2026-09-16”, “event”: “Fed Interest Rate Decision”, “type”: “RATE”},
{“date”: “2026-11-04”, “event”: “FOMC Meeting”,               “type”: “FED”},
{“date”: “2026-11-05”, “event”: “Fed Interest Rate Decision”, “type”: “RATE”},
]

EVENT_COLORS = {“FED”: “#f59e0b”, “RATE”: “#ef4444”, “CPI”: “#8b5cf6”}

# ──────────────────────────────────────────────────────────────────────────────

# SESSION STATE

# ──────────────────────────────────────────────────────────────────────────────

def init_state():
defaults = {
“api_key”:      “”,          # Anthropic key
“market_data”:  {},          # {sym: {price, changePercent, iv, volume}}
“vix”:          None,
“last_updated”: None,
“data_error”:   None,
“ai_analysis”:  “”,
“history”:      [],          # signal history log
“tickers”:      DEFAULT_TICKERS.copy(),
}
for k, v in defaults.items():
if k not in st.session_state:
st.session_state[k] = v

init_state()

# ──────────────────────────────────────────────────────────────────────────────

# HELPERS

# ──────────────────────────────────────────────────────────────────────────────

def today_str():
return date.today().isoformat()

def today_events():
return [e for e in HIGH_RISK_EVENTS if e[“date”] == today_str()]

def upcoming_events():
return [e for e in HIGH_RISK_EVENTS if e[“date”] > today_str()][:6]

def vix_high():
v = st.session_state.vix
return v is not None and float(v) >= VIX_LIMIT

def has_risk():
return len(today_events()) > 0

def tradeable():
return not vix_high() and not has_risk()

def get_signal(chg_pct):
“”“Return signal dict based on day change %.”””
try:
v = float(chg_pct)
except (TypeError, ValueError):
return {“type”: “NO_TRADE”, “label”: “NO TRADE”, “cls”: “sig-stop”, “color”: “#6b7280”}
if vix_high() or has_risk():
return {“type”: “NO_TRADE”, “label”: “NO TRADE”, “cls”: “sig-stop”, “color”: “#6b7280”}
if v >= MOVE_THRESHOLD:
return {“type”: “SELL_CALL”, “label”: “SELL CALL”, “cls”: “sig-call”, “color”: “#f59e0b”}
if v <= -MOVE_THRESHOLD:
return {“type”: “SELL_PUT”,  “label”: “SELL PUT”,  “cls”: “sig-put”,  “color”: “#10b981”}
return {“type”: “WAIT”, “label”: “WAIT”, “cls”: “sig-wait”, “color”: “#475569”}

def get_strike(price, sig_type):
try:
p = float(price)
except (TypeError, ValueError):
return “—”
if sig_type == “SELL_CALL”:
return f”{p * 1.10:.2f}”
if sig_type == “SELL_PUT”:
return f”{p * 0.90:.2f}”
return “—”

def fmt_vol(v):
if not v:
return “—”
v = int(v)
if v >= 1_000_000:
return f”{v/1_000_000:.1f}M”
if v >= 1_000:
return f”{v/1_000:.0f}K”
return str(v)

def next_expiry_str():
“”“Return 3rd Friday ~30 DTE as formatted string.”””
target = date.today() + timedelta(days=30)
d = date(target.year, target.month, 1)
fri = 0
while True:
if d.weekday() == 4:
fri += 1
if fri == 3:
return d.strftime(”%-m/%-d/%Y”)
d += timedelta(days=1)
if d.month != target.month:
break
# fallback: next month
nm = target.month % 12 + 1
ny = target.year + (1 if target.month == 12 else 0)
d = date(ny, nm, 1)
fri = 0
while True:
if d.weekday() == 4:
fri += 1
if fri == 3:
return d.strftime(”%-m/%-d/%Y”)
d += timedelta(days=1)

# ──────────────────────────────────────────────────────────────────────────────

# ANTHROPIC API — all calls go through here

# ──────────────────────────────────────────────────────────────────────────────

ANTHROPIC_URL  = “https://api.anthropic.com/v1/messages”
ANTHROPIC_VER  = “2023-06-01”
MODEL          = “claude-sonnet-4-20250514”

def call_claude(prompt: str, use_web_search: bool = False, max_tokens: int = 1000) -> str:
“””
Call Claude API server-side (Python requests).
use_web_search=True adds the web_search tool so Claude can fetch live data.
“””
key = st.session_state.api_key
if not key:
raise ValueError(“No API key set”)

```
headers = {
    "Content-Type":      "application/json",
    "x-api-key":         key,
    "anthropic-version": ANTHROPIC_VER,
    "anthropic-beta":    "interleaved-thinking-2025-05-14",
}

body: dict = {
    "model":      MODEL,
    "max_tokens": max_tokens,
    "messages":   [{"role": "user", "content": prompt}],
}
if use_web_search:
    body["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]

r = requests.post(ANTHROPIC_URL, headers=headers, json=body, timeout=60)
if not r.ok:
    err = r.json().get("error", {}).get("message", f"HTTP {r.status_code}")
    raise RuntimeError(err)

data = r.json()
# Extract all text blocks (Claude may interleave tool-use and text)
parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
return "\n".join(p for p in parts if p).strip()
```

def fetch_live_market_data():
“””
Ask Claude to search Yahoo Finance for live quotes.
Returns list of dicts: [{symbol, price, changePercent, iv, volume}, …]
“””
tickers_str = “, “.join(st.session_state.tickers)
prompt = f””“You are a financial data API. Search Yahoo Finance RIGHT NOW for live quotes for:
{tickers_str}, and ^VIX (the CBOE Volatility Index).

Return ONLY a raw JSON array — no markdown, no backticks, no explanation. Exact format:
[
{{“symbol”:“TSLL”,“price”:14.52,“changePercent”:4.54,“volume”:3200000,“impliedVolatility”:95.2}},
{{“symbol”:“SOXL”,“price”:28.10,“changePercent”:2.18,“volume”:8500000,“impliedVolatility”:110.5}},
{{“symbol”:“TQQQ”,“price”:52.80,“changePercent”:3.12,“volume”:12000000,“impliedVolatility”:72.3}},
{{“symbol”:“VIX”,“price”:19.45,“changePercent”:2.91,“volume”:0,“impliedVolatility”:0}}
]

Rules:

- Use the LATEST available price from Yahoo Finance right now
- changePercent = ((price - previousClose) / previousClose) * 100, rounded 2 decimals
- impliedVolatility: current 30-day IV as plain number e.g. 95.2 (not 0.952)
- For ^VIX: symbol = “VIX”, price = current VIX level
- Return ONLY the JSON array — nothing else”””
  
  raw = call_claude(prompt, use_web_search=True, max_tokens=800)
  
  # Extract the JSON array robustly
  
  raw = re.sub(r”```[a-z]*”, “”, raw).strip()
  match = re.search(r”[[\s\S]*?]”, raw)
  if not match:
  raise ValueError(f”Could not parse market data. Response was:\n{raw[:300]}”)
  return json.loads(match.group(0))

def load_market_data():
“”“Fetch market data and update session state.”””
with st.spinner(“📡 Fetching live data via Claude + Yahoo Finance…”):
try:
quotes = fetch_live_market_data()
md = {}
vix_val = None
for q in quotes:
sym = q.get(“symbol”, “”)
if sym == “VIX”:
try:
vix_val = round(float(q[“price”]), 2)
except (TypeError, ValueError):
pass
elif sym in st.session_state.tickers:
md[sym] = {
“price”:         str(round(float(q.get(“price”, 0)), 2)),
“changePercent”: str(round(float(q.get(“changePercent”, 0)), 2)),
“iv”:            str(round(float(q.get(“impliedVolatility”, 0)), 1)),
“volume”:        int(q.get(“volume”, 0)),
}
st.session_state.market_data  = md
st.session_state.vix          = vix_val
st.session_state.last_updated = datetime.now().strftime(”%H:%M:%S”)
st.session_state.data_error   = None
except Exception as e:
st.session_state.data_error = str(e)

def get_ai_analysis():
“”“Generate AI daily briefing using Claude (no web search — uses already-loaded data).”””
te  = today_events()
ue  = upcoming_events()
md  = st.session_state.market_data
tickers = st.session_state.tickers

```
summary = "\n".join(
    f"{t}: ${md[t]['price']} | Δ{md[t]['changePercent']}% | IV {md[t]['iv']}% | Signal: {get_signal(md[t]['changePercent'])['label']}"
    if t in md else f"{t}: no data"
    for t in tickers
)

prompt = f"""You are a senior options trader specialising in leveraged ETFs. Today's live snapshot:
```

{summary}

VIX: {st.session_state.vix or ‘unknown’} ({‘HIGH — cautious’ if vix_high() else ‘Normal’})
Risk Events Today: {’, ‘.join(e[‘event’] for e in te) if te else ‘None’}
Upcoming Risk Events: {’ | ‘.join(e[‘date’]+’: ’+e[‘event’] for e in ue)}

Strategy rules:
• Sell 30DTE options 10% OTM ONLY on >5% move days
• Sell calls on >5% UP days or reversal DOWN >5% within 2 weeks of a prior spike
• Sell puts on >5% DOWN days
• Exit at >50% premium captured
• Block all new trades on high VIX (≥{VIX_LIMIT}) or FOMC/CPI/Rate event days

Write a concise actionable DAILY BRIEFING (max 220 words). Sections:

1. VERDICT — trade today or stand down, one sentence
1. PER TICKER — for each: signal, strike price (10% OTM), approx premium, rationale
1. RISK FLAGS — any red flags to watch
1. OPEN POSITION EXITS — exit guidance if near 50% profit
   Trader tone. No fluff. Numbers matter.”””
   
   with st.spinner(“⚡ Generating AI briefing…”):
   text = call_claude(prompt, use_web_search=False, max_tokens=800)
   
   st.session_state.ai_analysis = text
   
   # Log to history
   
   st.session_state.history.insert(0, {
   “date”:    date.today().isoformat(),
   “time”:    datetime.now().strftime(”%H:%M”),
   “vix”:     str(st.session_state.vix or “—”),
   “signals”: [
   {
   “ticker”: t,
   “signal”: get_signal(md.get(t, {}).get(“changePercent”, “”)).get(“label”, “—”),
   “change”: md.get(t, {}).get(“changePercent”, “”),
   }
   for t in tickers
   ],
   })
   st.session_state.history = st.session_state.history[:10]

# ──────────────────────────────────────────────────────────────────────────────

# KEY SETUP SCREEN

# ──────────────────────────────────────────────────────────────────────────────

def render_setup():
st.markdown(”””
<div style="min-height:70vh;display:flex;align-items:center;justify-content:center;padding:20px;">
<div style="max-width:380px;width:100%;background:rgba(255,255,255,0.03);
border:1px solid rgba(16,185,129,0.25);border-radius:16px;
padding:32px 28px;box-shadow:0 0 60px rgba(16,185,129,0.08);">
<div style="text-align:center;margin-bottom:24px;">
<div style="font-size:36px;margin-bottom:8px;">📡</div>
<div style="font-size:18px;font-weight:700;color:#10b981;letter-spacing:0.12em;">
OPTIONS RADAR</div>
<div style="font-size:11px;color:#64748b;margin-top:4px;letter-spacing:0.08em;">
TSLL · SOXL · TQQQ · 30DTE PREMIUM SELLER</div>
</div>
<div style="font-size:11px;color:#94a3b8;line-height:1.7;margin-bottom:18px;">
Enter your <span style="color:#10b981;">Anthropic API key</span> to enable live
Yahoo Finance data and AI trade briefings.
</div>
</div></div>
“””, unsafe_allow_html=True)

```
with st.container():
    st.markdown("**API KEY**")
    key_input = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-api03-…",
        label_visibility="collapsed",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        launch = st.button("LAUNCH APP →", type="primary", use_container_width=True)

    if launch:
        k = key_input.strip()
        if not k.startswith("sk-ant-"):
            st.error("Key must start with sk-ant-…")
        else:
            with st.spinner("Verifying key…"):
                try:
                    headers = {
                        "Content-Type":      "application/json",
                        "x-api-key":         k,
                        "anthropic-version": ANTHROPIC_VER,
                    }
                    body = {
                        "model":      "claude-haiku-4-5-20251001",
                        "max_tokens": 5,
                        "messages":   [{"role": "user", "content": "Hi"}],
                    }
                    r = requests.post(ANTHROPIC_URL, headers=headers, json=body, timeout=15)
                    if not r.ok:
                        raise RuntimeError(r.json().get("error", {}).get("message", "Invalid key"))
                    st.session_state.api_key = k
                    st.success("Key verified ✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.markdown("""
    <div style="margin-top:18px;padding:13px;background:rgba(6,182,212,0.05);
                border:1px solid rgba(6,182,212,0.15);border-radius:8px;">
      <div style="font-size:10px;color:#06b6d4;letter-spacing:0.1em;margin-bottom:6px;">
        HOW TO GET YOUR FREE KEY</div>
      <div style="font-size:11px;color:#94a3b8;line-height:1.7;">
        1. Go to <span style="color:#06b6d4;">console.anthropic.com</span><br/>
        2. Sign up free → API Keys → Create Key<br/>
        3. Free tier includes $5 credit (≈ 500+ daily checks)
      </div>
    </div>
    """, unsafe_allow_html=True)
```

# ──────────────────────────────────────────────────────────────────────────────

# MAIN APP

# ──────────────────────────────────────────────────────────────────────────────

def render_app():
te = today_events()
ue = upcoming_events()
md = st.session_state.market_data

```
# ── Header ──────────────────────────────────────────────────────────────
dot_col    = "#10b981" if tradeable() else "#ef4444"
status_txt = "✓ TRADE DAY" if tradeable() else "✗ STAND DOWN"
tickers_display = " · ".join(st.session_state.tickers)

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(f"""
    <div class="or-header">
      <div>
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="width:9px;height:9px;border-radius:50%;background:{dot_col};
                       box-shadow:0 0 8px {dot_col};flex-shrink:0;"></div>
          <span class="or-title">OPTIONS RADAR</span>
        </div>
        <div class="or-sub">{tickers_display} · 30DTE PREMIUM SELLER</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
with col_h2:
    if st.button("↻ REFRESH", use_container_width=True):
        load_market_data()
        st.rerun()
    if st.button("🔑 RESET KEY", use_container_width=True):
        st.session_state.api_key = ""
        st.rerun()

# ── Alert bars ───────────────────────────────────────────────────────────
if vix_high():
    st.markdown(f'<div class="alert-red">⚠️ HIGH VIX {st.session_state.vix} ≥ {VIX_LIMIT} — NO NEW TRADES</div>',
                unsafe_allow_html=True)
if has_risk():
    evts = ", ".join(e["event"] for e in te)
    st.markdown(f'<div class="alert-amber">⚠️ RISK EVENT TODAY: {evts} — NO NEW TRADES</div>',
                unsafe_allow_html=True)
if st.session_state.data_error:
    st.markdown(f'<div class="alert-amber">⚠ {st.session_state.data_error}</div>',
                unsafe_allow_html=True)
if st.session_state.last_updated and not st.session_state.data_error:
    st.markdown(f'<div class="alert-green">● LIVE · Yahoo Finance via Claude · {st.session_state.last_updated}</div>',
                unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────
tab_dash, tab_analysis, tab_calendar, tab_history, tab_settings = st.tabs([
    "DASHBOARD", "ANALYSIS", "CALENDAR", "HISTORY", "SETTINGS"
])

# ════════════════════════════════════════════════════════════════════════
# DASHBOARD TAB
# ════════════════════════════════════════════════════════════════════════
with tab_dash:
    # VIX + Status row
    col_vix, col_status = st.columns(2)
    vv = st.session_state.vix
    with col_vix:
        if vv:
            v_col = "#ef4444" if float(vv) >= VIX_LIMIT else "#f59e0b" if float(vv) > 20 else "#10b981"
            v_lbl = "⛔ HIGH — AVOID" if float(vv) >= VIX_LIMIT else "⚡ ELEVATED" if float(vv) > 20 else "✓ NORMAL"
            st.markdown(f"""
            <div class="or-card" style="margin-bottom:10px;">
              <div class="stat-lbl">VIX INDEX</div>
              <div style="font-size:32px;font-weight:700;color:{v_col};line-height:1;">{vv}</div>
              <div style="font-size:10px;color:{v_col};margin-top:5px;">{v_lbl}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="or-card" style="margin-bottom:10px;"><div class="stat-lbl">VIX INDEX</div>'
                        '<div style="font-size:28px;color:#334155;">—</div>'
                        '<div style="font-size:10px;color:#334155;margin-top:5px;">loading…</div></div>',
                        unsafe_allow_html=True)
    with col_status:
        s_col = "#10b981" if tradeable() else "#ef4444"
        s_sub = (te[0]["event"] if has_risk() else "VIX too high" if vix_high() else "Monitor for >5% signals")
        st.markdown(f"""
        <div class="or-card" style="margin-bottom:10px;">
          <div class="stat-lbl">TODAY</div>
          <div style="font-size:17px;font-weight:700;color:{s_col};letter-spacing:0.04em;line-height:1.2;">
            {status_txt}</div>
          <div style="font-size:10px;color:#64748b;margin-top:5px;">{s_sub}</div>
        </div>""", unsafe_allow_html=True)

    # No data yet
    if not md:
        st.markdown("""
        <div style="text-align:center;padding:48px 0;color:#334155;letter-spacing:0.12em;font-size:12px;">
          <div style="font-size:28px;margin-bottom:8px;">📡</div>
          Tap ↻ REFRESH to fetch live data
        </div>""", unsafe_allow_html=True)
    else:
        for ticker in st.session_state.tickers:
            d = md.get(ticker)
            if not d:
                st.markdown(f'<div class="or-card" style="color:#334155;font-size:12px;">{ticker} — no data</div>',
                            unsafe_allow_html=True)
                continue

            sig   = get_signal(d["changePercent"])
            chg   = float(d["changePercent"])
            price = d["price"]
            iv    = d["iv"]
            vol   = fmt_vol(d["volume"])
            stk   = get_strike(price, sig["type"])
            pct   = min(abs(chg) / MOVE_THRESHOLD * 100, 100)
            active = sig["type"] in ("SELL_CALL", "SELL_PUT")
            expiry = next_expiry_str()

            # Card CSS class
            if sig["type"] == "SELL_CALL":
                card_cls = "or-card-active-call"
            elif sig["type"] == "SELL_PUT":
                card_cls = "or-card-active-put"
            else:
                card_cls = "or-card"

            chg_sign  = "+" if chg >= 0 else ""
            chg_color = "#10b981" if chg >= 0 else "#f87171"
            bar_color = sig["color"] if pct >= 100 else "rgba(255,255,255,0.12)"

            # Trade setup block (only when active)
            setup_html = ""
            if active:
                box_cls = "setup-box-call" if sig["type"] == "SELL_CALL" else "setup-box-put"
                setup_html = f"""
                <div class="{box_cls}">
                  <div><span style="color:#64748b;font-size:11px;">Type: </span>
                       <b style="color:{sig['color']};">{'Sell Call' if sig['type']=='SELL_CALL' else 'Sell Put'}</b></div>
                  <div><span style="color:#64748b;font-size:11px;">Expiry: </span>
                       <b style="color:#e2e8f0;">30 DTE ({expiry})</b></div>
                  <div><span style="color:#64748b;font-size:11px;">Strike: </span>
                       <b style="color:#e2e8f0;">${stk}</b></div>
                  <div><span style="color:#64748b;font-size:11px;">Exit: </span>
                       <b style="color:#10b981;">&gt;50% profit</b></div>
                </div>"""

            st.markdown(f"""
            <div class="{card_cls}">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <div style="display:flex;align-items:center;gap:10px;">
                  <span style="font-size:18px;font-weight:700;color:#f1f5f9;">{ticker}</span>
                  <span class="{sig['cls']}">{sig['label']}</span>
                </div>
                <span style="font-size:10px;color:#475569;">IV {iv}%</span>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:12px;">
                <div class="stat-box">
                  <div class="stat-lbl">PRICE</div>
                  <div class="stat-val" style="color:#e2e8f0;">${price}</div>
                </div>
                <div class="stat-box">
                  <div class="stat-lbl">DAY Δ</div>
                  <div class="stat-val" style="color:{chg_color};">{chg_sign}{d['changePercent']}%</div>
                </div>
                <div class="stat-box">
                  <div class="stat-lbl">STRIKE</div>
                  <div class="stat-val" style="color:{sig['color']};">{"$"+stk if stk != "—" else "—"}</div>
                </div>
              </div>
              {setup_html}
              <div>
                <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                  <span style="font-size:9px;color:#475569;">SIGNAL THRESHOLD ({abs(chg):.1f}% / {MOVE_THRESHOLD}%)</span>
                  <span style="font-size:9px;color:#475569;">{pct:.0f}%</span>
                </div>
                <div class="pbar-track">
                  <div style="height:100%;width:{pct}%;background:{bar_color};
                               border-radius:2px;transition:width 1s ease;"></div>
                </div>
              </div>
              <div style="font-size:9px;color:#334155;margin-top:6px;">VOL {vol}</div>
            </div>
            """, unsafe_allow_html=True)

    # AI briefing button
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    ai_disabled = not md
    if st.button(
        "⚡  GET AI DAILY BRIEFING",
        use_container_width=True,
        disabled=ai_disabled,
        type="primary",
    ):
        try:
            get_ai_analysis()
            st.success("Briefing generated — see ANALYSIS tab ↑")
        except Exception as e:
            st.error(f"AI error: {e}")

# ════════════════════════════════════════════════════════════════════════
# ANALYSIS TAB
# ════════════════════════════════════════════════════════════════════════
with tab_analysis:
    st.markdown(f"""
    <div style="font-size:9px;color:#64748b;letter-spacing:0.14em;margin-bottom:14px;">
      AI DAILY BRIEFING — {date.today().strftime("%-m/%-d/%Y")}
    </div>""", unsafe_allow_html=True)

    if st.session_state.ai_analysis:
        st.markdown(f"""
        <div class="or-card">
          <pre style="white-space:pre-wrap;font-family:'DM Mono','Courier New',monospace;
                      font-size:13px;line-height:1.85;color:#cbd5e1;margin:0;
                      border-left:3px solid #10b981;padding-left:14px;">{st.session_state.ai_analysis}</pre>
        </div>""", unsafe_allow_html=True)
        if st.button("↻ REFRESH ANALYSIS", use_container_width=True):
            try:
                get_ai_analysis()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.markdown("""
        <div class="or-card" style="text-align:center;padding:32px 0;">
          <div style="font-size:28px;margin-bottom:10px;">📊</div>
          <div style="color:#334155;font-size:12px;letter-spacing:0.1em;">
            Tap "GET AI DAILY BRIEFING" on the Dashboard tab
          </div>
        </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# CALENDAR TAB
# ════════════════════════════════════════════════════════════════════════
with tab_calendar:
    te = today_events()
    ue = upcoming_events()

    if te:
        for e in te:
            c = EVENT_COLORS.get(e["type"], "#6b7280")
            st.markdown(f"""
            <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);
                         border-radius:9px;padding:14px;margin-bottom:12px;">
              <div style="font-size:9px;color:#ef4444;letter-spacing:0.14em;margin-bottom:8px;">
                ⛔ TODAY'S HIGH-RISK EVENTS</div>
              <div style="color:#fca5a5;font-size:13px;display:flex;align-items:center;gap:8px;">
                <span style="background:{c}25;color:{c};border:1px solid {c}40;
                             padding:1px 7px;border-radius:4px;font-size:9px;">{e['type']}</span>
                {e['event']}
              </div>
            </div>""", unsafe_allow_html=True)

    # Upcoming events table
    st.markdown("""
    <div class="or-card" style="padding:0;overflow:hidden;">
      <div style="padding:12px 14px;border-bottom:1px solid rgba(16,185,129,0.08);
                   font-size:9px;color:#64748b;letter-spacing:0.14em;">
        UPCOMING NO-TRADE EVENTS</div>""", unsafe_allow_html=True)

    for i, e in enumerate(ue):
        c     = EVENT_COLORS.get(e["type"], "#6b7280")
        bdr   = "border-bottom:1px solid rgba(255,255,255,0.04);" if i < len(ue)-1 else ""
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:12px 14px;{bdr}flex-wrap:wrap;">
          <span style="font-size:11px;color:#94a3b8;min-width:82px;">{e['date']}</span>
          <span style="background:{c}22;color:{c};border:1px solid {c}35;
                       padding:2px 7px;border-radius:4px;font-size:9px;">{e['type']}</span>
          <span style="font-size:12px;color:#cbd5e1;flex:1;">{e['event']}</span>
          <span style="font-size:9px;color:#ef4444;letter-spacing:0.06em;">NO TRADE</span>
        </div>""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # Strategy rules
    st.markdown("""
    <div class="or-card" style="margin-top:12px;">
      <div style="font-size:9px;color:#64748b;letter-spacing:0.14em;margin-bottom:10px;">STRATEGY RULES</div>""",
    unsafe_allow_html=True)
    rules = [
        ("ENTRY",   "Only on >5% single-day move"),
        ("CALLS",   "Sell on >5% up day OR reversal >5% down within 2 weeks of a spike"),
        ("PUTS",    "Sell on >5% down days"),
        ("STRIKE",  "10% OTM from current price"),
        ("EXPIRY",  "30 DTE — 3rd Friday of month"),
        ("EXIT",    ">50% premium captured → close & redeploy"),
        ("VIX",     f"≥{VIX_LIMIT} → no new trades"),
        ("EVENTS",  "FOMC/CPI/Rate day → no new trades"),
    ]
    for k, v in rules:
        st.markdown(f"""
        <div style="display:flex;gap:10px;margin-bottom:7px;font-size:11px;">
          <span style="color:#10b981;min-width:64px;font-weight:600;
                       font-size:10px;letter-spacing:0.08em;">{k}</span>
          <span style="color:#94a3b8;line-height:1.5;">{v}</span>
        </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# HISTORY TAB
# ════════════════════════════════════════════════════════════════════════
with tab_history:
    st.markdown("""
    <div style="font-size:9px;color:#64748b;letter-spacing:0.14em;margin-bottom:12px;">
      SESSION SIGNAL LOG</div>""", unsafe_allow_html=True)

    hist = st.session_state.history
    if not hist:
        st.markdown("""
        <div style="text-align:center;padding:48px 0;color:#334155;font-size:12px;letter-spacing:0.1em;">
          <div style="font-size:28px;margin-bottom:8px;">📋</div>
          No signals logged yet.<br/>Run the AI briefing to record entries.
        </div>""", unsafe_allow_html=True)
    else:
        for h in hist:
            signals_html = ""
            for s in h.get("signals", []):
                sc = "#f59e0b" if s["signal"]=="SELL CALL" else "#10b981" if s["signal"]=="SELL PUT" else "#334155"
                signals_html += f"""
                <div style="background:{sc}15;border:1px solid {sc}28;border-radius:6px;
                             padding:5px 10px;display:inline-block;margin:2px;">
                  <span style="color:#94a3b8;font-size:10px;">{s['ticker']} </span>
                  <span style="color:{sc};font-size:10px;font-weight:700;">{s['signal']}</span>
                  {"<span style='color:#475569;font-size:9px;'> ("+str(s['change'])+"%)</span>" if s.get('change') else ""}
                </div>"""

            st.markdown(f"""
            <div class="or-card">
              <div style="display:flex;justify-content:space-between;margin-bottom:9px;">
                <span style="font-size:11px;color:#94a3b8;">{h['date']} {h['time']}</span>
                <span style="font-size:10px;color:#475569;">VIX: {h.get('vix','—')}</span>
              </div>
              <div style="display:flex;flex-wrap:wrap;gap:4px;">{signals_html}</div>
            </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# SETTINGS TAB
# ════════════════════════════════════════════════════════════════════════
with tab_settings:
    st.markdown("""
    <div style="font-size:9px;color:#64748b;letter-spacing:0.14em;margin-bottom:14px;">
      SETTINGS</div>""", unsafe_allow_html=True)

    # ── Watched Tickers ──────────────────────────────────────────────
    st.markdown("""
    <div style="font-size:10px;color:#10b981;letter-spacing:0.10em;margin-bottom:8px;font-weight:600;">
      WATCHED TICKERS</div>
    <div style="font-size:11px;color:#64748b;margin-bottom:12px;">
      Add or remove tickers. Each ticker gets live data and signal analysis.</div>
    """, unsafe_allow_html=True)

    # Current tickers
    ticker_cols = st.columns(min(len(st.session_state.tickers), 5))
    for i, sym in enumerate(st.session_state.tickers):
        with ticker_cols[i % len(ticker_cols)]:
            st.markdown(f"""
            <div style="background:rgba(16,185,129,0.10);border:1px solid rgba(16,185,129,0.30);
                         border-radius:7px;padding:8px 12px;text-align:center;
                         color:#10b981;font-weight:700;font-size:13px;margin-bottom:6px;">
              {sym}</div>""", unsafe_allow_html=True)
            if st.button(f"✕ {sym}", key=f"remove_{sym}",
                         disabled=len(st.session_state.tickers) <= 1,
                         use_container_width=True):
                st.session_state.tickers.remove(sym)
                st.session_state.market_data.pop(sym, None)
                st.rerun()

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    # Add new ticker
    st.markdown("""
    <div style="font-size:10px;color:#64748b;letter-spacing:0.10em;margin-bottom:6px;">
      ADD TICKER</div>""", unsafe_allow_html=True)
    col_t, col_b = st.columns([3, 1])
    with col_t:
        new_sym = st.text_input("New ticker", placeholder="e.g. UVXY, SQQQ…",
                                max_chars=6, label_visibility="collapsed").upper().strip()
    with col_b:
        add_btn = st.button("+ ADD", use_container_width=True, type="primary")

    if add_btn:
        sym = new_sym.replace(" ", "").upper()
        if not sym:
            st.error("Enter a ticker symbol.")
        elif len(sym) > 6:
            st.error("Max 6 characters.")
        elif sym in st.session_state.tickers:
            st.warning(f"{sym} is already tracked.")
        else:
            # Quick verify via Claude web search
            with st.spinner(f"Verifying {sym}…"):
                try:
                    verify_prompt = (
                        f"Search Yahoo Finance for the current price of {sym}. "
                        f"If it's a valid ticker, return ONLY a JSON object like: "
                        f'{{\"symbol\":\"{sym}\",\"price\":12.34,\"valid\":true}}. '
                        f"If not found, return: {{\"valid\":false}}"
                    )
                    raw = call_claude(verify_prompt, use_web_search=True, max_tokens=100)
                    raw = re.sub(r"```[a-z]*", "", raw).strip()
                    m = re.search(r"\{[\s\S]*?\}", raw)
                    result = json.loads(m.group(0)) if m else {}
                    if result.get("valid") is False:
                        st.error(f"Could not find {sym} on Yahoo Finance.")
                    else:
                        st.session_state.tickers.append(sym)
                        st.success(f"✅ {sym} added! Tap ↻ REFRESH to load its data.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Verification failed: {e}. You can still add it manually.")
                    if st.button(f"Add {sym} anyway"):
                        st.session_state.tickers.append(sym)
                        st.rerun()

    st.markdown("""
    <div style="font-size:9px;color:#475569;margin-top:8px;">
      ✓ Ticker verified against Yahoo Finance via Claude before adding<br/>
      ✓ Each ticker uses 1 web search per refresh
    </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # ── API Key reset ────────────────────────────────────────────────
    st.markdown("""
    <div style="font-size:10px;color:#64748b;letter-spacing:0.10em;margin-bottom:8px;">
      API KEY</div>""", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="font-size:11px;color:#475569;margin-bottom:10px;">
      Current key: <span style="color:#10b981;">{"sk-ant-…" + st.session_state.api_key[-6:] if st.session_state.api_key else "not set"}</span>
    </div>""", unsafe_allow_html=True)
    if st.button("🔑 Reset API Key", use_container_width=True):
        st.session_state.api_key = ""
        st.session_state.market_data = {}
        st.session_state.vix = None
        st.session_state.ai_analysis = ""
        st.rerun()
```

# ──────────────────────────────────────────────────────────────────────────────

# ENTRY POINT

# ──────────────────────────────────────────────────────────────────────────────

if st.session_state.api_key:
render_app()
else:
render_setup()