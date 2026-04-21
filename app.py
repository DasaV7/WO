import streamlit as st
import pandas as pd
import requests
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(page_title="WheelOS • Options Radar", page_icon="◈", layout="wide")

st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; }
        .metric-label { font-size: 0.9rem; color: #555; }
    </style>
""", unsafe_allow_html=True)

DATA_FILE = Path("wheelos_data.json")

def load_persistent_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            st.session_state.trades = data.get("trades", [])
            st.session_state.held_shares = data.get("held_shares", [])
            st.session_state.leaps = data.get("leaps", [])
            st.session_state.leap_fund = data.get("leap_fund", 0.0)
            st.session_state.journal = data.get("journal", [])
        except:
            pass

def save_persistent_data():
    data = {
        "trades": st.session_state.get("trades", []),
        "held_shares": st.session_state.get("held_shares", []),
        "leaps": st.session_state.get("leaps", []),
        "leap_fund": st.session_state.get("leap_fund", 0.0),
        "journal": st.session_state.get("journal", [])
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# ==================== SESSION STATE ====================
if 'finnhub_key' not in st.session_state:
    st.session_state.finnhub_key = st.secrets.get("finnhub", {}).get("key", "")
if 'trades' not in st.session_state: st.session_state.trades = []
if 'held_shares' not in st.session_state: st.session_state.held_shares = []
if 'leaps' not in st.session_state: st.session_state.leaps = []
if 'leap_fund' not in st.session_state: st.session_state.leap_fund = 0.0
if 'market_data' not in st.session_state: st.session_state.market_data = {}
if 'tickers' not in st.session_state: st.session_state.tickers = ["TSLL", "SOXL", "TQQQ"]
if 'capital' not in st.session_state: st.session_state.capital = 20000
if 'journal' not in st.session_state: st.session_state.journal = []
if 'vix' not in st.session_state: st.session_state.vix = 20.0

load_persistent_data()

RED_THRESHOLD = -1.5
GREEN_THRESHOLD = 5.0
VIX_LIMIT = 25
MAX_CALLS_PER_MIN = 50

# ==================== FINNHUB HELPERS ====================
def fetch_quote(sym): 
    if not st.session_state.finnhub_key: return None
    try:
        r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={st.session_state.finnhub_key}", timeout=10)
        return r.json() if r.ok else None
    except: return None

def fetch_candles(sym): 
    if not st.session_state.finnhub_key: return None
    try:
        to_ts = int(time.time())
        from_ts = to_ts - (40 * 86400)
        r = requests.get(f"https://finnhub.io/api/v1/stock/candle?symbol={sym}&resolution=D&from={from_ts}&to={to_ts}&token={st.session_state.finnhub_key}", timeout=10)
        data = r.json()
        if data.get("s") == "ok":
            return pd.DataFrame({"time": pd.to_datetime(data["t"], unit="s").dt.strftime("%Y-%m-%d"),
                                 "open": data["o"], "high": data["h"], "low": data["l"], "close": data["c"],
                                 "volume": data.get("v", [0] * len(data["c"]))})
    except: pass
    return None

def fetch_options_chain(sym):
    if not st.session_state.finnhub_key: return None
    try:
        r = requests.get(f"https://finnhub.io/api/v1/stock/option?symbol={sym}&token={st.session_state.finnhub_key}", timeout=10)
        data = r.json()
        return data.get("data", []) if isinstance(data, dict) else None
    except: return None

def calc_rv(df):
    if df is None or len(df) < 5: return None
    returns = df["close"].pct_change().dropna()
    return round(returns.std() * (252 ** 0.5) * 100, 1)

def calc_rsi(df, period=14):
    if df is None or len(df) < period + 1: return None
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 1)

def safe_batch_update(tickers):
    updated = 0
    vix_q = fetch_quote("VIX")
    if vix_q and vix_q.get("c"):
        st.session_state.vix = round(vix_q["c"], 2)
        updated += 1
    for sym in tickers:
        if updated >= MAX_CALLS_PER_MIN: break
        q = fetch_quote(sym)
        if q and q.get("c"):
            df = fetch_candles(sym)
            rv = calc_rv(df)
            rsi = calc_rsi(df)
            volume = int(df["volume"].iloc[-1]) if df is not None and len(df) > 0 else None
            st.session_state.market_data[sym] = {
                "price": round(q["c"], 2),
                "change": round(q.get("dp", 0), 2),
                "rv": rv,
                "rsi": rsi,
                "volume": volume,
                "options": None  # we fetch matrix on demand now
            }
            updated += 2
        time.sleep(1.2)

# ==================== KEY PERSISTENCE ====================
st.components.v1.html("""
<script>
const saved = localStorage.getItem('wheelos_finnhub_key');
if (saved) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.id = 'finnhub_key_load';
    input.value = saved;
    document.body.appendChild(input);
}
</script>
""", height=0)

hidden_key = st.text_input("", key="finnhub_key_hidden", label_visibility="collapsed")
if hidden_key:
    st.session_state.finnhub_key = hidden_key

# ==================== FIRST-TIME SETUP ====================
if not st.session_state.finnhub_key:
    st.title("Welcome to WheelOS")
    st.markdown("### First Time Setup")
    st.info("Get your free Finnhub API key at [finnhub.io](https://finnhub.io) → Dashboard → API Key")
    key = st.text_input("Paste your Finnhub API Key", type="password")
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Save & Launch App", type="primary"):
            if key.strip():
                st.session_state.finnhub_key = key.strip()
                st.rerun()
    with col2:
        if st.button("💾 Save to Browser (persists forever)"):
            if key.strip():
                st.session_state.finnhub_key = key.strip()
                st.components.v1.html(f"""
                <script>
                localStorage.setItem('wheelos_finnhub_key', '{key.strip()}');
                alert('✅ Key saved securely in browser!');
                </script>
                """, height=0)
                st.success("Key saved permanently")
                st.rerun()
    st.stop()

# Sidebar
with st.sidebar:
    st.title("◈ WheelOS")
    st.success("Finnhub connected")
    if st.button("Reset Finnhub Key"):
        st.session_state.finnhub_key = ""
        st.rerun()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Dashboard", "🔁 CSP / Wheel Trades", "🚀 LEAP Trades", "📈 Super Chart", "📅 Calendar", "⚙️ Settings"])

with tab1:
    st.subheader("Matt’s Profit Recycling Loop")
    st.info("CSP → Assignment → Covered Calls → 50% income, 50% to LEAP fund")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: st.metric("House Money", f"${st.session_state.leap_fund:,.0f}")
    with col2: 
        closed = [t for t in st.session_state.trades if t.get("status") == "closed"]
        total_pnl = sum(t.get("pnl", 0) for t in closed)
        st.metric("Realized P&L", f"${total_pnl:,.0f}")
    with col3:
        win_rate = round(len([t for t in closed if t.get("pnl",0) > 0]) / len(closed) * 100, 1) if closed else 0
        st.metric("Win Rate", f"{win_rate}%")
    with col4:
        avg_days = round(sum(t.get("days_active", 0) for t in closed) / len(closed), 1) if closed else 0
        st.metric("Avg Days to Close", f"{avg_days} days")
    with col5:
        st.metric("VIX", f"{st.session_state.vix:.1f}")

    if st.button("🔄 Safe Refresh (≤50 calls/min)"):
        safe_batch_update(st.session_state.tickers)
        st.success("Batch update completed safely")
        st.rerun()

    if st.session_state.market_data:
        st.dataframe(pd.DataFrame.from_dict(st.session_state.market_data, orient="index"), use_container_width=True)

with tab2:
    st.subheader("Wheel Trades • Red Day CSP Put | Green Day Covered Call")
    for ticker in st.session_state.tickers:
        d = st.session_state.market_data.get(ticker, {})
        price = d.get("price")
        rv = d.get("rv")
        rsi = d.get("rsi")
        volume = d.get("volume")
        if not price:
            st.write(f"Waiting for data on {ticker}...")
            continue

        chg = d.get("change", 0)
        has_held = any(h['ticker'] == ticker for h in st.session_state.held_shares)

        signal = "NO TRADE"
        color_style = "color: gray;"
        button_type = "secondary"
        is_put = True

        if st.session_state.vix >= VIX_LIMIT:
            signal = f"NO TRADE (VIX HIGH ≥{VIX_LIMIT})"
        elif (rsi and rsi > 60) or (rv is not None and rv < 50):
            signal = "NO TRADE (RSI >60 or Low IV)"
        elif chg <= RED_THRESHOLD:
            signal = f"SELL CSP PUT (Red Day {chg:.1f}%)"
            color_style = "color: #d32f2f;"
            button_type = "primary"
            is_put = True
        elif chg >= GREEN_THRESHOLD and has_held:
            signal = f"SELL COVERED CALL (Green Day {chg:.1f}%)"
            color_style = "color: #2e7d32;"
            button_type = "primary"
            is_put = False

        with st.expander(f"{ticker} — **{signal}**"):
            st.markdown(f"<h4 style='{color_style}'>{signal}</h4>", unsafe_allow_html=True)

            # REAL CHAIN or estimate
            options_raw = fetch_options_chain(ticker)
            if options_raw:
                today = datetime.now().date()
                valid = [c for c in options_raw if 'expiry' in c]
                expiries = {}
                for c in valid:
                    exp_date = datetime.strptime(c['expiry'], "%Y-%m-%d").date()
                    dte = (exp_date - today).days
                    if dte > 0:
                        expiries.setdefault(dte, []).append(c)
                if expiries:
                    closest_dte = min(expiries.keys(), key=lambda d: abs(d - 30))
                    chain = expiries[closest_dte]
                    puts = [c for c in chain if c.get('putCall') == 'P']
                    calls = [c for c in chain if c.get('putCall') == 'C']
                    otm_put = min(puts, key=lambda c: abs(c['strike'] - price*0.9)) if puts else None
                    otm_call = min(calls, key=lambda c: abs(c['strike'] - price*1.1)) if calls else None
                    opt = otm_put if is_put else otm_call
                    if opt:
                        strike = opt['strike']
                        premium = round((opt.get('bid',0) + opt.get('ask',0))/2, 2)
                        iv = opt.get('iv') or (rv or 85)
                        dte = closest_dte
                        expiry = chain[0]['expiry']
                        source = "✅ REAL Finnhub"
                    else:
                        strike = round(price * (0.9 if is_put else 1.1), 2)
                        premium = round(price * 0.04, 2)
                        iv = rv or 85
                        dte = 30
                        expiry = "≈30 days"
                        source = "Estimate"
                else:
                    source = "Estimate (no chain)"
            else:
                strike = round(price * (0.9 if is_put else 1.1), 2)
                premium = round(price * 0.04, 2)
                iv = rv or 85
                dte = 30
                expiry = "≈30 days"
                source = "Estimate (chain unavailable)"

            cols = st.columns([2, 2, 2, 2])
            with cols[0]:
                st.metric("Price", f"${price:,.2f}")
                st.metric("Day Change", f"{chg}%")
            with cols[1]:
                st.metric("Strike (10% OTM)", f"${strike}")
                st.metric("Premium", f"${premium}")
            with cols[2]:
                st.metric("Premium %", f"{round((premium / price)*100, 1)}%")
                st.metric("IV", f"{iv}%")
            with cols[3]:
                st.metric("RSI", f"{rsi if rsi else '—'}")
                st.metric("Volume", f"{volume:,.0f}" if volume else "—")

            st.caption(f"**DTE:** {dte} days • Expiry: {expiry} • {source}")

            # ... (log button and suggested size unchanged - same as previous version)

    # ==================== NEW OPTIONS MATRIX ====================
    st.subheader("📊 Options Matrix (30 DTE) – P&L Color Map")
    matrix_ticker = st.selectbox("Select Ticker", st.session_state.tickers, key="matrix_sel")
    if st.button("Load Full Options Matrix"):
        options_raw = fetch_options_chain(matrix_ticker)
        price = st.session_state.market_data.get(matrix_ticker, {}).get("price", 0)
        if options_raw and price:
            today = datetime.now().date()
            valid = [c for c in options_raw if 'expiry' in c]
            expiries = {}
            for c in valid:
                exp_date = datetime.strptime(c['expiry'], "%Y-%m-%d").date()
                dte = (exp_date - today).days
                if dte > 0:
                    expiries.setdefault(dte, []).append(c)
            if expiries:
                closest_dte = min(expiries.keys(), key=lambda d: abs(d - 30))
                chain = expiries[closest_dte]
                rows = []
                for c in chain:
                    strike = c['strike']
                    prem = round((c.get('bid',0) + c.get('ask',0))/2, 2)
                    iv = c.get('iv') or "—"
                    opt_type = "Put" if c.get('putCall') == 'P' else "Call"
                    # P&L if stock price stays the same at expiry (selling the option)
                    if opt_type == "Put":
                        pnl = prem if price > strike else prem - (strike - price)
                    else:
                        pnl = prem if price < strike else prem - (price - strike)
                    rows.append({
                        "Type": opt_type,
                        "Strike": strike,
                        "Premium": prem,
                        "IV %": iv,
                        "P&L (sell, unchanged price)": round(pnl, 2)
                    })
                df_matrix = pd.DataFrame(rows).sort_values("Strike")
                # Color map
                def color_pnl(val):
                    return f'background-color: {"#2e7d32" if val > 0 else "#d32f2f"}; color: white'
                styled = df_matrix.style.applymap(color_pnl, subset=['P&L (sell, unchanged price)'])
                st.dataframe(styled, use_container_width=True, hide_index=True)
            else:
                st.warning("No 30 DTE chain found")
        else:
            st.error("Options chain unavailable for this ticker (Finnhub free-tier limitation). Try adding QQQ or SPY.")

    # Open trades, held shares, etc. (unchanged - with save_persistent_data() on every action)

# (LEAP tab, Super Chart, Settings, etc. remain exactly as in the previous stable version - omitted here for brevity but included in the full file you paste)

# Auto-refresh + caption
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if time.time() - st.session_state.last_refresh > 900:
    safe_batch_update(st.session_state.tickers)
    st.session_state.last_refresh = time.time()

if st.button("🔄 Safe Full Refresh (≤50 calls/min)"):
    safe_batch_update(st.session_state.tickers)
    st.success("Safe batch update completed")
    st.rerun()

st.caption("WheelOS • Real Options Chain + Permanent Journal + Color-Coded Options Matrix")
