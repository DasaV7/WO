# app.py

import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_lightweight_charts import renderLightweightCharts

# ==================== PAGE CONFIG ====================

st.set_page_config(
    page_title="WheelOS • Options Radar",
    page_icon="◈",
    layout="wide",
)

# ==================== IOS / APPLE MINIMALIST THEME ====================

APPLE_CSS = """
<style>
body {
    background-color: #FAFAFA;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
}

/* Push content down so tabs are fully visible under Streamlit toolbar */
.block-container {
    padding-top: 3.5rem !important;
    padding-bottom: 2rem;
}

/* General buttons */
div.stButton > button {
    border-radius: 999px;
    border: none;
    padding: 0.5rem 1.4rem;
    font-weight: 600;
    transition: all 0.15s ease-in-out;
    box-shadow: 0 8px 18px rgba(0,0,0,0.04);
    color: #FFFFFF !important;
}

/* Primary button (systemGreen) */
button[kind="primary"] {
    background: linear-gradient(135deg, #34C759, #30D158) !important;
    color: #FFFFFF !important;
}

/* Secondary button (systemGray) */
button[kind="secondary"] {
    background: linear-gradient(135deg, #8E8E93, #AEAEB2) !important;
    color: #FFFFFF !important;
}

/* Disabled buttons */
button[disabled] {
    opacity: 0.45 !important;
    cursor: not-allowed !important;
}

/* Hover effect */
div.stButton > button:hover {
    transform: translateY(-1px) scale(1.01);
    box-shadow: 0 12px 26px rgba(0,0,0,0.08);
}

/* Cards */
.card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1.1rem 1.2rem;
    box-shadow: 0 14px 30px rgba(15,23,42,0.04);
    border: 1px solid rgba(148,163,184,0.18);
}

/* Metric cards */
.metric-card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 0.9rem 1.1rem;
    box-shadow: 0 10px 24px rgba(15,23,42,0.03);
    border: 1px solid rgba(148,163,184,0.16);
}

/* Soft red / green badges if needed */
.soft-red {
    background: linear-gradient(135deg, #FF3B30, #FF453A);
    color: #FFFFFF !important;
}
.soft-green {
    background: linear-gradient(135deg, #34C759, #30D158);
    color: #FFFFFF !important;
}
.soft-gray {
    background: linear-gradient(135deg, #8E8E93, #AEAEB2);
    color: #FFFFFF !important;
}
</style>
"""
st.markdown(APPLE_CSS, unsafe_allow_html=True)

# ==================== CONSTANTS ====================

VIX_LIMIT = 25
MOVE_PCT = 5
MAX_CALLS_PER_MIN = 50

MAIN_TICKER_MAP = {
    "TQQQ": "QQQ",
    "SOXL": "SOXX",
    "TSLL": "TSLA",
    "NVDL": "NVDA",
    "QQQ": "QQQ",
    "SPY": "SPY",
}

CORE_LEVERAGED = ["TSLL", "SOXL", "TQQQ", "NVDL"]

# ==================== SESSION STATE ====================

if "finnhub_key" not in st.session_state:
    st.session_state.finnhub_key = ""

if "trades" not in st.session_state:
    st.session_state.trades = []  # CSP + Covered Calls

if "leaps" not in st.session_state:
    st.session_state.leaps = []

if "leap_fund" not in st.session_state:
    st.session_state.leap_fund = 0.0

if "market_data" not in st.session_state:
    st.session_state.market_data = {}

if "chart_data" not in st.session_state:
    st.session_state.chart_data = {}

if "tickers" not in st.session_state:
    st.session_state.tickers = ["TSLL", "SOXL", "TQQQ"]

if "capital" not in st.session_state:
    st.session_state.capital = 20000

if "journal" not in st.session_state:
    st.session_state.journal = []

if "vix" not in st.session_state:
    st.session_state.vix = None

if "econ_events" not in st.session_state:
    st.session_state.econ_events = []

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

# ==================== FINNHUB HELPERS ====================

def _finnhub_get(path: str, params: dict | None = None):
    """Generic Finnhub GET helper with API key injection and basic error handling."""
    if not st.session_state.finnhub_key:
        return None
    base = "https://finnhub.io/api/v1"
    params = params or {}
    params["token"] = st.session_state.finnhub_key
    try:
        r = requests.get(f"{base}{path}", params=params, timeout=10)
        if r.ok:
            return r.json()
    except Exception:
        return None
    return None


def fetch_quote(sym: str):
    return _finnhub_get("/quote", {"symbol": sym})


def fetch_candles(sym: str):
    to_ts = int(time.time())
    from_ts = to_ts - (40 * 86400)
    data = _finnhub_get(
        "/stock/candle",
        {"symbol": sym, "resolution": "D", "from": from_ts, "to": to_ts},
    )
    if not data or data.get("s") != "ok":
        return None
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(data["t"], unit="s"),
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
        }
    )
    df["time_str"] = df["time"].dt.strftime("%Y-%m-%d")
    return df


def calc_rv(df: pd.DataFrame | None):
    if df is None or len(df) < 5:
        return None
    returns = df["close"].pct_change().dropna()
    return round(returns.std() * (252 ** 0.5) * 100, 1)


def fetch_vix():
    q = fetch_quote("^VIX")
    if q and q.get("c"):
        return round(q["c"], 2)
    return None


def fetch_economic_calendar(days_ahead: int = 7):
    today = datetime.utcnow().date()
    end = today + timedelta(days=days_ahead)
    data = _finnhub_get(
        "/calendar/economic",
        {"from": today.isoformat(), "to": end.isoformat()},
    )
    if not data or "economicCalendar" not in data:
        return []
    events = data["economicCalendar"]
    df = pd.DataFrame(events)
    if "impact" in df.columns:
        df = df[df["impact"].isin(["high", "medium"])].copy()
    return df.sort_values("time").to_dict(orient="records")


def fetch_options_chain(symbol: str):
    data = _finnhub_get("/stock/option-chain", {"symbol": symbol})
    if not data:
        return None
    return data


def nearest_30d_expiry_from_chain(chain: dict):
    if not chain or "data" not in chain:
        return None
    expiries = set()
    for row in chain["data"]:
        exp = row.get("expirationDate")
        if exp:
            expiries.add(exp)
    if not expiries:
        return None
    target = datetime.utcnow().date() + timedelta(days=30)
    best = None
    best_diff = None
    for e in expiries:
        try:
            d = datetime.strptime(e, "%Y-%m-%d").date()
        except Exception:
            continue
        diff = abs((d - target).days)
        if best is None or diff < best_diff:
            best = e
            best_diff = diff
    return best


def safe_batch_update(tickers):
    updated = 0
    for sym in tickers:
        if updated >= MAX_CALLS_PER_MIN:
            st.warning(
                f"Reached safe limit ({MAX_CALLS_PER_MIN}/min). Remaining updates will run next minute."
            )
            break
        q = fetch_quote(sym)
        if q and q.get("c"):
            df = fetch_candles(sym)
            rv = calc_rv(df)
            st.session_state.market_data[sym] = {
                "price": round(q["c"], 2),
                "change": round(q.get("dp", 0), 2),
                "rv": rv,
            }
            updated += 2
            time.sleep(1.2)

    st.session_state.vix = fetch_vix()
    st.session_state.econ_events = fetch_economic_calendar()

# ==================== FINNHUB KEY PERSISTENCE (QUERY PARAMS) ====================

# Use URL query params as a simple browser-side persistence mechanism.
# On first save, we store the key in the URL; on reload/redeploy, we read it back.

if not st.session_state.finnhub_key:
    if "fhk" in st.query_params and st.query_params["fhk"]:
        st.session_state.finnhub_key = st.query_params["fhk"]

# ==================== FIRST-TIME FINNHUB SETUP ====================

if not st.session_state.finnhub_key:
    st.title("Welcome to WheelOS")
    st.markdown("### First Time Setup")
    st.info("Get your free Finnhub API key at finnhub.io → Dashboard → API Key")

    key = st.text_input("Paste your Finnhub API Key", type="password")
    if st.button("Save & Launch App", type="primary"):
        if key.strip():
            st.session_state.finnhub_key = key.strip()
            # Persist in URL query params so it survives refresh/redeploy
            st.query_params["fhk"] = st.session_state.finnhub_key
            st.success("Key saved! Loading app…")
            st.rerun()
        else:
            st.error("Please enter a valid key")
    st.stop()

# ==================== SIDEBAR ====================

with st.sidebar:
    st.title("◈ WheelOS")
    st.success("Finnhub connected")

    if st.session_state.vix is not None:
        if st.session_state.vix >= VIX_LIMIT:
            st.error(f"VIX: {st.session_state.vix} (≥ {VIX_LIMIT}) — New trades paused")
        else:
            st.metric("VIX", st.session_state.vix)
    else:
        st.caption("VIX loading…")

    st.markdown("---")
    st.markdown("**Discipline Guardrails**")
    st.caption(
        "• Only CSP on red days (≤ -5%)\n"
        "• Close at 50% profit\n"
        "• 50% income / 50% LEAP fund\n"
        "• LEAPs = house money only\n"
        "• Max 5 open positions\n"
        "• Keep 30%+ cash"
    )

    if st.button("Reset Finnhub Key", type="secondary"):
        st.session_state.finnhub_key = ""
        # Clear query param
        st.query_params.clear()
        st.rerun()

# ==================== AUTO REFRESH (15 MIN) ====================

if time.time() - st.session_state.last_refresh > 900:
    safe_batch_update(st.session_state.tickers)
    st.session_state.last_refresh = time.time()

# ==================== TABS ====================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["📊 Dashboard", "🔁 CSP & Wheel", "🚀 LEAP Trades", "📈 Super Chart", "📅 Calendar", "⚙️ Settings"]
)

# ==================== DASHBOARD TAB ====================

with tab1:
    st.subheader("Matt’s Profit Recycling Loop")
    st.info(
        "CSP on **red days (≤ -5%)** → Close at **50% profit** → "
        "**50% income**, **50% to LEAP fund (house money only)**."
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("House Money", f"${st.session_state.leap_fund:,.0f}")
        st.markdown("</div>", unsafe_allow_html=True)

    closed = [t for t in st.session_state.trades if t.get("status") == "closed"]
    total_pnl = sum(t.get("pnl", 0) for t in closed)
    win_rate = round(
        len([t for t in closed if t.get("pnl", 0) > 0]) / len(closed) * 100, 1
    ) if closed else 0
    avg_days = round(
        sum(t.get("days_active", 0) for t in closed) / len(closed), 1
    ) if closed else 0

    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Realized P&L", f"${total_pnl:,.0f}")
        st.markdown("</div>", unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Win Rate", f"{win_rate}%")
        st.markdown("</div>", unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("Avg Days to Close", f"{avg_days} days")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    if st.button("🔄 Safe Refresh (≤50 calls/min)", type="primary"):
        safe_batch_update(st.session_state.tickers)
        st.success("Batch update completed safely")
        st.rerun()

    if st.session_state.market_data:
        st.markdown("#### Live Ticker Snapshot")
        df_md = pd.DataFrame.from_dict(
            st.session_state.market_data, orient="index"
        ).rename(columns={"price": "Price", "change": "Change %", "rv": "Realized Vol %"})
        st.dataframe(df_md, use_container_width=True)
    else:
        st.info("Click **Safe Refresh** to load market data.")

    st.markdown("---")
    st.markdown("#### Graduation Progress")

    num_csp_closed = len([t for t in closed if "CSP" in t.get("type", "")])
    num_leaps = len(st.session_state.leaps)

    if num_csp_closed < 5:
        level = 1
        label = "Level 1 — CSP Foundation"
    elif num_csp_closed >= 5 and num_leaps == 0:
        level = 2
        label = "Level 2 — Add Leveraged ETFs"
    elif num_leaps > 0 and num_csp_closed < 15:
        level = 3
        label = "Level 3 — Introduce LEAPs"
    else:
        level = 4
        label = "Level 4 — Full Wheel (CSP → Assignment → Covered Calls)"

    st.progress(level / 4.0)
    st.write(label)

    st.markdown("---")
    st.markdown("#### Profit Recycling Visualization (Simple View)")
    if closed:
        income = sum(t.get("pnl", 0) * 0.5 for t in closed)
        recycled = sum(t.get("pnl", 0) * 0.5 for t in closed)
        pr_df = pd.DataFrame(
            {
                "Bucket": ["Income (50%)", "Recycled to LEAP Fund (50%)"],
                "Amount": [income, recycled],
            }
        )
        st.bar_chart(pr_df.set_index("Bucket"))
    else:
        st.info("Close some CSP trades at 50% profit to see the recycling chart.")

# ==================== CSP & WHEEL TAB ====================

with tab2:
    st.subheader("CSP Trades • Red Day Sell Put / Assignment → Covered Calls")

    open_positions = [t for t in st.session_state.trades if t.get("status") == "open"]
    num_open = len(open_positions)
    cash_required = sum(
        t.get("strike", 0) * 100 for t in open_positions if "Put" in t.get("type", "")
    )
    cash_available = st.session_state.capital - cash_required
    cash_ratio = (
        cash_available / st.session_state.capital if st.session_state.capital else 1
    )

    if num_open >= 5:
        st.error("Max 5 open positions reached — new CSPs are disabled.")
    if cash_ratio < 0.3:
        st.warning(
            f"Cash buffer below 30% (Current: {cash_ratio:.0%}). "
            "Consider closing or avoiding new positions."
        )

    if len(st.session_state.tickers) > 5:
        st.warning(
            "You are watching more than 5 tickers. "
            "Matt’s system prefers 3–5 core names."
        )

    if st.session_state.vix is not None and st.session_state.vix >= VIX_LIMIT:
        st.error("VIX is elevated — new CSP/CC trades are paused per rules.")

    for ticker in st.session_state.tickers:
        d = st.session_state.market_data.get(ticker, {})
        price = d.get("price")
        rv = d.get("rv")
        chg = d.get("change", 0)

        if not price:
            st.write(f"Waiting for data on {ticker}… (hit Safe Refresh)")
            continue

        signal = "NO TRADE"
        put_enabled = False
        call_enabled = False

        if st.session_state.vix is not None and st.session_state.vix >= VIX_LIMIT:
            signal = "NO TRADE (VIX HIGH)"
        elif chg <= -MOVE_PCT:
            signal = "SELL PUT (Red Day ≤ -5%)"
            put_enabled = True
        elif chg >= MOVE_PCT:
            signal = "SELL CALL (Green Day ≥ +5%)"
            call_enabled = True

        expander_label = f"{ticker} — {signal}"
        with st.expander(expander_label):
            st.write(
                f"Price: **${price}** | Change: **{chg}%** | "
                f"RV: **{rv if rv is not None else 'Not loaded yet'}**"
            )
            if rv is not None and rv < 50:
                st.warning("Realized volatility < 50% — system prefers high IV names.")
            elif rv is None:
                st.warning("RV data not loaded yet – trading based on price action only.")

            main_ticker = MAIN_TICKER_MAP.get(ticker, ticker)
            chain = fetch_options_chain(main_ticker)
            expiry_30 = nearest_30d_expiry_from_chain(chain)
            if chain and expiry_30:
                st.markdown(
                    f"**Nearest ~30D Expiry:** `{expiry_30}` (underlying: {main_ticker})"
                )
                rows = [
                    r for r in chain["data"]
                    if r.get("expirationDate") == expiry_30
                ]
                if rows:
                    df_chain = pd.DataFrame(rows)
                    cols_to_show = [
                        "type",
                        "strike",
                        "lastPrice",
                        "bid",
                        "ask",
                        "impliedVolatility",
                        "openInterest",
                    ]
                    df_chain = df_chain[cols_to_show].rename(
                        columns={
                            "type": "Type",
                            "strike": "Strike",
                            "lastPrice": "Last",
                            "bid": "Bid",
                            "ask": "Ask",
                            "impliedVolatility": "IV",
                            "openInterest": "OI",
                        }
                    )
                    st.dataframe(
                        df_chain.sort_values(["Type", "Strike"]),
                        use_container_width=True,
                        height=260,
                    )
                else:
                    st.info("No options rows found for nearest 30D expiry.")
            else:
                st.caption("Options chain not available or limit reached.")

            st.markdown("---")
            st.markdown("**Log New Trade (Manual Premium)**")

            col_a, col_b = st.columns(2)
            with col_a:
                strike_input = st.number_input(
                    f"{ticker} Strike (approx 10% OTM for CSP)",
                    min_value=0.0,
                    value=round(price * 0.9, 2),
                    step=0.5,
                    key=f"strike_{ticker}",
                )
            with col_b:
                premium_input = st.number_input(
                    f"{ticker} Premium per Contract ($)",
                    min_value=0.01,
                    value=round(price * 0.05, 2),
                    step=0.05,
                    key=f"prem_{ticker}",
                )

            expiry_date = datetime.utcnow().date() + timedelta(days=30)
            st.caption(f"Target expiry ~30 DTE: **{expiry_date.isoformat()}**")

            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                disabled_put = (
                    not put_enabled
                    or num_open >= 5
                    or (
                        st.session_state.vix is not None
                        and st.session_state.vix >= VIX_LIMIT
                    )
                )
                if st.button(
                    f"Log Sell CSP Put on {ticker}",
                    key=f"put_{ticker}",
                    disabled=disabled_put,
                    type="primary",
                ):
                    required = strike_input * 100
                    if cash_available - required < st.session_state.capital * 0.3:
                        st.error("This CSP would push cash below 30% — blocked by rules.")
                    else:
                        st.session_state.trades.append(
                            {
                                "id": int(time.time()),
                                "type": "CSP Put",
                                "ticker": ticker,
                                "strike": float(strike_input),
                                "expiry": expiry_date.isoformat(),
                                "entry_premium": float(premium_input),
                                "status": "open",
                                "pnl": 0.0,
                                "opened": datetime.utcnow().strftime("%Y-%m-%d"),
                                "assigned": False,
                            }
                        )
                        st.success("CSP Put logged (red day rule enforced).")
                        st.rerun()

            with col_btn2:
                assigned_positions = [
                    t for t in st.session_state.trades
                    if t.get("ticker") == ticker and t.get("assigned") is True
                ]
                disabled_call = (
                    not call_enabled
                    or len(assigned_positions) == 0
                    or num_open >= 5
                    or (
                        st.session_state.vix is not None
                        and st.session_state.vix >= VIX_LIMIT
                    )
                )
                if st.button(
                    f"Log Covered Call on {ticker}",
                    key=f"cc_{ticker}",
                    disabled=disabled_call,
                    type="primary",
                ):
                    st.session_state.trades.append(
                        {
                            "id": int(time.time()),
                            "type": "Covered Call",
                            "ticker": ticker,
                            "strike": float(round(price * 1.1, 2)),
                            "expiry": expiry_date.isoformat(),
                            "entry_premium": float(premium_input),
                            "status": "open",
                            "pnl": 0.0,
                            "opened": datetime.utcnow().strftime("%Y-%m-%d"),
                            "assigned": False,
                        }
                    )
                    st.success("Covered Call logged (assignment → CC on green day).")
                    st.rerun()

    st.markdown("---")
    st.subheader("Open Wheel Positions")

    for t in st.session_state.trades:
        if t.get("status") != "open":
            continue

        label = f"{t['ticker']} {t['type']} @ ${t['strike']} (exp {t['expiry']})"
        with st.expander(label):
            st.write(f"Entry Premium: **${t.get('entry_premium', '—')}**")
            st.write(f"Opened: {t.get('opened', '—')}")

            col1, col2, col3 = st.columns(3)
            with col1:
                if "CSP" in t["type"] or "Covered Call" in t["type"]:
                    if st.button("Close at 50% Profit", key=f"close50_{t['id']}"):
                        profit = round(t["entry_premium"] * 0.5, 2)
                        t["pnl"] = profit
                        t["status"] = "closed"
                        t["closed_date"] = datetime.utcnow().strftime("%Y-%m-%d")
                        income = profit * 0.5
                        recycled = profit * 0.5
                        st.session_state.leap_fund += recycled

                        st.session_state.journal.append(
                            {
                                "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                                "ticker": t["ticker"],
                                "type": t["type"],
                                "action": "Closed at 50%",
                                "profit": profit,
                                "note": f"Income: ${income:.2f}, Recycled to LEAP fund: ${recycled:.2f}",
                            }
                        )

                        st.success(
                            f"Closed at 50% profit. "
                            f"Income: ${income:.2f} • Recycled: ${recycled:.2f} → House Money"
                        )
                        st.rerun()

            with col2:
                if "CSP" in t["type"] and not t.get("assigned", False):
                    if st.button(
                        "Mark as Assigned (Shares Received)", key=f"assign_{t['id']}"
                    ):
                        t["assigned"] = True
                        st.session_state.journal.append(
                            {
                                "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                                "ticker": t["ticker"],
                                "type": t["type"],
                                "action": "Assigned",
                                "profit": 0.0,
                                "note": "CSP assigned → shares owned, ready for covered calls.",
                            }
                        )
                        st.success(
                            "Position marked as assigned. Look for green days to sell covered calls."
                        )
                        st.rerun()

            with col3:
                if st.button("Manual Close (Custom P&L)", key=f"manual_{t['id']}"):
                    pnl = st.number_input(
                        "Enter realized P&L for this trade",
                        key=f"pnl_input_{t['id']}",
                        value=0.0,
                    )
                    confirm = st.button(
                        "Confirm Manual Close", key=f"confirm_manual_{t['id']}"
                    )
                    if confirm:
                        t["pnl"] = float(pnl)
                        t["status"] = "closed"
                        t["closed_date"] = datetime.utcnow().strftime("%Y-%m-%d")
                        if pnl > 0:
                            income = pnl * 0.5
                            recycled = pnl * 0.5
                            st.session_state.leap_fund += recycled
                            note = (
                                f"Manual close. Income: ${income:.2f}, "
                                f"Recycled: ${recycled:.2f}"
                            )
                        else:
                            note = "Manual close. Loss or zero P&L."
                        st.session_state.journal.append(
                            {
                                "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                                "ticker": t["ticker"],
                                "type": t["type"],
                                "action": "Manual Close",
                                "profit": pnl,
                                "note": note,
                            }
                        )
                        st.success("Trade manually closed and journal updated.")
                        st.rerun()

# ==================== LEAP TRADES TAB ====================

with tab3:
    st.subheader("LEAP Calls • House Money Only")

    st.metric("House Money Available", f"${st.session_state.leap_fund:,.0f}")

    st.info(
        "LEAPs are **long-dated calls (≥ 360 DTE)**, typically **~10% OTM** on quality names "
        "(QQQ, SOXX, TSLA, NVDA, etc.). Only buy with **house money** from CSP profits."
    )

    leap_ticker = st.selectbox(
        "LEAP Ticker", options=list(MAIN_TICKER_MAP.values()), key="leap_sel"
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        leap_cost = st.number_input(
            "Cost per LEAP position ($)",
            min_value=100.0,
            value=1200.0,
            step=50.0,
        )
    with col2:
        contracts = st.number_input(
            "Contracts",
            min_value=1,
            value=1,
            step=1,
        )
    with col3:
        expiry_leap = datetime.utcnow().date() + timedelta(days=365)
        st.caption(f"Target LEAP expiry ≥ 360 DTE: **{expiry_leap.isoformat()}**")

    if st.button("Add LEAP (House Money Only)", type="primary"):
        total_cost = leap_cost * contracts
        if st.session_state.leap_fund >= total_cost:
            st.session_state.leaps.append(
                {
                    "id": int(time.time()),
                    "ticker": leap_ticker,
                    "cost": float(total_cost),
                    "current_val": float(total_cost),
                    "contracts": int(contracts),
                    "expiry": expiry_leap.isoformat(),
                    "opened": datetime.utcnow().strftime("%Y-%m-%d"),
                }
            )
            st.session_state.leap_fund -= total_cost
            st.success("LEAP added using house money only.")
            st.rerun()
        else:
            st.error("Not enough house money — LEAPs must be funded only from CSP profits.")

    st.markdown("---")
    st.subheader("Your LEAP Positions")

    if not st.session_state.leaps:
        st.info(
            "No LEAP positions yet. Build CSP profits first, then deploy house money into LEAPs."
        )
    else:
        for l in st.session_state.leaps:
            with st.expander(
                f"{l['ticker']} LEAP — {l['contracts']} contract(s) exp {l['expiry']}"
            ):
                st.write(
                    f"Cost: **${l['cost']}** | Current: **${l['current_val']}** | "
                    f"Opened: {l.get('opened', '—')}"
                )
                profit_pct = ((l["current_val"] - l["cost"]) / l["cost"]) * 100
                st.write(f"Unrealized Return: **{profit_pct:.1f}%**")

                if profit_pct >= 100:
                    st.success("🎯 >100% profit – System suggests selling half & recycling.")

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Update Current Value", key=f"upd_{l['id']}"):
                        new_val = st.number_input(
                            "New current value ($)",
                            value=float(l["current_val"]),
                            key=f"val_{l['id']}",
                        )
                        confirm = st.button(
                            "Confirm Value Update", key=f"confirm_val_{l['id']}"
                        )
                        if confirm:
                            l["current_val"] = float(new_val)
                            st.success("LEAP value updated.")
                            st.rerun()

                with col_b:
                    if st.button("Sell Half & Recycle", key=f"sell_half_{l['id']}"):
                        if l["contracts"] <= 0:
                            st.warning("No contracts left to sell.")
                        else:
                            sell_contracts = max(1, l["contracts"] // 2)
                            avg_price = l["current_val"] / max(l["contracts"], 1)
                            proceeds = avg_price * sell_contracts
                            cost_fraction = l["cost"] * (
                                sell_contracts / max(l["contracts"], 1)
                            )
                            profit = proceeds - cost_fraction
                            recycled = max(profit, 0) * 0.5
                            st.session_state.leap_fund += recycled
                            l["contracts"] -= sell_contracts
                            l["cost"] -= cost_fraction
                            l["current_val"] -= avg_price * sell_contracts

                            st.session_state.journal.append(
                                {
                                    "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                                    "ticker": l["ticker"],
                                    "type": "LEAP",
                                    "action": "Sell Half & Recycle",
                                    "profit": profit,
                                    "note": f"Sold {sell_contracts} contract(s). Recycled ${recycled:.2f} to LEAP fund.",
                                }
                            )

                            st.success(
                                f"Sold {sell_contracts} contract(s). "
                                f"Profit: ${profit:.2f} • Recycled: ${recycled:.2f} to House Money."
                            )
                            st.rerun()

# ==================== SUPER CHART TAB ====================

with tab4:
    st.subheader("TradingView Super Chart + RSI")

    ticker = st.selectbox(
        "Select Leveraged Ticker", st.session_state.tickers, key="superchart_ticker"
    )
    main_ticker = MAIN_TICKER_MAP.get(ticker, ticker)
    st.write(f"Showing: **{ticker}** (Volume + RSI) + **{main_ticker}** (overlay)")

    tv_html = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
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
          "studies": [
              "RSI@tv-basicstudies",
              "Volume@tv-basicstudies"
          ],
          "overrides": {{
              "paneProperties.background": "#FAFAFA",
              "paneProperties.vertGridProperties.color": "#E5E7EB",
              "paneProperties.horzGridProperties.color": "#E5E7EB"
          }},
          "container_id": "tradingview_chart"
      }});
      </script>
    </div>
    """
    st.components.v1.html(tv_html, height=680, scrolling=True)

# ==================== CALENDAR TAB ====================

with tab5:
    st.subheader("📅 Upcoming Economic Events")
    st.info("Avoid new trades on **high VIX (≥25)** or **major economic events**.")

    if not st.session_state.econ_events:
        st.caption("No events loaded yet. Use Safe Refresh on Dashboard to pull calendar.")
    else:
        df_events = pd.DataFrame(st.session_state.econ_events)
        rename_map = {
            "time": "Time",
            "country": "Country",
            "event": "Event",
            "impact": "Impact",
            "actual": "Actual",
            "forecast": "Forecast",
            "previous": "Previous",
        }
        df_events = df_events.rename(columns=rename_map)
        st.dataframe(df_events, use_container_width=True, height=420)

# ==================== SETTINGS TAB ====================

with tab6:
    st.subheader("⚙️ Settings")

    st.markdown("### Investment Capital")
    capital_options = [10000, 20000, 30000, 50000, 100000]
    selected_index = (
        capital_options.index(st.session_state.capital)
        if st.session_state.capital in capital_options
        else 1
    )
    selected = st.selectbox(
        "Select starting capital",
        capital_options,
        index=selected_index,
    )
    manual = st.number_input(
        "Or enter custom amount",
        min_value=5000,
        value=int(st.session_state.capital),
        step=1000,
    )
    if st.button("Save Capital", type="primary"):
        st.session_state.capital = (
            manual if manual != st.session_state.capital else selected
        )
        st.success(f"Capital set to ${st.session_state.capital:,.0f}")

    st.markdown("---")
    st.markdown("### House Money")
    st.metric("Current House Money", f"${st.session_state.leap_fund:,.0f}")

    st.markdown("---")
    st.markdown("### Journal Entries (Closed Trades)")

    if st.session_state.journal:
        journal_df = pd.DataFrame(st.session_state.journal)
        st.dataframe(journal_df, use_container_width=True, height=320)

        csv = journal_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Export Journal to CSV",
            data=csv,
            file_name="wheelos_journal.csv",
            mime="text/csv",
        )
    else:
        st.info("No closed trades yet.")

    st.markdown("---")
    st.markdown("### Watched Tickers")

    for t in list(st.session_state.tickers):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"• {t}")
        with col2:
            if st.button("Remove", key=f"rem_{t}", type="secondary"):
                if len(st.session_state.tickers) > 1:
                    st.session_state.tickers.remove(t)
                    st.success(f"Removed {t}")
                    st.rerun()
                else:
                    st.error("Keep at least one ticker.")

    st.markdown("---")
    st.markdown("### Add New Ticker")

    new_t = st.text_input("Ticker Symbol").upper().strip()
    if st.button("Add Ticker", type="primary"):
        if new_t and new_t not in st.session_state.tickers:
            q = fetch_quote(new_t)
            if q and q.get("c"):
                st.session_state.tickers.append(new_t)
                st.success(f"Added {new_t}")
                st.rerun()
            else:
                st.error("Ticker not found or no data.")
        else:
            st.warning("Already watching or empty input.")

    st.markdown("---")
    st.markdown("### Safe Full Refresh")
    if st.button("🔄 Safe Full Refresh (≤50 calls/min)", type="primary"):
        safe_batch_update(st.session_state.tickers)
        st.success("Safe batch update completed.")
        st.rerun()

st.caption(
    "WheelOS • Matt @MarketMovesMatt Strategy • CSP Income + LEAP Growth • House Money Only for LEAPs"
)
