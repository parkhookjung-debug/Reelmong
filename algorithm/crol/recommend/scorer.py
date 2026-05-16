"""
바이럴 잠재력 점수 모듈 (신규)

제목·후킹멘트의 바이럴 가능성을 다차원 점수로 계산합니다.

점수 구성:
  - 길이 점수    : 15~25자가 최적 (너무 짧거나 길면 감점)
  - 후킹 점수    : 질문형/반전형/감탄형 키워드 감지
  - 숫자 점수    : 숫자 포함 시 클릭률↑ (연구 기반)
  - 음식 점수    : 음식 관련 감각어 포함 여부
  - 긴급성 점수  : "지금", "오늘", "한정", "품절" 등
  - 패턴 점수    : 성공한 쇼츠 제목 패턴 일치도
"""
import re
from dataclasses import dataclass, field


# ── 후킹 패턴 (점수 가중치) ──────────────────────────────────────────
_HOOK_PATTERNS: list[tuple[re.Pattern, float, str]] = [
    # (패턴, 점수, 설명)
    (re.compile(r"(실화|실화임|실화야|실화인가)"), 1.0, "실화형"),
    (re.compile(r"(미쳤|미친|미쳐|ㅁㅊ)"), 0.9, "감탄형"),
    (re.compile(r"(레전드|레전|ㄹㅈㄷ)"), 0.85, "레전드형"),
    (re.compile(r"(반칙|말이 돼|말이돼|가능해|된다고)"), 0.9, "반전형"),
    (re.compile(r"(이거|여기|이 집|이집).{0,5}(봐|봐봐|봐라|보세요|보지마)"), 0.8, "지시형"),
    (re.compile(r"(숨겨|공개|찾았|발굴|발견)"), 0.85, "발견형"),
    (re.compile(r"(손해|안 하면|안하면|놓치면|후회)"), 0.8, "손해회피형"),
    (re.compile(r"\?"), 0.6, "질문형"),
    (re.compile(r"(대박|짱|완전|진짜).{0,3}(맛|맛있|맛남|맛집)"), 0.75, "감탄맛형"),
    (re.compile(r"TOP\s*\d|1등|1위|\d+위"), 0.7, "랭킹형"),
]

# ── 음식 감각어 ────────────────────────────────────────────────────────
_FOOD_SENSORY = [
    "바삭", "쫄깃", "촉촉", "육즙", "고소", "달콤", "짭짤", "매콤", "담백",
    "부드럽", "쫀득", "겉바속촉", "크리스피", "녹는", "살살", "향긋",
]

# ── 긴급성/희소성 키워드 ──────────────────────────────────────────────
_URGENCY = ["지금", "오늘", "한정", "품절", "마지막", "곧", "시즌", "시간"]

# ── 성공 쇼츠 제목 구조 패턴 ──────────────────────────────────────────
_SUCCESS_PATTERNS = [
    r"\d+",                         # 숫자 포함
    r"[가-힣]+에서\s+[가-힣]+",      # 장소 + 음식
    r"(이 가격에|이 맛에|이 퀄리티)",  # 가성비 강조
    r"(웨이팅|오픈런|예약)\s*\d*",   # 인기 지표
    r"(솔직|솔직히|찐후기|진짜후기)",  # 진정성
]


@dataclass
class ViralScore:
    title: str
    total: float = 0.0
    length_score: float = 0.0
    hook_score: float = 0.0
    number_score: float = 0.0
    food_score: float = 0.0
    urgency_score: float = 0.0
    pattern_score: float = 0.0
    matched_hooks: list[str] = field(default_factory=list)

    def __str__(self):
        return (
            f"[{self.total:.2f}] {self.title}\n"
            f"  길이:{self.length_score:.2f} 후킹:{self.hook_score:.2f} "
            f"숫자:{self.number_score:.2f} 음식:{self.food_score:.2f} "
            f"긴급:{self.urgency_score:.2f} 패턴:{self.pattern_score:.2f}"
        )


def score_title(title: str) -> ViralScore:
    """제목 하나의 바이럴 잠재력 점수 계산"""
    vs = ViralScore(title=title)
    text = title.strip()
    length = len(text)

    # 1) 길이 점수 (15~25자 최적)
    if 15 <= length <= 25:
        vs.length_score = 1.0
    elif 10 <= length < 15:
        vs.length_score = 0.7
    elif 25 < length <= 35:
        vs.length_score = 0.7
    elif length < 10:
        vs.length_score = 0.3
    else:
        vs.length_score = 0.4

    # 2) 후킹 키워드 점수
    hook_total = 0.0
    for pattern, weight, name in _HOOK_PATTERNS:
        if pattern.search(text):
            hook_total += weight
            vs.matched_hooks.append(name)
    vs.hook_score = min(hook_total, 2.0) / 2.0  # 최대 1.0 정규화

    # 3) 숫자 포함 여부
    numbers = re.findall(r"\d+", text)
    if numbers:
        vs.number_score = 0.8 if len(numbers) == 1 else 0.6
    else:
        vs.number_score = 0.0

    # 4) 음식 감각어 점수
    sensory_matches = [s for s in _FOOD_SENSORY if s in text]
    vs.food_score = min(len(sensory_matches) * 0.4, 1.0)

    # 5) 긴급성/희소성 점수
    urgency_matches = [u for u in _URGENCY if u in text]
    vs.urgency_score = min(len(urgency_matches) * 0.5, 1.0)

    # 6) 성공 패턴 매칭
    pattern_hits = sum(1 for p in _SUCCESS_PATTERNS if re.search(p, text))
    vs.pattern_score = min(pattern_hits * 0.3, 1.0)

    # 종합 점수 (가중 평균)
    vs.total = round(
        vs.length_score  * 0.15 +
        vs.hook_score    * 0.35 +
        vs.number_score  * 0.15 +
        vs.food_score    * 0.15 +
        vs.urgency_score * 0.10 +
        vs.pattern_score * 0.10,
        3
    )

    return vs


def rank_titles(titles: list[str]) -> list[ViralScore]:
    """제목 목록 → 바이럴 점수 순 정렬"""
    scores = [score_title(t) for t in titles]
    scores.sort(key=lambda x: x.total, reverse=True)
    return scores


def score_hook_candidates(candidates: list[str]) -> list[tuple[str, float]]:
    """
    후킹 멘트 후보 → 점수 순 정렬
    반환: [(멘트, 점수), ...] 높은 점수 순
    """
    scored = [(c, score_title(c).total) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def pick_best_hook(candidates: list[str], top_k: int = 3) -> str:
    """
    후킹 멘트 후보에서 최고 점수 중 상위 k개 안에서 랜덤 선택
    (완전 랜덤 대신 상위 중 약간의 다양성 확보)
    """
    import random
    if not candidates:
        return ""
    scored = score_hook_candidates(candidates)
    top = scored[:min(top_k, len(scored))]
    chosen, chosen_score = random.choice(top)
    return chosen


# ── C: 유사 제목 중복 억제 ─────────────────────────────────────────────

def _jaccard(a: str, b: str) -> float:
    """토큰 Jaccard 유사도 (한글/영숫자 2자 이상 기준)"""
    ta = set(re.findall(r"[가-힣a-zA-Z0-9]{2,}", a))
    tb = set(re.findall(r"[가-힣a-zA-Z0-9]{2,}", b))
    union = ta | tb
    return len(ta & tb) / len(union) if union else 1.0


def deduplicate_titles(
    scored: list[ViralScore],
    threshold: float = 0.55,
) -> list[ViralScore]:
    """
    C: 유사 제목 중복 억제
    scored는 바이럴 점수 내림차순 정렬 상태여야 함.
    Jaccard 유사도 >= threshold 이면 점수 낮은 쪽(나중에 나온 쪽) 제거.
    """
    kept: list[ViralScore] = []
    for vs in scored:
        if all(_jaccard(vs.title, k.title) < threshold for k in kept):
            kept.append(vs)
    return kept


# ── D: 실제 DB 데이터 기반 가중치 보정 ────────────────────────────────

def calibrate_from_db(db_path: str) -> dict[str, float]:
    """
    D: DB 고/저 engagement 영상 제목 비교 → 패턴별 multiplier 계산

    고engagement(상위 20%) 제목에 자주 등장하는 패턴 → multiplier > 1.0
    저engagement(하위 20%) 제목에 자주 등장하는 패턴 → multiplier < 1.0

    DB 데이터 부족(< 20개) 시 모두 1.0 반환.
    """
    import sqlite3

    multipliers: dict[str, float] = {name: 1.0 for _, _, name in _HOOK_PATTERNS}
    try:
        conn = sqlite3.connect(db_path)
        cur  = conn.cursor()
        cur.execute("""
            SELECT title,
                   (CAST(like_count AS REAL) + CAST(comment_count AS REAL) * 2)
                   / (CAST(view_count AS REAL) + 1) AS eng
            FROM videos
            WHERE is_short = 1
              AND view_count > 500
            ORDER BY eng DESC
        """)
        rows = cur.fetchall()
        conn.close()

        if len(rows) < 20:
            return multipliers

        cut    = max(len(rows) // 5, 10)
        high_t = [r[0] for r in rows[:cut]  if r[0]]
        low_t  = [r[0] for r in rows[-cut:] if r[0]]

        adjusted = 0
        for pattern, _, name in _HOOK_PATTERNS:
            hr = sum(1 for t in high_t if pattern.search(t)) / len(high_t)
            lr = sum(1 for t in low_t  if pattern.search(t)) / len(low_t)
            m  = round(min(max((hr + 0.01) / (lr + 0.01), 0.5), 2.0), 3)
            multipliers[name] = m
            if m != 1.0:
                adjusted += 1

        print(f"[scorer] D: {len(rows)}개 영상 분석 → {adjusted}개 패턴 가중치 보정 완료")

    except Exception as e:
        print(f"[scorer] D: 보정 실패 ({e}), 기본 가중치 사용")

    return multipliers


def apply_calibration(
    scored: list[ViralScore],
    multipliers: dict[str, float],
) -> list[ViralScore]:
    """
    D: calibrate_from_db() 결과를 ViralScore에 적용 후 재정렬.
    matched_hooks에 있는 패턴들의 multiplier 평균으로 total 보정.
    """
    for vs in scored:
        if vs.matched_hooks:
            boost = sum(multipliers.get(h, 1.0) for h in vs.matched_hooks) / len(vs.matched_hooks)
            vs.total = round(min(vs.total * boost, 1.0), 3)
    scored.sort(key=lambda x: x.total, reverse=True)
    return scored
