"""
Atlas AI Trader PRO - Market News
Aggregates recent headlines from Yahoo Finance via yfinance for a handful
of reference tickers (indices, gold, oil, BTC) to give a general market
news pulse without requiring a separate news API key.
"""

import logging
from datetime import datetime, timezone

import yfinance as yf

from config import NEWS_TICKERS

logger = logging.getLogger(__name__)


def get_market_news(limit: int = 8) -> list:
    """Return a deduplicated, time-sorted list of news items.

    Each item: {"title": str, "publisher": str, "link": str, "time": datetime|None}
    """
    items = []
    seen_titles = set()

    for ticker in NEWS_TICKERS:
        try:
            news = yf.Ticker(ticker).news or []
        except Exception as e:
            logger.warning("Failed to fetch news for %s: %s", ticker, e)
            continue

        for n in news:
            # yfinance news items sometimes nest fields under "content"
            content = n.get("content", n)
            title = content.get("title") or n.get("title")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            link = (
                content.get("clickThroughUrl", {}).get("url")
                if isinstance(content.get("clickThroughUrl"), dict)
                else content.get("canonicalUrl", {}).get("url")
                if isinstance(content.get("canonicalUrl"), dict)
                else n.get("link")
            )
            publisher = (
                content.get("provider", {}).get("displayName")
                if isinstance(content.get("provider"), dict)
                else n.get("publisher", "Unknown")
            )

            ts = n.get("providerPublishTime")
            pub_time = None
            if ts:
                try:
                    pub_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                except Exception:
                    pub_time = None

            items.append({
                "title": title,
                "publisher": publisher or "Unknown",
                "link": link or "",
                "time": pub_time,
            })

    items.sort(key=lambda x: x["time"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items[:limit]


def format_news_message(items: list) -> str:
    if not items:
        return "No market news available right now. Please try again shortly."

    lines = ["\U0001F4F0 *Market News*\n"]
    for item in items:
        time_str = item["time"].strftime("%b %d, %H:%M UTC") if item["time"] else "Recent"
        lines.append(f"\u2022 *{item['title']}*")
        lines.append(f"  _{item['publisher']} \u2014 {time_str}_")
        if item["link"]:
            lines.append(f"  {item['link']}")
        lines.append("")

    return "\n".join(lines)
