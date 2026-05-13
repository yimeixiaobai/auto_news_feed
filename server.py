import asyncio
import logging
from pathlib import Path

import feedparser
import httpx
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.db import NewsDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
FEEDS_PATH = BASE_DIR / "config" / "feeds.yaml"
SETTINGS_PATH = BASE_DIR / "config" / "settings.yaml"

app = FastAPI(title="AI News Feed Console")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── helpers ──────────────────────────────────────────────

def read_feeds() -> list[dict]:
    with open(FEEDS_PATH) as f:
        return yaml.safe_load(f).get("feeds", [])


def write_feeds(feeds: list[dict]):
    with open(FEEDS_PATH, "w") as f:
        yaml.dump({"feeds": feeds}, f, allow_unicode=True, default_flow_style=False)


def read_settings() -> dict:
    with open(SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def write_settings(settings: dict):
    with open(SETTINGS_PATH, "w") as f:
        yaml.dump(settings, f, allow_unicode=True, default_flow_style=False)


# ── models ───────────────────────────────────────────────

class FeedItem(BaseModel):
    name: str
    url: str
    category: str = "industry"
    enabled: bool = True


class FeedTestRequest(BaseModel):
    url: str


class PushTestRequest(BaseModel):
    channel: str
    message: str = "AI News Feed test message"


class SettingsUpdate(BaseModel):
    settings: dict


class RunRequest(BaseModel):
    dry_run: bool = True
    no_summary: bool = False


# ── feed endpoints ───────────────────────────────────────

@app.get("/api/feeds")
def get_feeds():
    return {"feeds": read_feeds()}


@app.post("/api/feeds")
def add_feed(item: FeedItem):
    feeds = read_feeds()
    for f in feeds:
        if f["url"] == item.url:
            raise HTTPException(400, "Feed URL already exists")
    feeds.append(item.model_dump())
    write_feeds(feeds)
    return {"ok": True, "feeds": feeds}


@app.put("/api/feeds/{index}")
def update_feed(index: int, item: FeedItem):
    feeds = read_feeds()
    if index < 0 or index >= len(feeds):
        raise HTTPException(404, "Feed not found")
    feeds[index] = item.model_dump()
    write_feeds(feeds)
    return {"ok": True, "feeds": feeds}


@app.delete("/api/feeds/{index}")
def delete_feed(index: int):
    feeds = read_feeds()
    if index < 0 or index >= len(feeds):
        raise HTTPException(404, "Feed not found")
    removed = feeds.pop(index)
    write_feeds(feeds)
    return {"ok": True, "removed": removed, "feeds": feeds}


@app.patch("/api/feeds/{index}/toggle")
def toggle_feed(index: int):
    feeds = read_feeds()
    if index < 0 or index >= len(feeds):
        raise HTTPException(404, "Feed not found")
    feeds[index]["enabled"] = not feeds[index].get("enabled", True)
    write_feeds(feeds)
    return {"ok": True, "enabled": feeds[index]["enabled"], "feeds": feeds}


@app.post("/api/feeds/test")
async def test_feed(req: FeedTestRequest):
    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AutoNewsFeed/1.0)",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        ) as client:
            resp = await client.get(req.url, follow_redirects=True)

        if resp.status_code != 200:
            return {
                "ok": False,
                "status": resp.status_code,
                "message": f"HTTP {resp.status_code}",
                "articles": 0,
            }

        feed = feedparser.parse(resp.text)
        entries = feed.entries[:5]
        articles = [
            {"title": e.get("title", ""), "link": e.get("link", "")}
            for e in entries
        ]
        return {
            "ok": True,
            "status": 200,
            "message": f"Found {len(feed.entries)} entries",
            "articles": len(feed.entries),
            "preview": articles,
        }
    except Exception as e:
        return {"ok": False, "status": 0, "message": str(e), "articles": 0}


async def _test_one(client: httpx.AsyncClient, url: str) -> dict:
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return {"ok": False, "message": f"HTTP {resp.status_code}", "articles": 0}
        feed = feedparser.parse(resp.text)
        return {"ok": True, "message": f"{len(feed.entries)} 条", "articles": len(feed.entries)}
    except Exception as e:
        return {"ok": False, "message": str(e)[:80], "articles": 0}


@app.post("/api/feeds/test-all")
async def test_all_feeds():
    feeds = read_feeds()
    async with httpx.AsyncClient(
        timeout=15,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AutoNewsFeed/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    ) as client:
        import asyncio
        tasks = [_test_one(client, f["url"]) for f in feeds]
        results = await asyncio.gather(*tasks)
    return {"results": [{"index": i, **r} for i, r in enumerate(results)]}


# ── settings endpoints ───────────────────────────────────

@app.get("/api/settings")
def get_settings():
    return {"settings": read_settings()}


@app.put("/api/settings")
def update_settings(req: SettingsUpdate):
    write_settings(req.settings)
    return {"ok": True, "settings": req.settings}


# ── push test ─────────────────────────────────────────────

@app.post("/api/push/test")
async def test_push(req: PushTestRequest):
    settings = read_settings()
    channel = req.channel
    cfg = settings.get("push", {}).get(channel, {})

    try:
        if channel == "telegram":
            token = cfg.get("bot_token", "")
            chat_id = cfg.get("chat_id", "")
            if not token or not chat_id:
                return {"ok": False, "message": "bot_token or chat_id not configured"}
            from src.pusher.telegram import TelegramPusher
            pusher = TelegramPusher(token, chat_id)
            ok = await pusher.send(req.message)

        elif channel == "bark":
            device_key = cfg.get("device_key", "")
            if not device_key:
                return {"ok": False, "message": "device_key not configured"}
            from src.pusher.bark import BarkPusher
            pusher = BarkPusher(cfg.get("server_url", "https://api.day.app"), device_key)
            ok = await pusher.send(req.message)

        elif channel == "wecom":
            webhook_url = cfg.get("webhook_url", "")
            if not webhook_url:
                return {"ok": False, "message": "webhook_url not configured"}
            from src.pusher.wecom import WecomPusher
            pusher = WecomPusher(webhook_url)
            ok = await pusher.send(req.message)

        elif channel == "wps":
            webhook_url = cfg.get("webhook_url", "")
            if not webhook_url:
                return {"ok": False, "message": "webhook_url not configured"}
            from src.pusher.wps import WpsPusher
            pusher = WpsPusher(webhook_url)
            ok = await pusher.send(req.message)

        elif channel == "lark":
            webhook_url = cfg.get("webhook_url", "")
            if not webhook_url:
                return {"ok": False, "message": "webhook_url not configured"}
            from src.pusher.lark import LarkPusher
            pusher = LarkPusher(webhook_url, cfg.get("secret", ""))
            ok = await pusher.send(req.message)

        else:
            return {"ok": False, "message": f"Unknown channel: {channel}"}

        return {"ok": ok, "message": "Sent" if ok else "Send failed"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ── articles / stats ─────────────────────────────────────

@app.get("/api/articles")
def get_articles(limit: int = 50):
    try:
        db = NewsDB(read_settings()["database"]["path"])
        cur = db.conn.execute(
            """SELECT url, title, source, category, published_at, summary, pushed_at, created_at
               FROM articles ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        )
        articles = [dict(row) for row in cur.fetchall()]
        cur2 = db.conn.execute("SELECT COUNT(*) as total FROM articles")
        total = cur2.fetchone()["total"]
        db.close()
        return {"articles": articles, "total": total}
    except Exception:
        return {"articles": [], "total": 0}


@app.get("/api/stats")
def get_stats():
    try:
        db = NewsDB(read_settings()["database"]["path"])
        cur = db.conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN pushed_at IS NOT NULL THEN 1 END) as pushed,
                COUNT(CASE WHEN summary != '' THEN 1 END) as summarized,
                COUNT(DISTINCT source) as sources
            FROM articles
        """)
        row = dict(cur.fetchone())
        db.close()
        return row
    except Exception:
        return {"total": 0, "pushed": 0, "summarized": 0, "sources": 0}


# ── manual run ────────────────────────────────────────────

@app.post("/api/run")
async def manual_run(req: RunRequest):
    import subprocess
    cmd = ["python3", "main.py", "-v"]
    if req.dry_run:
        cmd.append("--dry-run")
    if req.no_summary:
        cmd.append("--no-summary")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, cwd=str(BASE_DIR)
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[-10000:],
            "stderr": result.stderr[-10000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "Timeout after 300s"}


# ── static files ──────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
