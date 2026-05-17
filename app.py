"""
app.py — Week 6 GL 드릴다운 탐색 + Risk View
실행: streamlit run app.py
"""

import os
import sys
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))
from src.analyzer import (
    load_data,
    get_account_list,
    get_ledger,
    get_journal_entry,
    calculate_balance,
)
from src.anomaly import run_anomaly_pipeline, load_anomaly_config, RULE_LABELS_KO

# ──────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────
_BASE       = os.path.dirname(__file__)
GL_PATH     = os.path.join(_BASE, "data", "w4_processed", "master_gl_clean.csv")
MASTER_PATH = os.path.join(_BASE, "data", "w4_processed", "account_master.csv")
ANOMALY_PATH   = os.path.join(_BASE, "data", "w6_anomaly", "master_gl_anomaly.csv")
SUMMARY_PATH   = os.path.join(_BASE, "data", "w6_anomaly", "anomaly_summary.csv")
CONFIG_PATH    = os.path.join(_BASE, "config", "anomaly_config.yaml")


# ──────────────────────────────────────────
# 데이터 로드 (캐싱)
# ──────────────────────────────────────────
@st.cache_data
def load_all():
    df = load_data(GL_PATH, MASTER_PATH)
    master = pd.read_csv(MASTER_PATH, dtype=str)
    return df, master


@st.cache_data
def load_anomaly():
    if not os.path.exists(ANOMALY_PATH):
        return None, None
    anomaly_df = pd.read_csv(ANOMALY_PATH, dtype={"acc_code": str, "doc_no": str}, low_memory=False)
    anomaly_df["post_date"] = pd.to_datetime(anomaly_df["post_date"], errors="coerce")
    summary_df = pd.read_csv(SUMMARY_PATH) if os.path.exists(SUMMARY_PATH) else None
    return anomaly_df, summary_df


# ──────────────────────────────────────────
# session_state 초기화
# ──────────────────────────────────────────
def init_state():
    defaults = {
        "target_acc":   None,   # 현재 조회 계정 코드
        "target_level": None,   # 1 / 2 / 3
        "target_code":  None,   # 레벨 코드 (lv1_code or lv2_code or acc_code)
        "selected_doc": None,   # 선택된 전표번호
        "history":      [],     # 탐색 히스토리 [(label, level, code), ...]
        "date_range":   (None, None),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ──────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────
def account_label(code: str, name: str) -> str:
    return f"{code} — {name}"


def push_history(label: str, level: int, code: str):
    hist = st.session_state.history
    hist.append({"label": label, "level": level, "code": code})
    st.session_state.history = hist[-10:]  # 최대 10개


# ──────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────
def render_sidebar(master: pd.DataFrame):
    with st.sidebar:
        st.header("계정 탐색")

        # 계층 선택
        level_choice = st.radio("조회 단위", ["대분류", "중분류", "세분류"])

        lv1_items = get_account_list(master, level=1)
        lv1_labels = [account_label(x["code"], x["name"]) for x in lv1_items]
        lv1_map = {account_label(x["code"], x["name"]): x for x in lv1_items}

        selected_level = None
        selected_code = None
        selected_label = None

        if level_choice == "대분류":
            if lv1_labels:
                sel = st.selectbox("대분류", lv1_labels)
                item = lv1_map[sel]
                selected_level, selected_code, selected_label = 1, item["code"], sel
            else:
                st.warning("대분류 없음 — account_master.csv 확인")

        elif level_choice == "중분류":
            if lv1_labels:
                lv1_sel = st.selectbox("대분류", lv1_labels)
                lv1_code = lv1_map[lv1_sel]["code"]
                lv2_items = get_account_list(master, level=2, parent=lv1_code)
                lv2_labels = [account_label(x["code"], x["name"]) for x in lv2_items]
                lv2_map = {account_label(x["code"], x["name"]): x for x in lv2_items}
                if lv2_labels:
                    sel = st.selectbox("중분류", lv2_labels)
                    item = lv2_map[sel]
                    selected_level, selected_code, selected_label = 2, item["code"], sel

        else:  # 세분류
            if lv1_labels:
                lv1_sel = st.selectbox("대분류", lv1_labels)
                lv1_code = lv1_map[lv1_sel]["code"]
                lv2_items = get_account_list(master, level=2, parent=lv1_code)
                lv2_labels = [account_label(x["code"], x["name"]) for x in lv2_items]
                lv2_map = {account_label(x["code"], x["name"]): x for x in lv2_items}
                if lv2_labels:
                    lv2_sel = st.selectbox("중분류", lv2_labels)
                    lv2_code = lv2_map[lv2_sel]["code"]
                    lv3_items = get_account_list(master, level=3, parent=lv2_code)
                    lv3_labels = [account_label(x["code"], x["name"]) for x in lv3_items]
                    lv3_map = {account_label(x["code"], x["name"]): x for x in lv3_items}
                    if lv3_labels:
                        sel = st.selectbox("계정", lv3_labels)
                        item = lv3_map[sel]
                        selected_level, selected_code, selected_label = 3, item["code"], sel

        # 기간 선택
        st.subheader("조회 기간")
        start_date = st.date_input("시작일", value=None)
        end_date   = st.date_input("종료일", value=None)

        # 조회 버튼
        if st.button("조회", type="primary") and selected_code:
            st.session_state.target_level = selected_level
            st.session_state.target_code  = selected_code
            st.session_state.target_acc   = selected_label
            st.session_state.date_range   = (start_date, end_date)
            st.session_state.selected_doc = None
            st.session_state.history      = []
            st.rerun()

        # 뒤로 가기
        if st.session_state.history:
            prev = st.session_state.history[-1]
            if st.button(f"← 이전: {prev['label']}"):
                st.session_state.history.pop()
                st.session_state.target_level = prev["level"]
                st.session_state.target_code  = prev["code"]
                st.session_state.target_acc   = prev["label"]
                st.session_state.selected_doc = None
                st.rerun()

        st.divider()
        st.caption("탐색 히스토리")
        for h in reversed(st.session_state.history):
            st.caption(f"· {h['label']}")


# ──────────────────────────────────────────
# 분개 뷰
# ──────────────────────────────────────────
def render_journal_view(df: pd.DataFrame):
    doc_no = st.session_state.selected_doc
    if not doc_no:
        return

    entry = get_journal_entry(df, doc_no)

    with st.expander(f"전표 상세: {doc_no}", expanded=True):
        info = entry.get("doc_info", {})
        col_a, col_b = st.columns(2)
        col_a.write(f"**전기일**: {info.get('post_date', '')}")
        col_b.write(f"**전표유형**: {info.get('doc_type', '')}")

        # ── 통합 분개 테이블 ──────────────────────
        rows = []
        for item in entry.get("debit", []):
            rows.append({
                "구분":   "차변",
                "계정코드": item["acc_code"],
                "계정명":  item["acc_name"],
                "차변금액": item["amount"],
                "대변금액": None,
                "_acc_code": item["acc_code"],
                "_acc_name": item["acc_name"],
            })
        for item in entry.get("credit", []):
            rows.append({
                "구분":   "대변",
                "계정코드": item["acc_code"],
                "계정명":  item["acc_name"],
                "차변금액": None,
                "대변금액": item["amount"],
                "_acc_code": item["acc_code"],
                "_acc_name": item["acc_name"],
            })

        if rows:
            tbl = pd.DataFrame(rows)
            display_tbl = tbl[["구분", "계정코드", "계정명", "차변금액", "대변금액"]].copy()
            st.dataframe(
                display_tbl,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "차변금액": st.column_config.NumberColumn("차변금액", format="%,.0f"),
                    "대변금액": st.column_config.NumberColumn("대변금액", format="%,.0f"),
                },
            )

            total_debit  = tbl["차변금액"].fillna(0).sum()
            total_credit = tbl["대변금액"].fillna(0).sum()
            ca, cb, cc = st.columns(3)
            ca.metric("차변 합계", f"{total_debit:,.0f}")
            cb.metric("대변 합계", f"{total_credit:,.0f}")
            cc.metric("차대 차이", f"{abs(total_debit - total_credit):,.0f}")

        if entry.get("balanced"):
            st.success("차대균형 일치")
        else:
            st.error("차대균형 불일치")

        # ── 계정 드릴다운 버튼 ────────────────────
        st.caption("계정을 클릭하면 해당 계정 원장으로 이동합니다.")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**차변**")
            for idx, item in enumerate(entry.get("debit", [])):
                if st.button(f"{item['acc_name']}  {item['amount']:,.0f}",
                             key=f"debit_{item['acc_code']}_{item['line_no']}_{idx}"):
                    push_history(st.session_state.target_acc,
                                 st.session_state.target_level,
                                 st.session_state.target_code)
                    st.session_state.target_level = 3
                    st.session_state.target_code  = item["acc_code"]
                    st.session_state.target_acc   = item["acc_name"]
                    st.session_state.selected_doc = None
                    st.rerun()
        with col2:
            st.write("**대변**")
            for idx, item in enumerate(entry.get("credit", [])):
                if st.button(f"{item['acc_name']}  {item['amount']:,.0f}",
                             key=f"credit_{item['acc_code']}_{item['line_no']}_{idx}"):
                    push_history(st.session_state.target_acc,
                                 st.session_state.target_level,
                                 st.session_state.target_code)
                    st.session_state.target_level = 3
                    st.session_state.target_code  = item["acc_code"]
                    st.session_state.target_acc   = item["acc_name"]
                    st.session_state.selected_doc = None
                    st.rerun()


# ──────────────────────────────────────────
# Main
# ──────────────────────────────────────────
def render_risk_view():
    anomaly_df, summary_df = load_anomaly()

    if anomaly_df is None:
        st.warning("anomaly 산출물이 없습니다. `src/anomaly.py`의 `run_anomaly_pipeline()`을 먼저 실행하세요.")
        return

    # ── Sidebar 필터 ──────────────────────────
    with st.sidebar:
        st.header("Risk 필터")
        max_score = int(anomaly_df["_risk_score"].max()) if "_risk_score" in anomaly_df.columns else 12
        min_score = st.slider("최소 Risk Score", 0, max_score, 1)

        level_options = ["ALL", "HIGH", "MEDIUM", "LOW"]
        selected_level = st.selectbox("Risk Level", level_options)

        # 신버전 Rule(_flag_<rule>)만 포함, 구버전 컬럼 제외
        flag_cols = [
            f"_flag_{rule}" for rule in RULE_LABELS_KO
            if f"_flag_{rule}" in anomaly_df.columns
        ]
        label_to_col = {RULE_LABELS_KO[c.replace("_flag_", "")]: c for c in flag_cols}
        selected_labels = st.multiselect("Flag 종류 (AND 조건)", list(label_to_col.keys()))

    # ── 필터 적용 ──────────────────────────────
    filtered = anomaly_df[anomaly_df["_risk_score"] >= min_score].copy()
    if selected_level != "ALL":
        filtered = filtered[filtered["_risk_level"] == selected_level]
    for label in selected_labels:
        col = label_to_col[label]
        if col in filtered.columns:
            filtered = filtered[filtered[col]]

    # ── 요약 지표 ──────────────────────────────
    st.title("Risk View")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 전표 라인", f"{len(anomaly_df):,}")
    c2.metric("필터 결과", f"{len(filtered):,}")
    c3.metric("HIGH 건수", f"{(anomaly_df['_risk_level'] == 'HIGH').sum():,}")
    c4.metric("MEDIUM 건수", f"{(anomaly_df['_risk_level'] == 'MEDIUM').sum():,}")

    st.divider()

    # ── Rule 요약 ──────────────────────────────
    if summary_df is not None:
        with st.expander("Rule별 탐지 현황", expanded=False):
            st.dataframe(
                summary_df,
                use_container_width=True,
                column_config={
                    "rule":            st.column_config.TextColumn("Rule"),
                    "weight":          st.column_config.NumberColumn("가중치"),
                    "count":           st.column_config.NumberColumn("탐지 건수"),
                    "ratio_pct":       st.column_config.NumberColumn("탐지 비율(%)", format="%.2f"),
                    "avg_abs_amount":  st.column_config.NumberColumn("평균 금액", format="%,.0f"),
                },
            )

    # ── High Risk 거래 목록 ────────────────────
    st.subheader(f"High Risk Transactions ({len(filtered):,}건)")

    if filtered.empty:
        st.info("조건에 해당하는 거래가 없습니다.")
        return

    display_cols = [c for c in [
        "post_date", "doc_no", "acc_code", "acc_name",
        "doc_type", "_amount", "_risk_score", "_risk_level", "_risk_flags",
    ] if c in filtered.columns]

    display_df = filtered[display_cols].copy()
    if "post_date" in display_df.columns:
        display_df["post_date"] = display_df["post_date"].astype(str).str[:10]

    event = st.dataframe(
        display_df.sort_values("_risk_score", ascending=False).reset_index(drop=True),
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key="risk_table",
        column_config={
            "post_date":   st.column_config.TextColumn("전기일"),
            "doc_no":      st.column_config.TextColumn("전표번호"),
            "acc_code":    st.column_config.TextColumn("계정코드"),
            "acc_name":    st.column_config.TextColumn("계정명"),
            "doc_type":    st.column_config.TextColumn("전표유형"),
            "_amount":     st.column_config.NumberColumn("금액", format="%,.0f"),
            "_risk_score": st.column_config.NumberColumn("Risk Score"),
            "_risk_level": st.column_config.TextColumn("Level"),
            "_risk_flags": st.column_config.TextColumn("탐지 Rule"),
        },
    )

    # ── 행 선택 → 전표 상세 ────────────────────
    sel = st.session_state.get("risk_table", {})
    rows = sel.get("selection", {}).get("rows", []) if isinstance(sel, dict) else []
    if rows:
        sorted_df = display_df.sort_values("_risk_score", ascending=False).reset_index(drop=True)
        doc_no = str(sorted_df.iloc[rows[0]]["doc_no"])
        st.divider()
        st.subheader(f"전표 상세: {doc_no}")
        df, _ = load_all()
        entry = get_journal_entry(df, doc_no)
        info = entry.get("doc_info", {})
        col_a, col_b = st.columns(2)
        col_a.write(f"**전기일**: {info.get('post_date', '')}")
        col_b.write(f"**전표유형**: {info.get('doc_type', '')}")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("차변")
            for item in entry.get("debit", []):
                st.write(f"{item['acc_name']}  {item['amount']:,.0f}")
        with col2:
            st.subheader("대변")
            for item in entry.get("credit", []):
                st.write(f"{item['acc_name']}  {item['amount']:,.0f}")
        if entry.get("balanced"):
            st.success("차대균형 일치")
        else:
            st.error("차대균형 불일치")


def main():
    st.set_page_config(page_title="GL 분석", layout="wide")
    init_state()

    if not os.path.exists(GL_PATH):
        st.error(f"파일 없음: {GL_PATH}")
        st.stop()
    if not os.path.exists(MASTER_PATH):
        st.error(f"계정 마스터 없음: {MASTER_PATH}")
        st.stop()

    tab_explorer, tab_risk = st.tabs(["계정 탐색", "Risk View"])

    # ── 계정 탐색 탭 ──────────────────────────
    with tab_explorer:
        df, master = load_all()
        render_sidebar(master)

        if not st.session_state.target_code:
            st.title("GL 드릴다운 탐색")
            st.info("좌측 사이드바에서 계정을 선택하고 [조회] 버튼을 누르세요.")
        else:
            st.title(f"계정 원장: {st.session_state.target_acc}")
            level = st.session_state.target_level
            code  = st.session_state.target_code

            if level == 3:
                bal    = calculate_balance(df, acc_code=code)
                ledger = get_ledger(df, acc_code=code, date_range=st.session_state.date_range)
            else:
                bal    = calculate_balance(df, level=level, level_code=code)
                ledger = get_ledger(df, level=level, level_code=code, date_range=st.session_state.date_range)

            c1, c2, c3 = st.columns(3)
            c1.metric("차변 합계", f"{bal['debit']:,.0f}")
            c2.metric("대변 합계", f"{bal['credit']:,.0f}")
            c3.metric("순잔액",   f"{bal['net']:,.0f}")
            st.divider()

            if ledger.empty:
                st.warning("해당 조건의 전표가 없습니다.")
            else:
                display_df = ledger.copy()
                if "post_date" in display_df.columns:
                    display_df["post_date"] = display_df["post_date"].astype(str).str[:10]

                st.dataframe(
                    display_df,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="ledger_table",
                    column_config={
                        "doc_no":    st.column_config.TextColumn("전표번호"),
                        "post_date": st.column_config.TextColumn("전기일"),
                        "_debit":    st.column_config.NumberColumn("차변", format="%,.0f"),
                        "_credit":   st.column_config.NumberColumn("대변", format="%,.0f"),
                        "_amount":   st.column_config.NumberColumn("금액", format="%,.0f"),
                    },
                )

                sel = st.session_state.get("ledger_table", {})
                rows = sel.get("selection", {}).get("rows", []) if isinstance(sel, dict) else []
                if rows:
                    doc_no = str(display_df.iloc[rows[0]]["doc_no"])
                    if doc_no != st.session_state.selected_doc:
                        st.session_state.selected_doc = doc_no
                        st.rerun()

            render_journal_view(df)

    # ── Risk View 탭 ──────────────────────────
    with tab_risk:
        render_risk_view()


if __name__ == "__main__":
    main()
