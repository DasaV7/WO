import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(page_title="WheelOS • Options Radar", page_icon="◈", layout="wide")

# Light clean theme
st.markdown("""
<style>
    .main {background-color: #f0f4f8;}
    .stButton>button {border-radius: 10px; font-weight: 700;}
    .badge-call {background:#fef3c7; color:#92400e; padding:4px 10px; border-radius:5px; font-size:10px; font-weight:800;}
    .badge-put {background:#d1fae5; color:#065f46; padding:4px 10px; border-radius:5px; font-size:10px; font-weight:800;}
    .badge-wait {background:#f1f5f9; color:#64748b; padding:4px 10px; border-radius:5px; font-size:10px; font-weight:800;}
    .badge-notrade {background:#fee2e2; color:#991b1b; padding:4px 10px; border-radius:5px; font-size:10px; font-weight:800;}
    .alert-red {background:#fee2e2; border:1.5px solid #fca5a5; border-radius:10px; padding:12px; color:#7f1d1d;}
</style>
""", unsafe_allow_html=True)

# ==================== SESSION STATE ====================
if 'finnhub_key' not in st.session_state:
    st.session_state.finnhub_key = st.secrets.get("finnhub", {}).get("key", "")
if 'trades' not in st.session_state:
    st.session_state.trades = []
if 'leaps' not in st.session_state:
    st.session_state.leaps = []
if 'leap_fund' not in st.session_state:
    st.session_state.leap_fund = 0.0
if 'market_data' not in st.session_state:
    st.session_state.market_data = {}
if 'chart_data' not in st.session_state:
    st.session_state.chart_data = {}
if 'tickers' not in st.session_state:
    st.session_state.tickers = ["TSLL", "SOXL", "TQQQ"]  # Default from Matt's leveraged focus

VIX_LIMIT = 25
MOVE_PCT = 5
MAX_CALLS_PER_MIN = 50  # Safe free-tier limit

# ==================== FINNHUB HELPERS WITH RATE LIMIT ====================
def fetch_quote(sym):
    if not st.session_state.finnhub_key:
        return None
    try:
        r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={st.session_state.finnhub_key}", timeout=10)
        return r.json() if r.ok else None
    except:
        return None

def fetch_candles(sym):
    if not st.session_state.finnhub_key:
        return None
    try:
        to_ts = int(time.time())
        from_ts = to_ts - (40 * 86400)
        r = requests.get(
            f"https://finnhub.io/api/v1/stock/candle?symbol={sym}&resolution=D&from={from_ts}&to={to_ts}&token={st.session_state.finnhub_key}",
            timeout=10
        )
        data = r.json()
        if data.get("s") == "ok":
            df = pd.DataFrame({
                "time": pd.to_datetime(data["t"], unit="s").dt.strftime("%Y-%m-%d"),
                "open": data["o"], "high": data["h"], "low": data["l"], "close": data["c"]
            })
            return df
    except:
        pass
    return None

def calc_rv(df):
    if df is None or len(df) < 5:
        return None
    returns = df["close"].pct_change().dropna()
    rv = returns.std() * (252 ** 0.5) * 100
    return round(rv, 1)

def estimate_options(price, strike_call, strike_put, dte, rv):
    iv = rv if rv else 85.0
    iv_val = iv / 100.0
    t = max(dte, 1) / 365.0
    sqrt_t = t ** 0.5
    atm_prem = iv_val * sqrt_t * price * 0.3989
    call_otm = max(0.05, 1 - abs(strike_call - price) / price * 0.75)
    put_otm = max(0.05, 1 - abs(strike_put - price) / price * 0.75)
    call_mid = max(0.01, atm_prem * call_otm)
    put_mid = max(0.01, atm_prem * put_otm)
    spread = max(0.02, call_mid * 0.12)
    return {
        "call_mid": round(call_mid, 2),
        "call_bid": round(call_mid - spread/2, 2),
        "call_ask": round(call_mid + spread/2, 2),
        "put_mid": round(put_mid, 2),
        "put_bid": round(put_mid - spread/2, 2),
        "put_ask": round(put_mid + spread/2, 2),
        "call_pct": round((call_mid / price) * 100, 1),
        "put_pct": round((put_mid / price) * 100, 1),
        "iv_used": round(iv)
    }

def next_expiry():
    target = datetime.now() + timedelta(days=30)
    d = datetime(target.year, target.month, 1)
    fridays = []
    while d.month == target.month:
        if d.weekday() == 4:
            fridays.append(d)
        d += timedelta(days=1)
    if len(fridays) >= 3:
        return fridays[2]
    d = datetime(target.year, target.month + 1, 1)
    fridays = []
    while len(fridays) < 3:
        if d.weekday() == 4:
            fridays.append(d)
        d += timedelta(days=1)
    return fridays[2] if fridays else target + timedelta(days=30)

# Safe batch update respecting 50 calls/min
def safe_batch_update(tickers_to_update):
    updated = 0
    for sym in tickers_to_update:
        if updated >= MAX_CALLS_PER_MIN:
            st.warning(f"Reached safe limit ({MAX_CALLS_PER_MIN}/min). Remaining updates will run next minute.")
            break
        q = fetch_quote(sym)
        if q and q.get("c"):
            df_candles = fetch_candles(sym)
            rv = calc_rv(df_candles)
            st.session_state.market_data[sym] = {
                "price": round(q["c"], 2),
                "change": round(q.get("dp", 0), 2),
                "rv": rv
            }
            updated += 2  # quote + candles count as 2 calls
        time.sleep(1.2)  # extra safety spacing

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("◈ WheelOS")
    st.caption("CSP Income + LEAP Growth (Matt Style)")
    if not st.session_state.finnhub_key:
        key = st.text_input("Finnhub API Key", type="password")
        if st.button("Save Key"):
            st.session_state.finnhub_key = key
            st.success("Key saved!")
            st.rerun()
    else:
        st.success("Finnhub connected")
        if st.button("Reset Key"):
            st.session_state.finnhub_key = ""
            st.rerun()

# ==================== TABS ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Dashboard", "🔁 Trades", "🚀 LEAPs", "📈 Chart", "⚙️ Settings"])

with tab1:  # Dashboard
    st.subheader("Matt’s Profit Recycling Loop")
    st.info("CSPs on red days → 50% profit close → 50% income, 50% to LEAP fund (house money). Minimal screen time (15 min/week).")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("LEAP Fund", f"${st.session_state.leap_fund:,.0f}")
    with col2:
        closed = [t for t in st.session_state.trades if t.get("status") == "closed"]
        st.metric("Realized CSP P&L", f"${sum(t.get('pnl',0) for t in closed):,.0f}")

    if st.button("🔄 Safe Refresh (≤50 calls/min)"):
        safe_batch_update(st.session_state.tickers)
        st.success("Batch update completed safely")
        st.rerun()

    if st.session_state.market_data:
        df = pd.DataFrame.from_dict(st.session_state.market_data, orient="index")
        st.dataframe(df, use_container_width=True)

with tab2:  # Trades
    st.subheader("CSP Trades • Red Day + 50% Rule")
    ticker = st.selectbox("Ticker", st.session_state.tickers)
    if st.button("Log New CSP"):
        q = st.session_state.market_data.get(ticker, {})
        price = q.get("price", 450)
        rv = q.get("rv")
        strike = round(price * 0.90)
        premium = estimate_options(price, price*1.10, price*0.90, 30, rv)["put_mid"]
        st.session_state.trades.append({
            "id": int(time.time()),
            "type": "CSP",
            "ticker": ticker,
            "strike": strike,
            "expiry": next_expiry().strftime("%Y-%m-%d"),
            "premium": premium,
            "status": "open",
            "pnl": 0,
            "entry_date": datetime.now().strftime("%Y-%m-%d")
        })
        st.success(f"CSP on {ticker} logged")
        st.rerun()

    for t in st.session_state.trades:
        if t["status"] == "open":
            with st.expander(f"{t['ticker']} CSP @ ${t['strike']}"):
                st.write(f"Premium: ${t['premium']} | Exp: {t['expiry']}")
                if st.button("Close at 50%", key=t["id"]):
                    profit = round(t["premium"] * 0.5, 2)
                    t["pnl"] = profit
                    t["status"] = "closed"
                    st.session_state.leap_fund += profit * 0.5
                    st.success(f"Closed! ${profit} profit → ${profit*0.5:.0f} to LEAP fund")
                    st.rerun()

with tab3:  # LEAPs
    st.subheader("LEAPs • House Money Only (Matt Style)")
    st.metric("LEAP Fund Available", f"${st.session_state.leap_fund:,.0f}")
    ticker = st.selectbox("LEAP Ticker", st.session_state.tickers, key="leap_ticker")
    if st.button("Buy LEAP (from fund)"):
        if st.session_state.leap_fund >= 1000:
            st.session_state.leaps.append({"id": int(time.time()), "ticker": ticker, "cost": 1200, "current_val": 1200, "contracts": 1})
            st.session_state.leap_fund -= 1200
            st.success("LEAP purchased with recycled profits")
            st.rerun()
        else:
            st.error("Not enough LEAP fund")

    for l in st.session_state.leaps:
        with st.expander(f"{l['ticker']} LEAP"):
            st.write(f"Cost: ${l['cost']} | Current: ${l['current_val']}")
            if st.button("Sell Half & Recycle", key=l["id"]):
                st.session_state.leap_fund += l["cost"] * 0.8
                l["contracts"] = max(0, l["contracts"] - 1)
                st.success("Half sold • Profits recycled")
                st.rerun()

with tab4:  # Chart
    st.subheader("Interactive Candlestick Chart")
    ticker = st.selectbox("Ticker", st.session_state.tickers, key="chart_sel")
    if st.button("Load Candles"):
        df = fetch_candles(ticker)
        if df is not None:
            st.session_state.chart_data[ticker] = df
            st.success(f"Loaded {len(df)} days")
    if ticker in st.session_state.chart_data:
        df = st.session_state.chart_data[ticker]
        chart_data = []
        for _, row in df.iterrows():
            chart_data.append({
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"])
            })
        renderLightweightCharts([{"series": [{"type": "candlestick", "data": chart_data}], "options": {"height": 420}}], key=f"lc_{ticker}")

with tab5:  # Settings
    st.subheader("⚙️ Settings – Manage Tickers")
    st.write("**Current Watched Tickers** (max recommended: 3–5 for free tier)")
    for t in st.session_state.tickers:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"• {t}")
        with col2:
            if st.button("Remove", key=f"rem_{t}"):
                if len(st.session_state.tickers) > 1:
                    st.session_state.tickers.remove(t)
                    st.success(f"Removed {t}")
                    st.rerun()
                else:
                    st.error("Keep at least one ticker")

    st.divider()
    st.write("**Add New Ticker**")
    new_t = st.text_input("Ticker Symbol (e.g. NVDA, AAPL)").upper().strip()
    if st.button("Add Ticker"):
        if new_t and new_t not in st.session_state.tickers:
            q = fetch_quote(new_t)
            if q and q.get("c"):
                st.session_state.tickers.append(new_t)
                st.success(f"Added {new_t}")
                st.rerun()
            else:
                st.error("Ticker not found or no data")
        elif new_t in st.session_state.tickers:
            st.warning("Already watching this ticker")
        else:
            st.error("Enter a ticker")

    st.caption("Free tier safe: ≤50 calls/min. More tickers = slower batch updates.")

# Global safe refresh
if st.button("🔄 Safe Full Refresh (≤50 calls/min)"):
    safe_batch_update(st.session_state.tickers)
    st.success("Safe batch update completed")
    st.rerun()

st.caption("WheelOS • CSP Income + LEAP Growth via Profit Recycling (Matt @MarketMovesMatt style)")
