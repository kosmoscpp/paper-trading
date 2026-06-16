
# ⚡ NSE Live Terminal

A real-time Indian Stock Market simulation dashboard designed for high-frequency virtual paper trading. This terminal allows users to authenticate securely, track live intraday stock vectors, allocate a starting capital of ₹1 Crore across a diversified asset matrix, and compete in real-time on a live rankings leaderboard.

## 🔗 Live Application
Access the production terminal directly at: https://paper-trader-kosmos.up.railway.app/

## 🚀 Features

* **📦 Main-Screen Authentication:** Clean, zero-sidebar authentication. Profiles automatically initialize upon custom Nickname and 4-digit PIN configuration.
* **🛒 Live Trade Room:** Blazing-fast execution windows for Market BUY and Market SELL orders.
* **📊 Intraday Vector Charts:** Powered by **Plotly**, charts automatically crop boundaries tightly around high-frequency market fluctuations—no flat lines or zero-baselines.
* **💼 Asset Allocation Matrix:** Comprehensive portfolio tracking detailing Average Buy Price, Live Value, and realized Net P&L metrics.
* **🏆 Elite Trader Standings:** A dynamic live leaderboard calculated directly from your net worth (Liquid Cash + Live Asset Value).
* **⚙️ SRE Resiliency Pipeline:** Built-in global background sync engine that polls data every 15 seconds across all core instruments simultaneously, gracefully utilizing memory cache fallbacks if upstream APIs get rate-limited.

## 📈 Supported Core Instruments

The engine tracks 12 massive, high-liquidity Indian blue-chip giants to support deep portfolio diversification strategies:
* **Tech:** TCS, Infosys
* **Banking:** HDFC Bank, ICICI Bank, SBI
* **Energy/Infra:** Reliance Industries, Adani Ports, NTPC
* **Automobile:** Maruti Suzuki, Mahindra & Mahindra (M&M)
* **Consumer Goods:** ITC, Hindustan Unilever (HUL)

## 🛠️ Stack Architecture

* **Frontend Framework:** Streamlit (Python UI Engine)
* **Data Layer:** SQLite3 (Local containerized transactional relational database)
* **API Stream:** Yahoo Finance (`yfinance` SDK)
* **Visualization Engine:** Plotly Open-Source Graphing Objects
* **Deployment Platform:** Railway Container Runtime Environment via Docker Pipeline

## 🧑‍💻 How to Run Locally

If you want to clone this repository and spin it up on your local machine, follow these infrastructure setup commands:

1. **Clone the Repo:**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git)
   cd YOUR_REPO_NAME

```
 2. **Install Package Dependencies:**
   ```bash
   pip install -r requirements.txt
   
   ```
 3. **Initialize the Streamlit Runtime Engine:**
   ```bash
   streamlit run app.py
   ```
