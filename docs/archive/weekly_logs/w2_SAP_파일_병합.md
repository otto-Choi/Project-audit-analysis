# Week 2 — SAP 테이블 병합 및 샘플 데이터 구축

> 기간: 2026년 2주차  
> 작업 파일: `00_sample_data_build.ipynb`  
> 중간 산출물: `master_gl.csv`  
> 최종 출력: `GL_type_A.csv`, `GL_type_B.csv`, `GL_type_C.csv`, `GL_type_D.csv`

---

## 1. 수행 의도

SAP에서 추출한 7개의 원천 CSV 테이블을 하나의 분석용 마스터 데이터셋으로 병합한다.
목적은 감사인이 실제 업무에서 수령하는 원장 파일과 유사한 **샘플 데이터**를 구축하는 것이다.

이 노트북(`00_sample_data_build.ipynb`)은 분석 파이프라인(`01_convert`, `02_clean` 등)과 별도로 관리하며, **샘플 데이터 생성 전용**으로 사용한다. 한 번 실행하면 이후 분석 노트북들의 입력 데이터로 활용된다.

> **이 노트북의 역할 범위**  
> 샘플 데이터 생성 = 회사가 감사인에게 제출하는 원장의 형태를 시뮬레이션하는 것까지.  
> 파생변수 생성(요일, 순금액, 코드 변환 등)은 정제 모듈(`02_clean.ipynb`)의 역할이므로 여기서 수행하지 않는다.

### 대상 테이블

| 테이블 | 내용 | 역할 |
|--------|------|------|
| BSEG | 전표 라인 아이템 | 기준(Fact) 테이블 |
| BKPF | 전표 헤더 | 전기일·증빙일·전표유형 등 헤더 정보 |
| SKA1 | 계정과목표 | 계정 BS/PL 구분 |
| SKAT | 계정 텍스트 | 계정명(영문) |
| KNA1 | 고객 마스터 | 고객명 |
| LFA1 | 벤더 마스터 | 벤더명 |
| CSKT | 원가센터 텍스트 | 원가센터명(부서명) |

### 최종 출력 스키마 (18개 컬럼)

전표번호, 회사코드, 회계연도, 라인번호 / 전기일, 증빙일, 회계월 / 계정코드, 계정명, 계정속성(BS/PL) / 현지통화금액, 차대구분 / 통화코드, 거래통화금액 / 통합거래처명, 원가센터명, 적요, 전표유형 / 역분개여부, 역분개참조번호

거래금액을 순금액으로 표시하는 경우와 대차변별 절대금액으로 표시하는 경우 두가지 형태의 파일을 저장한다. (2-5)

> **제외 항목 (정제 모듈 역할)**  
> - `전기요일` → `02_clean.ipynb`에서 `_weekday`로 생성  
> - `통합순금액(Net)` → `02_clean.ipynb`에서 `_amount`로 생성  
> - 코드 자연어 변환(S→차변, RE→매입송장 등) → `02_clean.ipynb`에서 처리  
> 샘플 데이터는 원본 코드 값을 그대로 유지하여 정제 모듈 연습 환경을 보존한다.

---

## 2. 설계 원칙

### 2-1. 데이터 타입 보존
전표번호(`belnr`), 계정코드(`saknr`), 회사코드(`bukrs`), 거래처코드(`kunnr`/`lifnr`) 등 ID성 필드는 **pandas `dtype=str`** 로 로드한다.
이유: 기본 로드 시 지수표기(e.g. `5.1056e+09`) 또는 앞자리 `0` 소실이 발생함.

```python
STR_COLS = {
    'bseg': ['bukrs', 'belnr', 'gjahr', 'buzei', 'saknr', 'hkont',
             'kunnr', 'lifnr', 'kostl', 'kokrs', 'aufnr'],
    'bkpf': ['bukrs', 'belnr', 'gjahr', 'stblg', 'stjah'],
    ...
}
```

### 2-2. 마스터 테이블 1:1 매핑 보장
- **SKAT**: `spras='E'` 필터 후 `saknr` 기준 최신 레코드 1건
- **CSKT**: `datbi` 기준 최신 레코드 1건 (유효기간이 가장 최근인 원가센터명 사용)
- **KNA1 / LFA1**: 거래처코드별 중복 제거

### 2-3. 통합거래처명 단일 필드
`kunnr`(고객) → KNA1, `lifnr`(벤더) → LFA1 각각 매핑 후 하나의 `통합거래처명` 필드로 통합.
고객명 우선, 없으면 벤더명으로 채운다.

### 2-4. 컬럼명 한글화 및 column_map 연동
한국 회사가 제출하는 원장은 한글 컬럼명인 경우가 많으므로, 최종 샘플 데이터는 한글 컬럼명으로 저장한다. 단, 이 컬럼명들은 `config_template.yaml`의 `column_map`에 반드시 반영하여 정제 모듈이 자동으로 표준 스키마로 변환할 수 있도록 한다.

```yaml
# config_template.yaml의 column_map
column_map:
  "전표번호": "doc_no"
  "전기일": "post_date"
  "증빙일": "doc_date"
  "계정코드": "account_code"
  "계정명": "account_name"
  "현지통화금액": "amount"
  "차대구분": "flag"        # C형: S=차변, H=대변
  "통화코드": "currency"
  "통합거래처명": "counterparty_name"
  "원가센터명": "department"
  "적요": "description"
  "전표유형": "doc_type"
  ...
```

### 2-5. 금액 형태별 4개 파일 생성
`master_gl.csv`를 중간 산출물로 생성한 뒤, 동일 데이터를 금액 형태별로 변환하여 4개 파일로 저장한다. 이를 통해 정제 모듈의 각 금액 형태 처리 로직을 독립적으로 연습할 수 있다.

| 파일 | 금액 형태 | 설명 |
|------|----------|------|
| `GL_type_A.csv` | A형 | 차변 컬럼 / 대변 컬럼 분리 |
| `GL_type_B.csv` | B형 | 단일 금액 컬럼 + 양수(차변)/음수(대변) |
| `GL_type_C.csv` | C형 | 단일 금액 컬럼 + 차대구분 플래그(S/H) |
| `GL_type_D.csv` | D형 | 계정별 잔액 누계형 |

데이터셋 병합을 통해 B형과 C형의 형태로 저장하였으며, A형으로 변환하는 것을 이후 과제로 설정하였다.

---

## 3. 시행착오 및 수정 이력

### 3-1. [문제] 행 수가 원본의 약 1/4로 줄어듦

**현상**
노트북 실행 후 Master GL 행 수가 BSEG 원본 대비 약 22% 수준으로 급감.

**원인 분석**
BSEG 정제 단계에서 `saknr.notna()` 조건을 필터로 사용했는데,
실제 데이터를 확인해보니 **BSEG의 77.6%(257,694행)가 `saknr = NaN`** 이었다.

```
전체: 332,106행
saknr 결측: 257,694행 (77.6%)
hkont 결측:       0행 (0.0%)
```

**SAP 구조상 원인**
SAP BSEG 테이블에서 계정코드 필드의 의미가 `koart`(전기키 유형)에 따라 달라진다.

| koart | 의미 | saknr | hkont |
|-------|------|-------|-------|
| S (원장계정) | 178,846행 | **null** | 항상 있음 |
| M (자재) | 78,848행 | **null** | 항상 있음 |
| K (벤더) | 60,860행 | 있음 (조정계정) | 있음 |
| D (고객) | 13,552행 | 있음 (조정계정) | 있음 |

즉, G/L 라인(`koart=S/M`)의 실제 계정코드는 `saknr`이 아닌 **`hkont`** 에 저장된다.
`saknr`은 고객·벤더 조정계정(Reconciliation Account)에만 채워진다.

**수정 내용**

```python
# 수정 전
bseg = bseg[
    (bseg['dmbtr'] != 0) &
    (bseg['saknr'].notna())   # ← 77.6% 제거됨
].copy()

# 수정 후
# saknr 없는 행은 hkont로 보충 (G/L 라인 계정코드 복원)
bseg['saknr'] = bseg['saknr'].fillna(bseg['hkont'])

bseg = bseg[
    (bseg['dmbtr'] != 0) &
    (bseg['hkont'].notna())   # ← hkont 기준: 전 행 0% 결측
].copy()
```

`hkont`와 `saknr`의 포맷이 동일(`0000500010` 형식)하므로 SKA1/SKAT 조인에 그대로 사용 가능함을 확인.

---

### 3-2. [문제] 행 수가 오히려 늘어남 (Many-to-Many Join)

**현상**
3-1 수정 후 실행 시, 이번엔 반대로 행 수가 BSEG 원본보다 증가.

**원인 분석**
두 테이블에서 조인 키 중복을 확인:

```
BKPF: (bukrs, belnr, gjahr) 중복 13,166행 (8.8%)
SKA1: saknr 중복 130,898행 (89.2%)
```

- **BKPF 중복**: 병렬회계 원장 또는 변경이력으로 동일 전표번호가 여러 행으로 저장됨.
  → BSEG 1행이 BKPF 2+행에 매칭되어 라인 수 팽창.

- **SKA1 중복**: `ktopl`(계정과목표) 47개가 동일 `saknr`을 각각 보유.
  → 기존 코드에서 `drop_duplicates`를 쓰고 있었으나, 정렬 없이 임의 선택 중이었음.

**수정 내용**

```python
# BKPF: 조인 전 최신 레코드 1건으로 중복 제거
bkpf_dedup = (
    bkpf[bkpf_cols]
    .sort_values('recordstamp', ascending=False)
    .drop_duplicates(subset=['bukrs', 'belnr', 'gjahr'], keep='first')
    .drop(columns='recordstamp')
)

# SKA1: recordstamp 기준 정렬 후 중복 제거 (일관성 확보)
ska1_dedup = (
    ska1[['saknr', 'xbilk', 'ktoks', 'recordstamp']]
    .sort_values('recordstamp', ascending=False)
    .drop_duplicates(subset='saknr', keep='first')
    .drop(columns='recordstamp')
)
```

---

## 4. 최종 파이프라인 요약

```
BSEG (원본)
  ↓ [정제] dmbtr=0 제거 / saknr = saknr.fillna(hkont) / hkont notna 필터
BSEG (정제)
  ↓ [LEFT JOIN] BKPF_dedup  on bukrs, belnr, gjahr
  ↓ [LEFT JOIN] SKA1_dedup  on saknr
  ↓ [LEFT JOIN] SKAT_filt   on saknr  (spras='E', 최신 1건)
  ↓ [LEFT JOIN] KNA1_slim   on kunnr
  ↓ [LEFT JOIN] LFA1_slim   on lifnr
  ↓ [파생] 통합거래처명 = kna1.name1 coalesce lfa1.name1
  ↓ [LEFT JOIN] CSKT_filt   on kostl  (datbi 최신 1건)
  ↓ [스키마] 18개 컬럼 선택 & 한글 컬럼명 변환
master_gl.csv (중간 산출물, utf-8-sig)
  ↓ [금액 형태 변환]
  ├── GL_type_A.csv  차변/대변 컬럼 분리형
  ├── GL_type_B.csv  단일금액+부호형
  ├── GL_type_C.csv  단일금액+플래그형 (S/H)
  └── GL_type_D.csv  잔액누계형
```

> **파생변수 및 코드 변환은 이 파이프라인에 포함하지 않는다.**  
> 요일, 순금액, 코드→한글 변환 등은 `02_clean.ipynb`(정제 모듈)에서 처리한다.

---

## 5. 정합성 검증 항목

| 검증 | 기준 | 판정 방법 |
|------|------|-----------|
| 차대균형 | 차변 합계 = 대변 합계 | `abs(차변합 - 대변합) < 0.01` |
| 행 수 유지 | Master GL 행 수 = 필터링된 BSEG 행 수 | 불일치 시 조인 중복 재확인 |
| 계정명 매핑율 | 결측율 < 5% | SKAT 마스터 누락 여부 점검 |
| 통합거래처명 결측율 | 참고용 (거래처 없는 전표 존재 가능) | — |
| 원가센터명 결측율 | 참고용 (원가센터 미지정 전표 존재 가능) | — |
| 금액 형태별 파일 일치 | 4개 파일의 dmbtr 합계 동일 | A/B/C/D형 간 순금액 합계 비교 |

---

## 6. 주요 설계 결정 사항

| 결정 | 이유 |
|------|------|
| `saknr = saknr.fillna(hkont)` | SAP G/L 라인의 계정코드는 hkont에 저장되므로 |
| BKPF dedup 기준: `recordstamp` 최신 | 병렬회계/이력 중 가장 최신 상태를 정본으로 간주 |
| SKA1 dedup 기준: `recordstamp` 최신 | 47개 ktopl 중 임의 선택 대신 일관된 기준 확보 |
| CSKT dedup 기준: `datbi` 최신 | 유효기간 기준 현재 유효한 원가센터명 사용 |
| 저장 인코딩: `utf-8-sig` | BOM 포함으로 엑셀에서 한글 깨짐 없이 열람 가능 |
| 통합거래처명: 고객 우선 | 동일 전표에 kunnr·lifnr이 동시에 존재할 경우 고객 우선 |
| 파생변수 미포함 | 샘플 데이터는 원본 시뮬레이션 목적, 파생변수는 정제 모듈 역할 |
| 코드 자연어 변환 미포함 | 원본 코드(S/H, RE/SA 등) 보존, config 기반 정제 모듈에서 처리 |
| 컬럼명 한글화 + column_map 연동 | 한국 회사 원장 형식 시뮬레이션, 정제 모듈의 column_map으로 표준 스키마 변환 |

---

## 7. 다음 주 작업 계획

- `config_template.yaml`에 이번 샘플 데이터 기준 `column_map` 작성
- `01_convert.ipynb` 작성: 엑셀→CSV 변환 모듈 (병합셀, 헤더 위치, 인코딩 처리)
- `02_clean.ipynb` 작성 시작: 날짜 형식 통일, 금액 형태별(A/B/C/D) 표준화
