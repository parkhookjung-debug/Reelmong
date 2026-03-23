"""STEP 1: Vision 입력 해석 모듈 (무료 로컬 버전)

BLIP (이미지 캡셔닝) + Ollama (로컬 LLM 한국어 변환/분석)
- BLIP: 이미지 → 영어 캡션 생성 (HuggingFace, 무료)
- Ollama: 영어 캡션 → 한국어 장면 묘사 + 구조화 분석 (로컬, 무료)
"""
import json
from pathlib import Path

import requests
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

from config.settings import (
    BLIP_MODEL,
    MAX_IMAGES,
    SUPPORTED_FORMATS,
    CATEGORIES,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)
from .models import SceneDescription, StoreAnalysis


class ImageAnalyzer:
    """F&B 매장 이미지를 분석하여 숏폼 스크립트용 장면 묘사를 생성

    BLIP (무료) → 이미지 캡셔닝
    Ollama (무료) → 한국어 변환 + 장면 분석 구조화
    """

    def __init__(self):
        print("[릴몽] BLIP 모델 로딩 중...")
        self.processor = BlipProcessor.from_pretrained(BLIP_MODEL)
        self.blip_model = BlipForConditionalGeneration.from_pretrained(BLIP_MODEL)
        print("[릴몽] BLIP 모델 로딩 완료!")

    # ─── BLIP: 이미지 → 영어 캡션 ─────────────────────────

    def _caption_image(self, image_path: str) -> str:
        """BLIP으로 이미지 캡션 생성 (영어)"""
        image = Image.open(image_path).convert("RGB")

        # 조건부 캡셔닝: F&B 컨텍스트 힌트 제공
        inputs = self.processor(
            image,
            text="a photograph of a restaurant",
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

    # ─── Ollama: 영어 캡션 → 한국어 분석 ──────────────────

    def _ollama_generate(self, prompt: str) -> str:
        """Ollama 로컬 LLM 호출"""
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
                timeout=120,
            )
            response.raise_for_status()
            return response.json()["response"]
        except requests.ConnectionError:
            print("[!] Ollama 서버에 연결할 수 없습니다.")
            print("    → 'ollama serve' 명령으로 서버를 먼저 실행해주세요.")
            print(f"    → 모델 설치: 'ollama pull {OLLAMA_MODEL}'")
            raise
        except requests.Timeout:
            print("[!] Ollama 응답 시간 초과 (120초)")
            raise

    def _parse_json_from_response(self, text: str) -> dict:
        """LLM 응답에서 JSON 추출 (마크다운 코드블록 포함 대응)"""
        text = text.strip()
        # ```json ... ``` 블록 추출
        if "```" in text:
            start = text.find("```")
            end = text.rfind("```")
            if start != end:
                block = text[start:end + 3]
                # ```json 또는 ``` 제거
                lines = block.split("\n")
                lines = lines[1:-1]  # 첫줄(```json)과 마지막줄(```) 제거
                text = "\n".join(lines)

        # JSON 파싱 시도
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # { } 사이만 추출 재시도
            brace_start = text.find("{")
            brace_end = text.rfind("}")
            if brace_start != -1 and brace_end != -1:
                try:
                    return json.loads(text[brace_start:brace_end + 1])
                except json.JSONDecodeError:
                    pass
            return {}

    def _analyze_caption_with_ollama(self, caption: str, image_path: str) -> dict:
        """Ollama로 BLIP 캡션을 한국어 장면 분석으로 변환"""
        prompt = f"""당신은 F&B 매장 홍보 숏폼 영상 제작을 위한 이미지 분석 전문가입니다.

다음은 매장 관련 이미지의 영어 설명입니다:
"{caption}"

이 설명을 바탕으로 아래 JSON 형식으로 분석 결과를 작성해주세요.
반드시 JSON만 출력하세요.

{{
  "scene_type": "food 또는 interior 또는 exterior 또는 menu 또는 other 중 하나",
  "description_ko": "숏폼 나레이션에 활용할 수 있는 감성적인 한국어 장면 묘사 1~2문장",
  "mood": "warm 또는 cozy 또는 modern 또는 traditional 또는 vibrant 또는 elegant 또는 casual 중 하나",
  "key_elements": ["핵심 시각 요소1", "요소2", "요소3"],
  "color_tone": "따뜻한 난색 또는 차가운 한색 또는 밝고 경쾌한 또는 어둡고 고급스러운 또는 자연스러운 중 하나",
  "suggested_duration": 3.0
}}"""

        response_text = self._ollama_generate(prompt)
        result = self._parse_json_from_response(response_text)

        # 파싱 실패 시 기본값 반환
        if not result:
            print(f"[!] JSON 파싱 실패, 기본값 사용 (원문: {caption})")
            return {
                "scene_type": "other",
                "description_ko": f"매장의 모습을 담은 사진입니다. ({caption})",
                "mood": "warm",
                "key_elements": [],
                "color_tone": "자연스러운",
                "suggested_duration": 3.0,
            }

        return result

    # ─── 메인 분석 로직 ────────────────────────────────────

    def analyze_single_image(self, image_path: str) -> SceneDescription:
        """단일 이미지 분석: BLIP 캡셔닝 → Ollama 한국어 변환"""
        ext = Path(image_path).suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"지원하지 않는 이미지 형식: {ext}")

        # 1) BLIP 캡셔닝 (영어)
        caption_en = self._caption_image(image_path)
        print(f"    BLIP 캡션: {caption_en}")

        # 2) Ollama 한국어 분석
        analysis = self._analyze_caption_with_ollama(caption_en, image_path)

        return SceneDescription(
            image_path=image_path,
            scene_type=analysis.get("scene_type", "other"),
            description_ko=analysis.get("description_ko", ""),
            description_en=caption_en,
            mood=analysis.get("mood", "warm"),
            key_elements=analysis.get("key_elements", []),
            color_tone=analysis.get("color_tone", ""),
            suggested_duration=analysis.get("suggested_duration", 3.0),
        )

    def analyze_store(
        self,
        image_paths: list[str],
        store_name: str,
        store_intro: str,
        category: str = "",
    ) -> StoreAnalysis:
        """매장 전체 분석: 여러 이미지 + 소개 텍스트 → StoreAnalysis JSON"""
        if len(image_paths) > MAX_IMAGES:
            image_paths = image_paths[:MAX_IMAGES]
            print(f"[릴몽] 이미지가 {MAX_IMAGES}장을 초과하여 앞 {MAX_IMAGES}장만 사용합니다.")

        # 1) 개별 이미지 분석
        scenes: list[SceneDescription] = []
        for i, path in enumerate(image_paths, 1):
            print(f"[릴몽] 이미지 분석 중 ({i}/{len(image_paths)}): {Path(path).name}")
            scene = self.analyze_single_image(path)
            scenes.append(scene)

        # 2) 전체 매장 종합 분석
        summary = self._summarize_store(scenes, store_name, store_intro, category)

        return StoreAnalysis(
            store_name=store_name,
            store_intro=store_intro,
            category=summary.get("category", category or "기타"),
            scenes=scenes,
            overall_mood=summary.get("overall_mood", ""),
            highlight_points=summary.get("highlight_points", []),
            target_audience=summary.get("target_audience", ""),
        )

    def _summarize_store(
        self,
        scenes: list[SceneDescription],
        store_name: str,
        store_intro: str,
        category: str,
    ) -> dict:
        """개별 장면 분석 결과를 종합하여 매장 전체 요약 생성"""
        scenes_text = "\n".join(
            f"- [{s.scene_type}] {s.description_ko} (분위기: {s.mood})"
            for s in scenes
        )

        categories_str = ", ".join(CATEGORIES)

        prompt = f"""당신은 F&B 매장 마케팅 분석 전문가입니다.

다음은 '{store_name}' 매장의 이미지 분석 결과입니다.

매장 소개: {store_intro}
{f'업종: {category}' if category else '업종: 아래 분석을 보고 자동 판별 필요'}

개별 장면 분석:
{scenes_text}

위 정보를 바탕으로 매장 전체를 종합 분석하여 아래 JSON 형식으로 응답하세요.
반드시 JSON만 출력하세요.

{{
  "category": "{categories_str} 중 하나",
  "overall_mood": "매장 전체 분위기를 한 문장으로 요약",
  "highlight_points": ["숏폼에서 강조할 홍보 포인트1", "포인트2", "포인트3"],
  "target_audience": "추천 타겟 고객층 설명 1문장"
}}"""

        response_text = self._ollama_generate(prompt)
        result = self._parse_json_from_response(response_text)

        if not result:
            return {
                "category": category or "기타",
                "overall_mood": "따뜻하고 편안한 분위기의 매장",
                "highlight_points": ["맛있는 음식", "편안한 분위기", "합리적인 가격"],
                "target_audience": "20~40대 직장인 및 가족 단위 고객",
            }

        return result
