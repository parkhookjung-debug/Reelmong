"""STEP 5 실행 스크립트 - 제목 / 해시태그 추천

STEP 2에서 생성된 대본(step2_storyboard.json)을 바탕으로
유튜브 쇼츠·인스타 릴스에 최적화된 제목과 해시태그를 추천합니다.

추천 방식:
  1. 템플릿 기반 추천 (업종 + 장소 조합, 즉시 사용 가능)
  2. Gemini AI 추천 (대본 맥락 기반, google/gemini-2.5-flash)
  3. DB 인기 해시태그 (crol이 수집한 실제 쇼츠 데이터 기반)

사용법:
  python run_step5.py
  python run_step5.py --storyboard data/output/step2_storyboard.json
  python run_step5.py --no-ollama   # AI 추천 생략, 빠른 실행
"""
import sys
import io
import json
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / "crol"))  # crol은 뒤에 추가 (config 충돌 방지)

from config.settings import OUTPUT_DIR


def main():
    parser = argparse.ArgumentParser(description="릴몽 STEP 5: 제목/해시태그 추천")
    parser.add_argument(
        "--storyboard",
        default=str(OUTPUT_DIR / "step2_storyboard.json"),
        help="스토리보드 JSON 경로",
    )
    parser.add_argument(
        "--no-ollama",
        action="store_true",
        help="AI 추천 생략 (템플릿 + DB 기반만 사용)",
    )
    args = parser.parse_args()

    storyboard_path = Path(args.storyboard)
    use_ollama = not args.no_ollama

    print("=" * 50)
    print("  릴몽 STEP 5: 제목 / 해시태그 추천")
    print("=" * 50)
    print()

    # 1) 스토리보드 로드
    if not storyboard_path.exists():
        print(f"[!] 스토리보드 파일 없음: {storyboard_path}")
        print("    → 먼저 'python run_step2.py'를 실행해주세요.")
        return

    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    store_name = storyboard.get("store_name", "").strip()
    category   = storyboard.get("category", "기타").strip()
    # food_type: step2에서 LLM이 생성한 값 우선, 없으면 category로 fallback
    food_type  = storyboard.get("food_type", "").strip() or category
    script     = storyboard.get("script_full_text", "").strip()

    if not store_name:
        print("[!] 스토리보드에 매장명이 없습니다.")
        return
    if not script:
        print("[!] 스토리보드에 대본(script_full_text)이 없습니다.")
        return

    print(f"[v] 매장명 : {store_name}")
    print(f"[v] 업종   : {category}")
    print(f"[v] 음식   : {food_type}")
    print(f"[v] 대본   : {script}")
    print()

    # 2) crol 추천 엔진 로드
    try:
        from recommend.engine import run as crol_run, print_result as crol_print
    except ImportError as e:
        print(f"[!] 추천 엔진 로드 실패: {e}")
        print("    → pip install python-dotenv google-api-python-client 를 실행해주세요.")
        return

    # 3) 추천 실행
    print(f"[*] 추천 실행 중... (AI={'ON' if use_ollama else 'OFF'})")
    print()

    result = crol_run(
        script=script,
        food_type=food_type,
        use_ollama=use_ollama,
    )

    # 4) 결과 출력
    crol_print(result)

    # 5) 결과 저장
    output_path = OUTPUT_DIR / "step5_recommend.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[v] 추천 결과 저장: {output_path.name}")
    print()
    print("=" * 50)
    print("  STEP 5 완료!")
    print("=" * 50)
    print()
    print("  STEP 1: 이미지 분석     → step1_result.json")
    print("  STEP 2: 스토리보드 생성  → step2_storyboard.json")
    print("  STEP 3: 오디오 합성     → step3_final_audio.mp3")
    print("  STEP 4: 비디오 렌더링   → step4_final_video.mp4")
    print("  STEP 5: 제목/태그 추천  → step5_recommend.json  ✓")
    print()


if __name__ == "__main__":
    main()
