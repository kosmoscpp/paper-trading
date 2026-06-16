import streamlit as st
import yfinance as yf
import sqlite3
import pandas as pd

# --- APP CONFIG & DARK THEME ---
st.set_page_config(page_title="NSE Paper Trader", page_icon="📈", layout="centered")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        .stApp { background-color: #111111; color: #e3e3e3; font-family: 'Segoe UI', sans-serif; }
        .main-title { text-align: center; font-size: 2.2rem; font-weight: 600; background: linear-gradient(45deg, #00b0ff, #00e676); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.2rem; }
        .main-subtitle { text-align: center; font-size: 0.9rem; color: #80868b; margin-bottom: 1.5rem; }
        .metric-card { background-color: #1e1f20; padding: 15px; border-radius: 14px; border: 1px solid #303134; text-align: center; }
        div[data-baseweb="input"] input { background-color: #1e1f20 !important; color: #e3e3e3 !important; border-radius: 8px !important; }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE ENGINE LAYOUT ---
DB_FILE = "userdata.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Table 1: Users profile and their liquid cash balance
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, pin TEXT, balance REAL)''')
    # Table 2: Portfolio holdings tracker
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio 
                 (username TEXT, ticker TEXT, quantity INTEGER, avg_price REAL, PRIMARY KEY (username, ticker))''')
    conn.commit()
    conn.close()

init_db()

# --- HEADER INTERFACE ---
st.markdown('<div class="main-title">NSE Virtual Trader</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subtitle">Real-time Indian Stock Simulation Dashboard</div>', unsafe_allow_html=True)

# --- USER IDENTIFICATION BAR ---
st.sidebar.markdown("### 🔐 Secure Terminal Access")
user_input = st.sidebar.text_input("Username / Nickname", value="").strip().lower()
pin_input = st.sidebar.text_input("4-Digit Secure PIN", type="password", value="").strip()

if not user_input or not pin_input:
    st.info("👈 Enter a custom Nickname and PIN in the sidebar terminal to initialize your trading terminal.")
    st.stop()

# --- AUTHENTICATION & INITIALIZATION LOOP ---
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT pin, balance FROM users WHERE username = ?", (user_input,))
user_record = c.fetchone()

if user_record:
    db_pin, current_balance = user_record
    if db_pin != pin_input:
        st.sidebar.error("❌ Access Denied: Incorrect PIN framework for this account identifier.")
        conn.close()
        st.stop()
    st.sidebar.success(f"🔓 Connected: {user_input.upper()}")
else:
    # Auto-registration logic if the identifier string is completely new
    current_balance = 100000.0  # Starting balance: ₹1 Lakh
    c.execute("INSERT INTO users (username, pin, balance) VALUES (?, ?, ?)", (user_input, pin_input, current_balance))
    conn.commit()
    st.sidebar.success(f"✨ Profile Constructed! Welcome {user_input.upper()}")

conn.close()

# --- APP INTERFACE NAVIGATION TABS ---
tab1, tab2, tab3 = st.tabs(["📈 Market Watch", "💼 Portfolio Summary", "🛒 Execution Desk"])

# Common Stock Library (Mapped precisely to Yahoo Finance NSE syntax)
STOCK_DICT = {
    "Reliance Industries": "RELIANCE.NS",
    "Tata Consultancy Services (TCS)": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "Zomato Limited": "ZOMATO.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "State Bank of India (SBI)": "SBIN.NS"
}

# --- TAB 1: MARKET WATCH ---
with tab1:
    st.markdown("### Live Market Feed")
    selected_stock_label = st.selectbox("Select Asset Asset Class:", list(STOCK_DICT.keys()))
    ticker_symbol = STOCK_DICT[selected_stock_label]
    
    with st.spinner("Fetching live execution price data via yfinance..."):
        try:
            stock_data = yf.Ticker(ticker_symbol)
            # Fetch current live trading execution price
            live_price = stock_data.history(period="1d")["Close"].iloc[-1]
            st.markdown(
                f"<div class='metric-card'><h4>{selected_stock_label}</h4>"
                f"<h1 style='color:#00e676;'>₹{live_price:,.2f}</h1>"
                f"<p style='color:#80868b; font-size:0.8rem;'>Ticker ID: {ticker_symbol} | Exchange: NSE India</p></div>", 
                unsafe_allow_html=True
            )
        except Exception as e:
            st.error("Failed to stream asset metrics. Verify execution connection context.")
            live_price = 0.0

# --- TAB 2: PORTFOLIO SUMMARY ---
with tab2:
    st.markdown("### Asset Allocation Matrix")
    
    # Calculate live portfolio status and valuations
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
        
        # Get live asset valuation
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
        
    # Display overall performance dashboard
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
        st.caption("No open investment profiles detected. Navigate to the Execution Desk tab to allocate assets.")

# --- TAB 3: EXECUTION DESK ---
with tab3:
    st.markdown("### Order Allocation Window")
    st.info(f"Available Allocation Capital: **₹{current_balance:,.2f}**")
    
    trade_stock_label = st.selectbox("Select Target Instrument:", list(STOCK_DICT.keys()), key="trade_stock")
    trade_ticker = STOCK_DICT[trade_stock_label]
    
    trade_qty = st.number_input("Shares Quantity", min_value=1, step=1, value=5)
    
    try:
        execution_price = yf.Ticker(trade_ticker).history(period="1d")["Close"].iloc[-1]
    except:
        execution_price = 0.0
        
    order_value = trade_qty * execution_price
    st.write(f"Estimated Order Value: **₹{order_value:,.2f}** (@ ₹{execution_price:,.2f} per unit)")
    
    btn_buy, btn_sell = st.columns(2)
    
    with btn_buy:
        if st.button("EXECUTE MARKET BUY 🟢", use_container_width=True):
            if order_value > current_balance:
                st.error("Insufficient margin capability to process order.")
            elif execution_price == 0:
                st.error("Invalid execution parameters.")
            else:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                
                # Deduct asset costs from balance sheet
                new_balance = current_balance - order_value
                c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, user_input))
                
                # Adjust portfolio configurations
                c.execute("SELECT quantity, avg_price FROM portfolio WHERE username = ? AND ticker = ?", (user_input, trade_ticker))
                existing_asset = c.fetchone()
                
                if existing_asset:
                    ex_qty, ex_avg = existing_asset
                    new_qty = ex_qty + trade_qty
                    # Weighted average buy price calculator
                    new_avg = ((ex_qty * ex_avg) + order_value) / new_qty
                    c.execute("UPDATE portfolio SET quantity = ?, avg_price = ? WHERE username = ? AND ticker = ?", (new_qty, new_avg, user_input, trade_ticker))
                else:
                    c.execute("INSERT INTO portfolio (username, ticker, quantity, avg_price) VALUES (?, ?, ?, ?)", (user_input, trade_ticker, trade_qty, execution_price))
                    
                conn.commit()
                conn.close()
                st.success(f"Market filled: Bought {trade_qty} units of {trade_stock_label}!")
                st.rerun()
                
    with btn_sell:
        if st.button("EXECUTE MARKET SELL 🔴", use_container_width=True):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT quantity, avg_price FROM portfolio WHERE username = ? AND ticker = ?", (user_input, trade_ticker))
            existing_asset = c.fetchone()
            
            if not existing_asset or existing_asset[0] < trade_qty:
                st.error("Insufficient short margin inventory available to sell.")
                conn.close()
            else:
                ex_qty, ex_avg = existing_asset
                new_qty = ex_qty - trade_qty
                gain_capital = trade_qty * execution_price
                new_balance = current_balance + gain_capital
                
                c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, user_input))
                c.execute("UPDATE portfolio SET quantity = ? WHERE username = ? AND ticker = ?", (new_qty, user_input, trade_ticker))
                
                conn.commit()
                conn.close()
                st.success(f"Market filled: Liquidated {trade_qty} units of {trade_stock_label}!")
                st.rerun()
