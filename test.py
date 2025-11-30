import db
import streamlit as st
import openai
import base64
from openai import OpenAI
import random

db.init_db()
db.seed_missions()

QUIZ_REWARD = 10  # 예: 일일 퀴즈 포인트

# 퀴즈 목록 로딩 (한 번만)
if "quizzes" not in st.session_state:
    st.session_state["quizzes"] = db.get_quizzes_by_item()

if not st.session_state["quizzes"]:  # [], None 둘 다 대비
    st.info("퀴즈가 아직 없습니다.")
else:
    # 한 번 선택한 퀴즈는 유지하고 싶으면 index를 state로
    if "current_quiz_id" not in st.session_state:
        quiz = random.choice(st.session_state["quizzes"])
        st.session_state["current_quiz_id"] = quiz["id"]
    else:
        # 같은 id의 퀴즈 다시 찾기
        qid = st.session_state["current_quiz_id"]
        quiz = next((q for q in st.session_state["quizzes"] if q["id"] == qid), st.session_state["quizzes"][0])

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
        is_correct = (selected == quiz["options"][quiz["answer_idx"]])

        if is_correct:
            # 🔹 이미 오늘 퀴즈 포인트를 받은 적 있는지 확인
            if db.has_solved_quiz_today(user_id):
                st.success("정답입니다! (오늘은 이미 퀴즈 포인트를 받았습니다. 연습용으로 계속 풀 수 있어요.)")
            else:
                # 처음으로 오늘 퀴즈를 맞춘 순간
                db.mark_quiz_solved_today(user_id)
                db.add_points(user_id, QUIZ_REWARD)
                st.success(f"정답입니다! 🎉 오늘 퀴즈 보상 {QUIZ_REWARD}점을 획득했습니다.")
        else:
            st.error("오답입니다. 다른 문제로 다시 도전해보세요!")
