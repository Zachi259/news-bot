import requests
import time
from datetime import datetime, timedelta 
from zoneinfo import ZoneInfo

print("🔥 BOT VERSION CATALYST RADAR V1 🔥")

sweden = ZoneInfo("Europe/Stockholm")

BOT_TOKEN = "7980179520:AAEjd0iiVhXwkRLNcg0Htj0ATArvklHQgIE"
CHAT_ID = "5828070794"
FINNHUB_API_KEY = "d5e1e61r01qjckl18q0gd5e1e61r01qjckl18q10"

CHECK_INTERVAL = 60

REPORT_HOUR = 15
REPORT_MINUTE = 0

BATCH_SIZE = 15
SLEEP_BETWEEN_SYMBOLS = 1

MIN_MCAP = 300
MAX_MCAP = 20000


def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)


def fetch_company_news(symbol):
    url = "https://finnhub.io/api/v1/company-news"

    today = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    params = {
        "symbol": symbol,
        "from": yesterday,
        "to": today,
        "token": FINNHUB_API_KEY
    }

    r = requests.get(url, params=params, timeout=10)
    if r.status_code != 200:
        return []

    data = r.json()
    return data if isinstance(data, list) else []


def fetch_us_symbols():
    url = "https://finnhub.io/api/v1/stock/symbol"
    params = {"exchange": "US", "token": FINNHUB_API_KEY}

    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        return []

    data = r.json()
    return [x["symbol"] for x in data if x.get("type") == "Common Stock"]


def fetch_market_cap(symbol):
    url = "https://finnhub.io/api/v1/stock/profile2"
    params = {"symbol": symbol, "token": FINNHUB_API_KEY}

    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None
        return r.json().get("marketCapitalization")
    except:
        return None


def catalyst_score(text):

    text = text.lower()

    keywords = [
        "earnings",
        "guidance",
        "fda",
        "trial",
        "contract",
        "acquisition",
        "launch",
        "approval",
        "partnership",
        "forecast",
        "revenue",
        "phase",
        "study"
    ]

    score = 0

    for k in keywords:
        if k in text:
            score += 1

    return score


def is_valid_news_time(unix_ts):

    news_time = datetime.fromtimestamp(unix_ts, tz=sweden)
    h = news_time.hour
    m = news_time.minute

    if (h == 15 and m >= 30) or (15 < h < 22):
        return False

    return True


seen_ids = set()
news_counter = {}
catalyst_counter = {}

report_sent_date = None
last_heartbeat_hour = None
ticker_index = 0

tickers = fetch_us_symbols()

if not tickers:
    send_message("❌ Kunde inte ladda symboler")
    raise SystemExit

send_message(f"✅ Catalyst Radar Startad\nUniverse: {len(tickers)}")


while True:
    try:
        now = datetime.now(sweden)

        if last_heartbeat_hour != now.hour:
            last_heartbeat_hour = now.hour

            tradable = []

            for sym, score in catalyst_counter.items():

                mcap = fetch_market_cap(sym)
                if not mcap:
                    continue

                if mcap < MIN_MCAP or mcap > MAX_MCAP:
                    continue

                intensity = news_counter.get(sym, 0)

                tradable.append((sym, score, intensity, mcap))

            tradable.sort(key=lambda x: (x[1], x[2]), reverse=True)

            if tradable:

                lines = [
                    f"🫀 LIVE CATALYST RADAR {now.strftime('%H:%M')}",
                    f"Tradable stocks: {len(tradable)}",
                    ""
                ]

                for sym, score, intensity, mcap in tradable[:10]:
                    lines.append(
                        f"{sym} | cat:{score} | news:{intensity} | {round(mcap/1000,2)}B"
                    )

                send_message("\n".join(lines))

            else:
                send_message(
                    f"🫀 LIVE CATALYST RADAR {now.strftime('%H:%M')}\nNo catalysts yet"
                )

        batch = tickers[ticker_index:ticker_index + BATCH_SIZE]

        for symbol in batch:
            items = fetch_company_news(symbol)

            for item in items:

                news_id = item.get("id")
                ts = item.get("datetime")
                headline = item.get("headline", "")

                if not news_id or not ts:
                    continue

                if news_id in seen_ids:
                    continue

                if not is_valid_news_time(ts):
                    continue

                seen_ids.add(news_id)

                news_counter[symbol] = news_counter.get(symbol, 0) + 1

                score = catalyst_score(headline)

                if score > 0:
                    catalyst_counter[symbol] = catalyst_counter.get(symbol, 0) + score

            time.sleep(SLEEP_BETWEEN_SYMBOLS)

        ticker_index += BATCH_SIZE
        if ticker_index >= len(tickers):
            ticker_index = 0

        if (
            (now.hour > REPORT_HOUR or
             (now.hour == REPORT_HOUR and now.minute >= REPORT_MINUTE))
            and report_sent_date != now.date()
        ):

            sorted_companies = sorted(
                news_counter.items(),
                key=lambda x: x[1],
                reverse=True
            )[:20]

            lines = ["📊 PREMARKET NEWS INTENSITY\n"]

            for sym, cnt in sorted_companies:
                mcap = fetch_market_cap(sym)

                if mcap:
                    lines.append(f"{sym}: {cnt} | {round(mcap/1000,2)}B")
                else:
                    lines.append(f"{sym}: {cnt}")

            send_message("\n".join(lines))

            news_counter.clear()
            catalyst_counter.clear()
            report_sent_date = now.date()

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        send_message(f"❌ Bot error: {str(e)[:150]}")
        time.sleep(30)
