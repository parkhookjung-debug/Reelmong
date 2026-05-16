"""
부팅/로그온 1회 수집 스크립트 (재작성판)

특징:
- 항상 자기 폴더 기준으로 실행 (cwd 무관)
- logs/collect_YYYY-MM-DD.log 에 모든 로그 기록 (스케줄러 silent 실패 방지)
- 단계별 try/except — 한 단계 실패해도 다음 단계 계속 시도
- .collect.lock 으로 중복 실행 방지 (스테일 락 자동 해제)
- 같은 날 이미 성공한 수집이 있으면 스킵 (전원 온/오프 반복 시 중복 방지)
- 네트워크 미연결 감지 → 즉시 종료 (작업 스케줄러 조건과 이중 안전망)
"""
from __future__ import annotations

import io
import logging
import os
import socket
import sqlite3
import sys
import time
from datetime import datetime, date
from logging.handlers import RotatingFileHandler

# ── 0. 경로 / 인코딩 ────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
os.chdir(_HERE)

LOG_DIR  = os.path.join(_HERE, "logs")
LOCK_FILE = os.path.join(_HERE, ".collect.lock")
LOCK_STALE_SECONDS = 60 * 60  # 1시간 이상 된 락은 스테일로 간주

os.makedirs(LOG_DIR, exist_ok=True)

# stdout 도 UTF-8 (작업 스케줄러에서 cp949 → UnicodeEncodeError 방지)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

# ── 1. 로깅 ─────────────────────────────────────────────────────────
log = logging.getLogger("collect_once")
log.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

_log_path = os.path.join(LOG_DIR, f"collect_{date.today().isoformat()}.log")
_fh = RotatingFileHandler(_log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
_fh.setFormatter(_fmt)
log.addHandler(_fh)

_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
log.addHandler(_sh)


# ── 2. 헬퍼 ─────────────────────────────────────────────────────────
def has_network(timeout: float = 5.0) -> bool:
    """여러 엔드포인트 시도 — 하나라도 연결되면 OK"""
    targets = [
        ("8.8.8.8",        53),
        ("1.1.1.1",        53),
        ("www.google.com", 80),
        ("youtube.com",    443),
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
        if age < LOCK_STALE_SECONDS:
            log.warning(f"이미 다른 프로세스가 수집 중인 것으로 보임 (lock age={int(age)}s) — 종료")
            return False
        log.warning(f"스테일 락 발견 (age={int(age)}s) — 제거하고 계속")
        try:
            os.remove(LOCK_FILE)
        except OSError as e:
            log.error(f"스테일 락 제거 실패: {e}")
            return False
    try:
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n{datetime.now().isoformat()}\n")
        return True
    except OSError as e:
        log.error(f"락 생성 실패: {e}")
        return False


def release_lock() -> None:
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except OSError as e:
        log.warning(f"락 해제 실패 (무시): {e}")


def already_collected_today() -> bool:
    """오늘 날짜로 videos 스냅샷이 이미 있으면 True."""
    try:
        from crol_config import DB_PATH
        if not os.path.exists(DB_PATH):
            return False
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM videos WHERE DATE(snapshot_at) = ?",
                    (date.today().isoformat(),))
        n = cur.fetchone()[0]
        conn.close()
        return n > 0
    except Exception as e:
        log.warning(f"오늘 수집 여부 확인 실패 (계속 진행): {e}")
        return False


# ── 3. 단계 실행 ────────────────────────────────────────────────────
def step(name: str, fn, *args, **kwargs):
    """한 단계 실행 — 실패해도 다음 단계로 넘어감."""
    log.info(f"[STEP] {name} 시작")
    t0 = time.time()
    try:
        result = fn(*args, **kwargs)
        log.info(f"[STEP] {name} 완료 ({time.time()-t0:.1f}s)")
        return True, result
    except Exception as e:
        log.exception(f"[STEP] {name} 실패: {e}")
        return False, None


def main() -> int:
    log.info("=" * 60)
    log.info(f"[START] PID={os.getpid()}  python={sys.executable}")
    log.info(f"        cwd={os.getcwd()}  log={_log_path}")

    if not has_network():
        log.error("네트워크 연결 없음 → 종료 (다음 로그온 때 재시도)")
        return 2

    if not acquire_lock():
        return 3

    try:
        if already_collected_today():
            log.info("오늘 이미 수집 완료 — 스킵 (전원 재부팅 시 중복 방지)")
            return 0

        from db.database import init_db
        from collect.youtube import run_collection
        from collect.keywords import update_trend_keywords
        from analyze.analyzer import analyze_date

        ok_count = 0
        if step("DB 초기화", init_db)[0]: ok_count += 1
        if step("트렌드 키워드 갱신", update_trend_keywords, force=False)[0]: ok_count += 1

        ok, snapshot_at = step("YouTube 수집", run_collection)
        if ok and snapshot_at:
            ok_count += 1
            step("일일 분석", analyze_date, snapshot_at[:10])

        log.info(f"[END] 성공 단계 {ok_count}/4")
        return 0 if ok_count >= 3 else 1
    finally:
        release_lock()
        log.info("[BYE] " + "=" * 56)


if __name__ == "__main__":
    sys.exit(main())
