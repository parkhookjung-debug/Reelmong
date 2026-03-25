"""STEP 4 비디오 이펙트 - 장면별 영상 효과 (MoviePy 2.x)

지원 효과:
- ken_burns: 느린 팬 + 줌 (다큐멘터리 스타일)
- zoom_in: 점진적 확대
- zoom_out: 점진적 축소
- fade: 페이드인
- slide: 좌→우 슬라이드
"""
import numpy as np
from PIL import Image
from moviepy import ImageClip, VideoClip


def apply_effect(image_path: str, duration: float, effect: str, fps: int = 30,
                 target_w: int = 1080, target_h: int = 1920) -> ImageClip:
    """이미지에 영상 효과를 적용하여 VideoClip 반환"""
    # 이미지를 PIL로 로드 → 9:16 크롭 + 이펙트 여유분 포함 리사이즈
    img = Image.open(image_path).convert("RGB")
    img = _fit_image_to_vertical(img, target_w, target_h, scale=1.3)
    base_array = np.array(img)

    effect_map = {
        "ken_burns": _ken_burns,
        "zoom_in": _zoom_in,
        "zoom_out": _zoom_out,
        "fade": _fade,
        "slide": _slide,
    }

    effect_fn = effect_map.get(effect, _ken_burns)
    clip = effect_fn(base_array, duration, fps, target_w, target_h)

    return clip


def _fit_image_to_vertical(img: Image.Image, target_w: int, target_h: int,
                           scale: float = 1.3) -> Image.Image:
    """이미지를 9:16 세로 비율에 맞게 크롭 + 리사이즈 (이펙트 여유분 포함)"""
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

    # 이펙트 여유분 포함하여 리사이즈
    img = img.resize((int(target_w * scale), int(target_h * scale)), Image.LANCZOS)
    return img


def _crop_and_resize(frame: np.ndarray, x: int, y: int,
                     crop_w: int, crop_h: int,
                     target_w: int, target_h: int) -> np.ndarray:
    """프레임에서 크롭 후 타겟 크기로 리사이즈"""
    h, w = frame.shape[:2]
    x = max(0, min(x, w - crop_w))
    y = max(0, min(y, h - crop_h))
    crop_w = min(crop_w, w - x)
    crop_h = min(crop_h, h - y)

    cropped = frame[y:y + crop_h, x:x + crop_w]
    img = Image.fromarray(cropped)
    img = img.resize((target_w, target_h), Image.LANCZOS)
    return np.array(img)


def _ken_burns(base: np.ndarray, duration: float, fps: int,
               target_w: int, target_h: int) -> ImageClip:
    """Ken Burns 효과: 느린 팬 + 살짝 줌인"""
    ch, cw = base.shape[:2]

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        zoom = 1.0 - 0.15 * progress
        crop_w = min(int(target_w / zoom), cw)
        crop_h = min(int(target_h / zoom), ch)

        max_x = cw - crop_w
        max_y = ch - crop_h
        x = int(max_x * progress * 0.5)
        y = int(max_y * progress * 0.3)

        return _crop_and_resize(base, x, y, crop_w, crop_h, target_w, target_h)

    return VideoClip(make_frame, duration=duration).with_fps(fps)


def _zoom_in(base: np.ndarray, duration: float, fps: int,
             target_w: int, target_h: int) -> ImageClip:
    """줌인 효과: 점진적 확대"""
    ch, cw = base.shape[:2]

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        zoom = 1.0 - 0.25 * progress
        crop_w = min(int(target_w / zoom), cw)
        crop_h = min(int(target_h / zoom), ch)

        x = (cw - crop_w) // 2
        y = (ch - crop_h) // 2

        return _crop_and_resize(base, x, y, crop_w, crop_h, target_w, target_h)

    return VideoClip(make_frame, duration=duration).with_fps(fps)


def _zoom_out(base: np.ndarray, duration: float, fps: int,
              target_w: int, target_h: int) -> ImageClip:
    """줌아웃 효과: 점진적 축소"""
    ch, cw = base.shape[:2]

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        zoom = 0.75 + 0.25 * progress
        crop_w = min(int(target_w / zoom), cw)
        crop_h = min(int(target_h / zoom), ch)

        x = (cw - crop_w) // 2
        y = (ch - crop_h) // 2

        return _crop_and_resize(base, x, y, crop_w, crop_h, target_w, target_h)

    return VideoClip(make_frame, duration=duration).with_fps(fps)


def _fade(base: np.ndarray, duration: float, fps: int,
          target_w: int, target_h: int) -> ImageClip:
    """페이드인 효과: 검정에서 서서히 나타남"""
    ch, cw = base.shape[:2]

    def make_frame(t):
        fade_duration = min(0.5, duration * 0.3)
        alpha = min(1.0, t / fade_duration) if fade_duration > 0 else 1.0

        # 중앙 크롭
        crop_w = min(target_w, cw)
        crop_h = min(target_h, ch)
        x = (cw - crop_w) // 2
        y = (ch - crop_h) // 2

        frame = _crop_and_resize(base, x, y, crop_w, crop_h, target_w, target_h)
        return (frame * alpha).astype(np.uint8)

    return VideoClip(make_frame, duration=duration).with_fps(fps)


def _slide(base: np.ndarray, duration: float, fps: int,
           target_w: int, target_h: int) -> ImageClip:
    """슬라이드 효과: 좌→우로 천천히 이동"""
    ch, cw = base.shape[:2]

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        crop_w = min(target_w, cw)
        crop_h = min(target_h, ch)

        max_x = max(0, cw - crop_w)
        x = int(max_x * progress)
        y = (ch - crop_h) // 2

        return _crop_and_resize(base, x, y, crop_w, crop_h, target_w, target_h)

    return VideoClip(make_frame, duration=duration).with_fps(fps)
