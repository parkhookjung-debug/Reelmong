"""STEP 4-B: 립싱크 애니메이션 (오디오 진폭 기반)

오디오 파형을 분석하여 프레임별 입 열림 정도를 계산합니다.
- 음성이 나올 때 → 입이 열림
- 음성이 없을 때 → 입이 닫힘
- 진폭에 비례하여 입 크기 변화
"""
import numpy as np
from pydub import AudioSegment


class LipSyncAnimator:
    """오디오 진폭 기반 립싱크 데이터 생성"""

    def __init__(self, fps: int = 30):
        self.fps = fps

    def analyze_audio(self, audio_path: str) -> list[float]:
        """오디오 파일 → 프레임별 입 열림 정도 (0.0 ~ 1.0)

        Args:
            audio_path: 음성 파일 경로

        Returns:
            프레임별 openness 리스트 (길이 = 총 프레임 수)
        """
        audio = AudioSegment.from_file(audio_path)
        duration_s = len(audio) / 1000.0
        total_frames = int(duration_s * self.fps)

        if total_frames == 0:
            return []

        # 오디오 → numpy array
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

        # 스테레오 → 모노
        if audio.channels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)

        # 프레임당 샘플 수
        samples_per_frame = len(samples) / total_frames

        # 프레임별 RMS(진폭) 계산
        rms_values = []
        for i in range(total_frames):
            start = int(i * samples_per_frame)
            end = int((i + 1) * samples_per_frame)
            end = min(end, len(samples))

            if start >= end:
                rms_values.append(0.0)
                continue

            chunk = samples[start:end]
            rms = np.sqrt(np.mean(chunk ** 2))
            rms_values.append(float(rms))

        # 정규화 (0.0 ~ 1.0)
        max_rms = max(rms_values) if rms_values else 1.0
        if max_rms < 1e-6:
            return [0.0] * total_frames

        openness = []
        for rms in rms_values:
            normalized = rms / max_rms

            # 임계값 적용: 너무 작은 소리는 입 닫기
            if normalized < 0.05:
                openness.append(0.0)
            else:
                # 약간의 비선형 매핑 (입이 너무 크게 안 벌어지게)
                value = min(1.0, normalized * 1.2)
                # 부드럽게 (제곱근)
                value = value ** 0.7
                openness.append(round(value, 3))

        # 스무딩 (급격한 변화 완화)
        openness = self._smooth(openness, window=3)

        return openness

    def _smooth(self, values: list[float], window: int = 3) -> list[float]:
        """이동 평균 스무딩"""
        if len(values) <= window:
            return values

        result = []
        half = window // 2

        for i in range(len(values)):
            start = max(0, i - half)
            end = min(len(values), i + half + 1)
            avg = sum(values[start:end]) / (end - start)
            result.append(round(avg, 3))

        return result

    def get_timing_info(self, openness: list[float]) -> dict:
        """립싱크 통계 정보"""
        if not openness:
            return {"total_frames": 0, "singing_frames": 0, "silent_frames": 0}

        singing = sum(1 for v in openness if v > 0.05)
        silent = len(openness) - singing

        return {
            "total_frames": len(openness),
            "singing_frames": singing,
            "silent_frames": silent,
            "singing_ratio": round(singing / len(openness), 2),
            "duration_s": round(len(openness) / self.fps, 1),
        }
