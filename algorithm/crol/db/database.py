import sqlite3
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from crol_config import DB_PATH


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id            TEXT NOT NULL,
            snapshot_at   TEXT NOT NULL,
            source        TEXT,
            keyword       TEXT,
            title         TEXT,
            description   TEXT,
            tags          TEXT,
            channel       TEXT,
            channel_id    TEXT DEFAULT '',
            view_count    INTEGER,
            like_count    INTEGER,
            comment_count INTEGER,
            published_at  TEXT,
            duration      TEXT,
            is_short      INTEGER,
            PRIMARY KEY (id, snapshot_at)
        )
    """)

    # 기존 DB에 channel_id 컬럼 없으면 추가
    try:
        cur.execute("ALTER TABLE videos ADD COLUMN channel_id TEXT DEFAULT ''")
    except Exception:
        pass

    # 채널 구독자 수 스냅샷 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id       TEXT NOT NULL,
            snapshot_at      TEXT NOT NULL,
            title            TEXT,
            subscriber_count INTEGER DEFAULT 0,
            video_count      INTEGER DEFAULT 0,
            view_count       INTEGER DEFAULT 0,
            PRIMARY KEY (channel_id, snapshot_at)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date               TEXT PRIMARY KEY,
            top_title_patterns TEXT,
            top_tags           TEXT,
            top_hashtags       TEXT,
            top_keywords       TEXT,
            created_at         TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] 초기화 완료")


# ── videos ──────────────────────────────────────────────────────────
def upsert_video(row: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO videos
        (id, snapshot_at, source, keyword, title, description, tags, channel,
         channel_id, view_count, like_count, comment_count, published_at, duration, is_short)
        VALUES (:id, :snapshot_at, :source, :keyword, :title, :description, :tags,
                :channel, :channel_id, :view_count, :like_count, :comment_count,
                :published_at, :duration, :is_short)
    """, row)
    conn.commit()
    conn.close()


def get_videos_for_date(date: str) -> list[dict]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM videos WHERE snapshot_at LIKE ?", (f"{date}%",))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── channels ─────────────────────────────────────────────────────────
def upsert_channel(row: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO channels
        (channel_id, snapshot_at, title, subscriber_count, video_count, view_count)
        VALUES (:channel_id, :snapshot_at, :title, :subscriber_count, :video_count, :view_count)
    """, row)
    conn.commit()
    conn.close()


def get_channel_viral_coefficients() -> dict[str, float]:
    """
    channel_id → viral_coefficient 매핑 반환
    viral_coefficient = 채널 평균 영상 조회수 / 구독자 수
    → 구독자 대비 조회수가 높을수록 성장 중인 채널
    """
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 채널별 최신 구독자 수
    cur.execute("""
        SELECT c.channel_id, c.subscriber_count,
               AVG(v.view_count) AS avg_views
        FROM channels c
        JOIN videos v ON v.channel_id = c.channel_id
        WHERE c.snapshot_at = (
            SELECT MAX(snapshot_at) FROM channels c2
            WHERE c2.channel_id = c.channel_id
        )
        AND v.is_short = 1
        AND v.view_count > 0
        GROUP BY c.channel_id
        HAVING c.subscriber_count > 0
    """)
    rows = cur.fetchall()
    conn.close()

    result = {}
    for row in rows:
        subs      = max(row["subscriber_count"], 1)
        avg_views = row["avg_views"] or 0
        result[row["channel_id"]] = avg_views / subs  # viral coefficient

    return result


# ── daily_stats ──────────────────────────────────────────────────────
def save_daily_stats(date: str, stats: dict):
    import json
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO daily_stats
        (date, top_title_patterns, top_tags, top_hashtags, top_keywords, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        date,
        json.dumps(stats.get("top_title_patterns", []), ensure_ascii=False),
        json.dumps(stats.get("top_tags", []), ensure_ascii=False),
        json.dumps(stats.get("top_hashtags", []), ensure_ascii=False),
        json.dumps(stats.get("top_keywords", []), ensure_ascii=False),
        datetime.now().isoformat(),
    ))
    conn.commit()
    conn.close()


def get_latest_daily_stats() -> dict | None:
    import json
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_stats ORDER BY date DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for key in ("top_title_patterns", "top_tags", "top_hashtags", "top_keywords"):
        d[key] = json.loads(d[key])
    return d
