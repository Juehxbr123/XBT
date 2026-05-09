"""
Воркер отслеживания Twitter аккаунтов
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set
from aiogram import Bot
from aiogram.types import InputMediaPhoto
from database import db
from services.twitter import twitter_service, Tweet
from locales import get_text
import logging

logger = logging.getLogger(__name__)

# Московское время (UTC+3)
MSK = timezone(timedelta(hours=3))


class TrackerWorker:
    """Воркер для отслеживания твитов"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self.rate_limit_multiplier = 1.0
        self._task: asyncio.Task = None
    
    def calculate_interval(self, targets_count: int) -> float:
        """
        Динамический интервал
        Формула: targets * 60 / (33 * available_accounts)
        """
        available = twitter_service.get_available_accounts_count()
        
        if available == 0:
            # Все в rate limit
            self.rate_limit_multiplier = min(self.rate_limit_multiplier * 1.5, 2.0)
            return min(120, 60 * self.rate_limit_multiplier)
        
        # Плавно возвращаем множитель к 1.0
        self.rate_limit_multiplier = max(1.0, self.rate_limit_multiplier * 0.9)
        
        if targets_count == 0:
            return 60
        
        interval = (targets_count * 60) / (33 * available)
        interval *= self.rate_limit_multiplier
        
        # Ограничения
        return max(5, min(60, interval))
    
    async def start(self):
        """Запустить воркер"""
        if self.running:
            return
        
        self.running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("Tracker worker started")
    
    async def stop(self):
        """Остановить воркер"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Tracker worker stopped")
    
    async def _worker_loop(self):
        """Основной цикл воркера"""
        while self.running:
            try:
                # Получаем уникальные цели
                targets = await db.get_all_tracking_targets()
                
                if not targets:
                    await asyncio.sleep(30)
                    continue
                
                logger.info(f"Tracking {len(targets)} unique accounts")
                
                # Обрабатываем каждую цель
                for username in targets:
                    if not self.running:
                        break
                    
                    await self._process_target(username)
                    
                    # Интервал между запросами
                    interval = self.calculate_interval(len(targets))
                    await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(30)
    
    async def _process_target(self, username: str):
        """Обработка одной цели"""
        try:
            # Получаем твиты
            tweets = await twitter_service.fetch_tweets(username)
            
            if not tweets:
                return
            
            # Получаем последний известный ID
            last_tweet_id = await db.get_tracking_last_tweet_id(username)
            
            # Фильтруем новые твиты
            new_tweets = []
            for tweet in tweets:
                if last_tweet_id and int(tweet.id) <= int(last_tweet_id):
                    break
                new_tweets.append(tweet)
            
            if not new_tweets:
                return
            
            # Обновляем last_tweet_id (самый новый)
            await db.update_last_tweet_id(username, new_tweets[0].id)
            
            # Если это первый запуск - не отправляем
            if not last_tweet_id:
                logger.info(f"Initial fetch for @{username}, skipping notifications")
                return
            
            # Получаем юзеров для рассылки
            users = await db.get_users_tracking(username)
            
            # Отправляем уведомления (от старых к новым)
            for tweet in reversed(new_tweets):
                await self._send_notifications(tweet, users)
            
            logger.info(f"Sent {len(new_tweets)} tweets from @{username} to {len(users)} users")
            
        except Exception as e:
            logger.error(f"Process target @{username} error: {e}")
    
    async def _send_notifications(self, tweet: Tweet, users: List[Dict]):
        """Отправить уведомления юзерам"""
        for user in users:
            try:
                # Проверяем фильтры
                if tweet.is_retweet and not user.get("filter_retweets", True):
                    continue
                if tweet.is_reply and not user.get("filter_replies", True):
                    continue
                
                # Формируем сообщение
                message = self._format_tweet_message(tweet)
                
                # Отправляем
                if tweet.media_url:
                    try:
                        await self.bot.send_photo(
                            chat_id=user["user_id"],
                            photo=tweet.media_url,
                            caption=message,
                            parse_mode="HTML"
                        )
                    except Exception:
                        # Если фото не отправилось - отправляем текст
                        await self.bot.send_message(
                            chat_id=user["user_id"],
                            text=message + f"\n\n📷 {tweet.media_url}",
                            parse_mode="HTML",
                            disable_web_page_preview=False
                        )
                else:
                    await self.bot.send_message(
                        chat_id=user["user_id"],
                        text=message,
                        parse_mode="HTML",
                        disable_web_page_preview=False
                    )
                
            except Exception as e:
                logger.error(f"Send notification to {user['user_id']} error: {e}")
    
    def _format_tweet_message(self, tweet: Tweet) -> str:
        """Форматирование сообщения о твите"""
        # Заголовок
        if tweet.is_retweet:
            header = get_text("alert_retweet", username=tweet.author_username)
            if tweet.retweeted_from:
                header += f"\n<i>Оригинал: @{tweet.retweeted_from}</i>"
        elif tweet.is_reply:
            header = get_text("alert_reply", username=tweet.author_username)
        else:
            header = get_text("alert_new_post", username=tweet.author_username)
        
        # Текст твита (ограничиваем)
        text = tweet.text[:500]
        if len(tweet.text) > 500:
            text += "..."
        
        # Дата в МСК
        msk_time = tweet.created_at.astimezone(MSK)
        date_str = msk_time.strftime("%d.%m.%Y %H:%M")
        
        # Собираем сообщение
        footer = get_text("alert_footer", date=date_str, link=tweet.url)
        
        return f"{header}\n\n{text}{footer}"


# Глобальный инстанс (инициализируется в bot.py)
tracker_worker: TrackerWorker = None


def init_tracker_worker(bot: Bot) -> TrackerWorker:
    """Инициализация воркера"""
    global tracker_worker
    tracker_worker = TrackerWorker(bot)
    return tracker_worker
