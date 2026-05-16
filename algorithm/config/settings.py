"""릴몽 프로젝트 설정"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent

# 데이터 경로
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
OUTPUT_DIR = DATA_DIR / "output"

# OpenRouter 설정
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# 모델 설정
LLM_MODEL    = "google/gemini-2.5-flash"   # 대본 생성, 이미지 요약
VISION_MODEL = "google/gemini-2.5-flash"   # 이미지 분석 (Vision 내장)
TTS_MODEL    = "google/gemini-3.1-flash-tts-preview"  # 한국어 음성 합성
TTS_VOICE    = "alloy"                     # OpenRouter 기본 보이스

# 영상 설정
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920  # 9:16 비율
VIDEO_DURATION_MIN = 15  # 초
VIDEO_DURATION_MAX = 30  # 초
VIDEO_FPS = 30

MAX_IMAGES = 10
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}

# 업종 카테고리
CATEGORIES = [
    "한식", "카페", "치킨", "피자", "분식",
    "중식", "일식", "양식", "베이커리", "기타"
]
