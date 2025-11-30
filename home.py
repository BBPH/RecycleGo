import streamlit as st
import openai
import base64
from openai import OpenAI
import db
import os  # 파일 존재 여부 체크용
import random

# 나중에 도메인 좀 직관적이고 예쁜걸로 바꾸기!
# 웹페이지로(아마)
# 정보 출처 표기 일단은 여기 --> 출처: 생활법령정보, 제품·포장재 분리배출요령
# 이것 말고도 정보가 더 있으면 좋겠음. 법령이랑 추가정보랑 해서 pdf 통합해야 될 듯.
# 아이디 비번 형식이나, api key 필요없는 버전으로 만들고 싶지만, 일단 보류. (방법 필요)
# github는 streamlit cloud로 웹사이트를 실행하면 서버 복사본으로 실행중이랬나? 그렇게 되니까... 계속 켜두기만 하면 정보손실 없는거 아닌가?







### function list



# --- 로그인 / 회원가입 UI 함수 ---
def show_auth():
    st.title("분리수Go! 로그인")

    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

    with tab_signup:
        su_name = st.text_input("새 아이디", key="su_name")
        su_pw = st.text_input("새 비밀번호", type="password", key="su_pw")
        su_region = st.text_input("지역(선택)", key="su_region")

        if st.button("회원가입"):
            if not su_name or not su_pw:
                st.error("아이디와 비밀번호는 필수입니다.")
            else:
                try:
                    db.create_user(su_name, su_pw, su_region or None)
                    st.success("회원가입 완료! 이제 로그인 탭에서 로그인하세요.")
                except Exception as e:
                    st.error(f"회원가입 실패: {e}")

    with tab_login:
        li_name = st.text_input("아이디", key="li_name")
        li_pw = st.text_input("비밀번호", type="password", key="li_pw")

        if st.button("로그인"):
            user_id = db.authenticate(li_name, li_pw)
            if user_id is None:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
            else:
                st.session_state["user_id"] = user_id
                st.session_state["username"] = li_name
                st.success("로그인 성공!")
                st.session_state["show_login"] = False
                st.session_state["show_chat"] = True
                st.rerun()  # 로그인 후 메인 화면으로 바로 전환

def show_INFO():
    st.title("Information")
    st.write("정보 출처 : 생활법령정보, 제품·포장재 분리배출요령")
    st.write("개발 언어 : Python")

def show_quiz(user_id):    # 틀렸을 때 같은 퀴즈 보여줄 수 있으니 수정
    QUIZ_REWARD = 10  # 예: 일일 퀴즈 포인트

    # 퀴즈 목록 로딩 (한 번만)
    if "quizzes" not in st.session_state:
        st.session_state["quizzes"] = db.get_quizzes_by_item(str(random.randint(1, 4)))

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

def gpt(prompt):    #response 생성 함수, 필요없는 정보도 제공하는 이슈 있음(해결인지 아닌지 긴가민가).
    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
        tools=[{
            "type": "file_search",
            "vector_store_ids": [st.session_state["vector_store_id"]],
        }],
        include=["file_search_call.results"]
    )
    return response.output_text

def analyze_image(client, image_file):    # 물건 최대 2개정도 제대로 인식함.
    bytes_data = image_file.read()
    b64 = base64.b64encode(bytes_data).decode("utf-8")

    response = client.responses.create(
        model="gpt-4.1-mini",  # vision 지원되는 모델로 교체
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": """이 물건이 어떤 물건인지 추리해서, 어떤 물건인지만 알려줘. 예를 들어서, 유리컵과 축구공이 보이는 사진을 입력받으면, "유리컵, 축구공" 이라고만 답해줘."""
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{b64}",
                        "detail": "auto"
                    }
                ]
            }
        ]
    )
    return response.output_text

def create_vector(client):   # vector 저장여부 확인함수
    TARGET_NAME = "recycle_PDF"

    # 1) 내 계정에 이미 같은 이름의 vector store가 있는지 확인
    vs_list = client.vector_stores.list(limit=50)
    for vs in vs_list.data:
        if vs.name == TARGET_NAME:
            return vs  # 있으면 그거 재사용

    # 2) 없으면 새로 만들고 PDF 2개 업로드
    file_paths = [
        "data/recycle.pdf",
        "data/foods.pdf",   # 새로 추가한 음식물 쓰레기 PDF
    ]

    # 실제로 존재하는 파일만 필터링 (혹시 한쪽이 없을 때 대비)
    existing_paths = [p for p in file_paths if os.path.exists(p)]
    if not existing_paths:
        raise FileNotFoundError("업로드할 PDF 파일을 찾을 수 없습니다. data/ 폴더를 확인하세요.")

    file_streams = [open(path, "rb") for path in existing_paths]

    try:
        vs = client.vector_stores.create(name=TARGET_NAME)
        client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vs.id,
            files=file_streams,
        )
    finally:
        # 파일 핸들 닫기
        for f in file_streams:
            f.close()

    return vs

def show_chat(m):   #chat show 함수, 어떤 인터페이스 쓸지 고민 필요.
    with st.chat_message(m['role']):
        st.markdown(m["content"])

def show_image(m):
    if m.get("role") != "assistant":
        return  # user면 아무것도 표시 안 함

    with st.chat_message("assistant"):
        st.markdown(m.get("content", ""))




### User Interface     ------------------------------------------------------------------------------------------------------------------------------



db.init_db()
db.seed_missions()

st.set_page_config(page_title="분리수Go!", page_icon="♻️")

# --- 세션 기본값 세팅 ---
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
    st.session_state["username"] = None

if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

if "show_INFO" not in st.session_state:
    st.session_state["show_INFO"] = False

if "show_login" not in st.session_state:
    st.session_state["show_login"] = False

if "show_quiz" not in st.session_state:
    st.session_state["show_quiz"] = False

if "show_chat" not in st.session_state:
    st.session_state["show_chat"] = True


# --- 사이드바 ---
with st.sidebar:
    st.title(":blue[분]:green[리]:yellow[수]:rainbow[Go!]")

    # 🔹 API Key 입력 (항상 보이게)
    st.subheader("OpenAI API Key")
    api_key = st.text_input(
        "API Key",
        type="password",
        value=st.session_state.get("api_key", "")
    )
    if api_key:
        st.session_state["api_key"] = api_key
        # 키가 새로 입력되었거나 바뀌었으면 client 갱신
        if "client" not in st.session_state or st.session_state.get("client_key") != api_key:
            st.session_state["client"] = OpenAI(api_key=api_key)
            st.session_state["client_key"] = api_key
        st.caption("✅ 키 입력 완료")
    else:
        st.warning("API Key를 입력해야 챗봇을 사용할 수 있어요.")

    st.divider()

    if st.button("챗봇"):
        st.session_state["show_chat"] = True
        st.session_state["show_login"] = False
        st.session_state["show_quiz"] = False

    if st.button("퀴즈"):
        st.session_state["show_chat"] = False
        st.session_state["show_login"] = False
        st.session_state["show_quiz"] = True

    st.divider()

    # 🔹 로그인 / 로그아웃
    if st.session_state["user_id"] is None:
        if st.button("로그인", key="sidebar_login"):
            st.session_state["show_login"] = True
    else:
        user_id = st.session_state["user_id"]
        username = st.session_state["username"]

        # 🔹 현재 프리미엄 여부 표시
        premium_now = db.is_premium(user_id)
        if premium_now:
            st.caption("⭐ 현재 프리미엄 계정입니다.")
        else:
            st.caption("일반 계정입니다.")

        # 🔹 프리미엄 토글 버튼 (개발용)
        if st.button("현재 계정 프리미엄 토글", key="sidebar_premium_toggle"):
            db.set_premium(user_id, not premium_now)
            st.rerun()

        if st.button("로그아웃", key="sidebar_logout"):
            st.session_state["user_id"] = None
            st.session_state["username"] = None
            st.session_state["show_login"] = False
            st.rerun()

    # 🔹 INFO
    if st.button("INFO", key="sidebar_info"):
        st.session_state["show_INFO"] = True

# --- INFO 페이지 ---
if st.session_state["show_INFO"]:
    show_INFO()
    st.session_state["show_INFO"] = False   # 한 번 보여주고 끄기

# --- 로그인 화면 (선택 사항) ---
if st.session_state["user_id"] is None and st.session_state["show_login"]:
    show_auth()   # ✅ 메인 영역에 로그인/회원가입 UI 렌더링
    st.session_state["show_chat"] = False

# --- OpenAI client 체크 ---
client = st.session_state.get("client")
if client is None:
    st.warning("사이드바에서 OpenAI API Key를 먼저 입력해 주세요.")
    st.stop()

# --- 여기부터는 '로그인된 상태' 전용 메인 화면 ---

if st.session_state["user_id"] is not None:
    username = st.session_state["username"]
    user_id = st.session_state["user_id"]

    total_points = db.get_points(user_id)
    today_points = db.get_today_points(user_id)
    title = db.get_title(total_points)

    premium = db.is_premium(user_id)   # 프리미엄으로 바꿔주는 기능 필요

    if premium:
        st.success("⭐ 프리미엄 사용자입니다!")
        if "image_record" not in st.session_state:
            st.session_state["image_record"] = [{"role": "developer", "content": """너는 한국의 분리수거 도우미야. 다른 내용 말고, 사용자가 말한 품목만을 어떻게 분리수거해야 하는지 주어진 자료를 통해 간단하고 정확하게 알려줘."""}]
    else:
        st.info("일반 사용자입니다. (데모에서는 'admin' 계정 등을 프리미엄으로 가정)")

    if premium:                                                        # sidebar에 기능 분리. (또는 pages 활용)
        uploaded = st.file_uploader("품목 사진 업로드", type=["jpg", "jpeg", "png"])
        if uploaded is not None:
            with st.spinner("이미지 분석 중..."):
                try:
                    explanation = analyze_image(client, uploaded)
                    p1 = {"role":"user", "content": explanation}
                    st.session_state["image_record"].append(p1)
                    show_image(p1)
                    response = gpt(st.session_state["image_record"])
                    p2 = {"role":"assistant", "content": response}
                    st.session_state["image_record"].append(p2)
                    show_image(p2)
                except Exception as e:
                    st.error(f"이미지 분석 중 오류가 발생했습니다: {e}")

# 유저의 현재 포인트 / 칭호 / 오늘 포인트

    col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
    with col1:
        st.metric("총 마일리지", total_points)
    with col2:
        st.metric("오늘 획득", today_points)
    with col3:
        st.write(f"현재 칭호: **{title}**")

    st.divider()

    st.subheader("오늘의 미션")

    missions = db.get_or_create_today_missions(user_id)
    if not missions:
        st.info("오늘은 미션이 없습니다.")
    else:
        done = sum(1 for m in missions if m["completed"])
        total = len(missions)
        st.write(f"오늘 미션 진행도: **{done} / {total}**")

        cols = st.columns(total)
        for col, m in zip(cols, missions):
            with col:
                st.write(f"✅ {m['description']}")
                st.write(f"보상: **+{m['reward']}점**")
                if m["completed"]:
                    st.success("완료됨")
                else:
                    if st.button("완료하기", key=f"mission_{m['user_mission_id']}"):
                        db.complete_mission(m["user_mission_id"])
                        st.success("미션 완료!")
                        st.rerun()

    if st.session_state["show_quiz"]:
        show_quiz(user_id)
        st.session_state["show_quiz"] = False   # 한 번 보여주고 끄기

    st.divider()

else:
    # 🔓 Guest 모드 안내
    st.info("현재 Guest 모드입니다. 로그인하면 마일리지, 일일 미션, 프리미엄 기능을 사용할 수 있습니다.")
    username = "Guest"
    st.divider()

if st.session_state["show_chat"]:
    st.title(f":blue[분]:green[리]:yellow[수]:rainbow[Go!] 🌱 – {username}님 환영합니다!")

    vector_store = create_vector(client)
    st.session_state["vector_store_id"] = vector_store.id

    if "record" not in st.session_state:
        st.session_state["record"] = [{"role": "developer", "content": """너는 한국의 분리수거 도우미야. 다른 내용 말고, 사용자가 말한 품목만을 어떻게 분리수거해야 하는지 주어진 자료를 통해 간단하고 정확하게 알려줘."""}]

    for m in st.session_state["record"][1:]:
        show_chat(m)

    if prompt := st.chat_input("분리수거 하고싶은 품목을 입력하세요."):   # 실제 prompt 입력, sidebar에 기능 분리. (또는 pages 활용)
        p1 = {"role":"user", "content": prompt}
        st.session_state["record"].append(p1)
        show_chat(p1)
        response = gpt(st.session_state["record"])
        p2 = {"role":"assistant", "content": response}
        st.session_state["record"].append(p2)
        show_chat(p2)