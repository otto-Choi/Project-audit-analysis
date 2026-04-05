# Week 3 — 정제 모듈 설계 (sap.ipynb)

> 기간: 2026년 4월  
> 작업 파일: `sap.ipynb`  
> 설정 파일: `config.yaml` (클라이언트별 교체)  
> 입력: config.yaml에 지정된 파일 (A/B/C형 대응)  
> 출력: `master_gl_clean.csv` (원본 + 파생변수), `master_gl_subtotal.csv` (소계행)

---

## 1. 수행 의도

`병합과정/merge.ipynb`이 생성한 `master_gl` 파일을 받아 **분석 가능한 표준 스키마**로 변환한다.

**핵심 설계 원칙**: 노트북 코드는 수정하지 않는다. 클라이언트마다 다른 컬럼명·금액 형태는 **config.yaml만 교체**하여 대응한다.

```
client_A.yaml ─┐
client_B.yaml ─┤── sap.ipynb (처리 로직, 고정) → master_gl_clean.csv
client_C.yaml ─┘
```

### 역할 범위

| 역할 | 포함 여부 |
|------|-----------|
| config.yaml 로드 | ✅ |
| 컬럼명 표준화 (column_map 적용) | ✅ |
| 소계행 탐지 및 분리 | ✅ |
| 날짜 파싱 (다형성 지원) 및 파생변수 | ✅ |
| 금액 형태별 표준화 (A/B/C형) | ✅ |
| 코드 자연어 변환 파생변수 | ✅ |
| 이상치 플래그 생성 | ✅ |
| 원본 데이터 수정 | ❌ (절대 금지) |
| 시각화·분석 | ❌ (03_analyze.ipynb 역할) |

---

## 2. config.yaml 구조

모든 "데이터 지식"(컬럼명, 키워드, 금액 형태 등)을 config.yaml에 집약한다.  
노트북 내 하드코딩 없음.

```yaml
client:   "SAP_sample"
encoding: "utf-8-sig"

paths:
  input_file:      "master_gl_순금액 표시.csv"
  output_clean:    "master_gl_clean.csv"
  output_subtotal: "master_gl_subtotal.csv"

str_cols: [전표번호, 회사코드, 회계연도, 라인번호, 계정코드, 역분개참조번호]

column_map:
  "전표번호":           "doc_no"
  "현지통화금액":       "amount"
  "차대구분":           "dc_indicator"
  # ... (18개 전체)

subtotal:
  keywords: [소계, 합계, total, subtotal, 계]
  acc_code_min_len: 10
  required_not_null: "doc_no"

date:
  post_date_col:  "post_date"
  doc_date_col:   "doc_date"
  fisc_month_col: "fisc_month"

amount:
  type: "B"               # A / B / C
  amount_col: "amount"    # column_map 적용 후 컬럼명
  dc_col: "dc_indicator"
  debit_keywords: [차변, Debit, DR, S]
  net_col:    "net_amount"     # B형 시 사용
  debit_col:  "debit_amount"   # A형 시 사용
  credit_col: "credit_amount"  # A형 시 사용

flags:
  reversal_col:        "reversal_yn"
  reversal_keyword:    "역분개"
  acc_type_col:        "acc_type"
  acc_type_pl_keyword: "PL"
  fisc_year_col:       "fisc_year"
```

---

## 3. 표준 컬럼명 (column_map 적용 후)

`sap.ipynb` 및 config.yaml 기준으로 확정된 표준 영어 컬럼명.

| 한글 원본 | 표준 영어 | 타입 | 비고 |
|-----------|-----------|------|------|
| 전표번호 | `doc_no` | str | |
| 회사코드 | `company_code` | str | |
| 회계연도 | `fisc_year` | str | |
| 라인번호 | `line_no` | str | |
| 전기일 | `post_date` | datetime (파싱 후) | |
| 증빙일 | `doc_date` | datetime (파싱 후) | |
| 회계월 | `fisc_month` | str 원본 → `_fisc_month_int`로 파생 | "04월" 형태 |
| 계정코드 | `acc_code` | str | 앞자리 0 포함 |
| 계정명 | `acc_name` | str | |
| 계정속성(BS/PL) | `acc_type` | str | |
| 현지통화금액 | `amount` | float | C형 입력 |
| 차대구분 | `dc_indicator` | str | C형 입력 |
| 통합거래처명 | `counterparty` | str | NaN 가능 |
| 원가센터명(부서명) | `department` | str | NaN 가능 |
| 적요 | `description` | str | |
| 전표성격 | `doc_type` | str | |
| 역분개여부 | `reversal_yn` | str | |
| 역분개참조번호 | `reversal_ref` | str | NaN 가능 |

---

## 4. 처리 단계 설계

### STEP 0 — 파일 로드

```python
df = pd.read_csv(
    cfg['paths']['input_file'],
    dtype={col: str for col in cfg['str_cols']},
    encoding=cfg['encoding'],
    low_memory=False
)
```

- `str_cols`는 config에서 읽음 — 지수표기·앞자리 0 소실 방지
- `low_memory=False` — mixed types 경고 방지
- 원본 보존: `df_raw = df_raw.copy()`

---

### STEP 1 — column_map 적용

```python
df = df.rename(columns=cfg['column_map'])
unmapped = [c for c in df.columns if any(ord(ch) > 127 for ch in c)]
```

- 매핑 후 한글 잔존 컬럼 자동 감지 출력 → config 누락 확인용

---

### STEP 2 — 소계행 탐지 및 분리

탐지 기준 3가지 (OR 조건), 모두 config에서 읽음:

| 기준 | config 키 | 탐지 방법 |
|------|-----------|-----------|
| 전표번호 NaN | `required_not_null` | `doc_no.isna()` |
| 계정명 키워드 | `keywords` | `acc_name.str.contains(...)` |
| 계정코드 자릿수 | `acc_code_min_len` | `acc_code.str.len() < 10` |

소계행은 삭제하지 않고 `df_subtotal`로 분리 보존.  
행수 합계 검증: `len(df) + len(df_subtotal) == RAW_LEN`

---

### STEP 3 — 날짜 파싱 및 파생변수

#### parse_date_flexible() 함수

| 입력 형태 | 예시 | 처리 방법 |
|-----------|------|-----------|
| 구분자형 | `2022-04-24`, `2022.04.24` | `infer_datetime_format=True` |
| 8자리 숫자형 | `20220424` | `format='%Y%m%d'` |
| 엑셀 시리얼형 | `44675` | `Timestamp('1899-12-30') + timedelta` |
| 한글형 | `2022년 4월 24일` | 정규식 전처리 후 파싱 |

#### parse_fisc_month() 함수

`"04월"` → `4` (정수), `"4"` / `"04"` 형태도 모두 처리.

#### 날짜 파생변수

| 컬럼명 | 내용 |
|--------|------|
| `_post_year` | 전기연도 |
| `_post_month` | 전기월 |
| `_post_day` | 전기일 |
| `_post_weekday` | 전기요일 (day_name) |
| `_post_quarter` | 분기 |
| `_is_weekend` | 주말여부 (bool) |
| `_fisc_month_int` | 회계월 정수 (`fisc_month` 파싱) |

---

### STEP 4 — 금액 표준화 (amount_type 분기)

config `amount.type` 값에 따라 분기:

| type | 입력 컬럼 | 처리 방법 |
|------|-----------|-----------|
| **C** | `amount` (절대값) + `dc_indicator` (플래그) | `str.contains` + `where` 벡터화 |
| **B** | `net_amount` (순금액, 양수=차변/음수=대변) | `clip(lower=0)` / `(-x).clip(lower=0)` |
| **A** | `debit_amount` + `credit_amount` (컬럼 분리) | `fillna(0)` 후 합산 |

**표준 출력 3컬럼** (형태 불문 동일):

| 컬럼 | 내용 |
|------|------|
| `_debit` | 차변금액 (대변이면 0) |
| `_credit` | 대변금액 (차변이면 0) |
| `_amount` | 순금액 (차변 양수, 대변 음수) |

---

### STEP 5 — 코드 변환 파생변수

원본 코드값 보존 + 파생변수 추가:

| 파생 컬럼 | 산출 | config 키 |
|-----------|------|-----------|
| `_is_pl` | `acc_type`에 'PL' 포함 여부 | `acc_type_pl_keyword` |
| `_is_reversal_flag` | `reversal_yn`에 '역분개' 포함 여부 | `reversal_keyword` |

---

### STEP 6 — 이상치 플래그

| 컬럼 | 탐지 조건 |
|------|-----------|
| `_flag_weekend` | `_is_weekend == True` |
| `_flag_reversal` | `_is_reversal_flag == True` |
| `_flag_out_of_period` | `post_date.year != fisc_year` |
| `_flag_duplicate` | `(doc_no, line_no)` 중복 |

---

## 5. 출력 스키마 (파생변수 전체 목록)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `_post_year` | int | 전기연도 |
| `_post_month` | int | 전기월 |
| `_post_day` | int | 전기일 |
| `_post_weekday` | str | 전기요일 |
| `_post_quarter` | int | 분기 |
| `_is_weekend` | bool | 주말여부 |
| `_fisc_month_int` | Int64 | 회계월 정수 |
| `_debit` | float | 차변금액 |
| `_credit` | float | 대변금액 |
| `_amount` | float | 순금액 |
| `_is_pl` | bool | PL 계정여부 |
| `_is_reversal_flag` | bool | 역분개여부 |
| `_flag_weekend` | bool | 이상치: 주말전기 |
| `_flag_reversal` | bool | 이상치: 역분개 |
| `_flag_out_of_period` | bool | 이상치: 기간외전기 |
| `_flag_duplicate` | bool | 이상치: 중복전표 |

---

## 6. 검증 항목

| 검증 | 기준 | 판정 |
|------|------|------|
| 행수 유지 | `len(df) + len(df_subtotal) == RAW_LEN` | ❌ 불일치 시 소계행 탐지 조건 재확인 |
| 차대균형 | `abs(_debit.sum() - _credit.sum()) < 0.01` | ❌ 불일치 시 금액 처리 재확인 |
| 날짜 파싱 오류 | `post_date.isna().sum() == 0` | ⚠️ NaN 존재 시 파싱 실패 행 출력 |
| 플래그 건수 | 각 플래그 True 건수 출력 | 참고용 |

---

## 7. 노트북 셀 구성

```
[Cell 1]  라이브러리 import (pandas, numpy, yaml, re)
[Cell 2]  config 로드 — CONFIG_FILE 경로만 수정하면 클라이언트 전환
[Cell 3]  STEP 0: 파일 로드
[Cell 4]  STEP 1: column_map 적용 + 잔존 한글 컬럼 확인
[Cell 5]  STEP 2: 소계행 탐지 및 분리 + 행수 검증
[Cell 6]  날짜 파싱 함수 정의 (parse_date_flexible, parse_fisc_month)
[Cell 7]  STEP 3: 날짜 파싱 + 파생변수
[Cell 8]  STEP 4: 금액 표준화 (amount_type 분기)
[Cell 9]  STEP 5: 코드 변환 파생변수
[Cell 10] STEP 6: 이상치 플래그
[Cell 11] 검증: 차대균형 + 파생변수 샘플 출력
[Cell 12] 저장
```

---

## 8. 시행착오 이력

### [2026-04-05] config.yaml — acc_code_min_len 조정
- **현상**: 초기 설정값 `acc_code_min_len: 10`으로 설정했으나 실데이터 확인 후 `6`으로 수정
- **원인**: 데이터셋의 계정코드 자릿수가 예상과 달랐음
- **교훈**: 소계행 탐지 기준값은 데이터 확인 후 config에서 조정 — 코드 수정 불필요

### [2026-04-05] B형 입력 검증 완료
- `master_gl_순금액 표시.csv` (구분자 없이 순액으로 표시된 B형) 를 config 교체만으로 정제 성공
- config 변경 내용: `paths.input_file`, `amount.type: B`, `amount.net_col`
- 노트북 코드 수정 없이 동작 확인 → config 기반 설계 유효성 검증

---

## 9. 주요 설계 결정

| 결정 | 이유 |
|------|------|
| config.yaml 기반 설계 | 클라이언트마다 다른 컬럼명·금액 형태를 노트북 수정 없이 대응 |
| 표준 컬럼명을 sap.ipynb 기준으로 확정 | 설계 문서와 코드 간 불일치 해소 |
| 파생변수 `_` 접두사 | 원본 컬럼과 구분, 조서 참조 시 실수 방지 |
| 소계행 분리 보존 (삭제 X) | 원본 재현 가능성 유지 |
| bool 타입 플래그 | 필터링·집계 편의성 (`_flag.sum()`) |
| `parse_date_flexible` 함수 분리 | 다형성 날짜 처리를 재사용 가능한 단위로 캡슐화 |
| `parse_fisc_month` 함수 분리 | "04월" → 정수 변환, 다양한 형태 대응 |

---

## 10. 다음 작업 계획 (Week 4)

정제된 `master_gl_clean.csv`를 바탕으로 **탐색·조회 기능**을 구현한다.  
작업 파일: `03_analyze.ipynb` (신규)

### 10-1. 계정별 내역 조회

특정 계정의 전표 내역을 필터링하여 확인한다.

```
입력: master_gl_clean.csv
조회 흐름: 계정 선택 → 해당 계정의 전표 목록 → 금액 집계 (월별·분기별)
```

| 구현 항목 | 내용 |
|-----------|------|
| 계정 목록 출력 | `acc_code` + `acc_name` 유니크 목록, 잔액 기준 정렬 |
| 계정별 필터링 | `df[df['acc_code'] == target_acc]` |
| 기간별 집계 | `groupby(['_post_year', '_post_month'])['_amount'].sum()` |
| 이상치 건수 확인 | 해당 계정의 `_flag_*` 건수 |

### 10-2. 전표번호별 분개 조회

특정 전표번호로 모인 라인 아이템 전체를 확인한다.  
감사 목적: 특정 분개의 차대변 양측을 동시에 확인 → 거래의 성격 파악.

```
입력: master_gl_clean.csv
조회 흐름: 전표번호 입력 → 해당 전표의 모든 라인 출력 → 차대변 합계 확인
```

| 구현 항목 | 내용 |
|-----------|------|
| 전표 단건 조회 | `df[df['doc_no'] == target_doc]` |
| 분개 요약 출력 | `doc_no`, `line_no`, `acc_code`, `acc_name`, `_debit`, `_credit`, `description` 선택 출력 |
| 차대균형 확인 | 해당 전표의 `_debit.sum() == _credit.sum()` |
| 관련 계정 목록 | 해당 전표에 포함된 모든 `acc_code` 목록 → 연계 계정 파악 |

### 10-3. 설계 방향

- **이번 주**: Jupyter Notebook 셀 기반 조회 (인터랙티브 변수 수정)
- **이후**: Streamlit UI로 발전 (계정 선택 → 전표 클릭 → 분개 확인 드릴다운)
