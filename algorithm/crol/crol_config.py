import os
from dotenv import load_dotenv

# crol 패키지 루트 디렉토리 (이 파일이 있는 곳)
_CROL_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_CROL_DIR)

# 루트 .env → crol/.env 순서로 로드 (루트 OpenRouter 키 공유)
load_dotenv(os.path.join(_ROOT_DIR, ".env"))
load_dotenv(os.path.join(_CROL_DIR, ".env"))

# ── API 키 ────────────────────────────────────────────────────────
YOUTUBE_API_KEY      = os.getenv("YOUTUBE_API_KEY", "")
NAVER_CLIENT_ID      = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET  = os.getenv("NAVER_CLIENT_SECRET", "")
OPENROUTER_API_KEY   = os.getenv("OPENROUTER_API_KEY", "")

# ── 수집 설정 ─────────────────────────────────────────────────────
REGION_CODE           = "KR"
MAX_RESULTS_POPULAR   = 50
MAX_RESULTS_SEARCH    = 50
DB_PATH               = os.path.join(_CROL_DIR, "crol.db")
KEYWORDS_FILE         = os.path.join(_CROL_DIR, "keywords.json")  # 트렌드 키워드 저장 파일

# ── 고정 키워드 (항상 수집) ───────────────────────────────────────
# 음식 쇼츠 마케팅에서 기본이 되는 키워드
FIXED_KEYWORDS = [
    "먹방",
    "맛집",
    "맛집후기",
    "음식리뷰",
    "솔직후기",
    "신상맛집",
    "카페투어",
    "먹스타그램",
    "혼밥",
    "웨이팅맛집",
]

# ── 트렌드 후보 키워드 풀 (매주 검색량 체크 후 상위 10개 선별) ───
# 여기서 매주 유행하는 것만 골라 로테이션
TREND_KEYWORD_CANDIDATES = [
    # 장소 기반
    "성수맛집", "홍대맛집", "강남맛집", "연남동맛집", "망원맛집",
    "을지로맛집", "신촌맛집", "이태원맛집", "합정맛집", "건대맛집",
    "부산맛집", "제주맛집", "인천맛집", "수원맛집", "대전맛집",
    # 음식 종류
    "디저트", "브런치", "파스타맛집", "스시맛집", "라멘맛집",
    "떡볶이맛집", "고기맛집", "해산물맛집", "비건맛집", "샐러드맛집",
    "빵집", "베이커리카페", "신상카페", "루프탑카페", "감성카페",
    # 트렌드 포맷
    "핫플", "줄서는집", "인스타맛집", "가성비맛집", "데이트코스",
    "혼술", "야식", "새벽맛집", "24시맛집", "배달맛집",
    # 시즌/이슈성
    "봄카페", "여름음료", "빙수맛집", "겨울음식", "크리스마스카페",
    "오마카세", "뷔페맛집", "브런치카페", "팝업스토어", "콜라보카페",
]

# 매주 선별할 트렌드 키워드 수
TREND_KEYWORDS_COUNT = 10

# ── 스케줄 설정 ───────────────────────────────────────────────────
SCHEDULE_TIMES = ["09:00", "18:00", "23:00"]

# ── OpenRouter / LLM 설정 ─────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OLLAMA_MODEL        = "google/gemini-2.5-flash"  # 내부 호환 변수명 유지
OLLAMA_HOST         = OPENROUTER_BASE_URL        # 내부 호환 변수명 유지
OLLAMA_TIMEOUT      = 60
