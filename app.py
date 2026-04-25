# app.py

import streamlit as st
import sqlite3
import requests
import pandas as pd
import time
import json
from datetime import datetime, date, timedelta
from math import sqrt

# ============================================================
#  CONFIG & CONSTANTS
# ============================================================

DB_PATH = "wheelos.db"
SAFE_REFRESH_MIN_INTERVAL = 60  # seconds
MAX_HISTORY_ROWS_PER_TRADE = 300

DEFAULT_TICKERS = ["TSLL", "SOXL", "TQQQ"]
DEFAULT_CAPITAL = 20000
DEFAULT_LEAP_FUND = 0

# Mapping leveraged tickers to underlyings for charts
MAIN_TICKER_MAP = {
    "TSLL": "TSLA",
    "TQQQ": "QQQ",
    "SOXL": "SOXX",
    "NVDL": "NVDA",
}

# ============================================================
#  DB HELPERS
# ============================================================

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ownership (
            ticker TEXT PRIMARY KEY,
            owns_shares INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            type TEXT,
            strike REAL,
            expiry TEXT,
            entry_premium REAL,
            contracts INTEGER,
            status TEXT,
            pnl REAL,
            opened TEXT,
            closed_date TEXT,
            assigned INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            cost REAL,
            current_val REAL,
            contracts INTEGER,
            expiry TEXT,
            opened TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            ticker TEXT,
            type TEXT,
            action TEXT,
            profit REAL,
            note TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            timestamp TEXT,
            price REAL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return default
    return row[0]


def set_setting(key, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()
    conn.close()


def load_tickers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT symbol FROM tickers ORDER BY symbol")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def save_ticker(symbol):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO tickers(symbol) VALUES(?)",
        (symbol,),
    )
    conn.commit()
    conn.close()


def load_ownership():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT ticker, owns_shares FROM ownership")
    rows = cur.fetchall()
    conn.close()
    return {r[0]: bool(r[1]) for r in rows}


def save_ownership(ticker, owns):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ownership(ticker, owns_shares)
        VALUES(?, ?)
        ON CONFLICT(ticker) DO UPDATE SET owns_shares = excluded.owns_shares
        """,
        (ticker, int(owns)),
    )
    conn.commit()
    conn.close()


def load_trades():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, ticker, type, strike, expiry, entry_premium,
               contracts, status, pnl, opened, closed_date, assigned
        FROM trades
        ORDER BY opened DESC, id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    trades = []
    for r in rows:
        trades.append(
            {
                "id": r[0],
                "ticker": r[1],
                "type": r[2],
                "strike": r[3],
                "expiry": r[4],
                "entry_premium": r[5],
                "contracts": r[6],
                "status": r[7],
                "pnl": r[8],
                "opened": r[9],
                "closed_date": r[10],
                "assigned": bool(r[11]),
            }
        )
    return trades


def save_trade(trade):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO trades(
            ticker, type, strike, expiry, entry_premium,
            contracts, status, pnl, opened, closed_date, assigned
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            trade["ticker"],
            trade["type"],
            trade["strike"],
            trade["expiry"],
            trade["entry_premium"],
            trade["contracts"],
            trade["status"],
            trade["pnl"],
            trade["opened"],
            trade["closed_date"],
            int(trade["assigned"]),
        ),
    )
    conn.commit()
    conn.close()


def update_trade(trade):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE trades
        SET ticker = ?, type = ?, strike = ?, expiry = ?,
            entry_premium = ?, contracts = ?, status = ?,
            pnl = ?, opened = ?, closed_date = ?, assigned = ?
        WHERE id = ?
        """,
        (
            trade["ticker"],
            trade["type"],
            trade["strike"],
            trade["expiry"],
            trade["entry_premium"],
            trade["contracts"],
            trade["status"],
            trade["pnl"],
            trade["opened"],
            trade["closed_date"],
            int(trade["assigned"]),
            trade["id"],
        ),
    )
    conn.commit()
    conn.close()


def load_leaps():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, ticker, cost, current_val, contracts, expiry, opened
        FROM leaps
        ORDER BY opened DESC, id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    leaps = []
    for r in rows:
        leaps.append(
            {
                "id": r[0],
                "ticker": r[1],
                "cost": r[2],
                "current_val": r[3],
                "contracts": r[4],
                "expiry": r[5],
                "opened": r[6],
            }
        )
    return leaps


def save_leap(leap):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO leaps(
            ticker, cost, current_val, contracts, expiry, opened
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            leap["ticker"],
            leap["cost"],
            leap["current_val"],
            leap["contracts"],
            leap["expiry"],
            leap["opened"],
        ),
    )
    conn.commit()
    conn.close()


def load_journal():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, date, ticker, type, action, profit, note
        FROM journal
        ORDER BY date DESC, id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    journal = []
    for r in rows:
        journal.append(
            {
                "id": r[0],
                "date": r[1],
                "ticker": r[2],
                "type": r[3],
                "action": r[4],
                "profit": r[5],
                "note": r[6],
            }
        )
    return journal


def save_journal(entry):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO journal(date, ticker, type, action, profit, note)
        VALUES(?,?,?,?,?,?)
        """,
        (
            entry["date"],
            entry["ticker"],
            entry["type"],
            entry["action"],
            entry["profit"],
            entry.get("note", ""),
        ),
    )
    conn.commit()
    conn.close()


def insert_trade_history(trade_id, price, ts=None):
    if ts is None:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO trade_history(trade_id, timestamp, price)
        VALUES(?,?,?)
        """,
        (trade_id, ts, price),
    )
    conn.commit()
    conn.close()


def trim_trade_history(trade_id, max_rows=MAX_HISTORY_ROWS_PER_TRADE):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id FROM trade_history
        WHERE trade_id = ?
        ORDER BY timestamp DESC, id DESC
        LIMIT -1 OFFSET ?
        """,
        (trade_id, max_rows),
    )
    rows = cur.fetchall()
    if rows:
        ids_to_delete = [r[0] for r in rows]
        cur.execute(
            f"DELETE FROM trade_history WHERE id IN ({','.join('?'*len(ids_to_delete))})",
            ids_to_delete,
        )
    conn.commit()
    conn.close()


def load_trade_history(trade_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT timestamp, price
        FROM trade_history
        WHERE trade_id = ?
        ORDER BY timestamp ASC, id ASC
        """,
        (trade_id,),
    )
    rows = cur.fetchall()
    conn.close()
    history = []
    for r in rows:
        history.append({"timestamp": r[0], "price": r[1]})
    return history


# ============================================================
#  VERSIONING HELPERS
# ============================================================

def parse_version(ver_str):
    # "A.05" -> ("A", 5)
    try:
        letter, num = ver_str.split(".")
        return letter, int(num)
    except Exception:
        return "A", 1


def format_version(letter, num):
    return f"{letter}.{num:02d}"


def increment_version(ver_str):
    letter, num = parse_version(ver_str)
    num += 1
    return format_version(letter, num)


def next_baseline_version(ver_str):
    letter, _ = parse_version(ver_str)
    new_letter = chr(ord(letter) + 1)
    return format_version(new_letter, 1)


def load_version_info():
    ver = get_setting("app_version", None)
    notes_json = get_setting("version_notes", None)

    if ver is None:
        ver = "A.01"
        notes = {"A.01": "Initial baseline with live status tracking and iOS-style UI."}
        set_setting("app_version", ver)
        set_setting("version_notes", json.dumps(notes))
        return ver, notes

    if notes_json is None:
        notes = {ver: "Initial version (notes missing, auto-created)."}
        set_setting("version_notes", json.dumps(notes))
        return ver, notes

    try:
        notes = json.loads(notes_json)
        if not isinstance(notes, dict):
            notes = {ver: "Version notes reset due to invalid format."}
    except Exception:
        notes = {ver: "Version notes reset due to JSON error."}

    return ver, notes


def save_version_info(version, notes_dict):
    set_setting("app_version", version)
    set_setting("version_notes", json.dumps(notes_dict))


# ============================================================
#  FINNHUB HELPERS
# ============================================================

def _finnhub_get(path, params=None):
    if params is None:
        params = {}
    token = st.session_state.get("finnhub_key", "")
    if not token:
        return None
    base = "https://finnhub.io/api/v1"
    params["token"] = token
    try:
        resp = requests.get(base + path, params=params, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def fetch_quote(symbol):
    return _finnhub_get("/quote", {"symbol": symbol})


def fetch_candles(symbol, days=60):
    now = int(time.time())
    frm = now - days * 24 * 60 * 60
    data = _finnhub_get(
        "/stock/candle",
        {"symbol": symbol, "resolution": "D", "from": frm, "to": now},
    )
    if not data or data.get("s") != "ok":
        return None
    df = pd.DataFrame(
        {
            "time": [datetime.fromtimestamp(t) for t in data["t"]],
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
        }
    )
    return df


def calc_rv(df):
    if df is None or df.empty:
        return None
    closes = df["close"].astype(float)
    rets = closes.pct_change().dropna()
    if len(rets) < 2:
        return None
    vol = rets.std() * sqrt(252) * 100
    return float(vol)


def fetch_vix():
    q = fetch_quote("^VIX")
    if not q:
        return None
    return q.get("c")


def fetch_economic_calendar():
    today = date.today()
    to_date = today + timedelta(days=7)
    data = _finnhub_get(
        "/calendar/economic",
        {"from": today.isoformat(), "to": to_date.isoformat()},
    )
    if not data or "economicCalendar" not in data:
        return []
    events = []
    for ev in data["economicCalendar"]:
        impact = ev.get("impact")
        if impact not in ("high", "medium", "High", "Medium"):
            continue
        events.append(
            {
                "time": ev.get("time", ""),
                "country": ev.get("country", ""),
                "event": ev.get("event", ""),
                "impact": ev.get("impact", ""),
                "actual": ev.get("actual", ""),
                "forecast": ev.get("forecast", ""),
                "previous": ev.get("previous", ""),
            }
        )
    return events


# ============================================================
#  STATE LOADING
# ============================================================

def load_state_from_db():
    st.session_state.tickers = load_tickers()
    if not st.session_state.tickers:
        for sym in DEFAULT_TICKERS:
            save_ticker(sym)
        st.session_state.tickers = load_tickers()

    st.session_state.ownership = load_ownership()
    st.session_state.trades = load_trades()
    st.session_state.leaps = load_leaps()
    st.session_state.journal = load_journal()

    if "market_data" not in st.session_state:
        st.session_state.market_data = {}
    if "vix" not in st.session_state:
        st.session_state.vix = None
    if "econ_events" not in st.session_state:
        st.session_state.econ_events = []
    if "capital" not in st.session_state:
        st.session_state.capital = DEFAULT_CAPITAL
    if "leap_fund" not in st.session_state:
        st.session_state.leap_fund = DEFAULT_LEAP_FUND
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = 0.0


# ============================================================
#  LIVE STATUS HELPERS
# ============================================================

def compute_option_unrealized(trade, price):
    if price is None:
        return None, None

    entry = trade["entry_premium"]
    contracts = trade["contracts"]
    strike = trade["strike"]
    mult = contracts * 100

    if "Put" in trade["type"]:
        intrinsic = max(0.0, strike - price)
    else:
        intrinsic = max(0.0, price - strike)

    unrealized = entry * mult - intrinsic * mult
    if entry <= 0:
        return unrealized, None
    percent = unrealized / (entry * mult)
    return unrealized, percent


def format_option_status(unrealized, percent):
    if unrealized is None or percent is None:
        return "⚪ Status unavailable (no price data)", "gray"

    pct_str = f"{percent*100:.1f}%"
    if percent >= 0.5:
        return f"🟢 Target reached (≥50% profit) — Unrealized +${unrealized:,.2f} ({pct_str})", "green"
    elif percent >= 0:
        return f"🟢 Profit +${unrealized:,.2f} ({pct_str})", "green"
    else:
        return f"🔴 Loss ${unrealized:,.2f} ({pct_str})", "red"


def compute_leap_status(leap):
    cost = leap["cost"]
    current = leap["current_val"]
    contracts = leap["contracts"]
    mult = contracts * 100

    if cost <= 0:
        return None, None, "⚪ LEAP status unavailable (cost ≤ 0)", "gray"

    unrealized = (current - cost) * mult
    percent = (current - cost) / cost
    pct_str = f"{percent*100:.1f}%"

    if percent >= 0.5:
        text = f"🟢 LEAP target reached (≥50% profit) — Unrealized +${unrealized:,.2f} ({pct_str})"
        color = "green"
    elif percent >= 0:
        text = f"🟢 LEAP profit +${unrealized:,.2f} ({pct_str})"
        color = "green"
    else:
        text = f"🔴 LEAP loss ${unrealized:,.2f} ({pct_str})"
        color = "red"

    return unrealized, percent, text, color


# ============================================================
#  SAFE REFRESH
# ============================================================

def safe_batch_update(tickers):
    now = time.time()
    if now - st.session_state.last_refresh < SAFE_REFRESH_MIN_INTERVAL:
        st.warning("Safe Refresh is limited to once per minute.")
        return

    st.session_state.last_refresh = now

    market_data = st.session_state.get("market_data", {})
    for sym in tickers:
        main_sym = MAIN_TICKER_MAP.get(sym, sym)
        q = fetch_quote(main_sym)
        if q:
            price = q.get("c")
            prev_close = q.get("pc")
            if price is not None and prev_close not in (None, 0):
                chg = (price - prev_close) / prev_close * 100
            else:
                chg = None
        else:
            price = None
            chg = None

        df = fetch_candles(main_sym)
        rv = calc_rv(df) if df is not None else None

        market_data[sym] = {
            "price": price,
            "change": chg,
            "rv": rv,
        }

    st.session_state.market_data = market_data

    # Update trade history for open trades
    for t in st.session_state.trades:
        if t["status"] != "open":
            continue
        sym = t["ticker"]
        md = market_data.get(sym, {})
        price = md.get("price")
        if price is None:
            continue
        insert_trade_history(t["id"], price)
        trim_trade_history(t["id"], MAX_HISTORY_ROWS_PER_TRADE)

    st.session_state.vix = fetch_vix()
    st.session_state.econ_events = fetch_economic_calendar()
    st.success("Market data refreshed.")


# ============================================================
#  STREAMLIT SETUP & STYLING
# ============================================================

st.set_page_config(
    page_title="WheelOS • Options Radar",
    page_icon="◈",
    layout="wide",
)

init_db()
load_state_from_db()
app_version, version_notes = load_version_info()

# iOS-like styling
st.markdown(
    """
    <style>
    body, .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
        background-color: #f5f5f7;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
    }
    .stMetric {
        background: #ffffff;
        padding: 0.75rem 1rem;
        border-radius: 0.75rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 999px;
        padding: 0.35rem 0.9rem;
        background-color: #f2f2f7;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.06);
    }
    .status-green {
        color: #0a7f3f;
        font-weight: 500;
    }
    .status-red {
        color: #b00020;
        font-weight: 500;
    }
    .status-gray {
        color: #6e6e73;
    }
    .version-footer {
        font-size: 0.8rem;
        color: #6e6e73;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
#  SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("### Settings")

    st.session_state.finnhub_key = st.text_input(
        "Finnhub API Key",
        type="password",
        value=st.session_state.get("finnhub_key", ""),
        help="Used only to fetch market data for your personal tracking.",
    )

    st.session_state.capital = st.number_input(
        "Wheel Capital ($)",
        min_value=0,
        value=int(st.session_state.get("capital", DEFAULT_CAPITAL)),
        step=1000,
    )

    st.session_state.leap_fund = st.number_input(
        "LEAP Fund ($)",
        min_value=0,
        value=int(st.session_state.get("leap_fund", DEFAULT_LEAP_FUND)),
        step=1000,
    )

    if st.button("Safe Refresh Prices", type="primary"):
        safe_batch_update(st.session_state.tickers)

    st.markdown("---")
    st.markdown("#### Version Controls")

    st.caption(f"Current Version: **{app_version}**")

    with st.form("version_increment_form", clear_on_submit=True):
        st.write("Increment Version (A.01 → A.02)")
        inc_note = st.text_input(
            "One-line summary for new version",
            placeholder="Describe what changed in this version...",
        )
        inc_submit = st.form_submit_button("Increment Version")
        if inc_submit:
            if not inc_note.strip():
                st.warning("Please enter a short summary for this version.")
            else:
                new_ver = increment_version(app_version)
                version_notes[new_ver] = inc_note.strip()
                app_version = new_ver
                save_version_info(app_version, version_notes)
                st.success(f"Version incremented to {app_version}")

    with st.form("version_baseline_form", clear_on_submit=True):
        st.write("New Baseline Version (A.05 → B.01)")
        base_note = st.text_input(
            "One-line summary for new baseline version",
            placeholder="Describe what changed in this baseline...",
        )
        base_submit = st.form_submit_button("New Baseline Version")
        if base_submit:
            if not base_note.strip():
                st.warning("Please enter a short summary for this baseline.")
            else:
                new_ver = next_baseline_version(app_version)
                version_notes[new_ver] = base_note.strip()
                app_version = new_ver
                save_version_info(app_version, version_notes)
                st.success(f"New baseline version set to {app_version}")

# ============================================================
#  HEADER METRICS
# ============================================================

st.title("◈ WheelOS — Personal Options Tracking")

col_a, col_b, col_c, col_d = st.columns(4)

with col_a:
    total_pnl = sum(t["pnl"] for t in st.session_state.trades if t["status"] == "closed")
    st.metric("Realized P&L", f"${total_pnl:,.2f}")

with col_b:
    open_trades = [t for t in st.session_state.trades if t["status"] == "open"]
    st.metric("Open Positions", len(open_trades))

with col_c:
    st.metric("Wheel Capital", f"${st.session_state.capital:,.0f}")

with col_d:
    if st.session_state.vix is not None:
        st.metric("VIX", f"{st.session_state.vix:.2f}")
    else:
        st.metric("VIX", "—")

# ============================================================
#  TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Wheel / CSP", "LEAPs", "Super Chart", "Journal", "Settings"]
)

# ============================================================
#  TAB 1 — WHEEL / CSP
# ============================================================

with tab1:
    st.subheader("Wheel / CSP Tracker")

    st.markdown("#### Tracked Tickers")
    c1, c2 = st.columns([3, 1])
    with c1:
        new_sym = st.text_input("Add Ticker", placeholder="e.g. TSLL")
    with c2:
        if st.button("Add", key="add_ticker_btn"):
            sym = new_sym.strip().upper()
            if sym and sym not in st.session_state.tickers:
                save_ticker(sym)
                load_state_from_db()
                st.success(f"Added {sym}")
            elif sym in st.session_state.tickers:
                st.info(f"{sym} is already tracked.")

    st.write(", ".join(st.session_state.tickers))

    st.markdown("---")

    st.markdown("#### Ownership")
    for sym in st.session_state.tickers:
        owns = st.checkbox(
            f"Own shares of {sym} (for covered calls)",
            value=st.session_state.ownership.get(sym, False),
            key=f"own_{sym}",
        )
        st.session_state.ownership[sym] = owns
        save_ownership(sym, owns)

    st.markdown("---")

    st.markdown("#### Log New Trade")

    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        trade_ticker = st.selectbox(
            "Ticker",
            options=st.session_state.tickers,
            key="trade_ticker",
        )
    with col_t2:
        trade_type = st.selectbox(
            "Type",
            options=["Cash-Secured Put", "Covered Call"],
            key="trade_type",
        )
    with col_t3:
        contracts = st.number_input(
            "Contracts",
            min_value=1,
            value=1,
            step=1,
            key="trade_contracts",
        )

    col_t4, col_t5, col_t6 = st.columns(3)
    with col_t4:
        strike = st.number_input("Strike", min_value=0.0, step=0.5)
    with col_t5:
        entry_premium = st.number_input(
            "Entry Premium (per contract)",
            min_value=0.0,
            step=0.05,
        )
    with col_t6:
        expiry = st.date_input("Expiry")

    if st.button("Add Trade", type="primary", key="add_trade_btn"):
        if strike <= 0 or entry_premium <= 0:
            st.error("Strike and premium must be positive.")
        else:
            new_trade = {
                "ticker": trade_ticker,
                "type": "CSP Put" if "Put" in trade_type else "Covered Call",
                "strike": float(strike),
                "expiry": expiry.isoformat(),
                "entry_premium": float(entry_premium),
                "contracts": int(contracts),
                "status": "open",
                "pnl": 0.0,
                "opened": datetime.utcnow().strftime("%Y-%m-%d"),
                "closed_date": None,
                "assigned": False,
            }
            save_trade(new_trade)
            load_state_from_db()
            st.success("Trade logged.")

    st.markdown("---")

    st.markdown("### Open Wheel Positions")

    open_trades = [t for t in st.session_state.trades if t["status"] == "open"]
    if not open_trades:
        st.info("No open wheel positions.")
    else:
        for t in open_trades:
            label = f"{t['ticker']} {t['type']} @ ${t['strike']} (exp {t['expiry']})"
            with st.expander(label, expanded=False):
                col_o1, col_o2, col_o3 = st.columns(3)
                with col_o1:
                    st.write(f"**Contracts:** {t['contracts']}")
                    st.write(f"**Entry Premium:** ${t['entry_premium']:.2f}")
                    st.write(f"**Strike:** ${t['strike']:.2f}")
                with col_o2:
                    md = st.session_state.market_data.get(t["ticker"], {})
                    price = md.get("price")
                    chg = md.get("change")
                    rv = md.get("rv")
                    st.write(f"**Underlying:** {t['ticker']}")
                    st.write(f"**Price:** {price if price is not None else '—'}")
                    st.write(f"**Change:** {f'{chg:.2f}%' if chg is not None else '—'}")
                    st.write(f"**RV:** {f'{rv:.1f}%' if rv is not None else '—'}")
                with col_o3:
                    st.write(f"**Opened:** {t['opened']}")
                    if t.get("closed_date"):
                        st.write(f"**Closed:** {t['closed_date']}")
                    st.write(f"**Realized P&L:** ${t['pnl']:.2f}")

                st.markdown("---")

                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    if st.button(
                        "Close at 50%",
                        key=f"close50_{t['id']}",
                        type="secondary",
                    ):
                        realized = t["entry_premium"] * 0.5 * t["contracts"] * 100
                        t["pnl"] = realized
                        t["status"] = "closed"
                        t["closed_date"] = datetime.utcnow().strftime("%Y-%m-%d")
                        update_trade(t)
                        save_journal(
                            {
                                "date": t["closed_date"],
                                "ticker": t["ticker"],
                                "type": t["type"],
                                "action": "Closed 50%",
                                "profit": realized,
                                "note": "",
                            }
                        )
                        load_state_from_db()
                        st.success("Trade closed at 50% target.")

                with col_b2:
                    if st.button(
                        "Mark Assigned",
                        key=f"assign_{t['id']}",
                        type="secondary",
                    ):
                        t["assigned"] = True
                        t["status"] = "closed"
                        t["closed_date"] = datetime.utcnow().strftime("%Y-%m-%d")
                        update_trade(t)

                        # Flip ownership based on type
                        owns = st.session_state.ownership.get(t["ticker"], False)
                        if "Put" in t["type"]:
                            # CSP assigned → now own shares
                            owns = True
                        else:
                            # CC assigned → shares called away
                            owns = False
                        st.session_state.ownership[t["ticker"]] = owns
                        save_ownership(t["ticker"], owns)

                        save_journal(
                            {
                                "date": t["closed_date"],
                                "ticker": t["ticker"],
                                "type": t["type"],
                                "action": "Assigned",
                                "profit": t["pnl"],
                                "note": "",
                            }
                        )
                        load_state_from_db()
                        st.success("Trade marked as assigned and ownership updated.")

                with col_b3:
                    manual_pnl = st.number_input(
                        "Manual P&L ($)",
                        key=f"manual_pnl_{t['id']}",
                        value=0.0,
                    )
                    if st.button(
                        "Manual Close",
                        key=f"manual_close_{t['id']}",
                        type="secondary",
                    ):
                        t["pnl"] = manual_pnl
                        t["status"] = "closed"
                        t["closed_date"] = datetime.utcnow().strftime("%Y-%m-%d")
                        update_trade(t)
                        save_journal(
                            {
                                "date": t["closed_date"],
                                "ticker": t["ticker"],
                                "type": t["type"],
                                "action": "Manual Close",
                                "profit": manual_pnl,
                                "note": "",
                            }
                        )
                        load_state_from_db()
                        st.success("Trade manually closed.")

                st.markdown("---")

                # Live status (bottom)
                md = st.session_state.market_data.get(t["ticker"], {})
                price = md.get("price")
                unrealized, percent = compute_option_unrealized(t, price)
                status_text, status_color = format_option_status(unrealized, percent)
                css_class = (
                    "status-green"
                    if status_color == "green"
                    else "status-red"
                    if status_color == "red"
                    else "status-gray"
                )
                st.markdown(
                    f'<div class="{css_class}">{status_text}</div>',
                    unsafe_allow_html=True,
                )

                st.markdown("---")

                history = load_trade_history(t["id"])
                if history:
                    st.markdown("**Price Action While Trade Is Open**")
                    df_hist = pd.DataFrame(history)
                    df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"])

                    st.line_chart(
                        df_hist.set_index("timestamp")["price"],
                        height=180,
                    )

                    st.dataframe(
                        df_hist.sort_values("timestamp", ascending=False).head(20),
                        use_container_width=True,
                        height=220,
                    )
                else:
                    st.caption(
                        "No price history yet — run Safe Refresh to start tracking this trade."
                    )

# ============================================================
#  TAB 2 — LEAPs
# ============================================================

with tab2:
    st.subheader("LEAPs Tracker")

    st.markdown("#### Add LEAP Position")
    l1, l2, l3 = st.columns(3)
    with l1:
        leap_ticker = st.selectbox(
            "Ticker",
            options=st.session_state.tickers,
            key="leap_ticker",
        )
    with l2:
        leap_contracts = st.number_input(
            "Contracts",
            min_value=1,
            value=1,
            step=1,
            key="leap_contracts",
        )
    with l3:
        leap_expiry = st.date_input("Expiry", key="leap_expiry")

    l4, l5 = st.columns(2)
    with l4:
        leap_cost = st.number_input(
            "Cost (per contract)",
            min_value=0.0,
            step=0.05,
            key="leap_cost",
        )
    with l5:
        leap_current_val = st.number_input(
            "Current Value (per contract)",
            min_value=0.0,
            step=0.05,
            key="leap_current_val",
        )

    if st.button("Add LEAP", type="primary", key="add_leap_btn"):
        if leap_cost <= 0:
            st.error("Cost must be positive.")
        else:
            new_leap = {
                "ticker": leap_ticker,
                "cost": float(leap_cost),
                "current_val": float(leap_current_val),
                "contracts": int(leap_contracts),
                "expiry": leap_expiry.isoformat(),
                "opened": datetime.utcnow().strftime("%Y-%m-%d"),
            }
            save_leap(new_leap)
            load_state_from_db()
            st.success("LEAP position added.")

    st.markdown("---")

    st.markdown("### Open LEAP Positions")
    if not st.session_state.leaps:
        st.info("No LEAP positions logged.")
    else:
        rows = []
        for l in st.session_state.leaps:
            invested = l["cost"] * l["contracts"] * 100
            current = l["current_val"] * l["contracts"] * 100
            pnl = current - invested
            rows.append(
                {
                    "Ticker": l["ticker"],
                    "Contracts": l["contracts"],
                    "Expiry": l["expiry"],
                    "Cost/Contract": l["cost"],
                    "Current/Contract": l["current_val"],
                    "Invested ($)": invested,
                    "Current ($)": current,
                    "P&L ($)": pnl,
                }
            )
        df_leaps = pd.DataFrame(rows)
        st.dataframe(df_leaps, use_container_width=True)

        st.markdown("---")
        st.markdown("#### LEAP Status")
        for l in st.session_state.leaps:
            unrealized, percent, text, color = compute_leap_status(l)
            css_class = (
                "status-green"
                if color == "green"
                else "status-red"
                if color == "red"
                else "status-gray"
            )
            st.markdown(
                f'<div class="{css_class}">{l["ticker"]}: {text}</div>',
                unsafe_allow_html=True,
            )

# ============================================================
#  TAB 3 — SUPER CHART
# ============================================================

with tab3:
    st.subheader("Super Chart")

    if not st.session_state.tickers:
        st.info("Add at least one ticker to view charts.")
    else:
        sc1, sc2 = st.columns([2, 1])
        with sc1:
            chart_ticker = st.selectbox(
                "Chart Ticker",
                options=st.session_state.tickers,
                key="chart_ticker",
            )
        with sc2:
            main_sym = MAIN_TICKER_MAP.get(chart_ticker, chart_ticker)
            st.caption(f"Underlying used for data: **{main_sym}**")

        df = fetch_candles(main_sym)
        if df is None or df.empty:
            st.warning("No candle data available for this symbol.")
        else:
            st.line_chart(
                df.set_index("time")["close"],
                height=260,
            )
            rv = calc_rv(df)
            if rv is not None:
                st.caption(f"Realized Volatility (approx): **{rv:.1f}%**")

        st.markdown("---")
        st.markdown("#### Economic Calendar (High / Medium Impact)")
        if st.session_state.econ_events:
            df_econ = pd.DataFrame(st.session_state.econ_events)
            st.dataframe(
                df_econ[
                    [
                        "time",
                        "country",
                        "event",
                        "impact",
                        "actual",
                        "forecast",
                        "previous",
                    ]
                ],
                use_container_width=True,
                height=260,
            )
        else:
            st.caption("No upcoming high/medium impact events loaded yet. Run Safe Refresh.")

# ============================================================
#  TAB 4 — JOURNAL
# ============================================================

with tab4:
    st.subheader("Trade Journal")

    if not st.session_state.journal:
        st.info("No journal entries yet. Closing trades will add entries here.")
    else:
        df_j = pd.DataFrame(st.session_state.journal)
        st.dataframe(df_j, use_container_width=True, height=320)

        csv = df_j.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Journal as CSV",
            data=csv,
            file_name="wheelos_journal.csv",
            mime="text/csv",
        )

# ============================================================
#  TAB 5 — SETTINGS (DETAIL)
# ============================================================

with tab5:
    st.subheader("App Settings & Version Info")

    st.markdown("### App Version")
    st.write(f"**Current Version:** {app_version}")

    st.markdown("#### Version Notes (Newest First)")
    if version_notes:
        # sort newest first by version string order (approx)
        # we sort by letter then number descending
        def sort_key(item):
            v = item[0]
            letter, num = parse_version(v)
            return (ord(letter), num)

        for ver, note in sorted(
            version_notes.items(), key=sort_key, reverse=True
        ):
            st.write(f"- **{ver}** — {note}")
    else:
        st.caption("No version notes stored yet.")

    st.markdown("---")
    st.markdown("### Data Notes")
    st.caption(
        "All data is stored locally in a SQLite database (`wheelos.db`). "
        "This app is for personal tracking and journaling only."
    )

# ============================================================
#  FOOTER
# ============================================================

st.markdown("---")
latest_note = version_notes.get(app_version, "")
footer_text = f"WheelOS — Personal options tracking and journaling tool. Version {app_version}"
if latest_note:
    footer_text += f" • {latest_note}"
st.markdown(f'<div class="version-footer">{footer_text}</div>', unsafe_allow_html=True)
