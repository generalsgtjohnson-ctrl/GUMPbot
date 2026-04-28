import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "gumpbot.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Message mirroring map
    c.execute("""
        CREATE TABLE IF NOT EXISTS message_map (
            original_channel_id INTEGER,
            original_message_id INTEGER,
            mirrored_channel_id INTEGER,
            mirrored_message_id INTEGER,
            PRIMARY KEY (original_channel_id, original_message_id, mirrored_channel_id)
        )
    """)

    # Channel groups (mirrors of each other)
    c.execute("""
        CREATE TABLE IF NOT EXISTS channel_groups (
            group_id TEXT,
            channel_id INTEGER,
            language TEXT,
            PRIMARY KEY (group_id, channel_id)
        )
    """)

    # Universal channels (visible to all)
    c.execute("""
        CREATE TABLE IF NOT EXISTS universal_channels (
            channel_id INTEGER PRIMARY KEY
        )
    """)

    # Configured languages
    c.execute("""
        CREATE TABLE IF NOT EXISTS languages (
            code TEXT PRIMARY KEY,
            name TEXT,
            flag TEXT,
            role_id INTEGER
        )
    """)

    # Bot config (key/value store)
    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()

# ── Config ────────────────────────────────────────────────────────────────────

def set_config(key: str, value: str):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_config(key: str) -> str | None:
    conn = get_conn()
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None

# ── Languages ─────────────────────────────────────────────────────────────────

def add_language(code: str, name: str, flag: str, role_id: int):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO languages (code, name, flag, role_id) VALUES (?, ?, ?, ?)",
        (code, name, flag, role_id)
    )
    conn.commit()
    conn.close()

def get_languages() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT code, name, flag, role_id FROM languages").fetchall()
    conn.close()
    return [{"code": r[0], "name": r[1], "flag": r[2], "role_id": r[3]} for r in rows]

def get_language_by_role(role_id: int) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT code, name, flag, role_id FROM languages WHERE role_id = ?", (role_id,)
    ).fetchone()
    conn.close()
    return {"code": row[0], "name": row[1], "flag": row[2], "role_id": row[3]} if row else None

# ── Channel groups ────────────────────────────────────────────────────────────

def add_channel_to_group(group_id: str, channel_id: int, language: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO channel_groups (group_id, channel_id, language) VALUES (?, ?, ?)",
        (group_id, channel_id, language)
    )
    conn.commit()
    conn.close()

def get_group_for_channel(channel_id: int) -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT group_id FROM channel_groups WHERE channel_id = ?", (channel_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None

def get_channels_in_group(group_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT channel_id, language FROM channel_groups WHERE group_id = ?", (group_id,)
    ).fetchall()
    conn.close()
    return [{"channel_id": r[0], "language": r[1]} for r in rows]

def get_all_groups() -> list[str]:
    conn = get_conn()
    rows = conn.execute("SELECT DISTINCT group_id FROM channel_groups").fetchall()
    conn.close()
    return [r[0] for r in rows]

# ── Universal channels ────────────────────────────────────────────────────────

def add_universal_channel(channel_id: int):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO universal_channels (channel_id) VALUES (?)", (channel_id,))
    conn.commit()
    conn.close()

def is_universal(channel_id: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM universal_channels WHERE channel_id = ?", (channel_id,)
    ).fetchone()
    conn.close()
    return row is not None

# ── Message mapping ───────────────────────────────────────────────────────────

def save_mapping(original_channel_id: int, original_message_id: int,
                 mirrored_channel_id: int, mirrored_message_id: int):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO message_map
        (original_channel_id, original_message_id, mirrored_channel_id, mirrored_message_id)
        VALUES (?, ?, ?, ?)
    """, (original_channel_id, original_message_id, mirrored_channel_id, mirrored_message_id))
    conn.commit()
    conn.close()

def get_mirrors(channel_id: int, message_id: int) -> list[tuple[int, int]]:
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT mirrored_channel_id, mirrored_message_id FROM message_map
        WHERE original_channel_id = ? AND original_message_id = ?
    """, (channel_id, message_id))
    mirrors = c.fetchall()

    if mirrors:
        conn.close()
        return mirrors

    c.execute("""
        SELECT original_channel_id, original_message_id FROM message_map
        WHERE mirrored_channel_id = ? AND mirrored_message_id = ?
    """, (channel_id, message_id))
    row = c.fetchone()

    if row:
        orig_ch, orig_msg = row
        c.execute("""
            SELECT mirrored_channel_id, mirrored_message_id FROM message_map
            WHERE original_channel_id = ? AND original_message_id = ?
              AND NOT (mirrored_channel_id = ? AND mirrored_message_id = ?)
        """, (orig_ch, orig_msg, channel_id, message_id))
        siblings = c.fetchall()
        siblings.append((orig_ch, orig_msg))
        conn.close()
        return siblings

    conn.close()
    return []

def is_mirrored_message(channel_id: int, message_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("""
        SELECT 1 FROM message_map
        WHERE mirrored_channel_id = ? AND mirrored_message_id = ?
    """, (channel_id, message_id)).fetchone()
    conn.close()
    return row is not None
