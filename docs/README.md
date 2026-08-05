# 문서 색인

제품 의도·장기 계획·모듈·알고리즘·작업 방식은 아래를 본다.

| 문서 | 내용 |
|------|------|
| [architecture.md](architecture.md) | 설계 계층, 파이프라인, 모듈 역할, 단계별 알고리즘 |
| [reverse_translation.md](reverse_translation.md) | 역점역 모듈 구조·처리 순서·시험지 토큰·테스트 |
| [quality_loop.md](quality_loop.md) | 참고 BRF 정합을 위한 개발·테스트 루프 (문서 수동 편집 최소화) |
| [guidance_policy.md](guidance_policy.md) | 시각장애용 안내 문구 삽입·양식 일치 정책 |
| [../README.md](../README.md) | 설치·실행·현재 프로토타입 상태 |

## Phase 0 분석 노트 (규칙 축적)

실제 PDF–BRF 짝을 보며 채운다. 빈 표는 “아직 미기록”이지 기능 부재를 뜻하지 않는다.

| 문서 | 기록 대상 |
|------|-----------|
| [brf_structure_notes.md](brf_structure_notes.md) | 면·행·머리말·구분선·문항 표기 관례 |
| [pdf_brf_mapping.md](pdf_brf_mapping.md) | PDF 면 ↔ 점자 면 대응 |
| [separator_patterns.md](separator_patterns.md) | 구분선 ASCII 패턴 |
| [page_number_rules.md](page_number_rules.md) | 머리말·쪽 번호 |
| [question_choice_rules.md](question_choice_rules.md) | 문항·선택지 점자 형태 |
| [unresolved_cases.md](unresolved_cases.md) | 미해결·예외 사례 |

규칙을 코드에 반영한 뒤에는 해당 노트의 “코드 반영” 칸에 모듈·커밋을 적는다.
