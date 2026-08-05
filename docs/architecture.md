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
| `common/` | 구조 태그·Exam 노드 타입 상수 | — |
| `pdf/` | PDF → 물리 구조 문서 | `DefaultPdfStructureExtractor` |
| `exam/` | 물리 구조 → 의미 트리·관계 | `RuleExamStructureBuilder`, `RuleExamStructureValidator` |
| `braille/` | Exam/묵자 → 점자 시퀀스 | `TableBrailleTranslator` |
| `layout/` | 시퀀스 → 줄·면 → BRF 문자열 | `RuleBrailleLayoutEngine`, `AsciiBrfSerializer` |
| `brf/` | BRF 입출력·역점역·비교·주석 | parser, reverse_translator, compare, exam_diff |
| `nav/` | Exam 트리 탐색 | `TreeExamNavigator` |
| `pipeline/` | 포트 조립·실행 | `ConversionPipeline` |
| `ui/*` | 진단·미리보기·Inspector (편집은 최소화) | PySide6 |
| `ml/` | (후속) 결정·후보 — 비어 있음 | — |

설정: `profiles/default.yaml` (줄 폭·면 높이·들여쓰기).  
규칙 축적: `docs/` Phase 0 노트, 향후 `rules/`.

---

## 4. 단계별 알고리즘 (현재 코드 기준)

### 4.1 PDF (`pdf/`)

1. **추출** (`extractor`): PyMuPDF로 페이지 렌더·문자 스팬(좌표·텍스트) 수집.
2. **행** (`line_builder`): y 근접·x 순으로 스팬을 행으로 묶음.
3. **레이아웃 프로필** (`layout_profile`): 면별 다단·여백·헤더/푸터 대역 추정.
4. **블록** (`block_builder`): 행을 문단/구조 단위로 병합.  
   - 새 블록 시작 휴리스틱: `[N~M]`, `N.`, ①–⑤, 〈보기〉, 긴 구분선 등 (`_BLOCK_START`).
5. **읽기 순서** (`reading_order`): 열·수직 순으로 `reading_order` 부여.
6. **후보 태그** (`candidates`): 정규식·위치로 Header/Question/Choice/PassageGroup 등 `candidate_tags` 부여.

진단 UI에서 병합·분할·태그 덮어쓰기가 가능하나, **제품 목표는 이 단계 자동 정확도를 올려 UI 수정을 줄이는 것**이다.

### 4.2 Exam (`exam/`)

`RuleExamStructureBuilder`:

1. 페이지·`reading_order` 순으로 블록 순회.
2. 블록의 tags/candidate_tags에서 우선순위로 대표 태그 선택 (Header > … > Question > Choice …).
3. 상태 기계적으로 PassageGroup / Question / Choice / ExampleBox 등을 트리에 부착.
4. `[N~M]`·문항 번호 정규식으로 메타데이터(`question_number` 등) 채움.
5. 지문↔문항 등 `ExamRelation` 생성.

`RuleExamStructureValidator`: 문항 수·선택지 개수 등 전역 경고.

### 4.3 점역 (`braille/`)

`TableBrailleTranslator`:

1. Exam 트리를 순회하며 노드 텍스트를 토큰화.
2. 한글: 음절 분해 → 초·중·종 + 약자/약어 표 (`korean_tables`, CV/VC, 된소리 등) → ASCII 셀.
3. 시험 특수 형태: `[N~M]` → `82#…`, `N.` → `#x4`, ① → `#1` 등 (국내 참고 BRF 관례에 맞춤).
4. 출력: `BrailleSequence` 목록 (노드 타입·source id 메타 포함).

역점역은 `brf/reverse_translator` (Inspector·내용 비교용). **모듈 구조·처리 순서·시험지 토큰·테스트 목록은 [reverse_translation.md](reverse_translation.md).**  
요약: 복합 문장부호 최장 일치 → 온표/수표/로마자 상태 → 된소리 → 약자 → 음절 분석이며, 미인식 셀은 `<U:…>`로 남긴다. 로마자 모드는 공백·괄호를 유지하고, 대문자 약어 뒤 한글 조사에서만 종료한다. **정합의 최종 척도는 ASCII 셀 비교**이지 역점역 유사도가 아니다.

### 4.4 레이아웃 (`layout/`)

`RuleBrailleLayoutEngine` + `LayoutProfile`:

1. 시퀀스 ASCII를 노드 타입별 들여쓰기로 배치.
2. 줄 폭 초과 시 셀 단위 줄바꿈 (`_wrap_ascii`).
3. 면 높이 초과 시 새 면(폼피드).
4. 국내 관례 구분선 `=ggg…=` 삽입.
5. 머리말: 참고 BRF에 맞춘 줄 분리·가운데 패딩 (`header_format` 등).

`AsciiBrfSerializer`: 면을 `\x0c`로 이어 BRF 텍스트 생성.

### 4.5 비교 (`brf/`)

| 도구 | 입력 | 방법 | 용도 |
|------|------|------|------|
| `compare` | 생성·참고 BRF | 면·줄 ASCII 셀 overlap | **최종 정합 지표** |
| `exam_diff` | 동일 | 역점역 묵자 + 지문/문항 앵커 정렬 | 구조·누락·안내 분리 진단 |

`exam_diff`는 참고본 안내를 당분간 `expected_guidance`로 분류한다. 안내 삽입이 구현되면 이 분류는 “아직 미삽입” 또는 “양식 불일치”로 바뀐다.

### 4.6 탐색 (`nav/`)

`TreeExamNavigator`: ExamDocument만 바인딩. 부모/형제/유형별 다음·원위치. PDF 블록 id ↔ 노드 양방향 연동은 UI. 점역·BRF 면 동기화는 후속 (`source_node_ids`).

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
