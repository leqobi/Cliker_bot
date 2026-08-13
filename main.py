import sqlite3
import time
import math
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# ============================================================
# APP
# ============================================================

app = FastAPI(title="Sundered Star API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE
# ============================================================

DB_PATH = "clicker.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=10,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        yield conn
    finally:
        conn.close()


def begin_write(conn):
    """
    Защищает операции изменения баланса/прогресса
    от одновременных запросов.
    """
    conn.execute("BEGIN IMMEDIATE")


# ============================================================
# ECONOMY
# ============================================================

# ------------------------------------------------------------
# CLICK
# ------------------------------------------------------------

# Level 1 = 1 монета и 1 прогресс за клик.
#
# ВАЖНО:
# Click Level теперь влияет и на прогресс.
# Поэтому прокачка клика действительно ускоряет
# путешествие между объектами.

BASE_CLICK_UPGRADE_COST = 50
CLICK_UPGRADE_MULTIPLIER = 1.45
MAX_CLICK_LEVEL = 25


# ------------------------------------------------------------
# STAMINA
# ------------------------------------------------------------

BASE_STAMINA_MAX = 1000

# 1 stamina каждые 4 секунды.
STAMINA_REGEN_PER_SEC = 0.25

BASE_STAMINA_UPGRADE_COST = 100
STAMINA_UPGRADE_MULTIPLIER = 1.55

MAX_STAMINA_LEVEL = 15
STAMINA_MAX_PER_LEVEL = 200


# ------------------------------------------------------------
# PRESTIGE
# ------------------------------------------------------------

# Престиж увеличивает только доход монет.
# На прогресс объекта множитель не распространяется.
PRESTIGE_BOOST_PER_LEVEL = 0.35


# ------------------------------------------------------------
# DAILY BONUS
# ------------------------------------------------------------

# Более ровная система:
#
# День 1: 100
# День 2: 125
# День 3: 150
# День 4: 175
# День 5: 200
# День 6: 225
# День 7: 250
#
# После 7-го дня остаётся 250,
# пока streak не будет потерян.

DAILY_BONUS_BASE = 100
DAILY_BONUS_PER_DAY = 25
DAILY_BONUS_MAX_STREAK_DAY = 7

SECONDS_IN_DAY = 86400


# ------------------------------------------------------------
# REFERRALS
# ------------------------------------------------------------

# Пригласивший получает 2500 монет.
REFERRAL_START_BONUS = 2500

# 7% от click earnings приглашённого.
REFERRAL_PERCENT = 0.07

# Выплата раз в 7 дней.
REFERRAL_PERIOD = 7 * SECONDS_IN_DAY


# ------------------------------------------------------------
# LANGUAGES
# ------------------------------------------------------------

SUPPORTED_LANGUAGES = {
    "ru",
    "en",
}

DEFAULT_LANGUAGE = "ru"


# ============================================================
# CELESTIAL OBJECTS
# ============================================================

# Пороги уменьшены.
#
# Самая большая проблема старой экономики была в том,
# что поздние объекты требовали десятки миллионов
# физических тапов.
#
# Теперь Click Level увеличивает progress за клик,
# поэтому игрок реально ускоряется через прокачку.

CELESTIAL_OBJECTS = [
    {
        "id": 0,
        "name": "Меркурий",
        "category": "planet",
        "threshold": 5000,
        "image": "mercury.png",
    },
    {
        "id": 1,
        "name": "Венера",
        "category": "planet",
        "threshold": 15000,
        "image": "venus.png",
    },
    {
        "id": 2,
        "name": "Марс",
        "category": "planet",
        "threshold": 35000,
        "image": "mars.png",
    },
    {
        "id": 3,
        "name": "Юпитер",
        "category": "planet",
        "threshold": 70000,
        "image": "jupiter.png",
    },
    {
        "id": 4,
        "name": "Сатурн",
        "category": "planet",
        "threshold": 140000,
        "image": "saturn.png",
    },
    {
        "id": 5,
        "name": "Альфа Центавра",
        "category": "star",
        "threshold": 250000,
        "image": "alpha_centauri.png",
    },
    {
        "id": 6,
        "name": "Проксима Центавра",
        "category": "star",
        "threshold": 400000,
        "image": "proxima_centauri.png",
    },
    {
        "id": 7,
        "name": "Сириус",
        "category": "star",
        "threshold": 650000,
        "image": "sirius.png",
    },
    {
        "id": 8,
        "name": "Бетельгейзе",
        "category": "star",
        "threshold": 1000000,
        "image": "betelgeuse.png",
    },
    {
        "id": 9,
        "name": "Ригель",
        "category": "star",
        "threshold": 1500000,
        "image": "rigel.png",
    },
    {
        "id": 10,
        "name": "Вега",
        "category": "star",
        "threshold": 2200000,
        "image": "vega.png",
    },
    {
        "id": 11,
        "name": "Белый карлик",
        "category": "star",
        "threshold": 3000000,
        "image": "white_dwarf.png",
    },
    {
        "id": 12,
        "name": "Нейтронная звезда",
        "category": "star",
        "threshold": 4000000,
        "image": "neutron_star.png",
    },
    {
        "id": 13,
        "name": "Магнетар",
        "category": "star",
        "threshold": 5000000,
        "image": "magnetar.png",
    },
    {
        "id": 14,
        "name": "Чёрная дыра",
        "category": "blackhole",
        "threshold": 6000000,
        "image": "black_hole.png",
    },
    {
        "id": 15,
        "name": "Сверхмассивная чёрная дыра",
        "category": "blackhole",
        "threshold": 8000000,
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

def column_exists(
    conn,
    table_name: str,
    column_name: str,
) -> bool:

    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        row["name"] == column_name
        for row in rows
    )


def add_column_if_missing(
    conn,
    table_name: str,
    column_name: str,
    column_definition: str,
):

    if not column_exists(
        conn,
        table_name,
        column_name,
    ):
        conn.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_definition}"
        )


def init_db():

    with get_db() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,

                balance INTEGER NOT NULL DEFAULT 0,

                click_level INTEGER NOT NULL DEFAULT 1,

                stamina_level INTEGER NOT NULL DEFAULT 1,

                stamina REAL NOT NULL DEFAULT 1000,

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
        # MIGRATIONS
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
        # REFERRALS
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS referrals (
                referred_id INTEGER PRIMARY KEY,

                referrer_id INTEGER NOT NULL,

                created_at REAL NOT NULL,

                signup_bonus INTEGER NOT NULL DEFAULT 2500,

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

        # ----------------------------------------------------
        # REFERRAL PAYMENTS
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_payments (
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
        # INDEXES
        # ----------------------------------------------------

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_users_balance
            ON users(balance DESC)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_users_progress
            ON users(object_progress DESC)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_users_prestige
            ON users(prestige_count DESC)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_referrals_referrer
            ON referrals(referrer_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_referral_payments_referrer
            ON referral_payments(referrer_id)
            """
        )


init_db()


# ============================================================
# GAME CALCULATIONS
# ============================================================

def get_click_power(
    click_level: int,
) -> int:

    return max(
        1,
        min(
            click_level,
            MAX_CLICK_LEVEL,
        ),
    )


def get_click_upgrade_cost(
    current_level: int,
) -> int:

    if current_level >= MAX_CLICK_LEVEL:
        return -1

    return math.ceil(
        BASE_CLICK_UPGRADE_COST
        * (
            CLICK_UPGRADE_MULTIPLIER
            ** (current_level - 1)
        )
    )


def get_stamina_max(
    stamina_level: int,
) -> int:

    return (
        BASE_STAMINA_MAX
        + (
            max(1, stamina_level) - 1
        )
        * STAMINA_MAX_PER_LEVEL
    )


def get_stamina_upgrade_cost(
    current_level: int,
) -> int:

    if current_level >= MAX_STAMINA_LEVEL:
        return -1

    return math.ceil(
        BASE_STAMINA_UPGRADE_COST
        * (
            STAMINA_UPGRADE_MULTIPLIER
            ** (current_level - 1)
        )
    )


def calculate_current_stamina(
    stored_stamina: float,
    last_update: float,
    stamina_max: int,
) -> float:

    if last_update <= 0:
        return float(stamina_max)

    elapsed = max(
        0,
        time.time() - last_update,
    )

    regenerated = (
        elapsed
        * STAMINA_REGEN_PER_SEC
    )

    return min(
        float(stamina_max),
        max(
            0.0,
            stored_stamina + regenerated,
        ),
    )


def get_prestige_multiplier(
    prestige_count: int,
) -> float:

    return (
        1
        + max(0, prestige_count)
        * PRESTIGE_BOOST_PER_LEVEL
    )


def get_daily_bonus_amount(
    streak: int,
) -> int:

    effective_day = min(
        max(streak, 1),
        DAILY_BONUS_MAX_STREAK_DAY,
    )

    return (
        DAILY_BONUS_BASE
        + (
            effective_day - 1
        )
        * DAILY_BONUS_PER_DAY
    )


# ============================================================
# DAILY STATUS
# ============================================================

def get_daily_status(
    last_claim: float,
    streak: int,
) -> dict:

    now = time.time()

    if last_claim <= 0:

        return {
            "can_claim": True,
            "next_streak": 1,
            "hours_until_next": 0,
        }

    elapsed = now - last_claim

    # Ещё не прошло 24 часа.
    if elapsed < SECONDS_IN_DAY:

        hours_left = math.ceil(
            (
                SECONDS_IN_DAY
                - elapsed
            )
            / 3600
        )

        return {
            "can_claim": False,
            "next_streak": max(
                1,
                streak,
            ),
            "hours_until_next": hours_left,
        }

    # Можно забрать следующий день.
    if elapsed < SECONDS_IN_DAY * 2:

        return {
            "can_claim": True,
            "next_streak": min(
                max(1, streak) + 1,
                DAILY_BONUS_MAX_STREAK_DAY,
            ),
            "hours_until_next": 0,
        }

    # Пропущен день — streak сбрасывается.
    return {
        "can_claim": True,
        "next_streak": 1,
        "hours_until_next": 0,
    }


# ============================================================
# USER
# ============================================================

def get_or_create_user(
    conn,
    user_id: int,
):

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

        stamina_max = get_stamina_max(1)

        conn.execute(
            """
            INSERT INTO users (
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
            VALUES (
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
                stamina_max,
                now,
                now,
                DEFAULT_LANGUAGE,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    # Старые пользователи из предыдущей версии.
    if row["created_at"] == 0:

        now = time.time()

        conn.execute(
            """
            UPDATE users
            SET created_at = ?
            WHERE user_id = ?
            """,
            (
                now,
                user_id,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if (
        row["language"] is None
        or row["language"] not in SUPPORTED_LANGUAGES
    ):

        conn.execute(
            """
            UPDATE users
            SET language = ?
            WHERE user_id = ?
            """,
            (
                DEFAULT_LANGUAGE,
                user_id,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    return row


# ============================================================
# REFERRAL PAYOUT
# ============================================================

def settle_referral_for_referred(
    conn,
    referred_id: int,
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

    last_payout_at = (
        referral["last_payout_at"]
    )

    if last_payout_at <= 0:
        last_payout_at = referral["created_at"]

    if (
        now - last_payout_at
        < REFERRAL_PERIOD
    ):
        return 0

    referred = conn.execute(
        """
        SELECT total_click_earnings
        FROM users
        WHERE user_id = ?
        """,
        (referred_id,),
    ).fetchone()

    if referred is None:
        return 0

    total_earned = max(
        0,
        referred["total_click_earnings"],
    )

    baseline = max(
        0,
        referral["weekly_click_baseline"],
    )

    delta = max(
        0,
        total_earned - baseline,
    )

    reward = math.floor(
        delta * REFERRAL_PERCENT
    )

    period_start = last_payout_at
    period_end = now

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
            INSERT INTO referral_payments (
                referrer_id,
                referred_id,
                period_start,
                period_end,
                click_earnings,
                reward,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                referral["referrer_id"],
                referred_id,
                period_start,
                period_end,
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
            total_earned,
            reward,
            now,
            referred_id,
        ),
    )

    return reward


def settle_all_referrals_for_referrer(
    conn,
    referrer_id: int,
):

    referrals = conn.execute(
        """
        SELECT referred_id
        FROM referrals
        WHERE referrer_id = ?
        """,
        (referrer_id,),
    ).fetchall()

    total_reward = 0

    for referral in referrals:

        total_reward += (
            settle_referral_for_referred(
                conn,
                referral["referred_id"],
            )
        )

    return total_reward


# ============================================================
# REFERRAL STATS
# ============================================================

def get_referral_stats(
    conn,
    user_id: int,
) -> dict:

    count_row = conn.execute(
        """
        SELECT COUNT(*) AS total
        FROM referrals
        WHERE referrer_id = ?
        """,
        (user_id,),
    ).fetchone()

    paid_row = conn.execute(
        """
        SELECT COALESCE(SUM(reward), 0) AS total
        FROM referral_payments
        WHERE referrer_id = ?
        """,
        (user_id,),
    ).fetchone()

    return {
        "count": count_row["total"],
        "total_earned": paid_row["total"],
    }


# ============================================================
# USER SERIALIZATION
# ============================================================

def user_to_dict(
    row,
    conn=None,
) -> dict:

    if conn is None:

        with get_db() as local_conn:

            return user_to_dict(
                row,
                local_conn,
            )

    stamina_max = get_stamina_max(
        row["stamina_level"]
    )

    current_stamina = (
        calculate_current_stamina(
            row["stamina"],
            row["last_stamina_update"],
            stamina_max,
        )
    )

    obj_index = max(
        0,
        min(
            row["object_index"],
            len(CELESTIAL_OBJECTS) - 1,
        ),
    )

    current_object = (
        CELESTIAL_OBJECTS[obj_index]
    )

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
            "@"
            + row["telegram_username"]
        )

    elif row["telegram_first_name"]:

        display_name = (
            row["telegram_first_name"]
        )

    else:

        display_name = (
            f"Исследователь #{row['user_id']}"
        )

    return {

        # ----------------------------------------------------
        # USER
        # ----------------------------------------------------

        "user_id": row["user_id"],

        "username": row["telegram_username"],

        "first_name": row[
            "telegram_first_name"
        ],

        "last_name": row[
            "telegram_last_name"
        ],

        "display_name": display_name,

        "language": (
            row["language"]
            if row["language"]
            in SUPPORTED_LANGUAGES
            else DEFAULT_LANGUAGE
        ),

        "supported_languages": [
            "ru",
            "en",
        ],

        # ----------------------------------------------------
        # ECONOMY
        # ----------------------------------------------------

        "balance": row["balance"],

        # ----------------------------------------------------
        # CLICK
        # ----------------------------------------------------

        "click_level": row[
            "click_level"
        ],

        "click_power": get_click_power(
            row["click_level"]
        ),

        "click_upgrade_cost": (
            get_click_upgrade_cost(
                row["click_level"]
            )
        ),

        # ----------------------------------------------------
        # STAMINA
        # ----------------------------------------------------

        "stamina": round(
            current_stamina
        ),

        "stamina_max": stamina_max,

        "stamina_level": row[
            "stamina_level"
        ],

        "stamina_upgrade_cost": (
            get_stamina_upgrade_cost(
                row["stamina_level"]
            )
        ),

        "stamina_regen_per_sec": (
            STAMINA_REGEN_PER_SEC
        ),

        # ----------------------------------------------------
        # OBJECT
        # ----------------------------------------------------

        "object_index": obj_index,

        "object_name": current_object[
            "name"
        ],

        "object_category": current_object[
            "category"
        ],

        "object_image": current_object[
            "image"
        ],

        "object_progress": row[
            "object_progress"
        ],

        "object_threshold": current_object[
            "threshold"
        ],

        # ----------------------------------------------------
        # PRESTIGE
        # ----------------------------------------------------

        "prestige_count": row[
            "prestige_count"
        ],

        "prestige_multiplier": (
            get_prestige_multiplier(
                row["prestige_count"]
            )
        ),

        "can_prestige": (
            current_object["threshold"]
            is not None
            and row["object_progress"]
            >= current_object["threshold"]
        ),

        "is_final_object": (
            current_object["threshold"]
            is None
        ),

        # ----------------------------------------------------
        # DAILY
        # ----------------------------------------------------

        "daily_streak": row[
            "daily_streak"
        ],

        "daily_status": daily_status,

        "daily_next_amount": (
            get_daily_bonus_amount(
                daily_status["next_streak"]
            )
        ),

        # ----------------------------------------------------
        # REFERRALS
        # ----------------------------------------------------

        "referral_count": (
            referral_stats["count"]
        ),

        "referral_total_earned": (
            referral_stats["total_earned"]
        ),

        "referral_bonus": (
            REFERRAL_START_BONUS
        ),

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
# API: STATE
# ============================================================

@app.get("/api/state/{user_id}")
def get_state(
    user_id: int,
):

    with get_db() as conn:

        get_or_create_user(
            conn,
            user_id,
        )

        begin_write(conn)

        settle_referral_for_referred(
            conn,
            user_id,
        )

        settle_all_referrals_for_referrer(
            conn,
            user_id,
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

        return user_to_dict(
            row,
            conn,
        )


# ============================================================
# API: PROFILE
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

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        return user_to_dict(
            row,
            conn,
        )


# ============================================================
# API: LANGUAGE
# ============================================================

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
            detail=(
                "Неподдерживаемый язык. "
                "Доступны: ru, en"
            ),
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

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        return user_to_dict(
            row,
            conn,
        )


# ============================================================
# API: CLICK
# ============================================================

@app.post("/api/click")
def click(
    data: ClickRequest,
):

    with get_db() as conn:

        begin_write(conn)

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        stamina_max = get_stamina_max(
            row["stamina_level"]
        )

        current_stamina = (
            calculate_current_stamina(
                row["stamina"],
                row["last_stamina_update"],
                stamina_max,
            )
        )

        actual_taps = min(
            data.taps,
            math.floor(
                current_stamina
            ),
        )

        if actual_taps <= 0:

            conn.rollback()

            raise HTTPException(
                status_code=400,
                detail="Недостаточно стамины",
            )

        click_power = get_click_power(
            row["click_level"]
        )

        prestige_mult = (
            get_prestige_multiplier(
                row["prestige_count"]
            )
        )

        # ----------------------------------------------------
        # MONETARY REWARD
        # ----------------------------------------------------
        #
        # Prestige влияет на монеты.
        #
        earned = round(
            actual_taps
            * click_power
            * prestige_mult
        )

        # ----------------------------------------------------
        # PROGRESS
        # ----------------------------------------------------
        #
        # Прогресс теперь зависит от Click Level.
        #
        # 1 уровень -> 1 progress / tap
        # 10 уровень -> 10 progress / tap
        # 25 уровень -> 25 progress / tap
        #
        # Prestige multiplier здесь НЕ используется,
        # чтобы прогресс не разгонялся слишком быстро.
        #
        progress_gain = (
            actual_taps
            * click_power
        )

        new_stamina = (
            current_stamina
            - actual_taps
        )

        now = time.time()

        conn.execute(
            """
            UPDATE users
            SET
                balance = balance + ?,

                stamina = ?,

                last_stamina_update = ?,

                object_progress =
                    object_progress + ?,

                total_click_earnings =
                    total_click_earnings + ?

            WHERE user_id = ?
            """,
            (
                earned,
                new_stamina,
                now,
                progress_gain,
                earned,
                data.user_id,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        result = user_to_dict(
            row,
            conn,
        )

        result["accepted_taps"] = (
            actual_taps
        )

        result["earned"] = earned

        result["progress_gained"] = (
            progress_gain
        )

        return result


# ============================================================
# API: CLICK UPGRADE
# ============================================================

@app.post("/api/upgrade/click")
def upgrade_click(
    data: UpgradeRequest,
):

    with get_db() as conn:

        begin_write(conn)

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        cost = get_click_upgrade_cost(
            row["click_level"]
        )

        if cost == -1:

            conn.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Достигнут максимальный "
                    "уровень Click"
                ),
            )

        if row["balance"] < cost:

            conn.rollback()

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

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        return user_to_dict(
            row,
            conn,
        )


# ============================================================
# API: STAMINA UPGRADE
# ============================================================

@app.post("/api/upgrade/stamina")
def upgrade_stamina(
    data: UpgradeRequest,
):

    with get_db() as conn:

        begin_write(conn)

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        cost = get_stamina_upgrade_cost(
            row["stamina_level"]
        )

        if cost == -1:

            conn.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Достигнут максимальный "
                    "уровень Stamina"
                ),
            )

        if row["balance"] < cost:

            conn.rollback()

            raise HTTPException(
                status_code=400,
                detail="Недостаточно монет",
            )

        old_max = get_stamina_max(
            row["stamina_level"]
        )

        current_stamina = (
            calculate_current_stamina(
                row["stamina"],
                row["last_stamina_update"],
                old_max,
            )
        )

        new_level = (
            row["stamina_level"] + 1
        )

        new_max = get_stamina_max(
            new_level
        )

        # Сохраняем текущую энергию и добавляем
        # новое максимальное значение.
        added_capacity = (
            new_max - old_max
        )

        new_stamina = min(
            new_max,
            current_stamina
            + added_capacity,
        )

        conn.execute(
            """
            UPDATE users
            SET
                balance = balance - ?,

                stamina_level =
                    stamina_level + 1,

                stamina = ?,

                last_stamina_update = ?

            WHERE user_id = ?
            """,
            (
                cost,
                new_stamina,
                time.time(),
                data.user_id,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        return user_to_dict(
            row,
            conn,
        )


# ============================================================
# API: PRESTIGE
# ============================================================

@app.post("/api/prestige")
def prestige(
    data: UpgradeRequest,
):

    with get_db() as conn:

        begin_write(conn)

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        current_index = max(
            0,
            min(
                row["object_index"],
                len(CELESTIAL_OBJECTS) - 1,
            ),
        )

        current_object = (
            CELESTIAL_OBJECTS[
                current_index
            ]
        )

        if current_object["threshold"] is None:

            conn.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Это финальный объект, "
                    "дальше лететь некуда"
                ),
            )

        if (
            row["object_progress"]
            < current_object["threshold"]
        ):

            conn.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Ещё не набран порог "
                    "для перехода"
                ),
            )

        next_index = (
            current_index + 1
        )

        if next_index >= len(
            CELESTIAL_OBJECTS
        ):

            conn.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Следующего объекта "
                    "не существует"
                ),
            )

        new_prestige_count = (
            row["prestige_count"] + 1
        )

        new_stamina = get_stamina_max(1)

        # Баланс НЕ сбрасывается.
        #
        # Click и Stamina сбрасываются,
        # потому что это часть prestige loop.
        #
        # Prestige multiplier остаётся навсегда.

        conn.execute(
            """
            UPDATE users
            SET
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
                new_stamina,
                time.time(),
                next_index,
                new_prestige_count,
                data.user_id,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        return user_to_dict(
            row,
            conn,
        )


# ============================================================
# API: DAILY
# ============================================================

@app.post("/api/daily/claim")
def claim_daily(
    data: UpgradeRequest,
):

    with get_db() as conn:

        begin_write(conn)

        row = get_or_create_user(
            conn,
            data.user_id,
        )

        status = get_daily_status(
            row["last_daily_claim"],
            row["daily_streak"],
        )

        if not status["can_claim"]:

            conn.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Бонус уже забран сегодня"
                ),
            )

        new_streak = status[
            "next_streak"
        ]

        amount = get_daily_bonus_amount(
            new_streak
        )

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
                new_streak,
                time.time(),
                data.user_id,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        result = user_to_dict(
            row,
            conn,
        )

        result["claimed_amount"] = (
            amount
        )

        return result


# ============================================================
# API: OBJECTS
# ============================================================

@app.get("/api/objects")
def get_objects_list():

    return CELESTIAL_OBJECTS


# ============================================================
# API: REFERRAL REGISTER
# ============================================================

@app.post("/api/referral/register")
def register_referral(
    data: ReferralRegisterRequest,
):

    if data.user_id == data.referrer_id:

        raise HTTPException(
            status_code=400,
            detail=(
                "Нельзя пригласить "
                "самого себя"
            ),
        )

    with get_db() as conn:

        begin_write(conn)

        referred = get_or_create_user(
            conn,
            data.user_id,
        )

        get_or_create_user(
            conn,
            data.referrer_id,
        )

        # ----------------------------------------------------
        # Уже зарегистрирован
        # ----------------------------------------------------

        existing = conn.execute(
            """
            SELECT *
            FROM referrals
            WHERE referred_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        if existing is not None:

            conn.commit()

            row = conn.execute(
                """
                SELECT *
                FROM users
                WHERE user_id = ?
                """,
                (data.user_id,),
            ).fetchone()

            return {
                "success": True,
                "already_registered": True,
                "referrer_id": existing[
                    "referrer_id"
                ],
                "state": user_to_dict(
                    row,
                    conn,
                ),
            }

        # ----------------------------------------------------
        # Защита от referral abuse
        # ----------------------------------------------------
        #
        # Referral можно активировать только для
        # практически нового аккаунта.
        #
        # Нельзя взять старый аккаунт, который уже
        # заработал монеты/прогресс, и получить
        # бонус 2500.

        is_new_user = (
            referred["balance"] == 0
            and referred["click_level"] == 1
            and referred["stamina_level"] == 1
            and referred["object_index"] == 0
            and referred["object_progress"] == 0
            and referred["prestige_count"] == 0
            and referred["total_click_earnings"] == 0
        )

        if not is_new_user:

            conn.rollback()

            raise HTTPException(
                status_code=400,
                detail=(
                    "Referral можно "
                    "активировать только "
                    "для нового аккаунта"
                ),
            )

        referrer = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (data.referrer_id,),
        ).fetchone()

        if referrer is None:

            conn.rollback()

            raise HTTPException(
                status_code=404,
                detail=(
                    "Пригласивший "
                    "пользователь не найден"
                ),
            )

        now = time.time()

        baseline = max(
            0,
            referred["total_click_earnings"],
        )

        # ----------------------------------------------------
        # Бонус получает ПРИГЛАСИВШИЙ.
        # ----------------------------------------------------

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
            INSERT INTO referrals (
                referred_id,
                referrer_id,
                created_at,
                signup_bonus,
                weekly_click_baseline,
                total_paid,
                last_payout_at
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
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

        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (data.user_id,),
        ).fetchone()

        return {
            "success": True,
            "already_registered": False,
            "referrer_id": data.referrer_id,
            "signup_bonus": REFERRAL_START_BONUS,
            "state": user_to_dict(
                row,
                conn,
            ),
        }


# ============================================================
# API: REFERRAL INFO
# ============================================================

@app.get("/api/referral/{user_id}")
def referral_info(
    user_id: int,
):

    with get_db() as conn:

        get_or_create_user(
            conn,
            user_id,
        )

        begin_write(conn)

        settle_referral_for_referred(
            conn,
            user_id,
        )

        settle_all_referrals_for_referrer(
            conn,
            user_id,
        )

        conn.commit()

        referrals = conn.execute(
            """
            SELECT
                r.referred_id,
                r.created_at,
                r.total_paid,
                r.last_payout_at,

                u.telegram_username,
                u.telegram_first_name,
                u.telegram_last_name,

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

        total_earned = conn.execute(
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

        result_referrals = []

        now = time.time()

        for r in referrals:

            last_payout = (
                r["last_payout_at"]
            )

            if last_payout <= 0:
                last_payout = r[
                    "created_at"
                ]

            elapsed = (
                now - last_payout
            )

            seconds_until_payout = max(
                0,
                REFERRAL_PERIOD
                - elapsed,
            )

            days_until_payout = math.ceil(
                seconds_until_payout
                / SECONDS_IN_DAY
            )

            if r["telegram_username"]:

                name = (
                    "@"
                    + r["telegram_username"]
                )

            elif r["telegram_first_name"]:

                name = r[
                    "telegram_first_name"
                ]

            else:

                name = (
                    f"Исследователь "
                    f"#{r['referred_id']}"
                )

            result_referrals.append(
                {
                    "user_id": r[
                        "referred_id"
                    ],

                    "name": name,

                    "created_at": r[
                        "created_at"
                    ],

                    "total_paid": r[
                        "total_paid"
                    ],

                    "total_click_earnings": r[
                        "total_click_earnings"
                    ],

                    "object_index": r[
                        "object_index"
                    ],

                    "prestige_count": r[
                        "prestige_count"
                    ],

                    "days_until_payout": (
                        days_until_payout
                    ),
                }
            )

        return {
            "referral_bonus": (
                REFERRAL_START_BONUS
            ),

            "referral_percent": int(
                REFERRAL_PERCENT * 100
            ),

            "weekly_period_days": 7,

            "referral_count": len(
                result_referrals
            ),

            "total_earned": total_earned,

            "referrals": result_referrals,
        }


# ============================================================
# API: REFERRAL HISTORY
# ============================================================

@app.get(
    "/api/referral/{user_id}/history"
)
def referral_history(
    user_id: int,
):

    with get_db() as conn:

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
                    + row[
                        "telegram_username"
                    ]
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

                    "reward": row[
                        "reward"
                    ],

                    "created_at": row[
                        "created_at"
                    ],
                }
            )

        return result


# ============================================================
# API: LEADERBOARD
# ============================================================

@app.get("/api/leaderboard")
def leaderboard(
    limit: int = 50,
):

    limit = max(
        1,
        min(limit, 100),
    )

    with get_db() as conn:

        balance_rows = conn.execute(
            """
            SELECT
                user_id,
                balance,
                telegram_username,
                telegram_first_name,
                telegram_last_name,
                object_index,
                prestige_count

            FROM users

            ORDER BY balance DESC

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
                prestige_count DESC

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
                object_progress DESC

            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        def format_name(row):

            if row["telegram_username"]:

                return (
                    "@"
                    + row["telegram_username"]
                )

            if row["telegram_first_name"]:

                return row[
                    "telegram_first_name"
                ]

            return (
                f"Исследователь "
                f"#{row['user_id']}"
            )

        def safe_object(index):

            return CELESTIAL_OBJECTS[
                min(
                    max(index, 0),
                    len(CELESTIAL_OBJECTS) - 1,
                )
            ]

        def format_balance(rows):

            result = []

            for index, row in enumerate(
                rows,
                start=1,
            ):

                obj = safe_object(
                    row["object_index"]
                )

                result.append(
                    {
                        "rank": index,

                        "user_id": row[
                            "user_id"
                        ],

                        "name": format_name(
                            row
                        ),

                        "balance": row[
                            "balance"
                        ],

                        "object_index": row[
                            "object_index"
                        ],

                        "object_name": obj[
                            "name"
                        ],

                        "prestige_count": row[
                            "prestige_count"
                        ],
                    }
                )

            return result

        def format_progress(rows):

            result = []

            for index, row in enumerate(
                rows,
                start=1,
            ):

                obj = safe_object(
                    row["object_index"]
                )

                threshold = obj[
                    "threshold"
                ]

                if threshold:

                    percent = min(
                        100,
                        round(
                            (
                                row[
                                    "object_progress"
                                ]
                                / threshold
                            )
                            * 100
                        ),
                    )

                else:

                    percent = 100

                result.append(
                    {
                        "rank": index,

                        "user_id": row[
                            "user_id"
                        ],

                        "name": format_name(
                            row
                        ),

                        "object_index": row[
                            "object_index"
                        ],

                        "object_name": obj[
                            "name"
                        ],

                        "object_progress": row[
                            "object_progress"
                        ],

                        "object_threshold": (
                            threshold
                        ),

                        "progress_percent": (
                            percent
                        ),

                        "prestige_count": row[
                            "prestige_count"
                        ],
                    }
                )

            return result

        def format_prestige(rows):

            result = []

            for index, row in enumerate(
                rows,
                start=1,
            ):

                obj = safe_object(
                    row["object_index"]
                )

                result.append(
                    {
                        "rank": index,

                        "user_id": row[
                            "user_id"
                        ],

                        "name": format_name(
                            row
                        ),

                        "prestige_count": row[
                            "prestige_count"
                        ],

                        "object_index": row[
                            "object_index"
                        ],

                        "object_name": obj[
                            "name"
                        ],
                    }
                )

            return result

        return {
            "balance": format_balance(
                balance_rows
            ),

            "progress": format_progress(
                progress_rows
            ),

            "prestige": format_prestige(
                prestige_rows
            ),
        }


# ============================================================
# API: MY RANK
# ============================================================

@app.get(
    "/api/leaderboard/{user_id}/rank"
)
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
            (
                user["balance"],
            ),
        ).fetchone()["rank"]

        prestige_rank = conn.execute(
            """
            SELECT COUNT(*) + 1 AS rank

            FROM users

            WHERE prestige_count > ?
            """,
            (
                user["prestige_count"],
            ),
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
            "balance_rank": balance_rank,
            "progress_rank": progress_rank,
            "prestige_rank": prestige_rank,
        }


# ============================================================
# API: HEALTH
# ============================================================

@app.get("/api/health")
def health():

    return {
        "status": "ok",

        "service": "sundered-star",

        "objects": len(
            CELESTIAL_OBJECTS
        ),

        "time": int(
            time.time()
        ),
    }


# ============================================================
# STATIC FRONTEND
# ============================================================

app.mount(
    "/",
    StaticFiles(
        directory="static",
        html=True,
    ),
    name="static",
    )
