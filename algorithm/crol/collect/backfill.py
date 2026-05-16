"""
연/월별 백필 수집기

특정 연도(예: 2025)의 1~12월 × 확장 키워드별로
월간 상위 50개 영상(조회수 기준)을 수집.

특징:
- 진행 상태 파일(backfill_progress.json)에 (연,월,키워드) 단위로 기록
- API 할당량 초과 시 자동 종료 → 다음날 이어서 진행
- 재실행해도 이미 수집한 조합은 스킵
"""
import json
import os
import sys
import time
from datetime import datetime
from typing import Iterable

from googleapiclient.errors import HttpError

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from crol_config import REGION_CODE
from collect.keywords_expanded import FOOD_KEYWORDS_EXPANDED
from collect.youtube import (
    _build_service,
    _fetch_video_details,
    _build_row,
    collect_channel_stats,
)
from db.database import upsert_video

PROGRESS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "backfill_progress.json",
)


class QuotaExceededError(Exception):
    pass


def _load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed": [], "stats": {}}


def _save_progress(p: dict) -> None:
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def _month_range_iso(year: int, month: int) -> tuple[str, str]:
    """해당 월의 시작 ~ 다음 월의 시작 (ISO 8601 UTC)"""
    after = f"{year}-{month:02d}-01T00:00:00Z"
    if month == 12:
        before = f"{year+1}-01-01T00:00:00Z"
    else:
        before = f"{year}-{month+1:02d}-01T00:00:00Z"
    return after, before


def backfill_one(service, year: int, month: int, keyword: str) -> tuple[int, list[str]]:
    """
    (연, 월, 키워드) 조합 1건 백필 — 조회수 순 상위 50개
    반환: (저장된 영상 수, 채널 ID 목록)
    """
    after, before = _month_range_iso(year, month)
    snapshot_at   = f"{year}-{month:02d}-15 12:00:00"  # 월 중간으로 통일

    try:
        resp = service.search().list(
            part="id",
            q=keyword + " #shorts",
            type="video",
            videoDuration="short",
            order="viewCount",
            regionCode=REGION_CODE,
            relevanceLanguage="ko",
            maxResults=50,
            publishedAfter=after,
            publishedBefore=before,
        ).execute()
    except HttpError as e:
        if e.resp.status == 403 and "quotaExceeded" in str(e):
            raise QuotaExceededError()
        # 다른 에러는 그냥 빈 결과로 처리
        print(f"  [!] search 실패: {e}")
        return 0, []

    video_ids = [
        item["id"]["videoId"]
        for item in resp.get("items", [])
        if item.get("id", {}).get("kind") == "youtube#video"
    ]
    if not video_ids:
        return 0, []

    try:
        details = _fetch_video_details(service, video_ids)
    except HttpError as e:
        if e.resp.status == 403 and "quotaExceeded" in str(e):
            raise QuotaExceededError()
        print(f"  [!] 영상 상세 실패: {e}")
        return 0, []

    channel_ids = []
    for vid, item in details.items():
        row             = _build_row(vid, item, snapshot_at, "backfill", keyword)
        row["source"]   = "backfill"
        upsert_video(row)
        ch_id = item.get("snippet", {}).get("channelId", "")
        if ch_id:
            channel_ids.append(ch_id)

    return len(details), channel_ids


def run_backfill(
    year: int = 2025,
    months: Iterable[int] = range(1, 13),
    keywords: list[str] | None = None,
    sleep_between: float = 0.3,
    max_calls: int | None = None,
    iterate_by: str = "keyword_first",
) -> None:
    """
    백필 실행 (API 할당량 다 쓰면 자동 종료, 진행 상태 저장)

    Args:
        year       : 백필 대상 연도
        months     : 대상 월 (기본 1~12)
        keywords   : 사용할 키워드 (기본 FOOD_KEYWORDS_EXPANDED 전체)
        iterate_by : "keyword_first" → 각 키워드의 전 월을 먼저 채움 (조기 트렌드 분석 가능)
                     "month_first"   → 각 월의 전 키워드를 먼저 채움
    """
    keywords = list(keywords or FOOD_KEYWORDS_EXPANDED)
    months   = list(months)
    progress = _load_progress()
    completed = set(progress["completed"])
    stats     = progress.get("stats") or {}
    stats.setdefault("videos",   0)
    stats.setdefault("channels", 0)
    stats.setdefault("calls",    0)

    service = _build_service()
    all_channels: set[str] = set()
    new_video_count = 0
    new_calls       = 0

    total_combos    = len(months) * len(keywords)
    done_combos     = sum(1 for k in completed if k.startswith(f"{year}-"))

    # 이터레이션 순서 결정
    if iterate_by == "keyword_first":
        combos = [(m, kw) for kw in keywords for m in months]
    else:
        combos = [(m, kw) for m in months for kw in keywords]

    print(f"=== {year}년 백필 시작 ===")
    print(f"  키워드: {len(keywords)}개 | 월: {len(months)}개 | 순서: {iterate_by}")
    print(f"  총 조합: {total_combos:,}개 / 누적 완료: {done_combos:,}개")
    print(f"  진행률: {done_combos/max(total_combos,1)*100:.1f}%")

    try:
        for month, keyword in combos:
            key = f"{year}-{month:02d}_{keyword}"
            if key in completed:
                continue

            # 일일 호출 제한 도달
            if max_calls is not None and new_calls >= max_calls:
                print(f"\n[백필] 일일 호출 제한 {max_calls}건 도달 — 종료")
                print("       내일 다시 실행하면 이어서 진행됩니다.")
                return

            try:
                n, channels = backfill_one(service, year, month, keyword)
            except QuotaExceededError:
                print("\n[!] YouTube API 일일 할당량 초과")
                print("    내일 다시 실행하면 이어서 진행됩니다.")
                return

            new_video_count += n
            new_calls       += 1
            all_channels.update(channels)
            completed.add(key)
            progress["completed"] = list(completed)
            _save_progress(progress)

            # 진행 표시 (10개마다)
            if new_calls % 10 == 0:
                cumul = len(completed)
                print(
                    f"  [{year}-{month:02d}] '{keyword[:10]}' {n}개 | "
                    f"누적 {cumul}/{total_combos} ({cumul/total_combos*100:.1f}%)"
                )
            time.sleep(sleep_between)
    finally:
        if all_channels:
            try:
                print(f"\n채널 통계 수집 중... ({len(all_channels)}개)")
                snapshot_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                collect_channel_stats(snapshot_at, list(all_channels))
            except QuotaExceededError:
                print("[!] 채널 수집 도중 할당량 초과 (다음에 보충)")
            except Exception as e:
                print(f"[!] 채널 수집 실패: {e}")

        stats["videos"]   += new_video_count
        stats["calls"]    += new_calls
        stats["channels"] += len(all_channels)
        progress["stats"]  = stats
        _save_progress(progress)

        print(f"\n=== 이번 세션 결과 ===")
        print(f"  새 영상: {new_video_count:,}개")
        print(f"  새 채널 통계: {len(all_channels):,}개")
        print(f"  API 호출: {new_calls:,}회")
        print(f"  누적: 영상 {stats['videos']:,} / 채널 {stats['channels']:,} / 호출 {stats['calls']:,}")
