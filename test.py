import db
import streamlit as st
import openai
import base64
from openai import OpenAI
import random

db.init_db()
db.seed_missions()
db.create_user("admin", "admin")
user_id = db.authenticate("admin", "admin")

missions = db.get_or_create_today_missions(user_id)
for m in missions:
    print(m)
print(db.get_mission_id_by_code("1"))
db.add_mission_progress(user_id, "1", 3)
print(db.has_enough_actions_today(user_id, "1", 3))

#has_enough_actions_today(user_id: int, mission_code: str, required_count: int, action_type: str | None = None) -> bool