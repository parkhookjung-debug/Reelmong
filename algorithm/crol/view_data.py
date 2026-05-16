"""
수집된 데이터 조회 도구

사용법:
  python view_data.py                       # 전체 개요
  python view_data.py --top 20              # 조회수 TOP 20 영상
  python view_data.py --channels 20         # 인기 채널 TOP 20
  python view_data.py --keyword 마라탕      # 특정 키워드 영상
  python view_data.py --channel UCxxxx      # 특정 채널 영상
  python view_data.py --recent              # 최근 수집된 영상
  python view_data.py --search 두바이        # 제목 검색
  python view_data.py --hooks               # 후킹 패턴 통계
  python view_data.py --by-month 2025-08    # 특정 월 영상
"""
import argparse
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crol_config import DB_PATH


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fmt_views(n: int) -> str:
    if n >= 10_000_000:
        return f"{n/10_000_000:.1f}천만"
    if n >= 10_000:
        return f"{n/10_000:.1f}만"
    if n >= 1_000:
        return f"{n/1000:.1f}천"
    return str(n)


def show_overview():
    conn = _conn()
    cur  = conn.cursor()

    print("\n" + "=" * 70)
    print("  맛노래 수집 데이터 개요")
    print("=" * 70)

    cur.execute("SELECT COUNT(*) FROM videos")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT channel_id) FROM videos WHERE channel_id != ''")
    channels = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM channels")
    channel_snaps = cur.fetchone()[0]
    cur.execute("SELECT SUM(view_count) FROM videos")
    total_views = cur.fetchone()[0] or 0
    cur.execute("SELECT source, COUNT(*) FROM videos GROUP BY source")
    sources = dict(cur.fetchall())

    print(f"\n  📺 영상 총계   : {total:,}개")
    print(f"  📡 추적 채널   : {channels:,}개")
    print(f"  📸 채널 스냅샷 : {channel_snaps:,}개")
    print(f"  👀 누적 조회수 : {total_views:,}뷰 ({_fmt_views(total_views)})")
    print()
    print(f"  [출처별]")
    for src, n in sources.items():
        label = {"search": "키워드 검색", "popular": "인기차트", "backfill": "백필"}.get(src, src or "(기타)")
        print(f"    {label:<12}: {n:,}개")

    cur.execute("SELECT MIN(snapshot_at), MAX(snapshot_at) FROM videos")
    mn, mx = cur.fetchone()
    print(f"\n  📅 수집 기간   : {mn} ~ {mx}")

    cur.execute("SELECT keyword, COUNT(*) FROM videos WHERE keyword IS NOT NULL GROUP BY keyword ORDER BY 2 DESC LIMIT 10")
    print(f"\n  🔑 키워드별 수집 TOP 10")
    for kw, n in cur.fetchall():
        bar = "█" * min(n // 20, 30)
        print(f"    {kw:<10} {bar} {n}개")

    conn.close()


def show_top_videos(n: int = 20):
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT title, channel, view_count, like_count, comment_count, keyword
        FROM videos
        WHERE is_short = 1
        ORDER BY view_count DESC
        LIMIT ?
    """, (n,))

    print(f"\n=== 🏆 조회수 TOP {n} 쇼츠 ===\n")
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"  {i:>2}. [{_fmt_views(row['view_count']):>6}뷰] {row['title'][:55]}")
        print(f"      ❤ {_fmt_views(row['like_count']):>5}  💬 {row['comment_count']:>4}  "
              f"@ {row['channel'][:25]:<25}  키워드: {row['keyword']}")
    conn.close()


def show_top_channels(n: int = 20):
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT title, subscriber_count, video_count, view_count
        FROM channels
        WHERE snapshot_at = (SELECT MAX(snapshot_at) FROM channels c2 WHERE c2.channel_id = channels.channel_id)
        ORDER BY subscriber_count DESC
        LIMIT ?
    """, (n,))

    print(f"\n=== 📡 구독자 TOP {n} 채널 ===\n")
    for i, row in enumerate(cur.fetchall(), 1):
        print(f"  {i:>2}. {row['title'][:30]:<30}  "
              f"👥 {_fmt_views(row['subscriber_count']):>6}  "
              f"📹 {row['video_count']:,}개 영상  "
              f"👁 {_fmt_views(row['view_count'])} 총조회")
    conn.close()


def show_keyword(keyword: str):
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT title, channel, view_count, like_count, snapshot_at
        FROM videos
        WHERE keyword = ? AND is_short = 1
        ORDER BY view_count DESC
        LIMIT 30
    """, (keyword,))

    rows = cur.fetchall()
    if not rows:
        print(f"\n  '{keyword}' 키워드 영상 없음")
        return

    print(f"\n=== 🔑 키워드 '{keyword}' TOP 30 ===\n")
    for i, row in enumerate(rows, 1):
        print(f"  {i:>2}. [{_fmt_views(row['view_count']):>6}뷰] {row['title'][:55]}")
        print(f"      @ {row['channel'][:30]:<30}  스냅: {row['snapshot_at'][:10]}")
    conn.close()


def show_recent(n: int = 30):
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT title, channel, view_count, snapshot_at, keyword
        FROM videos
        ORDER BY snapshot_at DESC, view_count DESC
        LIMIT ?
    """, (n,))

    print(f"\n=== 🆕 최근 수집된 영상 {n}개 ===\n")
    for row in cur.fetchall():
        print(f"  [{_fmt_views(row['view_count']):>6}뷰] {row['title'][:55]}")
        print(f"     수집: {row['snapshot_at']}  키워드: {row['keyword']}  @ {row['channel'][:25]}")
    conn.close()


def show_search(query: str):
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT title, channel, view_count, keyword
        FROM videos
        WHERE title LIKE ?
        ORDER BY view_count DESC
        LIMIT 30
    """, (f"%{query}%",))

    rows = cur.fetchall()
    print(f"\n=== 🔍 '{query}' 검색 결과 ({len(rows)}개) ===\n")
    for row in rows:
        print(f"  [{_fmt_views(row['view_count']):>6}뷰] {row['title'][:60]}")
        print(f"     @ {row['channel'][:25]}  키워드: {row['keyword']}")
    conn.close()


def show_hooks():
    import re
    HOOKS = {
        "실화형": r"(실화|실화임|실화야)",
        "감탄형": r"(미쳤|미친|미쳐)",
        "레전드형": r"(레전드|레전)",
        "반전형": r"(반칙|말이\s*돼|가능해)",
        "발견형": r"(숨겨|공개|찾았|발견)",
        "질문형": r"\?",
        "랭킹형": r"TOP\s*\d|\d+위|\d+등",
    }

    conn = _conn()
    cur  = conn.cursor()
    cur.execute("SELECT title FROM videos WHERE title IS NOT NULL AND is_short = 1")
    titles = [r[0] for r in cur.fetchall()]
    conn.close()

    print(f"\n=== 💬 후킹 패턴 출현 빈도 (총 {len(titles):,}개 쇼츠) ===\n")
    for name, pattern in HOOKS.items():
        regex = re.compile(pattern)
        n = sum(1 for t in titles if regex.search(t))
        pct = n / max(len(titles), 1) * 100
        bar = "█" * min(int(pct * 2), 40)
        print(f"  {name:<10} {bar} {n:,}개 ({pct:.1f}%)")


def show_by_month(ym: str):
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT title, channel, view_count, keyword
        FROM videos
        WHERE strftime('%Y-%m', snapshot_at) = ? AND is_short = 1
        ORDER BY view_count DESC
        LIMIT 30
    """, (ym,))

    rows = cur.fetchall()
    print(f"\n=== 📅 {ym} 월 TOP {len(rows)} ===\n")
    for row in rows:
        print(f"  [{_fmt_views(row['view_count']):>6}뷰] {row['title'][:55]}")
        print(f"     @ {row['channel'][:25]}  키워드: {row['keyword']}")
    conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top",      type=int, default=None, help="조회수 TOP N 영상")
    p.add_argument("--channels", type=int, default=None, help="구독자 TOP N 채널")
    p.add_argument("--keyword",  default=None, help="특정 키워드 영상")
    p.add_argument("--recent",   action="store_true", help="최근 수집된 영상")
    p.add_argument("--search",   default=None, help="제목 검색")
    p.add_argument("--hooks",    action="store_true", help="후킹 패턴 통계")
    p.add_argument("--by-month", default=None, help="특정 월 영상 (YYYY-MM)")
    args = p.parse_args()

    if args.top:
        show_top_videos(args.top)
    elif args.channels:
        show_top_channels(args.channels)
    elif args.keyword:
        show_keyword(args.keyword)
    elif args.recent:
        show_recent()
    elif args.search:
        show_search(args.search)
    elif args.hooks:
        show_hooks()
    elif args.by_month:
        show_by_month(args.by_month)
    else:
        show_overview()


if __name__ == "__main__":
    main()
