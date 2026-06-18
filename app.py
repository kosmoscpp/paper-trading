import streamlit as st
import yfinance as yf
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import time
import os

# --- APP CONFIG & PROFESSIONAL DARK THEME ---
st.set_page_config(page_title="NSE Trading Terminal", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        .stApp { background-color: #000000; color: #ffffff; font-family: 'Segoe UI', sans-serif; }
        
        /* Compact TradingView Style Header */
        .tv-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 5px; border-bottom: 1px solid #1e222d; margin-bottom: 10px; }
        .tv-operator { font-size: 0.85rem; color: #848e9c; font-weight: 600; }
        .tv-networth { font-size: 1.1rem; color: #26a69a; font-weight: 700; text-align: right; }
        
        /* Metric Styling */
        .price-box { padding: 10px 0; border-bottom: 1px solid #1e222d; margin-bottom: 15px; }
        .price-title { font-size: 1.4rem; font-weight: 700; margin: 0; color: #ffffff; }
        .price-value { font-size: 1.8rem; font-weight: 700; color: #00e676; margin: 5px 0 0 0; }
        
        /* Flat UI input fields */
        div[data-baseweb="input"] input { background-color: #1c2030 !important; color: #ffffff !important; border-radius: 6px !important; border: 1px solid #2f3342 !important; }
        div[data-baseweb="select"] > div { background-color: #1c2030 !important; color: #ffffff !important; border-radius: 6px !important; border: 1px solid #2f3342 !important; }
        
        /* Trading View Native Buy/Sell Buttons */
        .stButton>button { width: 100%; border-radius: 6px; font-weight: 700; font-size: 1rem; height: 45px; transition: all 0.2s; border: none; }
        button[data-testid="baseButton-primary"] { background-color: #26a69a !important; color: #ffffff !important; } /* Buy Green */
        button[data-testid="baseButton-secondary"] { background-color: #ef5350 !important; color: #ffffff !important; } /* Sell Red */
        
        /* Tab Emojis Custom Sizing */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; justify-content: flex-end; border-bottom: 1px solid #1e222d; }
        .stTabs [data-baseweb="tab"] { font-size: 1.3rem !important; padding: 10px 15px !important; color: #848e9c; }
        .stTabs [aria-selected="true"] { color: #2962ff !important; border-bottom-color: #2962ff !important; }
    </style>
""", unsafe_allow_html=True)

# --- DIRECTORY & PERSISTENT DATABASE STORAGE ---
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "userdata.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, pin TEXT, balance REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio (
                    username TEXT, 
                    ticker TEXT, 
                    quantity INTEGER, 
                    avg_price REAL, 
                    stop_loss REAL DEFAULT 0.0, 
                    take_profit REAL DEFAULT 0.0, 
                    PRIMARY KEY (username, ticker))''')
    conn.commit()
    conn.close()

init_db()

# --- THE RADAR SYSTEM (18 DIRECT SECTOR TICKERS) ---
STOCK_DICT = {
    "Reliance": "RELIANCE.NS", "TCS": "TCS.NS", "Infosys": "INFY.NS", "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS", "SBI": "SBIN.NS", "ITC": "ITC.NS", "Hindustan Unilever": "HINDUNILVR.NS",
    "Maruti Suzuki": "MARUTI.NS", "Mahindra & Mahindra": "M&M.NS", "Adani Ports": "ADANIPORTS.NS", "NTPC": "NTPC.NS",
    "Sun Pharma (Pharma)": "SUNPHARMA.NS", "Cipla (Pharma)": "CIPLA.NS", "ONGC (Oil)": "ONGC.NS", "IOC (Oil)": "IOC.NS",
    "Tata Power (Energy)": "TATAPOWER.NS", "Power Grid (Energy)": "POWERGRID.NS"
}

if "market_cache" not in st.session_state: st.session_state.market_cache = {}
if "last_sync_time" not in st.session_state: st.session_state.last_sync_time = 0.0

# --- TRACKING ENGINE: RUNS TRIGGERS SAFE FROM FALSE AUTO-LIQUIDATIONS ---
def process_auto_triggers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username, ticker, quantity, stop_loss, take_profit FROM portfolio WHERE quantity > 0")
    positions = c.fetchall()
    
    for username, ticker, qty, sl, tp in positions:
        if ticker in st.session_state.market_cache:
            current_p = st.session_state.market_cache[ticker]["price"]
            triggered = False
            
            # Boundary check (> 0) to prevent instant 0.0 trigger traps
            if sl > 0.0 and current_p <= sl:
                triggered = True
            elif tp > 0.0 and current_p >= tp:
                triggered = True
                
            if triggered:
                gain_capital = qty * current_p
                c.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (gain_capital, username))
                c.execute("UPDATE portfolio SET quantity = 0 WHERE username = ? AND ticker = ?", (username, ticker))
                if st.session_state.get("user") == username:
                    st.session_state.balance += gain_capital
                    
    conn.commit()
    conn.close()

# --- HIGH-SPEED ENGINE FOR NETWORK EFFICIENCY ---
def global_market_sync(force=False):
    current_time = time.time()
    if not force and (current_time - st.session_state.last_sync_time < 15) and st.session_state.market_cache:
        return

    ticker_string = " ".join(STOCK_DICT.values())
    try:
        data = yf.download(ticker_string, period="5d", interval="5m", progress=False)
        
        for name, ticker in STOCK_DICT.items():
            if ticker in data.columns.get_level_values(1):
                ticker_df = pd.DataFrame({
                    'Open': data['Open'][ticker], 'High': data['High'][ticker],
                    'Low': data['Low'][ticker], 'Close': data['Close'][ticker]
                }).dropna()
            elif ticker in data.columns.get_level_values(0):
                ticker_df = pd.DataFrame({
                    'Open': data[ticker]['Open'], 'High': data[ticker]['High'],
                    'Low': data[ticker]['Low'], 'Close': data[ticker]['Close']
                }).dropna()
            else:
                continue

            if not ticker_df.empty:
                st.session_state.market_cache[ticker] = {
                    "price": float(ticker_df["Close"].iloc[-1]),
                    "history": ticker_df.tail(35)
                }
                
        st.session_state.last_sync_time = current_time
        process_auto_triggers()
    except:
        pass

if not st.session_state.market_cache:
    global_market_sync(force=True)

# --- TERMINAL AUTHENTICATION GATEWAYS ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = ""
    st.session_state.balance = 10000000.0

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center; margin-top: 40px;'>⚡ SECURE ACCESS TERMINAL</h2>", unsafe_allow_html=True)
    with st.container():
        st.markdown('<div style="background-color: #1c2030; padding: 25px; border-radius: 8px; border: 1px solid #2f3342;">', unsafe_allow_html=True)
        u_input = st.text_input("Username / Operator Key").strip().lower()
        p_input = st.text_input("4-Digit Access PIN", type="password").strip()
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.button("INITIALIZE SECURE SYSTEM LINK"):
            if u_input and p_input:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT pin, balance FROM users WHERE username = ?", (u_input,))
                record = c.fetchone()
                
                if record:
                    db_pin, current_balance = record
                    if db_pin != p_input:
                        st.error("❌ Invalid security credentials.")
                        conn.close()
                        st.stop()
                else:
                    current_balance = 10000000.0
                    c.execute("INSERT INTO users (username, pin, balance) VALUES (?, ?, ?)", (u_input, p_input, current_balance))
                    conn.commit()
                conn.close()
                
                st.session_state.authenticated = True
                st.session_state.user = u_input
                st.session_state.balance = current_balance
                st.rerun()
        st.stop()

# --- CALCULATE LIVE VALUE MATRICES FOR NAV BAR ---
user_id = st.session_state.user
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT balance FROM users WHERE username = ?", (user_id,))
st.session_state.balance = c.fetchone()[0]
current_cash_balance = st.session_state.balance

# Pull active holding calculations to compute live Net Worth
df_calc = pd.read_sql_query("SELECT ticker, quantity, avg_price FROM portfolio WHERE username = ? AND quantity > 0", conn, params=(user_id,))
conn.close()

total_asset_worth = 0.0
for _, r in df_calc.iterrows():
    t_sym = r['ticker']
    t_qty = r['quantity']
    c_prc = st.session_state.market_cache.get(t_sym, {}).get('price', r['avg_price'])
    total_asset_worth += (t_qty * c_prc)

live_net_worth = current_cash_balance + total_asset_worth

# --- TRADINGVIEW NATIVE STATUS TOP BAR ---
st.markdown(f"""
    <div class="tv-header">
        <div class="tv-operator">● OPERATOR: {user_id.upper()}</div>
        <div class="tv-networth">Net Worth: ₹{live_net_worth:,.2f}</div>
    </div>
""", unsafe_allow_html=True)

# --- NATIVE TICKER SELECTION ---
selected_stock_label = st.selectbox("Asset Selector", list(STOCK_DICT.keys()), label_visibility="collapsed")
ticker_symbol = STOCK_DICT[selected_stock_label]

# --- THREE NAVIGATION TAB GLYPHS ---
tab1, tab2, tab3 = st.tabs(["🛒", "💼", "🏆"])

# --- TAB 1: CHART WINDOW & ACTION FOOTERS ---
with tab1:
    if ticker_symbol in st.session_state.market_cache:
        live_price = st.session_state.market_cache[ticker_symbol]["price"]
        live_history = st.session_state.market_cache[ticker_symbol]["history"]
        
        st.markdown(f"""
            <div class="price-box">
                <div class="price-title">{selected_stock_label}</div>
                <div class="price-value">₹{live_price:,.2f}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Plotly Candlestick Interface Mapping (Fixed Properties Syntax)
        chart_df = live_history.copy()
        chart_df.index = pd.to_datetime(chart_df.index).strftime('%H:%M')
        
        fig = go.Figure(data=[go.Candlestick(
            x=chart_df.index, open=chart_df['Open'], high=chart_df['High'], low=chart_df['Low'], close=chart_df['Close'],
            increasing=dict(line=dict(color='#26a69a'), fillcolor='#26a69a'),
            decreasing=dict(line=dict(color='#ef5350'), fillcolor='#ef5350')
        )])
        fig.update_layout(
            template="plotly_dark", xaxis_rangeslider_visible=False,
            margin=dict(l=5, r=5, t=5, b=5), height=290,
            paper_bgcolor='#000000', plot_bgcolor='#000000',
            xaxis=dict(showgrid=False, color='#848e9c'),
            yaxis=dict(showgrid=True, gridcolor='#1e222d', color='#848e9c', side="right")
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.error("Market asset sync offline.")
        live_price = 0.0

    # --- IN-APP DIALOG POP-UP MODALS ---
    @st.dialog("Order Parameters Window")
    def open_order_modal(order_side):
        st.markdown(f"### Market Execution: {order_side}")
        st.markdown(f"Asset: **{selected_stock_label}** | Live Spot: **₹{live_price:,.2f}**")
        st.markdown("---")
        
        qty_input = st.number_input("Order Size (Shares Quantity)", min_value=1, step=1, value=10)
        est_cost = qty_input * live_price
        st.write(f"Total Order Exposure Value: **₹{est_cost:,.2f}**")
        
        sl_input = st.number_input("Risk Limit: Stop Loss Price (₹) [0 for none]", min_value=0.0, step=0.5, value=0.0)
        tp_input = st.number_input("Target Limit: Take Profit Price (₹) [0 for none]", min_value=0.0, step=0.5, value=0.0)
        
        if st.button(f"TRANSMIT {order_side} PACKET", type="primary" if order_side == "BUY" else "secondary"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            if order_side == "BUY":
                if est_cost > st.session_state.balance:
                    st.error("Execution Rejected: Insufficient Margin Balance.")
                else:
                    new_wallet_balance = st.session_state.balance - est_cost
                    c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_wallet_balance, user_id))
                    c.execute("SELECT quantity, avg_price FROM portfolio WHERE username = ? AND ticker = ?", (user_id, ticker_symbol))
                    exists = c.fetchone()
                    
                    if exists:
                        old_qty, old_avg = exists
                        updated_qty = old_qty + qty_input
                        updated_avg = ((old_qty * old_avg) + est_cost) / updated_qty
                        c.execute("UPDATE portfolio SET quantity = ?, avg_price = ?, stop_loss = ?, take_profit = ? WHERE username = ? AND ticker = ?", 
                                  (updated_qty, updated_avg, sl_input, tp_input, user_id, ticker_symbol))
                    else:
                        c.execute("INSERT INTO portfolio VALUES (?, ?, ?, ?, ?, ?)", (user_id, ticker_symbol, qty_input, live_price, sl_input, tp_input))
                    
                    conn.commit()
                    st.session_state.balance = new_wallet_balance
                    st.success("Buy order successfully processed!")
                    time.sleep(0.6)
                    st.rerun()
            else:
                # SELL BLOCK EXECUTION
                c.execute("SELECT quantity FROM portfolio WHERE username = ? AND ticker = ?", (user_id, ticker_symbol))
                exists = c.fetchone()
                if not exists or exists[0] < qty_input:
                    st.error("Execution Rejected: Insufficient inventory position.")
                else:
                    updated_qty = exists[0] - qty_input
                    return_funds = qty_input * live_price
                    new_wallet_balance = st.session_state.balance + return_funds
                    c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_wallet_balance, user_id))
                    c.execute("UPDATE portfolio SET quantity = ? WHERE username = ? AND ticker = ?", (updated_qty, user_id, ticker_symbol))
                    
                    conn.commit()
                    st.session_state.balance = new_wallet_balance
                    st.success("Sell liquidation processed!")
                    time.sleep(0.6)
                    st.rerun()
            conn.close()

    # Layout Action Execution Grid
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("BUY", type="primary", use_container_width=True):
            open_order_modal("BUY")
    with col_btn2:
        if st.button("SELL", type="secondary", use_container_width=True):
            open_order_modal("SELL")

# --- TAB 2: ADVANCED SCROLLABLE TRADINGVIEW PORTFOLIO SUMMARY ---
with tab2:
    st.markdown("### Open Investment Matrix")
    conn = sqlite3.connect(DB_FILE)
    df_portfolio = pd.read_sql_query("SELECT ticker, quantity, avg_price, stop_loss, take_profit FROM portfolio WHERE username = ? AND quantity > 0", conn, params=(user_id,))
    conn.close()
    
    if not df_portfolio.empty:
        portfolio_rows = []
        for _, row in df_portfolio.iterrows():
            tk = row['ticker']
            q = row['quantity']
            avg_b = row['avg_price']
            sl_v = row['stop_loss']
            tp_v = row['take_profit']
            
            clean_name = next((k for k, v in STOCK_DICT.items() if v == tk), tk)
            curr_market_p = st.session_state.market_cache.get(tk, {}).get('price', avg_b)
            
            value_invested = q * avg_b
            value_current = q * curr_market_p
            net_pnl = value_current - value_invested
            
            portfolio_rows.append({
                "Asset": clean_name, "Qty": q, "Avg Buy Price": avg_b, "Current Price": curr_market_p,
                "Stop Loss": sl_v if sl_v > 0 else None, "Take Profit": tp_v if tp_v > 0 else None, "P&L (₹)": net_pnl
            })
            
        df_display = pd.DataFrame(portfolio_rows)
        
        # Fixed Pandas String Formatting Codes (Removed syntax error causing '?')
        st.dataframe(
            df_display.style.format({
                "Avg Buy Price": "₹{:,.2f}", 
                "Current Price": "₹{:,.2f}",
                "Stop Loss": lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "None", 
                "Take Profit": lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "None", 
                "P&L (₹)": "₹{:,.2f}"
            }).map(lambda val: 'color: #00e676; font-weight: bold;' if val > 0 else 'color: #ff1744; font-weight: bold;', subset=['P&L (₹)']),
            use_container_width=True, hide_index=True
        )
        
        st.markdown(f"**Liquid Cash Margin:** ₹{current_cash_balance:,.2f}")
    else:
        st.markdown(f"### Net Worth: **₹{live_net_worth:,.2f}**")
        st.caption("No open tracking positions detected on user account.")

# --- TAB 3: MASTER LEADERBOARD STANDINGS ---
with tab3:
    st.markdown("### 🏆 Global Standing Matrix")
    conn = sqlite3.connect(DB_FILE)
    all_users = pd.read_sql_query("SELECT username, balance FROM users", conn)
    all_portfolios = pd.read_sql_query("SELECT username, ticker, quantity, avg_price FROM portfolio WHERE quantity > 0", conn)
    conn.close()
    
    leader_matrix = []
    for _, u_row in all_users.iterrows():
        name_key = u_row['username']
        wallet_cash = u_row['balance']
        
        sub_portfolio = all_portfolios[all_portfolios['username'] == name_key]
        inventory_worth = 0.0
        for _, p_row in sub_portfolio.iterrows():
            t_sym = p_row['ticker']
            t_qty = p_row['quantity']
            c_price = st.session_state.market_cache.get(t_sym, {}).get('price', p_row['avg_price'])
            inventory_worth += (t_qty * c_price)
            
        calculated_net_worth = wallet_cash + inventory_worth
        net_returns = calculated_net_worth - 10000000.0 # Starting capital is ₹1 Crore
        
        leader_matrix.append({
            "User": name_key.upper(), "Net Worth": calculated_net_worth, "Total Returns (₹)": net_returns
        })
        
    if leader_matrix:
        df_leaderboard = pd.DataFrame(leader_matrix).sort_values(by="Net Worth", ascending=False).reset_index(drop=True)
        df_leaderboard.index += 1
        
        st.dataframe(
            df_leaderboard.style.format({
                "Net Worth": "₹{:,.2f}", 
                "Total Returns (₹)": "₹{:,.2f}"
            }).map(lambda val: 'color: #00e676;' if val > 0 else 'color: #ff1744;', subset=['Total Returns (₹)']),
            use_container_width=True
        )

# --- CONTROLLED BACKSTAGE TICKING ---
time.sleep(15)
global_market_sync()
st.rerun()
