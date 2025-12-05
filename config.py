import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("API_FOOTBALL_KEY")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "20"))

if not TOKEN or not CHAT_ID or not API_KEY:
    raise ValueError("Проверь .env — не хватает токена или ключа!")

LEAGUE_IDS = [
    39,    # EPL
    140,   # LaLiga
    135,   # Serie A
    78,    # Bundesliga
    61,    # Ligue 1
    40,    # England Championship
    2,     # UEFA Champions League
    3,     # UEFA Europa League
    4,     # UEFA Conference League
    114,   # AFCON
]
