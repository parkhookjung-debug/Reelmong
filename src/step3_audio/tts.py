"""TTS 모듈 - Edge TTS (무료 한국어 음성 합성)

Microsoft Edge TTS를 사용하여 나레이션 텍스트를 한국어 음성으로 변환합니다.
- 무료, API 키 불필요
- 고품질 한국어 음성 지원
- 다양한 음성 선택 가능
"""
import asyncio
import re
from pathlib import Path

import edge_tts


# 한국어 음성 목록 (용도별 추천)
KOREAN_VOICES = {
    "female_friendly": "ko-KR-SunHiNeural",     # 여성, 밝고 친근 (기본)
    "male_friendly": "ko-KR-InJoonNeural",       # 남성, 친근
    "female_calm": "ko-KR-SunHiNeural",          # 여성, 차분
    "male_calm": "ko-KR-InJoonNeural",           # 남성, 차분
}

# 업종별 추천 음성
CATEGORY_VOICE_MAP = {
    "한식": "female_friendly",
    "카페": "female_friendly",
    "치킨": "male_friendly",
    "피자": "male_friendly",
    "분식": "female_friendly",
    "중식": "male_friendly",
    "일식": "female_calm",
    "양식": "female_friendly",
    "베이커리": "female_friendly",
    "마라탕": "female_friendly",
    "기타": "female_friendly",
}


class TTSGenerator:
    """Edge TTS를 사용한 한국어 음성 합성"""

    def __init__(self, voice_key: str = "female_friendly"):
        self.voice = KOREAN_VOICES.get(voice_key, KOREAN_VOICES["female_friendly"])
        self.rate = "+0%"    # 발화 속도 (기본)
        self.volume = "+0%"  # 볼륨 (기본)

    @classmethod
    def for_category(cls, category: str) -> "TTSGenerator":
        """업종에 맞는 음성으로 TTS 생성기 반환"""
        voice_key = CATEGORY_VOICE_MAP.get(category, "female_friendly")
        return cls(voice_key=voice_key)

    def set_speed(self, rate: str):
        """발화 속도 설정 (예: '+10%', '-5%')"""
        self.rate = rate

    def _clean_text(self, text: str) -> str:
        """TTS에 불필요한 이모지/특수문자 제거"""
        # 한글, 영문, 숫자, 기본 문장부호만 남기고 전부 제거
        text = re.sub(
            r"[^\uAC00-\uD7AF\u3130-\u318F\uA960-\uA97F"
            r"\u0020-\u007E"  # ASCII (영문, 숫자, 기본 문장부호)
            r"]+",
            " ",
            text,
        )
        # 연속 공백 정리
        text = re.sub(r"\s+", " ", text).strip()
        return text

    async def _generate_async(self, text: str, output_path: str) -> str:
        """비동기 TTS 생성"""
        clean_text = self._clean_text(text)
        if not clean_text:
            raise ValueError("TTS 변환할 텍스트가 비어있습니다.")

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
        )
        await communicate.save(output_path)
        return output_path

    def generate(self, text: str, output_path: str) -> str:
        """나레이션 텍스트 → MP3 음성 파일 생성

        Args:
            text: 나레이션 텍스트
            output_path: 출력 MP3 파일 경로
        Returns:
            생성된 MP3 파일 경로
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(self._generate_async(text, output_path))
        return output_path

    def generate_per_scene(
        self, scenes: list[dict], output_dir: str
    ) -> list[str]:
        """장면별 나레이션 개별 생성

        Args:
            scenes: [{"narration": "텍스트", "scene_index": 1}, ...]
            output_dir: 출력 디렉토리
        Returns:
            생성된 MP3 파일 경로 리스트
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        paths = []

        for scene in scenes:
            narration = scene.get("narration", "")
            idx = scene.get("scene_index", 0)
            if not narration.strip():
                continue

            out_path = str(Path(output_dir) / f"scene_{idx:02d}.mp3")
            print(f"    [TTS] 장면 {idx} 음성 생성 중...")
            self.generate(narration, out_path)
            paths.append(out_path)

        return paths
