import asyncio
import logging
import peewee
from .errors import APIError, APILimitError, APINotAllowedError
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
            LOGGER.debug('UserService cycle')
            try:
                yield from self._ensure_enough_users()
            except APILimitError as e:
                LOGGER.debug('Fetching users. Instagram limits were reached: %s', e)
                yield from asyncio.sleep(60)
            except IOError as e:
                LOGGER.debug('Fetching users. Some troubles: %s', e)
                yield from asyncio.sleep(5)
            else:
                yield from asyncio.sleep(5)

    @asyncio.coroutine
    def _ensure_enough_users(self):
        users_to_follow_count = User.select().where(User.was_followed_at == None).count()
        LOGGER.debug('{0} users to follow found'.format(users_to_follow_count))
        if users_to_follow_count < USERS_LIMIT:
            last_users_to_follow_count = users_to_follow_count
            for user in User.select().where(User.were_followers_fetched == False).order_by(
                User.following_depth,
                User.created,
                ):
                following_depth = user.following_depth + 1
                try:
                    followers = yield from self._client.get_some_followers(user.instagram_id)
                except APINotAllowedError as e:
                    LOGGER.debug(
                        'Fetching users. Can\'t fetch followers of {0}: {1}'.format(
                            user.instagram_id,
                            e,
                            ),
                        )
                    user.were_followers_fetched = True
                    user.save()
                    yield from asyncio.sleep(.7)
                    continue
                user.were_followers_fetched = True
                user.save()
                LOGGER.debug(
                    'Fetching users. {0} followers of {1} were fetched'.format(
                        len(followers),
                        user.instagram_id,
                        ),
                    )
                for follower_id in followers:
                    try:
                        User.create(
                            instagram_id=follower_id,
                            following_depth=following_depth,
                            )
                    except peewee.IntegrityError:
                        pass
                    else:
                        users_to_follow_count += 1
                        self._stats_service.increment('users_to_follow_fetched')
                if users_to_follow_count >= USERS_LIMIT:
                    break
            LOGGER.debug(
                'Fetching users. %d users fetched.',
                users_to_follow_count - last_users_to_follow_count,
                )
