"""STEP 3 실행 스크립트 - 오디오 합성 (TTS + BGM)

STEP 2 결과(step2_storyboard.json)를 읽어서:
1. 장면별 나레이션 음성 생성 (Edge TTS, 무료)
2. 분위기에 맞는 BGM 자동 선택
3. TTS + BGM 믹싱 → 최종 오디오 트랙

타이밍: 실제 영상 클립 길이 기준, 화면 전환 후 0.3초 뒤 나레이션 시작

사용법:
  python run_step3.py
"""
import sys
import io
import json
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import OUTPUT_DIR, IMAGES_DIR
from src.step3_audio.tts import TTSGenerator
from src.step3_audio.bgm import BGMManager
from src.step3_audio.mixer import AudioMixer
from src.step4_video.renderer import _find_video_files

NARRATION_DELAY = 0.3  # 장면 전환 후 0.3초 뒤 나레이션 시작


def get_video_durations(videos_dir: str) -> list[float]:
    """실제 영상 클립 길이 목록 반환 (초)"""
    from moviepy import VideoFileClip
    video_files = _find_video_files(videos_dir)
    durations = []
    for vf in video_files:
        try:
            clip = VideoFileClip(str(vf))
            durations.append(clip.duration)
            clip.close()
        except Exception as e:
            print(f"    [!] {vf.name} 길이 읽기 실패: {e}")
            durations.append(3.0)
    return durations


def main():
    parser = argparse.ArgumentParser(description="릴몽 STEP 3: 오디오 합성")
    parser.add_argument("--input",  default=str(OUTPUT_DIR / "step2_storyboard.json"))
    parser.add_argument("--videos", default=str(IMAGES_DIR))
    args = parser.parse_args()

    input_path = Path(args.input)

    print("=" * 50)
    print("  릴몽 STEP 3: 오디오 합성")
    print("  (Edge TTS + BGM 자동 매칭)")
    print("=" * 50)
    print()

    if not input_path.exists():
        print(f"[!] STEP 2 결과 파일 없음: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        storyboard = json.load(f)

    store_name = storyboard["store_name"]
    category   = storyboard.get("category", "기타")
    bgm_mood   = storyboard.get("bgm_mood", "warm")
    scenes     = storyboard.get("scenes", [])

    print(f"[v] 스토리보드: {store_name} | 장면 {len(scenes)}개 | BGM: {bgm_mood}")
    print()

    # 1) 실제 영상 클립 길이 측정 → 타이밍 계산
    print("[*] 실제 영상 클립 길이 측정 중...")
    video_durations = get_video_durations(args.videos)
    total_duration  = sum(video_durations)

    actual_start_times = []
    t = 0.0
    for d in video_durations:
        actual_start_times.append(t)
        t += d

    print(f"    클립 {len(video_durations)}개 | 총 {total_duration:.2f}초")
    print()

    # 2) TTS 생성 + 큐 방식 타이밍 계산
    # 규칙:
    #   - 나레이션 시작 = max(장면 전환 시각 + 0.3s, 이전 나레이션 종료 시각)  → 겹침 방지
    #   - 영상 종료 시각을 초과하는 나레이션은 스킵 (엔딩멘트는 영상 끝에 맞춰 트림)
    print("[*] TTS 나레이션 생성 중...")
    tts       = TTSGenerator.for_category(category)
    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    scene_audios      = []
    total_duration_ms = int(total_duration * 1000)
    delay_ms          = int(NARRATION_DELAY * 1000)
    queue_end_ms      = 0   # 이전 나레이션이 끝나는 시각
    last_scene_idx    = len(scenes) - 1  # 엔딩멘트 = 마지막 장면

    import re as _re
    from pydub import AudioSegment

    def _clean_narration(text: str) -> str:
        """이모티콘·특수문자 제거, 공백 정리"""
        # 유니코드 이모지 제거 (기본 다국어 평면 밖 문자)
        text = _re.sub(r'[\U00010000-\U0010ffff]', '', text)
        # 기타 이모지/특수 심볼 범위 제거
        text = _re.sub(r'[\u2600-\u27BF\u2B00-\u2BFF\uFE00-\uFE0F]', '', text)
        return text.strip()

    for i, scene in enumerate(scenes):
        idx       = scene["scene_index"]
        narration = _clean_narration(scene.get("narration", ""))
        if not narration:
            continue

        if i >= len(actual_start_times):
            print(f"    [!] 장면 {idx}: 대응 영상 클립 없음, 건너뜀")
            continue

        out_path = str(audio_dir / f"scene_{idx:02d}.mp3")
        print(f"    [TTS] 장면 {idx}: {narration}")
        tts.generate(narration, out_path)

        tts_duration_ms = len(AudioSegment.from_file(out_path))
        scene_start_ms  = int(actual_start_times[i] * 1000) + delay_ms
        start_ms        = max(scene_start_ms, queue_end_ms)  # 겹침 방지
        end_ms          = start_ms + tts_duration_ms
        is_ending       = (i == last_scene_idx)

        # 시작 시각이 영상 밖이면 스킵
        if start_ms >= total_duration_ms:
            print(f"        [!] 장면 {idx}: 시작 시각이 영상 종료 후 → 건너뜀")
            continue

        # 나레이션이 영상 종료를 초과할 때
        ENDING_BUFFER_MS = 500  # 엔딩멘트 후 0.5초 여유
        if end_ms > total_duration_ms:
            if is_ending:
                # 엔딩멘트: 영상 종료 0.5초 전에 끝나도록 시작 시각 역산
                ideal_start = total_duration_ms - tts_duration_ms - ENDING_BUFFER_MS
                if ideal_start >= queue_end_ms:
                    # 이전 나레이션 안 겹치면 당겨서 배치
                    start_ms = ideal_start
                    end_ms   = start_ms + tts_duration_ms
                    print(f"        엔딩(역산): {start_ms/1000:.2f}s~{end_ms/1000:.2f}s")
                elif queue_end_ms + tts_duration_ms + ENDING_BUFFER_MS <= total_duration_ms:
                    # queue 바로 다음에 배치하면 버퍼 확보 가능
                    start_ms = queue_end_ms
                    end_ms   = start_ms + tts_duration_ms
                    print(f"        엔딩(queue후): {start_ms/1000:.2f}s~{end_ms/1000:.2f}s")
                else:
                    # 공간이 부족 → 영상 끝에 맞춰 트림 (최후 수단)
                    tts_duration_ms = total_duration_ms - start_ms - ENDING_BUFFER_MS
                    end_ms = start_ms + tts_duration_ms
                    print(f"        엔딩(트림): {start_ms/1000:.2f}s~{end_ms/1000:.2f}s")
            else:
                # 일반 나레이션: 영상 종료 초과 시 스킵
                print(f"        [!] 장면 {idx}: 영상 종료 초과 → 건너뜀")
                continue
        else:
            print(f"        시작: {start_ms/1000:.2f}s  끝: {end_ms/1000:.2f}s  길이: {tts_duration_ms/1000:.2f}s")

        queue_end_ms = end_ms  # 다음 나레이션은 이 시각 이후에 시작

        scene_audios.append({
            "path":         out_path,
            "start_ms":     start_ms,
            "scene_index":  idx,
            "narration":    narration,
            "tts_duration": tts_duration_ms / 1000.0,
        })

    print(f"[v] TTS 완료: {len(scene_audios)}개")

    # 나레이션 타이밍 저장 → STEP 4 자막 타이밍에 사용
    narr_timings = [
        {
            "scene_index": s["scene_index"],
            "narration":   s["narration"],
            "start":       s["start_ms"] / 1000.0,
            "duration":    s["tts_duration"],
            "path":        s["path"],
        }
        for s in scene_audios
    ]
    timings_path = OUTPUT_DIR / "step3_narr_timings.json"
    with open(timings_path, "w", encoding="utf-8") as f:
        import json as _json
        _json.dump(narr_timings, f, ensure_ascii=False, indent=2)
    print(f"[v] 나레이션 타이밍 저장: {timings_path.name}")

    print()

    # 3) BGM 선택
    print("[*] BGM 매칭 중...")
    bgm_manager = BGMManager()
    print(f"    {bgm_manager.get_status()}")
    bgm_path = bgm_manager.select_bgm(mood=bgm_mood, category=category)
    if bgm_path:
        print(f"[v] BGM: {Path(bgm_path).name}")
    else:
        print("[!] BGM 없음 → 나레이션만으로 생성합니다.")
    print()

    # 4) 믹싱
    print("[*] 오디오 믹싱 중...")
    mixer            = AudioMixer()
    # 오디오 캔버스 = 영상 길이에 맞춤 (나레이션은 이미 영상 범위 내로 제한됨)
    final_audio_path = str(OUTPUT_DIR / "step3_final_audio.mp3")

    mixer.mix(
        scene_audio_paths=scene_audios,
        bgm_path=bgm_path,
        total_duration_ms=total_duration_ms,  # 영상 길이 기준
        output_path=final_audio_path,
    )

    print(f"[v] 최종 오디오: {final_audio_path}")
    print()
    print("[v] STEP 3 완료!")
    print("    다음: python run_step4.py")


if __name__ == "__main__":
    main()
