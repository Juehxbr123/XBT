"""
Конфигурация бота из .env файла
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Tuple, Optional

# Определяем директорию бота
BOT_DIR = Path(__file__).parent.absolute()

# Загружаем .env из директории бота
load_dotenv(BOT_DIR / ".env")

# Telegram
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "support")

# Проверка обязательных параметров
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не задан в .env")
    sys.exit(1)

if not ADMIN_ID:
    print("❌ Ошибка: ADMIN_ID не задан в .env")
    sys.exit(1)

# CryptoBot
CRYPTOBOT_TOKEN: str = os.getenv("CRYPTOBOT_TOKEN", "")
CRYPTOBOT_API_URL: str = "https://pay.crypt.bot/api"

if not CRYPTOBOT_TOKEN:
    print("⚠️ Предупреждение: CRYPTOBOT_TOKEN не задан, оплата не будет работать")

# Twitter аккаунты (до 10)
def get_twitter_accounts() -> List[Tuple[str, str]]:
    """Получить список Twitter аккаунтов (auth_token, ct0)"""
    accounts = []
    
    # Основной аккаунт
    main_auth = os.getenv("TWITTER_AUTH_TOKEN")
    main_ct0 = os.getenv("TWITTER_CT0")
    if main_auth and main_ct0:
        accounts.append((main_auth, main_ct0))
    
    # Дополнительные аккаунты (1-10)
    for i in range(1, 11):
        auth = os.getenv(f"TWITTER_ACCOUNT_{i}_AUTH")
        ct0 = os.getenv(f"TWITTER_ACCOUNT_{i}_CT0")
        if auth and ct0:
            accounts.append((auth, ct0))
    
    return accounts

TWITTER_ACCOUNTS: List[Tuple[str, str]] = get_twitter_accounts()

if not TWITTER_ACCOUNTS:
    print("⚠️ Предупреждение: Twitter аккаунты не настроены, будет использоваться только Nitter")

# Прокси (опционально)
PROXY: Optional[str] = os.getenv("PROXY")

# Twitter API константы
TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
TWITTER_GRAPHQL_USER = "https://x.com/i/api/graphql/IGgvgiOx4QZndDHuD3x9TQ/UserByScreenName"
TWITTER_GRAPHQL_TWEETS = "https://x.com/i/api/graphql/r4C5KgRvWxMOHyE4sZRmzg/UserTweets"

# Nitter зеркала
NITTER_MIRRORS = [
    "https://nitter.net",
    "https://xcancel.com",
    "https://nitter.poast.org",
]

# Тарифы
TIERS = {
    "starter": {"price": 5, "accounts": 5, "name": "Starter"},
    "pro": {"price": 10, "accounts": 10, "name": "Pro"},
    "business": {"price": 15, "accounts": 15, "name": "Business"},
}

# Триал
TRIAL_DAYS = 1
TRIAL_ACCOUNTS = 1

# Рефералка
REFERRAL_PERCENT = 10

# База данных (в директории бота)
DATABASE_PATH = str(BOT_DIR / "bot_database.db")

# Логи
LOGS_DIR = BOT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
