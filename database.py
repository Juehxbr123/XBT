"""
База данных SQLite с aiosqlite
"""
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import DATABASE_PATH
import asyncio
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self):
        """Подключение к БД"""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info(f"Database connected: {self.db_path}")

    async def close(self):
        """Закрытие соединения"""
        if self._connection:
            await self._connection.close()
            logger.info("Database connection closed")

    async def _create_tables(self):
        """Создание таблиц"""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                tier TEXT DEFAULT NULL,
                subscription_until TIMESTAMP DEFAULT NULL,
                trial_used INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT NULL,
                balance REAL DEFAULT 0,
                filter_retweets INTEGER DEFAULT 1,
                filter_replies INTEGER DEFAULT 1,
                banned INTEGER DEFAULT 0,
                reminder_3_sent INTEGER DEFAULT 0,
                reminder_2_sent INTEGER DEFAULT 0,
                reminder_1_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                twitter_username TEXT NOT NULL,
                last_tweet_id TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                UNIQUE(user_id, twitter_username)
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                tier TEXT NOT NULL,
                invoice_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP DEFAULT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                payment_amount REAL NOT NULL,
                commission REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_tracking_user ON tracking(user_id);
            CREATE INDEX IF NOT EXISTS idx_tracking_username ON tracking(twitter_username);
            CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
            CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
            CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);
        """)
        await self._connection.commit()

    # ============ USERS ============

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить пользователя"""
        async with self._connection.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_user(self, user_id: int, username: str = None, referred_by: int = None) -> Dict[str, Any]:
        """Создать пользователя"""
        await self._connection.execute(
            "INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
            (user_id, username, referred_by)
        )
        await self._connection.commit()
        return await self.get_user(user_id)

    async def update_user(self, user_id: int, **kwargs):
        """Обновить пользователя"""
        if not kwargs:
            return
        
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [user_id]
        
        await self._connection.execute(
            f"UPDATE users SET {fields} WHERE user_id = ?", values
        )
        await self._connection.commit()

    async def activate_trial(self, user_id: int) -> bool:
        """Активировать триал"""
        user = await self.get_user(user_id)
        if user and user["trial_used"]:
            return False
        
        until = datetime.now() + timedelta(days=1)
        await self._connection.execute(
            "UPDATE users SET tier = 'trial', subscription_until = ?, trial_used = 1 WHERE user_id = ?",
            (until, user_id)
        )
        await self._connection.commit()
        return True

    async def activate_subscription(self, user_id: int, tier: str, extend: bool = False):
        """Активировать/продлить подписку"""
        user = await self.get_user(user_id)
        now = datetime.now()
        
        if extend and user.get("subscription_until"):
            # Продление: добавляем к текущей дате истечения
            current_until = user["subscription_until"]
            if isinstance(current_until, str):
                current_until = datetime.fromisoformat(current_until)
            if current_until > now:
                base_date = current_until
            else:
                base_date = now
        else:
            base_date = now
        
        until = base_date + timedelta(days=30)
        
        await self._connection.execute(
            """UPDATE users SET 
               tier = ?, 
               subscription_until = ?,
               reminder_3_sent = 0,
               reminder_2_sent = 0,
               reminder_1_sent = 0
               WHERE user_id = ?""",
            (tier, until, user_id)
        )
        await self._connection.commit()

    async def expire_subscription(self, user_id: int):
        """Истечение подписки"""
        await self._connection.execute(
            "UPDATE users SET tier = NULL, subscription_until = NULL WHERE user_id = ?",
            (user_id,)
        )
        await self._connection.commit()

    async def ban_user(self, user_id: int):
        """Забанить пользователя"""
        async with self._lock:
            await self._connection.execute(
                "UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,)
            )
            await self._connection.execute(
                "DELETE FROM tracking WHERE user_id = ?", (user_id,)
            )
            await self._connection.commit()

    async def unban_user(self, user_id: int):
        """Разбанить пользователя"""
        await self._connection.execute(
            "UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,)
        )
        await self._connection.commit()

    async def add_balance(self, user_id: int, amount: float):
        """Добавить баланс (атомарно)"""
        async with self._lock:
            await self._connection.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await self._connection.commit()

    async def deduct_balance(self, user_id: int, amount: float) -> float:
        """Списать баланс, вернуть сколько списано"""
        async with self._lock:
            user = await self.get_user(user_id)
            current = user.get("balance", 0)
            deducted = min(current, amount)
            
            if deducted > 0:
                await self._connection.execute(
                    "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                    (deducted, user_id)
                )
                await self._connection.commit()
            
            return deducted

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Найти пользователя по username"""
        clean_username = username.lstrip("@").lower()
        async with self._connection.execute(
            "SELECT * FROM users WHERE LOWER(username) = ?", (clean_username,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_expiring_users(self, days: int) -> List[Dict[str, Any]]:
        """Получить юзеров с истекающей подпиской"""
        target_date = datetime.now() + timedelta(days=days)
        next_date = datetime.now() + timedelta(days=days + 1)
        
        async with self._connection.execute(
            """SELECT * FROM users 
               WHERE subscription_until IS NOT NULL 
               AND subscription_until >= ? 
               AND subscription_until < ?
               AND banned = 0""",
            (target_date.isoformat(), next_date.isoformat())
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_expired_users(self) -> List[Dict[str, Any]]:
        """Получить юзеров с истекшей подпиской"""
        now = datetime.now()
        
        async with self._connection.execute(
            """SELECT * FROM users 
               WHERE subscription_until IS NOT NULL 
               AND subscription_until < ?
               AND tier IS NOT NULL""",
            (now.isoformat(),)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ============ REFERRALS ============

    async def get_user_referrals(self, user_id: int) -> List[Dict[str, Any]]:
        """Получить список приглашённых пользователей"""
        async with self._connection.execute(
            """SELECT u.user_id, u.username, 
                      (SELECT COUNT(*) FROM referrals r WHERE r.referred_id = u.user_id AND r.referrer_id = ?) > 0 as has_paid
               FROM users u 
               WHERE u.referred_by = ?
               ORDER BY u.created_at DESC""",
            (user_id, user_id)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_referral_commission(self, referrer_id: int, referred_id: int, 
                                      payment_amount: float, commission: float):
        """Начислить реферальную комиссию"""
        async with self._lock:
            await self._connection.execute(
                """INSERT INTO referrals (referrer_id, referred_id, payment_amount, commission)
                   VALUES (?, ?, ?, ?)""",
                (referrer_id, referred_id, payment_amount, commission)
            )
            await self._connection.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (commission, referrer_id)
            )
            await self._connection.commit()

    async def get_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """Статистика рефералов"""
        # Приглашённые
        async with self._connection.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE referred_by = ?", (user_id,)
        ) as cursor:
            invited = (await cursor.fetchone())["cnt"]
        
        # Оплатившие (уникальные)
        async with self._connection.execute(
            "SELECT COUNT(DISTINCT referred_id) as cnt FROM referrals WHERE referrer_id = ?",
            (user_id,)
        ) as cursor:
            paid = (await cursor.fetchone())["cnt"]
        
        # Заработано
        async with self._connection.execute(
            "SELECT COALESCE(SUM(commission), 0) as total FROM referrals WHERE referrer_id = ?",
            (user_id,)
        ) as cursor:
            earned = (await cursor.fetchone())["total"]
        
        return {"invited": invited, "paid": paid, "earned": round(earned, 2)}

    # ============ TRACKING ============

    async def get_user_tracking(self, user_id: int) -> List[Dict[str, Any]]:
        """Получить отслеживаемые аккаунты пользователя"""
        async with self._connection.execute(
            "SELECT * FROM tracking WHERE user_id = ? ORDER BY added_at",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_tracking(self, user_id: int, twitter_username: str) -> bool:
        """Добавить отслеживание"""
        try:
            await self._connection.execute(
                "INSERT INTO tracking (user_id, twitter_username) VALUES (?, ?)",
                (user_id, twitter_username.lower())
            )
            await self._connection.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_tracking(self, user_id: int, twitter_username: str):
        """Удалить отслеживание"""
        await self._connection.execute(
            "DELETE FROM tracking WHERE user_id = ? AND twitter_username = ?",
            (user_id, twitter_username.lower())
        )
        await self._connection.commit()

    async def get_user_tracking_count(self, user_id: int) -> int:
        """Количество отслеживаемых аккаунтов"""
        async with self._connection.execute(
            "SELECT COUNT(*) as cnt FROM tracking WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["cnt"] if row else 0

    async def get_all_tracking_targets(self) -> List[str]:
        """Все уникальные отслеживаемые аккаунты (активных юзеров)"""
        async with self._connection.execute(
            """SELECT DISTINCT t.twitter_username 
               FROM tracking t
               JOIN users u ON t.user_id = u.user_id
               WHERE u.banned = 0 
               AND u.tier IS NOT NULL
               AND u.subscription_until > datetime('now')"""
        ) as cursor:
            rows = await cursor.fetchall()
            return [row["twitter_username"] for row in rows]

    async def get_users_tracking(self, twitter_username: str) -> List[Dict[str, Any]]:
        """Получить всех юзеров, отслеживающих данный аккаунт"""
        async with self._connection.execute(
            """SELECT u.*, t.last_tweet_id 
               FROM users u
               JOIN tracking t ON u.user_id = t.user_id
               WHERE t.twitter_username = ?
               AND u.banned = 0
               AND u.tier IS NOT NULL
               AND u.subscription_until > datetime('now')""",
            (twitter_username.lower(),)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_last_tweet_id(self, twitter_username: str, tweet_id: str):
        """Обновить ID последнего твита"""
        await self._connection.execute(
            "UPDATE tracking SET last_tweet_id = ? WHERE twitter_username = ?",
            (tweet_id, twitter_username.lower())
        )
        await self._connection.commit()

    async def get_tracking_last_tweet_id(self, twitter_username: str) -> Optional[str]:
        """Получить last_tweet_id для аккаунта"""
        async with self._connection.execute(
            "SELECT last_tweet_id FROM tracking WHERE twitter_username = ? LIMIT 1",
            (twitter_username.lower(),)
        ) as cursor:
            row = await cursor.fetchone()
            return row["last_tweet_id"] if row else None

    # ============ PAYMENTS ============

    async def create_payment(self, user_id: int, amount: float, currency: str, 
                            tier: str, invoice_id: str = None) -> int:
        """Создать запись об оплате"""
        cursor = await self._connection.execute(
            """INSERT INTO payments (user_id, amount, currency, tier, invoice_id, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (user_id, amount, currency, tier, invoice_id)
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_payment_by_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Получить платёж по invoice_id"""
        async with self._connection.execute(
            "SELECT * FROM payments WHERE invoice_id = ?", (invoice_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def complete_payment(self, invoice_id: str):
        """Отметить платёж как оплаченный"""
        await self._connection.execute(
            "UPDATE payments SET status = 'paid', paid_at = ? WHERE invoice_id = ?",
            (datetime.now(), invoice_id)
        )
        await self._connection.commit()

    async def expire_payment(self, invoice_id: str):
        """Отметить платёж как истекший"""
        await self._connection.execute(
            "UPDATE payments SET status = 'expired' WHERE invoice_id = ?",
            (invoice_id,)
        )
        await self._connection.commit()

    # ============ ADMIN STATS ============

    async def get_admin_stats(self) -> Dict[str, Any]:
        """Статистика для админа"""
        stats = {}
        
        async with self._connection.execute("SELECT COUNT(*) as cnt FROM users") as cursor:
            stats["total_users"] = (await cursor.fetchone())["cnt"]
        
        for tier in ["starter", "pro", "business"]:
            async with self._connection.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE tier = ? AND subscription_until > datetime('now')",
                (tier,)
            ) as cursor:
                stats[tier] = (await cursor.fetchone())["cnt"]
        
        stats["active_subs"] = stats["starter"] + stats["pro"] + stats["business"]
        
        async with self._connection.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'paid'"
        ) as cursor:
            stats["total_income"] = round((await cursor.fetchone())["total"], 2)
        
        month_ago = (datetime.now() - timedelta(days=30)).isoformat()
        async with self._connection.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'paid' AND paid_at > ?",
            (month_ago,)
        ) as cursor:
            stats["month_income"] = round((await cursor.fetchone())["total"], 2)
        
        async with self._connection.execute(
            "SELECT COUNT(DISTINCT twitter_username) as cnt FROM tracking"
        ) as cursor:
            stats["tracking"] = (await cursor.fetchone())["cnt"]
        
        async with self._connection.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE banned = 1"
        ) as cursor:
            stats["banned"] = (await cursor.fetchone())["cnt"]
        
        return stats


# Глобальный инстанс
db = Database()
