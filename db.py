import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "")

_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_id      BIGINT PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                last_seen  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_channels (
                user_id  BIGINT NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
                channel  TEXT   NOT NULL,
                added_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (user_id, channel)
            )
        """)


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool


async def upsert_user(tg_id: int, username: str | None, first_name: str | None):
    async with _get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO users (tg_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (tg_id) DO UPDATE
              SET username   = EXCLUDED.username,
                  first_name = EXCLUDED.first_name,
                  last_seen  = NOW()
        """, tg_id, username, first_name)


async def get_channels(user_id: int) -> list[str]:
    async with _get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT channel FROM user_channels WHERE user_id = $1 ORDER BY added_at",
            user_id,
        )
        return [r["channel"] for r in rows]


async def add_channel(user_id: int, channel: str):
    async with _get_pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_channels (user_id, channel)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            user_id, channel,
        )


async def remove_channel(user_id: int, channel: str):
    async with _get_pool().acquire() as conn:
        await conn.execute(
            "DELETE FROM user_channels WHERE user_id = $1 AND channel = $2",
            user_id, channel,
        )
