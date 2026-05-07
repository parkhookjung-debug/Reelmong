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
        prompt = f"""너는 언더그라운드 무대 위에서 마이크를 쥔 거친 힙합 래퍼야.
아래 음식을 주제로 15초 분량의 빠르고 강렬한 속사포 랩 가사를 써줘.

## 음식 정보
- 음식: {analysis.food_name}
- 성격: {analysis.personality}
- 맛: {', '.join(analysis.taste_keywords) if analysis.taste_keywords else '맛있는'}
- 분위기: {style['mood']}

## 작성 규칙
1. 음식이 1인칭("나")으로 랩하는 가사
2. 딱 6줄 (각 줄 10~20자)
3. 문장 끝마다 라임(각운) 철저히 맞추기
4. 의성어·반복 리듬 환영 (예: 빠삭빠삭, 쫀득쫀득)
5. 강렬하고 중독성 있게
6. 절대 금지: "verse:", "hook:", "후렴:", "1절:" 같은 레이블 붙이지 말 것. 가사 내용만.

JSON 형식으로만 응답:

{{
  "title": "랩 제목",
  "lyrics": [
    "첫째 줄 가사",
    "둘째 줄 가사",
    "셋째 줄 가사",
    "넷째 줄 가사",
    "다섯째 줄 가사",
    "여섯째 줄 가사"
  ]
}}"""

        response_text = self._ollama_generate(prompt)
        return self._parse_json_from_response(response_text)

    def _fallback_lyrics(self, analysis: FoodAnalysis, style: dict) -> dict:
        """LLM 실패 시 기본 랩 가사"""
        name = analysis.food_name or "맛있는 음식"
        taste = analysis.taste_keywords[0] if analysis.taste_keywords else "맛있는"

        return {
            "title": f"{name} 랩",
            "lyrics": [
                f"나는 {name} 최강의 맛",
                f"{taste} 향기로 너를 잡아",
                "한 입 베어물면 눈이 번쩍",
                "세상 모든 걱정 다 박살",
                f"{name} {name} 나를 먹어",
                "배달 앱 켜고 지금 당장",
            ],
        }

    def save_lyrics(self, lyrics_data: dict, output_path: str) -> None:
        """가사 데이터 JSON 저장"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(lyrics_data, f, ensure_ascii=False, indent=2)
