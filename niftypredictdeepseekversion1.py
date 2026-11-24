import os
from datetime import datetime
import pandas as pd
import pytz
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ==============================
# PUT YOUR UPSTOX TOKEN HERE
# ==============================
UPSTOX_ACCESS_TOKEN = "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"

# ==============================
# PAGE & 5-SECOND REFRESH
# ==============================
st.set_page_config(
    page_title="Nifty Live (Upstox) - 5s",
    page_icon="📈",
    layout="centered"
)

st_autorefresh(interval=5_000, key="nifty_5s_refresh")

IST = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)

NIFTY_INSTRUMENT_KEY = "NSE_INDEX|Nifty 50"
UPSTOX_LTP_URL = "https://api.upstox.com/v2/market-quote/ltp"
LOCAL_LOG_FILE = "nifty_5s_logs.csv"

if "nifty_5s_logs" not in st.session_state:
    st.session_state.nifty_5s_logs = []

with st.sidebar:
    st.header("⚙️ 5-Second Nifty Feed")
    st.write(f"**IST Time:** {now_ist.strftime('%Y-%m-%d %H:%M:%S')}")
    st.write("**Interval:** Every 5 seconds")
    if st.button("🧹 Clear 5s Logs"):
        st.session_state.nifty_5s_logs = []
        if os.path.exists(LOCAL_LOG_FILE):
            os.remove(LOCAL_LOG_FILE)
        st.rerun()


def get_active_token() -> str:
    tok = (UPSTOX_ACCESS_TOKEN or "").strip()
    if tok and tok != "PASTE_YOUR_UPSTOX_ACCESS_TOKEN_HERE":
        return tok
    try:
        return str(
            st.secrets.get("UPSTOX_ACCESS_TOKEN")
            or st.secrets.get("UPSTOX_TOKEN")
            or ""
        ).strip()
    except Exception:
        return ""


def fetch_nifty_upstox(access_token: str):
    if not access_token:
        return None, "Please paste your Upstox token into UPSTOX_ACCESS_TOKEN at the top of the file."

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    params = {"instrument_key": NIFTY_INSTRUMENT_KEY}

    try:
        resp = requests.get(UPSTOX_LTP_URL, headers=headers, params=params, timeout=5)
        if resp.status_code == 401:
            return None, "401 Unauthorized: Paste a fresh daily Upstox token into UPSTOX_ACCESS_TOKEN."
        resp.raise_for_status()

        data = resp.json().get("data", {})
        quote = data.get("NSE_INDEX:Nifty 50") or data.get(NIFTY_INSTRUMENT_KEY)
        if not quote and data:
            quote = next(iter(data.values()))

        if not quote or "last_price" not in quote:
            return None, f"Unexpected Upstox response: {data}"

        ltp = float(quote["last_price"])
        prev_close = float(
            quote.get("cp") or quote.get("prev_close") or quote.get("close") or 0.0
        )

        if prev_close > 0:
            change_pts = round(ltp - prev_close, 2)
            change_pct = round((change_pts / prev_close) * 100, 2)
        else:
            change_pts = 0.0
            change_pct = 0.0

        return {
            "price": round(ltp, 2),
            "change": change_pts,
            "change_pct": change_pct,
        }, None

    except Exception as e:
        return None, f"Upstox API error: {e}"


# ==============================
# FETCH & LOG EVERY 5 SECONDS
# ==============================
st.title("📈 NIFTY 50 — Live Upstox (5s)")

active_token = get_active_token()
quote, err = fetch_nifty_upstox(active_token)

if err:
    st.error(err)
else:
    price = quote["price"]
    change = quote["change"]
    change_pct = quote["change_pct"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Nifty Price", f"{price:,.2f}")
    c2.metric("Change", f"{change:+,.2f}")
    c3.metric("Change (%)", f"{change_pct:+.2f}%")

    entry = {
        "timestamp_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": "NIFTY 50",
        "price": price,
        "change": change,
        "change_pct": change_pct,
    }
    st.session_state.nifty_5s_logs.append(entry)
    pd.DataFrame(st.session_state.nifty_5s_logs).to_csv(LOCAL_LOG_FILE, index=False)

# ==============================
# 5-SECOND LOGS DISPLAY
# ==============================
st.subheader("🕒 5-Second Logs")
if st.session_state.nifty_5s_logs:
    df_view = pd.DataFrame(st.session_state.nifty_5s_logs)
    st.dataframe(df_view.iloc[::-1].reset_index(drop=True), use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download 5s Logs CSV",
        data=df_view.to_csv(index=False),
        file_name=f"nifty_5s_logs_{now_ist.strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
else:
    st.info("Waiting for first 5-second Nifty tick...")
