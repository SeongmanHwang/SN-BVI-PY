# 품질 루프 — 코드로 참고 BRF에 맞추기

## 원칙

1. **최종 성공 기준**: 같은 시험의 생성 BRF와 시각장애용 참고 BRF가 **거의 일치** (우선 지표: `brf.compare` 셀·줄 일치율).
2. **차이를 줄이는 수단**: 규칙·점역표·레이아웃·구조 빌더 등 **코드 수정** + `pytest` / 비교 CLI.
3. **UI 문서 편집**: PDF 블록 병합·태그 덮어쓰기, BRF 주석 저장 등은 **진단·예외 확인용**이다. 제품이 의도하는 일상 경로는 아니다.
4. **안내문**: 장기적으로는 무시하지 않고 삽입해 맞춘다 → [guidance_policy.md](guidance_policy.md).

## 개발자 루프 (권장)

```text
1. 고정 PDF + 참고 BRF 짝 준비 (data/ 또는 로컬 Downloads)
2. 파이프라인 실행 → 생성 BRF
3. 줄·셀 비교 (정합) + 필요 시 내용 비교 (구조 진단)
4. 실패 구간을 모듈에 귀속
     · 문항 누락/엉뚱한 본문 → pdf candidates / exam builder
     · 발문은 맞는데 점자 셀 다름 → braille translator / tables
     · 줄바꿈·구분선·머리말 → layout / profiles
     · 참고에만 있는 안내 → guidance (예정)
5. 최소 재현 fixture 또는 단위 테스트 추가
6. 코드 수정 → pytest → 같은 짝으로 비교 재실행
7. docs/ Phase 0 노트에 관례·예외 한 줄 기록
```

### CLI

```bash
# 셀·줄 정합 (최종 지표에 가깝다)
python -c "from korean_exam_braille.app.brf.compare import compare_to_reference_file; from korean_exam_braille.app.pipeline import default_pipeline; r=default_pipeline().run('exam.pdf'); print(compare_to_reference_file(r.brf_text, 'ref.brf').summary())"

# 앵커 내용 진단 (역점역 기반 — 보조)
python -c "from korean_exam_braille.app.brf import compare_pdf_to_reference_brf; print(compare_pdf_to_reference_brf('exam.pdf', 'ref.brf').summary())"

python -m pytest
```

### UI (진단)

- PDF 열기 → 변환 미리보기 / 참고 BRF 비교로 **어디가 깨졌는지** 확인.
- 블록을 손으로 고쳐서 “이 구조면 통과한다”를 확인했다면, **그 보정을 코드 휴리스틱으로 옮긴 뒤** UI 수정에 의존하지 않는다.

## 비교 도구 역할

| 도구 | 비교 대상 | 쓸 때 |
|------|-----------|--------|
| `compare` | BRF ASCII 셀 | 점역·레이아웃 정합, 회귀 |
| `exam_diff` | 역점역 묵자 + 앵커 | 문항 매핑 오류, 누락, 안내 구간 분리 |

내용 비교의 낮은 유사도만으로 점역 버그를 단정하지 않는다. 역점역 노이즈가 섞인다.

## 수락 기준 (목표치 — 조정 가능)

| 단계 | 기준 (안) |
|------|-----------|
| Prototype 3 유지 | 대표 짝에서 머리말·구분선·주요 앵커 형태 참고와 동일 계열 |
| Prototype 4 | 45문항 구조 누락 없이 생성, 내용 비교 오류 후보를 코드로 소거 |
| 정합 목표 | 참고 BRF 대비 셀 일치율을 회차별로 측정·상향 (수치는 노트에 기록) |
| 안내 삽입 후 | guidance_policy 체크리스트 통과 + 셀 비교에 안내 구간 포함 |

## UI 편집을 남겨 두는 이유

자동 추출이 틀린 **원인을 눈으로 확인**하고, 수정 전후 BRF를 빠르게 보기 위함이다.  
“사용자가 매번 블록을 고쳐 완성본을 만든다”는 목표가 아니다.
