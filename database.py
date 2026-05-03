import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "gumpbot.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS message_map (
            original_channel_id INTEGER,
            original_message_id INTEGER,
            mirrored_channel_id INTEGER,
            mirrored_message_id INTEGER,
            PRIMARY KEY (original_channel_id, original_message_id, mirrored_channel_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS channel_groups (
            guild_id INTEGER,
            group_id TEXT,
            channel_id INTEGER,
            language TEXT,
            PRIMARY KEY (group_id, channel_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS universal_channels (
            guild_id INTEGER,
            channel_id INTEGER,
            PRIMARY KEY (guild_id, channel_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS languages (
            guild_id INTEGER,
            code TEXT,
            name TEXT,
            flag TEXT,
            role_id INTEGER,
            PRIMARY KEY (guild_id, code)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            guild_id INTEGER,
            key TEXT,
            value TEXT,
            PRIMARY KEY (guild_id, key)
        )
    """)

    conn.commit()
    conn.close()

# ââ Config ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def set_config(guild_id: int, key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO config (guild_id, key, value) VALUES (?, ?, ?)",
        (guild_id, key, value)
    )
    conn.commit()
    conn.close()

def get_config(guild_id: int, key: str) -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM config WHERE guild_id = ? AND key = ?", (guild_id, key)
    ).fetchone()
    conn.close()
    return row[0] if row else None

# ââ Languages âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def add_language(guild_id: int, code: str, name: str, flag: str, role_id: int):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO languages (guild_id, code, name, flag, role_id) VALUES (?, ?, ?, ?, ?)",
        (guild_id, code, name, flag, role_id)
    )
    conn.commit()
    conn.close()

def get_languages(guild_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT code, name, flag, role_id FROM languages WHERE guild_id = ?", (guild_id,)
    ).fetchall()
    conn.close()
    return [{"code": r[0], "name": r[1], "flag": r[2], "role_id": r[3]} for r in rows]

# ââ Channel groups ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def add_channel_to_group(guild_id: int, group_id: str, channel_id: int, language: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO channel_groups (guild_id, group_id, channel_id, language) VALUES (?, ?, ?, ?)",
        (guild_id, group_id, channel_id, language)
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

def get_all_groups(guild_id: int) -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT group_id FROM channel_groups WHERE guild_id = ?", (guild_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]

# ââ Universal channels ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def add_universal_channel(guild_id: int, channel_id: int):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO universal_channels (guild_id, channel_id) VALUES (?, ?)",
        (guild_id, channel_id)
    )
    conn.commit()
    conn.close()

def is_universal(guild_id: int, channel_id: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM universal_channels WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id)
    ).fetchone()
    conn.close()
    return row is not None

# ââ Message mapping âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

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

# ââ Cleanup âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def reset_guild(guild_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM channel_groups WHERE guild_id = ?", (guild_id,))
    conn.execute("DELETE FROM universal_channels WHERE guild_id = ?", (guild_id,))
    conn.execute("DELETE FROM languages WHERE guild_id = ?", (guild_id,))
    conn.execute("DELETE FROM config WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()
