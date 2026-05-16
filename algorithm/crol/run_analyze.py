"""
트렌드 분석 + 2026 예측 실행 진입점

사용법:
  python run_analyze.py                     # 전체 분석 리포트
  python run_analyze.py --rising            # 라이징 키워드만
  python run_analyze.py --falling           # 폴링 키워드만
  python run_analyze.py --hooks             # 후킹 패턴 트렌드
  python run_analyze.py --predict           # 2026 예측 TOP
  python run_analyze.py --backtest 마라탕   # 키워드 백테스트
  python run_analyze.py --keyword 마라탕    # 특정 키워드 상세
"""
import argparse
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyze.trend_analyzer import (
    rising_keywords,
    falling_keywords,
    hook_pattern_trends,
    fast_growing_channels,
    monthly_keyword_metrics,
)
from analyze.predictor import predict_keyword, predict_2026_winners, backtest


def print_rising():
    print("\n=== 🔥 라이징 키워드 TOP 20 ===")
    print(f"{'키워드':<15}{'영상수':<8}{'이전':<12}{'최근':<12}{'성장률':<10}")
    print("-" * 60)
    for k in rising_keywords(20):
        print(f"{k['keyword']:<15}{k['total_videos']:<8}"
              f"{int(k['prev']):>10,}  {int(k['recent']):>10,}  "
              f"+{k['growth_pct']:.1f}%")


def print_falling():
    print("\n=== ❄️ 폴링 키워드 TOP 20 ===")
    print(f"{'키워드':<15}{'영상수':<8}{'이전':<12}{'최근':<12}{'성장률':<10}")
    print("-" * 60)
    for k in falling_keywords(20):
        print(f"{k['keyword']:<15}{k['total_videos']:<8}"
              f"{int(k['prev']):>10,}  {int(k['recent']):>10,}  "
              f"{k['growth_pct']:.1f}%")


def print_hooks():
    print("\n=== 💬 후킹 패턴 트렌드 ===")
    for h in hook_pattern_trends():
        arrow = "📈" if h["direction"] == "rising" else ("📉" if h["direction"] == "falling" else "➡️")
        print(f"  {arrow} {h['pattern']:<10} {h['direction']:<8} "
              f"이전: {h['prev']:.0f} → 최근: {h['recent']:.0f}  "
              f"({h['growth_pct']:+.1f}%)")
        # 월별 사용량 표시
        for m, c in list(h["monthly_counts"].items())[-6:]:
            bar = "█" * min(c // 5, 30)
            print(f"      {m}: {bar} {c}")


def print_channels():
    print("\n=== 🚀 급성장 채널 TOP 20 (스냅샷 비교) ===")
    print(f"{'채널명':<30}{'시작 구독':<12}{'최근 구독':<12}{'성장률':<10}")
    print("-" * 70)
    for c in fast_growing_channels(20):
        print(f"{c['title'][:28]:<30}"
              f"{c['first_subs']:>10,}  {c['last_subs']:>10,}  "
              f"+{c['growth_pct']:.1f}%   ({c['from_to']})")


def print_2026_predictions():
    print("\n=== 🔮 2026년 잠재 트렌드 예측 ===")
    pred = predict_2026_winners(top_n=15)

    print("\n  [예측: 2026 라이징 키워드]")
    for k in pred["rising_keywords"][:15]:
        print(f"    +{k['growth_pct']:>6.1f}%  {k['keyword']:<15}  "
              f"현재 {int(k['current_avg_views']):>10,}뷰 → "
              f"예측 {int(k['predicted_avg_views']):>10,}뷰  "
              f"(신뢰도 {k['confidence']:.0%})")

    print("\n  [예측: 2026 라이징 후킹 패턴]")
    for h in pred["rising_hook_patterns"][:10]:
        print(f"    {h['growth_pct']:+>6.1f}%  {h['pattern']:<10}  "
              f"현재 {int(h['current_count']):>5}개 → "
              f"예측 {int(h['predicted_count']):>5}개")


def print_keyword_detail(keyword: str):
    print(f"\n=== 키워드 상세: '{keyword}' ===")
    monthly = monthly_keyword_metrics(keyword)
    if not monthly:
        print(f"  데이터 없음")
        return

    print(f"\n  [월별 영상 수 / 평균 조회수]")
    for m, d in sorted(monthly.items()):
        bar = "█" * min(d["count"] // 5, 30)
        print(f"    {m}: {bar} {d['count']:3}개  "
              f"평균 {int(d['avg_views']):>10,}뷰")

    pred = predict_keyword(keyword, n_months=6)
    print(f"\n  [향후 6개월 예측]")
    for f in pred["forecast"]:
        print(f"    {f['month']}: 예측 {int(f['predicted']):>10,}뷰  "
              f"(신뢰도 {f.get('confidence', 0):.0%})")


def print_backtest(keyword: str):
    print(f"\n=== 백테스트: '{keyword}' ===")
    result = backtest(keyword, holdout_months=3)
    if "error" in result:
        print(f"  {result['error']}")
        return

    print(f"  학습 기간: {result['train_months'][0]} ~ {result['train_months'][-1]}")
    print(f"  검증 기간: {result['test_months'][0]} ~ {result['test_months'][-1]}")
    print()
    print(f"  {'월':<10}{'예측':<15}{'실제':<15}{'오차':<12}")
    for m, p, a in zip(result['test_months'], result['predicted'], result['actual']):
        err = abs(p - a)
        print(f"  {m:<10}{int(p):>12,}   {int(a):>12,}   {int(err):>10,}")
    print()
    print(f"  평균 절대오차 (MAE) : {result['mae']:>10,.0f}")
    print(f"  평균 오차율 (MAPE)  : {result['mape_pct']:>10.1f}%")
    print(f"  예측 정확도         : {result['accuracy_pct']:>10.1f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rising",   action="store_true")
    parser.add_argument("--falling",  action="store_true")
    parser.add_argument("--hooks",    action="store_true")
    parser.add_argument("--channels", action="store_true")
    parser.add_argument("--predict",  action="store_true")
    parser.add_argument("--keyword",  default=None)
    parser.add_argument("--backtest", default=None)
    args = parser.parse_args()

    any_flag = any([args.rising, args.falling, args.hooks, args.channels,
                    args.predict, args.keyword, args.backtest])

    if args.keyword:
        print_keyword_detail(args.keyword)
        return
    if args.backtest:
        print_backtest(args.backtest)
        return

    if args.rising or not any_flag:
        print_rising()
    if args.falling or not any_flag:
        print_falling()
    if args.hooks or not any_flag:
        print_hooks()
    if args.channels or not any_flag:
        print_channels()
    if args.predict or not any_flag:
        print_2026_predictions()


if __name__ == "__main__":
    main()
