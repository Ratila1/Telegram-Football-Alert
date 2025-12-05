import asyncio
from api_football import get_live_fixtures, is_top5_league, parse_events
from bot import send_message
from keep_alive import keep_alive

keep_alive()  # ← чтобы Replit не спал

async def main_loop():
    print("Бот запущен — слежу за топ-5 лигами")
    while True:
        try:
            for fixture in get_live_fixtures():
                if not is_top5_league(fixture):
                    continue
                for message in parse_events(fixture):
                    await send_message(message)
        except Exception as e:
            print(f"Ошибка: {e}")
        await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main_loop())