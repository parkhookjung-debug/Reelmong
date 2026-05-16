"""
시계열 예측 모듈

- 단순 선형회귀 (numpy polyfit) — 데이터 적을 때도 동작
- 이동평균 + 모멘텀 기반 fallback
- 키워드/패턴별 다음 N개월 예측
- 백테스트 검증 함수
"""
import sys
import os
from datetime import datetime
from typing import Iterable

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from analyze.trend_analyzer import (
    monthly_keyword_metrics,
    monthly_all_keywords,
    monthly_hook_pattern_usage,
)


def _to_xy(monthly: dict[str, dict], metric: str = "avg_views") -> tuple[np.ndarray, np.ndarray]:
    """월별 데이터 → (X=시퀀스 인덱스, Y=메트릭값) 변환"""
    sorted_months = sorted(monthly.keys())
    if not sorted_months:
        return np.array([]), np.array([])
    x = np.arange(len(sorted_months), dtype=float)
    y = np.array([monthly[m].get(metric, 0) for m in sorted_months], dtype=float)
    return x, y


def _next_months(last_month: str, n: int) -> list[str]:
    """'2025-12'부터 다음 n개월 라벨 생성"""
    y, m = map(int, last_month.split("-"))
    out = []
    for _ in range(n):
        m += 1
        if m > 12:
            m = 1
            y += 1
        out.append(f"{y}-{m:02d}")
    return out


def predict_linear(monthly: dict[str, dict], n_months: int = 3,
                   metric: str = "avg_views") -> list[dict]:
    """
    선형회귀 기반 다음 n개월 예측
    데이터 부족(<3개월) 시 마지막 값 유지 (naive)
    """
    sorted_months = sorted(monthly.keys())
    if len(sorted_months) < 3:
        # naive: 마지막 값 유지
        last_val = monthly[sorted_months[-1]].get(metric, 0) if sorted_months else 0
        last_m = sorted_months[-1] if sorted_months else datetime.now().strftime("%Y-%m")
        return [
            {"month": m, "predicted": round(last_val, 1), "method": "naive"}
            for m in _next_months(last_m, n_months)
        ]

    x, y = _to_xy(monthly, metric)
    # 1차 선형회귀
    slope, intercept = np.polyfit(x, y, 1)

    # R^2 신뢰도
    y_pred  = slope * x + intercept
    ss_res  = np.sum((y - y_pred) ** 2)
    ss_tot  = np.sum((y - y.mean()) ** 2)
    r2      = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    # 다음 n개월 예측
    last_idx     = len(x) - 1
    next_indices = np.arange(last_idx + 1, last_idx + 1 + n_months)
    predictions  = slope * next_indices + intercept
    predictions  = np.maximum(predictions, 0)  # 음수 방지

    future_months = _next_months(sorted_months[-1], n_months)
    return [
        {
            "month": fm,
            "predicted": round(float(p), 1),
            "confidence": round(max(0, r2), 3),
            "method": "linear",
        }
        for fm, p in zip(future_months, predictions)
    ]


def predict_keyword(keyword: str, n_months: int = 3) -> dict:
    """특정 키워드의 다음 N개월 평균 조회수 예측"""
    monthly = monthly_keyword_metrics(keyword)
    forecast = predict_linear(monthly, n_months=n_months, metric="avg_views")
    return {
        "keyword": keyword,
        "history": dict(sorted(monthly.items())),
        "forecast": forecast,
    }


def predict_all_keywords(n_months: int = 3, min_total: int = 30) -> list[dict]:
    """전체 키워드 일괄 예측"""
    all_data = monthly_all_keywords()
    results = []
    for keyword, monthly in all_data.items():
        total = sum(m["count"] for m in monthly.values())
        if total < min_total:
            continue
        forecast = predict_linear(monthly, n_months=n_months, metric="avg_views")
        # 마지막 history 값 대비 마지막 forecast 값 → 성장 예측
        last_hist  = monthly[max(monthly.keys())]["avg_views"] if monthly else 0
        last_fcast = forecast[-1]["predicted"] if forecast else 0
        growth_pct = ((last_fcast - last_hist) / max(last_hist, 1)) * 100

        results.append({
            "keyword": keyword,
            "current_avg_views": last_hist,
            "predicted_avg_views": last_fcast,
            "growth_pct": round(growth_pct, 1),
            "confidence": forecast[0].get("confidence", 0) if forecast else 0,
            "forecast": forecast,
        })

    results.sort(key=lambda x: x["growth_pct"], reverse=True)
    return results


def predict_2026_winners(top_n: int = 20) -> dict:
    """
    2026년 잠재 트렌드 TOP 종합 예측
    1) 음식/지역 키워드 라이징 TOP N
    2) 후킹 패턴 라이징 TOP N
    """
    keyword_predictions = predict_all_keywords(n_months=6, min_total=20)
    rising_keywords     = [k for k in keyword_predictions if k["growth_pct"] > 20][:top_n]

    # 후킹 패턴 예측
    hook_monthly = monthly_hook_pattern_usage()
    hook_preds = []
    for pattern_name, by_month in hook_monthly.items():
        if not by_month or len(by_month) < 2:
            continue
        synth = {m: {"avg_views": c} for m, c in by_month.items()}
        forecast = predict_linear(synth, n_months=3, metric="avg_views")
        last_hist  = by_month[max(by_month.keys())]
        last_fcast = forecast[-1]["predicted"] if forecast else 0
        growth = ((last_fcast - last_hist) / max(last_hist, 1)) * 100
        hook_preds.append({
            "pattern": pattern_name,
            "current_count": last_hist,
            "predicted_count": last_fcast,
            "growth_pct": round(growth, 1),
        })
    hook_preds.sort(key=lambda x: x["growth_pct"], reverse=True)

    return {
        "rising_keywords": rising_keywords,
        "rising_hook_patterns": hook_preds[:top_n],
    }


# ── 백테스트 검증 ──────────────────────────────────────────────
def backtest(keyword: str, holdout_months: int = 3) -> dict:
    """
    마지막 holdout_months 개월을 가린 채 예측 → 실제와 비교
    반환: MAE (Mean Absolute Error) + 정확도
    """
    monthly = monthly_keyword_metrics(keyword)
    sorted_months = sorted(monthly.keys())
    if len(sorted_months) < holdout_months + 3:
        return {"error": "데이터 부족 — 백테스트 불가"}

    train_months = sorted_months[:-holdout_months]
    test_months  = sorted_months[-holdout_months:]
    train_data   = {m: monthly[m] for m in train_months}

    forecast = predict_linear(train_data, n_months=holdout_months)
    predicted = [f["predicted"] for f in forecast]
    actual    = [monthly[m]["avg_views"] for m in test_months]

    errors = [abs(p - a) for p, a in zip(predicted, actual)]
    mae    = sum(errors) / len(errors)
    mape   = sum(abs(p - a) / max(a, 1) for p, a in zip(predicted, actual)) / len(actual) * 100

    return {
        "keyword": keyword,
        "train_months": train_months,
        "test_months": test_months,
        "predicted": predicted,
        "actual": actual,
        "mae": round(mae, 1),
        "mape_pct": round(mape, 1),
        "accuracy_pct": round(max(0, 100 - mape), 1),
    }
