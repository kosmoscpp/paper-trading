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
        
        /* Flat UI execution panel inputs */
        div[data-baseweb="input"] input { background-color: #1c2030 !important; color: #ffffff !important; border-radius: 6px !important; border: 1px solid #2f3342 !important; }
        div[data-baseweb="select"] > div { background-color: #1c2030 !important; color: #ffffff !important; border-radius: 6px !important; border: 1px solid #2f3342 !important; }
        
        /* Native TradingView Buy/Sell Button Overrides */
        .buy-btn button { background-color: #26a69a !important; color: #ffffff !important; width: 100%; border-radius: 6px; font-weight: 700; height: 45px; border: none; }
        .sell-btn button { background-color: #ef5350 !important; color: #ffffff !important; width: 100%; border-radius: 6px; font-weight: 700; height: 45px; border: none; }
        
        /* Tab Navigation Adjustments */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; justify-content: flex-end; border-bottom: 1px solid #1e222d; }
        .stTabs [data-baseweb="tab"] { font-size: 1.3rem !important; padding: 10px 15px !important; color: #848e9c; }
        .stTabs [aria-selected="true"] { color: #2962ff !important; border-bottom-color: #2962ff !important; }
    </style>
""", unsafe_allow_html=True)

# --- PERSISTENT DATABASE SETUP ---
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

# --- THE MARKETS DICTIONARY ---
STOCK_DICT = {
    "Reliance": "RELIANCE.NS", "TCS": "TCS.NS", "Infosys": "INFY.NS", "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS", "SBI": "SBIN.NS", "ITC": "ITC.NS", "Hindustan Unilever": "HINDUNILVR.NS",
    "Maruti Suzuki": "MARUTI.NS", "Mahindra & Mahindra": "M&M.NS", "Adani Ports": "ADANIPORTS.NS", "NTPC": "NTPC.NS",
    "Sun Pharma (Pharma)": "SUNPHARMA.NS", "Cipla (Pharma)": "CIPLA.NS", "ONGC (Oil)": "ONGC.NS", "IOC (Oil)": "IOC.NS",
    "Tata Power (Energy)": "TATAPOWER.NS", "Power Grid (Energy)": "POWERGRID.NS"
}

if "market_cache" not in st.session_state: st.session_state.market_cache = {}
if "last_sync_time" not in st.session_state: st.session_state.last_sync_time = 0.0

# --- THE AUTO TARGET TRACKING TRIGGER ENGINE ---
def process_auto_triggers():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username, ticker, quantity, stop_loss, take_profit FROM portfolio WHERE quantity > 0")
    positions = c.fetchall()
    
    for username, ticker, qty, sl, tp in positions:
        if ticker in st.session_state.market_cache:
            current_p = st.session_state.market_cache[ticker]["price"]
            triggered = False
            
            # Boundaries protect against the 0.0 value wipe drop out
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

# --- REAL-TIME EXCHANGE DATA SYNC ENGINE ---
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

# --- SECURITY SYSTEM LAYER GATEWAY ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = ""
    st.session_state.balance = 10000000.0

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center; margin-top: 40px;'>⚡ SECURE ACCESS TERMINAL</h2>", unsafe_allow_html=True)
    u_input = st.text_input("Username / Operator Key").strip().lower()
    p_input = st.text_input("4-Digit Access PIN", type="password").strip()
    
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

# --- FETCH REFRESHED USER SNAPSHOT ---
user_id = st.session_state.user
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT balance FROM users WHERE username = ?", (user_id,))
st.session_state.balance = c.fetchone()[0]
current_cash_balance = st.session_state.balance

df_calc = pd.read_sql_query("SELECT ticker, quantity, avg_price FROM portfolio WHERE username = ? AND quantity > 0", conn, params=(user_id,))
conn.close()

total_asset_worth = 0.0
for _, r in df_calc.iterrows():
    t_sym = r['ticker']
    t_qty = r['quantity']
    c_prc = st.session_state.market_cache.get(t_sym, {}).get('price', r['avg_price'])
    total_asset_worth += (t_qty * c_prc)

live_net_worth = current_cash_balance + total_asset_worth

# --- TRADINGVIEW DASHBOARD NAVBAR STATUS ---
st.markdown(f"""
    <div class="tv-header">
        <div class="tv-operator">● SYSTEM LINK: {user_id.upper()}</div>
        <div class="tv-networth">Net Worth: ₹{live_net_worth:,.2f}</div>
    </div>
""", unsafe_allow_html=True)

selected_stock_label = st.selectbox("Asset Selector", list(STOCK_DICT.keys()), label_visibility="collapsed")
ticker_symbol = STOCK_DICT[selected_stock_label]

tab1, tab2, tab3 = st.tabs(["🛒", "💼", "🏆"])

# --- TAB 1: EMBEDDED GRAPH TRADING ROOM ---
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
        
        chart_df = live_history.copy()
        chart_df.index = pd.to_datetime(chart_df.index).strftime('%H:%M')
        
        fig = go.Figure(data=[go.Candlestick(
            x=chart_df.index, open=chart_df['Open'], high=chart_df['High'], low=chart_df['Low'], close=chart_df['Close'],
            increasing=dict(line=dict(color='#26a69a'), fillcolor='#26a69a'),
            decreasing=dict(line=dict(color='#ef5350'), fillcolor='#ef5350')
        )])
        fig.update_layout(
            template="plotly_dark", xaxis_rangeslider_visible=False,
            margin=dict(l=5, r=5, t=5, b=5), height=270,
            paper_bgcolor='#000000', plot_bgcolor='#000000',
            xaxis=dict(showgrid=False, color='#848e9c'),
            yaxis=dict(showgrid=True, gridcolor='#1e222d', color='#848e9c', side="right")
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    else:
        st.error("Market asset sync offline.")
        live_price = 0.0

    # --- FLAT ON-PAGE EXECUTION CONTAINER (No popup modals) ---
    st.markdown("<br>", unsafe_allow_html=True)
    qty_input = st.number_input("Shares Quantity", min_value=1, step=1, value=5)
    
    col_sl, col_tp = st.columns(2)
    with col_sl:
        sl_input = st.number_input("Stop Loss Price (₹) [0 for none]", min_value=0.0, step=0.5, value=0.0)
    with col_tp:
        tp_input = st.number_input("Take Profit Price (₹) [0 for none]", min_value=0.0, step=0.5, value=0.0)
        
    order_exposure = qty_input * live_price
    st.caption(f"Estimated Execution Cost: ₹{order_exposure:,.2f}")
    
    col_buy, col_sell = st.columns(2)
    with col_buy:
        st.markdown('<div class="buy-btn">', unsafe_allow_html=True)
        if st.button("BUY", key="exec_buy"):
            if order_exposure > current_cash_balance:
                st.error("Insufficient Cash Margin Balance.")
            elif live_price == 0.0:
                st.error("Invalid execution data frame.")
            else:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                new_cash_balance = current_cash_balance - order_exposure
                c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_cash_balance, user_id))
                
                c.execute("SELECT quantity, avg_price FROM portfolio WHERE username = ? AND ticker = ?", (user_id, ticker_symbol))
                exists = c.fetchone()
                
                if exists and exists[0] > 0:
                    old_qty, old_avg = exists
                    updated_qty = old_qty + qty_input
                    updated_avg = ((old_qty * old_avg) + order_exposure) / updated_qty
                    c.execute("UPDATE portfolio SET quantity = ?, avg_price = ?, stop_loss = ?, take_profit = ? WHERE username = ? AND ticker = ?", 
                              (updated_qty, updated_avg, sl_input, tp_input, user_id, ticker_symbol))
                else:
                    c.execute("INSERT OR REPLACE INTO portfolio (username, ticker, quantity, avg_price, stop_loss, take_profit) VALUES (?, ?, ?, ?, ?, ?)", 
                              (user_id, ticker_symbol, qty_input, live_price, sl_input, tp_input))
                conn.commit()
                conn.close()
                st.success("Market Buy order filled!")
                time.sleep(0.4)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_sell:
        st.markdown('<div class="sell-btn">', unsafe_allow_html=True)
        if st.button("SELL", key="exec_sell"):
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT quantity FROM portfolio WHERE username = ? AND ticker = ?", (user_id, ticker_symbol))
            exists = c.fetchone()
            
            if not exists or exists[0] < qty_input:
                st.error("Insufficient tracking inventory shares.")
                conn.close()
            else:
                updated_qty = exists[0] - qty_input
                returned_funds = qty_input * live_price
                new_cash_balance = current_cash_balance + returned_funds
                c.execute("UPDATE users SET balance = ? WHERE username = ?", (new_cash_balance, user_id))
                c.execute("UPDATE portfolio SET quantity = ? WHERE username = ? AND ticker = ?", (updated_qty, user_id, ticker_symbol))
                conn.commit()
                conn.close()
                st.success("Market Sell liquidations complete!")
                time.sleep(0.4)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- TAB 2: ADVANCED REAL-TIME PORTFOLIO LEDGER ---
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
        
        st.dataframe(
            df_display.style.format({
                "Avg Buy Price": "₹{:,.2f}", "Current Price": "₹{:,.2f}",
                "Stop Loss": lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "None", 
                "Take Profit": lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "None", 
                "P&L (₹)": "₹{:,.2f}"
            }).map(lambda val: 'color: #00e676; font-weight: bold;' if val > 0 else 'color: #ff1744; font-weight: bold;', subset=['P&L (₹)']),
            use_container_width=True, hide_index=True
        )
    else:
        st.caption("No tracking positions active.")
    st.markdown(f"**Liquid Wallet Cash Margin:** ₹{current_cash_balance:,.2f}")

# --- TAB 3: DYNAMIC LEADERBOARD METRIC STANDINGS ---
with tab3:
    st.markdown("### 🏆 Leaderboard Standings Matrix")
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
        net_returns = calculated_net_worth - 10000000.0
        
        leader_matrix.append({
            "User": name_key.upper(), "Net Worth": calculated_net_worth, "Total Returns (₹)": net_returns
        })
        
    if leader_matrix:
        df_leaderboard = pd.DataFrame(leader_matrix).sort_values(by="Net Worth", ascending=False).reset_index(drop=True)
        df_leaderboard.index += 1
        
        st.dataframe(
            df_leaderboard.style.format({
                "Net Worth": "₹{:,.2f}", "Total Returns (₹)": "₹{:,.2f}"
            }).map(lambda val: 'color: #00e676;' if val > 0 else 'color: #ff1744;', subset=['Total Returns (₹)']),
            use_container_width=True
        )

# --- STEADY CONTROLLED DELAY TICK REFRESH ---
time.sleep(15)
global_market_sync()
st.rerun()
#kaash kaam kare ab...
