# data/

파이프라인 단계별 데이터 디렉터리입니다.

| 폴더 | 내용 |
|---|---|
| `w2_raw/` | 원본 SAP 테이블 7개 (비공개) |
| `w3_interim/` | 병합 산출물 (master_gl 절대금액·순금액형) |
| `w4_processed/` | 정제 완료 데이터 (master_gl_clean, account_master) |
| `w5_output/` | Excel 조서 출력물 |
| `w6_anomaly/` | Rule Engine 산출물 (master_gl_anomaly, anomaly_summary) |
| `dataset_git/` | GitHub 공개용 데이터 스냅샷 |
