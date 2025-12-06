# api_football.py

import requests
import hashlib
from typing import List, Dict, Any

# Assuming config.py is available
from config import API_KEY, LEAGUE_IDS

HEADERS = {
    "x-apisports-key": API_KEY
}

# Global caches to prevent duplicates
sent_events: set[str] = set()
last_corners: dict[int, tuple[int, int]] = {}
last_offsides: dict[int, tuple[int, int]] = {}
last_scores: dict[int, tuple[int, int]] = {}


def get_live_fixtures() -> list[dict]:
    """Fetch all LIVE fixtures with detailed, non-verbose logging."""
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"live": "all"}

    print(f"\n[API] Fetching LIVE fixtures (URL: {url}, Params: {params})")

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=15
        )

        print(f"[API] Status: {r.status_code}")

        if r.status_code != 200:
            print(f"[API ERROR] HTTP Status {r.status_code}. Response text (partial): {r.text[:100].strip()}...")
            if r.status_code == 403:
                print("      - Check API Key, daily quota, or rate limits.")
            if r.status_code == 451:
                print("      - Live data may require a PRO plan.")
            r.raise_for_status()

        data = r.json()
        fixtures = data.get("response", [])
        
        print(f"[API] Received {len(fixtures)} live fixtures.")
        
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


def parse_events(fixture: dict) -> list[str]:
    """Parse match events and statistics, return formatted messages."""
    messages: list[str] = []
    fid = fixture["fixture"]["id"]

    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]

    gh = fixture["goals"]["home"] or 0
    ga = fixture["goals"]["away"] or 0
    score = f"{gh} : {ga}"

    league = fixture["league"]["name"]
    league_id = fixture["league"]["id"]

    flag = {
        39: "🏴", 140: "🇪🇸", 135: "🇮🇹",
        78: "🇩🇪", 61: "🇫🇷"
    }.get(league_id, "")

    round_info = fixture["league"].get("round", "").replace("Regular Season - ", "Matchday ")

    header = f"<b>{flag} {league}</b>\n{round_info}\n\n<b>{home} {score} {away}</b>"

    # Update score cache
    last_scores[fid] = (gh, ga)
    
    print(f"[PARSE] Analyzing Fixture #{fid}: {home} {gh}-{ga} {away} ({league})")

    # ===== EVENTS =====
    for ev in fixture.get("events", []):
        key = hashlib.md5(
            f"{fid}_{ev['time']['elapsed']}_{ev['type']}_{ev['detail']}_{ev['team']['id']}".encode()
        ).hexdigest()

        if key in sent_events:
            continue
        sent_events.add(key)
        
        # Log the detected event
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

        if msg:
            messages.append(f"{header}\n\n{msg}\n──────────────────")

    # ===== STATISTICS =====
    stats = fixture.get("statistics")
    if stats and len(stats) == 2:

        def get_value(stat_list: list, name: str) -> int:
            for s in stat_list:
                if s["type"] == name:
                    # Replace None/"" with 0 and ensure integer type
                    return int(s["value"].strip().replace('%', '') or 0)
            return 0

        ch = get_value(stats[0]["statistics"], "Corner Kicks")
        ca = get_value(stats[1]["statistics"], "Corner Kicks")

        oh = get_value(stats[0]["statistics"], "Offsides")
        oa = get_value(stats[1]["statistics"], "Offsides")

        if last_corners.get(fid) != (ch, ca):
            # Log the change in statistics
            print(f"[STATS] Corner update for #{fid}: {ch}-{ca}")
            last_corners[fid] = (ch, ca)
            messages.append(f"{header}\n\n📐 Corner Kicks: {ch}–{ca}\n──────────────────")

        if last_offsides.get(fid) != (oh, oa):
            # Log the change in statistics
            print(f"[STATS] Offside update for #{fid}: {oh}-{oa}")
            last_offsides[fid] = (oh, oa)
            messages.append(f"{header}\n\n🚩 Offsides: {oh}–{oa}\n──────────────────")

    return messages