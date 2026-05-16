"""
분석 결과 기반 추천 생성
"""
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db.database import get_latest_daily_stats

TITLE_TEMPLATES = [
    "{place}에서 요즘 제일 핫한 {food}",
    "솔직히 여긴 반칙임 | {keyword} 맛집",
    "{keyword} 웨이팅 이해되는 집",
    "서울 {keyword} 찐 추천 TOP {n}",
    "{food} 처음 먹어봤는데 {reaction}",
    "요즘 난리난 {keyword} 신상 카페 다녀왔어요",
    "{place} 숨겨진 {food} 맛집 발굴",
    "솔직 {food} 후기 (진짜 맛있는 집 알려드림)",
]
PLACES    = ["성수", "홍대", "강남", "연남동", "망원", "을지로", "신촌", "이태원"]
REACTIONS = ["인생 맛이었다", "이건 진짜임", "완전 반했어", "매일 오고 싶다"]


def _top_n(items: list, n: int) -> list:
    return [item for item, _ in items[:n]]


def generate_recommendations(stats: dict | None = None) -> dict:
    if stats is None:
        stats = get_latest_daily_stats()
    if not stats:
        print("[recommender] 분석 데이터 없음.")
        return {}

    top_keywords = _top_n(stats.get("top_keywords", []), 10)
    top_tags     = _top_n(stats.get("top_tags", []), 20)
    top_hashtags = _top_n(stats.get("top_hashtags", []), 20)

    recommended_titles = []
    for _ in range(10):
        template = random.choice(TITLE_TEMPLATES)
        keyword  = random.choice(top_keywords) if top_keywords else "맛집"
        title    = template.format(
            keyword=keyword, food=keyword,
            place=random.choice(PLACES),
            reaction=random.choice(REACTIONS),
            n=random.choice([3, 5, 7, 10]),
        )
        recommended_titles.append(title)

    hashtag_set = list(dict.fromkeys(top_hashtags + top_tags))[:15]
    hashtag_set = ["#" + h.lstrip("#") for h in hashtag_set]

    trending_combos = [phrase for phrase, _ in stats.get("top_title_patterns", [])[:5]]

    return {
        "date"                   : stats.get("date"),
        "recommended_titles"     : recommended_titles,
        "recommended_hashtags"   : hashtag_set,
        "trending_keyword_combos": trending_combos,
        "hot_single_keywords"    : top_keywords[:15],
    }


def print_recommendations(rec: dict):
    if not rec:
        print("추천 결과 없음")
        return

    print(f"\n{'='*55}")
    print(f"  트렌드 추천  |  기준일: {rec.get('date')}")
    print(f"{'='*55}")

    print("\n[오늘 음식 숏폼에 어울리는 추천 제목 10개]")
    for i, title in enumerate(rec.get("recommended_titles", []), 1):
        print(f"  {i:2}. {title}")

    print("\n[추천 해시태그 세트]")
    print("  " + " ".join(rec.get("recommended_hashtags", [])))

    print("\n[오늘 뜨는 키워드 조합]")
    for combo in rec.get("trending_keyword_combos", []):
        print(f"  • {combo}")

    print("\n[핫 단일 키워드]")
    print("  " + ", ".join(rec.get("hot_single_keywords", [])))
    print()
