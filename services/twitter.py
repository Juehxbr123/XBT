"""
Twitter сервис: GraphQL + Nitter
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
    auth_token: str
    ct0: str
    rate_limited_until: datetime = field(default_factory=lambda: datetime.min)
    request_count: int = 0
    
    def is_available(self) -> bool:
        return datetime.now() > self.rate_limited_until
    
    def mark_rate_limited(self, reset_time: int):
        self.rate_limited_until = datetime.fromtimestamp(reset_time)
        logger.warning(f"Account rate limited until {self.rate_limited_until}")
    
    def increment_count(self):
        self.request_count += 1


@dataclass
class Tweet:
    id: str
    text: str
    created_at: datetime
    author_username: str
    url: str
    is_retweet: bool = False
    is_reply: bool = False
    retweeted_from: str = None
    media_url: str = None


# Рабочие Nitter зеркала с RSS (обновлено май 2026)
NITTER_RSS_MIRRORS = [
    "https://xcancel.com",
    "https://nitter.privacyredirect.com",
    "https://nitter.poast.org",
    "https://nitter.net",
]


class TwitterService:
    USER_FEATURES = {
        "hidden_profile_subscriptions_enabled": True,
        "rweb_tipjar_consumption_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "verified_phone_label_enabled": False,
        "subscriptions_verification_info_is_identity_verified_enabled": True,
        "highlights_tweets_tab_ui_enabled": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
    }
    
    TWEETS_FEATURES = {
        **USER_FEATURES,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "freedom_of_speech_not_reach_fetch_enabled": True,
    }
    
    def __init__(self):
        self.accounts: List[TwitterAccount] = [
            TwitterAccount(auth, ct0) for auth, ct0 in TWITTER_ACCOUNTS
        ]
        self.client = httpx.AsyncClient(
            timeout=15.0,
            proxy=PROXY,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        self._nitter_fails: Dict[str, datetime] = {}  # зеркало -> время последней ошибки
    
    def _get_best_account(self) -> Optional[TwitterAccount]:
        available = [acc for acc in self.accounts if acc.is_available()]
        if not available:
            return None
        return min(available, key=lambda a: a.request_count)
    
    def get_available_accounts_count(self) -> int:
        return len([acc for acc in self.accounts if acc.is_available()])
    
    def all_rate_limited(self) -> bool:
        return len(self.accounts) == 0 or all(not acc.is_available() for acc in self.accounts)
    
    def _get_headers(self, account: TwitterAccount) -> Dict[str, str]:
        return {
            "authorization": f"Bearer {TWITTER_BEARER}",
            "x-csrf-token": account.ct0,
            "cookie": f"auth_token={account.auth_token}; ct0={account.ct0}",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
    
    def _get_working_mirrors(self) -> List[str]:
        """Получить зеркала, исключая недавно упавшие (кулдаун 5 мин)"""
        now = datetime.now()
        working = []
        for mirror in NITTER_RSS_MIRRORS:
            fail_time = self._nitter_fails.get(mirror)
            if fail_time is None or (now - fail_time).total_seconds() > 300:
                working.append(mirror)
        # Если все в кулдауне — пробуем все
        return working if working else NITTER_RSS_MIRRORS
    
    async def check_user_exists(self, username: str) -> Tuple[bool, Optional[str]]:
        """Проверить существование пользователя"""
        username = username.lstrip("@")
        
        # Пробуем GraphQL
        account = self._get_best_account()
        if account:
            try:
                params = {
                    "variables": json.dumps({"screen_name": username}),
                    "features": json.dumps(self.USER_FEATURES),
                }
                response = await self.client.get(
                    TWITTER_GRAPHQL_USER,
                    headers=self._get_headers(account),
                    params=params
                )
                account.increment_count()
                
                if response.status_code == 429:
                    reset = int(response.headers.get("x-rate-limit-reset", 0))
                    if reset > 0:
                        account.mark_rate_limited(reset)
                    else:
                        account.mark_rate_limited(int((datetime.now() + timedelta(minutes=15)).timestamp()))
                elif response.status_code == 200:
                    data = response.json()
                    user = data.get("data", {}).get("user", {}).get("result", {})
                    if user and user.get("__typename") not in ("UserUnavailable", None):
                        user_id = user.get("rest_id")
                        logger.info(f"GraphQL: @{username} exists, id={user_id}")
                        return True, user_id
                    return False, None
            except Exception as e:
                logger.error(f"GraphQL user check error for @{username}: {e}")
        
        # Fallback на Nitter
        for mirror in self._get_working_mirrors():
            try:
                response = await self.client.get(
                    f"{mirror}/{username}/rss",
                    timeout=10.0
                )
                if response.status_code == 200 and len(response.text) > 100:
                    logger.info(f"Nitter ({mirror}): @{username} exists")
                    return True, None
                else:
                    logger.debug(f"Nitter ({mirror}): @{username} status={response.status_code}, len={len(response.text)}")
            except Exception as e:
                logger.warning(f"Nitter {mirror} error checking @{username}: {e}")
                self._nitter_fails[mirror] = datetime.now()
                continue
        
        return False, None
    
    async def _fetch_tweets_graphql(self, username: str, user_id: str = None) -> Optional[List[Tweet]]:
        """Получить твиты через GraphQL API"""
        account = self._get_best_account()
        if not account:
            logger.debug(f"GraphQL: no available accounts for @{username}")
            return None
        
        if not user_id:
            exists, user_id = await self.check_user_exists(username)
            if not exists or not user_id:
                return None
        
        try:
            params = {
                "variables": json.dumps({
                    "userId": user_id,
                    "count": 10,
                    "includePromotedContent": False,
                    "withVoice": True
                }),
                "features": json.dumps(self.TWEETS_FEATURES),
                "fieldToggles": json.dumps({"withArticlePlainText": False})
            }
            
            response = await self.client.get(
                TWITTER_GRAPHQL_TWEETS,
                headers=self._get_headers(account),
                params=params
            )
            account.increment_count()
            
            if response.status_code == 429:
                reset = int(response.headers.get("x-rate-limit-reset", 0))
                if reset > 0:
                    account.mark_rate_limited(reset)
                else:
                    account.mark_rate_limited(int((datetime.now() + timedelta(minutes=15)).timestamp()))
                logger.warning(f"GraphQL 429 for @{username}")
                return None
            
            if response.status_code != 200:
                logger.warning(f"GraphQL {response.status_code} for @{username}")
                return None
            
            data = response.json()
            tweets = []
            
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
            
            if tweets:
                logger.info(f"GraphQL: got {len(tweets)} tweets from @{username}")
            return tweets
            
        except Exception as e:
            logger.error(f"GraphQL tweets error for @{username}: {e}")
            return None
    
    def _parse_graphql_tweet(self, entry: Dict, username: str) -> Optional[Tweet]:
        try:
            content = entry.get("content", {})
            if content.get("entryType") != "TimelineTimelineItem":
                return None
            
            item = content.get("itemContent", {})
            if item.get("itemType") != "TimelineTweet":
                return None
            
            result = item.get("tweet_results", {}).get("result", {})
            if not result or result.get("__typename") == "TweetTombstone":
                return None
            
            # Обработка TweetWithVisibilityResults
            if result.get("__typename") == "TweetWithVisibilityResults":
                result = result.get("tweet", result)
            
            legacy = result.get("legacy", {})
            if not legacy:
                return None
            
            is_retweet = "retweeted_status_result" in legacy
            retweeted_from = None
            
            if is_retweet:
                rt_result = legacy["retweeted_status_result"].get("result", {})
                if rt_result.get("__typename") == "TweetWithVisibilityResults":
                    rt_result = rt_result.get("tweet", rt_result)
                rt_legacy = rt_result.get("legacy", {})
                rt_user = rt_result.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
                retweeted_from = rt_user.get("screen_name")
                text = rt_legacy.get("full_text", "")
                media_entities = rt_legacy.get("extended_entities", {}).get("media", [])
            else:
                text = legacy.get("full_text", "")
                media_entities = legacy.get("extended_entities", {}).get("media", [])
            
            is_reply = legacy.get("in_reply_to_status_id_str") is not None
            
            media_url = None
            for media in media_entities:
                if media.get("type") == "photo":
                    media_url = media.get("media_url_https")
                    break
            
            created_at_str = legacy.get("created_at", "")
            try:
                created_at = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
            except:
                created_at = datetime.now(timezone.utc)
            
            tweet_id = legacy.get("id_str", result.get("rest_id", ""))
            if not tweet_id:
                return None
            
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
            logger.error(f"Parse GraphQL tweet error: {e}")
            return None
    
    async def _fetch_tweets_nitter(self, username: str) -> Optional[List[Tweet]]:
        """Получить твиты через Nitter RSS"""
        username = username.lstrip("@")
        
        mirrors = self._get_working_mirrors()
        
        for mirror in mirrors:
            try:
                response = await self.client.get(
                    f"{mirror}/{username}/rss",
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.debug(f"Nitter {mirror}: status {response.status_code} for @{username}")
                    self._nitter_fails[mirror] = datetime.now()
                    continue
                
                # Проверяем что ответ — валидный XML
                text = response.text.strip()
                if not text or len(text) < 100 or not text.startswith("<?xml") and not text.startswith("<"):
                    logger.debug(f"Nitter {mirror}: empty/invalid response for @{username}")
                    self._nitter_fails[mirror] = datetime.now()
                    continue
                
                root = ET.fromstring(text)
                tweets = []
                
                for item in root.findall(".//item")[:10]:
                    tweet = self._parse_nitter_item(item, username, mirror)
                    if tweet:
                        tweets.append(tweet)
                
                if tweets:
                    logger.info(f"Nitter ({mirror}): got {len(tweets)} tweets from @{username}")
                    # Убираем зеркало из списка ошибок
                    self._nitter_fails.pop(mirror, None)
                    return tweets
                else:
                    logger.debug(f"Nitter {mirror}: 0 parseable tweets for @{username}")
                    
            except ET.ParseError as e:
                logger.warning(f"Nitter {mirror} XML parse error for @{username}: {e}")
                self._nitter_fails[mirror] = datetime.now()
                continue
            except Exception as e:
                logger.warning(f"Nitter {mirror} error for @{username}: {e}")
                self._nitter_fails[mirror] = datetime.now()
                continue
        
        logger.warning(f"All Nitter mirrors failed for @{username}")
        return None
    
    def _parse_nitter_item(self, item: ET.Element, username: str, mirror: str) -> Optional[Tweet]:
        try:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pubdate_el = item.find("pubDate")
            
            if title_el is None or link_el is None:
                return None
            
            title = title_el.text or ""
            link = link_el.text or ""
            description = desc_el.text if desc_el is not None else ""
            pub_date = pubdate_el.text if pubdate_el is not None else ""
            
            tweet_id_match = re.search(r"/status/(\d+)", link)
            tweet_id = tweet_id_match.group(1) if tweet_id_match else ""
            if not tweet_id:
                return None
            
            is_retweet = title.startswith("RT by")
            is_reply = title.startswith("R to")
            
            retweeted_from = None
            if is_retweet:
                rt_match = re.search(r"RT by @\w+: (@(\w+))?", title)
                if rt_match and rt_match.group(2):
                    retweeted_from = rt_match.group(2)
            
            text = re.sub(r"<[^>]+>", "", description or "").strip()
            
            media_url = None
            if description:
                img_match = re.search(r'<img src="([^"]+)"', description)
                if img_match:
                    media_url = img_match.group(1)
                    if media_url.startswith("/"):
                        media_url = mirror + media_url
            
            try:
                created_at = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
            except:
                created_at = datetime.now(timezone.utc)
            
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
            logger.error(f"Parse Nitter item error: {e}")
            return None
    
    async def fetch_tweets(self, username: str) -> List[Tweet]:
        """Получить твиты (гонка GraphQL vs Nitter)"""
        username = username.lstrip("@").lower()
        
        # Если все аккаунты в rate limit — только Nitter
        if self.all_rate_limited():
            logger.debug(f"All accounts rate limited, using Nitter only for @{username}")
            result = await self._fetch_tweets_nitter(username)
            return result or []
        
        # Запускаем оба параллельно
        try:
            graphql_task = asyncio.create_task(self._fetch_tweets_graphql(username))
            nitter_task = asyncio.create_task(self._fetch_tweets_nitter(username))
            
            done, pending = await asyncio.wait(
                [graphql_task, nitter_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=20.0
            )
            
            # Отменяем оставшиеся
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            
            # Берём результат первого завершившегося
            for task in done:
                try:
                    result = task.result()
                    if result:
                        return result
                except Exception as e:
                    logger.error(f"Task error for @{username}: {e}")
            
            # Если первый вернул None, ждём отменённых (может уже успели)
            for task in pending:
                try:
                    result = task.result()
                    if result:
                        return result
                except (asyncio.CancelledError, asyncio.InvalidStateError, Exception):
                    pass
            
        except Exception as e:
            logger.error(f"Fetch tweets race error for @{username}: {e}")
        
        return []
    
    async def close(self):
        await self.client.aclose()


twitter_service = TwitterService()
