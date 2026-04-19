import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_lightweight_charts import render_lightweight_charts

st.set_page_config(page_title="Options Radar", page_icon="📈", layout="wide")

# Light clean theme
st.markdown("""
<style>
    .main {background-color: #f0f4f8;}
    .stButton>button {border-radius: 10px; font-weight: 700;}
    .metric-label {font-size: 10px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; color: #94a3b8;}
    .badge-call {background:#fef3c7; color:#92400e; padding:4px 10px; border-radius:5px; font-size:10px; font-weight:800;}
    .badge-put {background:#d1fae5; color:#065f46; padding:4px 10px; border-radius:5px; font-size:10px; font-weight:800;}
    .badge-wait {background:#f1f5f9; color:#64748b; padding:4px 10px; border-radius:5px; font-size:10px; font-weight:800;}
    .badge-notrade {background:#fee2e2; color:#991b1b; padding:4px 10px; border-radius:5px; font-size:10px; font-weight:800;}
</style>
""", unsafe_allow_html=True)

# Session State
if 'finnhub_key' not in st.session_state:
    st.session_state.finnhub_key = st.secrets.get("finnhub", {}).get("key", "")
if 'trades' not in st.session_state:
    st.session_state.trades = []
if 'market_data' not in st.session_state:
    st.session_state.market_data = {}
if 'chart_data' not in st.session_state:
    st.session_state.chart_data = {}
if 'vix' not in st.session_state:
    st.session_state.vix = None

TICKERS = ["TSLL", "SOXL", "TQQQ"]
VIX_LIMIT = 25
MOVE_PCT = 5

# ==================== HELPERS ====================
def fetch_quote(sym):
    if not st.session_state.finnhub_key:
        return None
    try:
        r = requests.get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={st.session_state.finnhub_key}", timeout=10)
        if r.ok:
            return r.json()
    except:
        pass
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
    iv = rv if rv else 85
    iv_val = iv / 100
    t = max(dte, 1) / 365
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
    # Find 3rd Friday
    d = datetime(target.year, target.month, 1)
    fridays = []
    while d.month == target.month:
        if d.weekday() == 4:  # Friday
            fridays.append(d)
        d += timedelta(days=1)
    if len(fridays) >= 3:
        return fridays[2]
    # Next month
    d = datetime(target.year, target.month + 1, 1)
    fridays = []
    while d.month == target.month + 1 or (target.month == 12 and d.month == 1):
        if d.weekday() == 4:
            fridays.append(d)
        d += timedelta(days=1)
    return fridays[2] if fridays else target + timedelta(days=30)

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("📈 Options Radar")
    st.caption("Leveraged ETF Options • 30DTE Seller")
    if not st.session_state.finnhub_key:
        key = st.text_input("Finnhub API Key", type="password", help="Free at finnhub.io")
        if st.button("Save Key"):
            st.session_state.finnhub_key = key
            st.success("Key saved for this session")
            st.rerun()
    else:
        st.success("Finnhub connected")
        if st.button("Reset Key"):
            st.session_state.finnhub_key = ""
            st.rerun()

# ==================== TABS ====================
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🔁 Trades", "📈 Chart", "📅 Calendar"])

with tab1:  # Dashboard
    st.subheader("Market Status")
    if st.button("Refresh Live Data"):
        for sym in TICKERS:
            q = fetch_quote(sym)
            if q and q.get("c"):
                rv = calc_rv(fetch_candles(sym))
                st.session_state.market_data[sym] = {
                    "price": round(q["c"], 2),
                    "change": round(q.get("dp", 0), 2),
                    "rv": rv
                }
        st.success("Data refreshed")

    if st.session_state.market_data:
        df = pd.DataFrame.from_dict(st.session_state.market_data, orient="index")
        st.dataframe(df, use_container_width=True)

    vix = st.session_state.get("vix")
    if vix:
        st.metric("VIX", vix, delta=None, delta_color="normal" if float(vix) < VIX_LIMIT else "inverse")

with tab2:  # Trades
    st.subheader("Trade Signals & Logging")
    for ticker in TICKERS:
        d = st.session_state.market_data.get(ticker, {})
        price = d.get("price")
        rv = d.get("rv")
        if not price:
            continue

        chg = d.get("change", 0)
        signal = "NO TRADE"
        badge_class = "badge-notrade"
        if float(vix or 0) >= VIX_LIMIT:
            signal = "NO TRADE (VIX HIGH)"
        elif abs(chg) >= MOVE_PCT:
            if chg >= MOVE_PCT:
                signal = "SELL CALL"
                badge_class = "badge-call"
            else:
                signal = "SELL PUT"
                badge_class = "badge-put"
        else:
            signal = "WAIT"
            badge_class = "badge-wait"

        with st.expander(f"{ticker} — {signal}"):
            st.write(f"Price: ${price} | Change: {chg}% | RV: {rv}%")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Log Call", key=f"call_{ticker}"):
                    expiry = next_expiry()
                    opts = estimate_options(price, price*1.10, price*0.90, 30, rv)
                    st.session_state.trades.append({
                        "id": int(time.time()),
                        "ticker": ticker,
                        "type": "call",
                        "strike": round(price*1.10, 2),
                        "expiry": expiry.strftime("%Y-%m-%d"),
                        "entry_premium": opts["call_mid"],
                        "status": "open"
                    })
                    st.success("Call trade logged")
                    st.rerun()
            with col2:
                if st.button("Log Put", key=f"put_{ticker}"):
                    expiry = next_expiry()
                    opts = estimate_options(price, price*1.10, price*0.90, 30, rv)
                    st.session_state.trades.append({
                        "id": int(time.time()),
                        "ticker": ticker,
                        "type": "put",
                        "strike": round(price*0.90, 2),
                        "expiry": expiry.strftime("%Y-%m-%d"),
                        "entry_premium": opts["put_mid"],
                        "status": "open"
                    })
                    st.success("Put trade logged")
                    st.rerun()

    st.subheader("Open Trades")
    for trade in st.session_state.trades:
        if trade.get("status") == "open":
            with st.expander(f"{trade['ticker']} {trade['type'].upper()} @ ${trade['strike']}"):
                st.write(f"Entry Premium: ${trade.get('entry_premium', '—')}")
                if st.button("Mark Closed (50% target)", key=trade["id"]):
                    trade["status"] = "closed"
                    st.success("Trade closed at target")
                    st.rerun()

with tab3:  # Chart
    st.subheader("Candlestick Chart")
    ticker = st.selectbox("Ticker", TICKERS, key="chart_ticker")
    if st.button("Load Candles"):
        df = fetch_candles(ticker)
        if df is not None:
            st.session_state.chart_data[ticker] = df
            st.success(f"Loaded {len(df)} days")

    if ticker in st.session_state.chart_data:
        df = st.session_state.chart_data[ticker]
        # Convert to Lightweight Charts format
        chart_data = []
        for _, row in df.iterrows():
            chart_data.append({
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"])
            })
        render_lightweight_charts([{
            "series": [{"type": "candlestick", "data": chart_data}],
            "options": {"height": 420}
        }], key=f"lc_{ticker}")

with tab4:  # Calendar
    st.subheader("Event Calendar (No-Trade Days)")
    st.info("Avoid new trades on high VIX or major events (FOMC, CPI, Rate decisions)")

# Refresh button
if st.button("Refresh All"):
    for sym in TICKERS:
        q = fetch_quote(sym)
        if q and q.get("c"):
            rv = calc_rv(fetch_candles(sym))
            st.session_state.market_data[sym] = {"price": round(q["c"],2), "change": round(q.get("dp",0),2), "rv": rv}
    st.rerun()

st.caption("Options Radar • Powered by Finnhub + Lightweight Charts")