import streamlit as st
import openai
import base64
from openai import OpenAI

# 나중에 도메인 좀 직관적이고 예쁜걸로 바꾸기!
# 웹페이지로(아마)
# 정보 출처 표기 일단은 여기 --> 출처: 생활법령정보, 제품·포장재 분리배출요령
# 이것 말고도 정보가 더 있으면 좋겠음. 법령이랑 추가정보랑 해서 pdf 통합해야 될 듯.
# 아이디 비번 형식이나, api key 필요없는 버전으로 만들고 싶지만, 일단 보류. (방법 필요)

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

def create_vector(client):   #vector 저장여부 확인함수
    TARGET_NAME = "recycle_PDF"

    # 1) 내 계정에 이미 같은 이름의 vector store가 있는지 확인
    vs_list = client.vector_stores.list(limit=50)
    for vs in vs_list.data:
        if vs.name == TARGET_NAME:
            return vs  # 있으면 그거 재사용

    # 2) 없으면 새로 만들고 PDF 업로드
    with open("data/recycle.pdf", "rb") as f:
        vs = client.vector_stores.create(name=TARGET_NAME)
        client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vs.id,
            files=[f],
        )
    return vs

def show_chat(m):   #chat show 함수, 어떤 인터페이스 쓸지 고민 필요.
    with st.chat_message(m['role']):
        st.markdown(m["content"])

if 'api_key' not in st.session_state:
    st.session_state["api_key"] = ''

st.title(":blue[분]:green[리]:yellow[수]:rainbow[Go!]")
api_key = st.text_input(":blue[Api key]", type="password", value=st.session_state["api_key"])

if api_key:   #문구수정, 위치조정 등등의 수정 필요
    st.session_state["api_key"] = api_key
    client = OpenAI(api_key=api_key)
    st.session_state["client"] = client
    st.write("Input complete!!!")
else:
    st.markdown("api key를 입력하세요.")
    st.stop()

vector_store = create_vector(client)
st.session_state["vector_store_id"] = vector_store.id

if "record" not in st.session_state:
    st.session_state["record"] = [{"role": "developer", "content": """너는 한국의 분리수거 도우미야. 다른 내용 말고, 사용자가 말한 품목만을 어떻게 분리수거해야 하는지 주어진 자료를 통해 간단하고 정확하게 알려줘."""}]

if st.button(":rainbow[Clear!!]"):    #임시 clear버튼
    del st.session_state["record"]
    st.rerun()

for m in st.session_state["record"][1:]:
    show_chat(m)

if prompt := st.chat_input("분리수거 하고싶은 품목을 입력하세요."):   #실제 prompt 입력
    p1 = {"role":"user", "content": prompt}
    st.session_state["record"].append(p1)
    show_chat(p1)
    response = gpt(st.session_state["record"])
    p2 = {"role":"assistant", "content": response}
    st.session_state["record"].append(p2)
    show_chat(p2)