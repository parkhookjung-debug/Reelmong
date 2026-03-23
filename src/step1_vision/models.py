"""STEP 1 데이터 모델 - Vision 분석 결과 구조화"""
from dataclasses import dataclass, field, asdict
import json


@dataclass
class SceneDescription:
    """개별 이미지 분석 결과"""
    image_path: str
    scene_type: str          # "food", "interior", "exterior", "menu", "other"
    description_ko: str      # 한국어 장면 묘사
    description_en: str      # BLIP 영어 원문 캡션
    mood: str                # "warm", "cozy", "modern", "traditional", "vibrant"
    key_elements: list[str] = field(default_factory=list)
    color_tone: str = ""
    suggested_duration: float = 3.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StoreAnalysis:
    """매장 전체 분석 결과 (STEP 2로 전달되는 JSON)"""
    store_name: str
    store_intro: str
    category: str
    scenes: list[SceneDescription] = field(default_factory=list)
    overall_mood: str = ""
    highlight_points: list[str] = field(default_factory=list)
    target_audience: str = ""

    def to_dict(self) -> dict:
        return {
            "store_name": self.store_name,
            "store_intro": self.store_intro,
            "category": self.category,
            "scenes": [s.to_dict() for s in self.scenes],
            "overall_mood": self.overall_mood,
            "highlight_points": self.highlight_points,
            "target_audience": self.target_audience,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
