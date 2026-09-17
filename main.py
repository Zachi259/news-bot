import requests
import time
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

print("🔥 BOT VERSION CATALYST RADAR V3 + EARNINGS 🔥")

sweden = ZoneInfo("Europe/Stockholm")

# =========================
# KONFIGURATION
# =========================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

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

# Earnings-kalendern uppdateras var 15:e minut.
# Det är bara ett extra Finnhub-anrop per uppdatering.
EARNINGS_REFRESH_SECONDS = 15 * 60


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

    if now.hour >= 22:
        start = now.replace(hour=22, minute=0, second=0, microsecond=0)
        end = (now + timedelta(days=1)).replace(
            hour=12, minute=0, second=0, microsecond=0
        )

    elif now.hour >= 12:
        start = now.replace(hour=12, minute=0, second=0, microsecond=0)
        end = now.replace(hour=15, minute=30, second=0, microsecond=0)

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

    except Exception:
        return None


def fetch_earnings_calendar(now):
    """
    Hämtar earnings för datumen som kan beröra det aktiva news-fönstret.
    Returnerar {symbol: event}.
    """
    start, _ = get_news_window(now)
    url = "https://finnhub.io/api/v1/calendar/earnings"

    params = {
        "from": start.strftime("%Y-%m-%d"),
        "to": now.strftime("%Y-%m-%d"),
        "token": FINNHUB_API_KEY
    }

    try:
        r = requests.get(url, params=params, timeout=15)

        if r.status_code != 200:
            print("❌ Finnhub earnings-fel:", r.status_code, r.text[:200])
            return None

        data = r.json().get("earningsCalendar", [])
        earnings = {}

        for item in data:
            symbol = item.get("symbol")
            if symbol:
                earnings[symbol] = item

        print(f"📊 Earnings loaded: {len(earnings)} bolag")
        return earnings

    except Exception as e:
        print("❌ Earnings calendar exception:", e)
        return None


# =========================
# EARNINGS ANALYS
# =========================
def to_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_surprise(actual, estimate):
    actual = to_float(actual)
    estimate = to_float(estimate)

    if actual is None or estimate is None:
        return None

    # Procent mot exakt 0 blir inte meningsfullt.
    if abs(estimate) < 0.000001:
        return None

    return ((actual - estimate) / abs(estimate)) * 100


def eps_impact(abs_surprise):
    if abs_surprise is None:
        return 0
    if abs_surprise >= 20:
        return 5
    if abs_surprise >= 10:
        return 4
    if abs_surprise >= 5:
        return 3
    if abs_surprise >= 2:
        return 2
    return 1


def revenue_impact(abs_surprise):
    if abs_surprise is None:
        return 0
    if abs_surprise >= 10:
        return 5
    if abs_surprise >= 5:
        return 4
    if abs_surprise >= 3:
        return 3
    if abs_surprise >= 1:
        return 2
    return 1


def surprise_direction(value):
    if value is None:
        return 0
    if value > 0.25:
        return 1
    if value < -0.25:
        return -1
    return 0


def analyze_earnings(event):
    """
    Ger ett impact-värde 1–5 för en publicerad rapport.
    5/5 betyder stor avvikelse, inte automatiskt positivt.
    """
    if not event:
        return None

    eps_actual = to_float(event.get("epsActual"))
    eps_estimate = to_float(event.get("epsEstimate"))
    revenue_actual = to_float(event.get("revenueActual"))
    revenue_estimate = to_float(event.get("revenueEstimate"))

    eps_surprise = calculate_surprise(eps_actual, eps_estimate)
    revenue_surprise = calculate_surprise(revenue_actual, revenue_estimate)

    # Om Finnhub ännu inte har actual-värden är rapporten sannolikt inte
    # publicerad i kalenderdatan ännu. Då ska den inte påverka impact.
    if eps_surprise is None and revenue_surprise is None:
        return None

    eps_score = eps_impact(abs(eps_surprise)) if eps_surprise is not None else 0
    revenue_score = revenue_impact(abs(revenue_surprise)) if revenue_surprise is not None else 0

    impact = max(eps_score, revenue_score)

    eps_dir = surprise_direction(eps_surprise)
    revenue_dir = surprise_direction(revenue_surprise)

    # Om både EPS och revenue tydligt slår/missar åt samma håll
    # får rapporten en liten förstärkning, max 5/5.
    if (
        eps_dir != 0
        and eps_dir == revenue_dir
        and eps_score >= 3
        and revenue_score >= 3
    ):
        impact = min(5, impact + 1)

    dirs = [d for d in [eps_dir, revenue_dir] if d != 0]

    if not dirs:
        direction = "NEUTRAL"
    elif all(d > 0 for d in dirs):
        direction = "POSITIVE"
    elif all(d < 0 for d in dirs):
        direction = "NEGATIVE"
    else:
        direction = "MIXED"

    return {
        "impact": impact,
        "direction": direction,
        "eps_actual": eps_actual,
        "eps_estimate": eps_estimate,
        "eps_surprise": eps_surprise,
        "revenue_actual": revenue_actual,
        "revenue_estimate": revenue_estimate,
        "revenue_surprise": revenue_surprise
    }


def format_pct(value):
    if value is None:
        return "N/A"
    return f"{value:+.1f}%"


def format_value(value):
    if value is None:
        return "N/A"

    value = float(value)
    abs_value = abs(value)

    # Revenue kan komma som stora råtal. Gör dem läsbara om så är fallet.
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"

    return f"{value:.2f}"


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
        "guidance",
        "contract",
        "order",
        "backlog",
        "trial"
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

    for k in high_impact_keywords:
        if k in text:
            return 5

    for k in medium_impact_keywords:
        if k in text:
            return 3

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


def build_radar_message(
    now,
    news_counter,
    catalyst_counter,
    headline_tracker,
    earnings_tracker
):
    tradable = []

    for sym, score in catalyst_counter.items():
        mcap = fetch_market_cap(sym)

        if not mcap:
            continue

        if mcap < MIN_MCAP or mcap > MAX_MCAP:
            continue

        intensity = news_counter.get(sym, 0)
        headline = headline_tracker.get(sym, "No headline")
        earnings = earnings_tracker.get(sym)

        tradable.append((sym, score, intensity, mcap, headline, earnings))

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

    for sym, score, intensity, mcap, headline, earnings in tradable[:15]:
        lines.append(
            f"{sym} | impact:{score}/5 | news:{intensity} | {round(mcap / 1000, 2)}B"
        )

        if earnings:
            if earnings["direction"] == "POSITIVE":
                icon = "🟢"
            elif earnings["direction"] == "NEGATIVE":
                icon = "🔴"
            elif earnings["direction"] == "MIXED":
                icon = "🟡"
            else:
                icon = "⚪"

            lines.append(
                f"📊 Earnings {icon} {earnings['direction']}"
            )

            if earnings["eps_surprise"] is not None:
                lines.append(
                    "EPS: "
                    f"{format_value(earnings['eps_actual'])} vs "
                    f"{format_value(earnings['eps_estimate'])} "
                    f"({format_pct(earnings['eps_surprise'])})"
                )

            if earnings["revenue_surprise"] is not None:
                lines.append(
                    "Revenue: "
                    f"{format_value(earnings['revenue_actual'])} vs "
                    f"{format_value(earnings['revenue_estimate'])} "
                    f"({format_pct(earnings['revenue_surprise'])})"
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
earnings_tracker = {}

earnings_calendar = {}
last_earnings_refresh_at = None

ticker_index = 0
last_radar_sent_at = None
active_window_start = None

# Snabb kontroll utan att skriva ut några hemligheter.
print("Telegram token loaded:", bool(BOT_TOKEN))
print("Telegram chat id loaded:", bool(CHAT_ID))
print("Finnhub key loaded:", bool(FINNHUB_API_KEY))

if not BOT_TOKEN or not CHAT_ID or not FINNHUB_API_KEY:
    print("❌ En eller flera Railway-variabler saknas")
    raise SystemExit

tickers = fetch_us_symbols()

if not tickers:
    send_message("❌ Kunde inte ladda symboler")
    raise SystemExit

send_message(f"✅ Catalyst Radar V3 Startad\nUniverse: {len(tickers)}")


# =========================
# MAIN LOOP
# =========================
while True:
    try:
        now = datetime.now(sweden)
        window_start, window_end = get_news_window(now)

        # =========================
        # RESET VID NYTT NEWS-FÖNSTER
        # =========================
        if active_window_start != window_start:
            active_window_start = window_start
            seen_ids.clear()
            news_counter.clear()
            catalyst_counter.clear()
            headline_tracker.clear()
            earnings_tracker.clear()
            earnings_calendar.clear()

            last_radar_sent_at = None
            last_earnings_refresh_at = None

            send_message(
                f"🔄 Nytt news-fönster startat\n"
                f"Start: {window_start.strftime('%Y-%m-%d %H:%M')}\n"
                f"Slut: {window_end.strftime('%Y-%m-%d %H:%M')}"
            )

        # =========================
        # UPPDATERA EARNINGS VAR 15:E MINUT
        # =========================
        if (
            last_earnings_refresh_at is None
            or (now - last_earnings_refresh_at).total_seconds() >= EARNINGS_REFRESH_SECONDS
        ):
            fresh_earnings = fetch_earnings_calendar(now)

            if fresh_earnings is not None:
                earnings_calendar = fresh_earnings

                # Om vi redan har hittat news för ett bolag kan den nya
                # earnings-datan förbättra dess impact direkt.
                for sym in list(news_counter.keys()):
                    analysis = analyze_earnings(earnings_calendar.get(sym))

                    if analysis:
                        earnings_tracker[sym] = analysis

                        old_score = catalyst_counter.get(sym, 0)
                        if analysis["impact"] > old_score:
                            catalyst_counter[sym] = analysis["impact"]

                            if sym not in headline_tracker:
                                headline_tracker[sym] = "Earnings report"

            last_earnings_refresh_at = now

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

                # 1) Vanlig keyword-score från nyheten
                news_score = catalyst_score(text)

                # 2) Faktisk EPS/revenue-data om bolaget rapporterat
                earnings_analysis = analyze_earnings(
                    earnings_calendar.get(symbol)
                )

                earnings_score = 0

                if earnings_analysis:
                    earnings_tracker[symbol] = earnings_analysis
                    earnings_score = earnings_analysis["impact"]

                # Starkaste av nyheten och den faktiska rapportdatan vinner.
                score = max(news_score, earnings_score)

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
            message = build_radar_message(
                now,
                news_counter,
                catalyst_counter,
                headline_tracker,
                earnings_tracker
            )

            send_message(message)
            last_radar_sent_at = now

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("❌ Bot error:", repr(e))
        send_message(f"❌ Bot error: {str(e)[:150]}")
        time.sleep(30)
