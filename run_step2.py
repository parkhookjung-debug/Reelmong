"""STEP 2 실행 스크립트 - 스크립트/스토리보드 생성

STEP 1 결과(step1_result.json)를 읽어서 30초 릴스 대본을 생성합니다.

사용법:
  python run_step2.py
  python run_step2.py --input data/output/step1_result.json
"""
import sys
import io
import argparse
from pathlib import Path

# Windows 콘솔 인코딩 이슈 방지 (이모지 등)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import OUTPUT_DIR
from src.step2_script import ScriptGenerator


def main():
    parser = argparse.ArgumentParser(description="릴몽 STEP 2: 스크립트 생성")
    parser.add_argument(
        "--input",
        default=str(OUTPUT_DIR / "step1_result.json"),
        help="STEP 1 결과 JSON 경로",
    )
    args = parser.parse_args()

    input_path = Path(args.input)

    print("=" * 50)
    print("  릴몽 STEP 2: 스크립트/스토리보드 생성")
    print("  (Ollama 로컬 LLM)")
    print("=" * 50)
    print()

    # 1) STEP 1 결과 로드
    if not input_path.exists():
        print(f"[!] STEP 1 결과 파일을 찾을 수 없습니다: {input_path}")
        print("    → 먼저 'python run_step1.py'를 실행해주세요.")
        return

    print(f"[v] STEP 1 결과 로드: {input_path}")
    generator = ScriptGenerator()
    analysis = generator.load_analysis(str(input_path))

    print(f"    매장명: {analysis.store_name}")
    print(f"    업종: {analysis.category}")
    print(f"    장면 수: {len(analysis.scenes)}개")
    print()

    # 2) 스토리보드 생성
    storyboard = generator.generate(analysis)

    # 3) 결과 출력
    print()
    print("=" * 50)
    print("  생성된 스토리보드")
    print("=" * 50)
    print()
    print(f"  오프닝 후크: {storyboard.opening_hook}")
    print(f"  총 길이: {storyboard.total_duration:.1f}초")
    print(f"  BGM 분위기: {storyboard.bgm_mood}")
    print()

    for scene in storyboard.scenes:
        print(f"  [{scene.scene_index}] {scene.start_time:.1f}s ~ {scene.start_time + scene.duration:.1f}s ({scene.duration:.1f}초)")
        print(f"      나레이션: {scene.narration}")
        print(f"      자막: {scene.subtitle}")
        print(f"      효과: {scene.effect}")
        print()

    print(f"  클로징 CTA: {storyboard.closing_cta}")
    print()

    # 4) 결과 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 스토리보드 JSON
    json_path = OUTPUT_DIR / "step2_storyboard.json"
    storyboard.save(str(json_path))
    print(f"[v] 스토리보드 저장: {json_path}")

    # SRT 자막 파일
    srt_path = OUTPUT_DIR / "step2_subtitles.srt"
    storyboard.save_srt(str(srt_path))
    print(f"[v] 자막 저장: {srt_path}")

    # 전체 나레이션 텍스트 (TTS 입력용)
    narration_path = OUTPUT_DIR / "step2_narration.txt"
    with open(narration_path, "w", encoding="utf-8") as f:
        f.write(storyboard.script_full_text)
    print(f"[v] 나레이션 텍스트 저장: {narration_path}")

    print()
    print("[v] STEP 2 완료!")
    print("    → step2_storyboard.json  : STEP 3(오디오) + STEP 4(영상)의 입력")
    print("    → step2_subtitles.srt    : 영상 자막 파일")
    print("    → step2_narration.txt    : TTS 음성 합성용 텍스트")


if __name__ == "__main__":
    main()
