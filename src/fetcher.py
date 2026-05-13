import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import feedparser
import httpx

logger = logging.getLogger(__name__)


@dataclass
class Article:
    url: str
    title: str
    source: str
    category: str
    published_at: str
    content: str = ""


async def fetch_feed_raw(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def parse_feed(
    raw: str, source_name: str, category: str, max_age_hours: int, max_items: int
) -> list[Article]:
    feed = feedparser.parse(raw)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    articles = []

    for entry in feed.entries[:max_items * 2]:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

        if published and published < cutoff:
            continue

        link = entry.get("link", "")
        title = entry.get("title", "").strip()
        if not link or not title:
            continue

        content = ""
        if hasattr(entry, "summary"):
            content = entry.summary
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", content)
        content = _strip_html(content)

        articles.append(
            Article(
                url=link,
                title=title,
                source=source_name,
                category=category,
                published_at=published.isoformat() if published else "",
                content=content,
            )
        )

        if len(articles) >= max_items:
            break

    return articles


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


async def fetch_all_feeds(
    feeds: list[dict],
    max_age_hours: int = 24,
    timeout: int = 30,
    max_per_feed: int = 10,
) -> list[Article]:
    all_articles = []

    async with httpx.AsyncClient(
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AutoNewsFeed/1.0; +https://github.com)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    ) as client:
        tasks = [fetch_feed_raw(client, f["url"]) for f in feeds]
        results = await asyncio.gather(*tasks)

    for feed_cfg, raw in zip(feeds, results):
        if raw is None:
            continue
        articles = parse_feed(
            raw,
            source_name=feed_cfg["name"],
            category=feed_cfg.get("category", ""),
            max_age_hours=max_age_hours,
            max_items=max_per_feed,
        )
        logger.info("Fetched %d articles from %s", len(articles), feed_cfg["name"])
        all_articles.extend(articles)

    return all_articles
