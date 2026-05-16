"""
추천 실행 진입점 (수집과 완전 분리)
실행: python recommend.py

옵션:
  --food   음식 종류 (필수)
  --script 대본 텍스트 (선택, 없으면 직접 입력)
  --no-ollama  Ollama 없이 템플릿만 사용
  --check  Ollama 연결 확인
"""
import argparse
import sys

from recommend.engine    import run, print_result
from recommend.ollama_gen import check_connection


def main():
    parser = argparse.ArgumentParser(description="음식 쇼츠 제목/태그 추천")
    parser.add_argument("--food",      default=None, help="음식 종류 (예: 카페라떼, 삼겹살)")
    parser.add_argument("--script",    default=None, help="영상 대본 텍스트")
    parser.add_argument("--no-ollama", action="store_true", help="템플릿만 사용")
    parser.add_argument("--check",     action="store_true", help="Ollama 연결 확인")
    args = parser.parse_args()

    # Ollama 연결 확인 모드
    if args.check:
        check_connection()
        return

    # 음식 종류 입력
    food_type = args.food
    if not food_type:
        food_type = input("음식 종류를 입력하세요 (예: 카페라떼, 삼겹살): ").strip()
        if not food_type:
            print("음식 종류를 입력해야 합니다.")
            sys.exit(1)

    # 대본 입력
    script = args.script
    if not script:
        print("영상 대본을 입력하세요 (입력 완료 후 빈 줄에서 Enter 두 번):")
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        script = "\n".join(lines)

    if not script.strip():
        script = food_type  # 대본 없으면 음식 종류로 대체

    # 추천 실행
    use_ollama = not args.no_ollama
    result     = run(script=script, food_type=food_type, use_ollama=use_ollama)
    print_result(result)


if __name__ == "__main__":
    main()
