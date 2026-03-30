"""STEP 1 데이터 모델 - 음식 분석 결과"""
from dataclasses import dataclass, field, asdict
import json


@dataclass
class FoodAnalysis:
    """음식 이미지 분석 결과"""
    image_path: str
    food_name: str = ""           # 음식 이름 (한국어)
    food_name_en: str = ""        # BLIP 원문 캡션
    category: str = "기타"        # 한식, 중식, 일식 등
    description: str = ""         # 음식 묘사 (감성적)
    ingredients: list[str] = field(default_factory=list)  # 주요 재료
    taste_keywords: list[str] = field(default_factory=list)  # 맛 키워드
    color_mood: str = ""          # 색감 분위기
    personality: str = ""         # 음식 의인화 성격 (노래 스타일용)
    emotion: str = "즐거운"       # 노래 감정

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: str) -> "FoodAnalysis":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
