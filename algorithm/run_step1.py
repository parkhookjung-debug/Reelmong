"""STEP 1 실행 스크립트 - Vision 이미지 분석
#reelven\Scripts\activate
#python run_step2.py
#python run_step3.py
#python run_step4.py

사전 준비:
  1. pip install -r requirements.txt
  2. .env 파일에 OPENROUTER_API_KEY 설정
  3. data/images/ 폴더에 영상 파일(mp4) 넣기

사용법:
  python run_step1.py --name "매장 이름" --intro "매장 소개"

또는 대화형 모드:
  python run_step1.py
"""
import sys
import io
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import IMAGES_DIR, OUTPUT_DIR
from src.step1_vision import ImageAnalyzer
from src.step4_video.renderer import _find_video_files


def extract_middle_frames(video_files: list[Path], frames_dir: Path) -> list[str]:
    """각 영상의 중간 프레임을 추출하여 이미지로 저장

    Returns:
        저장된 프레임 이미지 경로 목록
    """
    from moviepy import VideoFileClip
    from PIL import Image
    import numpy as np

    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_paths = []

    for i, video_path in enumerate(video_files):
        out_path = frames_dir / f"frame_{i:02d}.jpg"

        # 이미 추출된 프레임이 있으면 재사용
        if out_path.exists():
            print(f"    [프레임] {video_path.name} → {out_path.name} (캐시)")
            frame_paths.append(str(out_path))
            continue

        try:
            clip = VideoFileClip(str(video_path))
            mid_time = clip.duration / 2
            frame_array = clip.get_frame(mid_time)
            clip.close()

            img = Image.fromarray(frame_array.astype("uint8"))
            img.save(str(out_path), "JPEG", quality=90)
            print(f"    [프레임] {video_path.name} → {out_path.name} ({mid_time:.1f}초 지점)")
            frame_paths.append(str(out_path))

        except Exception as e:
            print(f"    [!] {video_path.name} 프레임 추출 실패: {e}")

    return frame_paths


def check_openrouter():
    """OpenRouter API 키 확인"""
    from config.settings import OPENROUTER_API_KEY
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        print("[X] OPENROUTER_API_KEY 가 설정되지 않았습니다!")
        print("    1. .env.example 을 복사하여 .env 파일 생성")
        print("    2. OPENROUTER_API_KEY=your_key_here 입력")
        print("    3. https://openrouter.ai/settings/keys 에서 키 발급")
        return False
    print(f"[v] OpenRouter API 키 확인 OK")
    return True


def interactive_mode():
    """대화형 모드"""
    print("=" * 50)
    print("  릴몽 STEP 1: Vision 이미지 분석")
    print("  (영상 중간 프레임 추출 → Gemini Vision)")
    print("=" * 50)
    print()

    if not check_openrouter():
        return

    # 영상 파일 탐색
    video_files = _find_video_files(str(IMAGES_DIR))
    if not video_files:
        print(f"\n[!] data/images 폴더에 mp4 영상이 없습니다.")
        print(f"    → {IMAGES_DIR} 에 영상 파일을 넣어주세요.")
        return

    print(f"\n[v] 발견된 영상 {len(video_files)}개:")
    for i, vf in enumerate(video_files):
        print(f"    {i}. {vf.name}")
    print()

    store_name = input("매장 이름: ").strip() or "테스트 매장"
    store_intro = input("매장 소개 (1~3문장): ").strip() or "맛있는 음식을 제공하는 매장입니다"
    category = input("업종 (빈칸=자동판별): ").strip()

    print()
    print("[*] 영상에서 중간 프레임 추출 중...")
    frames_dir = OUTPUT_DIR / "frames"
    frame_paths = extract_middle_frames(video_files, frames_dir)

    if not frame_paths:
        print("[!] 프레임 추출에 실패했습니다.")
        return

    print(f"[v] 프레임 추출 완료: {len(frame_paths)}개")
    print()
    print("[*] 이미지 분석 시작...")
    print("    (Gemini Vision API 호출)")
    print()

    analyzer = ImageAnalyzer()
    result = analyzer.analyze_store(
        image_paths=frame_paths,
        store_name=store_name,
        store_intro=store_intro,
        category=category,
    )

    print()
    print("=" * 50)
    print("  분석 결과")
    print("=" * 50)
    print(result.to_json())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "step1_result.json"
    result.save(str(output_path))
    print(f"\n[v] 결과 저장: {output_path}")
    print("[v] STEP 1 완료! → 이 JSON이 STEP 2 (스크립트 생성)의 입력이 됩니다.")


def cli_mode(args):
    """CLI 인자 모드"""
    if not check_openrouter():
        return

    video_files = _find_video_files(str(IMAGES_DIR))
    if not video_files:
        print(f"[!] data/images 폴더에 mp4 영상이 없습니다.")
        return

    print(f"[v] 발견된 영상 {len(video_files)}개")
    print("[*] 영상에서 중간 프레임 추출 중...")

    frames_dir = OUTPUT_DIR / "frames"
    frame_paths = extract_middle_frames(video_files, frames_dir)

    if not frame_paths:
        print("[!] 프레임 추출에 실패했습니다.")
        return

    print(f"[v] 프레임 추출 완료: {len(frame_paths)}개")
    print("[*] 이미지 분석 시작...")

    analyzer = ImageAnalyzer()
    result = analyzer.analyze_store(
        image_paths=frame_paths,
        store_name=args.name,
        store_intro=args.intro,
        category=args.category or "",
    )

    print(result.to_json())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "step1_result.json"
    result.save(str(output_path))
    print(f"\n[v] 결과 저장: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="릴몽 STEP 1: Vision 이미지 분석")
    parser.add_argument("--name", default="", help="매장 이름")
    parser.add_argument("--intro", default="맛있는 음식을 제공합니다", help="매장 소개")
    parser.add_argument("--category", default="", help="업종 카테고리")

    args = parser.parse_args()

    if args.name:
        cli_mode(args)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
