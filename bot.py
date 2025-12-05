from telegram import Bot
from telegram.error import TelegramError
from config import TOKEN, CHAT_ID

bot = Bot(token=TOKEN)
chat_id = CHAT_ID  # может быть str или int — библиотека сама разберётся

async def send_message(text: str):
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        print(f"Отправлено: {text.splitlines()[0][:70]}...")
    except TelegramError as e:
        print(f"Telegram ошибка: {e}")
    except Exception as e:
        print(f"Неизвестная ошибка отправки: {e}")