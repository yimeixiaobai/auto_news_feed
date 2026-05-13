import argparse
import asyncio
import logging

from src.config import read_feeds, read_settings
from src.db import NewsDB
from src.fetcher import fetch_all_feeds
from src.summarizer import Summarizer
from src.pusher.telegram import TelegramPusher
from src.pusher.bark import BarkPusher
from src.pusher.wecom import WecomPusher
from src.pusher.wps import WpsPusher
from src.pusher.lark import LarkPusher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def push_digest(digest: str, settings: dict):
    enabled = settings["push"].get("enabled", [])
    results = []

    if "telegram" in enabled:
        cfg = settings["push"]["telegram"]
        if cfg.get("bot_token") and cfg.get("chat_id"):
            pusher = TelegramPusher(cfg["bot_token"], cfg["chat_id"])
            ok = await pusher.send(digest)
            results.append(("Telegram", ok))

    if "bark" in enabled:
        cfg = settings["push"]["bark"]
        if cfg.get("device_key"):
            pusher = BarkPusher(cfg["server_url"], cfg["device_key"])
            ok = await pusher.send(digest)
            results.append(("Bark", ok))

    if "wecom" in enabled:
        cfg = settings["push"]["wecom"]
        if cfg.get("webhook_url"):
            pusher = WecomPusher(cfg["webhook_url"])
            ok = await pusher.send(digest)
            results.append(("Wecom", ok))

    if "wps" in enabled:
        cfg = settings["push"]["wps"]
        if cfg.get("webhook_url"):
            pusher = WpsPusher(cfg["webhook_url"])
            ok = await pusher.send(digest)
            results.append(("WPS", ok))

    if "lark" in enabled:
        cfg = settings["push"]["lark"]
        if cfg.get("webhook_url"):
            pusher = LarkPusher(cfg["webhook_url"], cfg.get("secret", ""))
            ok = await pusher.send(digest)
            results.append(("Lark", ok))

    for name, ok in results:
        status = "success" if ok else "FAILED"
        logger.info("Push %s: %s", name, status)

    return results


async def run(args):
    settings = read_settings()
    fetch_settings = settings["fetch"]
    all_feeds = read_feeds()

    db = NewsDB(settings["database"]["path"])

    active_feeds = [f for f in all_feeds if f.get("enabled", True)]
    logger.info("Fetching feeds (%d/%d enabled)...", len(active_feeds), len(all_feeds))
    articles = await fetch_all_feeds(
        feeds=active_feeds,
        max_age_hours=fetch_settings["max_age_hours"],
        timeout=fetch_settings["timeout_seconds"],
        max_per_feed=fetch_settings["max_articles_per_feed"],
    )
    logger.info("Fetched %d articles total", len(articles))

    new_articles = []
    for article in articles:
        if not db.exists(article.url):
            if not args.dry_run:
                db.insert_article(
                    url=article.url,
                    title=article.title,
                    source=article.source,
                    category=article.category,
                    published_at=article.published_at,
                )
            new_articles.append(article)

    logger.info("New articles after dedup: %d", len(new_articles))
    for i, a in enumerate(new_articles, 1):
        logger.debug("  [%d] 【%s】%s", i, a.source, a.title)

    if not new_articles:
        logger.info("No new articles. Done.")
        db.close()
        return

    article_dicts = [
        {
            "url": a.url,
            "title": a.title,
            "source": a.source,
            "category": a.category,
            "summary": a.content,
        }
        for a in new_articles
    ]

    if not args.no_summary:
        summarizer_cfg = settings["summarizer"]
        top_n = summarizer_cfg.get("top_n", 15)
        provider = summarizer_cfg.get("provider", "anthropic")
        provider_cfg = summarizer_cfg.get(provider, {})
        model = provider_cfg.get("model", summarizer_cfg.get("model", ""))
        logger.info(
            "Generating digest with %s/%s (%d articles -> top %d)...",
            provider, model, len(article_dicts), top_n,
        )
        summarizer = Summarizer(
            provider=provider,
            model=model,
            api_key=provider_cfg.get("api_key", ""),
            base_url=provider_cfg.get("base_url", ""),
        )
        digest = summarizer.generate_digest(article_dicts, top_n=top_n)
    else:
        digest = _plain_digest(article_dicts)

    if args.dry_run:
        print("\n" + "=" * 60)
        print(digest)
        print("=" * 60 + "\n")
    else:
        await push_digest(digest, settings)
        for a in new_articles:
            db.mark_pushed(a.url)
        logger.info("Pushed digest (%d articles fed, top N selected by AI)", len(new_articles))

    db.close()


def _plain_digest(articles: list[dict]) -> str:
    lines = ["📰 AI 日报\n"]
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. 【{a['source']}】{a['title']}")
        if a.get("summary"):
            lines.append(f"   {a['summary']}")
        lines.append(f"   [🔗 原文链接]({a['url']})\n")
    lines.append(f"\n共 {len(articles)} 条新闻")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="AI News Feed Aggregator")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and print digest without pushing",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip AI summarization (faster, no API cost)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed article list during fetch",
    )
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger(__name__).setLevel(logging.DEBUG)
        logging.getLogger("src").setLevel(logging.DEBUG)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
