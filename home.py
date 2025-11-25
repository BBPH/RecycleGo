import streamlit as st
import openai
import base64
from openai import OpenAI

import streamlit as st
import openai
import base64
from openai import OpenAI
#https://3amtgxmdtwyym69bwahkyv.streamlit.app/

st.title(":blue[Chat!]")
client = st.session_state.get("client", None)

if client is None:
    st.stop()

def gpt(prompt):
    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )
    return response.output_text

def s_m(m):
    with st.chat_message(m['role']):
        st.markdown(m["content"])

if "record" not in st.session_state:
    st.session_state["record"] = []

if st.button("Clear!!"):
    del st.session_state["record"]

for m in st.session_state["record"][1:]:
    s_m(m)

if prompt := st.chat_input("Say something!!!"):
    p1 = {"role":"user", "content": prompt}
    st.session_state["record"].append(p1)
    s_m(p1)
    response = gpt(st.session_state["record"])
    p2 = {"role":"assistant", "content": response}
    st.session_state["record"].append(p2)
    s_m(p2)

#https://xn--oy2b29bd3a601b.kr/