import requests
import time
import pandas as pd


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
    params = {
        "symbol": symbol,
        "from": "2024-01-01",
        "to": time.strftime("%Y-%m-%d"),
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

SP500_TICKERS = fetch_sp500_tickers()

BATCH_SIZE = 5      # antal bolag per varv
ticker_index = 0    # håller koll på var vi är i listan

send_message(f"📊 S&P 500 universum laddat: {len(SP500_TICKERS)} bolag")

send_message("🟢 News-botten är live och lyssnar på USA-nyheter")

while True:
    try:
        batch = SP500_TICKERS[ticker_index:ticker_index + BATCH_SIZE]

        for symbol in batch:
            news_items = fetch_company_news(symbol)

            for item in news_items:
                headline = item.get("headline", "").strip()
                news_id = item.get("id")

                if not headline or not news_id:
                    continue

                if news_id in seen_ids:
                    continue

                seen_ids.add(news_id)

                message = (
                    "📰 COMPANY NEWS\n"
                    f"Company: {symbol}\n"
                    f"Headline: {headline}"
                )

                send_message(message)

            time.sleep(1)  # liten paus per bolag (viktigt)

        ticker_index += BATCH_SIZE

        if ticker_index >= len(SP500_TICKERS):
            ticker_index = 0  # börja om från början

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("Oväntat fel:", e)
        time.sleep(30)
