"""STEP 2: 스크립트 생성 모듈

STEP 1 결과 (StoreAnalysis JSON) → Gemini LLM → 30초 릴스 스토리보드
- 장면별 나레이션 + 자막
- BGM 분위기 결정
"""
import json
import random
from pathlib import Path

from openai import OpenAI

from config.settings import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    LLM_MODEL,
    VIDEO_DURATION_MIN,
    VIDEO_DURATION_MAX,
    CATEGORIES,
)
from src.step1_vision.models import StoreAnalysis
from .models import SceneScript, Storyboard


class ScriptGenerator:
    """STEP 1 분석 결과를 받아 숏폼 스토리보드를 생성"""

    def __init__(self):
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
        self.model = LLM_MODEL
        self.target_duration = 25  # 목표 영상 길이 (초)

    def _llm_generate(self, prompt: str, temperature: float = 0.7) -> str:
        """Gemini LLM 호출 (OpenRouter)"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=temperature,
        )
        return response.choices[0].message.content

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

        print("[릴몽] Gemini로 스토리보드 생성 중...")
        storyboard_data = self._generate_storyboard(analysis)

        storyboard = self._build_storyboard(storyboard_data, analysis)

        print(f"[릴몽] 스크립트 생성 완료! (총 {storyboard.total_duration:.1f}초)")
        return storyboard

    def _generate_storyboard(self, analysis: StoreAnalysis) -> dict:
        """Gemini로 스토리보드 JSON 생성"""
        scenes_info = "\n".join(
            f"  장면{i+1}: [{s.scene_type}] {s.description_ko} / 핵심요소: {', '.join(s.key_elements)} / 분위기: {s.mood}"
            for i, s in enumerate(analysis.scenes)
        )

        num_scenes = len(analysis.scenes)
        duration_per_scene = round(self.target_duration / num_scenes, 1)

        prompt = f"""당신은 MZ세대가 운영하는 맛집 유튜브 채널의 숏폼 스크립트 작가입니다.
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

## 문체 규칙 (매우 중요)
- 반드시 요즘 MZ 친근한 말투로 작성. 문장 끝은 반드시 아래 스타일 중 하나로 끝내세요.
- 말투 스타일: "-해봐", "-했어!", "-잖아!", "-인 거야?", "-실화야?", "-대박이야!", "-이거 봐봐"
- 절대 금지 말투: "-입니다", "-습니다", "-합니다", "-다", "-군요", "-네요"
- 이모티콘, 이모지, 특수문자 사용 금지 (😊🔥✨ 등 절대 쓰지 말 것)
- 후킹: "이거 실화야?", "여기가 맞아?", "어떻게 이 가격에?", "이게 말이 돼?"
- 감탄: "완전 미쳤어!", "레전드 아니야?", "이거 진짜잖아!", "대박이잖아!"
- 맛 표현: "너무 맛있어!", "이 맛 실화야?", "입에서 살살 녹아!", "한 입 먹어봐"
- 공간/분위기: "분위기 미쳤어!", "여기 감성 봐봐", "뭔데 이 감성이야?"
- 엔딩: "저장해봐!", "팔로우 안 하면 손해야!", "다음에 또 와야겠어!"
- 절대 쓰면 안 되는 표현: "따뜻한 햇살", "정성 가득", "편안한 공간", "특별한 경험", "아늑한", "여유로운"

## 작성 규칙
1. food_type: 이 매장의 핵심 음식/서비스를 한 줄로 (예: "무한리필 초밥 뷔페", "수제 디저트 카페", "한우 소고기 구이")
   - 매장명이 아닌 음식 종류+특징으로 작성, 10자 이내
2. hook_candidates: 첫 장면에 쓸 후킹 멘트 10개 (시청자를 즉시 사로잡는 짧고 강렬한 문장)
   - 질문형, 감탄형, 충격형 등 다양하게
   - 반드시 15자 이내
   - 예시: "이거 실화임?", "여기 미쳤다", "이 가격에 이게 돼?"
3. 각 장면의 narration: 반드시 해당 장면에 보이는 것(음식, 공간, 분위기 등)을 직접 언급
   - 장면N의 narration은 반드시 장면N의 핵심요소/묘사를 기반으로 작성
   - 화면 자막으로도 쓰이므로 반드시 15자 이내 짧고 간결한 한 문장
   - TTS로 자연스럽게 읽혀야 함
   - 반드시 MZ 말투로 작성
4. bgm_mood: 배경음악 분위기 (energetic, calm, warm, trendy, elegant 중 하나)
5. 장면당 약 {duration_per_scene}초, 전체 {self.target_duration}초 목표
6. ending_candidates: 마지막 장면에 쓸 엔딩 멘트 10개 (팔로우/저장 유도, 또는 여운 남기는 문장)
   - 반드시 15자 이내
   - 예시: "저장 필수!", "팔로우 안 하면 손해", "다음 영상도 기대해줘요!"

아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요.

{{
  "food_type": "무한리필 초밥 뷔페",
  "bgm_mood": "warm",
  "hook_candidates": [
    "후킹멘트1", "후킹멘트2", "후킹멘트3", "후킹멘트4", "후킹멘트5",
    "후킹멘트6", "후킹멘트7", "후킹멘트8", "후킹멘트9", "후킹멘트10"
  ],
  "ending_candidates": [
    "엔딩멘트1", "엔딩멘트2", "엔딩멘트3", "엔딩멘트4", "엔딩멘트5",
    "엔딩멘트6", "엔딩멘트7", "엔딩멘트8", "엔딩멘트9", "엔딩멘트10"
  ],
  "scenes": [
    {{
      "scene_index": 1,
      "narration": "15자 이내 짧은 문장",
      "duration": {duration_per_scene}
    }}
  ]
}}"""

        response_text = self._llm_generate(prompt)
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
                narration = f"{analysis.store_name} 방문해봐!"
            elif scene.scene_type == "food":
                narration = "이 맛 실화야?"
            elif scene.scene_type == "interior":
                narration = "분위기 미쳤어!"
            else:
                narration = "여기 레전드잖아!"

            scenes.append({
                "scene_index": i + 1,
                "narration": narration,
                "duration": duration_per_scene,
            })

        return {
            "bgm_mood": "warm",
            "scenes": scenes,
        }

    def _build_storyboard(self, data: dict, analysis: StoreAnalysis) -> Storyboard:
        """JSON 데이터 → Storyboard 객체 변환 + 타이밍 계산"""
        scenes: list[SceneScript] = []
        current_time = 0.0

        raw_scenes = data.get("scenes", [])

        for i, raw in enumerate(raw_scenes):
            image_idx = min(i, len(analysis.scenes) - 1)
            image_path = analysis.scenes[image_idx].image_path

            duration = float(raw.get("duration", 4.0))
            duration = max(2.0, min(8.0, duration))

            narration = raw.get("narration", "")
            scene = SceneScript(
                scene_index=raw.get("scene_index", i + 1),
                image_path=image_path,
                narration=narration,
                subtitle=narration,
                duration=duration,
                start_time=current_time,
                effect=raw.get("effect", "ken_burns"),
                transition=raw.get("transition", "crossfade"),
            )
            scenes.append(scene)
            current_time += duration

        # 후킹 멘트 처리: 바이럴 점수 기반 상위 3개 중 선택
        hook_candidates = data.get("hook_candidates", [])
        if hook_candidates and scenes:
            try:
                from crol.recommend.scorer import pick_best_hook, score_hook_candidates
                scored_hooks = score_hook_candidates(hook_candidates)
                print(f"[릴몽] 후킹 점수 TOP3: {[(h, round(s,2)) for h, s in scored_hooks[:3]]}")
                selected_hook = pick_best_hook(hook_candidates, top_k=3)
            except Exception:
                selected_hook = random.choice(hook_candidates)
            scenes[0].narration = selected_hook
            scenes[0].subtitle  = selected_hook
            print(f"[릴몽] 선택된 후킹 멘트: {selected_hook}")

        # 엔딩 멘트 처리: 바이럴 점수 기반 상위 3개 중 선택
        ending_candidates = data.get("ending_candidates", [])
        if ending_candidates and len(scenes) > 1:
            try:
                from crol.recommend.scorer import pick_best_hook
                selected_ending = pick_best_hook(ending_candidates, top_k=3)
            except Exception:
                selected_ending = random.choice(ending_candidates)
            scenes[-1].narration = selected_ending
            scenes[-1].subtitle  = selected_ending
            print(f"[릴몽] 선택된 엔딩 멘트: {selected_ending}")

        full_text = " ".join(s.narration for s in scenes if s.narration)
        food_type = data.get("food_type", "").strip() or analysis.category

        storyboard = Storyboard(
            store_name=analysis.store_name,
            category=analysis.category,
            food_type=food_type,
            total_duration=current_time,
            scenes=scenes,
            bgm_mood=data.get("bgm_mood", "warm"),
            script_full_text=full_text,
            hook_candidates=hook_candidates,
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
