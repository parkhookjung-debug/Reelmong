"""
컴퓨터 시작 시 1회 수집 스크립트
Windows 작업 스케줄러 → 로그온 시 실행
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import init_db
from collect.youtube import run_collection
from collect.keywords import update_trend_keywords
from analyze.analyzer import analyze_date

if __name__ == "__main__":
    print("[시작] 수집 시작...")
    init_db()
    update_trend_keywords(force=False)
    snapshot_at = run_collection()
    analyze_date(snapshot_at[:10])
    print("[완료] 수집 완료")
