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

# Vision 설정 (BLIP - 무료 로컬 모델)
BLIP_MODEL = "Salesforce/blip-image-captioning-large"
MAX_IMAGES = 10
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}

# LLM 설정 (Ollama - 무료 로컬)
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma3:4b"  # 가벼운 모델, 한국어 지원

# 영상 설정
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920  # 9:16 비율
VIDEO_DURATION_MIN = 15  # 초
VIDEO_DURATION_MAX = 30  # 초
VIDEO_FPS = 30

# 업종 카테고리
CATEGORIES = [
    "한식", "카페", "치킨", "피자", "분식",
    "중식", "일식", "양식", "베이커리", "기타"
]
