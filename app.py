import streamlit as st
import yfinance as yf
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import time
import os

# --- APP CONFIG & CUSTOM CSS ---
st.set_page_config(page_title="NSE Live Terminal", page_icon="⚡", layout="centered")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        .stApp { background-color: #111111; color: #e3e3e3; font-family: 'Segoe UI', sans-serif; }
        .main-title { text-align: center; font-size: 2.2rem; font-weight: 600; background: linear-gradient(45deg, #00b0ff, #00e676); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.2rem; }
        .main-subtitle { text-align: center; font-size: 0.9rem; color: #80868b; margin-bottom: 1.5rem; }
        .metric-card { background-color: #1e1f20; padding: 15px; border-radius: 14px; border: 1px solid #303134; text-align: center; margin-bottom: 15px; }
        .login-box { background-color: #1e1f20; padding: 25px; border-radius: 14px; border: 1px solid #303134; margin-bottom: 20px; }
        div[data-baseweb="input"] input { background-color: #1a1a1a !important; color: #e3e3e3 !important; border-radius: 8px !important; }
    </style>
""", unsafe_allow_html=True)

# --- CONTAINER PERSISTENT DATABASE SETUP ---
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_FILE = os.path.join(DATA_DIR, "userdata.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, pin TEXT, balance REAL)''')
    # Added stop_loss and take_profit columns
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio (
                    username TEXT, 
                    ticker TEXT, 
                    quantity INTEGER, 
                    avg_price REAL, 
                    stop_loss REAL, 
                    take_profit REAL, 
                    PRIMARY KEY (username, ticker))''')
    
    # Dynamic migration check to add columns if updating an old database file
    try:
        c.execute("ALTER TABLE portfolio ADD COLUMN stop_loss REAL DEFAULT 0.0")
        c.execute("ALTER TABLE portfolio ADD COLUMN take_profit REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass # Columns already exist
        
    conn.commit()
    conn.close()

init_db()

# --- MULTI-SECTOR MARKET MATRIX (18 STOCKS) ---
STOCK_DICT = {
    "Reliance Industries": "RELIANCE.NS",
    "Tata Consultancy Services (TCS)": "TCS.NS",
    "Infosys Limited": "INFY.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "State Bank of India (SBI)": "SBIN.NS",
    "ITC Limited": "ITC.NS",
    "Hindustan Unilever (HUL)": "HINDUNILVR.NS",
    "Maruti Suzuki": "MARUTI.NS",
    "Mahindra & Mahindra (M&M)": "M&M.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "NTPC Limited": "NTPC.NS",
    "Sun Pharmaceutical (Pharma)": "SUNPHARMA.NS",
    "Cipla Limited (Pharma)": "CIPLA.NS",
    "Oil & Natural Gas Corp (ONGC)": "ONGC.NS",
    "Indian Oil Corporation (IOC)": "IOC.NS",
    "Tata Power (Energy)": "TATAPOWER.NS",
    "Power Grid Corp (Energy)": "POWERGRID.NS"
}

if "market_cache" not in st.session_state:
    st.session_state.market_cache = {}
if "last_sync_time" not in st.session_state:
    st.session_state.last_sync_time = 0.0

# --- AUTOMATED STOP LOSS / TAKE PROFIT ENGINE ---
def process_auto_triggers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Grab all active open positions
    c.execute("SELECT username, ticker, quantity, stop_loss, take_profit FROM portfolio WHERE quantity > 0")
    positions = c.fetchall()
    
    for username, ticker, qty, sl, tp in positions:
        if ticker in st.session_state.market_cache:
            current_p = st.session_state.market_cache[ticker]["price"]
            triggered = False
            reason = ""
            
            # Check Stop Loss (Trigger if price falls below SL, given SL is set > 0)
            if sl > 0.0 and current_p <= sl:
                triggered = True
                reason = "STOP LOSS 🔴"
            # Check Take Profit (Trigger if price rises above TP, given TP is set > 0)
            elif tp > 0.0 and current_p >= tp:
                triggered = True
                reason = "TAKE PROFIT 🟢"
                
            if triggered:
                # Calculate return capital and update user's account balance
                gain_capital = qty * current_p
                c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (gain_capital, username))
                # Wipe out inventory quantity for this stock asset profile
                c.execute("UPDATE portfolio SET quantity = 0 WHERE username = ? AND ticker = ?", (username, ticker))
                
                # If the triggered user happens to be the current viewer, update their live local session state
                if st.session_state.get("user") == username:
                    st.session_state.balance += gain_capital
                    
    conn.commit()
    conn.close()

# --- BUNDLED & OPTIMIZED SYNC ENGINE (HIGH SPEED / LOW CPU) ---
def global_market_sync(force=False):
    current_time = time.time()
    if not force and (current_time - st.session_state.last_sync_time < 30) and st.session_state.market_cache:
        return

    ticker_string = " ".join(STOCK_DICT.values())
    try:
        data = yf.download(ticker_string, period="5d", interval="5m", group_by='ticker', progress=False)
        
        for name, ticker in STOCK_DICT.items():
            if ticker in data.columns.levels[0]:
                ticker_df = data[ticker].dropna()
                if not ticker_df.empty:
                    st.session_state.market_cache[ticker] = {
                        "price": float(ticker_df["Close"].iloc[-1]),
                        "history": ticker_df.tail(35)
                    }
        st.session_state.last_sync_time = current_time
        
        # RUN THE TRIGGER ENGINE RIGHT AFTER REFRESHING DATA FEEDS
        process_auto_triggers()
    except Exception as e:
        pass

if not st.session_state.market_cache:
    with st.spinner("Initializing optimized global market feeds..."):
        global_market_sync(force=True)

# --- CLEAN HEADER ---
st.markdown('<div class="main-title">NSE Live Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Real-Time Indian Stock Simulation & Execution Room</div>', unsafe_allow_html=True)

# --- CONDITIONAL TERMINAL AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = ""
    st.session_state.balance = 10000000.0

if not st.session_state.authenticated:
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown("### 🔐 Terminal Authentication")
    col_user, col_pin = st.columns(2)
    with col_user:
        user_input = st.text_input("Username / Nickname", value="").strip().lower()
    with col_pin:
        pin_input = st.text_input("4-Digit Secure PIN", type="password", value="").strip()
    st.markdown('</div>', unsafe_allow_html=True)

    if not user_input or not pin_input:
        st.stop()

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT pin, balance FROM users WHERE username = ?", (user_input,))
    user_record = c.fetchone()

    if user_record:
        db_pin, current_balance = user_record
        if db_pin != pin_input:
            st.error("❌ Access Denied: Incorrect PIN framework.")
            conn.close()
            st.stop()
    else:
        current_balance = 10000000.0
        c.execute("INSERT INTO users (username, pin, balance) VALUES (?, ?, ?)", (user_input, pin_input, current_balance))
        conn.commit()
    conn.close()

    st.session_state.authenticated = True
    st.session_state.user = user_input
    st.session_state.balance = current_balance
    st.rerun()

user_input = st.session_state.user
current_balance = st.session_state.balance

st.markdown(f"👤 **Operator:** {user_input.upper()} | 💰 **Wallet Balance:** ₹{current_balance:,.2f}")

tab1, tab2, tab3 = st.tabs(["🛒 Live Trade Room", "💼 Portfolio Summary", "🏆 Rankings Leaderboard"])

# --- TAB 1: LIVE TRADE ROOM ---
with tab1:
    selected_stock_label = st.selectbox("Select Target Instrument:", list(STOCK_DICT.keys()))
    ticker_symbol = STOCK_DICT[selected_stock_label]
    
    if ticker_symbol in st.session_state.market_cache:
        live_price = st.session_state.market_cache[ticker_symbol]["price"]
        live_history = st.session_state.market_cache[ticker_symbol]["history"]
        
        st.markdown(
            f"<div class='metric-card'><h4>{selected_stock_label}</h4>"
            f"<h1 style='color:#00e676;'>₹{live_price:,.2f}</h1>"
            f"<p style='color:#80868b; font-size:0.8rem;'>Auto-Refreshing Active | Exch: NSE India</p></div>", 
            unsafe_allow_html=True
        )
        
        chart_df = live_history.copy()
        chart_df.index = chart_df.index.strftime('%H:%M')
        
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=chart_df.index, open=chart_df['Open'], high=chart_df['High'], low=chart_df['Low'], close=chart_df['Close'], name='Market Price'
        ))
        fig.update_layout(
            xaxis_rangeslider_visible=False,
            margin=dict(l=20, r=20, t=10, b=10), height=270,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, color='#80868b'),
            yaxis=dict(showgrid=True, gridcolor='#303134', color='#80868b', autorange=True),
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.error("Streaming connection dropped. Resynchronizing baseline matrix...")
        live_price = 0.0

    st.markdown("### ⚡ Execution Window")
    trade_qty = st.number_input("Shares Quantity", min_value=1, step=1, value=5, key="order_qty")
    
    # ADDED USER INPUT WINDOWS FOR TARGET LIMITS DURING ORDER EXECUTION
    col_sl, col_tp = st.columns(2)
    with col_sl:
        input_sl = st.number_input("Set Stop Loss Price (₹) [0 for none]", min_value=0.0, step=0.5, value=0.0)
    with col_tp:
        input_tp = st.number_input("Set Take Profit Price (₹) [0 for none]", min_value=0.0, step=0.5, value=0.0)

    order_value = trade_qty * live_price
    st.write(f"Estimated Order Value: **₹{order_value:,.2f}**")
    
    btn_buy, btn_sell = st.columns(2)
    with btn_buy:
        if st.button("EXECUTE MARKET BUY 🟢", use_container_width=True):
            if order_value > current_balance:
                st.error("Insufficient margin capability.")
            elif live_price == 0:
                st.error("Invalid execution parameters.")
            else:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                new_balance = current_balance - order_value
                c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, user_input))
                c.execute("SELECT quantity, avg_price FROM portfolio WHERE username = ? AND ticker = ?", (user_input, ticker_symbol))
                existing_asset = c.fetchone()
                
                if existing_asset:
                    ex_qty, ex_avg = existing_asset
                    new_qty = ex_qty + trade_qty
                    new_avg = ((ex_qty * ex_avg) + order_value) / new_qty
                    # Update targets along with average purchase price updates
                    c.execute("UPDATE portfolio SET quantity = ?, avg_price = ?, stop_loss = ?, take_profit = ? WHERE username = ? AND ticker = ?", 
                              (new_qty, new_avg, input_sl, input_tp, user_input, ticker_symbol))
                else:
                    c.execute("INSERT INTO portfolio (username, ticker, quantity, avg_price, stop_loss, take_profit) VALUES (?, ?, ?, ?, ?, ?)", 
                              (user_input, ticker_symbol, trade_qty, live_price, input_sl, input_tp))
                conn.commit()
                conn.close()
                st.session_state.balance = new_balance
                st.success(f"Bought {trade_qty} units of {selected_stock_label}!")
                time.sleep(0.5)
                st.rerun()
                
    with btn_sell:
        if st.button("EXECUTE MARKET SELL 🔴", use_container_width=True):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT quantity, avg_price FROM portfolio WHERE username = ? AND ticker = ?", (user_input, ticker_symbol))
            existing_asset = c.fetchone()
            if not existing_asset or existing_asset[0] < trade_qty:
                st.error("Insufficient inventory available.")
                conn.close()
            else:
                ex_qty, ex_avg = existing_asset
                new_qty = ex_qty - trade_qty
                gain_capital = trade_qty * live_price
                new_balance = current_balance + gain_capital
                c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, user_input))
                c.execute("UPDATE portfolio SET quantity = ? WHERE username = ? AND ticker = ?", (new_qty, user_input, ticker_symbol))
                conn.commit()
                conn.close()
                st.session_state.balance = new_balance
                st.success(f"Liquidated {trade_qty} units of {selected_stock_label}!")
                time.sleep(0.5)
                st.rerun()

# --- TAB 2: PORTFOLIO SUMMARY ---
with tab2:
    st.markdown("### Asset Allocation Matrix")
    conn = sqlite3.connect(DB_FILE)
    # Added stop_loss and take_profit metrics to output view mapping
    df_holdings = pd.read_sql_query("SELECT ticker, quantity, avg_price, stop_loss, take_profit FROM portfolio WHERE username = ? AND quantity > 0", conn, params=(user_input,))
    conn.close()
    
    total_holding_value = 0.0
    total_invested_value = 0.0
    portfolio_rows = []
    
    for idx, row in df_holdings.iterrows():
        tick = row['ticker']
        qty = row['quantity']
        avg_p = row['avg_price']
        sl_val = row['stop_loss']
        tp_val = row['take_profit']
        
        asset_label = next((k for k, v in STOCK_DICT.items() if v == tick), tick)
        
        try:
            current_p = st.session_state.market_cache[tick]["price"] if tick in st.session_state.market_cache else avg_p
        except:
            current_p = avg_p
            
        invested_v = qty * avg_p
        current_v = qty * current_p
        pnl = current_v - invested_v
        total_invested_value += invested_v
        total_holding_value += current_v
        portfolio_rows.append({
            "Asset": asset_label, "Qty": qty, "Avg Buy Price": f"₹{avg_p:,.2f}",
            "Current Price": f"₹{current_p:,.2f}", "Current Value": f"₹{current_v:,.2f}", "P&L": f"₹{pnl:,.2f}",
            "Stop Loss": f"₹{sl_val:,.2f}" if sl_val > 0 else "None", "Take Profit": f"₹{tp_val:,.2f}" if tp_val > 0 else "None"
        })
        
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"<div class='metric-card'><small>Liquid Wallet Balance</small><h3>₹{current_balance:,.2f}</h3></div>", unsafe_allow_html=True)
    with col2:
        net_pnl = total_holding_value - total_invested_value
        pnl_color = "#00e676" if net_pnl >= 0 else "#ff1744"
        st.markdown(f"<div class='metric-card'><small>Total Open Net P&L</small><h3 style='color:{pnl_color};'>₹{net_pnl:,.2f}</h3></div>", unsafe_allow_html=True)
    st.markdown("---")
    if len(portfolio_rows) > 0:
        st.table(pd.DataFrame(portfolio_rows))
    else:
        st.caption("No open investment profiles detected.")

# --- TAB 3: DYNAMIC RANKINGS LEADERBOARD ---
with tab3:
    st.markdown("### 🏆 Elite Trader Standings")
    
    conn = sqlite3.connect(DB_FILE)
    all_users = pd.read_sql_query("SELECT username, balance FROM users", conn)
    all_portfolio = pd.read_sql_query("SELECT username, ticker, quantity FROM portfolio WHERE quantity > 0", conn)
    conn.close()
