# UI 셸 경계 — UI만 교체하기 위한 계약

제품 UI는 진단·미리보기·전환만 담당한다. 변환·구조 로직은 `session/`·`pipeline/`·도메인 포트에 둔다.  
이 문서는 **제품 모드 계획**, **새 UI가 호출해도 되는 API**, **직접 import하면 안 되는 패키지**를 고정한다.

관련: [architecture.md](architecture.md), [quality_loop.md](quality_loop.md).

---

## 0. 제품 UI 계획 (확정)

### 0.1 사용자 모드 (기본·첫 화면) — **웹 셸**

스크린 리더로 W3C(WCAG) 수준 접근성을 맞추는 **단순 플로우**. Qt가 아니라 **웹 셸**로 구현한다.

| 조작 | 동작 |
|------|------|
| PDF 선택 및 변환 | 파일 선택 → `load_pdf` → `analyze_and_convert()` (한 버튼) |
| BRF 다운로드 | 마지막 변환 결과 |
| DTBook XML 다운로드 | DAISY용 중간 구조 (**DTBook 2005-3**, 패키지 아님) |

앱 내 수동 수정 UI는 **두지 않는다**.

### 0.2 개발자 모드 — 같은 업로드 파일

사용자 모드에서 연 문서를 대상으로 진단만 한다. **구조 병합·분할·태그 수동 편집 유도 버튼은 제거**한다.

| 모드 | 패널 |
|------|------|
| A | 원문 PDF(읽기 전용) · BRF · 역점역 |
| B | 원문 PDF(읽기 전용) · 구조 계층 · **DTBook XML** |

모드 A 면 선택은 **PDF 기준**. 한 PDF 면에 점자 면이 여러 장이면 BRF·역점역을 묶어 표시하고 (`── 점자 N면 ──`), `pdf_to_braille`로 모든 점자 면이 배정되어 유실되지 않게 한다.

구현 스택: 웹 `/dev` — 모드 A/B 패널. PDF는 읽기 전용(이미지+추출 텍스트).

### 0.2b 검토 모드 — BRF 대 BRF (별도 흐름)

사용자·개발자와 **성격이 다른** 비교 전용 화면 (`/review`).

| 조작 | 동작 |
|------|------|
| 생성 BRF 업로드 | 비교 왼쪽 (또는 사용자 모드 변환 결과 재사용) |
| 참고 BRF 업로드 | 비교 오른쪽 |
| 비교하기 | **생성 면**마다 참고에서 창을 배정해 점자·역점역 비교 |

배정: 생성 면 텍스트와 **아직 미배정인 참고 구간**에서 최장 연속 일치(기본 ≥16자, **공백·줄바꿈 무시**)를 찾고, 그 앵커로 **생성 면과 같은 내용 길이**의 참고 창을 자른다. 창은 서로 겹치지 않으며, 남는 참고 구간은 **누락**으로 집계·요약에 표시한다. 면 안 음영은 최장 일치 앵커 최대 5개. API: `POST /api/review/generated-brf` · `POST /api/review/reference-brf` · `GET /api/review/bundle` · `GET /api/review/bundle-stream`.

### 0.3 변환 상태·오류 안내 (접근성) — 확정

| 신호 | 구현 |
|------|------|
| 진행·완료 | 페이지당 하나의 `role="status"` + `aria-live="polite"` 영역. 단계 문구만 갱신 (예: «PDF 분석 중», «변환 완료. BRF를 받을 수 있습니다.») |
| 실패 | `role="alert"` + `aria-live="assertive"`. 버튼은 이전 가능 상태로 복귀 |
| 비활성 이유 | `aria-describedby`로 «PDF를 먼저 업로드하세요» / «DTBook보내기는 아직 준비 중입니다» |
| 포커스 | 변환 성공 후 상태 영역으로 포커스 이동 → Tab으로 다운로드 버튼 |

진행률 % 애니메이션·토스트는 쓰지 않는다. 문장형 상태만 쓴다.

---

## 1. 목표 계층

```text
web/ (사용자 모드)     HTML · a11y · 업로드/변환/다운로드
ui/* (진단, 축소 중)   개발자 패널 (읽기 전용 방향)
    ↓
session/               ConversionWorkspace · PdfStructureService
    ↓
pipeline/ · daisy/     종단 변환 · DTBook export 포트
pdf · exam · braille · layout · brf · nav
```

---

## 2. 허용 이음새 (새 셸이 호출)

| API | 모듈 | 용도 |
|-----|------|------|
| `ConversionWorkspace` | `session.workspace` | 사용자/개발자 공용 — 열기·변환·BRF/DTBook (편집 API 없음) |
| `PdfStructureService` | `session.pdf_structure` | 저수준 PDF 세션 (진단·테스트; 편집은 제품 UI에서 비노출) |
| `default_pipeline()` / `PipelineResult` | `pipeline` | 워크스페이스가 감쌈 |
| `DtbookExporter` | `daisy.ports` | Exam → DTBook 2005-3 XML (`ExamDtbookExporter`) |
| `ExamNavigator` + `NavLocation` | `nav` | 개발자 모드 B 계층 패널 |
| `brf` reverse / compare | `brf/*` | 개발자 모드 A 역점역 · 검토 모드 비교 |
| `session.review` | `session/review.py` | 검토 모드 — 생성 면 기준 참고 창 배정·누락 집계 |

### `ConversionWorkspace` 요약

```text
load_pdf(path|bytes) → 메타
analyze_and_convert() → PipelineResult (+ 캐시)
brf_text / brf_bytes
dtbook_xml / dtbook_available
exam_document / source_path
```

---

## 3. UI가 직접 쓰지 말 것

| 패키지 | 이유 |
|--------|------|
| `braille/` · `layout/` | 파이프라인 전용 |
| `pdf` 저수준 편집 API | 제품 UI에서 제거; 서비스/테스트만 |
| `exam.builder` 구체 | 워크스페이스/서비스 경유 |

---

## 4. 현재 매핑

| UI | 상태 |
|----|------|
| `web/` 사용자·개발자·검토 모드 | `/` 업로드·변환·다운로드 · `/dev` 모드 A/B · `/review` BRF 전체 비교 |
| `PdfStructureWindow` | 레거시 **읽기 전용** (병합·분할·태그·저장 메뉴 제거) |
| `BrfInspectorWindow` | 레거시 **읽기 전용** (태그 저장·후보 적용 제거) |

---

## 5. 체크리스트 (새 UI PR)

- [ ] 사용자 플로우는 웹 셸 + `ConversionWorkspace`만
- [ ] 변환은 `analyze_and_convert()` (또는 동일 의미)
- [x] 제품 UI에 병합/분할/태그 수동 편집 없음
- [x] 모드 B XML = DTBook 2005-3 구조 (`ExamDtbookExporter`)
- [ ] 상태/오류는 §0.3 `aria-live` 계약
- [ ] `braille/` · `layout/` 를 UI에서 import하지 않음
