"""
추천 엔진 통합 진입점
A: DB 트렌드 기반 제목 추가 생성
C: 유사 제목 중복 억제 (Jaccard)
D: 실제 조회수 데이터 기반 가중치 보정
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from recommend.extractor  import extract_info
from recommend.retriever  import retrieve
from recommend.templates  import generate_template_titles
from recommend.ollama_gen import generate as ollama_generate, check_connection
from recommend.scorer     import (
    rank_titles,
    deduplicate_titles,
    calibrate_from_db,
    apply_calibration,
)

# ── A: DB 트렌드 기반 제목 생성 헬퍼 ────────────────────────────────────
_HOOK_WORDS   = ["실화", "미쳤", "반칙", "레전드", "이거", "여기", "숨겨", "이게"]
_TREND_SUFFIX = ["인데 미쳤다", "가봤는데 레전드", "찐맛집 여기였음", "실화임?"]


def _generate_trend_titles(food_type: str, patterns: dict) -> list[str]:
    """
    A: DB 트렌드 데이터(실제 인기 제목 구조 + 해시태그)를 활용해
    추가 제목 후보 생성. DB 데이터 없으면 빈 리스트 반환.
    """
    results: list[str] = []
    top_tags   = patterns.get("top_hashtags", [])[:5]
    ref_titles = patterns.get("titles", [])[:8]

    # 1) 실제 인기 제목의 앞 구조 + food_type
    for title in ref_titles:
        words = title.split()
        if len(words) < 2:
            continue
        first = words[0]
        # 첫 단어가 후킹 성격이면 "[후킹단어] [food_type]" 생성
        if any(hw in first for hw in _HOOK_WORDS):
            candidate = f"{first} {food_type}임"
            if 4 <= len(candidate) <= 22:
                results.append(candidate)
        # "X에서" 구조 → "X에서 [food_type] 찐맛집"
        for i, w in enumerate(words[:3]):
            if "에서" in w:
                prefix    = " ".join(words[:i+1])
                candidate = f"{prefix} {food_type} 찐맛집"
                if len(candidate) <= 26:
                    results.append(candidate)
                break

    # 2) 트렌드 해시태그 키워드 + food_type 조합
    import random
    for tag in top_tags:
        suffix    = random.choice(_TREND_SUFFIX)
        candidate = f"{food_type} {tag} {suffix}"
        if 8 <= len(candidate) <= 28:
            results.append(candidate)

    # 중복 제거 후 최대 6개
    return list(dict.fromkeys(results))[:6]


def run(script: str, food_type: str, use_ollama: bool = True) -> dict:
    """
    추천 실행
    - script   : 영상 대본 텍스트
    - food_type: 음식 종류 (예: "카페 라떼", "삼겹살", "디저트")
    - use_ollama: Ollama 사용 여부
    """
    print(f"\n{'='*55}")
    print(f"  추천 시작 | 음식: {food_type}")
    print(f"{'='*55}")

    # 1. 대본에서 정보 추출
    info = extract_info(script, food_type)
    print(f"[engine] 장소: {info['location']} | 분위기: {info['moods']}")
    print(f"[engine] 카테고리: {info['food_category']}")

    # 2. DB에서 관련 영상 패턴 검색
    patterns    = retrieve(food_type, info["keywords"])
    has_db_data = len(patterns.get("titles", [])) > 0

    # 3. 템플릿 기반 추천
    template_results = generate_template_titles(
        food_type=food_type,
        location=info["location"],
        count=8,
    )

    # 4. Ollama 기반 추천
    ollama_results = {"titles": [], "hashtags": []}
    if use_ollama:
        ollama_results = ollama_generate(script, food_type, info, patterns)

    # ── A: DB 트렌드 기반 추가 후보 ───────────────────────────────────
    trend_titles: list[str] = []
    if has_db_data:
        trend_titles = _generate_trend_titles(food_type, patterns)
        if trend_titles:
            print(f"[engine] A: DB 트렌드 기반 제목 {len(trend_titles)}개 추가")

    # 5. 해시태그 통합 (Ollama + DB 패턴)
    combined_hashtags = list(dict.fromkeys(
        ollama_results.get("hashtags", []) +
        [f"#{h}" for h in patterns.get("top_hashtags", [])[:20]]
    ))[:20]

    # 6. 전체 제목 후보 수집
    all_candidates = (
        ollama_results.get("titles", []) +
        [t["title"] for t in template_results] +
        trend_titles
    )

    # 7. 바이럴 점수 계산
    ranked = rank_titles(all_candidates)

    # ── D: DB 데이터 있으면 실제 engagement 기반 가중치 보정 ──────────
    if has_db_data:
        try:
            from crol_config import DB_PATH
            multipliers = calibrate_from_db(DB_PATH)
            ranked      = apply_calibration(ranked, multipliers)
        except Exception as e:
            print(f"[engine] D: 보정 스킵 ({e})")

    # ── C: 유사 제목 중복 억제 ─────────────────────────────────────────
    before_dedup = len(ranked)
    ranked       = deduplicate_titles(ranked, threshold=0.55)
    print(f"[engine] C: 중복 억제 {before_dedup}개 → {len(ranked)}개")

    ranked_titles = [
        {"title": vs.title, "viral_score": vs.total, "hooks": vs.matched_hooks}
        for vs in ranked
    ]

    return {
        "food_type"           : food_type,
        "location"            : info["location"],
        "food_category"       : info["food_category"],
        "moods"               : info["moods"],
        "keyword_scores"      : info.get("keyword_scores", {}),
        "template_titles"     : template_results,
        "ollama_titles"       : ollama_results.get("titles", []),
        "trend_titles"        : trend_titles,
        "ranked_titles"       : ranked_titles,
        "recommended_hashtags": combined_hashtags,
        "ref_titles"          : patterns.get("titles", [])[:5],
    }


def print_result(result: dict):
    if not result:
        print("추천 결과 없음")
        return

    print(f"\n{'='*55}")
    print(f"  추천 결과 | {result.get('food_type')} | {result.get('location', '장소 미상')}")
    print(f"{'='*55}")

    if result.get("ranked_titles"):
        print("\n[바이럴 점수 통합 랭킹 TOP5]  ← C: 중복제거 + D: 보정 적용")
        for i, item in enumerate(result["ranked_titles"][:5], 1):
            hooks = ", ".join(item.get("hooks", [])) or "-"
            print(f"  {i}. [{item['viral_score']:.2f}] {item['title']}")
            print(f"       패턴: {hooks}")

    if result.get("trend_titles"):
        print("\n[A: DB 트렌드 기반 제목]")
        for i, t in enumerate(result["trend_titles"], 1):
            print(f"  {i}. {t}")

    if result.get("ollama_titles"):
        print("\n[AI 추천 제목 (Ollama)]")
        for i, title in enumerate(result["ollama_titles"], 1):
            print(f"  {i}. {title}")

    print("\n[템플릿 추천 제목]")
    for i, item in enumerate(result.get("template_titles", []), 1):
        tag = f"[{item['type']}]"
        print(f"  {i}. {tag:<12} {item['title']}")

    print("\n[추천 해시태그]")
    print("  " + " ".join(result.get("recommended_hashtags", [])))

    if result.get("ref_titles"):
        print("\n[참고한 실제 인기 영상 제목]")
        for t in result["ref_titles"]:
            print(f"  • {t}")
    print()
