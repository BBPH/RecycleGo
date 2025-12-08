import sqlite3
from pathlib import Path
from datetime import datetime
import bcrypt
import json

# DB 파일 경로 (프로젝트 루트에 recyclego.db 생성)
DB_PATH = Path(__file__).parent / "recyclego.db"


def get_conn():
    """DB 연결 반환 (사용 후 꼭 conn.close())"""
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # users 테이블 (is_premium 추가)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            region        TEXT,
            points        INTEGER NOT NULL DEFAULT 0,
            is_premium    INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL
        )
        """
    )

    # 미션 정의 테이블
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS missions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            reward      INTEGER NOT NULL
        )
        """
    )

    # 유저별/날짜별 미션 할당/진행도
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_missions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            mission_id   INTEGER NOT NULL,
            date         TEXT NOT NULL,
            completed    INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            UNIQUE(user_id, mission_id, date),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        )
        """
    )

    # 🔹 분리수거 퀴즈 테이블
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS quizzes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name  TEXT    NOT NULL,   -- 예: '페트병', '종이컵'
            question   TEXT    NOT NULL,   -- 문제 문장
            options    TEXT    NOT NULL,   -- 보기: JSON 문자열로 저장
            answer_idx INTEGER NOT NULL    -- 정답 보기 인덱스(0,1,2,3...)
        )
        """
    )

    # 🔹 유저별 일일 퀴즈 기록 테이블
    #    + 오늘 사용한 퀴즈 id 목록(used_quiz_ids, JSON 문자열) 추가
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_daily_quiz (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            date         TEXT    NOT NULL,   -- YYYY-MM-DD
            solved       INTEGER NOT NULL DEFAULT 0,  -- 오늘 퀴즈 클리어 여부 (0/1)
            solved_at    TEXT,               -- 처음 클리어한 시각
            used_quiz_ids TEXT,              -- 오늘 시도한 퀴즈 id 목록(JSON)
            UNIQUE(user_id, date),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    # 🔹 미션 수행 카운트 & 로그 테이블 (오늘 날짜 기준으로 count 누적)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_action (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            mission_id INTEGER NOT NULL,
            date       TEXT NOT NULL,        -- YYYY-MM-DD 기준
            count      INTEGER NOT NULL DEFAULT 0,
            data_json  TEXT,                 -- JSON 문자열(추가 정보)
            created_at TEXT NOT NULL,
            UNIQUE(user_id, mission_id, date),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        )
        """
    )

    conn.commit()
    conn.close()


# ---------------- 기본 유저/포인트 ----------------

def create_user(username: str, password: str, region: str | None = None):
    """회원가입: username, password, region 저장"""
    conn = get_conn()
    cur = conn.cursor()

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    pw_hash_str = pw_hash.decode("utf-8")

    now = datetime.now().isoformat(timespec="seconds")

    cur.execute(
        """
        INSERT INTO users (username, password_hash, region, points, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, pw_hash_str, region, 0, now),
    )

    conn.commit()
    conn.close()


def authenticate(username: str, password: str):
    """로그인 시도. 성공하면 user_id(int) 반환, 실패하면 None."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    user_id, pw_hash_str = row
    pw_hash_bytes = pw_hash_str.encode("utf-8")

    if bcrypt.checkpw(password.encode("utf-8"), pw_hash_bytes):
        return user_id

    return None


def get_points(user_id: int) -> int:
    """해당 유저의 현재 포인트 조회"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT points FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return 0
    return row[0]


def add_points(user_id: int, delta: int):
    """마일리지 증감 (delta만큼 더하기)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET points = points + ? WHERE id = ?",
        (delta, user_id),
    )
    conn.commit()
    conn.close()


# ---------------- 미션 정의 & 오늘 미션 ----------------

def seed_missions():
    """미션 테이블이 비어 있으면 기본 미션 몇 개 넣기."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM missions")
    (count,) = cur.fetchone()
    if count == 0:
        data = [
            ("1", "퀴즈 3개 이상 풀기", 100),
            ("2", "질의응답 2개 이상 하기", 100),
            ("3", "일일 미션 전부 완수하기", 150),
        ]
        cur.executemany(
            "INSERT INTO missions (code, description, reward) VALUES (?, ?, ?)",
            data,
        )
        conn.commit()

    conn.close()


def get_or_create_today_missions(user_id: int):
    """해당 유저의 '오늘 미션 3개'를 가져오고, 없으면 생성."""
    today = datetime.now().date().isoformat()
    conn = get_conn()
    cur = conn.cursor()

    # 이미 오늘 미션이 있는지 확인
    cur.execute(
        """
        SELECT um.id, m.id, m.code, m.description, m.reward, um.completed
        FROM user_missions um
        JOIN missions m ON um.mission_id = m.id
        WHERE um.user_id = ? AND um.date = ?
        ORDER BY um.id
        """,
        (user_id, today),
    )
    rows = cur.fetchall()

    if rows:
        conn.close()
        return [
            {
                "user_mission_id": r[0],
                "mission_id": r[1],
                "code": r[2],
                "description": r[3],
                "reward": r[4],
                "completed": bool(r[5]),
            }
            for r in rows
        ]

    # 오늘 미션이 없는 경우 → id 순서대로 3개 선택
    cur.execute("SELECT id, code, description, reward FROM missions ORDER BY id ASC LIMIT 3")
    selected = cur.fetchall()

    if len(selected) == 0:
        conn.close()
        return []

    # user_missions에 삽입
    for mid, code, desc, reward in selected:
        cur.execute(
            """
            INSERT INTO user_missions (user_id, mission_id, date)
            VALUES (?, ?, ?)
            """,
            (user_id, mid, today),
        )

    conn.commit()

    # 다시 가져오기
    cur.execute(
        """
        SELECT um.id, m.id, m.code, m.description, m.reward, um.completed
        FROM user_missions um
        JOIN missions m ON um.mission_id = m.id
        WHERE um.user_id = ? AND um.date = ?
        ORDER BY um.id
        """,
        (user_id, today),
    )
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "user_mission_id": r[0],
            "mission_id": r[1],
            "code": r[2],
            "description": r[3],
            "reward": r[4],
            "completed": bool(r[5]),
        }
        for r in rows
    ]


def complete_mission(user_mission_id: int):
    """미션 완료 처리 + 해당 유저에게 마일리지 지급."""
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    cur = conn.cursor()

    # 이미 완료된 미션인지 확인 + 보상 정보 가져오기
    cur.execute(
        """
        SELECT um.completed, um.user_id, m.reward
        FROM user_missions um
        JOIN missions m ON um.mission_id = m.id
        WHERE um.id = ?
        """,
        (user_mission_id,),
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        return

    completed, user_id, reward = row
    if completed:  # 이미 완료면 두 번 지급 방지
        conn.close()
        return

    # user_missions 완료 표시
    cur.execute(
        """
        UPDATE user_missions
        SET completed = 1, completed_at = ?
        WHERE id = ?
        """,
        (now, user_mission_id),
    )

    # 유저 포인트 추가
    cur.execute(
        "UPDATE users SET points = points + ? WHERE id = ?",
        (reward, user_id),
    )

    conn.commit()
    conn.close()


def get_today_points(user_id: int) -> int:
    """오늘 완료한 미션들의 reward 합."""
    today = datetime.now().date().isoformat()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT SUM(m.reward)
        FROM user_missions um
        JOIN missions m ON um.mission_id = m.id
        WHERE um.user_id = ? AND um.date = ? AND um.completed = 1
        """,
        (user_id, today),
    )
    row = cur.fetchone()
    conn.close()

    total = row[0]
    return total if total is not None else 0


def get_title(points: int) -> str:
    if points >= 300:
        return "분리수거 달인 🌟"
    elif points >= 150:
        return "환경 지킴이 🌱"
    elif points >= 50:
        return "분리수거 초보 탈출 👣"
    else:
        return "새싹 분리수거러 🌱(입문)"


# ---------------- 프리미엄 ----------------

def is_premium(user_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT is_premium FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row[0]) if row else False


def set_premium(user_id: int, value: bool):
    """현재 계정의 프리미엄 여부를 설정한다."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET is_premium = ? WHERE id = ?",
        (1 if value else 0, user_id),
    )
    conn.commit()
    conn.close()


# ---------------- 퀴즈 ----------------

def add_quiz(item_name: str, question: str, options_list, answer_idx: int):
    """
    분리수거 퀴즈 추가.
    options_list: ['보기1', '보기2', ...] 형태의 리스트
    answer_idx: 정답이 되는 보기의 인덱스(0부터 시작)
    """
    options_json = json.dumps(options_list, ensure_ascii=False)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO quizzes (item_name, question, options, answer_idx)
        VALUES (?, ?, ?, ?)
        """,
        (item_name, question, options_json, answer_idx),
    )
    conn.commit()
    conn.close()


def get_quizzes_by_item(item_name: str):
    """
    해당 항목 이름과 연결된 모든 퀴즈를 가져온다.
    return: [{id, item_name, question, options(list), answer_idx}, ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, item_name, question, options, answer_idx
        FROM quizzes
        WHERE item_name = ?
        """,
        (item_name,),
    )
    rows = cur.fetchall()
    conn.close()

    quizzes = []
    for qid, item, question, options_json, answer_idx in rows:
        options_list = json.loads(options_json)
        quizzes.append(
            {
                "id": qid,
                "item_name": item,
                "question": question,
                "options": options_list,
                "answer_idx": answer_idx,
            }
        )
    return quizzes


def get_quiz_by_id(quiz_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, item_name, question, options, answer_idx
        FROM quizzes
        WHERE id = ?
        """,
        (quiz_id,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    qid, item, question, options_json, answer_idx = row
    return {
        "id": qid,
        "item_name": item,
        "question": question,
        "options": json.loads(options_json),
        "answer_idx": answer_idx,
    }


def check_quiz_answer(quiz_id: int, selected_idx: int) -> bool:
    """사용자가 선택한 보기 인덱스가 정답인지 확인."""
    quiz = get_quiz_by_id(quiz_id)
    if quiz is None:
        return False
    return quiz["answer_idx"] == selected_idx


def has_solved_quiz_today(user_id: int) -> bool:
    """해당 유저가 '오늘 일일 퀴즈를 이미 클리어했는지' 여부."""
    today = datetime.now().date().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT solved
        FROM user_daily_quiz
        WHERE user_id = ? AND date = ?
        """,
        (user_id, today),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return False
    return bool(row[0])


def mark_quiz_solved_today(user_id: int):
    """
    오늘 날짜 기준으로 해당 유저의 일일 퀴즈를 '클리어' 상태로 기록.
    이미 기록이 있으면 solved=1로 업데이트.
    """
    today = datetime.now().date().isoformat()
    now = datetime.now().isoformat(timespec="seconds")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id FROM user_daily_quiz
        WHERE user_id = ? AND date = ?
        """,
        (user_id, today),
    )
    row = cur.fetchone()

    if row is None:
        cur.execute(
            """
            INSERT INTO user_daily_quiz (user_id, date, solved, solved_at)
            VALUES (?, ?, 1, ?)
            """,
            (user_id, today, now),
        )
    else:
        record_id = row[0]
        cur.execute(
            """
            UPDATE user_daily_quiz
            SET solved = 1, solved_at = ?
            WHERE id = ?
            """,
            (now, record_id),
        )

    conn.commit()
    conn.close()


def get_today_quiz_status(user_id: int):
    """오늘 유저의 일일 퀴즈 기록을 딕셔너리 형태로 반환. 없으면 None."""
    today = datetime.now().date().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, solved, solved_at
        FROM user_daily_quiz
        WHERE user_id = ? AND date = ?
        """,
        (user_id, today),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    record_id, solved, solved_at = row
    return {
        "id": record_id,
        "solved": bool(solved),
        "solved_at": solved_at,
    }


def get_today_used_quiz_ids(user_id: int) -> list[int]:
    """
    오늘 user가 한 번이라도 시도한 퀴즈 id 목록.
    """
    today = datetime.now().date().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT used_quiz_ids
        FROM user_daily_quiz
        WHERE user_id = ? AND date = ?
        """,
        (user_id, today),
    )
    row = cur.fetchone()
    conn.close()

    if row is None or row[0] is None:
        return []

    try:
        return json.loads(row[0])
    except Exception:
        return []


def add_today_used_quiz(user_id: int, quiz_id: int):
    """
    오늘 날짜 기준으로 used_quiz_ids에 quiz_id를 추가.
    (중복이면 무시)
    """
    today = datetime.now().date().isoformat()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT used_quiz_ids, solved, solved_at
        FROM user_daily_quiz
        WHERE user_id = ? AND date = ?
        """,
        (user_id, today),
    )
    row = cur.fetchone()

    if row is None:
        used_list = [quiz_id]
        used_json = json.dumps(used_list, ensure_ascii=False)
        cur.execute(
            """
            INSERT INTO user_daily_quiz (user_id, date, solved, solved_at, used_quiz_ids)
            VALUES (?, ?, 0, NULL, ?)
            """,
            (user_id, today, used_json),
        )
    else:
        used_json, solved, solved_at = row
        try:
            used_list = json.loads(used_json) if used_json else []
        except Exception:
            used_list = []

        if quiz_id not in used_list:
            used_list.append(quiz_id)
            new_used_json = json.dumps(used_list, ensure_ascii=False)
            cur.execute(
                """
                UPDATE user_daily_quiz
                SET used_quiz_ids = ?
                WHERE user_id = ? AND date = ?
                """,
                (new_used_json, user_id, today),
            )

    conn.commit()
    conn.close()


def seed_quizzes():
    """quizzes 테이블이 비어 있으면 기본 퀴즈 몇 개 넣기."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM quizzes")
    (count,) = cur.fetchone()

    if count == 0:
        data = [
            # ------------------------
            # 📌 기존 1~4번 퀴즈 (그대로 유지)
            # ------------------------
            ("1", "다음 중 분리수거를 할 수 없는 것은?", 
             ["종이컵", "스티로폼", "뽁뽁이", "테이프"], 3),

            ("2", "다음 보기 중 음식물 쓰레기는?", 
             ["수박 껍질", "양파 껍질", "생선 가시", "고추장"], 0),

            ("3", "다음 중 종이로 배출할 수 없는 것은?", 
             ["각종 고지서", "과자박스", "영수증", "포스트잇"], 2),

            ("4", "다음 보기 중 재활용이 가능한 것은?", 
             ["우산", "커피 캡슐", "치약 튜브", "빨대"], 2),

            # ------------------------
            # 📌 새롭게 추가된 5~8번 퀴즈
            #     → 정답이 곧 분리배출 방법
            # ------------------------

            ("5", "부피가 큰 화분을 버릴 때 가장 올바른 방법은?",
             [
                 "대형폐기물로 신고 후 배출한다.",
                 "깨뜨려서 마대자루에 넣어 버린다.",
                 "흙을 털고 플라스틱 재활용으로 버린다.",
                 "음식물 쓰레기와 함께 버린다.",
             ],
             0),

            ("6", "고추장·간장·쌈장처럼 염분이 많은 장류를 버릴 때 올바른 방법은?",
             [
                 "음식물 쓰레기 수거함에 그대로 부어 버린다.",
                 "물을 섞어 하수구로 흘려보낸다.",
                 "내용물을 최대한 비우고 종량제 봉투에 넣어 일반쓰레기로 버린다.",
                 "플라스틱 재활용 배출함에 넣는다.",
             ],
             2),

            ("7", "사용이 끝난 칫솔을 버릴 때 가장 올바른 분리배출 방법은?",
             [
                 "플라스틱류 재활용으로 분리배출한다.",
                 "금속류 재활용으로 버린다.",
                 "유리류 재활용으로 버린다.",
                 "일반쓰레기(종량제 봉투)에 담아 버린다.",
             ],
             3),

            ("8", "패스트푸드 컵의 뚜껑과 빨대를 버릴 때 올바른 방법은?",
             [
                 "둘 다 플라스틱 재활용으로 버린다.",
                 "뚜껑은 플라스틱 재활용, 빨대는 일반쓰레기로 버린다.",
                 "둘 다 일반쓰레기로 버린다.",
                 "뚜껑은 종이류, 빨대는 플라스틱류로 버린다.",
             ],
             1),
        ]

        for item_name, question, options, answer_idx in data:
            options_json = json.dumps(options, ensure_ascii=False)
            cur.execute(
                """
                INSERT INTO quizzes (item_name, question, options, answer_idx)
                VALUES (?, ?, ?, ?)
                """,
                (item_name, question, options_json, answer_idx),
            )
        conn.commit()

    conn.close()



# ---------------- 미션 progress/조건 체크 ----------------

def get_mission_id_by_code(code: str) -> int | None:
    """missions.code 로 missions.id 조회. 없으면 None."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM missions WHERE code = ?",
        (code,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None
    return row[0]


def add_mission_progress(user_id: int, mission_code: str, delta: int = 1):
    """
    오늘 날짜 기준으로 해당 유저/미션의 count를 delta 만큼 증가.
    예) 퀴즈 1개 풀었을 때: add_mission_progress(user_id, "1", 1)
    """
    mission_id = get_mission_id_by_code(mission_code)
    if mission_id is None:
        return

    today = datetime.now().date().isoformat()
    now = datetime.now().isoformat(timespec="seconds")

    conn = get_conn()
    cur = conn.cursor()

    # 오늘 row 있는지 확인
    cur.execute(
        """
        SELECT count
        FROM mission_action
        WHERE user_id = ? AND mission_id = ? AND date = ?
        """,
        (user_id, mission_id, today),
    )
    row = cur.fetchone()

    if row is None:
        # 새 row
        cur.execute(
            """
            INSERT INTO mission_action (user_id, mission_id, date, count, data_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, mission_id, today, delta, None, now),
        )
    else:
        # count 증가
        cur.execute(
            """
            UPDATE mission_action
            SET count = count + ? 
            WHERE user_id = ? AND mission_id = ? AND date = ?
            """,
            (delta, user_id, mission_id, today),
        )

    conn.commit()
    conn.close()


def log_mission_action(user_id: int, mission_code: str, data: dict | None = None):
    """
    행동 1회 기록 + 추가 정보 JSON 저장.
    (내부적으로 count 1 증가하는 효과)
    """
    mission_id = get_mission_id_by_code(mission_code)
    if mission_id is None:
        return

    today = datetime.now().date().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    data_json = json.dumps(data, ensure_ascii=False) if data is not None else None

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT count
        FROM mission_action
        WHERE user_id = ? AND mission_id = ? AND date = ?
        """,
        (user_id, mission_id, today),
    )
    row = cur.fetchone()

    if row is None:
        cur.execute(
            """
            INSERT INTO mission_action (user_id, mission_id, date, count, data_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, mission_id, today, 1, data_json, now),
        )
    else:
        cur.execute(
            """
            UPDATE mission_action
            SET count = count + 1, data_json = ?
            WHERE user_id = ? AND mission_id = ? AND date = ?
            """,
            (data_json, user_id, mission_id, today),
        )

    conn.commit()
    conn.close()


def get_mission_progress_today(user_id: int, mission_code: str) -> int:
    """
    오늘 해당 미션에 대해 누적된 count를 반환.
    (없으면 0)
    """
    mission_id = get_mission_id_by_code(mission_code)
    if mission_id is None:
        return 0

    today = datetime.now().date().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT count
        FROM mission_action
        WHERE user_id = ? AND mission_id = ? AND date = ?
        """,
        (user_id, mission_id, today),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return 0
    return row[0] or 0


def has_enough_actions_today(user_id: int, mission_code: str, required_count: int) -> bool:
    """
    오늘 특정 미션에 대해 count가 required_count 이상인지 확인.
    예) '퀴즈 3개 이상 풀기' → has_enough_actions_today(user_id, "1", 3)
    """
    cnt = get_mission_progress_today(user_id, mission_code)
    return cnt >= required_count
