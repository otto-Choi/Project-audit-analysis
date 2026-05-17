# order.md — 작업 요청 및 수행 이력

> 토큰 효율을 위한 작업 관리 파일.  
> Claude는 이 파일과 요청된 파일만을 참고하여 작업을 수행한다.

---

## 작업 원칙

- 이 파일(order.md)과 명시적으로 요청된 파일만 참고
- 코드 작성 전 반드시 MD 설계 문서 확정
- 원본 데이터 절대 수정 금지
- 각 작업 완료 시 이 파일에 수행 내역 기록

---

## 현재 상태 (2026-05-17 최신)

### 완료된 작업
| 주차 | 파일 | 내용 |
|------|------|------|
| Week 1 | docs/w1_01_방향설정_및_설계.md | 프로젝트 전체 설계 방향 수립 |
| Week 1 | docs/w1_02_방향설정및설계.md | SAP 테이블 구조 파악, 사용 테이블 7개 확정 |
| Week 2 | docs/w2_SAP_파일_병합.md | 7개 테이블 조인, master_gl 생성 설계 |
| Week 2 | notebooks/w2_merge.ipynb | SAP 7개 테이블 병합 → master_gl 생성 |
| Week 3 | docs/w3_정제모듈_설계.md | 정제 모듈 처리 단계 및 출력 스키마 설계 |
| Week 3 | notebooks/w3_clean.ipynb | 정제 모듈 완성 (STEP 0~6 + 검증 + 저장) |
| Week 4 | docs/w4_탐색모듈_및_Streamlit_UI.md | 탐색 모듈 및 Streamlit UI 설계 기록 |
| Week 4 | notebooks/w4_analyzer.ipynb | 계정 마스터 생성 및 검증 |
| Week 4 | src/analyzer.py | 탐색 함수 모듈 (7개 함수) |
| Week 4 | app.py | Streamlit 드릴다운 탐색 UI |
| Week 4 | data/w4_processed/account_master.csv | Prefix 기반 계정 계층 마스터 (수동 편집 완료) |
| Week 5 | docs/w5_Excel_출력모듈_설계.md | Excel 출력 모듈 설계 및 구현 기록 |
| Week 5 | notebooks/w5_excel_export.ipynb | Excel 출력 모듈 구현 (3시트, Config 셀 방식) |
| Week 6 | docs/w6_디렉터리_구조화.md | 코드·데이터·설정 레이어 분리, 폴더 구조 전면 재편 |
| Week 6 | docs/w6_방향성 재정의.md | Rule Engine 설계 방향 수립 (config 기반 이상탐지) |
| Week 6 | docs/w6_방향성 재정의 추가내용.md | 구조·설계 기준 상세 확정 (notebook/src 분리, naming, config 범위, 라이브러리 기준) |
| Week 6 | config/anomaly_config.yaml | Rule 파라미터·가중치·threshold 정의 |
| Week 6 | src/anomaly.py | Rule 함수 8개, score 계산, 요약 집계 모듈 |
| Week 6 | app.py | 탭 2개 구조로 변경 + Risk View 추가, 전표 조회 통합 테이블 개선 |
| Week 6 | run_app.bat | streamlit run app.py 원클릭 실행 배치 |
| Week 6 | docs/w6_구현_요약.md | Rule Engine 구현 내역 전체 정리 |

### 현재 산출물 현황
| 파일 | 상태 | 내용 |
|------|------|------|
| notebooks/w2_merge.ipynb | 완료 | 7개 SAP 테이블 병합 → master_gl |
| config/config_clean.yaml | 완료 | 정제 모듈 설정 (SAP 샘플 기준) |
| notebooks/w3_clean.ipynb | 완료 | 정제 모듈 (STEP 0~6, config 연동, A/B/C형) |
| data/w3_interim/master_gl_절대금액 표시.csv | 생성완료 | C형 입력 |
| data/w3_interim/master_gl_순금액 표시.csv | 생성완료 | B형 입력 |
| data/w4_processed/master_gl_clean.csv | 생성완료 | 정제 완료 데이터 (원본 18컬럼 + 파생변수 16개) |
| data/w3_interim/master_gl_subtotal.csv | 생성완료 | 분리된 소계행 |
| data/w4_processed/account_master.csv | 생성완료 | Prefix 기반 계층 마스터 (lv1/lv2 한글명 편집 완료) |
| src/analyzer.py | 완료 | 탐색 함수 7개 |
| src/anomaly.py | 완료 | Rule 함수 8개, score 계산, 요약 집계 모듈 |
| config/anomaly_config.yaml | 완료 | Rule 파라미터·가중치·threshold 정의 |
| app.py | 완료 | 탭 2개 구조 (계정 탐색 / Risk View) |
| run_app.bat | 완료 | streamlit run app.py 원클릭 실행 |
| notebooks/w5_excel_export.ipynb | 완료 | Excel 출력 모듈 (원장·월별집계·유형별집계 3시트) |
| data/w5_output/원장_조서_20260429.xlsx | 생성완료 | Config 기반 계정 필터링 + 3시트 Excel 조서 |
| data/w6_anomaly/master_gl_anomaly.csv | 생성완료 | `_flag_*` · `_risk_score` · `_risk_level` · `_risk_flags` 포함 (332,103 라인) |
| data/w6_anomaly/anomaly_summary.csv | 생성완료 | Rule별 탐지 건수·비율·평균 금액 요약 |

### Week 5 구현 상태 (excel_export.ipynb)

| 기능 | 구현 여부 | 비고 |
|------|-----------|------|
| CONFIG 셀 1개 수정으로 계정 교체 | ✅ | TARGET_ACCOUNTS, LV1/LV2_FILTER 지원 |
| Sheet1 원장 — AutoFilter + Freeze | ✅ | 13컬럼, 플래그 하이라이팅 포함 |
| Sheet2 월별집계 — 4컬럼 + SUM 합계 행 | ✅ | M/Q/Y 주기 선택 가능 |
| Sheet3 유형별집계 — doc_type × 플래그 건수 | ✅ | 플래그 비zero 셀 오렌지 하이라이팅 |
| 금액 컬럼 천단위 서식 | ✅ | `#,##0` |
| 헤더/합계행 스타일 (진파랑/연파랑) | ✅ | 헬퍼 함수로 전시트 일관 적용 |
| 열 너비 자동 계산 | ✅ | 콘텐츠 길이 기반 min4~max40 |

### Week 4 구현 상태 (analyzer.py / app.py)

| 기능 | 구현 여부 | 비고 |
|------|-----------|------|
| generate_master() — 계정 마스터 생성 | ✅ | Prefix 기반 lv1/lv2 자동 분류 |
| load_data() — GL + 마스터 조인 | ✅ | post_date datetime 변환 포함 |
| get_account_list() — 계층별 계정 목록 | ✅ | level 1/2/3, parent 필터 |
| get_ledger() — 계정/그룹 원장 조회 | ✅ | 날짜 범위 필터 포함 |
| get_journal_entry() — 전표 분개 조회 | ✅ | 차변/대변 분리, 차대균형 확인 |
| get_related_accounts() — 연관 계정 목록 | ✅ | |
| calculate_balance() — 잔액 계산 | ✅ | 차변/대변/순잔액 |
| Streamlit 사이드바 — 계층 선택 | ✅ | 대/중/세분류 3단계 |
| Streamlit 원장 테이블 — 행 클릭 전표 조회 | ✅ | on_select="rerun" |
| Streamlit 전표 분개 뷰 — 계정 버튼 클릭 이동 | ✅ | session_state 히스토리 |
| @st.cache_data 캐싱 | ✅ | GL 재로드 방지 |
| 기간 필터 (시작일/종료일) | ✅ | |

### Week 6 구현 상태 (anomaly.py / app.py)

| 기능 | 구현 여부 | 비고 |
|---|---|---|
| anomaly_config.yaml — Rule·가중치·threshold 정의 | ✅ | |
| Rule loop — `_flag_*` 자동 생성 | ✅ | 8개 Rule |
| `_risk_score` / `_risk_level` / `_risk_flags` 산출 | ✅ | |
| anomaly_summary.csv — Rule별 건수·비율 집계 | ✅ | |
| Streamlit Risk View 탭 | ✅ | Score 슬라이더, Level, Flag 필터 |
| 전표 조회 통합 테이블 (차변·대변 나란히) | ✅ | 차대 차이 metric 포함 |
| 계정별 이상금액 (Z-score) | ✅ | min_count 조건 포함 |
| 차대불균형 전표 탐지 | ✅ | tolerance 설정 가능 |
| run_app.bat 원클릭 실행 | ✅ | |

### 미구현 항목 (이후 과제)
- 중복 전표 Rule key 재설계 (현재 97% 탐지 → 실무 기준 재정의 필요)
- 차대불균형 Rule에 전표유형 필터 추가 (순금액형 오탐 방지)
- Benford's Law 분석 모듈
- GL_type_A (차변/대변 컬럼 분리형), GL_type_D (잔액 누계형)
- B형 입력 실제 테스트 (`master_gl_순금액 표시.csv` config 교체 후 실행)
- 참조 Excel 생성 모듈 (XLOOKUP/SUMIFS) — 보류 (한국 실무 종속성 높아 범용성 제한)

---

## 작업 이력

### [2026-04-05] 요청 #1 — 정제 모듈 설계 MD 작성
- **요청**: week01 MD 참고하여 master_gl 정제 파이썬 주피터 파일 작성 계획, 우선 정제 모듈 구현을 목표로 MD 작성
- **참고 파일**: week01_01, week01_02, week02, master_gl_절대금액 표시.csv (헤더 확인)
- **수행 내역**: order.md 초기 작성, week03_정제모듈_설계.md 작성
- **상태**: 완료

### [2026-04-05] 요청 #2 — sap.ipynb 피드백 및 order.md 업데이트
- **요청**: sap.ipynb 피드백 제공, order.md 확인 후 다음 할 일 안내 및 업데이트
- **참고 파일**: sap.ipynb, order.md
- **수행 내역**: sap.ipynb 코드 리뷰 (8개 이슈 식별), order.md 업데이트
- **상태**: 완료

### [2026-04-05] 요청 #3 — sap.ipynb 보완 및 order.md 업데이트
- **요청**: order.md의 다음 작업 계획 기반으로 sap.ipynb 수정, order.md 업데이트
- **참고 파일**: sap.ipynb, order.md
- **수행 내역**: sap.ipynb 전면 재작성 (column_map 완성, 벡터화, 플래그, 검증, 저장 추가)
- **상태**: 완료

### [2026-04-05] 요청 #4 — config 연동 + B형/날짜다형성/fisc_month 구현
- **요청**: config.yaml 작성, sap.ipynb config 연동 및 B형·날짜다형성·fisc_month 구현, week03 설계 문서 업데이트
- **참고 파일**: week01_01~02, week02, week03, sap.ipynb, order.md
- **수행 내역**:
  - `config.yaml` 신규 작성
  - `sap.ipynb` 재작성: config 연동, parse_date_flexible, parse_fisc_month, A/B/C형 분기
  - `week03_정제모듈_설계.md` 전면 업데이트
- **상태**: 완료

### [2026-04-26] 요청 #5 — 탐색 모듈 및 Streamlit UI 포트폴리오 MD 작성, order.md 업데이트
- **요청**: Week 4 코딩 완료 후 포트폴리오 저장용 MD 작성 및 order.md 업데이트. 예상보다 난이도가 높아 필사 형식으로 진행, Streamlit 인터랙티브 활용도에 대한 인상 수록 요청
- **참고 파일**: week01_01~02, week02, week03, order.md, an.ipynb, app.py, analyzer.py, account_master.csv
- **수행 내역**:
  - `week04_탐색모듈_및_Streamlit_UI.md` 신규 작성 (an.ipynb / analyzer.py / app.py 전체 기록)
  - `order.md` 업데이트 (Week 4 완료 항목, 미구현 항목, 다음 작업 계획 반영)
- **상태**: 완료

### [2026-04-29] 요청 #6 — Excel 출력 모듈 설계 MD 작성 및 구현
- **요청**: master_gl_clean.csv → Excel 조서 자동 생성 모듈 설계 및 구현
- **참고 파일**: week05_Excel_출력모듈_설계.md, data/master_gl_clean.csv, data/account_master.csv
- **수행 내역**:
  - `week05_Excel_출력모듈_설계.md` 설계 문서 작성
  - `excel_output/excel_export.ipynb` 구현 (Cell 0~10, 3시트 출력)
  - `output/원장_조서_20260429.xlsx` 생성 확인
- **상태**: 완료

### [2026-05-02] 요청 #7 — week05 수행내용 정리 및 order.md 업데이트
- **요청**: week05 MD 수행내용 기준으로 수정, order.md Week 5 반영
- **참고 파일**: week05_Excel_출력모듈_설계.md, excel_output/excel_export.ipynb, output/원장_조서_20260429.xlsx, order.md
- **수행 내역**:
  - `week05_Excel_출력모듈_설계.md` 실제 구현 기준으로 업데이트 (Config LV1/LV2 추가, Sheet3명 수정, 셀 구조 실제화, 완료 기준 체크, Week 6 계획 추가)
  - `order.md` 업데이트 (Week 5 완료 항목, 산출물, 구현 상태, 작업 이력, 다음 작업 계획 반영)
- **상태**: 완료

### [2026-05-14] 요청 #8 — 디렉터리 구조화, 파일 검토, README·order.md 업데이트
- **요청**: 프로젝트 폴더를 data/notebooks/docs/config 레이어로 재구성, 노트북 실행 가능성 검토, README 및 order.md 업데이트
- **참고 파일**: 전체 프로젝트 파일
- **수행 내역**:
  - 폴더 구조 전면 재편 (병합과정·정제과정·탐색과정·excel_output → notebooks/, data/w2_raw~w5_output/, config/)
  - docs 파일명 `week0X_` → `wX_` 통일, `docs/w6_디렉터리_구조화.md` 작성
  - 노트북 경로 버그 수정 3건 (`w2_merge` BASE_DIR, `w5_excel_export` OUTPUT_DIR, `config_clean.yaml` 3개 경로)
  - docs/w4·w5 구 경로 표기 업데이트
  - `docs/w6_방향성 재정의.md` 반영하여 README 향후 과제 재배열 (Rule Engine 최우선, XLOOKUP 보류)
  - `docs/w6_방향성 재정의 추가내용.md` 반영: README 제목·개요·목적 재작성 ("ERP Risk Analytics Pipeline" 방향), order.md 미구현 항목 재정리
  - order.md 파일 경로 전면 업데이트 및 향후 과제 재작성
- **상태**: 완료

### [2026-05-17] 요청 #9 — Week 6 Rule Engine 구현 및 Streamlit Risk View 연동

- **요청**: Streamlit 환경 유지하며 리스크 탐지 계층 추가, w6 문서 기반 구현
- **참고 파일**: docs/w6_방향성 재정의.md, docs/w6_방향성 재정의 추가내용.md, app.py, src/analyzer.py
- **수행 내역**:
  - `config/anomaly_config.yaml` 신규 작성 (Rule 8개, 가중치, threshold)
  - `src/anomaly.py` 신규 구현 (Rule 함수 8개, score 계산, 요약 집계, 파이프라인 진입점)
  - `data/w6_anomaly/` 산출물 생성 (master_gl_anomaly.csv, anomaly_summary.csv)
  - `app.py` 탭 2개 구조로 변경, Risk View 탭 신규 구현 (필터·테이블·전표 상세)
  - 전표 조회 화면 — 통합 분개 테이블(차변·대변 나란히) + 차대 차이 metric 추가
  - Flag 드롭박스 한국어화, 구버전 `_flag_*` UI 노출 제거
  - `run_app.bat` 신규 작성
  - `docs/w6_구현_요약.md` 작성
  - README·order.md 업데이트
- **상태**: 완료

---

## 다음 작업 계획 (Week 7 이후)

1. **중복 전표 Rule 재설계** — `(doc_no, line_no)` key 기준 재검토, 실무 중복 정의 반영
2. **차대불균형 Rule 개선** — 순금액형 전표 오탐 방지를 위한 전표유형 필터 추가
3. **Benford's Law 분석 모듈** — 전표 금액 첫째 자리 빈도 분포 기반 이상탐지
4. **제2 데이터셋 적용** — 파이프라인 범용성 검증
5. **B형 입력 실데이터 검증** — `master_gl_순금액 표시.csv` config 교체 후 실행
