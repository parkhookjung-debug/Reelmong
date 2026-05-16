"""STEP 4 비디오 렌더러 - 영상 클립 연결 + 자막 + 오디오 → 최종 MP4 (MoviePy 2.x)

스토리보드(step2)와 오디오(step3)를 결합하여 9:16 세로 숏폼 영상을 생성합니다.
- data/images/ 폴더의 영상 파일(0~9번)을 순서대로 연결
- 장면별 나레이션 자막 오버레이 (화면 중앙, PIL 직접 렌더링)
- 최종 오디오 트랙 합성
"""
import re
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    VideoClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
    vfx,
)

# 나레이션 시작까지 딜레이 (run_step3.py의 NARRATION_DELAY와 동일하게 맞출 것)
NARRATION_DELAY = 0.0


# 한국어 자막용 폰트 (Windows 기본 폰트 경로)
_KOREAN_FONT_PATHS = [
    "C:/Users/wf260113/Documents/reelmong/data/fonts/KyoboHandwriting2025lyb.ttf",
    "C:/Users/wf260113/Documents/reelmong/data/fonts/Paperlogy-7Bold.ttf",
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


def _sort_key(path: Path) -> int:
    """파일명 끝 숫자로 정렬 (숫자 없으면 0)"""
    m = re.search(r'(\d+)$', path.stem)
    return int(m.group(1)) if m else 0


def _find_video_files(videos_dir: str) -> list[Path]:
    """videos_dir 에서 mp4 파일을 이름 순으로 정렬하여 반환"""
    d = Path(videos_dir)
    files = [p for p in d.iterdir() if p.suffix.lower() == ".mp4"]
    return sorted(files, key=_sort_key)


def _render_text_image(
    text: str,
    font_path: str,
    font_size: int,
    text_color: tuple = (255, 255, 255, 255),
    stroke_color: tuple = (0, 0, 0, 255),
    stroke_width: int = 2,
    bg_color: tuple = (0, 0, 0, 0),
    max_width: int = 900,
    padding: tuple = (24, 16),
) -> np.ndarray:
    """PIL로 텍스트를 RGBA 이미지로 렌더링"""
    font = ImageFont.truetype(font_path, font_size)
    lines = _wrap_text(text, font, max_width)
    line_spacing = int(font_size * 0.35)

    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    line_heights, line_widths = [], []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    total_text_w = max(line_widths) if line_widths else 0
    total_text_h = sum(line_heights) + line_spacing * (len(lines) - 1) if lines else 0

    pad_x, pad_y = padding
    img_w = total_text_w + pad_x * 2
    img_h = total_text_h + pad_y * 2

    img = Image.new("RGBA", (img_w, img_h), bg_color)
    draw = ImageDraw.Draw(img)

    y_cursor = pad_y
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        lw = bbox[2] - bbox[0]
        x = (img_w - lw) // 2
        draw.text((x, y_cursor), line, font=font,
                  fill=text_color, stroke_width=stroke_width,
                  stroke_fill=stroke_color)
        y_cursor += line_heights[i] + line_spacing

    return np.array(img)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """텍스트를 max_width에 맞게 줄바꿈"""
    if not text:
        return []

    dummy_img = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_width:
        return [text]

    lines, current = [], ""
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
    """숏폼 비디오 렌더러 (영상 클립 연결 방식)"""

    def __init__(self, width: int = 1080, height: int = 1920, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.font = _find_korean_font()
        print(f"    [폰트] {Path(self.font).name}")

    def _adjust_duration(self, clip, target: float):
        """클립 길이를 target(초)에 맞게 조정
        - 길면 앞부분만 사용 (trim)
        - 짧으면 마지막 프레임 정지로 연장 (freeze)
        """
        if abs(clip.duration - target) < 0.05:
            return clip
        if clip.duration >= target:
            return clip.subclipped(0, target)
        last_frame = clip.get_frame(clip.duration - 0.01)
        freeze = (
            ImageClip(last_frame, is_mask=False)
            .with_duration(target - clip.duration)
            .with_fps(self.fps)
        )
        return concatenate_videoclips([clip, freeze])

    def render(
        self,
        storyboard: dict,
        audio_path: str,
        output_path: str,
        videos_dir: str,
        narr_timings: list[dict] | None = None,
        tts_durations: list[float] | None = None,  # 하위 호환용 (미사용)
    ) -> str:
        """영상 클립 연결 + 자막 + 오디오 → 최종 비디오 렌더링

        자막 타이밍:
          narr_timings 있음 → 나레이션 시작 시각 기준으로 전체 타임라인에 오버레이
          narr_timings 없음 → 클립별 자막 (기존 방식 폴백)
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        scenes = storyboard.get("scenes", [])
        video_files = _find_video_files(videos_dir)

        if not video_files:
            print(f"[!] {videos_dir} 에 mp4 파일이 없습니다.")
            return ""

        print(f"    [영상] {len(video_files)}개 클립 발견")

        # 1) 클립 로드 + 리사이즈 (자막 없이, 자연 길이 그대로)
        scene_clips = []
        for i, video_path in enumerate(video_files):
            print(f"    [클립 {i + 1}/{len(video_files)}] {video_path.name} 처리 중...")
            clip = self._load_and_fit(str(video_path))

            # narr_timings 없을 때만 기존 방식(클립별 자막) 적용
            if not narr_timings and i < len(scenes):
                narration = scenes[i].get("narration", "")
                if narration:
                    clip = self._add_subtitle(clip, narration)

            scene_clips.append(clip)

        # 2) 클립 연결 (자연 길이 기준)
        print("    [편집] 클립 연결 중...")
        final_video = concatenate_videoclips(scene_clips, method="compose")

        # 3) 나레이션 타이밍 기준 자막 오버레이
        if narr_timings:
            print("    [자막] 나레이션 타이밍 기준 오버레이 적용 중...")
            subtitle_overlays = []
            for timing in narr_timings:
                narr_start = timing["start"]
                narr_dur   = timing["duration"]
                narration  = timing.get("narration", "")

                if not narration or narr_start >= final_video.duration:
                    continue

                # 영상 끝을 넘어가면 클리핑
                actual_dur = min(narr_dur, final_video.duration - narr_start)
                if actual_dur <= 0:
                    continue

                subtitle_clip = self._make_subtitle_overlay(narration, actual_dur)
                subtitle_clip = subtitle_clip.with_start(narr_start)
                subtitle_overlays.append(subtitle_clip)

            if subtitle_overlays:
                final_video = CompositeVideoClip(
                    [final_video] + subtitle_overlays,
                    size=(self.width, self.height),
                )

        # 4) 오디오 합성
        if audio_path and Path(audio_path).exists():
            print("    [오디오] 합성 중...")
            audio = AudioFileClip(audio_path)
            if audio.duration > final_video.duration:
                audio = audio.subclipped(0, final_video.duration)
            final_video = final_video.with_audio(audio)

        # 5) 최종 렌더링
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

    def _load_and_fit(self, video_path: str):
        """영상 로드 후 9:16 비율로 크롭 + 타겟 해상도로 리사이즈"""
        clip = VideoFileClip(video_path)

        target_ratio = self.width / self.height
        clip_ratio = clip.w / clip.h

        if abs(clip_ratio - target_ratio) > 0.01:
            if clip_ratio > target_ratio:
                # 가로가 넓은 경우 → 좌우 크롭
                new_w = int(clip.h * target_ratio)
                x1 = (clip.w - new_w) // 2
                clip = clip.cropped(x1=x1, x2=x1 + new_w)
            else:
                # 세로가 긴 경우 → 상하 크롭
                new_h = int(clip.w / target_ratio)
                y1 = (clip.h - new_h) // 2
                clip = clip.cropped(y1=y1, y2=y1 + new_h)

        if clip.w != self.width or clip.h != self.height:
            clip = clip.resized((self.width, self.height))

        return clip

    def _make_text_overlay(self, text: str, font_size: int, duration: float,
                           text_color=(255, 255, 255, 255),
                           stroke_color=(0, 0, 0, 255),
                           stroke_width=2,
                           bg_color=(0, 0, 0, 0),
                           max_width=None) -> ImageClip:
        """PIL로 텍스트를 렌더링하여 RGBA ImageClip 생성"""
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

    def _add_subtitle(self, clip, text: str):
        """화면 중앙에 팝 애니메이션 자막 오버레이
        - 나레이션 시작(NARRATION_DELAY) 타이밍에 맞춰 뿅! 등장
        - 0→130% 확대 후 100%로 안착
        """
        try:
            # 텍스트 이미지 풀사이즈로 한 번만 렌더링
            text_arr = _render_text_image(
                text=text,
                font_path=self.font,
                font_size=59,
                text_color=(255, 255, 255, 255),
                stroke_color=(0, 0, 0, 255),
                stroke_width=2,
                bg_color=(0, 0, 0, 0),
                max_width=self.width - 160,
            )
            pil_img  = Image.fromarray(text_arr)
            base_w, base_h = pil_img.size

            # 팝 애니메이션 파라미터
            POP_PEAK  = 0.10   # 최대 크기 도달 (초)
            POP_END   = 0.22   # 원래 크기로 안착 (초)
            PEAK_SCALE = 1.3   # 최대 스케일

            cw, ch = self.width, self.height

            def make_frame(t):
                local_t = t - NARRATION_DELAY  # 나레이션 시작 기준

                # 나레이션 전 → 완전 투명
                if local_t < 0:
                    return np.zeros((ch, cw, 4), dtype=np.uint8)

                # 스케일 계산 (뿅! 이징)
                if local_t < POP_PEAK:
                    scale = (local_t / POP_PEAK) * PEAK_SCALE
                elif local_t < POP_END:
                    progress = (local_t - POP_PEAK) / (POP_END - POP_PEAK)
                    scale = PEAK_SCALE - (PEAK_SCALE - 1.0) * progress
                else:
                    scale = 1.0

                scale = max(0.01, scale)
                new_w = max(1, int(base_w * scale))
                new_h = max(1, int(base_h * scale))

                scaled  = pil_img.resize((new_w, new_h), Image.LANCZOS)
                canvas  = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
                x = (cw - new_w) // 2
                y = (ch - new_h) // 2
                canvas.paste(scaled, (x, y), scaled)
                return np.array(canvas)

            overlay = (
                VideoClip(make_frame, duration=clip.duration)
                .with_fps(self.fps)
            )

            return CompositeVideoClip(
                [clip, overlay], size=(self.width, self.height)
            )
        except Exception as e:
            print(f"    [!] 자막 생성 실패: {e}")
            return clip

    def _make_subtitle_overlay(self, text: str, duration: float):
        """전체 타임라인용 자막 오버레이 클립 생성
        - with_start(narr_start)로 타이밍 지정해서 사용
        - t=0부터 팝 애니메이션 시작
        """
        try:
            text_arr = _render_text_image(
                text=text,
                font_path=self.font,
                font_size=59,
                text_color=(255, 255, 255, 255),
                stroke_color=(0, 0, 0, 255),
                stroke_width=2,
                bg_color=(0, 0, 0, 0),
                max_width=self.width - 160,
            )
            pil_img        = Image.fromarray(text_arr)
            base_w, base_h = pil_img.size

            POP_PEAK   = 0.10
            POP_END    = 0.22
            PEAK_SCALE = 1.3
            cw, ch     = self.width, self.height

            def make_frame(t):
                # 팝 애니메이션 (t=0 기준)
                if t < POP_PEAK:
                    scale = (t / POP_PEAK) * PEAK_SCALE
                elif t < POP_END:
                    progress = (t - POP_PEAK) / (POP_END - POP_PEAK)
                    scale    = PEAK_SCALE - (PEAK_SCALE - 1.0) * progress
                else:
                    scale = 1.0

                scale = max(0.01, scale)
                new_w  = max(1, int(base_w * scale))
                new_h  = max(1, int(base_h * scale))
                scaled = pil_img.resize((new_w, new_h), Image.LANCZOS)

                canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
                x = (cw - new_w) // 2
                y = (ch - new_h) // 2
                canvas.paste(scaled, (x, y), scaled)
                return np.array(canvas)

            return (
                VideoClip(make_frame, duration=duration, is_mask=False)
                .with_fps(self.fps)
            )
        except Exception as e:
            print(f"    [!] 자막 오버레이 생성 실패: {e}")
            return VideoClip(lambda t: np.zeros((self.height, self.width, 4), dtype=np.uint8),
                             duration=duration).with_fps(self.fps)

    def _join_scenes(self, clips: list, transitions: list):
        """장면 전환 효과를 적용하여 클립 연결"""
        if len(clips) <= 1:
            return clips[0] if clips else None

        transition_duration = 0.5
        has_crossfade = any(
            transitions[i] == "crossfade"
            for i in range(1, len(transitions))
            if i < len(transitions)
        )

        processed = [clips[0]]
        for i in range(1, len(clips)):
            transition = transitions[i] if i < len(transitions) else "cut"
            if transition == "crossfade":
                clips[i] = clips[i].with_effects([vfx.CrossFadeIn(transition_duration)])
                processed.append(clips[i])
            elif transition == "fade_black":
                processed[-1] = processed[-1].with_effects([vfx.CrossFadeOut(transition_duration * 0.5)])
                clips[i] = clips[i].with_effects([vfx.CrossFadeIn(transition_duration * 0.5)])
                processed.append(clips[i])
            else:
                processed.append(clips[i])

        if has_crossfade:
            return concatenate_videoclips(processed, method="compose", padding=-transition_duration)
        else:
            return concatenate_videoclips(processed, method="compose")
