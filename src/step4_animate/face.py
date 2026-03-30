"""STEP 4-A: 카툰 얼굴 합성 (PIL)

음식 이미지 위에 카툰 눈과 입을 그려서 의인화합니다.
- PIL로 직접 그리기 (외부 에셋 불필요)
- 눈: 큰 동그란 눈 + 반짝이는 하이라이트
- 입: 열림/닫힘 상태를 프레임별로 전환 (립싱크용)
"""
import numpy as np
from PIL import Image, ImageDraw


class FaceComposer:
    """음식 이미지에 카툰 얼굴 합성"""

    def __init__(self, eye_size: int = 60, mouth_size: int = 50):
        self.eye_size = eye_size
        self.mouth_size = mouth_size

    def _draw_eye(self, draw: ImageDraw.Draw, cx: int, cy: int, size: int):
        """카툰 눈 그리기 (큰 동그란 눈 + 하이라이트)"""
        r = size // 2

        # 흰자
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(255, 255, 255, 255),
            outline=(40, 40, 40, 255),
            width=3,
        )

        # 눈동자 (검정)
        pupil_r = int(r * 0.55)
        draw.ellipse(
            [cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r],
            fill=(30, 30, 30, 255),
        )

        # 하이라이트 (반짝임)
        hl_r = int(r * 0.2)
        hl_x = cx - int(r * 0.2)
        hl_y = cy - int(r * 0.25)
        draw.ellipse(
            [hl_x - hl_r, hl_y - hl_r, hl_x + hl_r, hl_y + hl_r],
            fill=(255, 255, 255, 255),
        )

    def _draw_mouth_closed(self, draw: ImageDraw.Draw, cx: int, cy: int, size: int):
        """닫힌 입 (미소)"""
        r = size // 2
        # 반원 미소
        draw.arc(
            [cx - r, cy - int(r * 0.5), cx + r, cy + int(r * 0.8)],
            start=0, end=180,
            fill=(200, 60, 60, 255),
            width=4,
        )

    def _draw_mouth_open(self, draw: ImageDraw.Draw, cx: int, cy: int,
                         size: int, openness: float = 1.0):
        """열린 입 (노래하는 중)

        Args:
            openness: 0.0 (살짝) ~ 1.0 (크게)
        """
        r = size // 2
        open_h = int(r * 0.4 + r * 0.8 * openness)

        # 입 외곽 (타원)
        draw.ellipse(
            [cx - r, cy - int(open_h * 0.3), cx + r, cy + open_h],
            fill=(200, 60, 60, 255),
            outline=(120, 30, 30, 255),
            width=3,
        )

        # 입 안쪽 (어두운 부분)
        inner_r = int(r * 0.7)
        inner_h = int(open_h * 0.6)
        draw.ellipse(
            [cx - inner_r, cy + int(open_h * 0.05),
             cx + inner_r, cy + inner_h],
            fill=(80, 20, 20, 255),
        )

    def compose_frame(
        self,
        base_image: Image.Image,
        mouth_openness: float = 0.0,
        face_center: tuple[int, int] | None = None,
        face_scale: float = 0.3,
    ) -> Image.Image:
        """음식 이미지 + 카툰 얼굴 = 합성 프레임

        Args:
            base_image: 원본 음식 이미지 (RGB)
            mouth_openness: 입 열림 정도 (0.0 ~ 1.0)
            face_center: 얼굴 중심 좌표 (None이면 이미지 중앙)
            face_scale: 얼굴 크기 비율

        Returns:
            합성된 RGBA 이미지
        """
        img = base_image.copy().convert("RGBA")
        w, h = img.size

        # 얼굴 위치/크기 결정
        if face_center is None:
            face_cx = w // 2
            face_cy = int(h * 0.45)  # 살짝 위쪽
        else:
            face_cx, face_cy = face_center

        # 크기 계산
        ref_size = min(w, h) * face_scale
        eye_size = int(ref_size * 0.4)
        mouth_size = int(ref_size * 0.35)
        eye_gap = int(ref_size * 0.35)  # 눈 사이 간격
        mouth_offset_y = int(ref_size * 0.35)  # 눈에서 입까지 거리

        # 오버레이 레이어
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 눈 그리기
        left_eye_x = face_cx - eye_gap
        right_eye_x = face_cx + eye_gap
        eye_y = face_cy

        self._draw_eye(draw, left_eye_x, eye_y, eye_size)
        self._draw_eye(draw, right_eye_x, eye_y, eye_size)

        # 입 그리기
        mouth_y = face_cy + mouth_offset_y
        if mouth_openness < 0.1:
            self._draw_mouth_closed(draw, face_cx, mouth_y, mouth_size)
        else:
            self._draw_mouth_open(draw, face_cx, mouth_y, mouth_size, mouth_openness)

        # 합성
        result = Image.alpha_composite(img, overlay)
        return result

    def get_face_image_closed(self, base_image: Image.Image, **kwargs) -> np.ndarray:
        """닫힌 입 프레임 → numpy array"""
        frame = self.compose_frame(base_image, mouth_openness=0.0, **kwargs)
        return np.array(frame.convert("RGB"))

    def get_face_image_open(self, base_image: Image.Image,
                            openness: float = 0.8, **kwargs) -> np.ndarray:
        """열린 입 프레임 → numpy array"""
        frame = self.compose_frame(base_image, mouth_openness=openness, **kwargs)
        return np.array(frame.convert("RGB"))
