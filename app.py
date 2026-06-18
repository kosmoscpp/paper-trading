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
        .stApp { background-color: #000000; color: #ffffff; }
        .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
        [data-testid="stMetricValue"] { font-size: 1.2rem; }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE & SYNC ---
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

STOCK_DICT = {
    "Reliance": "RELIANCE.NS", "TCS": "TCS.NS", "Infosys": "INFY.NS", "HDFC Bank": "HDFCBANK.NS",
    "ICICI": "ICICIBANK.NS", "SBI": "SBIN.NS", "ITC": "ITC.NS", "HUL": "HINDUNILVR.NS",
    "Maruti": "MARUTI.NS", "M&M": "M&M.NS", "Adani Ports": "ADANIPORTS.NS", "NTPC": "NTPC.NS",
    "Sun Pharma": "SUNPHARMA.NS", "Cipla": "CIPLA.NS", "ONGC": "ONGC.NS", "IOC": "IOC.NS",
    "Tata Power": "TATAPOWER.NS", "Power Grid": "POWERGRID.NS"
}

if "market_cache" not in st.session_state: st.session_state.market_cache = {}

def global_market_sync():
    try:
        # Use a single fetch for all
        data = yf.download(list(STOCK_DICT.values()), period="5d", interval="5m", group_by='ticker', progress=False)
        for name, sym in STOCK_DICT.items():
            df = data[sym].dropna()
            if not df.empty:
                st.session_state.market_cache[sym] = {"price": float(df['Close'].iloc[-1]), "history": df}
    except: pass

if not st.session_state.market_cache: global_market_sync()

# --- UI LOGIC ---
if "user" not in st.session_state:
    st.markdown("### 🔐 Terminal")
    st.session_state.user = st.text_input("Username").strip().lower()
    if st.button("Enter"): st.rerun()
    st.stop()

ticker_name = st.selectbox("Market Instrument", list(STOCK_DICT.keys()))
sym = STOCK_DICT[ticker_name]

t1, t2, t3 = st.tabs(["🛒", "💼", "🏆"])

with t1:
    # --- CHART ---
    if sym in st.session_state.market_cache:
        d = st.session_state.market_cache[sym]['history']
        fig = go.Figure(data=[go.Candlestick(x=d.index, open=d['Open'], high=d['High'], low=d['Low'], close=d['Close'])])
        fig.update_layout(template="plotly_dark", margin=dict(l=0,r=0,t=0,b=0), height=300, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    
    # --- BUY/SELL ---
    c1, c2 = st.columns(2)
    with c1: 
        if st.button("BUY", type="primary"): st.info("Trade Modal Active")
    with c2: 
        if st.button("SELL", type="primary"): st.info("Trade Modal Active")

with t2:
    st.subheader("Portfolio")
    conn = sqlite3.connect(DB_FILE)
    # Corrected Portfolio Query
    df = pd.read_sql_query("SELECT ticker AS Asset, quantity AS Qty, avg_price AS 'Avg Price', stop_loss AS SL, take_profit AS TP FROM portfolio WHERE username = ?", conn, params=(st.session_state.user,))
    conn.close()
    
    if not df.empty:
        # Calculate P/L live
        df['Current Price'] = df['Asset'].map(lambda x: st.session_state.market_cache.get(x, {}).get('price', 0))
        df['P/L'] = (df['Current Price'] - df['Avg Price']) * df['Qty']
        st.dataframe(df.style.map(lambda v: 'color: green' if v > 0 else 'color: red', subset=['P/L']), use_container_width=True)
    else:
        st.write("No holdings.")

with t3:
    st.subheader("Leaderboard")
    st.write("Rankings based on total Net Worth.")

# Periodic sync
if time.time() % 60 < 2: global_market_sync()
        
