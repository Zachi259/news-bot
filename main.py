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

REPORT_HOUR = 15
REPORT_MINUTE = 00

HEARTBEAT_EVERY_MIN = 30  # ping var 30:e minut så du ser att den lever

BATCH_SIZE = 15
SLEEP_BETWEEN_SYMBOLS = 1  # snäll mot Finnhub

# =========================
# TELEGRAM
# =========================
def send_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    r = requests.post(url, data=payload, timeout=10)

    if r.status_code != 200:
        print("❌ Telegram-fel:", r.status_code, r.text)
    else:
        print("✅ Telegram skickade:", text[:80])

# =========================
# FINNHUB
# =========================
def fetch_company_news(symbol: str):
    url = "https://finnhub.io/api/v1/company-news"

    # kör UTC på datum-parametrarna (Funkar stabilt för Finnhub)
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
        # rate-limit mm
        print(f"❌ Finnhub company-news fel {symbol}: {r.status_code} {r.text[:120]}")
        return []

    data = r.json()
    return data if isinstance(data, list) else []

def fetch_us_symbols():
    # OBS: Detta ger TUSENTALS symboler => kan bli tungt + rate limits.
    # Om du vill: byt till en mindre lista (S&P500) när det är stabilt.
    url = "https://finnhub.io/api/v1/stock/symbol"
    params = {"exchange": "US", "token": FINNHUB_API_KEY}

    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        print("❌ Finnhub symbol-fel:", r.text[:200])
        return []

    data = r.json()
    symbols = [x["symbol"] for x in data if x.get("type") == "Common Stock"]
    return symbols

# =========================
# TIDSFILTER
# =========================
def is_valid_news_time(unix_ts: int) -> bool:
    """
    True = räknas in i rapporten.
    Exkluderar 15:30–22:00 svensk tid.
    """
    news_time = datetime.fromtimestamp(unix_ts, tz=sweden)
    h, m = news_time.hour, news_time.minute

    # 15:30–21:59 exkluderas
    if (h == 15 and m >= 30) or (15 < h < 22):
        return False

    # 22:00 och framåt räknas med igen (natten/early morning)
    return True

# =========================
# MAIN
# =========================
seen_ids = set()
news_counter = {}

report_sent_date = None
last_heartbeat_bucket = None

tickers = fetch_us_symbols()
if not tickers:
    send_message("❌ Kunde inte ladda symboler från Finnhub (kolla API-key / quota)")
    raise SystemExit

send_message(f"✅ Bot startad. Universe: {len(tickers)} symboler.")
send_message("🟢 Samlar news tyst + skickar daglig rapport.")

ticker_index = 0

while True:
    try:
        now = datetime.now(sweden)

        # 1️⃣ HEARTBEAT
        ...

        # 2️⃣ SAMLA NEWS (tyst)
        batch = tickers[ticker_index:ticker_index + BATCH_SIZE]
        for symbol in batch:
            ...
        ticker_index += BATCH_SIZE

        # 3️⃣ DAGLIG RAPPORT (SIST!)
        if should_send_today:
            ...

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        # Skicka fel till Telegram så du aldrig blir blind
        try:
            send_message(f"❌ Bot error: {type(e).__name__}: {str(e)[:200]}")
        except Exception:
            pass

        print("Oväntat fel:", e)
        time.sleep(30)
