# bot.py
import asyncio
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TOKEN
from api_football import parse_events

# --- Token check ---
if TOKEN is None:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

# --- Dictionary to store manually tracked matches ---
# chat_id -> set(match_id)
user_tracked_matches: dict[int, set[str]] = {}

# --- Message sending ---
async def send_message(chat_id: int, text: str):
    try:
        app_bot = Application.builder().token(TOKEN).build().bot
        await app_bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        print(f"Sent: {text.splitlines()[0][:70]}...")
    except Exception as e:
        print(f"Error sending message: {e}")

# --- Telegram commands ---
async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or not update.message:
        return
    chat_id = chat.id
    if not context.args:
        await update.message.reply_text("Usage: /track <match_id>")
        return
    match_id = context.args[0]
    user_tracked_matches.setdefault(chat_id, set()).add(match_id)
    await update.message.reply_text(f"Now tracking match {match_id}")

async def untrack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or not update.message:
        return
    chat_id = chat.id
    if not context.args:
        await update.message.reply_text("Usage: /untrack <match_id>")
        return
    match_id = context.args[0]
    user_tracked_matches.get(chat_id, set()).discard(match_id)
    await update.message.reply_text(f"Stopped tracking match {match_id}")

async def mygames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or not update.message:
        return
    chat_id = chat.id
    matches = user_tracked_matches.get(chat_id, set())
    text = "You have no tracked matches" if not matches else "Tracked matches:\n" + "\n".join(matches)
    await update.message.reply_text(text)

# --- Notify manually tracked matches ---
async def notify_tracked_matches(fixture: dict):
    fid = str(fixture["fixture"]["id"])
    messages = parse_events(fixture)
    if not messages:
        return
    for chat_id, matches in user_tracked_matches.items():
        if fid in matches:
            for message in messages:
                await send_message(chat_id, message)

# --- Start Telegram bot ---
def start_telegram_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("track", track))
    app.add_handler(CommandHandler("untrack", untrack))
    app.add_handler(CommandHandler("mygames", mygames))
    app.run_polling()

# --- Call notify_tracked_matches(fixture) in main_loop for each fixture ---

if __name__ == "__main__":
    t = threading.Thread(target=start_telegram_bot, daemon=True)
    t.start()
    print("Telegram bot started and listening to commands /track /untrack /mygames")
