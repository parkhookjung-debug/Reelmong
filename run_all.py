"""맛노래 - 음식이 노래하는 숏폼 영상 생성기

음식 사진 한 장을 넣으면:
1. AI가 음식을 분석하고
2. 음식이 1인칭으로 부르는 가사를 만들고
3. 한국어 음성으로 합성하고
4. 음식 위에 카툰 얼굴을 그려서
5. 오디오에 맞춰 입을 움직이는 영상을 만듭니다

사전 준비:
  pip install -r requirements.txt
  ollama pull gemma3:4b
  ollama serve

사용법:
  python run_all.py                              # 대화형 모드
  python run_all.py --image data/input/food.jpg  # CLI 모드
"""
import sys
import io
import json
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import INPUT_DIR, OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, SUPPORTED_FORMATS


def check_ollama():
    """Ollama 서버 상태 확인"""
    import requests
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"[v] Ollama 서버 연결 OK")
        print(f"    설치된 모델: {', '.join(models) if models else '없음'}")
        return True
    except Exception:
        print("[X] Ollama 서버에 연결할 수 없습니다!")
        print("    1. Ollama 설치: https://ollama.com")
        print("    2. 서버 실행: ollama serve")
        print("    3. 모델 설치: ollama pull gemma3:4b")
        return False


def find_input_images() -> list[str]:
    """data/input 폴더에서 이미지 자동 탐색"""
    images = []
    if INPUT_DIR.exists():
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            images.extend(str(p) for p in INPUT_DIR.glob(ext))
    return sorted(images)


def main():
    parser = argparse.ArgumentParser(description="맛노래 - 음식이 노래하는 숏폼 생성기")
    parser.add_argument("--image", help="음식 이미지 경로")
    args = parser.parse_args()

    print()
    print("=" * 50)
    print("  맛노래 - 음식이 노래하는 숏폼 영상 생성기")
    print("  (BLIP + Ollama + Edge TTS + MoviePy)")
    print("  모든 모델 무료 로컬 실행")
    print("=" * 50)
    print()

    # 0) Ollama 확인
    if not check_ollama():
        return
    print()

    # 이미지 선택
    if args.image:
        image_path = args.image
    else:
        images = find_input_images()
        if not images:
            print(f"[!] data/input 폴더에 이미지가 없습니다.")
            print(f"    -> {INPUT_DIR} 에 음식 사진을 넣어주세요.")
            print(f"    지원 형식: {', '.join(SUPPORTED_FORMATS)}")
            return

        print(f"[v] 발견된 이미지 {len(images)}장:")
        for i, img in enumerate(images, 1):
            print(f"    {i}. {Path(img).name}")

        choice = input("\n사용할 이미지 번호 (엔터=1): ").strip()
        idx = int(choice) - 1 if choice.isdigit() else 0
        idx = max(0, min(idx, len(images) - 1))
        image_path = images[idx]

    print(f"\n[v] 선택된 이미지: {Path(image_path).name}")
    print()

    # ─── STEP 1: 음식 분석 ────────────────────────────
    print("=" * 40)
    print("  STEP 1: 음식 이미지 분석")
    print("=" * 40)

    from src.step1_analyze import FoodAnalyzer
    analyzer = FoodAnalyzer()
    analysis = analyzer.analyze(image_path)

    print(f"\n    음식: {analysis.food_name}")
    print(f"    카테고리: {analysis.category}")
    print(f"    성격: {analysis.personality}")
    print(f"    묘사: {analysis.description}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    analysis.save(str(OUTPUT_DIR / "step1_analysis.json"))
    print(f"[v] STEP 1 완료!")
    print()

    # ─── STEP 2: 가사 생성 ────────────────────────────
    print("=" * 40)
    print("  STEP 2: 노래 가사 생성")
    print("=" * 40)

    from src.step2_lyrics import LyricsGenerator
    lyricist = LyricsGenerator()
    lyrics_data = lyricist.generate(analysis)

    print(f"\n    제목: {lyrics_data['title']}")
    print(f"    가사:")
    for line in lyrics_data["lyrics"]:
        print(f"      {line}")

    lyricist.save_lyrics(lyrics_data, str(OUTPUT_DIR / "step2_lyrics.json"))
    print(f"\n[v] STEP 2 완료!")
    print()

    # ─── STEP 3: 음성 합성 ────────────────────────────
    print("=" * 40)
    print("  STEP 3: 음성 합성 (Edge TTS)")
    print("=" * 40)

    from src.step3_voice import VoiceGenerator
    singer = VoiceGenerator()

    voice_dir = str(OUTPUT_DIR / "voice")
    voice_result = singer.generate_full_song(
        lyrics=lyrics_data["lyrics"],
        output_dir=voice_dir,
    )

    print(f"\n[v] STEP 3 완료!")
    print(f"    총 길이: {voice_result['total_duration_ms'] / 1000:.1f}초")
    print(f"    음성 파일: {voice_result['full_audio_path']}")
    print()

    # ─── STEP 3.5: 멜로디 생성 + 믹싱 ──────────────────
    print("=" * 40)
    print("  STEP 3.5: 멜로디 생성 (MusicGen)")
    print("=" * 40)

    from src.step3_voice import is_musicgen_available, AudioMixer

    final_audio_path = voice_result["full_audio_path"]  # 기본값: TTS만

    if is_musicgen_available():
        try:
            from src.step3_voice import MelodyGenerator
            melody_gen = MelodyGenerator()

            melody_duration = voice_result["total_duration_ms"] / 1000.0
            melody_path = str(OUTPUT_DIR / "voice" / "melody.wav")

            melody_gen.generate(
                category=analysis.category,
                duration_s=melody_duration,
                output_path=melody_path,
            )

            # TTS + 멜로디 믹싱
            print("\n[*] TTS + 멜로디 믹싱 중...")
            mixer = AudioMixer()
            final_audio_path = str(OUTPUT_DIR / "voice" / "final_mixed.mp3")

            mixer.mix(
                voice_path=voice_result["full_audio_path"],
                melody_path=melody_path,
                output_path=final_audio_path,
                voice_lines=voice_result["lines"],
            )

            print(f"[v] 멜로디 + 음성 믹싱 완료!")
            print(f"    최종 오디오: {Path(final_audio_path).name}")

        except Exception as e:
            print(f"[!] 멜로디 생성 실패: {e}")
            print("    → TTS 음성만으로 진행합니다.")
            final_audio_path = voice_result["full_audio_path"]
    else:
        print("[!] MusicGen 미설치 - TTS 음성만으로 진행합니다.")
        print("    → 멜로디 추가하려면: pip install transformers torch")
        print("    → MusicGen-small 모델이 자동 다운로드됩니다 (~300MB)")

    print()

    # ─── STEP 4+5: 애니메이션 + 렌더링 ─────────────────
    print("=" * 40)
    print("  STEP 4+5: 애니메이션 + 영상 렌더링")
    print("=" * 40)

    from src.step5_render import VideoRenderer
    renderer = VideoRenderer(
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
        fps=VIDEO_FPS,
    )

    output_video = str(OUTPUT_DIR / "singing_food.mp4")
    result_path = renderer.render(
        image_path=image_path,
        audio_path=final_audio_path,
        lyrics_lines=voice_result["lines"],
        title=lyrics_data["title"],
        output_path=output_video,
    )

    if result_path and Path(result_path).exists():
        file_size_mb = Path(result_path).stat().st_size / (1024 * 1024)
        print()
        print("=" * 50)
        print("  맛노래 완성!")
        print("=" * 50)
        print()
        print(f"  출력: {Path(result_path).name} ({file_size_mb:.1f} MB)")
        print(f"  해상도: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
        print(f"  노래 제목: {lyrics_data['title']}")
        print()
        print("  결과물:")
        print("    step1_analysis.json  - 음식 분석 결과")
        print("    step2_lyrics.json    - 노래 가사")
        print("    voice/               - 음성 파일들")
        print("    singing_food.mp4     - 최종 영상 (!)")
    else:
        print("\n[!] 영상 생성에 실패했습니다.")


if __name__ == "__main__":
    main()
