import streamlit as st
import yfinance as yf
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import time
import os

# --- APP CONFIG & MOBILE-CENTRIC STYLE ---
st.set_page_config(page_title="NSE Terminal", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
        .stApp { background-color: #000000; color: #e3e3e3; }
        .main-title { font-weight: 800; font-size: 1.5rem; text-align: center; }
        .buy-btn { background-color: #00e676 !important; color: #000 !important; }
        .sell-btn { background-color: #ff1744 !important; color: #fff !important; }
        [data-testid="stMetricValue"] { font-size: 1.2rem; }
    </style>
""", unsafe_allow_html=True)

# --- DB & CACHE INIT ---
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "userdata.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, pin TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio (username TEXT, ticker TEXT, quantity INTEGER, avg_price REAL, stop_loss REAL DEFAULT 0.0, take_profit REAL DEFAULT 0.0, PRIMARY KEY (username, ticker))''')
    conn.commit(); conn.close()

init_db()

# --- MARKET MATRIX ---
STOCK_DICT = {
    "Reliance": "RELIANCE.NS", "TCS": "TCS.NS", "Infosys": "INFY.NS", "HDFC Bank": "HDFCBANK.NS",
    "ICICI": "ICICIBANK.NS", "SBI": "SBIN.NS", "ITC": "ITC.NS", "HUL": "HINDUNILVR.NS",
    "Maruti": "MARUTI.NS", "M&M": "M&M.NS", "Adani Ports": "ADANIPORTS.NS", "NTPC": "NTPC.NS",
    "Sun Pharma": "SUNPHARMA.NS", "Cipla": "CIPLA.NS", "ONGC": "ONGC.NS", "IOC": "IOC.NS",
    "Tata Power": "TATAPOWER.NS", "Power Grid": "POWERGRID.NS"
}

if "market_cache" not in st.session_state: st.session_state.market_cache = {}

def global_market_sync():
    ticker_str = " ".join(STOCK_DICT.values())
    data = yf.download(ticker_str, period="5d", interval="5m", progress=False)
    for ticker in STOCK_DICT.values():
        try:
            # Handle multi-index column structures from yfinance
            df = data['Close'][ticker].dropna() if 'Close' in data.columns else data[ticker].dropna()
            st.session_state.market_cache[ticker] = {"price": float(df.iloc[-1]), "history": data[ticker] if 'Open' in data[ticker].columns else data}
        except: pass

if not st.session_state.market_cache: global_market_sync()

# --- AUTH LOGIC (Simplified) ---
if "user" not in st.session_state:
    st.markdown("<h1 class='main-title'>🔐 Terminal</h1>", unsafe_allow_html=True)
    user = st.text_input("Username").strip().lower()
    pin = st.text_input("PIN", type="password")
    if st.button("Enter"):
        st.session_state.user = user
        st.rerun()
    st.stop()

# --- MODAL FOR TRADES ---
@st.dialog("Execute Trade")
def trade_modal(ticker, side):
    qty = st.number_input("Shares Quantity", min_value=1, step=1)
    sl = st.number_input("Stop Loss (₹)", value=0.0)
    tp = st.number_input("Take Profit (₹)", value=0.0)
    if st.button(f"CONFIRM {side}"):
        st.success(f"Order processed for {ticker}")
        time.sleep(1); st.rerun()

# --- UI LAYOUT ---
st.markdown(f"**Operator:** {st.session_state.user.upper()}")
ticker = st.selectbox("Market Instrument", list(STOCK_DICT.keys()))
sym = STOCK_DICT[ticker]

# --- TABS ---
t1, t2, t3 = st.tabs(["🛒", "💼", "🏆"])

with t1:
    if sym in st.session_state.market_cache:
        d = st.session_state.market_cache[sym]['history']
        fig = go.Figure(data=[go.Candlestick(x=d.index, open=d['Open'], high=d['High'], low=d['Low'], close=d['Close'])])
        fig.update_layout(template="plotly_dark", margin=dict(l=0,r=0,t=0,b=0), height=300, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
    c1, c2 = st.columns(2)
    with c1: 
        if st.button("BUY", key="buy", use_container_width=True): trade_modal(sym, "BUY")
    with c2: 
        if st.button("SELL", key="sell", use_container_width=True): trade_modal(sym, "SELL")

with t2:
    st.subheader("Portfolio")
    # Add dummy data for visual logic
    df = pd.DataFrame({"Asset": ["RELIANCE", "TCS"], "P&L": [500, -200]})
    st.dataframe(df.style.map(lambda v: 'color: green' if v > 0 else 'color: red', subset=['P&L']), use_container_width=True)

with t3:
    st.subheader("Leaderboard")
    st.info("Rankings active.")

# --- AUTO SYNC ---
if time.time() % 30 < 1: global_market_sync()
        
