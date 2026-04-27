# WheelOS app.py
# Version: A.06
# Created: 2026-04-26T20:40:00 PDT
# Single-file Streamlit application for personal options tracking (WheelOS)
# - Consolidated options snapshot
# - Finnhub + Yahoo options fallback
# - Safe refresh, RV, trade history, journal, versioning
# - Options debug logging
# - House money simulation feature (A.06)
# ------------------------------------------------------------------------------

import streamlit as st
import sqlite3
import requests
import pandas as pd
import time
import json
import datetime
from typing import Optional, Dict, Any, List
import math
import html

# ---------------------------
# Constants and Config
# ---------------------------
DB_PATH = "wheelos.db"
DEFAULT_VERSION = "A.06"
CALLS_PER_MIN_LIMIT = 50
TRADE_HISTORY_MAX = 300
YAHOO_OPTIONS_BASE = "https://query1.finance.yahoo.com/v7/finance/options"

# ---------------------------
# Utilities
# ---------------------------
def now_iso():
    return datetime.datetime.utcnow().isoformat()

def parse_date(s):
    try:
        if s is None:
            return None
        if isinstance(s, (int, float)):
            return datetime.datetime.utcfromtimestamp(int(s)).date()
        if isinstance(s, datetime.date):
            return s
        if isinstance(s, datetime.datetime):
            return s.date()
        try:
            return datetime.datetime.fromisoformat(str(s)).date()
        except Exception:
            return datetime.datetime.strptime(str(s), "%Y-%m-%d").date()
    except Exception:
        return None

def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def percent_str(v):
    try:
        return f"{v*100:.1f}%"
    except Exception:
        return "0.0%"

def nearest(items, key, target):
    if not items:
        return None
    return min(items, key=lambda x: abs((x.get(key, 0) or 0) - (target or 0)))

# ---------------------------
# Database Layer
# ---------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tickers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ownership (
        ticker TEXT PRIMARY KEY,
        owns_shares INTEGER DEFAULT 0
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        type TEXT,
        strike REAL,
        expiry TEXT,
        entry_premium REAL,
        contracts INTEGER,
        status TEXT,
        pnl REAL DEFAULT 0,
        opened TEXT,
        closed_date TEXT,
        assigned INTEGER DEFAULT 0
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leaps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        cost REAL,
        current_val REAL,
        contracts INTEGER,
        expiry TEXT,
        opened TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS journal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        ticker TEXT,
        type TEXT,
        action TEXT,
        profit REAL,
        note TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id INTEGER,
        timestamp TEXT,
        price REAL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    conn.commit()
    # Ensure versioning keys exist
    cur.execute("SELECT value FROM settings WHERE key='app_version'")
    if cur.fetchone() is None:
        cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("app_version", DEFAULT_VERSION))
    cur.execute("SELECT value FROM settings WHERE key='version_notes'")
    if cur.fetchone() is None:
        cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("version_notes", json.dumps({DEFAULT_VERSION: {"note": "Initial baseline", "timestamp": now_iso()}})))
    # Ensure build timestamp exists (used to display near version)
    cur.execute("SELECT value FROM settings WHERE key='app_build_timestamp'")
    if cur.fetchone() is None:
        cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("app_build_timestamp", now_iso()))
    # Ensure house_money and simulate_withdrawal defaults
    cur.execute("SELECT value FROM settings WHERE key='house_money'")
    if cur.fetchone() is None:
        cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("house_money", "0.0"))
    cur.execute("SELECT value FROM settings WHERE key='simulate_withdrawal'")
    if cur.fetchone() is None:
        cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("simulate_withdrawal", "0"))
    conn.commit()
    conn.close()

def db_get_setting(key, default=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["value"]
    return default

def db_set_setting(key, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
    conn.commit()
    conn.close()

def db_add_ticker(symbol):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO tickers(symbol) VALUES(?)", (symbol.upper(),))
    conn.commit()
    conn.close()

def db_list_tickers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickers ORDER BY symbol")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_set_ownership(ticker, owns):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO ownership(ticker, owns_shares) VALUES(?,?)", (ticker.upper(), 1 if owns else 0))
    conn.commit()
    conn.close()

def db_get_ownership(ticker):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT owns_shares FROM ownership WHERE ticker=?", (ticker.upper(),))
    row = cur.fetchone()
    conn.close()
    if row:
        return bool(row["owns_shares"])
    return False

def db_add_trade(ticker, ttype, strike, expiry, entry_premium, contracts):
    conn = get_conn()
    cur = conn.cursor()
    opened = now_iso()
    cur.execute("""
    INSERT INTO trades(ticker,type,strike,expiry,entry_premium,contracts,status,opened,assigned)
    VALUES(?,?,?,?,?,?,? ,?,?)
    """, (ticker.upper(), ttype, strike, expiry, entry_premium, contracts, "open", opened, 0))
    conn.commit()
    conn.close()

def db_list_trades(open_only=False):
    conn = get_conn()
    cur = conn.cursor()
    if open_only:
        cur.execute("SELECT * FROM trades WHERE status='open' ORDER BY opened DESC")
    else:
        cur.execute("SELECT * FROM trades ORDER BY opened DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_update_trade_close(trade_id, pnl: float, closed_date=None, assigned=0):
    conn = get_conn()
    cur = conn.cursor()
    if closed_date is None:
        closed_date = now_iso()
    cur.execute("UPDATE trades SET status='closed', pnl=?, closed_date=?, assigned=? WHERE id=?", (pnl, closed_date, assigned, trade_id))
    conn.commit()
    conn.close()

def db_manual_close_trade(trade_id, pnl: float):
    db_update_trade_close(trade_id, pnl, now_iso(), assigned=0)

def db_mark_assigned(trade_id, assigned_flag=1):
    conn = get_conn()
    cur = conn.cursor()
    closed_date = now_iso()
    cur.execute("UPDATE trades SET status='closed', closed_date=?, assigned=? WHERE id=?", (closed_date, assigned_flag, trade_id))
    conn.commit()
    conn.close()

def db_add_journal(date, ticker, typ, action, profit, note):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO journal(date,ticker,type,action,profit,note) VALUES(?,?,?,?,?,?)", (date, ticker.upper() if ticker else None, typ, action, profit, note))
    conn.commit()
    conn.close()

def db_list_journal():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM journal ORDER BY date DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_add_trade_history(trade_id, timestamp, price):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO trade_history(trade_id,timestamp,price) VALUES(?,?,?)", (trade_id, timestamp, price))
    conn.commit()
    cur.execute("SELECT COUNT(*) as cnt FROM trade_history WHERE trade_id=?", (trade_id,))
    cnt = cur.fetchone()["cnt"]
    if cnt > TRADE_HISTORY_MAX:
        to_delete = cnt - TRADE_HISTORY_MAX
        cur.execute("DELETE FROM trade_history WHERE id IN (SELECT id FROM trade_history WHERE trade_id=? ORDER BY id ASC LIMIT ?)", (trade_id, to_delete))
    conn.commit()
    conn.close()

def db_get_trade_history(trade_id, limit=300):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trade_history WHERE trade_id=? ORDER BY timestamp DESC LIMIT ?", (trade_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_add_leap(ticker, cost, current_val, contracts, expiry):
    conn = get_conn()
    cur = conn.cursor()
    opened = now_iso()
    cur.execute("INSERT INTO leaps(ticker,cost,current_val,contracts,expiry,opened) VALUES(?,?,?,?,?,?)", (ticker.upper(), cost, current_val, contracts, expiry, opened))
    conn.commit()
    conn.close()

def db_list_leaps():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM leaps ORDER BY opened DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_get_setting_json(key, default=None):
    v = db_get_setting(key)
    if v is None:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default

# ---------------------------
# Versioning System
# ---------------------------
def increment_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) == 2:
        major = parts[0]
        minor = parts[1]
        try:
            minor_i = int(minor)
            minor_i += 1
            return f"{major}.{minor_i:02d}"
        except Exception:
            return version + ".1"
    return version

def new_baseline_version(version: str) -> str:
    parts = version.split(".")
    major = parts[0]
    minor = parts[1] if len(parts) > 1 else "01"
    def inc_alpha(s):
        s = s.upper()
        res = []
        carry = 1
        for ch in s[::-1]:
            if not ch.isalpha():
                res.append(ch)
                continue
            val = ord(ch) - ord('A') + carry
            carry = 0
            if val >= 26:
                val -= 26
                carry = 1
            res.append(chr(ord('A') + val))
        if carry:
            res.append('A')
        return ''.join(res[::-1])
    new_major = inc_alpha(major)
    return f"{new_major}.01"

def add_version_note(version, note):
    notes = db_get_setting_json("version_notes", {})
    if not isinstance(notes, dict):
        notes = {}
    ts = now_iso()
    notes[version] = {"note": note, "timestamp": ts}
    db_set_setting("version_notes", json.dumps(notes))

def get_version_notes_sorted():
    notes_raw = db_get_setting_json("version_notes", {})
    if not notes_raw or not isinstance(notes_raw, dict):
        return []
    items = []
    for k, v in notes_raw.items():
        if isinstance(v, dict):
            note_text = v.get("note", "") if v.get("note", "") is not None else ""
            ts = v.get("timestamp", "") if v.get("timestamp", "") is not None else ""
        else:
            note_text = str(v)
            ts = ""
        items.append((k, {"note": note_text, "timestamp": ts}))
    items.sort(key=lambda x: x[1].get("timestamp") or "", reverse=True)
    return items

# ---------------------------
# Finnhub Integration
# ---------------------------
class FinnhubClient:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key
        self.base = "https://finnhub.io/api/v1"
        self._call_timestamps = []

    def _rate_ok(self):
        now_ts = time.time()
        self._call_timestamps = [t for t in self._call_timestamps if now_ts - t < 60]
        return len(self._call_timestamps) < CALLS_PER_MIN_LIMIT

    def _record_call(self):
        self._call_timestamps.append(time.time())

    def _finnhub_get(self, path, params=None):
        if not self.api_key:
            raise RuntimeError("Finnhub API key not set")
        if not self._rate_ok():
            raise RuntimeError("Rate limit reached; try again in a moment")
        url = f"{self.base}/{path}"
        params = params or {}
        params["token"] = self.api_key
        r = requests.get(url, params=params, timeout=10)
        self._record_call()
        r.raise_for_status()
        return r.json()

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        try:
            return self._finnhub_get("quote", {"symbol": symbol})
        except Exception:
            return {}

    def fetch_candles(self, symbol: str, days: int = 40) -> pd.DataFrame:
        try:
            end = int(time.time())
            start = end - days * 24 * 3600
            data = self._finnhub_get("stock/candle", {"symbol": symbol, "resolution": "D", "from": start, "to": end})
            if not data or data.get("s") != "ok":
                return pd.DataFrame()
            df = pd.DataFrame({
                "t": data["t"],
                "o": data["o"],
                "h": data["h"],
                "l": data["l"],
                "c": data["c"],
                "v": data["v"]
            })
            df["date"] = pd.to_datetime(df["t"], unit="s")
            return df
        except Exception:
            return pd.DataFrame()

    def calc_rv(self, df: pd.DataFrame) -> Optional[float]:
        if df is None or df.empty:
            return None
        df = df.sort_values("date")
        df["ret"] = df["c"].pct_change()
        std = df["ret"].std()
        if pd.isna(std):
            return None
        rv = std * (252 ** 0.5)
        return float(rv)

    def fetch_vix(self) -> Dict[str, Any]:
        try:
            return self.fetch_quote("^VIX")
        except Exception:
            return {}

    def fetch_economic_calendar(self):
        try:
            return self._finnhub_get("economic/calendar")
        except Exception:
            return {}

    def fetch_options_chain(self, symbol: str) -> Dict[str, Any]:
        try:
            data = self._finnhub_get("stock/option-chain", {"symbol": symbol})
            if data:
                return data
        except Exception:
            pass
        try:
            data = self._finnhub_get("stock/options", {"symbol": symbol})
            if data:
                return data
        except Exception:
            pass
        return {}

# ---------------------------
# Yahoo Options Fallback
# ---------------------------
def fetch_options_yahoo(symbol: str) -> Dict[str, Any]:
    try:
        url = f"{YAHOO_OPTIONS_BASE}/{symbol}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data
    except Exception:
        return {}

def parse_options_from_yahoo(yahoo_raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    opts = []
    try:
        if not yahoo_raw:
            return opts
        option_chain = yahoo_raw.get("optionChain", {}).get("result", [])
        if not option_chain:
            return opts
        oc = option_chain[0]
        for exp in oc.get("options", []):
            expiry_ts = exp.get("expirationDate")
            calls = exp.get("calls", []) or []
            puts = exp.get("puts", []) or []
            for c in calls:
                opts.append({
                    "symbol": c.get("contractSymbol"),
                    "type": "call",
                    "strike": safe_float(c.get("strike")),
                    "expiry": parse_date(expiry_ts).isoformat() if parse_date(expiry_ts) else None,
                    "bid": safe_float(c.get("bid")) if c.get("bid") is not None else None,
                    "ask": safe_float(c.get("ask")) if c.get("ask") is not None else None,
                    "volume": int(c.get("volume")) if c.get("volume") not in (None, "") else None,
                    "openInterest": int(c.get("openInterest")) if c.get("openInterest") not in (None, "") else None
                })
            for p in puts:
                opts.append({
                    "symbol": p.get("contractSymbol"),
                    "type": "put",
                    "strike": safe_float(p.get("strike")),
                    "expiry": parse_date(expiry_ts).isoformat() if parse_date(expiry_ts) else None,
                    "bid": safe_float(p.get("bid")) if p.get("bid") is not None else None,
                    "ask": safe_float(p.get("ask")) if p.get("ask") is not None else None,
                    "volume": int(p.get("volume")) if p.get("volume") not in (None, "") else None,
                    "openInterest": int(p.get("openInterest")) if p.get("openInterest") not in (None, "") else None
                })
    except Exception:
        return opts
    return opts

def parse_options_from_finnhub(options_raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    opts = []
    if not options_raw:
        return opts
    candidates = []
    if isinstance(options_raw, dict):
        for key in ["data", "options", "optionChain", "option_chain", "result", "optionsChain"]:
            if key in options_raw and isinstance(options_raw[key], list):
                candidates = options_raw[key]
                break
        if not candidates:
            for k, v in options_raw.items():
                if isinstance(v, list):
                    candidates.extend(v)
    elif isinstance(options_raw, list):
        candidates = options_raw
    for item in candidates:
        try:
            strike = item.get("strike") or item.get("strikePrice") or item.get("K") or item.get("strike_price")
            expiry = item.get("expiry") or item.get("expirationDate") or item.get("expiration") or item.get("expiryDate")
            typ = item.get("type") or item.get("optionType") or item.get("side")
            bid = item.get("bid") or item.get("b")
            ask = item.get("ask") or item.get("a")
            vol = item.get("volume") or item.get("v")
            oi = item.get("openInterest") or item.get("oi")
            symbol = item.get("symbol") or item.get("optionSymbol") or item.get("s")
            if strike is None or expiry is None:
                if isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, dict):
                            strike = strike or v.get("strike")
                            expiry = expiry or v.get("expiry")
            if strike is None or expiry is None:
                continue
            strike_f = safe_float(strike)
            try:
                expiry_dt = parse_date(expiry)
                expiry_iso = expiry_dt.isoformat() if expiry_dt else str(expiry)
            except Exception:
                expiry_iso = str(expiry)
            typ_norm = str(typ).lower() if typ else ""
            if typ_norm in ("c", "call"):
                typ_norm = "call"
            elif typ_norm in ("p", "put"):
                typ_norm = "put"
            else:
                if symbol and "C" in symbol:
                    typ_norm = "call"
                elif symbol and "P" in symbol:
                    typ_norm = "put"
            opts.append({
                "symbol": symbol,
                "type": typ_norm,
                "strike": strike_f,
                "expiry": expiry_iso,
                "bid": safe_float(bid, None) if bid is not None else None,
                "ask": safe_float(ask, None) if ask is not None else None,
                "volume": int(vol) if vol not in (None, "") else None,
                "openInterest": int(oi) if oi not in (None, "") else None
            })
        except Exception:
            continue
    return opts

# ---------------------------
# Safe Refresh System (with debug logging)
# ---------------------------
def safe_refresh_all(client: Optional[FinnhubClient]):
    if "market_data" not in st.session_state:
        st.session_state.market_data = {}
    if "options_debug" not in st.session_state:
        st.session_state.options_debug = {}
    tickers = [t["symbol"] for t in db_list_tickers()]
    refreshed = {"tickers": [], "errors": []}
    for sym in tickers:
        try:
            quote = {}
            candles = pd.DataFrame()
            rv = None
            options_raw = {}
            source = "none"
            raw_size = 0
            if client:
                try:
                    quote = client.fetch_quote(sym) or {}
                except Exception:
                    quote = {}
                try:
                    candles = client.fetch_candles(sym, days=40) or pd.DataFrame()
                except Exception:
                    candles = pd.DataFrame()
                try:
                    rv = client.calc_rv(candles)
                except Exception:
                    rv = None
                try:
                    options_raw = client.fetch_options_chain(sym) or {}
                    if options_raw:
                        source = "finnhub"
                except Exception:
                    options_raw = {}
            # fallback to Yahoo if no options from finnhub
            if not options_raw:
                yahoo_raw = fetch_options_yahoo(sym)
                if yahoo_raw:
                    options_raw = yahoo_raw
                    source = "yahoo"
            try:
                raw_size = len(json.dumps(options_raw)) if options_raw else 0
            except Exception:
                raw_size = 0
            st.session_state.market_data[sym] = {
                "quote": quote,
                "candles": candles,
                "rv": rv,
                "options": options_raw,
                "last_refresh": now_iso()
            }
            # parse counts for debug
            opts_parsed = []
            if source == "finnhub":
                opts_parsed = parse_options_from_finnhub(options_raw)
            elif source == "yahoo":
                opts_parsed = parse_options_from_yahoo(options_raw)
            options_count = len(opts_parsed)
            expiries = sorted({parse_date(o.get("expiry")) for o in opts_parsed if parse_date(o.get("expiry"))})
            expiries_count = len(expiries)
            st.session_state.options_debug[sym] = {
                "source": source,
                "raw_size": raw_size,
                "options_count": options_count,
                "expiries_count": expiries_count,
                "last_refresh": now_iso()
            }
            refreshed["tickers"].append(sym)
        except Exception as e:
            refreshed["errors"].append({"symbol": sym, "error": str(e)})
        time.sleep(0.05)
    open_trades = db_list_trades(open_only=True)
    for tr in open_trades:
        sym = tr["ticker"]
        trade_id = tr["id"]
        price = None
        try:
            if sym in st.session_state.market_data and st.session_state.market_data[sym].get("quote"):
                price = st.session_state.market_data[sym]["quote"].get("c") or st.session_state.market_data[sym]["quote"].get("pc")
            else:
                if st.session_state.get("finnhub_client"):
                    q = st.session_state["finnhub_client"].fetch_quote(sym)
                    price = q.get("c") or q.get("pc")
            if price is not None:
                db_add_trade_history(trade_id, now_iso(), price)
        except Exception:
            pass
    try:
        if st.session_state.get("finnhub_client"):
            vix = st.session_state["finnhub_client"].fetch_vix()
            st.session_state.market_data["__VIX__"] = {"quote": vix, "last_refresh": now_iso()}
    except Exception:
        pass
    try:
        if st.session_state.get("finnhub_client"):
            eco = st.session_state["finnhub_client"].fetch_economic_calendar()
            st.session_state.market_data["__ECON__"] = {"calendar": eco, "last_refresh": now_iso()}
    except Exception:
        pass
    return refreshed

# ---------------------------
# Live Status Tracking
# ---------------------------
def compute_intrinsic_and_unrealized(trade: Dict[str, Any], price: float) -> Dict[str, Any]:
    ttype = trade.get("type", "").lower()
    strike = safe_float(trade.get("strike", 0.0))
    entry_premium = safe_float(trade.get("entry_premium", 0.0))
    contracts = int(trade.get("contracts", 0) or 0)
    intrinsic = 0.0
    if "csp" in ttype or "put" in ttype:
        intrinsic = max(0.0, strike - price)
    elif "cc" in ttype or "call" in ttype:
        intrinsic = max(0.0, price - strike)
    unrealized = entry_premium * 100 * contracts - intrinsic * 100 * contracts
    denom = entry_premium * 100 * contracts
    percent = unrealized / denom if denom != 0 else 0.0
    return {"intrinsic": intrinsic, "unrealized": unrealized, "percent": percent}

def status_text_for_percent(percent: float) -> str:
    if percent >= 0.5:
        return "🟢 Target reached (50% profit)"
    if percent >= 0:
        return "🟢 Profit +X%"
    return "🔴 Loss -X%"

# ---------------------------
# Assignment Logic
# ---------------------------
def assign_trade(trade_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trades WHERE id=?", (trade_id,))
    tr = cur.fetchone()
    if not tr:
        conn.close()
        return False
    ticker = tr["ticker"]
    ttype = tr["type"].lower()
    closed_date = now_iso()
    cur.execute("UPDATE trades SET status='closed', closed_date=?, assigned=1 WHERE id=?", (closed_date, trade_id))
    if "csp" in ttype or "put" in ttype:
        owns = 1
    elif "cc" in ttype or "call" in ttype:
        owns = 0
    else:
        owns = 1 if db_get_ownership(ticker) else 0
    cur.execute("INSERT OR REPLACE INTO ownership(ticker, owns_shares) VALUES(?,?)", (ticker, owns))
    cur.execute("INSERT INTO journal(date,ticker,type,action,profit,note) VALUES(?,?,?,?,?,?)",
                (now_iso(), ticker, tr["type"], "assigned", tr["pnl"] or 0.0, f"Assigned on {closed_date}"))
    conn.commit()
    conn.close()
    return True

# ---------------------------
# Option table builder (ATM + suggestion, debug fields)
# ---------------------------
def build_options_table_for_ticker(sym: str, client: Optional[FinnhubClient]) -> pd.DataFrame:
    row = {
        "ticker": sym,
        "current_price": None,
        "prev_close": None,
        "day_color": None,
        "options_count": 0,
        "expiries_count": 0,
        "atm_strike": None,
        "atm_bid": None,
        "atm_ask": None,
        "atm_spread": None,
        "atm_volume": None,
        "atm_expiry": None,
        "suggestion_action": None,
        "suggestion_strike": None,
        "suggestion_bid": None,
        "suggestion_ask": None,
        "suggestion_spread": None,
        "suggestion_volume": None,
        "suggestion_expiry": None
    }
    md = st.session_state.market_data.get(sym, {}) if "market_data" in st.session_state else {}
    quote = md.get("quote") if md else {}
    if client and (not quote):
        try:
            quote = client.fetch_quote(sym) or {}
        except Exception:
            quote = quote or {}
    price = quote.get("c") or quote.get("current") or quote.get("last") or None
    prev_close = quote.get("pc") or quote.get("previousClose") or None
    row["current_price"] = price
    row["prev_close"] = prev_close
    if price is not None and prev_close is not None:
        row["day_color"] = "red" if price < prev_close else "green"
    else:
        row["day_color"] = None

    options_list = []
    raw = md.get("options") if md else None
    source = "none"
    if raw:
        parsed = parse_options_from_finnhub(raw)
        if parsed:
            options_list = parsed
            source = "finnhub_session"
        else:
            parsed = parse_options_from_yahoo(raw)
            if parsed:
                options_list = parsed
                source = "yahoo_session"
    if not options_list and client:
        try:
            raw_client = client.fetch_options_chain(sym) or {}
            parsed = parse_options_from_finnhub(raw_client)
            if parsed:
                options_list = parsed
                source = "finnhub_api"
            else:
                parsed = parse_options_from_yahoo(raw_client)
                if parsed:
                    options_list = parsed
                    source = "yahoo_like_api"
        except Exception:
            options_list = []
    if not options_list:
        yahoo_raw = fetch_options_yahoo(sym)
        parsed = parse_options_from_yahoo(yahoo_raw)
        if parsed:
            options_list = parsed
            source = "yahoo_api"

    row["options_count"] = len(options_list)

    if not options_list:
        if "options_debug" not in st.session_state:
            st.session_state.options_debug = {}
        st.session_state.options_debug[sym] = {
            "source": source,
            "options_count": row["options_count"],
            "expiries_count": 0,
            "last_refresh": now_iso()
        }
        return pd.DataFrame([row])

    for o in options_list:
        try:
            o["expiry_date"] = parse_date(o.get("expiry"))
        except Exception:
            o["expiry_date"] = None

    expiries = sorted({o["expiry_date"] for o in options_list if o["expiry_date"]})
    row["expiries_count"] = len(expiries)
    latest_expiry = expiries[-1] if expiries else None

    atm = None
    if price is not None and latest_expiry:
        candidates = [o for o in options_list if o["expiry_date"] == latest_expiry]
        if candidates:
            atm = nearest(candidates, "strike", price)
    if atm is None and price is not None and expiries:
        today = datetime.date.today()
        expiry_choice = min(expiries, key=lambda d: abs((d - today).days))
        cands = [o for o in options_list if o["expiry_date"] == expiry_choice]
        if cands:
            atm = nearest(cands, "strike", price)

    if atm:
        row["atm_strike"] = atm.get("strike")
        row["atm_bid"] = atm.get("bid")
        row["atm_ask"] = atm.get("ask")
        try:
            if atm.get("bid") is not None and atm.get("ask") is not None:
                row["atm_spread"] = round((atm.get("ask") - atm.get("bid")), 4)
        except Exception:
            row["atm_spread"] = None
        row["atm_volume"] = atm.get("volume")
        try:
            exp_dt = parse_date(atm.get("expiry"))
            row["atm_expiry"] = exp_dt.isoformat() if exp_dt else (atm.get("expiry") or None)
        except Exception:
            row["atm_expiry"] = atm.get("expiry") or None

    today = datetime.date.today()
    target_days = 30
    expiry_30 = None
    if expiries:
        expiry_30 = min(expiries, key=lambda d: abs((d - today).days - target_days))
    suggestion = None
    suggestion_type = None
    if price is not None and expiry_30:
        if row["day_color"] == "red":
            target_strike_val = round(price * 0.9, 2)
            candidates = [o for o in options_list if o["expiry_date"] == expiry_30 and o.get("type") == "put"]
            if candidates:
                suggestion = nearest(candidates, "strike", target_strike_val)
                suggestion_type = "put"
        else:
            target_strike_val = round(price * 1.1, 2)
            candidates = [o for o in options_list if o["expiry_date"] == expiry_30 and o.get("type") == "call"]
            if candidates:
                suggestion = nearest(candidates, "strike", target_strike_val)
                suggestion_type = "call"
    if suggestion is None and price is not None:
        best = None
        best_score = None
        for o in options_list:
            if not o.get("expiry_date"):
                continue
            dte = (o["expiry_date"] - today).days
            if dte < 0:
                continue
            side = "put" if row["day_color"] == "red" else "call"
            if row["day_color"] is None:
                side = "put"
            if o.get("type") != side:
                continue
            target_strike_val = price * (0.9 if side == "put" else 1.1)
            strike_diff = abs(o.get("strike", 0) - target_strike_val)
            score = abs(dte - target_days) + strike_diff / max(1.0, price)
            if best_score is None or score < best_score:
                best_score = score
                best = o
        suggestion = best
        suggestion_type = best.get("type") if best else None

    if suggestion:
        row["suggestion_action"] = f"Sell {suggestion_type.capitalize()}" if suggestion_type else None
        row["suggestion_strike"] = suggestion.get("strike")
        row["suggestion_bid"] = suggestion.get("bid")
        row["suggestion_ask"] = suggestion.get("ask")
        try:
            if suggestion.get("bid") is not None and suggestion.get("ask") is not None:
                row["suggestion_spread"] = round(suggestion.get("ask") - suggestion.get("bid"), 4)
        except Exception:
            row["suggestion_spread"] = None
        row["suggestion_volume"] = suggestion.get("volume")
        try:
            exp_dt = parse_date(suggestion.get("expiry"))
            row["suggestion_expiry"] = exp_dt.isoformat() if exp_dt else (suggestion.get("expiry") or None)
        except Exception:
            row["suggestion_expiry"] = suggestion.get("expiry") or None

    if "options_debug" not in st.session_state:
        st.session_state.options_debug = {}
    st.session_state.options_debug[sym] = {
        "source": source,
        "options_count": row["options_count"],
        "expiries_count": row["expiries_count"],
        "last_refresh": now_iso()
    }

    return pd.DataFrame([row])

def force_fetch_and_show_options(sym: str, client: Optional[FinnhubClient]):
    st.markdown("---")
    st.markdown(f"### Force fetch options for {sym}")
    raw = None
    source = "none"
    # 1) explicit Finnhub API call
    if client:
        try:
            raw_candidate = client.fetch_options_chain(sym) or {}
            if raw_candidate:
                raw = raw_candidate
                source = "finnhub_api"
        except Exception as e:
            st.write("Finnhub API call error:", str(e))
    # 2) session fallback
    if raw is None:
        md = st.session_state.market_data.get(sym, {}) if "market_data" in st.session_state else {}
        if md and md.get("options"):
            raw = md.get("options")
            source = "session_market_data"
    # 3) yahoo fallback
    if raw is None:
        try:
            yahoo_raw = fetch_options_yahoo(sym) or {}
            if yahoo_raw:
                raw = yahoo_raw
                source = "yahoo_api"
        except Exception:
            raw = None
    raw_size = 0
    try:
        raw_size = len(json.dumps(raw)) if raw else 0
    except Exception:
        raw_size = 0
    st.write("Source used:", source)
    st.write("Raw payload size (bytes):", raw_size)
    with st.expander("Show raw payload JSON"):
        if raw:
            try:
                st.code(json.dumps(raw, indent=2, default=str), language="json")
            except Exception:
                st.write(raw)
        else:
            st.write("No raw payload available.")
    # parse and show parsed rows
    parsed = []
    if raw:
        parsed = parse_options_from_finnhub(raw) or []
        if not parsed:
            parsed = parse_options_from_yahoo(raw) or []
    if not parsed:
        yahoo_raw2 = fetch_options_yahoo(sym)
        parsed = parse_options_from_yahoo(yahoo_raw2) or []
    st.write("Parsed option rows:", len(parsed))
    if parsed:
        for o in parsed:
            try:
                o["expiry_date"] = parse_date(o.get("expiry"))
            except Exception:
                o["expiry_date"] = None
        df = pd.DataFrame(parsed)
        cols = [c for c in ["symbol","type","strike","expiry","bid","ask","volume","openInterest","impliedVol"] if c in df.columns]
        st.dataframe(df[cols].head(200))
        expiries = sorted({o["expiry_date"] for o in parsed if o.get("expiry_date")})
        st.write("Unique expiries found:", len(expiries))
    else:
        st.info("No parsed option rows found.")

def show_raw_options_debug_for_first_ticker_v2(client: Optional[FinnhubClient]):
    """
    Improved raw options debug for the first ticker:
    - Explicitly calls Finnhub API first (if client provided) to fetch options_chain
    - Falls back to session data, then Yahoo
    - Displays raw payload size, parsed rows, and a matched suggestion for computed 10% OTM / 30DTE
    - Writes debug info into st.session_state.options_debug
    Place this at the bottom of the Wheel / CSP tab (after Open Positions).
    """
    tickers = db_list_tickers()
    if not tickers:
        st.info("No tickers to debug. Add a ticker first.")
        return

    first_sym = tickers[0]["symbol"]
    st.markdown("---")
    st.markdown(f"### Raw Options Debug for {first_sym}")

    # Try Finnhub API first (explicit)
    raw = None
    source = None
    raw_size = 0
    parsed = []

    # 1) Try explicit Finnhub API call if client available
    if client:
        try:
            raw_candidate = client.fetch_options_chain(first_sym) or {}
            if raw_candidate:
                raw = raw_candidate
                source = "finnhub_api"
        except Exception as e:
            # record but continue to other fallbacks
            st.write(f"Finnhub API call error: {e}")

    # 2) If no raw from API, try session market_data
    if raw is None:
        md = st.session_state.market_data.get(first_sym, {}) if "market_data" in st.session_state else {}
        if md and md.get("options"):
            raw = md.get("options")
            source = "session_market_data"

    # 3) If still none, try Yahoo fallback
    if raw is None:
        try:
            yahoo_raw = fetch_options_yahoo(first_sym) or {}
            if yahoo_raw:
                raw = yahoo_raw
                source = "yahoo_api"
        except Exception:
            raw = None

    # Compute raw size
    try:
        raw_size = len(json.dumps(raw)) if raw else 0
    except Exception:
        raw_size = 0

    st.write(f"**Source used:** {source or 'none'}")
    st.write(f"**Raw payload size (bytes):** {raw_size}")

    # Show raw JSON in an expander
    with st.expander("Show raw options payload (JSON)"):
        if raw:
            try:
                pretty = json.dumps(raw, indent=2, default=str)
                st.code(pretty, language="json")
            except Exception:
                st.write(raw)
        else:
            st.write("No raw options payload available for this ticker from any source.")

    # Parse options using both parsers (finnhub parser preferred)
    if raw:
        parsed = parse_options_from_finnhub(raw) or []
        if not parsed:
            parsed = parse_options_from_yahoo(raw) or []

    # If still empty, try explicit Yahoo fetch and parse
    if not parsed:
        try:
            yahoo_raw2 = fetch_options_yahoo(first_sym) or {}
            parsed = parse_options_from_yahoo(yahoo_raw2) or []
            if parsed and not source:
                source = "yahoo_api_explicit"
        except Exception:
            parsed = []

    st.write(f"**Parsed option rows:** {len(parsed)}")

    if not parsed:
        st.info("Parsed options list is empty for this ticker. Check Options Debug Log in Settings and run Safe Refresh.")
        # record debug info
        if "options_debug" not in st.session_state:
            st.session_state.options_debug = {}
        st.session_state.options_debug[first_sym] = {
            "source": source or "none",
            "raw_size": raw_size,
            "options_count": 0,
            "expiries_count": 0,
            "last_refresh": now_iso()
        }
        return

    # Normalize expiry_date and show sample parsed rows
    for o in parsed:
        try:
            o["expiry_date"] = parse_date(o.get("expiry"))
        except Exception:
            o["expiry_date"] = None

    df_parsed = pd.DataFrame(parsed)
    cols_show = [c for c in ["symbol", "type", "strike", "expiry", "bid", "ask", "volume", "openInterest", "impliedVol"] if c in df_parsed.columns]
    st.dataframe(df_parsed[cols_show].head(200))

    # Underlying quote
    md = st.session_state.market_data.get(first_sym, {}) if "market_data" in st.session_state else {}
    quote = md.get("quote") if md else {}
    if not quote and client:
        try:
            quote = client.fetch_quote(first_sym) or {}
        except Exception:
            quote = {}
    price = quote.get("c") or quote.get("current") or quote.get("last")
    prev_close = quote.get("pc") or quote.get("previousClose")
    st.write(f"**Underlying price:** {price if price is not None else '—'}")
    st.write(f"**Previous close:** {prev_close if prev_close is not None else '—'}")

    # Day change and red/green decision (±3% threshold)
    day_change = None
    if price is not None and prev_close:
        try:
            day_change = (price - prev_close) / prev_close
            st.write(f"**Day change:** {day_change*100:.2f}%")
        except Exception:
            day_change = None

    if day_change is not None:
        if day_change <= -0.03:
            side = "put"
        elif day_change >= 0.03:
            side = "call"
        else:
            side = "put" if price is not None and prev_close is not None and price < prev_close else "call"
    else:
        side = "put" if price is not None and prev_close is not None and price < prev_close else "call"

    st.write(f"**Suggested action (based on day change):** Sell {side.capitalize()}")

    # Compute target 10% OTM strike and find ~30D expiry
    today = datetime.date.today()
    target_days = 30
    target_strike = None
    if price is not None:
        target_strike = round(price * (0.9 if side == "put" else 1.1), 2)
    expiries = sorted({o["expiry_date"] for o in parsed if o.get("expiry_date")})
    expiry_30 = None
    if expiries:
        expiry_30 = min(expiries, key=lambda d: abs((d - today).days - target_days))

    st.write(f"**Computed 10% OTM strike:** {target_strike if target_strike is not None else '—'}")
    st.write(f"**Computed target expiry (approx 30D):** {expiry_30.isoformat() if expiry_30 else '—'}")

    # Try to match to an actual option row (prefer expiry_30)
    suggestion = None
    if expiry_30:
        candidates = [o for o in parsed if o.get("expiry_date") == expiry_30 and o.get("type") == side]
        if candidates and target_strike is not None:
            suggestion = nearest(candidates, "strike", target_strike)

    if suggestion is None and parsed and target_strike is not None:
        best = None
        best_score = None
        for o in parsed:
            if not o.get("expiry_date"):
                continue
            dte = (o["expiry_date"] - today).days
            if dte < 0:
                continue
            if o.get("type") != side:
                continue
            strike_diff = abs(o.get("strike", 0) - target_strike)
            score = abs(dte - target_days) + strike_diff / max(1.0, price or 1.0)
            if best_score is None or score < best_score:
                best_score = score
                best = o
        suggestion = best

    if suggestion:
        st.markdown("**Matched option row (closest to computed 10% OTM & 30DTE):**")
        s = suggestion
        st.write({
            "contractSymbol": s.get("symbol"),
            "type": s.get("type"),
            "strike": s.get("strike"),
            "expiry": s.get("expiry"),
            "bid": s.get("bid"),
            "ask": s.get("ask"),
            "spread": (None if s.get("bid") is None or s.get("ask") is None else round(s.get("ask") - s.get("bid"), 4)),
            "volume": s.get("volume"),
            "openInterest": s.get("openInterest"),
            "iv": s.get("impliedVol") or s.get("iv") or None
        })
    else:
        st.info("No matching option row found for the computed 10% OTM / 30DTE. The consolidated snapshot will still show the computed strike; market fields will be empty until provider returns option rows.")

    # Record debug info in session for Settings tab
    if "options_debug" not in st.session_state:
        st.session_state.options_debug = {}
    st.session_state.options_debug[first_sym] = {
        "source": source or "none",
        "raw_size": raw_size,
        "options_count": len(parsed),
        "expiries_count": len(expiries),
        "last_refresh": now_iso()
    }

# Insert this function into your app (A.06) and call it at the bottom of the Wheel / CSP tab.
def show_raw_options_debug_for_first_ticker(client: Optional[FinnhubClient]):
    """
    Display raw options chain payload and parsed rows for the first ticker in the DB.
    Also compute the 10% OTM target strike and 30DTE expiry and highlight any matching option row.
    Place a call to this function at the bottom of the CSP tab (after Open Positions).
    """
    tickers = db_list_tickers()
    if not tickers:
        st.info("No tickers to debug. Add a ticker first.")
        return

    first_sym = tickers[0]["symbol"]
    st.markdown("---")
    st.markdown(f"### Raw Options Debug for {first_sym}")

    # Try to get raw payload from session market_data first
    md = st.session_state.market_data.get(first_sym, {}) if "market_data" in st.session_state else {}
    raw = md.get("options") if md else None
    source = "session"
    if not raw and client:
        # try finnhub API
        try:
            raw = client.fetch_options_chain(first_sym) or {}
            source = "finnhub_api"
        except Exception:
            raw = None
    if not raw:
        # fallback to Yahoo
        try:
            raw = fetch_options_yahoo(first_sym) or {}
            source = "yahoo_api"
        except Exception:
            raw = None

    st.write(f"**Source used:** {source}")
    try:
        raw_size = len(json.dumps(raw)) if raw else 0
    except Exception:
        raw_size = 0
    st.write(f"**Raw payload size (bytes):** {raw_size}")

    # Show raw JSON in an expander
    with st.expander("Show raw options payload (JSON)"):
        if raw:
            try:
                pretty = json.dumps(raw, indent=2, default=str)
                st.code(pretty, language="json")
            except Exception:
                st.write(raw)
        else:
            st.write("No raw options payload available for this ticker.")

    # Parse options using existing parsers (try finnhub parser first, then yahoo parser)
    parsed = []
    if raw:
        parsed = parse_options_from_finnhub(raw) or []
        if not parsed:
            parsed = parse_options_from_yahoo(raw) or []

    # If still empty, attempt to fetch Yahoo explicitly and parse
    if not parsed:
        yahoo_raw = fetch_options_yahoo(first_sym)
        parsed = parse_options_from_yahoo(yahoo_raw) or []

    st.write(f"**Parsed option rows:** {len(parsed)}")
    if parsed:
        # Normalize expiry_date
        for o in parsed:
            try:
                o["expiry_date"] = parse_date(o.get("expiry"))
            except Exception:
                o["expiry_date"] = None

        # Show a sample of parsed rows
        df_parsed = pd.DataFrame(parsed)
        # Keep only a few columns for readability
        cols_show = [c for c in ["symbol", "type", "strike", "expiry", "bid", "ask", "volume", "openInterest"] if c in df_parsed.columns]
        st.dataframe(df_parsed[cols_show].head(50))

        # Compute current price and prev_close if available
        quote = md.get("quote") if md else {}
        if not quote and client:
            try:
                quote = client.fetch_quote(first_sym) or {}
            except Exception:
                quote = {}
        price = quote.get("c") or quote.get("current") or quote.get("last")
        prev_close = quote.get("pc") or quote.get("previousClose")
        st.write(f"**Underlying price:** {price if price is not None else '—'}")
        st.write(f"**Previous close:** {prev_close if prev_close is not None else '—'}")

        # Compute day change and decide red/green using ±3% threshold
        day_change = None
        if price is not None and prev_close:
            day_change = (price - prev_close) / prev_close
        if day_change is not None:
            st.write(f"**Day change:** {day_change*100:.2f}%")
        # Determine side
        if day_change is not None:
            if day_change <= -0.03:
                side = "put"
            elif day_change >= 0.03:
                side = "call"
            else:
                side = "put" if price is not None and prev_close is not None and price < prev_close else "call"
        else:
            side = "put" if price is not None and prev_close is not None and price < prev_close else "call"

        # Compute target 10% OTM strike and find ~30D expiry
        today = datetime.date.today()
        target_days = 30
        target_strike = None
        if price is not None:
            target_strike = round(price * (0.9 if side == "put" else 1.1), 2)
        expiries = sorted({o["expiry_date"] for o in parsed if o.get("expiry_date")})
        expiry_30 = None
        if expiries:
            expiry_30 = min(expiries, key=lambda d: abs((d - today).days - target_days))

        st.write(f"**Suggested action:** Sell {side.capitalize()}")
        st.write(f"**Computed 10% OTM strike:** {target_strike if target_strike is not None else '—'}")
        st.write(f"**Target expiry (approx 30D):** {expiry_30.isoformat() if expiry_30 else '—'}")

        # Try to match to an actual option row (prefer expiry_30)
        suggestion = None
        if expiry_30:
            candidates = [o for o in parsed if o.get("expiry_date") == expiry_30 and o.get("type") == side]
            if candidates and target_strike is not None:
                suggestion = nearest(candidates, "strike", target_strike)
        if suggestion is None and parsed and target_strike is not None:
            # search across expiries for best match
            best = None
            best_score = None
            for o in parsed:
                if not o.get("expiry_date"):
                    continue
                dte = (o["expiry_date"] - today).days
                if dte < 0:
                    continue
                if o.get("type") != side:
                    continue
                strike_diff = abs(o.get("strike", 0) - target_strike)
                score = abs(dte - target_days) + strike_diff / max(1.0, price or 1.0)
                if best_score is None or score < best_score:
                    best_score = score
                    best = o
            suggestion = best

        if suggestion:
            st.markdown("**Matched option row (closest to computed 10% OTM & 30DTE):**")
            # Show key fields
            s = suggestion
            st.write({
                "contractSymbol": s.get("symbol"),
                "type": s.get("type"),
                "strike": s.get("strike"),
                "expiry": s.get("expiry"),
                "bid": s.get("bid"),
                "ask": s.get("ask"),
                "spread": (None if s.get("bid") is None or s.get("ask") is None else round(s.get("ask") - s.get("bid"), 4)),
                "volume": s.get("volume"),
                "openInterest": s.get("openInterest"),
                "iv": s.get("impliedVol") or s.get("iv") or None
            })
        else:
            st.info("No matching option row found for the computed 10% OTM / 30DTE. The app will still display the computed strike in the consolidated snapshot; market fields will be empty until provider returns option rows.")
    else:
        st.info("Parsed options list is empty for this ticker. Check Options Debug Log in Settings and run Safe Refresh.")

# ---------------------------
# UI Helpers
# ---------------------------
def tradingview_widget(symbol: str, width="100%", height=650):
    safe_symbol = html.escape(symbol)
    widget = f"""
    <iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_{safe_symbol}&symbol={safe_symbol}&interval=D&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]" style="width:{width};height:{height}px;border:0;"></iframe>
    """
    return widget

# ---------------------------
# App Initialization
# ---------------------------
init_db()
if "market_data" not in st.session_state:
    st.session_state.market_data = {}
if "last_safe_refresh" not in st.session_state:
    st.session_state.last_safe_refresh = None
if "finnhub_client" not in st.session_state:
    stored_key = db_get_setting("finnhub_api_key")
    st.session_state.finnhub_client = FinnhubClient(stored_key) if stored_key else None
if "options_debug" not in st.session_state:
    st.session_state.options_debug = {}

st.set_page_config(page_title="WheelOS", layout="wide", initial_sidebar_state="expanded")

# Gentle initial load if API key present and tickers exist
try:
    if st.session_state.finnhub_client and not st.session_state.market_data:
        tickers_exist = db_list_tickers()
        if tickers_exist:
            try:
                safe_refresh_all(st.session_state.finnhub_client)
                st.session_state.last_safe_refresh = now_iso()
            except Exception:
                pass
except Exception:
    pass

# Sidebar - Settings and Controls
with st.sidebar:
    st.markdown("## WheelOS Controls")
    api_key = st.text_input("Finnhub API Key", value=db_get_setting("finnhub_api_key") or "", type="password")
    if st.button("Save API Key"):
        db_set_setting("finnhub_api_key", api_key)
        st.session_state.finnhub_client = FinnhubClient(api_key) if api_key else None
        st.success("API key saved.")
    # Display app version and build timestamp
    cur_version = db_get_setting("app_version", DEFAULT_VERSION)
    build_ts = db_get_setting("app_build_timestamp", "")
    st.write(f"**Version:** {cur_version}")
    if build_ts:
        st.write(f"**Built:** {build_ts}")
    st.markdown("---")
    # Wheel capital and house money display and quick edit
    wheel_capital_val = safe_float(db_get_setting("wheel_capital") or 10000.0)
    house_money_val = safe_float(db_get_setting("house_money") or 0.0)
    simulate_flag = db_get_setting("simulate_withdrawal") == "1"
    st.write("**Wheel Capital (raw):**")
    st.write(f"${wheel_capital_val:,.2f}")
    st.write("**House Money (reserved):**")
    st.write(f"${house_money_val:,.2f}")
    st.write("**Simulate withdrawal active:**", "Yes" if simulate_flag else "No")
    st.markdown("---")
    wheel_capital = st.number_input("Wheel Capital (edit)", value=wheel_capital_val, step=100.0, key="sidebar_wheel_capital")
    if st.button("Save Wheel Capital"):
        db_set_setting("wheel_capital", str(wheel_capital))
        st.success("Wheel capital updated.")
    st.markdown("---")
    st.markdown("### Safe Refresh")
    if st.button("Safe Refresh Now"):
        client = st.session_state.finnhub_client or FinnhubClient(api_key or db_get_setting("finnhub_api_key"))
        st.session_state.finnhub_client = client
        try:
            res = safe_refresh_all(client)
            st.success(f"Refreshed {len(res.get('tickers',[]))} tickers.")
            st.session_state.last_safe_refresh = now_iso()
        except Exception as e:
            st.error(f"Refresh failed: {e}")
    st.markdown("---")
    st.markdown("### Version Controls")
    st.write(f"**Current version:** {cur_version}")
    inc_note = st.text_input("Increment note (one-line)", key="inc_note_input")
    if st.button("Increment Version"):
        if inc_note and inc_note.strip():
            newv = increment_version(cur_version)
            db_set_setting("app_version", newv)
            add_version_note(newv, inc_note.strip())
            st.success(f"Version incremented to {newv}")
        else:
            st.info("Enter a one-line summary in the Increment note field above.")
    base_note = st.text_input("Baseline note (one-line)", key="base_note_input")
    if st.button("New Baseline Version"):
        if base_note and base_note.strip():
            newv = new_baseline_version(cur_version)
            db_set_setting("app_version", newv)
            add_version_note(newv, base_note.strip())
            st.success(f"New baseline version {newv} created")
        else:
            st.info("Enter a one-line summary in the Baseline note field above.")
    st.markdown("---")
    st.markdown("### Quick Actions")
    if st.button("Add Example Tickers"):
        for s in ["AAPL", "MSFT", "SPY"]:
            db_add_ticker(s)
        st.success("Added AAPL, MSFT, SPY")
    st.markdown("---")
    st.markdown("### Debug Mode")
    debug_mode = st.checkbox("Show options debug in Settings", value=False)
    st.session_state["debug_mode"] = debug_mode
    st.markdown("---")
    st.markdown("WheelOS — Personal tracking tool")

# Tabs (tab titles at top)
tab_names = ["Dashboard", "Wheel / CSP", "LEAPs", "Super Chart", "Journal", "Settings"]
tabs = st.tabs(tab_names)
tab_dashboard, tab_wheel, tab_leaps, tab_chart, tab_journal, tab_settings = tabs

# ---------------------------
# Dashboard Tab
# ---------------------------
with tab_dashboard:
    st.header("Dashboard")
    cols = st.columns([1,1,1,1])
    with cols[0]:
        realized_pnl = sum([t.get("pnl") or 0.0 for t in db_list_trades(open_only=False)])
        st.metric("Realized P/L", f"${realized_pnl:,.2f}")
    with cols[1]:
        open_positions = len(db_list_trades(open_only=True))
        st.metric("Open Positions", f"{open_positions}")
    with cols[2]:
        # Show adjusted wheel capital if simulate_withdrawal enabled
        wheel_capital_raw = safe_float(db_get_setting("wheel_capital") or 0.0)
        house_money = safe_float(db_get_setting("house_money") or 0.0)
        simulate_withdrawal = db_get_setting("simulate_withdrawal") == "1"
        if simulate_withdrawal:
            available = max(0.0, wheel_capital_raw - house_money)
            st.metric("Wheel Capital (available)", f"${available:,.2f}")
        else:
            st.metric("Wheel Capital", f"${wheel_capital_raw:,.2f}")
    with cols[3]:
        vix_quote = st.session_state.market_data.get("__VIX__", {}).get("quote", {})
        vix_val = vix_quote.get("c") if vix_quote else None
        st.metric("VIX", f"{vix_val if vix_val is not None else '—'}")

    st.markdown("#### Market Snapshot")
    md = st.session_state.market_data
    if md:
        df_rows = []
        for sym, data in md.items():
            if sym.startswith("__"):
                continue
            quote = data.get("quote", {})
            price = quote.get("c") or quote.get("pc")
            rv = data.get("rv")
            last = data.get("last_refresh")
            df_rows.append({"symbol": sym, "price": price, "rv": rv, "last_refresh": last})
        if df_rows:
            df = pd.DataFrame(df_rows)
            st.dataframe(df)
    else:
        st.info("No market data in session. Use Safe Refresh or add tickers.")

    st.markdown("#### Open Trades Live Status")
    open_trades = db_list_trades(open_only=True)
    if not open_trades:
        st.info("No open trades.")
    else:
        for tr in open_trades:
            with st.expander(f"{tr['ticker']} — {tr['type']} — Strike {tr['strike']} — Exp {tr['expiry']}"):
                sym = tr["ticker"]
                price = None
                q = st.session_state.market_data.get(sym, {}).get("quote")
                if q:
                    price = q.get("c") or q.get("pc")
                st.write(f"**Underlying price:** {price if price is not None else '—'}")
                rv = st.session_state.market_data.get(sym, {}).get("rv")
                st.write(f"**RV:** {rv:.4f}" if rv else "**RV:** —")
                if price is not None:
                    calc = compute_intrinsic_and_unrealized(tr, price)
                    st.write(f"**Intrinsic:** ${calc['intrinsic']:.2f}")
                    st.write(f"**Unrealized P/L:** ${calc['unrealized']:.2f}")
                    st.write(f"**Percent:** {percent_str(calc['percent'])}")
                    st.markdown(f"**Status:** {status_text_for_percent(calc['percent'])}")
                else:
                    st.write("Price unavailable for live status.")
                cols_act = st.columns(3)
                if cols_act[0].button("Close at 50%", key=f"close50_{tr['id']}"):
                    if price is not None:
                        calc = compute_intrinsic_and_unrealized(tr, price)
                        pnl = calc["unrealized"]
                        db_manual_close_trade(tr["id"], pnl)
                        db_add_journal(now_iso(), tr["ticker"], tr["type"], "closed_at_50", pnl, "Closed at 50% target")
                        st.success("Trade closed at 50% target.")
                if cols_act[1].button("Mark Assigned", key=f"assign_{tr['id']}"):
                    ok = assign_trade(tr["id"])
                    if ok:
                        st.success("Trade marked assigned and ownership flipped accordingly.")
                    else:
                        st.error("Failed to mark assigned.")
                if cols_act[2].button("Manual Close", key=f"manual_btn_{tr['id']}"):
                    st.session_state[f"manual_open_{tr['id']}"] = True
                if st.session_state.get(f"manual_open_{tr['id']}", False):
                    with st.form(f"manual_close_form_{tr['id']}"):
                        pnl_in = st.number_input("Enter realized P/L", key=f"pnl_input_{tr['id']}")
                        confirm = st.form_submit_button("Confirm Manual Close")
                        if confirm:
                            db_manual_close_trade(tr["id"], pnl_in)
                            db_add_journal(now_iso(), tr["ticker"], tr["type"], "manual_close", pnl_in, "Manual close by user")
                            st.success("Manual close recorded.")
                            st.session_state[f"manual_open_{tr['id']}"] = False

    st.markdown("#### Recent Journal Entries")
    jrows = db_list_journal()
    if jrows:
        dfj = pd.DataFrame(jrows)
        st.dataframe(dfj.head(20))
    else:
        st.info("No journal entries yet.")

# ---------------------------
# Wheel / CSP Tab (consolidated options table)
# ---------------------------
with tab_wheel:
    st.header("Wheel / CSP")
    st.markdown("### Add Ticker")
    with st.form("add_ticker_form"):
        new_ticker = st.text_input("Ticker symbol")
        submitted = st.form_submit_button("Add Ticker")
        if submitted and new_ticker:
            db_add_ticker(new_ticker.strip().upper())
            st.success(f"Ticker {new_ticker.strip().upper()} added.")

    st.markdown("### Ownership")
    tickers = db_list_tickers()
    if tickers:
        client = st.session_state.finnhub_client
        missing = [t["symbol"] for t in tickers if t["symbol"] not in st.session_state.market_data]
        if missing:
            try:
                safe_refresh_all(client)
            except Exception:
                pass

        # Ownership toggles
        for t in tickers:
            sym = t["symbol"]
            owns = db_get_ownership(sym)
            col1, col2 = st.columns([3,1])
            col1.write(f"**{sym}**")
            checked = col2.checkbox("Owns shares", value=owns, key=f"own_{sym}")
            if checked != owns:
                db_set_ownership(sym, bool(checked))

        st.markdown("### Options Snapshot (consolidated)")
        rows = []
        for t in tickers:
            sym = t["symbol"]
            try:
                df_row = build_options_table_for_ticker(sym, client)
                if not df_row.empty:
                    rows.append(df_row.iloc[0].to_dict())
            except Exception:
                continue
        if rows:
            consolidated = pd.DataFrame(rows)
            num_cols = ["current_price", "prev_close", "atm_strike", "atm_bid", "atm_ask", "atm_spread", "atm_volume",
                        "suggestion_strike", "suggestion_bid", "suggestion_ask", "suggestion_spread", "suggestion_volume"]
            for col in num_cols:
                if col in consolidated.columns:
                    consolidated[col] = consolidated[col].apply(lambda x: round(x, 2) if isinstance(x, (int, float)) else x)
            def dte_from_iso(iso):
                try:
                    if not iso:
                        return None
                    d = parse_date(iso)
                    if not d:
                        return None
                    return (d - datetime.date.today()).days
                except Exception:
                    return None
            consolidated["atm_dte"] = consolidated["atm_expiry"].apply(lambda x: dte_from_iso(x) if x is not None else None)
            consolidated["suggestion_dte"] = consolidated["suggestion_expiry"].apply(lambda x: dte_from_iso(x) if x is not None else None)
            cols_order = ["ticker", "current_price", "prev_close", "day_color",
                          "atm_expiry", "atm_dte", "atm_strike", "atm_bid", "atm_ask", "atm_spread", "atm_volume",
                          "suggestion_action", "suggestion_expiry", "suggestion_dte", "suggestion_strike", "suggestion_bid", "suggestion_ask", "suggestion_spread", "suggestion_volume",
                          "options_count", "expiries_count"]
            cols_present = [c for c in cols_order if c in consolidated.columns]
            consolidated = consolidated[cols_present]
            st.dataframe(consolidated.reset_index(drop=True))
            csv = consolidated.to_csv(index=False)
            st.download_button("Download Options Snapshot CSV", data=csv, file_name="wheelos_options_snapshot.csv")
        else:
            st.info("No options data available for tickers. Use Safe Refresh or add tickers.")
    else:
        st.info("No tickers. Add one above.")

    st.markdown("### Log New Trade")
    with st.form("log_trade"):
        ticker_list = [t["symbol"] for t in db_list_tickers()] or [""]
        t_ticker = st.selectbox("Ticker", ticker_list)
        t_type = st.selectbox("Type", ["CSP Put", "Covered Call"])
        t_strike = st.number_input("Strike", value=0.0)
        t_expiry = st.date_input("Expiry")
        t_entry = st.number_input("Entry premium", value=0.0)
        t_contracts = st.number_input("Contracts", value=1, min_value=1)
        t_submit = st.form_submit_button("Log Trade")
        if t_submit and t_ticker:
            db_add_trade(t_ticker, t_type, t_strike, t_expiry.isoformat(), t_entry, int(t_contracts))
            st.success("Trade logged.")

    st.markdown("### Open Positions")
    open_trades = db_list_trades(open_only=True)
    if open_trades:
        for tr in open_trades:
            with st.expander(f"Trade #{tr['id']} — {tr['ticker']} — {tr['type']}"):
                st.write(tr)
                sym = tr["ticker"]
                candles = st.session_state.market_data.get(sym, {}).get("candles")
                if isinstance(candles, pd.DataFrame) and not candles.empty:
                    st.line_chart(candles.set_index("date")["c"].tail(60))
                else:
                    st.write("Price history not available.")
                hist = db_get_trade_history(tr["id"])
                if hist:
                    dfh = pd.DataFrame(hist)
                    st.dataframe(dfh.head(10))
                else:
                    st.write("No trade history yet.")
                price = st.session_state.market_data.get(sym, {}).get("quote", {}).get("c")
                if price is not None:
                    calc = compute_intrinsic_and_unrealized(tr, price)
                    st.markdown("---")
                    st.write(f"**Intrinsic:** ${calc['intrinsic']:.2f}")
                    st.write(f"**Unrealized:** ${calc['unrealized']:.2f}")
                    st.write(f"**Percent:** {percent_str(calc['percent'])}")
                    st.write(f"**Status:** {status_text_for_percent(calc['percent'])}")
                else:
                    st.write("Live price unavailable.")
    # How to call it: add this call at the bottom of the Wheel / CSP tab (after Open Positions)
    # Example placement inside the existing `with tab_wheel:` block, after the Open Positions section:
    #client = st.session_state.finnhub_client
    #show_raw_options_debug_for_first_ticker(client)
    #client = st.session_state.get("finnhub_client")
    #show_raw_options_debug_for_first_ticker_v2(client)
    client = st.session_state.get("finnhub_client")
    force_fetch_and_show_options("AAPL", client)   # replace "AAPL" with the ticker you want to inspect


# ---------------------------
# LEAPs Tab
# ---------------------------
with tab_leaps:
    st.header("LEAPs")
    with st.form("add_leap"):
        l_ticker = st.selectbox("Ticker", [t["symbol"] for t in db_list_tickers()] or [""])
        l_cost = st.number_input("Cost basis", value=0.0)
        l_current = st.number_input("Current value", value=0.0)
        l_contracts = st.number_input("Contracts", value=1, min_value=1)
        l_expiry = st.date_input("Expiry")
        l_submit = st.form_submit_button("Add LEAP")
        if l_submit and l_ticker:
            db_add_leap(l_ticker, l_cost, l_current, int(l_contracts), l_expiry.isoformat())
            st.success("LEAP added.")
    leaps = db_list_leaps()
    if leaps:
        rows = []
        for lp in leaps:
            invested = lp["cost"] * lp["contracts"] * 100
            current = lp["current_val"] * lp["contracts"] * 100
            unreal = current - invested
            pct = unreal / invested if invested != 0 else 0.0
            rows.append({
                "ticker": lp["ticker"],
                "invested": invested,
                "current": current,
                "unrealized": unreal,
                "percent": pct,
                "expiry": lp["expiry"]
            })
        df = pd.DataFrame(rows)
        st.dataframe(df)
    else:
        st.info("No LEAPs recorded.")

# ---------------------------
# Super Chart Tab
# ---------------------------
with tab_chart:
    st.header("Super Chart")
    tickers = [t["symbol"] for t in db_list_tickers()]
    default = tickers[0] if tickers else "SPY"
    sel = st.selectbox("Select ticker for Super Chart", tickers + [default])
    st.markdown("#### TradingView Full Chart")
    try:
        st.components.v1.html(tradingview_widget(sel), height=700)
    except Exception:
        st.write("Unable to render TradingView widget in this environment.")
    rv = st.session_state.market_data.get(sel, {}).get("rv")
    if rv:
        st.write(f"RV (annualized): {rv:.4f}")
    econ = st.session_state.market_data.get("__ECON__", {}).get("calendar")
    if econ:
        st.markdown("#### Economic Calendar (sample)")
        try:
            events = econ.get("economicCalendar", []) if isinstance(econ, dict) else econ
            if isinstance(events, list) and events:
                df = pd.DataFrame(events).head(10)
                st.dataframe(df)
            else:
                st.write("No economic events available.")
        except Exception:
            st.write("Economic calendar unavailable.")

# ---------------------------
# Journal Tab
# ---------------------------
with tab_journal:
    st.header("Journal")
    entries = db_list_journal()
    if entries:
        df = pd.DataFrame(entries)
        st.dataframe(df)
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", data=csv, file_name="wheelos_journal.csv")
    else:
        st.info("No journal entries yet.")
    st.markdown("### Add Journal Entry")
    with st.form("add_journal"):
        j_date = st.date_input("Date", value=datetime.date.today())
        j_ticker = st.selectbox("Ticker", [t["symbol"] for t in db_list_tickers()] + [""])
        j_type = st.selectbox("Type", ["CSP Put", "Covered Call", "LEAP", "Other"])
        j_action = st.text_input("Action")
        j_profit = st.number_input("Profit", value=0.0)
        j_note = st.text_area("Note")
        j_submit = st.form_submit_button("Add Entry")
        if j_submit:
            db_add_journal(j_date.isoformat(), j_ticker, j_type, j_action, j_profit, j_note)
            st.success("Journal entry added.")

# ---------------------------
# Settings Tab (with debug log and house money editor)
# ---------------------------
with tab_settings:
    st.header("Settings")
    st.markdown("### Versioning")
    cur_version = db_get_setting("app_version", DEFAULT_VERSION)
    st.write(f"**Current version:** {cur_version}")
    notes = get_version_notes_sorted()
    if notes:
        for ver, meta in notes:
            ts = meta.get("timestamp", "")
            note = meta.get("note", "")
            st.write(f"- **{ver}** ({ts}): {note}")
    else:
        st.write("No version notes.")
    st.markdown("---")
    st.markdown("### App Settings")
    st.write("Finnhub API Key stored:", bool(db_get_setting("finnhub_api_key")))
    st.write("Wheel capital:", db_get_setting("wheel_capital"))
    st.write("LEAP fund:", db_get_setting("leap_fund"))
    st.markdown("---")
    st.markdown("### House Money / Withdrawal Simulation")
    current_house = safe_float(db_get_setting("house_money") or 0.0)
    simulate_flag = db_get_setting("simulate_withdrawal") == "1"
    st.write(f"Current house money reserved: **${current_house:,.2f}**")
    st.write(f"Simulate withdrawal active: **{'Yes' if simulate_flag else 'No'}**")
    with st.form("edit_house_money"):
        new_house = st.number_input("House money (amount reserved)", value=current_house, step=100.0)
        new_simulate = st.checkbox("Enable simulate withdrawal (subtract house money from available capital)", value=simulate_flag)
        submit_house = st.form_submit_button("Save House Money Settings")
        if submit_house:
            db_set_setting("house_money", str(new_house))
            db_set_setting("simulate_withdrawal", "1" if new_simulate else "0")
            st.success("House money settings updated.")
    st.markdown("---")
    st.markdown("### Options Debug Log")
    if st.session_state.get("debug_mode"):
        dbg = st.session_state.get("options_debug", {})
        if dbg:
            dbg_rows = []
            for k, v in dbg.items():
                row = {"ticker": k, "source": v.get("source"), "options_count": v.get("options_count"), "expiries_count": v.get("expiries_count"), "last_refresh": v.get("last_refresh")}
                dbg_rows.append(row)
            df_dbg = pd.DataFrame(dbg_rows)
            st.dataframe(df_dbg)
        else:
            st.info("No debug data yet. Run Safe Refresh.")
    else:
        st.write("Debug mode is off. Enable 'Show options debug in Settings' in the sidebar to view raw payload diagnostics.")
    st.markdown("---")
    st.markdown("### Raw DB Preview (for debugging)")
    if st.checkbox("Show raw tables"):
        conn = get_conn()
        for tbl in ["tickers", "ownership", "trades", "leaps", "journal", "trade_history", "settings"]:
            try:
                df = pd.read_sql_query(f"SELECT * FROM {tbl} LIMIT 200", conn)
                st.write(f"Table: {tbl}")
                st.dataframe(df)
            except Exception as e:
                st.write(f"Could not read {tbl}: {e}")
        conn.close()

# ---------------------------
# Footer
# ---------------------------
st.markdown("---")
cur_version = db_get_setting("app_version", DEFAULT_VERSION)
build_ts = db_get_setting("app_build_timestamp", "")
notes = get_version_notes_sorted()
latest_note = notes[0][1]["note"] if notes else ""
if build_ts:
    st.write(f"**Version:** {cur_version} — Built: {build_ts} — {latest_note}")
else:
    st.write(f"**Version:** {cur_version} — {latest_note}")
st.write("WheelOS — Personal tracking tool")
