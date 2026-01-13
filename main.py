import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import pytz

sweden = pytz.timezone("Europe/Stockholm")

# =========================
# KONFIGURATION
# =========================
BOT_TOKEN = "7980179520:AAEjd0iiVhXwkRLNcg0Htj0ATArvklHQgIE"
CHAT_ID = "5828070794"
FINNHUB_API_KEY = "d5e1e61r01qjckl18q0gd5e1e61r01qjckl18q10"

CHECK_INTERVAL = 60

# =========================
# TELEGRAM
# =========================
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text
    }

    r = requests.post(url, data=payload, timeout=10)

    if r.status_code != 200:
        print("❌ Telegram-fel:", r.status_code, r.text)
    else:
        print("✅ Telegram skickade:", text[:50])

# =========================
# FINNHUB
# =========================
def fetch_company_news(symbol):
    url = "https://finnhub.io/api/v1/company-news"

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    params = {
        "symbol": symbol,
        "from": yesterday,
        "to": today,
        "token": FINNHUB_API_KEY
    }

    r = requests.get(url, params=params)

    if r.status_code != 200:
        print(f"Finnhub company-news fel ({symbol}):", r.text)
        return []

    data = r.json()

    if not isinstance(data, list):
        return []

    return data
    
# =========================
# S&P 500 – HÄMTA UNIVERSUM
# =========================
def fetch_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)",
        "Accept-Language": "en-US,en;q=0.9",
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    tables = pd.read_html(response.text)
    df = tables[0]

    tickers = df["Symbol"].tolist()
    return tickers

# =========================
# MAIN
# =========================
seen_ids = set()
news_counter = {}

last_report_date = None

SP500_TICKERS = fetch_sp500_tickers()

BATCH_SIZE = 15
ticker_index = 0

send_message(f"📊 S&P 500 universum laddat: {len(SP500_TICKERS)} bolag")
send_message("🟢 News-botten är live och lyssnar på USA-nyheter")

while True:
    try:
        now = datetime.now(sweden)

        # =========================
        # SKICKA PRE-MARKET RAPPORT 14:30
        # =========================
        if now.hour == 22 and 36 <= now.minute < 37:
            if last_report_date != now.date():

                if news_counter:
                    sorted_companies = sorted(
                        news_counter.items(),
                        key=lambda x: x[1]
                    )

                    report_lines = ["📊 PRE-MARKET NEWS INTENSITY (24h)\n"]

                    for company, count in sorted_companies:
                        report_lines.append(
                            f"Company: {company}\nNyheter: {count}\n────────────"
                        )

                    send_message("\n".join(report_lines))
                else:
                    send_message(
                        "📊 PRE-MARKET NEWS INTENSITY\n"
                        "Inga company-nyheter senaste 24h"
                    )

                news_counter.clear()
                last_report_date = now.date()

        # =========================
        # SAMLA COMPANY-NEWS (TYST)
        # =========================
        batch = SP500_TICKERS[ticker_index:ticker_index + BATCH_SIZE]

        for symbol in batch:
            news_items = fetch_company_news(symbol)

            for item in news_items:
                news_id = item.get("id")
                headline = item.get("headline", "").strip()

                if not news_id or not headline:
                    continue

                if news_id in seen_ids:
                    continue

                seen_ids.add(news_id)
                news_counter[symbol] = news_counter.get(symbol, 0) + 1

            time.sleep(1)

        ticker_index += BATCH_SIZE
        if ticker_index >= len(SP500_TICKERS):
            ticker_index = 0

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("Oväntat fel:", e)
        time.sleep(30)

