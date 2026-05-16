"""
컴퓨터 시작 시 매일 1회 백필 진행 스크립트

특징:
- 일일 자동 수집 후 남은 API quota 안에서 백필 진행
- 같은 날 이미 한 번 실행했으면 스킵
- 진행 상태는 backfill_progress.json에 누적 (재실행 시 이어서)
- 네트워크 미연결 감지 → 종료
- 단계별 실패해도 다음 실행에서 이어서 계속
"""
from __future__ import annotations

import io
import logging
import os
import socket
import sys
import time
from datetime import date, datetime
from logging.handlers import RotatingFileHandler

# ── 경로 / 인코딩 ──────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
os.chdir(_HERE)

LOG_DIR    = os.path.join(_HERE, "logs")
LOCK_FILE  = os.path.join(_HERE, ".backfill_daily.lock")
TODAY_DONE = os.path.join(_HERE, f".backfill_done_{date.today().isoformat()}")

os.makedirs(LOG_DIR, exist_ok=True)

# 일일 호출 제한 (regular collection ~20 calls 후 남은 quota)
# 70 calls × 6개월 = 키워드 당 6 calls → 일일 약 11~12개 키워드 풀히스토리 완성
DAILY_MAX_CALLS = 70

# 백필 대상
TARGET_YEAR   = 2025
TARGET_MONTHS = list(range(7, 13))  # 7~12월 후반기

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

# ── 로깅 ───────────────────────────────────────────────────────────
log = logging.getLogger("backfill_daily")
log.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

_log_path = os.path.join(LOG_DIR, f"backfill_{date.today().isoformat()}.log")
_fh = RotatingFileHandler(_log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
_fh.setFormatter(_fmt)
log.addHandler(_fh)

_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
log.addHandler(_sh)


def has_network(timeout: float = 5.0) -> bool:
    """여러 엔드포인트 시도 — 하나라도 연결되면 OK"""
    targets = [
        ("8.8.8.8",        53),    # Google DNS (TCP)
        ("1.1.1.1",        53),    # Cloudflare DNS
        ("www.google.com", 80),    # HTTP
        ("youtube.com",    443),   # HTTPS — YouTube 직접
    ]
    for host, port in targets:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def acquire_lock() -> bool:
    if os.path.exists(LOCK_FILE):
        age = time.time() - os.path.getmtime(LOCK_FILE)
        if age < 60 * 60:
            log.warning(f"다른 백필 프로세스 진행 중 (age={int(age)}s) — 종료")
            return False
        log.warning(f"스테일 락 제거 (age={int(age)}s)")
        try:
            os.remove(LOCK_FILE)
        except OSError:
            return False
    try:
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n{datetime.now().isoformat()}\n")
        return True
    except OSError:
        return False


def release_lock() -> None:
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except OSError:
        pass


def main() -> int:
    log.info("=" * 60)
    log.info(f"[백필 데몬] PID={os.getpid()}")

    # 오늘 이미 실행했으면 스킵
    if os.path.exists(TODAY_DONE):
        log.info("오늘 백필 이미 진행됨 — 스킵")
        return 0

    if not has_network():
        log.error("네트워크 미연결 → 종료")
        return 2

    if not acquire_lock():
        return 3

    try:
        # 일일 자동 수집(collect_once)가 먼저 끝나도록 60초 대기
        log.info("일일 자동 수집 완료 대기 (60초)...")
        time.sleep(60)

        from db.database import init_db
        from collect.backfill import run_backfill

        init_db()
        log.info(f"백필 시작: {TARGET_YEAR}년 {TARGET_MONTHS}월 / 일일 최대 {DAILY_MAX_CALLS}건")

        run_backfill(
            year=TARGET_YEAR,
            months=TARGET_MONTHS,
            max_calls=DAILY_MAX_CALLS,
        )

        # 오늘 마커 생성 (같은 날 중복 실행 방지)
        with open(TODAY_DONE, "w", encoding="utf-8") as f:
            f.write(datetime.now().isoformat())
        log.info("오늘 백필 완료")
        return 0

    except Exception as e:
        log.exception(f"백필 실패: {e}")
        return 1
    finally:
        release_lock()
        log.info("[종료] " + "=" * 56)


if __name__ == "__main__":
    sys.exit(main())
