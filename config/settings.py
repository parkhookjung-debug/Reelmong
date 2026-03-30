"""맛노래 프로젝트 설정 - 음식이 노래하는 숏폼 영상 생성"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent

# 데이터 경로
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"

# Vision 설정 (BLIP - 무료 로컬 모델)
BLIP_MODEL = "Salesforce/blip-image-captioning-large"
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}

# LLM 설정 (Ollama - 무료 로컬)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

# TTS 설정 (Edge TTS - 무료)
TTS_VOICE = "ko-KR-SunHiNeural"  # 밝고 친근한 여성 목소리
TTS_RATE = "+10%"  # 약간 빠르게 (노래 느낌)

# 영상 설정
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1080  # 1:1 정사각형 (인스타 피드용)
VIDEO_FPS = 30
VIDEO_DURATION_TARGET = 15  # 목표 영상 길이 (초)

# 카툰 얼굴 설정
FACE_EYE_SIZE = 60       # 눈 크기 (px)
FACE_MOUTH_SIZE = 50     # 입 크기 (px)
FACE_SCALE = 0.3         # 얼굴 크기 비율 (이미지 대비)

# 음식 카테고리별 노래 스타일
SONG_STYLES = {
    "한식": {"mood": "따뜻한 발라드", "tempo": "중간", "emotion": "정겨운"},
    "중식": {"mood": "활기찬 팝", "tempo": "빠른", "emotion": "신나는"},
    "일식": {"mood": "차분한 재즈", "tempo": "느린", "emotion": "우아한"},
    "양식": {"mood": "세련된 팝", "tempo": "중간", "emotion": "로맨틱한"},
    "카페": {"mood": "감성 어쿠스틱", "tempo": "느린", "emotion": "몽환적인"},
    "디저트": {"mood": "귀여운 팝", "tempo": "빠른", "emotion": "달콤한"},
    "치킨": {"mood": "신나는 힙합", "tempo": "빠른", "emotion": "흥겨운"},
    "피자": {"mood": "신나는 록", "tempo": "빠른", "emotion": "열정적인"},
    "분식": {"mood": "트로트 풍", "tempo": "중간", "emotion": "유쾌한"},
    "기타": {"mood": "밝은 팝", "tempo": "중간", "emotion": "즐거운"},
}
