"""BGM 관리 모듈 - 분위기별 무료 BGM 자동 매칭

릴스 트렌드 스타일의 로열티 프리 BGM을 분위기(mood)에 따라 자동 선택합니다.
Pixabay Music 등 무료 소스에서 다운로드한 BGM을 관리합니다.
"""
import os
import random
from pathlib import Path

from config.settings import DATA_DIR


BGM_DIR = DATA_DIR / "bgm"

# 분위기별 BGM 폴더 매핑
MOOD_FOLDERS = {
    "trendy": BGM_DIR / "trendy",       # 트렌디/힙한 (릴스 유행 스타일)
    "warm": BGM_DIR / "warm",            # 따뜻한/감성적
    "calm": BGM_DIR / "calm",            # 차분한/lo-fi
    "energetic": BGM_DIR / "energetic",  # 활기찬/신나는
    "elegant": BGM_DIR / "elegant",      # 고급스러운/재즈
}

# 업종별 기본 BGM 분위기 매핑
CATEGORY_BGM_MAP = {
    "한식": "warm",
    "카페": "calm",
    "치킨": "energetic",
    "피자": "energetic",
    "분식": "trendy",
    "중식": "warm",
    "일식": "elegant",
    "양식": "elegant",
    "베이커리": "calm",
    "마라탕": "trendy",
    "기타": "warm",
}

SUPPORTED_AUDIO = {".mp3", ".wav", ".ogg", ".m4a"}


class BGMManager:
    """분위기 기반 BGM 자동 선택 관리자"""

    def __init__(self):
        self.bgm_dir = BGM_DIR
        self._ensure_dirs()

    def _ensure_dirs(self):
        """BGM 분위기별 폴더 생성"""
        for folder in MOOD_FOLDERS.values():
            folder.mkdir(parents=True, exist_ok=True)

    def get_available_moods(self) -> dict[str, int]:
        """각 분위기별 사용 가능한 BGM 수 반환"""
        result = {}
        for mood, folder in MOOD_FOLDERS.items():
            count = len(self._list_audio_files(folder))
            result[mood] = count
        return result

    def _list_audio_files(self, folder: Path) -> list[Path]:
        """폴더 내 오디오 파일 목록"""
        if not folder.exists():
            return []
        return [
            f for f in folder.iterdir()
            if f.suffix.lower() in SUPPORTED_AUDIO
        ]

    def select_bgm(self, mood: str = "", category: str = "") -> str | None:
        """분위기 또는 업종에 맞는 BGM 자동 선택

        Args:
            mood: BGM 분위기 (trendy, warm, calm, energetic, elegant)
            category: 업종 카테고리 (mood가 없으면 업종에서 자동 매칭)
        Returns:
            선택된 BGM 파일 경로 또는 None (BGM 없음)
        """
        # 1) mood 결정
        if not mood:
            mood = CATEGORY_BGM_MAP.get(category, "warm")

        # 2) 해당 mood 폴더에서 BGM 선택
        folder = MOOD_FOLDERS.get(mood, MOOD_FOLDERS["warm"])
        files = self._list_audio_files(folder)

        if files:
            selected = random.choice(files)
            return str(selected)

        # 3) 해당 mood에 BGM 없으면 아무 BGM이나 찾기
        for other_mood, other_folder in MOOD_FOLDERS.items():
            files = self._list_audio_files(other_folder)
            if files:
                print(f"    [BGM] '{mood}' BGM 없음 → '{other_mood}'에서 대체 선택")
                return str(random.choice(files))

        return None

    def get_status(self) -> str:
        """BGM 라이브러리 상태 문자열"""
        moods = self.get_available_moods()
        total = sum(moods.values())
        lines = [f"BGM 라이브러리: 총 {total}개"]
        for mood, count in moods.items():
            status = f"{count}개" if count > 0 else "없음"
            lines.append(f"  {mood}: {status}")

        if total == 0:
            lines.append("")
            lines.append("BGM 추가 방법:")
            lines.append(f"  {self.bgm_dir}/<mood>/ 폴더에 MP3 파일을 넣어주세요.")
            lines.append("  mood: trendy, warm, calm, energetic, elegant")
            lines.append("")
            lines.append("무료 BGM 다운로드:")
            lines.append("  - Pixabay Music: https://pixabay.com/music/")
            lines.append("  - YouTube Audio Library: YouTube 스튜디오 > 오디오 라이브러리")

        return "\n".join(lines)
