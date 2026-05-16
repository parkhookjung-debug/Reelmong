"""
2025년 백필 수집 실행 진입점

사용법:
  python run_backfill.py              # 2025 전체 (1~12월)
  python run_backfill.py --year 2024  # 2024 전체
  python run_backfill.py --months 7-12  # 2025 후반기만
  python run_backfill.py --status     # 진행 상황만 출력
"""
import argparse
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import init_db
from collect.backfill import run_backfill, PROGRESS_FILE
from collect.keywords_expanded import FOOD_KEYWORDS_EXPANDED


def parse_months(arg: str) -> list[int]:
    if "-" in arg:
        a, b = arg.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in arg.split(",")]


def show_status():
    print("\n=== 백필 진행 상황 ===")
    if not os.path.exists(PROGRESS_FILE):
        print("  진행 기록 없음 (아직 미실행)")
        return
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        p = json.load(f)
    completed = p.get("completed", [])
    stats     = p.get("stats", {})

    # 연도별 집계
    by_year_month = {}
    for k in completed:
        ym = k.split("_")[0]
        by_year_month[ym] = by_year_month.get(ym, 0) + 1

    print(f"  완료된 조합: {len(completed):,}개")
    print(f"  누적 영상  : {stats.get('videos', 0):,}개")
    print(f"  누적 채널  : {stats.get('channels', 0):,}개")
    print(f"  누적 API   : {stats.get('calls', 0):,}회")
    print(f"\n  [월별 진행]")
    for ym in sorted(by_year_month.keys()):
        n = by_year_month[ym]
        bar = "█" * min(n // 5, 40)
        print(f"    {ym}: {bar} {n}/{len(FOOD_KEYWORDS_EXPANDED)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year",   type=int, default=2025)
    parser.add_argument("--months", default="1-12", help="예: '1-12' 또는 '6,7,8'")
    parser.add_argument("--status", action="store_true", help="진행 상황만 출력")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    init_db()
    months = parse_months(args.months)
    print(f"대상: {args.year}년 {months}월")
    print(f"키워드: {len(FOOD_KEYWORDS_EXPANDED)}개")
    print(f"예상 총 조합: {len(months) * len(FOOD_KEYWORDS_EXPANDED):,}개")
    print(f"예상 API 비용: {len(months) * len(FOOD_KEYWORDS_EXPANDED) * 101:,} units\n")

    run_backfill(year=args.year, months=months)


if __name__ == "__main__":
    main()
