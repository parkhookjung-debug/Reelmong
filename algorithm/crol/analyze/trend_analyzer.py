"""
시계열 트렌드 분석 모듈

월별 데이터 추출 + 모멘텀 계산 + 라이징/폴링 감지
- 키워드별 월간 영상 수, 평균 조회수, 평균 engagement
- 채널별 성장률
- 후킹 패턴(2-gram) 사용 빈도 변화
"""
import re
import sqlite3
import sys
import os
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from crol_config import DB_PATH


# ── 후킹 패턴 사전 (scorer.py와 동일 기준) ──────────────────────
HOOK_PATTERNS = {
    "실화형": re.compile(r"(실화|실화임|실화야|실화인가)"),
    "감탄형": re.compile(r"(미쳤|미친|미쳐)"),
    "레전드형": re.compile(r"(레전드|레전|ㄹㅈㄷ)"),
    "반전형": re.compile(r"(반칙|말이\s*돼|가능해|된다고)"),
    "발견형": re.compile(r"(숨겨|공개|찾았|발굴|발견)"),
    "손해회피": re.compile(r"(손해|안\s*하면|놓치면|후회)"),
    "질문형": re.compile(r"\?"),
    "랭킹형": re.compile(r"TOP\s*\d|\d+위|\d+등"),
}


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── 1) 월별 키워드 메트릭 ──────────────────────────────────────
def monthly_keyword_metrics(keyword: str) -> dict[str, dict]:
    """
    특정 키워드의 월별 메트릭
    반환: {"2025-07": {"count": 50, "avg_views": 350000, "avg_engagement": 0.03}, ...}
    """
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT strftime('%Y-%m', snapshot_at) AS ym,
               COUNT(*) AS n,
               AVG(view_count) AS avg_v,
               AVG((CAST(like_count AS REAL) + CAST(comment_count AS REAL) * 2)
                   / (CAST(view_count AS REAL) + 1)) AS avg_eng
        FROM videos
        WHERE keyword = ? AND is_short = 1
        GROUP BY ym
        ORDER BY ym
    """, (keyword,))
    result = {
        row["ym"]: {
            "count": row["n"],
            "avg_views": round(row["avg_v"] or 0, 1),
            "avg_engagement": round(row["avg_eng"] or 0, 5),
        }
        for row in cur.fetchall()
    }
    conn.close()
    return result


def monthly_all_keywords() -> dict[str, dict[str, dict]]:
    """전체 키워드 × 월별 메트릭 일괄 추출"""
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT keyword,
               strftime('%Y-%m', snapshot_at) AS ym,
               COUNT(*) AS n,
               AVG(view_count) AS avg_v
        FROM videos
        WHERE keyword IS NOT NULL AND is_short = 1
        GROUP BY keyword, ym
    """)
    result: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in cur.fetchall():
        result[row["keyword"]][row["ym"]] = {
            "count": row["n"],
            "avg_views": round(row["avg_v"] or 0, 1),
        }
    conn.close()
    return dict(result)


# ── 2) 모멘텀 계산 ──────────────────────────────────────────────
def compute_momentum(monthly: dict[str, dict], window: int = 2) -> dict:
    """
    최근 window개월 평균 vs 그 이전 window개월 평균
    반환: {recent, prev, growth_pct, direction}
    """
    months_sorted = sorted(monthly.keys())
    if len(months_sorted) < window * 2:
        return {"recent": 0, "prev": 0, "growth_pct": 0, "direction": "unknown"}

    recent_months = months_sorted[-window:]
    prev_months   = months_sorted[-window*2:-window]

    recent_avg = sum(monthly[m]["avg_views"] for m in recent_months) / window
    prev_avg   = sum(monthly[m]["avg_views"] for m in prev_months) / window

    growth = ((recent_avg - prev_avg) / max(prev_avg, 1)) * 100

    if growth > 30:
        direction = "rising"
    elif growth < -30:
        direction = "falling"
    else:
        direction = "stable"

    return {
        "recent": round(recent_avg, 1),
        "prev": round(prev_avg, 1),
        "growth_pct": round(growth, 1),
        "direction": direction,
    }


# ── 3) 라이징 / 폴링 키워드 ─────────────────────────────────────
def rank_keywords_by_trend(
    min_total_videos: int = 30,
    window: int = 2,
) -> list[dict]:
    """
    모든 키워드의 모멘텀 계산 → 상승률 순 정렬
    """
    all_data = monthly_all_keywords()
    ranked   = []

    for keyword, monthly in all_data.items():
        total = sum(m["count"] for m in monthly.values())
        if total < min_total_videos:
            continue

        mom = compute_momentum(monthly, window=window)
        if mom["direction"] == "unknown":
            continue

        ranked.append({
            "keyword": keyword,
            "total_videos": total,
            **mom,
        })

    ranked.sort(key=lambda x: x["growth_pct"], reverse=True)
    return ranked


def rising_keywords(top_n: int = 20) -> list[dict]:
    """급상승 키워드 TOP N"""
    return [k for k in rank_keywords_by_trend() if k["direction"] == "rising"][:top_n]


def falling_keywords(top_n: int = 20) -> list[dict]:
    """급하락 키워드 TOP N"""
    falling = [k for k in rank_keywords_by_trend() if k["direction"] == "falling"]
    return sorted(falling, key=lambda x: x["growth_pct"])[:top_n]


# ── 4) 후킹 패턴 트렌드 ────────────────────────────────────────
def monthly_hook_pattern_usage() -> dict[str, dict[str, int]]:
    """
    월별 × 후킹 패턴별 영상 수
    반환: {"실화형": {"2025-07": 30, "2025-08": 45}, ...}
    """
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT strftime('%Y-%m', snapshot_at) AS ym, title
        FROM videos
        WHERE is_short = 1 AND title IS NOT NULL
    """)

    result: dict[str, dict[str, int]] = {name: defaultdict(int) for name in HOOK_PATTERNS}
    for row in cur.fetchall():
        title = row["title"]
        ym    = row["ym"]
        for name, pattern in HOOK_PATTERNS.items():
            if pattern.search(title):
                result[name][ym] += 1
    conn.close()

    return {name: dict(d) for name, d in result.items()}


def hook_pattern_trends() -> list[dict]:
    """후킹 패턴별 모멘텀 분석"""
    monthly = monthly_hook_pattern_usage()
    results = []
    for name, by_month in monthly.items():
        if not by_month:
            continue
        # count 메트릭으로 모멘텀 계산
        # 변환: {ym: {avg_views: count}} 형태로
        synthetic = {m: {"avg_views": c} for m, c in by_month.items()}
        mom = compute_momentum(synthetic)
        results.append({
            "pattern": name,
            "monthly_counts": dict(sorted(by_month.items())),
            **mom,
        })
    results.sort(key=lambda x: x["growth_pct"], reverse=True)
    return results


# ── 5) 채널 성장률 분석 ────────────────────────────────────────
def fast_growing_channels(top_n: int = 20) -> list[dict]:
    """
    같은 채널의 여러 스냅샷 사이 구독자/평균조회수 증가율
    """
    conn = _conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT c.channel_id, c.title,
               MIN(c.snapshot_at) AS first_snap,
               MAX(c.snapshot_at) AS last_snap,
               (SELECT subscriber_count FROM channels WHERE channel_id = c.channel_id
                ORDER BY snapshot_at ASC LIMIT 1) AS first_subs,
               (SELECT subscriber_count FROM channels WHERE channel_id = c.channel_id
                ORDER BY snapshot_at DESC LIMIT 1) AS last_subs,
               COUNT(DISTINCT c.snapshot_at) AS snaps
        FROM channels c
        GROUP BY c.channel_id
        HAVING snaps >= 2 AND first_subs > 100
    """)

    results = []
    for row in cur.fetchall():
        first, last = row["first_subs"], row["last_subs"]
        growth_pct  = ((last - first) / max(first, 1)) * 100
        if growth_pct > 0:
            results.append({
                "channel_id":  row["channel_id"],
                "title":       row["title"],
                "first_subs":  first,
                "last_subs":   last,
                "growth_pct":  round(growth_pct, 1),
                "snaps":       row["snaps"],
                "from_to":     f"{row['first_snap'][:10]} → {row['last_snap'][:10]}",
            })
    conn.close()

    results.sort(key=lambda x: x["growth_pct"], reverse=True)
    return results[:top_n]
