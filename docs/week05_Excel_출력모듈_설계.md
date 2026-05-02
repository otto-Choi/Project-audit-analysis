# Week 5 — 원장 Excel 출력 모듈 설계 및 구현

> 작성일: 2026-04-29 / 정리일: 2026-05-02  
> **성과**: `master_gl_clean.csv` → 계정별 원장·집계 조서 Excel 자동 생성 모듈 설계 및 구현 완료  
> 작업 환경: Jupyter Notebook (뼈대 셀 방식) + openpyxl  
> 실제 출력 파일: `output/원장_조서_20260429.xlsx`

---

## 1. 이번 주 목표 요약

| 항목 | 내용 |
|------|------|
| 입력 | `data/master_gl_clean.csv` |
| 출력 | `output/원장_조서_YYYYMMDD.xlsx` (멀티시트) |
| 작업 파일 | `excel_output/excel_export.ipynb` |
| 핵심 라이브러리 | pandas, openpyxl |

사용자가 노트북 최상단 **Config 셀**에서 계정코드·기간·집계 단위만 바꾸면 나머지 셀이 자동으로 실행되는 구조를 목표로 한다.

---

## 2. 출력 Excel 시트 구성

### Sheet 1: `원장` (Raw Ledger)
- 선택한 계정(들)의 모든 전표 행
- 컬럼: 전표번호, 전기일, 회계연월, 계정코드, 계정명, 차/대변 구분, 금액, 상대방, 적요, 전표유형
- 필터/정렬 자동 적용 (AutoFilter)
- 헤더 고정 (Freeze Panes)

### Sheet 2: `월별집계` (Monthly Summary)
- 선택 계정의 월별 차변합 / 대변합 / 순잔액
- Python 집계 결과를 셀에 기록 + 합계 행은 **Excel SUM 수식** 삽입
- 컬럼 구성 예시:

| 회계연월 | 차변합계 | 대변합계 | 순잔액 | 누계잔액 |
|----------|----------|----------|--------|----------|
| 2022-04 | 1,200 | 800 | 400 | 400 |
| 2022-05 | ... | ... | ... | ... |
| **합계** | **=SUM(B2:B13)** | **=SUM(C2:C13)** | | |

### Sheet 3 (선택): `유형별집계` (Document Type Summary)
- `doc_type` × 계정코드 교차 집계 (Python groupby 후 값 출력)
- 이상치 플래그(`_flag_weekend`, `_flag_reversal`, `_flag_duplicate`) 건수 포함
- 플래그 값이 0이 아닌 셀에 연한 오렌지(`#FCE4D6`) 하이라이팅 자동 적용

---

## 3. Notebook 셀 구조 (뼈대)

```
[Cell 0]  라이브러리 임포트
[Cell 1]  ★ CONFIG ★  ← 사용자가 수정하는 유일한 셀
[Cell 2]  데이터 로드 및 필터
[Cell 3]  원장 컬럼 준비 (13컬럼 선택·이름변환)
[Cell 4]  월별집계 집계 (groupby, 누계잔액 계산)
[Cell 5]  유형별집계 집계 (doc_type × 플래그 건수)
[Cell 6]  스타일 헬퍼 함수 정의 (헤더·합계행·열너비·숫자포맷)
[Cell 7]  Sheet1 원장 출력 (AutoFilter, Freeze, 플래그 하이라이팅)
[Cell 8]  Sheet2 월별집계 출력 (SUM 수식 합계 행)
[Cell 9]  Sheet3 유형별집계 출력 (SUM 수식 + 플래그 오렌지 하이라이팅)
[Cell 10] 파일 저장 및 경로 출력
```

### Cell 1 Config 구조 (실제 구현)

```python
# ★ 이 셀만 수정하세요 ★

# 계정 선택: 단일 코드 or 리스트 (None이면 전체)
TARGET_ACCOUNTS = ["500010"]

# 계층 필터 (account_master.csv 기반, TARGET_ACCOUNTS보다 우선)
LV1_FILTER = None   # 대분류 한글명, e.g. "매출원가"
LV2_FILTER = None   # 중분류 한글명

# 기간 필터 (None이면 전체)
DATE_FROM = "2022-01-01"
DATE_TO   = "2022-12-31"

# 집계 단위: "M" (월별) / "Q" (분기별) / "Y" (연별)
AGG_FREQ = "M"

# 파일 경로
DATA_PATH   = "../data/master_gl_clean.csv"
MASTER_PATH = "../data/account_master.csv"
OUTPUT_DIR  = "../output"

# 출력 파일명 (None이면 자동 날짜)
OUTPUT_NAME = None
```

---

## 4. openpyxl 주요 적용 기법

| 기법 | 적용 위치 | 목적 |
|------|-----------|------|
| `freeze_panes` | 전체 시트 (행1) | 헤더 고정 |
| `auto_filter` | 원장 Sheet | 드롭다운 필터 |
| `PatternFill` | 헤더 행 (진파랑 `#1F3864`) | 헤더 강조 |
| `PatternFill` | 합계 행 (연파랑 `#D9E1F2`) | 합계 행 구분 |
| `PatternFill` | 플래그 컬럼 비zero 셀 (`#FCE4D6`) | 이상치 시각화 |
| `Font(bold=True)` | 헤더 행 / 합계 행 | 시각적 구분 |
| SUM 수식 문자열 삽입 | 월별집계·유형별집계 합계 행 | 실제 Excel 수식 |
| `number_format` | 금액 컬럼 | `#,##0` 천단위 |
| 열 너비 자동 계산 | 전체 시트 | 콘텐츠 기준 min4~max40 |

> SUMIFS 수식: Excel 내 데이터 참조용 수식은 복잡도가 높으므로 이번 주는 **Python 집계 → 값 출력** 방식을 기본으로 하고, 합계 행에만 SUM 수식을 삽입한다.

---

## 5. 구현 순서 (권장)

1. **Cell 0~1**: 임포트 및 Config 뼈대 확정
2. **Cell 2**: `master_gl_clean.csv` 로드 → Config 기반 필터링 검증
3. **Cell 3**: 원장 Sheet 출력 (포맷 없이 값만 먼저)
4. **Cell 3 보완**: AutoFilter / Freeze / 헤더 스타일 추가
5. **Cell 4**: 월별 집계 계산 (pandas groupby)
6. **Cell 4 보완**: 집계 Sheet 출력 + SUM 수식 합계 행
7. **Cell 5 (선택)**: 전표유형별 집계 Sheet
8. **Cell 6**: 파일 저장

---

## 6. 디렉토리 구조

```
project/
├── excel_output/
│   └── excel_export.ipynb       ← 신규 작성
├── output/                      ← 신규 (생성된 Excel 저장)
│   └── (자동 생성)
├── data/
│   ├── master_gl_clean.csv
│   └── account_master.csv
└── week05_Excel_출력모듈_설계.md
```

---

## 7. 이번 주 범위 외 (다음으로 미룸)

| 항목 | 이유 |
|------|------|
| 이상치 탐지 시각화 (차트) | Excel 차트 삽입은 openpyxl 고급 기능 → 별도 주차 |
| Benford's Law 분석 | 독립 모듈, 이번 주 목표와 별개 |
| B형 입력 테스트 | 정제 단계 검증, 출력 모듈과 무관 |
| XLOOKUP 수식 자동 삽입 | 시트 간 참조 구조 복잡 → 기본 버전 완성 후 고도화 |

---

## 8. 완료 기준

- [x] `excel_export.ipynb` Config 셀 1개 수정으로 계정 교체 가능
- [x] Sheet1 원장: AutoFilter + Freeze + 헤더 강조 적용
- [x] Sheet2 월별집계: 차변합 / 대변합 / 순잔액 / 누계잔액 4컬럼 + SUM 합계 행
- [x] 금액 컬럼 천단위 서식 적용
- [x] 복수 계정 선택 시 정상 동작 확인

---

## 9. 다음 주 계획 (Week 6)

| 항목 | 내용 |
|------|------|
| XLOOKUP 수식 삽입 | 시트 간 계정명 참조 자동화 |
| SUMIFS 수식 삽입 | 원장 Sheet → 집계 Sheet 교차 검증 수식 |
| 수식 기반 조서 | Python 집계값 대신 Excel 수식으로 집계 시트 구성 |
| 이상치 시각화 차트 | `_flag_*` 계정별·월별 집계 차트 삽입 (openpyxl BarChart) |
