import sqlite3
from pathlib import Path
from datetime import datetime
import bcrypt
from datetime import datetime
import json

# 이거 그냥 리팩토링 해버리는게 더 나을 것 같기도 하고... 괜히 gpt한테 일임한 것 같다는 생각이 드는데.
# 근데 리팩토링 하면 home.py에서 고쳐야할게 늘어서... 가능성 체크해보고 해야할 듯.

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
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            mission_id  INTEGER NOT NULL,
            date        TEXT NOT NULL,
            completed   INTEGER NOT NULL DEFAULT 0,
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

    # 🔹 유저별 일일 퀴즈 기록 테이블  ⬅⬅⬅ 여기 추가
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_daily_quiz (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            date      TEXT    NOT NULL,   -- YYYY-MM-DD
            solved    INTEGER NOT NULL DEFAULT 0,  -- 오늘 퀴즈 클리어 여부 (0/1)
            solved_at TEXT,               -- 처음 클리어한 시각
            UNIQUE(user_id, date),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    # 🔹 미션 수행 로그 테이블 (어떤 행동으로 미션을 했는지 기록)   이거때문이구나 찾았다 범인!!! date와 date_json사이
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mission_action (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            mission_id  INTEGER NOT NULL,
            date        TEXT NOT NULL,        -- YYYY-MM-DD 기준
            data_json   TEXT,                 -- JSON 문자열(추가 정보: 퀴즈 id, 정답 여부 등)
            count      INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, mission_id, date),
            created_at  TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        )
        """
    )

#            action_type TEXT NOT NULL,        -- 예: 'quiz_solved', 'qa_asked'

    conn.commit()
    conn.close()

def create_user(username: str, password: str, region: str | None = None):
    """회원가입: username, password, region 저장"""
    conn = get_conn()
    cur = conn.cursor()

    # 비밀번호 해시
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
    """
    로그인 시도.
    성공하면 user_id(int) 반환, 실패하면 None 반환.
    """
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
            ("3", "일일 미션 전부 완수하기", 150)
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
                "code": r[2],           # ← 미션 코드 추가됨
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
            "code": r[2],           # ← 코드 명확하게 포함
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
    """
    사용자가 선택한 보기 인덱스가 정답인지 확인.
    """
    quiz = get_quiz_by_id(quiz_id)
    if quiz is None:
        return False
    return quiz["answer_idx"] == selected_idx

def has_solved_quiz_today(user_id: int) -> bool:
    """
    해당 유저가 '오늘 일일 퀴즈를 이미 클리어했는지' 여부를 반환.
    (포인트 지급 여부 판단용)
    """
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

    # 이미 기록이 있는지 확인
    cur.execute(
        """
        SELECT id FROM user_daily_quiz
        WHERE user_id = ? AND date = ?
        """,
        (user_id, today),
    )
    row = cur.fetchone()

    if row is None:
        # 오늘 처음 기록
        cur.execute(
            """
            INSERT INTO user_daily_quiz (user_id, date, solved, solved_at)
            VALUES (?, ?, 1, ?)
            """,
            (user_id, today, now),
        )
    else:
        # 기록은 있는데 solved만 1로 갱신
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
    """
    오늘 유저의 일일 퀴즈 기록을 딕셔너리 형태로 반환.
    없으면 None.
    """
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

def get_mission_id_by_code(code: str) -> int | None:
    """
    missions.code 로 missions.id 조회.
    없으면 None.
    """
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
        return  # 미션 코드가 없는 경우는 그냥 무시

    today = datetime.now().date().isoformat()

    conn = get_conn()
    cur = conn.cursor()

    # 먼저 오늘 row가 있는지 확인
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
        # 오늘 처음 기록하는 경우 → 새 row 삽입
        cur.execute(
            """
            INSERT INTO mission_action (user_id, mission_id, date, count)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, mission_id, today, delta),
        )
    else:
        # 이미 있으면 count 증가
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

def log_mission_action(
    user_id: int,
    mission_code: str,
    data: dict | None = None,
):
    """
    특정 미션과 관련된 '행동'을 기록.
    예)
      - mission_code='1', data={'quiz_id': 3, 'correct': True}
      - mission_code='2', data={'query': '종이컵 버리는 법'}
    """
    mission_id = get_mission_id_by_code(mission_code)
    if mission_id is None:
        # 정의되지 않은 미션 코드면 그냥 무시하거나 에러를 던져도 됨
        return

    today = datetime.now().date().isoformat()
    now = datetime.now().isoformat(timespec="seconds")

    data_json = json.dumps(data, ensure_ascii=False) if data is not None else None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO mission_actions (user_id, mission_id, date, data_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, mission_id, today, data_json, now),
    )
    conn.commit()
    conn.close()

def count_mission_actions_today(
    user_id: int,
    mission_code: str
) -> int:
    """
    오늘 날짜 기준으로 특정 미션에 대해 기록된 행동 수를 반환.
    action_type 을 지정하면 그 종류만 세고,
    None 이면 해당 미션에 대한 모든 행동을 센다.
    """
    mission_id = get_mission_id_by_code(mission_code)
    if mission_id is None:
        return 0

    today = datetime.now().date().isoformat()
    conn = get_conn()
    cur = conn.cursor()

#    if action_type is None:
#        cur.execute(
#            """
#            SELECT COUNT(*)
#            FROM mission_actions
#            WHERE user_id = ? AND mission_id = ? AND date = ?
#            """,
#            (user_id, mission_id, today),
#        )
#    else:
    cur.execute(
        """
        SELECT COUNT(*)
        FROM mission_actions
        WHERE user_id = ? AND mission_id = ? AND date = ?
        """,
        (user_id, mission_id, today),
    )

    (cnt,) = cur.fetchone()
    conn.close()
    return cnt or 0

def has_enough_actions_today(
    user_id: int,
    mission_code: str,
    required_count: int,
) -> bool:
    """
    오늘 특정 미션에 대해 일정 횟수 이상 행동이 있었는지 여부 반환.
    예) 미션 '1'에 대해 quiz_solved 3번 이상 -> True
    """
    cnt = count_mission_actions_today(user_id, mission_code)
    return cnt >= required_count
