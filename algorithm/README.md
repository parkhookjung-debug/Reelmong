# 릴몽 (Reelmong)

**F&B 매장 홍보 숏폼 영상 자동 생성 AI 파이프라인**

영상 클립 10개와 매장 정보만 넣으면, 나레이션·자막·BGM이 합성된 9:16 세로 숏폼 영상과 유튜브/인스타 제목·해시태그까지 자동으로 만들어줍니다.

---

## 어떤 프로그램인가요?

음식점·카페 등 F&B 매장의 홍보 영상(인스타 릴스, 유튜브 쇼츠)을 자동으로 제작합니다.

**인풋**
- `data/images/` 폴더에 3~5초짜리 mp4 클립 최대 10개
- 매장 이름, 매장 소개, 업종 (Step 1 실행 시 입력)

**아웃풋**
- `step4_final_video.mp4` — 바로 업로드 가능한 9:16 세로 숏폼 영상
- `step5_recommend.json` — 유튜브/인스타 제목 후보 8개 + 해시태그 20개

**핵심 특징**
- **OpenRouter API 키 하나**로 전체 파이프라인 동작 (Vision + LLM + TTS 통합)
- Gemini Vision으로 영상 속 음식·공간을 직접 한국어로 인식해서 대본 작성
- 후킹 멘트 10개 후보 자동 생성 후 바이럴 점수 기반 선택 → 첫 장면에 배치
- 나레이션 끝나는 타이밍에 맞춰 영상 클립 자동 분할/연장
- 자막 팝(pop) 애니메이션 (나레이션 시작 시 뿅! 등장)

---

## AI 모델 구성

모든 AI는 **OpenRouter** (https://openrouter.ai) 를 통해 단일 API 키로 연동됩니다.

| 역할 | 모델 | 비고 |
|------|------|------|
| 이미지 분석 (Vision) | `google/gemini-2.5-flash` | 이미지 → 한국어 분석 직접 출력 |
| 대본 생성 (LLM) | `google/gemini-2.5-flash` | 숏폼 스토리보드 생성 |
| 음성 합성 (TTS) | `google/gemini-3.1-flash-tts-preview` | 한국어 특화 보이스 `Kore` |
| 제목 추천 (LLM) | `google/gemini-2.5-flash` | 유튜브/인스타 제목·해시태그 |
| 영상 편집 | MoviePy 2.x | 로컬 |
| 오디오 믹싱 | pydub | 로컬 |
| 제목 추천 엔진 | crol (템플릿 + Gemini + SQLite DB) | 로컬 |

> 모델 상세 설명은 [AI_MODELS.md](AI_MODELS.md) 참고

---

## 동작 구조

```
data/images/ (mp4 클립 10개)
        │
        ▼
  ┌─────────────────────────────────────────────────────┐
  │  Step 1  영상 중간 프레임 추출 → Gemini Vision 분석   │
  │          각 클립에서 무슨 음식·공간인지 한국어로 직접   │
  │          파악 (BLIP+Ollama 2단계 → Gemini 1단계)     │
  └─────────────────────┬───────────────────────────────┘
                        │ step1_result.json
                        ▼
  ┌─────────────────────────────────────────────────────┐
  │  Step 2  Gemini LLM으로 대본 생성                    │
  │          - 후킹 멘트 10개 생성 후 바이럴 점수로 선택   │
  │          - 장면별 나레이션 (15자 이내, 이미지 반영)     │
  │          - 음식 종류(food_type) 자동 분류             │
  └─────────────────────┬───────────────────────────────┘
                        │ step2_storyboard.json
                        ▼
  ┌─────────────────────────────────────────────────────┐
  │  Step 3  나레이션 음성 + BGM 합성                    │
  │          - Gemini TTS로 한국어 음성 생성 (Kore 보이스) │
  │          - 업종별 자동 BGM 선택 (data/bgm/ 폴더)      │
  │          - 나레이션 큐(queue) 방식: 겹침 없이 연속 재생 │
  └─────────────────────┬───────────────────────────────┘
                        │ step3_final_audio.mp3
                        │ step3_narr_timings.json
                        ▼
  ┌─────────────────────────────────────────────────────┐
  │  Step 4  최종 영상 렌더링                             │
  │          - 영상 클립 10개 순서대로 연결               │
  │          - 나레이션 길이에 맞게 클립 자동 조정          │
  │          - 자막 팝 애니메이션 오버레이                 │
  │          - 오디오(TTS+BGM) 합성                      │
  └─────────────────────┬───────────────────────────────┘
                        │ step4_final_video.mp4
                        ▼
  ┌─────────────────────────────────────────────────────┐
  │  Step 5  제목 / 해시태그 추천 (crol 엔진)             │
  │          - 템플릿 기반 제목 8개                       │
  │          - Gemini AI 제목 추천                       │
  │          - DB 기반 인기 해시태그 20개                 │
  └─────────────────────┬───────────────────────────────┘
                        │ step5_recommend.json
                        ▼
                   완성!
```

---

## 폴더 구조

```
reelmong/
├── run_step1.py          # Step 1: 프레임 추출 + 이미지 분석
├── run_step2.py          # Step 2: 대본/스토리보드 생성
├── run_step3.py          # Step 3: TTS + BGM 오디오 합성
├── run_step4.py          # Step 4: 최종 영상 렌더링
├── run_step5.py          # Step 5: 제목/해시태그 추천
├── run_step6.py          # Step 6: 영상 품질 평가 (선택)
├── AI_MODELS.md          # AI 모델 구성 상세 설명
│
├── config/
│   └── settings.py       # 전역 설정 (해상도, 모델명, 경로 등)
│
├── src/
│   ├── step1_vision/     # Gemini Vision 이미지 분석
│   ├── step2_script/     # 스토리보드 생성 (Gemini LLM)
│   ├── step3_audio/      # TTS / BGM / 오디오 믹서
│   ├── step4_video/      # 영상 렌더러 (MoviePy)
│   └── step5_eval/       # 영상 품질 평가
│
├── crol/                 # 제목/해시태그 추천 엔진
│   ├── recommend/        # 추천 핵심 로직
│   ├── collect/          # YouTube 데이터 수집 (선택)
│   └── crol_config.py    # crol 설정
│
├── data/
│   ├── images/           # 여기에 mp4 클립 넣기
│   ├── bgm/              # 분위기별 BGM 폴더
│   │   ├── warm/
│   │   ├── energetic/
│   │   ├── calm/
│   │   ├── trendy/
│   │   └── elegant/
│   ├── fonts/            # 한국어 폰트
│   └── output/           # 각 스텝 결과물 (자동 생성)
│
├── requirements.txt
└── .env.example
```

---

## 설치 방법

### 1. 사전 요구사항

| 항목 | 설치 방법 |
|------|----------|
| Python 3.10+ | https://python.org |
| FFmpeg | `winget install ffmpeg` (Windows) / `brew install ffmpeg` (Mac) |
| OpenRouter API 키 | https://openrouter.ai/settings/keys 에서 발급 |

> Ollama, BLIP 모델 다운로드 불필요 — OpenRouter API로 대체되었습니다.

### 2. 패키지 설치

```bash
pip install -r requirements.txt
pip install -r crol/requirements.txt
```

Python 3.13 이상 사용 시 추가 설치 필요:
```bash
pip install audioop-lts
```

### 3. 환경변수 설정

```bash
# .env.example을 복사해서 .env 파일 생성
cp .env.example .env
```

`.env` 파일에 OpenRouter API 키 입력:
```
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

crol 제목 추천에 YouTube 데이터를 직접 수집하려면 `crol/.env` 파일에 추가 입력:
```
# crol/.env
YOUTUBE_API_KEY=your_youtube_api_key_here
NAVER_CLIENT_ID=your_naver_client_id_here
NAVER_CLIENT_SECRET=your_naver_client_secret_here
```
> YouTube/Naver API 키 없이도 기본 추천(템플릿 + Gemini AI)은 정상 동작합니다.

### 4. BGM 파일 추가 (선택)

`data/bgm/` 하위 폴더에 분위기에 맞는 mp3 파일을 넣으면 자동으로 선택됩니다.

```
data/bgm/warm/      ← 따뜻한 분위기 (카페, 한식)
data/bgm/energetic/ ← 신나는 분위기 (치킨, 분식)
data/bgm/calm/      ← 차분한 분위기 (일식, 양식)
data/bgm/trendy/    ← 트렌디한 분위기 (카페, 베이커리)
data/bgm/elegant/   ← 고급스러운 분위기
```

---

## 사용 방법

### Step 1: 영상 클립 준비 + 분석

```bash
# data/images/ 폴더에 mp4 파일 넣기 (파일명 숫자 순서대로)
# 예: 쿠우쿠우0.mp4, 쿠우쿠우1.mp4 ... 쿠우쿠우9.mp4

# 실행 (대화형)
python run_step1.py

# 또는 인자로 직접 입력
python run_step1.py --name "쿠우쿠우 홍대점" --intro "무한리필 초밥 뷔페" --category "일식"
```

### Step 2~4: 대본 생성 → 오디오 합성 → 영상 렌더링

```bash
python run_step2.py
python run_step3.py
python run_step4.py
```

### Step 5: 제목 / 해시태그 추천

```bash
python run_step5.py

# AI 추천 생략하고 빠르게 실행하려면
python run_step5.py --no-ollama
```

### (선택) Step 6: 영상 품질 평가

```bash
python run_step6.py
```

---

## 출력 결과 예시

**제목 추천 (step5_recommend.json)**
```
[AI 추천 제목 (Gemini)]
  1. 초밥 무한리필, 이 퀄리티 실화냐?
  2. 연어 육회 초밥이 무한? 미쳤다!

[템플릿 추천 제목]
  1. [hook]    이거 보면 지금 당장 가고싶어짐
  2. [honest]  쿠우쿠우 광고 아님 진짜 맛있어서 올림
  3. [twist]   기대 안 했다가 쿠우쿠우 완전 반함
  ...

[추천 해시태그]
  #초밥무한리필 #초밥뷔페 #서울맛집 #가족외식 ...
```

---

## 주의사항

- 영상 클립 파일명은 숫자로 끝나야 순서대로 정렬됨 (예: `clip0.mp4`, `clip1.mp4`)
- `data/images/` 폴더는 한 번에 한 매장 작업용 — 새 매장 촬영 시 기존 클립 교체 후 Step 1부터 재실행
- OpenRouter API 키는 절대 GitHub에 올리지 마세요 (`.env` 파일은 `.gitignore`에 포함)
