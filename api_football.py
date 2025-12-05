# api_football.py — Final Premium English Version
import requests
import hashlib
from typing import List, Dict, Any

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
    """Fetch all LIVE fixtures with detailed logging."""
    url = "https://v3.football.api-sports.io/fixtures"

    print("\n\n========== API REQUEST LOG ==========")
    print("URL:", url)
    print("Params:", {"live": "all"})
    print("Headers:")
    for k, v in HEADERS.items():
        masked = v[:5] + "..." + v[-5:] if isinstance(v, str) else str(v)
        print(f"  {k}: {masked}")

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            params={"live": "all"},
            timeout=15
        )

        print("\n--- RAW RESPONSE ---")
        print("Status Code:", r.status_code)

        try:
            print("Response JSON:", r.json())
        except Exception:
            print("Response Text:", r.text)

        if r.status_code == 403:
            print("\n--- 403 Forbidden ---")
            print("Possible reasons:")
            print("1) Invalid API key")
            print("2) Daily limit reached")
            print("3) Rate limit exceeded")

        if r.status_code == 451:
            print("\n--- 451 Blocked ---")
            print("Live fixtures may require a PRO plan.")

        r.raise_for_status()
        return r.json().get("response", [])

    except requests.exceptions.HTTPError as http_err:
        print("\nHTTP ERROR:", http_err)
        return []

    except Exception as e:
        print("\nUnexpected ERROR:", e)
        return []


def is_top5_league(fixture: dict) -> bool:
    """Check if match belongs to tracked leagues."""
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

    # ===== EVENTS =====
    for ev in fixture.get("events", []):
        key = hashlib.md5(
            f"{fid}_{ev['time']['elapsed']}_{ev['type']}_{ev['detail']}_{ev['team']['id']}".encode()
        ).hexdigest()

        if key in sent_events:
            continue
        sent_events.add(key)

        minute = ev["time"]["elapsed"]
        extra = ev["time"].get("extra")
        time_str = f"{minute}{'+' + str(extra) if extra else ''}'"

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

        else:
            continue

        messages.append(f"{header}\n\n{msg}\n──────────────────")

    # ===== STATISTICS =====
    stats = fixture.get("statistics")
    if stats and len(stats) == 2:

        def get_value(stat_list: list, name: str) -> int:
            for s in stat_list:
                if s["type"] == name:
                    return int(s["value"] or 0)
            return 0

        ch = get_value(stats[0]["statistics"], "Corner Kicks")
        ca = get_value(stats[1]["statistics"], "Corner Kicks")

        oh = get_value(stats[0]["statistics"], "Offsides")
        oa = get_value(stats[1]["statistics"], "Offsides")

        if last_corners.get(fid) != (ch, ca):
            last_corners[fid] = (ch, ca)
            messages.append(f"{header}\n\n📐 Corner Kicks: {ch}–{ca}\n──────────────────")

        if last_offsides.get(fid) != (oh, oa):
            last_offsides[fid] = (oh, oa)
            messages.append(f"{header}\n\n🚩 Offsides: {oh}–{oa}\n──────────────────")

    return messages
