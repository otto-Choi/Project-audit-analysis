# anomaly_config.yaml — 파라미터 레퍼런스

`config/anomaly_config.yaml`의 전체 파라미터 설명.  
새 클라이언트 적용 시 이 파일만 수정하면 코드 변경 없이 Rule 기준을 재설정할 수 있다.

---

## 전체 구조

```yaml
risk_score:
  weights:       # Rule별 점수 가중치
  thresholds:    # risk_level 판정 기준

anomaly:
  <rule_name>:
    enabled: true/false
    <rule_params>: ...
```

---

## risk_score 섹션

### weights

각 Rule이 발동될 때 `_risk_score`에 더해지는 점수.

```yaml
risk_score:
  weights:
    weekend_posting:      1
    month_end_posting:    2
    reversal_entry:       2
    duplicate_journal:    3
    unusual_round_amount: 1
    large_manual_entry:   3
    unbalanced_journal:   5
    amount_outlier:       2
```

가중치 변경 시 `thresholds`도 함께 재검토해야 한다.

### thresholds

`_risk_level` 판정 기준 (score ≥ 값이면 해당 레벨).

```yaml
risk_score:
  thresholds:
    low:    1   # score >= 1 → LOW
    medium: 3   # score >= 3 → MEDIUM
    high:   5   # score >= 5 → HIGH
```

score == 0이면 탐지되지 않은 것으로 분류된다.

---

## anomaly 섹션 — Rule별 파라미터

### weekend_posting

```yaml
anomaly:
  weekend_posting:
    enabled: true
```

| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `enabled` | Rule 활성화 여부 | `true` |

추가 파라미터 없음. 토·일(weekday 5, 6)을 탐지한다.  
월말 마감을 위해 주말 전기가 정상적인 클라이언트는 `enabled: false` 처리.

---

### month_end_posting

```yaml
anomaly:
  month_end_posting:
    enabled: true
    last_days: 3
```

| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `enabled` | Rule 활성화 여부 | `true` |
| `last_days` | 월말 기준 마지막 N일 | `3` |

`last_days: 3`이면 매월 29·30·31일(또는 월 마지막 3일)을 월말로 판정한다.  
마감 일정이 늦은 클라이언트는 `last_days: 5` 등으로 확대.

---

### reversal_entry

```yaml
anomaly:
  reversal_entry:
    enabled: true
```

| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `enabled` | Rule 활성화 여부 | `true` |

SAP `reversal_flag` 필드를 직접 참조한다. 추가 파라미터 없음.

---

### duplicate_journal

```yaml
anomaly:
  duplicate_journal:
    enabled: true
    key_cols:
      - doc_no
      - line_no
```

| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `enabled` | Rule 활성화 여부 | `true` |
| `key_cols` | 중복 판단 기준 컬럼 목록 | `[doc_no, line_no]` |

**현재 알려진 문제:** `[doc_no, line_no]` 조합은 SAP에서 동일 전표의 여러 라인을 모두 중복으로 판정하므로 오탐 비율이 높다. 실무 기준 재설계 필요.

재설계 후보 key: `[amount, acc_code, post_date, vendor_no]` 또는 `[acc_code, amount, doc_type, post_date]`

---

### unusual_round_amount

```yaml
anomaly:
  unusual_round_amount:
    enabled: true
    modulus: 1000000
```

| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `enabled` | Rule 활성화 여부 | `true` |
| `modulus` | 배수 판단 단위 (원) | `1000000` |

`abs(amount) % modulus == 0`인 전표를 탐지한다.  
통화 단위가 다른 클라이언트는 `modulus` 조정.

---

### large_manual_entry

```yaml
anomaly:
  large_manual_entry:
    enabled: true
    doc_types: [SA]
    threshold: 100000000
```

| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `enabled` | Rule 활성화 여부 | `true` |
| `doc_types` | 검사할 전표유형 목록 | `[SA]` |
| `threshold` | 고액 기준 (원, 절대금액) | `100000000` |

`doc_types`는 클라이언트별로 수동 전기 전표유형이 다르므로 반드시 확인 후 조정.  
SA(수동 분개) 외에 JE(저널 엔트리), ZP 등이 사용되는 클라이언트도 있다.

---

### unbalanced_journal

```yaml
anomaly:
  unbalanced_journal:
    enabled: true
    tolerance: 0.01
```

| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `enabled` | Rule 활성화 여부 | `true` |
| `tolerance` | 차대 차이 허용 오차 (원) | `0.01` |

전표 단위로 `sum(debit) - sum(credit)`의 절대값이 `tolerance`를 초과하면 탐지.  
외화 환산 전표는 환율 반올림으로 소액 차이가 발생할 수 있으므로 `tolerance` 조정 필요.

---

### amount_outlier

```yaml
anomaly:
  amount_outlier:
    enabled: true
    z_threshold: 3.0
    min_count: 10
```

| 파라미터 | 설명 | 기본값 |
|---|---|---|
| `enabled` | Rule 활성화 여부 | `true` |
| `z_threshold` | Z-score 임계값 (절대값 기준) | `3.0` |
| `min_count` | 계정 내 최소 거래 건수 | `10` |

계정별 `amount`의 평균·표준편차를 계산하고, `|z| > z_threshold`인 전표를 탐지.  
`min_count` 미만인 계정은 통계적으로 유의하지 않으므로 제외된다.

거래량이 많고 금액 변동이 큰 계정(예: AP, 매출채권)은 `z_threshold`를 높이거나, 계정 범주 필터를 추가하는 것이 권장된다.

---

## 클라이언트별 적용 체크리스트

새 클라이언트 데이터에 적용 전 확인 사항:

- [ ] `large_manual_entry.doc_types` — 해당 클라이언트의 수동 전기 전표유형 확인
- [ ] `large_manual_entry.threshold` — 내부통제 승인 한도 기준으로 조정
- [ ] `month_end_posting.last_days` — 클라이언트 마감 일정 확인
- [ ] `unusual_round_amount.modulus` — 통화 단위 확인
- [ ] `amount_outlier.z_threshold` — 계정별 금액 분포 특성 확인 후 조정
- [ ] `weekend_posting.enabled` — 주말 정규 전기 여부 확인
- [ ] `unbalanced_journal.tolerance` — 외화 거래 비중 확인
- [ ] `risk_score.thresholds` — 가중치 변경 시 함께 재검토
