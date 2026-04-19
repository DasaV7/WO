import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

# Page config
st.set_page_config(
    page_title="WheelOS • CSP + LEAPs",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for clean Apple-like light theme
st.markdown("""
<style>
    .main { background-color: #FAFAFA; }
    .stButton>button { border-radius: 9999px; font-weight: 700; }
    .metric-label { font-size: 13px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; color: #86868B; }
    .green { color: #34C759; }
    .red { color: #FF3B30; }
    .gold { color: #FF9500; }
</style>
""", unsafe_allow_html=True)

# ==================== SESSION STATE ====================
if 'finnhub_key' not in st.session_state:
    st.session_state.finnhub_key = ""
if 'trades' not in st.session_state:
    st.session_state.trades = []
if 'leaps' not in st.session_state:
    st.session_state.leaps = []
if 'leap_fund' not in st.session_state:
    st.session_state.leap_fund = 0.0
if 'market_data' not in st.session_state:
    st.session_state.market_data = {}

# ==================== SIDEBAR SETUP ====================
with st.sidebar:
    st.title("◈ WheelOS")
    st.caption("CSP Income + LEAP Growth • Matt Style")

    if not st.session_state.finnhub_key:
        st.warning("Enter Finnhub API Key to enable live data")
        key = st.text_input("Finnhub API Key", type="password", help="Get free key at finnhub.io")
        if st.button("Save Key"):
            st.session_state.finnhub_key = key
            st.success("Key saved!")
            st.rerun()
    else:
        st.success("✓ Finnhub connected")
        if st.button("Reset Key"):
            st.session_state.finnhub_key = ""
            st.rerun()

    st.divider()
    st.caption("Strategy: Sell CSP on red days (IV>50%, 30 DTE) → 50% profit rule → Recycle half to LEAPs")

# ==================== FINNHUB HELPERS ====================
def fetch_quote(symbol):
    if not st.session_state.finnhub_key:
        return None
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={st.session_state.finnhub_key}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def load_market_data():
    tickers = ["QQQ", "SPY", "TQQQ", "SOXL"]
    data = {}
    for sym in tickers:
        q = fetch_quote(sym)
        if q and q.get("c"):
            data[sym] = {
                "price": round(q["c"], 2),
                "change": round(q.get("dp", 0), 2)
            }
    st.session_state.market_data = data

# ==================== MAIN APP ====================
st.title("WheelOS • Cash-Secured Puts + LEAPs")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🔁 Trades (CSP + Wheel)", "🚀 LEAPs", "📈 Chart"])

with tab1:  # Dashboard
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("LEAP Fund (50% recycled)", f"${st.session_state.leap_fund:,.0f}")
    with col2:
        closed_trades = [t for t in st.session_state.trades if t.get("status") == "closed"]
        total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
        st.metric("Realized CSP P&L", f"${total_pnl:,.0f}")
    with col3:
        open_trades = len([t for t in st.session_state.trades if t.get("status") == "open"])
        st.metric("Open Positions", open_trades)

    st.subheader("Profit Recycling Loop")
    st.info("Red day → Sell CSP → Close at 50% profit → 50% income, 50% to LEAP fund → Compound growth")

    if st.button("Refresh Live Data"):
        load_market_data()
        st.success("Market data updated")

    st.subheader("Live Snapshot")
    if st.session_state.market_data:
        df = pd.DataFrame.from_dict(st.session_state.market_data, orient="index")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Enter Finnhub key in sidebar and refresh data")

with tab2:  # Trades
    st.subheader("CSP Trades • 50% Profit Rule + Wheel")

    col_a, col_b = st.columns(2)
    with col_a:
        ticker = st.selectbox("Ticker", ["QQQ", "TQQQ", "SOXL", "SPY"])
        if st.button("Log New CSP"):
            price = st.session_state.market_data.get(ticker, {}).get("price", 450)
            strike = round(price * 0.90)
            premium = round(price * 0.028, 2)
            st.session_state.trades.append({
                "id": int(time.time()),
                "type": "CSP",
                "ticker": ticker,
                "strike": strike,
                "expiry": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                "premium": premium,
                "status": "open",
                "pnl": 0,
                "entry_date": datetime.now().strftime("%Y-%m-%d")
            })
            st.success(f"CSP logged on {ticker}")
            st.rerun()

    with col_b:
        if st.button("Refresh Market"):
            load_market_data()

    # Display trades
    if st.session_state.trades:
        for trade in st.session_state.trades[:]:
            with st.expander(f"{trade['ticker']} {trade['type']} @ ${trade['strike']} | {trade['status'].upper()}"):
                st.write(f"Premium: ${trade['premium']} | Entry: {trade['entry_date']}")
                if trade["status"] == "open":
                    if st.button("Close at 50% Profit", key=trade["id"]):
                        profit = round(trade["premium"] * 0.5, 2)
                        trade["pnl"] = profit
                        trade["status"] = "closed"
                        st.session_state.leap_fund += profit * 0.5   # 50% recycling
                        st.success(f"Closed with ${profit} profit • ${profit*0.5:.0f} recycled to LEAP fund")
                        st.rerun()
    else:
        st.info("No trades yet. Log a CSP above.")

with tab3:  # LEAPs
    st.subheader("LEAPs • Funded by CSP Profits Only")

    st.metric("Available LEAP Fund", f"${st.session_state.leap_fund:,.0f}")

    col_leap = st.columns(2)
    with col_leap[0]:
        leap_ticker = st.selectbox("LEAP Ticker", ["QQQ", "NVDA", "TQQQ"], key="leap_ticker")
        if st.button("Buy LEAP (from fund)"):
            if st.session_state.leap_fund >= 1000:
                st.session_state.leaps.append({
                    "id": int(time.time()),
                    "ticker": leap_ticker,
                    "strike": 999,  # placeholder
                    "expiry": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"),
                    "cost": 1200,
                    "current_val": 1200,
                    "contracts": 1
                })
                st.session_state.leap_fund -= 1200
                st.success("LEAP purchased with house money")
                st.rerun()
            else:
                st.error("Not enough LEAP fund")

    with col_leap[1]:
        if st.session_state.leaps:
            for leap in st.session_state.leaps:
                with st.expander(f"{leap['ticker']} LEAP"):
                    st.write(f"Cost: ${leap['cost']} | Current: ${leap['current_val']}")
                    if st.button("Sell Half & Recycle", key=leap["id"]):
                        st.session_state.leap_fund += leap["cost"] * 0.8
                        leap["contracts"] = max(0, leap["contracts"] - 1)
                        st.success("Half sold • Profits recycled")
                        st.rerun()

with tab4:  # Chart
    st.subheader("Price Chart")
    st.info("Using Lightweight Charts via Streamlit component (demo data shown)")

    # For real chart you can install streamlit-lightweight-charts
    # pip install streamlit-lightweight-charts
    # Then use it here for full candlestick support

    # Simple placeholder for now
    st.line_chart(pd.DataFrame({
        "QQQ": [480, 492, 505, 518, 525],
        "TQQQ": [45, 48, 52, 55, 58]
    }))

# Auto-refresh button
if st.button("🔄 Refresh All Data"):
    load_market_data()
    st.rerun()

# Footer
st.caption("WheelOS v15 → Streamlit conversion | CSP Income + LEAP Growth Strategy")