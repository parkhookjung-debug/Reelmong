"""STEP 5 실행 스크립트 - 품질 평가

STEP 4에서 생성된 영상의 품질을 종합 평가합니다.
- 해상도, FPS, 파일 크기, 비트레이트
- 영상 길이 적합성 (15~30초)
- 오디오 동기화
- 장면 구성 검증
- 100점 만점 종합 점수 + S/A/B/C/D 등급

사용법:
  python run_step5.py
  python run_step5.py --video data/output/step4_final_video.mp4
"""
import sys
import io
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import OUTPUT_DIR
from src.step5_eval.evaluator import VideoEvaluator


def main():
    parser = argparse.ArgumentParser(description="릴몽 STEP 5: 품질 평가")
    parser.add_argument(
        "--video",
        default=str(OUTPUT_DIR / "step4_final_video.mp4"),
        help="평가할 영상 경로",
    )
    parser.add_argument(
        "--storyboard",
        default=str(OUTPUT_DIR / "step2_storyboard.json"),
        help="스토리보드 JSON 경로 (선택)",
    )
    parser.add_argument(
        "--audio",
        default=str(OUTPUT_DIR / "step3_final_audio.mp3"),
        help="원본 오디오 경로 (선택)",
    )
    args = parser.parse_args()

    video_path = Path(args.video)
    storyboard_path = Path(args.storyboard)
    audio_path = Path(args.audio)

    print("=" * 50)
    print("  릴몽 STEP 5: 품질 평가")
    print("  (숏폼 영상 종합 품질 분석)")
    print("=" * 50)
    print()

    # 영상 확인
    if not video_path.exists():
        print(f"[!] 영상 파일을 찾을 수 없습니다: {video_path}")
        print("    → 먼저 'python run_step4.py'를 실행해주세요.")
        return

    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"[v] 평가 대상: {video_path.name} ({file_size_mb:.1f} MB)")
    print()

    # 평가 실행
    print("[*] 품질 분석 중...")
    evaluator = VideoEvaluator()

    result = evaluator.evaluate(
        video_path=str(video_path),
        storyboard_path=str(storyboard_path) if storyboard_path.exists() else "",
        audio_path=str(audio_path) if audio_path.exists() else "",
    )

    # 결과 출력
    print()
    print("-" * 50)
    print(f"  종합 평가: {result.grade} 등급 ({result.total_score:.1f}점/100점)")
    print("-" * 50)
    print()

    # 항목별 결과
    print("[항목별 평가]")
    for metric in result.metrics:
        status = "v" if metric.passed else "x"
        bar_len = int(metric.score / metric.max_score * 10)
        bar = "#" * bar_len + "-" * (10 - bar_len)
        print(f"  [{status}] {metric.name:<10} [{bar}] {metric.score:.1f}/{metric.max_score:.1f}  {metric.detail}")
    print()

    # 요약
    print(f"[요약] {result.summary}")
    print()

    # 권장사항
    if result.recommendations:
        print("[개선 권장사항]")
        for i, rec in enumerate(result.recommendations, 1):
            print(f"  {i}. {rec}")
        print()

    # 결과 저장
    result_path = OUTPUT_DIR / "step5_eval_result.json"
    result.save(str(result_path))
    print(f"[v] 평가 결과 저장: {result_path.name}")
    print()

    # 파이프라인 완료 메시지
    print("=" * 50)
    print("  릴몽 전체 파이프라인 완료!")
    print("=" * 50)
    print()
    print("  STEP 1: 이미지 분석     → step1_result.json")
    print("  STEP 2: 스토리보드 생성  → step2_storyboard.json")
    print("  STEP 3: 오디오 합성     → step3_final_audio.mp3")
    print("  STEP 4: 비디오 렌더링   → step4_final_video.mp4")
    print("  STEP 5: 품질 평가       → step5_eval_result.json")
    print()

    if result.grade in ("S", "A"):
        print("  영상이 업로드 준비 완료되었습니다!")
    else:
        print("  권장사항을 참고하여 품질을 개선해보세요.")


if __name__ == "__main__":
    main()
