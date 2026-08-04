# 수능 국어 PDF–BRF 자동 변환

비장애 응시자용 **국어 문제지 PDF**를 입력하면, 같은 시험의 **시각장애용 참고 BRF에 거의 일치하는 구조적 BRF**를 자동 생성하는 것을 최종 목표로 한다.

단순한 문자 치환기가 아니라 PDF 구조 → 수능 의미 구조 → (안내 양식) → 점역 → 줄·면 편집 → BRF → 참고본 비교까지를 다루는 시스템이다.  
차이는 실행 중 문서 수동 편집이 아니라 **규칙·코드·테스트**로 줄인다.

초기 개발 언어는 **Python 3.12+** 이다.

```text
국어 문제지 PDF
→ 문자·좌표·블록 추출
→ 지문·문항·선택지·보기 구조
→ 시각장애용 안내 양식 삽입 (목표)
→ 점자 변환
→ 줄·면 재편집
→ BRF 출력
→ 참고 BRF와 셀·구조 비교 → 코드 수정 루프
```

설계·모듈·알고리즘: **[docs/architecture.md](docs/architecture.md)**  
개발 루프: **[docs/quality_loop.md](docs/quality_loop.md)** · 안내문: **[docs/guidance_policy.md](docs/guidance_policy.md)** · 문서 색인: **[docs/README.md](docs/README.md)**

---

## 목표

### 북극성

| 항목 | 내용 |
|------|------|
| 성공 상태 | 생성 BRF ≈ 동일 회차 시각장애용 참고 BRF (셀·구조·안내 양식) |
| 개선 수단 | 비교·테스트 → 점역/레이아웃/구조 **코드** 수정 |
| UI 역할 | 진단·미리보기·탐색. 문서 수동 보정은 **최소** |

### 범위 (초기)

| 항목 | 내용 |
|------|------|
| 과목 | 국어 |
| 입력 | 평가원·교육청 시험지 PDF (+ 정합용 참고 BRF) |
| 출력 | BRF |
| 주요 구조 | 시험·시각장애 안내, 지문, 문단, 문항, 발문, 선택지, 〈보기〉, 인용문, 각주, 표·그림 |
| 주요 기능 | 자동 변환 파이프라인, 참고본 비교, 구조 탐색, 진단용 Inspector/PDF 뷰어 |

### 제외 (초기)

- 수학·과학 과목
- 완전 자동 그림 설명
- 음성 시험지 생성
- 한소네 전용 앱 직접 개발
- 딥러닝 종단 간 변환 (규칙 우선; ML은 후속 보조)
- **일상 경로로서의** 문제지 수동 재편집으로 완성본 만들기

### 설계 계층

```text
1. PDF 물리 구조
2. 수능 국어 의미 구조
3. 시각장애 안내·양식 (목표: 참고와 일치하도록 삽입)
4. 점자 번역 구조
5. BRF 출력 구조
6. 사용자 탐색 구조
7. 검수·비교
```

---

## 현재 상태

**Prototype 3 — 지문 한 묶음 종단 변환** 1차. 참고 BRF와 머리말·앵커 형태는 접근 중이며, 본문 셀 정합·안내 삽입·시험 전체는 이후 과제.

| 프로토타입 | 상태 |
|------------|------|
| 1. BRF Inspector | 완료 — 무손실 로딩, 유니코드·역점역, 구조 태그 |
| 2. PDF Structure Viewer | 완료 — 문자·행·블록, 오버레이, 진단용 병합/분할 |
| 3. 지문 한 묶음 종단 변환 | 1차 — Exam 빌더 + 표 점역 + 규칙 레이아웃 + 비교 |
| 4. 시험 전체 변환 | 예정 — 45문항, 경고, 참고 BRF 정합 루프 |

### 설치

```bash
pip install -e ".[dev]"
```

### 실행

```bash
python -m korean_exam_braille.app.main path/to/file.brf
python -m korean_exam_braille.app.main path/to/file.pdf
python -m korean_exam_braille.app.main --mode brf
python -m korean_exam_braille.app.main --mode pdf
```

`Ctrl+2` — BRF Inspector ↔ PDF 뷰어.  
`Ctrl+Shift+B` — BRF 변환 미리보기.  
`Ctrl+Shift+D` — 참고 BRF와 내용 비교(진단).  
`Ctrl+3` — 계층 탐색 도킹 패널.

**줄 비교** = ASCII 셀 정합(최종 지표에 가깝다).  
**내용 비교** = 역점역+앵커 진단(안내는 당분간 예상 차이; 이후 삽입 대상).

### 변환·비교

```bash
python -c "from korean_exam_braille.app.pipeline import default_pipeline; r=default_pipeline().run('exam.pdf'); print(r.brf_text[:500]); print(r.warnings)"

python -c "from korean_exam_braille.app.brf import compare_pdf_to_reference_brf; print(compare_pdf_to_reference_brf('exam.pdf', 'ref.brf').summary())"

python -m pytest
```

품질 루프 상세는 [docs/quality_loop.md](docs/quality_loop.md).

---

## 개발 단계

| Phase | 내용 | 산출 / 완료 기준 |
|-------|------|------------------|
| **0** | 자료·규칙 노트 | PDF–BRF 짝, `docs/` 관례 기록 |
| **1** | BRF Inspector | 무손실 로딩·역점역·태그 **(완료)** |
| **2** | BRF 구조 주석 | 1회분 태깅·연결 |
| **3** | PDF 추출기 | 문자·행·블록 시각화 **(완료)** |
| **4** | 읽기 순서 | 다단·예외; UI 보정은 진단용 |
| **5** | 수능 구조 모델 | 계층 트리 + 참조 |
| **6** | 규칙 자동 인식 | 문항·선택지·지문 재현율 |
| **7** | 계층 탐색기 | 키보드 탐색 **(1차)** |
| **8** | 점역 엔진 | 규정 점역 + **참고 BRF 셀 비교** |
| **9** | 줄·면 편집 | 폭·높이·구분선·머리말 |
| **9b** | 안내 양식 삽입 | 참고와 동일 역할의 유의·머리말·꼬리말 |
| **10** | 표·그림 | 탐지·설명·누락 경고 |
| **11** | 비교 검증기 | 셀·행·면·구조·안내 차이 분류 **(1차)** |
| **12** | 사용자 평가 | 탐색 과제 지표 |
| **13** | 결정트리(후속) | 후보 제안 — 본류는 규칙 정합 |

---

## 프로토타입 · 마일스톤

1. BRF Inspector *(완료)*  
2. PDF Structure Viewer *(완료)*  
3. 지문 한 묶음 종단 변환 *(1차)*  
4. 시험 전체 변환 + 참고 BRF 정합 루프  

| ID | 목표 |
|----|------|
| M1–M4 | Inspector·주석·PDF 뷰어 |
| M5–M6 | 구조 모델·지문 묶음 BRF |
| M7 | 시험 전체 변환 |
| M7b | 참고 BRF 셀 정합률 상향 + 안내 삽입 |
| M8 | 계층 탐색기 |
| M9 | 사용자 평가 |

---

## 기술 스택

| 구분 | 라이브러리 |
|------|------------|
| 언어 | Python 3.12+ |
| PDF | PyMuPDF *(pdfplumber·Pillow 후속)* |
| GUI | PySide6 |
| 설정 | pydantic, PyYAML |
| 테스트 | pytest |
| ML *(후속)* | scikit-learn |

---

## 디렉터리

```text
korean_exam_braille/app/
  main.py, common/, pdf/, exam/, braille/, layout/,
  brf/, nav/, pipeline/, ui/
tests/
data/          # raw PDF·BRF, fixtures
docs/          # 아키텍처·품질루프·안내정책·Phase0 노트
profiles/      # 줄·면 프로필
rules/         # (예정) 구조·점역·안내 템플릿
```

```python
from korean_exam_braille.app.pipeline import default_pipeline
from korean_exam_braille.app.nav import TreeExamNavigator

result = default_pipeline().run("path/to/exam.pdf")
nav = TreeExamNavigator()
nav.bind(result.exam)
nav.next_of_type("Question")
```

---

## 다음 작업

1. 본문 점역·레이아웃 정합 (참고 BRF **셀** 일치율, quality_loop)
2. 시각장애 안내 템플릿 목록화·삽입 (guidance_policy)
3. 시험 전체 45문항 (Prototype 4) — 매핑 오류(Q1/22/25 등) 코드로 제거
4. Phase 0 `docs/` 규칙 노트 채우기
5. 탐색 ↔ BRF 면/줄 동기화 (`source_node_ids`)
