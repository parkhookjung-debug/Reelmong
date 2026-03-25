"""STEP 4 실행 스크립트 - 비디오 렌더링

STEP 2 결과(스토리보드) + STEP 3 결과(오디오)를 합성하여 최종 MP4 영상을 생성합니다.
- 장면별 이미지에 영상 효과(Ken Burns, 줌, 페이드 등) 적용
- 자막 오버레이
- 오프닝 후크 + 클로징 CTA 표시
- 최종 오디오(TTS + BGM) 합성

사용법:
  python run_step4.py
  python run_step4.py --storyboard data/output/step2_storyboard.json --audio data/output/step3_final_audio.mp3
"""
import sys
import io
import json
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
from src.step4_video.renderer import VideoRenderer


def main():
    parser = argparse.ArgumentParser(description="릴몽 STEP 4: 비디오 렌더링")
    parser.add_argument(
        "--storyboard",
        default=str(OUTPUT_DIR / "step2_storyboard.json"),
        help="STEP 2 스토리보드 JSON 경로",
    )
    parser.add_argument(
        "--audio",
        default=str(OUTPUT_DIR / "step3_final_audio.mp3"),
        help="STEP 3 최종 오디오 경로",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "step4_final_video.mp4"),
        help="출력 비디오 경로",
    )
    args = parser.parse_args()

    storyboard_path = Path(args.storyboard)
    audio_path = Path(args.audio)
    output_path = Path(args.output)

    print("=" * 50)
    print("  릴몽 STEP 4: 비디오 렌더링")
    print("  (MoviePy 기반 숏폼 영상 생성)")
    print("=" * 50)
    print()

    # 1) 스토리보드 로드
    if not storyboard_path.exists():
        print(f"[!] 스토리보드 파일을 찾을 수 없습니다: {storyboard_path}")
        print("    → 먼저 'python run_step2.py'를 실행해주세요.")
        return

    with open(storyboard_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    store_name = storyboard.get("store_name", "")
    scenes = storyboard.get("scenes", [])
    total_duration = storyboard.get("total_duration", 30)

    print(f"[v] 스토리보드 로드 완료")
    print(f"    매장: {store_name}")
    print(f"    장면 수: {len(scenes)}개")
    print(f"    총 길이: {total_duration}초")
    print(f"    해상도: {VIDEO_WIDTH}x{VIDEO_HEIGHT} (9:16)")
    print(f"    FPS: {VIDEO_FPS}")
    print()

    # 2) 이미지 파일 확인
    print("[*] 이미지 파일 확인 중...")
    valid_scenes = 0
    for scene in scenes:
        img_path = scene.get("image_path", "")
        exists = Path(img_path).exists() if img_path else False
        status = "v" if exists else "x"
        effect = scene.get("effect", "ken_burns")
        print(f"    [{status}] 장면 {scene.get('scene_index', '?')}: {Path(img_path).name if img_path else '없음'} ({effect})")
        if exists:
            valid_scenes += 1

    if valid_scenes == 0:
        print()
        print("[!] 유효한 이미지가 없습니다. data/images/ 폴더에 이미지를 넣어주세요.")
        return

    print(f"    → 유효 이미지: {valid_scenes}/{len(scenes)}개")
    print()

    # 3) 오디오 확인
    if audio_path.exists():
        print(f"[v] 오디오 파일 확인: {audio_path.name}")
    else:
        print(f"[!] 오디오 파일이 없습니다: {audio_path}")
        print("    → 먼저 'python run_step3.py'를 실행해주세요.")
        print("    → 오디오 없이 무음 영상으로 렌더링합니다.")
    print()

    # 4) 렌더링
    print("[*] 비디오 렌더링 시작...")
    print(f"    출력: {output_path}")
    print()

    renderer = VideoRenderer(
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
        fps=VIDEO_FPS,
    )

    result_path = renderer.render(
        storyboard=storyboard,
        audio_path=str(audio_path) if audio_path.exists() else "",
        output_path=str(output_path),
    )

    if result_path and Path(result_path).exists():
        file_size_mb = Path(result_path).stat().st_size / (1024 * 1024)
        print()
        print("[v] STEP 4 완료!")
        print(f"    → {output_path.name} ({file_size_mb:.1f} MB)")
        print(f"    → 해상도: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
        print(f"    → FPS: {VIDEO_FPS}")
        print()
        print("    다음: STEP 5 (품질 평가)에서 영상 품질을 분석합니다.")
    else:
        print()
        print("[!] 비디오 렌더링에 실패했습니다.")


if __name__ == "__main__":
    main()
