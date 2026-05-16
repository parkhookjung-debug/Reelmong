"""STEP 1: Vision 입력 해석 모듈 (OpenRouter Vision 버전)

Gemini Vision으로 이미지를 직접 한국어 분석
- 기존 BLIP(영어 캡션) + Ollama(한국어 변환) 2단계
  → Gemini Vision 1단계로 단순화
- 이미지 base64 인코딩 → OpenRouter API → 한국어 JSON 직접 출력
"""
import base64
import json
from pathlib import Path

from openai import OpenAI

from config.settings import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    VISION_MODEL,
    LLM_MODEL,
    MAX_IMAGES,
    SUPPORTED_FORMATS,
    CATEGORIES,
)
from .models import SceneDescription, StoreAnalysis


class ImageAnalyzer:
    """F&B 매장 이미지를 분석하여 숏폼 스크립트용 장면 묘사를 생성

    Gemini Vision (OpenRouter) — 이미지 → 한국어 분석 직접 출력
    """

    def __init__(self):
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
        print("[릴몽] OpenRouter Vision 초기화 완료")

    # ─── 이미지 인코딩 ──────────────────────────────────────

    def _encode_image(self, image_path: str) -> tuple[str, str]:
        """이미지를 base64로 인코딩, (data, mime_subtype) 반환"""
        ext = Path(image_path).suffix.lower().lstrip(".")
        if ext == "jpg":
            ext = "jpeg"
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return data, ext

    # ─── API 호출 ───────────────────────────────────────────

    def _call_vision(self, image_path: str, prompt: str) -> str:
        """Gemini Vision API 호출 — 이미지 + 텍스트 프롬프트"""
        image_data, ext = self._encode_image(image_path)
        response = self.client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{ext};base64,{image_data}"
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }],
            max_tokens=600,
        )
        return response.choices[0].message.content

    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """텍스트 전용 LLM 호출"""
        response = self.client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=temperature,
        )
        return response.choices[0].message.content

    def _parse_json(self, text: str) -> dict:
        """LLM 응답에서 JSON 추출 (마크다운 코드블록 포함 대응)"""
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

    # ─── 이미지 분석 ────────────────────────────────────────

    def _analyze_image(self, image_path: str) -> dict:
        """Gemini Vision으로 이미지를 직접 한국어 분석"""
        prompt = """당신은 F&B 매장 홍보 숏폼 영상 제작을 위한 이미지 분석 전문가입니다.

이 매장 이미지를 분석하여 아래 JSON 형식으로 응답하세요.
반드시 JSON만 출력하세요.

{
  "scene_type": "food 또는 interior 또는 exterior 또는 menu 또는 other 중 하나",
  "description_ko": "숏폼 나레이션에 활용할 수 있는 감성적인 한국어 장면 묘사 1~2문장",
  "mood": "warm 또는 cozy 또는 modern 또는 traditional 또는 vibrant 또는 elegant 또는 casual 중 하나",
  "key_elements": ["핵심 시각 요소1", "요소2", "요소3"],
  "color_tone": "따뜻한 난색 또는 차가운 한색 또는 밝고 경쾌한 또는 어둡고 고급스러운 또는 자연스러운 중 하나",
  "suggested_duration": 3.0
}"""
        response_text = self._call_vision(image_path, prompt)
        result = self._parse_json(response_text)

        if not result:
            print(f"[!] Vision 분석 JSON 파싱 실패, 기본값 사용")
            return {
                "scene_type": "other",
                "description_ko": "매장의 모습을 담은 장면입니다.",
                "mood": "warm",
                "key_elements": [],
                "color_tone": "자연스러운",
                "suggested_duration": 3.0,
            }
        return result

    # ─── 메인 분석 로직 ────────────────────────────────────

    def analyze_single_image(self, image_path: str) -> SceneDescription:
        """단일 이미지 분석: Gemini Vision → 한국어 구조화 분석"""
        ext = Path(image_path).suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"지원하지 않는 이미지 형식: {ext}")

        analysis = self._analyze_image(image_path)
        print(f"    [Vision] {analysis.get('scene_type', '?')} / {analysis.get('mood', '?')}")

        return SceneDescription(
            image_path=image_path,
            scene_type=analysis.get("scene_type", "other"),
            description_ko=analysis.get("description_ko", ""),
            description_en="",  # Vision 직접 분석으로 영어 캡션 불필요
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

        scenes: list[SceneDescription] = []
        for i, path in enumerate(image_paths, 1):
            print(f"[릴몽] 이미지 분석 중 ({i}/{len(image_paths)}): {Path(path).name}")
            scene = self.analyze_single_image(path)
            scenes.append(scene)

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

        response_text = self._call_llm(prompt)
        result = self._parse_json(response_text)

        if not result:
            return {
                "category": category or "기타",
                "overall_mood": "활기차고 매력적인 분위기의 매장",
                "highlight_points": ["맛있는 음식", "편안한 분위기", "합리적인 가격"],
                "target_audience": "20~40대 직장인 및 가족 단위 고객",
            }
        return result
