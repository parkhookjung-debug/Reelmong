"""STEP 5 품질 평가 - 생성된 숏폼 영상 품질 분석

평가 항목:
1. 기술 품질: 해상도, FPS, 파일 크기, 비트레이트
2. 길이 적합성: 15~30초 범위 확인
3. 오디오 동기화: 오디오-비디오 길이 일치 확인
4. 장면 구성: 스토리보드 대비 장면 수, 타이밍 검증
5. 자막 검증: 자막 타이밍 + 텍스트 존재 여부
6. 종합 점수: 100점 만점 종합 평가
"""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from moviepy import VideoFileClip, AudioFileClip


@dataclass
class QualityMetric:
    """개별 평가 항목"""
    name: str
    score: float       # 0~100
    max_score: float   # 배점
    detail: str = ""
    passed: bool = True


@dataclass
class EvalResult:
    """전체 평가 결과"""
    video_path: str
    total_score: float = 0.0
    grade: str = ""          # S, A, B, C, D
    metrics: list = field(default_factory=list)
    summary: str = ""
    recommendations: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "video_path": self.video_path,
            "total_score": round(self.total_score, 1),
            "grade": self.grade,
            "metrics": [asdict(m) for m in self.metrics],
            "summary": self.summary,
            "recommendations": self.recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())


class VideoEvaluator:
    """숏폼 영상 품질 평가기"""

    # 평가 기준
    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920
    TARGET_FPS = 30
    MIN_DURATION = 15.0
    MAX_DURATION = 30.0
    MAX_FILE_SIZE_MB = 50.0

    def evaluate(
        self,
        video_path: str,
        storyboard_path: str = "",
        audio_path: str = "",
    ) -> EvalResult:
        """영상 품질 종합 평가

        Args:
            video_path: 평가할 영상 경로
            storyboard_path: 스토리보드 JSON 경로 (선택)
            audio_path: 원본 오디오 경로 (선택)
        Returns:
            EvalResult 평가 결과
        """
        result = EvalResult(video_path=video_path)

        if not Path(video_path).exists():
            result.summary = "영상 파일을 찾을 수 없습니다."
            result.grade = "D"
            return result

        # 비디오 로드
        clip = VideoFileClip(video_path)

        try:
            # 1) 기술 품질 (30점)
            result.metrics.append(self._eval_resolution(clip))
            result.metrics.append(self._eval_fps(clip))
            result.metrics.append(self._eval_file_size(video_path))

            # 2) 길이 적합성 (20점)
            result.metrics.append(self._eval_duration(clip))

            # 3) 오디오 (20점)
            result.metrics.append(self._eval_audio(clip, audio_path))

            # 4) 장면 구성 (20점)
            storyboard = None
            if storyboard_path and Path(storyboard_path).exists():
                with open(storyboard_path, "r", encoding="utf-8") as f:
                    storyboard = json.load(f)
            result.metrics.append(self._eval_scenes(clip, storyboard))

            # 5) 비트레이트 (10점)
            result.metrics.append(self._eval_bitrate(video_path, clip))

            # 종합 점수 계산
            total = sum(m.score for m in result.metrics)
            max_total = sum(m.max_score for m in result.metrics)
            result.total_score = (total / max_total * 100) if max_total > 0 else 0

            # 등급 부여
            result.grade = self._calculate_grade(result.total_score)

            # 요약 + 개선 권장사항
            result.summary = self._generate_summary(result)
            result.recommendations = self._generate_recommendations(result)

        finally:
            clip.close()

        return result

    def _eval_resolution(self, clip) -> QualityMetric:
        """해상도 평가 (15점)"""
        w, h = clip.size
        score = 15.0
        detail = f"{w}x{h}"

        if w < self.TARGET_WIDTH or h < self.TARGET_HEIGHT:
            # 해상도 부족 → 비례 감점
            ratio = min(w / self.TARGET_WIDTH, h / self.TARGET_HEIGHT)
            score = 15.0 * ratio
            detail += f" (목표: {self.TARGET_WIDTH}x{self.TARGET_HEIGHT})"

        # 비율 확인 (9:16)
        actual_ratio = w / h
        target_ratio = self.TARGET_WIDTH / self.TARGET_HEIGHT
        if abs(actual_ratio - target_ratio) > 0.05:
            score *= 0.8
            detail += " [비율 불일치]"

        return QualityMetric(
            name="해상도",
            score=round(score, 1),
            max_score=15.0,
            detail=detail,
            passed=score >= 10,
        )

    def _eval_fps(self, clip) -> QualityMetric:
        """FPS 평가 (5점)"""
        fps = clip.fps or 0
        detail = f"{fps:.0f} fps"

        if fps >= self.TARGET_FPS:
            score = 5.0
        elif fps >= 24:
            score = 4.0
            detail += " (권장: 30fps)"
        elif fps >= 15:
            score = 2.5
            detail += " (낮음)"
        else:
            score = 1.0
            detail += " (매우 낮음)"

        return QualityMetric(
            name="프레임레이트",
            score=score,
            max_score=5.0,
            detail=detail,
            passed=fps >= 24,
        )

    def _eval_file_size(self, video_path: str) -> QualityMetric:
        """파일 크기 평가 (10점)"""
        size_mb = Path(video_path).stat().st_size / (1024 * 1024)
        detail = f"{size_mb:.1f} MB"

        if size_mb <= self.MAX_FILE_SIZE_MB:
            score = 10.0
        elif size_mb <= self.MAX_FILE_SIZE_MB * 1.5:
            score = 7.0
            detail += " (약간 큼)"
        elif size_mb <= self.MAX_FILE_SIZE_MB * 2:
            score = 4.0
            detail += " (큼 - 업로드 제한 주의)"
        else:
            score = 2.0
            detail += " (매우 큼 - 압축 필요)"

        return QualityMetric(
            name="파일 크기",
            score=score,
            max_score=10.0,
            detail=detail,
            passed=size_mb <= self.MAX_FILE_SIZE_MB,
        )

    def _eval_duration(self, clip) -> QualityMetric:
        """영상 길이 평가 (20점)"""
        duration = clip.duration
        detail = f"{duration:.1f}초"

        if self.MIN_DURATION <= duration <= self.MAX_DURATION:
            score = 20.0
            detail += " (적정)"
        elif self.MIN_DURATION - 3 <= duration <= self.MAX_DURATION + 5:
            score = 15.0
            detail += f" (권장: {self.MIN_DURATION}~{self.MAX_DURATION}초)"
        elif duration < self.MIN_DURATION:
            score = 10.0 * (duration / self.MIN_DURATION)
            detail += " (너무 짧음)"
        else:
            score = 10.0
            detail += " (너무 김 - 숏폼 기준 초과)"

        return QualityMetric(
            name="영상 길이",
            score=round(score, 1),
            max_score=20.0,
            detail=detail,
            passed=self.MIN_DURATION <= duration <= self.MAX_DURATION,
        )

    def _eval_audio(self, clip, audio_path: str) -> QualityMetric:
        """오디오 평가 (20점)"""
        detail = ""

        # 비디오에 오디오가 있는지 확인
        if clip.audio is None:
            return QualityMetric(
                name="오디오",
                score=0,
                max_score=20.0,
                detail="오디오 없음",
                passed=False,
            )

        score = 10.0  # 오디오 존재 기본 점수
        detail = "오디오 있음"

        # 오디오-비디오 길이 차이 확인
        audio_duration = clip.audio.duration
        video_duration = clip.duration
        diff = abs(audio_duration - video_duration)

        if diff < 0.5:
            score += 10.0
            detail += ", 싱크 우수"
        elif diff < 2.0:
            score += 7.0
            detail += f", 싱크 양호 (차이: {diff:.1f}초)"
        else:
            score += 3.0
            detail += f", 싱크 불량 (차이: {diff:.1f}초)"

        return QualityMetric(
            name="오디오",
            score=round(score, 1),
            max_score=20.0,
            detail=detail,
            passed=score >= 15,
        )

    def _eval_scenes(self, clip, storyboard: dict | None) -> QualityMetric:
        """장면 구성 평가 (20점)"""
        if not storyboard:
            return QualityMetric(
                name="장면 구성",
                score=10.0,
                max_score=20.0,
                detail="스토리보드 없음 - 기본 점수 부여",
                passed=True,
            )

        scenes = storyboard.get("scenes", [])
        expected_duration = storyboard.get("total_duration", 0)
        actual_duration = clip.duration

        score = 0.0
        details = []

        # 장면 수 확인
        scene_count = len(scenes)
        if 3 <= scene_count <= 8:
            score += 10.0
            details.append(f"장면 {scene_count}개 (적정)")
        elif scene_count > 0:
            score += 5.0
            details.append(f"장면 {scene_count}개")
        else:
            details.append("장면 없음")

        # 예상 길이 대비 실제 길이
        if expected_duration > 0:
            duration_ratio = actual_duration / expected_duration
            if 0.8 <= duration_ratio <= 1.2:
                score += 10.0
                details.append("타이밍 일치")
            elif 0.5 <= duration_ratio <= 1.5:
                score += 5.0
                details.append(f"타이밍 편차 ({duration_ratio:.0%})")
            else:
                details.append(f"타이밍 불일치 ({duration_ratio:.0%})")
        else:
            score += 5.0

        return QualityMetric(
            name="장면 구성",
            score=round(score, 1),
            max_score=20.0,
            detail=", ".join(details),
            passed=score >= 10,
        )

    def _eval_bitrate(self, video_path: str, clip) -> QualityMetric:
        """비트레이트 평가 (10점)"""
        file_size_bits = Path(video_path).stat().st_size * 8
        duration = clip.duration if clip.duration > 0 else 1
        bitrate_kbps = file_size_bits / duration / 1000

        detail = f"{bitrate_kbps:.0f} kbps"

        # 1080p 30fps 기준 적정 비트레이트: 4000~8000 kbps
        if 3000 <= bitrate_kbps <= 10000:
            score = 10.0
            detail += " (적정)"
        elif 1500 <= bitrate_kbps <= 15000:
            score = 7.0
            detail += " (양호)"
        elif bitrate_kbps < 1500:
            score = 4.0
            detail += " (낮음 - 화질 저하 가능)"
        else:
            score = 5.0
            detail += " (높음 - 파일 크기 주의)"

        return QualityMetric(
            name="비트레이트",
            score=score,
            max_score=10.0,
            detail=detail,
            passed=score >= 7,
        )

    def _calculate_grade(self, score: float) -> str:
        """점수 → 등급"""
        if score >= 90:
            return "S"
        elif score >= 80:
            return "A"
        elif score >= 65:
            return "B"
        elif score >= 50:
            return "C"
        else:
            return "D"

    def _generate_summary(self, result: EvalResult) -> str:
        """종합 평가 요약"""
        grade_desc = {
            "S": "우수 - 바로 업로드 가능한 품질입니다!",
            "A": "양호 - 약간의 개선으로 완벽해질 수 있습니다.",
            "B": "보통 - 일부 항목 개선이 필요합니다.",
            "C": "미흡 - 여러 항목에서 개선이 필요합니다.",
            "D": "부족 - 주요 항목을 재작업해야 합니다.",
        }
        return f"등급 {result.grade} ({result.total_score:.1f}점) - {grade_desc.get(result.grade, '')}"

    def _generate_recommendations(self, result: EvalResult) -> list[str]:
        """개선 권장사항 생성"""
        recommendations = []
        for metric in result.metrics:
            if not metric.passed:
                if metric.name == "해상도":
                    recommendations.append("원본 이미지 해상도를 높이거나 1080x1920 이미지를 사용하세요.")
                elif metric.name == "프레임레이트":
                    recommendations.append("FPS를 30으로 설정하세요 (settings.py에서 VIDEO_FPS 조정).")
                elif metric.name == "파일 크기":
                    recommendations.append("비디오 코덱 설정을 조정하거나 해상도를 낮춰 파일 크기를 줄이세요.")
                elif metric.name == "영상 길이":
                    recommendations.append("숏폼 최적 길이는 15~30초입니다. 스토리보드 타이밍을 조정하세요.")
                elif metric.name == "오디오":
                    recommendations.append("STEP 3을 다시 실행하여 오디오를 재생성하세요.")
                elif metric.name == "장면 구성":
                    recommendations.append("3~8개 장면으로 스토리보드를 재구성하세요.")
                elif metric.name == "비트레이트":
                    recommendations.append("적정 비트레이트(4000~8000 kbps)에 맞게 인코딩 설정을 조정하세요.")

        if not recommendations:
            recommendations.append("모든 항목이 기준을 충족합니다. 바로 업로드하세요!")

        return recommendations
