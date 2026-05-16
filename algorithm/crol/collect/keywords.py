"""
키워드 관리자 — 고정 키워드 + 매주 트렌드 키워드 조합
"""
import json
import os
from datetime import datetime, date, timedelta
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from crol_config import FIXED_KEYWORDS, KEYWORDS_FILE, TREND_KEYWORDS_COUNT


def _load_keywords_file() -> dict:
    if os.path.exists(KEYWORDS_FILE):
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_keywords_file(data: dict):
    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _is_update_needed() -> bool:
    data         = _load_keywords_file()
    last_updated = data.get("updated_at")
    if not last_updated:
        return True
    last_date   = datetime.fromisoformat(last_updated).date()
    today       = date.today()
    this_monday = today - timedelta(days=today.weekday())
    return last_date < this_monday


def get_active_keywords() -> list[str]:
    data           = _load_keywords_file()
    trend_keywords = data.get("trend_keywords", [])
    seen, result   = set(), []
    for kw in FIXED_KEYWORDS + trend_keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


def update_trend_keywords(force: bool = False) -> list[str]:
    if not force and not _is_update_needed():
        data           = _load_keywords_file()
        trend_keywords = data.get("trend_keywords", [])
        print(f"[keyword] 이번 주 트렌드 키워드 이미 최신 ({len(trend_keywords)}개) — 스킵")
        return trend_keywords

    from collect.naver import get_top_trending_keywords
    trend_keywords = get_top_trending_keywords(n=TREND_KEYWORDS_COUNT)

    data                   = _load_keywords_file()
    data["trend_keywords"] = trend_keywords
    data["updated_at"]     = datetime.now().isoformat()
    _save_keywords_file(data)

    print(f"[keyword] 트렌드 키워드 갱신 완료: {trend_keywords}")
    return trend_keywords


def print_active_keywords():
    data    = _load_keywords_file()
    active  = get_active_keywords()
    updated = data.get("updated_at", "없음")

    print(f"\n{'='*45}")
    print(f"  활성 키워드 ({len(active)}개) | 마지막 갱신: {updated[:10] if updated != '없음' else '없음'}")
    print(f"{'='*45}")
    print("\n  [고정 키워드]")
    for kw in FIXED_KEYWORDS:
        print(f"    • {kw}")

    trend = data.get("trend_keywords", [])
    print(f"\n  [트렌드 키워드 — 이번주 TOP {TREND_KEYWORDS_COUNT}]")
    if trend:
        for kw in trend:
            print(f"    • {kw}")
    else:
        print("    (아직 갱신 안 됨)")
    print()
