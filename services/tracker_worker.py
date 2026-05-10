"""
Воркер отслеживания Twitter
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from aiogram import Bot
from database import db
from services.twitter import twitter_service, Tweet
from services.translator import translate_to_russian
from locales import get_text
import logging

logger = logging.getLogger(__name__)
MSK = timezone(timedelta(hours=3))


class TrackerWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self._task: asyncio.Task = None

    def calculate_interval(self, num_targets: int) -> float:
        num_accounts = twitter_service.get_available_accounts_count()
        if num_accounts <= 0:
            return 30.0
        if num_targets <= 0:
            return 5.0
        interval = (num_targets * 60) / (33 * num_accounts)
        return max(3.0, min(30.0, interval))

    async def start(self):
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("Tracker worker started")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Tracker worker stopped")

    async def _worker_loop(self):
        cycle = 0
        while self.running:
            try:
                targets = await db.get_all_tracking_targets()
                if not targets:
                    await asyncio.sleep(5)
                    continue

                cycle += 1
                interval = self.calculate_interval(len(targets))

                if cycle % 20 == 1:
                    avail = twitter_service.get_available_accounts_count()
                    total = len(twitter_service.accounts)
                    logger.info(f"Цикл #{cycle} | Целей: {len(targets)} | Акков: {avail}/{total} | {interval:.1f}с")

                start = time.time()
                tasks = [self._process_target(u) for u in targets]
                await asyncio.gather(*tasks)

                elapsed = time.time() - start
                sleep_time = max(1.0, interval - elapsed)
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)

    async def _process_target(self, username: str):
        try:
            tweets = await twitter_service.fetch_tweets(username)
            if not tweets:
                return

            last_tweet_id = await db.get_tracking_last_tweet_id(username)

            new_tweets = []
            for tweet in tweets:
                try:
                    if last_tweet_id and int(tweet.id) <= int(last_tweet_id):
                        break
                    new_tweets.append(tweet)
                except (ValueError, TypeError):
                    continue

            if not new_tweets:
                return

            await db.update_last_tweet_id(username, new_tweets[0].id)

            if not last_tweet_id:
                logger.info(f"Init @{username}, id={new_tweets[0].id}")
                users = await db.get_users_tracking(username)
                if users and new_tweets:
                    await self._send_notifications(new_tweets[-1], users)
                return

            users = await db.get_users_tracking(username)
            if not users:
                return

            for tweet in sorted(new_tweets, key=lambda t: int(t.id)):
                logger.info(f"🔔 @{username} ID:{tweet.id}")
                await self._send_notifications(tweet, users)
                await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"@{username} error: {e}")

    async def _send_notifications(self, tweet: Tweet, users: List[Dict]):
        # Кэш перевода (один перевод для всех юзеров)
        translation_cache = None
        translation_done = False

        for user in users:
            try:
                if tweet.is_retweet and not user.get("filter_retweets", True):
                    continue
                if tweet.is_reply and not user.get("filter_replies", True):
                    continue

                # Перевод
                translation = None
                if user.get("filter_translate"):
                    if not translation_done:
                        translation_cache = await translate_to_russian(tweet.text)
                        translation_done = True
                    translation = translation_cache

                message = self._format_tweet_message(tweet, translation)

                if tweet.media_url:
                    try:
                        await self.bot.send_photo(chat_id=user["user_id"], photo=tweet.media_url,
                                                  caption=message, parse_mode="HTML")
                    except:
                        await self.bot.send_message(chat_id=user["user_id"], text=message, parse_mode="HTML")
                else:
                    await self.bot.send_message(chat_id=user["user_id"], text=message, parse_mode="HTML")

            except Exception as e:
                logger.error(f"Send to {user['user_id']}: {e}")

    def _format_tweet_message(self, tweet: Tweet, translation: str = None) -> str:
        if tweet.is_retweet:
            header = get_text("alert_retweet", username=tweet.author_username)
            if tweet.retweeted_from:
                header += f"\n<i>Оригинал: @{tweet.retweeted_from}</i>"
        elif tweet.is_reply:
            header = get_text("alert_reply", username=tweet.author_username)
        else:
            header = get_text("alert_new_post", username=tweet.author_username)

        text = tweet.text[:500] + ("..." if len(tweet.text) > 500 else "")
        msk_time = tweet.created_at.astimezone(MSK)
        date_str = msk_time.strftime("%d.%m.%Y %H:%M")
        footer = get_text("alert_footer", date=date_str, link=tweet.url)

        msg = f"{header}\n\n{text}{footer}"

        if translation:
            msg += get_text("alert_translation", text=translation[:500])

        return msg


tracker_worker: TrackerWorker = None

def init_tracker_worker(bot: Bot) -> TrackerWorker:
    global tracker_worker
    tracker_worker = TrackerWorker(bot)
    return tracker_worker
