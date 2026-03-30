"""STEP 2: 가사 생성 (Ollama LLM)

음식 분석 결과를 받아 음식이 1인칭으로 부르는 재밌는 노래 가사를 생성합니다.
- 음식이 자기 자신을 소개하는 노래
- 4~6줄의 짧은 가사 (숏폼용)
- 음식 성격/감정에 맞는 톤
"""
import json
from pathlib import Path

import requests

from config.settings import OLLAMA_BASE_URL, OLLAMA_MODEL, SONG_STYLES
from src.step1_analyze.models import FoodAnalysis


class LyricsGenerator:
    """음식 분석 결과 -> 노래 가사 생성"""

    def __init__(self):
        self.model = OLLAMA_MODEL

    def _ollama_generate(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,
                        "num_predict": 1024,
                    },
                },
                timeout=180,
            )
            response.raise_for_status()
            return response.json()["response"]
        except requests.ConnectionError:
            print("[!] Ollama 서버에 연결할 수 없습니다.")
            raise

    def _parse_json_from_response(self, text: str) -> dict:
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

    def generate(self, analysis: FoodAnalysis) -> dict:
        """음식 분석 결과 -> 노래 가사 + 메타데이터

        Returns:
            {
                "title": "노래 제목",
                "lyrics": ["가사 줄1", "가사 줄2", ...],
                "lyrics_full": "전체 가사 텍스트",
                "mood": "분위기",
                "tempo": "빠르기",
            }
        """
        print(f"[맛노래] 가사 생성 중... ({analysis.food_name})")

        style = SONG_STYLES.get(analysis.category, SONG_STYLES["기타"])

        result = self._generate_lyrics(analysis, style)

        if not result or "lyrics" not in result:
            print("[!] LLM 가사 생성 실패, 기본 가사 사용")
            result = self._fallback_lyrics(analysis, style)

        # lyrics_full 조합
        if isinstance(result.get("lyrics"), list):
            result["lyrics_full"] = " ".join(result["lyrics"])
        else:
            result["lyrics_full"] = result.get("lyrics", "")
            result["lyrics"] = [result["lyrics_full"]]

        result["mood"] = result.get("mood", style["mood"])
        result["tempo"] = result.get("tempo", style["tempo"])

        print(f"[맛노래] 가사 생성 완료! 제목: {result.get('title', '무제')}")
        return result

    def _generate_lyrics(self, analysis: FoodAnalysis, style: dict) -> dict:
        prompt = f"""당신은 음식을 의인화하여 재밌는 노래 가사를 만드는 작사가입니다.

## 음식 정보
- 음식: {analysis.food_name}
- 카테고리: {analysis.category}
- 묘사: {analysis.description}
- 재료: {', '.join(analysis.ingredients) if analysis.ingredients else '알 수 없음'}
- 맛: {', '.join(analysis.taste_keywords) if analysis.taste_keywords else '맛있는'}
- 성격: {analysis.personality}
- 감정: {analysis.emotion}

## 노래 스타일
- 분위기: {style['mood']}
- 템포: {style['tempo']}
- 감정: {style['emotion']}

## 작사 규칙
1. 음식이 1인칭("나")으로 자기를 소개하며 부르는 노래
2. 4~6줄의 짧은 가사 (각 줄 10~20자)
3. 재미있고 중독성 있는 가사 (말장난, 의성어 환영)
4. 한국어로 작성
5. TTS로 읽었을 때 리듬감 있게
6. 후렴구 느낌의 반복 구절 포함

아래 JSON 형식으로만 응답하세요.

{{
  "title": "노래 제목",
  "lyrics": [
    "첫 번째 줄 가사",
    "두 번째 줄 가사",
    "세 번째 줄 가사",
    "네 번째 줄 가사",
    "다섯 번째 줄 가사 (후렴)"
  ]
}}"""

        response_text = self._ollama_generate(prompt)
        return self._parse_json_from_response(response_text)

    def _fallback_lyrics(self, analysis: FoodAnalysis, style: dict) -> dict:
        """LLM 실패 시 기본 가사"""
        name = analysis.food_name or "맛있는 음식"
        taste = analysis.taste_keywords[0] if analysis.taste_keywords else "맛있는"

        return {
            "title": f"나는 {name}",
            "lyrics": [
                f"안녕 나는 {name}이야",
                f"{taste} 맛이 내 매력이지",
                "한 입 먹으면 못 멈춰",
                "자꾸자꾸 생각나",
                f"나는 {name} 날 먹어줘",
            ],
        }

    def save_lyrics(self, lyrics_data: dict, output_path: str) -> None:
        """가사 데이터 JSON 저장"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(lyrics_data, f, ensure_ascii=False, indent=2)
