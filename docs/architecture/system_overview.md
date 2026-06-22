# System Overview — 설계 결정 기록

SAP GL Risk Analytics Pipeline의 전체 아키텍처와 핵심 설계 결정을 기록한 문서.  
"무엇을 만들었는가"보다 "왜 이렇게 설계했는가"를 중심으로 작성했다.

---

## 레이어 구조

```
┌─────────────────────────────────────────────────────────┐
│  config/                 클라이언트 설정 레이어           │
│  ├── config_clean.yaml   컬럼 매핑 · 금액 형식 · 파생변수 │
│  └── anomaly_config.yaml Rule · 가중치 · threshold       │
└─────────────────────────────────────────────────────────┘
          ↓ 읽기만 함 (코드는 config를 참조할 뿐)
┌─────────────────────────────────────────────────────────┐
│  notebooks/              탐색 · 개발 레이어              │
│  ├── w2_merge.ipynb      7개 테이블 병합 탐색             │
│  ├── w3_clean.ipynb      정제 모듈 개발 및 검증           │
│  ├── w4_analyzer.ipynb   계정 마스터 생성 및 검증         │
│  └── w5_excel_export.ipynb  Excel 출력 모듈              │
└─────────────────────────────────────────────────────────┘
          ↓ 검증된 로직은 src/ 로 이전
┌─────────────────────────────────────────────────────────┐
│  src/                    생산 코드 레이어                 │
│  ├── analyzer.py         계정 탐색 · 원장 조회 함수 (7개) │
│  └── anomaly.py          Rule Engine · Risk Score 산출   │
└─────────────────────────────────────────────────────────┘
          ↓ 사용
┌─────────────────────────────────────────────────────────┐
│  app.py                  UI 레이어 (Streamlit)           │
│  ├── Tab 1: 계정 탐색    계층 선택 → 원장 → 전표 드릴다운 │
│  └── Tab 2: Risk View    Score/Level/Flag 필터 → 탐색    │
└─────────────────────────────────────────────────────────┘
```

**핵심 원칙**: config 레이어만 교체하면 다른 클라이언트 데이터에 적용 가능하다. `src/`와 `app.py`는 수정하지 않는다.

---

## 설계 결정 1 — 왜 ML이 아닌 Rule Engine인가

**배경:**  
이상거래 탐지에서 ML(비지도 학습, Isolation Forest, Autoencoder 등)은 더 많은 패턴을 잡을 수 있다. 그러나 감사 맥락에서는 탐지 결과를 감사 조서에 기재해야 한다.

**결정:**  
Rule Engine 채택.

**근거:**

| 기준 | Rule Engine | ML |
|---|---|---|
| 탐지 근거 설명 | 명확 (Rule 조건 직접 확인 가능) | 어려움 (모델 내부 로직) |
| 감사인 파라미터 조정 | 가능 (config 수정) | 어려움 (재학습 필요) |
| 감사 조서 활용 | 가능 | 근거 불명확으로 사용 제한 |
| 클라이언트별 기준 적용 | config로 즉시 대응 | 데이터별 재학습 필요 |

감사에서 "왜 이 전표가 이상한가"는 Rule로 직접 설명된다. Threshold와 가중치를 감사인이 직접 조정할 수 있다는 점도 현장 적용에 결정적이다.

---

## 설계 결정 2 — 왜 YAML config인가

**대안:**  
Python 딕셔너리 하드코딩, JSON, 환경변수, 데이터베이스

**결정:**  
YAML 채택.

**근거:**
- **주석 지원** — JSON은 주석을 허용하지 않는다. config 파일에 "왜 이 threshold인가"를 바로 적을 수 있다
- **비개발자 편집 가능** — 감사 현장에서 임시로 파라미터를 조정할 때, 개발자 없이도 텍스트 에디터로 수정할 수 있다
- **계층 구조 표현** — Rule → 가중치 → 파라미터의 계층 구조가 Python dict보다 읽기 쉽다

**실제 구조:**
```yaml
anomaly:
  large_manual_entry:
    enabled: true
    doc_types: [SA]       # SA = 수동 전기 전표유형
    threshold: 100000000  # 1억 원 기준 (클라이언트별 조정)
```

---

## 설계 결정 3 — 계정 계층을 Prefix로 자동 생성하는 이유

**배경:**  
SAP에서 완전한 계정과목표(Chart of Accounts, CoA)가 제공되는 경우도 있지만, 일부 현장에서는 별도 파일이 없거나 갱신이 오래된 상태로 제공된다.

**SAP 계정코드 Prefix 구조:**
- `1xxxxx` → 자산
- `2xxxxx` → 부채
- `3xxxxx` → 자본
- `4xxxxx` → 수익
- `5xxxxx`, `6xxxxx` → 비용

앞 1~2자리로 대/중분류를 자동 생성하고, lv1/lv2 한글 계정명은 `account_master.csv`를 수동으로 보완한다.

**한계:**  
이 방식은 SAP 표준 계정 넘버링을 사용하는 현장에 유효하다. 클라이언트 자체 numbering을 쓰는 경우 수동 매핑이 필요하다.

---

## 설계 결정 4 — notebooks/와 src/ 분리

**이유:**  
탐색과 개발 단계에서 노트북은 빠른 실험이 목적이다. 검증된 함수를 `src/`로 이전하면 `app.py`는 안정적인 인터페이스만 참조할 수 있다.

- `notebooks/`: 데이터 탐색, 함수 개발, 출력 검증
- `src/analyzer.py`: 계정 탐색·원장 조회 7개 함수 (app.py가 참조)
- `src/anomaly.py`: Rule Engine, Score 산출, 파이프라인 진입점

`app.py`와 `src/`만 보면 실제 파이프라인 로직 전체가 파악된다.

---

## 데이터 스키마

### master_gl_clean.csv (정제 완료 데이터)

원본 SAP 필드 18개 + 파생변수 16개 = 34컬럼, 332,103행

**주요 원본 필드:**

| 컬럼 | 설명 |
|---|---|
| `doc_no` | 전표번호 (BKPF.BELNR) |
| `line_no` | 전표 라인 번호 (BSEG.BUZEI) |
| `acc_code` | 계정코드 (BSEG.HKONT) |
| `post_date` | 전기일 (BKPF.BUDAT) |
| `doc_type` | 전표유형 (BKPF.BLART) |
| `amount` | 정규화된 금액 (부호 포함) |
| `debit` / `credit` | 차변/대변 금액 (A/C형 원본 필드) |
| `reversal_flag` | 역분개 전표 여부 |
| `vendor_no` / `customer_no` | 거래처 코드 |

**주요 파생 필드:**

| 컬럼 | 생성 방식 |
|---|---|
| `fisc_month` | 회계연월 (회계연도 기준, YYYYMM) |
| `weekday` | 전기 요일 (0=월, 6=일) |
| `is_weekend` | 토·일 여부 |
| `sign` | 거래 방향 (+1 / -1) |
| `lv1_code`, `lv2_code` | 계정 대/중분류 코드 (Prefix 기반) |
| `lv1_name`, `lv2_name` | 계정 대/중분류 한글명 |

### master_gl_anomaly.csv (이상탐지 결과)

`master_gl_clean.csv`에 아래 컬럼 추가:

| 컬럼 | 설명 |
|---|---|
| `_flag_weekend_posting` | Rule 1 탐지 여부 (bool) |
| `_flag_month_end_posting` | Rule 2 탐지 여부 |
| ... (Rule별 `_flag_*` 8개) | |
| `_risk_score` | Rule 가중치 합산 점수 |
| `_risk_level` | LOW / MEDIUM / HIGH |
| `_risk_flags` | 탐지된 Rule 목록 (쉼표 구분 문자열) |
