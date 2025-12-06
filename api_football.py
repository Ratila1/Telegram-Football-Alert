# api_football.py

import requests
import hashlib
import json
import os
from typing import List, Dict, Any, Set, Iterable

# Предполагаем, что config.py доступен в том же каталоге
from config import API_KEY, LEAGUE_IDS

HEADERS = {
    "x-apisports-key": API_KEY
}

# ====================== КЭШИРОВАНИЕ СОБЫТИЙ (PERSISTENT) ======================
EVENTS_CACHE_FILE = "events_cache.json"

def load_sent_events() -> Set[str]:
    """Загружает хеши отправленных событий из файла."""
    if not os.path.exists(EVENTS_CACHE_FILE):
        return set()
    try:
        with open(EVENTS_CACHE_FILE, "r") as f:
            data = json.load(f)
            return set(data) if isinstance(data, list) else set()
    except Exception as e:
        print(f"[CACHE ERROR] Failed to load sent events: {e}")
        return set()

def save_sent_events(events: Set[str]):
    """Сохраняет хеши отправленных событий в файл."""
    temp_file = EVENTS_CACHE_FILE + ".tmp"
    try:
        with open(temp_file, "w") as f:
            json.dump(list(events), f)
        os.replace(temp_file, EVENTS_CACHE_FILE)
    except Exception as e:
        print(f"[CACHE ERROR] Failed to save sent events: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

# Global caches to prevent duplicates
sent_events: Set[str] = load_sent_events() # ЗАГРУЗКА ПРИ СТАРТЕ
last_corners: Dict[int, tuple[int, int]] = {}
last_offsides: Dict[int, tuple[int, int]] = {}
last_scores: Dict[int, tuple[int, int]] = {}
# ==============================================================================

# ====================== API-ЗАПРОС ДЛЯ СТАТИСТИКИ ======================
def get_fixture_statistics(fid: int) -> list[dict] | None:
    """Отдельным запросом получает подробную статистику матча."""
    url = "https://v3.football.api-sports.io/fixtures/statistics"
    params = {"fixture": fid}
    print(f"[API] Fetching STATS for #{fid}")
    
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        response_data = data.get("response")
        
        if not response_data:
            print(f"[API STATS] No statistics data found for #{fid}.")
            return None
            
        return response_data
        
    except Exception as e:
        print(f"[API STATS ERROR] #{fid}: {e}")
        return None
# ==============================================================================


# ИЗМЕНЕНИЕ: Убран аргумент manual_tracked_ids и убрана фильтрация по league
def get_live_fixtures() -> list[dict]:
    """Fetch all LIVE fixtures without filtering by league ID (тянем все live-матчи)."""
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"live": "all"} # Запрос всех live-матчей

    print(f"\n[API] Fetching ALL LIVE fixtures.")

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=15
        )

        r.raise_for_status()

        data = r.json()
        fixtures = data.get("response", [])
        
        print(f"[API] Received {len(fixtures)} live fixtures (UNFILTERED).")
        
        return fixtures

    except requests.exceptions.HTTPError as http_err:
        print(f"[API ERROR] HTTP Error occurred: {http_err}")
        return []
    except Exception as e:
        print(f"[API ERROR] Unexpected error during request: {e}")
        return []


def is_top5_league(fixture: dict) -> bool:
    """Check if match belongs to tracked leagues defined in LEAGUE_IDS."""
    return fixture["league"]["id"] in LEAGUE_IDS


def parse_events(fixture: dict, is_tracked_match: bool) -> list[str]:
    """
    Parse match events and statistics, return formatted messages.
    Аргумент is_tracked_match сохранен, так как он нужен для условного запроса статистики.
    """
    messages: list[str] = []
    fid = fixture["fixture"]["id"]

    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]

    gh = fixture["goals"]["home"] or 0
    ga = fixture["goals"]["away"] or 0
    
    # 1. Получаем старый счет из кэша для проверки разницы
    old_gh, old_ga = last_scores.get(fid, (0, 0)) 
    
    score = f"{gh} : {ga}"
    league = fixture["league"]["name"]
    league_id = fixture["league"]["id"]

    flag = {
        39: "🏴", 140: "🇪🇸", 135: "🇮🇹",
        78: "🇩🇪", 61: "🇫🇷"
    }.get(league_id, "")

    round_info = fixture["league"].get("round", "").replace("Regular Season - ", "Matchday ")

    header = f"<b>{flag} {league}</b>\n{round_info}\n\n<b>{home} {score} {away}</b>"

    # Обновляем кэш счета 
    last_scores[fid] = (gh, ga)
    
    print(f"[PARSE] Analyzing Fixture #{fid}: {home} {gh}-{ga} {away} ({league}). Tracked: {is_tracked_match}")

    # ====================== SCORE DISCREPANCY CHECK (Проверка счета) ======================
    is_goal_in_events_list = any(ev["type"] == "Goal" for ev in fixture.get("events", []))
    
    if (gh != old_gh or ga != old_ga) and not is_goal_in_events_list:
        scorer_team = ""
        if gh > old_gh and ga == old_ga:
            scorer_team = home
        elif ga > old_ga and gh == old_gh:
            scorer_team = away
        
        if scorer_team:
            time_elapsed = fixture["fixture"]["status"].get("elapsed", "??")
            synthetic_key = hashlib.md5(f"{fid}_{time_elapsed}_GOAL_SYNTHETIC_{gh}{ga}".encode()).hexdigest()
            
            if synthetic_key not in sent_events:
                sent_events.add(synthetic_key)
                
                msg = (
                    f"⚽️ GOAL (Score Update via API)!\n"
                    f"Team: {scorer_team} leads to {gh}-{ga}\nMinute: {time_elapsed}'"
                )
                print(f"[EVENT-FIX] Synthetic Goal event created for #{fid}: {scorer_team} ({gh}-{ga})")
                messages.append(f"{header}\n\n{msg}\n──────────────────")

    # ====================== EVENTS PROCESSING (Обработка событий) ======================
    for ev in fixture.get("events", []):
        key = hashlib.md5(
            f"{fid}_{ev['time']['elapsed']}_{ev['type']}_{ev['detail']}_{ev['team']['id']}".encode()
        ).hexdigest()

        if key in sent_events:
            continue
        sent_events.add(key)
        
        print(f"[EVENT] New event found for #{fid}: Type='{ev['type']}', Detail='{ev['detail']}', Min='{ev['time']['elapsed']}'")

        minute = ev["time"]["elapsed"]
        extra = ev["time"].get("extra")
        time_str = f"{minute}{'+' + str(extra) if extra else ''}'"

        msg = ""

        if ev["type"] == "Goal":
            player = ev.get("player", {}).get("name", "Unknown Player")
            assist = ev.get("assist", {}).get("name") or "no assist"
            own = " (Own Goal)" if "own" in ev["detail"].lower() else ""
            pen = " (Penalty)" if "penalty" in ev["detail"].lower() else ""

            msg = (
                f"⚽️ GOAL{own}{pen}!\n"
                f"Scorer: {player}\nAssist: {assist}\n{time_str}"
            )

        elif ev["type"] == "Card":
            card = "🟨 Yellow Card" if "yellow" in ev["detail"].lower() else "🟥 Red Card"
            player = ev.get("player", {}).get("name", "Unknown Player")
            msg = f"{card}\nPlayer: {player}\n{time_str}"

        elif ev["type"].lower() == "subst":
            team = home if ev["team"]["id"] == fixture["teams"]["home"]["id"] else away
            out_p = ev.get("player", {}).get("name", "Unknown Player")
            in_p = ev.get("assist", {}).get("name", "Unknown Player")
            msg = f"🔄 Substitution ({team})\n{out_p} → {in_p}\n{time_str}"

        elif ev["type"].lower() == "var":
            msg = f"🖥️ VAR Check — {ev['detail']}\n{time_str}"
            
        elif ev["type"] == "Corner":
            team = home if ev["team"]["id"] == fixture["teams"]["home"]["id"] else away
            msg = f"📐 Corner for {team}\n{time_str}"

        if msg:
            messages.append(f"{header}\n\n{msg}\n──────────────────")

    # ====================== STATISTICS (Статистика - ОПТИМИЗИРОВАНО) ======================
    stats = fixture.get("statistics")
    
    # ОПТИМИЗАЦИЯ: Запрашиваем статистику только если матчи отслеживаются И 
    # статистика отсутствует в основном ответе.
    if is_tracked_match and (not stats or len(stats) < 2): 
        stats = get_fixture_statistics(fid)
    
    if stats and len(stats) == 2:

        def get_value(stat_list: list, name: str) -> int:
            for s in stat_list:
                if s["type"] == name:
                    value = s["value"]
                    if value is None:
                        return 0
                    return int(str(value).strip().replace('%', '') or 0)
            return 0

        ch = get_value(stats[0]["statistics"], "Corner Kicks")
        ca = get_value(stats[1]["statistics"], "Corner Kicks")

        oh = get_value(stats[0]["statistics"], "Offsides")
        oa = get_value(stats[1]["statistics"], "Offsides")

        # --- УГЛОВЫЕ (С ЗАЩИТОЙ ОТ ДУБЛИРОВАНИЯ) ---
        if last_corners.get(fid) != (ch, ca):
            corner_key = hashlib.md5(f"{fid}_CORNERS_{ch}-{ca}".encode()).hexdigest()
            
            if corner_key not in sent_events:
                old_ch, old_ca = last_corners.get(fid, (0, 0)) 
                
                print(f"[STATS] Corner update for #{fid}: {old_ch}-{old_ca} -> {ch}-{ca}")
                
                last_corners[fid] = (ch, ca)
                sent_events.add(corner_key) 
                
                corner_team = ""
                if ch > old_ch and ca == old_ca: corner_team = home
                elif ca > old_ca and ch == old_ch: corner_team = away
                
                team_msg = f" ({corner_team})" if corner_team else ""
                
                messages.append(
                    f"{header}\n\n📐 Corner Kicks{team_msg}: {ch}–{ca}\n──────────────────"
                )

        # --- ОФСАЙДЫ (С ЗАЩИТОЙ ОТ ДУБЛИРОВАНИЯ) ---
        if last_offsides.get(fid) != (oh, oa):
            offside_key = hashlib.md5(f"{fid}_OFFSIDES_{oh}-{oa}".encode()).hexdigest()
            
            if offside_key not in sent_events:
                print(f"[STATS] Offside update for #{fid}: {oh}-{oa}")
                last_offsides[fid] = (oh, oa)
                sent_events.add(offside_key) 
                messages.append(f"{header}\n\n🚩 Offsides: {oh}–{oa}\n──────────────────")

    # ====================== КОНЕЦ ФУНКЦИИ (ОБЯЗАТЕЛЬНОЕ СОХРАНЕНИЕ КЭША) ======================
    save_sent_events(sent_events)
    return messages