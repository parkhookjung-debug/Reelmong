"""STEP 2: 스크립트 생성 모듈

STEP 1 결과 (StoreAnalysis JSON) → Ollama LLM → 30초 릴스 스토리보드
- 오프닝 후크 (첫 3초 - 시청자 이목 집중)
- 장면별 나레이션 + 자막
- 클로징 CTA (행동 유도)
- BGM 분위기 결정
"""
import json
from pathlib import Path

import requests

from config.settings import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    VIDEO_DURATION_MIN,
    VIDEO_DURATION_MAX,
    CATEGORIES,
)
from src.step1_vision.models import StoreAnalysis
from .models import SceneScript, Storyboard


class ScriptGenerator:
    """STEP 1 분석 결과를 받아 숏폼 스토리보드를 생성"""

    def __init__(self):
        self.model = OLLAMA_MODEL
        self.target_duration = 25  # 목표 영상 길이 (초)

    def _ollama_generate(self, prompt: str) -> str:
        """Ollama 로컬 LLM 호출"""
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2048,
                    },
                },
                timeout=180,
            )
            response.raise_for_status()
            return response.json()["response"]
        except requests.ConnectionError:
            print("[!] Ollama 서버에 연결할 수 없습니다.")
            print("    → 'ollama serve' 로 서버를 실행해주세요.")
            raise

    def _parse_json_from_response(self, text: str) -> dict:
        """LLM 응답에서 JSON 추출"""
        text = text.strip()
        if "```" in text:
            start = text.find("```")
            end = text.rfind("```")
            if start != end:
                block = text[start:end + 3]
                lines = block.split("\n")
                lines = lines[1:-1]
                text = "\n".join(lines)

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

    def generate(self, analysis: StoreAnalysis) -> Storyboard:
        """StoreAnalysis → Storyboard 생성

        Args:
            analysis: STEP 1에서 생성된 매장 분석 결과
        Returns:
            Storyboard: 장면별 나레이션, 자막, 타이밍이 포함된 스토리보드
        """
        num_scenes = len(analysis.scenes)
        if num_scenes == 0:
            raise ValueError("분석된 장면이 없습니다. STEP 1을 먼저 실행해주세요.")

        print(f"[릴몽] 스크립트 생성 시작 ({num_scenes}개 장면)")

        # 1) LLM으로 스토리보드 생성
        print("[릴몽] Ollama로 스토리보드 생성 중...")
        storyboard_data = self._generate_storyboard(analysis)

        # 2) 구조화된 Storyboard 객체 생성
        storyboard = self._build_storyboard(storyboard_data, analysis)

        print(f"[릴몽] 스크립트 생성 완료! (총 {storyboard.total_duration:.1f}초)")
        return storyboard

    def _generate_storyboard(self, analysis: StoreAnalysis) -> dict:
        """Ollama로 스토리보드 JSON 생성"""
        scenes_info = "\n".join(
            f"  장면{i+1}: [{s.scene_type}] {s.description_ko} (분위기: {s.mood}, 이미지: {s.image_path})"
            for i, s in enumerate(analysis.scenes)
        )

        num_scenes = len(analysis.scenes)
        duration_per_scene = round(self.target_duration / num_scenes, 1)

        prompt = f"""당신은 F&B 매장 홍보 숏폼 영상의 스크립트 작가입니다.
인스타 릴스, 유튜브 쇼츠 스타일의 15~30초 홍보 영상 대본을 작성해주세요.

## 매장 정보
- 매장명: {analysis.store_name}
- 업종: {analysis.category}
- 소개: {analysis.store_intro}
- 전체 분위기: {analysis.overall_mood}
- 홍보 포인트: {', '.join(analysis.highlight_points)}
- 타겟 고객: {analysis.target_audience}

## 이미지 분석 결과 ({num_scenes}개 장면)
{scenes_info}

## 작성 규칙
1. opening_hook: 첫 3초 안에 시청자를 잡는 강렬한 한 문장 (질문형 또는 감탄형)
2. 각 장면의 narration: 자연스럽고 감성적인 나레이션 (TTS로 읽힘)
3. 각 장면의 subtitle: 화면에 표시할 짧은 자막 (나레이션 요약, 10자 이내)
4. closing_cta: 마지막 행동 유도 문구 (위치, 검색 키워드 등)
5. bgm_mood: 배경음악 분위기 (energetic, calm, warm, trendy, elegant 중 하나)
6. 장면당 약 {duration_per_scene}초, 전체 {self.target_duration}초 목표
7. effect: 각 장면 효과 (ken_burns, zoom_in, zoom_out, fade, slide 중 하나)

아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요.

{{
  "opening_hook": "첫 3초 후크 문구",
  "bgm_mood": "warm",
  "closing_cta": "마지막 CTA 문구",
  "scenes": [
    {{
      "scene_index": 1,
      "narration": "나레이션 텍스트",
      "subtitle": "짧은 자막",
      "duration": {duration_per_scene},
      "effect": "ken_burns"
    }}
  ]
}}"""

        response_text = self._ollama_generate(prompt)
        result = self._parse_json_from_response(response_text)

        if not result or "scenes" not in result:
            print("[!] LLM 스토리보드 생성 실패, 기본 템플릿 사용")
            result = self._fallback_storyboard(analysis)

        return result

    def _fallback_storyboard(self, analysis: StoreAnalysis) -> dict:
        """LLM 실패 시 규칙 기반 기본 스토리보드"""
        num_scenes = len(analysis.scenes)
        duration_per_scene = round(self.target_duration / num_scenes, 1)

        scenes = []
        for i, scene in enumerate(analysis.scenes):
            if i == 0:
                narration = f"{analysis.store_name}을 소개합니다. {analysis.store_intro}"
                subtitle = analysis.store_name
            elif scene.scene_type == "food":
                narration = f"정성 가득한 메뉴를 만나보세요. {scene.description_ko}"
                subtitle = "시그니처 메뉴"
            elif scene.scene_type == "interior":
                narration = f"편안한 공간에서 특별한 시간을 보내세요. {scene.description_ko}"
                subtitle = "아늑한 공간"
            else:
                narration = scene.description_ko or "특별한 경험이 기다립니다."
                subtitle = "특별한 경험"

            scenes.append({
                "scene_index": i + 1,
                "narration": narration,
                "subtitle": subtitle,
                "duration": duration_per_scene,
                "effect": "ken_burns",
            })

        return {
            "opening_hook": f"이런 곳 찾고 있었죠? {analysis.store_name}!",
            "bgm_mood": "warm",
            "closing_cta": f"{analysis.store_name}, 지금 바로 검색해보세요!",
            "scenes": scenes,
        }

    def _build_storyboard(self, data: dict, analysis: StoreAnalysis) -> Storyboard:
        """JSON 데이터 → Storyboard 객체 변환 + 타이밍 계산"""
        scenes: list[SceneScript] = []
        current_time = 0.0

        raw_scenes = data.get("scenes", [])

        for i, raw in enumerate(raw_scenes):
            # 이미지 매핑: 장면 수와 이미지 수 맞추기
            image_idx = min(i, len(analysis.scenes) - 1)
            image_path = analysis.scenes[image_idx].image_path

            duration = float(raw.get("duration", 4.0))
            # 최소 2초, 최대 8초로 클램핑
            duration = max(2.0, min(8.0, duration))

            scene = SceneScript(
                scene_index=raw.get("scene_index", i + 1),
                image_path=image_path,
                narration=raw.get("narration", ""),
                subtitle=raw.get("subtitle", ""),
                duration=duration,
                start_time=current_time,
                effect=raw.get("effect", "ken_burns"),
                transition=raw.get("transition", "crossfade"),
            )
            scenes.append(scene)
            current_time += duration

        # 전체 나레이션 텍스트 조합 (TTS 입력용)
        opening = data.get("opening_hook", "")
        closing = data.get("closing_cta", "")
        narrations = [opening] + [s.narration for s in scenes] + [closing]
        full_text = " ".join(n for n in narrations if n)

        storyboard = Storyboard(
            store_name=analysis.store_name,
            category=analysis.category,
            total_duration=current_time,
            opening_hook=opening,
            scenes=scenes,
            closing_cta=closing,
            bgm_mood=data.get("bgm_mood", "warm"),
            script_full_text=full_text,
        )

        return storyboard

    @staticmethod
    def load_analysis(json_path: str) -> StoreAnalysis:
        """STEP 1 결과 JSON 파일 로드"""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        from src.step1_vision.models import SceneDescription
        scenes = [
            SceneDescription(**s) for s in data.get("scenes", [])
        ]

        return StoreAnalysis(
            store_name=data["store_name"],
            store_intro=data["store_intro"],
            category=data["category"],
            scenes=scenes,
            overall_mood=data.get("overall_mood", ""),
            highlight_points=data.get("highlight_points", []),
            target_audience=data.get("target_audience", ""),
        )
