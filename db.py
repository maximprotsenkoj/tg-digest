import aiosqlite


async def init_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_channels (
                user_id INTEGER NOT NULL,
                channel  TEXT    NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, channel)
            )
        """)
        await db.commit()


async def get_channels(db_path: str, user_id: int) -> list[str]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT channel FROM user_channels WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def add_channel(db_path: str, user_id: int, channel: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR IGNORE INTO user_channels (user_id, channel) VALUES (?, ?)",
            (user_id, channel),
        )
        await db.commit()


async def remove_channel(db_path: str, user_id: int, channel: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "DELETE FROM user_channels WHERE user_id = ? AND channel = ?",
            (user_id, channel),
        )
        await db.commit()
