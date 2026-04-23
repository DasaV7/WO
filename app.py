import streamlit as st
import pandas as pd
import requests
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(
page_title=“WheelOS - Options Radar”,
page_icon=“O”,
layout=“wide”,
initial_sidebar_state=“collapsed”
)

st.markdown(”””

<style>
:root {
  --ios-blue:       #007AFF;
  --ios-green:      #34C759;
  --ios-red:        #FF3B30;
  --ios-orange:     #FF9500;
  --ios-gray:       #8E8E93;
  --ios-gray2:      #AEAEB2;
  --ios-gray6:      #F2F2F7;
  --ios-label:      #1C1C1E;
  --ios-sep:        rgba(60,60,67,0.12);
  --ios-app-bg:     #F2F2F7;
  --shadow-sm:      0 1px 3px rgba(0,0,0,0.08),0 1px 2px rgba(0,0,0,0.06);
  --shadow-md:      0 4px 12px rgba(0,0,0,0.10),0 2px 4px rgba(0,0,0,0.06);
  --shadow-lg:      0 10px 30px rgba(0,0,0,0.12),0 4px 8px rgba(0,0,0,0.06);
  --r-sm: 10px; --r-md: 14px; --r-lg: 18px; --r-xl: 22px;
}
.stApp {
  background-color: var(--ios-app-bg) !important;
  font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

h1,h2,h3,h4 {
  font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
  font-weight: 700 !important; color: var(--ios-label) !important; letter-spacing: -0.5px;
}
h1 { font-size: 2.2rem !important; }
h2 { font-size: 1.6rem !important; }
h3 { font-size: 1.2rem !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  background: var(--ios-gray6) !important;
  border-radius: var(--r-xl) !important;
  padding: 4px !important; gap: 2px !important; border: none !important;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.06) !important;
}
.stTabs [data-baseweb="tab"] {
  border-radius: var(--r-lg) !important; font-weight: 500 !important;
  font-size: 0.85rem !important; color: var(--ios-gray) !important;
  padding: 8px 14px !important;
  transition: all 0.2s cubic-bezier(0.34,1.56,0.64,1) !important;
  border: none !important; background: transparent !important;
}
.stTabs [aria-selected="true"] {
  background: white !important; color: var(--ios-label) !important;
  box-shadow: var(--shadow-sm) !important; font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 20px !important; }

/* Buttons */
.stButton > button {
  font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
  font-weight: 600 !important; font-size: 0.9rem !important;
  border-radius: var(--r-md) !important; border: none !important;
  height: 44px !important; padding: 0 20px !important; cursor: pointer !important;
  transition: transform 0.15s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.15s ease, background 0.15s ease !important;
  position: relative !important; overflow: hidden !important;
}
.stButton > button[kind="primary"] {
  background: var(--ios-blue) !important; color: white !important;
  box-shadow: 0 4px 14px rgba(0,122,255,0.35) !important;
}
.stButton > button[kind="primary"]:hover {
  background: #0066DD !important;
  box-shadow: 0 6px 20px rgba(0,122,255,0.45) !important;
  transform: translateY(-2px) scale(1.01) !important;
}
.stButton > button[kind="primary"]:active {
  transform: scale(0.95) !important; box-shadow: 0 2px 8px rgba(0,122,255,0.3) !important; opacity: 0.9 !important;
}
.stButton > button[kind="secondary"] {
  background: white !important; color: var(--ios-blue) !important;
  box-shadow: var(--shadow-sm) !important; border: 1.5px solid var(--ios-sep) !important;
}
.stButton > button[kind="secondary"]:hover {
  background: var(--ios-gray6) !important; box-shadow: var(--shadow-md) !important; transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"]:active { transform: scale(0.95) !important; background: #E8E8ED !important; }
.stButton > button:disabled {
  background: var(--ios-gray6) !important; color: var(--ios-gray2) !important;
  box-shadow: none !important; cursor: not-allowed !important; opacity: 0.6 !important;
}
.stButton > button::after {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(circle at center, rgba(255,255,255,0.3) 0%, transparent 70%);
  opacity: 0; transition: opacity 0.3s ease;
}
.stButton > button:active::after { opacity: 1; }

/* Inputs */
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
  font-family: -apple-system, BlinkMacSystemFont, sans-serif !important;
  border-radius: var(--r-md) !important; border: 1.5px solid var(--ios-sep) !important;
  background: white !important; padding: 10px 14px !important;
  font-size: 0.95rem !important; color: var(--ios-label) !important;
  box-shadow: var(--shadow-sm) !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important; height: 44px !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
  border-color: var(--ios-blue) !important;
  box-shadow: 0 0 0 4px rgba(0,122,255,0.12), var(--shadow-sm) !important; outline: none !important;
}
.stTextInput > div > div > input:hover,
.stNumberInput > div > div > input:hover { border-color: var(--ios-gray2) !important; }

/* Selectbox */
.stSelectbox > div > div {
  border-radius: var(--r-md) !important; border: 1.5px solid var(--ios-sep) !important;
  background: white !important; box-shadow: var(--shadow-sm) !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stSelectbox > div > div:hover {
  border-color: var(--ios-blue) !important; box-shadow: 0 0 0 3px rgba(0,122,255,0.08) !important;
}
[data-baseweb="popover"] ul {
  border-radius: var(--r-md) !important; box-shadow: var(--shadow-lg) !important;
  border: 1px solid var(--ios-sep) !important; overflow: hidden !important;
  padding: 6px !important; background: white !important;
}
[data-baseweb="popover"] li {
  border-radius: var(--r-sm) !important; padding: 10px 14px !important;
  font-size: 0.9rem !important; transition: background 0.15s ease !important; cursor: pointer !important;
}
[data-baseweb="popover"] li:hover { background: var(--ios-gray6) !important; }
[data-baseweb="popover"] li[aria-selected="true"] {
  background: rgba(0,122,255,0.1) !important; color: var(--ios-blue) !important; font-weight: 600 !important;
}

/* Metrics */
[data-testid="metric-container"] {
  background: white !important; border-radius: var(--r-md) !important;
  padding: 16px !important; box-shadow: var(--shadow-sm) !important;
  border: 1px solid var(--ios-sep) !important;
  transition: box-shadow 0.2s ease, transform 0.2s ease !important;
}
[data-testid="metric-container"]:hover { box-shadow: var(--shadow-md) !important; transform: translateY(-1px) !important; }
[data-testid="metric-container"] label {
  font-size: 0.75rem !important; font-weight: 600 !important;
  text-transform: uppercase !important; letter-spacing: 0.8px !important; color: var(--ios-gray) !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
  font-size: 1.6rem !important; font-weight: 700 !important;
  color: var(--ios-label) !important; letter-spacing: -0.5px !important;
}

/* Expanders */
.stExpander {
  border-radius: var(--r-md) !important; border: none !important;
  box-shadow: var(--shadow-sm) !important; overflow: hidden !important;
  margin-bottom: 10px !important; transition: box-shadow 0.2s ease !important;
}
.stExpander:hover { box-shadow: var(--shadow-md) !important; }
[data-testid="stExpander"] summary {
  border-radius: var(--r-md) !important; padding: 14px 18px !important;
  font-weight: 600 !important; font-size: 0.95rem !important;
  transition: background 0.15s ease !important; user-select: none !important;
}
[data-testid="stExpander"] summary:hover { background: rgba(0,0,0,0.02) !important; }

/* DataFrames */
[data-testid="stDataFrame"] {
  border-radius: var(--r-md) !important; overflow: hidden !important;
  box-shadow: var(--shadow-sm) !important; border: 1px solid var(--ios-sep) !important;
}
[data-testid="stDataFrame"] th {
  background: var(--ios-gray6) !important; font-weight: 600 !important;
  font-size: 0.8rem !important; text-transform: uppercase !important;
  letter-spacing: 0.6px !important; color: var(--ios-gray) !important; padding: 10px 14px !important;
}
[data-testid="stDataFrame"] td {
  font-size: 0.9rem !important; padding: 10px 14px !important;
  border-bottom: 1px solid var(--ios-sep) !important; transition: background 0.1s ease !important;
}
[data-testid="stDataFrame"] tr:hover td { background: rgba(0,122,255,0.04) !important; }

.stAlert { border-radius: var(--r-md) !important; border: none !important; box-shadow: var(--shadow-sm) !important; }

[data-testid="stSidebar"] {
  background: rgba(255,255,255,0.85) !important;
  backdrop-filter: blur(20px) !important; -webkit-backdrop-filter: blur(20px) !important;
  border-right: 1px solid var(--ios-sep) !important;
}

/* Ticker signal cards */
.ticker-card {
  border-radius: var(--r-lg); margin-bottom: 14px; overflow: hidden;
  box-shadow: var(--shadow-md); transition: box-shadow 0.25s ease, transform 0.25s ease;
  border: 1px solid var(--ios-sep);
}
.ticker-card:hover { box-shadow: var(--shadow-lg); transform: translateY(-2px); }
.signal-header {
  display: flex; align-items: center; gap: 10px; padding: 14px 20px;
  font-weight: 700; font-size: 1rem; letter-spacing: -0.2px;
  cursor: pointer; user-select: none; transition: filter 0.15s ease;
}
.signal-header:hover { filter: brightness(0.97); }
.signal-header:active { filter: brightness(0.93); }
.header-red   { background: linear-gradient(135deg,#FF3B30 0%,#FF6B60 100%); color: white; }
.header-green { background: linear-gradient(135deg,#34C759 0%,#5EE080 100%); color: white; }
.header-gray  { background: linear-gradient(135deg,#636366 0%,#8E8E93 100%); color: white; }
.header-badge {
  background: rgba(255,255,255,0.25); border-radius: 20px;
  padding: 3px 10px; font-size: 0.75rem; font-weight: 600;
  letter-spacing: 0.5px; backdrop-filter: blur(4px);
}

/* Matrix table */
.matrix-table {
  width: 100%; border-collapse: separate; border-spacing: 0;
  border-radius: var(--r-md); overflow: hidden;
  box-shadow: var(--shadow-md); font-size: 0.88rem;
}
.matrix-table th {
  background: #1C1C1E; color: white; padding: 11px 14px;
  font-weight: 600; font-size: 0.75rem; text-transform: uppercase;
  letter-spacing: 0.8px; text-align: left;
}
.matrix-table td {
  padding: 11px 14px; border-bottom: 1px solid var(--ios-sep);
  font-weight: 500; transition: filter 0.15s ease;
}
.matrix-table tr:last-child td { border-bottom: none; }
.matrix-table tr:hover td { filter: brightness(0.96); }

/* Profit cells */
.p-dg { background:#1B7F3A; color:white; font-weight:700; border-radius:8px; text-align:center; display:inline-block; width:80px; padding:5px 0; }
.p-g  { background:#34C759; color:white; font-weight:700; border-radius:8px; text-align:center; display:inline-block; width:80px; padding:5px 0; }
.p-lg { background:#B5EAC3; color:#1B5E20; font-weight:700; border-radius:8px; text-align:center; display:inline-block; width:80px; padding:5px 0; }
.p-n  { background:#F2F2F7; color:#636366; font-weight:700; border-radius:8px; text-align:center; display:inline-block; width:80px; padding:5px 0; }
.p-lr { background:#FDDEDE; color:#8B0000; font-weight:700; border-radius:8px; text-align:center; display:inline-block; width:80px; padding:5px 0; }
.p-r  { background:#FF3B30; color:white; font-weight:700; border-radius:8px; text-align:center; display:inline-block; width:80px; padding:5px 0; }
.p-dr { background:#C0392B; color:white; font-weight:700; border-radius:8px; text-align:center; display:inline-block; width:80px; padding:5px 0; }

/* Tags */
.tag-otm { background:rgba(52,199,89,0.15); color:#1B7F3A; border-radius:6px; padding:2px 7px; font-size:0.72rem; font-weight:700; }
.tag-atm { background:rgba(0,122,255,0.12); color:#007AFF; border-radius:6px; padding:2px 7px; font-size:0.72rem; font-weight:700; }
.tag-itm { background:rgba(255,59,48,0.12); color:#FF3B30; border-radius:6px; padding:2px 7px; font-size:0.72rem; font-weight:700; }

/* KPI strip */
.kpi-strip { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }
.kpi-card {
  flex:1; min-width:140px; background:white; border-radius:var(--r-md);
  padding:16px 20px; box-shadow:var(--shadow-sm); border:1px solid var(--ios-sep);
  transition:box-shadow 0.2s ease,transform 0.2s ease;
}
.kpi-card:hover { box-shadow:var(--shadow-md); transform:translateY(-2px); }
.kpi-label { font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:0.9px; color:var(--ios-gray); margin-bottom:6px; }
.kpi-value { font-size:1.7rem; font-weight:800; letter-spacing:-0.8px; color:var(--ios-label); line-height:1; }
.kpi-sub   { font-size:0.75rem; color:var(--ios-gray2); margin-top:4px; }
.kpi-vix-high { color:#FF3B30 !important; }
.kpi-vix-warn { color:#FF9500 !important; }
.kpi-vix-ok   { color:#34C759 !important; }

/* Section header */
.sec-hdr {
  font-size:1.1rem; font-weight:700; color:var(--ios-label); letter-spacing:-0.3px;
  margin:24px 0 12px 0; display:flex; align-items:center; gap:8px;
}
.sec-hdr::after { content:''; flex:1; height:1px; background:var(--ios-sep); }

/* Pills */
.pill { display:inline-block; border-radius:20px; padding:3px 10px; font-size:0.72rem; font-weight:700; letter-spacing:0.4px; }
.pill-blue   { background:rgba(0,122,255,0.12);  color:#007AFF; }
.pill-green  { background:rgba(52,199,89,0.15);  color:#1B7F3A; }
.pill-red    { background:rgba(255,59,48,0.12);  color:#FF3B30; }
.pill-gray   { background:rgba(142,142,147,0.15);color:#636366; }
</style>

“””, unsafe_allow_html=True)

# ── Persistence ──────────────────────────────────────────────────────────────

DATA_FILE = Path(“wheelos_data.json”)
KEY_FILE  = Path(“finnhub_key.json”)

def load_persistent_data():
if DATA_FILE.exists():
try:
with open(DATA_FILE, “r”) as f:
data = json.load(f)
st.session_state.trades      = data.get(“trades”, [])
st.session_state.held_shares = data.get(“held_shares”, [])
st.session_state.leaps       = data.get(“leaps”, [])
st.session_state.leap_fund   = data.get(“leap_fund”, 0.0)
st.session_state.journal     = data.get(“journal”, [])
except Exception:
pass

def save_persistent_data():
data = {
“trades”:      st.session_state.get(“trades”, []),
“held_shares”: st.session_state.get(“held_shares”, []),
“leaps”:       st.session_state.get(“leaps”, []),
“leap_fund”:   st.session_state.get(“leap_fund”, 0.0),
“journal”:     st.session_state.get(“journal”, [])
}
with open(DATA_FILE, “w”) as f:
json.dump(data, f)

# ── Session state ─────────────────────────────────────────────────────────────

if “finnhub_key” not in st.session_state:
st.session_state.finnhub_key = st.secrets.get(“finnhub”, {}).get(“key”, “”)
if not st.session_state.finnhub_key and KEY_FILE.exists():
try:
with open(KEY_FILE, “r”) as f:
st.session_state.finnhub_key = json.load(f).get(“key”, “”)
except Exception:
pass

defaults = {
“trades”: [], “held_shares”: [], “leaps”: [], “leap_fund”: 0.0,
“market_data”: {}, “tickers”: [“TSLL”, “SOXL”, “TQQQ”],
“capital”: 20000, “journal”: [], “vix”: 20.0,
}
for k, v in defaults.items():
if k not in st.session_state:
st.session_state[k] = v

load_persistent_data()

RED_THRESHOLD     = -1.5
GREEN_THRESHOLD   = 5.0
VIX_LIMIT         = 25
MAX_CALLS_PER_MIN = 50

# ── API helpers ───────────────────────────────────────────────────────────────

def fetch_quote(sym):
if not st.session_state.finnhub_key:
return None
try:
r = requests.get(
f”https://finnhub.io/api/v1/quote?symbol={sym}&token={st.session_state.finnhub_key}”,
timeout=10)
return r.json() if r.ok else None
except Exception:
return None

def fetch_candles(sym):
if not st.session_state.finnhub_key:
return None
try:
to_ts   = int(time.time())
from_ts = to_ts - 40 * 86400
r = requests.get(
f”https://finnhub.io/api/v1/stock/candle?symbol={sym}&resolution=D”
f”&from={from_ts}&to={to_ts}&token={st.session_state.finnhub_key}”,
timeout=10)
d = r.json()
if d.get(“s”) == “ok”:
return pd.DataFrame({
“time”:   pd.to_datetime(d[“t”], unit=“s”).dt.strftime(”%Y-%m-%d”),
“open”:   d[“o”], “high”: d[“h”], “low”: d[“l”], “close”: d[“c”],
“volume”: d.get(“v”, [0] * len(d[“c”]))
})
except Exception:
pass
return None

def fetch_options_chain(sym):
if not st.session_state.finnhub_key:
return None
try:
r = requests.get(
f”https://finnhub.io/api/v1/stock/option?symbol={sym}&token={st.session_state.finnhub_key}”,
timeout=10)
d = r.json()
return d.get(“data”, []) if isinstance(d, dict) else None
except Exception:
return None

def calc_rv(df):
if df is None or len(df) < 5:
return None
return round(df[“close”].pct_change().dropna().std() * (252 ** 0.5) * 100, 1)

def calc_rsi(df, period=14):
if df is None or len(df) < period + 1:
return None
delta = df[“close”].diff()
gain  = delta.where(delta > 0, 0).rolling(window=period).mean()
loss  = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
rs    = gain / loss
return round((100 - 100 / (1 + rs)).iloc[-1], 1)

def safe_batch_update(tickers):
updated = 0
vix_q = fetch_quote(“VIX”)
if vix_q and vix_q.get(“c”):
st.session_state.vix = round(vix_q[“c”], 2)
updated += 1
for sym in tickers:
if updated >= MAX_CALLS_PER_MIN:
break
q = fetch_quote(sym)
if q and q.get(“c”):
df     = fetch_candles(sym)
rv     = calc_rv(df)
rsi    = calc_rsi(df)
volume = int(df[“volume”].iloc[-1]) if df is not None and len(df) > 0 else None
st.session_state.market_data[sym] = {
“price”: round(q[“c”], 2), “change”: round(q.get(“dp”, 0), 2),
“rv”: rv, “rsi”: rsi, “volume”: volume
}
updated += 2
time.sleep(1.2)

def profit_cls(pct):
if   pct >  4: return “p-dg”
elif pct >  2: return “p-g”
elif pct >  0: return “p-lg”
elif pct == 0: return “p-n”
elif pct > -3: return “p-lr”
elif pct > -6: return “p-r”
else:          return “p-dr”

def money_tag(moneyness, opt_type):
if abs(moneyness) < 0.5:
return ‘<span class="tag-atm">ATM</span>’
if (opt_type == “Put” and moneyness < 0) or (opt_type == “Call” and moneyness > 0):
return ‘<span class="tag-otm">OTM</span>’
return ‘<span class="tag-itm">ITM</span>’

# ── First-time setup ──────────────────────────────────────────────────────────

if not st.session_state.finnhub_key:
st.markdown(”””
<div style="max-width:480px;margin:80px auto;text-align:center;">
<div style="font-size:3rem;margin-bottom:8px;">O</div>
<h1 style="font-size:2rem;margin-bottom:4px;">WheelOS</h1>
<p style="color:#8E8E93;font-size:1rem;margin-bottom:32px;">Options Radar - Profit Recycling Engine</p>
</div>
“””, unsafe_allow_html=True)
col = st.columns([1, 2, 1])[1]
with col:
st.markdown(”**First-time Setup**”)
st.info(“Get your free API key at [finnhub.io](https://finnhub.io) then Dashboard then API Key”)
key = st.text_input(“Finnhub API Key”, type=“password”, placeholder=“Paste your key here”)
if st.button(“Launch WheelOS”, type=“primary”, use_container_width=True):
if key.strip():
st.session_state.finnhub_key = key.strip()
with open(KEY_FILE, “w”) as f:
json.dump({“key”: key.strip()}, f)
st.success(“Connected! Launching…”)
st.rerun()
st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
st.markdown(”## WheelOS”)
st.markdown(’<span class="pill pill-green">Finnhub Live</span>’, unsafe_allow_html=True)
st.markdown(”—”)
if st.button(“Reset API Key”, type=“secondary”, use_container_width=True):
st.session_state.finnhub_key = “”
if KEY_FILE.exists():
KEY_FILE.unlink()
st.rerun()
st.markdown(”—”)
st.markdown(f”**Capital:** ${st.session_state.capital:,.0f}”)
st.markdown(f”**VIX:** {st.session_state.vix:.1f}”)
st.markdown(f”**House Money:** ${st.session_state.leap_fund:,.0f}”)

# ── Header ────────────────────────────────────────────────────────────────────

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
st.markdown(”# WheelOS - Options Radar”)
with col_h2:
if st.button(“Refresh All”, type=“primary”, use_container_width=True):
safe_batch_update(st.session_state.tickers)
st.success(“Updated!”)
st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
“Dashboard”, “Wheel Trades”, “LEAP Trades”,
“Super Chart”, “Calendar”, “Settings”
])

# ════════════════════════════════════════════════════════════════════════════════

# TAB 1 - DASHBOARD

# ════════════════════════════════════════════════════════════════════════════════

with tab1:
closed    = [t for t in st.session_state.trades if t.get(“status”) == “closed”]
total_pnl = sum(t.get(“pnl”, 0) for t in closed)
wins      = [t for t in closed if t.get(“pnl”, 0) > 0]
win_rate  = round(len(wins) / len(closed) * 100, 1) if closed else 0
avg_days  = round(sum(t.get(“days_active”, 0) for t in closed) / len(closed), 1) if closed else 0
vix_val   = st.session_state.vix

```
if vix_val >= 30:
    vix_color = "kpi-vix-high"
    vix_label = "DANGER"
elif vix_val >= 25:
    vix_color = "kpi-vix-warn"
    vix_label = "CAUTION"
else:
    vix_color = "kpi-vix-ok"
    vix_label = "SAFE"

pnl_color = "#34C759" if total_pnl >= 0 else "#FF3B30"
no_trade_txt = "No new trades" if vix_val >= VIX_LIMIT else "Trading enabled"

st.markdown('<div class="sec-hdr">Performance Overview</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="kpi-strip">
  <div class="kpi-card">
    <div class="kpi-label">House Money</div>
    <div class="kpi-value">${st.session_state.leap_fund:,.0f}</div>
    <div class="kpi-sub">LEAP fuel (recycled profit)</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Realized P&amp;L</div>
    <div class="kpi-value" style="color:{pnl_color}">${total_pnl:,.0f}</div>
    <div class="kpi-sub">{len(closed)} closed trades</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Win Rate</div>
    <div class="kpi-value">{win_rate}%</div>
    <div class="kpi-sub">{len(wins)} of {len(closed)} winners</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Avg Hold</div>
    <div class="kpi-value">{avg_days}d</div>
    <div class="kpi-sub">days to close</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">VIX - {vix_label}</div>
    <div class="kpi-value {vix_color}">{vix_val:.1f}</div>
    <div class="kpi-sub">{no_trade_txt}</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.info("Profit Recycling Loop: CSP on red days -> Close at 50% -> 50% income, 50% to House Money -> LEAP calls")

if st.session_state.market_data:
    st.markdown('<div class="sec-hdr">Live Market Data</div>', unsafe_allow_html=True)
    df_mkt = pd.DataFrame.from_dict(st.session_state.market_data, orient="index")
    df_mkt.index.name = "Ticker"

    def style_change(val):
        if isinstance(val, (int, float)):
            if val > 0: return "color: #34C759; font-weight:700"
            if val < 0: return "color: #FF3B30; font-weight:700"
        return ""

    st.dataframe(df_mkt.style.map(style_change, subset=["change"]), use_container_width=True)
```

# ════════════════════════════════════════════════════════════════════════════════

# TAB 2 - WHEEL TRADES

# ════════════════════════════════════════════════════════════════════════════════

with tab2:
st.markdown(’<div class="sec-hdr">Signal Scanner</div>’, unsafe_allow_html=True)

```
for ticker in st.session_state.tickers:
    d      = st.session_state.market_data.get(ticker, {})
    price  = d.get("price")
    rv     = d.get("rv")
    rsi    = d.get("rsi")
    volume = d.get("volume")

    if not price:
        st.markdown(f"""
        <div class="ticker-card">
          <div class="signal-header header-gray">
            <span>{ticker}</span>
            <span class="header-badge">AWAITING DATA</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
        continue

    chg      = d.get("change", 0)
    has_held = any(h["ticker"] == ticker for h in st.session_state.held_shares)

    if st.session_state.vix >= VIX_LIMIT:
        signal        = f"NO TRADE - VIX >= {VIX_LIMIT}"
        header_cls    = "header-gray"
        badge_txt     = "VIX BLOCK"
        is_put        = True
        trade_enabled = False
    elif (rsi and rsi > 60) or (rv is not None and rv < 50):
        signal        = "NO TRADE - RSI >60 or Low IV"
        header_cls    = "header-gray"
        badge_txt     = "FILTER BLOCK"
        is_put        = True
        trade_enabled = False
    elif chg <= RED_THRESHOLD:
        signal        = f"SELL CSP PUT  {chg:+.1f}%"
        header_cls    = "header-red"
        badge_txt     = "RED DAY"
        is_put        = True
        trade_enabled = True
    elif chg >= GREEN_THRESHOLD and has_held:
        signal        = f"SELL COVERED CALL  {chg:+.1f}%"
        header_cls    = "header-green"
        badge_txt     = "GREEN DAY"
        is_put        = False
        trade_enabled = True
    else:
        signal        = f"NO TRADE - Day {chg:+.1f}%"
        header_cls    = "header-gray"
        badge_txt     = f"{chg:+.1f}%"
        is_put        = True
        trade_enabled = False

    strike   = round(price * (0.90 if is_put else 1.10), 2)
    premium  = round(price * 0.04, 2)
    iv       = rv or 85
    expiry   = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    prem_pct = round((premium / price) * 100, 1)
    n_contr  = int(st.session_state.capital * 0.25 // (price * 100)) if price else 0

    st.markdown(f"""
    <div class="ticker-card">
      <div class="signal-header {header_cls}">
        <span style="font-size:1.1rem;">{ticker}</span>
        <span class="header-badge">{badge_txt}</span>
        <span style="margin-left:auto;opacity:0.9;font-size:0.9rem;">{signal}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander(f"Details & Order Entry - {ticker}", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Price",     f"${price:,.2f}")
            st.metric("Change",    f"{chg:+.2f}%")
        with c2:
            st.metric("Strike",    f"${strike}")
            st.metric("Premium",   f"${premium}")
        with c3:
            st.metric("Prem %",    f"{prem_pct}%")
            st.metric("IV (RV)",   f"{iv}%")
        with c4:
            st.metric("RSI",       f"{rsi if rsi else '--'}")
            st.metric("DTE",       "30 days")
        with c5:
            st.metric("Volume",    f"{volume:,.0f}" if volume else "--")
            st.metric("Contracts", f"~{n_contr}")

        trade_lbl = "CSP Put" if is_put else "Covered Call"
        st.caption(f"Expiry: {expiry} - Max 25% capital allocation - {trade_lbl}")

        btn_label = f"Log {trade_lbl} on {ticker}"
        if trade_enabled:
            if st.button(btn_label, key=f"trade_{ticker}", type="primary"):
                st.session_state.trades.append({
                    "id": int(time.time()), "type": trade_lbl, "ticker": ticker,
                    "strike": strike, "expiry": expiry, "entry_premium": premium,
                    "status": "open", "pnl": 0, "contracts": n_contr
                })
                save_persistent_data()
                st.success(f"{trade_lbl} logged on {ticker}")
                st.rerun()
        else:
            st.button(btn_label, disabled=True, key=f"dis_{ticker}")

# Open trades
st.markdown('<div class="sec-hdr">Open Positions</div>', unsafe_allow_html=True)
open_trades = [t for t in st.session_state.trades if t.get("status") == "open"]
if not open_trades:
    st.markdown('<p style="color:#8E8E93;font-style:italic;padding:12px 0;">No open positions.</p>', unsafe_allow_html=True)
for t in open_trades:
    with st.expander(f"{t['ticker']} {t['type']} @ ${t['strike']} - {t['expiry']}"):
        ca, cb, cc = st.columns(3)
        with ca: st.metric("Entry Premium", f"${t.get('entry_premium', '--')}")
        with cb: st.metric("Contracts",     f"{t.get('contracts', 1)}")
        with cc: st.metric("Status",        t.get("status", "open").title())
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Close at 50% Profit", key=f"close_{t['id']}", type="primary"):
                profit = round(t["entry_premium"] * 0.5, 2)
                t["pnl"] = profit
                t["status"] = "closed"
                t["closed_date"] = datetime.now().strftime("%Y-%m-%d")
                st.session_state.leap_fund += profit * 0.5
                st.session_state.journal.append({
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "ticker": t["ticker"], "type": t["type"],
                    "action": "Closed at 50%", "profit": profit, "note": "Recycled"
                })
                save_persistent_data()
                st.success(f"Closed! +${profit:.2f} -> ${profit*0.5:.2f} to House Money")
                st.rerun()
        with c2:
            if t["type"] == "CSP Put":
                if st.button("Simulate Assignment", key=f"assign_{t['id']}"):
                    shares     = t.get("contracts", 1) * 100
                    cost_basis = t["strike"] - t["entry_premium"]
                    st.session_state.held_shares.append({
                        "ticker": t["ticker"], "shares": shares,
                        "cost_basis": round(cost_basis, 2),
                        "entry_date": datetime.now().strftime("%Y-%m-%d")
                    })
                    t["status"] = "assigned"
                    save_persistent_data()
                    st.success(f"Assigned - {shares} shares at ${cost_basis:.2f}")
                    st.rerun()

# Held shares
st.markdown('<div class="sec-hdr">Held Shares</div>', unsafe_allow_html=True)
if not st.session_state.held_shares:
    st.markdown('<p style="color:#8E8E93;font-style:italic;padding:12px 0;">No held shares.</p>', unsafe_allow_html=True)
for idx, h in enumerate(st.session_state.held_shares):
    with st.expander(f"{h['ticker']} - {h['shares']} shares @ ${h['cost_basis']}"):
        c1, c2 = st.columns(2)
        with c1: st.metric("Cost Basis",  f"${h['cost_basis']}")
        with c2: st.metric("Entry Date",  h.get("entry_date", "--"))
        if st.button("Simulate Call-Away", key=f"callaway_{idx}", type="primary"):
            st.session_state.held_shares.pop(idx)
            save_persistent_data()
            st.success("Wheel complete - shares called away!")
            st.rerun()

# Options matrix
st.markdown('<div class="sec-hdr">Options Matrix - Strike Profit % Color Map</div>', unsafe_allow_html=True)
c_inp, c_btn = st.columns([3, 1])
with c_inp:
    matrix_ticker = st.text_input(
        "Ticker for Matrix", value="QQQ", key="matrix_input",
        placeholder="e.g. AAPL, NVDA, SPY"
    ).upper().strip()
with c_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    load_matrix = st.button("Load Matrix", type="primary", use_container_width=True)

if load_matrix:
    with st.spinner(f"Fetching options for {matrix_ticker}..."):
        pdata = fetch_quote(matrix_ticker)
        price = pdata["c"] if pdata and pdata.get("c") else 0
    if not price:
        st.error(f"Could not find price for {matrix_ticker}")
    else:
        rows   = []
        source = "Estimated (Finnhub free-tier)"
        options_raw = fetch_options_chain(matrix_ticker)
        if options_raw:
            today    = datetime.now().date()
            expiries = {}
            for c in options_raw:
                if "expiry" not in c:
                    continue
                exp_date = datetime.strptime(c["expiry"], "%Y-%m-%d").date()
                dte      = (exp_date - today).days
                if dte > 0:
                    expiries.setdefault(dte, []).append(c)
            if expiries:
                closest_dte = min(expiries.keys(), key=lambda d: abs(d - 30))
                for c in expiries[closest_dte]:
                    sp       = c["strike"]
                    prem     = round((c.get("bid", 0) + c.get("ask", 0)) / 2, 2)
                    iv       = c.get("iv") or "--"
                    otype    = "Put" if c.get("putCall") == "P" else "Call"
                    otm_flag = (otype == "Put" and price > sp) or (otype == "Call" and price < sp)
                    pnl      = prem if otm_flag else prem - abs(price - sp)
                    pp       = round((pnl / price) * 100, 2)
                    mm       = round((sp - price) / price * 100, 1)
                    rows.append({"type": otype, "strike": sp, "premium": prem, "iv": iv, "profit_pct": pp, "moneyness": mm})
                source = "Real Finnhub chain"

        if not rows:
            for pct in [0.80, 0.90, 1.00, 1.10, 1.20]:
                sp      = round(price * pct, 2)
                is_call = pct >= 1.0
                otype   = "Call" if is_call else "Put"
                prem    = round(price * 0.04, 2)
                otm_f   = (is_call and price < sp) or (not is_call and price > sp)
                pnl     = prem if otm_f else prem - abs(price - sp)
                pp      = round((pnl / price) * 100, 2)
                mm      = round((sp - price) / price * 100, 1)
                rows.append({"type": otype, "strike": sp, "premium": prem, "iv": "--", "profit_pct": pp, "moneyness": mm})

        trows = ""
        for r in sorted(rows, key=lambda x: x["strike"]):
            pc   = r["profit_pct"]
            cls  = profit_cls(pc)
            mtag = money_tag(r["moneyness"], r["type"])
            iv_s = f"{r['iv']}%" if r["iv"] != "--" else "--"
            sign = "+" if pc > 0 else ""
            trows += f"""
            <tr>
              <td><strong>{r['type']}</strong></td>
              <td>${r['strike']:,.2f} {mtag}</td>
              <td>${r['premium']:.2f}</td>
              <td>{iv_s}</td>
              <td><span class="{cls}">{sign}{pc:.1f}%</span></td>
              <td style="color:#8E8E93">{r['moneyness']:+.1f}%</td>
            </tr>"""

        st.markdown(f"""
        <div style="margin-top:12px;">
          <table class="matrix-table">
            <thead><tr>
              <th>Type</th><th>Strike</th><th>Premium</th>
              <th>IV</th><th>Profit %</th><th>Moneyness</th>
            </tr></thead>
            <tbody>{trows}</tbody>
          </table>
          <p style="margin-top:10px;font-size:0.75rem;color:#8E8E93;">
            {source} - Profit % = (premium minus intrinsic) / stock price -
            <span class="tag-otm">OTM</span> full premium captured
            <span class="tag-itm">ITM</span> intrinsic loss deducted
            <span class="tag-atm">ATM</span> at-the-money
          </p>
        </div>
        """, unsafe_allow_html=True)
```

# ════════════════════════════════════════════════════════════════════════════════

# TAB 3 - LEAP TRADES

# ════════════════════════════════════════════════════════════════════════════════

with tab3:
st.markdown(’<div class="sec-hdr">LEAP Call Finder - 360+ DTE</div>’, unsafe_allow_html=True)
st.markdown(f’<span class="pill pill-blue">House Money: ${st.session_state.leap_fund:,.0f}</span>’, unsafe_allow_html=True)
st.markdown(”<br>”, unsafe_allow_html=True)

```
c_lt, c_lb = st.columns([3, 1])
with c_lt:
    leap_ticker = st.text_input(
        "Ticker for LEAP", value="QQQ", key="leap_input",
        placeholder="e.g. NVDA, AAPL, SPY"
    ).upper().strip()
with c_lb:
    st.markdown("<br>", unsafe_allow_html=True)
    load_leap = st.button("Find LEAP", type="primary", use_container_width=True)

if load_leap:
    with st.spinner(f"Fetching LEAP options for {leap_ticker}..."):
        pdata = fetch_quote(leap_ticker)
        price = pdata["c"] if pdata and pdata.get("c") else 0
    if not price:
        st.error("Ticker not found")
    else:
        options_raw = fetch_options_chain(leap_ticker)
        leap_rsi    = calc_rsi(fetch_candles(leap_ticker))
        if options_raw:
            today    = datetime.now().date()
            expiries = {}
            for c in options_raw:
                if "expiry" not in c:
                    continue
                exp_date = datetime.strptime(c["expiry"], "%Y-%m-%d").date()
                dte      = (exp_date - today).days
                if dte >= 360:
                    expiries.setdefault(dte, []).append(c)
            if expiries:
                closest_dte = min(expiries.keys())
                chain       = expiries[closest_dte]
                calls       = [c for c in chain if c.get("putCall") == "C"]
                if calls:
                    best    = min(calls, key=lambda c: abs(c["strike"] - price * 1.10))
                    strike  = best["strike"]
                    premium = round((best.get("bid", 0) + best.get("ask", 0)) / 2, 2)
                    iv      = best.get("iv") or "--"
                    expiry  = chain[0]["expiry"]
                    iv_disp = f"{iv}%" if iv != "--" else "--"
                    rsi_disp = leap_rsi if leap_rsi else "--"

                    st.markdown(f"""
                    <div style="background:white;border-radius:18px;padding:24px;
                                box-shadow:0 4px 12px rgba(0,0,0,0.10);
                                border:1px solid rgba(60,60,67,0.12);max-width:520px;margin-bottom:20px;">
                      <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;
                                  letter-spacing:0.8px;color:#8E8E93;margin-bottom:14px;">
                        LEAP Call - {leap_ticker} - {closest_dte} DTE
                      </div>
                      <div style="display:flex;flex-wrap:wrap;gap:16px;">
                        <div><div class="kpi-label">Current Price</div><div class="kpi-value">${price:,.2f}</div></div>
                        <div><div class="kpi-label">Strike 10% OTM</div><div class="kpi-value">${strike:,.2f}</div></div>
                        <div><div class="kpi-label">Premium</div><div class="kpi-value">${premium:,.2f}</div></div>
                        <div><div class="kpi-label">Total Cost</div><div class="kpi-value">${premium*100:,.0f}</div></div>
                        <div><div class="kpi-label">IV</div><div class="kpi-value">{iv_disp}</div></div>
                        <div><div class="kpi-label">RSI</div><div class="kpi-value">{rsi_disp}</div></div>
                        <div><div class="kpi-label">Expiry</div><div class="kpi-value" style="font-size:1rem;">{expiry}</div></div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button("Add LEAP (house money only)", type="primary"):
                        if st.session_state.leap_fund >= premium * 100:
                            st.session_state.leaps.append({
                                "id": int(time.time()), "ticker": leap_ticker,
                                "cost": premium * 100, "current_val": premium * 100,
                                "contracts": 1, "expiry": expiry
                            })
                            st.session_state.leap_fund -= premium * 100
                            save_persistent_data()
                            st.success(f"LEAP added - ${premium*100:.0f} deducted from house money")
                            st.rerun()
                        else:
                            st.error(f"Insufficient house money (need ${premium*100:.0f}, have ${st.session_state.leap_fund:.0f})")
                else:
                    st.warning("No suitable 360+ DTE calls found")
            else:
                st.warning("No options with 360+ DTE available")
        else:
            st.warning("Options chain unavailable for this ticker")

st.markdown('<div class="sec-hdr">LEAP Positions</div>', unsafe_allow_html=True)
if not st.session_state.leaps:
    st.markdown('<p style="color:#8E8E93;font-style:italic;">No LEAP positions yet.</p>', unsafe_allow_html=True)
for l in st.session_state.leaps:
    with st.expander(f"{l['ticker']} LEAP - Expiry {l['expiry']}"):
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Cost",        f"${l['cost']:.0f}")
        with c2: st.metric("Current Val", f"${l['current_val']:.0f}")
        with c3: st.metric("Contracts",   f"{l['contracts']}")
        if st.button("Sell Half & Recycle", key=l["id"], type="secondary"):
            st.session_state.leap_fund += l["cost"] * 0.8
            l["contracts"] = max(0, l["contracts"] - 1)
            save_persistent_data()
            st.success("Half sold - 80% cost recycled to house money")
            st.rerun()
```

# ════════════════════════════════════════════════════════════════════════════════

# TAB 4 - SUPER CHART

# ════════════════════════════════════════════════════════════════════════════════

with tab4:
st.markdown(’<div class="sec-hdr">TradingView Super Chart + RSI + MACD</div>’, unsafe_allow_html=True)
chart_ticker = st.selectbox(“Select Ticker”, st.session_state.tickers, key=“superchart_ticker”)
tv_html = f”””
<div style="width:100%;height:620px;border-radius:18px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.12);">
<div id="tv_widget" style="width:100%;height:100%;"></div>
<script src="https://s3.tradingview.com/tv.js"></script>
<script>
new TradingView.widget({{
autosize:true, symbol:”{chart_ticker}”, interval:“D”,
timezone:“Etc/UTC”, theme:“light”, style:“1”, locale:“en”,
toolbar_bg:”#f1f3f6”, enable_publishing:false, hide_side_toolbar:false,
allow_symbol_change:true,
studies:[“RSI@tv-basicstudies”,“MACD@tv-basicstudies”],
container_id:“tv_widget”
}});
</script>
</div>
“””
st.components.v1.html(tv_html, height=650, scrolling=False)

# ════════════════════════════════════════════════════════════════════════════════

# TAB 5 - CALENDAR

# ════════════════════════════════════════════════════════════════════════════════

with tab5:
st.markdown(’<div class="sec-hdr">Economic Calendar</div>’, unsafe_allow_html=True)
st.markdown(f”””
<div style="background:white;border-radius:18px;padding:24px;
box-shadow:0 1px 3px rgba(0,0,0,0.08);border:1px solid rgba(60,60,67,0.12);">
<p style="margin:0 0 8px 0;color:#636366;font-size:0.9rem;">
Avoid new trades on <strong>high VIX (>={VIX_LIMIT})</strong> or major macro events.
</p>
<p style="margin:0;color:#8E8E93;font-size:0.85rem;">
Watch: FOMC meetings - CPI / PCE releases - Non-Farm Payrolls - Earnings dates
</p>
</div>
“””, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════

# TAB 6 - SETTINGS

# ════════════════════════════════════════════════════════════════════════════════

with tab6:
st.markdown(’<div class="sec-hdr">Capital</div>’, unsafe_allow_html=True)
manual = st.number_input(“Investment Capital ($)”, min_value=5000, value=st.session_state.capital, step=1000)
if st.button(“Save Capital”, type=“primary”):
st.session_state.capital = manual
st.success(f”Capital set to ${manual:,.0f}”)

```
st.markdown('<div class="sec-hdr">API Key</div>', unsafe_allow_html=True)
st.markdown('<span class="pill pill-green">Finnhub connected</span>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)
new_key = st.text_input("Update Finnhub API Key", type="password", placeholder="Paste new key")
if st.button("Update Key", type="secondary"):
    if new_key.strip():
        st.session_state.finnhub_key = new_key.strip()
        with open(KEY_FILE, "w") as f:
            json.dump({"key": new_key.strip()}, f)
        st.success("Key updated")
        st.rerun()

st.markdown('<div class="sec-hdr">Watched Tickers</div>', unsafe_allow_html=True)
for t in st.session_state.tickers:
    c1, c2 = st.columns([5, 1])
    with c1:
        st.markdown(f"""
        <div style="background:white;border-radius:12px;padding:12px 16px;
                    box-shadow:0 1px 3px rgba(0,0,0,0.08);border:1px solid rgba(60,60,67,0.12);
                    font-weight:600;color:#1C1C1E;margin-bottom:8px;">
          {t}
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("X", key=f"rem_{t}", type="secondary"):
            if len(st.session_state.tickers) > 1:
                st.session_state.tickers.remove(t)
                st.rerun()
            else:
                st.error("Need at least 1 ticker")

st.markdown('<div class="sec-hdr">Add Ticker</div>', unsafe_allow_html=True)
ca, cb = st.columns([3, 1])
with ca:
    new_t = st.text_input("Symbol", placeholder="e.g. NVDA, AAPL, SPY", label_visibility="collapsed").upper().strip()
with cb:
    if st.button("Add", type="primary", use_container_width=True):
        if new_t and new_t not in st.session_state.tickers:
            q = fetch_quote(new_t)
            if q and q.get("c"):
                st.session_state.tickers.append(new_t)
                st.success(f"Added {new_t}")
                st.rerun()
            else:
                st.error("Ticker not found")
        elif new_t in st.session_state.tickers:
            st.warning("Already watching")
```

# ── Auto-refresh (15 min) ─────────────────────────────────────────────────────

if “last_refresh” not in st.session_state:
st.session_state.last_refresh = time.time()
if time.time() - st.session_state.last_refresh > 900:
safe_batch_update(st.session_state.tickers)
st.session_state.last_refresh = time.time()

st.markdown(”””

<div style="text-align:center;padding:24px 0 8px 0;color:#AEAEB2;font-size:0.75rem;letter-spacing:0.3px;">
  WheelOS - Options Radar - iOS-style UI
</div>
""", unsafe_allow_html=True)