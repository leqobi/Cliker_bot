import sqlite3
import time
import math
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "clicker.db"

BASE_CLICK_UPGRADE_COST = 50
CLICK_UPGRADE_MULTIPLIER = 2.2
MAX_CLICK_LEVEL = 20

BASE_STAMINA_MAX = 1500
STAMINA_REGEN_PER_SEC = 2
BASE_STAMINA_UPGRADE_COST = 80
STAMINA_UPGRADE_MULTIPLIER = 1.8
MAX_STAMINA_LEVEL = 15
STAMINA_MAX_PER_LEVEL = 300

PRESTIGE_BOOST_PER_LEVEL = 0.6

CELESTIAL_OBJECTS = [
    {"id": 0, "name": "Меркурий", "category": "planet", "threshold": 2000, "image": "mercury.png"},
    {"id": 1, "name": "Венера", "category": "planet", "threshold": 3000, "image": "venus.png"},
    {"id": 2, "name": "Марс", "category": "planet", "threshold": 4500, "image": "mars.png"},
    {"id": 3, "name": "Юпитер", "category": "planet", "threshold": 7000, "image": "jupiter.png"},
    {"id": 4, "name": "Сатурн", "category": "planet", "threshold": 10000, "image": "saturn.png"},
    {"id": 5, "name": "Альфа Центавра", "category": "star", "threshold": 15000, "image": "alpha_centauri.png"},
    {"id": 6, "name": "Проксима Центавра", "category": "star", "threshold": 22000, "image": "proxima_centauri.png"},
    {"id": 7, "name": "Сириус", "category": "star", "threshold": 32000, "image": "sirius.png"},
    {"id": 8, "name": "Бетельгейзе", "category": "star", "threshold": 47000, "image": "betelgeuse.png"},
    {"id": 9, "name": "Ригель", "category": "star", "threshold": 68000, "image": "rigel.png"},
    {"id": 10, "name": "Вега", "category": "star", "threshold": 98000, "image": "vega.png"},
    {"id": 11, "name": "Белый карлик", "category": "star", "threshold": 142000, "image": "white_dwarf.png"},
    {"id": 12, "name": "Нейтронная звезда", "category": "star", "threshold": 205000, "image": "neutron_star.png"},
    {"id": 13, "name": "Магнетар", "category": "star", "threshold": 295000, "image": "magnetar.png"},
    {"id": 14, "name": "Чёрная дыра", "category": "blackhole", "threshold": 425000, "image": "black_hole.png"},
    {"id": 15, "name": "Сверхмассивная чёрная дыра", "category": "blackhole", "threshold": 610000, "image": "supermassive_black_hole.png"},
    {"id": 16, "name": "Квазар", "category": "blackhole", "threshold": None, "image": "quasar.png"},
]


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                click_level INTEGER NOT NULL DEFAULT 1,
                stamina_level INTEGER NOT NULL DEFAULT 1,
                stamina REAL NOT NULL DEFAULT 1500,
                last_stamina_update REAL NOT NULL DEFAULT 0,
                object_index INTEGER NOT NULL DEFAULT 0,
                object_progress INTEGER NOT NULL DEFAULT 0,
                prestige_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


init_db()


def get_click_power(click_level: int) -> int:
    return click_level


def get_click_upgrade_cost(current_level: int) -> int:
    if current_level >= MAX_CLICK_LEVEL:
        return -1
    return math.ceil(BASE_CLICK_UPGRADE_COST * (CLICK_UPGRADE_MULTIPLIER ** (current_level - 1)))


def get_stamina_max(stamina_level: int) -> int:
    return BASE_STAMINA_MAX + (stamina_level - 1) * STAMINA_MAX_PER_LEVEL


def get_stamina_upgrade_cost(current_level: int) -> int:
    if current_level >= MAX_STAMINA_LEVEL:
        return -1
    return math.ceil(BASE_STAMINA_UPGRADE_COST * (STAMINA_UPGRADE_MULTIPLIER ** (current_level - 1)))


def calculate_current_stamina(stored_stamina: float, last_update: float, stamina_max: int) -> float:
    if last_update == 0:
        return stamina_max
    elapsed = time.time() - last_update
    regenerated = elapsed * STAMINA_REGEN_PER_SEC
    return min(stamina_max, stored_stamina + regenerated)


def get_prestige_multiplier(prestige_count: int) -> float:
    return 1 + prestige_count * PRESTIGE_BOOST_PER_LEVEL


def get_or_create_user(conn, user_id: int):
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        stamina_max = get_stamina_max(1)
        conn.execute(
            """INSERT INTO users
               (user_id, balance, click_level, stamina_level, stamina, last_stamina_update, object_index, object_progress, prestige_count)
               VALUES (?, 0, 1, 1, ?, ?, 0, 0, 0)""",
            (user_id, stamina_max, time.time()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return row


def user_to_dict(row) -> dict:
    stamina_max = get_stamina_max(row["stamina_level"])
    current_stamina = calculate_current_stamina(row["stamina"], row["last_stamina_update"], stamina_max)
    obj_index = row["object_index"]
    current_object = CELESTIAL_OBJECTS[obj_index]

    return {
        "user_id": row["user_id"],
        "balance": row["balance"],
        "click_level": row["click_level"],
        "click_power": get_click_power(row["click_level"]),
        "click_upgrade_cost": get_click_upgrade_cost(row["click_level"]),
        "stamina": round(current_stamina),
        "stamina_max": stamina_max,
        "stamina_level": row["stamina_level"],
        "stamina_upgrade_cost": get_stamina_upgrade_cost(row["stamina_level"]),
        "object_index": obj_index,
        "object_name": current_object["name"],
        "object_category": current_object["category"],
        "object_progress": row["object_progress"],
        "object_threshold": current_object["threshold"],
        "prestige_count": row["prestige_count"],
        "prestige_multiplier": get_prestige_multiplier(row["prestige_count"]),
        "can_prestige": current_object["threshold"] is not None and row["object_progress"] >= current_object["threshold"],
        "is_final_object": current_object["threshold"] is None,
    }


class ClickRequest(BaseModel):
    user_id: int
    taps: int = 1


class UpgradeRequest(BaseModel):
    user_id: int


@app.get("/api/state/{user_id}")
def get_state(user_id: int):
    with get_db() as conn:
        row = get_or_create_user(conn, user_id)
        return user_to_dict(row)


@app.post("/api/click")
def click(data: ClickRequest):
    with get_db() as conn:
        row = get_or_create_user(conn, data.user_id)
        stamina_max = get_stamina_max(row["stamina_level"])
        current_stamina = calculate_current_stamina(row["stamina"], row["last_stamina_update"], stamina_max)

        actual_taps = min(data.taps, math.floor(current_stamina))
        if actual_taps <= 0:
            raise HTTPException(status_code=400, detail="Недостаточно стамины")

        click_power = get_click_power(row["click_level"])
        prestige_mult = get_prestige_multiplier(row["prestige_count"])
        earned = round(actual_taps * click_power * prestige_mult)
        new_stamina = current_stamina - actual_taps
        new_progress = row["object_progress"] + actual_taps

        conn.execute(
            """
            UPDATE users
            SET balance = balance + ?, stamina = ?, last_stamina_update = ?, object_progress = ?
            WHERE user_id = ?
            """,
            (earned, new_stamina, time.time(), new_progress, data.user_id),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (data.user_id,)).fetchone()
        result = user_to_dict(row)
        result["accepted_taps"] = actual_taps
        result["earned"] = earned
        return result


@app.post("/api/upgrade/click")
def upgrade_click(data: UpgradeRequest):
    with get_db() as conn:
        row = get_or_create_user(conn, data.user_id)
        cost = get_click_upgrade_cost(row["click_level"])
        if cost == -1:
            raise HTTPException(status_code=400, detail="Достигнут максимальный уровень")
        if row["balance"] < cost:
            raise HTTPException(status_code=400, detail="Недостаточно монет")

        conn.execute(
            "UPDATE users SET balance = balance - ?, click_level = click_level + 1 WHERE user_id = ?",
            (cost, data.user_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (data.user_id,)).fetchone()
        return user_to_dict(row)


@app.post("/api/upgrade/stamina")
def upgrade_stamina(data: UpgradeRequest):
    with get_db() as conn:
        row = get_or_create_user(conn, data.user_id)
        cost = get_stamina_upgrade_cost(row["stamina_level"])
        if cost == -1:
            raise HTTPException(status_code=400, detail="Достигнут максимальный уровень")
        if row["balance"] < cost:
            raise HTTPException(status_code=400, detail="Недостаточно монет")

        old_max = get_stamina_max(row["stamina_level"])
        current_stamina = calculate_current_stamina(row["stamina"], row["last_stamina_update"], old_max)

        conn.execute(
            """
            UPDATE users
            SET balance = balance - ?, stamina_level = stamina_level + 1,
                stamina = ?, last_stamina_update = ?
            WHERE user_id = ?
            """,
            (cost, current_stamina, time.time(), data.user_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (data.user_id,)).fetchone()
        return user_to_dict(row)


@app.post("/api/prestige")
def prestige(data: UpgradeRequest):
    with get_db() as conn:
        row = get_or_create_user(conn, data.user_id)
        current_object = CELESTIAL_OBJECTS[row["object_index"]]

        if current_object["threshold"] is None:
            raise HTTPException(status_code=400, detail="Это финальный объект, дальше лететь некуда")
        if row["object_progress"] < current_object["threshold"]:
            raise HTTPException(status_code=400, detail="Ещё не набран порог для перехода")

        next_index = row["object_index"] + 1
        new_prestige_count = row["prestige_count"] + 1

        conn.execute(
            """
            UPDATE users
            SET click_level = 1, stamina_level = 1, stamina = ?, last_stamina_update = ?,
                object_index = ?, object_progress = 0, prestige_count = ?
            WHERE user_id = ?
            """,
            (get_stamina_max(1), time.time(), next_index, new_prestige_count, data.user_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (data.user_id,)).fetchone()
        return user_to_dict(row)


@app.get("/api/objects")
def get_objects_list():
    return CELESTIAL_OBJECTS


@app.get("/api/leaderboard")
def leaderboard():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10"
        ).fetchall()
    return [{"user_id": r["user_id"], "balance": r["balance"]} for r in rows]


app.mount("/", StaticFiles(directory="static", html=True), name="static")
