"""
네이버 데이터랩 검색어 트렌드 API 연동
"""
import time
from datetime import datetime, timedelta

import requests
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from crol_config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, TREND_KEYWORD_CANDIDATES, TREND_KEYWORDS_COUNT

DATALAB_URL = "https://openapi.naver.com/v1/datalab/search"


def _date_range() -> tuple[str, str]:
    end   = datetime.today()
    start = end - timedelta(weeks=4)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _query_batch(keyword_groups: list[dict], start: str, end: str) -> dict:
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise ValueError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 설정되지 않았습니다.")

    headers = {
        "X-Naver-Client-Id"    : NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "Content-Type"         : "application/json",
    }
    body = {
        "startDate"    : start,
        "endDate"      : end,
        "timeUnit"     : "week",
        "keywordGroups": keyword_groups,
    }

    resp = requests.post(DATALAB_URL, headers=headers, json=body, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    result = {}
    for item in data.get("results", []):
        name   = item["title"]
        ratios = [p["ratio"] for p in item.get("data", []) if p.get("ratio") is not None]
        result[name] = round(sum(ratios) / len(ratios), 2) if ratios else 0.0
    return result


def fetch_keyword_scores(keywords: list[str] | None = None) -> dict[str, float]:
    if keywords is None:
        keywords = TREND_KEYWORD_CANDIDATES

    start, end = _date_range()
    scores: dict[str, float] = {}

    for i in range(0, len(keywords), 5):
        batch  = keywords[i:i+5]
        groups = [{"groupName": kw, "keywords": [kw]} for kw in batch]
        try:
            batch_scores = _query_batch(groups, start, end)
            scores.update(batch_scores)
            print(f"  [naver] {i+1}~{i+len(batch)}번 키워드 조회 완료")
        except Exception as e:
            print(f"  [naver] 배치 오류 ({batch}): {e}")
        if i + 5 < len(keywords):
            time.sleep(0.5)

    return scores


def get_top_trending_keywords(n: int | None = None) -> list[str]:
    if n is None:
        n = TREND_KEYWORDS_COUNT

    print(f"\n[naver] 트렌드 키워드 조회 중... (후보 {len(TREND_KEYWORD_CANDIDATES)}개)")
    scores = fetch_keyword_scores()

    if not scores:
        print("[naver] 조회 실패. 빈 리스트 반환")
        return []

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top    = [kw for kw, _ in ranked[:n]]
    print(f"[naver] 트렌드 TOP {n}: {top}")
    return top


def print_scores(scores: dict[str, float]):
    print(f"\n{'='*45}")
    print(f"  네이버 데이터랩 키워드 검색량 (최근 4주)")
    print(f"{'='*45}")
    for kw, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(score / 3)
        print(f"  {kw:<16} {bar} ({score})")
    print()
