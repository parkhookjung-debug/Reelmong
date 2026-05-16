"""
음식 쇼츠 제목 템플릿 모음
실제 유튜브 음식 쇼츠 패턴을 타입별로 정리
"""
import random

# ── 템플릿 정의 ──────────────────────────────────────────────────────

TEMPLATES = {

    # 후킹형: 첫 1초에 시선 잡는 제목
    "hook": [
        "이거 보면 지금 당장 가고싶어짐",
        "{food} 이 집 숨겨놓고 싶었는데 공개함",
        "진짜 반칙이다... {food}",
        "여기 안가봤으면 진짜 손해",
        "이 맛 알면 다이어트 포기각",
        "솔직히 이건 좀 말이 안 됨 {food}",
        "{food} 보는 순간 참을 수가 없음",
        "이게 된다고? {food} 실화임",
    ],

    # 장소형: 지역 + 음식 조합
    "location": [
        "{location} {food} 찐맛집 여기였음",
        "{location} 웨이팅 {n}시간인데 이해됨",
        "{location}에서 제일 핫한 {food} 찾음",
        "{location} 숨은 {food} 맛집 발굴함",
        "서울 {food} 맛집 여기가 진짜 TOP임",
        "{location} {food} 안 가봤으면 손해",
        "{location}까지 {food} 먹으러 간 이유",
    ],

    # 솔직형: 진정성 있는 리뷰 느낌
    "honest": [
        "솔직히 {food} 여기가 제일 맛있음 (찐후기)",
        "유명하길래 가봤는데 {food} 진짜였음",
        "{food} 솔직 후기 (실망한 부분도 말함)",
        "인플루언서 다 가는 {food} 직접 먹어봄",
        "{food} 광고 아님 진짜 맛있어서 올림",
        "줄 서서 먹는 {food} 진짜 그만한 이유",
        "{food} 먹어보고 솔직하게 말함",
    ],

    # 반전형: 예상 뒤집기
    "twist": [
        "망했다고 생각했는데 {food} 인생맛집이었음",
        "기대 안 했다가 {food} 완전 반함",
        "처음엔 별로였는데 다 먹고나니 {food} 또 생각남",
        "{food} 비싸서 망설였는데 이건 진짜 가치있음",
        "웨이팅 포기할뻔 했는데 {food} 기다린 보람 있음",
        "외관은 별로인데 {food} 맛은 레전드",
    ],

    # 숫자형: 리스트, 랭킹
    "number": [
        "{location} {food} TOP {n} | 줄서도 후회없는 곳",
        "{food} 맛집 {n}곳 다 가봤는데 여기가 1등",
        "이 가격에 이 맛? {food} {n}번 재방문한 이유",
        "{food} {n}군데 비교해봤는데 진짜 여기 최고",
        "혼밥 {food} 추천 TOP {n}",
    ],

    # 공감형: 상황 공감
    "empathy": [
        "혼밥러들 {food} 여기 가봐야 함",
        "{food} 먹고싶은데 같이 갈 사람 없을 때",
        "데이트 코스 고민이면 {food} 여기 무조건",
        "야근하고 먹는 {food} 이 맛이 진짜임",
        "{food} 좋아하는 사람이라면 공감할 영상",
        "주말에 뭐 먹지 고민될 때 보는 {food} 영상",
    ],

    # 시즌/트렌드형
    "trend": [
        "요즘 {food} 이게 대세임",
        "지금 {location} 난리난 {food}",
        "SNS에서 핫한 {food} 직접 가봄",
        "요즘 사람들이 {food} 여기만 가는 이유",
        "2025 {food} 트렌드 총정리",
        "{food} 최신 핫플 다 정리함",
    ],

    # 식욕자극형
    "appetite": [
        "{food} 이 비주얼에 참을 수 있냐고",
        "이 {food} 보면 배고파짐 주의",
        "{food} 단면 보는 순간 침 고임",
        "바삭한 소리 들어봐 {food} 진짜임",
        "{food} 육즙이 이 정도면 반칙",
    ],
}

LOCATIONS = ["성수", "홍대", "강남", "연남동", "망원", "을지로", "신촌", "이태원", "합정"]
NUMBERS   = [3, 5, 7, 10]


def generate_template_titles(food_type: str, location: str | None = None,
                              count: int = 8) -> list[dict]:
    """
    템플릿 기반 제목 생성
    반환: [{"title": str, "type": str}, ...]
    """
    loc   = location or random.choice(LOCATIONS)
    n     = random.choice(NUMBERS)
    results = []

    # 타입별로 최소 1개씩, 총 count개
    all_types = list(TEMPLATES.keys())
    selected  = []

    # 랜덤하게 count개 타입 선택 (중복 허용)
    for i in range(count):
        t_type    = all_types[i % len(all_types)]
        template  = random.choice(TEMPLATES[t_type])
        title     = template.format(
            food=food_type,
            location=loc,
            n=n,
        )
        selected.append({"title": title, "type": t_type})

    return selected
