import requests
import time

# =========================
# KONFIGURATION
# =========================
BOT_TOKEN = "7980179520:AAEjd0iiVhXwkRLNcg0Htj0ATArvklHQgIE"
CHAT_ID = "5828070794"
FINNHUB_API_KEY = "d5e1e61r01qjckl18q0gd5e1e61r01qjckl18q10"

CHECK_INTERVAL = 60  # sekunder mellan varje koll

# =========================
# TELEGRAM
# =========================
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text
    }

    r = requests.post(url, data=payload)

    if r.status_code != 200:
        print("Telegram-fel:", r.text)

# =========================
# FINNHUB – NYHETER
# =========================
def fetch_news():
    url = "https://finnhub.io/api/v1/news"
    params = {
        "category": "general",
        "token": FINNHUB_API_KEY
    }

    r = requests.get(url, params=params)

    if r.status_code != 200:
        print("Finnhub HTTP-fel:", r.text)
        return []

    data = r.json()

    # 🔒 VIKTIG SÄKERHET:
    # Finnhub kan ibland returnera string eller dict vid fel
    if not isinstance(data, list):
        print("Oväntat Finnhub-svar:", data)
        return []

    return data

# =========================
# MAIN
# =========================
seen_ids = set()

send_message("🟢 News-botten är live och lyssnar på USA-nyheter")

while True:
    try:
        news = fetch_news()

        for item in news:
            if not isinstance(item, dict):
                continue

            headline = item.get("headline", "").strip()
            related = item.get("related", "").strip()
            news_id = item.get("id")

            if not headline or not related or not news_id:
                continue

            if news_id in seen_ids:
                continue

            seen_ids.add(news_id)

            message = (
                "📰 NEWS ALERT\n"
                f"Ticker: {related}\n"
                f"Headline: {headline}"
            )

            send_message(message)

        time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        send_message("🔴 News-botten stoppades manuellt")
        break

    except Exception as e:
        print("Oväntat fel:", e)
        time.sleep(30)

