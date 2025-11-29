import db
import streamlit as st
import openai
import base64
from openai import OpenAI
import random

db.init_db()
db.seed_missions()

item_name = "instant"  # 나중에 품목 이름이랑 연결할 수 있음

# 퀴즈 목록 로딩 (한 번만)
if "quizzes" not in st.session_state:
    st.session_state["quizzes"] = db.get_quizzes_by_item(item_name)

quizzes = st.session_state["quizzes"]

if not quizzes:  # [], None 둘 다 대비
    st.info(f"'{item_name}'에 대한 퀴즈가 아직 없습니다.")
else:
    # 한 번 선택한 퀴즈는 유지하고 싶으면 index를 state로
    if "current_quiz_id" not in st.session_state:
        quiz = random.choice(quizzes)
        st.session_state["current_quiz_id"] = quiz["id"]
    else:
        # 같은 id의 퀴즈 다시 찾기
        qid = st.session_state["current_quiz_id"]
        quiz = next((q for q in quizzes if q["id"] == qid), quizzes[0])

    st.subheader(f"퀴즈 - {quiz['item_name']}")
    st.write(quiz["question"])

    # 🔹 이제 options를 그냥 문자열 리스트로 사용
    options = quiz["options"]  # 예: ["O", "X"]

    selected = st.radio(
        "정답을 선택하세요.",
        options=options,  # ← ["O", "X"]
        key=f"quiz_{quiz['id']}",
        index=None,          # 처음엔 아무 것도 선택 안 하도록 (선택 안 한 상태 허용)
    )

    if st.button("정답 확인", key=f"quiz_check_{quiz['id']}"):
        if selected is None:
            st.warning("먼저 보기를 선택해 주세요.")
        else:
            correct_value = options[quiz["answer_idx"]]  # 예: "O" or "X"
            if selected == correct_value:
                st.success("정답입니다! 🎉")
            else:
                st.error(f"오답입니다. 정답은 '{correct_value}' 입니다.")
