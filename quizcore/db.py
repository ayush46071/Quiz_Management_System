"""SQLite constraints plus a single process gate for writes and restoration."""
import sqlite3
import threading
from contextlib import contextmanager

SCHEMA = """
PRAGMA user_version = 1;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, username TEXT NOT NULL COLLATE NOCASE UNIQUE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','teacher','student')),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), failures INTEGER NOT NULL DEFAULT 0,
 locked_until INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS questions (
 id INTEGER PRIMARY KEY, prompt TEXT NOT NULL, options TEXT NOT NULL,
 correct INTEGER NOT NULL CHECK(correct BETWEEN 0 AND 3), explanation TEXT NOT NULL DEFAULT '',
 category TEXT NOT NULL, points INTEGER NOT NULL CHECK(points BETWEEN 1 AND 100),
 created_by INTEGER REFERENCES users(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS quizzes (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 duration INTEGER NOT NULL CHECK(duration BETWEEN 1 AND 180),
 pass_percent INTEGER NOT NULL CHECK(pass_percent BETWEEN 0 AND 100),
 status TEXT NOT NULL CHECK(status IN ('draft','published','archived')),
 created_by INTEGER REFERENCES users(id) ON DELETE SET NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS quiz_questions (
 quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
 question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
 position INTEGER NOT NULL, PRIMARY KEY(quiz_id,question_id));
CREATE TABLE IF NOT EXISTS attempts (
 id INTEGER PRIMARY KEY, quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE RESTRICT,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 title TEXT NOT NULL, pass_percent INTEGER NOT NULL, snapshot TEXT NOT NULL,
 answers TEXT NOT NULL DEFAULT '{}', started_at INTEGER NOT NULL, deadline INTEGER NOT NULL,
 submitted_at INTEGER, score INTEGER, total INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 0,
 UNIQUE(quiz_id,user_id));
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, occurred_at INTEGER NOT NULL, actor_id INTEGER,
 actor TEXT NOT NULL, action TEXT NOT NULL, entity TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS defects (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
 severity INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 10),
 occurrences INTEGER NOT NULL CHECK(occurrences BETWEEN 1 AND 10000),
 status TEXT NOT NULL CHECK(status IN ('Open','In progress','Resolved')),
 evidence TEXT NOT NULL, source TEXT NOT NULL CHECK(source IN ('Observed','Illustrative')),
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS fmea (
 id INTEGER PRIMARY KEY, failure TEXT NOT NULL, effect TEXT NOT NULL, cause TEXT NOT NULL,
 severity INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 10),
 occurrence INTEGER NOT NULL CHECK(occurrence BETWEEN 1 AND 10),
 detection INTEGER NOT NULL CHECK(detection BETWEEN 1 AND 10),
 control TEXT NOT NULL, action TEXT NOT NULL, owner TEXT NOT NULL,
 residual_s INTEGER NOT NULL CHECK(residual_s BETWEEN 1 AND 10),
 residual_o INTEGER NOT NULL CHECK(residual_o BETWEEN 1 AND 10),
 residual_d INTEGER NOT NULL CHECK(residual_d BETWEEN 1 AND 10));
CREATE TABLE IF NOT EXISTS pdca (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, plan TEXT NOT NULL, do_text TEXT NOT NULL,
 check_text TEXT NOT NULL, act TEXT NOT NULL, status TEXT NOT NULL,
 owner TEXT NOT NULL, updated_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS attempts_user ON attempts(user_id,submitted_at);
CREATE INDEX IF NOT EXISTS audit_time ON audit(occurred_at DESC);
CREATE INDEX IF NOT EXISTS question_category ON questions(category);
"""

class Database:
    def __init__(self, config):
        self.config = config
        self.gate = threading.RLock()
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    def connect(self):
        conn = sqlite3.connect(self.config.database, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def transaction(self):
        with self.gate:
            conn = self.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def rows(self, sql, params=()):
        with self.gate:
            conn = self.connect()
            try:
                return [dict(r) for r in conn.execute(sql, params)]
            finally:
                conn.close()

    def one(self, sql, params=()):
        rows = self.rows(sql, params)
        return rows[0] if rows else None
