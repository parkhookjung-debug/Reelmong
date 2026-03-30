"""STEP 3: 음성 합성 (Edge TTS)

가사를 한국어 음성으로 변환합니다.
- Edge TTS (무료, API 키 불필요)
- 줄 단위 음성 생성 → 타이밍 정보 추출
- 노래 느낌을 위한 발화 속도/피치 조절
"""
import asyncio
import re
from pathlib import Path

import edge_tts
from pydub import AudioSegment

from config.settings import TTS_VOICE, TTS_RATE


class VoiceGenerator:
    """Edge TTS 기반 음성 합성 (노래 스타일)"""

    def __init__(self, voice: str = TTS_VOICE, rate: str = TTS_RATE):
        self.voice = voice
        self.rate = rate

    def _clean_text(self, text: str) -> str:
        """TTS에 불필요한 특수문자 제거"""
        text = re.sub(
            r"[^\uAC00-\uD7AF\u3130-\u318F\uA960-\uA97F"
            r"\u0020-\u007E"
            r"]+",
            " ",
            text,
        )
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
        )
        await communicate.save(output_path)
        return output_path

    def generate_line(self, text: str, output_path: str) -> str:
        """한 줄 가사 → MP3 음성 파일"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(self._generate_async(text, output_path))
        return output_path

    def generate_full_song(
        self,
        lyrics: list[str],
        output_dir: str,
        pause_ms: int = 400,
    ) -> dict:
        """전체 가사 → 줄별 음성 생성 + 합성

        Args:
            lyrics: 가사 줄 리스트
            output_dir: 출력 디렉토리
            pause_ms: 줄 사이 쉼표 길이 (ms)

        Returns:
            {
                "lines": [{"text": ..., "path": ..., "start_ms": ..., "duration_ms": ...}],
                "full_audio_path": ...,
                "total_duration_ms": ...,
            }
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        lines_info = []
        line_segments = []
        current_ms = 0

        # 1) 줄별 음성 생성
        for i, line in enumerate(lyrics):
            if not line.strip():
                continue

            line_path = str(Path(output_dir) / f"line_{i:02d}.mp3")
            print(f"    [TTS] {i + 1}/{len(lyrics)}: {line}")
            self.generate_line(line, line_path)

            # 길이 측정
            audio = AudioSegment.from_file(line_path)
            duration_ms = len(audio)

            lines_info.append({
                "text": line,
                "path": line_path,
                "start_ms": current_ms,
                "duration_ms": duration_ms,
                "line_index": i,
            })
            line_segments.append(audio)

            current_ms += duration_ms + pause_ms

        # 2) 전체 합성 (줄 사이에 pause 삽입)
        if not line_segments:
            raise ValueError("생성된 음성이 없습니다.")

        pause = AudioSegment.silent(duration=pause_ms)
        full_audio = line_segments[0]
        for seg in line_segments[1:]:
            full_audio = full_audio + pause + seg

        # 앞뒤 여백 추가
        intro_silence = AudioSegment.silent(duration=500)
        outro_silence = AudioSegment.silent(duration=1000)
        full_audio = intro_silence + full_audio + outro_silence

        # start_ms 보정 (intro 여백만큼)
        for info in lines_info:
            info["start_ms"] += 500

        full_path = str(Path(output_dir) / "full_voice.mp3")
        full_audio.export(full_path, format="mp3", bitrate="192k")

        total_duration_ms = len(full_audio)

        return {
            "lines": lines_info,
            "full_audio_path": full_path,
            "total_duration_ms": total_duration_ms,
        }
