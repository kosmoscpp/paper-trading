import streamlit as st
import yfinance as yf
import sqlite3
import pandas as pd
import time

# --- APP CONFIG & DARK THEME ---
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

# --- DATABASE ENGINE LAYOUT ---
DB_FILE = "userdata.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, pin TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio 
                 (username TEXT, ticker TEXT, quantity INTEGER, avg_price REAL, PRIMARY KEY (username, ticker))''')
    conn.commit()
    conn.close()

init_db()

# --- HEADER INTERFACE ---
st.markdown('<div class="main-title">NSE Live Terminal</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Real-Time Indian Stock Simulation & Execution Room</div>', unsafe_allow_html=True)

# --- AUTO REFRESH LOOP TRIGGER (Runs every 5 seconds for live movement) ---
if "run_count" not in st.session_state:
    st.session_state.run_count = 0

# --- MAIN SCREEN LOGIN CONTAINER ---
st.markdown('<div class="login-box">', unsafe_allow_html=True)
st.markdown("### 🔐 Terminal Authentication")
col_user, col_pin = st.columns(2)

with col_user:
    user_input = st.text_input("Username / Nickname", value="").strip().lower()
with col_pin:
    pin_input = st.text_input("4-Digit Secure PIN", type="password", value="").strip()
st.markdown('</div>', unsafe_allow_html=True)

if not user_input or not pin_input:
    st.info("👆 Enter your custom Nickname and PIN above to access your live trading console.")
    st.stop()

# --- AUTHENTICATION LOOP ---
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT pin, balance FROM users WHERE username = ?", (user_input,))
user_record = c.fetchone()

if user_record:
    db_pin, current_balance = user_record
    if db_pin != pin_input:
        st.error("❌ Access Denied: Incorrect PIN framework for this account identifier.")
        conn.close()
        st.stop()
else:
    current_balance = 100000.0  # Starting balance: ₹1 Lakh
    c.execute("INSERT INTO users (username, pin, balance) VALUES (?, ?, ?)", (user_input, pin_input, current_balance))
    conn.commit()
    st.success(f"✨ Profile Constructed! Welcome to the market, {user_input.upper()}!")

conn.close()

# Show ticker details neatly
st.markdown(f"👤 **Operator:** {user_input.upper()} | 💰 **Wallet:** ₹{current_balance:,.2f}")

# --- MERGED NAVIGATION TABS ---
tab1, tab2 = st.tabs(["🛒 Live Trade Room", "💼 Portfolio Summary"])

STOCK_DICT = {
    "Reliance Industries": "RELIANCE.NS",
    "Tata Consultancy Services (TCS)": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "Zomato Limited": "ZOMATO.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "State Bank of India (SBI)": "SBIN.NS"
}

# --- TAB 1: MERGED LIVE TRADE ROOM & EXECUTION ---
with tab1:
    selected_stock_label = st.selectbox("Select Target Instrument:", list(STOCK_DICT.keys()))
    ticker_symbol = STOCK_DICT[selected_stock_label]
    
    # Fetch today's data with tight 1-minute tracking intervals
    try:
        stock_data = yf.Ticker(ticker_symbol)
        # Fetching today's data at 1-minute intervals
        live_history = stock_data.history(period="1d", interval="1m")
        
        if live_history.empty:
            # Fallback if the Indian market is closed right now (shows last active day's 1m interval)
            live_history = stock_data.history(period="5d", interval="1m").tail(60)
            
        live_price = live_history["Close"].iloc[-1]
        
        # Display Dynamic Metric Card
        st.markdown(
            f"<div class='metric-card'><h4>{selected_stock_label}</h4>"
            f"<h1 style='color:#00e676;'>₹{live_price:,.2f}</h1>"
            f"<p style='color:#80868b; font-size:0.8rem;'>Live Auto-Polling Active (5s) | Exch: NSE</p></div>", 
            unsafe_allow_html=True
        )
        
        # Stream the chart
        st.markdown("#### 📊 Intraday Tick Chart (1m Bars)")
        st.line_chart(live_history[['Close']])
        
    except Exception as e:
        st.error("Market feed offline. Waiting for next tick stream...")
        live_price = 0.0

    st.markdown("---")
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
                st.success(f"Bought {trade_qty} units of {selected_stock_label}!")
                time.sleep(1)
                st.rerun()
                
    with btn_sell:
        if st.button("EXECUTE MARKET SELL 🔴", use_container_width=True):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT quantity, avg_price FROM portfolio WHERE username = ? AND ticker = ?", (user_input, ticker_symbol))
            existing_asset = c.fetchone()
            
            if not existing_asset or existing_asset[0] < trade_qty:
                st.error("Insufficient inventory available to sell.")
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
                st.success(f"Liquidated {trade_qty} units of {selected_stock_label}!")
                time.sleep(1)
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
            current_p = yf.Ticker(tick).history(period="1d")["Close"].iloc[-1]
        except:
            current_p = avg_p
            
        invested_v = qty * avg_p
        current_v = qty * current_p
        pnl = current_v - invested_v
        
        total_invested_value += invested_v
        total_holding_value += current_v
        
        portfolio_rows.append({
            "Asset": tick,
            "Qty": qty,
            "Avg Buy Price": f"₹{avg_p:,.2f}",
            "Current Price": f"₹{current_p:,.2f}",
            "Current Value": f"₹{current_v:,.2f}",
            "P&L": f"₹{pnl:,.2f}"
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

# --- THE LIVE ENGINE STIMULATOR ---
# This forces the page to reload every 5 seconds to query fresh market changes!
time.sleep(5)
st.session_state.run_count += 1
st.rerun()
