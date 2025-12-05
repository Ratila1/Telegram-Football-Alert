import asyncio
from api_football import get_live_fixtures, is_top5_league, parse_events
from bot import send_message
from keep_alive import keep_alive

keep_alive()

async def main_loop():
    print("Bot started — tracking live matches in Top-5 leagues")

    while True:
        try:
            fixtures = get_live_fixtures()

            print(f"\nReceived fixtures: {len(fixtures)}")

            for f in fixtures:
                league = f["league"]["name"]
                status = f["fixture"]["status"]["short"]
                print(f"- {league} | status: {status}")

            if not fixtures:
                print("⚠️ No live matches found (or blocked by free plan)")
                await asyncio.sleep(20)
                continue

            for fixture in fixtures:
                if not is_top5_league(fixture):
                    print(f"Skipping league: {fixture['league']['name']}")
                    continue

                home = fixture["teams"]["home"]["name"]
                away = fixture["teams"]["away"]["name"]
                print(f"Processing match: {home} vs {away}")

                messages = parse_events(fixture)

                if not messages:
                    print("No new events")
                    continue

                for message in messages:
                    await send_message(message)

        except Exception as e:
            print(f"[MAIN LOOP ERROR] {e}")

        await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main_loop())
