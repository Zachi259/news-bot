import requests
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

print("🔥 BOT VERSION CATALYST RADAR V2 🔥")

sweden = ZoneInfo("Europe/Stockholm")

# =========================
# KONFIGURATION
# =========================
BOT_TOKEN = "7980179520:AAEjd0iiVhXwkRLNcg0Htj0ATArvklHQgIE"
CHAT_ID = "5828070794"
FINNHUB_API_KEY = "d5e1e61r01qjckl18q0gd5e1e61r01qjckl18q10"

CHECK_INTERVAL = 60

BATCH_SIZE = 15
SLEEP_BETWEEN_SYMBOLS = 1

MIN_MCAP = 300       # 300M USD
MAX_MCAP = 20000     # 20B USD

FAST_START_HOUR = 14
FAST_START_MINUTE = 30

FAST_END_HOUR = 16
FAST_END_MINUTE = 30

FAST_INTERVAL_SECONDS = 20 * 60
NORMAL_INTERVAL_SECONDS = 60 * 60


# =========================
# TELEGRAM
# =========================
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        r = requests.post(
            url,
            data={"chat_id": CHAT_ID, "text": text},
            timeout=10
        )

        if r.status_code != 200:
            print("❌ Telegram-fel:", r.status_code, r.text)
        else:
            print("✅ Telegram skickade:", text[:80])

    except Exception as e:
        print("❌ Telegram exception:", e)


# =========================
# TIDSFÖNSTER 22:00 → 15:30
# =========================
def get_news_window(now):
    """
    Nyhetsfönster:
    22:00 → 12:00 = natt/pre-market-data
    12:00 → 15:30 = reset och bara nyaste inför öppning
    Efter 22:00 startar nytt dygnsfönster igen
    """

    # Efter 22:00: nytt nattfönster startar
    if now.hour >= 22:
        start = now.replace(hour=22, minute=0, second=0, microsecond=0)
        end = (now + timedelta(days=1)).replace(
            hour=12, minute=0, second=0, microsecond=0
        )

    # Mellan 12:00 och 21:59: reset-fönster från idag 12:00
    elif now.hour >= 12:
        start = now.replace(hour=12, minute=0, second=0, microsecond=0)
        end = now.replace(hour=15, minute=30, second=0, microsecond=0)

    # Före 12:00: använd gårdagens 22:00 fram till idag 12:00
    else:
        start = (now - timedelta(days=1)).replace(
            hour=22, minute=0, second=0, microsecond=0
        )
        end = now.replace(hour=12, minute=0, second=0, microsecond=0)

    return start, end

def is_valid_news_time(unix_ts, now):
    news_time = datetime.fromtimestamp(unix_ts, tz=sweden)
    start, end = get_news_window(now)

    return start <= news_time <= end


# =========================
# FINNHUB
# =========================
def fetch_company_news(symbol, now):
    url = "https://finnhub.io/api/v1/company-news"

    start, _ = get_news_window(now)

    params = {
        "symbol": symbol,
        "from": start.strftime("%Y-%m-%d"),
        "to": now.strftime("%Y-%m-%d"),
        "token": FINNHUB_API_KEY
    }

    try:
        r = requests.get(url, params=params, timeout=10)

        if r.status_code != 200:
            print(f"❌ Finnhub company-news fel {symbol}: {r.status_code} {r.text[:120]}")
            return []

        data = r.json()
        return data if isinstance(data, list) else []

    except Exception as e:
        print(f"❌ Finnhub exception {symbol}:", e)
        return []


def fetch_us_symbols():
    url = "https://finnhub.io/api/v1/stock/symbol"

    params = {
        "exchange": "US",
        "token": FINNHUB_API_KEY
    }

    try:
        r = requests.get(url, params=params, timeout=20)

        if r.status_code != 200:
            print("❌ Finnhub symbol-fel:", r.text[:200])
            return []

        data = r.json()

        return [
            x["symbol"]
            for x in data
            if x.get("type") == "Common Stock"
        ]

    except Exception as e:
        print("❌ Symbol exception:", e)
        return []


def fetch_market_cap(symbol):
    url = "https://finnhub.io/api/v1/stock/profile2"

    params = {
        "symbol": symbol,
        "token": FINNHUB_API_KEY
    }

    try:
        r = requests.get(url, params=params, timeout=10)

        if r.status_code != 200:
            return None

        data = r.json()
        return data.get("marketCapitalization")

    except:
        return None


# =========================
# CATALYST SCORING
# =========================
def catalyst_score(text):
    text = text.lower()

    high_impact_keywords = [
        "raises guidance",
        "cuts guidance",
        "guidance raised",
        "guidance cut",
        "beats estimates",
        "misses estimates",
        "above expectations",
        "below expectations",

        "fda approval",
        "fda rejects",
        "complete response letter",
        "clinical hold",

        "phase 3",
        "topline results",
        "primary endpoint met",
        "failed to meet primary endpoint",
        "statistically significant",

        "acquisition",
        "takeover",
        "merger",
        "buyout",
        "definitive agreement",

        "wins contract",
        "awarded contract",
        "receives order",
        "large order",
        "multi-year contract",
        "record backlog"
    ]

    medium_impact_keywords = [
        "earnings",
        "outlook",
        "forecast",
        "guidance",
        "revenue",
        "contract",
        "order",
        "backlog",
        "partnership",
        "trial",
        "clinical",
        "study"
    ]

    weak_alone_keywords = [
        "launch",
        "partnership",
        "forecast",
        "revenue",
        "phase",
        "study",
        "clinical",
        "deal"
    ]

    # 5 poäng: riktigt starka uttryck
    for k in high_impact_keywords:
        if k in text:
            return 5

    # 3 poäng: okej men inte alltid explosivt
    for k in medium_impact_keywords:
        if k in text:
            return 3

    # 1 poäng: svaga om de är ensamma
    for k in weak_alone_keywords:
        if k in text:
            return 1

    return 0

# =========================
# RADAR SCHEMA
# =========================
def in_fast_send_window(now):
    current_minutes = now.hour * 60 + now.minute
    start_minutes = FAST_START_HOUR * 60 + FAST_START_MINUTE
    end_minutes = FAST_END_HOUR * 60 + FAST_END_MINUTE

    return start_minutes <= current_minutes <= end_minutes


def current_send_interval(now):
    if in_fast_send_window(now):
        return FAST_INTERVAL_SECONDS

    return NORMAL_INTERVAL_SECONDS


def should_send_radar(now, last_sent_at):
    if last_sent_at is None:
        return True

    interval = current_send_interval(now)
    seconds_since_last = (now - last_sent_at).total_seconds()

    return seconds_since_last >= interval


def build_radar_message(now, news_counter, catalyst_counter, headline_tracker):
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

    if not tradable:
        return (
            f"🫀 LIVE CATALYST RADAR {now.strftime('%H:%M')}\n"
            f"No catalysts yet\n"
            f"Total news stocks: {len(news_counter)}"
        )

    lines = [
        f"🫀 LIVE CATALYST RADAR {now.strftime('%H:%M')}",
        f"Tradable stocks: {len(tradable)}",
        f"Total news stocks: {len(news_counter)}",
        ""
    ]

for sym, score, intensity, mcap in tradable[:15]:
    headline = headline_tracker.get(sym, "No headline")

    lines.append(
        f"{sym} | impact:{score}/5 | news:{intensity} | {round(mcap / 1000, 2)}B"
    )
    lines.append(f"↳ {headline[:140]}")
    lines.append("")
    
    return "\n".join(lines)

# =========================
# INIT
# =========================
seen_ids = set()
news_counter = {}
catalyst_counter = {}
headline_tracker = {}

ticker_index = 0
last_radar_sent_at = None
active_window_start = None

tickers = fetch_us_symbols()

if not tickers:
    send_message("❌ Kunde inte ladda symboler")
    raise SystemExit

send_message(f"✅ Catalyst Radar Startad\nUniverse: {len(tickers)}")


# =========================
# MAIN LOOP
# =========================
while True:
    try:
        now = datetime.now(sweden)

        window_start, window_end = get_news_window(now)

        # =========================
        # RESET VID NYTT 22:00-FÖNSTER
        # =========================
        if active_window_start != window_start:
            active_window_start = window_start
seen_ids.clear()
news_counter.clear()
catalyst_counter.clear()
headline_tracker.clear()
last_radar_sent_at = None

            send_message(
                f"🔄 Nytt news-fönster startat\n"
                f"Start: {window_start.strftime('%Y-%m-%d %H:%M')}\n"
                f"Slut: {window_end.strftime('%Y-%m-%d %H:%M')}"
            )

        # =========================
        # SAMLA NEWS
        # =========================
        batch = tickers[ticker_index:ticker_index + BATCH_SIZE]

        for symbol in batch:
            items = fetch_company_news(symbol, now)

            for item in items:
                news_id = item.get("id")
                ts = item.get("datetime")
                headline = item.get("headline", "")
                summary = item.get("summary", "")

                if not news_id or not ts:
                    continue

                if news_id in seen_ids:
                    continue

                if not is_valid_news_time(ts, now):
                    continue

                seen_ids.add(news_id)

                news_counter[symbol] = news_counter.get(symbol, 0) + 1

                text = headline + " " + summary
                score = catalyst_score(text)

if score > 0:
    old_score = catalyst_counter.get(symbol, 0)

    if score > old_score:
        catalyst_counter[symbol] = score
        headline_tracker[symbol] = headline

            time.sleep(SLEEP_BETWEEN_SYMBOLS)

        ticker_index += BATCH_SIZE

        if ticker_index >= len(tickers):
            ticker_index = 0

        # =========================
        # SKICKA RADAR
        # 14:30–16:30 = var 20:e minut
        # annars = 1 gång/timme
        # =========================
        if should_send_radar(now, last_radar_sent_at):
            message = build_radar_message(now, news_counter, catalyst_counter, headline_tracker)
            send_message(message)
            last_radar_sent_at = now

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        send_message(f"❌ Bot error: {str(e)[:150]}")
        time.sleep(30)
