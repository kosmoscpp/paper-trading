import streamlit as st
import yfinance as yf
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import time
import os

# --- APP CONFIG & CUSTOM CSS ---
st.set_page_config(page_title="NSE Terminal", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
        .stApp { background-color: #000000; color: #ffffff; }
        .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
        .stTabs [data-baseweb="tab-list"] { gap: 20px; justify-content: flex-end; }
        div[data-testid="stMetricValue"] { font-size: 1.5rem; font-weight: 700; color: #00e676; }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE SETUP ---
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "userdata.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, pin TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio (username TEXT, ticker TEXT, quantity INTEGER, avg_price REAL, stop_loss REAL DEFAULT 0.0, take_profit REAL DEFAULT 0.0, PRIMARY KEY (username, ticker))''')
    conn.commit()
    conn.close()

init_db()

# --- STOCKS MATRIX ---
STOCK_DICT = {
    "Reliance": "RELIANCE.NS", "TCS": "TCS.NS", "Infosys": "INFY.NS", "HDFC Bank": "HDFCBANK.NS",
    "ICICI": "ICICIBANK.NS", "SBI": "SBIN.NS", "ITC": "ITC.NS", "HUL": "HINDUNILVR.NS",
    "Maruti": "MARUTI.NS", "M&M": "M&M.NS", "Adani Ports": "ADANIPORTS.NS", "NTPC": "NTPC.NS",
    "Sun Pharma": "SUNPHARMA.NS", "Cipla": "CIPLA.NS", "ONGC": "ONGC.NS", "IOC": "IOC.NS",
    "Tata Power": "TATAPOWER.NS", "Power Grid": "POWERGRID.NS"
}

if "market_cache" not in st.session_state: st.session_state.market_cache = {}

# --- AUTOMATED ENGINE & HIGH-SPEED SYNC ---
def global_market_sync():
    try:
        # Single-trip query for all 18 tickers
        raw_data = yf.download(list(STOCK_DICT.values()), period="5d", interval="5m", progress=False)
        for name, sym in STOCK_DICT.items():
            if sym in raw_data.columns.get_level_values(1):
                df = pd.DataFrame({
                    'Open': raw_data['Open'][sym], 'High': raw_data['High'][sym],
                    'Low': raw_data['Low'][sym], 'Close': raw_data['Close'][sym]
                }).dropna()
                if not df.empty:
                    st.session_state.market_cache[sym] = {"price": float(df['Close'].iloc[-1]), "history": df.tail(35)}
        
        # Process Auto Triggers
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT username, ticker, quantity, stop_loss, take_profit FROM portfolio WHERE quantity > 0")
        for user, ticker, qty, sl, tp in c.fetchall():
            if ticker in st.session_state.market_cache:
                p = st.session_state.market_cache[ticker]["price"]
                if (sl > 0.0 and p <= sl) or (tp > 0.0 and p >= tp):
                    c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (qty * p, user))
                    c.execute("UPDATE portfolio SET quantity = 0 WHERE username = ? AND ticker = ?", (user, ticker))
        conn.commit(); conn.close()
    except: pass

if not st.session_state.market_cache: global_market_sync()

# --- AUTH FRAMEWORK ---
if "user" not in st.session_state:
    st.markdown("<h2 style='text-align:center;'>🔐 Live Terminal</h2>", unsafe_allow_html=True)
    u = st.text_input("Username").strip().lower()
    p = st.text_input("PIN (4-Digit)", type="password").strip()
    if st.button("Authenticate"):
        if u and p:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE username = ?", (u,))
            res = c.fetchone()
            if res: st.session_state.balance = res[0]
            else:
                st.session_state.balance = 10000000.0
                c.execute("INSERT INTO users VALUES (?, ?, ?)", (u, p, st.session_state.balance))
                conn.commit()
            conn.close()
            st.session_state.user = u
            st.rerun()
    st.stop()

# --- TOP STATUS NAV BAR ---
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT balance FROM users WHERE username = ?", (st.session_state.user,))
st.session_state.balance = c.fetchone()[0]
conn.close()

st.markdown(f"👤 **{st.session_state.user.upper()}**")

# --- UI CONTROLS ---
ticker_name = st.selectbox("Select Asset", list(STOCK_DICT.keys()), label_visibility="collapsed")
sym = STOCK_DICT[ticker_name]

t1, t2, t3 = st.tabs(["🛒", "💼", "🏆"])

# --- TAB 1: TRADING VIEW ---
with t1:
    if sym in st.session_state.market_cache:
        live_p = st.session_state.market_cache[sym]["price"]
        d = st.session_state.market_cache[sym]['history']
        
        st.metric(label=ticker_name, value=f"₹{live_p:,.2f}")
        
        fig = go.Figure(data=[go.Candlestick(x=d.index.strftime('%H:%M'), open=d['Open'], high=d['High'], low=d['Low'], close=d['Close'])])
        fig.update_layout(template="plotly_dark", margin=dict(l=0,r=0,t=0,b=0), height=280, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.warning("Fetching market data...")
        live_p = 0.0

    # --- ACTION BAR BUTTONS ---
    @st.dialog("Order Parameters")
    def order_placement(side):
        qty = st.number_input("Quantity", min_value=1, step=1, value=5)
        sl = st.number_input("Stop Loss Price (₹)", min_value=0.0, value=0.0)
        tp = st.number_input("Take Profit Price (₹)", min_value=0.0, value=0.0)
        
        if st.button(f"CONFIRM {side} MARKET ORDER"):
            val = qty * live_p
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            if side == "BUY":
                if val <= st.session_state.balance:
                    c.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (val, st.session_state.user))
                    c.execute("SELECT quantity, avg_price FROM portfolio WHERE username = ? AND ticker = ?", (st.session_state.user, sym))
                    exist = c.fetchone()
                    if exist:
                        nq = exist[0] + qty
                        navg = ((exist[0] * exist[1]) + val) / nq
                        c.execute("UPDATE portfolio SET quantity=?, avg_price=?, stop_loss=?, take_profit=? WHERE username=? AND ticker=?", (nq, navg, sl, tp, st.session_state.user, sym))
                    else:
                        c.execute("INSERT INTO portfolio VALUES (?, ?, ?, ?, ?, ?)", (st.session_state.user, sym, qty, live_p, sl, tp))
                    st.success("Buy executed!")
                else: st.error("Insufficient Funds")
            else:
                c.execute("SELECT quantity FROM portfolio WHERE username = ? AND ticker = ?", (st.session_state.user, sym))
                exist = c.fetchone()
                if exist and exist[0] >= qty:
                    c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (val, st.session_state.user))
                    c.execute("UPDATE portfolio SET quantity = quantity - ? WHERE username = ? AND ticker = ?", (qty, st.session_state.user, sym))
                    st.success("Sell executed!")
                else: st.error("Insufficient Shares")
                
            conn.commit(); conn.close()
            time.sleep(0.5); st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("BUY", type="primary"): order_placement("BUY")
    with c2:
        if st.button("SELL", type="secondary"): order_placement("SELL")

# --- TAB 2: PORTFOLIO ---
with t2:
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT ticker as Asset, quantity as Qty, avg_price as [Avg Buy], stop_loss as [SL], take_profit as [TP] FROM portfolio WHERE username = ? AND quantity > 0", conn, params=(st.session_state.user,))
    conn.close()
    
    net_worth = st.session_state.balance
    if not df.empty:
        df['Current Price'] = df['Asset'].map(lambda x: st.session_state.market_cache.get(x, {}).get('price', 0.0))
        df['P/L'] = (df['Current Price'] - df['Avg Buy']) * df['Qty']
        net_worth += df['P/L'].sum() + (df['Avg Buy'] * df['Qty']).sum()
        
        # Human-readable mapping names for assets
        inv_map = {v: k for k, v in STOCK_DICT.items()}
        df['Asset'] = df['Asset'].map(inv_map)
        
        st.markdown(f"### Net Worth: **₹{net_worth:,.2f}**")
        st.markdown(f"Wallet Cash: ₹{st.session_state.balance:,.2f}")
        st.dataframe(df.style.map(lambda v: 'color: #00e676' if v > 0 else 'color: #ff1744', subset=['P/L']), use_container_width=True)
    else:
        st.markdown(f"### Net Worth: **₹{net_worth:,.2f}**")
        st.write("No open positions.")

# --- TAB 3: LEADERBOARD ---
with t3:
    st.subheader("Leaderboard")
    conn = sqlite3.connect(DB_FILE)
    users_df = pd.read_sql_query("SELECT username, balance FROM users", conn)
    port_df = pd.read_sql_query("SELECT username, ticker, quantity, avg_price FROM portfolio WHERE quantity > 0", conn)
    conn.close()
    
    lead_board = []
    for _, u_row in users_df.iterrows():
        u_name = u_row['username']
        worth = u_row['balance']
        u_p = port_df[port_df['username'] == u_name]
        for _, p_row in u_p.iterrows():
            curr_p = st.session_state.market_cache.get(p_row['ticker'], {}).get('price', p_row['avg_price'])
            worth += p_row['quantity'] * curr_p
        lead_board.append({"User": u_name.upper(), "Net Worth": worth, "Returns": worth - 10000000.0})
        
    if lead_board:
        ld_df = pd.DataFrame(lead_board).sort_values(by="Net Worth", ascending=False).reset_index(drop=True)
        ld_df.index += 1
        st.dataframe(ld_df.style.map(lambda v: 'color: #00e676' if v > 0 else 'color: #ff1744', subset=['Returns']), use_container_width=True)

# Low-impact background ticking
if time.time() % 30 < 2: global_market_sync()
