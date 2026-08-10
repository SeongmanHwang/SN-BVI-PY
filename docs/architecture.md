# 아키텍처 — 모듈 역할과 알고리즘

최종 목표는 **비장애 국어 문제지 PDF → 생성 BRF**가 같은 시험의 **시각장애용 참고 BRF와 거의 일치**하는 자동 변환이다.  
UI의 문서 수동 편집은 진단용 최소 경로이고, 차이는 **코드·규칙·테스트**로 줄인다.  
작업 방식은 [quality_loop.md](quality_loop.md), 안내문은 [guidance_policy.md](guidance_policy.md).

---

## 1. 설계 계층

```text
1. PDF 물리 구조       문자·행·블록·좌표·후보 태그
2. 수능 국어 의미 구조   지문 묶음·문항·선택지·보기·관계
3. (예정) 안내·양식     시각장애용 머리말·유의·꼬리말 템플릿
4. 점자 번역 구조       묵자 → ASCII 점자 셀·토큰
5. BRF 출력 구조        들여쓰기·줄바꿈·면 분할·구분선·직렬화
6. 탐색 구조            Exam 트리 위 이동 (점역과 독립)
7. 검수                 셀 줄 비교 · 앵커 내용 비교
```

계층 3(안내)은 현재 비교에서 “예상 차이”로만 다루며, 장기적으로는 **생성 파이프라인에 삽입**해 참고본과 맞춘다.

---

## 2. 종단 파이프라인

기본 구현: `pipeline.default_pipeline()`.

```text
PDF 파일
  → PdfStructureExtractor          (pdf/)
  → ExamStructureBuilder           (exam/)
  → ExamStructureValidator         (exam/)  → warnings
  → BrailleTranslator              (braille/)
  → BrailleLayoutEngine            (layout/)
  → BrfSerializer                  (layout/)
  → BRF 텍스트 (+ PipelineResult에 중간물 보존)
```

각 단계는 `*/ports.py` Protocol로 주입한다. Stub 구현으로 단계 단위 테스트·교체가 가능하다.

**예정 삽입점 (안내문):** Builder 이후 또는 Layout 직전에 `Instruction`/`Guidance` 노드·시퀀스를 넣는 단계. 상세는 guidance_policy.md.

---

## 3. 모듈 역할

| 패키지 | 역할 | 기본 구현 |
|--------|------|-----------|
| `common/` | 구조 태그·Exam 노드 타입·점역 표·묵자 구조 정규식 | — |
| `pdf/` | PDF → 물리 구조 문서 | `DefaultPdfStructureExtractor` |
| `exam/` | 물리 구조 → 의미 트리·관계 | `RuleExamStructureBuilder`, `RuleExamStructureValidator` |
| `braille/` | Exam/묵자 → 점자 시퀀스 | `TableBrailleTranslator` |
| `layout/` | 시퀀스 → 줄·면 → BRF 문자열 | `RuleBrailleLayoutEngine`, `AsciiBrfSerializer` |
| `brf/` | BRF 입출력·역점역·비교·주석 | parser, reverse_translator, compare, exam_diff |
| `nav/` | Exam 트리 탐색 | `TreeExamNavigator` |
| `pipeline/` | 포트 조립·실행 | `ConversionPipeline` |
| `session/` | UI용 Qt-free 세션 | `ConversionWorkspace`, `PdfStructureService` |
| `daisy/` | Exam → DTBook 2005-3 구조 XML (DAISY 중간 원고) | `ExamDtbookExporter` |
| `web/` | 사용자 모드 웹 셸 (WCAG 지향) | Starlette |
| `ui/*` | 레거시 진단 UI (축소 예정; [ui_shell.md](ui_shell.md)) | PySide6 |
| `ml/` | (후속) 결정·후보 — 비어 있음 | — |

설정: `profiles/default.yaml` (줄 폭·면 높이·들여쓰기).  
규칙 축적: `docs/` Phase 0 노트, 향후 `rules/`.

---

## 4. 단계별 알고리즘 (현재 코드 기준)

### 4.1 PDF (`pdf/`)

1. **추출** (`extractor`): PyMuPDF `rawdict`로 문자 스팬(좌표·텍스트·`char_bboxes`) 수집.
2. **벡터 표·래스터 그림·밑줄·꺾쇠** (`tables`, `figures`, `emphasis`, `bracket_groups`):
   도면·이미지·짧은 가로선·여백 `[A]` 기하를 페이지 구조에 반영.
3. **행** (`line_builder`): 열·y 근접으로 줄을 묶고 `<u>…</u>` 직렬화.
4. **그래픽 선형화** (`graphic_linearize`): 원문자 전용 행 병합, 표/그림/박스 표선 승격.
5. **중략 줄거리** (`plot_summary`): 글꼴 런 끝에 `[줄거리 끝]` 삽입.
6. **레이아웃 프로필** (`layout_profile`): 머리/꼬리 밴드·2단 `column_cut_x`.
7. **블록·읽기 순서·후보 태그** (`block_builder`, `reading_order`, `candidates`).

상세 순서·표는 [local_translation_rules.md](local_translation_rules.md) §B.  
진단 UI는 **읽기 전용**이다. **제품 목표는 이 단계 자동 정확도를 올려 UI 수정을 불필요하게 하는 것**이다.

### 4.2 Exam (`exam/`)

`RuleExamStructureBuilder`:

1. 페이지·`reading_order` 순으로 블록 순회.
2. 후보 태그 우선순위로 PassageGroup / Question / Choice / ExampleBox 등 부착.
3. `[N~M]`·문항 번호로 메타데이터 채움, 지문↔문항 `ExamRelation` 생성.
4. **`apply_genre_paragraph_splits`**: 들여쓰기로 장르(시·대화문·소설·비문학) 판정,
   장르별 Passage 문단 재분할, Passage에 `indent_genre` 전파 (시는 개행·재분할 보존).

`RuleExamStructureValidator`: 문항 수·선택지 개수 등 전역 경고.  
장르·개행 관례: [local_translation_rules.md](local_translation_rules.md) §A-8 · §C.

### 4.3 점역 (`braille/`)

`TableBrailleTranslator`:

1. Exam 노드 텍스트 → (한자 음독/병기 접기) → 한글 음절·약자·시험 토큰 → ASCII 셀.
2. 로컬 셀 충돌·로마자·원문자 등은 [local_translation_rules.md](local_translation_rules.md) §A.
3. Passage/Choice/Question은 하드 개행을 공백으로 합침. **시**(`indent_genre`)만 시행 유지.
4. 출력: `BrailleSequence` (node_type · indent_genre · keep_hard_newlines 등).

역점역: [reverse_translation.md](reverse_translation.md). **최종 정합 척도는 ASCII 셀 비교**.

### 4.4 레이아웃 (`layout/`)

`RuleBrailleLayoutEngine` + `LayoutProfile` (기본 32셀×26줄):

1. 노드 타입별 들여쓰기.
2. 산문 등: 남은 `\n`도 평탄 후 soft wrap. **시**: 하드 개행 유지·행별 wrap.
3. 로마자 구간 줄바꿈 시 `0` 재삽입 (`roman_mask`).
4. 면 분할·구분선·머리말 패딩 (`header_format`).

`AsciiBrfSerializer`: 면을 `\x0c`로 이어 BRF 텍스트 생성.

### 4.5 비교 (`brf/`)

| 도구 | 입력 | 방법 | 용도 |
|------|------|------|------|
| `compare` | 생성·참고 BRF | 면·줄 ASCII 셀 overlap | **최종 정합 지표** |
| `exam_diff` | 동일 | 역점역 묵자 + 지문/문항 앵커 정렬 | 구조·누락·안내 분리 진단 |

`exam_diff`는 참고본 안내를 당분간 `expected_guidance`로 분류한다. 안내 삽입이 구현되면 이 분류는 “아직 미삽입” 또는 “양식 불일치”로 바뀐다.

### 4.6 탐색 (`nav/`)

`TreeExamNavigator`: ExamDocument만 바인딩. 부모/형제/유형별 다음·원위치. PDF 블록 id ↔ 노드 양방향 연동은 UI 어댑터. 점역·BRF 면 동기화는 후속 (`source_node_ids`).

UI 셸이 Exam/Nav를 만들 때는 `session.PdfStructureService.create_navigator()`를 쓴다 (빌더·내비게이터 주입 가능).

---

## 5. 데이터 계약 (요약)

```text
PdfDocumentStructure
  pages[] → lines[], blocks[] (bbox, text, reading_order, tags)

ExamDocument
  root ExamNode 트리 + relations[]
  SourceRange(page, block_ids, raw_text)

BrailleSequence / BrailleToken
  → BrailleDocument (pages → lines of cells)
  → str BRF (ASCII + form feed)
```

---

## 6. 장기 계획과의 대응

| 목표 | 관련 모듈 | 문서 |
|------|-----------|------|
| 참고 BRF 셀 거의 일치 | braille, layout, exam, pdf + compare | quality_loop.md |
| 안내 양식 일치 | (예정) guidance + layout | guidance_policy.md |
| 코드로 차이 해소 | tests/, compare, exam_diff | quality_loop.md |
| UI 수동 편집 최소화 | pdf/exam 자동화 강화 | README, quality_loop.md |

Phase·프로토타입 표는 README를 본다. 이 문서는 **구현이 바뀌면 여기 알고리즘 절을 갱신**한다.
