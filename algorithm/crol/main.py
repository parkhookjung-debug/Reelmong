"""
전체 파이프라인 수동 실행
실행: python main.py [옵션]

옵션:
  --date YYYY-MM-DD    분석할 날짜 (기본: 오늘)
  --skip-collect       수집 건너뛰기
  --only-recommend     저장된 최신 결과로 추천만 출력
  --update-keywords    네이버 트렌드 키워드 지금 바로 갱신
  --show-keywords      현재 활성 키워드 목록 출력
"""
import argparse
from datetime import date

from db.database import init_db
from collect.youtube import run_collection
from collect.keywords import update_trend_keywords, print_active_keywords
from analyze.analyzer import analyze_date, print_stats
from analyze.recommender import generate_recommendations, print_recommendations


def main():
    parser = argparse.ArgumentParser(description="YouTube 음식 쇼츠 트렌드 수집 & 추천")
    parser.add_argument("--date", default=None)
    parser.add_argument("--skip-collect", action="store_true")
    parser.add_argument("--only-recommend", action="store_true")
    parser.add_argument("--update-keywords", action="store_true")
    parser.add_argument("--show-keywords", action="store_true")
    args = parser.parse_args()

    init_db()

    if args.show_keywords:
        print_active_keywords()
        return

    if args.update_keywords:
        update_trend_keywords(force=True)
        print_active_keywords()
        return

    if args.only_recommend:
        print_recommendations(generate_recommendations())
        return

    target_date = args.date or date.today().isoformat()

    # 1. 매주 트렌드 키워드 자동 갱신
    update_trend_keywords(force=False)
    print_active_keywords()

    # 2. 수집
    if not args.skip_collect:
        run_collection()

    # 3. 분석
    stats = analyze_date(target_date)
    print_stats(stats)

    # 4. 추천
    print_recommendations(generate_recommendations(stats))


if __name__ == "__main__":
    main()
