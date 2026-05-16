"""
DB에서 관련 인기 영상 데이터 검색

스코어 구성:
  keyword_match  30% — 제목/설명 키워드 매칭
  engagement     30% — (좋아요 + 댓글×2) / 조회수
  recency        20% — 최신성 (2년 감쇠)
  view_norm       5% — 조회수 로그 정규화
  channel_growth 15% — 채널 바이럴 계수 (구독자 대비 조회수)
"""
import json
import sqlite3
import sys, os
from datetime import datetime
from math import log1p

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from crol_config import DB_PATH

# 채널 바이럴 계수 캐시 (수집 당시 로드, 재쿼리 방지)
_channel_viral_cache: dict[str, float] = {}
_channel_cache_loaded = False


def _load_channel_viral_cache():
    global _channel_viral_cache, _channel_cache_loaded
    if _channel_cache_loaded:
        return
    try:
        from db.database import get_channel_viral_coefficients
        _channel_viral_cache = get_channel_viral_coefficients()
        _channel_cache_loaded = True
        if _channel_viral_cache:
            print(f"[retriever] 채널 바이럴 계수 로드: {len(_channel_viral_cache)}개 채널")
    except Exception:
        _channel_cache_loaded = True  # 실패해도 재시도 안 함


def _channel_growth_score(channel_id: str) -> float:
    """
    채널 바이럴 계수 → 0~1 정규화
    viral_coeff = 평균 영상 조회수 / 구독자 수
    계수가 높을수록 구독자 대비 조회수가 많은 성장 중인 채널
    기준: 계수 100배(100x) 이상이면 만점
    """
    if not _channel_viral_cache:
        return 0.5  # 데이터 없으면 중립값
    coeff = _channel_viral_cache.get(channel_id, 0.0)
    if coeff <= 0:
        return 0.3  # 채널 정보 없는 경우 낮은 기본값
    return min(log1p(coeff) / log1p(100), 1.0)


def _score_video(row: dict, search_terms: list[str]) -> float:
    """
    영상 종합 스코어 계산

    score = keyword(30%) + engagement(30%) + recency(20%) + view(5%) + channel_growth(15%)
    """
    title         = row.get("title", "")
    desc          = row.get("description", "") or ""
    view_count    = max(int(row.get("view_count", 0) or 0), 1)
    like_count    = int(row.get("like_count", 0) or 0)
    comment_count = int(row.get("comment_count", 0) or 0)
    published_at  = row.get("published_at", "")
    channel_id    = row.get("channel_id", "")

    # 1) 키워드 매칭 (제목 가중치 2배)
    text_full  = title.lower() + " " + desc.lower()
    text_title = title.lower()
    match_score = 0.0
    for term in search_terms:
        t = term.lower()
        if t in text_title:
            match_score += 2.0
        elif t in text_full:
            match_score += 1.0
    match_norm = min(match_score / max(len(search_terms), 1), 3.0) / 3.0

    # 2) Engagement rate
    engagement      = (like_count + comment_count * 2) / view_count
    engagement_norm = min(engagement * 100, 1.0)

    # 3) 최신성 (2년 감쇠)
    recency = 0.5
    if published_at:
        try:
            pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            days_ago = (datetime.now(pub_date.tzinfo) - pub_date).days
            recency  = max(0.2, 1.0 - days_ago / 730)
        except Exception:
            pass

    # 4) 조회수 로그 정규화
    view_norm = min(log1p(view_count) / log1p(1_000_000), 1.0)

    # 5) 채널 성장률 (바이럴 계수)
    ch_growth = _channel_growth_score(channel_id)

    score = (
        match_norm      * 0.30 +
        engagement_norm * 0.30 +
        recency         * 0.20 +
        view_norm       * 0.05 +
        ch_growth       * 0.15
    )
    return round(score, 4)


def get_relevant_videos(
    food_type: str,
    keywords: list[str],
    food_category: str = "",
    limit: int = 40,
) -> list[dict]:
    """
    음식 종류 + 키워드 + 카테고리로 관련 영상 검색 (스코어링 기반 정렬)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
    except Exception as e:
        print(f"[retriever] DB 연결 실패: {e}")
        return []

    search_terms = [food_type] + keywords[:6]

    # 카테고리 필터 포함 OR 제외
    conditions = " OR ".join(["title LIKE ?" for _ in search_terms])
    params = [f"%{term}%" for term in search_terms]

    # DB 컬럼 확인 후 쿼리 조정
    try:
        cur.execute("PRAGMA table_info(videos)")
        cols = {row["name"] for row in cur.fetchall()}
    except Exception:
        cols = {"title", "tags", "description", "view_count", "is_short"}

    select_cols = "title, tags, description, view_count, is_short"
    if "like_count" in cols:
        select_cols += ", like_count"
    if "comment_count" in cols:
        select_cols += ", comment_count"
    if "published_at" in cols:
        select_cols += ", published_at"
    # support both 'channel' and 'channel_id' column names
    if "channel_id" in cols:
        select_cols += ", channel_id"
    elif "channel" in cols:
        select_cols += ", channel as channel_id"

    try:
        cur.execute(f"""
            SELECT {select_cols}
            FROM videos
            WHERE is_short = 1 AND ({conditions})
            LIMIT ?
        """, params + [limit * 2])  # 스코어링 후 줄이므로 넉넉하게

        rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[retriever] 쿼리 실패: {e}")
        rows = []
    finally:
        conn.close()

    if not rows:
        return []

    # 스코어링 + 정렬
    for row in rows:
        row["_score"] = _score_video(row, search_terms)

    rows.sort(key=lambda x: x["_score"], reverse=True)

    # 채널 다양성 보장 (같은 채널 최대 3개)
    channel_count: dict[str, int] = {}
    diverse_rows = []
    for row in rows:
        ch = row.get("channel_id", "unknown")
        if channel_count.get(ch, 0) < 3:
            diverse_rows.append(row)
            channel_count[ch] = channel_count.get(ch, 0) + 1
        if len(diverse_rows) >= limit:
            break

    return diverse_rows


def get_top_shorts(limit: int = 30) -> list[dict]:
    """fallback: engagement 기반 전체 쇼츠 TOP"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(videos)")
        cols = {row["name"] for row in cur.fetchall()}

        if "like_count" in cols:
            order = "(CAST(like_count AS REAL) + 1) / (CAST(view_count AS REAL) + 1) DESC, view_count DESC"
        else:
            order = "view_count DESC"

        cur.execute(f"""
            SELECT title, tags, description, view_count
            FROM videos
            WHERE is_short = 1
            ORDER BY {order}
            LIMIT ?
        """, (limit,))

        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[retriever] fallback 쿼리 실패: {e}")
        return []


def extract_patterns(videos: list[dict]) -> dict:
    """
    영상 목록에서 제목 패턴, 해시태그 빈도 추출 (가중치 반영)
    - 스코어 높은 영상의 패턴에 더 높은 가중치
    """
    import re
    from collections import Counter

    all_hashtags: Counter = Counter()
    all_tags:     Counter = Counter()
    titles_with_score: list[tuple[str, float]] = []

    for v in videos:
        title = v.get("title", "")
        desc  = v.get("description", "") or ""
        tags_raw = v.get("tags", "[]")
        score = v.get("_score", 0.5)
        weight = max(score * 2, 0.1)  # 스코어 높을수록 더 큰 가중치

        if title:
            titles_with_score.append((title, score))

        # 해시태그 (가중치 반영)
        hashtags = re.findall(r"#\S+", title + " " + desc)
        for h in hashtags:
            tag = h.lstrip("#").lower()
            all_hashtags[tag] += weight

        # 태그
        try:
            tags = json.loads(tags_raw) if tags_raw else []
            for t in tags:
                if t:
                    all_tags[t.lower()] += weight
        except Exception:
            pass

    # 스코어 높은 순 정렬
    titles_with_score.sort(key=lambda x: x[1], reverse=True)

    return {
        "titles"       : [t for t, _ in titles_with_score[:20]],
        "top_hashtags" : [tag for tag, _ in all_hashtags.most_common(25)],
        "top_tags"     : [tag for tag, _ in all_tags.most_common(25)],
        "avg_score"    : round(
            sum(v.get("_score", 0) for v in videos) / max(len(videos), 1), 3
        ),
    }


def retrieve(food_type: str, keywords: list[str], food_category: str = "") -> dict:
    """전체 검색 + 패턴 추출 통합"""
    _load_channel_viral_cache()  # 채널 성장률 캐시 로드
    videos = get_relevant_videos(food_type, keywords, food_category, limit=40)

    if len(videos) < 10:
        top = get_top_shorts(limit=20)
        # 중복 제거 후 보완
        existing_titles = {v["title"] for v in videos}
        for v in top:
            if v.get("title") not in existing_titles:
                videos.append(v)

    patterns = extract_patterns(videos)
    print(f"[retriever] 관련 영상 {len(videos)}개 검색됨 (avg_score: {patterns['avg_score']})")
    return patterns
