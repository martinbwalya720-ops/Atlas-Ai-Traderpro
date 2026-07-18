"""
Atlas AI Trader PRO - Economic Calendar
Pulls this week's economic events from a public, no-auth JSON feed
(commonly used by open-source calendar widgets) and formats the
upcoming high/medium impact events.
"""

import logging
from datetime import datetime, timezone

import requests

from config import FF_CALENDAR_URL

logger = logging.getLogger(__name__)

IMPACT_EMOJI = {
    "High": "\U0001F534",
    "Medium": "\U0001F7E1",
    "Low": "\U0001F7E2",
    "Holiday": "\u26aa",
}


def get_upcoming_events(limit: int = 10, min_impact: str = "Medium") -> list:
    """Fetch and return upcoming economic calendar events.

    Returns a list of dicts: {title, country, date, impact, forecast, previous}
    Only returns events that haven't happened yet, sorted chronologically.
    """
    try:
        resp = requests.get(FF_CALENDAR_URL, timeout=10)
        resp.raise_for_status()
        raw_events = resp.json()
    except Exception as e:
        logger.warning("Failed to fetch economic calendar: %s", e)
        return []

    impact_rank = {"Low": 0, "Medium": 1, "High": 2, "Holiday": 0}
    min_rank = impact_rank.get(min_impact, 1)

    now = datetime.now(timezone.utc)
    upcoming = []

    for ev in raw_events:
        try:
            date_str = ev.get("date")  # ISO 8601 with offset
            if not date_str:
                continue
            event_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        impact = ev.get("impact", "Low")
        if impact_rank.get(impact, 0) < min_rank:
            continue
        if event_time < now:
            continue

        upcoming.append({
            "title": ev.get("title", "Unknown Event"),
            "country": ev.get("country", ""),
            "date": event_time,
            "impact": impact,
            "forecast": ev.get("forecast", "") or "-",
            "previous": ev.get("previous", "") or "-",
        })

    upcoming.sort(key=lambda x: x["date"])
    return upcoming[:limit]


def format_calendar_message(events: list) -> str:
    if not events:
        return (
            "\U0001F4C5 *Economic Calendar*\n\n"
            "No upcoming medium/high impact events found right now "
            "(or the calendar feed is temporarily unavailable)."
        )

    lines = ["\U0001F4C5 *Economic Calendar \u2014 This Week*\n"]
    for ev in events:
        emoji = IMPACT_EMOJI.get(ev["impact"], "\u26aa")
        date_str = ev["date"].strftime("%a %b %d, %H:%M UTC")
        lines.append(f"{emoji} *{ev['title']}* ({ev['country']})")
        lines.append(f"  {date_str} | Impact: {ev['impact']}")
        lines.append(f"  Forecast: {ev['forecast']}  Previous: {ev['previous']}")
        lines.append("")

    return "\n".join(lines)
