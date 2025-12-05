# bot.py
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TOKEN
from api_football import parse_events

# --- Token check ---
if TOKEN is None:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

# --- Global bot application (initialized in start_telegram_bot) ---
app: Application | None = None

# chat_id -> set(match_id)
user_tracked_matches: dict[int, set[str]] = {}


# -------------------------------------------------------------------
# SEND MESSAGE (Unified)
# -------------------------------------------------------------------
async def send_message(chat_id: int, text: str):
    """
    Sends a message through the globally running bot application.
    """
    if app is None:
        print("[SEND ERROR] Bot not initialized yet")
        return

    try:
        await app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        print(f"[SENT] {text[:60]}...")
    except Exception as e:
        print(f"[SEND ERROR] {e}")


# -------------------------------------------------------------------
# TELEGRAM COMMANDS
# -------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("👋 Bot is running! Use /track <id>")


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Usage: /track <match_id>")
        return

    match_id = context.args[0]
    user_tracked_matches.setdefault(chat_id, set()).add(match_id)

    await update.message.reply_text(f"Tracking match {match_id}")


async def untrack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Usage: /untrack <match_id>")
        return

    match_id = context.args[0]
    user_tracked_matches.get(chat_id, set()).discard(match_id)

    await update.message.reply_text(f"Stopped tracking match {match_id}")


async def mygames(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.effective_chat.id
    matches = user_tracked_matches.get(chat_id, set())

    if not matches:
        await update.message.reply_text("You have no tracked matches.")
    else:
        await update.message.reply_text("Tracked matches:\n" + "\n".join(matches))


# -------------------------------------------------------------------
# NOTIFY TRACKED MATCHES
# -------------------------------------------------------------------
async def notify_tracked_matches(fixture: dict):
    fid = str(fixture["fixture"]["id"])
    messages = parse_events(fixture)

    if not messages:
        return

    for chat_id, matches in user_tracked_matches.items():
        if fid in matches:
            for msg in messages:
                await send_message(chat_id, msg)


# -------------------------------------------------------------------
# START TELEGRAM BOT (CALLED FROM main.py)
# -------------------------------------------------------------------
def start_telegram_bot():
    """
    Creates and runs the bot.
    Called by main.py in a separate thread.
    """
    global app
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track))
    app.add_handler(CommandHandler("untrack", untrack))
    app.add_handler(CommandHandler("mygames", mygames))

    print("Telegram bot is now running (commands enabled).")
    app.run_polling()
