import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bot.db")


class Database:
    def __init__(self):
        self.db = None

    async def connect(self):
        self.db = await aiosqlite.connect(DB_PATH)
        self.db.row_factory = aiosqlite.Row
        await self._create_tables()

    async def _create_tables(self):
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                mod_log_channel INTEGER DEFAULT 0,
                ticket_category INTEGER DEFAULT 0,
                ticket_log_channel INTEGER DEFAULT 0,
                welcome_channel INTEGER DEFAULT 0,
                welcome_message TEXT DEFAULT 'Welcome {user} to {server}!',
                premium_until REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                timestamp REAL
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                user_id INTEGER,
                status TEXT DEFAULT 'open',
                created_at REAL
            );

            CREATE TABLE IF NOT EXISTS levels (
                user_id INTEGER,
                guild_id INTEGER,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, guild_id)
            );

            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER,
                guild_id INTEGER,
                balance INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );

            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                prize TEXT,
                winners INTEGER,
                ends_at REAL,
                host_id INTEGER,
                ended INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS premium_keys (
                key TEXT PRIMARY KEY,
                duration_days INTEGER,
                used_by INTEGER DEFAULT 0,
                created_at REAL
            );

            CREATE TABLE IF NOT EXISTS daily_rewards (
                user_id INTEGER,
                guild_id INTEGER,
                last_claim REAL,
                streak INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            );
        """)
        await self.db.commit()

    async def execute(self, query, params=None):
        if params is None:
            params = []
        cur = await self.db.execute(query, params)
        await self.db.commit()
        return cur

    async def fetchone(self, query, params=None):
        if params is None:
            params = []
        cur = await self.db.execute(query, params)
        return await cur.fetchone()

    async def fetchall(self, query, params=None):
        if params is None:
            params = []
        cur = await self.db.execute(query, params)
        return await cur.fetchall()

    async def close(self):
        if self.db:
            await self.db.close()


db = Database()
