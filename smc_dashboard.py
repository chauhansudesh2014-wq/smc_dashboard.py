import streamlit as st
import pandas as pd
import time
from fyers_apiv3 import fyersModel

# ============================================
# 🔐 SECURE CONFIG
# ============================================   
CLIENT_ID = st.secrets["CLIENT_ID"]
TOKEN = st.secrets["ACCESS_TOKEN"]

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, token=TOKEN)

# =========================
# SESSION INIT
# =========================
if "trades" not in st.session_state:
    st.session_state.trades = []

# =========================
# SIDEBAR
# =========================
st.sidebar.title("⚠️ SAFE EXECUTION MODE")

mode = st.sidebar.radio("Mode", ["PAPER", "LIVE"])
capital = st.sidebar.number_input("Capital", value=100000)
risk_pct = st.sidebar.slider("Risk %", 0.5, 5.0, 1.0)
max_trades = st.sidebar.number_input("Max Trades", value=3)
trail_on = st.sidebar.checkbox("Enable Trailing SL")
auto_trade = st.sidebar.checkbox("Auto Execute")

# =========================
# UI
# =========================
st.title("🔥 SMC Auto Trade Dashboard")

col1, col2, col3 = st.columns(3)
symbol = col1.text_input("Stock")
zone = col2.selectbox("Zone", ["DEMAND", "SUPPLY"])
entry = col3.number_input("Entry")

col4, col5 = st.columns(2)
sl = col4.number_input("Stop Loss")
target = col5.number_input("Target")

# =========================
# ADD TRADE
# =========================
if st.button("➕ Add Trade"):

    if symbol == "":
        st.error("❌ Enter valid symbol")
        st.stop()

    st.session_state.trades.append({
        "Symbol": symbol.upper(),
        "Zone": zone,
        "Entry": entry,
        "SL": sl,
        "Target": target,
        "Status": "WAITING",
        "Qty": 0,
        "Executed": False
    })

# =========================
# FUNCTIONS
# =========================
def get_ltp(symbol):
    try:
        data = fyers.quotes({"symbols": f"NSE:{symbol}-EQ"})
        return data["d"][0]["v"]["lp"]
    except Exception as e:
        st.error(f"LTP Error ({symbol}): {e}")
        return None


def place_order(trade):
    if trade["Executed"]:
        return

    if mode == "PAPER":
        trade["Executed"] = True
        st.warning(f"📄 PAPER TRADE: {trade['Symbol']}")
        return

    try:
        side = 1 if trade["Zone"] == "DEMAND" else -1

        order = {
            "symbol": f"NSE:{trade['Symbol']}-EQ",
            "qty": int(trade["Qty"]),
            "type": 1,  # ✅ MARKET ORDER FIX
            "side": side,
            "productType": "INTRADAY",
            "limitPrice": 0,
            "stopPrice": 0,
            "validity": "DAY"
        }

        fyers.place_order(order)
        trade["Executed"] = True
        st.success(f"✅ ORDER: {trade['Symbol']}")

    except Exception as e:
        st.error(f"Order Error: {e}")


def exit_trade(trade):
    try:
        side = -1 if trade["Zone"] == "DEMAND" else 1

        order = {
            "symbol": f"NSE:{trade['Symbol']}-EQ",
            "qty": int(trade["Qty"]),
            "type": 1,  # ✅ MARKET ORDER FIX
            "side": side,
            "productType": "INTRADAY",
            "limitPrice": 0,
            "stopPrice": 0,
            "validity": "DAY"
        }

        if mode == "LIVE":
            fyers.place_order(order)

        st.success(f"🔴 EXIT: {trade['Symbol']}")

    except Exception as e:
        st.error(f"Exit Error: {e}")

# =========================
# PROCESS
# =========================
active_trades = sum(1 for t in st.session_state.trades if t["Status"] == "ACTIVE")

for trade in st.session_state.trades:

    ltp = get_ltp(trade["Symbol"])
    if not ltp:
        continue

    trade["LTP"] = ltp

    # Position sizing
    risk_amt = capital * (risk_pct / 100)
    risk_per_share = abs(trade["Entry"] - trade["SL"])

    if risk_per_share <= 0:
        continue

    trade["Qty"] = int(risk_amt / risk_per_share)

    # Entry condition
    if trade["Status"] == "WAITING":

        if trade["Zone"] == "DEMAND" and ltp <= trade["Entry"]:
            trade["Status"] = "READY"

        elif trade["Zone"] == "SUPPLY" and ltp >= trade["Entry"]:
            trade["Status"] = "READY"

# =========================
# DISPLAY
# =========================
st.subheader("📊 Trades")

for i, trade in enumerate(st.session_state.trades):

    col1, col2, col3, col4 = st.columns([3,2,2,2])

    direction = "BUY" if trade["Zone"] == "DEMAND" else "SELL"

    col1.write(f"{trade['Symbol']} | {direction} | {trade['Status']}")
    col2.write(f"LTP: {trade.get('LTP','-')}")
    col3.write(f"Qty: {trade['Qty']}")

    # ENTRY
    if trade["Status"] == "READY" and active_trades < max_trades:

        if auto_trade:
            place_order(trade)
            trade["Status"] = "ACTIVE"
            active_trades += 1

        elif col4.button(f"EXEC {i}"):
            place_order(trade)
            trade["Status"] = "ACTIVE"
            active_trades += 1

    # EXIT + TRAILING
    if trade["Status"] == "ACTIVE":

        ltp = trade["LTP"]

        # Breakeven
        if trade["Zone"] == "DEMAND" and ltp > trade["Entry"]:
            trade["SL"] = max(trade["SL"], trade["Entry"])

        if trade["Zone"] == "SUPPLY" and ltp < trade["Entry"]:
            trade["SL"] = min(trade["SL"], trade["Entry"])

        # Trailing
        if trail_on:
            if trade["Zone"] == "DEMAND":
                trade["SL"] = max(trade["SL"], ltp * 0.995)
            else:
                trade["SL"] = min(trade["SL"], ltp * 1.005)

        # Exit conditions
        if trade["Zone"] == "DEMAND":

            if ltp <= trade["SL"]:
                exit_trade(trade)
                trade["Status"] = "SL HIT"

            elif ltp >= trade["Target"]:
                exit_trade(trade)
                trade["Status"] = "TARGET HIT"

        else:

            if ltp >= trade["SL"]:
                exit_trade(trade)
                trade["Status"] = "SL HIT"

            elif ltp <= trade["Target"]:
                exit_trade(trade)
                trade["Status"] = "TARGET HIT"

# =========================
# REFRESH
# =========================
time.sleep(3)
st.rerun()