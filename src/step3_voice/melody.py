"""멜로디 생성 모듈 - MusicGen (Meta, 무료 로컬)

음식 분위기에 맞는 배경 멜로디를 AI로 생성합니다.
- facebook/musicgen-small (~300MB, GPU 권장)
- 텍스트 프롬프트 → 멜로디 생성
- CPU에서도 동작 (느림)
"""
import numpy as np
from pathlib import Path

import torch
import scipy.io.wavfile as wavfile


# 음식 카테고리별 멜로디 프롬프트 (영어)
MELODY_PROMPTS = {
    "한식": "warm gentle Korean style acoustic melody, soft piano and traditional instruments, medium tempo, cheerful",
    "중식": "upbeat Chinese pop style melody, energetic, fun, bright synth and percussion",
    "일식": "calm elegant Japanese jazz melody, soft piano, smooth, relaxing",
    "양식": "romantic pop melody, acoustic guitar, warm, medium tempo, elegant",
    "카페": "lo-fi chill hop beat, acoustic guitar, dreamy, relaxing coffee shop music",
    "디저트": "cute bubbly pop melody, playful xylophone, sweet, happy, bouncy",
    "치킨": "fun upbeat hip hop beat, energetic drums, party vibe, exciting",
    "피자": "energetic rock melody, electric guitar, fun, exciting, fast tempo",
    "분식": "catchy Korean trot style melody, upbeat, playful accordion, fun retro",
    "기타": "happy upbeat pop melody, bright, cheerful, catchy, medium tempo",
}


class MelodyGenerator:
    """MusicGen 기반 AI 멜로디 생성"""

    def __init__(self):
        self.model = None
        self.processor = None
        self._loaded = False

    def _load_model(self):
        """MusicGen 모델 로딩 (최초 1회)"""
        if self._loaded:
            return

        print("[맛노래] MusicGen 모델 로딩 중... (최초 1회, 시간 소요)")
        try:
            from transformers import AutoProcessor, MusicgenForConditionalGeneration

            self.processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
            self.model = MusicgenForConditionalGeneration.from_pretrained(
                "facebook/musicgen-small"
            )

            # GPU 사용 가능하면 GPU로
            if torch.cuda.is_available():
                self.model = self.model.to("cuda")
                print("[맛노래] MusicGen GPU 모드")
            else:
                print("[맛노래] MusicGen CPU 모드 (느릴 수 있음)")

            self._loaded = True
            print("[맛노래] MusicGen 모델 로딩 완료!")

        except ImportError:
            print("[!] MusicGen 사용 불가 - transformers 버전을 확인하세요.")
            print("    pip install transformers torch")
            raise
        except Exception as e:
            print(f"[!] MusicGen 로딩 실패: {e}")
            raise

    def generate(
        self,
        category: str = "기타",
        duration_s: float = 15.0,
        output_path: str = "melody.wav",
        custom_prompt: str = "",
    ) -> str:
        """카테고리에 맞는 멜로디 생성

        Args:
            category: 음식 카테고리 (한식, 카페 등)
            duration_s: 멜로디 길이 (초)
            output_path: 출력 파일 경로
            custom_prompt: 커스텀 프롬프트 (빈값이면 카테고리 기반)

        Returns:
            생성된 WAV 파일 경로
        """
        self._load_model()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 프롬프트 결정
        prompt = custom_prompt or MELODY_PROMPTS.get(category, MELODY_PROMPTS["기타"])
        print(f"    [멜로디] 프롬프트: {prompt[:50]}...")

        # MusicGen은 최대 ~30초 생성 가능
        # max_new_tokens: 약 50 tokens = 1초 (32kHz sample rate 기준)
        tokens_per_second = 50
        max_tokens = int(duration_s * tokens_per_second)
        max_tokens = min(max_tokens, 1500)  # 최대 ~30초

        # 생성
        inputs = self.processor(
            text=[prompt],
            padding=True,
            return_tensors="pt",
        )

        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        print(f"    [멜로디] 생성 중... ({duration_s:.0f}초 분량)")
        with torch.no_grad():
            audio_values = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
            )

        # numpy로 변환
        audio_data = audio_values[0, 0].cpu().numpy()

        # 정규화
        audio_data = audio_data / np.max(np.abs(audio_data)) * 0.8

        # WAV 저장
        sample_rate = self.model.config.audio_encoder.sampling_rate
        audio_int16 = (audio_data * 32767).astype(np.int16)
        wavfile.write(output_path, sample_rate, audio_int16)

        print(f"    [멜로디] 저장: {Path(output_path).name}")
        return output_path


def is_musicgen_available() -> bool:
    """MusicGen 사용 가능 여부 확인"""
    try:
        from transformers import MusicgenForConditionalGeneration
        return True
    except ImportError:
        return False
