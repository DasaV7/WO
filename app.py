import streamlit as st
import pandas as pd
import requests
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(page_title="WheelOS • Options Radar", page_icon="◈", layout="wide")

# iOS-style Apple minimalist theme
st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .metric-label { font-size: 0.9rem; color: #555; }
        
        /* iOS-style buttons */
        .stButton > button {
            border-radius: 12px !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1) !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
            height: 48px !important;
            font-weight: 500 !important;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
        }
        .stButton > button:active {
            transform: scale(0.96);
        }
        
        /* iOS-style selectboxes & inputs */
        .stSelectbox, .stTextInput > div > div > input {
            border-radius: 12px !important;
        }
        
        /* Colored expander headers */
        .red-expander { background-color: #ffebee !important; border-left: 6px solid #d32f2f; padding: 12px; border-radius: 12px; }
        .green-expander { background-color: #e8f5e9 !important; border-left: 6px solid #2e7d32; padding: 12px; border-radius: 12px; }
        .gray-expander { background-color: #f5f5f5 !important; border-left: 6px solid #9e9e9e; padding: 12px; border-radius: 12px; }
        
        .stExpander { border-radius: 12px !important; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

DATA_FILE = Path("wheelos_data.json")
KEY_FILE = Path("finnhub_key.json")

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

# Load API Key (persists forever)
if 'finnhub_key' not in st.session_state:
    st.session_state.finnhub_key = st.secrets.get("finnhub", {}).get("key", "")
    if not st.session_state.finnhub_key and KEY_FILE.exists():
        try:
            with open(KEY_FILE, "r") as f:
                saved = json.load(f)
                st.session_state.finnhub_key = saved.get("key", "")
        except:
            pass

# Session State
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

# Finnhub Helpers (unchanged)
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
                "open": data["o"], "high": data["h"], "low": data["l"], "close": data["c"],
                "volume": data.get("v", [0] * len(data["c"]))
            })
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
                "volume": volume
            }
            updated += 2
        time.sleep(1.2)

# First-time setup (unchanged)
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
                with open(KEY_FILE, "w") as f:
                    json.dump({"key": key.strip()}, f)
                st.success("Key saved!")
                st.rerun()
    with col2:
        if st.button("💾 Save Permanently"):
            if key.strip():
                st.session_state.finnhub_key = key.strip()
                with open(KEY_FILE, "w") as f:
                    json.dump({"key": key.strip()}, f)
                st.success("Key saved permanently")
                st.rerun()
    st.stop()

# Sidebar
with st.sidebar:
    st.title("◈ WheelOS")
    st.success("Finnhub connected")
    if st.button("Reset Finnhub Key"):
        st.session_state.finnhub_key = ""
        if KEY_FILE.exists():
            KEY_FILE.unlink()
        st.rerun()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Dashboard", "🔁 CSP / Wheel Trades", "🚀 LEAP Trades", "📈 Super Chart", "📅 Calendar", "⚙️ Settings"])

with tab1:
    # Dashboard (unchanged)
    st.subheader("Matt’s Profit Recycling Loop")
    st.info("CSP on red days → Close at 50% → 50% income, 50% to LEAP fund (house money only)")
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
        css_class = "gray-expander"
        button_type = "secondary"
        is_put = True

        if st.session_state.vix >= VIX_LIMIT:
            signal = f"NO TRADE (VIX HIGH ≥{VIX_LIMIT})"
        elif (rsi and rsi > 60) or (rv is not None and rv < 50):
            signal = "NO TRADE (RSI >60 or Low IV)"
        elif chg <= RED_THRESHOLD:
            signal = f"SELL CSP PUT (Red Day {chg:.1f}%)"
            css_class = "red-expander"
            button_type = "primary"
            is_put = True
        elif chg >= GREEN_THRESHOLD and has_held:
            signal = f"SELL COVERED CALL (Green Day {chg:.1f}%)"
            css_class = "green-expander"
            button_type = "primary"
            is_put = False

        # iOS-style colored header
        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        with st.expander(f"{ticker} — **{signal}**", expanded=False):
            st.markdown(f"<h4 style='margin:0; color:inherit'>{signal}</h4>", unsafe_allow_html=True)

            strike = round(price * (0.9 if is_put else 1.1), 2)
            premium = round(price * 0.04, 2)
            iv = rv or 85
            dte_val = 30
            expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            source = "Estimate"

            cols = st.columns([2,2,2,2])
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
            st.caption(f"**DTE:** {dte_val} days • Expiry: {expiry} • {source}")

            max_cash = st.session_state.capital * 0.25
            suggested_contracts = int(max_cash // (price * 100)) if price else 0
            st.caption(f"**Suggested size**: ~{suggested_contracts} contracts")

            if (chg <= RED_THRESHOLD or (chg >= GREEN_THRESHOLD and has_held)) and st.session_state.vix < VIX_LIMIT:
                btn_text = f"Log {'CSP Put' if is_put else 'Covered Call'} on {ticker}"
                if st.button(btn_text, key=f"trade_{ticker}_{'put' if is_put else 'call'}", type=button_type):
                    expiry_dt = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                    trade_type = "CSP Put" if is_put else "Covered Call"
                    st.session_state.trades.append({
                        "id": int(time.time()), "type": trade_type, "ticker": ticker,
                        "strike": strike, "expiry": expiry_dt, "entry_premium": premium,
                        "status": "open", "pnl": 0, "contracts": suggested_contracts
                    })
                    save_persistent_data()
                    st.success(f"{trade_type} logged")
                    st.rerun()
            else:
                st.button(f"Log {'CSP Put' if is_put else 'Covered Call'} on {ticker}", disabled=True, key=f"disabled_{ticker}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Open trades and held shares (unchanged)
    st.subheader("Open Wheel Trades")
    for t in st.session_state.trades:
        if t.get("status") == "open":
            with st.expander(f"{t['ticker']} {t['type']} @ ${t['strike']}"):
                st.write(f"Entry Premium: ${t.get('entry_premium','—')}")
                col_close, col_assign = st.columns(2)
                with col_close:
                    if st.button("Close at 50% Profit", key=f"close_{t['id']}"):
                        profit = round(t["entry_premium"] * 0.5, 2)
                        t["pnl"] = profit
                        t["status"] = "closed"
                        t["closed_date"] = datetime.now().strftime("%Y-%m-%d")
                        st.session_state.leap_fund += profit * 0.5
                        st.session_state.journal.append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "ticker": t["ticker"], "type": t["type"], "action": "Closed at 50%", "profit": profit, "note": "Profit recycled"})
                        save_persistent_data()
                        st.success(f"Closed! ${profit} → ${profit*0.5:.0f} to House Money")
                        st.rerun()
                with col_assign:
                    if t["type"] == "CSP Put":
                        if st.button("🔄 Simulate Assignment", key=f"assign_{t['id']}"):
                            shares = t.get("contracts", 1) * 100
                            cost_basis = t["strike"] - t["entry_premium"]
                            st.session_state.held_shares.append({"ticker": t["ticker"], "shares": shares, "cost_basis": round(cost_basis, 2), "entry_date": datetime.now().strftime("%Y-%m-%d")})
                            t["status"] = "assigned"
                            save_persistent_data()
                            st.success(f"Assigned! {shares} shares ready")
                            st.rerun()

    st.subheader("Held Shares")
    for idx, h in enumerate(st.session_state.held_shares):
        with st.expander(f"📌 {h['ticker']} – {h['shares']} shares"):
            if st.button("Simulate Call-Away", key=f"callaway_{idx}"):
                st.session_state.held_shares.pop(idx)
                save_persistent_data()
                st.success("Wheel complete!")
                st.rerun()

    # Options Matrix with profit % and color scale
    st.subheader("📊 Options Matrix (30 DTE) – P&L % Color Map")
    matrix_ticker = st.text_input("Enter any ticker (e.g. AAPL, NVDA, QQQ)", value="QQQ", key="matrix_input").upper().strip()
    if st.button("Load Options Matrix", type="primary"):
        price_data = fetch_quote(matrix_ticker)
        price = price_data["c"] if price_data and price_data.get("c") else 0
        if not price:
            st.error("Ticker not found")
            st.stop()

        rows = []
        source = "Estimated (Finnhub free-tier limitation)"

        options_raw = fetch_options_chain(matrix_ticker)
        if options_raw:
            # Try real data
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
                for c in chain:
                    strike = c['strike']
                    prem = round((c.get('bid',0) + c.get('ask',0))/2, 2)
                    iv = c.get('iv') or "—"
                    opt_type = "Put" if c.get('putCall') == 'P' else "Call"
                    pnl = prem if (opt_type == "Put" and price > strike) or (opt_type == "Call" and price < strike) else prem - abs(price - strike)
                    profit_pct = (pnl / price) * 100 if price else 0
                    rows.append({"Type": opt_type, "Strike": strike, "Premium": prem, "IV %": iv, "Profit %": round(profit_pct, 1)})
                source = "✅ REAL Finnhub chain"

        if not rows:
            # Synthetic matrix with -10% ITM, ATM, +10% OTM for puts & calls
            for pct in [0.90, 1.00, 1.10]:
                strike = round(price * pct, 2)
                is_call = pct > 1.0
                prem = round(price * 0.04, 2)
                pnl = prem if (is_call and price < strike) or (not is_call and price > strike) else prem - abs(price - strike)
                profit_pct = (pnl / price) * 100 if price else 0
                rows.append({"Type": "Call" if is_call else "Put", "Strike": strike, "Premium": prem, "IV %": "—", "Profit %": round(profit_pct, 1)})

        df_matrix = pd.DataFrame(rows).sort_values("Strike")
        def color_profit(val):
            if val > 2: return 'background-color: #2e7d32; color: white'
            if val > 0: return 'background-color: #81c784; color: white'
            if val == 0: return 'background-color: #f5f5f5'
            return 'background-color: #ef5350; color: white'
        styled = df_matrix.style.map(color_profit, subset=['Profit %'])
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.caption(f"Source: {source} • Profit % assumes stock price unchanged at 30 DTE • Green = OTM profit • Red = ITM loss")

# LEAP tab, Super Chart, Settings, etc. (unchanged from previous stable version)
with tab3:
    st.subheader("🚀 LEAP Calls • Any Ticker (360+ DTE)")
    leap_ticker_input = st.text_input("Enter any ticker for LEAP (e.g. NVDA, AAPL, QQQ)", value="QQQ", key="leap_input").upper().strip()
    if st.button("Load LEAP Data (360+ DTE)"):
        price_data = fetch_quote(leap_ticker_input)
        price = price_data["c"] if price_data and price_data.get("c") else 0
        if not price:
            st.error("Ticker not found")
            st.stop()

        options_raw = fetch_options_chain(leap_ticker_input)
        leap_rsi = calc_rsi(fetch_candles(leap_ticker_input))
        if options_raw:
            today = datetime.now().date()
            valid = [c for c in options_raw if 'expiry' in c]
            expiries = {}
            for c in valid:
                exp_date = datetime.strptime(c['expiry'], "%Y-%m-%d").date()
                dte = (exp_date - today).days
                if dte >= 360:
                    expiries.setdefault(dte, []).append(c)
            if expiries:
                closest_dte = min(expiries.keys())
                chain = expiries[closest_dte]
                calls = [c for c in chain if c.get('putCall') == 'C']
                if calls:
                    otm_call = min(calls, key=lambda c: abs(c['strike'] - price*1.10))
                    strike = otm_call['strike']
                    premium = round((otm_call.get('bid',0) + otm_call.get('ask',0))/2, 2)
                    iv = otm_call.get('iv') or "—"
                    expiry = chain[0]['expiry']
                    st.success(f"✅ LEAP Call for {leap_ticker_input}")
                    st.metric("Price", f"${price:,.2f}")
                    st.metric("Strike (≈10% OTM)", f"${strike}")
                    st.metric("Premium", f"${premium}")
                    st.metric("IV", f"{iv}%")
                    st.metric("DTE", f"{closest_dte} days")
                    st.metric("Expiry", expiry)
                    st.metric("RSI", f"{leap_rsi if leap_rsi else '—'}")
                    if st.button("Add this LEAP (house money only)", key="add_leap"):
                        if st.session_state.leap_fund >= 1000:
                            st.session_state.leaps.append({
                                "id": int(time.time()),
                                "ticker": leap_ticker_input,
                                "cost": premium * 100,
                                "current_val": premium * 100,
                                "contracts": 1,
                                "expiry": expiry
                            })
                            st.session_state.leap_fund -= premium * 100
                            save_persistent_data()
                            st.success("LEAP added!")
                            st.rerun()
                        else:
                            st.error("Not enough house money")
                else:
                    st.warning("No suitable 360+ DTE call found")
            else:
                st.warning("No 360+ DTE options available")
        else:
            st.warning("Options chain unavailable – using estimate")

    st.subheader("Your LEAP Positions")
    for l in st.session_state.leaps:
        with st.expander(f"{l['ticker']} LEAP"):
            st.write(f"Cost: ${l['cost']} | Current: ${l['current_val']} | Expiry: {l['expiry']}")
            if st.button("Sell Half & Recycle", key=l["id"]):
                st.session_state.leap_fund += l["cost"] * 0.8
                l["contracts"] = max(0, l["contracts"] - 1)
                save_persistent_data()
                st.success("Half sold")
                st.rerun()

with tab4:
    st.subheader("TradingView Super Chart + RSI")
    ticker = st.selectbox("Select Leveraged Ticker", st.session_state.tickers, key="superchart_ticker")
    tv_html = f"""
    <div style="width:100%; height:620px; position:relative; margin:0 auto;">
      <div id="tradingview_widget" style="width:100%; height:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true,
          "symbol": "{ticker}",
          "interval": "D",
          "timezone": "Etc/UTC",
          "theme": "light",
          "style": "1",
          "locale": "en",
          "toolbar_bg": "#f1f3f6",
          "enable_publishing": false,
          "hide_side_toolbar": false,
          "allow_symbol_change": true,
          "studies": ["RSI@tv-basicstudies"],
          "container_id": "tradingview_widget"
        }});
      </script>
    </div>
    """
    st.components.v1.html(tv_html, height=650, scrolling=False)

with tab5:
    st.subheader("📅 Upcoming Economic Events")
    st.info("Avoid new trades on high VIX (≥25) or major events")

with tab6:
    st.subheader("⚙️ Settings")
    st.write("**Investment Capital**")
    capital_options = [10000, 20000, 30000, 50000, 100000]
    selected = st.selectbox("Select starting capital", capital_options, index=1)
    manual = st.number_input("Or enter custom amount", min_value=5000, value=st.session_state.capital, step=1000)
    if st.button("Save Capital"):
        st.session_state.capital = manual if manual != st.session_state.capital else selected
        st.success(f"Capital set to ${st.session_state.capital:,.0f}")

    st.divider()
    st.write("**Finnhub API Key**")
    st.success("✅ Key is saved permanently")
    new_key = st.text_input("Update Finnhub API Key", type="password")
    if st.button("Update & Save"):
        if new_key.strip():
            st.session_state.finnhub_key = new_key.strip()
            with open(KEY_FILE, "w") as f:
                json.dump({"key": new_key.strip()}, f)
            st.success("Key updated and saved")
            st.rerun()

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

# Auto-refresh
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
if time.time() - st.session_state.last_refresh > 900:
    safe_batch_update(st.session_state.tickers)
    st.session_state.last_refresh = time.time()

if st.button("🔄 Safe Full Refresh (≤50 calls/min)"):
    safe_batch_update(st.session_state.tickers)
    st.success("Safe batch update completed")
    st.rerun()

st.caption("WheelOS • iOS-style UI + Color-coded CSP Headers + Profit % Matrix")