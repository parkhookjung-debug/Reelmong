"""STEP 4 실행 스크립트 - 비디오 렌더링

data/images/ 폴더의 영상 클립(0~9번)을 순서대로 연결하여 최종 MP4를 생성합니다.
- 영상 클립 순서대로 연결
- 나레이션 자막 오버레이 (화면 중앙)
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

from config.settings import OUTPUT_DIR, IMAGES_DIR, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
from src.step4_video.renderer import VideoRenderer, _find_video_files


def main():
    parser = argparse.ArgumentParser(description="릴몽 STEP 4: 비디오 렌더링")
    parser.add_argument("--storyboard", default=str(OUTPUT_DIR / "step2_storyboard.json"))
    parser.add_argument("--audio",      default=str(OUTPUT_DIR / "step3_final_audio.mp3"))
    parser.add_argument("--videos",     default=str(IMAGES_DIR))
    parser.add_argument("--output",     default=str(OUTPUT_DIR / "step4_final_video.mp4"))
    args = parser.parse_args()

    storyboard_path = Path(args.storyboard)
    audio_path      = Path(args.audio)
    videos_dir      = Path(args.videos)
    output_path     = Path(args.output)

    print("=" * 50)
    print("  릴몽 STEP 4: 비디오 렌더링")
    print("  (영상 클립 연결 방식)")
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
    scenes     = storyboard.get("scenes", [])

    print(f"[v] 스토리보드 로드 완료")
    print(f"    매장: {store_name}")
    print(f"    장면(나레이션) 수: {len(scenes)}개")
    print(f"    해상도: {VIDEO_WIDTH}x{VIDEO_HEIGHT} (9:16)")
    print(f"    FPS: {VIDEO_FPS}")
    print()

    # 2) 영상 클립 확인
    print("[*] 영상 클립 확인 중...")
    video_files = _find_video_files(str(videos_dir))

    if not video_files:
        print(f"[!] {videos_dir} 에 mp4 파일이 없습니다.")
        return

    for i, vf in enumerate(video_files):
        narration = scenes[i].get("narration", "(나레이션 없음)") if i < len(scenes) else "(나레이션 없음)"
        print(f"    [{i}] {vf.name}  →  {narration}")

    print(f"    → 총 {len(video_files)}개 클립")
    print()

    # 3) 오디오 확인
    if audio_path.exists():
        print(f"[v] 오디오 파일 확인: {audio_path.name}")
    else:
        print(f"[!] 오디오 파일이 없습니다: {audio_path}")
        print("    → 오디오 없이 무음 영상으로 렌더링합니다.")
    print()

    # 4) 나레이션 타이밍 로드 (step3에서 생성)
    narr_timings = None
    narr_timings_path = OUTPUT_DIR / "step3_narr_timings.json"
    if narr_timings_path.exists():
        with open(narr_timings_path, "r", encoding="utf-8") as f:
            narr_timings = json.load(f)
        print(f"[v] 나레이션 타이밍 로드: {len(narr_timings)}개")
        for t in narr_timings:
            print(f"    [장면 {t['scene_index']}] 시작 {t['start']:.2f}s  길이 {t['duration']:.2f}s  끝 {t['start']+t['duration']:.2f}s")
        print()
    else:
        print("[!] step3_narr_timings.json 없음 → 클립별 자막 방식 사용")
        print()

    # 5) 렌더링
    print("[*] 비디오 렌더링 시작...")
    print(f"    출력: {output_path}")
    print()

    renderer = VideoRenderer(width=VIDEO_WIDTH, height=VIDEO_HEIGHT, fps=VIDEO_FPS)

    result_path = renderer.render(
        storyboard=storyboard,
        audio_path=str(audio_path) if audio_path.exists() else "",
        output_path=str(output_path),
        videos_dir=str(videos_dir),
        narr_timings=narr_timings,
    )

    if result_path and Path(result_path).exists():
        file_size_mb = Path(result_path).stat().st_size / (1024 * 1024)
        print()
        print("[v] STEP 4 완료!")
        print(f"    → {output_path.name} ({file_size_mb:.1f} MB)")
        print(f"    → 해상도: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
        print(f"    → FPS: {VIDEO_FPS}")
        print()
        print("    다음: python run_step5.py  (제목/태그 추천)")
    else:
        print()
        print("[!] 비디오 렌더링에 실패했습니다.")


if __name__ == "__main__":
    main()
