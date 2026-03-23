"""오디오 믹서 - TTS 나레이션 + BGM 합성

장면별 TTS 음성과 BGM을 믹싱하여 최종 오디오 트랙을 생성합니다.
- 장면별 TTS를 타이밍에 맞게 배치
- BGM을 영상 길이에 맞게 루프/페이드
- 나레이션이 나올 때 BGM 볼륨 자동 조절 (ducking)
"""
from pathlib import Path

from pydub import AudioSegment
from pydub.effects import normalize


class AudioMixer:
    """TTS 나레이션 + BGM 믹싱"""

    def __init__(self):
        self.bgm_volume_db = -18       # BGM 기본 볼륨 (나레이션 대비 낮게)
        self.bgm_duck_db = -25         # 나레이션 중 BGM 볼륨 (더 낮게)
        self.narration_volume_db = 0   # 나레이션 볼륨
        self.fade_in_ms = 1000         # BGM 페이드인 (ms)
        self.fade_out_ms = 2000        # BGM 페이드아웃 (ms)

    def mix(
        self,
        scene_audio_paths: list[dict],
        bgm_path: str | None,
        total_duration_ms: int,
        output_path: str,
    ) -> str:
        """장면별 TTS + BGM → 최종 오디오 파일

        Args:
            scene_audio_paths: [{"path": "mp3경로", "start_ms": 0, "duration_ms": 5000}, ...]
            bgm_path: BGM 파일 경로 (None이면 BGM 없이)
            total_duration_ms: 전체 영상 길이 (밀리초)
            output_path: 출력 파일 경로
        Returns:
            생성된 오디오 파일 경로
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 1) 빈 캔버스 생성
        canvas = AudioSegment.silent(duration=total_duration_ms)

        # 2) 장면별 나레이션 배치
        narration_regions = []  # BGM ducking용 나레이션 구간 기록

        for scene in scene_audio_paths:
            audio_path = scene.get("path", "")
            start_ms = int(scene.get("start_ms", 0))

            if not audio_path or not Path(audio_path).exists():
                continue

            tts_audio = AudioSegment.from_file(audio_path)
            tts_audio = tts_audio + self.narration_volume_db

            # 나레이션이 장면보다 길면 잘라내기
            scene_duration_ms = int(scene.get("duration_ms", len(tts_audio)))
            if len(tts_audio) > scene_duration_ms:
                tts_audio = tts_audio[:scene_duration_ms]

            canvas = canvas.overlay(tts_audio, position=start_ms)
            narration_regions.append((start_ms, start_ms + len(tts_audio)))

        # 3) BGM 처리
        if bgm_path and Path(bgm_path).exists():
            bgm = self._prepare_bgm(bgm_path, total_duration_ms)

            # BGM ducking: 나레이션 구간에서 BGM 볼륨 더 낮추기
            bgm = self._apply_ducking(bgm, narration_regions)

            canvas = canvas.overlay(bgm)

        # 4) 정규화 및 저장
        canvas = normalize(canvas)
        canvas.export(output_path, format="mp3", bitrate="192k")

        return output_path

    def _prepare_bgm(self, bgm_path: str, target_duration_ms: int) -> AudioSegment:
        """BGM을 영상 길이에 맞게 준비 (루프 + 페이드)"""
        bgm = AudioSegment.from_file(bgm_path)
        bgm = bgm + self.bgm_volume_db

        # BGM이 짧으면 루프
        if len(bgm) < target_duration_ms:
            loops_needed = (target_duration_ms // len(bgm)) + 1
            bgm = bgm * loops_needed

        # 길이 맞추기
        bgm = bgm[:target_duration_ms]

        # 페이드인/아웃
        bgm = bgm.fade_in(self.fade_in_ms).fade_out(self.fade_out_ms)

        return bgm

    def _apply_ducking(
        self, bgm: AudioSegment, narration_regions: list[tuple]
    ) -> AudioSegment:
        """나레이션 구간에서 BGM 볼륨 낮추기 (ducking)"""
        if not narration_regions:
            return bgm

        duck_amount = self.bgm_duck_db - self.bgm_volume_db  # 추가로 낮출 dB

        for start_ms, end_ms in narration_regions:
            start_ms = max(0, start_ms)
            end_ms = min(len(bgm), end_ms)

            if start_ms >= end_ms:
                continue

            # 구간 분리 → 볼륨 조절 → 재결합
            before = bgm[:start_ms]
            during = bgm[start_ms:end_ms] + duck_amount
            after = bgm[end_ms:]
            bgm = before + during + after

        return bgm

    def mix_simple(
        self,
        narration_path: str,
        bgm_path: str | None,
        output_path: str,
    ) -> str:
        """간단 믹싱: 전체 나레이션 1파일 + BGM → 출력

        Args:
            narration_path: 전체 나레이션 MP3
            bgm_path: BGM 파일 (None 가능)
            output_path: 출력 경로
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        narration = AudioSegment.from_file(narration_path)
        narration = normalize(narration)

        total_ms = len(narration) + 2000  # 나레이션 + 2초 여유

        if bgm_path and Path(bgm_path).exists():
            bgm = self._prepare_bgm(bgm_path, total_ms)
            # 전체에 ducking 적용
            bgm = bgm + (self.bgm_duck_db - self.bgm_volume_db)
            canvas = bgm.overlay(narration, position=500)  # 0.5초 후 나레이션 시작
        else:
            canvas = AudioSegment.silent(duration=500) + narration

        canvas = normalize(canvas)
        canvas.export(output_path, format="mp3", bitrate="192k")
        return output_path
