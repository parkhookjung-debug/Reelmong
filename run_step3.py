"""STEP 3 실행 스크립트 - 오디오 합성 (TTS + BGM)

STEP 2 결과(step2_storyboard.json)를 읽어서:
1. 장면별 나레이션 음성 생성 (Edge TTS, 무료)
2. 분위기에 맞는 BGM 자동 선택
3. TTS + BGM 믹싱 → 최종 오디오 트랙

사용법:
  python run_step3.py
  python run_step3.py --input data/output/step2_storyboard.json
"""
import sys
import io
import json
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import OUTPUT_DIR, DATA_DIR
from src.step3_audio.tts import TTSGenerator
from src.step3_audio.bgm import BGMManager
from src.step3_audio.mixer import AudioMixer


def main():
    parser = argparse.ArgumentParser(description="릴몽 STEP 3: 오디오 합성")
    parser.add_argument(
        "--input",
        default=str(OUTPUT_DIR / "step2_storyboard.json"),
        help="STEP 2 스토리보드 JSON 경로",
    )
    args = parser.parse_args()

    input_path = Path(args.input)

    print("=" * 50)
    print("  릴몽 STEP 3: 오디오 합성")
    print("  (Edge TTS + BGM 자동 매칭)")
    print("=" * 50)
    print()

    # 1) STEP 2 결과 로드
    if not input_path.exists():
        print(f"[!] STEP 2 결과 파일을 찾을 수 없습니다: {input_path}")
        print("    → 먼저 'python run_step2.py'를 실행해주세요.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    store_name = storyboard["store_name"]
    category = storyboard.get("category", "기타")
    bgm_mood = storyboard.get("bgm_mood", "warm")
    scenes = storyboard.get("scenes", [])
    total_duration = storyboard.get("total_duration", 30)

    print(f"[v] 스토리보드 로드 완료")
    print(f"    매장: {store_name}")
    print(f"    장면 수: {len(scenes)}개")
    print(f"    총 길이: {total_duration}초")
    print(f"    BGM 분위기: {bgm_mood}")
    print()

    # 2) TTS 생성 (장면별)
    print("[*] TTS 나레이션 생성 중...")
    tts = TTSGenerator.for_category(category)

    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    scene_audios = []
    for scene in scenes:
        idx = scene["scene_index"]
        narration = scene.get("narration", "")
        if not narration.strip():
            continue

        out_path = str(audio_dir / f"scene_{idx:02d}.mp3")
        print(f"    [TTS] 장면 {idx}: {narration[:30]}...")
        tts.generate(narration, out_path)

        scene_audios.append({
            "path": out_path,
            "start_ms": int(scene.get("start_time", 0) * 1000),
            "duration_ms": int(scene.get("duration", 5) * 1000),
            "scene_index": idx,
        })

    print(f"[v] TTS 완료: {len(scene_audios)}개 음성 파일 생성")
    print()

    # 3) BGM 선택
    print("[*] BGM 매칭 중...")
    bgm_manager = BGMManager()
    print(f"    {bgm_manager.get_status()}")
    print()

    bgm_path = bgm_manager.select_bgm(mood=bgm_mood, category=category)
    if bgm_path:
        print(f"[v] BGM 선택: {Path(bgm_path).name}")
    else:
        print("[!] BGM 파일이 없습니다. 나레이션만으로 오디오를 생성합니다.")
        print(f"    → data/bgm/{bgm_mood}/ 폴더에 MP3 파일을 넣으면 자동 매칭됩니다.")
    print()

    # 4) 믹싱
    print("[*] 오디오 믹싱 중...")
    mixer = AudioMixer()

    total_duration_ms = int(total_duration * 1000)
    final_audio_path = str(OUTPUT_DIR / "step3_final_audio.mp3")

    mixer.mix(
        scene_audio_paths=scene_audios,
        bgm_path=bgm_path,
        total_duration_ms=total_duration_ms,
        output_path=final_audio_path,
    )

    print(f"[v] 최종 오디오 저장: {final_audio_path}")
    print()

    # 5) 전체 나레이션 단일 파일도 생성 (백업)
    full_narration = storyboard.get("script_full_text", "")
    if full_narration:
        full_narration_path = str(audio_dir / "full_narration.mp3")
        print("[*] 전체 나레이션 단일 파일 생성 중...")
        tts.generate(full_narration, full_narration_path)
        print(f"[v] 전체 나레이션: {full_narration_path}")

    print()
    print("[v] STEP 3 완료!")
    print(f"    → step3_final_audio.mp3  : 최종 오디오 (TTS + BGM)")
    print(f"    → audio/scene_XX.mp3     : 장면별 TTS 파일")
    print(f"    → audio/full_narration.mp3 : 전체 나레이션")
    print()
    print("    다음: STEP 4 (비디오 렌더링)에서 이 오디오 + 이미지를 합성합니다.")


if __name__ == "__main__":
    main()
