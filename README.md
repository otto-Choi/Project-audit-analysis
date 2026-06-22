# SAP GL 기반 ERP Risk Analytics Pipeline

> 클라이언트마다 구조가 다른 SAP GL 데이터를 config 하나로 표준화하고,  
> 이상거래를 감사 리스크 관점에서 탐지하는 재사용 가능한 audit analytics 파이프라인.  
> 공인회계사(CPA)가 감사 현장 경험을 바탕으로 설계했다.

**기간** 2026.04 – 2026.05 (6주) · **유형** 개인 프로젝트 (정규 스터디)

---

## 문제 정의

SAP ERP에서 추출한 GL 데이터는 현장마다 구조가 다르다.

- **컬럼명이 다르다** — 동일한 필드가 클라이언트마다 다른 이름으로 수출된다
- **금액 형식이 다르다** — 절대금액형(차변/대변 분리), 순금액형(+/-), 차대분리형 세 포맷이 혼재한다
- **리스크 기준이 다르다** — "고액"의 threshold, "월말 집중" 판단 일수가 engagement마다 다르다
- **7~10개의 분리 테이블** — 전표 헤더(BKPF), 전표 라인(BSEG), 계정 마스터(SKA1/SKAT), 거래처 마스터(KNA1/LFA1), 코스트센터(CSKT)를 직접 병합해야 한다

전통적 접근은 매 현장마다 코드를 새로 짜거나 수작업으로 맞추는 것이다.  
이 프로젝트는 그 반복 작업을 **config로 추상화**했다.

---

## 핵심 설계 결정

### 1. Rule Engine — ML 대신 Rule을 선택한 이유

감사에서 이상거래 탐지 결과는 감사 조서의 근거가 된다. 모델이 "왜 이상한가"를 설명할 수 없으면 조서에 쓸 수 없다. Rule Engine은 탐지 근거가 명확하고, 감사인이 파라미터를 직접 해석하고 조정할 수 있다.

### 2. Config-driven 설계 — 코드와 파라미터를 분리한 이유

`config_clean.yaml`은 컬럼 매핑과 금액 형식을, `anomaly_config.yaml`은 Rule 파라미터와 가중치를 담는다. 새 클라이언트에 적용할 때 코드는 건드리지 않고 config 파일만 교체한다. Rule 추가 시 함수 1개 + config 항목 1개만 작성하면 파이프라인 전체에 반영된다.

### 3. 계정 계층 자동 생성 — 완전한 CoA 없이 적용 가능하게

SAP 계정코드는 앞 1~2자리가 대분류를 나타내는 Prefix 구조를 갖는다. 이를 이용해 완전한 계정과목표(Chart of Accounts) 없이도 대/중/세분류 계층을 자동 생성한다. 계정과목표가 제공되지 않는 현장에도 바로 적용할 수 있다.

> 설계 결정의 상세 근거: [`docs/architecture/system_overview.md`](docs/architecture/system_overview.md)

---

## 시스템 구성

```
Raw SAP 7-table Export
        │
        ▼
    [Merge]  7개 테이블 병합 → 단일 GL master
        │
        ▼
    [Clean]  config_clean.yaml 기반 컬럼 표준화 · 파생변수 생성
        │
     ┌──┴────────────────────────────┐
     ▼                               ▼
[Anomaly Detection]          [Excel Working Paper]
anomaly_config.yaml          계정별 원장 조서 (3시트)
8개 Rule → Risk Score
     │
     ▼
[Streamlit UI]
계정 탐색 / Risk View
```

| 기능 | 설명 |
|---|---|
| 7개 SAP 테이블 병합 | BKPF · BSEG · SKA1 · SKAT · KNA1 · LFA1 · CSKT → 단일 GL master |
| Config 기반 정제 | 컬럼 매핑 · 금액 형식(A/B/C형) · 파생변수를 YAML로 관리. 코드 수정 없이 포맷 전환 |
| Rule Engine 이상탐지 | 8개 감사 Rule 실행 → 전표 라인별 Risk Score · Risk Level(LOW/MEDIUM/HIGH) 산출 |
| 전표 드릴다운 UI | 계정 계층 → 원장 → 전표 분개 → 상대 계정 이동 (탐색 히스토리 포함) |
| Risk View | Score 슬라이더 · Level · Flag 복합 필터로 고위험 거래 우선 탐색 |
| Excel 조서 출력 | CONFIG 셀 1개 수정 → 원장 + 월별집계 + 유형별집계 3시트 자동 생성 |

---

## 이상탐지 Rule

감사 리스크 관점에서 설계한 8개 Rule. 각 Rule은 `anomaly_config.yaml`의 파라미터로 독립적으로 제어된다.

| Rule | 타겟 감사 리스크 | 탐지 기준 |
|---|---|---|
| Weekend Posting | 내부통제 우회 의심 전기 | 토·일 전기일 |
| Month-end Concentration | 기간 귀속 조작 가능성 | 월말 마지막 N일 집중 전기 |
| Reversal Entry | 원상복구 패턴 (전기 취소) | Reversal flag 전표 |
| Duplicate Journal | 이중 처리 의심 | 동일 전표번호·라인 중복 |
| Unusual Round Amount | 가공 거래 의심 | 설정 단위(기본 100만 원)의 배수 금액 |
| Large Manual Entry | 수동 전기 고위험 거래 | 특정 전표유형 + threshold 초과 |
| Debit-Credit Imbalance | 전표 무결성 오류 | 전표 내 차대 불일치 |
| Account-level Outlier | 계정별 비정상 금액 | 계정 내 Z-score 임계값 초과 |

> Rule별 가중치·threshold 설정: [`config/anomaly_config.yaml`](config/anomaly_config.yaml)  
> Rule 선정 rationale 및 감사 기준 매핑: [`docs/rule_engine/rule_design_rationale.md`](docs/rule_engine/rule_design_rationale.md)

---

## 주요 결과 (샘플 데이터 기준)

- 332,103개 GL line items 처리 (SAP 샘플 1 engagement 기준)
- 8개 Rule 전 단계 정상 실행 확인
- 차대불균형 전표 21,374건, 계정별 이상금액 2,068건(20개 계정) 탐지
- Excel 조서: CONFIG 셀 1개 수정으로 원장·집계 3시트 자동 출력

---

## 한계

- **단일 데이터셋 검증** — 모든 설정은 1개 SAP 샘플 기준. 다른 클라이언트 적용 시 config 재설정 범위 미검증
- **Rule threshold 미튜닝** — 중복 전표·차대불균형 Rule은 오탐 가능성 있음. Engagement별 calibration 필요
- **B형(순금액형) 미검증** — 입력 경로 설계 완료, 실 데이터 테스트 없음

> 한계 상세 및 재설계 방향: [`docs/validation/known_issues.md`](docs/validation/known_issues.md)

---

## 기술 스택

Python 3.11 · pandas · numpy · scipy · Streamlit · PyYAML · openpyxl

---

## 실행 방법

```bash
pip install streamlit pandas numpy pyyaml openpyxl scipy
streamlit run app.py
# 또는
run_app.bat
```

데이터 재생성이 필요한 경우: `notebooks/w2_merge.ipynb` → `w3_clean.ipynb` → `src/anomaly.py`의 `run_anomaly_pipeline()` 순으로 실행.

---

## 문서

| 문서 | 내용 |
|---|---|
| [`docs/architecture/system_overview.md`](docs/architecture/system_overview.md) | 전체 설계 결정 및 레이어 구조 |
| [`docs/rule_engine/rule_design_rationale.md`](docs/rule_engine/rule_design_rationale.md) | Rule 선정 근거 및 감사 리스크 매핑 |
| [`docs/rule_engine/config_reference.md`](docs/rule_engine/config_reference.md) | anomaly_config.yaml 파라미터 레퍼런스 |
| [`docs/validation/known_issues.md`](docs/validation/known_issues.md) | 알려진 오탐 이슈 및 재설계 방향 |
| [`docs/audit_logic/gl_structure_primer.md`](docs/audit_logic/gl_structure_primer.md) | SAP GL 구조 입문 (비SAP 독자용) |
