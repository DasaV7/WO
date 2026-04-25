# ============================================================
#  WHEELOS — PERSONAL OPTIONS TRACKING TOOL
#  PART 1 — SQLITE ENGINE, SCHEMA, PERSISTENCE LAYER
# ============================================================

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import requests
import os

DB_PATH = "wheelos.db"

# ------------------------------------------------------------
#  CONNECT TO SQLITE
# ------------------------------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

conn = get_conn()

# ------------------------------------------------------------
#  AUTO-CREATE SCHEMA ON FIRST RUN
# ------------------------------------------------------------
def init_db():
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ownership (
            ticker TEXT PRIMARY KEY,
            owns_shares INTEGER DEFAULT 0
        );
    """)

    conn.execute("""
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
            assigned INTEGER DEFAULT 0
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS leaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            cost REAL,
            current_val REAL,
            contracts INTEGER,
            expiry TEXT,
            opened TEXT
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            ticker TEXT,
            type TEXT,
            action TEXT,
            profit REAL,
            note TEXT
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            timestamp TEXT,
            price REAL
        );
    """)

    conn.commit()

init_db()

# ------------------------------------------------------------
#  HELPER: RUN SQL QUERY
# ------------------------------------------------------------
def run_query(query, params=(), fetch=False, many=False):
    cur = conn.cursor()
    if many:
        cur.executemany(query, params)
    else:
        cur.execute(query, params)
    conn.commit()
    if fetch:
        return cur.fetchall()
    return None

# ------------------------------------------------------------
#  LOAD SESSION STATE FROM SQLITE
# ------------------------------------------------------------
def load_state_from_db():
    # Load tickers
    rows = run_query("SELECT symbol FROM tickers;", fetch=True)
    st.session_state.tickers = [r[0] for r in rows] if rows else ["TSLL", "SOXL", "TQQQ"]

    # Load ownership
    rows = run_query("SELECT ticker, owns_shares FROM ownership;", fetch=True)
    st.session_state.ownership = {r[0]: bool(r[1]) for r in rows}

    # Load trades
    rows = run_query("""
        SELECT id, ticker, type, strike, expiry, entry_premium, contracts,
               status, pnl, opened, closed_date, assigned
        FROM trades;
    """, fetch=True)

    st.session_state.trades = []
    for r in rows:
        st.session_state.trades.append({
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
            "assigned": bool(r[11])
        })

    # Load LEAPs
    rows = run_query("""
        SELECT id, ticker, cost, current_val, contracts, expiry, opened
        FROM leaps;
    """, fetch=True)

    st.session_state.leaps = []
    for r in rows:
        st.session_state.leaps.append({
            "id": r[0],
            "ticker": r[1],
            "cost": r[2],
            "current_val": r[3],
            "contracts": r[4],
            "expiry": r[5],
            "opened": r[6]
        })

    # Load journal
    rows = run_query("""
        SELECT date, ticker, type, action, profit, note
        FROM journal
        ORDER BY id DESC;
    """, fetch=True)

    st.session_state.journal = []
    for r in rows:
        st.session_state.journal.append({
            "date": r[0],
            "ticker": r[1],
            "type": r[2],
            "action": r[3],
            "profit": r[4],
            "note": r[5]
        })

    # Initialize market data container
    if "market_data" not in st.session_state:
        st.session_state.market_data = {}

    # Initialize VIX + econ events
    st.session_state.vix = None
    st.session_state.econ_events = []

    # Initialize capital + leap fund if missing
    st.session_state.capital = st.session_state.get("capital", 20000)
    st.session_state.leap_fund = st.session_state.get("leap_fund", 0.0)

load_state_from_db()

# ------------------------------------------------------------
#  SAVE FUNCTIONS (WRITE TO SQLITE)
# ------------------------------------------------------------
def save_ticker(symbol):
    run_query("INSERT OR IGNORE INTO tickers(symbol) VALUES (?);", (symbol,))

def save_ownership(ticker, owns):
    run_query("""
        INSERT INTO ownership(ticker, owns_shares)
        VALUES (?, ?)
        ON CONFLICT(ticker) DO UPDATE SET owns_shares=excluded.owns_shares;
    """, (ticker, int(owns)))

def save_trade(t):
    run_query("""
        INSERT INTO trades(ticker, type, strike, expiry, entry_premium,
                           contracts, status, pnl, opened, closed_date, assigned)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        t["ticker"], t["type"], t["strike"], t["expiry"], t["entry_premium"],
        t["contracts"], t["status"], t["pnl"], t["opened"], t.get("closed_date"),
        int(t.get("assigned", False))
    ))

def update_trade(t):
    run_query("""
        UPDATE trades
        SET status=?, pnl=?, closed_date=?, assigned=?
        WHERE id=?;
    """, (
        t["status"], t["pnl"], t.get("closed_date"), int(t.get("assigned", False)),
        t["id"]
    ))

def save_leap(l):
    run_query("""
        INSERT INTO leaps(ticker, cost, current_val, contracts, expiry, opened)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (
        l["ticker"], l["cost"], l["current_val"], l["contracts"],
        l["expiry"], l["opened"]
    ))

def update_leap(l):
    run_query("""
        UPDATE leaps
        SET cost=?, current_val=?, contracts=?
        WHERE id=?;
    """, (l["cost"], l["current_val"], l["contracts"], l["id"]))

def save_journal(entry):
    run_query("""
        INSERT INTO journal(date, ticker, type, action, profit, note)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (
        entry["date"], entry["ticker"], entry["type"],
        entry["action"], entry["profit"], entry["note"]
    ))

# ------------------------------------------------------------
#  TRADE HISTORY (H1) — ROW-BASED, ROLLING WINDOW OF 300
# ------------------------------------------------------------
def save_trade_history(trade_id, timestamp, price):
    run_query("""
        INSERT INTO trade_history(trade_id, timestamp, price)
        VALUES (?, ?, ?);
    """, (trade_id, timestamp, price))

    # Trim to last 300 rows
    run_query("""
        DELETE FROM trade_history
        WHERE id NOT IN (
            SELECT id FROM trade_history
            WHERE trade_id = ?
            ORDER BY id DESC
            LIMIT 300
        ) AND trade_id = ?;
    """, (trade_id, trade_id))

def load_trade_history(trade_id):
    rows = run_query("""
        SELECT timestamp, price
        FROM trade_history
        WHERE trade_id=?
        ORDER BY timestamp ASC;
    """, (trade_id,), fetch=True)

    return [{"timestamp": r[0], "price": r[1]} for r in rows]

# ============================================================
#  PART 2 — CONSTANTS, THEME, FINNHUB HELPERS, SAFE REFRESH
# ============================================================

# -------------------- PAGE CONFIG ---------------------------

st.set_page_config(
    page_title="WheelOS • Options Radar",
    page_icon="◈",
    layout="wide",
)

# -------------------- IOS / APPLE THEME ---------------------

APPLE_CSS = """
<style>
body {
    background-color: #FAFAFA;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
}
.block-container {
    padding-top: 3.5rem !important;
    padding-bottom: 2rem;
}
div.stButton > button {
    border-radius: 999px;
    border: none;
    padding: 0.5rem 1.4rem;
    font-weight: 600;
    transition: all 0.15s ease-in-out;
    box-shadow: 0 8px 18px rgba(0,0,0,0.04);
    color: #FFFFFF !important;
}
button[kind="primary"] {
    background: linear-gradient(135deg, #34C759, #30D158) !important;
    color: #FFFFFF !important;
}
button[kind="secondary"] {
    background: linear-gradient(135deg, #8E8E93, #AEAEB2) !important;
    color: #FFFFFF !important;
}
button[disabled] {
    opacity: 0.45 !important;
    cursor: not-allowed !important;
}
div.stButton > button:hover {
    transform: translateY(-1px) scale(1.01);
    box-shadow: 0 12px 26px rgba(0,0,0,0.08);
}
.card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 1.1rem 1.2rem;
    box-shadow: 0 14px 30px rgba(15,23,42,0.04);
    border: 1px solid rgba(148,163,184,0.18);
}
.metric-card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 0.9rem 1.1rem;
    box-shadow: 0 10px 24px rgba(15,23,42,0.03);
    border: 1px solid rgba(148,163,184,0.16);
}
.ticker-banner {
    width: 100%;
    padding: 0.65rem 1.0rem;
    border-radius: 14px;
    color: #FFFFFF;
    font-weight: 600;
    margin-bottom: 0.35rem;
    box-shadow: 0 6px 18px rgba(0,0,0,0.12);
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-sizing: border-box;
    font-size: 0.95rem;
}
.ticker-banner-red {
    background: #FF3B30;
}
.ticker-banner-green {
    background: #34C759;
}
.ticker-banner-gray {
    background: #8E8E93;
}
.ticker-banner-label {
    font-size: 0.8rem;
    opacity: 0.9;
}
</style>
"""
st.markdown(APPLE_CSS, unsafe_allow_html=True)

# -------------------- CONSTANTS -----------------------------

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

# -------------------- SESSION DEFAULTS ----------------------

if "finnhub_key" not in st.session_state:
    st.session_state.finnhub_key = ""

if "market_data" not in st.session_state:
    st.session_state.market_data = {}

if "vix" not in st.session_state:
    st.session_state.vix = None

if "econ_events" not in st.session_state:
    st.session_state.econ_events = []

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

# -------------------- FINNHUB HELPERS -----------------------

def _finnhub_get(path: str, params: dict | None = None):
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

# -------------------- SAFE BATCH UPDATE ---------------------

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

    # log price snapshots for open trades
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    for t in st.session_state.trades:
        if t.get("status") != "open":
            continue
        sym = t["ticker"]
        md = st.session_state.market_data.get(sym, {})
        price = md.get("price")
        if price is None:
            continue
        save_trade_history(t["id"], now_str, float(price))

    st.session_state.vix = fetch_vix()
    st.session_state.econ_events = fetch_economic_calendar()

# ============================================================
#  PART 3 — MAIN UI, DASHBOARD, WHEEL / CSP TAB WITH CHARTS
# ============================================================

# -------------------- TOP BAR & LAYOUT ----------------------

st.title("◈ WheelOS — Personal Options Tracking")

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
        value=int(st.session_state.get("capital", 20000)),
        step=1000,
    )
    st.session_state.leap_fund = st.number_input(
        "LEAP Fund ($)",
        min_value=0,
        value=int(st.session_state.get("leap_fund", 0)),
        step=1000,
    )

    if st.button("Safe Refresh Prices", type="primary"):
        now = time.time()
        if now - st.session_state.last_refresh < 60:
            st.warning("Safe Refresh is limited to once per minute.")
        else:
            st.session_state.last_refresh = now
            safe_batch_update(st.session_state.tickers)
            st.success("Market data refreshed.")

# -------------------- HEADER METRICS ------------------------

col_a, col_b, col_c, col_d = st.columns(4)

with col_a:
    total_pnl = sum(t["pnl"] for t in st.session_state.trades)
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

# -------------------- TABS ------------------------

tab1, tab2, tab3, tab4 = st.tabs(
    ["Wheel / CSP", "LEAPs", "Super Chart", "Journal"]
)

# ============================================================
#  TAB 1 — WHEEL / CSP
# ============================================================

with tab1:
    st.subheader("Wheel / CSP Tracker")

    # --- Ticker management ---
    st.markdown("#### Tracked Tickers")
    c1, c2 = st.columns([3, 1])
    with c1:
        new_sym = st.text_input("Add Ticker", placeholder="e.g. TSLL")
    with c2:
        if st.button("Add", key="add_ticker_btn"):
            sym = new_sym.strip().upper()
            if sym and sym not in st.session_state.tickers:
                st.session_state.tickers.append(sym)
                save_ticker(sym)
                st.success(f"Added {sym}")

    st.write(", ".join(st.session_state.tickers))

    st.markdown("---")

    # --- Ownership toggles ---
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

    # --- Log new CSP / CC trade ---
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
                "id": None,  # will be set by DB
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
            # reload trades to get ID
            load_state_from_db()
            st.success("Trade logged.")

    st.markdown("---")

    # --- Open positions with per-trade chart & table ---
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

                # --- Close at 50% button ---
                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    if st.button(
                        "Close at 50%",
                        key=f"close50_{t['id']}",
                        type="secondary",
                    ):
                        # 50% of premium, scaled by contracts * 100
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
                        st.success("Trade marked as assigned.")

                with col_b3:
                    if st.button(
                        "Manual Close",
                        key=f"manual_close_{t['id']}",
                        type="secondary",
                    ):
                        manual_pnl = st.number_input(
                            "Manual P&L ($)",
                            key=f"manual_pnl_{t['id']}",
                            value=0.0,
                        )
                        confirm = st.button(
                            "Confirm Manual Close",
                            key=f"confirm_manual_{t['id']}",
                            type="primary",
                        )
                        if confirm:
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

                # --- Price action chart & table for this trade ---
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
#  PART 4 — LEAPs, SUPER CHART, JOURNAL, CALENDAR, FOOTER
# ============================================================

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
                "id": None,
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
                df_econ[["time", "country", "event", "impact", "actual", "forecast", "previous"]],
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
#  FOOTER
# ============================================================

st.markdown("---")
st.caption(
    "WheelOS — Personal options tracking and journaling tool. "
    "All data and calculations are for personal record‑keeping only."
)