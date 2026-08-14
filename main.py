import math
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# ============================================================
# SUNDERED STAR — BACKEND
# ============================================================

app = FastAPI(title="Sundered Star API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "clicker.db"


# ============================================================
# DATABASE
# ============================================================

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        yield conn
    finally:
        conn.close()


# ============================================================
# GAME CONSTANTS
# ============================================================

BASE_CLICK_UPGRADE_COST = 75
CLICK_UPGRADE_MULTIPLIER = 1.75
MAX_CLICK_LEVEL = 20

BASE_STAMINA_MAX = 2000
STAMINA_REGEN_PER_SEC = 3

BASE_STAMINA_UPGRADE_COST = 150
STAMINA_UPGRADE_MULTIPLIER = 1.65
MAX_STAMINA_LEVEL = 15
STAMINA_MAX_PER_LEVEL = 400

PRESTIGE_BOOST_PER_LEVEL = 0.25

DAILY_BONUS_BASE = 250
DAILY_BONUS_PER_DAY = 100
DAILY_BONUS_MAX_STREAK_DAY = 7

SECONDS_IN_DAY = 86400

REFERRAL_START_BONUS = 1500
REFERRAL_PERCENT = 0.07
REFERRAL_PERIOD = 7 * SECONDS_IN_DAY
REFERRAL_MAX_WEEKLY_REWARD = 100000

SUPPORTED_LANGUAGES = {"ru", "en"}
DEFAULT_LANGUAGE = "ru"


# ============================================================
# CELESTIAL OBJECTS
# ============================================================

CELESTIAL_OBJECTS = [
    {
        "id": 0,
        "name": "Меркурий",
        "category": "planet",
        "threshold": 2500,
        "image": "mercury.png",
    },
    {
        "id": 1,
        "name": "Венера",
        "category": "planet",
        "threshold": 6000,
        "image": "venus.png",
    },
    {
        "id": 2,
        "name": "Марс",
        "category": "planet",
        "threshold": 12000,
        "image": "mars.png",
    },
    {
        "id": 3,
        "name": "Юпитер",
        "category": "planet",
        "threshold": 25000,
        "image": "jupiter.png",
    },
    {
        "id": 4,
        "name": "Сатурн",
        "category": "planet",
        "threshold": 50000,
        "image": "saturn.png",
    },
    {
        "id": 5,
        "name": "Альфа Центавра",
        "category": "star",
        "threshold": 90000,
        "image": "alpha_centauri.png",
    },
    {
        "id": 6,
        "name": "Проксима Центавра",
        "category": "star",
        "threshold": 150000,
        "image": "proxima_centauri.png",
    },
    {
        "id": 7,
        "name": "Сириус",
        "category": "star",
        "threshold": 240000,
        "image": "sirius.png",
    },
    {
        "id": 8,
        "name": "Бетельгейзе",
        "category": "star",
        "threshold": 375000,
        "image": "betelgeuse.png",
    },
    {
        "id": 9,
        "name": "Ригель",
        "category": "star",
        "threshold": 575000,
        "image": "rigel.png",
    },
    {
        "id": 10,
        "name": "Вега",
        "category": "star",
        "threshold": 850000,
        "image": "vega.png",
    },
    {
        "id": 11,
        "name": "Белый карлик",
        "category": "star",
        "threshold": 1250000,
        "image": "white_dwarf.png",
    },
    {
        "id": 12,
        "name": "Нейтронная звезда",
        "category": "star",
        "threshold": 1850000,
        "image": "neutron_star.png",
    },
    {
        "id": 13,
        "name": "Магнетар",
        "category": "star",
        "threshold": 2750000,
        "image": "magnetar.png",
    },
    {
        "id": 14,
        "name": "Чёрная дыра",
        "category": "blackhole",
        "threshold": 4100000,
        "image": "black_hole.png",
    },
    {
        "id": 15,
        "name": "Сверхмассивная чёрная дыра",
        "category": "blackhole",
        "threshold": 6200000,
        "image": "supermassive_black_hole.png",
    },
    {
        "id": 16,
        "name": "Квазар",
        "category": "blackhole",
        "threshold": None,
        "image": "quasar.png",
    },
]


# ============================================================
# DATABASE HELPERS
# ============================================================

def column_exists(conn, table_name, column_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(row["name"] == column_name for row in rows)


def add_column_if_missing(
    conn,
    table_name,
    column_name,
    definition,
):
    if not column_exists(conn, table_name, column_name):
        conn.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {definition}"
        )


def init_db():
    with get_db() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,

                balance INTEGER NOT NULL DEFAULT 0,

                click_level INTEGER NOT NULL DEFAULT 1,
                stamina_level INTEGER NOT NULL DEFAULT 1,

                stamina REAL NOT NULL DEFAULT 2000,
                last_stamina_update REAL NOT NULL DEFAULT 0,

                object_index INTEGER NOT NULL DEFAULT 0,
                object_progress INTEGER NOT NULL DEFAULT 0,

                prestige_count INTEGER NOT NULL DEFAULT 0,

                daily_streak INTEGER NOT NULL DEFAULT 0,
                last_daily_claim REAL NOT NULL DEFAULT 0,

                telegram_username TEXT DEFAULT NULL,
                telegram_first_name TEXT DEFAULT NULL,
                telegram_last_name TEXT DEFAULT NULL,

                total_click_earnings INTEGER NOT NULL DEFAULT 0,

                created_at REAL NOT NULL DEFAULT 0,

                language TEXT NOT NULL DEFAULT 'ru'
            )
            """
        )

        # ----------------------------------------------------
        # Migrations for old databases
        # ----------------------------------------------------

        add_column_if_missing(
            conn,
            "users",
            "telegram_username",
            "TEXT DEFAULT NULL",
        )

        add_column_if_missing(
            conn,
            "users",
            "telegram_first_name",
            "TEXT DEFAULT NULL",
        )

        add_column_if_missing(
            conn,
            "users",
            "telegram_last_name",
            "TEXT DEFAULT NULL",
        )

        add_column_if_missing(
            conn,
            "users",
            "total_click_earnings",
            "INTEGER NOT NULL DEFAULT 0",
        )

        add_column_if_missing(
            conn,
            "users",
            "created_at",
            "REAL NOT NULL DEFAULT 0",
        )

        add_column_if_missing(
            conn,
            "users",
            "language",
            "TEXT NOT NULL DEFAULT 'ru'",
        )

        # ----------------------------------------------------
        # Fix invalid language values from old database
        # ----------------------------------------------------

        conn.execute(
            """
            UPDATE users
            SET language = ?
            WHERE language IS NULL
               OR language NOT IN ('ru', 'en')
            """,
            (DEFAULT_LANGUAGE,),
        )

        # ----------------------------------------------------
        # Fix invalid numeric values from old versions
        # ----------------------------------------------------

        conn.execute(
            """
            UPDATE users
            SET click_level = 1
            WHERE click_level < 1
               OR click_level > ?
            """,
            (MAX_CLICK_LEVEL,),
        )

        conn.execute(
            """
            UPDATE users
            SET stamina_level = 1
            WHERE stamina_level < 1
               OR stamina_level > ?
            """,
            (MAX_STAMINA_LEVEL,),
        )

        conn.execute(
            """
            UPDATE users
            SET balance = 0
            WHERE balance < 0
            """
        )

        conn.execute(
            """
            UPDATE users
            SET object_index = 0
            WHERE object_index < 0
            """
        )

        conn.execute(
            """
            UPDATE users
            SET object_index = ?
            WHERE object_index >= ?
            """,
            (
                len(CELESTIAL_OBJECTS) - 1,
                len(CELESTIAL_OBJECTS),
            ),
        )

        conn.execute(
            """
            UPDATE users
            SET object_progress = 0
            WHERE object_progress < 0
            """
        )

        # ----------------------------------------------------
        # Referrals
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS referrals(
                referred_id INTEGER PRIMARY KEY,
                referrer_id INTEGER NOT NULL,

                created_at REAL NOT NULL,

                signup_bonus INTEGER NOT NULL DEFAULT 1500,

                weekly_click_baseline INTEGER NOT NULL DEFAULT 0,

                total_paid INTEGER NOT NULL DEFAULT 0,

                last_payout_at REAL NOT NULL DEFAULT 0,

                FOREIGN KEY(referred_id)
                    REFERENCES users(user_id),

                FOREIGN KEY(referrer_id)
                    REFERENCES users(user_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_payments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,

                period_start REAL NOT NULL,
                period_end REAL NOT NULL,

                click_earnings INTEGER NOT NULL DEFAULT 0,

                reward INTEGER NOT NULL DEFAULT 0,

                created_at REAL NOT NULL
            )
            """
        )

        # ----------------------------------------------------
        # Indexes
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_users_balance
            ON users(balance DESC)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_users_progress
            ON users(object_progress DESC)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_users_prestige
            ON users(prestige_count DESC)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_referrals_referrer
            ON referrals(referrer_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_referral_payments_referrer
            ON referral_payments(referrer_id)
            """
        )

        conn.commit()


init_db()


# ============================================================
# GAME CALCULATIONS
# ============================================================

def get_click_power(level):
    level = max(1, min(int(level), MAX_CLICK_LEVEL))
    return level


def get_click_upgrade_cost(level):
    level = max(1, int(level))

    if level >= MAX_CLICK_LEVEL:
        return -1

    return math.ceil(
        BASE_CLICK_UPGRADE_COST
        * CLICK_UPGRADE_MULTIPLIER ** (level - 1)
    )


def get_stamina_max(level):
    level = max(1, min(int(level), MAX_STAMINA_LEVEL))

    return (
        BASE_STAMINA_MAX
        + (level - 1) * STAMINA_MAX_PER_LEVEL
    )


def get_stamina_upgrade_cost(level):
    level = max(1, int(level))

    if level >= MAX_STAMINA_LEVEL:
        return -1

    return math.ceil(
        BASE_STAMINA_UPGRADE_COST
        * STAMINA_UPGRADE_MULTIPLIER ** (level - 1)
    )


def calculate_current_stamina(
    stored,
    last_update,
    maximum,
):
    stored = max(0.0, float(stored or 0))
    maximum = max(0.0, float(maximum))

    if last_update is None or last_update <= 0:
        return min(stored, maximum)

    elapsed = max(0.0, time.time() - last_update)

    regenerated = (
        stored
        + elapsed * STAMINA_REGEN_PER_SEC
    )

    return min(
        maximum,
        regenerated,
    )


def get_prestige_multiplier(count):
    count = max(0, int(count))

    if count <= 10:
        return 1 + count * PRESTIGE_BOOST_PER_LEVEL

    return (
        3.5
        + (count - 10) * 0.10
    )


def get_daily_bonus_amount(streak):
    streak = max(1, int(streak))

    streak = min(
        streak,
        DAILY_BONUS_MAX_STREAK_DAY,
    )

    return (
        DAILY_BONUS_BASE
        + (streak - 1) * DAILY_BONUS_PER_DAY
    )


def get_daily_status(
    last_claim,
    streak,
):
    last_claim = float(last_claim or 0)
    streak = max(0, int(streak or 0))

    if last_claim <= 0:
        return {
            "can_claim": True,
            "next_streak": 1,
            "hours_until_next": 0,
        }

    elapsed = max(
        0,
        time.time() - last_claim,
    )

    if elapsed < SECONDS_IN_DAY:
        return {
            "can_claim": False,
            "next_streak": max(1, streak),
            "hours_until_next": math.ceil(
                (SECONDS_IN_DAY - elapsed) / 3600
            ),
        }

    if elapsed < 2 * SECONDS_IN_DAY:
        return {
            "can_claim": True,
            "next_streak": min(
                streak + 1,
                DAILY_BONUS_MAX_STREAK_DAY,
            ),
            "hours_until_next": 0,
        }

    return {
        "can_claim": True,
        "next_streak": 1,
        "hours_until_next": 0,
    }


# ============================================================
# USER
# ============================================================

def get_or_create_user(conn, user_id):
    user_id = int(user_id)

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    if row is None:
        now = time.time()

        conn.execute(
            """
            INSERT INTO users(
                user_id,
                balance,
                click_level,
                stamina_level,
                stamina,
                last_stamina_update,
                object_index,
                object_progress,
                prestige_count,
                daily_streak,
                last_daily_claim,
                telegram_username,
                telegram_first_name,
                telegram_last_name,
                total_click_earnings,
                created_at,
                language
            )
            VALUES(
                ?,
                0,
                1,
                1,
                ?,
                ?,
                0,
                0,
                0,
                0,
                0,
                NULL,
                NULL,
                NULL,
                0,
                ?,
                ?
            )
            """,
            (
                user_id,
                get_stamina_max(1),
                now,
                now,
                DEFAULT_LANGUAGE,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    changed = False

    if row["created_at"] <= 0:
        conn.execute(
            """
            UPDATE users
            SET created_at = ?
            WHERE user_id = ?
            """,
            (time.time(), user_id),
        )
        changed = True

    if row["language"] not in SUPPORTED_LANGUAGES:
        conn.execute(
            """
            UPDATE users
            SET language = ?
            WHERE user_id = ?
            """,
            (DEFAULT_LANGUAGE, user_id),
        )
        changed = True

    if row["click_level"] < 1:
        conn.execute(
            """
            UPDATE users
            SET click_level = 1
            WHERE user_id = ?
            """,
            (user_id,),
        )
        changed = True

    if row["click_level"] > MAX_CLICK_LEVEL:
        conn.execute(
            """
            UPDATE users
            SET click_level = ?
            WHERE user_id = ?
            """,
            (MAX_CLICK_LEVEL, user_id),
        )
        changed = True

    if row["stamina_level"] < 1:
        conn.execute(
            """
            UPDATE users
            SET stamina_level = 1
            WHERE user_id = ?
            """,
            (user_id,),
        )
        changed = True

    if row["stamina_level"] > MAX_STAMINA_LEVEL:
        conn.execute(
            """
            UPDATE users
            SET stamina_level = ?
            WHERE user_id = ?
            """,
            (MAX_STAMINA_LEVEL, user_id),
        )
        changed = True

    if changed:
        conn.commit()

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    return row


def state_row(conn, user_id):
    return conn.execute(
        """
        SELECT *
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()


# ============================================================
# REFERRALS
# ============================================================

def settle_referral_for_referred(
    conn,
    referred_id,
):
    referral = conn.execute(
        """
        SELECT *
        FROM referrals
        WHERE referred_id = ?
        """,
        (referred_id,),
    ).fetchone()

    if referral is None:
        return 0

    now = time.time()

    last_payout = (
        referral["last_payout_at"]
        if referral["last_payout_at"] > 0
        else referral["created_at"]
    )

    if now - last_payout < REFERRAL_PERIOD:
        return 0

    user = conn.execute(
        """
        SELECT total_click_earnings
        FROM users
        WHERE user_id = ?
        """,
        (referred_id,),
    ).fetchone()

    if user is None:
        return 0

    delta = max(
        0,
        user["total_click_earnings"]
        - referral["weekly_click_baseline"],
    )

    reward = min(
        math.floor(delta * REFERRAL_PERCENT),
        REFERRAL_MAX_WEEKLY_REWARD,
    )

    if reward > 0:
        conn.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
            """,
            (
                reward,
                referral["referrer_id"],
            ),
        )

        conn.execute(
            """
            INSERT INTO referral_payments(
                referrer_id,
                referred_id,
                period_start,
                period_end,
                click_earnings,
                reward,
                created_at
            )
            VALUES(
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                referral["referrer_id"],
                referred_id,
                last_payout,
                now,
                delta,
                reward,
                now,
            ),
        )

    conn.execute(
        """
        UPDATE referrals
        SET
            weekly_click_baseline = ?,
            total_paid = total_paid + ?,
            last_payout_at = ?
        WHERE referred_id = ?
        """,
        (
            user["total_click_earnings"],
            reward,
            now,
            referred_id,
        ),
    )

    conn.commit()

    return reward


def settle_all_referrals_for_referrer(
    conn,
    referrer_id,
):
    rows = conn.execute(
        """
        SELECT referred_id
        FROM referrals
        WHERE referrer_id = ?
        """,
        (referrer_id,),
    ).fetchall()

    total = 0

    for row in rows:
        total += settle_referral_for_referred(
            conn,
            row["referred_id"],
        )

    return total


def get_referral_stats(conn, user_id):
    count = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM referrals
        WHERE referrer_id = ?
        """,
        (user_id,),
    ).fetchone()["total"]

    paid = conn.execute(
        """
        SELECT COALESCE(SUM(reward), 0) AS total
        FROM referral_payments
        WHERE referrer_id = ?
        """,
        (user_id,),
    ).fetchone()["total"]

    return {
        "count": count,
        "total_earned": paid,
    }


# ============================================================
# STATE SERIALIZATION
# ============================================================

def user_to_dict(row, conn):
    stamina_max = get_stamina_max(
        row["stamina_level"]
    )

    stamina = calculate_current_stamina(
        row["stamina"],
        row["last_stamina_update"],
        stamina_max,
    )

    object_index = max(
        0,
        min(
            int(row["object_index"]),
            len(CELESTIAL_OBJECTS) - 1,
        ),
    )

    obj = CELESTIAL_OBJECTS[object_index]

    daily_status = get_daily_status(
        row["last_daily_claim"],
        row["daily_streak"],
    )

    referral_stats = get_referral_stats(
        conn,
        row["user_id"],
    )

    if row["telegram_username"]:
        display_name = (
            "@" + row["telegram_username"]
        )
    elif row["telegram_first_name"]:
        display_name = row["telegram_first_name"]
    else:
        display_name = (
            f"Исследователь #{row['user_id']}"
        )

    language = row["language"]

    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    return {
        "user_id": row["user_id"],

        "username": row["telegram_username"],
        "first_name": row["telegram_first_name"],
        "last_name": row["telegram_last_name"],
        "display_name": display_name,

        "language": language,
        "supported_languages": [
            "ru",
            "en",
        ],

        "balance": max(
            0,
            int(row["balance"]),
        ),

        "click_level": row["click_level"],
        "click_power": get_click_power(
            row["click_level"]
        ),
        "click_upgrade_cost": get_click_upgrade_cost(
            row["click_level"]
        ),

        "stamina": round(
            max(0, stamina)
        ),
        "stamina_max": stamina_max,
        "stamina_level": row["stamina_level"],
        "stamina_upgrade_cost": get_stamina_upgrade_cost(
            row["stamina_level"]
        ),
        "stamina_regen_per_sec": STAMINA_REGEN_PER_SEC,

        "object_index": object_index,
        "object_name": obj["name"],
        "object_category": obj["category"],
        "object_image": obj["image"],

        "object_progress": max(
            0,
            int(row["object_progress"]),
        ),

        "object_threshold": obj["threshold"],

        "prestige_count": row["prestige_count"],
        "prestige_multiplier": get_prestige_multiplier(
            row["prestige_count"]
        ),

        "can_prestige": (
            obj["threshold"] is not None
            and row["object_progress"] >= obj["threshold"]
        ),

        "is_final_object": (
            obj["threshold"] is None
        ),

        "daily_streak": row["daily_streak"],
        "daily_status": daily_status,
        "daily_next_amount": get_daily_bonus_amount(
            daily_status["next_streak"]
        ),

        "referral_count": referral_stats["count"],
        "referral_total_earned": referral_stats[
            "total_earned"
        ],

        "referral_bonus": REFERRAL_START_BONUS,
        "referral_percent": int(
            REFERRAL_PERCENT * 100
        ),
    }


# ============================================================
# REQUEST MODELS
# ============================================================

class ClickRequest(BaseModel):
    user_id: int = Field(gt=0)
    taps: int = Field(
        default=1,
        ge=1,
        le=1000,
    )


class UpgradeRequest(BaseModel):
    user_id: int = Field(gt=0)


class UserProfileRequest(BaseModel):
    user_id: int = Field(gt=0)

    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class LanguageRequest(BaseModel):
    user_id: int = Field(gt=0)
    language: str


class ReferralRegisterRequest(BaseModel):
    user_id: int = Field(gt=0)
    referrer_id: int = Field(gt=0)


# ============================================================
# STATE
# ============================================================

@app.get("/api/state/{user_id}")
def get_state(user_id: int):
    with get_db() as conn:

        get_or_create_user(
            conn,
            user_id,
        )

        settle_referral_for_referred(
            conn,
            user_id,
        )

        settle_all_referrals_for_referrer(
            conn,
            user_id,
        )

        return user_to_dict(
            state_row(conn, user_id),
            conn,
        )


# ============================================================
# PROFILE
# ============================================================

@app.post("/api/profile")
def update_profile(
    data: UserProfileRequest,
):
    with get_db() as conn:

        get_or_create_user(
            conn,
            data.user_id,
        )

        conn.execute(
            """
            UPDATE users
            SET
                telegram_username = ?,
                telegram_first_name = ?,
                telegram_last_name = ?
            WHERE user_id = ?
            """,
            (
                data.username,
                data.first_name,
                data.last_name,
                data.user_id,
            ),
        )

        conn.commit()

        return user_to_dict(
            state_row(conn, data.user_id),
            conn,
        )


# ============================================================
# LANGUAGE
# ============================================================

@app.get("/api/settings/language/{user_id}")
def get_language(user_id: int):
    with get_db() as conn:

        row = get_or_create_user(
            conn,
            user_id,
        )

        language = row["language"]

        if language not in SUPPORTED_LANGUAGES:
            language = DEFAULT_LANGUAGE

        return {
            "language": language,
            "language_selected": language
            in SUPPORTED_LANGUAGES,
        }


@app.post("/api/language")
def update_language(
    data: LanguageRequest,
):
    language = (
        data.language or ""
    ).strip().lower()

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемый язык. Доступны: ru, en",
        )

    with get_db() as conn:

        get_or_create_user(
            conn,
            data.user_id,
        )

        conn.execute(
            """
            UPDATE users
            SET language = ?
            WHERE user_id = ?
            """,
            (
                language,
                data.user_id,
            ),
        )

        conn.commit()

        return user_to_dict(
            state_row(conn, data.user_id),
            conn,
        )


# ============================================================
# CLICK
# ============================================================

@app.post("/api/click")
def click(data: ClickRequest):
    with get_db() as conn:

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        stamina_max = get_stamina_max(
            row["stamina_level"]
        )

        current_stamina = calculate_current_stamina(
            row["stamina"],
            row["last_stamina_update"],
            stamina_max,
        )

        accepted_taps = min(
            data.taps,
            math.floor(current_stamina),
        )

        if accepted_taps <= 0:
            raise HTTPException(
                status_code=400,
                detail="Недостаточно стамины",
            )

        click_power = get_click_power(
            row["click_level"]
        )

        prestige_multiplier = get_prestige_multiplier(
            row["prestige_count"]
        )

        earned = round(
            accepted_taps
            * click_power
            * prestige_multiplier
        )

        new_stamina = max(
            0,
            current_stamina - accepted_taps,
        )

        now = time.time()

        conn.execute(
            """
            UPDATE users
            SET
                balance = balance + ?,
                stamina = ?,
                last_stamina_update = ?,
                object_progress = object_progress + ?,
                total_click_earnings =
                    total_click_earnings + ?
            WHERE user_id = ?
            """,
            (
                earned,
                new_stamina,
                now,
                earned,
                earned,
                data.user_id,
            ),
        )

        conn.commit()

        result = user_to_dict(
            state_row(conn, data.user_id),
            conn,
        )

        result.update(
            {
                "accepted_taps": accepted_taps,
                "earned": earned,
            }
        )

        return result


# ============================================================
# CLICK UPGRADE
# ============================================================

@app.post("/api/upgrade/click")
def upgrade_click(
    data: UpgradeRequest,
):
    with get_db() as conn:

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        cost = get_click_upgrade_cost(
            row["click_level"]
        )

        if cost == -1:
            raise HTTPException(
                status_code=400,
                detail="Достигнут максимальный уровень",
            )

        if row["balance"] < cost:
            raise HTTPException(
                status_code=400,
                detail="Недостаточно монет",
            )

        conn.execute(
            """
            UPDATE users
            SET
                balance = balance - ?,
                click_level = click_level + 1
            WHERE user_id = ?
            """,
            (
                cost,
                data.user_id,
            ),
        )

        conn.commit()

        return user_to_dict(
            state_row(conn, data.user_id),
            conn,
        )


# ============================================================
# STAMINA UPGRADE
# ============================================================

@app.post("/api/upgrade/stamina")
def upgrade_stamina(
    data: UpgradeRequest,
):
    with get_db() as conn:

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        current_level = row["stamina_level"]

        cost = get_stamina_upgrade_cost(
            current_level
        )

        if cost == -1:
            raise HTTPException(
                status_code=400,
                detail="Достигнут максимальный уровень",
            )

        if row["balance"] < cost:
            raise HTTPException(
                status_code=400,
                detail="Недостаточно монет",
            )

        old_max = get_stamina_max(
            current_level
        )

        current_stamina = calculate_current_stamina(
            row["stamina"],
            row["last_stamina_update"],
            old_max,
        )

        new_level = current_level + 1

        new_max = get_stamina_max(
            new_level
        )

        # Preserve current stamina.
        # Do not unexpectedly refill the whole bar.
        new_stamina = min(
            current_stamina,
            new_max,
        )

        now = time.time()

        conn.execute(
            """
            UPDATE users
            SET
                balance = balance - ?,
                stamina_level = ?,
                stamina = ?,
                last_stamina_update = ?
            WHERE user_id = ?
            """,
            (
                cost,
                new_level,
                new_stamina,
                now,
                data.user_id,
            ),
        )

        conn.commit()

        return user_to_dict(
            state_row(conn, data.user_id),
            conn,
        )


# ============================================================
# PRESTIGE / NEXT OBJECT
# ============================================================

@app.post("/api/prestige")
def prestige(
    data: UpgradeRequest,
):
    with get_db() as conn:

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        object_index = max(
            0,
            min(
                int(row["object_index"]),
                len(CELESTIAL_OBJECTS) - 1,
            ),
        )

        current_object = CELESTIAL_OBJECTS[
            object_index
        ]

        threshold = current_object[
            "threshold"
        ]

        if threshold is None:
            raise HTTPException(
                status_code=400,
                detail="Это финальный объект, дальше лететь некуда",
            )

        if row["object_progress"] < threshold:
            raise HTTPException(
                status_code=400,
                detail="Ещё не набран порог для перехода",
            )

        next_index = object_index + 1

        if next_index >= len(
            CELESTIAL_OBJECTS
        ):
            raise HTTPException(
                status_code=400,
                detail="Следующего объекта не существует",
            )

        new_prestige_count = (
            row["prestige_count"] + 1
        )

        now = time.time()

        # После перехода:
        # - баланс сбрасывается;
        # - улучшения сбрасываются;
        # - стамина возвращается к стартовой;
        # - объект становится следующим;
        # - прогресс нового объекта = 0;
        # - престиж увеличивается.
        #
        # total_click_earnings НЕ сбрасывается,
        # потому что он используется для реферальной
        # статистики.

        conn.execute(
            """
            UPDATE users
            SET
                balance = 0,
                click_level = 1,
                stamina_level = 1,
                stamina = ?,
                last_stamina_update = ?,
                object_index = ?,
                object_progress = 0,
                prestige_count = ?
            WHERE user_id = ?
            """,
            (
                get_stamina_max(1),
                now,
                next_index,
                new_prestige_count,
                data.user_id,
            ),
        )

        conn.commit()

        return user_to_dict(
            state_row(conn, data.user_id),
            conn,
        )


# ============================================================
# DAILY BONUS
# ============================================================

@app.post("/api/daily/claim")
def claim_daily(
    data: UpgradeRequest,
):
    with get_db() as conn:

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        status = get_daily_status(
            row["last_daily_claim"],
            row["daily_streak"],
        )

        if not status["can_claim"]:
            raise HTTPException(
                status_code=400,
                detail="Бонус уже забран сегодня",
            )

        amount = get_daily_bonus_amount(
            status["next_streak"]
        )

        now = time.time()

        conn.execute(
            """
            UPDATE users
            SET
                balance = balance + ?,
                daily_streak = ?,
                last_daily_claim = ?
            WHERE user_id = ?
            """,
            (
                amount,
                status["next_streak"],
                now,
                data.user_id,
            ),
        )

        conn.commit()

        result = user_to_dict(
            state_row(conn, data.user_id),
            conn,
        )

        result["claimed_amount"] = amount

        return result


# ============================================================
# OBJECTS
# ============================================================

@app.get("/api/objects")
def get_objects_list():
    return CELESTIAL_OBJECTS


# ============================================================
# REFERRAL REGISTER
# ============================================================

@app.post("/api/referral/register")
def register_referral(
    data: ReferralRegisterRequest,
):
    if data.user_id == data.referrer_id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя пригласить самого себя",
        )

    with get_db() as conn:

        get_or_create_user(
            conn,
            data.user_id,
        )

        get_or_create_user(
            conn,
            data.referrer_id,
        )

        existing = conn.execute(
            """
            SELECT *
            FROM referrals
            WHERE referred_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        if existing:
            return {
                "success": True,
                "already_registered": True,
                "referrer_id": existing[
                    "referrer_id"
                ],
                "state": user_to_dict(
                    state_row(
                        conn,
                        data.user_id,
                    ),
                    conn,
                ),
            }

        now = time.time()

        baseline_row = conn.execute(
            """
            SELECT total_click_earnings
            FROM users
            WHERE user_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        baseline = (
            baseline_row["total_click_earnings"]
            if baseline_row
            else 0
        )

        # Bonus is given to the referrer.
        conn.execute(
            """
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
            """,
            (
                REFERRAL_START_BONUS,
                data.referrer_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO referrals(
                referred_id,
                referrer_id,
                created_at,
                signup_bonus,
                weekly_click_baseline,
                total_paid,
                last_payout_at
            )
            VALUES(
                ?, ?, ?, ?, ?, 0, ?
            )
            """,
            (
                data.user_id,
                data.referrer_id,
                now,
                REFERRAL_START_BONUS,
                baseline,
                now,
            ),
        )

        conn.commit()

        return {
            "success": True,
            "already_registered": False,
            "referrer_id": data.referrer_id,
            "signup_bonus": REFERRAL_START_BONUS,
            "state": user_to_dict(
                state_row(
                    conn,
                    data.user_id,
                ),
                conn,
            ),
        }


# ============================================================
# REFERRAL INFO
# ============================================================

@app.get("/api/referral/{user_id}")
def referral_info(user_id: int):
    with get_db() as conn:

        get_or_create_user(
            conn,
            user_id,
        )

        settle_referral_for_referred(
            conn,
            user_id,
        )

        settle_all_referrals_for_referrer(
            conn,
            user_id,
        )

        rows = conn.execute(
            """
            SELECT
                r.*,
                u.telegram_username,
                u.telegram_first_name,
                u.total_click_earnings,
                u.object_index,
                u.prestige_count
            FROM referrals r
            JOIN users u
                ON u.user_id = r.referred_id
            WHERE r.referrer_id = ?
            ORDER BY r.created_at DESC
            """,
            (user_id,),
        ).fetchall()

        now = time.time()
        result = []

        for row in rows:

            last_payout = (
                row["last_payout_at"]
                or row["created_at"]
            )

            days_until_payout = math.ceil(
                max(
                    0,
                    REFERRAL_PERIOD
                    - (now - last_payout),
                )
                / SECONDS_IN_DAY
            )

            if row["telegram_username"]:
                name = (
                    "@"
                    + row["telegram_username"]
                )
            elif row["telegram_first_name"]:
                name = row[
                    "telegram_first_name"
                ]
            else:
                name = (
                    f"Исследователь "
                    f"#{row['referred_id']}"
                )

            result.append(
                {
                    "user_id": row[
                        "referred_id"
                    ],
                    "name": name,
                    "created_at": row[
                        "created_at"
                    ],
                    "total_paid": row[
                        "total_paid"
                    ],
                    "total_click_earnings": row[
                        "total_click_earnings"
                    ],
                    "object_index": row[
                        "object_index"
                    ],
                    "prestige_count": row[
                        "prestige_count"
                    ],
                    "days_until_payout":
                        days_until_payout,
                }
            )

        total = conn.execute(
            """
            SELECT COALESCE(
                SUM(reward),
                0
            ) AS total
            FROM referral_payments
            WHERE referrer_id = ?
            """,
            (user_id,),
        ).fetchone()["total"]

        return {
            "referral_bonus":
                REFERRAL_START_BONUS,

            "referral_percent":
                int(REFERRAL_PERCENT * 100),

            "weekly_period_days": 7,

            "weekly_max_reward":
                REFERRAL_MAX_WEEKLY_REWARD,

            "referral_count":
                len(result),

            "total_earned":
                total,

            "referrals":
                result,
        }


# ============================================================
# REFERRAL HISTORY
# ============================================================

@app.get("/api/referral/{user_id}/history")
def referral_history(user_id: int):
    with get_db() as conn:

        get_or_create_user(
            conn,
            user_id,
        )

        rows = conn.execute(
            """
            SELECT
                rp.*,
                u.telegram_username,
                u.telegram_first_name
            FROM referral_payments rp
            LEFT JOIN users u
                ON u.user_id = rp.referred_id
            WHERE rp.referrer_id = ?
            ORDER BY rp.created_at DESC
            LIMIT 50
            """,
            (user_id,),
        ).fetchall()

        result = []

        for row in rows:

            if row["telegram_username"]:
                name = (
                    "@"
                    + row["telegram_username"]
                )
            elif row["telegram_first_name"]:
                name = row[
                    "telegram_first_name"
                ]
            else:
                name = (
                    f"Исследователь "
                    f"#{row['referred_id']}"
                )

            result.append(
                {
                    "id": row["id"],
                    "referred_id": row[
                        "referred_id"
                    ],
                    "referred_name": name,
                    "click_earnings": row[
                        "click_earnings"
                    ],
                    "reward": row["reward"],
                    "created_at": row[
                        "created_at"
                    ],
                }
            )

        return result


# ============================================================
# LEADERBOARD HELPERS
# ============================================================

def safe_idx(index):
    return max(
        0,
        min(
            int(index),
            len(CELESTIAL_OBJECTS) - 1,
        ),
    )


def row_name(row):
    if row["telegram_username"]:
        return "@" + row[
            "telegram_username"
        ]

    if row["telegram_first_name"]:
        return row["telegram_first_name"]

    return (
        f"Исследователь #{row['user_id']}"
    )


# ============================================================
# LEADERBOARD
# ============================================================

@app.get("/api/leaderboard")
def leaderboard(limit: int = 50):

    limit = max(
        1,
        min(int(limit), 100),
    )

    with get_db() as conn:

        balance_rows = conn.execute(
            """
            SELECT
                user_id,
                balance,
                telegram_username,
                telegram_first_name,
                object_index,
                prestige_count
            FROM users
            ORDER BY
                balance DESC,
                user_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        progress_rows = conn.execute(
            """
            SELECT
                user_id,
                object_index,
                object_progress,
                prestige_count,
                telegram_username,
                telegram_first_name
            FROM users
            ORDER BY
                object_index DESC,
                object_progress DESC,
                prestige_count DESC,
                user_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        prestige_rows = conn.execute(
            """
            SELECT
                user_id,
                prestige_count,
                object_index,
                telegram_username,
                telegram_first_name
            FROM users
            ORDER BY
                prestige_count DESC,
                object_index DESC,
                object_progress DESC,
                user_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        balance = []

        for rank, row in enumerate(
            balance_rows,
            1,
        ):
            index = safe_idx(
                row["object_index"]
            )

            balance.append(
                {
                    "rank": rank,
                    "user_id": row[
                        "user_id"
                    ],
                    "name": row_name(row),
                    "balance": row[
                        "balance"
                    ],
                    "object_index": index,
                    "object_name":
                        CELESTIAL_OBJECTS[
                            index
                        ]["name"],
                    "prestige_count":
                        row["prestige_count"],
                }
            )

        progress = []

        for rank, row in enumerate(
            progress_rows,
            1,
        ):
            index = safe_idx(
                row["object_index"]
            )

            obj = CELESTIAL_OBJECTS[
                index
            ]

            threshold = obj[
                "threshold"
            ]

            if threshold is None:
                percent = 100
            else:
                percent = min(
                    100,
                    round(
                        row["object_progress"]
                        / threshold
                        * 100
                    ),
                )

            progress.append(
                {
                    "rank": rank,
                    "user_id": row[
                        "user_id"
                    ],
                    "name": row_name(row),
                    "object_index": index,
                    "object_name": obj[
                        "name"
                    ],
                    "object_progress":
                        row["object_progress"],
                    "object_threshold":
                        threshold,
                    "progress_percent":
                        percent,
                    "prestige_count":
                        row["prestige_count"],
                }
            )

        prestige = []

        for rank, row in enumerate(
            prestige_rows,
            1,
        ):
            index = safe_idx(
                row["object_index"]
            )

            prestige.append(
                {
                    "rank": rank,
                    "user_id": row[
                        "user_id"
                    ],
                    "name": row_name(row),
                    "prestige_count":
                        row["prestige_count"],
                    "object_index": index,
                    "object_name":
                        CELESTIAL_OBJECTS[
                            index
                        ]["name"],
                }
            )

        return {
            "balance": balance,
            "progress": progress,
            "prestige": prestige,
        }


# ============================================================
# MY LEADERBOARD RANK
# ============================================================

@app.get("/api/leaderboard/{user_id}/rank")
def my_leaderboard_rank(
    user_id: int,
):
    with get_db() as conn:

        user = get_or_create_user(
            conn,
            user_id,
        )

        balance_rank = conn.execute(
            """
            SELECT COUNT(*) + 1 AS rank
            FROM users
            WHERE balance > ?
            """,
            (user["balance"],),
        ).fetchone()["rank"]

        prestige_rank = conn.execute(
            """
            SELECT COUNT(*) + 1 AS rank
            FROM users
            WHERE prestige_count > ?
            """,
            (user["prestige_count"],),
        ).fetchone()["rank"]

        progress_rank = conn.execute(
            """
            SELECT COUNT(*) + 1 AS rank
            FROM users
            WHERE
                object_index > ?

                OR (
                    object_index = ?
                    AND object_progress > ?
                )

                OR (
                    object_index = ?
                    AND object_progress = ?
                    AND prestige_count > ?
                )
            """,
            (
                user["object_index"],
                user["object_index"],
                user["object_progress"],
                user["object_index"],
                user["object_progress"],
                user["prestige_count"],
            ),
        ).fetchone()["rank"]

        return {
            "balance_rank":
                balance_rank,

            "progress_rank":
                progress_rank,

            "prestige_rank":
                prestige_rank,
        }


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "sundered-star",
        "objects": len(
            CELESTIAL_OBJECTS
        ),
        "time": int(time.time()),
    }


# ============================================================
# STATIC FRONTEND
# ============================================================

STATIC_DIR = "static"

if not os.path.isdir(STATIC_DIR):
    os.makedirs(
        STATIC_DIR,
        exist_ok=True,
    )

app.mount(
    "/",
    StaticFiles(
        directory=STATIC_DIR,
        html=True,
    ),
    name="static",
)
