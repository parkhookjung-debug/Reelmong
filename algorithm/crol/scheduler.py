"""
하루 3회 자동 수집 스케줄러
실행: python scheduler.py
종료: Ctrl+C
"""
import time
import schedule
from datetime import datetime

from crol_config import SCHEDULE_TIMES
from collect.youtube import run_collection
from collect.keywords import update_trend_keywords
from analyze.analyzer import analyze_date
from analyze.recommender import generate_recommendations, print_recommendations


def _job():
    update_trend_keywords(force=False)
    snapshot_at = run_collection()
    stats       = analyze_date(snapshot_at[:10])
    print_recommendations(generate_recommendations(stats))


def start():
    print(f"[scheduler] 스케줄 등록: {SCHEDULE_TIMES}")
    for t in SCHEDULE_TIMES:
        schedule.every().day.at(t).do(_job)
    print("[scheduler] 대기 중... (Ctrl+C 로 종료)\n")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    start()
