import aiohttp
import asyncio
from config import TOKEN, CHAT_ID

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

async def send_message(text: str):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(TELEGRAM_API_URL, data=payload) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"[TELEGRAM ERROR] Status {resp.status} → {err}")
                else:
                    print(f"[SENT] {text.splitlines()[0][:60]}...")

    except Exception as e:
        print(f"[SEND ERROR] {e}")
