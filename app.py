import streamlit as st
import yfinance as yf
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import time

# --- APP CONFIG & CUSTOM CSS ---
st.set_page_config(page_title="NSE Live Trader", page_icon="⚡", layout="centered")

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

# --- DATABASE SETUP ---
DB_FILE = "userdata.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, pin TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio (username TEXT, ticker TEXT, quantity INTEGER, avg_price REAL, PRIMARY KEY (username, ticker))''')
    conn.commit()
    conn.close()

init_db()

if "market_cache" not in st.session_state:
    st.session_state.market_cache = {}

# --- CLEAN HEADER ---
st.markdown('<div class="main-title">NSE Live Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Real-Time Indian Stock Simulation & Execution Room</div>', unsafe_allow_html=True)

# --- CONDITIONAL TERMINAL AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = ""
    st.session_state.balance = 10000000.0  # UPGRADED STARTING BALANCE: ₹1 Crore

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
        current_balance = 10000000.0  # Assigned to new users: ₹1 Crore
        c.execute("INSERT INTO users (username, pin, balance) VALUES (?, ?, ?)", (user_input, pin_input, current_balance))
        conn.commit()
    conn.close()

    st.session_state.authenticated = True
    st.session_state.user = user_input
    st.session_state.balance = current_balance
    st.rerun()

# --- LIVE WORKSPACE LOADED ---
user_input = st.session_state.user
current_balance = st.session_state.balance

st.markdown(f"👤 **Operator:** {user_input.upper()} | 💰 **Wallet Balance:** ₹{current_balance:,.2f}")

tab1, tab2 = st.tabs(["🛒 Live Trade Room", "💼 Portfolio Summary"])

# Cleaned dictionary (Zomato & Tata Motors successfully removed)
STOCK_DICT = {
    "Reliance Industries": "RELIANCE.NS",
    "Tata Consultancy Services (TCS)": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "State Bank of India (SBI)": "SBIN.NS"
}

# --- TAB 1: LIVE TRADE ROOM ---
with tab1:
    selected_stock_label = st.selectbox("Select Target Instrument:", list(STOCK_DICT.keys()))
    ticker_symbol = STOCK_DICT[selected_stock_label]
    
    live_price = 0.0
    live_history = pd.DataFrame()
    
    try:
        stock_data = yf.Ticker(ticker_symbol)
        live_history = stock_data.history(period="5d", interval="5m").tail(35)
        
        if not live_history.empty:
            live_price = live_history["Close"].iloc[-1]
            st.session_state.market_cache[ticker_symbol] = {
                "price": live_price,
                "history": live_history
            }
    except Exception as e:
        pass
        
    if (ticker_symbol in st.session_state.market_cache) and (live_price == 0.0 or live_history.empty):
        live_price = st.session_state.market_cache[ticker_symbol]["price"]
        live_history = st.session_state.market_cache[ticker_symbol]["history"]
        st.caption("⚠️ API limit hit. Streaming live from local database memory relay...")

    if live_price > 0.0 and not live_history.empty:
        st.markdown(
            f"<div class='metric-card'><h4>{selected_stock_label}</h4>"
            f"<h1 style='color:#00e676;'>₹{live_price:,.2f}</h1>"
            f"<p style='color:#80868b; font-size:0.8rem;'>Auto-Refreshing Active | Exch: NSE India</p></div>", 
            unsafe_allow_html=True
        )
        
        chart_df = live_history[['Close']].copy()
        chart_df.index = chart_df.index.strftime('%H:%M')
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=chart_df.index, 
            y=chart_df['Close'], 
            mode='lines',
            line=dict(color='#00b0ff', width=2.5),
            name='Price'
        ))
        
        fig.update_layout(
            margin=dict(l=20, r=20, t=10, b=10),
            height=250,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, color='#80868b'),
            yaxis=dict(showgrid=True, gridcolor='#303134', color='#80868b', autorange=True),
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.error("Connection link resetting. Re-routing ticker packet stream in next loop cycle...")

    st.markdown("### ⚡ Execution Window")
    trade_qty = st.number_input("Shares Quantity", min_value=1, step=1, value=5, key="order_qty")
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
                    c.execute("UPDATE portfolio SET quantity = ?, avg_price = ? WHERE username = ? AND ticker = ?", (new_qty, new_avg, user_input, ticker_symbol))
                else:
                    c.execute("INSERT INTO portfolio (username, ticker, quantity, avg_price) VALUES (?, ?, ?, ?)", (user_input, ticker_symbol, trade_qty, live_price))
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
    df_holdings = pd.read_sql_query("SELECT ticker, quantity, avg_price FROM portfolio WHERE username = ? AND quantity > 0", conn, params=(user_input,))
    conn.close()
    
    total_holding_value = 0.0
    total_invested_value = 0.0
    portfolio_rows = []
    
    for idx, row in df_holdings.iterrows():
        tick = row['ticker']
        qty = row['quantity']
        avg_p = row['avg_price']
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
            "Asset": tick, "Qty": qty, "Avg Buy Price": f"₹{avg_p:,.2f}",
            "Current Price": f"₹{current_p:,.2f}", "Current Value": f"₹{current_v:,.2f}", "P&L": f"₹{pnl:,.2f}"
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

# --- AUTO REFRESH LOOP (10s) ---
time.sleep(10)
st.rerun()
                                   
