import streamlit as st
import openai
import base64
from openai import OpenAI
#https://3amtgxmdtwyym69bwahkyv.streamlit.app/

st.markdown(
    """
    <style>
    body {
        background-color: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True
)

if 'api_key' not in st.session_state:
    st.session_state["api_key"] = ''

st.title(":blue[분]:green[리]:yellow[수]:black[Go!]")
api_key = st.text_input(":blue[Api key!!]", type="password", value=st.session_state["api_key"])

if api_key:
    st.session_state["api_key"] = api_key
    client = OpenAI(api_key=api_key)
    st.session_state["client"] = client
    st.write("Input complete!!!")

if client is None:
    st.stop()

file_paths = ["data/recycle.pdf"]
file_streams = [open(path, "rb") for path in file_paths]

if file_streams !=[]:
    vector_store = client.vector_stores.create(name="recycle_PDF")
    file_batch = client.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id,
        files=file_streams
    )
    st.session_state["vector_store"] = vector_store

def gpt(prompt):
    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
        tools=[{
            "type": "file_search",
            "vector_store_ids": [vector_store.id],
        }],
        include=["file_search_call.results"]
    )
    return response.output_text

def show_chat(m):
    with st.chat_message(m['role']):
        st.markdown(m["content"])

if "record" not in st.session_state:
    st.session_state["record"] = [{"role": "developer", "content": """너는 한국의 분리수거 도우미야.사용자가 말한 품목을 어떻게 분리수거해야 하는지 주어진 자료를 통해 간단하고 정확하게 알려줘."""}]

if st.button("Clear!!"):
    del st.session_state["record"]

for m in st.session_state["record"][1:]:
    show_chat(m)

if prompt := st.chat_input("분리수거 하고싶은 품목을 입력하세요."):
    p1 = {"role":"user", "content": prompt}
    st.session_state["record"].append(p1)
    show_chat(p1)
    response = gpt(st.session_state["record"])
    p2 = {"role":"assistant", "content": response}
    st.session_state["record"].append(p2)
    show_chat(p2)

#https://xn--oy2b29bd3a601b.kr/