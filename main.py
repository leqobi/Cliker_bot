import sqlite3
from contextlib import contextmanager

from fastapi import FastAPI
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
                balance INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


init_db()


class ClickRequest(BaseModel):
    user_id: int
    amount: int = 1


@app.get("/api/balance/{user_id}")
def get_balance(user_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        balance = row["balance"] if row else 0
    return {"user_id": user_id, "balance": balance}


@app.post("/api/click")
def click(data: ClickRequest):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, balance) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
            """,
            (data.user_id, data.amount, data.amount),
        )
        conn.commit()
        row = conn.execute(
            "SELECT balance FROM users WHERE user_id = ?", (data.user_id,)
        ).fetchone()
    return {"user_id": data.user_id, "balance": row["balance"]}


@app.get("/api/leaderboard")
def leaderboard():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10"
        ).fetchall()
    return [{"user_id": r["user_id"], "balance": r["balance"]} for r in rows]


app.mount("/", StaticFiles(directory="static", html=True), name="static")
