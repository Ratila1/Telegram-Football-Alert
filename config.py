import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("API_FOOTBALL_KEY")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "20"))

if not TOKEN or not CHAT_ID or not API_KEY:
    raise ValueError("Проверь .env — не хватает токена или ключа!")

LEAGUE_IDS = [39, 140, 135, 78, 61]  # EPL, LaLiga, SerieA, Bundesliga, Ligue1