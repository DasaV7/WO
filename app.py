# ============================
# IMPORTS & BASIC CONFIG
# ============================

import os
import datetime as dt
from typing import Dict, Any, List

import requests
import pandas as pd
import streamlit as st

# ============================
# APP CONFIG
# ============================

st.set_page_config(
    page_title="Options Wheel Dashboard",
    layout="wide",
)

# Soft card styling (A.01-style)
st.markdown(
    """
    <style>
    .card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.35);
    }
    .card-header {
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 0.35rem;
        color: #0f172a;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #64748b;
    }
    .metric-value {
        font-size: 1.1rem;
        font-weight: 600;
        color: #0f172a;
    }
    .small-text {
        font-size: 0.8rem;
        color: #64748b;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0.4rem 0.9rem;
        border-radius: 999px;
        background-color: #e5e7eb20;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0f172a;
        color: #f9fafb !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================
# SETTINGS & API KEYS
# ============================

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "YOUR_FINNHUB_KEY_HERE")
FINNHUB_BASE = "https://finnhub.io/api/v1"


def _finnhub_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Low-level Finnhub GET helper."""
    url = f"{FINNHUB_BASE}/{path}"
    params = dict(params or {})
    params["token"] = FINNHUB_API_KEY
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ============================
# FINNHUB HELPERS
# ============================

def get_quote(symbol: str) -> Dict[str, Any]:
    """Current quote for a symbol."""
    try:
        data = _finnhub_get("quote", {"symbol": symbol})
    except Exception:
        data = {}
    return data or {}


def get_economic_calendar() -> pd.DataFrame:
    """Simple economic calendar for today ± 7 days."""
    today = dt.date.today()
    _from = (today - dt.timedelta(days=7)).isoformat()
    _to = (today + dt.timedelta(days=7)).isoformat()
    try:
        data = _finnhub_get("calendar/economic", {"from": _from, "to": _to})
        events = data.get("economicCalendar", [])
        if not events:
            return pd.DataFrame()
        df = pd.DataFrame(events)
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def get_market_snapshot(symbols: List[str]) -> pd.DataFrame:
    """Build a simple snapshot table for a list of tickers."""
    rows = []
    for sym in symbols:
        q = get_quote(sym)
        if not q:
            continue
        rows.append(
            {
                "Symbol": sym,
                "Last": q.get("c"),
                "Change": q.get("d"),
                "Change %": q.get("dp"),
                "High": q.get("h"),
                "Low": q.get("l"),
                "Prev Close": q.get("pc"),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# ============================
# OPTIONS CHAIN (CH2) HELPERS
# ============================

def get_options_chain_ch2(symbol: str) -> Dict[str, Any]:
    """
    Fetch options chain using Finnhub's grouped-by-expiry style (CH2).
    We assume an endpoint that returns:
    {
      "data": {
        "2024-05-17": {
            "CALL": [...],
            "PUT": [...]
        },
        ...
      }
    }
    If your actual endpoint differs, adjust this helper only.
    """
    try:
        # NOTE: Replace 'option/chain' with the exact CH2 endpoint you use.
        data = _finnhub_get("option/chain", {"symbol": symbol})
        return data or {}
    except Exception:
        return {}


def normalize_chain_ch2_to_frames(chain: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """
    Convert CH2-style grouped chain into a dict:
      { expiry_str: DataFrame([...]) }
    Each DataFrame has columns: type, strike, bid, ask, last, volume, openInterest, etc.
    """
    result: Dict[str, pd.DataFrame] = {}
    data = chain.get("data") or {}
    for expiry, side_map in data.items():
        rows = []
        for opt_type, contracts in (side_map or {}).items():
            for c in contracts or []:
                row = dict(c)
                row["type"] = opt_type
                rows.append(row)
        if rows:
            df = pd.DataFrame(rows)
            # Standardize some common columns if present
            rename_map = {
                "strikePrice": "strike",
                "Strike": "strike",
                "lastPrice": "last",
                "Last": "last",
            }
            df = df.rename(columns=rename_map)
            result[expiry] = df
    return result


# ============================
# SIMPLE STATE / SETTINGS
# ============================

DEFAULT_TICKERS = ["SPY", "QQQ", "TSLA", "AAPL"]

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "SPY"

if "tracked_tickers" not in st.session_state:
    st.session_state.tracked_tickers = DEFAULT_TICKERS.copy()


def set_selected_ticker(sym: str) -> None:
    st.session_state.selected_ticker = sym
# ============================
# MAIN LAYOUT & TABS
# ============================

st.title("Options Wheel Dashboard")

tabs = st.tabs(["Dashboard", "CSP", "LEAPs", "Super Chart", "Journal"])

# ============================
# DASHBOARD TAB
# ============================

with tabs[0]:
    st.subheader("Dashboard")

    # ---- Metrics Row ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Key Metrics</div>', unsafe_allow_html=True)

        cols = st.columns(4)
        for i, sym in enumerate(st.session_state.tracked_tickers[:4]):
            q = get_quote(sym)
            last = q.get("c", "-")
            chg = q.get("d", 0)
            pct = q.get("dp", 0)
            cols[i].markdown(f"<div class='metric-label'>{sym}</div>", unsafe_allow_html=True)
            cols[i].markdown(
                f"<div class='metric-value'>{last}</div>"
                f"<div class='small-text'>{chg} ({pct}%)</div>",
                unsafe_allow_html=True,
            )

        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Market Snapshot ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Market Snapshot</div>', unsafe_allow_html=True)

        snap = get_market_snapshot(st.session_state.tracked_tickers)
        if not snap.empty:
            st.dataframe(snap, use_container_width=True)
        else:
            st.info("No snapshot data available.")

        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Economic Calendar ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Economic Calendar</div>', unsafe_allow_html=True)

        econ = get_economic_calendar()
        if not econ.empty:
            st.dataframe(econ, use_container_width=True)
        else:
            st.info("No economic events found.")

        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Options Chain (CH2, OCF3) ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Options Chain</div>', unsafe_allow_html=True)

        dash_sym = st.selectbox(
            "Select symbol for options chain",
            st.session_state.tracked_tickers,
            key="dash_chain_sym",
        )

        chain_raw = get_options_chain_ch2(dash_sym)
        chain_frames = normalize_chain_ch2_to_frames(chain_raw)

        if not chain_frames:
            st.info("No options chain data available.")
        else:
            for expiry, df in chain_frames.items():
                with st.expander(f"Expiry: {expiry}"):
                    st.dataframe(df, use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)


# ============================
# CSP TAB
# ============================

with tabs[1]:
    st.subheader("Cash-Secured Puts / Covered Calls")

    # ---- Tracked Tickers ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Tracked Tickers</div>', unsafe_allow_html=True)

        new_ticker = st.text_input("Add ticker", "")
        if st.button("Add", key="add_ticker_btn"):
            if new_ticker and new_ticker.upper() not in st.session_state.tracked_tickers:
                st.session_state.tracked_tickers.append(new_ticker.upper())
                st.success(f"Added {new_ticker.upper()}")

        st.write("Current:", ", ".join(st.session_state.tracked_tickers))
        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Ownership Toggles ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Ownership</div>', unsafe_allow_html=True)

        for sym in st.session_state.tracked_tickers:
            st.checkbox(f"Own {sym}", key=f"own_{sym}")

        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Market Snapshot ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Market Snapshot</div>', unsafe_allow_html=True)

        snap2 = get_market_snapshot(st.session_state.tracked_tickers)
        if not snap2.empty:
            st.dataframe(snap2, use_container_width=True)
        else:
            st.info("No snapshot data available.")

        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Options Chain (CSP‑POS1) ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Options Chain</div>', unsafe_allow_html=True)

        csp_sym = st.selectbox(
            "Select symbol for CSP options chain",
            st.session_state.tracked_tickers,
            key="csp_chain_sym",
        )

        csp_chain_raw = get_options_chain_ch2(csp_sym)
        csp_chain_frames = normalize_chain_ch2_to_frames(csp_chain_raw)

        if not csp_chain_frames:
            st.info("No options chain data available.")
        else:
            for expiry, df in csp_chain_frames.items():
                with st.expander(f"Expiry: {expiry}"):
                    st.dataframe(df, use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Log New Trade ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Log New Trade</div>', unsafe_allow_html=True)

        st.text_input("Trade symbol", key="trade_sym")
        st.date_input("Open date", key="trade_open")
        st.number_input("Premium received", key="trade_prem", value=0.0)
        st.number_input("Strike", key="trade_strike", value=0.0)
        st.number_input("Contracts", key="trade_contracts", value=1)

        if st.button("Save Trade"):
            st.success("Trade saved (placeholder).")

        st.markdown('</div>', unsafe_allow_html=True)

    # ---- Open Positions ----
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Open Positions</div>', unsafe_allow_html=True)

        st.info("Open positions table placeholder.")

        st.markdown('</div>', unsafe_allow_html=True)
# ============================
# LEAPs TAB
# ============================

with tabs[2]:
    st.subheader("LEAPs Dashboard")

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">LEAPs Positions</div>', unsafe_allow_html=True)

        st.info("LEAPs tracking placeholder. Add your LEAPs logic here.")

        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Add New LEAP</div>', unsafe_allow_html=True)

        st.text_input("Symbol", key="leap_sym")
        st.date_input("Open Date", key="leap_open")
        st.number_input("Premium Paid", key="leap_prem", value=0.0)
        st.number_input("Strike", key="leap_strike", value=0.0)
        st.date_input("Expiration", key="leap_exp")

        if st.button("Save LEAP"):
            st.success("LEAP saved (placeholder).")

        st.markdown('</div>', unsafe_allow_html=True)


# ============================
# SUPER CHART TAB (TradingView TV1)
# ============================

with tabs[3]:
    st.subheader("Super Chart")

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">TradingView Chart</div>', unsafe_allow_html=True)

        chart_sym = st.text_input(
            "Enter symbol for chart",
            st.session_state.selected_ticker,
            key="tv_chart_sym",
        )

        st.session_state.selected_ticker = chart_sym.upper()

        tv_html = f"""
        <div class="tradingview-widget-container" style="height: 650px;">
          <div id="tradingview_chart"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
            new TradingView.widget({{
              "width": "100%",
              "height": 650,
              "symbol": "{chart_sym.upper()}",
              "interval": "D",
              "timezone": "Etc/UTC",
              "theme": "light",
              "style": "1",
              "locale": "en",
              "toolbar_bg": "#f1f3f6",
              "enable_publishing": false,
              "allow_symbol_change": true,
              "container_id": "tradingview_chart"
            }});
          </script>
        </div>
        """

        st.components.v1.html(tv_html, height=650, scrolling=False)

        st.markdown('</div>', unsafe_allow_html=True)


# ============================
# JOURNAL TAB
# ============================

with tabs[4]:
    st.subheader("Trading Journal")

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Journal Entries</div>', unsafe_allow_html=True)

        st.info("Journal table placeholder.")

        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Add Journal Entry</div>', unsafe_allow_html=True)

        st.text_area("Notes", key="journal_notes")
        st.date_input("Date", key="journal_date")

        if st.button("Save Entry"):
            st.success("Journal entry saved (placeholder).")

        st.markdown('</div>', unsafe_allow_html=True)


# ============================
# FOOTER
# ============================

st.markdown(
    """
    <div style='text-align:center; margin-top:2rem; color:#94a3b8; font-size:0.8rem;'>
        A.03 Build — Dashboard Restored • TradingView Chart • CH2 Options Chain • A.01 Enhancements Preserved
    </div>
    """,
    unsafe_allow_html=True,
)