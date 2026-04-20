import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_lightweight_charts import renderLightweightCharts

st.set_page_config(page_title="WheelOS • Options Radar", page_icon="◈", layout="wide")

# Apple minimalist light theme
st.markdown("""
<style>
    .main {background-color: #FAFAFA;}
    .block-container {padding-top: 2rem;}
    
    /* Soft cards - no sharp borders */
    .stCard, div[data-testid="stExpander"] {
        background-color: #FFFFFF;
        border-radius: 18px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
        border: 1px solid rgba(0,0,0,0.06);
    }
    
    /* Gradient buttons with smooth effects */
    .stButton>button {
        background: linear-gradient(135deg, #0071E3, #4A9EFF);
        color: white;
        border-radius: 9999px;
        font-weight: 700;
        border: none;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 14px rgba(0,113,227,0.3);
    }
    .stButton>button:hover {
        transform: scale(1.03);
        box-shadow: 0 8px 20px rgba(0,113,227,0.35);
        filter: brightness(1.08);
    }
    
    .metric-label {font-size:13px; font-weight:600; letter-spacing:0.8px; text-transform:uppercase; color:#86868B;}
    .green {color:#34C759;}
    .red {color:#FF3B30;}
    .gold {color:#FF9500;}
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
    st.session_state.tickers = ["TSLL", "SOXL", "TQQQ"]
if 'capital' not in st.session_state:
    st.session_state.capital = 20000
if 'journal' not in st.session_state:
    st.session_state.journal = []

VIX_LIMIT = 25
MOVE_PCT = 5
MAX_CALLS_PER_MIN = 50

MAIN_TICKER_MAP = {"TQQQ": "QQQ", "SOXL": "SOXX", "TSLL": "TSLA", "QQQ": "QQQ", "SPY": "SPY"}

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
            return pd.DataFrame({
                "time": pd.to_datetime(data["t"], unit="s").dt.strftime("%Y-%m-%d"),
                "open": data["o"], "high": data["h"], "low": data["l"], "close": data["c"]
            })
    except: pass
    return None

def calc_rv(df):
    if df is None or len(df) < 5: return None
    returns = df["close"].pct_change().dropna()
    return round(returns.std() * (252 ** 0.5) * 100, 1)

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
        "put_pct": round((put_mid / price) * 100, 1)
    }

def next_expiry(days=30):
    target = datetime.now() + timedelta(days=days)
    d = datetime(target.year, target.month, 1)
    fridays = []
    while d.month == target.month:
        if d.weekday() == 4: fridays.append(d)
        d += timedelta(days=1)
    if len(fridays) >= 3: return fridays[2]
    return target + timedelta(days=30)

def safe_batch_update(tickers):
    updated = 0
    for sym in tickers:
        if updated >= MAX_CALLS_PER_MIN:
            st.warning(f"Reached safe limit ({MAX_CALLS_PER_MIN}/min). Remaining updates will run next minute.")
            break
        q = fetch_quote(sym)
        if q and q.get("c"):
            df = fetch_candles(sym)
            rv = calc_rv(df)
            st.session_state.market_data[sym] = {
                "price": round(q["c"], 2),
                "change": round(q.get("dp", 0), 2),
                "rv": rv
            }
            updated += 2
        time.sleep(1.2)

# ==================== FULL SCREEN SETUP ====================
if not st.session_state.finnhub_key:
    st.title("Welcome to WheelOS")
    st.markdown("### First Time Setup")
    st.info("Get your free Finnhub API key at [finnhub.io](https://finnhub.io) → Dashboard → API Key")
    key = st.text_input("Paste your Finnhub API Key", type="password")
    if st.button("Save & Launch App", type="primary"):
        if key.strip():
            st.session_state.finnhub_key = key.strip()
            st.success("Key saved! Loading app...")
            st.rerun()
        else:
            st.error("Please enter a valid key")
    st.stop()

# Sidebar
with st.sidebar:
    st.title("◈ WheelOS")
    st.success("Finnhub connected")
    if st.button("Reset Finnhub Key"):
        st.session_state.finnhub_key = ""
        st.rerun()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Dashboard", "🔁 CSP Trades", "🚀 LEAP Trades", "📈 Super Chart", "📅 Calendar", "⚙️ Settings"])

with tab1:  # Revamped Dashboard
    st.subheader("Matt’s Profit Recycling Loop")
    st.info("CSP on red days → Close at 50% → 50% income, 50% to LEAP fund (house money only)")

    col1, col2, col3, col4 = st.columns(4)
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

    # Graduation Levels
    st.subheader("Graduation Progress")
    level = 1
    if total_pnl >= 1000: level = 2
    if st.session_state.leap_fund > 0: level = 3
    if len(closed) >= 5: level = 4
    st.progress(level/4)
    st.caption(f"Level {level}/4 • Next milestone: ${5000 if level < 2 else 50000 if level < 3 else 100000} account")

    if st.button("🔄 Safe Refresh (≤50 calls/min)"):
        safe_batch_update(st.session_state.tickers)
        st.success("Batch update completed safely")
        st.rerun()

    if st.session_state.market_data:
        st.dataframe(pd.DataFrame.from_dict(st.session_state.market_data, orient="index"), use_container_width=True)

with tab2:  # CSP Trades
    st.subheader("CSP Trades • Red Day Sell Put / Green Day Sell Call")
    for ticker in st.session_state.tickers:
        d = st.session_state.market_data.get(ticker, {})
        price = d.get("price")
        rv = d.get("rv")
        if not price: continue

        chg = d.get("change", 0)
        signal = "NO TRADE"
        if float(st.session_state.get("vix") or 0) >= VIX_LIMIT:
            signal = "NO TRADE (VIX HIGH)"
        elif chg <= -MOVE_PCT:
            signal = "SELL PUT (Red Day >5%)"
        elif chg >= MOVE_PCT:
            signal = "SELL CALL (Green Day >5%)"

        with st.expander(f"{ticker} — **{signal}**"):
            st.write(f"Price: **${price}** | Change: **{chg}%** | RV: **{rv if rv else 'Not loaded yet'}**")
            if not rv:
                st.warning("RV data not loaded yet – trading based on price action only")

            if chg <= -MOVE_PCT:
                if st.button("Log Sell Put", key=f"put_{ticker}"):
                    expiry = next_expiry()
                    opts = estimate_options(price, price*1.10, price*0.90, 30, rv)
                    st.session_state.trades.append({
                        "id": int(time.time()), "type":"CSP Put", "ticker":ticker, "strike":round(price*0.90,2),
                        "expiry":expiry.strftime("%Y-%m-%d"), "entry_premium":opts["put_mid"], "status":"open", "pnl":0
                    })
                    st.success("Sell Put logged")
                    st.rerun()

            if chg >= MOVE_PCT:
                if st.button("Log Sell Call", key=f"call_{ticker}"):
                    expiry = next_expiry()
                    opts = estimate_options(price, price*1.10, price*0.90, 30, rv)
                    st.session_state.trades.append({
                        "id": int(time.time()), "type":"CSP Call", "ticker":ticker, "strike":round(price*1.10,2),
                        "expiry":expiry.strftime("%Y-%m-%d"), "entry_premium":opts["call_mid"], "status":"open", "pnl":0
                    })
                    st.success("Sell Call logged")
                    st.rerun()

    st.subheader("Open CSP Trades")
    for t in st.session_state.trades:
        if t.get("status") == "open":
            with st.expander(f"{t['ticker']} {t['type']} @ ${t['strike']}"):
                st.write(f"Entry Premium: ${t.get('entry_premium','—')}")
                if st.button("Close at 50% Profit", key=t["id"]):
                    profit = round(t["entry_premium"] * 0.5, 2)
                    t["pnl"] = profit
                    t["status"] = "closed"
                    t["closed_date"] = datetime.now().strftime("%Y-%m-%d")
                    st.session_state.leap_fund += profit * 0.5
                    
                    st.session_state.journal.append({
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "ticker": t["ticker"],
                        "type": t["type"],
                        "action": "Closed at 50%",
                        "profit": profit,
                        "note": "Profit recycled to LEAP fund"
                    })
                    
                    st.success(f"Closed! ${profit} profit → ${profit*0.5:.0f} added to House Money")
                    st.rerun()

with tab3:  # LEAP Trades
    st.subheader("LEAP Calls • House Money Only")
    st.metric("House Money Available", f"${st.session_state.leap_fund:,.0f}")
    leap_ticker = st.selectbox("LEAP Ticker", st.session_state.tickers, key="leap_sel")
    if st.button("Add LEAP (360+ DTE)"):
        if st.session_state.leap_fund >= 1000:
            st.session_state.leaps.append({
                "id": int(time.time()), "ticker": leap_ticker, "cost": 1200, "current_val": 1200, "contracts": 1,
                "expiry": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
            })
            st.session_state.leap_fund -= 1200
            st.success("LEAP added with house money")
            st.rerun()
        else:
            st.error("Not enough house money")

    st.subheader("Your LEAP Positions")
    for l in st.session_state.leaps:
        with st.expander(f"{l['ticker']} LEAP"):
            st.write(f"Cost: ${l['cost']} | Current: ${l['current_val']} | Expiry: {l['expiry']}")
            profit_pct = ((l['current_val'] - l['cost']) / l['cost']) * 100
            if profit_pct > 100:
                st.success("🎯 >100% profit – Consider selling!")
            if st.button("Sell Half & Recycle", key=l["id"]):
                st.session_state.leap_fund += l["cost"] * 0.8
                l["contracts"] = max(0, l["contracts"] - 1)
                st.success("Half sold • Profits added to House Money")
                st.rerun()

with tab4:  # Super Chart with RSI
    st.subheader("TradingView Super Chart + RSI")
    ticker = st.selectbox("Select Leveraged Ticker", st.session_state.tickers, key="superchart_ticker")
    main_ticker = MAIN_TICKER_MAP.get(ticker, ticker)

    st.write(f"**Showing:** {ticker} (with Volume + RSI) + **{main_ticker}** (overlay)")

    tv_html = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_{ticker}"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "width": "100%",
        "height": 650,
        "symbol": "{ticker}",
        "interval": "D",
        "timezone": "Etc/UTC",
        "theme": "light",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_{ticker}",
        "studies": ["Volume@tv-basicstudies", "RSI@tv-basicstudies"],
        "show_volume": true,
        "overrides": {{ "mainSeriesProperties.showPriceLine": true }},
        "comparisons": [{{"symbol": "{main_ticker}"}}]
      }});
      </script>
    </div>
    """
    st.components.v1.html(tv_html, height=680, scrolling=True)

with tab5:  # Calendar
    st.subheader("📅 Upcoming Economic Events")
    st.info("Avoid new trades on high VIX (≥25) or major events")

with tab6:  # Settings
    st.subheader("⚙️ Settings")
    st.write("**Investment Capital**")
    capital_options = [10000, 20000, 30000, 50000, 100000]
    selected = st.selectbox("Select starting capital", capital_options, index=1)
    manual = st.number_input("Or enter custom amount", min_value=5000, value=st.session_state.capital, step=1000)
    if st.button("Save Capital"):
        st.session_state.capital = manual if manual != st.session_state.capital else selected
        st.success(f"Capital set to ${st.session_state.capital:,.0f}")

    st.divider()
    st.write("**House Money**")
    st.metric("Current House Money", f"${st.session_state.leap_fund:,.0f}")

    st.divider()
    st.write("**Journal Entries** (Closed Trades)")
    if st.session_state.journal:
        journal_df = pd.DataFrame(st.session_state.journal)
        st.dataframe(journal_df, use_container_width=True)
    else:
        st.info("No closed trades yet.")

    st.divider()
    st.write("**Watched Tickers**")
    for t in st.session_state.tickers:
        col1, col2 = st.columns([4,1])
        with col1: st.write(f"• {t}")
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
    new_t = st.text_input("Ticker Symbol").upper().strip()
    if st.button("Add Ticker"):
        if new_t and new_t not in st.session_state.tickers:
            q = fetch_quote(new_t)
            if q and q.get("c"):
                st.session_state.tickers.append(new_t)
                st.success(f"Added {new_t}")
                st.rerun()
            else:
                st.error("Ticker not found or no data")
        else:
            st.warning("Already watching or empty input")

# Auto-refresh every 15 minutes
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if time.time() - st.session_state.last_refresh > 900:
    safe_batch_update(st.session_state.tickers)
    st.session_state.last_refresh = time.time()

if st.button("🔄 Safe Full Refresh (≤50 calls/min)"):
    safe_batch_update(st.session_state.tickers)
    st.success("Safe batch update completed")
    st.rerun()

st.caption("WheelOS • Matt @MarketMovesMatt Strategy • CSP Income + LEAP Growth")
