"""오디오 믹서 - TTS 음성 + 멜로디 합성

TTS 목소리와 MusicGen 멜로디를 믹싱하여
음식이 멜로디 위에서 노래하는 느낌을 만듭니다.
- 멜로디는 배경으로 깔리고
- TTS 목소리가 그 위에 올라감
- 목소리 나올 때 멜로디 볼륨 살짝 낮춤 (ducking)
"""
from pathlib import Path

from pydub import AudioSegment
from pydub.effects import normalize


class AudioMixer:
    """TTS + 멜로디 믹싱"""

    def __init__(self):
        self.melody_volume_db = -10    # 멜로디 볼륨 (목소리보다 낮게)
        self.melody_duck_db = -16      # 목소리 나올 때 멜로디 볼륨
        self.voice_volume_db = 3       # 목소리 볼륨 (약간 부스트)
        self.fade_in_ms = 500
        self.fade_out_ms = 1500

    def mix(
        self,
        voice_path: str,
        melody_path: str | None,
        output_path: str,
        voice_lines: list[dict] | None = None,
    ) -> str:
        """TTS 음성 + 멜로디 → 최종 오디오

        Args:
            voice_path: TTS 전체 음성 파일
            melody_path: 멜로디 파일 (None이면 음성만)
            output_path: 출력 경로
            voice_lines: 목소리 구간 정보 (ducking용)
                [{"start_ms": 0, "duration_ms": 3000}, ...]
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 목소리 로드
        voice = AudioSegment.from_file(voice_path)
        voice = voice + self.voice_volume_db
        total_ms = len(voice)

        if not melody_path or not Path(melody_path).exists():
            # 멜로디 없으면 목소리만
            voice = normalize(voice)
            voice.export(output_path, format="mp3", bitrate="192k")
            return output_path

        # 멜로디 로드 + 길이 맞추기
        melody = AudioSegment.from_file(melody_path)
        melody = melody + self.melody_volume_db

        # 멜로디가 짧으면 루프
        if len(melody) < total_ms:
            loops = (total_ms // len(melody)) + 1
            melody = melody * loops
        melody = melody[:total_ms]

        # 페이드
        melody = melody.fade_in(self.fade_in_ms).fade_out(self.fade_out_ms)

        # 목소리 구간에서 멜로디 ducking
        if voice_lines:
            melody = self._apply_ducking(melody, voice_lines)

        # 합성
        mixed = melody.overlay(voice)
        mixed = normalize(mixed)
        mixed.export(output_path, format="mp3", bitrate="192k")

        return output_path

    def _apply_ducking(
        self, melody: AudioSegment, voice_lines: list[dict]
    ) -> AudioSegment:
        """목소리 구간에서 멜로디 볼륨 낮추기"""
        duck_amount = self.melody_duck_db - self.melody_volume_db

        for line in voice_lines:
            start = max(0, int(line.get("start_ms", 0)))
            duration = int(line.get("duration_ms", 0))
            end = min(len(melody), start + duration)

            if start >= end:
                continue

            before = melody[:start]
            during = melody[start:end] + duck_amount
            after = melody[end:]
            melody = before + during + after

        return melody
