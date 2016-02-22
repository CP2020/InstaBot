import asyncio
import logging
import peewee
from .errors import APIError, APIJSONError, APILimitError, APINotAllowedError, ConfigurationError
from .stats_service import StatsService
from .user import User

LOGGER = logging.getLogger('instabot.user_service')

class UserService:
    def __init__(self, client, configuration):
        self._client = client
        self._stats_service = StatsService.get_instance()
        self._users_to_follow_cache_size = configuration.users_to_follow_cache_size
        if self._users_to_follow_cache_size == 0:
            raise ConfigurationError('Users to follow count was set to 0.')

    @asyncio.coroutine
    def run(self):
        while True:
            try:
                yield from self._ensure_enough_users()
            except APILimitError as e:
                LOGGER.debug('Instagram limits were reached. {}'.format(e))
            except (APIError, APIJSONError, APINotAllowedError) as e:
                LOGGER.debug(e)
                yield from asyncio.sleep(5)
            except (IOError, OSError) as e:
                LOGGER.warning(e)
                yield from asyncio.sleep(5)
            else:
                yield from asyncio.sleep(60)

    @asyncio.coroutine
    def _ensure_enough_users(self):
        users_to_follow_count = User.select().where(User.was_followed_at == None).count()
        LOGGER.debug('{0} users to follow found'.format(users_to_follow_count))
        if users_to_follow_count < self._users_to_follow_cache_size:
            last_users_to_follow_count = users_to_follow_count
            for user in User.select().where(User.were_followers_fetched == False).order_by(
                User.following_depth,
                User.created,
                ):
                following_depth = user.following_depth + 1
                try:
                    followers_json = yield from self._client.get_some_followers(user)
                except APINotAllowedError as e:
                    LOGGER.debug(
                        'Can\'t fetch followers of {0}: {1}'.format(
                            user.username,
                            e,
                            ),
                        )
                    user.were_followers_fetched = True
                    user.save()
                    continue
                user.were_followers_fetched = True
                user.save()
                LOGGER.debug(
                    '{0} followers of {1} were fetched'.format(
                        len(followers_json),
                        user.username,
                        ),
                    )
                for follower_json in followers_json:
                    try:
                        User.create(
                            instagram_id=follower_json['id'],
                            following_depth=following_depth,
                            username=follower_json['username'],
                            )
                    except peewee.IntegrityError:
                        pass
                    else:
                        users_to_follow_count += 1
                        self._stats_service.increment('users_to_follow_fetched')
                if users_to_follow_count >= USERS_TO_FOLLOW_COUNT_MIN:
                    break
            LOGGER.debug(
                '%d users fetched.',
                users_to_follow_count - last_users_to_follow_count,
                )
