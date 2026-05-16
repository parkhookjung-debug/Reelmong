"""TTS 모듈 - Gemini TTS via OpenRouter

OpenRouter를 통해 Gemini TTS로 한국어 음성을 합성합니다.
- API 키 하나로 LLM + Vision + TTS 통합
- 고품질 한국어 음성 지원
"""
from pathlib import Path

from openai import OpenAI

from config.settings import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    TTS_MODEL,
    TTS_VOICE,
)


class TTSGenerator:
    """Gemini TTS (OpenRouter)를 사용한 한국어 음성 합성"""

    def __init__(self, voice: str = TTS_VOICE):
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
        self.voice = voice

    @classmethod
    def for_category(cls, category: str) -> "TTSGenerator":
        """업종에 맞는 설정으로 TTS 생성기 반환 (현재는 단일 보이스 사용)"""
        return cls(voice=TTS_VOICE)

    def generate(self, text: str, output_path: str) -> str:
        """나레이션 텍스트 → MP3 음성 파일 생성

        Args:
            text: 나레이션 텍스트
            output_path: 출력 MP3 파일 경로
        Returns:
            생성된 MP3 파일 경로
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with self.client.audio.speech.with_streaming_response.create(
            model=TTS_MODEL,
            input=text,
            voice=self.voice,
        ) as response:
            response.stream_to_file(output_path)

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
