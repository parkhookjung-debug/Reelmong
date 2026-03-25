"""STEP 4 비디오 렌더러 - 이미지 + 오디오 + 자막 → 최종 MP4 (MoviePy 2.x)

스토리보드(step2)와 오디오(step3)를 결합하여 9:16 세로 숏폼 영상을 생성합니다.
- 장면별 이미지에 효과(Ken Burns, 줌, 페이드 등) 적용
- 장면 전환(crossfade, cut, fade_black) 처리
- 자막 오버레이 (PIL 직접 렌더링)
- 오프닝 후크 + 클로징 CTA 텍스트 오버레이
- 최종 오디오 트랙 합성
"""
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
    vfx,
)  # TextClip 대신 PIL로 직접 렌더링

from src.step4_video.effects import apply_effect


# 한국어 자막용 폰트 (Windows 기본 폰트 경로)
_KOREAN_FONT_PATHS = [
    "C:/Windows/Fonts/malgunbd.ttf",     # 맑은 고딕 Bold
    "C:/Windows/Fonts/malgun.ttf",        # 맑은 고딕
    "C:/Windows/Fonts/NanumGothicBold.ttf",
    "C:/Windows/Fonts/NanumGothic.ttf",
    "C:/Windows/Fonts/gulim.ttc",
]


def _find_korean_font() -> str:
    """사용 가능한 한국어 폰트 파일 경로 탐색"""
    for font_path in _KOREAN_FONT_PATHS:
        if Path(font_path).exists():
            return font_path
    return "C:/Windows/Fonts/arial.ttf"


def _render_text_image(
    text: str,
    font_path: str,
    font_size: int,
    text_color: tuple = (255, 255, 255, 255),
    stroke_color: tuple = (0, 0, 0, 255),
    stroke_width: int = 2,
    bg_color: tuple = (0, 0, 0, 140),
    max_width: int = 900,
    padding: tuple = (24, 16),
) -> np.ndarray:
    """PIL로 텍스트를 RGBA 이미지로 렌더링 (잘림 없음 보장)

    Returns:
        numpy RGBA array
    """
    font = ImageFont.truetype(font_path, font_size)

    # 텍스트 줄바꿈 처리
    lines = _wrap_text(text, font, max_width)
    line_spacing = int(font_size * 0.35)

    # 전체 텍스트 크기 측정
    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    total_text_w = max(line_widths) if line_widths else 0
    total_text_h = sum(line_heights) + line_spacing * (len(lines) - 1) if lines else 0

    pad_x, pad_y = padding
    img_w = total_text_w + pad_x * 2
    img_h = total_text_h + pad_y * 2

    # 배경 + 텍스트 렌더링
    img = Image.new("RGBA", (img_w, img_h), bg_color)
    draw = ImageDraw.Draw(img)

    y_cursor = pad_y
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        lw = bbox[2] - bbox[0]
        x = (img_w - lw) // 2  # 중앙 정렬

        # 외곽선(stroke)
        if stroke_width > 0:
            draw.text((x, y_cursor), line, font=font,
                      fill=text_color, stroke_width=stroke_width,
                      stroke_fill=stroke_color)
        else:
            draw.text((x, y_cursor), line, font=font, fill=text_color)

        y_cursor += line_heights[i] + line_spacing

    return np.array(img)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """텍스트를 max_width에 맞게 줄바꿈"""
    if not text:
        return []

    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    # 한 줄에 들어가는지 체크
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_width:
        return [text]

    # 글자 단위로 줄바꿈
    lines = []
    current = ""
    for char in text:
        test = current + char
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width:
            if current:
                lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)

    return lines


class VideoRenderer:
    """숏폼 비디오 렌더러"""

    def __init__(self, width: int = 1080, height: int = 1920, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.font = _find_korean_font()
        print(f"    [폰트] {Path(self.font).name}")

    def render(
        self,
        storyboard: dict,
        audio_path: str,
        output_path: str,
    ) -> str:
        """스토리보드 + 오디오 → 최종 비디오 렌더링"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        scenes = storyboard.get("scenes", [])
        opening_hook = storyboard.get("opening_hook", "")
        closing_cta = storyboard.get("closing_cta", "")

        # 1) 장면별 클립 생성
        scene_clips = []
        for i, scene in enumerate(scenes):
            image_path = scene.get("image_path", "")
            duration = float(scene.get("duration", 4))
            effect = scene.get("effect", "ken_burns")
            subtitle = scene.get("subtitle", "")

            print(f"    [장면 {i + 1}/{len(scenes)}] {effect} 효과 적용 중...")

            if not image_path or not Path(image_path).exists():
                clip = ColorClip(
                    size=(self.width, self.height),
                    color=(0, 0, 0),
                    duration=duration,
                ).with_fps(self.fps)
            else:
                clip = apply_effect(
                    image_path=image_path,
                    duration=duration,
                    effect=effect,
                    fps=self.fps,
                    target_w=self.width,
                    target_h=self.height,
                )

            # 자막 오버레이
            if subtitle:
                clip = self._add_subtitle(clip, subtitle, duration)

            scene_clips.append(clip)

        if not scene_clips:
            print("[!] 렌더링할 장면이 없습니다.")
            return ""

        # 2) 오프닝 후크 텍스트 (첫 장면에 오버레이)
        if opening_hook and scene_clips:
            scene_clips[0] = self._add_hook_text(scene_clips[0], opening_hook)

        # 3) 클로징 CTA (마지막 장면에 오버레이)
        if closing_cta and scene_clips:
            scene_clips[-1] = self._add_cta_text(scene_clips[-1], closing_cta)

        # 4) 장면 전환 적용하여 연결
        transitions = [s.get("transition", "crossfade") for s in scenes]
        print("    [편집] 장면 연결 중...")
        final_video = self._join_scenes(scene_clips, transitions)

        # 5) 오디오 합성
        if audio_path and Path(audio_path).exists():
            print("    [오디오] 합성 중...")
            audio = AudioFileClip(audio_path)
            if audio.duration > final_video.duration:
                audio = audio.subclipped(0, final_video.duration)
            final_video = final_video.with_audio(audio)

        # 6) 최종 렌더링
        print("    [렌더링] MP4 인코딩 중...")
        final_video.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger="bar",
        )

        final_video.close()
        return output_path

    def _make_text_overlay(self, text: str, font_size: int, duration: float,
                           text_color=(255, 255, 255, 255),
                           stroke_color=(0, 0, 0, 255),
                           stroke_width=2,
                           bg_color=(0, 0, 0, 140),
                           max_width=None) -> ImageClip:
        """PIL로 텍스트를 렌더링하여 RGBA ImageClip 생성 (잘림 없음 보장)"""
        if max_width is None:
            max_width = self.width - 160

        text_img = _render_text_image(
            text=text,
            font_path=self.font,
            font_size=font_size,
            text_color=text_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            bg_color=bg_color,
            max_width=max_width,
        )
        return ImageClip(text_img, is_mask=False, transparent=True).with_duration(duration)

    def _add_subtitle(self, clip, text: str, duration: float):
        """하단 중앙에 자막 오버레이 (PIL 렌더링)"""
        try:
            txt_clip = self._make_text_overlay(
                text=text,
                font_size=44,
                duration=duration,
                bg_color=(0, 0, 0, 150),
            )

            # 하단에서 180px 위에 배치
            txt_h = txt_clip.size[1]
            y_pos = self.height - 180 - txt_h
            txt_clip = txt_clip.with_position(("center", y_pos))

            return CompositeVideoClip(
                [clip, txt_clip], size=(self.width, self.height)
            )
        except Exception as e:
            print(f"    [!] 자막 생성 실패: {e}")
            return clip

    def _add_hook_text(self, clip, text: str):
        """오프닝 후크: 화면 상단 1/3 위치에 큰 텍스트 (처음 3초)"""
        hook_duration = min(3.0, clip.duration)
        try:
            txt_clip = self._make_text_overlay(
                text=text,
                font_size=58,
                duration=hook_duration,
                text_color=(255, 255, 0, 255),
                stroke_width=3,
                bg_color=(0, 0, 0, 140),
            ).with_effects([
                vfx.CrossFadeIn(0.3),
                vfx.CrossFadeOut(0.5),
            ])

            txt_h = txt_clip.size[1]
            y_pos = self.height // 3 - txt_h // 2
            txt_clip = txt_clip.with_position(("center", y_pos))

            return CompositeVideoClip(
                [clip, txt_clip], size=(self.width, self.height)
            )
        except Exception as e:
            print(f"    [!] 후크 텍스트 생성 실패: {e}")
            return clip

    def _add_cta_text(self, clip, text: str):
        """클로징 CTA: 화면 중앙에 표시"""
        try:
            txt_clip = self._make_text_overlay(
                text=text,
                font_size=42,
                duration=clip.duration,
                bg_color=(0, 0, 0, 170),
            ).with_effects([
                vfx.CrossFadeIn(0.5),
            ])

            txt_h = txt_clip.size[1]
            y_pos = self.height // 2 - txt_h // 2
            txt_clip = txt_clip.with_position(("center", y_pos))

            return CompositeVideoClip(
                [clip, txt_clip], size=(self.width, self.height)
            )
        except Exception as e:
            print(f"    [!] CTA 텍스트 생성 실패: {e}")
            return clip

    def _join_scenes(self, clips: list, transitions: list):
        """장면 전환 효과를 적용하여 클립 연결"""
        if len(clips) <= 1:
            return clips[0] if clips else ColorClip(
                size=(self.width, self.height), color=(0, 0, 0), duration=1
            )

        transition_duration = 0.5

        # crossfade 전환이 있는지 확인
        has_crossfade = any(
            transitions[i] == "crossfade"
            for i in range(1, len(transitions))
            if i < len(transitions)
        )

        processed = [clips[0]]
        for i in range(1, len(clips)):
            transition = transitions[i] if i < len(transitions) else "cut"

            if transition == "crossfade":
                clips[i] = clips[i].with_effects([
                    vfx.CrossFadeIn(transition_duration)
                ])
                processed.append(clips[i])
            elif transition == "fade_black":
                processed[-1] = processed[-1].with_effects([
                    vfx.CrossFadeOut(transition_duration * 0.5)
                ])
                clips[i] = clips[i].with_effects([
                    vfx.CrossFadeIn(transition_duration * 0.5)
                ])
                processed.append(clips[i])
            else:
                processed.append(clips[i])

        if has_crossfade:
            return concatenate_videoclips(
                processed, method="compose", padding=-transition_duration
            )
        else:
            return concatenate_videoclips(processed, method="compose")
