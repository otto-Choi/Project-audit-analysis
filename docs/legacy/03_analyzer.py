"""
analyzer.py — Week 4 데이터 처리 모듈
UI와 분리된 계정 계층 탐색 및 집계 함수군
"""

import pandas as pd
from typing import Optional


# ──────────────────────────────────────────
# 1. 계정 마스터 생성
# ──────────────────────────────────────────

def generate_master(df: pd.DataFrame, output_path: str) -> pd.DataFrame:
    """
    master_gl_clean 데이터에서 Prefix 기반 계정 마스터 생성 후 CSV 저장.

    계층 분류 규칙:
      - acc_code_clean = acc_code.lstrip('0') (빈 문자열이면 '0')
      - lv1_code = acc_code_clean[0]
      - lv2_code = acc_code_clean[:3]  (1~2자리 코드면 전체 코드)
      - lv1/lv2_name = "(임시){code}" — 사용자가 CSV 열어 수동 편집
    """
    master = (
        df[["acc_code", "acc_name"]]
        .drop_duplicates(subset=["acc_code"])
        .copy()
    )

    master["acc_code_clean"] = master["acc_code"].astype(str).str.lstrip("0")
    master["acc_code_clean"] = master["acc_code_clean"].replace("", "0")

    master["lv1_code"] = master["acc_code_clean"].str[0]
    master["lv2_code"] = master["acc_code_clean"].str[:3]

    master["lv1_name"] = "(임시)" + master["lv1_code"]
    master["lv2_name"] = "(임시)" + master["lv2_code"]

    col_order = ["acc_code", "acc_code_clean", "acc_name",
                 "lv1_code", "lv1_name", "lv2_code", "lv2_name"]
    master = master[col_order].sort_values("acc_code_clean").reset_index(drop=True)

    master.to_csv(output_path, index=False, encoding="utf-8-sig")
    return master


# ──────────────────────────────────────────
# 2. 데이터 로드 (GL + 마스터 조인)
# ──────────────────────────────────────────

def load_data(gl_path: str, master_path: str) -> pd.DataFrame:
    """
    master_gl_clean + account_master를 acc_code 기준 left join 반환.
    post_date는 datetime 변환.
    """
    gl = pd.read_csv(gl_path, dtype={"acc_code": str, "doc_no": str}, low_memory=False)
    master = pd.read_csv(master_path, dtype=str)

    gl["post_date"] = pd.to_datetime(gl["post_date"], errors="coerce")

    merged = gl.merge(
        master[["acc_code", "acc_code_clean", "lv1_code", "lv1_name", "lv2_code", "lv2_name"]],
        on="acc_code",
        how="left"
    )
    return merged


# ──────────────────────────────────────────
# 3. 계층별 계정 목록
# ──────────────────────────────────────────

def get_account_list(
    master: pd.DataFrame,
    level: int,
    parent: Optional[str] = None
) -> list[dict]:
    """
    계층별 계정 목록 반환.

    level=1: [{code, name}, ...]  (대분류)
    level=2: [{code, name}, ...]  (중분류, parent=lv1_code 필터)
    level=3: [{code, name}, ...]  (소분류, parent=lv2_code 필터)
    """
    if level == 1:
        rows = master[["lv1_code", "lv1_name"]].drop_duplicates().sort_values("lv1_code")
        return [{"code": r.lv1_code, "name": r.lv1_name} for r in rows.itertuples()]

    if level == 2:
        df = master if parent is None else master[master["lv1_code"] == parent]
        rows = df[["lv2_code", "lv2_name"]].drop_duplicates().sort_values("lv2_code")
        return [{"code": r.lv2_code, "name": r.lv2_name} for r in rows.itertuples()]

    # level == 3
    df = master if parent is None else master[master["lv2_code"] == parent]
    rows = df[["acc_code", "acc_name"]].drop_duplicates().sort_values("acc_code")
    return [{"code": r.acc_code, "name": r.acc_name} for r in rows.itertuples()]


# ──────────────────────────────────────────
# 4. 원장 조회
# ──────────────────────────────────────────

def get_ledger(
    df: pd.DataFrame,
    acc_code: Optional[str] = None,
    level: Optional[int] = None,
    level_code: Optional[str] = None,
    date_range: Optional[tuple] = None
) -> pd.DataFrame:
    """
    계정 또는 그룹의 원장 조회.

    - acc_code 지정 시: 해당 계정 단독 조회 (Level 3)
    - level + level_code 지정 시: 그룹 롤업 조회 (Level 1/2)
    - date_range: (start_date, end_date) — None이면 전체 기간
    """
    result = df.copy()

    if acc_code is not None:
        result = result[result["acc_code"] == acc_code]
    elif level is not None and level_code is not None:
        col = "lv1_code" if level == 1 else "lv2_code"
        result = result[result[col] == level_code]

    if date_range is not None:
        start, end = date_range
        if start is not None:
            result = result[result["post_date"] >= pd.Timestamp(start)]
        if end is not None:
            result = result[result["post_date"] <= pd.Timestamp(end)]

    display_cols = [c for c in [
        "post_date", "doc_no", "acc_code", "acc_name",
        "description", "doc_type", "_debit", "_credit", "_amount",
        "lv1_name", "lv2_name"
    ] if c in result.columns]

    return result[display_cols].sort_values("post_date").reset_index(drop=True)


# ──────────────────────────────────────────
# 5. 전표 분개 조회
# ──────────────────────────────────────────

def get_journal_entry(df: pd.DataFrame, doc_no: str) -> dict:
    """
    전표번호 기준 분개를 차변/대변으로 분리하여 반환.

    Returns:
        {
            'doc_info': {'doc_no', 'post_date', 'doc_type'},
            'debit':  [{'acc_code', 'acc_name', 'amount', 'line_no'}, ...],
            'credit': [{'acc_code', 'acc_name', 'amount', 'line_no'}, ...],
            'balanced': bool
        }
    """
    lines = df[df["doc_no"] == doc_no].copy()

    if lines.empty:
        return {"doc_info": {}, "debit": [], "credit": [], "balanced": False}

    first = lines.iloc[0]
    doc_info = {
        "doc_no": doc_no,
        "post_date": str(first.get("post_date", ""))[:10],
        "doc_type": first.get("doc_type", ""),
    }

    def _rows(mask):
        return [
            {
                "acc_code": str(r.get("acc_code", "")),
                "acc_name": str(r.get("acc_name", "")),
                "amount": float(r.get("_debit" if is_debit else "_credit", 0) or 0),
                "line_no": str(r.get("line_no", "")),
            }
            for _, r in lines[mask].iterrows()
            for is_debit in [mask.name == "debit_mask"]  # resolved below
        ]

    debit_mask = lines["_debit"].fillna(0) > 0
    credit_mask = lines["_credit"].fillna(0) > 0

    debit_lines = [
        {
            "acc_code": str(r["acc_code"]),
            "acc_name": str(r["acc_name"]),
            "amount": float(r["_debit"] or 0),
            "line_no": str(r.get("line_no", "")),
        }
        for _, r in lines[debit_mask].iterrows()
    ]
    credit_lines = [
        {
            "acc_code": str(r["acc_code"]),
            "acc_name": str(r["acc_name"]),
            "amount": float(r["_credit"] or 0),
            "line_no": str(r.get("line_no", "")),
        }
        for _, r in lines[credit_mask].iterrows()
    ]

    total_debit = sum(item["amount"] for item in debit_lines)
    total_credit = sum(item["amount"] for item in credit_lines)
    balanced = abs(total_debit - total_credit) < 0.01

    return {
        "doc_info": doc_info,
        "debit": debit_lines,
        "credit": credit_lines,
        "balanced": balanced,
    }


# ──────────────────────────────────────────
# 6. 전표 관련 계정 목록
# ──────────────────────────────────────────

def get_related_accounts(df: pd.DataFrame, doc_no: str) -> list[str]:
    """특정 전표에 포함된 모든 acc_code unique 목록 반환."""
    return df[df["doc_no"] == doc_no]["acc_code"].dropna().unique().tolist()


# ──────────────────────────────────────────
# 7. 잔액 계산
# ──────────────────────────────────────────

def calculate_balance(
    df: pd.DataFrame,
    acc_code: Optional[str] = None,
    level: Optional[int] = None,
    level_code: Optional[str] = None,
) -> dict:
    """
    계정 또는 그룹의 차변 합계 / 대변 합계 / 순잔액 반환.

    Returns:
        {'debit': float, 'credit': float, 'net': float}
    """
    subset = df.copy()

    if acc_code is not None:
        subset = subset[subset["acc_code"] == acc_code]
    elif level is not None and level_code is not None:
        col = "lv1_code" if level == 1 else "lv2_code"
        subset = subset[subset[col] == level_code]

    debit = float(subset["_debit"].fillna(0).sum())
    credit = float(subset["_credit"].fillna(0).sum())
    return {"debit": debit, "credit": credit, "net": debit - credit}
