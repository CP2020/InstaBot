import asyncio
import logging
from .stats_service import StatsService
from .user import User

LOGGER = logging.getLogger('instabot')
USERS_LIMIT = 1000

class UserService:
    def __init__(self, client):
        self._client = client
        self._stats_service = StatsService.get_instance()

    @asyncio.coroutine
    def run(self):
        while True:
            try:
                yield from self._ensure_enough_users()
            except InstagramLimitError as e:
                LOGGER.debug('Fetching users. Instagram limits were reached: %s', e)
                yield from asyncio.sleep(60)
            except Exception as e:
                LOGGER.debug('Fetching users. Some troubles: %s', e)
                yield from asyncio.sleep(5)
            else:
                yield from asyncio.sleep(5)

    @asyncio.coroutine
    def _ensure_enough_users(self):
        users_to_follow_count = len(User.select().where(User.subscribed_at == None))
        if users_to_follow_count < USERS_LIMIT:
            last_users_to_follow_count = users_to_follow_count
            for user in User.select().where(User.were_followers_fetched == False).order_by(
                User.following_depth,
                User.created,
                ):
                following_depth = user.following_depth + 1
                for follower_id in (yield from client.get_some_followers(user.instagram_id)):
                    follower, created = User.get_or_create(instagram_id=follower_id)
                    if created:
                        follower.following_depth = following_depth
                        follower.save()
                        users_to_follow_count += 1
                        STATS_SERVICE.increment('users_to_follow_fetched')
                    elif follower.following_depth > following_depth:
                        follower.following_depth = following_depth
                        follower.save()
                if users_to_follow_count >= USERS_LIMIT:
                    break
            LOGGER.debug(
                'Fetching users. %d users fetched.',
                users_to_follow_count - last_users_to_follow_count,
                )
