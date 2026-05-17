"""
anomaly.py — Week 6 Rule Engine 모듈
config 기반 이상탐지 Rule 실행, Risk Score 계산, 요약 집계
"""

import os
import pandas as pd
import yaml
from pathlib import Path


# ──────────────────────────────────────────
# 1. Config 로드
# ──────────────────────────────────────────

def load_anomaly_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────
# 2. 개별 Rule 함수
# ──────────────────────────────────────────

def _rule_weekend_posting(df: pd.DataFrame, cfg: dict) -> pd.Series:
    if "_is_weekend" in df.columns:
        return df["_is_weekend"].fillna(False).astype(bool)
    post_date = pd.to_datetime(df["post_date"], errors="coerce")
    return post_date.dt.weekday >= 5


def _rule_month_end_posting(df: pd.DataFrame, cfg: dict) -> pd.Series:
    last_days = cfg.get("last_days", 3)
    post_date = pd.to_datetime(df["post_date"], errors="coerce")
    month_end = post_date + pd.offsets.MonthEnd(0)
    return (month_end - post_date).dt.days < last_days


def _rule_reversal_entry(df: pd.DataFrame, cfg: dict) -> pd.Series:
    if "_is_reversal_flag" in df.columns:
        return df["_is_reversal_flag"].fillna(False).astype(bool)
    return df["reversal_yn"].fillna("").str.upper().isin(["Y", "X", "1"])


def _rule_duplicate_journal(df: pd.DataFrame, cfg: dict) -> pd.Series:
    key_cols = [c for c in cfg.get("key_cols", ["doc_no", "line_no"]) if c in df.columns]
    if not key_cols:
        return pd.Series(False, index=df.index)
    return df.duplicated(subset=key_cols, keep=False)


def _rule_unusual_round_amount(df: pd.DataFrame, cfg: dict) -> pd.Series:
    modulus = cfg.get("modulus", 1_000_000)
    return (df["_amount"].abs() % modulus == 0) & (df["_amount"].abs() > 0)


def _rule_amount_outlier(df: pd.DataFrame, cfg: dict) -> pd.Series:
    z_threshold = cfg.get("z_threshold", 3.0)
    min_count   = cfg.get("min_count", 10)

    amounts = df["_amount"].fillna(0)
    mean = df.groupby("acc_code")["_amount"].transform("mean")
    std  = df.groupby("acc_code")["_amount"].transform("std").fillna(0)
    cnt  = df.groupby("acc_code")["_amount"].transform("count")

    # std=0이거나 건수 미달인 계정은 False
    z_score = ((amounts - mean) / std.replace(0, float("nan"))).abs()
    return (cnt >= min_count) & (z_score > z_threshold)


def _rule_unbalanced_journal(df: pd.DataFrame, cfg: dict) -> pd.Series:
    tolerance = cfg.get("tolerance", 0.01)
    debit  = df.groupby("doc_no")["_debit"].transform("sum").fillna(0)
    credit = df.groupby("doc_no")["_credit"].transform("sum").fillna(0)
    return (debit - credit).abs() > tolerance


def _rule_large_manual_entry(df: pd.DataFrame, cfg: dict) -> pd.Series:
    doc_types = cfg.get("doc_types", [])
    threshold = cfg.get("threshold", 100_000_000)
    type_mask = df["doc_type"].isin(doc_types) if doc_types else pd.Series(True, index=df.index)
    amount_mask = df["_amount"].abs() > threshold
    return type_mask & amount_mask


_RULE_FUNCS = {
    "weekend_posting":      _rule_weekend_posting,
    "month_end_posting":    _rule_month_end_posting,
    "reversal_entry":       _rule_reversal_entry,
    "duplicate_journal":    _rule_duplicate_journal,
    "unusual_round_amount": _rule_unusual_round_amount,
    "large_manual_entry":   _rule_large_manual_entry,
    "unbalanced_journal":   _rule_unbalanced_journal,
    "amount_outlier":       _rule_amount_outlier,
}

RULE_LABELS_KO = {
    "weekend_posting":      "비업무일 전기",
    "month_end_posting":    "월말 집중 전기",
    "reversal_entry":       "역분개 전표",
    "duplicate_journal":    "중복 전표",
    "unusual_round_amount": "비정상 정액 거래",
    "large_manual_entry":   "고액 수동 전기",
    "unbalanced_journal":   "차대불균형 전표",
    "amount_outlier":       "계정별 이상금액",
}


# ──────────────────────────────────────────
# 3. Rule Loop — _flag_* 컬럼 생성
# ──────────────────────────────────────────

def apply_rules(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    config의 anomaly 섹션을 순회하며 _flag_<rule> 컬럼 생성.
    enabled: false 인 rule은 False 컬럼으로 채움.
    """
    result = df.copy()
    anomaly_cfg = config.get("anomaly", {})

    for rule_name, rule_fn in _RULE_FUNCS.items():
        col = f"_flag_{rule_name}"
        rule_cfg = anomaly_cfg.get(rule_name, {})
        if rule_cfg.get("enabled", False):
            result[col] = rule_fn(result, rule_cfg)
        else:
            result[col] = False
        result[col] = result[col].fillna(False).astype(bool)

    return result


# ──────────────────────────────────────────
# 4. Risk Score / Level / Flags 계산
# ──────────────────────────────────────────

def calculate_risk_score(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    _flag_* 컬럼 × 가중치 합산 → _risk_score
    thresholds 기준 → _risk_level (LOW / MEDIUM / HIGH)
    탐지된 rule 목록 → _risk_flags
    """
    result = df.copy()
    weights = config.get("risk_score", {}).get("weights", {})
    thresholds = config.get("risk_score", {}).get("thresholds", {"low": 1, "medium": 3, "high": 5})

    score = pd.Series(0, index=result.index, dtype=float)
    for rule_name, weight in weights.items():
        col = f"_flag_{rule_name}"
        if col in result.columns:
            score += result[col].astype(int) * weight

    result["_risk_score"] = score

    def _level(s):
        if s >= thresholds.get("high", 5):
            return "HIGH"
        if s >= thresholds.get("medium", 3):
            return "MEDIUM"
        if s >= thresholds.get("low", 1):
            return "LOW"
        return "NONE"

    result["_risk_level"] = result["_risk_score"].apply(_level)

    flag_cols = [f"_flag_{r}" for r in weights if f"_flag_{r}" in result.columns]

    def _flags(row):
        triggered = [
            RULE_LABELS_KO.get(col.replace("_flag_", ""), col.replace("_flag_", ""))
            for col in flag_cols if row[col]
        ]
        return ";".join(triggered) if triggered else ""

    result["_risk_flags"] = result[flag_cols].apply(_flags, axis=1)

    return result


# ──────────────────────────────────────────
# 5. Rule별 탐지 건수 요약
# ──────────────────────────────────────────

def summarize_anomalies(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Rule별 탐지 건수, 탐지 비율, 평균 금액 요약 DataFrame 반환.
    """
    weights = config.get("risk_score", {}).get("weights", {})
    rows = []
    for rule_name, weight in weights.items():
        col = f"_flag_{rule_name}"
        if col not in df.columns:
            continue
        flagged = df[df[col]]
        rows.append({
            "rule":        RULE_LABELS_KO.get(rule_name, rule_name),
            "weight":      weight,
            "count":       len(flagged),
            "ratio_pct":   round(len(flagged) / max(len(df), 1) * 100, 2),
            "avg_abs_amount": round(flagged["_amount"].abs().mean(), 0) if not flagged.empty else 0,
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────
# 6. 전체 파이프라인 실행
# ──────────────────────────────────────────

def run_anomaly_pipeline(
    gl_path: str,
    config_path: str,
    output_dir: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    master_gl_clean.csv → Rule 실행 → Score 계산 → CSV 저장.

    Returns:
        (master_gl_anomaly, anomaly_summary)
    """
    config = load_anomaly_config(config_path)

    df = pd.read_csv(gl_path, dtype={"acc_code": str, "doc_no": str}, low_memory=False)
    df["post_date"] = pd.to_datetime(df["post_date"], errors="coerce")

    df = apply_rules(df, config)
    df = calculate_risk_score(df, config)

    summary = summarize_anomalies(df, config)

    os.makedirs(output_dir, exist_ok=True)
    anomaly_path  = os.path.join(output_dir, "master_gl_anomaly.csv")
    summary_path  = os.path.join(output_dir, "anomaly_summary.csv")

    df.to_csv(anomaly_path, index=False, encoding="utf-8-sig")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    return df, summary
