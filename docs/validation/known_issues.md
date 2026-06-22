# Known Issues — 알려진 오탐 이슈 및 재설계 방향

현재 파이프라인에서 확인된 이슈와 재설계 방향을 기록한 문서.  
단순 버그가 아닌, 실무 적용 시 calibration이 필요한 설계 한계를 포함한다.

---

## Issue 1 — 중복 전표 Rule의 97% 탐지율

**현상:**  
`duplicate_journal` Rule이 샘플 데이터에서 97% 탐지율을 기록했다.

**원인 분석:**  
현재 중복 key가 `(doc_no, line_no)`로 설정되어 있다. SAP BSEG 테이블에서 하나의 전표(doc_no)는 여러 라인(line_no 1, 2, 3...)으로 구성된다. 전표 라인별로 중복을 판정하면 동일 전표의 모든 라인이 "중복"으로 탐지된다.

**실무 기준 정의:**  
실무에서 중복 전표는 "다른 전표번호로 동일 거래가 두 번 처리된 것"이다. 예: 동일 거래처에 동일 금액의 비용이 이틀 간격으로 두 번 전기된 경우.

**재설계 방향:**

```yaml
# 현재 (오작동)
duplicate_journal:
  key_cols: [doc_no, line_no]

# 후보 1 — 동일 계정·금액·거래처·날짜
duplicate_journal:
  key_cols: [acc_code, amount, post_date, vendor_no]

# 후보 2 — 동일 계정·금액·전표유형 (날짜 윈도우 N일 이내)
# → config에 date_window_days 파라미터 추가 필요
```

`vendor_no`가 없는 전표(내부 분개 등)는 별도 처리 필요.

**현재 임시 조치:**  
`enabled: false`로 비활성화하거나, 결과 해석 시 이 Rule의 탐지 건수는 제외하고 분석.

---

## Issue 2 — 차대불균형 Rule의 순금액형 오탐

**현상:**  
`unbalanced_journal` Rule이 정상 전표를 대량으로 탐지하는 경우가 발생할 수 있다.

**원인 분석:**  
SAP GL 수출 포맷에는 세 가지 유형이 있다:
- **A형 (절대금액형):** `debit` 컬럼과 `credit` 컬럼에 각각 양수 금액 기재
- **B형 (순금액형):** 단일 `amount` 컬럼에 +/- 부호로 기재 (debit/credit 분리 없음)
- **C형 (차대분리형):** A형과 유사하나 컬럼명이 다름

현재 `unbalanced_journal` Rule은 `debit - credit`의 전표 단위 합계로 판정한다. B형 전표는 `debit`/`credit` 컬럼이 원본에 없어 정제 과정에서 0으로 채워지므로, `sum(debit) - sum(credit) = 0`이 아닌 경우가 발생한다.

**재설계 방향:**

```yaml
# config에 전표유형별 제외 조건 추가
unbalanced_journal:
  enabled: true
  tolerance: 0.01
  exclude_doc_types: [B_TYPE_CODES]  # B형 전표유형 목록 추가
```

또는 정제 단계에서 B형 전표의 `debit`/`credit`을 `amount` 부호 기반으로 역산하는 로직 추가.

---

## Issue 3 — Account-level Outlier의 AP 계정 대량 탐지

**현상:**  
샘플 데이터에서 Accounts Payable 계정에서 1,323건이 탐지됐다.

**원인 분석:**  
AP 계정은 거래처별로 금액 변동이 크다. 매입 규모가 다른 여러 거래처의 거래가 하나의 계정에 섞여 있어 Z-score가 높게 나오는 거래가 많다.

**재설계 방향:**

- **옵션 1 — z_threshold 상향:** AP 등 금액 변동 큰 계정에 대해 `z_threshold: 4.0~5.0` 적용
- **옵션 2 — 계정 범주별 threshold 설정:** 계정 lv1별로 다른 threshold를 적용하는 config 구조 설계
- **옵션 3 — 거래처별 Z-score:** AP는 계정 전체가 아닌 거래처(`vendor_no`) 단위로 Z-score 계산

현재는 `z_threshold: 3.0`이 전 계정 동일 기준으로 적용된다.

---

## Issue 4 — B형(순금액형) 입력 경로 미검증

**현상:**  
`config_clean.yaml`에 B형 처리 분기(`gl_format: B`)가 설계되어 있고, 정제 노트북에도 분기 코드가 존재하나, B형 실 데이터로 end-to-end 실행 검증이 되지 않았다.

**현황:**  
- `data/w3_interim/master_gl_순금액 표시.csv` 파일이 B형 중간 결과로 존재
- `config_clean.yaml`에서 `gl_format: B`로 교체 후 `w3_clean.ipynb` 실행 시 B형 경로로 동작해야 하나 미확인

**검증 방법:**
1. `config_clean.yaml`의 `gl_format`을 `B`로 변경
2. `notebooks/w3_clean.ipynb` 재실행
3. 출력 데이터의 `amount` 컬럼 부호 분포 및 `debit`/`credit` 파생 결과 확인
4. `anomaly.py`의 `unbalanced_journal` Rule이 B형 전표에서 어떻게 작동하는지 확인

---

## Issue 5 — HIGH Risk 비율 (14.8%)

**현상:**  
샘플 데이터에서 332,103건 중 49,163건(14.8%)이 HIGH로 분류됐다.

**원인 분석:**  
`unbalanced_journal` Rule의 가중치가 5이고, 이 Rule만 발동해도 HIGH가 된다. 21,374건의 차대불균형 탐지가 대부분 HIGH를 유발했다. 또한 Issue 1(중복 전표 97%)의 가중치 3이 많은 전표에 중복 적용됐다.

**실무 의미:**  
HIGH 14.8%는 감사인이 실제로 검토하기 어려운 양이다. 감사 analytics 도구에서 HIGH는 전수 검토 또는 표본 우선 추출 대상이므로, 현실적인 HIGH 비율은 1~5% 수준이 적절하다.

**재설계 방향:**
- Issue 1, 2 해결 후 HIGH 비율 재측정
- `high` threshold를 `5`에서 `7~8`로 상향
- `unbalanced_journal` 가중치를 일시적으로 낮추거나 별도 검토 탭으로 분리
