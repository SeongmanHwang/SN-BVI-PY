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

**Prototype 3 — 지문 한 묶음 종단 변환** 1차 구현.

| 프로토타입 | 상태 |
|------------|------|
| 1. BRF Inspector | 완료 — 무손실 로딩, 유니코드·역점역, 구조 태그 |
| 2. PDF Structure Viewer | 완료 — 문자·행·블록 추출, 오버레이, 병합/분할, 저장 |
| 3. 지문 한 묶음 종단 변환 | 1차 — `RuleExamStructureBuilder` + `TableBrailleTranslator` + `RuleBrailleLayoutEngine` |
| 4. 시험 전체 변환 | 예정 |

### 설치

```bash
pip install -e ".[dev]"
```

### 실행

```bash
# BRF Inspector / PDF Structure Viewer (실행 중 보기 메뉴·Ctrl+2로 전환)
python -m korean_exam_braille.app.main path/to/file.brf
python -m korean_exam_braille.app.main path/to/file.pdf
python -m korean_exam_braille.app.main --mode brf
python -m korean_exam_braille.app.main --mode pdf
```

실행 중 **보기 → PDF Structure Viewer로 전환** / **BRF Inspector로 전환** (`Ctrl+2`)으로 모드를 바꿉니다. 파일 열기에서 상대 확장자를 고르면 자동 전환됩니다.

PDF 뷰어에서 **BRF 변환 미리보기** (`Ctrl+Shift+B`)를 누르면 현재 구조로 파이프라인을 실행하고, 요약 대화상자 뒤 **BRF Inspector**에서 점자·묵자 역점역을 확인합니다.

**계층 탐색** (`Ctrl+3`)은 PDF 창 **오른쪽 도킹 패널**로 Exam 트리를 보여 줍니다.  
`Alt+←→↑↓`로 계층 이동, `Ctrl+←→`로 문항 이동. 위치는 상태바와 PDF 블록 선택에 반영됩니다.

### 변환 파이프라인

```bash
python -c "from korean_exam_braille.app.pipeline import default_pipeline; r=default_pipeline().run('exam.pdf'); print(r.brf_text[:500]); print(r.warnings)"
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
3. **지문 한 묶음 종단 변환** — 지문 1개 + 문항 2~3개 → BRF *(1차 완료)*
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
│  ├─ common/                 # 공통 태그·상수
│  ├─ brf/                    # 파서·ASCII 점자·역점역·주석
│  ├─ pdf/                    # 문자·행·블록 추출 (+ ports/adapter)
│  ├─ exam/                   # 수능 의미 구조 (포트·규칙 빌더)
│  ├─ braille/                # 점역 (포트·표 기반)
│  ├─ layout/                 # 줄·면 편집·BRF 직렬화
│  ├─ nav/                    # 계층 탐색 (포트·트리 내비게이터)
│  ├─ pipeline/               # PDF→Exam→Braille→Layout→BRF
│  ├─ ui/brf_inspector/
│  ├─ ui/pdf_viewer/
│  └─ ui/nav/                 # 탐색 패널·대화상자
tests/         # brf / pdf / exam / braille / layout / nav / pipeline
data/          # raw PDF·BRF, annotations, fixtures
docs/          # Phase 0 분석 노트
profiles/      # 줄·면 편집 프로필
rules/         # 구조·점역 규칙
```

변환·탐색은 단계 구현체를 주입해 교체한다.

```python
from korean_exam_braille.app.pipeline import default_pipeline
from korean_exam_braille.app.nav import TreeExamNavigator

result = default_pipeline().run("path/to/exam.pdf")
nav = TreeExamNavigator()
nav.bind(result.exam)
nav.next_of_type("Question")
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

1. 본문 점역 정합 (참고 BRF 셀 일치율)
2. 탐색 ↔ BRF 면/줄 동기화 (layout `source_node_ids`)
3. 시험 전체 45문항 변환 (Prototype 4)
4. Phase 0 `docs/` 규칙 노트 채우기

### 품질·탐색 루프

1. PDF 열기 → 블록·순서 보정  
2. **계층 탐색** (`Ctrl+3`) — 도킹 트리 + Alt/Ctrl 단축키 · PDF 블록 연동  
3. **BRF 변환 미리보기** — Exam 트리·참고 BRF 비교  
4. BRF Inspector에서 점자·역점역 확인  

점역·레이아웃 1차 반영: `[N~M]`, 문항번호, 선택지, VC약자, 구분선,  
**머리말 줄 분리·가운데 정렬**(1면 헤더가 참고와 동일 구조).  
탐색은 `nav/` 포트로 분리되어 점역과 독립적으로 교체한다.