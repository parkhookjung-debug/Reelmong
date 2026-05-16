"""
대본 텍스트에서 핵심 정보 추출 (강화버전)

개선사항:
- TF-IDF 기반 키워드 중요도 스코어링
- KoNLPy 형태소 분석 (설치 시 활성화, 미설치 시 regex fallback)
- 카테고리 가중치 매칭 (단순 first-match → 다중 스코어)
- 분위기 복합 감지
"""
import re
import sys, os
from collections import Counter
from math import log

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── 장소 키워드 ────────────────────────────────────────────────────────
LOCATION_WORDS = [
    "성수", "홍대", "강남", "연남", "망원", "을지로", "신촌", "이태원",
    "합정", "건대", "압구정", "청담", "여의도", "마포", "용산", "종로",
    "부산", "제주", "인천", "수원", "대전", "대구", "광주", "전주",
    "송리단길", "경리단길", "가로수길", "익선동", "북촌",
]

# ── 분위기 키워드 (가중치 포함) ───────────────────────────────────────
MOOD_WORDS: dict[str, list[tuple[str, float]]] = {
    "감성적": [("감성", 1.0), ("분위기", 0.8), ("뷰", 0.9), ("인테리어", 0.8),
               ("예쁜", 0.7), ("힐링", 0.9), ("인스타", 0.6), ("포토", 0.6)],
    "가성비": [("가성비", 1.0), ("저렴", 0.9), ("싸다", 0.9), ("착한가격", 1.0),
               ("합리적", 0.8), ("가격", 0.5), ("혜자", 0.9)],
    "프리미엄": [("오마카세", 1.0), ("파인다이닝", 1.0), ("고급", 0.9),
                 ("프리미엄", 0.9), ("특별한", 0.6), ("럭셔리", 0.9)],
    "웨이팅": [("웨이팅", 1.0), ("줄", 0.7), ("예약", 0.7), ("인기많은", 0.8),
               ("핫한", 0.8), ("오픈런", 1.0), ("품절", 0.7)],
    "혼밥": [("혼밥", 1.0), ("혼술", 0.9), ("혼자", 0.8), ("1인", 0.9),
              ("솔로", 0.5)],
    "데이트": [("데이트", 1.0), ("커플", 0.9), ("둘이서", 0.9), ("연인", 0.8),
               ("기념일", 0.8)],
    "가족": [("가족", 1.0), ("아이", 0.8), ("어린이", 0.7), ("키즈", 0.9),
             ("패밀리", 0.9)],
}

# ── 음식 카테고리 (가중치 포함) ───────────────────────────────────────
FOOD_CATEGORY: dict[str, list[tuple[str, float]]] = {
    "카페/디저트": [("카페", 1.0), ("디저트", 1.0), ("케이크", 0.9), ("빵", 0.8),
                   ("커피", 0.9), ("라떼", 0.9), ("베이커리", 1.0), ("마카롱", 0.8),
                   ("크로플", 0.9), ("타르트", 0.8)],
    "한식": [("한식", 1.0), ("비빔밥", 0.9), ("갈비", 0.9), ("삼겹살", 0.9),
             ("된장", 0.8), ("국밥", 0.9), ("김치", 0.7), ("불고기", 0.9),
             ("냉면", 0.8), ("설렁탕", 0.8)],
    "일식": [("스시", 1.0), ("초밥", 1.0), ("라멘", 1.0), ("우동", 0.9),
             ("돈카츠", 0.9), ("오마카세", 1.0), ("일식", 1.0), ("사시미", 0.9),
             ("규동", 0.8), ("가라아게", 0.8)],
    "양식": [("파스타", 1.0), ("스테이크", 1.0), ("피자", 0.9), ("버거", 0.9),
             ("양식", 1.0), ("브런치", 0.9), ("리조또", 0.8), ("샐러드", 0.7)],
    "중식": [("짜장면", 0.9), ("짬뽕", 0.9), ("마라", 1.0), ("중식", 1.0),
             ("딤섬", 0.9), ("탕수육", 0.8), ("마라탕", 1.0), ("훠궈", 0.9)],
    "분식": [("떡볶이", 1.0), ("순대", 0.9), ("튀김", 0.8), ("김밥", 0.9),
             ("분식", 1.0), ("라면", 0.7), ("핫도그", 0.8)],
    "고기": [("삼겹살", 1.0), ("갈비", 1.0), ("고기", 0.8), ("소고기", 0.9),
             ("돼지고기", 0.8), ("양꼬치", 0.9), ("야키니쿠", 0.9), ("곱창", 0.9)],
    "치킨": [("치킨", 1.0), ("닭", 0.8), ("후라이드", 0.9), ("양념치킨", 0.9),
             ("교촌", 0.7), ("bhc", 0.7), ("bbq", 0.7)],
}

# TF-IDF용 불용어
_STOPWORDS = {
    "이거", "저거", "그게", "인데", "이고", "있고", "하고", "인것", "같은",
    "정말", "진짜", "완전", "너무", "근데", "그냥", "되게", "엄청", "약간",
    "오늘", "어제", "내일", "지금", "여기", "저기", "거기", "이게", "그게",
    "있어", "없어", "했어", "한다", "하다", "이다", "에서", "에게", "으로",
}


def _tokenize(text: str) -> list[str]:
    """형태소 분석 (KoNLPy) 또는 regex fallback"""
    try:
        from konlpy.tag import Okt
        okt = Okt()
        nouns = okt.nouns(text)
        return [n for n in nouns if len(n) >= 2 and n not in _STOPWORDS]
    except Exception:
        # fallback: 한글 2글자 이상 추출
        tokens = re.findall(r"[가-힣]{2,}", text)
        return [t for t in tokens if t not in _STOPWORDS]


def _tfidf_keywords(text: str, top_n: int = 10) -> list[tuple[str, float]]:
    """
    단일 문서 TF-IDF 근사치 (IDF는 음식 도메인 사전 기반 역빈도 추정)
    - 짧은 자주 쓰이는 단어 → 낮은 IDF
    - 길고 특이한 단어 → 높은 IDF
    """
    tokens = _tokenize(text)
    if not tokens:
        return []

    tf: Counter = Counter(tokens)
    total = sum(tf.values())

    scored = []
    for token, count in tf.items():
        term_freq = count / total
        # 길이가 길수록 특이한 단어일 가능성 높음 → IDF 근사
        idf = log(1 + len(token) * 0.5)
        scored.append((token, round(term_freq * idf, 4)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def _score_moods(text: str) -> list[tuple[str, float]]:
    """분위기 키워드 스코어링 (가중치 합산)"""
    results = []
    for mood, keywords in MOOD_WORDS.items():
        score = sum(w for kw, w in keywords if kw in text)
        if score > 0:
            results.append((mood, round(score, 2)))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def _score_categories(text: str) -> list[tuple[str, float]]:
    """음식 카테고리 스코어링 (가중치 합산)"""
    results = []
    for cat, keywords in FOOD_CATEGORY.items():
        score = sum(w for kw, w in keywords if kw in text)
        if score > 0:
            results.append((cat, round(score, 2)))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def extract_info(script: str, food_type: str) -> dict:
    """
    대본 + 음식종류에서 핵심 정보 추출 (강화버전)

    반환:
        keywords      : TF-IDF 상위 키워드 리스트
        keyword_scores: {keyword: score} 딕셔너리
        location      : 감지된 장소 (없으면 None)
        moods         : 감지된 분위기 리스트 (스코어 높은 순)
        mood_scores   : {mood: score} 딕셔너리
        food_category : 최고 스코어 카테고리
        category_scores: [(cat, score), ...] 전체 카테고리 스코어
        food_type     : 입력 음식 종류 (정제)
    """
    text = script + " " + food_type

    # 1) 장소 감지 (첫 번째 매칭 + 스코어 높은 순)
    location_matches = [(w, text.count(w)) for w in LOCATION_WORDS if w in text]
    location_matches.sort(key=lambda x: x[1], reverse=True)
    location = location_matches[0][0] if location_matches else None

    # 2) 분위기 스코어링
    mood_scored = _score_moods(text)
    moods = [m for m, _ in mood_scored]
    mood_scores = {m: s for m, s in mood_scored}

    # 3) 카테고리 스코어링
    cat_scored = _score_categories(text)
    food_category = cat_scored[0][0] if cat_scored else "기타"

    # 4) TF-IDF 키워드 추출
    kw_scored = _tfidf_keywords(text, top_n=12)
    keywords = [kw for kw, _ in kw_scored]
    keyword_scores = {kw: s for kw, s in kw_scored}

    return {
        "keywords"       : keywords,
        "keyword_scores" : keyword_scores,
        "location"       : location,
        "moods"          : moods,
        "mood_scores"    : mood_scores,
        "food_category"  : food_category,
        "category_scores": cat_scored,
        "food_type"      : food_type.strip(),
    }
