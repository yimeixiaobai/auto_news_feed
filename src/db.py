import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime


class NewsDB:
    def __init__(self, db_path: str = "data/news.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT DEFAULT '',
                published_at TEXT,
                summary TEXT DEFAULT '',
                pushed_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_url_hash ON articles(url_hash);
            CREATE INDEX IF NOT EXISTS idx_created_at ON articles(created_at);
        """)
        self.conn.commit()

    @staticmethod
    def hash_url(url: str) -> str:
        return hashlib.sha256(url.strip().encode()).hexdigest()[:16]

    def exists(self, url: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM articles WHERE url_hash = ?", (self.hash_url(url),)
        )
        return cur.fetchone() is not None

    def insert_article(
        self,
        url: str,
        title: str,
        source: str,
        category: str = "",
        published_at: str = "",
        summary: str = "",
    ) -> bool:
        url_hash = self.hash_url(url)
        try:
            self.conn.execute(
                """INSERT INTO articles (url_hash, url, title, source, category, published_at, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (url_hash, url, title, source, category, published_at, summary),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def mark_pushed(self, url: str):
        self.conn.execute(
            "UPDATE articles SET pushed_at = ? WHERE url_hash = ?",
            (datetime.now().isoformat(), self.hash_url(url)),
        )
        self.conn.commit()

    def update_summary(self, url: str, summary: str):
        self.conn.execute(
            "UPDATE articles SET summary = ? WHERE url_hash = ?",
            (summary, self.hash_url(url)),
        )
        self.conn.commit()

    def get_recently_pushed(self, hours: int = 48) -> list[dict]:
        cur = self.conn.execute(
            """SELECT title, source FROM articles
               WHERE pushed_at IS NOT NULL
               AND pushed_at >= datetime('now', ?)
               ORDER BY pushed_at DESC""",
            (f'-{hours} hours',),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_unpushed_recent(self, max_age_hours: int = 24) -> list[dict]:
        cur = self.conn.execute(
            """SELECT url, title, source, category, published_at, summary
               FROM articles
               WHERE pushed_at IS NULL
               AND created_at >= datetime('now', ?)
               ORDER BY created_at DESC""",
            (f'-{max_age_hours} hours',),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_unpushed(self, limit: int = 50) -> list[dict]:
        cur = self.conn.execute(
            """SELECT url, title, source, category, published_at, summary
               FROM articles WHERE pushed_at IS NULL
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]

    def close(self):
        self.conn.close()
