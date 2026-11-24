import os
from datetime import datetime
import pandas as pd
import pytz
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Optional GitHub sync support
try:
    from github import Github, GithubException
    HAS_PYGITHUB = True
except ImportError:
    HAS_PYGITHUB = False

# ==============================
# PAGE & 5-SECOND REFRESH CONFIG
# ==============================
st.set_page_config(
    page_title="Nifty Live (Upstox) - Step 1",
    page_icon="📈",
    layout="centered"
)

# Refresh every 5 seconds (5000 ms)
st_autorefresh(interval=5_000, key="nifty_5s_refresh")

IST = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)

NIFTY_INSTRUMENT_KEY = "NSE_INDEX|Nifty 50"
UPSTOX_LTP_URL = "https://api.upstox.com/v2/market-quote/ltp"
LOCAL_LOG_FILE = "nifty_5s_logs.csv"

# ==============================
# SECRETS & SIDEBAR SETTINGS
# ==============================
UPSTOX_TOKEN = st.secrets.get("UPSTOX_ACCESS_TOKEN", "")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "")  # e.g. "username/repo-name"
GITHUB_LOG_PATH = st.secrets.get("GITHUB_LOG_PATH", "logs/nifty_5s_logs.csv")

with st.sidebar:
    st.header("⚙️ Step 1 Settings")
    st.write(f"**IST Time:** {now_ist.strftime('%Y-%m-%d %H:%M:%S')}")
    st.write("**Refresh Interval:** 5 seconds")
    sync_to_github = st.checkbox(
        "Push log snapshot to GitHub",
        value=False,
        help="Enable only when needed; pushing every 5s continuously can trigger GitHub API rate limits."
    )
    if st.button("🧹 Clear 5s Logs"):
        st.session_state.nifty_logs = []
        if os.path.exists(LOCAL_LOG_FILE):
            os.remove(LOCAL_LOG_FILE)
        st.rerun()

# ==============================
# UPSTOX FETCH FUNCTION (ONLY NIFTY)
# ==============================
@st.cache_data(ttl=4, show_spinner=False)
def fetch_nifty_upstox(access_token: str):
    if not access_token:
        return None, "Missing UPSTOX_ACCESS_TOKEN in Streamlit Secrets."

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token.strip()}",
    }
    params = {"instrument_key": NIFTY_INSTRUMENT_KEY}

    try:
        resp = requests.get(UPSTOX_LTP_URL, headers=headers, params=params, timeout=5)
        resp.raise_for_status()
        payload = resp.json()

        data = payload.get("data", {})
        # Upstox keys in response can vary slightly in casing/format (e.g., "NSE_INDEX:Nifty 50")
        quote = data.get("NSE_INDEX:Nifty 50") or data.get(NIFTY_INSTRUMENT_KEY)
        if not quote and data:
            quote = next(iter(data.values()))

        if not quote or "last_price" not in quote:
            return None, f"Unexpected Upstox response: {payload}"

        ltp = float(quote["last_price"])
        prev_close = float(quote.get("cp") or quote.get("prev_close") or quote.get("close") or 0.0)

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


def push_csv_to_github(df: pd.DataFrame, token: str, repo_name: str, file_path: str):
    if not (HAS_PYGITHUB and token and repo_name):
        return False, "GitHub token/repo/PyGithub not configured."
    try:
        gh = Github(token)
        repo = gh.get_repo(repo_name)
        csv_text = df.to_csv(index=False)
        commit_msg = f"5s Nifty log update ({now_ist.strftime('%Y-%m-%d %H:%M:%S')} IST)"
        try:
            existing = repo.get_contents(file_path)
            repo.update_file(existing.path, commit_msg, csv_text, existing.sha)
        except GithubException as ge:
            if ge.status == 404:
                repo.create_file(file_path, commit_msg, csv_text)
            else:
                return False, f"GitHub error: {ge}"
        return True, f"Synced to {repo_name}/{file_path}"
    except Exception as e:
        return False, f"GitHub sync failed: {e}"


# ==============================
# FETCH & LOG EVERY 5 SECONDS
# ==============================
if "nifty_logs" not in st.session_state:
    st.session_state.nifty_logs = []

quote_data, err_msg = fetch_nifty_upstox(UPSTOX_TOKEN)

st.title("📈 NIFTY 50 — Live Upstox (Step 1)")

if err_msg:
    st.error(err_msg)
else:
    price = quote_data["price"]
    change = quote_data["change"]
    change_pct = quote_data["change_pct"]

    # Show ONLY Nifty Price, Change, and Change in %
    c1, c2, c3 = st.columns(3)
    c1.metric("Nifty Price", f"{price:,.2f}")
    c2.metric("Change", f"{change:+,.2f}")
    c3.metric("Change (%)", f"{change_pct:+.2f}%")

    # Append 5-second log entry
    log_entry = {
        "timestamp_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": "NIFTY 50",
        "price": price,
        "change": change,
        "change_pct": change_pct,
    }
    st.session_state.nifty_logs.append(log_entry)

    log_df = pd.DataFrame(st.session_state.nifty_logs)
    log_df.to_csv(LOCAL_LOG_FILE, index=False)

    if sync_to_github:
        ok, gh_msg = push_csv_to_github(log_df, GITHUB_TOKEN, GITHUB_REPO, GITHUB_LOG_PATH)
        if ok:
            st.caption(f"✅ {gh_msg}")
        else:
            st.caption(f"⚠️ {gh_msg}")

# ==============================
# 5-SECOND LOGS VIEW
# ==============================
st.subheader("🕒 5-Second Logs")
if st.session_state.nifty_logs:
    df_display = pd.DataFrame(st.session_state.nifty_logs).iloc[::-1].reset_index(drop=True)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download 5s Logs CSV",
        data=pd.DataFrame(st.session_state.nifty_logs).to_csv(index=False),
        file_name=f"nifty_5s_logs_{now_ist.strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
else:
    st.info("Waiting for first 5-second Nifty tick...")
