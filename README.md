# 수능 국어 PDF–BRF 변환

대학수학능력시험 국어 문제지 PDF를 구조 분석·점역·재편집하여 BRF로 출력하는 프로그램입니다.

현재 단계: **Prototype 1 — BRF Inspector**

## 요구 사항

- Python 3.12+
- PySide6

## 설치

```bash
pip install -e ".[dev]"
```

## BRF Inspector 실행

```bash
brf-inspector
# 또는
python -m korean_exam_braille.app.main
```

파일 인자로도 열 수 있습니다.

```bash
python -m korean_exam_braille.app.main path/to/sample.brf
```

## 테스트

```bash
pytest
```

## 디렉터리

```text
korean_exam_braille/   애플리케이션 코드
tests/                 단위 테스트
data/                  PDF·BRF 원본과 주석
docs/                  Phase 0 분석 노트
profiles/              줄·면 편집 프로필
rules/                 구조·점역 규칙
```

## 개발 순서

1. BRF Inspector (현재)
2. PDF Structure Viewer
3. 지문 한 묶음 종단 변환
4. 시험 전체 변환
