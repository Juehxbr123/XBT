"""
Twitter сервис: GraphQL API + Nitter fallback
"""
import httpx
import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET
from config import (
    TWITTER_BEARER, TWITTER_GRAPHQL_USER, TWITTER_GRAPHQL_TWEETS,
    TWITTER_ACCOUNTS, NITTER_MIRRORS, PROXY
)
import logging

logger = logging.getLogger(__name__)


@dataclass
class TwitterAccount:
    """Twitter аккаунт для API запросов"""
    auth_token: str
    ct0: str
    rate_limited_until: datetime = field(default_factory=lambda: datetime.min)
    request_count: int = 0
    
    def is_available(self) -> bool:
        return datetime.now() > self.rate_limited_until
    
    def mark_rate_limited(self, reset_time: int):
        """Пометить как rate limited"""
        self.rate_limited_until = datetime.fromtimestamp(reset_time)
        logger.warning(f"Account rate limited until {self.rate_limited_until}")
    
    def increment_count(self):
        self.request_count += 1


@dataclass
class Tweet:
    """Твит"""
    id: str
    text: str
    created_at: datetime
    author_username: str
    url: str
    is_retweet: bool = False
    is_reply: bool = False
    retweeted_from: str = None
    media_url: str = None  # Первое фото
    

class TwitterService:
    """Сервис для работы с Twitter"""
    
    # GraphQL features
    USER_FEATURES = {
        "hidden_profile_subscriptions_enabled": True,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "rweb_tipjar_consumption_enabled": False,
        "verified_phone_label_enabled": False,
        "subscriptions_verification_info_is_identity_verified_enabled": True,
        "highlights_tweets_tab_ui_enabled": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
    }
    
    TWEETS_FEATURES = {
        **USER_FEATURES,
        "rweb_video_screen_enabled": False,
        "rweb_cashtags_enabled": True,
        "communities_web_enable_tweet_community_results_fetch": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
    }
    
    def __init__(self):
        self.accounts: List[TwitterAccount] = [
            TwitterAccount(auth, ct0) 
            for auth, ct0 in TWITTER_ACCOUNTS
        ]
        self.nitter_index = 0
        
        # HTTP клиент
        proxy = PROXY if PROXY else None
        self.client = httpx.AsyncClient(
            timeout=15.0,
            proxy=proxy,
            follow_redirects=True
        )
    
    def _get_best_account(self) -> Optional[TwitterAccount]:
        """Выбрать лучший аккаунт (минимум запросов, не в rate limit)"""
        available = [acc for acc in self.accounts if acc.is_available()]
        if not available:
            return None
        return min(available, key=lambda a: a.request_count)
    
    def get_available_accounts_count(self) -> int:
        """Количество доступных аккаунтов"""
        return len([acc for acc in self.accounts if acc.is_available()])
    
    def all_rate_limited(self) -> bool:
        """Все аккаунты в rate limit?"""
        return all(not acc.is_available() for acc in self.accounts)
    
    def _get_headers(self, account: TwitterAccount) -> Dict[str, str]:
        """Заголовки для GraphQL API"""
        return {
            "authorization": f"Bearer {TWITTER_BEARER}",
            "x-csrf-token": account.ct0,
            "cookie": f"auth_token={account.auth_token}; ct0={account.ct0}",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    async def check_user_exists(self, username: str) -> Tuple[bool, Optional[str]]:
        """Проверить существование пользователя, вернуть (exists, user_id)"""
        # Пробуем GraphQL
        account = self._get_best_account()
        if account:
            try:
                variables = {
                    "screen_name": username.lstrip("@"),
                    "withGrokTranslatedBio": True
                }
                field_toggles = {
                    "withPayments": False,
                    "withAuxiliaryUserLabels": True
                }
                
                params = {
                    "variables": json.dumps(variables),
                    "features": json.dumps(self.USER_FEATURES),
                    "fieldToggles": json.dumps(field_toggles)
                }
                
                response = await self.client.get(
                    TWITTER_GRAPHQL_USER,
                    headers=self._get_headers(account),
                    params=params
                )
                
                account.increment_count()
                
                if response.status_code == 429:
                    reset = int(response.headers.get("x-rate-limit-reset", 0))
                    account.mark_rate_limited(reset)
                elif response.status_code == 200:
                    data = response.json()
                    user = data.get("data", {}).get("user", {}).get("result", {})
                    if user and user.get("__typename") != "UserUnavailable":
                        return True, user.get("rest_id")
                    return False, None
                    
            except Exception as e:
                logger.error(f"GraphQL user check error: {e}")
        
        # Fallback на Nitter
        try:
            for mirror in NITTER_MIRRORS:
                try:
                    response = await self.client.get(
                        f"{mirror}/{username.lstrip('@')}/rss",
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        return True, None
                except:
                    continue
        except Exception as e:
            logger.error(f"Nitter user check error: {e}")
        
        return False, None
    
    async def _fetch_tweets_graphql(self, username: str, user_id: str = None) -> Optional[List[Tweet]]:
        """Получить твиты через GraphQL API"""
        account = self._get_best_account()
        if not account:
            return None
        
        # Если нет user_id, получаем его
        if not user_id:
            exists, user_id = await self.check_user_exists(username)
            if not exists or not user_id:
                return None
        
        try:
            variables = {
                "userId": user_id,
                "count": 10,
                "includePromotedContent": False,
                "withVoice": True
            }
            field_toggles = {"withArticlePlainText": False}
            
            params = {
                "variables": json.dumps(variables),
                "features": json.dumps(self.TWEETS_FEATURES),
                "fieldToggles": json.dumps(field_toggles)
            }
            
            response = await self.client.get(
                TWITTER_GRAPHQL_TWEETS,
                headers=self._get_headers(account),
                params=params
            )
            
            account.increment_count()
            
            if response.status_code == 429:
                reset = int(response.headers.get("x-rate-limit-reset", 0))
                account.mark_rate_limited(reset)
                return None
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            tweets = []
            
            # Парсим timeline
            instructions = (
                data.get("data", {})
                .get("user", {})
                .get("result", {})
                .get("timeline_v2", {})
                .get("timeline", {})
                .get("instructions", [])
            )
            
            for instruction in instructions:
                if instruction.get("type") == "TimelineAddEntries":
                    for entry in instruction.get("entries", []):
                        tweet = self._parse_graphql_tweet(entry, username)
                        if tweet:
                            tweets.append(tweet)
            
            return tweets
            
        except Exception as e:
            logger.error(f"GraphQL tweets error: {e}")
            return None
    
    def _parse_graphql_tweet(self, entry: Dict, username: str) -> Optional[Tweet]:
        """Парсинг твита из GraphQL ответа"""
        try:
            content = entry.get("content", {})
            if content.get("entryType") != "TimelineTimelineItem":
                return None
            
            item = content.get("itemContent", {})
            if item.get("itemType") != "TimelineTweet":
                return None
            
            result = item.get("tweet_results", {}).get("result", {})
            
            # Обработка ретвитов
            legacy = result.get("legacy", {})
            is_retweet = "retweeted_status_result" in legacy
            retweeted_from = None
            
            if is_retweet:
                rt_result = legacy["retweeted_status_result"].get("result", {})
                rt_legacy = rt_result.get("legacy", {})
                rt_user = rt_result.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
                retweeted_from = rt_user.get("screen_name")
                text = rt_legacy.get("full_text", "")
                media_entities = rt_legacy.get("extended_entities", {}).get("media", [])
            else:
                text = legacy.get("full_text", "")
                media_entities = legacy.get("extended_entities", {}).get("media", [])
            
            # Проверка reply
            is_reply = legacy.get("in_reply_to_status_id_str") is not None
            
            # Медиа (первое фото)
            media_url = None
            for media in media_entities:
                if media.get("type") == "photo":
                    media_url = media.get("media_url_https")
                    break
            
            # Дата
            created_at_str = legacy.get("created_at", "")
            try:
                created_at = datetime.strptime(
                    created_at_str, "%a %b %d %H:%M:%S %z %Y"
                )
            except:
                created_at = datetime.now(timezone.utc)
            
            tweet_id = legacy.get("id_str", result.get("rest_id", ""))
            
            return Tweet(
                id=tweet_id,
                text=text,
                created_at=created_at,
                author_username=username,
                url=f"https://x.com/{username}/status/{tweet_id}",
                is_retweet=is_retweet,
                is_reply=is_reply,
                retweeted_from=retweeted_from,
                media_url=media_url
            )
            
        except Exception as e:
            logger.error(f"Parse tweet error: {e}")
            return None
    
    async def _fetch_tweets_nitter(self, username: str) -> Optional[List[Tweet]]:
        """Получить твиты через Nitter RSS"""
        username = username.lstrip("@")
        
        for mirror in NITTER_MIRRORS:
            try:
                response = await self.client.get(
                    f"{mirror}/{username}/rss",
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    continue
                
                # Парсим RSS
                root = ET.fromstring(response.text)
                tweets = []
                
                for item in root.findall(".//item")[:10]:
                    tweet = self._parse_nitter_item(item, username, mirror)
                    if tweet:
                        tweets.append(tweet)
                
                if tweets:
                    return tweets
                    
            except Exception as e:
                logger.error(f"Nitter {mirror} error: {e}")
                continue
        
        return None
    
    def _parse_nitter_item(self, item: ET.Element, username: str, mirror: str) -> Optional[Tweet]:
        """Парсинг RSS item от Nitter"""
        try:
            title = item.find("title").text or ""
            link = item.find("link").text or ""
            description = item.find("description").text or ""
            pub_date = item.find("pubDate").text or ""
            
            # Извлекаем tweet_id из ссылки
            tweet_id_match = re.search(r"/status/(\d+)", link)
            tweet_id = tweet_id_match.group(1) if tweet_id_match else ""
            
            # Определяем тип
            is_retweet = title.startswith("RT by")
            is_reply = title.startswith("R to")
            
            # Извлекаем retweeted_from
            retweeted_from = None
            if is_retweet:
                rt_match = re.search(r"RT by @\w+: (@(\w+))?", title)
                if rt_match:
                    retweeted_from = rt_match.group(2)
            
            # Очищаем текст
            text = re.sub(r"<[^>]+>", "", description)
            text = text.strip()
            
            # Ищем медиа
            media_url = None
            img_match = re.search(r'<img src="([^"]+)"', description)
            if img_match:
                media_url = img_match.group(1)
                if media_url.startswith("/"):
                    media_url = mirror + media_url
            
            # Дата
            try:
                created_at = datetime.strptime(
                    pub_date, "%a, %d %b %Y %H:%M:%S %Z"
                ).replace(tzinfo=timezone.utc)
            except:
                created_at = datetime.now(timezone.utc)
            
            # Преобразуем ссылку в x.com
            url = f"https://x.com/{username}/status/{tweet_id}"
            
            return Tweet(
                id=tweet_id,
                text=text,
                created_at=created_at,
                author_username=username,
                url=url,
                is_retweet=is_retweet,
                is_reply=is_reply,
                retweeted_from=retweeted_from,
                media_url=media_url
            )
            
        except Exception as e:
            logger.error(f"Parse Nitter item error: {e}")
            return None
    
    async def fetch_tweets(self, username: str) -> List[Tweet]:
        """
        Получить твиты (гонка GraphQL vs Nitter)
        """
        username = username.lstrip("@").lower()
        
        # Если все аккаунты в rate limit - только Nitter
        if self.all_rate_limited():
            result = await self._fetch_tweets_nitter(username)
            return result or []
        
        # Запускаем гонку
        graphql_task = asyncio.create_task(self._fetch_tweets_graphql(username))
        nitter_task = asyncio.create_task(self._fetch_tweets_nitter(username))
        
        done, pending = await asyncio.wait(
            [graphql_task, nitter_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Отменяем проигравших
        for task in pending:
            task.cancel()
        
        # Берём результат победителя
        for task in done:
            try:
                result = task.result()
                if result:
                    return result
            except Exception as e:
                logger.error(f"Task error: {e}")
        
        # Если первый не вернул данные, ждём второго
        for task in pending:
            try:
                await task
                result = task.result()
                if result:
                    return result
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Pending task error: {e}")
        
        return []
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.aclose()


# Глобальный инстанс
twitter_service = TwitterService()
