"""STEP 1: 음식 이미지 분석 (BLIP + Ollama)

음식 사진을 분석하여:
- 음식 이름, 카테고리 판별
- 맛/재료/색감 키워드 추출
- 음식 의인화 성격 부여 (노래 스타일 결정용)
"""
import json
from pathlib import Path

import requests
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

from config.settings import (
    BLIP_MODEL,
    SUPPORTED_FORMATS,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)
from .models import FoodAnalysis


class FoodAnalyzer:
    """음식 이미지를 분석하여 노래 생성에 필요한 정보 추출"""

    def __init__(self):
        print("[맛노래] BLIP 모델 로딩 중...")
        self.processor = BlipProcessor.from_pretrained(BLIP_MODEL)
        self.blip_model = BlipForConditionalGeneration.from_pretrained(BLIP_MODEL)
        print("[맛노래] BLIP 모델 로딩 완료!")

    def _caption_image(self, image_path: str) -> str:
        """BLIP으로 이미지 캡션 생성 (영어)"""
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(
            image,
            text="a photograph of food",
            return_tensors="pt",
        )
        output = self.blip_model.generate(
            **inputs,
            max_new_tokens=80,
            num_beams=5,
            early_stopping=True,
        )
        caption = self.processor.decode(output[0], skip_special_tokens=True)
        return caption

    def _ollama_generate(self, prompt: str) -> str:
        """Ollama 로컬 LLM 호출"""
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.5},
                },
                timeout=120,
            )
            response.raise_for_status()
            return response.json()["response"]
        except requests.ConnectionError:
            print("[!] Ollama 서버에 연결할 수 없습니다.")
            print("    -> 'ollama serve' 로 서버를 실행해주세요.")
            raise

    def _parse_json_from_response(self, text: str) -> dict:
        """LLM 응답에서 JSON 추출"""
        text = text.strip()
        if "```" in text:
            start = text.find("```")
            end = text.rfind("```")
            if start != end:
                lines = text[start:end + 3].split("\n")
                text = "\n".join(lines[1:-1])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            brace_start = text.find("{")
            brace_end = text.rfind("}")
            if brace_start != -1 and brace_end != -1:
                try:
                    return json.loads(text[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    pass
            return {}

    def analyze(self, image_path: str) -> FoodAnalysis:
        """음식 이미지 분석: BLIP 캡셔닝 -> Ollama 한국어 분석 + 의인화"""
        ext = Path(image_path).suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"지원하지 않는 이미지 형식: {ext}")

        # 1) BLIP 캡셔닝 (영어)
        caption_en = self._caption_image(image_path)
        print(f"    BLIP 캡션: {caption_en}")

        # 2) Ollama 한국어 분석 + 의인화
        analysis = self._analyze_food(caption_en)

        return FoodAnalysis(
            image_path=str(Path(image_path).resolve()),
            food_name=analysis.get("food_name", "맛있는 음식"),
            food_name_en=caption_en,
            category=analysis.get("category", "기타"),
            description=analysis.get("description", ""),
            ingredients=analysis.get("ingredients", []),
            taste_keywords=analysis.get("taste_keywords", []),
            color_mood=analysis.get("color_mood", ""),
            personality=analysis.get("personality", "밝고 활발한"),
            emotion=analysis.get("emotion", "즐거운"),
        )

    def _analyze_food(self, caption: str) -> dict:
        """Ollama로 음식 분석 + 의인화 성격 부여"""
        prompt = f"""당신은 음식을 의인화하여 노래를 만드는 크리에이터입니다.

다음은 음식 사진의 영어 설명입니다:
"{caption}"

이 음식을 분석하고, 이 음식이 사람이라면 어떤 성격일지 상상해주세요.
반드시 JSON만 출력하세요.

{{
  "food_name": "음식 이름 (한국어)",
  "category": "한식/중식/일식/양식/카페/디저트/치킨/피자/분식/기타 중 하나",
  "description": "이 음식의 매력을 감성적으로 묘사한 1~2문장",
  "ingredients": ["주요 재료1", "재료2", "재료3"],
  "taste_keywords": ["맛 키워드1", "키워드2", "키워드3"],
  "color_mood": "음식의 색감 분위기 (예: 빨갛고 열정적인, 갈색빛 따뜻한)",
  "personality": "이 음식을 의인화했을 때 성격 (예: 매콤하고 당찬, 달콤하고 수줍은)",
  "emotion": "노래할 때 감정 (즐거운/신나는/감성적인/귀여운/열정적인 중 하나)"
}}"""

        response_text = self._ollama_generate(prompt)
        result = self._parse_json_from_response(response_text)

        if not result:
            print("[!] JSON 파싱 실패, 기본값 사용")
            return {
                "food_name": "맛있는 음식",
                "category": "기타",
                "description": "맛있어 보이는 음식입니다.",
                "ingredients": [],
                "taste_keywords": ["맛있는"],
                "color_mood": "따뜻한",
                "personality": "밝고 활발한",
                "emotion": "즐거운",
            }

        return result
