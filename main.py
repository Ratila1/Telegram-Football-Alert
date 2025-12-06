# main.py

import asyncio
import json
import os
from typing import Set, List 

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from api_football import get_live_fixtures, is_top5_league, parse_events
from config import TOKEN, CHECK_INTERVAL 

# ====================== TRACKED MATCHES STORAGE ======================
TRACKED_FILE = "tracked.json"
# ... (load_tracked, save_tracked functions) ...
def load_tracked() -> Set[int]:
    """Loads manually tracked fixture IDs from file."""
    if not os.path.exists(TRACKED_FILE):
        return set()
    
    try:
        with open(TRACKED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "manual" in data:
                return set(int(item) for item in data.get("manual", []) if str(item).isdigit())
            else:
                print(f"[LOAD ERROR] Invalid file structure in {TRACKED_FILE}. Resetting tracking.")
                return set()
    except Exception as e:
        print(f"[LOAD ERROR] Could not load tracked data from {TRACKED_FILE}: {e}. Resetting tracking.")
        return set()

def save_tracked(tracked: Set[int]):
    """Saves manually tracked fixture IDs to file using atomic replacement."""
    temp_file = TRACKED_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump({"manual": list(tracked)}, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, TRACKED_FILE)
        print(f"[STORAGE] Tracked matches saved successfully.")
    except Exception as e:
        print(f"[SAVE ERROR] Could not save tracked data: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

manual_tracked: Set[int] = load_tracked()

# ====================== SUBSCRIBED CHATS STORAGE ======================
SUBSCRIBED_FILE = "subscribers.json"
# ... (load_subscribers, save_subscribers functions) ...
def load_subscribers() -> Set[int]:
    """Loads CHAT IDs subscribed to receive alerts."""
    if not os.path.exists(SUBSCRIBED_FILE):
        return set()
    
    try:
        with open(SUBSCRIBED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return set(int(item) for item in data if str(item).lstrip('-').isdigit())
            else:
                print(f"[LOAD ERROR] Invalid file structure in {SUBSCRIBED_FILE}. Resetting subscribers.")
                return set()
    except Exception as e:
        print(f"[LOAD ERROR] Could not load subscriber data: {e}. Resetting subscriptions.")
        return set()

def save_subscribers(subscribed: Set[int]):
    """Saves subscribed CHAT IDs to file."""
    temp_file = SUBSCRIBED_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(list(subscribed), f, ensure_ascii=False, indent=2)
        os.replace(temp_file, SUBSCRIBED_FILE)
        print(f"[STORAGE] Subscribed chats saved successfully. Total: {len(subscribed)}")
    except Exception as e:
        print(f"[SAVE ERROR] Could not save subscribed data: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

subscribed_chats: Set[int] = load_subscribers()
# ====================== КОНЕЦ БЛОКА ======================

# ====================== UNTRACKED EXCEPTIONS STORAGE (НОВЫЙ БЛОК) ======================
EXCEPTIONS_FILE = "untracked_exceptions.json"

def load_untracked_exceptions() -> Set[int]:
    """Loads fixture IDs that should be ignored, even if they are Top-5."""
    if not os.path.exists(EXCEPTIONS_FILE):
        return set()
    try:
        with open(EXCEPTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Убеждаемся, что каждый элемент - целое число
            return set(int(item) for item in data if str(item).lstrip('-').isdigit())
    except Exception as e:
        print(f"[EXCEPTIONS ERROR] Failed to load untracked exceptions: {e}. Resetting.")
        return set()

def save_untracked_exceptions(exceptions: Set[int]):
    """Saves fixture IDs that should be ignored."""
    temp_file = EXCEPTIONS_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(list(exceptions), f, ensure_ascii=False, indent=2)
        os.replace(temp_file, EXCEPTIONS_FILE)
        print(f"[STORAGE] Untracked exceptions saved successfully.")
    except Exception as e:
        print(f"[EXCEPTIONS ERROR] Failed to save untracked exceptions: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

untracked_exceptions: Set[int] = load_untracked_exceptions()
# ====================== КОНЕЦ НОВОГО БЛОКА ======================


async def allgames(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows ALL matches currently being tracked by the bot (Top-5 + Manual)."""
    message = update.effective_message
    if not message:
        return
    
    await message.reply_text("Fetching list of all currently tracked live matches, please wait...")

    try:
        fixtures = get_live_fixtures() 
        
        if not fixtures:
            await message.reply_text("No live matches found at the moment.")
            return

        tracked_list = []
        
        for fixture in fixtures:
            fid = fixture["fixture"]["id"]
            
            is_top5 = is_top5_league(fixture)
            is_manual = fid in manual_tracked
            is_excluded = fid in untracked_exceptions # НОВАЯ ПРОВЕРКА
            
            # Показываем только те, которые активны или отслеживаются вручную (и не исключены)
            is_currently_tracked = (is_top5 or is_manual) and not is_excluded
            
            if is_top5 or is_manual: # Показываем все, что потенциально отслеживается
                league = fixture["league"]["name"]
                home = fixture["teams"]["home"]["name"]
                away = fixture["teams"]["away"]["name"]
                gh = fixture["goals"]["home"] or 0
                ga = fixture["goals"]["away"] or 0
                
                track_type = []
                if is_top5:
                    track_type.append("Auto (Top)")
                if is_manual:
                    track_type.append("Manual")
                
                status_info = f" [Tracked by: {', '.join(track_type)}]"
                if is_excluded:
                    status_info += " ⚠️ **PAUSED**" # Добавляем статус паузы
                
                tracked_list.append(
                    f"• <code>#{fid}</code> | {home} {gh}-{ga} {away} "
                    f"({league}){status_info}"
                )

        if not tracked_list:
            await message.reply_text("No tracked matches are currently live.")
            return

        text = "<b>ALL Currently Tracked Live Matches:</b>\n\n"
        text += "\n".join(tracked_list)
        text += "\n\n/track &lt;id&gt; — to add a match\n/untrack &lt;id&gt; — to stop"
        
        await message.reply_html(text)

    except Exception as e:
        print(f"[ALLGAMES ERROR] {e}")
        await message.reply_text("An error occurred while fetching live matches. Check bot logs.")

# ... (start function без изменений)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_chat:
        return
    
    chat_id_to_add = update.effective_chat.id
    
    # 1. Добавляем CHAT ID в список подписок
    if chat_id_to_add not in subscribed_chats:
        subscribed_chats.add(chat_id_to_add)
        save_subscribers(subscribed_chats)
        print(f"[SUBSCRIBE] New subscription: {chat_id_to_add}")
        
        message_text = "✅ *Subscription confirmed!* You will receive notifications in this chat.\n\n"
    else:
        message_text = "✅ *You are already subscribed.* Notifications arrive in this chat.\n\n"
        
    
    # 2. Отправляем приветственное сообщение
    await update.effective_message.reply_text(
        f"<b>Live Football Tracker</b>\n\n"
        f"{message_text}"
        "• Top-5 leagues are tracked automatically\n"
        "• Use /track &lt;fixture_id&gt; to follow any other match\n\n"
        "Commands:\n"
        "/track 123456789\n"
        "/untrack 123456789\n"
        "/mygames — your tracked matches",
        parse_mode="HTML"
    )

# ====================== ОБНОВЛЕННЫЕ КОМАНДЫ ======================

async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not context.args:
        if message:
            await message.reply_text("Usage: /track &lt;fixture_id&gt;", parse_mode="HTML")
        return
    try:
        fid = int(context.args[0])
        
        # 1. Добавляем в ручное отслеживание
        manual_tracked.add(fid)
        save_tracked(manual_tracked)
        
        # 2. УДАЛЯЕМ из списка исключений (если пользователь его ранее исключил)
        if fid in untracked_exceptions:
            untracked_exceptions.remove(fid)
            save_untracked_exceptions(untracked_exceptions)
            
        await message.reply_text(f"Now tracking match <code>#{fid}</code> (Notifications unpaused)", parse_mode="HTML")
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
        
        status_message = []
        
        # 1. Пытаемся удалить из ручного отслеживания (если был там)
        if fid in manual_tracked:
            manual_tracked.remove(fid)
            save_tracked(manual_tracked)
            status_message.append(f"Stopped manual tracking for <code>#{fid}</code>.")
        
        # 2. Добавляем в список исключений, чтобы остановить уведомления для Top-5 матчей
        if fid not in untracked_exceptions:
            untracked_exceptions.add(fid)
            save_untracked_exceptions(untracked_exceptions)
            status_message.append(f"Notifications for <code>#{fid}</code> have been **paused** (Exception added).")
        else:
            status_message.append(f"Notifications for <code>#{fid}</code> were already paused.")
             
        
        if not status_message:
             await message.reply_text(f"Match <code>#{fid}</code> was neither manually tracked nor in exceptions.", parse_mode="HTML")
             return
             
        await message.reply_html("\n".join(status_message))
        
    except ValueError:
        await message.reply_text("Invalid ID")

# ... (mygames function без изменений)

async def mygames(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    if not manual_tracked and not untracked_exceptions:
        await message.reply_text("You have no manually tracked matches or paused matches.\n\nTop-5 leagues are always active.")
        return

    text = "<b>Your tracking status:</b>\n\n"
    
    # 1. Вручную отслеживаемые матчи
    if manual_tracked:
        text += "<u>Manually Tracked Matches (Active):</u>\n"
        for fid in sorted(manual_tracked):
            text += f"• <code>#{fid}</code>\n"
        text += "\n"
        
    # 2. Исключенные/приостановленные матчи
    if untracked_exceptions:
        text += "<u>Paused Notifications (Exceptions):</u>\n"
        for fid in sorted(untracked_exceptions):
            text += f"• <code>#{fid}</code> (To resume, use /track {fid})\n"
        text += "\n"
        
    text += "\n/untrack &lt;id&gt; — to stop/pause"
    await message.reply_html(text)


async def send_alert(text: str, app: Application):
    if not subscribed_chats:
        print("[ALERT] No active subscriptions. Skipping alert.")
        return
        
    alert_text = text.strip()
    
    chats_to_remove = set() 
    
    for chat_id in subscribed_chats:
        try:
            await app.bot.send_message(
                chat_id=chat_id,
                text=alert_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            print(f"[ALERT] Successfully sent message to chat {chat_id}")
            
        except Exception as e:
            error_str = str(e)
            if "Forbidden" in error_str or "chat not found" in error_str: 
                print(f"[SEND ERROR] Bot blocked/kicked or chat not found in {chat_id}. Marking for unsubscribing.")
                chats_to_remove.add(chat_id)
            else:
                print(f"[SEND ERROR] Failed to send message to chat {chat_id}: {e}")
                
    if chats_to_remove:
        subscribed_chats.difference_update(chats_to_remove)
        save_subscribers(subscribed_chats)


# ====================== MAIN LOOP (ОБНОВЛЕННАЯ ЛОГИКА) ======================
async def main_loop(app: Application):
    print("\n[BOT] Starting main tracking loop...")
    print(f"[BOT] Initial state: {len(manual_tracked)} manually tracked matches.")
    print(f"[BOT] Initial exceptions: {len(untracked_exceptions)}.") # Добавлено логирование исключений
    print(f"[BOT] Check interval set to {CHECK_INTERVAL} seconds.") 
    print(f"[BOT] Active subscriptions: {len(subscribed_chats)} chats.")
    
    cycle_count = 0
    
    while True:
        cycle_count += 1
        print(f"\n--- Tracking Cycle #{cycle_count} ({len(manual_tracked)} manual, {len(subscribed_chats)} subs) ---")
        
        try:
            fixtures = get_live_fixtures() 
            
            if not fixtures:
                print("[LOOP] No live fixtures found. Waiting...")
                await asyncio.sleep(CHECK_INTERVAL) 
                continue

            matches_to_analyze = 0

            for fixture in fixtures:
                fid = fixture["fixture"]["id"]
                is_top5 = is_top5_league(fixture)
                is_manual = fid in manual_tracked
                is_excluded = fid in untracked_exceptions # НОВАЯ ПРОВЕРКА
                
                # Матч отслеживается, только если он Top-5 ИЛИ ручной, И НЕ находится в исключениях
                is_tracked_match = (is_top5 or is_manual) and not is_excluded
                
                home = fixture["teams"]["home"]["name"]
                away = fixture["teams"]["away"]["name"]
                
                if not is_tracked_match:
                    reason = []
                    if is_excluded:
                        reason.append("Excluded")
                    if not is_top5 and not is_manual:
                        reason.append("Not Tracked")
                        
                    print(f"[SKIP] Fixture #{fid} ({home} vs {away}) - Reason: {', '.join(reason)}")
                    continue
                
                matches_to_analyze += 1
                
                if is_top5 and is_manual:
                    track_type = "Top-5 & Manual"
                elif is_top5:
                    track_type = "Top-5"
                else:
                    track_type = "Manual"
                    
                print(f"[TRACK] Analyzing Fixture #{fid} ({home} vs {away}) - Reason: {track_type}")

                messages = parse_events(fixture, is_tracked_match) 
                
                if messages:
                    print(f"[TRACK] Found {len(messages)} new alert(s) for #{fid}")
                
                for msg in messages:
                    await send_alert(msg, app) 

            print(f"[LOOP] Analysis complete. {matches_to_analyze} matches processed.")
            
        except Exception as e:
            print(f"[LOOP ERROR] An unexpected error occurred in the main loop: {e}")
            
        await asyncio.sleep(CHECK_INTERVAL)

# ====================== BOT STARTUP ======================
async def main():
    if not TOKEN or TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("ERROR: Please set your Telegram TOKEN in config.py")
        return
        
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("track", track))
    app.add_handler(CommandHandler("untrack", untrack))
    app.add_handler(CommandHandler("mygames", mygames))
    app.add_handler(CommandHandler("allgames", allgames))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    print("Polling started — bot is alive!")
    await main_loop(app)

if __name__ == "__main__":
    try:
        import keep_alive
        keep_alive.keep_alive()
    except ImportError:
        pass

    asyncio.run(main())