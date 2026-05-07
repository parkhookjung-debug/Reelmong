"""STEP 0: 이미지 전처리 - 배경 제거 (rembg)

음식 사진에서 배경을 제거하여 음식만 남깁니다.
rembg 미설치 시 원본 이미지를 그대로 사용합니다.

설치:
    pip install rembg
"""
from pathlib import Path
from PIL import Image


# 음식 카테고리별 배경 그라디언트 색상 (상단 → 하단)
CATEGORY_BG_COLORS: dict[str, tuple[tuple, tuple]] = {
    "한식":   ((255, 248, 230), (255, 220, 160)),  # 따뜻한 노란 계열
    "중식":   ((255, 240, 230), (255, 190, 140)),  # 주황 계열
    "일식":   ((240, 248, 255), (200, 230, 255)),  # 청량한 파란 계열
    "양식":   ((250, 245, 255), (220, 200, 255)),  # 부드러운 보라 계열
    "카페":   ((250, 240, 225), (210, 185, 155)),  # 라떼 브라운 계열
    "디저트": ((255, 235, 245), (255, 190, 215)),  # 핑크 계열
    "치킨":   ((255, 245, 220), (255, 210, 120)),  # 황금빛 계열
    "피자":   ((255, 242, 230), (255, 200, 150)),  # 오렌지 계열
    "분식":   ((255, 245, 240), (255, 180, 160)),  # 연한 빨강 계열
    "기타":   ((245, 250, 245), (200, 235, 200)),  # 연한 초록 계열
}


def _make_gradient_bg(width: int, height: int, color_top: tuple, color_bot: tuple) -> Image.Image:
    """상하 그라디언트 배경 이미지 생성"""
    import numpy as np
    r = np.linspace(color_top[0], color_bot[0], height).reshape(height, 1)
    g = np.linspace(color_top[1], color_bot[1], height).reshape(height, 1)
    b = np.linspace(color_top[2], color_bot[2], height).reshape(height, 1)
    gradient = np.stack([r, g, b], axis=2).astype("uint8")
    gradient = np.repeat(gradient, width, axis=1)
    return Image.fromarray(gradient, "RGB")


def remove_background(image_path: str, output_path: str = None) -> tuple[str, bool]:
    """음식 이미지에서 배경 제거

    Args:
        image_path: 입력 이미지 경로
        output_path: 출력 PNG 경로 (None이면 자동 생성)

    Returns:
        (output_path, was_removed): 결과 경로, 실제 제거 여부
    """
    try:
        from rembg import remove as rembg_remove
        HAS_REMBG = True
    except ImportError:
        HAS_REMBG = False

    if not HAS_REMBG:
        print("[!] rembg 미설치 → 배경 제거 생략 (pip install rembg 로 설치)")
        return image_path, False

    if output_path is None:
        p = Path(image_path)
        output_path = str(p.parent / f"{p.stem}_nobg.png")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    print("    [rembg] 배경 제거 중...")
    with open(image_path, "rb") as f:
        input_data = f.read()

    output_data = rembg_remove(input_data)

    with open(output_path, "wb") as f:
        f.write(output_data)

    print(f"    [rembg] 완료 → {Path(output_path).name}")
    return output_path, True


def compose_on_color_bg(
    nobg_path: str,
    category: str = "기타",
    output_path: str = None,
    padding_ratio: float = 0.08,
) -> str:
    """배경 제거된 음식 이미지를 카테고리별 그라디언트 배경 위에 합성

    음식을 중앙에 배치하고, 주변에 여백을 주어 자연스럽게 합성합니다.

    Args:
        nobg_path: 배경 제거된 PNG (RGBA)
        category: 음식 카테고리
        output_path: 출력 경로
        padding_ratio: 여백 비율 (0.08 = 8%)

    Returns:
        합성된 이미지 경로 (PNG)
    """
    img = Image.open(nobg_path).convert("RGBA")
    w, h = img.size

    # 카테고리 배경 색상
    color_top, color_bot = CATEGORY_BG_COLORS.get(category, CATEGORY_BG_COLORS["기타"])
    bg = _make_gradient_bg(w, h, color_top, color_bot).convert("RGBA")

    # 음식 이미지에 그림자 효과 (alpha를 약간 블러)
    try:
        from PIL import ImageFilter
        shadow_img = img.copy()
        shadow_alpha = shadow_img.split()[3].filter(ImageFilter.GaussianBlur(radius=12))
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow.putalpha(shadow_alpha)
        # 그림자를 아래-오른쪽으로 8px 오프셋
        offset_shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        offset_shadow.paste(shadow, (8, 12))
        # 그림자 어둡게
        dark = Image.new("RGBA", (w, h), (30, 20, 10, 100))
        shadow_final = Image.alpha_composite(Image.new("RGBA", (w, h), (0, 0, 0, 0)), offset_shadow)
        shadow_final = Image.blend(shadow_final, dark, 0.0)
        bg = Image.alpha_composite(bg, shadow_final)
    except Exception:
        pass  # 그림자 실패해도 계속 진행

    # 음식 합성
    result = Image.alpha_composite(bg, img)

    if output_path is None:
        p = Path(nobg_path)
        output_path = str(p.parent / f"{p.stem}_composed.png")

    result.convert("RGB").save(output_path)
    return output_path
