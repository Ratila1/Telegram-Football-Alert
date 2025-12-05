# api_football.py — Final Premium English Version (No Pylance errors!)
import requests
import hashlib
from typing import List, Dict, Any

# Предполагаем, что config.py содержит:
# API_KEY (str)
# LEAGUE_IDS (list[int])
from config import API_KEY, LEAGUE_IDS

HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}

# Глобальное хранилище для предотвращения дублирования
sent_events: set[str] = set()
last_corners: dict[int, tuple[int, int]] = {}
last_offsides: dict[int, tuple[int, int]] = {}
# Хранилище для отслеживания счета в матче
last_scores: dict[int, tuple[int, int]] = {}


def get_live_fixtures() -> list[dict]:
    """Получает все LIVE матчи из API-Football."""
    try:
        r = requests.get(
            "https://api-football-v1.p.rapidapi.com/v3/fixtures",
            headers=HEADERS,
            params={"live": "all"},
            timeout=15
        )
        r.raise_for_status()
        return r.json().get("response", [])
    except Exception as e:
        print(f"API-Football error during fixtures fetch: {e}")
        return []


def is_top5_league(fixture: dict) -> bool:
    """Проверяет, относится ли матч к отслеживаемым лигам."""
    return fixture["league"]["id"] in LEAGUE_IDS


def parse_events(fixture: dict) -> list[str]:
    """
    Парсит события матча (Goals, Cards, Subs, VAR) и статистику (Corners, Offsides)
    и генерирует сообщения для отправки.
    """
    messages: list[str] = []
    fid = fixture["fixture"]["id"]
    
    # Исправлена ошибка: удален лишний "away" в пути
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"] 
    
    gh = fixture["goals"]["home"] if fixture["goals"]["home"] is not None else 0
    ga = fixture["goals"]["away"] if fixture["goals"]["away"] is not None else 0
    score = f"{gh} : {ga}"

    league = fixture["league"]["name"]
    league_id = fixture["league"]["id"]
    
    # Визуальные флаги
    flag = {
        39: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", 140: "🇪🇸", 135: "🇮🇹",
        78: "🇩🇪", 61: "🇫🇷"
    }.get(league_id, "")
    round_info = fixture["league"].get("round", "").replace("Regular Season - ", "Matchday ")

    # Шапка сообщения
    header = f"<b>{flag} {league}</b>\n{round_info}\n\n<b>{home} {score} {away}</b>"

    # === Events (Goals, Cards, Subs, VAR) ===
    
    # Проверка на новый гол (Если API не успел обновить events)
    current_score_tuple = (gh, ga)
    if last_scores.get(fid) != current_score_tuple:
        # Если счет изменился, но API-Football еще не обновил секцию 'events', 
        # мы все равно отправляем оповещение о голе, основываясь на разнице счета.
        if gh > last_scores.get(fid, (0, 0))[0] or ga > last_scores.get(fid, (0, 0))[1]:
            # Предполагаем, что это гол, если событие 'Goal' не найдено ниже
            
            # Внимание: В этой версии кода мы полагаемся на секцию 'events', 
            # где должны быть детали гола. Мы просто обновляем счет здесь, 
            # и событие 'Goal' будет обработано ниже.
            pass

    last_scores[fid] = current_score_tuple

    for ev in fixture.get("events", []):
        # Хеш для проверки дубликатов
        key = hashlib.md5(
            f"{fid}_{ev['time']['elapsed']}_{ev['type']}_{ev['detail']}_{ev['team']['id']}".encode()
        ).hexdigest()

        if key in sent_events:
            continue
        sent_events.add(key)

        minute = ev['time']['elapsed']
        extra = ev['time'].get('extra')
        time_str = f"{minute}{'+' + str(extra) if extra else ''}'"

        if ev["type"] == "Goal":
            player = ev.get("player", {}).get("name", "Unknown Player")
            assist = ev.get("assist", {}).get("name") or "no assist"
            own = " (OWN GOAL)" if "own" in ev["detail"].lower() else ""
            
            # Если это пенальти, добавляем маркер
            detail = " (PENALTY)" if "penalty" in ev["detail"].lower() else ""

            msg = f"⚽️ GOAL{own}{detail}!\nPlayer: {player} (Assist: {assist})\n{time_str}"

        elif ev["type"] == "Card":
            card = "🟨 Yellow Card" if "yellow" in ev["detail"].lower() else "🟥 Red Card"
            player = ev.get("player", {}).get("name", "Unknown Player")
            msg = f"{card} {player}\n{time_str}"

        elif ev["type"] == "subst":
            team = home if ev["team"]["id"] == fixture["teams"]["home"]["id"] else away
            out_p = ev.get("player", {}).get("name", "Out Player")
            in_p = ev.get("assist", {}).get("name", "In Player")
            
            msg = f"🔄 Substitution ({team})\n{out_p} → {in_p}\n{time_str}"

        elif ev["type"] == "Var":
            msg = f"🖥️ VAR Check: {ev['detail']}\n{time_str}"

        else:
            continue  # Неизвестное событие — пропускаем

        messages.append(f"{header}\n\n{msg}\n──────────────────")

    # === Statistics (Corners & Offsides) ===
    stats = fixture.get("statistics")
    if stats and len(stats) == 2:
        def get_value(stat_list: list, name: str) -> int:
            """Извлекает значение статистики или возвращает 0."""
            for s in stat_list:
                if s["type"] == name:
                    # ИСПРАВЛЕНА СИНТАКСИЧЕСКАЯ ОШИБКА: 
                    # Убрана лишняя квадратная скобка ']'
                    return int(s["value"] or 0)
            return 0

        # Угловые
        ch = get_value(stats[0]["statistics"], "Corner Kicks")
        ca = get_value(stats[1]["statistics"], "Corner Kicks")
        
        # Офсайды
        oh = get_value(stats[0]["statistics"], "Offsides")
        oa = get_value(stats[1]["statistics"], "Offsides")

        if last_corners.get(fid) != (ch, ca):
            last_corners[fid] = (ch, ca)
            messages.append(f"{header}\n\n📐 Corner Kicks {ch}:{ca}\n──────────────────")

        if last_offsides.get(fid) != (oh, oa):
            last_offsides[fid] = (oh, oa)
            messages.append(f"{header}\n\n🚩 Offsides {oh}:{oa}\n──────────────────")

    return messages