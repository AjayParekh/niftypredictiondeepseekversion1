
import streamlit as st
import requests
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# PAGE CONFIG
st.set_page_config(
    page_title="Nifty Live Price",
    page_icon="📈",
    layout="centered"
)

# REFRESH EVERY 5 SECONDS
st_autorefresh(interval=5000, key="nifty_refresh")

# CONFIGURATION
API_URL = "https://api.upstox.com/v3/market-quote/quotes"
INSTRUMENT_KEY = "NSE_INDEX|Nifty 50"
IST = pytz.timezone("Asia/Kolkata")

# FETCH NIFTY PRICE FROM UPSTOX
def get_nifty_data():

    token = st.secrets["UPSTOX_TOKEN"]

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    params = {
        "instrument_key": INSTRUMENT_KEY
    }

    response = requests.get(
        API_URL,
        headers=headers,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    result = response.json()

    if result.get("status") != "success":
        raise ValueError("Upstox API returned an unsuccessful response")

    data = result["data"]["NSE_INDEX:Nifty 50"]

    price = float(data["last_price"])
    change = float(data["net_change"])

    previous_close = price - change

    change_percent = (
        (change / previous_close) * 100
        if previous_close else 0
    )

    return price, change, change_percent


# DASHBOARD
st.title("📈 NIFTY 50 LIVE")

try:

    price, change, change_percent = get_nifty_data()

    st.metric(
        label="Nifty Current Price",
        value=f"{price:,.2f}",
        delta=f"{change:+,.2f} ({change_percent:+.2f}%)"
    )

    st.success("Connected to Upstox")

except KeyError:
    st.error("Please configure UPSTOX_TOKEN in Streamlit Secrets.")

except Exception as e:
    st.error(f"Unable to fetch Nifty data: {e}")

# LAST UPDATED
now = datetime.now(IST)

st.caption(
    f"Last updated: {now.strftime('%d-%m-%Y %H:%M:%S')} IST"
)

st.caption("Source: Upstox API | Refresh: 5 seconds")
