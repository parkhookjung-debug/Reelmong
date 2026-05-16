"""STEP 2 데이터 모델 - 스크립트/스토리보드 구조화"""
from dataclasses import dataclass, field, asdict
import json


@dataclass
class SceneScript:
    """개별 장면 스크립트"""
    scene_index: int             # 장면 순서 (1부터)
    image_path: str              # 사용할 이미지 경로
    narration: str               # 나레이션 텍스트 (TTS 입력)
    subtitle: str                # 자막 텍스트 (화면 표시용)
    duration: float              # 장면 지속 시간 (초)
    start_time: float = 0.0     # 시작 시간 (초)
    effect: str = "ken_burns"    # 영상 효과: ken_burns, zoom_in, zoom_out, fade, slide
    transition: str = "crossfade"  # 전환 효과: crossfade, cut, fade_black

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Storyboard:
    """전체 스토리보드 (STEP 3, 4로 전달)"""
    store_name: str
    category: str
    total_duration: float                        # 전체 영상 길이 (초)
    scenes: list[SceneScript] = field(default_factory=list)
    bgm_mood: str = ""                           # BGM 분위기 키워드
    script_full_text: str = ""                   # 전체 나레이션 텍스트 (TTS용)
    hook_candidates: list[str] = field(default_factory=list)  # 후킹 멘트 후보 10개
    food_type: str = ""                          # 음식 종류 설명 (예: 무한리필 초밥 뷔페)

    def to_dict(self) -> dict:
        return {
            "store_name": self.store_name,
            "category": self.category,
            "food_type": self.food_type,
            "total_duration": self.total_duration,
            "scenes": [s.to_dict() for s in self.scenes],
            "bgm_mood": self.bgm_mood,
            "script_full_text": self.script_full_text,
            "hook_candidates": self.hook_candidates,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def to_srt(self) -> str:
        """SRT 자막 파일 형식으로 변환"""
        lines = []
        for scene in self.scenes:
            start = _seconds_to_srt_time(scene.start_time)
            end = _seconds_to_srt_time(scene.start_time + scene.duration)
            lines.append(f"{scene.scene_index}")
            lines.append(f"{start} --> {end}")
            lines.append(scene.subtitle)
            lines.append("")
        return "\n".join(lines)

    def save_srt(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_srt())


def _seconds_to_srt_time(seconds: float) -> str:
    """초 → SRT 시간 형식 (HH:MM:SS,mmm)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
