import requests
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sweden = ZoneInfo("Europe/Stockholm")

# =========================
# KONFIGURATION
# =========================
BOT_TOKEN = "7980179520:AAEjd0iiVhXwkRLNcg0Htj0ATArvklHQgIE"
CHAT_ID = "5828070794"
FINNHUB_API_KEY = "d5e1e61r01qjckl18q0gd5e1e61r01qjckl18q10"

CHECK_INTERVAL = 60
REPORT_HOUR = 15        # t.ex. 15:00 svensk tid
REPORT_MINUTE = 00

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
def fetch_us_symbols():
    url = "https://finnhub.io/api/v1/stock/symbol"
    params = {
        "exchange": "US",
        "token": FINNHUB_API_KEY
    }

    r = requests.get(url, params=params, timeout=10)

    if r.status_code != 200:
        print("❌ Finnhub symbol-fel:", r.text)
        return []

    data = r.json()

    # Filtrera till vanliga aktier (inte ETF/ADR/etc)
    symbols = [
        item["symbol"]
        for item in data
        if item.get("type") == "Common Stock"
    ]

    return symbols
    
# =========================
# S&P 500 – HÄMTA UNIVERSUM
# =========================
def fetch_sp500_tickers():
    url = "https://finnhub.io/api/v1/index/constituents"
    params = {
        "symbol": "^GSPC",
        "token": FINNHUB_API_KEY
    }

    r = requests.get(url, params=params, timeout=10)

    if r.status_code != 200:
        print("❌ Finnhub index-fel:", r.text)
        return []

    data = r.json()

    tickers = data.get("constituents", [])
    return tickers

# =========================
# MAIN
# =========================
seen_ids = set()
news_counter = {}
last_report_date = None

SP500_TICKERS = fetch_us_symbols()

if not SP500_TICKERS:
    send_message("❌ Kunde inte ladda S&P 500 från Finnhub")
    raise SystemExit

BATCH_SIZE = 15
ticker_index = 0

send_message(f"📊 S&P 500 universum laddat: {len(SP500_TICKERS)} bolag")
send_message("🟢 News-botten är live och lyssnar på USA-nyheter")

def is_valid_news_time(unix_ts):
    """
    Returnerar True om nyheten ska räknas med i nästa dags rapport
    Exkluderar nyheter mellan 15:30–22:00 svensk tid
    """
    news_time = datetime.fromtimestamp(unix_ts, tz=sweden)

    hour = news_time.hour
    minute = news_time.minute

    # Exkludera 15:30–22:00
    if (hour == 15 and minute >= 30) or (15 < hour < 22):
        return False

    return True

while True:
    try:
        now = datetime.now(sweden)

        # =========================
        # SAMLA COMPANY-NEWS (TYST)
        # =========================
        batch = SP500_TICKERS[ticker_index:ticker_index + BATCH_SIZE]

        for symbol in batch:
            news_items = fetch_company_news(symbol)

            for item in news_items:
                news_id = item.get("id")
                headline = item.get("headline", "").strip()
                news_ts = item.get("datetime")

                if not news_id or not headline or not news_ts:
                    continue

                # 🔥 TIDSFILTER 15:30–22:00
                if not is_valid_news_time(news_ts):
                    continue

                if news_id in seen_ids:
                    continue

                seen_ids.add(news_id)
                news_counter[symbol] = news_counter.get(symbol, 0) + 1

            time.sleep(1)

        ticker_index += BATCH_SIZE
        if ticker_index >= len(SP500_TICKERS):
            ticker_index = 0

        # =========================
        # SKICKA DAGLIG RAPPORT
        # =========================
        if (
            now.hour > REPORT_HOUR
            or (now.hour == REPORT_HOUR and now.minute >= REPORT_MINUTE)
        ) and last_report_date != now.date():

            if news_counter:
                sorted_companies = sorted(
                    news_counter.items(),
                    key=lambda x: x[1]
                )

                report_lines = ["📊 PRE-MARKET NEWS INTENSITY (24h)\n"]
                for company, count in sorted_companies:
                    report_lines.append(f"{company}: {count}")

                send_message("\n".join(report_lines))
            else:
                send_message(
                    "📊 PRE-MARKET NEWS INTENSITY\nInga nyheter senaste 24h"
                )

            news_counter.clear()
            last_report_date = now.date()

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("Oväntat fel:", e)
        time.sleep(30)
