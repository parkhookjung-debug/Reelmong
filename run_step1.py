"""STEP 1 실행 스크립트 - Vision 이미지 분석 (무료 로컬 버전)

사전 준비:
  1. pip install transformers torch Pillow python-dotenv requests
  2. Ollama 설치 후 'ollama serve' 실행
  3. 'ollama pull gemma3:4b' 로 모델 다운로드
  4. data/images/ 폴더에 매장 이미지 넣기

사용법:
  python run_step1.py --images data/images/img1.jpg data/images/img2.jpg \
                      --name "맛있는 식당" \
                      --intro "강남역 근처 수제 파스타 전문점입니다"

또는 대화형 모드:
  python run_step1.py
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import IMAGES_DIR, OUTPUT_DIR
from src.step1_vision import ImageAnalyzer


def get_test_images() -> list[str]:
    """data/images 폴더에서 이미지 파일 자동 탐색"""
    images = []
    if IMAGES_DIR.exists():
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            images.extend(str(p) for p in IMAGES_DIR.glob(ext))
    return sorted(images)


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


def interactive_mode():
    """대화형 모드"""
    print("=" * 50)
    print("  릴몽 STEP 1: Vision 이미지 분석")
    print("  (BLIP + Ollama 무료 로컬 버전)")
    print("=" * 50)
    print()

    # Ollama 체크
    if not check_ollama():
        return

    # 이미지 탐색
    images = get_test_images()
    if not images:
        print(f"\n[!] data/images 폴더에 이미지가 없습니다.")
        print(f"    → {IMAGES_DIR} 에 매장 이미지를 넣어주세요.")
        print(f"    지원 형식: jpg, jpeg, png, webp")
        return

    print(f"\n[v] 발견된 이미지 {len(images)}장:")
    for i, img in enumerate(images, 1):
        print(f"    {i}. {Path(img).name}")
    print()

    store_name = input("매장 이름: ").strip() or "테스트 매장"
    store_intro = input("매장 소개 (1~3문장): ").strip() or "맛있는 음식을 제공하는 매장입니다"
    category = input("업종 (빈칸=자동판별): ").strip()

    print()
    print("[*] 이미지 분석을 시작합니다...")
    print("    (BLIP 모델 최초 로딩에 1~2분 소요될 수 있습니다)")
    print()

    analyzer = ImageAnalyzer()
    result = analyzer.analyze_store(
        image_paths=images,
        store_name=store_name,
        store_intro=store_intro,
        category=category,
    )

    # 결과 출력
    print()
    print("=" * 50)
    print("  분석 결과")
    print("=" * 50)
    print(result.to_json())

    # 결과 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "step1_result.json"
    result.save(str(output_path))
    print(f"\n[v] 결과 저장: {output_path}")
    print("[v] STEP 1 완료! → 이 JSON이 STEP 2 (스크립트 생성)의 입력이 됩니다.")


def cli_mode(args):
    """CLI 인자 모드"""
    if not check_ollama():
        return

    analyzer = ImageAnalyzer()
    result = analyzer.analyze_store(
        image_paths=args.images,
        store_name=args.name,
        store_intro=args.intro,
        category=args.category or "",
    )

    print(result.to_json())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "step1_result.json"
    result.save(str(output_path))
    print(f"\n[v] 결과 저장: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="릴몽 STEP 1: Vision 이미지 분석")
    parser.add_argument("--images", nargs="+", help="이미지 파일 경로들")
    parser.add_argument("--name", default="테스트 매장", help="매장 이름")
    parser.add_argument("--intro", default="맛있는 음식을 제공합니다", help="매장 소개")
    parser.add_argument("--category", default="", help="업종 카테고리")

    args = parser.parse_args()

    if args.images:
        cli_mode(args)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
