"""
제목/태그/해시태그 분석 모듈
"""
import json
import re
import sys
import os
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db.database import get_videos_for_date, save_daily_stats

try:
    from konlpy.tag import Okt
    _okt = Okt()
    KONLPY_AVAILABLE = True
except Exception:
    KONLPY_AVAILABLE = False

STOPWORDS = {
    "이", "가", "은", "는", "을", "를", "의", "에", "도", "와", "과",
    "로", "으로", "에서", "부터", "까지", "하다", "이다", "있다", "없다",
    "되다", "하고", "그리고", "하지만", "그러나", "그래서", "때문에",
    "때", "것", "수", "더", "진짜", "정말", "너무", "완전", "진심",
    "vlog", "브이로그", "영상", "유튜브", "채널", "구독", "좋아요",
}


def _extract_hashtags(text: str) -> list[str]:
    return [h.lstrip("#").lower() for h in re.findall(r"#\S+", text)]


def _tokenize(text: str) -> list[str]:
    tokens = _okt.nouns(text) if KONLPY_AVAILABLE else re.findall(r"[가-힣]{2,}", text)
    return [t for t in tokens if t not in STOPWORDS and len(t) >= 2]


def _extract_title_ngrams(title: str, n: int = 2) -> list[str]:
    tokens = _tokenize(title)
    if n == 1:
        return tokens
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def analyze_date(target_date: str | None = None) -> dict:
    if target_date is None:
        target_date = date.today().isoformat()

    videos = get_videos_for_date(target_date)
    if not videos:
        print(f"[analyzer] {target_date} 데이터 없음")
        return {}

    print(f"[analyzer] {target_date} 영상 {len(videos)}개 분석 중...")

    title_unigrams: Counter = Counter()
    title_bigrams:  Counter = Counter()
    all_tags:       Counter = Counter()
    all_hashtags:   Counter = Counter()

    for v in videos:
        title    = v.get("title", "")
        desc     = v.get("description", "")
        tags_raw = v.get("tags", "[]")

        title_unigrams.update(_extract_title_ngrams(title, n=1))
        title_bigrams.update(_extract_title_ngrams(title, n=2))

        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except Exception:
            tags = []
        all_tags.update([t.lower() for t in tags if t])
        all_hashtags.update(_extract_hashtags(title + " " + desc))

    stats = {
        "date"              : target_date,
        "video_count"       : len(videos),
        "top_keywords"      : title_unigrams.most_common(30),
        "top_title_patterns": title_bigrams.most_common(20),
        "top_tags"          : all_tags.most_common(30),
        "top_hashtags"      : all_hashtags.most_common(30),
    }

    save_daily_stats(target_date, stats)
    print(f"[analyzer] 분석 완료 → daily_stats 저장")
    return stats


def print_stats(stats: dict):
    if not stats:
        print("분석 결과 없음")
        return

    print(f"\n{'='*50}")
    print(f"  분석 날짜: {stats.get('date')}  |  영상 수: {stats.get('video_count')}")
    print(f"{'='*50}")

    print("\n[오늘 자주 등장한 키워드 TOP 20]")
    for word, cnt in stats.get("top_keywords", [])[:20]:
        print(f"  {'█' * min(cnt,30)}  {word} ({cnt})")

    print("\n[제목 패턴 (2-gram) TOP 15]")
    for phrase, cnt in stats.get("top_title_patterns", [])[:15]:
        print(f"  {phrase:<20} ({cnt})")

    print("\n[자주 쓰인 태그 TOP 20]")
    for tag, cnt in stats.get("top_tags", [])[:20]:
        print(f"  #{tag:<18} ({cnt})")

    print("\n[자주 쓰인 해시태그 TOP 20]")
    for ht, cnt in stats.get("top_hashtags", [])[:20]:
        print(f"  #{ht:<18} ({cnt})")
    print()
