import db
import streamlit as st
import openai
import base64
from openai import OpenAI

db.init_db()
db.seed_missions()

with st.sidebar:
    st.title("분리수Go! ♻️")

    # 🔼 위쪽: 메뉴
    page = st.radio(
        "메뉴",
        ["챗봇", "미션"],
        key="sidebar_menu"
    )

    st.divider()

    # 🔽 아래쪽: 로그인 / 유저 정보
    if st.session_state.get("user_id") is None:
        st.subheader("로그인")
        li_name = st.text_input("아이디", key="li_name_sidebar")
        li_pw = st.text_input("비밀번호", type="password", key="li_pw_sidebar")
        if st.button("로그인", key="login_sidebar"):
            user_id = db.authenticate(li_name, li_pw)
            if user_id is None:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
            else:
                st.session_state["user_id"] = user_id
                st.session_state["username"] = li_name
                st.rerun()
    else:
        st.subheader("내 정보")
        st.write(f"👤 {st.session_state['username']}")
        total_points = db.get_points(st.session_state["user_id"])
        st.write(f"🌱 마일리지: {total_points}")
        if st.button("로그아웃", key="logout_sidebar"):
            st.session_state["user_id"] = None
            st.session_state["username"] = None
            st.rerun()