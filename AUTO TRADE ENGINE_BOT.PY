import streamlit as st
import pandas as pd
import time
from fyers_apiv3 import fyersModel


# ============================================
# 🔐 FYERS CREDENTIALS & CONFIG
# ============================================


REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"

TOKEN = open("fyers_token.txt").read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, token=TOKEN)

# =========================
# SESSION
# =========================
if "trades" not in st.session_state:
    st.session_state.trades = []

# =========================
# SAFETY PANEL
# =========================
st.sidebar.title("⚠️ SAFE EXECUTION MODE")

mode = st.sidebar.radio("Mode", ["PAPER", "LIVE"])

capital = st.sidebar.number_input("Total Capital", value=100000)
risk_pct = st.sidebar.slider("Risk % per Trade", 0.5, 5.0, 1.0)
max_trades = st.sidebar.number_input("Max Active Trades", value=3)

st.sidebar.markdown("---")

# =========================
# UI INPUT
# =========================
st.title("🔥 SMC Auto Trade Dashboard")

col1, col2, col3 = st.columns(3)

symbol = col1.text_input("Stock")
zone   = col2.selectbox("Zone", ["DEMAND", "SUPPLY"])
entry  = col3.number_input("Entry")

col4, col5 = st.columns(2)
sl     = col4.number_input("Stop Loss")
target = col5.number_input("Target")

if st.button("➕ Add Trade"):

    st.session_state.trades.append({
        "Symbol": symbol.upper(),
        "Zone": zone,
        "Entry": entry,
        "SL": sl,
        "Target": target,
        "Status": "WAITING",
        "Qty": 0
    })

# =========================
# LTP FUNCTION
# =========================
def get_ltp(symbol):

    try:
        data = fyers.quotes({"symbols": f"NSE:{symbol}-EQ"})
        return data["d"][0]["v"]["lp"]
    except:
        return None

# =========================
# ORDER FUNCTION
# =========================
def place_order(trade):

    if mode == "PAPER":
        st.warning(f"📄 PAPER TRADE: {trade['Symbol']}")
        return

    try:
        side = 1 if trade["Zone"] == "DEMAND" else -1

        order = {
            "symbol": f"NSE:{trade['Symbol']}-EQ",
            "qty": int(trade["Qty"]),
            "type": 2,
            "side": side,
            "productType": "INTRADAY",
            "limitPrice": 0,
            "stopPrice": 0,
            "validity": "DAY"
        }

        fyers.place_order(order)
        st.success(f"✅ LIVE ORDER: {trade['Symbol']}")

    except Exception as e:
        st.error(f"Order Error: {e}")

# =========================
# PROCESS TRADES
# =========================
active_trades = 0

for i, trade in enumerate(st.session_state.trades):

    ltp = get_ltp(trade["Symbol"])

    if ltp is None:
        continue

    trade["LTP"] = ltp
    trade["Dist%"] = round(abs(ltp - trade["Entry"]) / ltp * 100, 2)

    # Calculate position size
    risk_amt = capital * (risk_pct / 100)
    per_share_risk = abs(trade["Entry"] - trade["SL"])

    if per_share_risk > 0:
        trade["Qty"] = int(risk_amt / per_share_risk)

    # Trigger → READY (NOT EXECUTE)
    if trade["Status"] == "WAITING":

        if trade["Zone"] == "DEMAND" and ltp <= trade["Entry"]:
            trade["Status"] = "READY"

        elif trade["Zone"] == "SUPPLY" and ltp >= trade["Entry"]:
            trade["Status"] = "READY"

    # Count active
    if trade["Status"] == "ACTIVE":
        active_trades += 1

def exit_trade(trade):

    try:
        side = -1 if trade["Zone"] == "DEMAND" else 1

        order = {
            "symbol": f"NSE:{trade['Symbol']}-EQ",
            "qty": int(trade["Qty"]),
            "type": 2,
            "side": side,
            "productType": "INTRADAY",
            "limitPrice": 0,
            "stopPrice": 0,
            "validity": "DAY"
        }

        fyers.place_order(order)
        st.success(f"🔴 EXIT: {trade['Symbol']}")

    except Exception as e:
        st.error(f"Exit Error: {e}")
# =========================
# DISPLAY + ACTION
# =========================
st.subheader("📊 Trades")

for i, trade in enumerate(st.session_state.trades):

    col1, col2, col3, col4, col5 = st.columns([2,2,2,1,1])

    direction = "BUY" if trade["Zone"] == "DEMAND" else "SELL"

    col1.write({
        "Stock": trade["Symbol"],
        "Type": direction,
        "Entry": trade["Entry"],
        "SL": trade["SL"],
        "Target": trade["Target"],
        "Status": trade["Status"]
    })

    col2.write(f"LTP: {trade.get('LTP','-')} | Dist%: {trade.get('Dist%','-')}")
    col3.write(f"Qty: {trade['Qty']}")

    # =====================
    # ENTRY BUTTON
    # =====================
    if trade["Status"] == "READY":

        if direction == "BUY":
            if col4.button(f"BUY {i}"):
                place_order(trade)
                trade["Status"] = "ACTIVE"

        else:
            if col4.button(f"SELL {i}"):
                place_order(trade)
                trade["Status"] = "ACTIVE"

    # =====================
    # EXIT ENGINE (AUTO)
    # =====================
    if trade["Status"] == "ACTIVE":

        ltp = trade.get("LTP")

        if ltp:

            # BUY TRADE
            if trade["Zone"] == "DEMAND":

                if ltp <= trade["SL"]:
                    exit_trade(trade)
                    trade["Status"] = "SL HIT"

                elif ltp >= trade["Target"]:
                    exit_trade(trade)
                    trade["Status"] = "TARGET HIT"

            # SELL TRADE
            else:

                if ltp >= trade["SL"]:
                    exit_trade(trade)
                    trade["Status"] = "SL HIT"

                elif ltp <= trade["Target"]:
                    exit_trade(trade)
                    trade["Status"] = "TARGET HIT"
# =========================
# AUTO REFRESH
# =========================
time.sleep(2)
st.rerun()
