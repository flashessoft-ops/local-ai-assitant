import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB = Path(os.getenv("CHAT_DB", str(Path(__file__).with_name("chat.db"))))
OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
app = FastAPI(title="Local Chat")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
generation_lock = Lock()


@contextmanager
def database():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


with database() as db:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY, topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')), content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS messages_topic ON messages(topic_id, id);
    """)


class TopicInput(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class MessageInput(BaseModel):
    content: str = Field(min_length=1, max_length=32000)


def require_topic(db, topic_id):
    if not db.execute("SELECT id FROM topics WHERE id = ?", (topic_id,)).fetchone():
        raise HTTPException(404, "Conversation not found")


@app.get("/api/health")
def health():
    try:
        response = httpx.get(f"{OLLAMA}/api/tags", timeout=3)
        response.raise_for_status()
        models = [m["name"] for m in response.json()["models"]]
        return {"ollama": "online", "model": MODEL, "model_ready": MODEL in models}
    except (httpx.HTTPError, ValueError, KeyError):
        return {"ollama": "offline", "model": MODEL, "model_ready": False}


@app.get("/api/topics")
def topics():
    with database() as db:
        return [dict(row) for row in db.execute("SELECT * FROM topics ORDER BY id DESC")]


@app.post("/api/topics", status_code=201)
def create_topic(body: TopicInput):
    with database() as db:
        cursor = db.execute("INSERT INTO topics(title) VALUES (?)", (body.title.strip() or "New conversation",))
        return dict(db.execute("SELECT * FROM topics WHERE id = ?", (cursor.lastrowid,)).fetchone())


@app.delete("/api/topics/{topic_id}", status_code=204)
def delete_topic(topic_id: int):
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(409, "Wait for the current response before deleting a conversation")
    try:
        with database() as db:
            require_topic(db, topic_id)
            db.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
    finally:
        generation_lock.release()


@app.get("/api/topics/{topic_id}/messages")
def messages(topic_id: int):
    with database() as db:
        require_topic(db, topic_id)
        return [dict(row) for row in db.execute("SELECT * FROM messages WHERE topic_id = ? ORDER BY id", (topic_id,))]


@app.post("/api/topics/{topic_id}/messages")
def send_message(topic_id: int, body: MessageInput):
    content = body.content.strip()
    if not content:
        raise HTTPException(422, "Message cannot be blank")
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(409, "The model is busy. Try again when the current response finishes.")
    try:
        with database() as db:
            require_topic(db, topic_id)
            history = [dict(row) for row in db.execute("SELECT role, content FROM messages WHERE topic_id = ? ORDER BY id", (topic_id,))]
        try:
            response = httpx.post(f"{OLLAMA}/api/chat", json={"model": MODEL, "messages": history[-40:] + [{"role": "user", "content": content}], "stream": False, "think": False}, timeout=180)
            response.raise_for_status()
            answer = response.json()["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Empty model response")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(502, f"Ollama could not answer. Ensure Ollama is running and run 'ollama pull {MODEL}'. Your message was not saved; you can retry.") from exc
        with database() as db:
            db.executemany("INSERT INTO messages(topic_id, role, content) VALUES (?, ?, ?)", [(topic_id, "user", content), (topic_id, "assistant", answer)])
            if not history:
                db.execute("UPDATE topics SET title = ? WHERE id = ?", (content[:70], topic_id))
        return messages(topic_id)
    finally:
        generation_lock.release()
