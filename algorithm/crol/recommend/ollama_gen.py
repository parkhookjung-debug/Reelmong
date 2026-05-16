"""
AI LLM 연동 — 대본 + DB 트렌드 기반 제목/태그 생성 (OpenRouter 버전)

Gemini LLM (google/gemini-2.5-flash) via OpenRouter
- JSON 구조화 출력
- 트렌드 참고 데이터 활용
- 생성 실패 시 단계별 fallback
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from crol_config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

from openai import OpenAI


def _get_client() -> OpenAI:
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )


def _call_llm(prompt: str, temperature: float = 0.7) -> str | None:
    """Gemini LLM API 호출 (OpenRouter)"""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ai] 오류: {e}")
        return None


def _parse_json_response(text: str) -> dict | None:
    """JSON 구조화 응답 파싱 (마크다운 코드블록 포함 대응)"""
    if not text:
        return None
    text = text.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if start != end:
            block = text[start:end + 3].split("\n")
            text = "\n".join(block[1:-1])
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
    return None


def _build_prompt(script: str, food_type: str, info: dict, patterns: dict) -> str:
    """구조화 JSON 출력 요청 프롬프트"""
    ref_titles = "\n".join(f"  - {t}" for t in patterns.get("titles", [])[:8])
    ref_hashtags = " ".join(f"#{h}" for h in patterns.get("top_hashtags", [])[:12])
    location = info.get("location") or "서울"
    moods = ", ".join(info.get("moods", [])[:3]) or "일반"
    food_category = info.get("food_category", "기타")
    kw_scores = info.get("keyword_scores", {})
    top_keywords = ", ".join(list(kw_scores.keys())[:6]) if kw_scores else ""

    return f"""당신은 한국 유튜브 음식 숏폼 콘텐츠 전문가입니다.
아래 정보를 바탕으로 조회수가 높을 유튜브 제목 5개와 해시태그 15개를 JSON으로 추천하세요.

[영상 대본 요약]
{script[:400]}

[음식 정보]
- 음식 종류: {food_type}
- 카테고리: {food_category}
- 촬영 장소: {location}
- 분위기 키워드: {moods}
- 핵심 키워드: {top_keywords}

[현재 트렌드 참고 제목 (실제 인기 숏폼)]
{ref_titles if ref_titles else "  (데이터 없음)"}

[현재 인기 해시태그]
{ref_hashtags if ref_hashtags else "(데이터 없음)"}

[제목 작성 규칙]
- 클릭 욕구를 자극하는 후킹형/반전형/공감형 제목
- MZ세대 말투 ("실화야?", "미쳤다", "레전드", "반칙이다" 등)
- 이모지/특수문자 금지
- 25자 이내
- 매장명 대신 음식 종류+특징 위주

[해시태그 규칙]
- # 포함
- 음식명, 장소, 분위기, 트렌드 혼합
- 조회수 높은 태그 위주

반드시 아래 JSON 형식으로만 응답하세요:

{{
  "titles": [
    "제목1",
    "제목2",
    "제목3",
    "제목4",
    "제목5"
  ],
  "hashtags": [
    "#태그1", "#태그2", "#태그3", "#태그4", "#태그5",
    "#태그6", "#태그7", "#태그8", "#태그9", "#태그10",
    "#태그11", "#태그12", "#태그13", "#태그14", "#태그15"
  ]
}}"""


def generate(script: str, food_type: str, info: dict, patterns: dict) -> dict:
    """
    Gemini LLM으로 제목 + 해시태그 생성 (JSON 구조화 출력)

    반환: {"titles": [...], "hashtags": [...]}
    """
    print(f"[ai] {OLLAMA_MODEL} 로 생성 중...")
    prompt = _build_prompt(script, food_type, info, patterns)
    response = _call_llm(prompt, temperature=0.7)

    if not response:
        print("[ai] 생성 실패")
        return {"titles": [], "hashtags": []}

    result = _parse_json_response(response)
    if result and "titles" in result:
        titles = [t for t in result.get("titles", []) if isinstance(t, str)][:5]
        hashtags = [h if h.startswith("#") else f"#{h}"
                    for h in result.get("hashtags", []) if isinstance(h, str)][:15]
        print(f"[ai] 제목 {len(titles)}개, 해시태그 {len(hashtags)}개 생성 (JSON)")
        return {"titles": titles, "hashtags": hashtags}

    # JSON 파싱 실패 시 텍스트 파싱 fallback
    print("[ai] JSON 파싱 실패 → 텍스트 파싱 fallback")
    titles, hashtags = [], []
    for line in response.splitlines():
        line = line.strip()
        if line.startswith("제목") and ":" in line:
            t = line.split(":", 1)[1].strip().strip('"').strip("'")
            if t:
                titles.append(t)
        elif line.startswith("해시태그:"):
            raw = line.split(":", 1)[1].strip()
            hashtags = [h.strip() for h in raw.split() if h.startswith("#")]
        elif line.startswith("#") and len(line) > 1:
            hashtags.extend(h for h in line.split() if h.startswith("#"))

    print(f"[ai] 제목 {len(titles[:5])}개, 해시태그 {len(hashtags[:15])}개 생성 (text)")
    return {"titles": titles[:5], "hashtags": hashtags[:15]}


def check_connection() -> bool:
    """OpenRouter 연결 및 API 키 확인"""
    try:
        client = _get_client()
        # 간단한 테스트 요청
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        print(f"[ai] OpenRouter 연결 성공 | 모델: {OLLAMA_MODEL}")
        return True
    except Exception as e:
        print(f"[ai] OpenRouter 연결 실패: {e}")
        print("    → .env 파일에 OPENROUTER_API_KEY 가 설정되어 있는지 확인하세요.")
        return False
