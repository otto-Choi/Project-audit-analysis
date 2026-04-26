"""
app.py — Week 4 Streamlit 드릴다운 탐색 UI
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

# ──────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────
GL_PATH     = os.path.join(os.path.dirname(__file__), "data", "master_gl_clean.csv")
MASTER_PATH = os.path.join(os.path.dirname(__file__), "data", "account_master.csv")


# ──────────────────────────────────────────
# 데이터 로드 (캐싱)
# ──────────────────────────────────────────
@st.cache_data
def load_all():
    df = load_data(GL_PATH, MASTER_PATH)
    master = pd.read_csv(MASTER_PATH, dtype=str)
    return df, master


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

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("차변")
            for idx, item in enumerate(entry.get("debit", [])):
                btn_key = f"debit_{item['acc_code']}_{item['line_no']}_{idx}"
                if st.button(
                    f"{item['acc_name']}  {item['amount']:,.0f}",
                    key=btn_key,
                ):
                    push_history(
                        st.session_state.target_acc,
                        st.session_state.target_level,
                        st.session_state.target_code,
                    )
                    st.session_state.target_level = 3
                    st.session_state.target_code  = item["acc_code"]
                    st.session_state.target_acc   = item["acc_name"]
                    st.session_state.selected_doc = None
                    st.rerun()

        with col2:
            st.subheader("대변")
            for idx, item in enumerate(entry.get("credit", [])):
                btn_key = f"credit_{item['acc_code']}_{item['line_no']}_{idx}"
                if st.button(
                    f"{item['acc_name']}  {item['amount']:,.0f}",
                    key=btn_key,
                ):
                    push_history(
                        st.session_state.target_acc,
                        st.session_state.target_level,
                        st.session_state.target_code,
                    )
                    st.session_state.target_level = 3
                    st.session_state.target_code  = item["acc_code"]
                    st.session_state.target_acc   = item["acc_name"]
                    st.session_state.selected_doc = None
                    st.rerun()

        if entry.get("balanced"):
            st.success("차대균형 일치")
        else:
            st.error("차대균형 불일치")


# ──────────────────────────────────────────
# Main
# ──────────────────────────────────────────
def main():
    st.set_page_config(page_title="GL 드릴다운 탐색", layout="wide")
    init_state()

    # 데이터 로드
    if not os.path.exists(GL_PATH):
        st.error(f"파일 없음: {GL_PATH}")
        st.stop()
    if not os.path.exists(MASTER_PATH):
        st.error(
            f"계정 마스터 없음: {MASTER_PATH}\n\n"
            "탐색과정/an.ipynb 를 실행하여 account_master.csv 를 먼저 생성하세요."
        )
        st.stop()

    df, master = load_all()

    render_sidebar(master)

    # 미선택 상태
    if not st.session_state.target_code:
        st.title("GL 드릴다운 탐색")
        st.info("좌측 사이드바에서 계정을 선택하고 [조회] 버튼을 누르세요.")
        return

    # 제목
    st.title(f"계정 원장: {st.session_state.target_acc}")

    # 잔액 요약
    level = st.session_state.target_level
    code  = st.session_state.target_code

    if level == 3:
        bal = calculate_balance(df, acc_code=code)
        ledger = get_ledger(df, acc_code=code, date_range=st.session_state.date_range)
    else:
        bal = calculate_balance(df, level=level, level_code=code)
        ledger = get_ledger(df, level=level, level_code=code, date_range=st.session_state.date_range)

    c1, c2, c3 = st.columns(3)
    c1.metric("차변 합계", f"{bal['debit']:,.0f}")
    c2.metric("대변 합계", f"{bal['credit']:,.0f}")
    c3.metric("순잔액",   f"{bal['net']:,.0f}")

    st.divider()

    if ledger.empty:
        st.warning("해당 조건의 전표가 없습니다.")
    else:
        # 날짜 포맷
        display_df = ledger.copy()
        if "post_date" in display_df.columns:
            display_df["post_date"] = display_df["post_date"].astype(str).str[:10]

        event = st.dataframe(
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

        # 행 선택 → 전표 조회
        sel = st.session_state.get("ledger_table", {})
        rows = sel.get("selection", {}).get("rows", []) if isinstance(sel, dict) else []
        if rows:
            doc_no = str(display_df.iloc[rows[0]]["doc_no"])
            if doc_no != st.session_state.selected_doc:
                st.session_state.selected_doc = doc_no
                st.rerun()

    render_journal_view(df)


if __name__ == "__main__":
    main()
