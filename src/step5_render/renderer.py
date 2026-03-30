"""STEP 5: 최종 영상 렌더링 (MoviePy 2.x)

음식 이미지 + 카툰 얼굴 + 립싱크 + 오디오 + 가사 자막 → 최종 MP4
- 프레임별 입 열림/닫힘 애니메이션
- 가사 자막 오버레이 (현재 줄 하이라이트)
- 살짝 흔들림 효과 (노래하는 느낌)
"""
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from moviepy import AudioFileClip, VideoClip, CompositeVideoClip, ImageClip, vfx

from src.step4_animate.face import FaceComposer
from src.step4_animate.lipsync import LipSyncAnimator


# 한국어 폰트
_KOREAN_FONT_PATHS = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/NanumGothicBold.ttf",
    "C:/Windows/Fonts/NanumGothic.ttf",
    "C:/Windows/Fonts/gulim.ttc",
]


def _find_korean_font() -> str:
    for font_path in _KOREAN_FONT_PATHS:
        if Path(font_path).exists():
            return font_path
    return "C:/Windows/Fonts/arial.ttf"


def _fit_image(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """이미지를 타겟 크기에 맞게 크롭 + 리사이즈"""
    target_ratio = target_w / target_h
    img_w, img_h = img.size
    img_ratio = img_w / img_h

    if img_ratio > target_ratio:
        new_h = img_h
        new_w = int(img_h * target_ratio)
        x_offset = (img_w - new_w) // 2
        img = img.crop((x_offset, 0, x_offset + new_w, new_h))
    else:
        new_w = img_w
        new_h = int(img_w / target_ratio)
        y_offset = max(0, (img_h - new_h) // 2)
        img = img.crop((0, y_offset, new_w, y_offset + new_h))

    img = img.resize((target_w, target_h), Image.LANCZOS)
    return img


class VideoRenderer:
    """노래하는 음식 영상 렌더러"""

    def __init__(self, width: int = 1080, height: int = 1080, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.font_path = _find_korean_font()
        self.face_composer = FaceComposer()
        self.lip_sync = LipSyncAnimator(fps=fps)

    def render(
        self,
        image_path: str,
        audio_path: str,
        lyrics_lines: list[dict],
        title: str,
        output_path: str,
    ) -> str:
        """최종 영상 렌더링

        Args:
            image_path: 음식 이미지 경로
            audio_path: 전체 음성 파일 경로
            lyrics_lines: [{"text": ..., "start_ms": ..., "duration_ms": ...}, ...]
            title: 노래 제목
            output_path: 출력 MP4 경로
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 1) 이미지 준비
        print("    [이미지] 로딩 및 리사이즈...")
        base_img = Image.open(image_path).convert("RGB")
        base_img = _fit_image(base_img, self.width, self.height)

        # 2) 립싱크 분석
        print("    [립싱크] 오디오 분석 중...")
        openness_data = self.lip_sync.analyze_audio(audio_path)
        timing = self.lip_sync.get_timing_info(openness_data)
        print(f"    [립싱크] {timing['total_frames']}프레임, "
              f"노래 {timing.get('singing_ratio', 0):.0%}")

        total_frames = len(openness_data)
        duration = total_frames / self.fps

        # 3) 프레임 생성 함수
        def make_frame(t):
            frame_idx = min(int(t * self.fps), total_frames - 1)

            # 입 열림 정도
            openness = openness_data[frame_idx] if frame_idx < len(openness_data) else 0.0

            # 카툰 얼굴 합성
            frame_img = self.face_composer.compose_frame(
                base_img,
                mouth_openness=openness,
                face_scale=0.3,
            )

            # 살짝 흔들림 (노래하는 느낌)
            if openness > 0.1:
                shake_x = int(np.sin(t * 8) * 2 * openness)
                shake_y = int(np.cos(t * 6) * 1.5 * openness)
                # PIL shift
                frame_img = frame_img.transform(
                    frame_img.size, Image.AFFINE,
                    (1, 0, -shake_x, 0, 1, -shake_y),
                    fillcolor=(0, 0, 0, 255),
                )

            return np.array(frame_img.convert("RGB"))

        # 4) 메인 비디오 클립
        print("    [렌더링] 프레임 생성 중...")
        video_clip = VideoClip(make_frame, duration=duration).with_fps(self.fps)

        # 5) 가사 자막 오버레이
        print("    [자막] 가사 오버레이 생성 중...")
        subtitle_clips = self._create_lyric_overlays(lyrics_lines, duration)

        # 6) 제목 오버레이
        title_clip = self._create_title_overlay(title, duration)

        # 7) 합성
        all_clips = [video_clip] + subtitle_clips
        if title_clip:
            all_clips.append(title_clip)

        final = CompositeVideoClip(all_clips, size=(self.width, self.height))

        # 8) 오디오 합성
        if audio_path and Path(audio_path).exists():
            print("    [오디오] 합성 중...")
            audio = AudioFileClip(audio_path)
            if audio.duration > final.duration:
                audio = audio.subclipped(0, final.duration)
            final = final.with_audio(audio)

        # 9) 인코딩
        print("    [인코딩] MP4 출력 중...")
        final.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger="bar",
        )
        final.close()

        return output_path

    def _create_lyric_overlays(
        self, lyrics_lines: list[dict], total_duration: float
    ) -> list:
        """가사 줄별 자막 클립 생성"""
        clips = []

        for line_info in lyrics_lines:
            text = line_info.get("text", "")
            start_s = line_info.get("start_ms", 0) / 1000.0
            dur_s = line_info.get("duration_ms", 2000) / 1000.0

            if not text.strip():
                continue

            # 텍스트 이미지 렌더링
            txt_img = self._render_lyric_text(text)
            txt_clip = (
                ImageClip(txt_img, transparent=True)
                .with_duration(dur_s + 0.3)  # 약간 여유
                .with_start(start_s)
                .with_effects([vfx.CrossFadeIn(0.15), vfx.CrossFadeOut(0.15)])
            )

            # 하단 배치
            txt_h = txt_img.shape[0]
            y_pos = self.height - 120 - txt_h
            txt_clip = txt_clip.with_position(("center", y_pos))

            clips.append(txt_clip)

        return clips

    def _render_lyric_text(self, text: str) -> np.ndarray:
        """가사 텍스트 → RGBA numpy array"""
        font_size = 42
        font = ImageFont.truetype(self.font_path, font_size)

        # 크기 측정
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad = 20
        img_w = tw + pad * 2
        img_h = th + pad * 2

        # 배경 + 텍스트
        img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 160))
        draw = ImageDraw.Draw(img)

        x = (img_w - tw) // 2
        y = pad
        draw.text(
            (x, y), text, font=font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 255),
        )

        return np.array(img)

    def _create_title_overlay(self, title: str, total_duration: float):
        """노래 제목 오버레이 (처음 3초)"""
        if not title:
            return None

        font_size = 52
        font = ImageFont.truetype(self.font_path, font_size)

        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        bbox = draw.textbbox((0, 0), title, font=font, stroke_width=3)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad = 24
        img_w = tw + pad * 2
        img_h = th + pad * 2

        img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 180))
        draw = ImageDraw.Draw(img)

        x = (img_w - tw) // 2
        draw.text(
            (x, pad), title, font=font,
            fill=(255, 255, 0, 255),
            stroke_width=3,
            stroke_fill=(0, 0, 0, 255),
        )

        title_clip = (
            ImageClip(np.array(img), transparent=True)
            .with_duration(3.0)
            .with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.5)])
            .with_position(("center", 80))
        )

        return title_clip
