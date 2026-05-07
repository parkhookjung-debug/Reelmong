"""맛노래 Flask 웹 서버

음식 사진을 업로드하면 노래하는 숏폼 영상을 생성합니다.

사용법:
    python app.py
    브라우저에서 http://localhost:5000 접속
"""
import sys
import io
import json
import threading
import traceback
import uuid
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

from config.settings import (
    INPUT_DIR, OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT,
    VIDEO_FPS, SUPPORTED_FORMATS,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB

# 진행 상황 저장소 (job_id → status)
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _set_status(job_id: str, step: str, message: str, progress: int):
    with _jobs_lock:
        _jobs[job_id]["step"] = step
        _jobs[job_id]["message"] = message
        _jobs[job_id]["progress"] = progress


def _run_pipeline(job_id: str, image_path: str):
    """백그라운드 파이프라인 실행"""
    out_dir = OUTPUT_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── STEP 0: 배경 제거 ──────────────────────────────────────
        _set_status(job_id, "분석", "배경 제거 중... (rembg)", 5)

        from src.step0_preprocess import remove_background
        nobg_path = str(out_dir / "nobg.png")
        nobg_path, bg_removed = remove_background(image_path, nobg_path)
        analyze_image = nobg_path if bg_removed else image_path

        # ── STEP 1: 음식 분석 ──────────────────────────────────────
        _set_status(job_id, "분석", "음식 이미지 분석 중... (BLIP + Ollama)", 10)

        from src.step1_analyze import FoodAnalyzer
        analyzer = FoodAnalyzer()
        analysis = analyzer.analyze(analyze_image)
        analysis.save(str(out_dir / "step1_analysis.json"))

        _set_status(job_id, "분석완료", f"음식 인식: {analysis.food_name}", 25)

        # ── STEP 2: 가사 생성 ──────────────────────────────────────
        _set_status(job_id, "가사", "노래 가사 생성 중... (Ollama LLM)", 30)

        from src.step2_lyrics import LyricsGenerator
        lyricist = LyricsGenerator()
        lyrics_data = lyricist.generate(analysis)
        lyricist.save_lyrics(lyrics_data, str(out_dir / "step2_lyrics.json"))

        _set_status(job_id, "가사완료", f"제목: {lyrics_data['title']}", 45)

        # ── STEP 3: 보컬 합성 (Bark 우선 → Edge TTS fallback) ────
        from src.step3_voice import is_bark_available
        voice_dir = str(out_dir / "voice")

        if is_bark_available():
            _set_status(job_id, "음성", "노래 보컬 생성 중... (Bark ♪)", 50)
            from src.step3_voice import BarkVocalGenerator
            singer = BarkVocalGenerator(emotion=analysis.emotion)
        else:
            _set_status(job_id, "음성", "음성 합성 중... (Edge TTS)", 50)
            from src.step3_voice import VoiceGenerator
            singer = VoiceGenerator()

        voice_result = singer.generate_full_song(
            lyrics=lyrics_data["lyrics"],
            output_dir=voice_dir,
        )

        engine = voice_result.get("engine", "edge-tts")
        _set_status(job_id, "음성완료", f"보컬 생성 완료 ({voice_result['total_duration_ms']/1000:.1f}초, {engine})", 60)

        # ── STEP 3.5: 멜로디 생성 + 믹싱 ─────────────────────────
        final_audio_path = voice_result["full_audio_path"]

        from src.step3_voice import is_musicgen_available, AudioMixer
        if is_musicgen_available():
            try:
                _set_status(job_id, "멜로디", "AI 멜로디 생성 중... (MusicGen)", 65)

                from src.step3_voice import MelodyGenerator
                melody_gen = MelodyGenerator()
                melody_duration = voice_result["total_duration_ms"] / 1000.0
                melody_path = str(out_dir / "voice" / "melody.wav")

                melody_gen.generate(
                    category=analysis.category,
                    duration_s=melody_duration,
                    output_path=melody_path,
                )

                mixer = AudioMixer()
                final_audio_path = str(out_dir / "voice" / "final_mixed.mp3")
                mixer.mix(
                    voice_path=voice_result["full_audio_path"],
                    melody_path=melody_path,
                    output_path=final_audio_path,
                    voice_lines=voice_result["lines"],
                )
                _set_status(job_id, "믹싱완료", "멜로디 + 음성 믹싱 완료", 72)

            except Exception as e:
                print(f"[!] 멜로디 생성 실패: {e}")
                final_audio_path = voice_result["full_audio_path"]

        # ── STEP 4+5: 애니메이션 + 렌더링 ────────────────────────
        _set_status(job_id, "영상", "영상 렌더링 중... (립싱크 애니메이션)", 75)

        from src.step5_render import VideoRenderer
        renderer = VideoRenderer(width=VIDEO_WIDTH, height=VIDEO_HEIGHT, fps=VIDEO_FPS)
        output_video = str(out_dir / "singing_food.mp4")

        renderer.render(
            image_path=analyze_image,
            audio_path=final_audio_path,
            lyrics_lines=voice_result["lines"],
            title=lyrics_data["title"],
            output_path=output_video,
            food_category=analysis.category,
        )

        _set_status(job_id, "완료", f"완성! '{lyrics_data['title']}'", 100)

        with _jobs_lock:
            _jobs[job_id]["result"] = {
                "video_url": f"/result/{job_id}/video",
                "title": lyrics_data["title"],
                "food_name": analysis.food_name,
                "lyrics": lyrics_data["lyrics"],
                "duration_s": voice_result["total_duration_ms"] / 1000,
            }
            _jobs[job_id]["done"] = True

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] job {job_id}: {e}\n{tb}")
        with _jobs_lock:
            _jobs[job_id]["step"] = "오류"
            _jobs[job_id]["message"] = f"오류 발생: {str(e)}"
            _jobs[job_id]["progress"] = 0
            _jobs[job_id]["error"] = str(e)
            _jobs[job_id]["done"] = True


# ──────────────────────────────────────────────────────────────────
# 라우트
# ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    """이미지 업로드 → 파이프라인 시작"""
    if "image" not in request.files:
        return jsonify({"error": "이미지 파일이 없습니다."}), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        return jsonify({"error": f"지원하지 않는 형식입니다. ({', '.join(SUPPORTED_FORMATS)})"}), 400

    # 저장
    job_id = str(uuid.uuid4())[:8]
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename) or f"food{ext}"
    save_path = str(INPUT_DIR / f"{job_id}_{safe_name}")
    file.save(save_path)

    # 작업 초기화
    with _jobs_lock:
        _jobs[job_id] = {
            "step": "대기",
            "message": "파이프라인 시작 중...",
            "progress": 5,
            "done": False,
        }

    # 백그라운드 실행
    t = threading.Thread(target=_run_pipeline, args=(job_id, save_path), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id: str):
    """진행 상황 조회 (폴링용)"""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if job is None:
        return jsonify({"error": "존재하지 않는 작업 ID"}), 404

    return jsonify({
        "step": job.get("step", ""),
        "message": job.get("message", ""),
        "progress": job.get("progress", 0),
        "done": job.get("done", False),
        "result": job.get("result"),
        "error": job.get("error"),
    })


@app.route("/result/<job_id>/video")
def result_video(job_id: str):
    """생성된 영상 파일 반환"""
    video_path = OUTPUT_DIR / job_id / "singing_food.mp4"
    if not video_path.exists():
        return "영상을 찾을 수 없습니다.", 404
    return send_file(str(video_path), mimetype="video/mp4")


@app.route("/result/<job_id>/download")
def download_video(job_id: str):
    """영상 다운로드"""
    with _jobs_lock:
        job = _jobs.get(job_id, {})
    title = job.get("result", {}).get("title", "맛노래") if job else "맛노래"
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-") or "matnorae"

    video_path = OUTPUT_DIR / job_id / "singing_food.mp4"
    if not video_path.exists():
        return "영상을 찾을 수 없습니다.", 404
    return send_file(
        str(video_path),
        mimetype="video/mp4",
        as_attachment=True,
        download_name=f"{safe_title}.mp4",
    )


if __name__ == "__main__":
    print()
    print("=" * 50)
    print("  맛노래 웹 서버 시작")
    print("  http://localhost:5000")
    print("=" * 50)
    print()
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
