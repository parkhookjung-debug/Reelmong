"""STEP 3 (보컬): Bark 기반 노래 보컬 생성 (Suno AI, 무료 로컬)

개선사항:
- 가사 레이블 자동 제거 (후렴:, 1절:, verse:, chorus: 등)
- 전체 가사를 한 번에 생성해서 끊김 최소화
- ♪ 기호로 노래 모드 활성화

설치:
    pip install git+https://github.com/suno-ai/bark.git

특징:
- 한국어 화자 프리셋 (v2/ko_speaker_0 ~ 9)
- GPU 권장, CPU에서도 동작 (느림)
- Bark 미설치/실패 시 Edge TTS 자동 fallback
"""
import re
from pathlib import Path

import numpy as np


# 제거할 레이블 패턴 (후렴:, 1절:, verse:, [chorus] 등)
_LABEL_PATTERN = re.compile(
    r"^\s*[\[\(]?\s*"
    r"(후렴|1절|2절|3절|브릿지|인트로|아웃트로|verse|chorus|bridge|intro|outro|hook|refrain)"
    r"\s*[\]\)]?\s*:?\s*",
    flags=re.IGNORECASE,
)

# Bark 한국어 화자 프리셋 (감정별)
_VOICE_PRESETS = {
    "즐거운":   "v2/ko_speaker_3",
    "신나는":   "v2/ko_speaker_5",
    "감성적인": "v2/ko_speaker_1",
    "귀여운":   "v2/ko_speaker_7",
    "열정적인": "v2/ko_speaker_4",
}
_DEFAULT_PRESET = "v2/ko_speaker_3"


def _clean_line(text: str) -> str:
    """레이블 제거 + 앞뒤 공백 정리"""
    text = _LABEL_PATTERN.sub("", text).strip()
    return text


def _wrap(text: str) -> str:
    """♪ 기호로 감싸 Bark 노래 모드 활성화"""
    if not text:
        return text
    if "♪" in text:
        return text
    return f"♪ {text} ♪"


def is_bark_available() -> bool:
    try:
        import bark  # noqa: F401
        return True
    except ImportError:
        return False


class BarkVocalGenerator:
    """Bark 기반 노래 보컬 생성기"""

    def __init__(self, emotion: str = "즐거운"):
        self.emotion = emotion
        self.voice_preset = _VOICE_PRESETS.get(emotion, _DEFAULT_PRESET)
        self._models_loaded = False

    def _load_models(self):
        if self._models_loaded:
            return
        print("[Bark] 모델 로딩 중... (최초 1회, 수분 소요)")
        from bark import preload_models
        preload_models()
        self._models_loaded = True
        print("[Bark] 모델 로딩 완료!")

    def _generate_audio(self, prompt: str) -> np.ndarray:
        """Bark 오디오 생성 (numpy float32)"""
        from bark import generate_audio
        return generate_audio(prompt, history_prompt=self.voice_preset)

    def generate_full_song(
        self,
        lyrics: list[str],
        output_dir: str,
        pause_ms: int = 300,
    ) -> dict:
        """전체 가사 → 보컬 생성 + 합성

        전략:
        1. 레이블(후렴:, 1절: 등) 제거
        2. 2줄씩 묶어서 생성 → 줄 사이 끊김 크게 줄어듦
        3. 개별 WAV 합산 → full_vocal.wav

        Returns:
            {lines, full_audio_path, total_duration_ms, engine}
        """
        import scipy.io.wavfile as wavfile
        from bark import SAMPLE_RATE
        from pydub import AudioSegment

        self._load_models()
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 1) 레이블 제거 + 빈 줄 걸러내기
        clean_lines = []
        for line in lyrics:
            cleaned = _clean_line(line)
            if cleaned:
                clean_lines.append(cleaned)

        if not clean_lines:
            raise ValueError("정제 후 가사가 비어있습니다.")

        print(f"    [Bark] 정제된 가사 {len(clean_lines)}줄:")
        for l in clean_lines:
            print(f"      ♪ {l} ♪")

        # 2) 2줄씩 묶어서 생성 (끊김 최소화)
        chunks = []
        for i in range(0, len(clean_lines), 2):
            group = clean_lines[i:i + 2]
            chunks.append(" ♪ ".join(group))

        line_segments = []
        line_meta = []
        current_ms = 0

        for idx, chunk in enumerate(chunks):
            prompt = _wrap(chunk)
            chunk_path = str(Path(output_dir) / f"bark_chunk_{idx:02d}.wav")
            print(f"    [Bark] {idx + 1}/{len(chunks)}: {prompt[:50]}...")

            audio_arr = self._generate_audio(prompt)
            audio_int16 = (audio_arr * 32767).clip(-32768, 32767).astype(np.int16)
            wavfile.write(chunk_path, SAMPLE_RATE, audio_int16)

            seg = AudioSegment.from_wav(chunk_path)
            duration_ms = len(seg)

            # 청크 안 줄들에 대해 타이밍 정보 생성 (균등 분배)
            n_lines = min(2, len(clean_lines) - idx * 2)
            per_line_ms = duration_ms // n_lines
            for j in range(n_lines):
                line_idx = idx * 2 + j
                line_meta.append({
                    "text": clean_lines[line_idx],
                    "path": chunk_path,
                    "start_ms": current_ms + j * per_line_ms,
                    "duration_ms": per_line_ms,
                    "line_index": line_idx,
                })

            line_segments.append(seg)
            current_ms += duration_ms + pause_ms

        # 3) 전체 합산
        pause = AudioSegment.silent(duration=pause_ms)
        full_audio = line_segments[0]
        for seg in line_segments[1:]:
            full_audio = full_audio + pause + seg

        intro = AudioSegment.silent(duration=300)
        outro = AudioSegment.silent(duration=800)
        full_audio = intro + full_audio + outro

        for info in line_meta:
            info["start_ms"] += 300

        full_path = str(Path(output_dir) / "full_vocal.wav")
        full_audio.export(full_path, format="wav")

        print(f"    [Bark] 완료 → {Path(full_path).name} ({len(full_audio)/1000:.1f}초)")

        return {
            "lines": line_meta,
            "full_audio_path": full_path,
            "total_duration_ms": len(full_audio),
            "engine": "bark",
        }
