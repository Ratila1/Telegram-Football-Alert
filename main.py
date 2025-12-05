import asyncio
import json
import os
from typing import Set

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from api_football import get_live_fixtures, is_top5_league, parse_events
from config import TOKEN, CHAT_ID

# ====================== TRACKED MATCHES STORAGE ======================
TRACKED_FILE = "tracked.json"

def load_tracked() -> Set[int]:
    if os.path.exists(TRACKED_FILE):
        try:
            with open(TRACKED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("manual", []))
        except Exception:
            return set()
    return set()

def save_tracked(tracked: Set[int]):
    with open(TRACKED_FILE, "w", encoding="utf-8") as f:
        json.dump({"manual": list(tracked)}, f, ensure_ascii=False, indent=2)

manual_tracked: Set[int] = load_tracked()

# ====================== TELEGRAM COMMANDS (100% без Pylance warning) ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    await update.effective_message.reply_text(
        "<b>Live Football Tracker</b>\n\n"
        "• Top-5 leagues are tracked automatically\n"
        "• Use /track &lt;fixture_id&gt; to follow any other match\n\n"
        "Commands:\n"
        "/track 123456789\n"
        "/untrack 123456789\n"
        "/mygames — your tracked matches",
        parse_mode="HTML"
    )

async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not context.args:
        if message:
            await message.reply_text("Usage: /track &lt;fixture_id&gt;", parse_mode="HTML")
        return
    try:
        fid = int(context.args[0])
        manual_tracked.add(fid)
        save_tracked(manual_tracked)
        await message.reply_text(f"Now tracking match <code>#{fid}</code>", parse_mode="HTML")
    except ValueError:
        await message.reply_text("Fixture ID must be a number!")

async def untrack(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not context.args:
        if message:
            await message.reply_text("Usage: /untrack &lt;fixture_id&gt;", parse_mode="HTML")
        return
    try:
        fid = int(context.args[0])
        if fid in manual_tracked:
            manual_tracked.remove(fid)
            save_tracked(manual_tracked)
            await message.reply_text(f"Stopped tracking <code>#{fid}</code>", parse_mode="HTML")
        else:
            await message.reply_text(f"Match <code>#{fid}</code> was not tracked", parse_mode="HTML")
    except ValueError:
        await message.reply_text("Invalid ID")

async def mygames(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    if not manual_tracked:
        await message.reply_text("You have no manually tracked matches.\n\nTop-5 leagues are always active.")
        return

    text = "<b>Your tracked matches:</b>\n\n"
    for fid in sorted(manual_tracked):
        text += f"• <code>#{fid}</code>\n"
    text += "\n/untrack &lt;id&gt; — to stop"
    await message.reply_html(text)

# ====================== ALERT SENDER ======================
async def send_alert(text: str, app: Application):
    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text=text.strip(),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"[SEND ERROR] {e}")

# ====================== MAIN LOOP ======================
async def main_loop(app: Application):
    print("Bot started — Top-5 + manual tracking active")
    while True:
        try:
            fixtures = get_live_fixtures()
            if not fixtures:
                await asyncio.sleep(20)
                continue

            for fixture in fixtures:
                fid = fixture["fixture"]["id"]
                if not (is_top5_league(fixture) or fid in manual_tracked):
                    continue

                messages = parse_events(fixture)
                for msg in messages:
                    await send_alert(msg, app)

        except Exception as e:
            print(f"[LOOP ERROR] {e}")
        await asyncio.sleep(20)

# ====================== BOT STARTUP ======================
async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track))
    app.add_handler(CommandHandler("untrack", untrack))
    app.add_handler(CommandHandler("mygames", mygames))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    print("Polling started — bot is alive!")
    await main_loop(app)  # Бесконечный цикл

if __name__ == "__main__":
    try:
        import keep_alive
        keep_alive.keep_alive()
    except ImportError:
        pass

    asyncio.run(main())