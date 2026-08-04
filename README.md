# 수능 국어 PDF–BRF 자동 변환

대학수학능력시험 국어 문제지 PDF를 입력하면, 시각적으로 구성된 시험지를 점자 사용자가 읽고 이동할 수 있는 **구조적 시험 문서(BRF)** 로 다시 편집하는 프로그램입니다.

단순한 문자 치환기가 아니라, PDF 구조 분석 → 수능 국어 의미 구조 → 점역 → 줄·면 재편집 → BRF 출력 → 검수까지를 다루는 시스템입니다.

초기 개발 언어는 **Python 3.12+** 로 통일합니다.

```text
국어 문제지 PDF
→ 문자·좌표·도형 추출
→ 지문·문항·선택지·보기 구조 분석
→ 문제지 구조 모델 생성
→ 점자 변환
→ 점자 줄·면 재편집
→ BRF 출력
→ 시각적 점자와 묵자 형태로 검토
```

---

## 목표

### 범위 (초기)

| 항목 | 내용 |
|------|------|
| 과목 | 국어 |
| 입력 | 평가원·교육청 시험지 PDF |
| 출력 | BRF |
| 주요 구조 | 시험 안내, 지문, 문단, 문항, 발문, 선택지, 〈보기〉, 인용문, 각주, 표·그림 |
| 주요 기능 | BRF 분석, PDF 구조 추출, 문제지 구조 생성, 점역, 줄·면 편집, 구조 탐색, 수동 수정 |

### 제외 (초기)

- 수학·과학 과목
- 완전 자동 그림 설명
- 음성 시험지 생성
- 한소네 전용 프로그램 직접 개발
- 딥러닝 기반 종단 간 변환
- 점역사 검수 없는 완전 무인 출력

### 설계 계층

```text
1. PDF 물리 구조      문자·행·블록·선·이미지·좌표
2. 수능 국어 의미 구조  지문 묶음·문항·선택지·보기
3. 사용자 탐색 구조    이동에 필요한 계층 노드만 제공
4. 점자 번역 구조      토큰 → 한글·숫자·영문·기호 점자 셀
5. BRF 출력 구조       줄바꿈·들여쓰기·면 분할·머리말·꼬리말
```

---

## 현재 상태

**Prototype 2 — PDF Structure Viewer** 까지 구현.

| 프로토타입 | 상태 |
|------------|------|
| 1. BRF Inspector | 완료 — 무손실 로딩, 유니코드·역점역, 구조 태그 |
| 2. PDF Structure Viewer | 완료 — 문자·행·블록 추출, 오버레이, 병합/분할, 저장 |
| 3. 지문 한 묶음 종단 변환 | 예정 |
| 4. 시험 전체 변환 | 예정 |

### 설치

```bash
pip install -e ".[dev]"
```

### 실행

```bash
# BRF Inspector
python -m korean_exam_braille.app.main path/to/file.brf
python -m korean_exam_braille.app.main --mode brf

# PDF Structure Viewer
python -m korean_exam_braille.app.main path/to/file.pdf
python -m korean_exam_braille.app.main --mode pdf path/to/file.pdf
```

### 테스트

```bash
python -m pytest
```
---

## 개발 단계

| Phase | 내용 | 산출 / 완료 기준 |
|-------|------|------------------|
| **0** | 자료 확보·분석 기준 | PDF–BRF 짝 최소 3회분, `docs/` 규칙 노트 |
| **1** | BRF Inspector | 무손실 로딩, 유니코드·역점역, 태그 저장 **(완료)** |
| **2** | BRF 구조 주석기 | 1회분 전체 태깅, 45문항·선택지·지문 연결 |
| **3** | PDF 페이지 추출기 | 문자·행·블록·도형 추출 및 시각화 **(Prototype 2 완료)** |
| **4** | 읽기 순서 분석기 | 다단·예외 처리, 수동 수정 가능 |
| **5** | 수능 국어 구조 모델 | 계층 트리 + 참조 그래프, 미분류 목록 |
| **6** | 규칙 기반 자동 인식 | 문항·선택지·지문·보기 높은 재현율 |
| **7** | 범용 계층 탐색기 | 한소네식 키보드 탐색, 현재 위치·원위치 |
| **8** | 한국어 점자 변환 엔진 | 규정 점역, 기존 BRF와 셀 단위 비교 |
| **9** | BRF 줄·면 편집 엔진 | 줄 폭·면 높이, 구분선·머리말, 대응표 |
| **10** | 표·그림 처리 | 탐지·연결·설명 입력·누락 경고 |
| **11** | 비교 검증기 | 셀·행·면·구조 수준 차이 분류 |
| **12** | 사용자 평가 | 탐색 과제, 위치 파악·이동 지표 |
| **13** | 결정트리 도입 | 주석 축적 후 후보 제안 + 사람 검토 |

---

## 프로토타입 순서

1. **BRF Inspector** — BRF 분석·역점역·태깅 *(완료)*
2. **PDF Structure Viewer** — 페이지 문자·행·블록 시각화 *(완료)*
3. **지문 한 묶음 종단 변환** — 지문 1개 + 문항 2~3개 → BRF
4. **시험 전체 변환** — 45문항, 경고 목록, 기존 BRF 비교

---

## 마일스톤

| ID | 목표 |
|----|------|
| M1 | BRF 무손실 로딩 (행·빈 줄·폼피드 보존) |
| M2 | 시각적 점자 뷰어 (원문·유니코드·면 이동) |
| M3 | BRF 구조 주석기 (문제·선택지·구분선 태깅) |
| M4 | PDF 구조 뷰어 |
| M5 | 시험지 구조 모델 (계층 + 참조) |
| M6 | 지문 한 묶음 BRF 생성 |
| M7 | 시험 전체 변환 |
| M8 | 범용 계층 탐색기 |
| M9 | 사용자 평가 |

---

## 기술 스택

| 구분 | 라이브러리 |
|------|------------|
| 언어 | Python 3.12+ |
| PDF | PyMuPDF, pdfplumber, Pillow *(후속)* |
| GUI | PySide6 |
| 설정 | pydantic, PyYAML |
| 테스트 | pytest |
| ML *(후속)* | scikit-learn |

---

## 디렉터리

```text
korean_exam_braille/
├─ app/
│  ├─ main.py                 # BRF / PDF 뷰어 진입점
│  ├─ brf/                    # 파서·ASCII 점자·역점역·주석
│  ├─ pdf/                    # 문자·행·블록 추출·후보·저장
│  ├─ ui/brf_inspector/       # BRF Inspector
│  ├─ ui/pdf_viewer/          # PDF Structure Viewer
│  ├─ exam/ braille/          # (예정) 구조·점역
│  └─ layout/ ml/             # (예정) 줄·면 편집·학습
tests/
data/          # raw PDF·BRF, annotations, fixtures
docs/          # Phase 0 분석 노트
profiles/      # 줄·면 편집 프로필
rules/         # 구조·점역 규칙
```

분석 노트(`docs/`):

- `brf_structure_notes.md` — BRF 구조
- `pdf_brf_mapping.md` — PDF–BRF 대응
- `separator_patterns.md` — 구분선
- `page_number_rules.md` — 면·쪽 번호
- `question_choice_rules.md` — 문항·선택지
- `unresolved_cases.md` — 미해결 사례

---

## 다음 작업

1. 실제 평가원·교육청 PDF를 PDF Viewer로 열어 블록·읽기 순서 보정 (Phase 3–4)
2. PDF–BRF 짝으로 `docs/` 규칙 정리 (Phase 0)
3. 지문 한 묶음 종단 변환 (Prototype 3)