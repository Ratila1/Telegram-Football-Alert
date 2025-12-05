import asyncio
import threading
from api_football import get_live_fixtures, is_top5_league, parse_events
from bot import send_message, notify_tracked_matches, start_telegram_bot
from keep_alive import keep_alive
from config import CHAT_ID

keep_alive()

if CHAT_ID is None:
    raise ValueError("CHAT_ID is not set in .env")

MAIN_CHAT_ID = int(CHAT_ID)

async def main_loop():
    print("Bot started — tracking live matches in Top-5 leagues and additional leagues")

    # --- Greeting message ---
    try:
        await send_message(chat_id=MAIN_CHAT_ID, text="🤖 Bot is online! Hello!")
        print(f"Greeting message sent to chat {MAIN_CHAT_ID}")
    except Exception as e:
        print(f"[GREETING ERROR] {e}")

    while True:
        try:
            fixtures = get_live_fixtures()
            print(f"\nReceived fixtures: {len(fixtures)}")

            if not fixtures:
                print("⚠️ No live matches found (or blocked by free plan)")
                await asyncio.sleep(20)
                continue

            for fixture in fixtures:
                league = fixture["league"]["name"]
                status = fixture["fixture"]["status"]["short"]
                print(f"- {league} | status: {status}")

                if not is_top5_league(fixture):
                    print(f"Skipping league: {league}")
                    continue

                home = fixture["teams"]["home"]["name"]
                away = fixture["teams"]["away"]["name"]
                print(f"Processing match: {home} vs {away}")

                messages = parse_events(fixture)
                if messages:
                    for message in messages:
                        await send_message(chat_id=MAIN_CHAT_ID, text=message)

                # Уведомление отслеживаемых матчей пользователями
                await notify_tracked_matches(fixture)

        except Exception as e:
            print(f"[MAIN LOOP ERROR] {e}")

        await asyncio.sleep(20)


if __name__ == "__main__":
    # ---- Start telegram bot thread ----
    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()
    print("Telegram bot started and listening for /start /track /untrack /mygames")

    # ---- Start main loop ----
    asyncio.run(main_loop())
