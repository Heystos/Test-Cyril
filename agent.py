#!/usr/bin/env python3
"""
World Cup 2026 Notification Agent
Polls football-data.org and sends iPhone push notifications via ntfy.sh
after each match: final score + scorers.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

FOOTBALL_API_KEY = os.environ["FOOTBALL_API_KEY"]
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

FOOTBALL_BASE = "https://api.football-data.org/v4"
NTFY_BASE = "https://ntfy.sh"
COMPETITION_CODE = "WC"

NOTIFIED_FILE = Path("notified_matches.json")

STAGE_LABELS: dict[str, str] = {
    "GROUP_STAGE": "Phase de groupes",
    "ROUND_OF_16": "8es de finale",
    "QUARTER_FINALS": "Quarts de finale",
    "SEMI_FINALS": "Demi-finales",
    "THIRD_PLACE": "Match pour la 3e place",
    "FINAL": "FINALE",
}


def load_notified() -> set[int]:
    if NOTIFIED_FILE.exists():
        return set(json.loads(NOTIFIED_FILE.read_text()))
    return set()


def save_notified(notified: set[int]) -> None:
    NOTIFIED_FILE.write_text(json.dumps(sorted(notified)))


def football_get(path: str, params: dict | None = None) -> dict:
    resp = requests.get(
        f"{FOOTBALL_BASE}{path}",
        headers={"X-Auth-Token": FOOTBALL_API_KEY},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_finished_matches() -> list[dict]:
    """Return finished WC matches from the last 24 hours."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    data = football_get(
        f"/competitions/{COMPETITION_CODE}/matches",
        params={
            "status": "FINISHED",
            "dateFrom": yesterday.strftime("%Y-%m-%d"),
            "dateTo": now.strftime("%Y-%m-%d"),
        },
    )
    return data.get("matches", [])


def team_label(team: dict) -> str:
    return team.get("shortName") or team.get("tla") or team["name"]


def format_scorers(match: dict) -> str:
    home_id = match["homeTeam"]["id"]
    goals: list[dict] = match.get("goals", [])

    home_goals: list[str] = []
    away_goals: list[str] = []

    for g in goals:
        scorer_name = (g.get("scorer") or {}).get("name", "?")
        minute = g.get("minute", "?")
        injury = g.get("injuryTime")
        goal_type = g.get("type", "REGULAR")

        time_str = f"{minute}+{injury}'" if injury else f"{minute}'"

        suffix = " (csc)" if goal_type == "OWN_GOAL" else (" (pen)" if goal_type == "PENALTY" else "")
        entry = f"{scorer_name} {time_str}{suffix}"

        if (g.get("team") or {}).get("id") == home_id:
            home_goals.append(entry)
        else:
            away_goals.append(entry)

    home_name = team_label(match["homeTeam"])
    away_name = team_label(match["awayTeam"])

    lines: list[str] = []
    if home_goals:
        lines.append(f"{home_name}: {', '.join(home_goals)}")
    if away_goals:
        lines.append(f"{away_name}: {', '.join(away_goals)}")
    if not lines:
        lines.append("Aucun but")

    return "\n".join(lines)


def build_notification(match: dict) -> tuple[str, str]:
    home = team_label(match["homeTeam"])
    away = team_label(match["awayTeam"])

    score = match["score"]
    ft = score.get("fullTime") or {}
    hs = ft.get("home", "?")
    aws = ft.get("away", "?")

    stage = match.get("stage", "")
    group = match.get("group", "")
    stage_label = STAGE_LABELS.get(stage, stage.replace("_", " ").title())
    if group and stage == "GROUP_STAGE":
        group_letter = group.replace("GROUP_", "")
        stage_label = f"Groupe {group_letter}"

    title = f"⚽ {home} {hs}–{aws} {away} | FT"

    body_parts = [f"🏆 Coupe du Monde 2026 · {stage_label}", "", "Buteurs:", format_scorers(match)]

    # Extra time or penalty shootout
    extra = score.get("extraTime") or {}
    pens = score.get("penalties") or {}
    if extra.get("home") is not None:
        rt = score.get("regularTime") or {}
        body_parts.append(f"\n90' : {rt.get('home', '?')}–{rt.get('away', '?')}")
        body_parts.append(f"Prolongations : {extra['home']}–{extra['away']}")
    if pens.get("home") is not None:
        body_parts.append(f"Tirs au but : {home} {pens['home']}–{pens['away']} {away}")

    return title, "\n".join(body_parts)


def send_notification(title: str, body: str) -> None:
    resp = requests.post(
        f"{NTFY_BASE}/{NTFY_TOPIC}",
        data=body.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Priority": "high",
            "Tags": "soccer,trophy",
            "Content-Type": "text/plain; charset=utf-8",
        },
        timeout=10,
    )
    resp.raise_for_status()
    log.info("Notification envoyée : %s", title)


def run() -> None:
    log.info("Agent Coupe du Monde 2026 démarré — topic ntfy : %s", NTFY_TOPIC)
    notified = load_notified()

    while True:
        try:
            matches = get_finished_matches()
            log.info("%d match(s) terminé(s) trouvé(s)", len(matches))
            for match in matches:
                mid = match["id"]
                if mid not in notified:
                    title, body = build_notification(match)
                    send_notification(title, body)
                    notified.add(mid)
                    save_notified(notified)
        except requests.HTTPError as exc:
            log.error("Erreur API (%s) : %s", exc.response.status_code, exc)
        except Exception:
            log.exception("Erreur inattendue")

        log.info("Prochain check dans %ds…", POLL_INTERVAL)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
